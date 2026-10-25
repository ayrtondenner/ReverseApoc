"""The one atomic file writer of the package (DI-18, D-41): fileio.write_atomic.

Every test writes only under pytest's tmp_path.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from reverseapoc import fileio, splice


def _temporaries(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir() if p.name.endswith(".tmp"))


def test_write_atomic_replaces_the_file(tmp_path):
    target = tmp_path / "out.bin"
    target.write_bytes(b"old bytes")
    fileio.write_atomic(target, b"new bytes")
    assert target.read_bytes() == b"new bytes"
    assert _temporaries(tmp_path) == []
    assert [p.name for p in tmp_path.iterdir()] == [target.name]


def test_write_atomic_creates_a_missing_file(tmp_path):
    target = tmp_path / "fresh.bin"
    fileio.write_atomic(target, b"data")
    assert target.read_bytes() == b"data"
    assert [p.name for p in tmp_path.iterdir()] == [target.name]


def test_write_atomic_keeps_the_old_file_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "out.bin"
    target.write_bytes(b"old bytes")

    def failing_replace(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError, match="No space left"):
        fileio.write_atomic(target, b"new bytes")
    monkeypatch.undo()
    assert target.read_bytes() == b"old bytes"
    assert _temporaries(tmp_path) == []


def test_write_atomic_replaces_a_link(tmp_path):
    pointee = tmp_path / "pointee.bin"
    pointee.write_bytes(b"pointee bytes")
    link = tmp_path / "link.bin"
    try:
        link.symlink_to(pointee)
    except OSError:
        pytest.skip("symlink creation needs privileges on this host")
    fileio.write_atomic(link, b"new bytes")
    assert not link.is_symlink()
    assert link.read_bytes() == b"new bytes"
    assert pointee.read_bytes() == b"pointee bytes"
    assert _temporaries(tmp_path) == []


def test_splice_alias_is_the_same_object():
    # One release of the old private name for out-of-tree callers (D-41).
    assert splice._write_atomic is fileio.write_atomic


def test_no_module_imports_the_private_alias():
    # Every module writes through fileio.write_atomic; only splice still names the old alias.
    package = Path(fileio.__file__).parent
    naming = sorted(
        p.name for p in package.glob("*.py") if "_write_atomic" in p.read_text(encoding="utf-8")
    )
    assert naming == ["splice.py"]
