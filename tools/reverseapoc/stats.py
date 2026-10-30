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
  revert is listed under re-matched, one not matched in HEAD's status tables under
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
from .functions import FunctionsError, read_functions_csv
from .mechanics import EXES, MEMBERS_CSV, MechanicsError, read_members

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

# DEC-07's function-size buckets [low, high) in bytes; None: no upper bound
SIZE_BUCKETS = ((0, 64), (64, 256), (256, 1024), (1024, None))
UNKNOWN = "unknown"  # the size bucket of a function functions.csv does not hold
NO_TIER = "none"  # the tier of a matched function the members file does not hold

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
    matched: frozenset[Key]  # matched in HEAD's status tables
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
    oldest first in topological order (never a child before its parent, whatever the dates;
    fix round 1). A merge brings no match of its own: its branches' commits are walked."""
    raw = _git(repo, "log", "--reverse", "--topo-order", "--no-merges", _LOG_FORMAT, "--",
               *STATUS_PATHS)  # fmt: skip
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
    """Every match event of the status.csv history, with the matched set of HEAD's own
    status tables (fix round 1: the last walked commit is not HEAD once branches merge)."""
    repo = Path(repo)
    shallow = is_shallow(repo)
    if not _has_commits(repo):
        return History((), frozenset(), shallow)
    events: list[MatchEvent] = []
    for commit, parent, trailers in _commits(repo):
        if parent is None and shallow:
            continue  # the shallow boundary: its table is the baseline, not a match
        after = _blobs(repo, commit)
        before = _blobs(repo, parent) if parent else {}
        cls, flagged = classify(trailers)
        for exe, path in zip(EXES, STATUS_PATHS, strict=True):
            if parent and after.get(path) == before.get(path):
                continue
            new = _matched(repo, after.get(path)) - _matched(repo, before.get(path))
            events.extend(MatchEvent(commit, exe, start, cls, flagged) for start in sorted(new))
    head = _blobs(repo, "HEAD")
    matched = frozenset((exe, start) for exe, path in zip(EXES, STATUS_PATHS, strict=True)
                        for start in _matched(repo, head.get(path)))  # fmt: skip
    return History(tuple(events), matched, shallow)


def match_history(repo: Path) -> list[MatchEvent]:
    """The match events of `repo`'s status.csv history, oldest first (DEC-07)."""
    return list(history(repo).events)


# ---- the inputs the metrics join: sizes and tiers ----


def read_sizes(config: Path) -> dict[Key, int]:
    """Each function's size in bytes from config/<exe>/functions.csv (a missing file: none)."""
    sizes: dict[Key, int] = {}
    for exe in EXES:
        path = Path(config) / exe / "functions.csv"
        if not path.is_file():
            continue
        try:
            rows = read_functions_csv(path)
        except (FunctionsError, OSError) as exc:
            raise StatsError(f"{path}: {exc}") from None
        sizes.update(((exe, row.start), row.end - row.start) for row in rows)
    return sizes


def read_tiers(config: Path) -> dict[Key, int] | None:
    """Each member's lowest tier from config/mechanics-members.csv; None without the file."""
    path = Path(config) / MEMBERS_CSV
    if not path.is_file():
        return None
    try:
        rows = read_members(path)
    except (MechanicsError, OSError) as exc:
        raise StatsError(f"{path}: {exc}") from None
    return {(row.exe, row.address): min(row.tiers) for row in rows}


# ---- the report ----


def size_bucket(size: int) -> int:
    """The index of the SIZE_BUCKETS range [low, high) holding `size` (DEC-07 boundary)."""
    for index, (low, high) in enumerate(SIZE_BUCKETS):
        if low <= size and (high is None or size < high):
            return index
    raise StatsError(f"a function size of {size} bytes is in no bucket")


def _bucket_label(index: int) -> str:
    low, high = SIZE_BUCKETS[index]
    return f"[{low}, {'inf' if high is None else high})"


def _dec(value: object) -> Decimal:
    """A log number as an exact decimal of its written form, so sums keep full precision."""
    return Decimal(str(value))


def money(value: Decimal) -> str:
    """A cost shown to 2 decimals, round-half-even (0.125 -> 0.12, 0.135 -> 0.14)."""
    return str(value.quantize(_CENTS, rounding=ROUND_HALF_EVEN))


def tenth(value: Decimal) -> str:
    """A percentage or per-match figure shown to 1 decimal, round-half-even."""
    return str(value.quantize(_TENTH, rounding=ROUND_HALF_EVEN))


def _rate(matched: int, attempted: int) -> str | None:
    return tenth(Decimal(matched) * 100 / attempted) if attempted else None


def _key(record: Mapping) -> Key:
    return record["exe"], int(record["start"], 16)


def _key_text(key: Key) -> str:
    return f"{key[0]} 0x{key[1]:08X}"


def _sums(attempts: Sequence[Mapping]) -> dict:
    return {
        "turns": sum(r["turns"] for r in attempts),
        "tokens": {k: sum(r["tokens"][k] for r in attempts) for k in _TOKENS},
        "cost_usd": sum((_dec(r["cost_usd"]) for r in attempts), Decimal(0)),
        "seconds": sum((_dec(r["seconds"]) for r in attempts), Decimal(0)),
    }


def _counted(hist: History) -> dict[Key, MatchEvent]:
    """Each function still matched, by its latest event (DEC-07 adjacency)."""
    latest: dict[Key, MatchEvent] = {}
    for event in hist.events:
        latest[(event.exe, event.start)] = event
    return {key: event for key, event in latest.items() if key in hist.matched}


def _classes(events: Iterable[MatchEvent]) -> dict[str, int]:
    events = list(events)
    return {cls: sum(e.cls == cls for e in events) for cls in CLASSES}


def _by_size(attempted: set[Key], matched: set[Key], sizes: Mapping[Key, int]) -> list[dict]:
    """Attempted and matched functions per size bucket, an `unknown` bucket for functions
    functions.csv does not size (only when there are some)."""
    groups: dict[str, list[Key]] = {_bucket_label(i): [] for i in range(len(SIZE_BUCKETS))}
    for key in sorted(attempted):
        label = _bucket_label(size_bucket(sizes[key])) if key in sizes else UNKNOWN
        groups.setdefault(label, []).append(key)
    return [{"bucket": label, "attempted": len(keys),
             "matched": sum(k in matched for k in keys),
             "rate_percent": _rate(sum(k in matched for k in keys), len(keys))}
            for label, keys in groups.items()]  # fmt: skip


def _per_match(matching: Sequence[Mapping], matched_count: int) -> dict:
    """Attempts, turns, tokens, cost and seconds per matched function (None without one)."""
    sums = _sums(matching)
    if not matched_count:
        return {"matched_functions": 0, "attempts": None, "turns": None,
                "tokens": dict.fromkeys(_TOKENS), "cost_usd": None,
                "seconds": None}  # fmt: skip
    per = Decimal(matched_count)
    return {"matched_functions": matched_count,
            "attempts": tenth(Decimal(len(matching)) / per),
            "turns": tenth(Decimal(sums["turns"]) / per),
            "tokens": {k: tenth(Decimal(sums["tokens"][k]) / per) for k in _TOKENS},
            "cost_usd": money(sums["cost_usd"] / per),
            "seconds": tenth(sums["seconds"] / per)}  # fmt: skip


def _share(records: Sequence[Mapping]) -> dict:
    return {"sessions": len(records),
            "matched": sum(r["outcome"] == driver.MATCHED for r in records),
            "cost_usd": money(sum((_dec(r["cost_usd"]) for r in records),
                                  Decimal(0)))}  # fmt: skip


def _split(v2: Sequence[Mapping], field: str, v1_count: int) -> dict:
    """v2 sessions, matches and cost per `field` value; v1 lines lack the field (n/a)."""
    names = sorted({r[field] for r in v2})
    return {"v1_records": v1_count,
            "kinds" if field == "session" else "models": {
                name: _share([r for r in v2 if r[field] == name]) for name in names}}  # fmt: skip


def _v2_sum(v2: Sequence[Mapping], value, v1_count: int) -> dict:
    """A v2-only figure: its sum over v2 records, None when there are none (n/a for v1)."""
    return {"value": sum(map(value, v2)) if v2 else None, "v1_records": v1_count}


def _by_tier(counted: Mapping[Key, MatchEvent], tiers: Mapping[Key, int] | None) -> dict | None:
    """The counted matches per class by each function's lowest tier (`none`: no member)."""
    if tiers is None:
        return None
    out: dict[str, dict[str, int]] = {}
    for key, event in sorted(counted.items()):
        label = str(tiers[key]) if key in tiers else NO_TIER
        out.setdefault(label, dict.fromkeys(CLASSES, 0))[event.cls] += 1
    return out


def build_report(records: Sequence[Mapping], hist: History, sizes: Mapping[Key, int],
                 tiers: Mapping[Key, int] | None) -> Report:  # fmt: skip
    """The DEC-07 report of validated `records` and a match history."""
    attempts = [r for r in records if r["kind"] == driver.KIND_ATTEMPT]
    v1 = [r for r in attempts if "schema" not in r]
    v2 = [r for r in attempts if "schema" in r]
    matching = [r for r in attempts if r.get("session", driver.MATCHING) == driver.MATCHING]
    counted = _counted(hist)
    seen: dict[Key, int] = {}
    for event in hist.events:
        seen[(event.exe, event.start)] = seen.get((event.exe, event.start), 0) + 1
    reverted = {key for key in seen if key not in counted}
    logged = {_key(r) for r in matching if r["outcome"] == driver.MATCHED}
    matched = (logged - reverted) | set(counted)
    attempted = {_key(r) for r in matching}
    sums = _sums(attempts)
    data = {
        "classes": _classes(counted.values()),
        "flags_approved": sum(e.cls == UNATTENDED and e.flags_approved
                              for e in counted.values()),  # fmt: skip
        "events": [e.to_json() for e in hist.events],
        "re_matched": [_key_text(k) for k in sorted(seen) if seen[k] > 1 and k in counted],
        "reverted": [_key_text(k) for k in sorted(reverted)],
        "shallow": hist.shallow,
        "attempts": {"records": len(records), "v1_records": sum("schema" not in r for r in records),
                     "v2_records": sum("schema" in r for r in records),
                     "sessions": len(attempts),
                     "matching_sessions": len(matching)},  # fmt: skip
        "totals": {"turns": sums["turns"], "tokens": sums["tokens"],
                   "cost_usd": money(sums["cost_usd"]),
                   "seconds": tenth(sums["seconds"])},  # fmt: skip
        "by_size": _by_size(attempted, matched, sizes),
        "per_match": _per_match(matching, len(attempted & matched)),
        "regressions_stopped": _v2_sum(
            v2, lambda r: r["gate"]["regressions"] if r["gate"] else 0, len(v1)),
        "hook_blocks": _v2_sum(v2, lambda r: r["hook_blocks"], len(v1)),
        "by_model": _split(v2, "model_requested", len(v1)),
        "by_session": _split(v2, "session", len(v1)),
        "by_tier": _by_tier(counted, tiers),
    }  # fmt: skip
    return Report(data)


def _na(figure: Mapping) -> str:
    """A v2-only figure as text: `n/a for v1` without v2 records."""
    if figure["value"] is None:
        return "n/a for v1" if figure["v1_records"] else "none"
    note = f" (n/a for the {figure['v1_records']} v1 records)" if figure["v1_records"] else ""
    return f"{figure['value']}{note}"


def _split_lines(title: str, split: Mapping, shares: Mapping) -> list[str]:
    if not shares:
        return [f"{title}: {'n/a for v1' if split['v1_records'] else 'none'}"]
    note = f" (n/a for the {split['v1_records']} v1 records)" if split["v1_records"] else ""
    return [f"{title}:{note}"] + [
        f"  {name}: sessions {s['sessions']}, matched {s['matched']}, cost ${s['cost_usd']}"
        for name, s in shares.items()]  # fmt: skip


def _class_lines(d: Mapping) -> list[str]:
    classes = d["classes"]
    lines = [f"matches classed from git trailers: {sum(classes.values())} functions",
             f"  unattended: {classes[UNATTENDED]} (flag-approved {d['flags_approved']})",
             f"  human-hints: {classes[HUMAN_HINTS]}",
             f"  human-written: {classes[HUMAN_WRITTEN]}",
             f"  re-matched: {', '.join(d['re_matched']) or 'none'}",
             f"  reverted: {', '.join(d['reverted']) or 'none'}"]  # fmt: skip
    if d["shallow"]:
        lines.append("  (shallow clone: matches before the clone's oldest commit are not seen)")
    return lines


def _metric_lines(d: Mapping) -> list[str]:
    a, t, per = d["attempts"], d["totals"], d["per_match"]
    tokens = ", ".join(f"{k} {t['tokens'][k]}" for k in _TOKENS)
    lines = [f"attempt log: {a['records']} records (v1 {a['v1_records']}, v2 {a['v2_records']}),"
             f" {a['sessions']} sessions ({a['matching_sessions']} matching)",
             f"totals: turns {t['turns']}, tokens {tokens}, cost ${t['cost_usd']}, "
             f"seconds {t['seconds']}", "match rate by function size (bytes):"]  # fmt: skip
    lines += [f"  {b['bucket']}: {b['matched']} of {b['attempted']} attempted matched "
              f"({'n/a' if b['rate_percent'] is None else b['rate_percent'] + '%'})"
              for b in d["by_size"]]  # fmt: skip
    if per["matched_functions"]:
        tokens = ", ".join(f"{k} {per['tokens'][k]}" for k in _TOKENS)
        lines.append(f"per matched function ({per['matched_functions']}): attempts "
                     f"{per['attempts']}, turns {per['turns']}, tokens {tokens}, cost "
                     f"${per['cost_usd']}, seconds {per['seconds']}")  # fmt: skip
    else:
        lines.append("per matched function: no attempted function is matched")
    lines.append(f"regressions the gate stopped: {_na(d['regressions_stopped'])}")
    lines.append(f"hook blocks: {_na(d['hook_blocks'])}")
    return lines


def _tier_lines(by_tier: Mapping | None) -> list[str]:
    if by_tier is None:
        return [f"per tier: no {MEMBERS_CSV}"]
    return ["per tier (lowest tier of the function):"] + [
        f"  {label}: " + ", ".join(f"{cls} {counts[cls]}" for cls in CLASSES)
        for label, counts in sorted(by_tier.items())]  # fmt: skip


@dataclass(frozen=True)
class Report:
    data: dict

    @property
    def unattended(self) -> int:
        """AGT-11's count: functions whose latest match is unattended (flag-approved ones
        included, R4)."""
        return self.data["classes"][UNATTENDED]

    def to_json(self) -> str:
        """The report as JSON with sorted keys, so two runs give identical bytes."""
        return json.dumps(self.data, indent=2, sort_keys=True)

    def format(self) -> str:
        d = self.data
        return "\n".join([
            *_class_lines(d), *_metric_lines(d),
            *_split_lines("per model", d["by_model"], d["by_model"]["models"]),
            *_split_lines("per session kind", d["by_session"], d["by_session"]["kinds"]),
            *_tier_lines(d["by_tier"]),
        ])  # fmt: skip


def collect(repo: Path, log: Path, config: Path) -> Report:
    """The report of `log`, `repo`'s history and `config`'s sizes and tiers."""
    records = read_attempts(log)
    return build_report(records, history(repo), read_sizes(config), read_tiers(config))
