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


@pytest.mark.skipif(not Path("/.dockerenv").exists(), reason="only inside the container")
@pytest.mark.parametrize("path", ["/work/orig", "/work/third_party", "/work/watcom"])
def test_protected_paths_are_not_writable_in_the_container(path):
    if not os.path.isdir(path):
        pytest.skip(f"{path} is not mounted")
    assert not os.access(path, os.W_OK)
