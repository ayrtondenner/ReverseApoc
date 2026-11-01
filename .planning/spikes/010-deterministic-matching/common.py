# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 010 shared harness: batch compile with the real wcc386 and judge like `check`.

The compile path gates each Watcom version once per batch (compiler.check_gate), then runs
compiler.build_argv commands in a thread pool: no per-call gate, no cc.log, no provenance stamp
(only `check` and ninja need those). The judge is check.py's own pieces: defined_functions,
with_relocs (the relocation check with the unit's public map and a leading jump table) and
compare_bytes. A function is exact when both pass. `score` (difflib over decoded instructions,
relocated fields masked) only ranks near-misses; it decides nothing.

Everything written goes under build/spike-010/. Records hold addresses, counts, percentages and
mnemonic shapes, never bytes.
"""

from __future__ import annotations

import csv
import dataclasses
import difflib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from reverseapoc import compiler
from reverseapoc.cflags import Rule, load_cflags, select_rule
from reverseapoc.check import (
    ExeInputs,
    compare_bytes,
    defined_functions,
    load_exe,
    parse_module,
    select_exe,
    unit_rule_path,
    with_relocs,
)
from reverseapoc.functions import KIND_DATA_IN_CODE, FunctionRow
from reverseapoc.relocs import FIELD_SIZE
from reverseapoc.targets import DEFAULT_MANIFEST, DEFAULT_ORIG, REPO_ROOT, load_manifest
from reverseapoc.watcom import DEFAULT_INSTALL
from reverseapoc.x86 import decode, is_filler

OUT = REPO_ROOT / "build" / "spike-010"
CONFIG = REPO_ROOT / "config"
EXES = {"ufo2p": "UFO2P.EXE", "tacp": "TACP.EXE"}
BUCKETS = ((0, 64, "<64"), (64, 256, "64-255"), (256, 1024, "256-1023"), (1024, 1 << 30, ">=1024"))


def bucket_of(size: int) -> str:
    return next(name for lo, hi, name in BUCKETS if lo <= size < hi)


# ---- inputs ----


_EXE_CACHE: dict[str, ExeInputs] = {}


def exe_inputs(stem: str) -> ExeInputs:
    if stem not in _EXE_CACHE:
        manifest = DEFAULT_MANIFEST
        target = select_exe(load_manifest(manifest), EXES[stem], manifest)
        _EXE_CACHE[stem] = load_exe(
            target, orig_dir=DEFAULT_ORIG, manifest=manifest, config_root=CONFIG
        )
    return _EXE_CACHE[stem]


def row_at(exe: ExeInputs, start: int) -> FunctionRow:
    return next(row for row in exe.rows if row.start == start)


def table_row(exe: ExeInputs, row: FunctionRow) -> FunctionRow | None:
    """The data-in-code row right before `row` in its unit (a jump table that leads it)."""
    before = [r for r in exe.rows if r.unit == row.unit and r.start < row.start]
    if not before:
        return None
    last = max(before, key=lambda r: r.start)
    return last if last.kind == KIND_DATA_IN_CODE and last.end <= row.start else None


_RULES: list[Rule] | None = None


def rule_for(stem: str, unit: str) -> Rule:
    global _RULES
    if _RULES is None:
        _RULES = load_cflags()
    return select_rule(_RULES, unit_rule_path(stem, unit))


# ---- batch compile ----


@dataclass
class Job:
    src: Path
    obj: Path
    rule: Rule


@dataclass
class Compiled:
    job: Job
    ok: bool
    seconds: float
    output: str


_GATES: dict[str, compiler.Gate] = {}


def gate(version: str) -> compiler.Gate:
    if version not in _GATES:
        _GATES[version] = compiler.check_gate("wcc386", version)
    return _GATES[version]


def _run(job: Job, prefix: list[str], env: dict[str, str]) -> Compiled:
    root = REPO_ROOT
    g = gate(job.rule.version)
    include = compiler._include_list(root, DEFAULT_INSTALL, job.rule.version)
    src = compiler.guest_path(job.src, root, inside=True)
    obj = compiler.guest_path(job.obj, root, inside=True)
    err = compiler.guest_path(job.obj.with_suffix(".err"), root, inside=True)
    argv = compiler.build_argv(
        g.root / compiler.COMPILER_EXE, job.rule, src, obj, err, include, prefix=prefix
    )
    job.obj.parent.mkdir(parents=True, exist_ok=True)
    job.obj.unlink(missing_ok=True)
    t0 = time.perf_counter()
    proc = subprocess.run(
        argv,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="latin-1",
        errors="replace",
        check=False,
    )
    seconds = time.perf_counter() - t0
    ok = proc.returncode == 0 and job.obj.is_file()
    return Compiled(job, ok, seconds, (proc.stdout or "") + (proc.stderr or ""))


def compile_all(jobs: Sequence[Job], workers: int) -> tuple[list[Compiled], dict[str, float]]:
    """Compile `jobs` in a pool; the gate runs once per version first and is timed apart."""
    t0 = time.perf_counter()
    for version in sorted({j.rule.version for j in jobs}):
        gate(version)
    gate_s = time.perf_counter() - t0
    # Made before the pool: Path.resolve (guest_path) on Windows races with a parallel mkdir.
    for parent in {j.obj.parent for j in jobs}:
        parent.mkdir(parents=True, exist_ok=True)
    prefix = compiler.runner_prefix(sys.platform)
    env = compiler.scrubbed_env(os.environ, sys.platform)
    t1 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        done = list(pool.map(lambda j: _run(j, prefix, env), jobs))
    return done, {"gate_s": gate_s, "compile_wall_s": time.perf_counter() - t1}


# ---- judge ----

_NUM = re.compile(r"0x[0-9a-f]+|\b\d+\b")


def _shape(mnemonic: str, op_str: str) -> str:
    return f"{mnemonic} {_NUM.sub('N', op_str)}".strip()


def _tokens(code: bytes, va: int, masked: set[int]) -> list[tuple[str, str, int]]:
    """(token, shape, va) per instruction; a token drops operand text when any of its bytes is a
    relocated field, so two references to different-but-relocated targets compare equal."""
    out = []
    for insn in decode(code, va):
        hit = any(a in masked for a in range(insn.va, insn.va + insn.size))
        shape = _shape(insn.mnemonic, insn.op_str)
        token = (
            shape if (hit or insn.branch_target is not None) else f"{insn.mnemonic} {insn.op_str}"
        )
        out.append((token, shape, insn.va))
    return out


@dataclass
class Verdict:
    exact: bool
    reloc_ok: bool
    bytes_ok: bool
    differing: int
    len_ours: int
    len_row: int
    score: float
    key: str  # the first differing instruction pair as mnemonic shapes, or a refusal reason
    exact_trim: bool = False  # exact once the row's trailing filler is cut off

    def to_json(self) -> dict:
        return dict(self.__dict__)


def judge(stem: str, obj: Path, start: int) -> Verdict:
    exe = exe_inputs(stem)
    row = row_at(exe, start)
    rows = [r for r in (table_row(exe, row), row) if r is not None]
    try:
        module = parse_module(obj.read_bytes(), obj)
    except Exception as exc:  # noqa: BLE001 - a spike records it as a failure group
        return Verdict(False, False, False, -1, 0, row.end - row.start, 0.0, f"no object: {exc}")
    defined = [d for d in defined_functions(module, rows, exe.symbols) if d.row.start == start]
    if not defined:
        return Verdict(False, False, False, -1, 0, row.end - row.start, 0.0, "not defined")
    ((d, reloc),) = [(d, r) for d, r in with_relocs(module, defined, rows, exe)]
    ours = d.ours
    cmp = compare_bytes(ours, row, exe.flat, reloc)
    masked = {va + i for va in reloc.ours | reloc.theirs for i in range(FIELD_SIZE)}
    a = _tokens(ours, row.start, masked)
    b = _tokens(exe.flat[row.start : row.end], row.start, masked)
    sm = difflib.SequenceMatcher(a=[t for t, _, _ in a], b=[t for t, _, _ in b], autojunk=False)
    score = 100.0 * sm.ratio()
    key = _first_diff(a, b, sm) if not (reloc.ok and cmp.ok) else ""
    if not key and not reloc.ok:
        key = (
            "reloc: " + _NUM.sub("N", reloc.problems[0].split(": ", 1)[-1])
            if reloc.problems
            else "reloc"
        )
    v = Verdict(
        reloc.ok and cmp.ok,
        reloc.ok,
        cmp.ok,
        cmp.differing,
        len(ours),
        row.end - row.start,
        round(score, 2),
        key,
    )
    if not v.exact and 0 < len(ours) < row.end - row.start and _filler_tail(exe, row, len(ours)):
        v.exact_trim = _trimmed_exact(module, exe, rows, row, start, len(ours))
    return v


def _filler_tail(exe: ExeInputs, row: FunctionRow, n: int) -> bool:
    """The row's bytes after our length are all Watcom filler (an alignment gap)."""
    tail = list(decode(exe.flat[row.start + n : row.end], row.start + n))
    return (
        bool(tail)
        and sum(i.size for i in tail) == row.end - row.start - n
        and all(is_filler(i) or _self_move(i.mnemonic, i.op_str) for i in tail)
    )


_SELF = re.compile(r"(\w+), (?:dword ptr )?\[\1\]|(\w+), \2")


def _self_move(mnemonic: str, op_str: str) -> bool:
    """Filler in any register: nop, mov r, r and lea r, [r]."""
    return mnemonic == "nop" or (mnemonic in ("mov", "lea") and bool(_SELF.fullmatch(op_str)))


def _trimmed_exact(module, exe, rows, row, start, n) -> bool:
    """check's verdict against the row cut at our length: exact up to the trailing filler, which
    the original linker or a 16-byte function alignment put there (a unit-boundary question)."""
    cut = dataclasses.replace(row, end=row.start + n)
    rows2 = [cut if r is row else r for r in rows]
    defined = [d for d in defined_functions(module, rows2, exe.symbols) if d.row.start == start]
    if not defined:
        return False
    ((d, reloc),) = with_relocs(module, defined, rows2, exe)
    return reloc.ok and compare_bytes(d.ours, cut, exe.flat, reloc).ok


def _first_diff(a, b, sm) -> str:
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        ours = a[i1][1] if i1 < i2 else "-"
        theirs = b[j1][1] if j1 < j2 else "-"
        return f"{ours} | {theirs}"
    return "length" if len(a) != len(b) else ""


# ---- records ----


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def append_jsonl(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def read_sample() -> list[dict]:
    with (OUT / "sample.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))
