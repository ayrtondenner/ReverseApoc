"""Bring-your-own-files hygiene: game files and the compiler never reach the image, and the
container cannot write to them."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from reverseapoc.targets import load_manifest

# Every host directory that holds user-supplied, never-committed bytes.
PROTECTED_DIRS = ("orig", "third_party")


def _ignore_patterns(path: Path) -> set[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


@pytest.mark.parametrize("ext", ["exe", "EXE", "iso", "ISO", "bin", "BIN"])
def test_dockerignore_excludes_executables_and_disc_images_at_any_depth(ext):
    # A bare `*.exe` in .dockerignore only matches at the context root; `**/` matches anywhere.
    assert f"**/*.{ext}" in _ignore_patterns(REPO_ROOT / ".dockerignore")


@pytest.mark.parametrize("name", PROTECTED_DIRS)
def test_dockerignore_excludes_protected_dirs(name):
    assert f"{name}/" in _ignore_patterns(REPO_ROOT / ".dockerignore")


def _compose_volumes() -> list[tuple[str, str, str]]:
    """(host, container, mode) for every short-syntax bind mount in docker/compose.yaml."""
    text = (REPO_ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
    mounts = []
    for m in re.finditer(r"^\s*-\s+(\.\.[^\s:]*):(/[^\s:]+)(?::(\w+))?\s*$", text, re.M):
        mounts.append((m.group(1), m.group(2), m.group(3) or "rw"))
    return mounts


def test_compose_parses_the_repo_mount():
    assert ("..", "/work", "rw") in _compose_volumes()


@pytest.mark.parametrize("name", PROTECTED_DIRS)
def test_protected_dir_is_read_only_at_its_own_path_inside_the_repo_mount(name):
    # The repo is mounted read-write at /work, so /work/<name> exposes the host directory
    # writable unless a read-only mount sits exactly on that path (or on a parent below /work).
    ro_targets = {target for _, target, mode in _compose_volumes() if mode == "ro"}
    assert f"/work/{name}" in ro_targets


def test_every_mount_of_a_protected_dir_is_read_only():
    for host, target, mode in _compose_volumes():
        if any(host == f"../{d}" or host.startswith(f"../{d}/") for d in PROTECTED_DIRS):
            assert mode == "ro", f"{host} -> {target} is mounted {mode}"


def _live_docs() -> list[Path]:
    # docs/research/ holds dated research snapshots and is left as written.
    docs = [p for p in (REPO_ROOT / "docs").rglob("*.md") if "research" not in p.parts]
    return [*docs, REPO_ROOT / "README.md", REPO_ROOT / "CLAUDE.md"]


def test_live_docs_carry_no_bare_tbd_markers():
    # Unknowns are written as "not known yet; <requirement or phase> records it", never "TBD".
    hits = [
        f"{path.relative_to(REPO_ROOT)}:{n}"
        for path in _live_docs()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"\bTBD\b", line)
    ]
    assert not hits


def test_no_doc_mentions_a_phase_zero():
    # Milestone phases are numbered from 1 (GSD reserves the zero id); a "Phase 0" anywhere,
    # research notes and planning records included, would point at a phase that does not exist.
    docs = [*(REPO_ROOT / "docs").rglob("*.md"), *(REPO_ROOT / ".planning").rglob("*.md")]
    hits = [
        f"{path.relative_to(REPO_ROOT)}:{n}"
        for path in [*docs, REPO_ROOT / "README.md", REPO_ROOT / "CLAUDE.md"]
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"\bphases? 0\b|^\| 0\. ", line, re.I)
    ]
    assert not hits


def test_toolchain_records_the_confirmed_le_layout():
    # RT-05: the LE layout section carries the spike-confirmed facts, the trailer after the last
    # page of UFO2P and TACP included, instead of the old EOF claim and the open question.
    text = (REPO_ROOT / "docs" / "toolchain.md").read_text(encoding="utf-8")
    stale = ("runs exactly to EOF", "To be confirmed in Phase 2/3")
    assert [claim for claim in stale if claim in text] == []
    assert [needle for needle in ("0x1A0723", "0x303DDF", "trailer") if needle not in text] == []


_HASH_PREFIX_DIGITS = 8


def _manifest_hash_needles() -> set[str]:
    """Every [[targets]] md5 and sha1 of config/targets.toml, in full and as its first eight hex
    digits. Read at test time, so no hash is written down in this file."""
    digests = [digest for t in load_manifest() for digest in (t.md5, t.sha1)]
    return {*digests, *(digest[:_HASH_PREFIX_DIGITS] for digest in digests)}


def _files_with_manifest_hashes(root: Path, needles: set[str], exclude: set[str]) -> list[str]:
    """Sorted POSIX paths, relative to `root`, of the *.py files under `root` whose text holds
    any needle (case-insensitive). Paths in `exclude` and anything under __pycache__ are
    skipped."""
    hits = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if "__pycache__" in rel.parts or rel.as_posix() in exclude:
            continue
        text = path.read_text(encoding="utf-8").lower()
        if any(needle in text for needle in needles):
            hits.append(rel.as_posix())
    return sorted(hits)


def test_manifest_hashes_scan_detects_a_planted_hash(tmp_path):
    # The guard below is only worth something if it can fail: plant a manifest SHA-1 (and,
    # separately, its 8-digit prefix) in throwaway files and expect the scan to name both.
    sha1 = load_manifest()[0].sha1
    needles = _manifest_hash_needles()
    (tmp_path / "test_full.py").write_text(f'EXPECTED = "{sha1}"\n', encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "test_prefix.py").write_text(f"# {sha1[:8]}\n", encoding="utf-8")
    (tmp_path / "test_pinned.py").write_text(f'PIN = "{sha1}"\n', encoding="utf-8")
    (tmp_path / "test_clean.py").write_text("EXPECTED = load_manifest()\n", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.py").write_text(f"# {sha1}\n", encoding="utf-8")
    found = _files_with_manifest_hashes(tmp_path, needles, exclude={"test_pinned.py"})
    assert found == ["sub/test_prefix.py", "test_full.py"]


# D-15: expected SHA-1s reach round-trip tests only through load_manifest, never as copied
# strings. D-21 exempts tests/test_targets.py alone: it pins the manifest itself, so an edit to
# config/targets.toml to make a gate pass still fails the suite.
def test_round_trip_tests_never_copy_manifest_hashes():
    found = _files_with_manifest_hashes(
        REPO_ROOT / "tests", _manifest_hash_needles(), exclude={"test_targets.py"}
    )
    assert found == []


def test_gitignore_excludes_the_compiler_media_and_installs():
    patterns = _ignore_patterns(REPO_ROOT / ".gitignore")
    assert "third_party/" in patterns
    assert "/watcom/" in patterns


_FETCH_NEEDLES = ["fetch-watcom", "install-watcom", "archive.org", "watcom-media"]
_WORKFLOWS = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))


@pytest.mark.parametrize("needle", _FETCH_NEEDLES)
def test_dockerfile_never_fetches_the_compiler(needle):
    # The proprietary compiler is user-supplied at run time, never baked into an image layer.
    text = (REPO_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
    assert needle not in text


def test_ci_workflows_exist():
    assert _WORKFLOWS


@pytest.mark.parametrize("needle", _FETCH_NEEDLES)
@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda p: p.name)
def test_ci_never_fetches_the_compiler(workflow, needle):
    # docs/legal.md: CI never downloads or installs the compiler either.
    assert needle not in workflow.read_text(encoding="utf-8")


@pytest.mark.skipif(not Path("/.dockerenv").exists(), reason="only inside the container")
@pytest.mark.parametrize("path", ["/work/orig", "/work/third_party", "/work/watcom"])
def test_protected_paths_are_not_writable_in_the_container(path):
    if not os.path.isdir(path):
        pytest.skip(f"{path} is not mounted")
    assert not os.access(path, os.W_OK)
