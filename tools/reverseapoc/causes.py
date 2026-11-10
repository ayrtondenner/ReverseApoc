# SPDX-License-Identifier: GPL-3.0-or-later
"""`reverseapoc causes` (999.8, plan 07.2-04): failed builds and mismatches counted by cause
over drive run directories, from saved evidence only.

It walks build/driver/<RUN>/<exe>/<function>/attempt-N (flags._run_dirs and
flags._attempt_dirs) and reads each attempt's checks.jsonl. A plain check is one try (D-19 9d,
FNV's per-try rates): exit 0 is a match, 1 a mismatch, 2 a build failure or tool error
(check.py's exit semantics). Sweeps are counted apart, and a line that is not a JSON object
with a boolean `sweep` and, for a plain check, an exit of 0, 1 or 2 is counted as malformed.
Extra keys (07.2-03's `note`) are ignored.

The causes come from the check's saved document, checks/NNNN.json:
- a build failure's tool-error document (attempt.py: `error`, `returncode`, `stdout`,
  `stderr`) is keyed by batch.compile_output_key over stdout then stderr, the rule batch keys
  its own failed compiles by, and every Watcom code (E or W and 3-4 digits) in it is counted;
  a check document saved for an exit 2 is keyed by its first problem;
- a mismatch is classed by the claimed function's entry: `not compiled` (absent from
  functions[], or a problem names it), the reloc key batch._reloc_key gives, `length` (its size
  differs from the config/<exe>/functions.csv row, read as stats.read_sizes reads it), else
  `bytes`, with the mnemonic pair of the window's first differing row when check saved one;
- a shared-header gap is a build failure naming an undeclared symbol (E1011) or a member or
  subscript error, keyed on the quoted name (the message itself when none is quoted) and
  ranked by the distinct functions it blocks.

Nothing is compiled and nothing under orig/ is read. The report holds counts, percentages,
Watcom codes, class keys and the C identifiers of the agent's own C, never bytes.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import batch, flags, stats

_OUTCOMES = ("build_failure", "mismatch", "match")  # FNV's order: 42/55/3
BUILD_FAILURE, MISMATCH, MATCH = _OUTCOMES
_EXIT_OUTCOME = {2: BUILD_FAILURE, 1: MISMATCH, 0: MATCH}  # check.py:28-31
_LABELS = {BUILD_FAILURE: "build failure", MISMATCH: "mismatch", MATCH: "match"}
SWEEPS, MALFORMED = "sweeps", "malformed"
TOTAL = "total"
CHECKS_DIR = "checks"  # attempt.CHECKS_DIR

# The keys of a check whose saved document cannot be classed.
NO_DOC = "no saved check document"
UNREADABLE = "unreadable check document"
# The mismatch classes besides batch._reloc_key's.
NOT_COMPILED, LENGTH, BYTES = "not compiled", "length", "bytes"
_NO_INSN = "none"  # the window side that has no instruction

WATCOM_CODE = re.compile(r"\b[EW]\d{3,4}\b")
_ERROR_MESSAGE = re.compile(r"\b(E\d{3,4})\b:?\s*(.*)")  # an error code and its message
_QUOTED = re.compile(r"'([^']+)'")
_UNDECLARED = "E1011"  # "Symbol 'X' has not been declared"
_MEMBER_OR_SUBSCRIPT = re.compile(r"member|subscript", re.IGNORECASE)
FEW_BUILD_FAILURES_PERCENT = Decimal(1)  # under it, format() says so (RESEARCH Q5 caveat)


class CausesError(ValueError):
    """The run directories or functions.csv cannot be read as asked."""


def _percent(count: int, checks: int) -> str | None:
    return stats.tenth(Decimal(count) * 100 / checks) if checks else None


@dataclass(frozen=True)
class Tally:
    """One run's (or the total's) plain checks by outcome, its sweeps and malformed lines."""

    run: str
    build_failure: int = 0
    mismatch: int = 0
    match: int = 0
    sweeps: int = 0
    malformed: int = 0

    @property
    def checks(self) -> int:
        return self.build_failure + self.mismatch + self.match

    def to_json(self) -> dict[str, Any]:
        doc: dict[str, Any] = {"run": self.run, "checks": self.checks, SWEEPS: self.sweeps,
                               MALFORMED: self.malformed}  # fmt: skip
        for name in _OUTCOMES:
            doc[name] = getattr(self, name)
            doc[f"{name}_percent"] = _percent(getattr(self, name), self.checks)
        return doc

    def line(self) -> str:
        parts = [f"{self.run}: {self.checks} checks"]
        for name in _OUTCOMES:
            percent = _percent(getattr(self, name), self.checks)
            shown = f" ({percent}%)" if percent is not None else ""
            parts.append(f"{_LABELS[name]} {getattr(self, name)}{shown}")
        parts.append(f"{SWEEPS} {self.sweeps}")
        if self.malformed:
            parts.append(f"{MALFORMED} {self.malformed}")
        return "  ".join(parts)


def _ranked(counts: Mapping[str, int]) -> list[tuple[str, int]]:
    """Most first, ties by name."""
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _section(title: str, counts: Mapping[str, int]) -> list[str]:
    if not counts:
        return [f"{title}: none"]
    return [f"{title}:", *(f"  {n:>5}  {key}" for key, n in _ranked(counts))]


@dataclass(frozen=True)
class Causes:
    runs: tuple[Tally, ...]
    total: Tally
    build_failures: Mapping[str, int]  # key -> checks
    codes: Mapping[str, int]  # Watcom code -> occurrences
    mismatch_classes: Mapping[str, int]  # class key -> checks
    header_gaps: tuple[tuple[str, int], ...]  # (name, distinct functions blocked), ranked

    def to_json(self) -> dict[str, Any]:
        """The report as one JSON object; the verb prints it with sorted keys."""
        return {"runs": [t.to_json() for t in self.runs], "rates": self.total.to_json(),
                SWEEPS: self.total.sweeps, MALFORMED: self.total.malformed,
                "build_failures": dict(self.build_failures), "codes": dict(self.codes),
                "mismatch_classes": dict(self.mismatch_classes),
                "header_gaps": [{"name": name, "functions": n}
                                for name, n in self.header_gaps]}  # fmt: skip

    def _few_build_failures(self) -> bool:
        checks = self.total.checks
        share = Decimal(self.total.build_failure) * 100 / checks if checks else None
        return share is not None and share < FEW_BUILD_FAILURES_PERCENT

    def format(self) -> str:
        head = (f"causes over {len(self.runs)} run(s): plain checks per try, sweeps apart "
                "(saved evidence only)")  # fmt: skip
        lines = [head, *(f"  {t.line()}" for t in (*self.runs, self.total))]
        lines += _section("build failures by key", self.build_failures)
        lines += _section("Watcom codes", self.codes)
        lines += _section("mismatch classes", self.mismatch_classes)
        lines += _section("shared-header gaps (distinct functions blocked)"
                          if self.header_gaps else "shared-header gaps",
                          dict(self.header_gaps))  # fmt: skip
        if self._few_build_failures():
            lines.append("note: build failures were few in these runs (under "
                         f"{FEW_BUILD_FAILURES_PERCENT}% of plain checks), so the mismatch "
                         "classes carry the signal")  # fmt: skip
        return "\n".join(lines)


# ---- one kind of evidence per generator ----


def _log_lines(attempt_dir: Path) -> Iterator[dict | None]:
    """Each line of the attempt's checks.jsonl as a JSON object, None for one that is not."""
    log = attempt_dir / flags.CHECKS_LOG
    if not log.is_file():
        return
    for raw in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            line = json.loads(raw)
        except ValueError:
            line = None
        yield line if isinstance(line, dict) else None


def _kind(line: dict | None) -> str:
    """The counter a checks.jsonl line goes to: an outcome, sweeps or malformed."""
    if line is None or not isinstance(line.get("sweep"), bool):
        return MALFORMED
    if line["sweep"]:
        return SWEEPS
    code = line.get("exit")
    if isinstance(code, bool) or not isinstance(code, int):
        return MALFORMED
    return _EXIT_OUTCOME.get(code, MALFORMED)


def _plain_lines(lines: Iterable[dict | None], outcome: str) -> Iterator[dict]:
    """The plain checks of one outcome."""
    for line in lines:
        if line is not None and _kind(line) == outcome:
            yield line


def _saved_doc(attempt_dir: Path, line: dict) -> dict | str:
    """The check's checks/NNNN.json, or NO_DOC / UNREADABLE."""
    n = line.get("n")
    if isinstance(n, bool) or not isinstance(n, int):
        return NO_DOC
    path = attempt_dir / CHECKS_DIR / f"{n:04d}.json"
    if not path.is_file():
        return NO_DOC
    try:
        doc = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except ValueError:
        return UNREADABLE
    return doc if isinstance(doc, dict) else UNREADABLE


@dataclass(frozen=True)
class _Failure:
    key: str
    text: str  # the compiler's text, "" when the document holds none


def _failure(doc: dict) -> _Failure:
    if "error" in doc:  # attempt.py's tool-error document
        text = "\n".join(v for v in (doc.get("stdout"), doc.get("stderr")) if isinstance(v, str))
        return _Failure(batch.compile_output_key(text), text)
    problems = doc.get("problems")
    if "functions" not in doc or not isinstance(problems, list):
        return _Failure(UNREADABLE, "")
    reason = problems[0].get("reason") if problems and isinstance(problems[0], dict) else None
    return _Failure(f"check: {reason}" if isinstance(reason, str) else "check: no problem", "")


def _tool_errors(attempt_dir: Path, lines: Sequence[dict | None]) -> Iterator[_Failure]:
    for line in _plain_lines(lines, BUILD_FAILURE):
        doc = _saved_doc(attempt_dir, line)
        yield _Failure(doc, "") if isinstance(doc, str) else _failure(doc)


def _mnemonic(insn: Any) -> str:
    return _NO_INSN if insn is None else str(insn["mnemonic"])


def _entry_class(entry: dict, exe: str, sizes: Mapping[stats.Key, int]) -> str:
    reloc = entry["reloc"]
    if not reloc["ok"]:
        return batch._reloc_key(reloc["problems"])
    row_size = sizes.get((exe, int(entry["va"], 16)))
    if row_size is not None and entry["size"] != row_size:
        return LENGTH
    first = next((row for row in entry.get("window", []) if row.get("first")), None)
    if first is None:
        return BYTES
    return f"{BYTES}: {_mnemonic(first['ours'])}/{_mnemonic(first['original'])}"


def _mismatch_class(doc: dict, exe: str, function: str, sizes: Mapping[stats.Key, int]) -> str:
    functions, problems = doc.get("functions"), doc.get("problems", [])
    if not isinstance(functions, list) or not isinstance(problems, list):
        return UNREADABLE
    if any(isinstance(p, dict) and p.get("name") == function for p in problems):
        return NOT_COMPILED
    entry = next((f for f in functions if isinstance(f, dict) and f.get("name") == function), None)
    if entry is None:
        return NOT_COMPILED
    try:
        return _entry_class(entry, exe, sizes)
    except (KeyError, TypeError, ValueError, AttributeError):
        return UNREADABLE


def _mismatches(attempt_dir: Path, exe: str, function: str, lines: Sequence[dict | None],
                sizes: Mapping[stats.Key, int]) -> Iterator[str]:  # fmt: skip
    for line in _plain_lines(lines, MISMATCH):
        doc = _saved_doc(attempt_dir, line)
        yield doc if isinstance(doc, str) else _mismatch_class(doc, exe, function, sizes)


def _gap_names(text: str) -> Iterator[str]:
    """The shared-header gap each error line of a compile failure names."""
    for raw in text.splitlines():
        found = _ERROR_MESSAGE.search(raw)
        if found is None:
            continue
        code, message = found.group(1), found.group(2).strip()
        quoted = _QUOTED.search(message)
        if code == _UNDECLARED and quoted is not None:
            yield quoted.group(1)
        elif _MEMBER_OR_SUBSCRIPT.search(message):
            yield quoted.group(1) if quoted is not None else message


# ---- the walk ----


@dataclass
class _Found:
    """What the walk accumulates over every attempt of every run."""

    sizes: Mapping[stats.Key, int]
    build_failures: Counter[str] = field(default_factory=Counter)
    codes: Counter[str] = field(default_factory=Counter)
    mismatch_classes: Counter[str] = field(default_factory=Counter)
    gaps: dict[str, set[tuple[str, str]]] = field(default_factory=dict)

    def add(self, exe: str, function: str, attempt_dir: Path,
            lines: Sequence[dict | None]) -> None:  # fmt: skip
        for failure in _tool_errors(attempt_dir, lines):
            self.build_failures[failure.key] += 1
            self.codes.update(WATCOM_CODE.findall(failure.text))
            for name in _gap_names(failure.text):
                self.gaps.setdefault(name, set()).add((exe, function))
        self.mismatch_classes.update(_mismatches(attempt_dir, exe, function, lines, self.sizes))

    def header_gaps(self) -> tuple[tuple[str, int], ...]:
        return tuple(_ranked({name: len(blocked) for name, blocked in self.gaps.items()}))


def _run_tally(run_dir: Path, found: _Found) -> Tally:
    counts: Counter[str] = Counter()
    for exe, function, attempt_dir in flags._attempt_dirs(run_dir):
        lines = list(_log_lines(attempt_dir))
        counts.update(_kind(line) for line in lines)
        found.add(exe, function, attempt_dir, lines)
    return Tally(run_dir.name, **counts)


def _sum(tallies: Sequence[Tally]) -> Tally:
    fields = (*_OUTCOMES, SWEEPS, MALFORMED)
    return Tally(TOTAL, **{f: sum(getattr(t, f) for t in tallies) for f in fields})


def collect(repo: Path, runs: Sequence[str] = (), *, config: Path | None = None) -> Causes:
    """The causes report over build/driver/<RUN> for each of `runs`, or every run when none is
    named; `config` (default <repo>/config) holds the functions.csv row sizes. An unknown run
    or an unreadable functions.csv is a CausesError."""
    repo = Path(repo)
    try:
        run_dirs = flags._run_dirs(repo, runs)
        sizes = stats.read_sizes(repo / "config" if config is None else Path(config))
    except (flags.FlagsError, stats.StatsError) as exc:
        raise CausesError(str(exc)) from None
    found = _Found(sizes)
    tallies = tuple(_run_tally(d, found) for d in run_dirs)
    return Causes(tallies, _sum(tallies), dict(found.build_failures), dict(found.codes),
                  dict(found.mismatch_classes), found.header_gaps())  # fmt: skip
