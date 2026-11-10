"""Name provenance markers are comments only (07.2-07; D-14, D-15, D-20).

A real compile of one matched unit per EXE, as committed and with a well-formed RL07 marker
beside every file-scope definition and extern declaration, through `reverseapoc cc`'s wrapper with
that unit's pinned config/cflags.txt rule: the two objects hash the same under
omf.normalized_object_sha1. Skipped, saying why, without a compiler runner or Watcom 10.6
(conftest.requires_runner and requires_version). Both copies and both objects live in pytest's
tmp_path, each under its own compile root with a copy of include/, so the source path the
compiler records is the same; src/ is only read. No game bytes: the test compares two hashes it
computes.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from conftest import REPO_ROOT, WATCOM_DIR, requires_runner, requires_version
from reverseapoc import omf, readlint, unitdefs
from reverseapoc.cflags import load_cflags, select_rule
from reverseapoc.compiler import CompilerError, check_gate, compile_rule

UNITS = ("src/ufo2p/u_000a34f0.c", "src/tacp/u_00054f20.c")  # one matched unit per EXE
_PLACEHOLDER_ADDRESS = re.compile(r"(?:func|D)_([0-9A-F]{8})")


def _require_compiler(version: str, stamps: Path) -> None:
    requires_runner()
    requires_version(version)
    try:
        check_gate("wcc386", version, watcom_dir=WATCOM_DIR, stamps=stamps)
    except CompilerError as exc:
        pytest.skip(f"Watcom {version}: gate refused ({exc})")


def _marker(line: str) -> str:
    """A well-formed marker naming the address of the line's first placeholder name."""
    found = _PLACEHOLDER_ADDRESS.search(line)
    address = found.group(1) if found else "00000000"
    return f"/* src: GUESS 0x{address} (confidence: low) */"


def _marked(text: str) -> str:
    """`text` with a marker at the end of each line that defines a file-scope function (its
    name and `(`, the next line `{`) or opens an `extern` declaration."""
    cfg = unitdefs.load_configure(REPO_ROOT / unitdefs.CONFIGURE)
    names = unitdefs.file_scope_definitions(cfg.code_text(text))
    lines = text.split("\n")
    for k, line in enumerate(lines[:-1]):
        defines = any(f"{name}(" in line for name in names) and lines[k + 1] == "{"
        if defines or line.startswith("extern "):
            lines[k] = f"{line} {_marker(line)}"
    return "\n".join(lines)


def _compile(root: Path, rel: str, text: str) -> str:
    """Compile `text` as <root>/<rel> with the committed unit's own cflags rule; its object's
    normalized SHA-1."""
    shutil.copytree(REPO_ROOT / "include", root / "include")
    src = root / rel
    src.parent.mkdir(parents=True)
    src.write_bytes(text.encode("utf-8"))
    rule = select_rule(load_cflags(REPO_ROOT / "config" / "cflags.txt"), rel)
    result = compile_rule(rule, src, src.with_suffix(".obj"), root=root, watcom_dir=WATCOM_DIR,
                          log=root / "cc.log", stamps=root / "stamps")  # fmt: skip
    assert result.ok, result.output
    return omf.normalized_object_sha1(result.obj.read_bytes())


@pytest.mark.parametrize("rel", UNITS)
def test_markers_leave_the_object_identical(tmp_path, rel):
    _require_compiler("10.6", tmp_path / "stamps")
    committed = (REPO_ROOT / rel).read_bytes().decode("utf-8")
    marked = _marked(committed)
    assert marked.count("/* src: ") >= 2, "the copy holds no markers to prove anything with"
    plain_sha1 = _compile(tmp_path / "plain", rel, committed)
    marked_sha1 = _compile(tmp_path / "marked", rel, marked)
    assert marked_sha1 == plain_sha1
    unit = tmp_path / "marked" / rel
    result = readlint.run_readlint([unit], src_root=tmp_path / "marked" / "src",
                                   config_root=REPO_ROOT / "config")  # fmt: skip
    assert result.files_checked, result.skipped
    assert [v for v in result.violations if v.rule == "RL07"] == []
    assert (REPO_ROOT / rel).read_bytes().decode("utf-8") == committed  # src/ untouched
