"""The stub convention compiled for real (SPL-04, D-12): `INCLUDE_ASM(func_XXXXXXXX);` from
include/common.h emits no bytes, no EXTDEF and no public under Watcom 10.6.

Sources are unit-shaped files compiled by `compile_source` under config/cflags.txt's `*` rule,
so `#include "common.h"` has to resolve through the wrapper's own `-i=` list. The tests run
natively on the Windows host and under wibo in the container, and are skipped only without a
compiler runner, without the 10.6 tree, or when the hash gate refuses that tree. Sources, objects,
logs and gate stamps live under build/test-stub/<test>/ (gitignored). A marker's emptiness is
measured against a control file holding the same function and nothing else, so no compiled byte
is written here as a literal.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

import pytest

from conftest import REPO_ROOT, WATCOM_DIR, requires_runner, requires_version
from reverseapoc import omf
from reverseapoc.compiler import CompilerError, check_gate, compile_source

STUB_ROOT = REPO_ROOT / "build" / "test-stub"
VERSION = "10.6"  # the `*` rule's version in config/cflags.txt
# The extern a marker would leave, `INCLUDE_ASM_<placeholder>` (include/common.h) with the
# Watcom decoration on either side, matched whole: a substring test would also count any name
# that merely contains the text (05-REVIEW row 4).
MARKER_EXTERN = re.compile(r"_?INCLUDE_ASM_func_[0-9A-F]{8}_?")

# C89: declarations first, block comments only.
DEFINED = """\
int func_00012345(void)
{
    return 0;
}
"""

UNIT = (
    """\
/* a unit-shaped file: three stubs and one defined function (D-12) */
#include "common.h"

INCLUDE_ASM(func_00012000);
INCLUDE_ASM(func_00012100);

"""
    + DEFINED
    + """
INCLUDE_ASM(func_00012400);
"""
)


@pytest.fixture
def stub_root(request) -> Path:
    """A fresh build/test-stub/<test name> directory, after the 10.6 compiler is known to run."""
    requires_runner()
    requires_version(VERSION)
    path = STUB_ROOT / re.sub(r"[^A-Za-z0-9._-]", "_", request.node.name)
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    try:
        check_gate("wcc386", VERSION, watcom_dir=WATCOM_DIR, stamps=path / "stamps")
    except CompilerError as exc:
        pytest.skip(f"Watcom {VERSION}: gate refused ({exc})")
    return path


def _compile(root_dir: Path, name: str, text: str) -> omf.Module:
    """Write `text` to root_dir/name, compile it with its cflags rule and read the object."""
    src = root_dir / name
    src.write_text(text, encoding="ascii")
    result = compile_source(
        src,
        src.with_suffix(".obj"),
        root=REPO_ROOT,
        watcom_dir=WATCOM_DIR,
        log=root_dir / "cc.log",
        stamps=root_dir / "stamps",
    )
    assert result.ok, result.output
    assert result.rule.spec == f"wcc386@{VERSION}"
    return omf.read_object(result.obj.read_bytes())


def _text(module: omf.Module) -> bytes:
    """The bytes of the module's _TEXT segment; b"" when it has none."""
    return next((seg.data for seg in module.segments if seg.name == "_TEXT"), b"")


def _publics(module: omf.Module) -> tuple[str, ...]:
    return tuple(public.name for public in module.publics)


def _marker_externs(module: omf.Module) -> list[str]:
    return [name for name in module.externs if MARKER_EXTERN.fullmatch(name)]


def _text_sha1(module: omf.Module) -> str:
    """SHA-1 of the _TEXT bytes, so a failing comparison prints hashes, never bytes (T-04-17)."""
    return hashlib.sha1(_text(module)).hexdigest()


def test_markers_emit_nothing(stub_root):
    unit = _compile(stub_root, "unit.c", UNIT)
    control = _compile(stub_root, "control.c", DEFINED)
    assert _publics(unit) == ("func_00012345_",)
    assert _marker_externs(unit) == []
    assert unit.externs == control.externs
    assert len(_text(control)) > 0  # the function compiled to something
    assert _text_sha1(unit) == _text_sha1(control)


MARKERS_ONLY = """\
/* a unit whose functions are all unmatched: markers only (D-12) */
#include "common.h"

INCLUDE_ASM(func_00012000);
INCLUDE_ASM(func_00012100);
"""

NEXT_TO = """\
/* a stub directly before a defined function */
#include "common.h"

INCLUDE_ASM(func_00012000);
int func_00012010(void)
{
    return 0;
}
"""


def test_markers_only_file(stub_root):
    module = _compile(stub_root, "markers.c", MARKERS_ONLY)
    assert module.publics == ()
    assert _marker_externs(module) == []
    assert module.externs == ()
    assert len(_text(module)) == 0


def test_marker_next_to_a_defined_function(stub_root):
    module = _compile(stub_root, "next.c", NEXT_TO)
    assert _publics(module) == ("func_00012010_",)
    assert _marker_externs(module) == []


REFERENCED = """/* a marker whose extern is referenced, so the compiler must emit it */
#include "common.h"

INCLUDE_ASM(func_00012000);
int func_00012010(void)
{
    return INCLUDE_ASM_func_00012000;
}
"""


def test_marker_extern_pattern_sees_a_referenced_marker(stub_root):
    """The marker pattern is right: a referenced marker's extern, as Watcom spells it, matches,
    so `_marker_externs(...) == []` above can fail."""
    module = _compile(stub_root, "referenced.c", REFERENCED)
    assert len(_marker_externs(module)) == 1, module.externs
