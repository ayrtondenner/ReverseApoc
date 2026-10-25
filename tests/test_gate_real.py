"""`gate --all` on the real files (AGT-06, D-24): the zero-regression gate passes on the committed
tree and refuses a match reverted to INCLUDE_ASM.

These tests need orig/<EXE>, the owner's Watcom tree (REVERSEAPOC_WATCOM_DIR or
third_party/watcom), a compiler runner and objdiff-cli, so they run in the main checkout's
container (plan 06-16). gate_all compiles every matched unit, lands it once per EXE and
cross-checks the landed starts against the real config/<exe>/status.csv; it writes nothing. The
compiler writes only inside the repository, so the build dirs and the reverted copy of src/
live under build/test-gate-real/. The tests assert on names, addresses, exit codes and SHA-1s
only, never on game bytes.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from conftest import (
    ORIG_DIR,
    REPO_ROOT,
    WATCOM_DIR,
    requires_objdiff,
    requires_runner,
    requires_version,
)
from reverseapoc import check
from reverseapoc.check import EXIT_MISMATCH, EXIT_OK
from reverseapoc.gate import GateRoots, gate_all
from reverseapoc.targets import load_manifest

MANIFEST = REPO_ROOT / "config" / "targets.toml"
CONFIG = REPO_ROOT / "config"
BUILD_ROOT = REPO_ROOT / "build" / "test-gate-real"  # the compiler writes only in the repo
EXES = ("UFO2P.EXE", "TACP.EXE")
VERSION = "10.6"  # config/cflags.txt's `*` rule
# The UFO2P Phase 5 match the reverted copy takes back to its INCLUDE_ASM marker.
REVERT_STEM, REVERT_UNIT = "ufo2p", "u_000a34f0"
REVERT_FUNC, REVERT_START = "func_000A3980", 0x000A3980
REVERT_HEAD = f"int {REVERT_FUNC}(void)\n{{"


@pytest.fixture
def work_dir(request) -> Path:
    """A fresh build/test-gate-real/<test name> directory (removed and recreated)."""
    path = BUILD_ROOT / re.sub(r"[^A-Za-z0-9._-]", "_", request.node.name)
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def _requires_real_files() -> None:
    for name in EXES:
        if not (ORIG_DIR / name).is_file():
            pytest.skip(f"orig/{name} not present (run uv run reverseapoc ingest)")
    requires_version(VERSION)
    requires_runner()
    requires_objdiff()


def _roots(src_root: Path, build_dir: Path) -> GateRoots:
    return GateRoots(orig_dir=ORIG_DIR, manifest=MANIFEST, config_root=CONFIG, src_root=src_root,
                     build_dir=build_dir, watcom_dir=WATCOM_DIR)  # fmt: skip


def _expected_sha1() -> dict[str, str]:
    return {t.name: t.sha1 for t in load_manifest(MANIFEST) if t.name in EXES}


def test_gate_all_passes_on_the_committed_tree(work_dir):
    """Every matched function is still objdiff 100.0 with reloc and bytes ok, the landed starts
    equal status.csv's matched starts, and both EXEs land SHA-1 identical."""
    _requires_real_files()
    result = gate_all(roots=_roots(check.DEFAULT_SRC, work_dir / "build"))
    assert result.problems == ()
    assert result.exit_code == EXIT_OK
    assert {s["exe"]: s["sha1"] for s in result.splices} == _expected_sha1()
    assert all(s["ok"] and s["landed"] >= 1 for s in result.splices)


def test_gate_all_refuses_a_reverted_match(work_dir, monkeypatch):
    """A copy of src/ where func_000A3980's definition is back to INCLUDE_ASM, with the real
    status.csv: gate --all exits 1 and the cross-check names the start that no longer lands."""
    _requires_real_files()
    src = work_dir / "src"
    shutil.copytree(check.DEFAULT_SRC, src)
    unit = src / REVERT_STEM / f"{REVERT_UNIT}.c"
    text = unit.read_bytes().decode("utf-8")
    assert text.count(REVERT_HEAD) == 1
    head = text.index(REVERT_HEAD)
    unit.write_bytes((text[:head] + f"INCLUDE_ASM({REVERT_FUNC});\n").encode("utf-8"))
    # gate compiles only the committed src tree (_committed_src reads check.DEFAULT_SRC at call
    # time): stand the reverted copy in for it.
    monkeypatch.setattr(check, "DEFAULT_SRC", src)
    result = gate_all(roots=_roots(src, work_dir / "build"))
    assert result.exit_code == EXIT_MISMATCH
    start = f"{REVERT_FUNC} at 0x{REVERT_START:08X}"
    not_landed = [p for p in result.problems
                  if p.startswith(f"UFO2P.EXE: {start} ") and "not landed" in p]  # fmt: skip
    assert len(not_landed) == 1, result.problems
    assert not [p for p in result.problems if p.startswith("TACP.EXE")]
