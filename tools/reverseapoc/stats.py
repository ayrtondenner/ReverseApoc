"""`reverseapoc stats` (DEC-07, plan 07-37): the research numbers of Phases 6-7 from committed
data only, so CI can run it.

- The attempt log (progress/attempts.jsonl) is read through the driver's own validator
  (`driver.validate_record`, v1 and v2 lines together); a line that is not JSON, not an object
  or fails its version's schema is a StatsError naming its line number (exit 2).
- Every match is classed from git, not from gitignored files. Walking the commits that change
  config/<exe>/status.csv oldest first, a start that becomes `matched` in a commit is a match
  event, classed by that commit's trailers: `Matched-By: reverseapoc drive` without
  `Match-Hints:` is `unattended`; with `Match-Hints:` it is `human-hints` (the committed carrier
  of the owner's notes in manual packs, which CI cannot read); no driver `Matched-By` is
  `human-written`. A missing trailer is not an error. `Flags-Approved-By:` keeps the class
  `unattended` (research R4, D-13) and is reported as its own subset, never hidden in it.
- A function counts once in the class totals, by its latest event; one matched again after a
  revert is listed under re-matched, one no longer matched at the end of the history under
  reverted (and is not counted). AGT-11 is the unattended count.

Every git call passes `-c safe.directory=*` (ruling F13: the container's bind mount is owned by
another user); a git failure is a StatsError, never an empty history. In a shallow clone the
oldest listed commit's parent is missing, so its table is the baseline and gives no events.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from . import driver
from .mechanics import EXES

CLASSES = ("unattended", "human-hints", "human-written")
UNATTENDED, HUMAN_HINTS, HUMAN_WRITTEN = CLASSES
STATUS_PATHS = tuple(f"config/{exe}/status.csv" for exe in EXES)
_SAFE = ("-c", "safe.directory=*")  # ruling F13
_MATCHED_BY_KEY, _DRIVE = (part.strip() for part in driver.MATCHED_BY.split(":", 1))
_HINTS_KEY = "match-hints"
_FLAGS_KEY = "flags-approved-by"
_RECORD, _UNIT = "\x1e", "\x1f"  # the log format's record and field separators
_LOG_FORMAT = f"--format={_RECORD}%H{_UNIT}%P{_UNIT}%(trailers:only,unfold)"
_TOKENS = ("input", "output", "cache_read", "cache_creation")
_CENTS = Decimal("0.01")
_TENTH = Decimal("0.1")

Key = tuple[str, int]  # (exe, start)


class StatsError(ValueError):
    """The attempt log or the git history cannot be read."""


# ---- the attempt log ----


def read_attempts(path: Path) -> list[dict]:
    """Every record of an attempts.jsonl, each validated by the driver's own validator; a
    blank line is skipped (as the driver's reader does). A missing or unreadable log, a line
    that is not JSON, not an object or fails its schema is a StatsError naming the line."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise StatsError(f"cannot read the attempt log {path}: {exc}") from None
    records = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except ValueError as exc:
            raise StatsError(f"{path} line {number}: not JSON: {exc}") from None
        try:
            driver.validate_record(record)
        except (driver.RecordError, KeyError, TypeError) as exc:
            raise StatsError(f"{path} line {number}: {exc}") from None
        records.append(record)
    return records


# ---- match events from git ----


@dataclass(frozen=True)
class MatchEvent:
    commit: str  # the full hash
    exe: str
    start: int
    cls: str  # one of CLASSES
    flags_approved: bool  # the commit carries Flags-Approved-By (R4)

    def to_json(self) -> dict:
        return {"commit": self.commit, "exe": self.exe, "start": f"0x{self.start:08X}",
                "class": self.cls, "flags_approved": self.flags_approved}  # fmt: skip


@dataclass(frozen=True)
class History:
    events: tuple[MatchEvent, ...]  # oldest first
    matched: frozenset[Key]  # matched at the end of the walked history
    shallow: bool


def _git(repo: Path, *args: str) -> bytes:
    """`git -c safe.directory=* <args>` in `repo`; a non-zero exit is a StatsError."""
    done = driver.git_runner(Path(repo))([*_SAFE, *args])
    if done.returncode != 0:
        why = (done.stderr or b"").decode("utf-8", "replace").strip()
        raise StatsError(f"git {args[0]} failed in {repo}: {why}")
    return done.stdout or b""


def is_shallow(repo: Path) -> bool:
    """Whether `repo` is a shallow clone; a failing probe is a StatsError, never "shallow"."""
    answer = _git(repo, "rev-parse", "--is-shallow-repository").decode("ascii", "replace")
    if answer.strip() not in ("true", "false"):
        raise StatsError(f"git rev-parse --is-shallow-repository answered {answer.strip()!r}")
    return answer.strip() == "true"


def _has_commits(repo: Path) -> bool:
    _git(repo, "rev-parse", "--git-dir")  # not a repository: a StatsError
    done = driver.git_runner(Path(repo))([*_SAFE, "rev-parse", "--verify", "--quiet", "HEAD"])
    return done.returncode == 0


def classify(trailers: Iterable[tuple[str, str]]) -> tuple[str, bool]:
    """A match commit's class and whether it is flag-approved, from its trailers (key in any
    case, value as written)."""
    pairs = [(key.strip().lower(), value.strip()) for key, value in trailers]
    keys = {key for key, _ in pairs}
    driven = (_MATCHED_BY_KEY.lower(), _DRIVE) in pairs
    if not driven:
        return HUMAN_WRITTEN, _FLAGS_KEY in keys
    return (HUMAN_HINTS if _HINTS_KEY in keys else UNATTENDED), _FLAGS_KEY in keys


def _trailers(text: str) -> list[tuple[str, str]]:
    out = []
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip():
            out.append((key, value))
    return out


def _commits(repo: Path) -> list[tuple[str, str | None, list[tuple[str, str]]]]:
    """(hash, parent or None, trailers) of every non-merge commit changing a status.csv,
    oldest first."""
    raw = _git(repo, "log", "--reverse", "--no-merges", _LOG_FORMAT, "--", *STATUS_PATHS)
    out = []
    for chunk in raw.decode("utf-8", "replace").split(_RECORD):
        if not chunk.strip():
            continue
        commit, parents, trailers = (chunk.split(_UNIT, 2) + ["", ""])[:3]
        parent = parents.split()[0] if parents.split() else None
        out.append((commit.strip(), parent, _trailers(trailers)))
    return out


def _blobs(repo: Path, rev: str) -> dict[str, str]:
    """The blob id of each status.csv path at `rev` (absent paths left out)."""
    raw = _git(repo, "ls-tree", "-z", rev, "--", *STATUS_PATHS).decode("utf-8", "replace")
    out = {}
    for entry in raw.split("\0"):
        meta, _, path = entry.partition("\t")
        if path:
            out[path] = meta.split()[2]
    return out


def _matched(repo: Path, blob: str | None) -> frozenset[int]:
    if blob is None:
        return frozenset()
    return driver.matched_starts(_git(repo, "cat-file", "blob", blob))


def history(repo: Path) -> History:
    """Every match event of the status.csv history with the matched set it ends with."""
    repo = Path(repo)
    shallow = is_shallow(repo)
    if not _has_commits(repo):
        return History((), frozenset(), shallow)
    events: list[MatchEvent] = []
    current: dict[str, frozenset[int]] = {}
    for commit, parent, trailers in _commits(repo):
        after = _blobs(repo, commit)
        before = _blobs(repo, parent) if parent else {}
        cls, flagged = classify(trailers)
        for exe, path in zip(EXES, STATUS_PATHS, strict=True):
            if parent and after.get(path) == before.get(path):
                continue
            now = _matched(repo, after.get(path))
            current[exe] = now
            if parent is None and shallow:
                continue  # the shallow boundary: its table is the baseline, not a match
            new = now - _matched(repo, before.get(path))
            events.extend(MatchEvent(commit, exe, start, cls, flagged) for start in sorted(new))
    matched = frozenset((exe, start) for exe, starts in current.items() for start in starts)
    return History(tuple(events), matched, shallow)


def match_history(repo: Path) -> list[MatchEvent]:
    """The match events of `repo`'s status.csv history, oldest first (DEC-07)."""
    return list(history(repo).events)


# ---- the report ----


def _dec(value: object) -> Decimal:
    """A log number as an exact decimal of its written form, so sums keep full precision."""
    return Decimal(str(value))


def money(value: Decimal) -> str:
    """A cost shown to 2 decimals, round-half-even (0.125 -> 0.12, 0.135 -> 0.14)."""
    return str(value.quantize(_CENTS, rounding=ROUND_HALF_EVEN))


def tenth(value: Decimal) -> str:
    """A percentage or per-match figure shown to 1 decimal, round-half-even."""
    return str(value.quantize(_TENTH, rounding=ROUND_HALF_EVEN))


def _attempts(records: Sequence[Mapping]) -> list[Mapping]:
    return [r for r in records if r["kind"] == driver.KIND_ATTEMPT]


def _counted(hist: History) -> dict[Key, MatchEvent]:
    """Each function still matched, by its latest event."""
    latest: dict[Key, MatchEvent] = {}
    for event in hist.events:
        latest[(event.exe, event.start)] = event
    return {key: event for key, event in latest.items() if key in hist.matched}


def _key_text(key: Key) -> str:
    return f"{key[0]} 0x{key[1]:08X}"


def _sums(attempts: Sequence[Mapping]) -> dict:
    return {
        "turns": sum(r["turns"] for r in attempts),
        "tokens": {k: sum(r["tokens"][k] for r in attempts) for k in _TOKENS},
        "cost_usd": sum((_dec(r["cost_usd"]) for r in attempts), Decimal(0)),
        "seconds": sum((_dec(r["seconds"]) for r in attempts), Decimal(0)),
    }


@dataclass(frozen=True)
class Report:
    data: dict

    @property
    def unattended(self) -> int:
        return self.data["classes"][UNATTENDED]

    def to_json(self) -> str:
        return json.dumps(self.data, indent=2, sort_keys=True)

    def format(self) -> str:
        d = self.data
        classes = d["classes"]
        lines = [f"matches classed from git trailers: {sum(classes.values())} functions"]
        lines.append(f"  unattended: {classes[UNATTENDED]} (flag-approved {d['flags_approved']})")
        lines.append(f"  human-hints: {classes[HUMAN_HINTS]}")
        lines.append(f"  human-written: {classes[HUMAN_WRITTEN]}")
        lines.append(f"  re-matched: {', '.join(d['re_matched']) or 'none'}")
        lines.append(f"  reverted: {', '.join(d['reverted']) or 'none'}")
        if d["shallow"]:
            lines.append("  (shallow clone: matches before the clone's oldest commit are not seen)")
        a, t = d["attempts"], d["totals"]
        lines.append(f"attempt log: {a['records']} records (v1 {a['v1_records']}, "
                     f"v2 {a['v2_records']}), {a['sessions']} sessions")  # fmt: skip
        tokens = ", ".join(f"{k} {t['tokens'][k]}" for k in _TOKENS)
        lines.append(f"totals: turns {t['turns']}, tokens {tokens}, cost ${t['cost_usd']}, "
                     f"seconds {t['seconds']}")  # fmt: skip
        return "\n".join(lines)


def build_report(records: Sequence[Mapping], hist: History) -> Report:
    attempts = _attempts(records)
    counted = _counted(hist)
    per_key: dict[Key, int] = {}
    for event in hist.events:
        per_key[(event.exe, event.start)] = per_key.get((event.exe, event.start), 0) + 1
    ever = sorted(per_key)
    sums = _sums(attempts)
    v2 = sum("schema" in r for r in records)
    data = {
        "classes": {cls: sum(e.cls == cls for e in counted.values()) for cls in CLASSES},
        "flags_approved": sum(e.cls == UNATTENDED and e.flags_approved
                              for e in counted.values()),  # fmt: skip
        "events": [e.to_json() for e in hist.events],
        "re_matched": [_key_text(k) for k in ever if per_key[k] > 1 and k in counted],
        "reverted": [_key_text(k) for k in ever if k not in counted],
        "shallow": hist.shallow,
        "attempts": {"records": len(records), "v1_records": len(records) - v2, "v2_records": v2,
                     "sessions": len(attempts)},  # fmt: skip
        "totals": {"turns": sums["turns"], "tokens": sums["tokens"],
                   "cost_usd": money(sums["cost_usd"]),
                   "seconds": tenth(sums["seconds"])},  # fmt: skip
    }
    return Report(data)


def collect(repo: Path, log: Path, config: Path) -> Report:
    """The report of `log` and `repo`'s history (`config`: the config/ directory)."""
    del config  # the size and tier tables join here in the metrics (Task 2)
    return build_report(read_attempts(log), history(repo))
