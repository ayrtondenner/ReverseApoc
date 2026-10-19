"""Bring-your-own-files hygiene: game files and the compiler never reach the image, and the
container cannot write to them."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from conftest import REPO_ROOT

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


def test_gitignore_excludes_the_compiler_media_and_installs():
    patterns = _ignore_patterns(REPO_ROOT / ".gitignore")
    assert "third_party/" in patterns
    assert "/watcom/" in patterns


@pytest.mark.parametrize(
    "needle", ["fetch-watcom", "install-watcom", "archive.org", "watcom-media"]
)
def test_dockerfile_never_fetches_the_compiler(needle):
    # The proprietary compiler is user-supplied at run time, never baked into an image layer.
    text = (REPO_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
    assert needle not in text


@pytest.mark.skipif(not Path("/.dockerenv").exists(), reason="only inside the container")
@pytest.mark.parametrize("path", ["/work/orig", "/work/third_party", "/work/watcom"])
def test_protected_paths_are_not_writable_in_the_container(path):
    if not os.path.isdir(path):
        pytest.skip(f"{path} is not mounted")
    assert not os.access(path, os.W_OK)
