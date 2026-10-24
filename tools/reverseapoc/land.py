# Derived from KKND-Decomp tools/build_kknd.py (CC0 1.0), https://github.com/Wyrelade/KKND-Decomp
"""The land step (SPL-10): checked functions spliced into the EXE and its SHA-1 compared with the
manifest. `reverseapoc check` and `ninja verify` share this one step.

splice() keeps the original bytes at LE fixup fields only. Our self-relative call fields are not
LE fixups, so splicing our raw bytes would write our placeholder displacement there and break the
SHA-1 (research Pitfall 2). The patch builder therefore follows KKND's keep-original rule: our
bytes everywhere except under a relocated field on either side, where the original bytes stay.
That is sound only after the relocation check proved each field lands on the original target, so
a function whose check did not pass is refused, never landed. objdiff's percentage is never a
substitute for that check.

The SHA-1 compare is independent of the check: a function whose check was wrongly reported ok
still fails here if any of its bytes outside the fields differ, and the result names the first
differing VA.

Results carry addresses, counts and SHA-1s only, never bytes. write_landed refuses a path inside
orig/ and the original file itself.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .functions import FunctionRow
from .le import LE
from .relocs import FIELD_SIZE, RelocResult
from .splice import (
    SpliceError,
    SpliceResult,
    _first_difference,
    _refuse_inside_orig,
    _refuse_same_file,
    _write_atomic,
    region_at,
    splice,
)
from .targets import hash_bytes

_SHA1_DIGITS = 40
_SHA1 = re.compile(f"[0-9a-fA-F]{{{_SHA1_DIGITS}}}")


class LandError(ValueError):
    """A function cannot be landed (its relocation check did not pass, or it does not fit its
    row), or a landed EXE cannot be written where asked."""


@dataclass(frozen=True)
class LandedFunction:
    """One checked function: its functions.csv row, our bytes for it, and its check result."""

    row: FunctionRow
    ours: bytes
    reloc: RelocResult


def _hex(va: int) -> str:
    return f"0x{va:08X}"


def build_patch(fn: LandedFunction, flat: bytes) -> bytes:
    """Our bytes for `fn`, with every field in ours | theirs holding the original bytes from
    `flat` (le.load_flat(relocate=False)). Refuses a function whose check did not pass."""
    start, end = fn.row.start, fn.row.end
    if not fn.reloc.ok:
        raise LandError(f"{fn.row.name}: the relocation check did not pass; not landing it")
    if len(fn.ours) != end - start:
        raise LandError(
            f"{fn.row.name}: {len(fn.ours)} bytes of ours for a row of {end - start} bytes"
        )
    patch = bytearray(fn.ours)
    for va in sorted(fn.reloc.ours | fn.reloc.theirs):
        if not start <= va < end:
            raise LandError(f"{fn.row.name}: field at {_hex(va)} lies outside the row")
        stop = min(va + FIELD_SIZE, end)
        patch[va - start : stop - start] = flat[va:stop]
    return bytes(patch)


@dataclass(frozen=True)
class LandResult:
    data: bytes  # the landed EXE
    sha1: str
    expected: str  # the manifest's SHA-1
    landed: tuple[int, ...]  # row starts of the landed functions, sorted
    masked: int  # distinct LE fixup fields the patches covered
    first_difference: int | None = None  # VA of the first byte that differs from the original

    @property
    def ok(self) -> bool:
        return self.sha1 == self.expected.lower()

    def format(self) -> str:
        count = f"landed {len(self.landed)} functions, masked {self.masked} fixup fields"
        if self.ok:
            return f"OK        {count}; sha1 {self.sha1} == manifest"
        line = f"MISMATCH  {count}; sha1 {self.sha1} != manifest {self.expected}"
        if self.first_difference is not None:
            line += f"; first difference at VA {_hex(self.first_difference)}"
        return line

    def to_json(self) -> dict[str, Any]:
        """Addresses, counts and SHA-1s only."""
        return {
            "ok": self.ok,
            "sha1": self.sha1,
            "expected_sha1": self.expected,
            "landed": list(self.landed),
            "functions": len(self.landed),
            "masked_fields": self.masked,
            "first_difference": self.first_difference,
        }


def _patches(functions: list[LandedFunction], flat: bytes) -> dict[int, bytes]:
    """{row start: patch}, every patch built (and every check verified) before any splice."""
    patches: dict[int, bytes] = {}
    for fn in functions:
        if fn.row.start in patches:
            raise LandError(f"two functions start at {_hex(fn.row.start)}")
        patches[fn.row.start] = build_patch(fn, flat)
    return patches


def _check_sha1(value: object) -> None:
    if not isinstance(value, str) or _SHA1.fullmatch(value) is None:
        raise LandError(f"expected SHA-1 must be {_SHA1_DIGITS} hex digits, got {value!r}")


def _first_difference_va(result: SpliceResult, orig: bytes) -> int | None:
    offset = _first_difference(result.data, orig)
    if offset is None:
        return None
    return region_at(result.regions, offset).va_at(offset)


def land(
    le: LE,
    functions: Iterable[LandedFunction],
    *,
    expected_sha1: str,
    flat: bytes | None = None,
) -> LandResult:
    """Splice every function into `le` and hash the result. Refuses any function whose
    relocation check did not pass, and two functions at one start, before anything is spliced;
    overlapping functions are refused by splice(). The result is the same for any input order.

    `expected_sha1` is required and has no default: callers (05-14 `ninja verify`, 05-17
    `check`) pass the manifest's value from targets.load_manifest(). A value that is not 40 hex
    digits raises LandError."""
    _check_sha1(expected_sha1)
    functions = sorted(functions, key=lambda fn: fn.row.start)
    flat = bytes(le.load_flat(relocate=False)) if flat is None else flat
    result = splice(le, _patches(functions, flat))
    sha1 = hash_bytes(result.data).sha1
    masked = len({m.fixup for m in result.masked})
    landed = tuple(fn.row.start for fn in functions)
    first = None if sha1 == expected_sha1.lower() else _first_difference_va(result, le.data)
    return LandResult(result.data, sha1, expected_sha1, landed, masked, first)


def write_landed(result: LandResult, path: Path, *, orig_dir: Path, source: Path) -> None:
    """Write the landed EXE to `path` atomically. Refuses a path inside `orig_dir` and a path
    that is the original `source` file under any name."""
    try:
        _refuse_inside_orig(path, orig_dir)
        _refuse_same_file(path, source)
    except SpliceError as exc:
        raise LandError(str(exc)) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(path, result.data)
