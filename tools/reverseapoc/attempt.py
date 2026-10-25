# SPDX-License-Identifier: GPL-3.0-or-later
"""The attempt wrapper (D-44): the only commands a matching session runs through Bash.

`uv run --frozen reverseapoc attempt check|asm|context` is bound to the claimed function. The
claim comes only from the driver's environment (REVERSEAPOC_CLAIM, REVERSEAPOC_FUNC,
REVERSEAPOC_ATTEMPT_DIR), each validated here; no agent argument chooses the unit, the
function, the flags, the Watcom tree or the source root. The accepted argument shapes are
exactly hooks.ATTEMPT_FORMS (ruling F27), which the matching-session hook allows.

`attempt check` runs `reverseapoc check <claim> --json` in the container through an injectable
runner, at most CHECK_BUDGET times per attempt (D-07). One run at a time: each holds
`check.lock` and reserves its number by creating the snapshot of the C it checks
(`checks/NNNN.c`, ruling F10, O_EXCL), so a reserved slot counts even if the run then fails.
Each run keeps the JSON (`checks/NNNN.json`) and appends one line to `checks.jsonl`, all under
the gitignored attempt directory in build/driver/. `--sweep` runs the
D-17 flag matrix as a diagnostic: a cell at 100% under flags other than the unit's cflags.txt
rule is logged as `sweep_hit`, for the owner to decide (D-18 of Phase 5; cflags.txt is
owner-only).
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import asm, contextpack
from .asm import data_ranges
from .cflags import DEFAULT_CFLAGS, load_cflags, select_rule
from .check import DEFAULT_CONFIG, DEFAULT_SRC, EXIT_MISMATCH, EXIT_OK, EXIT_TOOL, PERFECT
from .fileio import write_atomic
from .functions import FunctionRow, read_functions_csv, read_symbols_csv
from .hooks import ATTEMPT_FORMS, ATTEMPT_PREFIX, CLAIM_ENV, attempt_form_matches
from .le import LE, Fixup
from .libmatch import read_target, select_target
from .status import read_status, status_path
from .symbols import SymbolTable
from .targets import DEFAULT_MANIFEST, DEFAULT_ORIG, REPO_ROOT, config_dir, load_manifest

FUNC_ENV = "REVERSEAPOC_FUNC"
DIR_ENV = "REVERSEAPOC_ATTEMPT_DIR"
CHECK_BUDGET = 25  # D-07: "or stop after 25 check runs", enforced here
CHECK_TIMEOUT = 580  # seconds; under the Bash tool's 600 s cap, so the run is still logged
CHECKS_DIR = "checks"
CHECK_LOG = "checks.jsonl"
CHECK_LOCK = "check.lock"
NOTES_FILE = "notes.md"  # the driver's REVERSEAPOC_ATTEMPT_NOTES is <attempt dir>/notes.md (06-23)
_SNAPSHOT = re.compile(r"([0-9]{4})\.c")  # checks/NNNN.c: one reserved run
_O_BINARY = getattr(os, "O_BINARY", 0)  # Windows: no newline translation in the snapshot
DRIVER_PARTS = ("build", "driver")
CONTAINER_CHECK = ("docker", "compose", "run", "--rm", "-T", "build",
                   "uv", "run", "--frozen", "reverseapoc", "check")  # fmt: skip
_CLAIM = re.compile(r"(ufo2p|tacp)/([a-z0-9_]+)")
_FUNC = re.compile(r"func_([0-9A-F]{8})")
_HEX = 16
_TAIL_LINES = 40  # of a failed run's output shown to the agent
MEASURED = "measured"  # a sweep cell's status once compiled and diffed


class AttemptError(ValueError):
    """The wrapper refuses: a bad environment, an argument outside ATTEMPT_FORMS, the check
    budget used, an unreadable unit file. The CLI turns it into exit 2."""


@dataclass(frozen=True)
class Roots:
    """Where the wrapper reads and writes; the defaults are the repository's own trees."""

    repo: Path = REPO_ROOT
    orig: Path = DEFAULT_ORIG
    manifest: Path = DEFAULT_MANIFEST
    config: Path = DEFAULT_CONFIG
    src: Path = DEFAULT_SRC
    asm: Path = REPO_ROOT / "asm"
    cflags: Path = DEFAULT_CFLAGS
    common_h: Path = REPO_ROOT / "include" / "common.h"
    matching: Path = REPO_ROOT / "docs" / "matching.md"

    @property
    def driver(self) -> Path:
        return Path(self.repo).resolve().joinpath(*DRIVER_PARTS)


ROOTS = Roots()  # read at call time; tests replace it


@dataclass(frozen=True)
class Ran:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[Sequence[str]], Ran]


def default_runner(argv: Sequence[str]) -> Ran:
    """Runs argv from the repository root (where compose.yaml is), no shell. A missing docker
    or a timeout becomes a failed run (exit 2), so it is still logged and counted."""
    try:
        proc = subprocess.run(list(argv), cwd=ROOTS.repo, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=CHECK_TIMEOUT,
                              check=False)  # fmt: skip
    except FileNotFoundError as exc:
        return Ran(EXIT_TOOL, "", f"{argv[0]} not found: {exc}")
    except subprocess.TimeoutExpired:
        return Ran(EXIT_TOOL, "", f"the check ran longer than {CHECK_TIMEOUT} s and was stopped")
    return Ran(proc.returncode, proc.stdout or "", proc.stderr or "")


RUNNER: Runner = default_runner  # read at call time; tests replace it


def form_allowed(argv: Sequence[str]) -> bool:
    """Whether `argv` (after `attempt`) is one of hooks.ATTEMPT_FORMS (ruling F27)."""
    return attempt_form_matches(argv)


def forms_text() -> str:
    return "; ".join(" ".join((*ATTEMPT_PREFIX, *form)) for form in ATTEMPT_FORMS)


# ---- the claim (D-44: from the driver's environment only) ----


def _inside(path: Path, anchor: Path) -> bool:
    """`path` strictly below `anchor`, compared part by part with exact case (contextpack's
    rule: the container's file system does not fold case, and .gitignore's build/ does not
    cover Build/)."""
    parts, base = path.parts, anchor.parts
    return len(parts) > len(base) and tuple(parts[: len(base)]) == tuple(base)


@dataclass(frozen=True)
class Claim:
    exe: str  # ufo2p or tacp
    unit: str
    function: str  # func_XXXXXXXX
    attempt_dir: Path  # resolved, below build/driver/

    @property
    def target(self) -> str:
        return f"{self.exe}/{self.unit}"

    @property
    def address(self) -> int:
        return int(self.function[len("func_") :], _HEX)

    @classmethod
    def from_env(cls, env: Mapping[str, str], *, roots: Roots) -> Claim:
        claim = _CLAIM.fullmatch(env.get(CLAIM_ENV) or "")
        if claim is None:
            raise AttemptError(f"{CLAIM_ENV} must be set by the driver to ufo2p/<unit> or "
                               "tacp/<unit> (unit [a-z0-9_]+)")  # fmt: skip
        function = env.get(FUNC_ENV) or ""
        if _FUNC.fullmatch(function) is None:
            raise AttemptError(f"{FUNC_ENV} must be set by the driver to func_XXXXXXXX "
                               "(8 upper-case hex digits)")  # fmt: skip
        return cls(claim.group(1), claim.group(2), function, _attempt_dir(env, roots))


def _attempt_dir(env: Mapping[str, str], roots: Roots) -> Path:
    value = env.get(DIR_ENV) or ""
    anchor = roots.driver
    if not value:
        raise AttemptError(f"{DIR_ENV} must be set by the driver to a directory below {anchor}")
    path = (Path(roots.repo) / value).resolve()  # an absolute value replaces the root
    if not _inside(path, anchor) or not path.is_dir():
        raise AttemptError(f"{DIR_ENV} {value!r} is not an existing directory below {anchor} "
                           "(the gitignored build/driver/, exact case)")  # fmt: skip
    return path


# ---- attempt check ----


def container_check_argv(claim: Claim, *, sweep: bool) -> tuple[str, ...]:
    """`check <claim> --json` in the container's `build` service (-T: no tty, so the output is
    captured), plus `--sweep <function>` for the D-17 diagnostic."""
    argv = (*CONTAINER_CHECK, claim.target, "--json")
    return (*argv, "--sweep", claim.function) if sweep else argv


@dataclass(frozen=True)
class CheckLogLine:
    """One line of checks.jsonl. best_percent, reloc_ok and bytes_ok are the claimed
    function's (a sweep: its best cell's); None when the run printed no usable JSON."""

    n: int
    exit: int
    sweep: bool
    best_percent: float | None
    reloc_ok: bool | None
    bytes_ok: bool | None
    splice_ok: bool | None  # None for a sweep: it never lands
    sweep_hit: str | None  # "wcc386@V flags..." of a 100% cell under non-default flags
    source: str  # the C this run checked, relative to the attempt directory (F10)

    def to_json(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _parse(stdout: str) -> dict[str, Any] | None:
    try:
        doc = json.loads(stdout)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def _claimed(doc: Mapping[str, Any], claim: Claim) -> Mapping[str, Any] | None:
    for fn in doc["functions"]:
        if int(fn["va"], _HEX) == claim.address:
            return fn
    return None


def _check_line(
    doc: Mapping[str, Any], claim: Claim, ran: Ran, n: int, source: str
) -> CheckLogLine:
    ok = doc["ok"]
    if not isinstance(ok, bool):
        raise TypeError("ok is not a boolean")
    fn = _claimed(doc, claim)
    splices = doc["splice"]
    expected = EXIT_OK if ok else EXIT_MISMATCH
    return CheckLogLine(
        n, expected if ran.returncode == expected else EXIT_TOOL, False,
        float(fn["objdiff_percent"]) if fn else 0.0,
        fn["reloc"]["ok"] is True if fn else False,
        fn["bytes"]["ok"] is True if fn else False,
        bool(splices) and all(s["ok"] is True for s in splices),
        None, source,
    )  # fmt: skip


def _measured(doc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cells = [c for c in doc["cells"] if c["status"] == MEASURED]
    return sorted(cells, key=lambda c: int(c["cell"]))


def _cell_spec(cell: Mapping[str, Any]) -> str:
    return " ".join([str(cell["compiler"]), *map(str, cell["flags"])])


def _is_hit(cell: Mapping[str, Any], default: str) -> bool:
    perfect = cell["objdiff_percent"] == PERFECT and cell["reloc_ok"] is True
    return perfect and cell["differing"] == 0 and _cell_spec(cell) != default


def _best_cell(cells: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """check.SweepCell.rank: a passing relocation check, then objdiff, then fewer bytes."""
    ranked = sorted(cells, key=lambda c: (c["reloc_ok"] is not True, -float(c["objdiff_percent"]),
                                          int(c["differing"])))  # fmt: skip
    return ranked[0] if ranked else None


def _sweep_line(
    doc: Mapping[str, Any], default: str, ran: Ran, n: int, source: str
) -> CheckLogLine:
    cells = _measured(doc)
    best = _best_cell(cells)
    hit = next((_cell_spec(c) for c in cells if _is_hit(c, default)), None)
    return CheckLogLine(
        n, EXIT_OK if ran.returncode == EXIT_OK else EXIT_TOOL, True,
        float(best["objdiff_percent"]) if best else 0.0,
        best["reloc_ok"] is True if best else None,
        best["differing"] == 0 if best else None,
        None, hit, source,
    )  # fmt: skip


def _default_spec(claim: Claim, roots: Roots) -> str:
    """The unit's own cflags.txt rule as a sweep cell names it: `wcc386@10.6 -4r -s -fpi`."""
    rule = select_rule(load_cflags(roots.cflags), f"src/{claim.exe}/{claim.unit}.c")
    return " ".join([rule.spec, *rule.flags])


def _tool_line(n: int, sweep: bool, source: str) -> CheckLogLine:
    return CheckLogLine(n, EXIT_TOOL, sweep, None, None, None, None, None, source)


def _tail(text: str) -> list[str]:
    return [f"  | {line}" for line in text.rstrip("\n").splitlines()[-_TAIL_LINES:]]


def _ok(value: object) -> str:
    return "ok" if value is True else "FAILED"


def _check_summary(doc: Mapping[str, Any]) -> list[str]:
    lines = []
    for fn in doc["functions"]:
        same = fn["bytes"]
        differ = "" if same["ok"] is True else f" ({same['differing']} differ)"
        reloc = _ok(fn["reloc"]["ok"])
        lines.append(f"  {fn['name']}  {fn['va']}  objdiff {fn['objdiff_percent']:g}%  "
                     f"reloc {reloc}  bytes {_ok(same['ok'])}{differ}")  # fmt: skip
        lines += [f"    reloc: {problem}" for problem in fn["reloc"]["problems"]]
    lines += [f"  problem: {p['name']} {p['va'] or ''} {p['reason']}" for p in doc["problems"]]
    lines += [f"  stub: {s['name']} {s['va']}" for s in doc.get("stubs", ())]
    lines += [f"  splice {s['exe']} {_ok(s['ok'])}" for s in doc["splice"]]
    return lines


def _sweep_summary(doc: Mapping[str, Any], line: CheckLogLine) -> list[str]:
    best = _best_cell(_measured(doc))
    lines = ["  a sweep is a diagnostic: it never lands and never edits config/cflags.txt"]
    if best is None:
        lines.append("  no cell was measured")
    else:
        lines.append(f"  best cell {int(best['cell']):02d}  {_cell_spec(best)}  objdiff "
                     f"{best['objdiff_percent']:g}%  reloc {_ok(best['reloc_ok'])}  "
                     f"differing {best['differing']}")  # fmt: skip
    if line.sweep_hit:
        lines.append(f"  sweep hit: needs flags {line.sweep_hit} (the owner decides; "
                     "cflags.txt is owner-only)")  # fmt: skip
    return lines


_VERDICT = {EXIT_OK: "OK", EXIT_MISMATCH: "MISMATCH", EXIT_TOOL: "TOOL ERROR"}


def _summary(claim: Claim, line: CheckLogLine, doc: Mapping[str, Any] | None, ran: Ran) -> str:
    kind = "check --sweep" if line.sweep else "check"
    head = (f"attempt {kind} {line.n}/{CHECK_BUDGET} {claim.target} {claim.function}: "
            f"exit {line.exit} {_VERDICT[line.exit]}")  # fmt: skip
    body = []
    if doc is not None:
        body = _sweep_summary(doc, line) if line.sweep else _check_summary(doc)
    else:
        body = ["  the check printed no usable JSON"] + _tail(ran.stdout)
    if line.exit == EXIT_TOOL or doc is None:
        body += _tail(ran.stderr)
    source = claim.attempt_dir / line.source
    saved = (f"saved {source.with_suffix('.json').as_posix()} (full JSON) and "
             f"{source.as_posix()} (the C checked)\n"
             f"notes: {(claim.attempt_dir / NOTES_FILE).as_posix()}")  # fmt: skip
    return "\n".join([head, *body, saved])


def _append(log: Path, line: CheckLogLine) -> None:
    with log.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(line.to_json(), sort_keys=True) + "\n")


@contextmanager
def _check_lock(attempt_dir: Path) -> Iterator[None]:
    """Hold <attempt dir>/check.lock (O_CREAT|O_EXCL) for one whole run (security finding 1:
    a session can start checks with Bash run_in_background, and each would read the same
    count). Held already: AttemptError at once. A stale lock (a killed run) is never cleared:
    every session gets a fresh attempt directory, so it ends this attempt's checks."""
    lock = attempt_dir / CHECK_LOCK
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise AttemptError(f"another check is running in this attempt ({lock} exists; run "
                           "checks one at a time, in the foreground)") from exc  # fmt: skip
    try:
        try:
            os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        finally:
            os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def _reserved(checks: Path) -> int:
    """The highest run number reserved in checks/ (a NNNN.c snapshot), 0 for none. A slot
    counts whether or not its run finished or logged a line."""
    numbers = [int(m.group(1)) for p in checks.iterdir() if (m := _SNAPSHOT.fullmatch(p.name))]
    return max(numbers, default=0)


def _reserve(path: Path, text: bytes) -> None:
    """Create the run's snapshot with O_EXCL: the file is the slot (ruling F10)."""
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | _O_BINARY, 0o644)
    except FileExistsError as exc:
        raise AttemptError(f"{path} is already reserved") from exc
    with os.fdopen(fd, "wb") as fh:
        fh.write(text)


def run_check(claim: Claim, *, sweep: bool, runner: Runner, roots: Roots) -> tuple[int, str]:
    """One check run of the claimed unit: (exit code 0/1/2, the summary to print). Under the
    attempt's check lock, the budget is checked and the run's slot reserved (its snapshot of
    the unit file) before the container starts."""
    with _check_lock(claim.attempt_dir):
        return _locked_check(claim, sweep=sweep, runner=runner, roots=roots)


def _locked_check(claim: Claim, *, sweep: bool, runner: Runner, roots: Roots) -> tuple[int, str]:
    log = claim.attempt_dir / CHECK_LOG
    checks = claim.attempt_dir / CHECKS_DIR
    checks.mkdir(exist_ok=True)
    n = _reserved(checks) + 1
    if n > CHECK_BUDGET:
        raise AttemptError(f"check budget used: {CHECK_BUDGET} check runs in this attempt "
                           "(D-07); write notes.md and stop")  # fmt: skip
    default = _default_spec(claim, roots) if sweep else ""
    unit = Path(roots.src) / claim.exe / f"{claim.unit}.c"
    try:
        text = unit.read_bytes()
    except OSError as exc:
        raise AttemptError(f"{unit} cannot be read: {exc}") from exc
    stem = f"{n:04d}"
    source = f"{CHECKS_DIR}/{stem}.c"
    _reserve(claim.attempt_dir / source, text)
    ran = runner(container_check_argv(claim, sweep=sweep))
    doc = _parse(ran.stdout)
    try:
        if doc is None:
            raise ValueError("no JSON")
        line = (_sweep_line(doc, default, ran, n, source) if sweep
                else _check_line(doc, claim, ran, n, source))  # fmt: skip
        summary = _summary(claim, line, doc, ran)
    except (KeyError, TypeError, ValueError, AttributeError):
        doc = None
        line = _tool_line(n, sweep, source)
        summary = _summary(claim, line, None, ran)
    saved = doc if doc is not None else {"error": "no usable JSON", "returncode": ran.returncode,
                                         "stdout": ran.stdout, "stderr": ran.stderr}  # fmt: skip
    write_atomic(checks / f"{stem}.json", (json.dumps(saved, indent=2) + "\n").encode("utf-8"))
    _append(log, line)
    return line.exit, summary


def cmd_check(*, sweep: bool) -> int:
    claim = Claim.from_env(os.environ, roots=ROOTS)
    code, text = run_check(claim, sweep=sweep, runner=RUNNER, roots=ROOTS)
    print(text)
    return code


# ---- listings and the context pack (attempt asm, attempt context, the context verb; D-13) ----

IDIOM_HEADINGS = ("Known idioms", "Relocation rules")  # the matching.md sections a pack holds
NOTES_CAP = 6144  # bytes of earlier notes kept (the newest), so notes alone never fill the pack
ATTEMPT_LOG = Path("progress") / "attempts.jsonl"  # the driver's tracked log (06-23)
MANUAL_RUN = "manual"  # build/driver/manual/<exe>/<func>/: packs built by hand
_SECTION = re.compile(r"(?m)^(?=## )")


@dataclass(frozen=True)
class ExeData:
    """One EXE as the pack and the listings need it: rows, symbols and the unrelocated image."""

    stem: str  # ufo2p
    rows: list[FunctionRow]
    symbols: SymbolTable
    flat: bytes | bytearray
    fixups: list[Fixup]


def load_exe(
    exe: str,
    *,
    orig: Path,
    manifest: Path,
    config: Path,
    functions: Path | None = None,
    symbols: Path | None = None,
) -> ExeData:
    """The EXE (checked against the manifest) with config/<exe>/functions.csv and symbols.csv
    under `config` unless given."""
    target = select_target(load_manifest(manifest), exe, manifest)
    stem = config_dir(target.name).name
    rows = read_functions_csv(functions or Path(config) / stem / "functions.csv")
    le = LE(read_target(target, orig, manifest))
    named = read_symbols_csv(symbols or Path(config) / stem / "symbols.csv")
    table = SymbolTable.build(rows, named, data_ranges=data_ranges(le))
    return ExeData(stem, rows, table, le.load_flat(relocate=False), le.fixups())


def placeholder(row: FunctionRow) -> str:
    """func_XXXXXXXX: the driver's directory name for a row (REVERSEAPOC_FUNC's form)."""
    return f"func_{row.start:08X}"


def resolve_row(data: ExeData, name: str) -> FunctionRow:
    """The row of `data` whose functions.csv name, C name or placeholder is `name`."""
    for row in data.rows:
        if name in (row.name, data.symbols.c_name(row.start), placeholder(row)):
            return row
    raise AttemptError(f"{name} is no functions.csv row of {data.stem}")


def listing_text(data: ExeData, row: FunctionRow, asm_root: Path) -> str:
    path = Path(asm_root) / data.stem / asm.file_name(data.symbols, row)
    if not path.is_file():
        raise AttemptError(f"no listing {path}; the owner writes them with "
                           f"`uv run reverseapoc asm {data.stem}`")  # fmt: skip
    return path.read_text(encoding="utf-8")


def idioms(text: str | None) -> str | None:
    """The IDIOM_HEADINGS sections of docs/matching.md, picked by heading."""
    if text is None:
        return None
    def wanted(part: str) -> bool:
        return part.startswith("## ") and part[3:].partition("\n")[0].strip() in IDIOM_HEADINGS

    parts = [part.rstrip("\n") for part in _SECTION.split(text) if wanted(part)]
    return "\n\n".join(parts) + "\n" if parts else None


def _bounded(text: str) -> str:
    data = text.encode("utf-8")
    if len(data) <= NOTES_CAP:
        return text
    kept = data[-NOTES_CAP:].decode("utf-8", errors="ignore")
    return f"... {len(data) - NOTES_CAP} bytes of older notes cut\n{kept}"


def _attempt_records(log: Path, stem: str, func: str) -> list[str]:
    if not log.is_file():
        return []
    records = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict) or record.get("kind") != "attempt":
            continue
        if record.get("exe") == stem and record.get("function") == func:
            records.append(json.dumps(record, sort_keys=True))
    return records


def earlier_notes(repo: Path, stem: str, func: str) -> str | None:
    """Ruling F9: build/driver/*/<exe>/<func>/attempt-*/notes.md (the driver's layout) and
    build/driver/*/<exe>/<func>/notes.md (manual packs), sorted by path, then this function's
    attempt records in progress/attempts.jsonl; the newest NOTES_CAP bytes."""
    driver = Path(repo).joinpath(*DRIVER_PARTS)
    found = {*driver.glob(f"*/{stem}/{func}/attempt-*/notes.md"),
             *driver.glob(f"*/{stem}/{func}/notes.md")}  # fmt: skip
    parts = []
    for path in sorted(found, key=lambda p: p.relative_to(driver).as_posix()):
        text = path.read_text(encoding="utf-8", errors="replace").rstrip("\n")
        parts.append(f"--- {path.relative_to(driver).as_posix()}\n{text}")
    records = _attempt_records(Path(repo) / ATTEMPT_LOG, stem, func)
    if records:
        parts.append("\n".join([f"--- {ATTEMPT_LOG.as_posix()}", *records]))
    return _bounded("\n\n".join(parts) + "\n") if parts else None


def _unit_texts(src: Path, data: ExeData, claimed: str) -> dict[str, str]:
    """Every unit file of the EXE (06-13 note a: neighbours in other units need their C), read
    as bytes decoded as strict UTF-8 (note b: a lone CR stays refused, never translated). A
    unit that is not UTF-8 is left out, unless it is the claimed one."""
    texts = {}
    for unit in sorted({row.unit for row in data.rows if row.unit}):
        path = Path(src) / data.stem / f"{unit}.c"
        if not path.is_file():
            continue
        try:
            texts[unit] = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            if unit == claimed:
                raise AttemptError(f"{path} is not UTF-8: {exc}") from exc
    return texts


def _optional_text(path: Path) -> str | None:
    return Path(path).read_text(encoding="utf-8") if Path(path).is_file() else None


def make_pack(
    data: ExeData,
    row: FunctionRow,
    *,
    src: Path,
    config: Path,
    asm_root: Path,
    roots: Roots,
    calls: contextpack.CallIndex | None = None,
) -> contextpack.Pack:
    """The D-13 pack of `row`: status from config/<exe>/status.csv, every unit text of the EXE,
    the listing and draft from asm/<exe>/ (and its ghidra/), include/common.h, the matching.md
    idioms and earlier notes. Pass `calls` to reuse one CallIndex across functions."""
    status = {entry.start: entry.status for entry in read_status(status_path(config, data.stem))}
    listing_dir = Path(asm_root) / data.stem
    inputs = contextpack.gather(
        row, rows=data.rows, flat=data.flat, fixups=data.fixups, symbols=data.symbols,
        status=status, unit_texts=_unit_texts(src, data, row.unit), listing_dir=listing_dir,
        draft_dir=listing_dir / "ghidra", common_h=_optional_text(roots.common_h),
        idioms=idioms(_optional_text(roots.matching)),
        notes=earlier_notes(roots.repo, data.stem, placeholder(row)), calls=calls,
    )  # fmt: skip
    return contextpack.build_pack(**inputs)


def _claimed_row() -> tuple[Claim, ExeData, FunctionRow]:
    claim = Claim.from_env(os.environ, roots=ROOTS)
    data = load_exe(claim.exe, orig=ROOTS.orig, manifest=ROOTS.manifest, config=ROOTS.config)
    row = resolve_row(data, claim.function)
    if row.unit != claim.unit:
        raise AttemptError(f"{claim.function} is in unit {row.unit!r}, not the claimed "
                           f"{claim.unit}")  # fmt: skip
    return claim, data, row


def cmd_asm(name: str | None) -> int:
    """Print the claimed function's listing, or that of NAME (another row of the same EXE)."""
    _, data, row = _claimed_row()
    if name is not None:
        row = resolve_row(data, name)
    sys.stdout.write(listing_text(data, row, ROOTS.asm))
    return EXIT_OK


def cmd_context() -> int:
    """Rebuild the claimed function's pack into <attempt dir>/context.md and print it."""
    claim, data, row = _claimed_row()
    pack = make_pack(data, row, src=ROOTS.src, config=ROOTS.config, asm_root=ROOTS.asm,
                     roots=ROOTS)  # fmt: skip
    path = contextpack.write_pack(pack, claim.attempt_dir, root=ROOTS.repo)
    sys.stdout.write(pack.text)
    notes = (claim.attempt_dir / NOTES_FILE).as_posix()
    print(f"wrote {path.as_posix()}; notes: {notes}", file=sys.stderr)
    return EXIT_OK
