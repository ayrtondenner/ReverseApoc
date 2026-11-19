"""`reverseapoc handoff` (todo long-tail-handoff-board, owner ruling 2026-11-19): the threshold
that retires a function from every agent queue onto config/handoff.csv, and the rules that
bring it back.

- Retire (EXE, start) when it has had at least RETIRE_ATTEMPTS matching attempts and the best
  percent of its last RECENT_ATTEMPTS (three passes) is no higher than the best of every
  attempt before them: it did not rise. An attempt is every `attempt` record of the committed
  log (progress/attempts.jsonl, the errata ledger applied as `stats` applies it) whose session
  is matching (a record without `session` is matching, as `stats` reads it), a hold run's
  included, in record order. A check without a percent counts as none; no percent at all is 0.
- Never retire a matched row (config/<exe>/status.csv), one already on the board, one with an
  owner hint (config/hints/<exe>.toml), or one whose failure class got tooling that landed
  after its last attempt: either would return on the next run before an agent tried it again.
- The row: reason `long tail: <N> attempts, best <p>%, mostly <category>` (the give-up
  category most of its attempts name, ties in attempt.GIVEUP_CATEGORIES order, `other` when
  none names one), retired_on the day of the run, return_rule `hint or tooling:<category>`.
- Return a board row whose reason starts `long tail:` and whose return_rule is that form when
  the owner wrote a hint for its address, or when config/handoff-tooling.toml lists tooling for
  its category that landed after retired_on. Rows with any other reason (a suspected bad split,
  one the owner added by hand) are never returned or changed here.
- `--dry-run` lists both; `--write` removes the returned rows, adds the new ones and writes the
  board sorted by EXE order (picker.EXE_ORDER) and address under its fixed header.
"""

from __future__ import annotations

import csv
import datetime
import io
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import contextpack, driver, picker, stats
from .attempt import CLAIMABLE_KINDS, FUNCTIONS_CSV, GIVEUP_CATEGORIES
from .functions import read_functions_csv
from .status import format_percent, read_status, status_path

RETIRE_ATTEMPTS = 24  # the owner's threshold N (ruling 2026-11-19)
RECENT_ATTEMPTS = 9  # three passes of three sessions: the window the best must rise in
TOOLING_TOML = "handoff-tooling.toml"  # under config/: tooling landed per failure class
LONG_TAIL = "long tail:"  # the reason prefix of a row this verb retired, and may return
RETURN_RULE = "hint or tooling:"  # the return_rule prefix, the category after it
NO_CATEGORY = "other"  # the category of a function none of whose attempts gave up with one
_TOOLING_KEYS = ("category", "landed", "commit", "note")

Key = tuple[str, int]  # (exe, start)


class HandoffError(ValueError):
    """The tooling ledger cannot be read."""


@dataclass(frozen=True)
class BoardRow:
    exe: str
    address: int
    reason: str
    retired_on: str  # YYYY-MM-DD
    return_rule: str

    @property
    def key(self) -> Key:
        return self.exe, self.address

    def cells(self) -> list[str]:
        return [self.exe, f"0x{self.address:08X}", self.reason, self.retired_on,
                self.return_rule]  # fmt: skip

    def to_json(self) -> dict[str, str]:
        return dict(zip(picker.HANDOFF_HEADER, self.cells(), strict=True))


@dataclass(frozen=True)
class Retirement:
    row: BoardRow
    name: str  # the function name its latest attempt record gives


@dataclass(frozen=True)
class Return:
    row: BoardRow
    why: str


@dataclass(frozen=True)
class Plan:
    board: tuple[BoardRow, ...]  # the board as read, in file order
    retire: tuple[Retirement, ...]
    returns: tuple[Return, ...]

    def rows(self) -> list[BoardRow]:
        """The board after the plan: the returned rows gone, the retired ones added, sorted."""
        back = {r.row.key for r in self.returns}
        rows = [row for row in self.board if row.key not in back]
        return sorted(rows + [r.row for r in self.retire], key=_order)

    def to_json(self, written: bool) -> dict:
        return {"board": len(self.board), "written": written,
                "retire": [{**r.row.to_json(), "name": r.name} for r in self.retire],
                "returns": [{**r.row.to_json(), "why": r.why} for r in self.returns]}  # fmt: skip


def _order(row: BoardRow) -> tuple[int, int]:
    return picker.EXE_ORDER.index(row.exe), row.address


# ---- the tooling ledger ----


def _tooling_entry(path: Path, number: int, entry: object) -> tuple[str, datetime.date, str]:
    where = f"{path} tooling {number}"
    if not isinstance(entry, dict) or set(entry) != set(_TOOLING_KEYS):
        raise HandoffError(f"{where}: keys must be exactly {', '.join(_TOOLING_KEYS)}")
    if entry["category"] not in GIVEUP_CATEGORIES:
        raise HandoffError(f"{where}: category {entry['category']!r} is not one of "
                           f"{', '.join(GIVEUP_CATEGORIES)}")  # fmt: skip
    landed = entry["landed"]
    if type(landed) is not datetime.date:
        raise HandoffError(f"{where}: landed must be a bare TOML day (landed = 2026-11-20)")
    for key in ("commit", "note"):
        if not isinstance(entry[key], str) or not entry[key].strip():
            raise HandoffError(f"{where}: {key} must be a non-empty string")
    return entry["category"], landed, entry["commit"]


def read_tooling(path: Path) -> dict[str, tuple[datetime.date, str]]:
    """Each failure category's latest landing (day, commit) in the ledger at `path`; a missing
    ledger lists none. TOML that does not parse, a table other than [[tooling]], or an entry
    without exactly _TOOLING_KEYS, a known category, a TOML day and non-empty texts is a
    HandoffError naming it."""
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise HandoffError(f"{path}: not UTF-8 TOML: {exc}") from exc
    entries = doc.get("tooling", [])
    if set(doc) - {"tooling"} or not isinstance(entries, list):
        raise HandoffError(f"{path}: only [[tooling]] tables are allowed (found {sorted(doc)})")
    latest: dict[str, tuple[datetime.date, str]] = {}
    for number, entry in enumerate(entries, start=1):
        category, landed, commit = _tooling_entry(path, number, entry)
        if category not in latest or landed > latest[category][0]:
            latest[category] = landed, commit
    return latest


# ---- the inputs ----


def read_board(path: Path) -> tuple[BoardRow, ...]:
    """The board's rows in file order, checked by the picker's own reader first."""
    picker.read_handoff(path)
    if not Path(path).is_file():
        return ()
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return tuple(BoardRow(r["exe"], int(r["address"], 16), r["reason"], r["retired_on"],
                              r["return_rule"]) for r in csv.DictReader(handle))  # fmt: skip


def _histories(log: Path) -> dict[Key, list[dict]]:
    """Each function's matching attempt records in log order, the errata applied."""
    records, _ = stats.apply_errata(stats.read_attempts(log),
                                    stats.read_errata(Path(log).parent / stats.ERRATA))  # fmt: skip
    out: dict[Key, list[dict]] = defaultdict(list)
    for record in records:
        if record.get("kind") != driver.KIND_ATTEMPT:
            continue
        if record.get("session", driver.MATCHING) != driver.MATCHING:
            continue
        out[record["exe"], int(record["start"], 16)].append(record)
    return out


def _hinted(config: Path) -> frozenset[Key]:
    """Every (EXE, start) the owner wrote a hint for, each key checked against functions.csv."""
    out: set[Key] = set()
    for exe in picker.EXE_ORDER:
        path = contextpack.hints_path(config, exe)
        if not path.is_file():
            continue
        rows = read_functions_csv(Path(config) / exe / FUNCTIONS_CSV)
        starts = {row.start for row in rows if row.kind in CLAIMABLE_KINDS}
        out.update((exe, start) for start in contextpack.read_hints(path, starts))
    return frozenset(out)


# ---- the rule ----


def _best(records: Iterable[dict]) -> float:
    percents = (r["check"]["best_percent"] for r in records)
    return max((p for p in percents if p is not None), default=0.0)


def _dominant(records: Sequence[dict]) -> str:
    counts = Counter(r["giveup"]["category"] for r in records if r.get("giveup"))
    if not counts:
        return NO_CATEGORY
    return max(GIVEUP_CATEGORIES, key=counts.__getitem__)  # the first of the most named


def _long_tail(records: Sequence[dict]) -> bool:
    if len(records) < RETIRE_ATTEMPTS:
        return False
    return _best(records[-RECENT_ATTEMPTS:]) <= _best(records[:-RECENT_ATTEMPTS])


def _retirement(key: Key, records: Sequence[dict], tooling: Mapping, today: datetime.date
                ) -> Retirement | None:  # fmt: skip
    """The board row of a long-tail function, or None when its category's tooling landed
    after its last attempt (it would return untried)."""
    category = _dominant(records)
    tool = tooling.get(category)
    if tool is not None and tool[0] > datetime.date.fromisoformat(records[-1]["date"]):
        return None
    reason = (f"{LONG_TAIL} {len(records)} attempts, best {format_percent(_best(records))}%, "
              f"mostly {category}")  # fmt: skip
    row = BoardRow(key[0], key[1], reason, today.isoformat(), f"{RETURN_RULE}{category}")
    return Retirement(row, records[-1]["function"])


def _return(row: BoardRow, hinted: frozenset[Key], tooling: Mapping) -> Return | None:
    if not (row.reason.startswith(LONG_TAIL) and row.return_rule.startswith(RETURN_RULE)):
        return None
    if row.key in hinted:
        return Return(row, f"an owner hint in config/{contextpack.HINTS_DIR}/{row.exe}.toml")
    category = row.return_rule.removeprefix(RETURN_RULE)
    tool = tooling.get(category)
    if tool is None or tool[0] <= datetime.date.fromisoformat(row.retired_on):
        return None
    return Return(row, f"{category} tooling landed {tool[0].isoformat()} ({tool[1]})")


def plan(config: Path, log: Path, today: datetime.date) -> Plan:
    """What `handoff` would retire and return today, from the board, the attempt log, the
    status tables, the owner's hints and the tooling ledger under `config`."""
    config = Path(config)
    board = read_board(config / picker.HANDOFF_CSV)
    tooling = read_tooling(config / TOOLING_TOML)
    hinted = _hinted(config)
    matched = picker.matched_starts(picker.EXE_ORDER, path_of=lambda e: status_path(config, e),
                                    read=read_status)  # fmt: skip
    skip = matched | hinted | {row.key for row in board}
    histories = _histories(log)
    retire = []
    for key in sorted(histories, key=lambda k: (picker.EXE_ORDER.index(k[0]), k[1])):
        if key in skip or not _long_tail(histories[key]):
            continue
        retirement = _retirement(key, histories[key], tooling, today)
        if retirement is not None:
            retire.append(retirement)
    returns = (_return(row, hinted, tooling) for row in board)
    return Plan(board, tuple(retire), tuple(r for r in returns if r is not None))


def write(config: Path, done: Plan) -> Path:
    """Write the board after `done` to config/handoff.csv (LF, the fixed header first)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(picker.HANDOFF_HEADER)
    writer.writerows(row.cells() for row in done.rows())
    path = Path(config) / picker.HANDOFF_CSV
    path.write_bytes(buffer.getvalue().encode("utf-8"))
    return path


def format_plan(done: Plan, written: Path | None) -> str:
    lines = [f"hand-off board: {len(done.board)} rows; retire {len(done.retire)}, "
             f"return {len(done.returns)}"]  # fmt: skip
    lines += [f"retire {len(done.retire)}:"] + [
        f"  {r.row.exe} 0x{r.row.address:08X} {r.name} {r.row.reason}; returns on "
        f"{r.row.return_rule}" for r in done.retire]  # fmt: skip
    lines += [f"return {len(done.returns)}:"] + [
        f"  {r.row.exe} 0x{r.row.address:08X} {r.why}" for r in done.returns]  # fmt: skip
    lines.append("dry run: nothing written" if written is None else
                 f"wrote {written}: {len(done.retire)} added, {len(done.returns)} removed")
    return "\n".join(lines)
