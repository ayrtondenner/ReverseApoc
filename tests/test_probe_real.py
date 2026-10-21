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
from reverseapoc.probe import FLAG_SETS, PROBE_DIR, calibrate, count_idioms, object_code

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


# ---- Task 2: the calibration matrix ------------------------------------------------------------

CALIBRATED = ("10.6", "11.0")  # 10.5 joins once plan 04-11 reinstalls its BINW compiler
S3, S4, S5 = ("-3r", "-s"), ("-4r", "-s"), ("-5r", "-s")

# One row per 04-RESEARCH Pattern 6 claim: (version, flags, {field: condition}). A field is an
# idiom name or "chk_calls"; a condition is ">=1" or "==0".
ROWS = [
    pytest.param("10.6", S3, {"setcc_movzx": ">=1", "setcc_and": "==0"}, id="10.6-3r-movzx"),
    pytest.param(
        "10.6",
        S5,
        {"setcc_and": ">=1", "setcc_movzx": "==0", "movsd_unrolled": ">=1"},
        id="10.6-5r-and-unrolled",
    ),
    pytest.param("10.6", S5, {"rep_movsd_small": "==0"}, id="10.6-5r-no-small-rep"),
    pytest.param("10.6", S4, {"rep_movsd_small": ">=1"}, id="10.6-4r-small-rep"),
    pytest.param("11.0", S4, {"setcc_and": ">=1"}, id="11.0-4r-and"),
    pytest.param("11.0", S5, {"setcc_and": "==0", "setcc_movzx": "==0"}, id="11.0-5r-branch"),
    pytest.param("10.6", S5, {"loop_rotated": ">=1", "loop_top_tested": "==0"}, id="10.6-rotated"),
    pytest.param(
        "11.0", S5, {"loop_rotated": "==0", "loop_top_tested": ">=1"}, id="11.0-top-tested"
    ),
    pytest.param("10.6", ("-5r",), {"chk_calls": ">=1"}, id="10.6-no-s-chk"),
    pytest.param("11.0", ("-5r",), {"chk_calls": ">=1"}, id="11.0-no-s-chk"),
    pytest.param("10.6", S5, {"chk_calls": "==0"}, id="10.6-s-no-chk"),
    pytest.param("11.0", S5, {"chk_calls": "==0"}, id="11.0-s-no-chk"),
]

# (version, flags, default libraries that must be requested), compared case-insensitively.
LIBRARY_ROWS = [
    pytest.param(version, flags, libs, id=f"{version}-{tag}")
    for version in CALIBRATED
    for flags, libs, tag in (
        (S5, ("emu387",), "fpi-emu387"),
        (("-5r", "-s", "-fpi87"), ("noemu387",), "fpi87-noemu387"),
        (("-5s", "-s"), ("clib3s", "math387s"), "5s-3s-libraries"),
    )
]


@pytest.fixture(scope="module")
def calibration():
    """calibrate() over 10.6 and 11.0 once per module, into build/test-probe/calibration."""
    root_dir = PROBE_ROOT / "calibration"
    shutil.rmtree(root_dir, ignore_errors=True)
    root_dir.mkdir(parents=True)
    for version in CALIBRATED:
        _require_compiler(version, root_dir)
    return calibrate(
        versions=CALIBRATED,
        out_dir=root_dir,
        root=REPO_ROOT,
        watcom_dir=WATCOM_DIR,
        log=root_dir / "cc.log",
        stamps=root_dir / "stamps",
    )


def _value(cell, field: str) -> int:
    return cell.chk_calls if field == "chk_calls" else cell.counts[field]


def _holds(value: int, condition: str) -> bool:
    return value >= 1 if condition == ">=1" else value == 0


@pytest.mark.parametrize(("version", "flags", "expected"), ROWS)
def test_calibration_rows(calibration, version, flags, expected):
    cell = calibration.cell(version, flags)
    measured = {field: _value(cell, field) for field in expected}
    failed = {f: v for f, v in measured.items() if not _holds(v, expected[f])}
    assert not failed, f"{version} {' '.join(flags)}: expected {expected}, measured {measured}"


@pytest.mark.parametrize(("version", "flags", "libs"), LIBRARY_ROWS)
def test_calibration_libraries(calibration, version, flags, libs):
    requested = {name.lower() for name in calibration.cell(version, flags).default_libraries}
    assert set(libs) <= requested, requested


def test_calibration_covers_every_flag_set(calibration):
    assert [(c.version, c.flags) for c in calibration.cells] == [
        (version, flags) for version in CALIBRATED for flags in FLAG_SETS
    ]
    assert calibration.skipped == ()
    print()
    print(calibration.format())


def test_calibration_with_10_5():
    root_dir = PROBE_ROOT / "calibration-10.5"
    shutil.rmtree(root_dir, ignore_errors=True)
    root_dir.mkdir(parents=True)
    _require_compiler("10.5", root_dir)
    cal = calibrate(
        out_dir=root_dir,
        root=REPO_ROOT,
        watcom_dir=WATCOM_DIR,
        log=root_dir / "cc.log",
        stamps=root_dir / "stamps",
    )
    assert [version for version, _ in cal.skipped] == []
    tied = set()
    for flags, versions in cal.ties():
        hashes = {cal.cell(version, flags).normalized_sha1 for version in versions}
        assert len(hashes) == 1
        tied |= {(version, flags) for version in versions}
    # every pair of equal hashes under the same flags is reported in a tie
    for a in cal.cells:
        for b in cal.cells:
            same = a.flags == b.flags and a.normalized_sha1 == b.normalized_sha1
            if same and a.version != b.version:
                assert (a.version, a.flags) in tied
    print()
    print(cal.format())
