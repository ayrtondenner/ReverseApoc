"""Region map, reassembly and rebuild tests against synthetic LE images (tests/conftest.py).

No game bytes: every image here is built by `build_le_image`, and the rebuild tests write only
under pytest's tmp_path.
"""

from __future__ import annotations

from conftest import write_manifest
from reverseapoc import splice
from reverseapoc.le import LE
from reverseapoc.splice import decompose, reassemble, rebuild, rebuild_target
from reverseapoc.targets import load_manifest


def _orig(tmp_path, data: bytes, name: str = "SYNTH.EXE"):
    """An orig/ directory holding `data` as `name`, and a manifest that describes it."""
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / name).write_bytes(data)
    manifest = write_manifest(tmp_path / "m.toml", {name: data})
    return orig, manifest


# ---- Task 1: the round trip and the rebuild path ----------------------------------------------


def test_round_trip_reproduces_synthetic_le(synthetic_le):
    le = LE(synthetic_le.data)
    assert reassemble(le, decompose(le)) == synthetic_le.data


def test_rebuild_target_writes_ok_output(tmp_path, synthetic_le, monkeypatch):
    orig, manifest = _orig(tmp_path, synthetic_le.data)
    (target,) = load_manifest(manifest)
    out = tmp_path / "build"
    hashed = []
    real_hash_file = splice.hash_file

    def spy(path):
        hashed.append(path)
        return real_hash_file(path)

    monkeypatch.setattr(splice, "hash_file", spy)
    result = rebuild_target(target, orig, out)
    assert result.status == "ok"
    assert result.ok
    assert result.output == out / "SYNTH.EXE"
    assert (out / "SYNTH.EXE").read_bytes() == synthetic_le.data
    assert result.hashes.sha1 == target.sha1
    assert out / "SYNTH.EXE" in hashed  # the hash covers the file as written


def test_rebuild_is_idempotent(tmp_path, synthetic_le):
    orig, manifest = _orig(tmp_path, synthetic_le.data)
    out = tmp_path / "build"
    first = rebuild(orig, out, manifest)
    first_bytes = (out / "SYNTH.EXE").read_bytes()
    second = rebuild(orig, out, manifest)
    assert first.ok and second.ok
    assert [r.status for r in first.results] == ["ok"]
    assert [r.status for r in second.results] == ["ok"]
    assert (out / "SYNTH.EXE").read_bytes() == first_bytes == synthetic_le.data
