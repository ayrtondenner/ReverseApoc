# Derived from Theme Hospital decomp tools/check.py (GPLv3), https://github.com/matteo-pacini/theme-hospital-decomp
"""`reverseapoc check EXE/UNIT`: the only tool allowed to call a function matched (SPL-11, D-16).

For one unit it compiles src/<exe>/<unit>.c (`reverseapoc cc`'s compile path), converts the
object with omf2elf, cuts the unit's target object from the LE (target.py) and, for every function
our object defines (a code public that names a row of the unit), reports three things:

- objdiff's match percent, from `objdiff-cli diff -1 <target.o> -2 <base.o> -o - <symbol>`
  (spike 005). A symbol without `match_percent` in `left.symbols` counts as 0.0. objdiff is a
  score, never the gate (P7): spike 005 showed it scores 100.0 for a wrong second relocation;
- the relocation check (relocs.check_function), with the unit's public-to-row map
  (`own_publics`) so a call to another function of our unit resolves to its original row;
- the byte comparison outside the relocated fields of either side.

Then it lands every defined function of every compiled unit of every EXE that has
config/<exe>/units.csv through land.py, the same land step `ninja verify` runs (`land_all`, SPL-10),
and compares each landed EXE's SHA-1 with config/targets.toml. A function whose relocation check
fails is refused, never landed, and makes its EXE's splice fail.

Exit codes (`CheckResult.exit_code`): 0 only when every defined function scores 100.0, passes the
relocation check and the byte comparison, and every splice SHA-1 matches with nothing refused;
1 on any mismatch; 2 (EXIT_TOOL) for a tool or usage problem (CheckError and the tool errors the
CLI lists: compile failure, objdiff-cli missing, unknown unit). A missing tool is never a pass.

`check EXE/UNIT --sweep FUNC` runs the fixed D-17 matrix instead (`sweep`): versions 10.6, 10.5,
11.0 x CPU -4r, -5r x optimisation none, -ox, -os, -ot, -oneatx, with -s toggled only when the
function calls the runtime public __CHK. Each cell compiles with a temporary one-rule cflags file
under build/sweep/<exe>/<unit>/ and is logged, one line per cell, to
build/logs/sweep-<exe>-<unit>-<func>.log, then the best cells. The sweep never lands, never edits
config/cflags.txt (DEFAULT_CFLAGS) and decides no match: a cell worth keeping becomes a per-glob
rule (D-18) and is then proven by a plain `check`.

Output carries names, addresses, percentages, counts and SHA-1s, never game bytes or disassembly.
Outputs go to build/<exe>/obj|base|target/<unit>.*, the paths of build.ninja's edges, when check
compiles with the committed config/cflags.txt, config/watcom.toml and Watcom tree. With any other
--cflags, --watcom-manifest or --watcom-dir they go to build/check-custom/<exe>/... instead
(`object_root`), so ninja never takes an object built with flags it does not use for its own
up-to-date output, and `ninja verify` lands only objects of the committed flags (D-18, WR-01).
"""

from __future__ import annotations

import functools
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any

from .asm import data_ranges
from .cflags import DEFAULT_CFLAGS, CflagsError
from .compiler import CompilerError, compile_source
from .elf import STT_FUNC, write_elf
from .fileio import write_atomic
from .functions import (
    KIND_GAME,
    KIND_THUNK,
    FunctionRow,
    UnitRow,
    read_functions_csv,
    read_symbols_csv,
    read_units_csv,
)
from .land import LandedFunction, LandResult, land
from .le import LE, Fixup
from .libmatch import LibMatchError, read_target, select_target
from .omf import REC_THEADR, Module, Public, Segment, read_object
from .omf2elf import convert
from .probe import CHK_PUBLIC
from .relocs import FIELD_SIZE, OwnPublic, RelocError, RelocResult, check_function
from .symbols import SymbolTable
from .target import TargetResult, branch_fields, build_target
from .targets import REPO_ROOT, Target, check_bare_name, load_manifest
from .watcom import DEFAULT_INSTALL, DEFAULT_WATCOM_MANIFEST

EXIT_OK, EXIT_MISMATCH, EXIT_TOOL = 0, 1, 2
OBJDIFF = "objdiff-cli"
OBJDIFF_TIMEOUT = 300  # seconds for one per-symbol diff
PERFECT = 100.0  # objdiff's match_percent for an identical symbol
CONTAINER_HINT = "docker compose run --rm build uv run reverseapoc check {target}"
SOURCE_SUFFIX = ".c"
OBJECT_SUFFIX = ".obj"
ELF_SUFFIX = ".o"
_UNIT_NAME = re.compile(r"[a-z0-9_]+")  # the units.csv rule; the name becomes a path component

Runner = Callable[[Sequence[str]], str]  # argv -> stdout


class CheckError(ValueError):
    """A tool or usage problem: unknown EXE or unit, missing source, failed compile, missing
    objdiff-cli. The CLI turns it into exit 2."""


def _hex(va: int) -> str:
    return f"0x{va:08X}"


# ---- paths and inputs ----


def exe_stem(name: str) -> str:
    """config/<stem>, src/<stem>, build/<stem>: the lowercase stem of a bare manifest name."""
    check_bare_name(name)
    return PurePosixPath(name).stem.lower()


def check_unit_name(unit: str) -> None:
    if not _UNIT_NAME.fullmatch(unit):
        raise CheckError(f"unit {unit!r} must match [a-z0-9_]+")


@dataclass(frozen=True)
class UnitPaths:
    obj: Path  # the OMF object the compiler writes
    base: Path  # our side of objdiff (omf2elf)
    target: Path  # the original's side, cut from the LE

    @classmethod
    def of(cls, build_dir: Path, stem: str, unit: str) -> UnitPaths:
        root = Path(build_dir) / stem
        return cls(root / "obj" / f"{unit}{OBJECT_SUFFIX}", root / "base" / f"{unit}{ELF_SUFFIX}",
                   root / "target" / f"{unit}{ELF_SUFFIX}")  # fmt: skip


@dataclass(frozen=True)
class ExeInputs:
    """One EXE as check sees it: the manifest entry, the verified image and its config."""

    target: Target
    stem: str
    le: LE
    flat: bytes  # le.load_flat(relocate=False)
    fixups: tuple[Fixup, ...]
    rows: tuple[FunctionRow, ...]
    units: tuple[UnitRow, ...]
    symbols: SymbolTable
    units_path: Path

    def unit_rows(self, unit: str) -> list[FunctionRow]:
        """The functions.csv rows of `unit`; CheckError for a unit units.csv does not name."""
        check_unit_name(unit)
        if all(u.unit != unit for u in self.units):
            raise CheckError(f"{self.target.name}: no unit {unit!r} in {self.units_path}")
        rows = [row for row in self.rows if row.unit == unit]
        if not rows:
            raise CheckError(f"{self.target.name}: unit {unit} has no functions.csv rows")
        return rows


def load_exe(target: Target, *, orig_dir: Path, manifest: Path, config_root: Path) -> ExeInputs:
    """The EXE (read once and checked against the manifest) with its functions.csv, units.csv
    and, when present, symbols.csv. Runtime aliases are not loaded (that needs LIB386): a fixup
    to an alias a runtime row is not named after is refused by the relocation check, never
    passed."""
    stem = exe_stem(target.name)
    config = Path(config_root) / stem
    units_path = config / "units.csv"
    if not units_path.is_file():
        raise CheckError(f"{units_path} not found: {target.name} has no units yet")
    rows = read_functions_csv(config / "functions.csv")
    units = read_units_csv(units_path)
    symbols_path = config / "symbols.csv"
    named = read_symbols_csv(symbols_path) if symbols_path.is_file() else []
    le = LE(read_target(target, orig_dir, manifest))
    table = SymbolTable.build(rows, named, data_ranges=data_ranges(le))
    flat = bytes(le.load_flat(relocate=False))
    return ExeInputs(target, stem, le, flat, tuple(le.fixups()), tuple(rows), tuple(units),
                     table, units_path)  # fmt: skip


def select_exe(targets: Sequence[Target], exe: str, manifest: Path) -> Target:
    try:
        return select_target(targets, exe, manifest)
    except LibMatchError as exc:
        raise CheckError(str(exc)) from exc


# ---- compile ----


@dataclass(frozen=True)
class CompileOptions:
    """What compile_source takes besides the source and object; None keeps its defaults."""

    cflags: Path | None = None
    watcom_manifest: Path | None = None
    watcom_dir: Path | None = None
    log: Path | None = None


# Where check compiles with non-default options. Not [a-z0-9_]+, so it is never an EXE config stem
# and never a path build.ninja writes (its unit outputs are $builddir/<stem>/...).
CUSTOM_ROOT = "check-custom"


def _is_default(path: Path | None, default: Path) -> bool:
    return path is None or Path(path).resolve() == Path(default).resolve()


def object_root(build_dir: Path, options: CompileOptions) -> Path:
    """The build dir check compiles into with `options`: `build_dir` itself, whose
    <exe>/obj|base|target paths build.ninja's edges own, only when every option is the committed
    one ninja's cc edge uses (config/cflags.txt, config/watcom.toml, the default Watcom tree);
    otherwise `build_dir`/check-custom, so ninja never sees those objects (WR-01)."""
    default = (_is_default(options.cflags, DEFAULT_CFLAGS)
               and _is_default(options.watcom_manifest, DEFAULT_WATCOM_MANIFEST)
               and _is_default(options.watcom_dir, DEFAULT_INSTALL))  # fmt: skip
    return Path(build_dir) if default else Path(build_dir) / CUSTOM_ROOT


def _compile(compile_fn: Callable[..., Any], src: Path, obj: Path, options: CompileOptions) -> Any:
    result = compile_fn(src, obj, cflags=options.cflags, manifest=options.watcom_manifest,
                        watcom_dir=options.watcom_dir, log=options.log)  # fmt: skip
    if not result.ok:
        output = result.output.strip()
        raise CheckError(f"compile failed: {result.format()}" + (f"\n{output}" if output else ""))
    return result


def read_module(path: Path) -> Module:
    data = Path(path).read_bytes()
    if not data or data[0] != REC_THEADR:
        raise CheckError(f"{path}: not an OMF object (no THEADR record first)")
    return read_object(data)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path, data)


# ---- the functions our object defines ----


@dataclass(frozen=True)
class Defined:
    """A code public of our object that names a row of the unit."""

    row: FunctionRow
    symbol: str  # its linker name, the name objdiff pairs on
    segment: Segment
    off: int
    size: int  # omf2elf's size: the next public or the segment end, trailing filler trimmed

    @property
    def ours(self) -> bytes:
        return bytes(self.segment.data[self.off : self.off + self.size])


def _linker_names(rows: Iterable[FunctionRow], symbols: SymbolTable) -> dict[str, FunctionRow]:
    return {symbols.linker_name(row.start): row for row in rows}


def defined_functions(
    module: Module, rows: Sequence[FunctionRow], symbols: SymbolTable
) -> list[Defined]:
    """Our code publics that name a row of `rows`, in row order."""
    by_name = _linker_names(rows, symbols)
    code = {seg.index: seg for seg in module.segments if seg.is_code}
    sizes = {s.name: s.size for s in convert(module).symbols
             if s.section is not None and s.type == STT_FUNC}  # fmt: skip
    found = []
    for public in module.publics:
        row, segment = by_name.get(public.name), code.get(public.segment_index)
        if row is None or segment is None or public.name not in sizes:
            continue
        found.append(Defined(row, public.name, segment, public.offset, sizes[public.name]))
    return sorted(found, key=lambda d: d.row.start)


def own_publics(
    module: Module, segment: Segment, rows: Sequence[FunctionRow], symbols: SymbolTable
) -> tuple[OwnPublic, ...]:
    """The unit's public-to-row map relocs.check_function needs (05-09): every public of
    `segment` that names a row of `rows`, sized to the next public or the segment end."""
    starts = {name: row.start for name, row in _linker_names(rows, symbols).items()}
    publics = [p for p in module.publics if p.segment_index == segment.index]
    offsets = sorted({p.offset for p in publics})
    ends = dict(zip(offsets, [*offsets[1:], len(segment.data)], strict=True))
    return tuple(OwnPublic(p.name, p.offset, ends[p.offset] - p.offset, starts[p.name])
                 for p in publics if p.name in starts and ends[p.offset] > p.offset)  # fmt: skip


def _reloc(d: Defined, exe: ExeInputs, publics: Sequence[OwnPublic]) -> RelocResult:
    """The relocation check of `d`; a RelocError (a public or row it cannot compare) is a
    failed check naming the function, not a crash of the whole report."""
    try:
        return check_function(
            d.segment, off=d.off, size=d.size, row=d.row, flat=exe.flat, fixups=exe.fixups,
            symbols=exe.symbols, own_publics=publics,
        )  # fmt: skip
    except RelocError as exc:
        return RelocResult(False, (f"{_hex(d.row.start)}: {exc}",), frozenset(), frozenset())


def with_relocs(
    module: Module, defined: Iterable[Defined], rows: Sequence[FunctionRow], exe: ExeInputs
) -> list[tuple[Defined, RelocResult]]:
    """Each of `defined` with its relocation check."""
    out = []
    for d in defined:
        publics = own_publics(module, d.segment, rows, exe.symbols)
        out.append((d, _reloc(d, exe, publics)))
    return out


def checked_functions(
    module: Module, rows: Sequence[FunctionRow], exe: ExeInputs
) -> list[tuple[Defined, RelocResult]]:
    """Every defined function of `module` with its relocation check."""
    return with_relocs(module, defined_functions(module, rows, exe.symbols), rows, exe)


# ---- the unit's account: every game/thunk row exported or marked, nothing else exported ----

CONFIGURE = "configure.py"  # owns the D-12 parser of unit files; check imports it, never copies
STUB_STATUS = "stub, not checked"
SOURCE_PROBLEM = "source"  # the name of a problem that belongs to the unit file, not a row
_REQUIRED_KINDS = (KIND_GAME, KIND_THUNK)  # runtime and data-in-code rows stay exempt (F5)


@functools.cache
def _configure() -> ModuleType:
    """configure.py of this checkout, loaded by path (it is a script, not part of the
    package), or the one already imported under that name from the same file."""
    path = REPO_ROOT / CONFIGURE
    loaded = sys.modules.get("configure")
    if loaded is not None and Path(getattr(loaded, "__file__", "")).resolve() == path.resolve():
        return loaded
    spec = importlib.util.spec_from_file_location("_reverseapoc_configure", path)
    if not path.is_file() or spec is None or spec.loader is None:
        raise CheckError(f"{path} not found: check reads unit files with its D-12 parser")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclasses look their module up while it executes
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[spec.name]
        raise
    return module


@dataclass(frozen=True)
class SourceMarks:
    marked: frozenset[str]  # names marked INCLUDE_ASM in live code
    defined: frozenset[str]  # func_ names defined in C at file scope
    problems: tuple[str, ...]  # D-12 problems configure.py reports for the file


def source_marks(text: str, rows: Sequence[FunctionRow]) -> SourceMarks:
    """The unit file read by configure.py's D-12 parser, so configure and check agree on what
    is marked and defined. Its problems are those of check_unit_source that name something
    outside the unit, or a conditional the parser refuses."""
    cfg = _configure()
    try:
        code = cfg._live_code(cfg._NOT_CODE.sub(cfg._blank, text))
    except cfg._ConditionalError as exc:
        return SourceMarks(frozenset(), frozenset(), (str(exc),))
    outside = tuple(p for p in cfg.check_unit_source(text, rows)
                    if p.endswith("is not a function of the unit"))  # fmt: skip
    return SourceMarks(frozenset(cfg._MARKER.findall(code)),
                       frozenset(cfg._file_scope_definitions(code)), outside)  # fmt: skip


@dataclass(frozen=True)
class Unaccounted:
    """A mismatch of the unit's account: a row neither checked nor a stub, or a stray public."""

    name: str
    va: int | None  # the row start; None for a public that is no row
    reason: str

    def to_json(self) -> dict[str, Any]:
        return {"name": self.name, "va": None if self.va is None else _hex(self.va),
                "reason": self.reason}  # fmt: skip

    def format(self) -> str:
        where = "" if self.va is None else f"  {_hex(self.va)}"
        return f"MISMATCH  {self.name}{where}  {self.reason}"


@dataclass(frozen=True)
class UnitAccount:
    defined: tuple[Defined, ...]  # checked and landed
    stubs: tuple[FunctionRow, ...]  # marked INCLUDE_ASM: reported, not checked, not landed
    problems: tuple[Unaccounted, ...]


def _row_reason(linker: str, exported: bool, marked: bool, elsewhere: bool, in_c: bool) -> str:
    if exported and marked:
        return f"both exported as {linker} and marked INCLUDE_ASM"
    if elsewhere:
        return f"exported as {linker} outside a code segment"
    if in_c:
        return f"defined in C but not exported as {linker}"
    return f"neither exported nor marked INCLUDE_ASM (expected public {linker})"


def _stray_reason(public: Public, code: Collection[int]) -> str:
    """Why a public that names no row of the unit is a mismatch. A `static` is an LPUBDEF
    (code review IN-01): check pairs publics with rows by their row names, which a static's
    own name never is, so it can only fail; the reason says so."""
    if not public.local:
        return f"public {public.name} is not a function of the unit"
    if public.segment_index in code:
        return (f"public {public.name} is a static (LPUBDEF) function, which check cannot pair "
                "with a row: give it its row's func_ name or keep the row INCLUDE_ASM")  # fmt: skip
    return (f"public {public.name} is static (LPUBDEF) data, which check cannot pair with a "
            "row: make it non-static")  # fmt: skip


def account_unit(
    module: Module,
    rows: Sequence[FunctionRow],
    symbols: SymbolTable,
    text: str,
    *,
    unit_file: bool = True,
) -> UnitAccount:
    """Orchestrator ruling (review round 1): every game and thunk row of `rows` is exactly one
    of (a) exported under its linker name in a code segment, then checked and landed, or (b)
    marked INCLUDE_ASM in `text`, then a stub; anything else is a mismatch naming the row.
    A public of the object that names no row of `rows` is a mismatch too.

    `text` is a unit file (src/<exe>/<unit>.c) unless `unit_file` is False: its D-12 source
    problems (a refused conditional, a marker or definition naming another unit's function)
    are mismatches even when the unit has no game or thunk row, as configure.py refuses that
    file (code review IN-03). A file that is no unit file (the 05-18 runtime pair, Watcom's own
    CMAIN386.C, which configure never reads) gets them only when a row requires them."""
    defined = defined_functions(module, rows, symbols)
    exported = {d.row.start for d in defined}
    first: dict[str, Public] = {}
    for public in module.publics:
        first.setdefault(public.name, public)
    publics = list(first)
    required = [row for row in rows if row.kind in _REQUIRED_KINDS]
    checked = unit_file or required
    marks = source_marks(text, rows) if checked else SourceMarks(frozenset(), frozenset(), ())
    stubs, problems, failed = [], [], set()
    for row in required:
        linker = symbols.linker_name(row.start)
        is_exported, is_marked = row.start in exported, row.name in marks.marked
        if is_exported != is_marked:
            stubs += [] if is_exported else [row]
            continue
        reason = _row_reason(linker, is_exported, is_marked, linker in publics,
                             row.name in marks.defined)  # fmt: skip
        problems.append(Unaccounted(row.name, row.start, reason))
        failed.add(row.start)
    names = _linker_names(rows, symbols)
    code = {seg.index for seg in module.segments if seg.is_code}
    problems += [Unaccounted(name, None, _stray_reason(first[name], code))
                 for name in publics if name not in names]  # fmt: skip
    problems += [Unaccounted(SOURCE_PROBLEM, None, p) for p in marks.problems]
    kept = tuple(d for d in defined if d.row.start not in failed)
    return UnitAccount(kept, tuple(stubs), tuple(problems))


@dataclass(frozen=True)
class ByteCompare:
    ok: bool
    differing: int  # bytes outside the relocated fields that differ, plus any length difference
    first_va: int | None


def compare_bytes(ours: bytes, row: FunctionRow, flat: bytes, reloc: RelocResult) -> ByteCompare:
    """Our bytes against the row, ignoring every relocated field of either side (as land.py's
    patch builder keeps the original there)."""
    masked = {va + i for va in reloc.ours | reloc.theirs for i in range(FIELD_SIZE)}
    length = row.end - row.start
    common = min(len(ours), length)
    diffs = [row.start + i for i in range(common)
             if row.start + i not in masked and ours[i] != flat[row.start + i]]  # fmt: skip
    extra = abs(len(ours) - length)
    first = diffs[0] if diffs else (row.start + common if extra else None)
    return ByteCompare(not diffs and not extra, len(diffs) + extra, first)


# ---- objdiff ----


def objdiff_argv(target_o: Path, base_o: Path, symbol: str) -> list[str]:
    """The one-shot diff spike 005 ran: left (-1) is the target, right (-2) our base."""
    return [OBJDIFF, "diff", "-1", str(target_o), "-2", str(base_o), "-o", "-", symbol]


def match_percent(doc: object, symbol: str) -> float:
    """`match_percent` of `symbol` in `left.symbols`; absent, malformed or out of [0, 100]
    counts as 0.0, never as a match."""
    left = doc.get("left") if isinstance(doc, dict) else None
    entries = left.get("symbols") if isinstance(left, dict) else None
    for entry in entries if isinstance(entries, list) else ():
        if not isinstance(entry, dict) or entry.get("name") != symbol:
            continue
        value = entry.get("match_percent")
        if isinstance(value, bool) or not isinstance(value, int | float):
            return 0.0
        return float(value) if math.isfinite(value) and 0.0 <= value <= PERFECT else 0.0
    return 0.0


def objdiff_percent(target_o: Path, base_o: Path, symbol: str, *, runner: Runner) -> float:
    text = runner(objdiff_argv(target_o, base_o, symbol))
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise CheckError(f"{OBJDIFF} printed no JSON for {symbol}: {exc}") from exc
    return match_percent(doc, symbol)


def default_objdiff_runner(target: str = "<exe>/<unit>") -> Runner:
    """Runs objdiff-cli from PATH; CheckError when it is absent (the host: it exists only in the
    container)."""
    path = shutil.which(OBJDIFF)
    if path is None:
        raise CheckError(
            f"{OBJDIFF} is not on PATH; it exists only in the container: run "
            f"`{CONTAINER_HINT.format(target=target)}`"
        )

    def run(argv: Sequence[str]) -> str:
        proc = subprocess.run([path, *argv[1:]], capture_output=True, text=True,
                              timeout=OBJDIFF_TIMEOUT, check=False)  # fmt: skip
        if proc.returncode != 0:
            detail = (proc.stderr or "").strip().splitlines()
            raise CheckError(f"{OBJDIFF} exited {proc.returncode}"
                             + (f": {detail[0]}" if detail else ""))  # fmt: skip
        return proc.stdout

    return run


# ---- results ----


@dataclass(frozen=True)
class FunctionCheck:
    name: str
    va: int
    size: int
    objdiff_percent: float
    reloc: RelocResult
    bytes_ok: bool
    differing: int
    first_va: int | None

    @property
    def ok(self) -> bool:
        return self.objdiff_percent == PERFECT and self.reloc.ok and self.bytes_ok

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "va": _hex(self.va),
            "size": self.size,
            "objdiff_percent": self.objdiff_percent,
            "reloc": {"ok": self.reloc.ok, "problems": list(self.reloc.problems)},
            "bytes": {"ok": self.bytes_ok, "differing": self.differing,
                      "first_va": None if self.first_va is None else _hex(self.first_va)},
        }  # fmt: skip

    def format(self) -> list[str]:
        reloc = "reloc ok" if self.reloc.ok else f"reloc FAILED ({len(self.reloc.problems)})"
        same = "bytes ok" if self.bytes_ok else (
            f"bytes {self.differing} differ from {_hex(self.first_va or self.va)}")  # fmt: skip
        head = "OK      " if self.ok else "MISMATCH"
        lines = [f"{head}  {self.name}  {_hex(self.va)}  {self.size} bytes  "
                 f"objdiff {self.objdiff_percent:g}%  {reloc}  {same}"]  # fmt: skip
        return lines + [f"          {problem}" for problem in self.reloc.problems]


@dataclass(frozen=True)
class Refused:
    """What the land step did not land and fails the splice: a function whose relocation check
    failed, or a mismatch of the unit's account (a row neither exported nor marked, a stray
    public, whose va is None)."""

    name: str
    va: int | None
    problems: tuple[str, ...]

    def lines(self) -> list[str]:
        where = "" if self.va is None else f" at {_hex(self.va)}"
        return [f"  REFUSED {self.name}{where}: {p}"
                for p in self.problems or ("relocation check failed",)]  # fmt: skip


@dataclass(frozen=True)
class ExeLand:
    """The land step for one EXE: every checked function spliced, and the SHA-1."""

    exe: str
    result: LandResult
    refused: tuple[Refused, ...] = ()

    @property
    def ok(self) -> bool:
        return self.result.ok and not self.refused

    def to_json(self) -> dict[str, Any]:
        first = self.result.first_difference
        return {
            "exe": self.exe,
            "sha1": self.result.sha1,
            "expected": self.result.expected,
            "ok": self.ok,
            "landed": len(self.result.landed),
            "refused": [r.name for r in self.refused],
            "first_difference": None if first is None else _hex(first),
        }

    def format(self) -> list[str]:
        r = self.result
        landed = f"landed {len(r.landed)}"
        if r.ok:
            line = f"{'OK' if self.ok else 'MISMATCH'} {self.exe} sha1 {r.sha1} {landed}"
        else:
            line = f"MISMATCH {self.exe} sha1 {r.sha1} != manifest {r.expected} {landed}"
            if r.first_difference is not None:
                line += f"; first difference at VA {_hex(r.first_difference)}"
        return [line, *(text for f in self.refused for text in f.lines())]


@dataclass(frozen=True)
class CheckResult:
    exe: str  # config stem, as given on the command line
    unit: str
    compiler: str
    flags: tuple[str, ...]
    functions: tuple[FunctionCheck, ...]
    splices: tuple[ExeLand, ...]
    target: TargetResult | None = None
    compile_output: str = ""
    problems: tuple[Unaccounted, ...] = ()  # the unit's account (review round 1)
    stubs: tuple[FunctionRow, ...] = ()  # marked INCLUDE_ASM: not checked, not landed

    @property
    def ok(self) -> bool:
        return (bool(self.functions) and all(fn.ok for fn in self.functions)
                and not self.problems
                and bool(self.splices) and all(s.ok for s in self.splices))  # fmt: skip

    @property
    def exit_code(self) -> int:
        return EXIT_OK if self.ok else EXIT_MISMATCH

    def _target_json(self) -> dict[str, Any]:
        if self.target is None:
            return {"raw_fields": [], "undecoded": []}
        return {"raw_fields": [{"va": _hex(f.va), "kind": f.kind} for f in self.target.raw_fields],
                "undecoded": [_hex(va) for va in self.target.undecoded]}  # fmt: skip

    def to_json(self) -> dict[str, Any]:
        return {
            "exe": self.exe,
            "unit": self.unit,
            "compiler": self.compiler,
            "flags": list(self.flags),
            "functions": [fn.to_json() for fn in self.functions],
            "problems": [p.to_json() for p in self.problems],
            "stubs": [{"name": row.name, "va": _hex(row.start), "status": STUB_STATUS}
                      for row in self.stubs],  # fmt: skip
            "splice": [s.to_json() for s in self.splices],
            "target": self._target_json(),
            "ok": self.ok,
        }

    def format(self) -> str:
        lines = [f"check {self.exe}/{self.unit}  {self.compiler} {' '.join(self.flags)}"]
        for fn in self.functions:
            lines += fn.format()
        lines += [p.format() for p in self.problems]
        lines += [f"STUB      {row.name}  {_hex(row.start)}  {STUB_STATUS}" for row in self.stubs]
        target = self._target_json()
        if target["raw_fields"] or target["undecoded"]:
            raw = ", ".join(f"{f['va']} {f['kind']}" for f in target["raw_fields"]) or "none"
            lines.append(f"target: raw fields {raw}; undecoded "
                         f"{', '.join(target['undecoded']) or 'none'}")  # fmt: skip
        for s in self.splices:
            lines += [f"splice {line}" if i == 0 else line for i, line in enumerate(s.format())]
        lines.append("ok" if self.ok else "MISMATCH")
        return "\n".join(lines)


# ---- one source ----


@dataclass(frozen=True)
class SourceCheck:
    compiler: str
    flags: tuple[str, ...]
    functions: tuple[FunctionCheck, ...]
    target: TargetResult
    compile_output: str
    problems: tuple[Unaccounted, ...] = ()
    stubs: tuple[FunctionRow, ...] = ()


def read_source(src: Path) -> str:
    """The unit file's text for the D-12 parser; undecodable bytes cannot hide a marker."""
    return Path(src).read_text(encoding="utf-8", errors="replace")


def check_source(
    exe: ExeInputs,
    unit: str,
    src: Path,
    rows: Sequence[FunctionRow],
    *,
    build_dir: Path,
    compile_fn: Callable[..., Any],
    objdiff_runner: Runner,
    options: CompileOptions | None = None,
    unit_file: bool = True,
) -> SourceCheck:
    """Compile `src`, convert it, cut the target of `rows` and check every function the object
    defines among `rows` (objdiff, relocation check, bytes). `unit` names the outputs
    <root>/<exe>/obj|base|target/<unit>.*, where <root> is object_root(build_dir, options).
    Plan 05-18 calls this for the cmain386 runtime pair with `unit_file=False`: that source is
    Watcom's own CMAIN386.C, read in place, not a unit file configure.py checks (IN-03)."""
    check_unit_name(unit)
    options = options or CompileOptions()
    paths = UnitPaths.of(object_root(build_dir, options), exe.stem, unit)
    compiled = _compile(compile_fn, Path(src), paths.obj, options)
    module = read_module(paths.obj)
    _write(paths.base, write_elf(convert(module)))
    target = build_target(exe.le, rows, exe.symbols, flat=exe.flat, fixups=exe.fixups)
    _write(paths.target, target.data)
    account = account_unit(module, rows, exe.symbols, read_source(src), unit_file=unit_file)
    checked = with_relocs(module, account.defined, rows, exe)
    if not checked and not account.problems:
        raise CheckError(f"{src} defines no function of unit {unit}")
    functions = []
    for d, reloc in checked:
        same = compare_bytes(d.ours, d.row, exe.flat, reloc)
        percent = objdiff_percent(paths.target, paths.base, d.symbol, runner=objdiff_runner)
        functions.append(FunctionCheck(d.row.name, d.row.start, d.size, percent, reloc,
                                       same.ok, same.differing, same.first_va))  # fmt: skip
    return SourceCheck(compiled.rule.spec, tuple(compiled.rule.flags), tuple(functions), target,
                       compiled.output, account.problems, account.stubs)  # fmt: skip


# ---- the land step check and `ninja verify` share ----


def _land_exe(
    exe: ExeInputs,
    *,
    src_root: Path,
    build_dir: Path,
    compile_fn: Callable[..., Any] | None,
    options: CompileOptions,
    fresh: Collection[tuple[str, str]],
) -> ExeLand:
    landed, refused = [], []
    # Without compile_fn the objects are ninja's; compiled here, they go where check_source puts
    # them for the same options, never over ninja's with other options (WR-01).
    root = Path(build_dir) if compile_fn is None else object_root(build_dir, options)
    for unit in exe.units:
        src = Path(src_root) / exe.stem / f"{unit.unit}{SOURCE_SUFFIX}"
        if not src.is_file():
            continue  # a unit without C has nothing to land
        obj = UnitPaths.of(root, exe.stem, unit.unit).obj
        if compile_fn is not None and (exe.target.name, unit.unit) not in fresh:
            _compile(compile_fn, src, obj, options)
        elif not obj.is_file():
            raise CheckError(f"{obj} not found: run ninja first (`ninja objects`) to compile "
                             f"{src}")  # fmt: skip
        rows = [row for row in exe.rows if row.unit == unit.unit]
        module = read_module(obj)
        account = account_unit(module, rows, exe.symbols, read_source(src))
        refused += [Refused(p.name, p.va, (p.reason,)) for p in account.problems]
        for d, reloc in with_relocs(module, account.defined, rows, exe):
            if reloc.ok:
                landed.append(LandedFunction(d.row, d.ours, reloc))
            else:
                refused.append(Refused(d.row.name, d.row.start, reloc.problems))
    result = land(exe.le, landed, expected_sha1=exe.target.sha1, flat=exe.flat)
    return ExeLand(exe.target.name, result, tuple(refused))


def land_all(
    manifest: Path,
    *,
    orig_dir: Path,
    config_root: Path,
    src_root: Path,
    build_dir: Path,
    compile_fn: Callable[..., Any] | None = None,
    options: CompileOptions | None = None,
    fresh: Collection[tuple[str, str]] = frozenset(),
    loaded: Mapping[str, ExeInputs] | None = None,
) -> list[ExeLand]:
    """Land every defined function of every compiled unit (a unit with src/<exe>/<unit>.c) of
    every manifest target that has config/<exe>/units.csv (orchestrator ruling F4: an EXE
    without units.csv is skipped, so SMKP.EXE never appears). With `compile_fn` each unit is
    compiled first, into object_root(build_dir, options), except the (name, unit) pairs in
    `fresh` whose object is already built there; without it, the objects ninja built under
    `build_dir` are landed. `loaded` reuses ExeInputs by manifest name."""
    loaded = loaded or {}
    options = options or CompileOptions()
    out = []
    for target in load_manifest(manifest):
        if not (Path(config_root) / exe_stem(target.name) / "units.csv").is_file():
            continue
        exe = loaded.get(target.name) or load_exe(target, orig_dir=orig_dir, manifest=manifest,
                                                  config_root=config_root)  # fmt: skip
        out.append(_land_exe(exe, src_root=src_root, build_dir=build_dir,
                             compile_fn=compile_fn, options=options, fresh=fresh))  # fmt: skip
    return out


# ---- the target object of one unit (the ninja `target` edge) ----


def write_target(
    exe: str, unit: str, out: Path, *, orig_dir: Path, manifest: Path, config_root: Path
) -> tuple[TargetResult, int]:
    """Cut the target object of `unit` and write it to `out`; returns it with its row count."""
    target = select_exe(load_manifest(manifest), exe, manifest)
    inputs = load_exe(target, orig_dir=orig_dir, manifest=manifest, config_root=config_root)
    rows = inputs.unit_rows(unit)
    result = build_target(inputs.le, rows, inputs.symbols, flat=inputs.flat, fixups=inputs.fixups)
    _write(Path(out), result.data)
    return result, len(rows)


def format_target(out: Path, result: TargetResult, rows: int) -> str:
    """One line: the object, its row count, and the raw fields and undecoded sites (05-08)."""
    raw = ", ".join(f"{_hex(f.va)} {f.kind}" for f in result.raw_fields) or "none"
    undecoded = ", ".join(_hex(va) for va in result.undecoded) or "none"
    return f"wrote {out}: {rows} rows; raw fields {raw}; undecoded {undecoded}"


# ---- one unit ----


def check_unit(
    exe: str,
    unit: str,
    *,
    orig_dir: Path,
    manifest: Path,
    config_root: Path,
    src_root: Path,
    build_dir: Path,
    watcom_dir: Path | None = None,
    cflags: Path | None = None,
    watcom_manifest: Path | None = None,
    log: Path | None = None,
    compile_fn: Callable[..., Any] | None = None,
    objdiff_runner: Runner | None = None,
) -> CheckResult:
    """The D-16 evidence for one unit: every defined function checked, then every EXE landed."""
    check_unit_name(unit)
    targets = load_manifest(manifest)
    target = select_exe(targets, exe, manifest)
    runner = objdiff_runner or default_objdiff_runner(f"{exe}/{unit}")
    inputs = load_exe(target, orig_dir=orig_dir, manifest=manifest, config_root=config_root)
    rows = inputs.unit_rows(unit)
    src = Path(src_root) / inputs.stem / f"{unit}{SOURCE_SUFFIX}"
    if not src.is_file():
        raise CheckError(f"{src} not found: scaffold it with `uv run reverseapoc units "
                         f"{target.name} --write-src {unit}`")  # fmt: skip
    compile_fn = compile_fn or compile_source
    options = CompileOptions(cflags, watcom_manifest, watcom_dir, log)
    source = check_source(inputs, unit, src, rows, build_dir=build_dir, compile_fn=compile_fn,
                          objdiff_runner=runner, options=options)  # fmt: skip
    splices = land_all(manifest, orig_dir=orig_dir, config_root=config_root, src_root=src_root,
                       build_dir=build_dir, compile_fn=compile_fn, options=options,
                       fresh={(target.name, unit)}, loaded={target.name: inputs})  # fmt: skip
    return CheckResult(exe, unit, source.compiler, source.flags, source.functions,
                       tuple(splices), source.target, source.compile_output,
                       source.problems, source.stubs)  # fmt: skip


# ---- the D-17 sweep ----

SWEEP_COMPILER = "wcc386"
SWEEP_VERSIONS = ("10.6", "10.5", "11.0")
SWEEP_CPU = ("-4r", "-5r")
SWEEP_OPT = ((), ("-ox",), ("-os",), ("-ot",), ("-oneatx",))
NO_STACK_CHECKS = "-s"
SWEEP_FPU = "-fpi"
NOT_INSTALLED = "not installed"
COMPILE_FAILED = "compile failed"
NOT_DEFINED = "not defined"
SWEEP_RULE = "*  {spec}  {flags}\n"  # one `*` rule: every source takes it


def sweep_cells(*, chk: bool) -> list[tuple[str, tuple[str, ...]]]:
    """(version, flags) of every D-17 cell: 30, or 60 when -s is toggled for a __CHK caller."""
    stacks = ((NO_STACK_CHECKS,), ()) if chk else ((NO_STACK_CHECKS,),)
    return [(version, (cpu, *opt, *stack, SWEEP_FPU)) for version in SWEEP_VERSIONS
            for cpu in SWEEP_CPU for opt in SWEEP_OPT for stack in stacks]  # fmt: skip


@dataclass(frozen=True)
class SweepCell:
    number: int  # 1-based
    version: str
    flags: tuple[str, ...]
    status: str = ""  # NOT_INSTALLED, COMPILE_FAILED, NOT_DEFINED, or "" once measured
    percent: float = 0.0
    reloc_ok: bool = False
    differing: int = 0

    @property
    def measured(self) -> bool:
        return not self.status

    def rank(self) -> tuple[bool, float, int]:
        """Smaller is better: a passing relocation check, then objdiff, then fewer bytes."""
        return (not self.reloc_ok, -self.percent, self.differing)

    def line(self) -> str:
        head = f"cell {self.number:02d}  {SWEEP_COMPILER}@{self.version}  {' '.join(self.flags)}"
        if not self.measured:
            return f"{head}  {self.status}"
        reloc = "reloc ok" if self.reloc_ok else "reloc FAILED"
        return f"{head}  objdiff {self.percent:g}%  {reloc}  differing {self.differing}"

    def to_json(self) -> dict[str, Any]:
        measured = self.measured
        return {
            "cell": self.number,
            "compiler": f"{SWEEP_COMPILER}@{self.version}",
            "flags": list(self.flags),
            "status": self.status or "measured",
            "objdiff_percent": self.percent if measured else None,
            "reloc_ok": self.reloc_ok if measured else None,
            "differing": self.differing if measured else None,
        }


@dataclass(frozen=True)
class SweepReport:
    exe: str
    unit: str
    function: str
    chk: bool
    cells: tuple[SweepCell, ...]
    best: tuple[SweepCell, ...]
    log_path: Path

    @property
    def lines(self) -> list[str]:
        caller = "yes" if self.chk else "no"
        head = f"sweep {self.exe}/{self.unit} {self.function}  calls __CHK: {caller}"
        best = ", ".join(f"cell {cell.number:02d}" for cell in self.best) or "none"
        return [head, *(cell.line() for cell in self.cells), f"best: {best}"]

    def to_json(self) -> dict[str, Any]:
        return {
            "exe": self.exe,
            "unit": self.unit,
            "function": self.function,
            "chk": self.chk,
            "cells": [cell.to_json() for cell in self.cells],
            "best": [cell.number for cell in self.best],
            "log": str(self.log_path),
        }


def calls_chk(row: FunctionRow, exe: ExeInputs) -> bool:
    """Whether `row` calls a functions.csv runtime row named __CHK."""
    chk = {r.start for r in exe.rows if r.name == CHK_PUBLIC}
    if not chk:
        return False
    sites = {fx.src_va: fx.size for fx in exe.fixups}
    return any(dest in chk for _, dest in branch_fields(row, exe.flat, sites))


def _sweep_row(exe: ExeInputs, rows: Sequence[FunctionRow], function: str) -> FunctionRow:
    for row in rows:
        if function in (row.name, exe.symbols.linker_name(row.start)):
            return row
    raise CheckError(f"{function} is not a function of the unit")


@dataclass(frozen=True)
class _SweepSetup:
    exe: ExeInputs
    rows: Sequence[FunctionRow]
    row: FunctionRow
    src: Path
    work: Path  # build/sweep/<exe>/<unit>
    target_o: Path
    compile_fn: Callable[..., Any]
    runner: Runner
    options: CompileOptions


def _compile_cell(setup: _SweepSetup, number: int, version: str, flags: Sequence[str]) -> Path:
    """The cell's object, compiled with a temporary one-rule cflags file in `setup.work`."""
    rule = setup.work / f"cell-{number:02d}.cflags"
    if rule.resolve() == Path(DEFAULT_CFLAGS).resolve():  # T-05-38: never the committed table
        raise CheckError(f"refusing to write the sweep rule over {DEFAULT_CFLAGS}")
    spec = f"{SWEEP_COMPILER}@{version}"
    _write(rule, SWEEP_RULE.format(spec=spec, flags=" ".join(flags)).encode("ascii"))
    obj = setup.work / f"cell-{number:02d}{OBJECT_SUFFIX}"
    o = setup.options
    _compile(setup.compile_fn, setup.src, obj,
             CompileOptions(rule, o.watcom_manifest, o.watcom_dir, o.log))  # fmt: skip
    return obj


def _measure(setup: _SweepSetup, number: int, version: str, flags: tuple[str, ...]) -> SweepCell:
    if not (Path(setup.options.watcom_dir or DEFAULT_INSTALL) / version).is_dir():
        return SweepCell(number, version, flags, NOT_INSTALLED)
    try:
        obj = _compile_cell(setup, number, version, flags)
    except (CheckError, CompilerError, CflagsError):
        return SweepCell(number, version, flags, COMPILE_FAILED)
    module = read_module(obj)
    found = [pair for pair in checked_functions(module, setup.rows, setup.exe)
             if pair[0].row == setup.row]  # fmt: skip
    if not found:
        return SweepCell(number, version, flags, NOT_DEFINED)
    d, reloc = found[0]
    base = setup.work / f"cell-{number:02d}{ELF_SUFFIX}"
    _write(base, write_elf(convert(module)))
    same = compare_bytes(d.ours, d.row, setup.exe.flat, reloc)
    percent = objdiff_percent(setup.target_o, base, d.symbol, runner=setup.runner)
    return SweepCell(number, version, flags, "", percent, reloc.ok, same.differing)


def _best(cells: Sequence[SweepCell]) -> tuple[SweepCell, ...]:
    measured = [cell for cell in cells if cell.measured]
    if not measured:
        return ()
    top = min(cell.rank() for cell in measured)
    return tuple(cell for cell in measured if cell.rank() == top)


def sweep(
    exe: str,
    unit: str,
    function: str,
    *,
    orig_dir: Path,
    manifest: Path,
    config_root: Path,
    src_root: Path,
    build_dir: Path,
    watcom_dir: Path | None = None,
    watcom_manifest: Path | None = None,
    log: Path | None = None,
    compile_fn: Callable[..., Any] | None = None,
    objdiff_runner: Runner | None = None,
) -> SweepReport:
    """Run the D-17 matrix for one function of `unit` and log every cell (see the module
    docstring). Never lands and never writes config/cflags.txt."""
    check_unit_name(unit)
    target = select_exe(load_manifest(manifest), exe, manifest)
    runner = objdiff_runner or default_objdiff_runner(f"{exe}/{unit}")
    inputs = load_exe(target, orig_dir=orig_dir, manifest=manifest, config_root=config_root)
    rows = inputs.unit_rows(unit)
    row = _sweep_row(inputs, rows, function)
    src = Path(src_root) / inputs.stem / f"{unit}{SOURCE_SUFFIX}"
    if not src.is_file():
        raise CheckError(f"{src} not found")
    work = Path(build_dir) / "sweep" / inputs.stem / unit
    target_o = work / f"target{ELF_SUFFIX}"
    cut = build_target(inputs.le, rows, inputs.symbols, flat=inputs.flat, fixups=inputs.fixups)
    _write(target_o, cut.data)
    options = CompileOptions(None, watcom_manifest, watcom_dir, log)
    setup = _SweepSetup(inputs, rows, row, src, work, target_o, compile_fn or compile_source,
                        runner, options)  # fmt: skip
    chk = calls_chk(row, inputs)
    cells = tuple(_measure(setup, n, version, flags)
                  for n, (version, flags) in enumerate(sweep_cells(chk=chk), start=1))  # fmt: skip
    log_path = Path(build_dir) / "logs" / f"sweep-{inputs.stem}-{unit}-{row.name}.log"
    report = SweepReport(exe, unit, row.name, chk, cells, _best(cells), log_path)
    _write(log_path, ("\n".join(report.lines) + "\n").encode("utf-8"))
    return report

