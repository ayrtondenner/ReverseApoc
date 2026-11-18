# SPDX-License-Identifier: GPL-3.0-or-later
"""The whole-program signature table (todo whole-program-signature-table): the register
arguments, stack arguments and result of every game and thunk row, as the lifter infers them
from the row's own code and its callers' use of its result (lift.Lifter.signature, with the
result-used census). The context pack reads it for a function's callees; a matched callee's
own C prototype, from its unit, wins over the table.

Building the table lifts every row of the EXE (minutes, and the census on first use), so it is
generated once per EXE by `reverseapoc signatures EXE` into the gitignored
build/signatures/<exe>.json and only read afterwards: a live session never builds it. Beside
the binary (fixed by the manifest), the table depends on the functions.csv rows, their C names
(the lifter refuses a stack-convention name) and lift.py itself, so it carries a key over all
three; a table built under another key is stale and the pack says so instead of using it.

Calling convention: Watcom 10.6 -4r passes the first four arguments in eax, edx, ebx and ecx
and the rest on the stack, which the callee pops (`ret N`); the result comes back in eax.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import lift
from .fileio import write_atomic
from .functions import KIND_GAME, KIND_THUNK, FunctionRow

FORMAT = 1
TABLE_PARTS = ("build", "signatures")  # under the repository root: gitignored
_KEYS = ("format", "key", "signatures")
_INFERRED_KEYS = ("nregs", "nstack", "returns")
_SLOT = 4  # bytes of one stack argument
_ADDRESS_DIGITS = 8
_HEX = 16
_LIFTED = (KIND_GAME, KIND_THUNK)


class SignatureError(ValueError):
    """A signature table on disk is malformed."""


@dataclass(frozen=True, slots=True)
class Entry:
    """One row's inferred signature, or why the lifter refused the row (`refused`)."""

    nregs: int = 0
    nstack: int = 0
    returns: bool = False
    refused: str = ""

    def prototype(self, name: str) -> str:
        """A C prototype with `int` for every argument (the lifter infers counts, not types),
        then where the arguments and the result go."""
        if self.refused:
            return f"unknown: the lifter refused it ({self.refused})"
        count = self.nregs + self.nstack
        params = ", ".join(["int"] * count) or "void"
        result = "the result in eax" if self.returns else "no result"
        args = f"args in {', '.join(lift.ARG_REGS[: self.nregs])}" if self.nregs else "no args"
        if self.nstack:
            args += (f" and {self.nstack} on the stack (the callee pops "
                     f"{_SLOT * self.nstack} bytes)")  # fmt: skip
        return f"{'int' if self.returns else 'void'} {name}({params}); lifter: {args}, {result}"

    def to_json(self) -> dict[str, Any]:
        if self.refused:
            return {"refused": self.refused}
        return {"nregs": self.nregs, "nstack": self.nstack, "returns": self.returns}


@dataclass(frozen=True)
class Table:
    """The entries by row start, or none and `note`, why (no table here, or a stale one)."""

    entries: Mapping[int, Entry]
    note: str = ""


def table_path(repo: Path, stem: str) -> Path:
    return Path(repo).joinpath(*TABLE_PARTS) / f"{stem}.json"


def _shown(stem: str) -> str:
    """The table's path as a pack shows it: relative to the repository, never a host path."""
    return "/".join([*TABLE_PARTS, f"{stem}.json"])


def _lifter_digest() -> str:
    return hashlib.sha256(Path(lift.__file__).read_bytes()).hexdigest()


def table_key(exe: lift.ExeInputs) -> str:
    """sha256 over lift.py and every row's start, end, kind and C name, in address order."""
    rows = sorted((row.start, row.end, row.kind, exe.symbols.c_name(row.start))
                  for row in exe.rows)  # fmt: skip
    text = json.dumps([_lifter_digest(), rows])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _refusal(exe: lift.ExeInputs, row: FunctionRow) -> str:
    """Lifter.callee's refusal of a callee by name (a stack-convention or odd name), or ''."""
    name = exe.symbols.c_name(row.start)
    if name.startswith("_") or not name.replace("_", "a").isidentifier():
        return "call: stack-convention or odd callee name"
    return ""


def build(exe: lift.ExeInputs) -> dict[int, Entry]:
    """The signature of every game and thunk row of `exe`, in address order, as a caller's
    Lifter sees it: a name Lifter.callee refuses is refused here too, and a signature already
    worked out for a callee is reused (one shared map, so the table agrees with itself). The
    census is read or built first, so `returns` already has its callers' verdict."""
    lift.result_used(exe)
    sigs: dict[int, lift.Sig | None] = {}
    table = {}
    for row in sorted(exe.rows, key=lambda r: r.start):
        if row.kind not in _LIFTED:
            continue
        refused = _refusal(exe, row)
        if refused:
            table[row.start] = Entry(refused=refused)
            continue
        sig = sigs.get(row.start)
        if sig is None:  # not reached yet, or unknown to its callers: ask for the reason
            try:
                sig = lift.Lifter(exe, row, sigs).signature()
            except lift.Unliftable as exc:
                table[row.start] = Entry(refused=str(exc))
                continue
            sigs[row.start] = sig
        table[row.start] = Entry(sig.nregs, sig.nstack, sig.returns)
    return table


def write(path: Path, exe: lift.ExeInputs, table: Mapping[int, Entry]) -> None:
    doc = {"format": FORMAT, "key": table_key(exe),
           "signatures": {f"{va:0{_ADDRESS_DIGITS}X}": entry.to_json()
                          for va, entry in sorted(table.items())}}  # fmt: skip
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write_atomic(Path(path), (json.dumps(doc, indent=1) + "\n").encode("utf-8"))


def load(path: Path, exe: lift.ExeInputs) -> Table:
    """The table at `path` for `exe`. No file, or one built under another key (table_key),
    gives no entries and a note saying so; a malformed file is SignatureError naming it."""
    path = Path(path)
    shown = _shown(exe.stem)
    if not path.is_file():
        return Table({}, f"no signature table at {shown} on this machine "
                         f"(`uv run reverseapoc signatures {exe.stem}` writes it)")  # fmt: skip
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        entries = _entries(doc)
    except (ValueError, TypeError) as exc:
        raise SignatureError(f"{path}: {exc}") from exc
    if doc["key"] != table_key(exe):
        return Table({}, f"the signature table at {shown} is stale: it was built for other "
                         "functions.csv rows, names or lift.py (`uv run reverseapoc signatures "
                         f"{exe.stem}` rebuilds it)")  # fmt: skip
    return Table(entries)


def _entries(doc: object) -> dict[int, Entry]:
    if not isinstance(doc, dict) or sorted(doc) != sorted(_KEYS):
        raise ValueError(f"not a signature table (one JSON object with {', '.join(_KEYS)})")
    if doc["format"] != FORMAT:
        raise ValueError(f"format {doc['format']!r}, not {FORMAT}")
    if not isinstance(doc["key"], str) or not isinstance(doc["signatures"], dict):
        raise ValueError("key must be a string and signatures an object")
    return {_address(key): _entry(key, value) for key, value in doc["signatures"].items()}


def _address(key: str) -> int:
    if len(key) != _ADDRESS_DIGITS or any(c not in "0123456789ABCDEF" for c in key):
        raise ValueError(f"{key!r} is no 8-digit upper-case hex address")
    return int(key, _HEX)


def _entry(key: str, value: object) -> Entry:
    if isinstance(value, dict) and sorted(value) == ["refused"]:
        if isinstance(value["refused"], str) and value["refused"]:
            return Entry(refused=value["refused"])
    elif isinstance(value, dict) and sorted(value) == sorted(_INFERRED_KEYS):
        nregs, nstack, returns = (value[k] for k in _INFERRED_KEYS)
        counts = all(type(n) is int and n >= 0 for n in (nregs, nstack))
        if counts and nregs <= len(lift.ARG_REGS) and type(returns) is bool:
            return Entry(nregs, nstack, returns)
    raise ValueError(f"entry {key} is neither {{refused}} nor {{{', '.join(_INFERRED_KEYS)}}} "
                     "with counts and a boolean")  # fmt: skip
