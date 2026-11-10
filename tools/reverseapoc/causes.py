# SPDX-License-Identifier: GPL-3.0-or-later
"""`reverseapoc causes` (999.8, plan 07.2-04): failed builds and mismatches counted by cause
over drive run directories, from saved evidence only.

It walks build/driver/<RUN>/<exe>/<function>/attempt-N (flags._run_dirs and
flags._attempt_dirs) and reads each attempt's checks.jsonl. A plain check is one try (D-19 9d,
FNV's per-try rates): exit 0 is a match, 1 a mismatch, 2 a build failure or tool error
(check.py's exit semantics). Sweeps are counted apart, and a line that is not a JSON object
with a boolean `sweep` and, for a plain check, an exit of 0, 1 or 2 is counted as malformed.
Extra keys (07.2-03's `note`) are ignored.

Nothing is compiled and nothing under orig/ is read; the report holds counts and percentages.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from . import flags
from .stats import tenth

_OUTCOMES = ("build_failure", "mismatch", "match")  # FNV's order: 42/55/3
_EXIT_OUTCOME = {2: "build_failure", 1: "mismatch", 0: "match"}  # check.py:28-31
_LABELS = {"build_failure": "build failure", "mismatch": "mismatch", "match": "match"}
SWEEPS, MALFORMED = "sweeps", "malformed"
TOTAL = "total"


class CausesError(ValueError):
    """The run directories cannot be read as asked (an unknown run)."""


def _percent(count: int, checks: int) -> str | None:
    return tenth(Decimal(count) * 100 / checks) if checks else None


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


@dataclass(frozen=True)
class Causes:
    runs: tuple[Tally, ...]
    total: Tally

    def to_json(self) -> dict[str, Any]:
        """The report as one JSON object; the verb prints it with sorted keys."""
        return {"runs": [t.to_json() for t in self.runs], "rates": self.total.to_json(),
                SWEEPS: self.total.sweeps, MALFORMED: self.total.malformed}  # fmt: skip

    def format(self) -> str:
        head = (f"causes over {len(self.runs)} run(s): plain checks per try, sweeps apart "
                "(saved evidence only)")  # fmt: skip
        return "\n".join([head, *(f"  {t.line()}" for t in (*self.runs, self.total))])


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


def _run_tally(run_dir: Path) -> Tally:
    counts: Counter[str] = Counter()
    for _exe, _function, attempt_dir in flags._attempt_dirs(run_dir):
        counts.update(_kind(line) for line in _log_lines(attempt_dir))
    return Tally(run_dir.name, **counts)


def _sum(tallies: Sequence[Tally]) -> Tally:
    fields = (*_OUTCOMES, SWEEPS, MALFORMED)
    return Tally(TOTAL, **{f: sum(getattr(t, f) for t in tallies) for f in fields})


def collect(repo: Path, runs: Sequence[str] = (), *, config: Path | None = None) -> Causes:
    """The causes report over build/driver/<RUN> for each of `runs`, or every run when none is
    named. An unknown run is a CausesError."""
    try:
        run_dirs = flags._run_dirs(Path(repo), runs)
    except flags.FlagsError as exc:
        raise CausesError(str(exc)) from None
    tallies = tuple(_run_tally(d) for d in run_dirs)
    return Causes(tallies, _sum(tallies))
