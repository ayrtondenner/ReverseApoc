"""`reverseapoc` command line: ingest, check-orig, parse-le, rebuild, cc, omf2elf, libmatch,
cppscan, probe, asm, score, discover, functions, ghidra-export, lint, fetch-watcom,
install-watcom, check-watcom."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from . import probe
from .asm import AsmError, data_ranges, select_rows, write_listings
from .cflags import DEFAULT_CFLAGS, CflagsError
from .compiler import DEFAULT_LOG, CompilerError, compile_source
from .cppscan import CppScanError
from .cppscan import scan as cpp_scan
from .discover import DiscoverError, discover
from .elf import ElfError
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
    reconcile,
    seed_runtime_rows,
    symbols_csv_path,
    write_boundaries_csv,
    write_functions_csv,
)
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
from .omf import OMFError
from .omf2elf import Omf2ElfError, convert_file
from .probe import CHK_PUBLIC, ProbeError
from .score import ScoreError, ScoreReport, assess
from .splice import DEFAULT_OUT, _write_atomic, rebuild
from .symbols import SymbolError, SymbolTable
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
    _write_atomic(output, text.encode("utf-8"))
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
    if args.top < 1:
        raise ScoreError(f"--top must be at least 1, not {args.top}")
    target = select_target(load_manifest(args.manifest), args.exe, args.manifest)
    inputs = _split_inputs(args, target)
    assessments = assess(
        inputs.rows,
        flat=inputs.le.load_flat(relocate=False),
        fixups=inputs.le.fixups(),
        symbols=inputs.symbols,
        chk_targets=_chk_targets(inputs),
        runtime_starts=_runtime_starts(target),
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
    }


def _format_functions_report(report: dict) -> str:
    kinds = ", ".join(f"{n} {kind}" for kind, n in report["kinds"].items())
    verdicts = report["verdicts"]
    missing = verdicts["missing"]
    return "\n".join([
        f"{report['exe']}: {report['functions']} functions ({kinds})",
        f"{report['disagreements']} disagreements: {verdicts['auto']} auto (rule), "
        f"{verdicts['hand']} hand, {missing} missing verdict{'' if missing == 1 else 's'}",
        f"{report['dropped_ghidra']} Ghidra entries outside the code object dropped",
    ])  # fmt: skip


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
    write_functions_csv(out_dir / "functions.csv", result.functions, target.name)
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

DEFAULT_SRC = REPO_ROOT / "src"


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
        _write_atomic(args.stamp, stamp.encode("ascii"))
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
    _add_ghidra_export_command(sub)
    _add_lint_command(sub)
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
    SymbolError,
    AsmError,
    ScoreError,
    GhidraError,
    LintError,
    OSError,
)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except _ERRORS as exc:
        print(f"reverseapoc {args.command}: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
