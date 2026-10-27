"""`reverseapoc` command line: ingest, check-orig, parse-le, rebuild, cc, omf2elf, libmatch,
cppscan, probe, asm, score, discover, functions, units, ghidra-export, lint, check, target, land,
gate, context, attempt, drive, mechanics, fetch-watcom, install-watcom, check-watcom."""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from . import asmclass, attempt, driver, flags, locate, mechanics, probe
from .asm import AsmError, data_ranges, select_rows, write_listings
from .asmclass import AsmClassError
from .attempt import AttemptError
from .cflags import DEFAULT_CFLAGS, CflagsError
from .check import (
    DEFAULT_CONFIG,
    DEFAULT_SRC,
    EXIT_TOOL,
    CheckError,
    check_unit,
    format_target,
    land_all,
    sweep,
    write_target,
)
from .compiler import DEFAULT_LOG, CompilerError, compile_source
from .contextpack import ContextPackError, write_pack
from .cppscan import CppScanError
from .cppscan import scan as cpp_scan
from .discover import DiscoverError, discover
from .elf import ElfError
from .fileio import write_atomic
from .functions import (
    KINDS,
    RUNTIME_VERSION,
    VERDICT_RULE,
    FunctionRow,
    FunctionsError,
    Reconciled,
    functions_csv_path,
    read_boundaries_csv,
    read_functions_csv,
    read_symbols_csv,
    read_units_csv,
    reconcile,
    seed_runtime_rows,
    symbols_csv_path,
    write_boundaries_csv,
    write_functions_csv,
    write_units_csv,
)
from .gate import GateResult, GateRoots, gate_all, gate_partial, gate_units
from .ghidra import (
    DEFAULT_ASM_DIR,
    DEFAULT_EXPORT_DIR,
    GhidraError,
    export_drafts,
    export_functions,
    read_ghidra_export,
)
from .ingest import IngestError, ingest
from .iso9660 import ISOError
from .land import LandError, write_landed
from .le import LE, LEError, format_summary
from .libmatch import (
    SWEPT_VERSIONS,
    LibMatchError,
    LoadedLibrary,
    MatchRange,
    check_versions,
    load_libraries,
    read_runtime_csv,
    read_target,
    refuse_output,
    runtime_csv_path,
    scan_exe,
    select_target,
    write_runtime_csv,
)
from .lint import LintError, run_lint
from .locate import LocateError
from .mechanics import MechanicsError
from .omf import OMFError
from .omf2elf import Omf2ElfError, convert_file
from .probe import CHK_PUBLIC, ProbeError
from .relocs import RelocError
from .score import ScoreError, ScoreReport, assess
from .splice import DEFAULT_OUT, SpliceError, rebuild
from .status import StatusError
from .symbols import SymbolError, SymbolTable
from .target import TargetError
from .targets import (
    DEFAULT_MANIFEST,
    DEFAULT_ORIG,
    REPO_ROOT,
    ManifestError,
    Target,
    check_orig,
    config_dir,
    load_manifest,
)
from .units import (
    UnitsError,
    assign_units,
    chk_callers,
    draft_units,
    scaffold_unit,
    write_unit_source,
)
from .watcom import (
    ARCHIVE_BASE,
    DEFAULT_INSTALL,
    DEFAULT_MEDIA,
    DEFAULT_WATCOM_MANIFEST,
    MEDIA_NOTICE,
    WatcomError,
    check_watcom,
    fetch_watcom,
    install_version,
    load_watcom_manifest,
    select,
)


def _cmd_ingest(args: argparse.Namespace) -> int:
    result = ingest(orig_dir=args.orig, manifest=args.manifest, dotenv_path=args.env_file)
    print(result.format())
    return 0 if result.report.ok else 1


def _cmd_check_orig(args: argparse.Namespace) -> int:
    report = check_orig(args.orig, args.manifest)
    print(report.format())
    return 0 if report.ok else 1


def _cmd_parse_le(args: argparse.Namespace) -> int:
    summary = LE(args.file).summary()
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(format_summary(summary))
    return 0


def _cmd_rebuild(args: argparse.Namespace) -> int:
    try:
        report = rebuild(args.orig, args.out, args.manifest, exe=args.exe)
    except (LEError, ManifestError, OSError):
        # A failure before any target (manifest, --exe, --out): with --json, stdout is still a
        # list, and main() prints the error line (WR-04).
        if args.json:
            print("[]")
        raise
    if args.json:
        print(json.dumps(report.to_json(), indent=2))
    else:
        print(report.format())
    return 0 if report.ok else 1


def _cmd_cc(args: argparse.Namespace) -> int:
    result = compile_source(
        args.src,
        args.obj,
        cflags=args.cflags,
        manifest=args.manifest,
        watcom_dir=args.watcom_dir,
        log=args.log,
    )
    if result.output.strip():
        # With --json, stdout stays one JSON document; the compiler's messages go to stderr.
        print(result.output.rstrip("\n"), file=sys.stderr if args.json else sys.stdout)
    if args.json:
        print(json.dumps(result.to_json(), indent=2))
    else:
        print(result.format())
    return 0 if result.ok else 1


def _add_cc_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "cc",
        help="compile one C source with the Watcom version and flags config/cflags.txt assigns "
        "to it",
    )
    p.add_argument("src", type=Path, help="the C source, inside the repository")
    p.add_argument("-o", "--obj", type=Path, required=True, help="the object to write")
    p.add_argument("--cflags", type=Path, default=DEFAULT_CFLAGS, help=default)
    p.add_argument("--manifest", type=Path, default=DEFAULT_WATCOM_MANIFEST, help=default)
    p.add_argument("--watcom-dir", type=Path, default=DEFAULT_INSTALL, help=default)
    p.add_argument("--log", type=Path, default=DEFAULT_LOG, help=default)
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    p.set_defaults(func=_cmd_cc)


def _cmd_omf2elf(args: argparse.Namespace) -> int:
    result = convert_file(args.src, args.output)
    print(json.dumps(result.to_json(), indent=2) if args.json else result.format())
    return 0


def _add_omf2elf_command(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "omf2elf",
        help="convert a Watcom OMF object into an ELF32 relocatable object for objdiff",
    )
    p.add_argument("src", type=Path, help="the OMF object to convert")
    p.add_argument("-o", "--output", type=Path, required=True, help="the ELF object to write")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    p.set_defaults(func=_cmd_omf2elf)


def _refuse_partial_sweep(
    libraries: list[LoadedLibrary], versions: list[str], watcom_dir: Path
) -> None:
    """--write replaces the committed D-06 map, whose rows do not record which versions were
    swept: every SWEPT_VERSIONS entry and every --versions entry must load at least one OMF
    library, or a version would drop out of the rows without anyone seeing it."""
    loaded = {library.version for library in libraries}
    missing = [v for v in dict.fromkeys([*SWEPT_VERSIONS, *versions]) if v not in loaded]
    if missing:
        raise LibMatchError(
            f"--write needs the libraries of every swept version; none loaded under {watcom_dir} "
            f"for {', '.join(missing)} (install it, or use --output PATH for a partial sweep)"
        )


def _cmd_libmatch(args: argparse.Namespace) -> int:
    target = select_target(load_manifest(args.manifest), args.exe, args.manifest)
    output = runtime_csv_path(target.name) if args.write else args.output
    if output is not None:
        # The default trees stay protected when --orig or --watcom-dir point elsewhere.
        refuse_output(output, args.orig, DEFAULT_ORIG, args.watcom_dir, DEFAULT_INSTALL)
    check_versions(args.versions)
    data = read_target(target, args.orig, args.manifest)
    libraries, skipped = load_libraries(args.watcom_dir, args.versions)
    if not libraries:
        raise LibMatchError(
            f"no OMF library found under {args.watcom_dir} for versions {' '.join(args.versions)}"
        )
    if args.write:
        _refuse_partial_sweep(libraries, args.versions, args.watcom_dir)
    report = scan_exe(LE(data), libraries, exe=target.name, skipped=skipped)
    if args.json:
        print(json.dumps(report.to_json(), indent=2))
    else:
        print(report.format())
    if output is not None:
        write_runtime_csv(output, report, target.name)
        print(f"wrote {output}", file=sys.stderr)
    return 0


def _add_libmatch_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "libmatch",
        help="place Watcom runtime library modules in an EXE's code object and write "
        "config/<exe>/runtime.csv",
    )
    p.add_argument("exe", metavar="EXE", help="manifest name or its stem (case-insensitive)")
    p.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help=default)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=default)
    p.add_argument("--watcom-dir", type=Path, default=DEFAULT_INSTALL, help=default)
    p.add_argument(
        "--versions", nargs="+", default=list(SWEPT_VERSIONS), metavar="VERSION", help=default
    )
    where = p.add_mutually_exclusive_group()
    where.add_argument(
        "--write", action="store_true", help="write config/<exe>/runtime.csv (D-06, D-16)"
    )
    where.add_argument("--output", type=Path, metavar="PATH", help="write the CSV to PATH")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    p.set_defaults(func=_cmd_libmatch)


def _cmd_cppscan(args: argparse.Namespace) -> int:
    target = select_target(load_manifest(args.manifest), args.exe, args.manifest)
    runtime = args.runtime if args.runtime is not None else runtime_csv_path(target.name)
    if not Path(runtime).is_file():
        raise CppScanError(
            f"runtime map {runtime} not found; run `uv run reverseapoc libmatch {target.name} "
            "--write` (or --output PATH, then pass --runtime PATH)"
        )
    data = read_target(target, args.orig, args.manifest)
    report = cpp_scan(LE(data), read_runtime_csv(runtime), args.watcom_dir, exe=target.name)
    if args.json:
        print(json.dumps(report.to_json(), indent=2))
    else:
        print(report.format())
    return 0  # the verdict is information, not a failure


def _add_cppscan_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "cppscan",
        help="look for C++ evidence (static init/destructor tables, C++ runtime, mangled names) "
        "and report C or C++ per EXE",
    )
    p.add_argument("exe", metavar="EXE", help="manifest name or its stem (case-insensitive)")
    p.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help=default)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=default)
    p.add_argument("--watcom-dir", type=Path, default=DEFAULT_INSTALL, help=default)
    p.add_argument(
        "--runtime",
        type=Path,
        metavar="CSV",
        help="the runtime map from libmatch; default: config/<exe>/runtime.csv",
    )
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    p.set_defaults(func=_cmd_cppscan)


def _read_calibration(path: Path) -> probe.Calibration:
    """The calibration JSON at `path`; a file that is not JSON or not the to_json() shape is
    refused with an error naming the file."""
    try:
        return probe.Calibration.from_json(json.loads(Path(path).read_text(encoding="utf-8")))
    except (ValueError, UnicodeDecodeError) as exc:  # JSONDecodeError and ProbeError included
        raise ProbeError(
            f"{path}: not a calibration from `reverseapoc probe calibrate`: {exc}"
        ) from exc


def _consistent_lines(calibration: probe.Calibration, cells: list[probe.Cell]) -> list[str]:
    """The consistent cells as "<version> <flags>", then the ties among them only (D-10). The
    header keeps the `consistent:` prefix (plan 04-10 greps it) and names the filter after the
    count: the decisive idiom families, not the other evidence lines."""
    families = ", ".join(probe.DECISIVE_FAMILIES)
    lines = [
        f"consistent: {len(cells)} of {len(calibration.cells)} calibration cells "
        f"(decisive idiom families {families} only; not checked against the other evidence lines)"
    ]
    lines += [f"  {cell.version} {' '.join(cell.flags)}" for cell in cells]
    ties = probe.Calibration(tuple(cells), ()).ties()
    lines += [f"ties: {' '.join(flags)}: {' '.join(vs)}" for flags, vs in ties] or ["ties: none"]
    lines += [f"calibration skipped: {version}" for version, _ in calibration.skipped]
    return lines


def _probe_scan(args: argparse.Namespace) -> int:
    target = select_target(load_manifest(args.manifest), args.exe, args.manifest)
    rows = probe.runtime_rows(target.name, args.runtime)
    calibration = _read_calibration(args.calibration) if args.calibration else None
    data = read_target(target, args.orig, args.manifest)
    scan = probe.scan_exe(LE(data), rows, exe=target.name)
    cells = probe.consistent_cells(calibration, scan) if calibration is not None else []
    if args.json:
        report = scan.to_json()
        if calibration is not None:
            report["consistent"] = [{"version": c.version, "flags": list(c.flags)} for c in cells]
            ties = probe.Calibration(tuple(cells), ()).ties()
            report["ties"] = [{"flags": list(f), "versions": list(vs)} for f, vs in ties]
            report["calibration_skipped"] = [version for version, _ in calibration.skipped]
        print(json.dumps(report, indent=2))
        return 0
    print(scan.format())
    if calibration is not None:
        print("\n".join(_consistent_lines(calibration, cells)))
    return 0  # the verdict is information, not a failure


def _probe_calibrate(args: argparse.Namespace) -> int:
    refuse_output(args.output, DEFAULT_ORIG, args.watcom_dir, DEFAULT_INSTALL)
    check_versions(args.versions)
    calibration = probe.calibrate(args.versions, manifest=args.manifest, watcom_dir=args.watcom_dir)
    print(json.dumps(calibration.to_json(), indent=2) if args.json else calibration.format())
    if calibration.skipped or not calibration.cells:
        # A gate refusal is fatal, as in `cc`: a calibration without the refused version would
        # let a later `probe scan --calibration` leave it out without saying so.
        refused = "; ".join(f"{version}: {reason}" for version, reason in calibration.skipped)
        raise ProbeError(
            f"not writing {args.output}: the gate refused {refused or 'every version'}; "
            "fix or install the version, or leave it out of --versions"
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(calibration.to_json(), indent=2) + "\n"
    write_atomic(output, text.encode("utf-8"))
    print(f"wrote {output}", file=sys.stderr)
    return 0


def _cmd_probe(args: argparse.Namespace) -> int:
    return {"calibrate": _probe_calibrate, "scan": _probe_scan}[args.probe_command](args)


def _add_probe_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "probe",
        help="calibrate the codegen idioms per Watcom version and flag set, and count them in an "
        "EXE's non-library code (CID-03, D-10)",
    )
    probe_sub = p.add_subparsers(dest="probe_command", required=True)
    c = probe_sub.add_parser(
        "calibrate",
        help="compile probe/cg_basic.c with every version and flag set and write the idiom table "
        "as JSON",
    )
    c.add_argument(
        "--versions", nargs="+", default=list(SWEPT_VERSIONS), metavar="VERSION", help=default
    )
    c.add_argument("--manifest", type=Path, default=DEFAULT_WATCOM_MANIFEST, help=default)
    c.add_argument("--watcom-dir", type=Path, default=DEFAULT_INSTALL, help=default)
    c.add_argument(
        "--output", type=Path, default=probe.DEFAULT_PROBE_OUT / "calibration.json", help=default
    )
    c.add_argument("--json", action="store_true", help="print the calibration as JSON")
    s = probe_sub.add_parser(
        "scan",
        help="count the idioms in an EXE's code object outside its runtime map, with one "
        "evidence line per observable flag",
    )
    s.add_argument("exe", metavar="EXE", help="manifest name or its stem (case-insensitive)")
    s.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help=default)
    s.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=default)
    s.add_argument(
        "--runtime",
        type=Path,
        metavar="CSV",
        help="the runtime map from libmatch; default: config/<exe>/runtime.csv",
    )
    s.add_argument(
        "--calibration",
        type=Path,
        metavar="JSON",
        help="the output of `probe calibrate`: also list the consistent cells and their ties",
    )
    s.add_argument("--json", action="store_true", help="print the scan as JSON")
    p.set_defaults(func=_cmd_probe)


# ---- split reading aids: asm ----

DEFAULT_ASM = REPO_ROOT / "asm"


@dataclass(frozen=True)
class _SplitInputs:
    target: Target
    le: LE
    rows: list[FunctionRow]
    symbols: SymbolTable


def _split_inputs(args: argparse.Namespace, target: Target) -> _SplitInputs:
    """The EXE (checked against the manifest), its functions.csv rows and its symbol table."""
    functions = args.functions or functions_csv_path(target.name)
    symbols = args.symbols or symbols_csv_path(target.name)
    rows = read_functions_csv(functions)
    le = LE(read_target(target, args.orig, args.manifest))
    table = SymbolTable.build(rows, read_symbols_csv(symbols), data_ranges=data_ranges(le))
    return _SplitInputs(target, le, rows, table)


def _hex_address(value: str) -> int:
    try:
        return int(value, 16)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a hex address") from exc


def _cmd_asm(args: argparse.Namespace) -> int:
    target = select_target(load_manifest(args.manifest), args.exe, args.manifest)
    out_dir = Path(args.out) / config_dir(target.name).name
    # Listings are disassembly-class output: never inside orig/ or the Watcom tree (T-05-25).
    refuse_output(out_dir, args.orig, DEFAULT_ORIG, DEFAULT_INSTALL)
    inputs = _split_inputs(args, target)
    rows = select_rows(inputs.rows, inputs.symbols, only=args.only)
    report = write_listings(
        rows,
        flat=inputs.le.load_flat(relocate=False),
        fixups=inputs.le.fixups(),
        symbols=inputs.symbols,
        out_dir=out_dir,
    )
    print(json.dumps(report.to_json(), indent=2) if args.json else report.format())
    return 0


def _add_split_inputs(p: argparse.ArgumentParser) -> None:
    default = "default: %(default)s"
    p.add_argument("exe", metavar="EXE", help="manifest name or its stem (case-insensitive)")
    p.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help=default)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=default)
    p.add_argument(
        "--functions", type=Path, metavar="CSV", help="default: config/<exe>/functions.csv"
    )
    p.add_argument("--symbols", type=Path, metavar="CSV", help="default: config/<exe>/symbols.csv")


def _add_asm_command(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "asm",
        help="write one Intel-syntax listing per functions.csv row into the gitignored "
        "asm/<exe>/ (SPL-05)",
    )
    _add_split_inputs(p)
    p.add_argument(
        "--out", type=Path, default=DEFAULT_ASM, help="listing root; default: %(default)s"
    )
    p.add_argument(
        "--only",
        type=_hex_address,
        metavar="ADDR",
        help="list only the row containing this hex address",
    )
    p.add_argument("--json", action="store_true", help="print the count and directory as JSON")
    p.set_defaults(func=_cmd_asm)


def _runtime_starts(target: Target) -> set[int]:
    """The starts of the committed runtime.csv rows (D-06), when that file exists."""
    path = runtime_csv_path(target.name)
    return {row.start for row in read_runtime_csv(path)} if path.is_file() else set()


def _chk_targets(inputs: _SplitInputs) -> set[int]:
    """Where __CHK lives: rows named so, and the runtime public of that name."""
    targets = {row.start for row in inputs.rows if row.name == CHK_PUBLIC}
    if CHK_PUBLIC in inputs.symbols.names:
        targets.add(inputs.symbols.names[CHK_PUBLIC])
    return targets


def _cmd_score(args: argparse.Namespace) -> int:
    target = select_target(load_manifest(args.manifest), args.exe, args.manifest)
    inputs = _split_inputs(args, target)
    assessments = assess(
        inputs.rows,
        flat=inputs.le.load_flat(relocate=False),
        fixups=inputs.le.fixups(),
        symbols=inputs.symbols,
        chk_targets=_chk_targets(inputs),
        runtime_starts=_runtime_starts(target),
        page_size=inputs.le.page_size,
    )
    report = ScoreReport.build(target.name, assessments, inputs.symbols, args.top)
    print(json.dumps(report.to_json(), indent=2) if args.json else report.format())
    return 0


def _add_score_command(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "score",
        help="apply the P16 first-match filter and rank the survivors easiest-first (D-15); "
        "prints addresses and names only",
    )
    _add_split_inputs(p)
    p.add_argument("--top", type=int, default=10, help="candidates to print; default: %(default)s")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    p.set_defaults(func=_cmd_score)


# ---- the function list: discover, functions (SPL-02, D-07, D-08, D-10) ----


def _cmd_discover(args: argparse.Namespace) -> int:
    target = select_target(load_manifest(args.manifest), args.exe, args.manifest)
    le = LE(read_target(target, args.orig, args.manifest))
    found = discover(le, runtime_starts=_runtime_starts(target))
    print(json.dumps(found.to_json(), indent=2) if args.json else found.format())
    return 0


def _add_discover_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "discover",
        help="run the capstone recursive descent over an EXE's code object and print the counts "
        "(starts per evidence kind, decoded bytes, jump tables)",
    )
    p.add_argument("exe", metavar="EXE", help="manifest name or its stem (case-insensitive)")
    p.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help=default)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=default)
    p.add_argument("--json", action="store_true", help="print the counts as JSON")
    p.set_defaults(func=_cmd_discover)


def _runtime_matches(runtime: Path | None, target: Target) -> list[MatchRange]:
    """The runtime.csv rows (04 D-06): `runtime`, else the committed config/<exe>/runtime.csv."""
    path = runtime if runtime is not None else runtime_csv_path(target.name)
    if not Path(path).is_file():
        raise FunctionsError(
            f"runtime map {path} not found; run `uv run reverseapoc libmatch {target.name} "
            "--write` (or --output PATH, then pass --runtime PATH)"
        )
    return read_runtime_csv(path)


def _seeded_runtime_rows(matches: list[MatchRange], watcom_dir: Path) -> list[FunctionRow]:
    """The runtime functions.csv rows, split at the public offsets of the installed LIB386 of
    the version each row is seeded from (10.6 where the row lists it, else its first)."""
    if not matches:
        return []
    versions = {RUNTIME_VERSION if RUNTIME_VERSION in m.versions else m.versions[0]
                for m in matches if m.versions}  # fmt: skip
    libraries, _ = load_libraries(watcom_dir, sorted(versions))
    return seed_runtime_rows(matches, libraries)


def _existing(out: Path, committed: Path) -> Path | None:
    """The file a regeneration keeps hand-written columns from: the one it is about to replace,
    else the committed one."""
    return next((path for path in (out, committed) if path.is_file()), None)


def _functions_report(name: str, result: Reconciled) -> dict:
    kinds = {kind: sum(1 for r in result.functions if r.kind == kind) for kind in KINDS}
    verdicts = [row.verdict for row in result.boundaries]
    auto = sum(1 for v in verdicts if v == VERDICT_RULE)
    missing = sum(1 for v in verdicts if not v)
    return {
        "exe": name,
        "functions": len(result.functions),
        "kinds": kinds,
        "disagreements": len(verdicts),
        "verdicts": {"auto": auto, "hand": len(verdicts) - auto - missing, "missing": missing},
        "dropped_ghidra": result.dropped_ghidra,
        # Hand verdicts that did not survive (review round 1): addresses and verdict words only.
        "replaced": [{"address": f"0x{a:08X}", "verdict": v} for a, v in result.replaced],
        "dropped_hand": [f"0x{a:08X}" for a in result.dropped_hand],
    }


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _format_functions_report(report: dict) -> str:
    kinds = ", ".join(f"{n} {kind}" for kind, n in report["kinds"].items())
    verdicts = report["verdicts"]
    missing = verdicts["missing"]
    lines = [
        f"{report['exe']}: {report['functions']} functions ({kinds})",
        f"{report['disagreements']} disagreements: {verdicts['auto']} auto (rule), "
        f"{verdicts['hand']} hand, {_plural(missing, 'missing verdict')}",
        f"{report['dropped_ghidra']} Ghidra entries outside the code object dropped",
    ]
    if replaced := report["replaced"]:
        changes = ", ".join(f"{r['address']} {r['verdict']} -> {VERDICT_RULE}" for r in replaced)
        lines.append(f"{_plural(len(replaced), 'hand verdict')} replaced by the rule: {changes}")
    if dropped := report["dropped_hand"]:
        lines.append(f"{_plural(len(dropped), 'hand row')} no longer a disagreement, dropped: "
                     f"{', '.join(dropped)}")  # fmt: skip
    return "\n".join(lines)


def _cmd_functions(args: argparse.Namespace) -> int:
    target = select_target(load_manifest(args.manifest), args.exe, args.manifest)
    out_dir = config_dir(target.name) if args.write else Path(args.output)
    refuse_output(out_dir, args.orig, DEFAULT_ORIG, args.watcom_dir, DEFAULT_INSTALL)
    le = LE(read_target(target, args.orig, args.manifest))
    matches = _runtime_matches(args.runtime, target)
    runtime_rows = _seeded_runtime_rows(matches, args.watcom_dir)
    found = discover(le, runtime_starts=[row.start for row in runtime_rows])
    boundaries_out = out_dir / "boundaries.csv"
    kept = _existing(boundaries_out, config_dir(target.name) / "boundaries.csv")
    result = reconcile(le, read_ghidra_export(args.ghidra_export), found, runtime_rows,
                       existing=read_boundaries_csv(kept) if kept else (),
                       modules=matches)  # fmt: skip
    units = _existing(out_dir / "units.csv", config_dir(target.name) / "units.csv")
    rows = assign_units(result.functions, read_units_csv(units)) if units else result.functions
    write_functions_csv(out_dir / "functions.csv", rows, target.name)
    write_boundaries_csv(boundaries_out, result.boundaries, target.name)
    report = _functions_report(target.name, result)
    print(json.dumps(report, indent=2) if args.json else _format_functions_report(report))
    print(f"wrote {out_dir / 'functions.csv'} and {boundaries_out}", file=sys.stderr)
    return 0  # open verdicts are reported; the boundaries check (D-08) fails on them


def _add_functions_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "functions",
        help="reconcile the Ghidra export with the capstone pass (D-07) into functions.csv and "
        "boundaries.csv, keeping hand-written verdicts (D-08)",
    )
    p.add_argument("exe", metavar="EXE", help="manifest name or its stem (case-insensitive)")
    p.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help=default)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=default)
    p.add_argument("--watcom-dir", type=Path, default=DEFAULT_INSTALL, help=default)
    p.add_argument(
        "--runtime", type=Path, metavar="CSV", help="default: config/<exe>/runtime.csv"
    )
    p.add_argument(
        "--ghidra-export",
        type=Path,
        required=True,
        metavar="PATH",
        help="the functions.raw.csv written by `reverseapoc ghidra-export`",
    )
    where = p.add_mutually_exclusive_group(required=True)
    where.add_argument(
        "--write",
        action="store_true",
        help="write config/<exe>/functions.csv and boundaries.csv",
    )
    where.add_argument("--output", type=Path, metavar="DIR", help="write both CSVs into DIR")
    p.add_argument("--json", action="store_true", help="print the counts as JSON")
    p.set_defaults(func=_cmd_functions)


# ---- units: the D-11 draft and the D-12 scaffold (SPL-03, SPL-04) ----


def _draft(args: argparse.Namespace, target: Target, out_dir: Path) -> tuple[list, list]:
    """Draft units.csv from functions.csv and write both into `out_dir`; returns the units and
    the functions with their unit column filled."""
    units_out = out_dir / "units.csv"
    if args.write and units_out.is_file() and not args.redraft:
        raise UnitsError(
            f"{units_out} exists and may hold hand re-cuts; pass --redraft to replace it"
        )
    rows = read_functions_csv(args.functions or config_dir(target.name) / "functions.csv")
    le = LE(read_target(target, args.orig, args.manifest))
    matches = _runtime_matches(args.runtime, target)
    flat = le.load_flat(relocate=False)
    chk = [(m.start, m.end) for m in matches if CHK_PUBLIC in m.publics]
    units = draft_units(le, rows, runtime=matches, chk_callers=chk_callers(rows, flat, chk),
                        flat=flat, fixups=le.fixups())  # fmt: skip
    assigned = assign_units(rows, units)
    write_units_csv(units_out, units, target.name)
    write_functions_csv(out_dir / "functions.csv", assigned, target.name)
    reasons = ", ".join(f"{n} {reason}" for reason, n in
                        sorted(Counter(u.reason for u in units).items()))  # fmt: skip
    print(f"{target.name}: {len(units)} units ({reasons}); wrote {units_out}")
    return units, assigned


def _cmd_units(args: argparse.Namespace) -> int:
    target = select_target(load_manifest(args.manifest), args.exe, args.manifest)
    if (args.write or args.output is not None) and args.units is not None:
        raise UnitsError("--units names the units.csv --write-src reads on its own; a draft "
                         "(--write or --output) writes units.csv, so drop --units")  # fmt: skip
    if args.write or args.output is not None:
        out_dir = config_dir(target.name) if args.write else Path(args.output)
        refuse_output(out_dir, args.orig, DEFAULT_ORIG, DEFAULT_INSTALL)
        units, functions = _draft(args, target, out_dir)
    elif args.write_src is not None:  # orchestrator ruling F2: scaffold from the committed CSVs
        units = read_units_csv(args.units or config_dir(target.name) / "units.csv")
        functions = read_functions_csv(args.functions or config_dir(target.name) / "functions.csv")
    else:
        raise UnitsError("give --write, --output DIR or --write-src UNIT")
    if args.write_src is not None:
        unit = next((u for u in units if u.unit == args.write_src), None)
        if unit is None:
            raise UnitsError(f"no unit named {args.write_src!r} in units.csv")
        path = Path(args.src_root) / config_dir(target.name).name / f"{unit.unit}.c"
        refuse_output(path, args.orig, DEFAULT_ORIG, DEFAULT_INSTALL)
        write_unit_source(path, scaffold_unit(target.name, unit, functions))
        print(f"wrote {path}")
    return 0


def _add_units_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "units",
        help="draft config/<exe>/units.csv from functions.csv (D-11) and fill its unit column; "
        "with --write-src UNIT scaffold src/<exe>/<unit>.c with INCLUDE_ASM markers (D-12)",
    )
    p.add_argument("exe", metavar="EXE", help="manifest name or its stem (case-insensitive)")
    p.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help=default)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=default)
    p.add_argument(
        "--functions", type=Path, metavar="CSV", help="default: config/<exe>/functions.csv"
    )
    p.add_argument(
        "--runtime", type=Path, metavar="CSV", help="default: config/<exe>/runtime.csv"
    )
    p.add_argument(
        "--units",
        type=Path,
        metavar="CSV",
        help="the units.csv --write-src reads on its own; default: config/<exe>/units.csv",
    )
    where = p.add_mutually_exclusive_group()  # optional with --write-src (ruling F2)
    where.add_argument(
        "--write",
        action="store_true",
        help="write config/<exe>/units.csv and the unit column of config/<exe>/functions.csv",
    )
    where.add_argument(
        "--output", type=Path, metavar="DIR", help="write units.csv and functions.csv into DIR"
    )
    p.add_argument(
        "--redraft",
        action="store_true",
        help="let --write replace an existing units.csv (its hand re-cuts are lost)",
    )
    p.add_argument(
        "--write-src",
        metavar="UNIT",
        help="create src/<exe>/<UNIT>.c with one INCLUDE_ASM marker per game and thunk "
        "function; an existing file is never overwritten",
    )
    p.add_argument("--src-root", type=Path, default=DEFAULT_SRC, help=default)
    p.set_defaults(func=_cmd_units)


# ---- headless Ghidra: ghidra-export (container only, D-05) ----


def _cmd_ghidra_export(args: argparse.Namespace) -> int:
    target = select_target(load_manifest(args.manifest), args.exe, args.manifest)
    if args.drafts:
        result = export_drafts(
            target.name, args.orig, args.drafts, args.asm, manifest=args.manifest
        )
        ok = not result.missing
    else:
        result = export_functions(target.name, args.orig, args.out, manifest=args.manifest)
        ok = True
    print(json.dumps(result.to_json(), indent=2) if args.json else result.format())
    return 0 if ok else 1


def _add_ghidra_export_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "ghidra-export",
        help="run headless Ghidra on an EXE and write <out>/<exe>/functions.raw.csv, or with "
        "--drafts the decompile drafts asm/<exe>/ghidra/func_XXXXXXXX.c (in the container)",
    )
    p.add_argument("exe", metavar="EXE", help="manifest name or its stem (case-insensitive)")
    p.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help=default)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=default)
    p.add_argument("--out", type=Path, default=DEFAULT_EXPORT_DIR, help=default)
    p.add_argument(
        "--drafts",
        nargs="+",
        type=_hex_address,
        metavar="ADDR",
        help="write decompile drafts for these hex addresses instead of the function list",
    )
    p.add_argument("--asm", type=Path, default=DEFAULT_ASM_DIR, help="drafts root; " + default)
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    p.set_defaults(func=_cmd_ghidra_export)


# ---- the C89 lint gate: lint (container, SPL-12) ----


def _cmd_lint(args: argparse.Namespace) -> int:
    # Before plan 05-13 writes the first unit there is no src/: that is 0 files, not an error.
    paths = args.paths or ([DEFAULT_SRC] if DEFAULT_SRC.is_dir() else [])
    result = run_lint(paths)
    print(json.dumps(result.to_json(), indent=2) if args.json else result.format())
    if not result.ok:
        return 1
    if args.stamp is not None:  # ninja's lint edge depends on this file
        args.stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp = f"lint ok: {len(result.files)} files\n"
        write_atomic(args.stamp, stamp.encode("ascii"))
    return 0


def _add_lint_command(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "lint",
        help="check C sources with clang -fsyntax-only -std=gnu89 and the Watcom compat header "
        "(D-14; in the container)",
    )
    p.add_argument(
        "paths", nargs="*", type=Path, metavar="PATHS", help="files or directories; default: src"
    )
    p.add_argument("--stamp", type=Path, metavar="FILE", help="write FILE when the lint passes")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    p.set_defaults(func=_cmd_lint)


# ---- the single-unit check (SPL-11, D-16) ----

# DEFAULT_SRC and DEFAULT_CONFIG come from check.py, the one definition object_root also uses.
DEFAULT_BUILD = REPO_ROOT / "build"


def _split_unit(text: str) -> tuple[str, str]:
    exe, sep, unit = text.partition("/")
    if not (sep and exe and unit) or "/" in unit:
        raise CheckError(f"expected EXE/UNIT (e.g. ufo2p/u_000a1b2c), got {text!r}")
    return exe, unit


def _run_sweep(args: argparse.Namespace, exe: str, unit: str) -> int:
    report = sweep(
        exe, unit, args.sweep, orig_dir=args.orig, manifest=args.manifest,
        config_root=args.config, src_root=args.src, build_dir=args.build,
        watcom_dir=args.watcom_dir, watcom_manifest=args.watcom_manifest, log=args.log,
    )  # fmt: skip
    print(json.dumps(report.to_json(), indent=2) if args.json else "\n".join(report.lines))
    print(f"wrote {report.log_path}", file=sys.stderr)
    return 0  # the sweep is evidence for a cflags rule (D-18), never a match


def _run_check(args: argparse.Namespace) -> int:
    exe, unit = _split_unit(args.target)
    if args.sweep is not None:
        return _run_sweep(args, exe, unit)
    result = check_unit(
        exe, unit, orig_dir=args.orig, manifest=args.manifest, config_root=args.config,
        src_root=args.src, build_dir=args.build, watcom_dir=args.watcom_dir, cflags=args.cflags,
        watcom_manifest=args.watcom_manifest, log=args.log,
    )  # fmt: skip
    if result.compile_output.strip():
        print(result.compile_output.rstrip("\n"), file=sys.stderr)
    print(json.dumps(result.to_json(), indent=2) if args.json else result.format())
    return result.exit_code


def _cmd_check(args: argparse.Namespace) -> int:
    """Exit 0 matched, 1 mismatch, 2 for any tool or usage error (never a pass)."""
    try:
        return _run_check(args)
    except (*_ERRORS, CheckError) as exc:
        print(f"reverseapoc check: error: {exc}", file=sys.stderr)
        return EXIT_TOOL


def _add_unit_roots(p: argparse.ArgumentParser) -> None:
    default = "default: %(default)s"
    p.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help=default)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=default)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help=default)
    p.add_argument("--src", type=Path, default=DEFAULT_SRC, help=default)
    p.add_argument("--build", type=Path, default=DEFAULT_BUILD, help=default)


def _add_check_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "check",
        help="compile one unit, objdiff and relocation-check every function it defines, land "
        "every compiled unit and compare each EXE's SHA-1 (SPL-11; objdiff-cli: in the container)",
    )
    p.add_argument("target", metavar="EXE/UNIT", help="e.g. ufo2p/u_000a1b2c")
    _add_unit_roots(p)
    p.add_argument("--watcom-dir", type=Path, default=DEFAULT_INSTALL, help=default)
    p.add_argument("--watcom-manifest", type=Path, default=DEFAULT_WATCOM_MANIFEST, help=default)
    p.add_argument("--cflags", type=Path, default=DEFAULT_CFLAGS, help=default)
    p.add_argument("--log", type=Path, default=DEFAULT_LOG, help=default)
    p.add_argument(
        "--sweep",
        metavar="FUNC",
        help="run the fixed D-17 flag matrix for FUNC and log every cell to "
        "build/logs/sweep-<exe>-<unit>-<func>.log; never lands, never edits config/cflags.txt",
    )
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    p.set_defaults(func=_cmd_check)


def _cmd_target(args: argparse.Namespace) -> int:
    # The target object is cut from the game: never written inside orig/ or the Watcom tree.
    refuse_output(args.output, args.orig, DEFAULT_ORIG, DEFAULT_INSTALL)
    result, rows = write_target(args.exe, args.unit, args.output, orig_dir=args.orig,
                                manifest=args.manifest, config_root=args.config)  # fmt: skip
    print(format_target(args.output, result, rows))
    return 0


def _add_target_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "target",
        help="cut one unit's target ELF object from the LE image (the ninja `target` edge)",
    )
    p.add_argument("exe", metavar="EXE", help="manifest name or its stem (case-insensitive)")
    p.add_argument("unit", metavar="UNIT", help="a unit of config/<exe>/units.csv")
    p.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help=default)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=default)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help=default)
    p.add_argument("-o", "--output", type=Path, required=True, help="the ELF object to write")
    p.set_defaults(func=_cmd_target)


def _cmd_land(args: argparse.Namespace) -> int:
    out = args.out if args.out is not None else args.build / "land"
    refuse_output(out, args.orig, DEFAULT_ORIG, DEFAULT_INSTALL)
    lands = land_all(args.manifest, orig_dir=args.orig, config_root=args.config,
                     src_root=args.src, build_dir=args.build)  # fmt: skip
    for landed in lands:
        write_landed(landed.result, out / landed.exe, orig_dir=args.orig,
                     source=args.orig / landed.exe)  # fmt: skip
    if args.json:
        print(json.dumps([landed.to_json() for landed in lands], indent=2))
    else:
        lines = [line for landed in lands for line in landed.format()]
        print("\n".join(lines) or "no EXE has config/<exe>/units.csv: nothing to land")
    return 0 if all(landed.ok for landed in lands) else 1


def _add_land_command(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "land",
        help="land every function of every built unit object into its EXE, write the result to "
        "build/land/ and compare each SHA-1 with config/targets.toml (SPL-10, `ninja verify`)",
    )
    _add_unit_roots(p)
    p.add_argument("--out", type=Path, help="where the landed EXEs go; default: <build>/land")
    p.add_argument("--json", action="store_true", help="print the results as JSON")
    p.set_defaults(func=_cmd_land)


# ---- the status table writer and zero-regression gate (D-21, D-24) ----


def _gate_roots(args: argparse.Namespace) -> GateRoots:
    return GateRoots(orig_dir=args.orig, manifest=args.manifest, config_root=args.config,
                     src_root=args.src, build_dir=args.build, watcom_dir=args.watcom_dir,
                     cflags=args.cflags, watcom_manifest=args.watcom_manifest,
                     log=args.log)  # fmt: skip


def _gate(args: argparse.Namespace) -> GateResult:
    """The gate mode the arguments name; a CheckError for a combination that makes no sense."""
    if args.all:
        if args.targets:
            raise CheckError("--all re-checks every matched unit; it takes no EXE/UNIT")
        if args.attempts is not None:
            raise CheckError("--attempts has no meaning with --all, which writes nothing")
        if args.partial:
            raise CheckError("--partial scores one saved attempt; it does not combine with --all")
        return gate_all(roots=_gate_roots(args))
    if not args.targets:
        raise CheckError("expected EXE/UNIT [EXE/UNIT ...] or --all")
    targets = [_split_unit(text) for text in args.targets]
    if args.partial:
        return _gate_partial(args, targets)
    return gate_units(targets, roots=_gate_roots(args), attempts=args.attempts or 0)


def _gate_partial(args: argparse.Namespace, targets: list[tuple[str, str]]) -> GateResult:
    """`--partial --src FILE` (ruling F7): FILE is the saved attempt, never a src root."""
    if len(targets) != 1:
        raise CheckError("--partial scores one saved attempt: give exactly one EXE/UNIT")
    src = Path(args.src)
    if src.resolve() == Path(DEFAULT_SRC).resolve() or src.suffix != ".c" or not src.is_file():
        raise CheckError("--partial needs --src FILE naming the saved attempt's existing .c "
                         f"file, got {src}")  # fmt: skip
    (exe, unit), roots = targets[0], _gate_roots(args)
    roots = dataclasses.replace(roots, src_root=src.parent)
    return gate_partial(exe, unit, src, roots=roots, attempts=args.attempts or 0)


def _run_gate(args: argparse.Namespace) -> int:
    result = _gate(args)
    print(json.dumps(result.to_json(), indent=2) if args.json else result.format())
    return result.exit_code


def _cmd_gate(args: argparse.Namespace) -> int:
    """Exit 0 gated (rows written; --all writes none), 1 on a mismatch, with nothing written, 2
    for any tool or usage error, never a pass. A 2 writes nothing, except when a write fails
    after another EXE's table was already written: the message names that table, so config/ is
    restored before anything is committed."""
    try:
        return _run_gate(args)
    except (*_ERRORS, CheckError, StatusError) as exc:
        print(f"reverseapoc gate: error: {exc}", file=sys.stderr)
        return EXIT_TOOL


def _add_gate_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "gate",
        help="run check for each EXE/UNIT and, only when every check exits 0 and the landed set "
        "equals status.csv's matched set plus the units' functions, write matched rows to "
        "config/<exe>/status.csv (D-21, D-24; the only writer of status.csv; in the container)",
    )
    # One or more targets, or --all (argparse cannot put a nargs="+" positional in a mutually
    # exclusive group; _gate enforces "one or the other").
    p.add_argument("targets", nargs="*", metavar="EXE/UNIT",
                   help="e.g. ufo2p/u_000a1b2c; several are checked, cross-checked and written "
                   "together, all or nothing")  # fmt: skip
    p.add_argument("--all", action="store_true",
                   help="re-check every unit with matched rows (check_source each, one land) and "
                   "the cross-check; writes nothing")  # fmt: skip
    p.add_argument("--partial", action="store_true",
                   help="with one EXE/UNIT and --src FILE (the saved attempt's .c file, not a src "
                   "root): score FILE under build/check-custom and write partial rows with the "
                   "best percent; never touches a matched row")  # fmt: skip
    _add_unit_roots(p)
    p.add_argument("--watcom-dir", type=Path, default=DEFAULT_INSTALL, help=default)
    p.add_argument("--watcom-manifest", type=Path, default=DEFAULT_WATCOM_MANIFEST, help=default)
    p.add_argument("--cflags", type=Path, default=DEFAULT_CFLAGS, help=default)
    p.add_argument("--log", type=Path, default=DEFAULT_LOG, help=default)
    p.add_argument("--attempts", type=int, default=None, metavar="N",
                   help="matching attempts the rows record; 0 (the default) = matched by hand")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    p.set_defaults(func=_cmd_gate)


# ---- Watcom media: fetch-watcom, install-watcom, check-watcom ----


def _cmd_fetch_watcom(args: argparse.Namespace) -> int:
    print(MEDIA_NOTICE, file=sys.stderr)
    report = fetch_watcom(
        args.versions, manifest=args.manifest, media_dir=args.media, base=args.base_url
    )
    print(report.format())
    return 0 if report.ok else 1


def _cmd_install_watcom(args: argparse.Namespace) -> int:
    chosen = select(load_watcom_manifest(args.manifest), args.versions)
    ok = True
    for media in chosen:
        try:
            result = install_version(media, args.media, args.dest, force=args.force)
        except WatcomError as exc:
            print(f"reverseapoc install-watcom: {media.version}: {exc}", file=sys.stderr)
            ok = False
            continue
        print(result.format())
        ok = ok and result.ok
    return 0 if ok else 1


def _cmd_check_watcom(args: argparse.Namespace) -> int:
    report = check_watcom(args.versions, manifest=args.manifest, install_dir=args.dest)
    print(report.format())
    return 0 if report.ok else 1


# ---- the attempt wrapper: the only Bash a matching session runs (D-44) ----


def _cmd_attempt(args: argparse.Namespace) -> int:
    """`attempt check`: exit 0 only when the claimed function matches and check passes its
    unit, 1 for a mismatch or a claimed function that was not compiled, 2 for a refusal or any
    tool error (never a pass). `attempt check --sweep` exits 0 when it ran (never a match) and
    2 when it did not. The arguments after `attempt` must be one of hooks.ATTEMPT_FORMS
    exactly (ruling F27)."""
    raw = args.raw_argv
    rest = raw[raw.index("attempt") + 1 :]
    try:
        if not attempt.form_allowed(rest):
            raise AttemptError(f"accepts only: {attempt.forms_text()}")
        if args.attempt_command == "check":
            return attempt.cmd_check(sweep=args.sweep)
        if args.attempt_command == "asm":
            return attempt.cmd_asm(args.name)
        return attempt.cmd_context()
    except _ERRORS as exc:
        print(f"reverseapoc attempt: error: {_one_line(exc)}", file=sys.stderr)
        return EXIT_TOOL
    except Exception as exc:  # M9: any other failure is a tool error (2), never a mismatch (1)
        print(f"reverseapoc attempt: error: {type(exc).__name__}: {_one_line(exc)}",
              file=sys.stderr)  # fmt: skip
        return EXIT_TOOL


def _one_line(exc: BaseException) -> str:
    """The exception's text on one line (fix round 2 N1): every CR/LF run becomes a space."""
    return re.sub(r"[\r\n]+", " ", str(exc))


def _cmd_context(args: argparse.Namespace) -> int:
    roots = attempt.ROOTS
    data = attempt.exe_inputs(args.exe, orig=args.orig, manifest=args.manifest, config=args.config)
    row = attempt.resolve_row(data, args.function)
    out = args.out
    if out is None:
        driver = Path(roots.repo).joinpath(*attempt.DRIVER_PARTS)
        out = driver / attempt.MANUAL_RUN / data.stem / attempt.placeholder(row)
    pack = attempt.make_pack(data, row, src=args.src, config=args.config, asm_root=args.asm,
                             roots=roots)  # fmt: skip
    path = write_pack(pack, out, root=roots.repo)
    if args.json:
        print(json.dumps({"path": str(path), **pack.to_json()}, indent=2))
    else:
        cut = ", ".join(pack.truncated) or "nothing"
        print(f"wrote {path} ({pack.pack_bytes} bytes; cut: {cut})")
    return 0


def _add_context_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "context",
        help="write the D-13 context pack of one function to build/driver/ (gitignored; "
        "default build/driver/manual/<exe>/<func>/context.md)",
    )
    # check's loader (fix round 1 M12): every CSV comes from --config, as for check.
    p.add_argument("exe", metavar="EXE", help="manifest name or its stem (case-insensitive)")
    p.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help=default)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=default)
    p.add_argument("function", metavar="FUNC", help="func_XXXXXXXX or the row's symbols.csv name")
    p.add_argument("--src", type=Path, default=DEFAULT_SRC, help=default)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help=default)
    p.add_argument("--asm", type=Path, default=DEFAULT_ASM, help="listing root; " + default)
    p.add_argument("--out", type=Path, help="the pack's directory, under build/driver/")
    p.add_argument("--json", action="store_true", help="print the path, size and cuts as JSON")
    p.set_defaults(func=_cmd_context)


def _add_attempt_command(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "attempt",
        allow_abbrev=False,
        help="the matching session's wrapper: check, asm or context for the function the "
        "driver claimed (REVERSEAPOC_CLAIM, REVERSEAPOC_FUNC, REVERSEAPOC_ATTEMPT_DIR; D-44)",
        description="Takes its target only from the driver's environment. attempt check: exit "
        "0 only when the claimed function matches (objdiff 100, relocations and bytes ok) and "
        "check passes its unit; 1 for a mismatch or a claimed function that was not compiled "
        "(still INCLUDE_ASM); 2 refused or tool error. attempt check --sweep: 0 when it ran, "
        "2 when it did not; a sweep is a diagnostic, never a match.",
    )
    asub = p.add_subparsers(dest="attempt_command", required=True, metavar="{check,asm,context}")
    c = asub.add_parser(
        "check",
        allow_abbrev=False,
        help=f"run `reverseapoc check <claim> --json` in the container (at most "
        f"{attempt.CHECK_BUDGET} runs per attempt) and log it under the attempt directory",
    )
    c.add_argument(
        "--sweep",
        action="store_true",
        help="run the D-17 flag matrix for the claimed function instead (a diagnostic; a hit "
        "is logged for the owner, cflags.txt is owner-only)",
    )
    a = asub.add_parser(
        "asm",
        allow_abbrev=False,
        help="print the listing of the claimed function, or of NAME (another row of its EXE)",
    )
    a.add_argument("name", nargs="?", metavar="NAME", help="a func_XXXXXXXX or symbols.csv name")
    asub.add_parser(
        "context",
        allow_abbrev=False,
        help="rebuild the claimed function's context pack into the attempt directory and print it",
    )
    p.set_defaults(func=_cmd_attempt)


# ---- the night driver: drive (06-25; D-10, D-24, D-34, D-36, D-48) ----


def _positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a whole number") from exc
    if number < 1:
        raise argparse.ArgumentTypeError(f"{value} is below 1")
    return number


def _non_negative(value: str) -> int:
    """A whole number of 0 or more (drive --target-matched: 0 is off, 07-21)."""
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a whole number") from exc
    if number < 0:
        raise argparse.ArgumentTypeError(f"{value} is below 0")
    return number


def _run_id(value: str | None) -> str:
    """The run's id: `--run ID`, else the UTC time it starts (YYYYMMDD-HHMMSS)."""
    if value is None:
        return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        raise argparse.ArgumentTypeError(f"run id {value!r} is not [A-Za-z0-9_.-]+")
    return value


def _cmd_drive(args: argparse.Namespace) -> int:
    """Exit 0 for a night that ENDED with every end-of-run check passing, a dry run or a
    passing canary; 1 for a STOPPED night, a failed end-of-run check or a failing canary; 2
    when it refused to start (preflight, dirty outputs, or a canary refused before its
    session; once the canary's session ran, any error is a canary FAIL, exit 1)."""
    options = driver.DriveOptions(repo=REPO_ROOT, run_id=args.run or _run_id(None),
                                  max_sessions=args.max_sessions,
                                  target_matched=args.target_matched, workers=args.workers,
                                  dry_run=args.dry_run,
                                  canary=args.canary, json=args.json)  # fmt: skip
    return driver.run_drive(options, driver.default_seams(REPO_ROOT))


def _add_drive_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "drive",
        help="run the night driver in the main checkout: one fresh claude session per attempt, "
        "the container gate decides every match (D-24, D-34, D-48)",
        description="Refuses to start (exit 2) outside the main checkout, on a dirty tree, on a "
        f"Claude CLI that is not major {driver.TESTED_MAJOR} and at least "
        f"{'.'.join(map(str, driver.MIN_CLI_VERSION))}, when Docker does not answer or the "
        "container's uv sync fails.",
    )
    p.add_argument("--workers", type=_positive, default=3, metavar="N",
                   help="sessions at once, one unit each (D-06, D-07); " + default)  # fmt: skip
    p.add_argument("--max-sessions", type=_positive, default=60, metavar="N",
                   help="counted sessions of all workers before the night ends; "
                   + default)  # fmt: skip
    p.add_argument("--target-matched", type=_non_negative, default=0, metavar="N",
                   help="matches before the night ends, 0 = off; " + default)  # fmt: skip
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="print the 10 pilot picks and build their packs; no claude, no gate")
    mode.add_argument("--canary", action="store_true",
                      help="owner only: one real session that proves the guardrails deny "
                      "(PASS/FAIL)")  # fmt: skip
    p.add_argument("--run", type=_run_id, default=None, metavar="ID",
                   help="the run id under build/driver/; default: the UTC start time")
    p.add_argument("--json", action="store_true", help="print exactly one JSON document")
    p.set_defaults(func=_cmd_drive)


def _add_watcom_commands(sub: argparse._SubParsersAction) -> None:
    def common(p: argparse.ArgumentParser, *, media: bool, dest: bool) -> None:
        default = "default: %(default)s"
        p.add_argument("versions", nargs="*", metavar="VERSION", help="default: all")
        p.add_argument("--manifest", type=Path, default=DEFAULT_WATCOM_MANIFEST, help=default)
        if media:
            p.add_argument("--media", type=Path, default=DEFAULT_MEDIA, help=default)
        if dest:
            p.add_argument("--dest", type=Path, default=DEFAULT_INSTALL, help=default)

    p = sub.add_parser(
        "fetch-watcom",
        help="download the original Watcom CD images from the Internet Archive into "
        "third_party/watcom-media/ and verify them",
    )
    common(p, media=True, dest=False)
    p.add_argument("--base-url", default=ARCHIVE_BASE, help="default: %(default)s")
    p.set_defaults(func=_cmd_fetch_watcom)

    p = sub.add_parser(
        "install-watcom",
        help="extract verified Watcom CD images into third_party/watcom/<version>/ and check "
        "their key files",
    )
    common(p, media=True, dest=True)
    p.add_argument("--force", action="store_true", help="replace an existing installation")
    p.set_defaults(func=_cmd_install_watcom)

    p = sub.add_parser(
        "check-watcom", help="verify the key files of installed Watcom versions"
    )
    common(p, media=False, dest=True)
    p.set_defaults(func=_cmd_check_watcom)


# ---- mechanics: the DEC-01 item-to-function map (D-01, D-02, D-04, D-22, D-23, D-31) ----


def _mechanics_write(args: argparse.Namespace) -> int:
    rows = mechanics.generate(args.config, args.orig, args.manifest)
    out = Path(args.config) / mechanics.MEMBERS_CSV
    mechanics.write_members(out, rows)
    counts = Counter(row.role for row in rows)
    report = {"rows": len(rows), "roles": {role: counts[role] for role in mechanics.ROLES}}
    print(json.dumps(report, indent=2) if args.json else
          f"{len(rows)} rows: " + ", ".join(f"{n} {r}" for r, n in report["roles"].items()))
    print(f"wrote {out}", file=sys.stderr)
    return 0


def _mechanics_check(args: argparse.Namespace) -> int:
    problems = mechanics.check_committed(args.config)
    if args.json:
        print(json.dumps({"problems": problems}, indent=2))
    else:
        print("\n".join(problems) if problems else "mechanics: no problems")
    return 1 if problems else 0


def _mechanics_digest(args: argparse.Namespace) -> int:
    mech, rows = mechanics.read_committed(args.config)
    digest = mechanics.tier_digest(mech, rows, args.tier)
    print(json.dumps({"tier": args.tier, "members_sha256": digest}) if args.json else digest)
    return 0


def _format_hub_candidates(report: dict) -> str:
    lines = [f"tier {report['tier']} hub-rule candidates (K = min_direct_callers; the other "
             "[hub_rule] criteria as written)"]  # fmt: skip
    for exe, entries in report["exes"].items():
        lines.append(f"{exe}:  K  must-match  direct-only  hubs  asm-removed  members by via")
        for e in entries:
            vias = ", ".join(f"{via} {n}" for via, n in e["members_by_via"].items())
            lines.append(f"  {e['k']:>4}  {e['must_match']:>10}  {e['must_match_direct']:>11}  "
                         f"{len(e['hubs']):>4}  {e['asm_removed']:>11}  {vias}")  # fmt: skip
        for e in entries:
            hubs = ", ".join(f"{h['address']} ({h['callers']})" for h in e["hubs"]) or "none"
            lines.append(f"  hubs at K={e['k']}: {hubs}")
    return "\n".join(lines)


def _mechanics_hubs(args: argparse.Namespace) -> int:
    mech = mechanics.load(Path(args.config) / mechanics.MECHANICS_TOML)
    exes = mechanics.needed_exes(mech)
    asm = mechanics.signed_asm(args.config, mech)
    graphs = mechanics.load_graphs(args.config, args.orig, args.manifest, exes) if exes else {}
    rows = mechanics.read_rows(args.config, exes)
    report = mechanics.hub_candidates(mech, graphs, rows, asm, args.tier, args.k)
    print(json.dumps(report, indent=2) if args.json else _format_hub_candidates(report))
    return 0


def _mechanics_status(args: argparse.Namespace) -> int:
    mech, rows = mechanics.read_committed(args.config)
    statuses = mechanics.read_statuses(args.config, sorted({r.exe for r in rows}))
    tiers = [args.tier] if args.tier is not None else [t.id for t in mech.tiers]
    found = {tier: mechanics.tier_status(mech, rows, statuses, tier) for tier in tiers}
    if args.json:
        report = {str(tier): {**dataclasses.asdict(st), "unmatched_starts": [
            [exe, f"0x{start:08X}"] for exe, start in st.unmatched_starts]}
            for tier, st in found.items()}  # fmt: skip
        print(json.dumps({"tiers": report}, indent=2))
    else:
        for tier, st in found.items():
            print(f"tier {tier}: {st.total} members, {st.matched} matched, {st.partial} partial, "
                  f"{st.unmatched} unmatched")  # fmt: skip
    if not args.require_matched:
        return 0
    problems = mechanics.done_problems(mech, rows, found)
    for problem in problems:
        print(f"reverseapoc mechanics status: {problem}", file=sys.stderr)
    return 1 if problems else 0


def _format_graph_report(exe: str, report: dict) -> str:
    edges = ", ".join(f"{kind} {n}" for kind, n in report["edges"].items())
    midrow = report["midrow"]
    at_boundary = sum(1 for ref in midrow if ref["boundary"])
    from_data = sum(1 for ref in midrow if ref["origin"] == "data")
    indirect = report["indirect"]
    scc = report["largest_scc"]
    return "\n".join([
        f"{exe} edges: {edges}",
        f"midrow references: {len(midrow)} ({at_boundary} at an instruction start, "
        f"{from_data} from data)",
        f"indirect calls: {sum(e['count'] for e in indirect)} in {len(indirect)} rows",
        f"orphan tables: {len(report['orphan_tables'])}",
        f"largest SCC: direct {scc['direct']}, direct+pointer+table "
        f"{scc['direct_pointer_table']}, all kinds {scc['all']}",
    ])  # fmt: skip


def _mechanics_graph(args: argparse.Namespace) -> int:
    if args.exe not in mechanics.EXES:
        raise MechanicsError(f"--exe {args.exe!r} is not one of {', '.join(mechanics.EXES)}")
    graph = mechanics.load_graphs(args.config, args.orig, args.manifest, [args.exe])[args.exe]
    report = mechanics.graph_report(graph)
    print(json.dumps(report, indent=2) if args.json else _format_graph_report(args.exe, report))
    return 0


def _cmd_mechanics(args: argparse.Namespace) -> int:
    """Exit 0 clean, 1 problems found (check, status --require-matched), 2 any tool error."""
    try:
        return args.mechanics_func(args)
    except (*_ERRORS, MechanicsError, LocateError, AsmClassError) as exc:
        print(f"reverseapoc mechanics {args.mechanics_command}: error: {exc}", file=sys.stderr)
        return EXIT_TOOL


def _mechanics_roots(p: argparse.ArgumentParser, *, game: bool) -> None:
    default = "default: %(default)s"
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help=default)
    if game:
        p.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help=default)
        p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=default)
    p.add_argument("--json", action="store_true", help="print the result as JSON")


def _add_mechanics_command(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "mechanics",
        help="the DEC-01 map of OpenApoc checklist items to functions: config/mechanics.toml "
        "(hand-edited) and the generated config/mechanics-members.csv",
    )
    verbs = p.add_subparsers(dest="mechanics_command", required=True, metavar="VERB")
    w = verbs.add_parser(
        "write",
        help="regenerate config/mechanics-members.csv from mechanics.toml, functions.csv and the "
        "call graphs of orig/ (D-02)",
    )
    _mechanics_roots(w, game=True)
    w.set_defaults(mechanics_func=_mechanics_write)
    c = verbs.add_parser(
        "check",
        help="validate the committed mechanics files without game files: members rows, entries, "
        "signed tier digests, the asm list sign-off (exit 1 on any problem)",
    )
    _mechanics_roots(c, game=False)
    c.set_defaults(mechanics_func=_mechanics_check)
    d = verbs.add_parser(
        "digest", help="print a tier's members_sha256 from the committed rows, for its sign-off"
    )
    d.add_argument("--tier", type=_positive, required=True, metavar="N")
    _mechanics_roots(d, game=False)
    d.set_defaults(mechanics_func=_mechanics_digest)
    h = verbs.add_parser(
        "hubs",
        help="print candidate hub-rule numbers for a tier (D-22): must-match counts per K with "
        "all and direct-only edges, the hubs, members per via kind, asm rows removed",
    )
    h.add_argument("--tier", type=_positive, required=True, metavar="N")
    h.add_argument(
        "--k",
        type=_positive,
        nargs="+",
        default=list(mechanics.DEFAULT_HUB_KS),
        metavar="K",
        help="min_direct_callers values to try (several allowed); default: %(default)s",
    )
    _mechanics_roots(h, game=True)
    h.set_defaults(mechanics_func=_mechanics_hubs)
    s = verbs.add_parser(
        "status",
        help="matched/partial/unmatched counts of each tier's must-match members from status.csv "
        "(committed data only)",
    )
    s.add_argument("--tier", type=_positive, metavar="N", help="one tier; default: every tier")
    s.add_argument(
        "--require-matched",
        action="store_true",
        help="exit 1 unless every reported tier is signed off with a valid digest, has members "
        "and has every member matched (the D-05 done rule)",
    )
    _mechanics_roots(s, game=False)
    s.set_defaults(mechanics_func=_mechanics_status)
    g = verbs.add_parser(
        "graph",
        help="print an EXE's call-graph report: edge counts per kind, mid-row references, "
        "indirect calls, orphan tables, largest SCCs (addresses and counts only)",
    )
    g.add_argument("--exe", required=True, metavar="EXE", help="ufo2p or tacp")
    _mechanics_roots(g, game=True)
    g.set_defaults(mechanics_func=_mechanics_graph)
    _add_locate_verb(verbs)
    _add_asm_verb(verbs)
    p.set_defaults(func=_cmd_mechanics)


def _mechanics_asm(args: argparse.Namespace) -> int:
    proposed = []
    for exe in mechanics.EXES:
        inputs = locate.load_inputs(args.config, args.orig, args.manifest, exe)
        proposed += asmclass.classify(inputs)
    path = Path(args.config) / mechanics.ASM_CSV
    existing = mechanics.read_asm_list(path) if path.is_file() else []
    rows, changed = asmclass.merge(existing, proposed)
    if args.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(path, mechanics.format_asm_csv(rows).encode("ascii"))
    counts = asmclass.verdict_counts(rows)
    if args.json:
        print(json.dumps({"rows": len(rows), "verdicts": counts, "changed": changed,
                          "written": bool(args.write)}, indent=2))  # fmt: skip
    else:
        print(f"{len(rows)} rows: " + ", ".join(f"{n} {v}" for v, n in counts.items()))
        print(f"{len(changed)} changed" + "".join(f"\n  {line}" for line in changed))
    if args.write:
        print(f"wrote {path}", file=sys.stderr)
    return 0


def _add_asm_verb(verbs: argparse._SubParsersAction) -> None:
    a = verbs.add_parser(
        "asm",
        help="propose the D-23 asm list from orig/: unaligned and library-unit game rows with "
        "evidence tags and a proposed verdict (asm or unclear); prints counts and the rows whose "
        "tool-owned columns changed (addresses only)",
    )
    a.add_argument(
        "--write",
        action="store_true",
        help="write config/asm-functions.csv, keeping every existing verdict and reason "
        "(a changed list needs the owner's [asm_list] re-sign, D-23)",
    )
    _mechanics_roots(a, game=True)
    a.set_defaults(mechanics_func=_mechanics_asm)


def _number(value: str) -> int:
    try:
        number = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number (0x1A or 26)") from exc
    if number < 0:
        raise argparse.ArgumentTypeError(f"{value} is below 0")
    return number


def _locate_report(args: argparse.Namespace, exe) -> dict:
    if args.string is not None:
        return locate.report_string(exe, args.string)
    if args.range is not None:
        return locate.report_range(exe, *args.range)
    if args.va is not None:
        return locate.report_va(exe, args.va)
    if args.get_text is not None:
        return locate.report_get_text(exe, *args.get_text)
    return locate.report_interrupt(exe, args.int)


def _mechanics_locate(args: argparse.Namespace) -> int:
    if args.exe not in mechanics.EXES:
        raise MechanicsError(f"--exe {args.exe!r} is not one of {', '.join(mechanics.EXES)}")
    exe = locate.load_inputs(args.config, args.orig, args.manifest, args.exe)
    report = {"exe": args.exe, **_locate_report(args, exe)}
    print(json.dumps(report, indent=2) if args.json else locate.format_report(args.exe, report))
    return 0


def _add_locate_verb(verbs: argparse._SubParsersAction) -> None:
    lo = verbs.add_parser(
        "locate",
        help="locate entry candidates in one EXE (D-01, D-03): rows referencing a string, an "
        "address or a range, get_text call sites, int386_ callers (addresses and counts only; "
        "needs orig/)",
    )
    lo.add_argument("--exe", required=True, metavar="EXE", help="ufo2p or tacp")
    pick = lo.add_mutually_exclusive_group(required=True)
    pick.add_argument(
        "--string", metavar="KEYWORD", help="data strings holding KEYWORD and the rows "
        "with an exact fixup to each (case-insensitive)"
    )  # fmt: skip
    pick.add_argument(
        "--va", type=_hex_address, metavar="0xADDR", help="rows with a fixup to exactly ADDR"
    )
    pick.add_argument(
        "--range", type=_hex_address, nargs=2, metavar=("0xA", "0xB"),
        help="rows with a fixup into [A, B)",
    )  # fmt: skip
    pick.add_argument(
        "--get-text", type=_number, nargs=2, metavar=("SECTION", "INDEX"),
        help="get_text call sites asking for (SECTION, INDEX), and their rows",
    )  # fmt: skip
    pick.add_argument(
        "--int", type=_number, metavar="0x1A",
        help="rows calling int386_ with this interrupt number in eax",
    )  # fmt: skip
    _mechanics_roots(lo, game=True)
    lo.set_defaults(mechanics_func=_mechanics_locate)


# ---- flags: the owner-approval queue of per-unit cflags rules (D-12) ----


def _flags_propose(args: argparse.Namespace) -> int:
    report = flags.propose(args.from_attempts, repo=args.repo)
    print(json.dumps(report.to_json(), indent=2) if args.json else report.format())
    return 0


def _flags_regate(args: argparse.Namespace) -> int:
    """Exit 0 when every proposal re-gated, 1 when one failed (recorded in the queue)."""
    report = flags.regate(args.ids, repo=args.repo, orig_dir=args.orig, build_dir=args.build,
                          watcom_dir=args.watcom_dir)  # fmt: skip
    print(json.dumps(report.to_json(), indent=2) if args.json else report.format())
    return report.exit_code


def _flags_list(args: argparse.Namespace) -> int:
    proposals = flags.read_queue(args.repo / flags.QUEUE)
    if args.json:
        print(json.dumps({"version": flags.QUEUE_VERSION,
                          "proposals": [p.to_json() for p in proposals]}, indent=2))  # fmt: skip
    else:
        print("\n".join(p.line() for p in proposals) or f"{flags.QUEUE} holds no proposal")
    return 0


def _cmd_flags(args: argparse.Namespace) -> int:
    """Exit 0 done, 2 for any tool or usage error. Nothing here writes config/cflags.txt or
    src/ (D-12): approval is the owner's step."""
    try:
        return args.flags_func(args)
    except _ERRORS as exc:
        print(f"reverseapoc flags: error: {exc}", file=sys.stderr)
        return EXIT_TOOL


def _add_flags_command(sub: argparse._SubParsersAction) -> None:
    default = "default: %(default)s"
    p = sub.add_parser(
        "flags",
        help="per-unit cflags proposals from sweep hits (D-12): propose, re-gate, list; "
        "config/cflags.txt changes only through the owner's approval",
    )
    verbs = p.add_subparsers(dest="flags_verb", required=True, metavar="VERB")
    pr = verbs.add_parser(
        "propose",
        help="turn the sweep hits of driver attempts into proposals in "
        f"{flags.QUEUE.as_posix()}, copying the C that hit to build/flags/<id>/ (host)",
    )
    pr.add_argument("--from-attempts", nargs="*", metavar="RUN", required=True,
                    help="driver runs under build/driver/ to read; none named: every run")
    pr.add_argument("--json", action="store_true", help="print the report as JSON")
    pr.set_defaults(flags_func=_flags_propose)
    ls = verbs.add_parser(
        "list",
        help="show the queue: functions, unit, rule, alternatives, siblings, evidence and "
        "re-gate status",
    )
    ls.add_argument("--json", action="store_true", help="print the queue as JSON")
    ls.set_defaults(flags_func=_flags_list)
    rg = verbs.add_parser(
        "regate",
        help="re-prove proposals over their whole unit and both EXEs on a copy of src/ under "
        "the committed cflags plus the proposed rule; writes only the queue and build/flags/ "
        "(objdiff-cli: in the container)",
    )
    rg.add_argument("ids", nargs="+", metavar="ID", help="e.g. F-0001")
    rg.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help=default)
    rg.add_argument("--build", type=Path, default=None,
                    help="check's build dir; default: build/flags/<id>/build")
    rg.add_argument("--watcom-dir", type=Path, default=DEFAULT_INSTALL, help=default)
    rg.add_argument("--json", action="store_true", help="print the report as JSON")
    rg.set_defaults(flags_func=_flags_regate)
    for verb in (pr, ls, rg):
        verb.add_argument("--repo", type=Path, default=REPO_ROOT,
                          help=f"the checkout whose config/ and build/ are read; {default}")
    p.set_defaults(func=_cmd_flags)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reverseapoc", description="ReverseApoc tooling for the X-COM Apocalypse executables."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def orig_and_manifest(p: argparse.ArgumentParser) -> None:
        p.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help="default: %(default)s")
        p.add_argument(
            "--manifest", type=Path, default=DEFAULT_MANIFEST, help="default: %(default)s"
        )

    p = sub.add_parser(
        "ingest",
        help="copy the executables from your game folder into orig/ and verify them",
        description="Reads APOC_STEAM_FOLDER (then APOC_GOG_FOLDER) from the environment or "
        ".env; the game folder is only read.",
    )
    orig_and_manifest(p)
    p.add_argument("--env-file", type=Path, default=None, help="default: <repo>/.env")
    p.set_defaults(func=_cmd_ingest)

    p = sub.add_parser("check-orig", help="verify orig/ against config/targets.toml")
    orig_and_manifest(p)
    p.set_defaults(func=_cmd_check_orig)

    p = sub.add_parser("parse-le", help="print the LE layout of an executable")
    p.add_argument("file", type=Path)
    p.add_argument("--json", action="store_true", help="print the summary as JSON")
    p.set_defaults(func=_cmd_parse_le)

    p = sub.add_parser(
        "rebuild",
        help="rebuild every target (or only --exe NAME) from orig/ into build/ and check its "
        "SHA-1 against config/targets.toml",
    )
    orig_and_manifest(p)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="default: %(default)s")
    p.add_argument(
        "--exe",
        metavar="NAME",
        help="rebuild only this target from the manifest (case-insensitive)",
    )
    p.add_argument("--json", action="store_true", help="print the results as JSON")
    p.set_defaults(func=_cmd_rebuild)

    _add_cc_command(sub)
    _add_omf2elf_command(sub)
    _add_libmatch_command(sub)
    _add_cppscan_command(sub)
    _add_probe_command(sub)
    _add_asm_command(sub)
    _add_score_command(sub)
    _add_discover_command(sub)
    _add_functions_command(sub)
    _add_units_command(sub)
    _add_ghidra_export_command(sub)
    _add_lint_command(sub)
    _add_check_command(sub)
    _add_target_command(sub)
    _add_land_command(sub)
    _add_gate_command(sub)
    _add_context_command(sub)
    _add_attempt_command(sub)
    _add_drive_command(sub)
    _add_mechanics_command(sub)
    _add_flags_command(sub)
    _add_watcom_commands(sub)
    return parser


_ERRORS = (
    IngestError,
    LEError,
    ManifestError,
    ISOError,
    WatcomError,
    CompilerError,
    CflagsError,
    LibMatchError,
    CppScanError,
    ProbeError,
    OMFError,
    Omf2ElfError,
    ElfError,
    FunctionsError,
    DiscoverError,
    UnitsError,
    SymbolError,
    AsmError,
    ScoreError,
    GhidraError,
    LintError,
    CheckError,
    TargetError,
    RelocError,
    LandError,
    SpliceError,
    StatusError,
    AttemptError,
    ContextPackError,
    MechanicsError,
    flags.FlagsError,
    OSError,
)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    args = build_parser().parse_args(argv)
    args.raw_argv = tuple(argv)  # the attempt wrapper checks its own argv against the hook's forms
    try:
        return args.func(args)
    except _ERRORS as exc:
        print(f"reverseapoc {args.command}: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
