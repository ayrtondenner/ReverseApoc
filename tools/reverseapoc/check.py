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

Output carries names, addresses, percentages, counts and SHA-1s, never game bytes or disassembly.
Outputs go to build/<exe>/obj|base|target/<unit>.*.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .asm import data_ranges
from .compiler import compile_source
from .elf import STT_FUNC, write_elf
from .functions import FunctionRow, UnitRow, read_functions_csv, read_symbols_csv, read_units_csv
from .land import LandedFunction, LandResult, land
from .le import LE, Fixup
from .libmatch import LibMatchError, read_target, select_target
from .omf import REC_THEADR, Module, Segment, read_object
from .omf2elf import convert
from .relocs import FIELD_SIZE, OwnPublic, RelocError, RelocResult, check_function
from .splice import _write_atomic
from .symbols import SymbolTable
from .target import TargetResult, build_target
from .targets import Target, check_bare_name, load_manifest

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
    _write_atomic(path, data)


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


def checked_functions(
    module: Module, rows: Sequence[FunctionRow], exe: ExeInputs
) -> list[tuple[Defined, RelocResult]]:
    """Every defined function of `module` with its relocation check."""
    out = []
    for d in defined_functions(module, rows, exe.symbols):
        publics = own_publics(module, d.segment, rows, exe.symbols)
        out.append((d, _reloc(d, exe, publics)))
    return out


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
    """A defined function the land step did not land: its relocation check failed."""

    name: str
    va: int
    problems: tuple[str, ...]


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
        refused = [f"  REFUSED {f.name} at {_hex(f.va)}: {p}" for f in self.refused
                   for p in f.problems or ("relocation check failed",)]  # fmt: skip
        return [line, *refused]


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

    @property
    def ok(self) -> bool:
        return (bool(self.functions) and all(fn.ok for fn in self.functions)
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
            "splice": [s.to_json() for s in self.splices],
            "target": self._target_json(),
            "ok": self.ok,
        }

    def format(self) -> str:
        lines = [f"check {self.exe}/{self.unit}  {self.compiler} {' '.join(self.flags)}"]
        for fn in self.functions:
            lines += fn.format()
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
) -> SourceCheck:
    """Compile `src`, convert it, cut the target of `rows` and check every function the object
    defines among `rows` (objdiff, relocation check, bytes). `unit` names the outputs
    build/<exe>/obj|base|target/<unit>.*. Plan 05-18 calls this for the cmain386 runtime pair."""
    check_unit_name(unit)
    paths = UnitPaths.of(build_dir, exe.stem, unit)
    compiled = _compile(compile_fn, Path(src), paths.obj, options or CompileOptions())
    module = read_module(paths.obj)
    _write(paths.base, write_elf(convert(module)))
    target = build_target(exe.le, rows, exe.symbols, flat=exe.flat, fixups=exe.fixups)
    _write(paths.target, target.data)
    checked = checked_functions(module, rows, exe)
    if not checked:
        raise CheckError(f"{src} defines no function of unit {unit}")
    functions = []
    for d, reloc in checked:
        same = compare_bytes(d.ours, d.row, exe.flat, reloc)
        percent = objdiff_percent(paths.target, paths.base, d.symbol, runner=objdiff_runner)
        functions.append(FunctionCheck(d.row.name, d.row.start, d.size, percent, reloc,
                                       same.ok, same.differing, same.first_va))  # fmt: skip
    return SourceCheck(compiled.rule.spec, tuple(compiled.rule.flags), tuple(functions), target,
                       compiled.output)  # fmt: skip


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
    for unit in exe.units:
        src = Path(src_root) / exe.stem / f"{unit.unit}{SOURCE_SUFFIX}"
        if not src.is_file():
            continue  # a unit without C has nothing to land
        obj = UnitPaths.of(build_dir, exe.stem, unit.unit).obj
        if compile_fn is not None and (exe.target.name, unit.unit) not in fresh:
            _compile(compile_fn, src, obj, options)
        elif not obj.is_file():
            raise CheckError(f"{obj} not found: run ninja first (`ninja objects`) to compile "
                             f"{src}")  # fmt: skip
        rows = [row for row in exe.rows if row.unit == unit.unit]
        for d, reloc in checked_functions(read_module(obj), rows, exe):
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
    compiled first, except the (name, unit) pairs in `fresh` whose object is already built.
    `loaded` reuses ExeInputs by manifest name."""
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
                       tuple(splices), source.target, source.compile_output)  # fmt: skip

