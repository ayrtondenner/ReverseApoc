"""The trailing-filler rule (plan 07-48, owner ruling: option A) on the real row that started it:
tacp func_0006BEE0, row [0x0006BEE0, 0x0006BF30) in unit u_0006bcb0.

The C is ours, never game bytes: tests/fixtures/filler/tacp/f_0006bee0.c is a byte-identical copy
of the spike 011 b064 agent's file (build/spike-011/agents/b064/f_0006bee0.c), never edited. Our
object ends at the function's last instruction; the original row goes on with the linker's
alignment filler up to its 16-byte aligned end. tests/fixtures/filler/ is also a valid
`reverseapoc batch` DIR (`<exe>/f_<addr8hex>.c`).

- The judge test (host and container): the fixture compiled under its unit's committed cflags
  rule judges exact, shorter than its row, and the relocation verdict keeps 1-15 filler bytes.
- The view test (container: objdiff-cli runs only there): the fixture spliced into a scaffold of
  its unit inside a D-24 view, checked by `check.check_unit` with the view's roots. It prints the
  objdiff percent (`OBJDIFF func_0006BEE0 <percent>`) and passes only when objdiff is 100, the
  relocation check and the byte compare pass with the filler kept, and both whole-EXE SHA-1s
  equal the manifest.

Asserts on addresses, counts, percents, booleans and SHA-1 checks only. Writes only under
build/test-filler/ and build/driver/test-view/. Skips through the existing helpers only (R-A,
F40).
"""

from __future__ import annotations

import secrets
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from conftest import (
    ORIG_DIR,
    REPO_ROOT,
    WATCOM_DIR,
    requires_capstone,
    requires_objdiff,
    requires_runner,
    requires_version,
)
from reverseapoc import batch, check
from reverseapoc.cflags import load_cflags
from reverseapoc.compiler import CompilerError, check_gate
from reverseapoc.functions import read_functions_csv, read_units_csv
from reverseapoc.targets import load_manifest
from reverseapoc.units import scaffold_unit

EXE, STEM, UNIT = "TACP.EXE", "tacp", "u_0006bcb0"
START, END = 0x0006BEE0, 0x0006BF30  # the row: 80 bytes, its end 16-byte aligned
NAME = "func_0006BEE0"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "filler" / STEM / f"f_{START:08x}.c"
MARKER = f"INCLUDE_ASM({NAME});\n"
CONFIG = REPO_ROOT / "config"
MANIFEST = CONFIG / "targets.toml"
BUILD_ROOT = REPO_ROOT / "build" / "test-filler"
VIEW_ROOT = REPO_ROOT / "build" / "driver" / "test-view"
MAX_FILLER = 15  # relocs._MAX_FILLER: alignment to 16 pads at most 15 bytes


def _require_orig() -> None:
    if not (ORIG_DIR / EXE).is_file():
        pytest.skip(f"orig/{EXE} not present (run uv run reverseapoc ingest or set "
                    "REVERSEAPOC_ORIG)")  # fmt: skip


def _committed_rule():
    rules = load_cflags()
    rule = batch.committed_rule(rules, STEM, UNIT)
    requires_version(rule.version)
    try:
        check_gate("wcc386", rule.version, watcom_dir=WATCOM_DIR)
    except CompilerError as exc:
        pytest.skip(f"Watcom {rule.version}: gate refused ({exc})")
    return rule


def test_real_filler_judge_tacp_0006bee0():
    _require_orig()
    requires_capstone()
    requires_runner()
    rule = _committed_rule()
    exe = batch.load_exe_inputs(EXE, orig_dir=ORIG_DIR)
    row = batch.row_at(exe, START)
    assert (row.end, row.unit, row.name) == (END, UNIT, NAME)
    text = batch.read_ascii(FIXTURE)
    assert batch.refusal(text) is None
    out = BUILD_ROOT / "judge"
    shutil.rmtree(out, ignore_errors=True)
    (job,) = batch.write_cell_jobs(out, text, exe.flat[row.start : row.end], row.start,
                                   [("committed", rule)])  # fmt: skip
    (compiled,) = batch.compile_batch([job], 1, watcom_dir=WATCOM_DIR).compiled
    assert compiled.ok, compiled.output
    verdict = batch.judge(exe, job.obj, START)
    assert verdict.exact is True, verdict.key
    assert verdict.len_ours < verdict.len_row == END - START
    module = check.parse_module(job.obj.read_bytes(), job.obj)
    defined = [d for d in check.defined_functions(module, [row], exe.symbols)
               if d.row.start == START]  # fmt: skip
    ((d, reloc),) = check.with_relocs(module, defined, [row], exe)
    assert reloc.ok, reloc.problems
    assert reloc.filler == verdict.len_row - verdict.len_ours
    assert 0 < reloc.filler <= MAX_FILLER
    print(f"JUDGE {NAME} exact len ours/row {verdict.len_ours}/{verdict.len_row} "
          f"filler {reloc.filler}")  # fmt: skip


def _unit_text(view: Path) -> str:
    """The committed unit when one exists (it must define the function in C), else a scaffold of
    the unit with the function's INCLUDE_ASM marker replaced by the fixture."""
    committed = REPO_ROOT / "src" / STEM / f"{UNIT}.c"
    if committed.is_file():
        text = committed.read_text(encoding="ascii")
        assert MARKER not in text, f"{committed} still marks {NAME} INCLUDE_ASM"
        return text
    units = read_units_csv(view / "config" / STEM / "units.csv")
    (unit,) = [u for u in units if u.unit == UNIT]
    rows = read_functions_csv(view / "config" / STEM / "functions.csv")
    text = scaffold_unit(EXE, unit, rows)
    assert text.count(MARKER) == 1
    return text.replace(MARKER, batch.read_ascii(FIXTURE))


@pytest.fixture
def view() -> Iterator[Path]:
    """build/driver/test-view/<random hex>/view: a snapshot of src/, include/ and config/ as a
    D-24 view holds them, removed at teardown. Skips (F40: requires_runner and requires_objdiff
    first) before anything is copied."""
    requires_runner()
    requires_objdiff()
    for target in load_manifest(MANIFEST):
        if (CONFIG / check.exe_stem(target.name) / "units.csv").is_file() and not (
            ORIG_DIR / target.name
        ).is_file():
            pytest.skip(f"orig/{target.name} not present (run in the container)")
    if not (WATCOM_DIR / "10.6").is_dir():
        pytest.skip(f"{WATCOM_DIR / '10.6'} not installed (run in the container)")
    top = VIEW_ROOT / secrets.token_hex(4)
    path = top / "view"
    for tree in ("src", "include", "config"):
        shutil.copytree(REPO_ROOT / tree, path / tree)
    yield path
    shutil.rmtree(top, ignore_errors=True)


def test_real_filler_check_tacp_0006bee0(view):
    unit_file = view / "src" / STEM / f"{UNIT}.c"
    unit_file.parent.mkdir(parents=True, exist_ok=True)
    unit_file.write_bytes(_unit_text(view).encode("ascii"))
    build = view / "build"
    result = check.check_unit(
        STEM, UNIT, orig_dir=ORIG_DIR, manifest=view / "config" / "targets.toml",
        config_root=view / "config", src_root=view / "src", build_dir=build,
        watcom_dir=WATCOM_DIR, log=build / "cc.log",
    )  # fmt: skip
    (fn,) = [f for f in result.functions if f.va == START]
    print(f"OBJDIFF {NAME} {fn.objdiff_percent:g}")
    print("\n".join(fn.format()))
    assert fn.reloc.ok, fn.reloc.problems
    assert fn.bytes_ok, (fn.differing, fn.first_va)
    assert fn.filler == END - START - fn.size > 0
    splices = [s.format() for s in result.splices]
    assert result.splices and all(s.ok for s in result.splices), splices
    # objdiff decision B (48-objdiff-measure.log: 89.6552 over the full row): check_source cuts
    # the target of a filler-accepted row at our length, so objdiff compares what relocs proved.
    assert fn.ok, fn.format()
