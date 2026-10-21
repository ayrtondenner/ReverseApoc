"""The clean-room probe compiled with real Watcom compilers, and the idioms each version and flag
set emits (CID-03, D-10).

The same tests run natively on the Windows host and under wibo inside `docker compose run`. They
are skipped only without a compiler runner or an installed tree (conftest.requires_runner and
requires_version), or when a version's hash gate refuses its tree (the skip reason then starts
`Watcom <version>:`). Objects, logs and gate stamps live under build/test-probe/<test>/
(gitignored). Assertions compare idiom counts, library names and SHA-1s, never bytes.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from conftest import REPO_ROOT, WATCOM_DIR, requires_runner, requires_version
from reverseapoc.cflags import Rule
from reverseapoc.compiler import CompilerError, check_gate, compile_rule
from reverseapoc.probe import PROBE_DIR, count_idioms, object_code

PROBE_ROOT = REPO_ROOT / "build" / "test-probe"


@pytest.fixture
def cc_root(request) -> Path:
    """A fresh build/test-probe/<test name> directory for this test (removed and recreated)."""
    path = PROBE_ROOT / re.sub(r"[^A-Za-z0-9._-]", "_", request.node.name)
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def _require_compiler(version: str, root_dir: Path) -> None:
    """Skip unless `version` can run here: a runner, its tree, and a gate that accepts it."""
    requires_runner()
    requires_version(version)
    try:
        check_gate("wcc386", version, watcom_dir=WATCOM_DIR, stamps=root_dir / "stamps")
    except CompilerError as exc:
        pytest.skip(f"Watcom {version}: gate refused ({exc})")


def _probe_counts(root_dir: Path, version: str, flags: tuple[str, ...]) -> dict[str, int]:
    """Compile probe/cg_basic.c with one rule and sum the idiom counts over its CODE segments."""
    obj = root_dir / "_".join(flag.lstrip("-") for flag in flags) / "cg_basic.obj"
    result = compile_rule(
        Rule("*", "wcc386", version, flags, 0),
        PROBE_DIR / "cg_basic.c",
        obj,
        root=REPO_ROOT,
        watcom_dir=WATCOM_DIR,
        log=root_dir / "cc.log",
        stamps=root_dir / "stamps",
    )
    assert result.ok, result.output
    totals: dict[str, int] = {}
    for code, mask in object_code(obj.read_bytes()):
        for name, count in count_idioms(code, mask=mask).items():
            totals[name] = totals.get(name, 0) + count
    return totals


def test_byte_compare_calibration(cc_root):
    _require_compiler("10.6", cc_root)
    five = _probe_counts(cc_root, "10.6", ("-5r", "-s"))
    assert five["setcc_and"] >= 1
    assert five["setcc_movzx"] == 0
    three = _probe_counts(cc_root, "10.6", ("-3r", "-s"))
    assert three["setcc_movzx"] >= 1
    assert three["setcc_and"] == 0
