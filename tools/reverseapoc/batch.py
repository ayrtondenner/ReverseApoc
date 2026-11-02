# SPDX-License-Identifier: GPL-3.0-or-later
"""Batch compile and judge: many C files, many flag cells, one gate per Watcom version.

Ported from the spike 010/011 harness (.planning/spikes/010-deterministic-matching/common.py and
.planning/spikes/011-flags-from-filler/judge_cli.py), which keep their own copies.

`compile_batch` gates each (compiler, version) once per batch (compiler.check_gate), then runs
compiler.build_argv commands in a thread pool. There is no cc.log and no provenance stamp: only
`check` and ninja need those. `judge` is check.py's own pieces: defined_functions, with_relocs
(the relocation check with the unit's public map and a leading jump table) and compare_bytes. A
function is exact when both pass: check's own verdict, which accepts the original's trailing
Watcom filler under the 07-48 rule (relocs.py rule 1, docs/matching.md). `score` (difflib over
decoded instructions, relocated fields masked) and `key` (the first differing instruction as
mnemonic shapes) only rank and diagnose; they decide nothing.

This is never a match: nothing here lands, writes status.csv or edits config/cflags.txt. A match
is still claimed only by `reverseapoc check` / `gate` (D-16). Records hold addresses, counts,
percentages and mnemonic shapes, never bytes.
"""

from __future__ import annotations

import dataclasses
import difflib
import functools
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import compiler, x86
from .cflags import Rule, parse_cflags, select_rule
from .check import (
    DEFAULT_CONFIG,
    CheckError,
    ExeInputs,
    compare_bytes,
    defined_functions,
    load_exe,
    parse_module,
    select_exe,
    unit_rule_path,
    with_relocs,
)
from .fileio import write_atomic
from .functions import KIND_DATA_IN_CODE, FunctionRow
from .omf import Module, OMFError
from .relocs import FIELD_SIZE
from .targets import DEFAULT_MANIFEST, DEFAULT_ORIG, REPO_ROOT, load_manifest
from .watcom import DEFAULT_INSTALL
from .x86 import Insn, decode

BUILD_ROOT = REPO_ROOT / "build" / "batch"
ERR_SUFFIX = ".err"


class BatchError(ValueError):
    """A batch cannot run as asked: bad jobs, an unknown row, a refused cell or source."""


# ---- batch compile ----


@dataclass(frozen=True)
class Job:
    src: Path
    obj: Path
    rule: Rule


@dataclass(frozen=True)
class Compiled:
    job: Job
    ok: bool  # exit 0 and the object exists
    seconds: float
    output: str  # the compiler's stdout then stderr


@dataclass(frozen=True)
class BatchResult:
    compiled: tuple[Compiled, ...]  # in job order
    gate_s: float
    compile_wall_s: float


Gate = Callable[[str, str], compiler.Gate]


def _check_jobs(jobs: Sequence[Job], workers: int) -> None:
    if workers < 1:
        raise BatchError(f"workers must be at least 1, got {workers}")
    seen: dict[Path, Job] = {}
    for job in jobs:
        if job.obj.suffix != compiler.OBJ_SUFFIX:
            raise BatchError(f"object {job.obj} must end in {compiler.OBJ_SUFFIX}")
        obj = job.obj.resolve()
        if obj == job.src.resolve():
            raise BatchError(f"object {job.obj} is its own source")
        if obj in seen:
            raise BatchError(f"two jobs name one object {job.obj}: {seen[obj].src} and {job.src}")
        seen[obj] = job


@dataclass(frozen=True)
class _Setup:
    root: Path
    gates: dict[tuple[str, str], compiler.Gate]
    includes: dict[str, str]  # version -> the -i= list
    prefix: list[str]
    env: dict[str, str]
    run: Callable[..., Any]


def _compile_one(setup: _Setup, job: Job) -> Compiled:
    root = setup.root
    src = compiler.guest_path(job.src, root, inside=True)
    obj = compiler.guest_path(job.obj, root, inside=True)
    err = compiler.guest_path(job.obj.with_suffix(ERR_SUFFIX), root, inside=True)
    gate = setup.gates[job.rule.compiler, job.rule.version]
    argv = compiler.build_argv(
        gate.root / compiler.COMPILER_EXE, job.rule, src, obj, err,
        setup.includes[job.rule.version], prefix=setup.prefix,
    )  # fmt: skip
    job.obj.unlink(missing_ok=True)
    t0 = time.perf_counter()
    proc = setup.run(
        argv, cwd=root, env=setup.env, capture_output=True, text=True, encoding="latin-1",
        errors="replace", check=False,
    )  # fmt: skip
    seconds = time.perf_counter() - t0
    if proc.returncode != 0:
        job.obj.unlink(missing_ok=True)  # a partial object must never be judged
    ok = proc.returncode == 0 and job.obj.is_file()
    return Compiled(job, ok, seconds, (proc.stdout or "") + (proc.stderr or ""))


def compile_batch(
    jobs: Iterable[Job],
    workers: int,
    *,
    root: Path = REPO_ROOT,
    watcom_dir: Path = DEFAULT_INSTALL,
    gate: Gate | None = None,
    run: Callable[..., Any] = subprocess.run,
    platform: str = sys.platform,
    environ: Mapping[str, str] = os.environ,
) -> BatchResult:
    """Compile every job in a pool of `workers`. The jobs are checked first (workers >= 1, one
    object per job), then the gate runs once per (compiler, version), timed apart as gate_s.
    A non-zero exit leaves no object, a stale one included."""
    jobs = tuple(jobs)
    _check_jobs(jobs, workers)
    gate = gate if gate is not None else functools.partial(
        compiler.check_gate, watcom_dir=watcom_dir
    )  # fmt: skip
    t0 = time.perf_counter()
    pairs = sorted({(job.rule.compiler, job.rule.version) for job in jobs})
    gates = {pair: gate(*pair) for pair in pairs}
    gate_s = time.perf_counter() - t0
    # Made before the pool: Path.resolve (guest_path) on Windows races with a parallel mkdir
    # (measured in spike 010).
    for parent in {job.obj.parent for job in jobs}:
        parent.mkdir(parents=True, exist_ok=True)
    root = Path(root)
    setup = _Setup(
        root, gates,
        {version: compiler._include_list(root, Path(watcom_dir), version) for _, version in pairs},
        compiler.runner_prefix(platform), compiler.scrubbed_env(environ, platform), run,
    )  # fmt: skip
    t1 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        compiled = tuple(pool.map(functools.partial(_compile_one, setup), jobs))
    return BatchResult(compiled, gate_s, time.perf_counter() - t1)


# ---- inputs ----


def load_exe_inputs(
    exe: str,
    *,
    orig_dir: Path = DEFAULT_ORIG,
    manifest: Path = DEFAULT_MANIFEST,
    config_root: Path = DEFAULT_CONFIG,
) -> ExeInputs:
    """The EXE `exe` (a manifest name or its stem) as check sees it. Use its .stem for paths."""
    target = select_exe(load_manifest(manifest), exe, manifest)
    return load_exe(target, orig_dir=orig_dir, manifest=manifest, config_root=config_root)


def committed_rule(rules: Sequence[Rule], stem: str, unit: str) -> Rule:
    """The cflags rule the committed src/<stem>/<unit>.c takes."""
    return select_rule(rules, unit_rule_path(stem, unit))


def row_at(exe: ExeInputs, start: int) -> FunctionRow:
    """The functions.csv row that starts at `start`; BatchError when there is none."""
    row = next((r for r in exe.rows if r.start == start), None)
    if row is None:
        raise BatchError(f"{exe.target.name}: no functions.csv row starts at 0x{start:08X}")
    return row


def table_row(exe: ExeInputs, row: FunctionRow) -> FunctionRow | None:
    """The data-in-code row right before `row` in its unit (a jump table that leads it)."""
    before = [r for r in exe.rows if r.unit == row.unit and r.start < row.start]
    if not before:
        return None
    last = max(before, key=lambda r: r.start)
    return last if last.kind == KIND_DATA_IN_CODE and last.end <= row.start else None


# ---- diff summary (ranks and diagnoses, decides nothing) ----

_NUM = re.compile(r"0x[0-9a-f]+|\b\d+\b")


def shape(mnemonic: str, op_str: str) -> str:
    """An instruction with every number shown as N."""
    return f"{mnemonic} {_NUM.sub('N', op_str)}".strip()


def _tokens(code: bytes, va: int, masked: set[int]) -> list[tuple[str, str, int]]:
    """(token, shape, va) per instruction; a token drops operand text when any of its bytes is a
    relocated field, so two references to different-but-relocated targets compare equal."""
    out = []
    for insn in decode(code, va):
        hit = any(a in masked for a in range(insn.va, insn.va + insn.size))
        form = shape(insn.mnemonic, insn.op_str)
        exact_text = f"{insn.mnemonic} {insn.op_str}"
        token = form if (hit or insn.branch_target is not None) else exact_text
        out.append((token, form, insn.va))
    return out


def _first_diff(a, b, sm: difflib.SequenceMatcher) -> str:
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        ours = a[i1][1] if i1 < i2 else "-"
        theirs = b[j1][1] if j1 < j2 else "-"
        return f"{ours} | {theirs}"
    return "length" if len(a) != len(b) else ""


def diff_summary(ours: bytes, theirs: bytes, va: int, masked: set[int]) -> tuple[float, str]:
    """(score, key): difflib's ratio of the decoded instruction tokens in percent (2 places)
    and the first differing pair as `ours | theirs` mnemonic shapes ("" when none differ)."""
    a = _tokens(ours, va, masked)
    b = _tokens(theirs, va, masked)
    sm = difflib.SequenceMatcher(a=[t for t, _, _ in a], b=[t for t, _, _ in b], autojunk=False)
    return round(100.0 * sm.ratio(), 2), _first_diff(a, b, sm)


# ---- Watcom alignment filler and the pad ----

def is_alignment_filler(insn: Insn) -> bool:
    """Watcom filler in any register: x86.is_alignment_filler (07-48), from capstone's operand
    detail: nop, mov r, r, lea r, [r] with no index, displacement 0 and no segment override,
    and x86's FILLER_ENCODINGS. `mov eax, dword ptr [eax]` is a load, not filler (the spike's
    regex took it as filler)."""
    return x86.is_alignment_filler(insn)


def ends_in_filler(code: bytes, va: int) -> bool:
    """The last instruction of `code` (loaded at `va`) is alignment filler."""
    last = None
    for last in decode(code, va):  # noqa: B007 - the loop keeps the last instruction
        pass
    return last is not None and is_alignment_filler(last)


def filler_tail(code: bytes, va: int, n: int) -> bool:
    """The bytes of `code` after its first `n` decode exactly to the end, as at least one
    instruction, and every one is alignment filler (an alignment gap after our function)."""
    tail = list(decode(code[n:], va + n))
    return (bool(tail) and sum(i.size for i in tail) == len(code) - n
            and all(is_alignment_filler(i) for i in tail))  # fmt: skip


# Watcom 10.6 aligns the next function only under a `t` optimisation (measured on tacp
# 0x000A68B0 in spike 010), so a row that ends in filler needs a next function under these.
ALIGNING_FLAGS = ("-ot", "-oneatx")
PAD_NAME = "reverseapoc_pad"
PAD_RETURN = 0x5A5A5A5A
# Not empty: an empty pad's `ret` is tail-merged into the previous function's `ret` (measured).
_PAD = f"\nint {PAD_NAME}(void)\n{{\n    return 0x{PAD_RETURN:08x};\n}}\n"


def aligns_functions(flags: Sequence[str]) -> bool:
    return any(flag in ALIGNING_FLAGS for flag in flags)


def needs_pad(code: bytes, va: int, flags: Sequence[str]) -> bool:
    """The row's original bytes end in filler and the cell aligns the next function."""
    return aligns_functions(flags) and ends_in_filler(code, va)


def pad_source(text: str) -> str:
    """`text` followed by the pad function, so Watcom aligns our function as in the original."""
    return text + _PAD


def cell_rule(base: Rule, flags_text: str) -> Rule:
    """`base` with the flags of one --cell, validated by cflags' own parser (no wrapper-owned
    flag such as -fo= or -i=, no path character, no second `-` in a flag)."""
    if not flags_text.strip():
        raise BatchError("a --cell needs at least one flag")
    parsed = parse_cflags(f"* {base.spec} {flags_text}", versions=(base.version,), where="--cell")
    return dataclasses.replace(base, flags=parsed[0].flags)


# ---- judge ----


@dataclass(frozen=True)
class Verdict:
    exact: bool  # reloc_ok and bytes_ok: check's own verdict
    reloc_ok: bool
    bytes_ok: bool
    differing: int
    len_ours: int
    len_row: int
    score: float
    key: str  # the first differing instruction pair as mnemonic shapes, or why there is none
    # A diagnostic, never a match: exact once the row's trailing filler is cut off, for a filler
    # tail the 07-48 rule refused (an end off 16-byte alignment, more than 15 bytes, an LE fixup
    # in the tail, or our last instruction not terminal, so our code would run into the filler).
    exact_trim: bool = False

    def to_json(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def _reloc_key(problems: Sequence[str]) -> str:
    if not problems:
        return "reloc"
    return "reloc: " + _NUM.sub("N", problems[0].split(": ", 1)[-1])


def judge(exe: ExeInputs, obj: Path, start: int) -> Verdict:
    """check's verdict for the row at `start` from our object `obj`: the relocation check (with
    the data-in-code row right before it as its leading table) and the byte compare. `exact` is
    check's own verdict, so it accepts original trailing filler under the 07-48 rule;
    `exact_trim` is only looked for when that rule refused a filler tail."""
    row = row_at(exe, start)
    rows = [r for r in (table_row(exe, row), row) if r is not None]
    length = row.end - row.start
    try:
        module = parse_module(obj.read_bytes(), obj)
    except (OSError, CheckError, OMFError) as exc:
        return Verdict(False, False, False, -1, 0, length, 0.0, f"no object: {exc}")
    defined = [d for d in defined_functions(module, rows, exe.symbols) if d.row.start == start]
    if not defined:
        return Verdict(False, False, False, -1, 0, length, 0.0, "not defined")
    ((d, reloc),) = with_relocs(module, defined, rows, exe)
    cmp = compare_bytes(d.ours, row, exe.flat, reloc)
    masked = {va + i for va in reloc.ours | reloc.theirs for i in range(FIELD_SIZE)}
    score, key = diff_summary(d.ours, exe.flat[row.start : row.end], row.start, masked)
    exact = reloc.ok and cmp.ok
    if exact:
        key = ""
    elif not key and not reloc.ok:
        key = _reloc_key(reloc.problems)
    verdict = Verdict(exact, reloc.ok, cmp.ok, cmp.differing, len(d.ours), length, score, key)
    n = len(d.ours)
    if exact or not 0 < n < length or not filler_tail(exe.flat[row.start : row.end], row.start, n):
        return verdict
    return dataclasses.replace(verdict, exact_trim=_trimmed_exact(module, exe, rows, row, n))


def _trimmed_exact(
    module: Module, exe: ExeInputs, rows: Sequence[FunctionRow], row: FunctionRow, n: int
) -> bool:
    """check's verdict against the row cut at our length `n`: exact up to the trailing filler,
    which the original linker or a 16-byte function alignment put there (a unit-boundary
    question, never a match)."""
    cut = dataclasses.replace(row, end=row.start + n)
    cut_rows = [cut if r is row else r for r in rows]
    defined = [d for d in defined_functions(module, cut_rows, exe.symbols)
               if d.row.start == row.start]  # fmt: skip
    if not defined:
        return False
    ((d, reloc),) = with_relocs(module, defined, cut_rows, exe)
    return reloc.ok and compare_bytes(d.ours, cut, exe.flat, reloc).ok


def unjudged(len_row: int, key: str = "") -> Verdict:
    """The verdict of a cell that was never judged (refused, or its compile failed)."""
    return Verdict(False, False, False, -1, 0, len_row, 0.0, key)


COMMITTED_CELL = "committed"


def _compile_key(compiled: Compiled) -> str:
    lines = [ln.strip() for ln in compiled.output.splitlines() if ln.strip()]
    first = next((ln for ln in lines if "Error" in ln), lines[0] if lines else "no output")
    return f"compile failed: {first}"


def cell_record(
    stem: str,
    start: int,
    cell: str,
    rule: Rule,
    compiled: Compiled | None,
    verdict: Verdict,
    key: str | None = None,
) -> dict[str, Any]:
    """One JSON record for (function, cell): `cell` is "committed" or the --cell text. A cell
    that was refused (`compiled` None) or failed to compile is never exact and scores 0.0."""
    ok = compiled is not None and compiled.ok
    if key is None:
        key = verdict.key if ok or compiled is None else _compile_key(compiled)
    return {
        "exe": stem,
        "address": f"0x{start:08X}",
        "cell": cell,
        "flags": " ".join(rule.flags),
        "compiled": ok,
        "exact": ok and verdict.exact,
        "exact_trim": ok and verdict.exact_trim,
        "score": verdict.score if ok else 0.0,
        "len": [verdict.len_ours if ok else 0, verdict.len_row],
        "key": key,
    }


# ---- source intake ----

# The CLAUDE.md hard rule: no inline assembly to force a match.
_BANNED = re.compile(r"#\s*pragma|\b_asm\b|\b__asm\b")


def refusal(text: str) -> str | None:
    """Why `text` may not be compiled (a #pragma or inline assembly), or None."""
    hit = _BANNED.search(text)
    if hit is None:
        return None
    return f"{hit.group(0)!r}: #pragma and inline assembly are not allowed"


def read_ascii(path: Path) -> str:
    """`path` as ASCII text; BatchError when it is not ASCII (OSError when it cannot be read)."""
    try:
        return path.read_text(encoding="ascii")
    except UnicodeDecodeError as exc:
        raise BatchError(f"{path}: not ASCII ({exc.reason} at byte {exc.start})") from exc


def parse_address(text: str) -> int:
    """A hex address, with or without 0x."""
    try:
        return int(text, 16)
    except ValueError as exc:
        raise BatchError(f"expected a hex address (e.g. 0x000108E0), got {text!r}") from exc


# ---- cells and their sources ----


def cells_for(base: Rule, cell_texts: Sequence[str]) -> list[tuple[str, Rule]]:
    """(name, rule) per cell: the committed rule first, then one validated rule per --cell."""
    return [(COMMITTED_CELL, base), *((text, cell_rule(base, text)) for text in cell_texts)]


def check_cells(rules: Sequence[Rule], cell_texts: Sequence[str]) -> None:
    """Refuse a bad --cell before anything loads: each is validated against the `*` rule's
    compiler and version (the first rule of a cflags file)."""
    if not rules:
        raise BatchError("the cflags file holds no rule")
    cells_for(rules[0], cell_texts)


def _cell_file(index: int) -> str:
    """committed.c, then cell-1.c, cell-2.c ...: flag text never becomes a path."""
    return f"{COMMITTED_CELL}.c" if index == 0 else f"cell-{index}.c"


def write_cell_jobs(
    out_dir: Path, text: str, row_code: bytes, va: int, cells: Sequence[tuple[str, Rule]]
) -> list[Job]:
    """One source per cell under `out_dir` (padded when needs_pad holds for its flags) and the
    Job that compiles it to the object beside it."""
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for index, (_name, rule) in enumerate(cells):
        src = out_dir / _cell_file(index)
        body = pad_source(text) if needs_pad(row_code, va, rule.flags) else text
        write_atomic(src, body.encode("ascii"))
        jobs.append(Job(src, src.with_suffix(compiler.OBJ_SUFFIX), rule))
    return jobs


def judged_record(exe: ExeInputs, start: int, cell: str, compiled: Compiled) -> dict[str, Any]:
    """cell_record of one compiled cell, judged when its compile succeeded."""
    row = row_at(exe, start)
    verdict = judge(exe, compiled.job.obj, start) if compiled.ok else unjudged(row.end - row.start)
    return cell_record(exe.stem, start, cell, compiled.job.rule, compiled, verdict)


# ---- a directory of converter outputs ----

_SOURCE_NAME = re.compile(r"f_([0-9a-f]{8})\.c")  # lower hex, as the spike converter writes
_SOURCE_GLOB = "*/f_*.c"


def batch_sources(root_dir: Path) -> list[tuple[str, int, Path]]:
    """(exe dir name, address, path) for every <root_dir>/<exe>/f_<addr8hex>.c, sorted; a
    malformed f_*.c name is a BatchError naming the file."""
    found = []
    for path in Path(root_dir).glob(_SOURCE_GLOB):
        match = _SOURCE_NAME.fullmatch(path.name)
        if match is None:
            raise BatchError(f"{path}: expected f_<8 lower-case hex digits>.c")
        found.append((path.parent.name, int(match.group(1), 16), path))
    return sorted(found)
