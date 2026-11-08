"""The headers a draft includes against the real Watcom 10.6 (261107-qkd).

These tests skip without capstone, a compiler runner or an installed Watcom 10.6 the gate accepts.
A draft that includes string.h or math.h and calls rows named memset and floor compiles with the
headers' prototypes alone, and every name lift.HEADER_DECLARES lists is one its header declares.
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
from test_lift import HEADER_CALLERS, VA, clear_caches, header_callee_exe
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
