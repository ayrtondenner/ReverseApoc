"""Real compiles through `reverseapoc cc`'s wrapper (CID-01, CID-02).

The same tests run natively on the Windows host and under wibo inside `docker compose run`. They
are skipped only without a compiler runner or an installed tree (conftest.requires_runner and
requires_version), or when a version's hash gate refuses its tree (the skip reason then starts
`Watcom <version>:`). Sources, objects, logs and gate stamps live under build/test-cc/<test>/
(gitignored); nothing is ever written under third_party/ or orig/. Assertions compare SHA-1s,
public names and short x86 encodings written here as literals, never bytes taken from a file.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from conftest import REPO_ROOT, WATCOM_DIR, requires_runner, requires_version
from reverseapoc.cflags import Rule
from reverseapoc.compiler import CompilerError, CompileResult, check_gate, compile_rule, gate_paths
from reverseapoc.watcom import load_watcom_manifest

CC_ROOT = REPO_ROOT / "build" / "test-cc"
VERSIONS = ("10.5", "10.6", "11.0")
RUNNABLE = ("10.6", "11.0")  # 10.5 joins once plans 04-06 and 04-11 fix its BINW compiler
FLAGS = ("-5r", "-s")

# C89: declarations first, block comments only.
BYTE_COMPARE = """\
/* a byte compare: -5r gives setcc al; and eax,0FFh and -3r gives setcc al; movzx eax,al */
int pr_eq5(unsigned char c)
{
    return c == 5;
}
"""


@pytest.fixture
def cc_root(request) -> Path:
    """A fresh build/test-cc/<test name> directory for this test (removed and recreated)."""
    path = CC_ROOT / re.sub(r"[^A-Za-z0-9._-]", "_", request.node.name)
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


def _compile(
    root_dir: Path, version: str, flags: tuple[str, ...], name: str, text: str
) -> CompileResult:
    """Write `text` to root_dir/name and compile it into root_dir/<stem>.obj with one rule."""
    src = root_dir / name
    src.write_text(text, encoding="ascii")
    return compile_rule(
        Rule("*", "wcc386", version, flags, 0),
        src,
        src.with_suffix(".obj"),
        root=REPO_ROOT,
        watcom_dir=WATCOM_DIR,
        log=root_dir / "cc.log",
        stamps=root_dir / "stamps",
    )


def _gated_sha1s(version: str) -> tuple[tuple[str, str], ...]:
    """(path, sha1) of the gated binaries, in manifest key-file order, from config/watcom.toml."""
    wanted = gate_paths("wcc386", version)
    media = load_watcom_manifest()[version]
    return tuple((kf.path, kf.sha1) for kf in media.key_files if kf.path in wanted)


def _last_log_line(root_dir: Path) -> str:
    return (root_dir / "cc.log").read_text(encoding="utf-8").splitlines()[-1]


# ---- Task 1: one real compile per version ------------------------------------------------------


@pytest.mark.parametrize("version", VERSIONS)
def test_compile_real(cc_root, version):
    _require_compiler(version, cc_root)
    result = _compile(cc_root, version, FLAGS, "eq.c", BYTE_COMPARE)
    assert result.ok, result.output
    assert result.obj.is_file()
    assert f"Version {version}" in result.gate.banner
    expected = _gated_sha1s(version)
    assert len(expected) == len(gate_paths("wcc386", version))
    assert result.gate.files == expected
    assert result.object_sha1 is not None and result.normalized_sha1 is not None
    line = _last_log_line(cc_root)
    assert result.gate.banner in line
    for path, sha1 in expected:
        assert f"{path}={sha1}" in line
    assert f"sha1 {result.object_sha1}  normalized {result.normalized_sha1}" in line


@pytest.mark.parametrize("version", RUNNABLE)
def test_normalized_hash_is_stable(cc_root, version):
    _require_compiler(version, cc_root)
    first = _compile(cc_root, version, FLAGS, "eq.c", BYTE_COMPARE)
    second = _compile(cc_root, version, FLAGS, "eq.c", BYTE_COMPARE)
    assert first.ok and second.ok, first.output + second.output
    assert first.normalized_sha1 == second.normalized_sha1
