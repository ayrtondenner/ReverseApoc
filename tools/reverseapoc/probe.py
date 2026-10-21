"""The codegen probe: calibrate which idioms each Watcom version and flag set emits, from our own
clean-room probe (probe/cg_basic.c), so the same idioms can then be counted in the game's
non-library code (CID-03, D-10).

Research found mosura's register claims do not reproduce (04-RESEARCH Pitfall 9), so nothing
here is taken from a published fingerprint table: every idiom is matched by its byte encoding and
calibrated per version and flag set. Counts are evidence, not proof. The matching is byte-level
over raw code, so a hit can also be data or the middle of another instruction (research A7); the
setcc and struct-copy encodings are long enough for that to be rare, while the loop and switch
counts are "not decisive" on their own (research Pattern 6). Output holds counts, library names
and SHA-1s, never object or compiler bytes.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple

from . import omf
from .cflags import Rule
from .compiler import OBJ_SUFFIX, CompilerError, Runner, check_gate, compile_rule
from .libmatch import SWEPT_VERSIONS
from .targets import REPO_ROOT

PROBE_DIR = REPO_ROOT / "probe"
PROBE_SOURCES = ("cg_basic.c",)
DEFAULT_PROBE_OUT = REPO_ROOT / "build" / "probe"
COMPILER = "wcc386"

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

# The flag sets every version is calibrated with (04-RESEARCH Pattern 6 and Pitfall 9). Every
# entry names its CPU option, so wcc386's default CPU (research A5) never matters.
FLAG_SETS = (
    ("-3r", "-s"),  # 386 register convention: setcc;movzx, rep movsd
    ("-4r", "-s"),  # 486: setcc;and on both versions, mov ecx,n; rep movsd
    ("-5r", "-s"),  # Pentium: unrolled movsd; 11.0 branches instead of setcc
    ("-5r",),  # without -s: the __CHK stack-check calls appear
    ("-4r", "-s", "-ox"),  # full optimisation at -4: switch compare order
    ("-5r", "-s", "-ox"),  # full optimisation at -5: switch compare order
    ("-5r", "-s", "-oneatx"),  # the "fastest code" set: changes loop shape
    ("-5r", "-s", "-os"),  # optimise for size
    ("-5r", "-s", "-fpi87"),  # inline x87 without the emulator: noemu387
    ("-5s", "-s"),  # stack convention: clib3s and math387s
)

Span = tuple[int, int]  # [start, end) offsets inside the code
Match = tuple[Span, ...]  # the pieces of code one idiom hit reads, in code order


# ---- byte patterns -----------------------------------------------------------------------------

# setcc al (0F 90..9F C0); and eax,0FFh (25 FF 00 00 00)
_SETCC_AND = re.compile(rb"\x0f[\x90-\x9f]\xc0\x25\xff\x00\x00\x00")
# setcc al (0F 90..9F C0); movzx eax,al (0F B6 C0)
_SETCC_MOVZX = re.compile(rb"\x0f[\x90-\x9f]\xc0\x0f\xb6\xc0")
# two or more movsd (A5) not preceded by rep (F3) or by another movsd: one unrolled copy per run
_MOVSD_RUN = re.compile(rb"(?<![\xf3\xa5])\xa5{2,}")
# mov ecx,imm32 with 1..16 (B9 01..10 00 00 00); rep movsd (F3 A5)
_REP_MOVSD_SMALL = re.compile(rb"\xb9[\x01-\x10]\x00\x00\x00\xf3\xa5")
# cmp eax,imm8 (83 F8 ib), cmp eax,imm32 (3D id) or cmp al,imm8 (3C ib); found at every offset
_COMPARE = re.compile(rb"(?=(\x83\xf8.|\x3d.{4}|\x3c.))", re.DOTALL)
_CMP_EAX_IMM32 = 0x3D
_CMP_AL_IMM8 = 0x3C
_CMP_IMM8_AT = 2  # 83 F8 ib: the immediate follows the opcode and the ModRM byte
_CMP_IMM_AT = 1  # 3D id and 3C ib: the immediate follows the opcode

# Jump opcodes (Intel SDM vol. 2, JMP and Jcc).
_JMP_REL8 = 0xEB  # jmp rel8
_JMP_REL32 = 0xE9  # jmp rel32
_JCC_REL8 = range(0x70, 0x80)  # jcc rel8 (jo .. jg)
_TWO_BYTE = 0x0F  # escape: 0F 80..8F is jcc rel32
_JCC_REL32 = range(0x80, 0x90)
_REL8_SIZE, _REL32_SIZE = 1, 4

# Shape limits: the loop top's exit test sits within 16 bytes of the backward jmp's target; a
# switch compare is followed by its jcc within 6 bytes, and the next compare of its chain starts
# within 12 bytes of that jcc (every measured probe chain, 11.0 -ox included, fits); a chain of
# at least 3 compares fits in 64.
LOOP_TOP_WINDOW = 16
SWITCH_JCC_GAP = 6
SWITCH_STEP_GAP = 12
SWITCH_WINDOW = 64
SWITCH_MIN_COMPARES = 3


class _Jump(NamedTuple):
    start: int
    end: int  # one past the displacement: the address the target is relative to
    target: int
    conditional: bool


def _rel(code: bytes, at: int, size: int) -> int:
    return int.from_bytes(code[at : at + size], "little", signed=True)


def _jump_at(code: bytes, i: int) -> _Jump | None:
    """The jmp or jcc whose opcode starts at `i`, if the bytes there encode one."""
    op = code[i]
    if op in (_JMP_REL8, _JMP_REL32) or op in _JCC_REL8:
        size = _REL8_SIZE if op != _JMP_REL32 else _REL32_SIZE
        disp, conditional = i + 1, op in _JCC_REL8
    elif op == _TWO_BYTE and i + 1 < len(code) and code[i + 1] in _JCC_REL32:
        size, disp, conditional = _REL32_SIZE, i + 2, True
    else:
        return None
    end = disp + size
    if end > len(code):
        return None
    return _Jump(i, end, end + _rel(code, disp, size), conditional)


def _jumps(code: bytes) -> list[_Jump]:
    """Every byte offset read as a jump opcode (byte-level, research A7)."""
    return [jump for i in range(len(code)) if (jump := _jump_at(code, i)) is not None]


def _span(jump: _Jump) -> Span:
    return (jump.start, jump.end)


# ---- counters: each yields the pieces of every hit ---------------------------------------------


def _regex_matches(pattern: re.Pattern[bytes]) -> Callable[[bytes], Iterator[Match]]:
    def matches(code: bytes) -> Iterator[Match]:
        return ((match.span(),) for match in pattern.finditer(code))

    return matches


def _rotated_loops(code: bytes) -> Iterator[Match]:
    """A forward jmp to a bottom test, and a later backward jcc to the instruction right after
    that jmp; one hit per backward jcc."""
    jumps = _jumps(code)
    forward_by_end: dict[int, list[_Jump]] = {}
    for jump in jumps:
        if not jump.conditional and jump.target > jump.end:
            forward_by_end.setdefault(jump.end, []).append(jump)
    for jcc in jumps:
        if not jcc.conditional or jcc.target >= jcc.start:
            continue
        entry = next(
            (j for j in forward_by_end.get(jcc.target, ()) if j.target <= jcc.start), None
        )
        if entry is not None:
            yield (_span(entry), _span(jcc))


def _top_tested_loops(code: bytes) -> Iterator[Match]:
    """A backward jmp whose target starts, within LOOP_TOP_WINDOW bytes, a forward jcc that
    exits past the backward jmp; one hit per backward jmp."""
    jumps = _jumps(code)
    conditional_at = {jump.start: jump for jump in jumps if jump.conditional}
    for back in jumps:
        if back.conditional or back.target > back.start or back.target < 0:
            continue
        window = range(back.target, min(back.target + LOOP_TOP_WINDOW, back.start))
        candidates = (conditional_at.get(at) for at in window)
        exits = (c for c in candidates if c is not None and c.end <= back.start)
        exit_test = next((c for c in exits if c.target >= back.end), None)
        if exit_test is not None:
            yield (_span(exit_test), _span(back))


class _Compare(NamedTuple):
    start: int
    end: int
    value: int
    jcc: _Jump  # the first jcc within SWITCH_JCC_GAP bytes after the compare


def _compare_value(raw: bytes) -> int:
    """The immediate: imm8 of 83 F8 is sign-extended, imm32 of 3D is signed, imm8 of 3C (al) is
    unsigned."""
    if raw[0] == _CMP_AL_IMM8:
        return raw[_CMP_IMM_AT]
    at = _CMP_IMM_AT if raw[0] == _CMP_EAX_IMM32 else _CMP_IMM8_AT
    return int.from_bytes(raw[at:], "little", signed=True)


def _paired_compares(code: bytes) -> Iterator[_Compare]:
    for match in _COMPARE.finditer(code):
        raw = match.group(1)
        start, end = match.start(), match.start() + len(raw)
        jcc = next(
            (
                jump
                for at in range(end, min(end + SWITCH_JCC_GAP + 1, len(code)))
                if (jump := _jump_at(code, at)) is not None and jump.conditional
            ),
            None,
        )
        if jcc is not None:
            yield _Compare(start, end, _compare_value(raw), jcc)


def _direction(a: int, b: int) -> int:
    return (b > a) - (b < a)


def _step(prev: _Compare, cmp: _Compare) -> int:
    """+1 or -1, the direction from prev to cmp, when cmp starts within SWITCH_STEP_GAP bytes of
    prev's jcc; 0 when it starts further away (another function) or compares the same value."""
    if cmp.start - prev.jcc.end > SWITCH_STEP_GAP:
        return 0
    return _direction(prev.value, cmp.value)


def _switch_chains(code: bytes) -> Iterator[tuple[int, Match]]:
    """(direction, pieces) of every chain of at least SWITCH_MIN_COMPARES compares, each paired
    with a jcc and starting within SWITCH_STEP_GAP bytes of the previous jcc, all within
    SWITCH_WINDOW bytes, immediates strictly monotonic. A compare that turns the direction ends
    the chain and starts the next one together with the compare before it."""
    chain: list[_Compare] = []

    def finished() -> Iterator[tuple[int, Match]]:
        if len(chain) >= SWITCH_MIN_COMPARES:
            pieces = tuple(p for c in chain for p in ((c.start, c.end), _span(c.jcc)))
            yield _direction(chain[0].value, chain[1].value), pieces

    for cmp in _paired_compares(code):
        if chain and cmp.start < chain[-1].jcc.end:
            continue  # overlaps the previous compare or its jcc: not an instruction
        step = _step(chain[-1], cmp) if chain else 0
        heading = _direction(chain[0].value, chain[1].value) if len(chain) > 1 else step
        if step and step == heading and cmp.end - chain[0].start <= SWITCH_WINDOW:
            chain.append(cmp)
            continue
        yield from finished()
        chain = [chain[-1], cmp] if step and step != heading else [cmp]
    yield from finished()


def _switches(direction: int) -> Callable[[bytes], Iterator[Match]]:
    def matches(code: bytes) -> Iterator[Match]:
        return (pieces for d, pieces in _switch_chains(code) if d == direction)

    return matches


_COUNTERS: dict[str, Callable[[bytes], Iterator[Match]]] = {
    "setcc_and": _regex_matches(_SETCC_AND),
    "setcc_movzx": _regex_matches(_SETCC_MOVZX),
    "movsd_unrolled": _regex_matches(_MOVSD_RUN),
    "rep_movsd_small": _regex_matches(_REP_MOVSD_SMALL),
    "loop_rotated": _rotated_loops,
    "loop_top_tested": _top_tested_loops,
    "switch_ascending": _switches(1),
    "switch_descending": _switches(-1),
}


def _allowed(match: Match, *, base: int, exclude: Sequence[Span], mask: frozenset[int]) -> bool:
    """False when a piece of the match touches a masked offset, or when the match (from its
    first piece to its last) overlaps an excluded VA range. Bytes between pieces, such as a loop
    body with a call in it, may be masked."""
    if any(offset in mask for start, end in match for offset in range(start, end)):
        return False
    low, high = base + match[0][0], base + match[-1][1]
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
            for match in _COUNTERS[name](code)
            if _allowed(match, base=base, exclude=exclude, mask=mask)
        )
        for name in IDIOMS
    }


def object_code(data: bytes) -> list[tuple[bytes, frozenset[int]]]:
    """(bytes, fixup mask) of every CODE segment of one OMF object, in SEGDEF order."""
    return [(seg.data, seg.mask) for seg in omf.read_object(data).segments if seg.is_code]


def chk_sites(module: omf.Module) -> int:
    """Self-relative fixups to the extern __CHK: the stack-check calls a build without -s has."""
    fixups = [f for seg in module.segments for f in seg.fixups]
    fixups += [f for comdat in module.comdats for f in comdat.fixups]
    return sum(
        1
        for f in fixups
        if not f.segment_relative and f.target_kind == "extern" and f.target_name == "__CHK"
    )


# ---- calibration -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Cell:
    """What one version and flag set emits for the probe sources."""

    version: str
    flags: tuple[str, ...]
    counts: dict[str, int]  # IDIOMS order, summed over every CODE segment of every source
    chk_calls: int
    default_libraries: tuple[str, ...]
    normalized_sha1: str


@dataclass(frozen=True)
class Calibration:
    cells: tuple[Cell, ...]  # SWEPT_VERSIONS order, then flag-set order
    skipped: tuple[tuple[str, str], ...]  # (version, reason) for versions the gate refused

    def cell(self, version: str, flags: Sequence[str]) -> Cell:
        flags = tuple(flags)
        found = next((c for c in self.cells if (c.version, c.flags) == (version, flags)), None)
        if found is None:
            raise KeyError(f"no calibration cell for {version} {' '.join(flags)}")
        return found

    def ties(self) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
        """(flags, versions) for versions whose objects are equal after normalization under the
        same flags (D-10: stated as a tie, never merged or voted apart), in cell order."""
        groups: dict[tuple[tuple[str, ...], str], list[str]] = {}
        for c in self.cells:
            groups.setdefault((c.flags, c.normalized_sha1), []).append(c.version)
        return [(flags, tuple(vs)) for (flags, _), vs in groups.items() if len(vs) > 1]

    def format(self) -> str:
        header = ["version", f"{'flags':<20}", *IDIOMS, "chk", "default_libraries", "sha1"]
        lines = ["  ".join(header)]
        for c in self.cells:
            counts = (f"{c.counts[name]:>{len(name)}}" for name in IDIOMS)
            libraries = ",".join(c.default_libraries) or "-"
            row = [f"{c.version:<7}", f"{' '.join(c.flags):<20}", *counts]
            lines.append("  ".join([*row, f"{c.chk_calls:>3}", libraries, c.normalized_sha1]))
        lines += [f"tie: {' '.join(flags)}: {' '.join(vs)}" for flags, vs in self.ties()]
        lines += [f"skipped: {version}: {reason}" for version, reason in self.skipped]
        return "\n".join(lines)

    def to_json(self) -> dict[str, Any]:
        """The same numbers as format(): counts, library names and SHA-1s, never bytes."""
        return {
            "idioms": list(IDIOMS),
            "cells": [
                {
                    "version": c.version,
                    "flags": list(c.flags),
                    "counts": dict(c.counts),
                    "chk_calls": c.chk_calls,
                    "default_libraries": list(c.default_libraries),
                    "normalized_sha1": c.normalized_sha1,
                }
                for c in self.cells
            ],
            "ties": [{"flags": list(f), "versions": list(vs)} for f, vs in self.ties()],
            "skipped": [{"version": v, "reason": r} for v, r in self.skipped],
        }


def _version_order(versions: Iterable[str]) -> list[str]:
    """SWEPT_VERSIONS order, then any other version by name; duplicates dropped."""
    rank = {version: i for i, version in enumerate(SWEPT_VERSIONS)}
    return sorted(set(versions), key=lambda v: (rank.get(v, len(rank)), v))


def flag_id(flags: Sequence[str]) -> str:
    """The directory name of a flag set: the flags without dashes, joined by "_"."""
    return "_".join(flag.lstrip("-") for flag in flags)


def _combined_sha1(hashes: list[str]) -> str:
    """One source: its normalized SHA-1. Several: a SHA-1 over theirs, in source order."""
    if len(hashes) == 1:
        return hashes[0]
    return hashlib.sha1("\n".join(hashes).encode("ascii")).hexdigest()


def _cell(version: str, flags: tuple[str, ...], objects: list[tuple[Path, str]]) -> Cell:
    """Sum the counts and stack checks over the objects; join their default libraries."""
    counts = dict.fromkeys(IDIOMS, 0)
    chk_calls = 0
    libraries: list[str] = []
    for obj, _ in objects:
        data = obj.read_bytes()
        for code, mask in object_code(data):
            for name, count in count_idioms(code, mask=mask).items():
                counts[name] += count
        module = omf.read_object(data)
        chk_calls += chk_sites(module)
        libraries += [lib for lib in module.default_libraries if lib not in libraries]
    sha1 = _combined_sha1([normalized for _, normalized in objects])
    return Cell(version, flags, counts, chk_calls, tuple(libraries), sha1)


def calibrate(
    versions: Iterable[str] = SWEPT_VERSIONS,
    flag_sets: Iterable[Sequence[str]] = FLAG_SETS,
    *,
    sources: Iterable[str | Path] = PROBE_SOURCES,
    out_dir: Path | str = DEFAULT_PROBE_OUT,
    root: Path | str | None = None,
    manifest: Path | str | None = None,
    watcom_dir: Path | str | None = None,
    runner: Runner | None = None,
    platform: str | None = None,
    log: Path | str | None = None,
    stamps: Path | str | None = None,
) -> Calibration:
    """Compile every probe source with every version whose gate passes and every flag set, into
    out_dir/<version>/<flag id>/<stem>.obj, and record one Cell per (version, flags). A version
    the gate refuses is listed as skipped with the reason; a failed compile raises CompilerError
    naming the cell. Sources are names under PROBE_DIR, or paths."""
    out_dir = Path(out_dir)
    sources = [PROBE_DIR / source for source in sources]
    flag_sets = [tuple(flags) for flags in flag_sets]
    options: dict[str, Any] = dict(
        manifest=manifest, watcom_dir=watcom_dir, runner=runner, platform=platform, stamps=stamps
    )
    cells: list[Cell] = []
    skipped: list[tuple[str, str]] = []
    for version in _version_order(versions):
        try:
            check_gate(COMPILER, version, **options)
        except CompilerError as exc:
            skipped.append((version, str(exc)))
            continue
        for flags in flag_sets:
            rule = Rule("*", COMPILER, version, flags, 0)
            cell_dir = out_dir / version / flag_id(flags)
            objects = [_compile_probe(rule, src, cell_dir, root, log, options) for src in sources]
            cells.append(_cell(version, flags, objects))
    return Calibration(tuple(cells), tuple(skipped))


def _compile_probe(
    rule: Rule,
    src: Path,
    cell_dir: Path,
    root: Path | str | None,
    log: Path | str | None,
    options: dict[str, Any],
) -> tuple[Path, str]:
    """(object, normalized SHA-1) of one probe source compiled into cell_dir/<stem>.obj."""
    obj = cell_dir / f"{src.stem}{OBJ_SUFFIX}"
    result = compile_rule(rule, src, obj, root=root, log=log, **options)
    if not result.ok or result.normalized_sha1 is None:
        raise CompilerError(
            f"probe compile failed: {rule.version} {' '.join(rule.flags)} {src}: "
            f"exit {result.returncode}\n{result.output}"
        )
    return obj, result.normalized_sha1
