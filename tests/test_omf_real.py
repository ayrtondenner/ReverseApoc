"""Facts of the real Watcom LIB386 libraries (survey of 2026-10-21; counts and names only).

Each test skips unless WATCOM_DIR/<version> is installed (`uv run reverseapoc install-watcom
<version>`, or REVERSEAPOC_WATCOM_DIR pointing at the installed trees, which is how a git worktree
reads them). They never run in CI: the compilers are proprietary and never committed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import WATCOM_DIR, requires_version
from reverseapoc.omf import Library, is_omf_library, read_library

VERSIONS = ["10.5", "10.6", "11.0"]
NON_OMF_COUNTS = {"10.5": 41, "10.6": 51, "11.0": 68}  # COFF `!<arch>` libraries, all under NT/
MAY_FAIL = "DOS/GRAPH.LIB"  # Watcom's graphics library: no match expected, failures tolerated


def load(path: Path) -> Library:
    return read_library(path.read_bytes(), path=path.relative_to(WATCOM_DIR).as_posix())


@pytest.mark.parametrize(("version", "count"), [("10.5", 544), ("10.6", 549), ("11.0", 970)])
def test_clib3r_module_counts(version: str, count: int):
    root = requires_version(version)
    lib = load(root / "LIB386" / "DOS" / "CLIB3R.LIB")
    assert len(lib.modules) == count
    assert lib.failures == ()


def lib_files(lib386: Path) -> list[Path]:
    return sorted(p for p in lib386.rglob("*") if p.is_file() and p.suffix.upper() == ".LIB")


def sweep(lib386: Path) -> tuple[int, list[str], list[str]]:
    """(libraries parsed, non-OMF library paths, failures outside MAY_FAIL), paths under LIB386."""
    parsed, non_omf, failures = 0, [], []
    for path in lib_files(lib386):
        rel = path.relative_to(lib386).as_posix()
        data = path.read_bytes()
        if not is_omf_library(data):
            non_omf.append(rel)
            continue
        parsed += 1
        lib = read_library(data, path=rel)
        if rel.upper() == MAY_FAIL:
            continue
        failures += [f"{rel} module {f.index} at {f.offset:#x}: {f.message}" for f in lib.failures]
    return parsed, non_omf, failures


@pytest.mark.parametrize("version", VERSIONS)
def test_lib386_sweep(version: str):
    lib386 = requires_version(version) / "LIB386"
    parsed, non_omf, failures = sweep(lib386)
    assert parsed > 0
    assert [p for p in non_omf if p.split("/")[0].upper() != "NT"] == []
    assert len(non_omf) == NON_OMF_COUNTS[version]
    assert failures == []


def test_emu387_is_easy_omf():
    lib = load(requires_version("10.6") / "LIB386" / "DOS" / "EMU387.LIB")
    assert lib.failures == ()
    assert [m.name for m in lib.modules if m.easy_omf] == ["386inite"]
    assert all(m.publics for m in lib.modules)


def test_emu387_page_size_512_in_11_0():
    lib = load(requires_version("11.0") / "LIB386" / "DOS" / "EMU387.LIB")
    assert lib.page_size == 512
    assert lib.failures == ()
    assert len(lib.modules) == 2


def test_plib_has_comdat_code():
    lib = load(requires_version("10.6") / "LIB386" / "PLIB3R.LIB")
    assert lib.failures == ()
    with_comdats = [m for m in lib.modules if m.comdats]
    assert with_comdats
    assert all(c.name for m in with_comdats for c in m.comdats)
