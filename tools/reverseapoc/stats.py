"""`reverseapoc stats` (DEC-07, plan 07-37): the research numbers of Phases 6-7 from committed
data only, so CI can run it.

- The attempt log (progress/attempts.jsonl) is read through the driver's own validator
  (`driver.validate_record`, v1, v2 and v3 lines together); a line that is not JSON, not an
  object or fails its version's schema is a StatsError naming its line number (exit 2).
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

Quick 261110-f30 (spike 012, owner ruling 2026-11-10): `stats --run` adds the comparison table,
one row per arm (`arm_key`) over every selected run and both EXEs, with driver.STRATA's three
size groups and a total as columns (an `unknown` column only when a function has no
functions.csv size). A cell holds the functions attempted and exact (held exact or matched),
sessions, turns, wall time, tokens, the API-equivalent USD (the tokens at the arm's list price,
backends.Arm.list_price), the real paid USD (0 on a subscription or free arm, the
API-equivalent on a metered one, backends.Arm.billing), the per-try rates over the attempts'
saved checks.jsonl (causes' rule) and exact per API-equivalent $, per wall hour and per million
tokens. The recorded `cost_usd` is never read by it: it is 0 on every subscription arm. A
MATCHED landing counts as matched for its own arm and for every arm that held the function
exact among the selected records (`_holders`), in by_arm, by_model_size and the comparison; the
function still counts once in the matched totals and per_match.
"""

from __future__ import annotations

import json
import math
import re
import tomllib
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction
from pathlib import Path
from statistics import NormalDist

from . import backends, driver
from .functions import FunctionsError, read_functions_csv
from .mechanics import EXES, MEMBERS_CSV, MechanicsError, read_members
from .streamjson import TOKENS_PER_MTOK

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
TOTAL = "total"  # the comparison's column over every size (quick 261110-f30)
_MS_PER_SECOND = 1000
_MS_PER_MINUTE = 60 * _MS_PER_SECOND
_MS_PER_HOUR = 60 * _MS_PER_MINUTE
_PER_TRY = (("build_failure", "build failure"), ("mismatch", "mismatch"), ("match", "match"))
_PAID_WORDS = {
    backends.SUBSCRIPTION: "real paid $0.00: a subscription arm (the Claude Code login, ChatGPT "
                           "Plus or Google AI Plus) pays no per-token price",
    backends.FREE: "real paid $0.00: a local arm pays nothing",
    backends.METERED: "real paid: its tokens at its list price (a metered arm)",
}  # fmt: skip
_NO_PRICE = "no list price, so no API-equivalent or real paid figure"

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


# ---- todo errata-ledger: corrections to committed records ----

ERRATA = "errata.toml"  # next to the attempt log: progress/errata.toml for the committed one
_ERRATUM_KEYS = ("run", "field", "old", "new", "reason", "date")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class Erratum:
    """One `[[correction]]` of the ledger: in every record of `run` whose dotted `field`
    (`cost_usd`, `check.runs`) holds `old` (same type, same value), it becomes `new`."""

    run: str
    field: str
    old: object
    new: object
    reason: str
    date: str  # YYYY-MM-DD

    def to_json(self, records: int) -> dict:
        return {"run": self.run, "field": self.field, "old": self.old, "new": self.new,
                "reason": self.reason, "date": self.date, "records": records}  # fmt: skip


def _erratum(path: Path, number: int, entry: object) -> Erratum:
    where = f"{path} correction {number}"
    if not isinstance(entry, dict):
        raise StatsError(f"{where}: not a table")
    extra, missing = set(entry) - set(_ERRATUM_KEYS), set(_ERRATUM_KEYS) - set(entry)
    if extra or missing:
        raise StatsError(f"{where}: keys must be {', '.join(_ERRATUM_KEYS)}; extra "
                         f"{sorted(extra)}, missing {sorted(missing)}")  # fmt: skip
    for key in ("run", "field", "reason"):
        if not isinstance(entry[key], str) or not entry[key].strip():
            raise StatsError(f"{where}: {key} must be a non-empty string")
    if not isinstance(entry["date"], str) or not _DATE.fullmatch(entry["date"]):
        raise StatsError(f"{where}: date must be a \"YYYY-MM-DD\" string")
    for key in ("old", "new"):
        try:
            json.dumps(entry[key])
        except (TypeError, ValueError):
            raise StatsError(f"{where}: {key} must be a JSON value (no TOML date)") from None
    return Erratum(**entry)


def read_errata(path: Path) -> list[Erratum]:
    """The ledger's corrections in file order; a missing ledger has none. TOML that does not
    parse, or a correction without exactly _ERRATUM_KEYS, is a StatsError naming it."""
    path = Path(path)
    if not path.is_file():
        return []
    try:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise StatsError(f"{path}: not TOML: {exc}") from None
    extra = set(doc) - {"correction"}
    if extra or not isinstance(doc.get("correction", []), list):
        raise StatsError(f"{path}: only [[correction]] tables are allowed (found {sorted(doc)})")
    return [_erratum(path, n, e) for n, e in enumerate(doc.get("correction", []), start=1)]


def _same(a: object, b: object) -> bool:
    return type(a) is type(b) and a == b


def _holder(record: dict, parents: Sequence[str]) -> dict | None:
    """The mapping the dotted field's last part lives in, or None when the path is absent."""
    holder: object = record
    for part in parents:
        holder = holder.get(part) if isinstance(holder, dict) else None
    return holder if isinstance(holder, dict) else None


def _corrected(record: dict, erratum: Erratum) -> dict | None:
    """A copy of the record with the erratum applied, or None when it does not apply to it
    (the logged record itself is never changed)."""
    *parents, last = erratum.field.split(".")
    if record["run"] != erratum.run:
        return None
    holder = _holder(record, parents)
    if holder is None or last not in holder or not _same(holder[last], erratum.old):
        return None
    out = json.loads(json.dumps(record))  # a deep copy, only of a record that changes
    _holder(out, parents)[last] = erratum.new
    return out


def apply_errata(records: Sequence[dict], errata: Sequence[Erratum]
                 ) -> tuple[list[dict], list[tuple[Erratum, int]]]:  # fmt: skip
    """The records with every correction applied in ledger order, and each correction with
    the number of records it changed. A correction that changes no record (a stale ledger) or
    leaves a record failing its schema is a StatsError."""
    out, applied = list(records), []
    for erratum in errata:
        changed = 0
        for index, record in enumerate(out):
            fixed = _corrected(record, erratum)
            if fixed is None:
                continue
            try:
                driver.validate_record(fixed)
            except (driver.RecordError, KeyError, TypeError) as exc:
                raise StatsError(f"{ERRATA}: {erratum.run} {erratum.field}: the corrected "
                                 f"record fails its schema: {exc}") from None  # fmt: skip
            out[index], changed = fixed, changed + 1
        if not changed:
            raise StatsError(f"{ERRATA}: {erratum.run} {erratum.field} = {erratum.old!r} "
                             "changes no record")  # fmt: skip
        applied.append((erratum, changed))
    return out, applied


def _errata_lines(errata: Sequence[Mapping]) -> list[str]:
    if not errata:
        return ["errata applied: none"]
    return [f"errata applied ({ERRATA} next to the attempt log):"] + [
        f"  {e['run']} {e['field']}: {e['old']!r} -> {e['new']!r} on {e['records']} "
        f"record{'s' if e['records'] != 1 else ''} ({e['date']}): {e['reason']}"
        for e in errata]  # fmt: skip


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
        groups.setdefault(_size_label(key, sizes), []).append(key)
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


def _size_label(key: Key, sizes: Mapping[Key, int]) -> str:
    """The SIZE_BUCKETS label of a function, `unknown` when functions.csv does not size it."""
    return _bucket_label(size_bucket(sizes[key])) if key in sizes else UNKNOWN


_LABEL_ORDER = (*(_bucket_label(i) for i in range(len(SIZE_BUCKETS))), UNKNOWN)
_MODEL_SIZE_COUNTS = ("attempted", "matched", "hold_exact")


def arm_key(record: Mapping) -> str:
    """Phase 07.2 D-22: the arm of an attempt or landing record, `backend/harness/model`: the
    requested model (a landing's `model`, the held attempt's requested model). v1 and v2
    records name no backend or harness: they ran on the Claude Code login
    (`anthropic/claude/<model>`, a v1 record's model being its init model)."""
    model = record.get("model_requested", record.get("model")) or UNKNOWN
    backend = record.get("backend", driver.DEFAULT_BACKEND)
    return f"{backend}/{record.get('harness', driver.HARNESSES[0])}/{model}"


def _holders(matching: Sequence[Mapping]) -> dict[Key, set[str]]:
    """Quick 261110-f30: the arm (`arm_key`) of every HOLD_EXACT attempt, per function."""
    out: dict[Key, set[str]] = {}
    for r in matching:
        if r["outcome"] == driver.HOLD_EXACT:
            out.setdefault(_key(r), set()).add(arm_key(r))
    return out


def _landing_arms(landing: Mapping, holders: Mapping[Key, set[str]]) -> set[str]:
    """The arms a MATCHED landing is credited to (owner ruling 2026-11-10): its own and every
    arm that held the function exact among the selected records, as the commit credits them
    (`drive --land-held`)."""
    return {arm_key(landing), *holders.get(_key(landing), set())}


def _matched_by_arm(matching: Sequence[Mapping], landed: Sequence[Mapping]) -> dict[str, set]:
    """The functions each arm matched: its MATCHED attempts and the MATCHED landings credited
    to it (quick 261110-f30: to the landing's arm and to every holder, `_landing_arms`)."""
    out: dict[str, set[Key]] = {}
    for r in matching:
        if r["outcome"] == driver.MATCHED:
            out.setdefault(arm_key(r), set()).add(_key(r))
    holders = _holders(matching)
    for r in landed:
        if r["outcome"] != driver.MATCHED:
            continue
        for arm in _landing_arms(r, holders):
            out.setdefault(arm, set()).add(_key(r))
    return out


def _by_arm(matching: Sequence[Mapping], landed: Sequence[Mapping]) -> dict:
    """Phase 07.2 D-22 (`stats --run` splits by arm): per arm (`arm_key`), the distinct
    functions attempted, matched and held exact, and the tokens and cost of its attempts."""
    groups: dict[str, list[Mapping]] = {}
    for r in matching:
        groups.setdefault(arm_key(r), []).append(r)
    matched = _matched_by_arm(matching, landed)
    out = {}
    for arm in sorted({*groups, *matched}):
        records = groups.get(arm, [])
        sums = _sums(records)
        out[arm] = {"attempted": len({_key(r) for r in records}),
                    "matched": len(matched.get(arm, ())),
                    "hold_exact": len({_key(r) for r in records
                                       if r["outcome"] == driver.HOLD_EXACT}),
                    "tokens": sums["tokens"], "cost_usd": money(sums["cost_usd"])}  # fmt: skip
    return out


def _by_model_size(matching: Sequence[Mapping], landed: Sequence[Mapping],
                   sizes: Mapping[Key, int]) -> dict:  # fmt: skip
    """Phase 07.2 D-16: per requested model (v2 and v3 records) and size bucket, the distinct
    functions attempted, matched (a MATCHED attempt, or a MATCHED landing credited to that
    model) and held exact (a HOLD_EXACT attempt); only the buckets that occur, smallest
    first. D-22: the rows are arms (`arm_key`), so one model on two backends is two rows.
    Quick 261110-f30: a MATCHED landing is matched for every arm `_landing_arms` names."""
    cells: dict[str, dict[str, dict[str, set[Key]]]] = {}

    def add(arm: str, key: Key, count: str) -> None:
        buckets = cells.setdefault(arm, {})
        cell = buckets.setdefault(_size_label(key, sizes), {c: set() for c in _MODEL_SIZE_COUNTS})
        cell[count].add(key)

    for r in matching:
        if "model_requested" not in r:
            continue  # a v1 record names no requested model
        add(arm_key(r), _key(r), "attempted")
        if r["outcome"] in (driver.MATCHED, driver.HOLD_EXACT):
            add(arm_key(r), _key(r),
                "matched" if r["outcome"] == driver.MATCHED else "hold_exact")  # fmt: skip
    holders = _holders(matching)
    for r in landed:
        if r["outcome"] != driver.MATCHED:
            continue
        for arm in _landing_arms(r, holders):
            add(arm, _key(r), "matched")
    return {model: {label: {c: len(buckets[label][c]) for c in _MODEL_SIZE_COUNTS}
                    for label in sorted(buckets, key=_LABEL_ORDER.index)}
            for model, buckets in sorted(cells.items())}  # fmt: skip


# ---- quick 261110-f30 (spike 012): the comparison table of `stats --run` ----


def _stratum(key: Key, sizes: Mapping[Key, int]) -> str:
    """The driver.STRATA_NAMES group [low, high) holding the function's size (high None: no
    bound), UNKNOWN when functions.csv does not size it."""
    if key not in sizes:
        return UNKNOWN
    for name, (low, high) in zip(driver.STRATA_NAMES, driver.STRATA, strict=True):
        if low <= sizes[key] and (high is None or sizes[key] < high):
            return name
    raise StatsError(f"a function size of {sizes[key]} bytes is in no size group")


def _in(column: str, key: Key, sizes: Mapping[Key, int]) -> bool:
    return column == TOTAL or _stratum(key, sizes) == column


def _wall_ms(record: Mapping) -> tuple[int, bool]:
    """The session's wall time in ms and whether it is estimated: `duration_ms`, or the
    record's `seconds` when that is null (a timeout) or absent (v1, v2)."""
    ms = record.get("duration_ms")
    if ms is None:
        return int(round(_dec(record["seconds"]) * _MS_PER_SECOND)), True
    return ms, False


def _attempt_dir(repo: Path | None, record: Mapping) -> Path | None:
    """<repo>/build/driver/<run>/<exe>/<function>/attempt-<n>; None without a repo or for a
    run of "." or ".." (flags._run_dirs' rule). The fields passed driver.validate_record."""
    if repo is None or record["run"] in (".", ".."):
        return None
    return (Path(repo) / driver.DRIVER_DIR / record["run"] / record["exe"] / record["function"]
            / f"attempt-{record['attempt']}")  # fmt: skip


def _per_try(records: Sequence[Mapping], repo: Path | None, column: str) -> dict:
    """causes' per-try counters and rates over the records' saved checks.jsonl, and `repeats`:
    the checks the wrapper answered from an earlier verdict, which spend no try."""
    from . import attempt, causes  # causes imports this module

    counts: Counter[str] = Counter()
    repeats = 0
    for record in records:
        directory = _attempt_dir(repo, record)
        if directory is not None:
            counts.update(causes.attempt_counts(directory))
            repeats += attempt.repeat_count(directory)
    doc = causes.Tally(column, **counts).to_json()
    del doc["run"]
    return {**doc, "repeats": repeats}


def _ratio(exact: int, denominator: Decimal | None) -> str | None:
    """exact / denominator to 2 decimals; None when the denominator is None or 0."""
    return money(Decimal(exact) / denominator) if denominator else None


def _paid(api: Decimal | None, arm: backends.Arm | None) -> str | None:
    """What the arm really pays: nothing on a subscription or free arm, its API-equivalent on
    a metered one; None without a price."""
    if api is None or arm is None:
        return None
    return money(api if arm.billing == backends.METERED else Decimal(0))


def _cell(records: Sequence[Mapping], matched: set[Key], arm: backends.Arm | None,
          repo: Path | None, column: str) -> dict:  # fmt: skip
    """One arm's figures over `records` (its attempts in the column) and `matched` (the
    functions `_matched_by_arm` credits it with, in the column)."""
    sums = _sums(records)
    held = {_key(r) for r in records if r["outcome"] == driver.HOLD_EXACT}
    walls = [_wall_ms(r) for r in records]
    wall = sum(ms for ms, _ in walls)
    price = arm.list_price if arm is not None else None
    api = None if price is None else sum(
        (backends.token_cost(r["tokens"], price) for r in records), Decimal(0))  # fmt: skip
    exact = len(held | matched)
    return {"attempted": len({_key(r) for r in records}), "exact": exact,
            "hold_exact": len(held), "matched": len(matched), "sessions": len(records),
            "turns": sums["turns"], "tokens": sums["tokens"], "wall_ms": wall,
            "wall_estimated_sessions": sum(estimated for _, estimated in walls),
            "api_usd": None if api is None else money(api), "paid_usd": _paid(api, arm),
            "per_try": _per_try(records, repo, column),
            "exact_per_api_usd": _ratio(exact, api),
            "exact_per_wall_hour": _ratio(exact, Decimal(wall) / _MS_PER_HOUR),
            "exact_per_mtok": _ratio(exact, Decimal(sum(sums["tokens"].values()))
                                     / TOKENS_PER_MTOK)}  # fmt: skip


def _row(records: Sequence[Mapping], matched: set[Key], arm: backends.Arm | None,
         columns: Sequence[str], sizes: Mapping[Key, int], repo: Path | None) -> dict:  # fmt: skip
    cells = {column: _cell([r for r in records if _in(column, _key(r), sizes)],
                           {k for k in matched if _in(column, k, sizes)}, arm, repo, column)
             for column in columns}  # fmt: skip
    return {"arm": arm.name if arm is not None else None,
            "billing": arm.billing if arm is not None else None, "cells": cells}  # fmt: skip


def _comparison(matching: Sequence[Mapping], landed: Sequence[Mapping], sizes: Mapping[Key, int],
                arms: Mapping[str, backends.Arm], repo: Path | None) -> dict:  # fmt: skip
    """Spike 012's table: one row per arm (`arm_key`, sorted) of the matching attempts and the
    arms `_matched_by_arm` credits; each row's arm, list price and billing come from the arm
    table (backends.record_arm), never from a recorded cost."""
    groups: dict[str, list[Mapping]] = {}
    for r in matching:
        groups.setdefault(arm_key(r), []).append(r)
    matched = _matched_by_arm(matching, landed)
    sample = {}
    for r in [*matching, *landed]:
        sample.setdefault(arm_key(r), r)
    used = {_stratum(k, sizes) for k in {*map(_key, matching), *set().union(*matched.values())}}
    columns = [*driver.STRATA_NAMES, *([UNKNOWN] if UNKNOWN in used else []), TOTAL]
    rows = {name: _row(groups.get(name, []), matched.get(name, set()),
                       backends.record_arm(sample[name], arms), columns, sizes, repo)
            for name in sorted({*groups, *matched})}  # fmt: skip
    return {"columns": columns, "arms": rows}


# ---- todo check-budget-from-data: checks to an exact match per size bucket ----

# The bands of checks a session used, [low, high] inclusive (high None: no bound): no check,
# the first three, then the ranges the budget question turns on (attempt.CHECK_BUDGET).
_CHECK_BANDS = ((0, 0), (1, 3), (4, 6), (7, 10), (11, 15), (16, None))
_EXACT = (driver.MATCHED, driver.HOLD_EXACT)
_PERCENTILES = (50, 95)


def _band_label(low: int, high: int | None) -> str:
    if high is None:
        return f"{low}+"
    return str(low) if low == high else f"{low}-{high}"


def _nearest_rank(values: Sequence[int], percent: int) -> int | None:
    """The nearest-rank percentile of sorted `values`; None when there are none."""
    if not values:
        return None
    return values[max(0, -(-percent * len(values) // 100) - 1)]


def _token_total(record: Mapping) -> int:
    return sum(record["tokens"][k] for k in _TOKENS)


def _band(records: Sequence[Mapping], low: int, high: int | None, tokens: int) -> dict:
    inside = [r for r in records
              if low <= r["check"]["runs"] and (high is None or r["check"]["runs"] <= high)]
    spent = sum(map(_token_total, inside))
    return {"checks": _band_label(low, high), "sessions": len(inside),
            "exact": sum(r["outcome"] in _EXACT for r in inside),
            "tokens_percent": tenth(Decimal(spent) * 100 / tokens) if tokens else None}  # fmt: skip


def _curve(records: Sequence[Mapping]) -> dict:
    """One bucket's curve: the sessions, the exact ones (MATCHED or HOLD_EXACT) by the checks
    they used (`check.runs`), the cumulative share exact by each such check, the p50 and p95
    and latest check of an exact session, and every session by _CHECK_BANDS with its share of
    the bucket's tokens."""
    runs = sorted(r["check"]["runs"] for r in records if r["outcome"] in _EXACT)
    at = Counter(runs)
    cumulative, seen = [], 0
    for checks in sorted(at):
        seen += at[checks]
        cumulative.append([checks, tenth(Decimal(seen) * 100 / len(runs))])
    tokens = sum(map(_token_total, records))
    return {"sessions": len(records), "exact": len(runs),
            "exact_at": [[k, at[k]] for k in sorted(at)], "cumulative_percent": cumulative,
            **{f"p{p}": _nearest_rank(runs, p) for p in _PERCENTILES},
            "latest": runs[-1] if runs else None,
            "bands": [_band(records, low, high, tokens) for low, high in _CHECK_BANDS]}  # fmt: skip


def _check_curves(matching: Sequence[Mapping], sizes: Mapping[Key, int]) -> dict:
    """The curve of every SIZE_BUCKETS bucket (an `unknown` one only when a function has no
    size) and of all of them (`total`), over the matching sessions."""
    groups: dict[str, list[Mapping]] = {_bucket_label(i): [] for i in range(len(SIZE_BUCKETS))}
    for r in matching:
        groups.setdefault(_size_label(_key(r), sizes), []).append(r)
    return {**{label: _curve(records) for label, records in groups.items()},
            TOTAL: _curve(matching)}  # fmt: skip


# ---- todo held-benchmark-statistics: `stats --compare RUN_A RUN_B [RUN ...]` ----

_Z95 = NormalDist().inv_cdf(0.975)  # the two-sided 95% normal quantile, about 1.96


def wilson(exact: int, n: int) -> tuple[float, float] | None:
    """The Wilson score 95% interval of `exact` successes in `n` trials, as fractions; None
    for no trial."""
    if not n:
        return None
    p, z2 = exact / n, _Z95 * _Z95
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = _Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def mcnemar_exact(a_only: int, b_only: int) -> float:
    """The exact two-sided McNemar p-value of the discordant pairs: twice the binomial(n, 1/2)
    tail at the smaller count, capped at 1; 1 without a discordant pair."""
    n = a_only + b_only
    tail = Fraction(sum(math.comb(n, i) for i in range(min(a_only, b_only) + 1)), 2**n)
    return float(min(Fraction(1), 2 * tail))


def holm(p_values: Sequence[float]) -> list[float]:
    """The Holm-Bonferroni step-down adjustment of `p_values`, in their order: the i-th
    smallest of m is multiplied by m - i + 1, never below the adjusted one before it
    (monotone), and capped at 1. One p-value is its own adjustment."""
    m = len(p_values)
    adjusted = [0.0] * m
    running = 0.0
    for rank, index in enumerate(sorted(range(m), key=lambda i: p_values[i])):
        running = max(running, min(1.0, (m - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted


def _percent(fraction: float) -> str:
    return tenth(Decimal(fraction * 100))


def _proportion(exact: int, n: int) -> dict:
    interval = wilson(exact, n)
    return {"exact": exact, "functions": n,
            "rate_percent": _rate(exact, n),
            "wilson_percent": None if interval is None
            else [_percent(x) for x in interval]}  # fmt: skip


@dataclass(frozen=True)
class _RunOutcomes:
    """One run of `stats --compare`: its arms, per finished function whether a finished record
    of it was exact (MATCHED or HOLD_EXACT), and the functions it only has cut-short records
    of."""

    name: str
    arms: list[str]
    exact: dict[Key, bool]
    cut_short: frozenset[Key]


def _run_outcomes(records: Sequence[Mapping], name: str) -> _RunOutcomes:
    """Run `name`'s matching attempt records (a run with none is a StatsError). RULINGS "Held
    comparisons" (owner 2026-11-19): a function is finished when the run has a finished record
    of it, one that is not cut short by driver._cut_short, the rule `hold_progress` attempts a
    function again by: a record with abort reason guardrail or tool (the night's or its arm's
    stop reset the session's work), but a Copilot session's guardrail record with a refused
    call (it ended on a write Copilot denied: the model's own end) is finished. MATCHED,
    PARTIAL, HOLD_EXACT and GAVE_UP with no abort reason, timeout or lint are finished. A
    session a usage limit, a stop or an interrupt killed leaves no attempt record (a limit
    record, or none), so the function has no record at all unless another session finished
    it."""
    mine = [r for r in records if r["kind"] == driver.KIND_ATTEMPT
            and r.get("session", driver.MATCHING) == driver.MATCHING
            and run_selected(r["run"], [name])]  # fmt: skip
    if not mine:
        raise StatsError(f"run {name!r} has no matching attempt record")
    exact: dict[Key, bool] = {}
    for r in mine:
        if driver._cut_short(r):
            continue
        exact[_key(r)] = exact.get(_key(r), False) or r["outcome"] in _EXACT
    cut = frozenset(_key(r) for r in mine) - exact.keys()
    return _RunOutcomes(name, sorted({arm_key(r) for r in mine}), exact, cut)


def _side(run: _RunOutcomes) -> dict:
    return {"run": run.name, "arms": run.arms,
            **_proportion(sum(run.exact.values()), len(run.exact))}  # fmt: skip


def _left_out(run: _RunOutcomes, keys: Iterable[Key]) -> dict:
    """Of `keys`, the ones `run` did not finish: cut short, or with no record of it."""
    unfinished = [k for k in keys if k not in run.exact]
    cut = sum(k in run.cut_short for k in unfinished)
    return {"cut_short": cut, "no_record": len(unfinished) - cut}


def _pair(a: _RunOutcomes, b: _RunOutcomes) -> dict:
    """Two runs paired on the functions both finished: the four cells, each run's interval on
    them, the exact McNemar p-value (its Holm adjustment is set by compare_runs) and the
    functions either run attempted that are left out, by why."""
    shared = sorted(a.exact.keys() & b.exact.keys())
    cells = Counter((a.exact[k], b.exact[k]) for k in shared)
    a_only, b_only = cells[(True, False)], cells[(False, True)]
    both = cells[(True, True)]
    out = (a.exact.keys() | a.cut_short | b.exact.keys() | b.cut_short) - set(shared)
    return {
        "a": _side(a), "b": _side(b),
        "paired": {"functions": len(shared), "both": both, "a_only": a_only, "b_only": b_only,
                   "neither": cells[(False, False)],
                   "a": _proportion(both + a_only, len(shared)),
                   "b": _proportion(both + b_only, len(shared)),
                   "mcnemar_p": mcnemar_exact(a_only, b_only),
                   "left_out": {"functions": len(out), "a": _left_out(a, out),
                                "b": _left_out(b, out)}},
    }  # fmt: skip


def compare_runs(records: Sequence[Mapping], names: Sequence[str]) -> dict:
    """`stats --compare` over two or more runs (fewer is a StatsError): each run's exact
    functions of those it finished with a Wilson 95% interval (`runs`), and every pair of runs,
    in the order named, paired on the functions both finished (`pairs`, _pair) with the exact
    McNemar p-value and its Holm-Bonferroni adjustment over all the pairs (`holm_p`; with one
    pair it is the raw p). With two runs the one pair's `a`, `b` and `paired` are also the
    doc's own keys, the shape before quick 261119-bho."""
    if len(names) < 2:
        raise StatsError("--compare needs at least two runs")
    runs = [_run_outcomes(records, name) for name in names]
    pairs = [_pair(a, b) for i, a in enumerate(runs) for b in runs[i + 1:]]
    raw = [pair["paired"]["mcnemar_p"] for pair in pairs]
    for pair, p, adjusted in zip(pairs, raw, holm(raw), strict=True):
        pair["paired"].update(mcnemar_p=f"{p:.4f}", holm_p=f"{adjusted:.4f}")
    doc = {"runs": [_side(run) for run in runs], "pairs": pairs}
    return {**doc, **pairs[0]} if len(pairs) == 1 else doc


def _interval_text(p: Mapping, unit: str = "") -> str:
    counted = f"{p['exact']} exact of {p['functions']}{unit}"
    if p["wilson_percent"] is None:
        return counted
    low, high = p["wilson_percent"]
    return f"{counted}, {p['rate_percent']}% [{low}%, {high}%]"


def _left_out_text(side: str, counts: Mapping) -> str:
    return f"{side}: {counts['cut_short']} cut short, {counts['no_record']} no record"


def _pair_lines(pair: Mapping, letters: Mapping[str, str], count: int) -> list[str]:
    """One pair's lines; `letters` names each run by its letter, `count` is the pairs Holm
    adjusts over."""
    a, b = letters[pair["a"]["run"]], letters[pair["b"]["run"]]
    paired, out = pair["paired"], pair["paired"]["left_out"]
    return [f"paired {a} and {b}: {paired['functions']} functions both runs finished; both "
            f"exact {paired['both']}, {a} only {paired['a_only']}, {b} only "
            f"{paired['b_only']}, neither {paired['neither']}",
            f"  left out: {out['functions']} functions not finished by both "
            f"({_left_out_text(a, out['a'])}; {_left_out_text(b, out['b'])})",
            f"  {a}: {_interval_text(paired['a'])}", f"  {b}: {_interval_text(paired['b'])}",
            f"  exact McNemar test (two-sided, {paired['a_only'] + paired['b_only']} discordant "
            f"pairs): p = {paired['mcnemar_p']}, Holm p = {paired['holm_p']} (Holm-Bonferroni "
            f"over {count} pair{'' if count == 1 else 's'})"]  # fmt: skip


def format_comparison(doc: Mapping) -> str:
    """The runs lettered A, B, C... in the order named, then every pair."""
    letters = {side["run"]: chr(ord("A") + i) for i, side in enumerate(doc["runs"])}
    lines = ["compare (exact: MATCHED or HOLD_EXACT; finished functions only, a record a stop "
             "cut short is not; Wilson 95% intervals):"]  # fmt: skip
    lines += [f"  {letters[side['run']]} {side['run']} ({', '.join(side['arms'])}): "
              f"{_interval_text(side, ' functions')}" for side in doc["runs"]]  # fmt: skip
    for pair in doc["pairs"]:
        lines += _pair_lines(pair, letters, len(doc["pairs"]))
    return "\n".join(lines)


def compare(log: Path, names: Sequence[str]) -> dict:
    """`stats --compare`: compare_runs over `log` with the ledger next to it applied."""
    records, _ = apply_errata(read_attempts(log), read_errata(Path(log).parent / ERRATA))
    return compare_runs(records, names)


def run_selected(run_id: str, names: Sequence[str]) -> bool:
    """Phase 07.2 D-22: `run_id` equals one of `names`, or starts with a name's prefix before
    its trailing `*` (`spike012-*`). The one rule `stats --run` and `drive --land-held`
    share."""
    return any(run_id.startswith(name[:-1]) if name.endswith("*") else run_id == name
               for name in names)  # fmt: skip


def _selected(record: Mapping, runs: Sequence[str]) -> bool:
    """A record of the selected runs; a landing is selected by its own run or the run it lands
    from."""
    if record["kind"] == driver.KIND_LANDING and run_selected(record["from_run"], runs):
        return True
    return run_selected(record["run"], runs)  # every record kind names its run


def build_report(records: Sequence[Mapping], hist: History, sizes: Mapping[Key, int],
                 tiers: Mapping[Key, int] | None, *, own: bool = False,
                 arms: Mapping[str, backends.Arm] | None = None,
                 repo: Path | None = None, errata: Sequence[Mapping] = ()) -> Report:  # fmt: skip
    """The DEC-07 report of validated `records` and a match history. `own` (`stats --run`): a
    function is matched by the records' own logged matches only, not by the git history of
    other runs; the class lines still come from git. `arms` (quick 261110-f30, `stats --run`):
    the arm table the comparison prices by, None for no comparison; `repo` holds the attempts'
    saved checks (None: no saved evidence)."""
    attempts = [r for r in records if r["kind"] == driver.KIND_ATTEMPT]
    v1 = [r for r in attempts if "schema" not in r]
    v2 = [r for r in attempts if "schema" in r]  # v2 and v3 alike: both carry model_requested
    matching = [r for r in attempts if r.get("session", driver.MATCHING) == driver.MATCHING]
    counted = _counted(hist)
    seen: dict[Key, int] = {}
    for event in hist.events:
        seen[(event.exe, event.start)] = seen.get((event.exe, event.start), 0) + 1
    reverted = {key for key in seen if key not in counted}
    # A MATCHED landing (`--land-held`, D-26) is a logged match too; it has no cost of its own,
    # so `_sums` stays over the attempt records and the held attempt's cost is counted once.
    landed = [r for r in records if r["kind"] == driver.KIND_LANDING]
    logged = {_key(r) for r in [*matching, *landed] if r["outcome"] == driver.MATCHED}
    matched = logged if own else (logged - reverted) | set(counted)
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
                     "v2_records": sum(r.get("schema") == driver.SCHEMA_V2 for r in records),
                     "v3_records": sum(r.get("schema") == driver.SCHEMA_V3 for r in records),
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
        "by_model_size": _by_model_size(matching, landed, sizes),
        "by_arm": _by_arm(matching, landed),
        "by_session": _split(v2, "session", len(v1)),
        "by_tier": _by_tier(counted, tiers),
        "comparison": None if arms is None else _comparison(matching, landed, sizes, arms, repo),
        "check_curves": _check_curves(matching, sizes),
        "errata": list(errata),
        "environments": None if arms is None else _environments(records),
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
    lines = [f"attempt log: {a['records']} records (v1 {a['v1_records']}, v2 {a['v2_records']}, "
             f"v3 {a['v3_records']}), {a['sessions']} sessions ({a['matching_sessions']} "
             "matching)",
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


def _arm_lines(by_arm: Mapping) -> list[str]:
    """D-22: one line per arm: functions attempted, matched and held exact, tokens and cost."""
    if not by_arm:
        return ["per arm: none"]
    return ["per arm:"] + [
        f"  {arm}: attempted {a['attempted']}, matched {a['matched']}, hold exact "
        f"{a['hold_exact']}, tokens {', '.join(f'{k} {a['tokens'][k]}' for k in _TOKENS)}, "
        f"cost ${a['cost_usd']}"
        for arm, a in by_arm.items()]  # fmt: skip


def _model_size_lines(by_model_size: Mapping) -> list[str]:
    """One line per arm (D-22): each bucket's matched, attempted and hold-exact counts."""
    if not by_model_size:
        return ["per arm and size: none"]
    return ["per arm and size:"] + [
        f"  {model}: " + "; ".join(
            f"{label} {c['matched']} of {c['attempted']} matched, {c['hold_exact']} hold exact"
            for label, c in buckets.items())
        for model, buckets in by_model_size.items()]  # fmt: skip


def _shown(value: str | None, unit: str = "") -> str:
    """A comparison figure as text: `n/a` (no unit sign) for None."""
    return "n/a" if value is None else f"{unit}{value}"


def _per_try_text(per_try: Mapping) -> str:
    if not per_try["checks"]:
        return "no saved checks"
    repeats = f", repeats {per_try['repeats']}" if per_try["repeats"] else ""
    return f"({per_try['checks']} checks) " + ", ".join(
        f"{label} {per_try[f'{name}_percent']}%" for name, label in _PER_TRY) + repeats  # fmt: skip


def _column_line(column: str, c: Mapping) -> str:
    tokens = ", ".join(f"{k} {c['tokens'][k]}" for k in _TOKENS)
    return (f"    {column}: attempted {c['attempted']}, exact {c['exact']} (hold exact "
            f"{c['hold_exact']}, matched {c['matched']}), sessions {c['sessions']}, turns "
            f"{c['turns']}, wall {tenth(Decimal(c['wall_ms']) / _MS_PER_MINUTE)} min, tokens "
            f"{tokens}, API-equivalent {_shown(c['api_usd'], '$')}, real paid "
            f"{_shown(c['paid_usd'], '$')}, per try {_per_try_text(c['per_try'])}, exact per "
            f"API-equivalent $ {_shown(c['exact_per_api_usd'])}, per wall hour "
            f"{_shown(c['exact_per_wall_hour'])}, per million tokens "
            f"{_shown(c['exact_per_mtok'])}")  # fmt: skip


def _head_line(key: str, row: Mapping) -> str:
    """The arm's name and billing, and its real-paid case in words."""
    priced = row["cells"][TOTAL]["api_usd"] is not None
    words = _PAID_WORDS[row["billing"]] if priced else _NO_PRICE
    return (f"  {key} ({row['arm'] or 'no backends.toml arm'}, "
            f"{row['billing'] if priced else 'no price'}): {words}")  # fmt: skip


def _comparison_lines(comparison: Mapping | None) -> list[str]:
    """Quick 261110-f30: the comparison per arm, only with `--run`."""
    if comparison is None:
        return []
    if not comparison["arms"]:
        return ["comparison per arm: none"]
    lines = [f"comparison per arm (columns: {', '.join(comparison['columns'])}; "
             "API-equivalent: tokens at the arm's list price):"]  # fmt: skip
    for key, row in comparison["arms"].items():
        lines.append(_head_line(key, row))
        lines += [_column_line(column, cell) for column, cell in row["cells"].items()]
    return lines


def _curve_lines(label: str, c: Mapping) -> list[str]:
    if not c["sessions"]:
        return [f"  {label}: no matching session"]
    if c["exact"]:
        by_check = ", ".join(f"{k} {v}%" for k, v in c["cumulative_percent"])
        head = (f"  {label}: {c['exact']} exact of {c['sessions']} sessions; p50 {c['p50']}, "
                f"p95 {c['p95']}, latest {c['latest']}; exact by check: {by_check}")  # fmt: skip
    else:
        head = f"  {label}: 0 exact of {c['sessions']} sessions"
    bands = "; ".join(
        f"{b['checks']}: {b['sessions']} ({b['exact']} exact, "
        f"{_shown(b['tokens_percent'])}% of tokens)" for b in c["bands"])  # fmt: skip
    return [head, f"    sessions by checks used: {bands}"]


def _check_curve_lines(curves: Mapping) -> list[str]:
    """Todo check-budget-from-data: the checks each exact session used, per size bucket."""
    lines = ["checks to an exact match per size bucket (check.runs of the matching sessions; "
             "exact: MATCHED or HOLD_EXACT):"]  # fmt: skip
    for label, curve in curves.items():
        lines += _curve_lines(label, curve)
    return lines


def _environments(records: Sequence[Mapping]) -> list[dict]:
    """Todo run-environment-digest (`stats --run`): each STARTED run record in log order (a run
    id started twice is listed twice) with its environment and controls; both None for a
    record from before them, controls None for a --land-held night."""
    return [{"run": r["run"], "environment": r.get("environment"), "controls": r.get("controls")}
            for r in records if r["kind"] == driver.KIND_RUN and r["event"] == driver.STARTED]


def _environment_line(entry: Mapping) -> str:
    env, controls = entry["environment"], entry["controls"]
    if env is None:
        return f"  {entry['run']}: no environment recorded"
    cli = ", ".join(f"{h} {v or 'none'}" for h, v in env["cli"].items()) or "none"
    image = env["image"].removeprefix("sha256:")[:12] if env["image"] else "unknown"
    checked = (f"controls gold {controls['gold']}, null {controls['null']} "
               f"({controls['null_percent']:g}%)" if controls else "no controls")  # fmt: skip
    return (f"  {entry['run']}: digest {env['digest'][:12]}, head {env['head'][:12]}, image "
            f"{image}, cli {cli}; {checked}")


def _environment_lines(environments: Sequence[Mapping] | None) -> list[str]:
    if environments is None:
        return []
    return ["environment per run:", *map(_environment_line, environments)]


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
            *_class_lines(d), *_errata_lines(d["errata"]), *_metric_lines(d),
            *_check_curve_lines(d["check_curves"]),
            *_split_lines("per model", d["by_model"], d["by_model"]["models"]),
            *_arm_lines(d["by_arm"]),
            *_model_size_lines(d["by_model_size"]),
            *_comparison_lines(d["comparison"]),
            *_environment_lines(d["environments"]),
            *_split_lines("per session kind", d["by_session"], d["by_session"]["kinds"]),
            *_tier_lines(d["by_tier"]),
        ])  # fmt: skip


def collect(repo: Path, log: Path, config: Path, *, runs: Sequence[str] | None = None) -> Report:
    """The report of `log`, `repo`'s history and `config`'s sizes and tiers. `runs` (`stats
    --run`, D-16, D-22): only the records of those runs (run_selected), matched by their own
    logged matches. 07.2-06 (D-17): without `runs`, a hold run's attempt records are left out
    (a spike's arms are read through `--run`); a landing from one is still a logged match.
    Quick 261110-f30 (spike 012, owner ruling 2026-11-10): with `runs`, the report adds the
    comparison per arm, priced by backends.toml (an unreadable table is a StatsError) and with
    the per-try rates of <repo>/build/driver; without `runs`, `comparison` is null.
    Todo errata-ledger: the ledger next to `log` (ERRATA, progress/errata.toml for the
    committed log) is applied to the whole log first, and the report lists the corrections of
    the runs it holds a record of."""
    records, applied = apply_errata(read_attempts(log), read_errata(Path(log).parent / ERRATA))
    if runs is None:
        records = [r for r in records if r.get("hold_run") is not True]
        return build_report(records, history(repo), read_sizes(config), read_tiers(config),
                            errata=_listed(applied, records))  # fmt: skip
    records = [r for r in records if _selected(r, runs)]
    try:
        arms = backends.load_arms()
    except backends.ArmError as exc:
        raise StatsError(f"the arm table: {exc}") from None
    return build_report(records, history(repo), read_sizes(config), read_tiers(config),
                        own=True, arms=arms, repo=Path(repo),
                        errata=_listed(applied, records))  # fmt: skip


def _listed(applied: Sequence[tuple[Erratum, int]], records: Sequence[Mapping]) -> list[dict]:
    """The applied corrections of the runs the report holds a record of."""
    runs = {r["run"] for r in records}
    return [e.to_json(n) for e, n in applied if e.run in runs]
