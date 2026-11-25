"""driver.load_world's up-front check of the pack inputs (todo hint-file-preflight).

attempt.make_pack reads config/hints/<exe>.toml and build/signatures/<exe>.json at every
session's launch and raises on a malformed one; the night caught only PackOverCap there, so one
typo stopped a night partway. load_world reads both once per EXE, so the drive refuses before
any session. Every address, name and file below is made up.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from reverseapoc import attempt, contextpack, driver, signatures
from reverseapoc.functions import KIND_GAME, FunctionRow

EXE = "ufo2p"
START = 0x00010010
ROW = FunctionRow(START, START + 0x20, f"func_{START:08X}", KIND_GAME, "u_00010000", "made up")
DATA = SimpleNamespace(stem=EXE, rows=(ROW,))


def _roots(tmp_path: Path) -> attempt.Roots:
    return attempt.Roots(repo=tmp_path, config=tmp_path / "config")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(attempt, "exe_inputs", lambda exe, **_: DATA)
    driver._load_worlds(SimpleNamespace(world=lambda: {EXE: driver.load_world(
        EXE, roots=_roots(tmp_path))}))  # fmt: skip


def test_the_world_pack_hands_the_variants_to_make_pack(tmp_path: Path, monkeypatch):
    """Runs 20261125b-abl-lookalike-off-r1 and -carry-off-r1 stopped at once: the driver called
    the world's pack with `variants=` (--pack-variant) but load_world's pack took none
    (TypeError). The world pack passes them to attempt.make_pack, and with none it passes ()."""
    seen = []

    def fake_make_pack(data, row, **kwargs):
        seen.append(kwargs.get("variants"))
        return SimpleNamespace(pack_bytes=1, truncated=())

    monkeypatch.setattr(attempt, "make_pack", fake_make_pack)
    monkeypatch.setattr(driver, "write_pack", lambda built, directory, root: None)
    roots = _roots(tmp_path)
    pick = SimpleNamespace(start=START)
    args = (DATA, {START: ROW}, roots, None, pick, tmp_path / "attempt")
    driver._world_pack(*args, variants=("no-carry",))
    driver._world_pack(*args)
    assert seen == [("no-carry",), ()]


def test_pack_inputs_pass_with_no_files_or_good_ones(tmp_path: Path):
    roots = _roots(tmp_path)
    driver.check_pack_inputs(DATA, roots)  # no hint file and no table: nothing to refuse
    _write(contextpack.hints_path(roots.config, EXE), f'0x{START:08X} = "a made-up hint"\n')
    driver.check_pack_inputs(DATA, roots)


def test_a_bad_hint_file_refuses_the_drive_up_front(tmp_path: Path, monkeypatch):
    _write(contextpack.hints_path(tmp_path / "config", EXE), '0x0001001a = "lower-case key"\n')
    with pytest.raises(driver.Refused) as refused:
        _load(tmp_path, monkeypatch)
    assert refused.value.reason == "world"
    assert "ContextPackError" in refused.value.detail
    assert "ufo2p.toml" in refused.value.detail


def test_a_malformed_signature_table_refuses_the_drive_up_front(tmp_path: Path, monkeypatch):
    _write(signatures.table_path(tmp_path, EXE), "{not json\n")
    with pytest.raises(driver.Refused) as refused:
        _load(tmp_path, monkeypatch)
    assert refused.value.reason == "world"
    assert "SignatureError" in refused.value.detail
    assert "ufo2p.json" in refused.value.detail
