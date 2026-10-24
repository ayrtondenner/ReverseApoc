# Derived from KKND-Decomp tools/build_kknd.py (CC0 1.0), https://github.com/Wyrelade/KKND-Decomp
"""The land step (SPL-10): checked functions spliced into the EXE and its SHA-1 compared with the
manifest. `reverseapoc check` and `ninja verify` share this one step.

splice() keeps the original bytes at LE fixup fields only. Our self-relative call fields are not
LE fixups, so splicing our raw bytes would write our placeholder displacement there and break the
SHA-1 (research Pitfall 2). The patch builder therefore follows KKND's keep-original rule: our
bytes everywhere except under a relocated field on either side, where the original bytes stay.
That is sound only after the relocation check proved each field lands on the original target, so
a function whose check did not pass is refused, never landed.

The SHA-1 compare is independent of the check: a function whose check was wrongly reported ok
still fails here if any of its bytes outside the fields differ.

Results carry addresses, counts and SHA-1s only, never bytes.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .functions import FunctionRow
from .le import LE
from .relocs import FIELD_SIZE, RelocResult
from .splice import splice
from .targets import hash_bytes


class LandError(ValueError):
    """A function cannot be landed: its relocation check did not pass, or it does not fit."""


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

    @property
    def ok(self) -> bool:
        return self.sha1 == self.expected.lower()

    def format(self) -> str:
        count = f"landed {len(self.landed)} functions, masked {self.masked} fixup fields"
        if self.ok:
            return f"OK        {count}; sha1 {self.sha1} == manifest"
        return f"MISMATCH  {count}; sha1 {self.sha1} != manifest {self.expected}"

    def to_json(self) -> dict[str, Any]:
        """Addresses, counts and SHA-1s only."""
        return {
            "ok": self.ok,
            "sha1": self.sha1,
            "expected_sha1": self.expected,
            "landed": list(self.landed),
            "functions": len(self.landed),
            "masked_fields": self.masked,
        }


def land(
    le: LE,
    functions: Iterable[LandedFunction],
    *,
    expected_sha1: str,
    flat: bytes | None = None,
) -> LandResult:
    """Splice every function into `le` and hash the result. Refuses any function whose
    relocation check did not pass before anything is spliced."""
    functions = sorted(functions, key=lambda fn: fn.row.start)
    flat = bytes(le.load_flat(relocate=False)) if flat is None else flat
    patches = {fn.row.start: build_patch(fn, flat) for fn in functions}
    result = splice(le, patches)
    masked = len({m.fixup for m in result.masked})
    landed = tuple(fn.row.start for fn in functions)
    return LandResult(result.data, hash_bytes(result.data).sha1, expected_sha1, landed, masked)
