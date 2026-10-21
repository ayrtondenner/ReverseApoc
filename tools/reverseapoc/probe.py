"""The codegen probe: calibrate which idioms each Watcom version and flag set emits, from our own
clean-room probe (probe/cg_basic.c), so the same idioms can then be counted in the game's
non-library code (CID-03, D-10).

Research found mosura's register claims do not reproduce (04-RESEARCH Pitfall 9), so nothing
here is taken from a published fingerprint table: every idiom is matched by its byte encoding and
calibrated per version and flag set. Counts are evidence, not proof. Output holds counts, library
names and SHA-1s, never object or compiler bytes.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator

from . import omf
from .targets import REPO_ROOT

PROBE_DIR = REPO_ROOT / "probe"
PROBE_SOURCES = ("cg_basic.c",)
DEFAULT_PROBE_OUT = REPO_ROOT / "build" / "probe"

IDIOMS = (
    "setcc_and",
    "setcc_movzx",
    "movsd_unrolled",
    "rep_movsd_small",
    "loop_rotated",
    "loop_top_tested",
    "switch_ascending",
    "switch_descending",
)

# setcc al (0F 90..9F C0); and eax,0FFh (25 FF 00 00 00)
_SETCC_AND = re.compile(rb"\x0f[\x90-\x9f]\xc0\x25\xff\x00\x00\x00")
# setcc al (0F 90..9F C0); movzx eax,al (0F B6 C0)
_SETCC_MOVZX = re.compile(rb"\x0f[\x90-\x9f]\xc0\x0f\xb6\xc0")

Span = tuple[int, int]  # [start, end) offsets of one match inside the code


def _regex_spans(pattern: re.Pattern[bytes]) -> Callable[[bytes], Iterator[Span]]:
    def spans(code: bytes) -> Iterator[Span]:
        return (match.span() for match in pattern.finditer(code))

    return spans


def _no_spans(code: bytes) -> Iterator[Span]:
    return iter(())


_COUNTERS: dict[str, Callable[[bytes], Iterator[Span]]] = {
    "setcc_and": _regex_spans(_SETCC_AND),
    "setcc_movzx": _regex_spans(_SETCC_MOVZX),
    "movsd_unrolled": _no_spans,
    "rep_movsd_small": _no_spans,
    "loop_rotated": _no_spans,
    "loop_top_tested": _no_spans,
    "switch_ascending": _no_spans,
    "switch_descending": _no_spans,
}


def _allowed(
    span: Span, *, base: int, exclude: Iterable[Span], mask: frozenset[int]
) -> bool:
    """False when the match touches a masked offset or overlaps an excluded VA range."""
    start, end = span
    if any(offset in mask for offset in range(start, end)):
        return False
    low, high = base + start, base + end
    return not any(ex_start < high and low < ex_end for ex_start, ex_end in exclude)


def count_idioms(
    code: bytes,
    *,
    base: int = 0,
    exclude: Iterable[Span] = (),
    mask: frozenset[int] = frozenset(),
) -> dict[str, int]:
    """How often each idiom occurs in `code`, in IDIOMS order. `base` is the VA of code[0];
    `exclude` holds VA ranges [start, end) (e.g. the runtime library map) and `mask` code
    offsets (fixup sites); a match touching either by one byte is not counted."""
    exclude = tuple(exclude)
    return {
        name: sum(
            1
            for span in _COUNTERS[name](code)
            if _allowed(span, base=base, exclude=exclude, mask=mask)
        )
        for name in IDIOMS
    }


def object_code(data: bytes) -> list[tuple[bytes, frozenset[int]]]:
    """(bytes, fixup mask) of every CODE segment of one OMF object, in SEGDEF order."""
    return [(seg.data, seg.mask) for seg in omf.read_object(data).segments if seg.is_code]
