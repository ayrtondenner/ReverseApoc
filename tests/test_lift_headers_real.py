"""The headers a draft includes against the real Watcom 10.6 (261107-qkd).

These tests skip without capstone, a compiler runner or an installed Watcom 10.6 the gate accepts.
A draft that includes string.h or math.h and calls rows named memset and floor compiles with the
headers' prototypes alone, every name lift.HEADER_DECLARES lists is one its header declares with
the parameter list the table gives it, and every HEADER_ARGUMENT_ROWS draft passes the header's
count and argument types (no E1151, no E1071, 261109-gzt).
They write only under build/test-lift-headers/ (the compiler refuses objects outside the
repository). No game byte is read here.
"""

from __future__ import annotations

import re
import shutil

import pytest

from conftest import REPO_ROOT, WATCOM_DIR, requires_capstone, requires_runner, requires_version
from reverseapoc import batch, lift
from reverseapoc.compiler import CompilerError, check_gate
from test_lift import (
    HEADER_ARGUMENT_ROWS,
    HEADER_CALLERS,
    VA,
    clear_caches,
    header_argument_exe,
    header_callee_exe,
)
from test_lift_probe_real import BOTH, VERSION, _rule

BUILD_ROOT = REPO_ROOT / "build" / "test-lift-headers"


def _gate() -> None:
    requires_capstone()
    requires_runner()
    requires_version(VERSION)
    try:
        check_gate("wcc386", VERSION, watcom_dir=WATCOM_DIR)
    except CompilerError as exc:
        pytest.skip(f"Watcom {VERSION}: gate refused ({exc})")


@pytest.mark.parametrize("header", HEADER_CALLERS)  # the headers the lifter includes
def test_every_name_in_the_table_is_one_the_header_declares(header):
    path = requires_version(VERSION) / "H" / header
    text = path.read_text(encoding="latin-1")
    missing = [n for n in lift.HEADER_DECLARES[header] if not re.search(rf"\b{n}\s*\(", text)]
    assert not missing, f"{path}: {missing}"


def _parameter_types(params: str) -> tuple[str, ...]:
    """`( void *__s, int __c )`'s inside as ("void *", "int"): names dropped, whitespace one."""
    return tuple(" ".join(re.sub(r"__\w+\s*$", "", p).split()) for p in params.split(","))


@pytest.mark.parametrize("header", HEADER_CALLERS)
def test_every_parameter_list_in_the_table_is_the_headers(header):
    path = requires_version(VERSION) / "H" / header
    text = path.read_text(encoding="latin-1")
    wrong = {}
    for name, params in lift.HEADER_DECLARES[header].items():
        m = re.search(rf"^extern\b[^(\n]*\b{name}\s*\(([^)]*)\)\s*;", text, re.M)
        spelled = _parameter_types(m[1]) if m else None
        if spelled != params:
            wrong[name] = (params, spelled)
    assert not wrong, f"{path}: table, header: {wrong}"


@pytest.mark.parametrize("header", HEADER_CALLERS)
def test_a_draft_calling_what_its_header_declares_compiles(header, monkeypatch):
    _gate()
    case_dir = BUILD_ROOT / header.replace(".", "_")
    shutil.rmtree(case_dir, ignore_errors=True)
    monkeypatch.setattr(lift, "CACHE_DIR", case_dir / "lift")
    clear_caches()
    try:
        exe = header_callee_exe(header)
        text = lift.lift_row(exe, VA)
    finally:
        clear_caches()
    code = exe.flat[exe.rows[0].start : exe.rows[0].end]
    jobs = batch.write_cell_jobs(case_dir, text, code, VA, [(c, _rule(c)) for c in BOTH])
    for one in batch.compile_batch(jobs, len(jobs), watcom_dir=WATCOM_DIR).compiled:
        assert "E1062" not in one.output and "E1071" not in one.output, one.output
        assert one.ok, f"{one.output}\n{text}"


@pytest.mark.parametrize("name", HEADER_ARGUMENT_ROWS)
def test_a_draft_passing_header_arguments_compiles(name, monkeypatch):
    _gate()
    case_dir = BUILD_ROOT / name
    shutil.rmtree(case_dir, ignore_errors=True)
    monkeypatch.setattr(lift, "CACHE_DIR", case_dir / "lift")
    clear_caches()
    try:
        exe = header_argument_exe(name)
        text = lift.lift_row(exe, VA)
    finally:
        clear_caches()
    code = exe.flat[exe.rows[0].start : exe.rows[0].end]
    jobs = batch.write_cell_jobs(case_dir, text, code, VA, [(c, _rule(c)) for c in BOTH])
    for one in batch.compile_batch(jobs, len(jobs), watcom_dir=WATCOM_DIR).compiled:
        assert "E1151" not in one.output and "E1071" not in one.output, f"{one.output}\n{text}"
        assert one.ok, f"{one.output}\n{text}"
