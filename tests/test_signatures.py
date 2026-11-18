"""The whole-program signature table (todo whole-program-signature-table). Every encoding is
written here by hand, never game bytes; the table is written under pytest's tmp_path."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from reverseapoc import attempt, lift, signatures
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import FunctionRow
from reverseapoc.le import Fixup
from reverseapoc.signatures import Entry, SignatureError

VA = 0x1000
ROW_SPACING = 0x100
TWO_ARGS = "39d0 19c9 89c8 c3"  # cmp eax, edx; sbb ecx, ecx; mov eax, ecx; ret: eax, edx -> eax
POPS_8 = "c20800"  # ret 8: four register arguments and two on the stack
TWO_POPS = "85c0 7403 c20800 c3"  # test; je; ret 8; ret: the lifter refuses it
NOTHING = "c3"  # ret


class StubSymbols:
    def c_name(self, va: int, *, data: bool = False) -> str:
        return f"{'D' if data else 'func'}_{va:08X}"


@dataclass
class StubExe:
    flat: bytes
    rows: tuple[FunctionRow, ...]
    fixups: tuple[Fixup, ...]
    symbols: StubSymbols
    stem: str = "stub"


def stub_exe(*codes: str, kinds: tuple[str, ...] = ()) -> StubExe:
    """One row per hex string (a game row unless `kinds` says otherwise), ROW_SPACING apart."""
    flat = bytearray(VA + ROW_SPACING * len(codes))
    rows = []
    for n, text in enumerate(codes):
        code = bytes.fromhex(text)
        start = VA + ROW_SPACING * n
        flat[start : start + len(code)] = code
        kind = kinds[n] if n < len(kinds) else "game"
        rows.append(FunctionRow(start, start + len(code), f"row{n}", kind, "u_stub", "test"))
    return StubExe(bytes(flat), tuple(rows), (), StubSymbols())


@pytest.fixture(autouse=True)
def fresh_lifter(monkeypatch, tmp_path):
    """The lifter's caches key on a stem and on id(exe); the census goes under tmp_path."""
    monkeypatch.setattr(lift, "CACHE_DIR", tmp_path / "lift")
    caches = (lift._RESULT_USED, lift._BUILDING, lift._INDEX, lift._FIXUPS)
    for cache in caches:
        cache.clear()
    yield
    for cache in caches:
        cache.clear()


def test_build_infers_every_game_row():
    exe = stub_exe(TWO_ARGS, POPS_8, TWO_POPS, NOTHING, kinds=("game", "thunk", "game", "runtime"))
    table = signatures.build(exe)
    assert table == {
        VA: Entry(nregs=2, nstack=0, returns=True),
        VA + ROW_SPACING: Entry(nregs=4, nstack=2, returns=False),
        VA + 2 * ROW_SPACING: Entry(refused="stack: reachable returns pop different amounts"),
    }  # the runtime row is never lifted


@pytest.mark.parametrize(
    ("entry", "text"),
    [
        (Entry(2, 0, True), "int f(int, int); lifter: args in eax, edx, the result in eax"),
        (Entry(0, 0, False), "void f(void); lifter: no args, no result"),
        (Entry(4, 2, False), "void f(int, int, int, int, int, int); lifter: args in eax, edx, "
                             "ebx, ecx and 2 on the stack (the callee pops 8 bytes), no result"),
        (Entry(refused="frame: ebp frame"), "unknown: the lifter refused it (frame: ebp frame)"),
    ],
)  # fmt: skip
def test_prototype_text(entry: Entry, text: str):
    assert entry.prototype("f") == text


def test_write_then_load_round_trips(tmp_path: Path):
    exe = stub_exe(TWO_ARGS, TWO_POPS)
    path = signatures.table_path(tmp_path, exe.stem)
    assert path == tmp_path / "build" / "signatures" / "stub.json"
    built = signatures.build(exe)
    signatures.write(path, exe.rows, built)
    loaded = signatures.load(path, exe.rows, exe.stem)
    assert loaded.entries == built and loaded.note == ""


def test_load_of_a_missing_table_says_how_to_make_one(tmp_path: Path):
    loaded = signatures.load(tmp_path / "none.json", (), "ufo2p")
    assert loaded.entries == {}
    assert "no signature table" in loaded.note and "reverseapoc signatures ufo2p" in loaded.note


def test_load_of_a_table_for_other_rows_is_stale(tmp_path: Path):
    exe = stub_exe(TWO_ARGS)
    path = tmp_path / "t.json"
    signatures.write(path, exe.rows, signatures.build(exe))
    moved = (dataclasses.replace(exe.rows[0], end=exe.rows[0].end + 1),)
    loaded = signatures.load(path, moved, exe.stem)
    assert loaded.entries == {} and "stale" in loaded.note


@pytest.mark.parametrize(
    "text",
    ["{", "[]", '{"format": 99}', json.dumps({"format": 1, "rows_sha256": "x", "signatures": []})],
)
def test_load_refuses_a_malformed_table(tmp_path: Path, text: str):
    path = tmp_path / "t.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(SignatureError, match="t.json"):
        signatures.load(path, (), "stub")


def test_load_refuses_a_malformed_entry(tmp_path: Path):
    exe = stub_exe(TWO_ARGS)
    path = tmp_path / "t.json"
    signatures.write(path, exe.rows, signatures.build(exe))
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["signatures"][f"{VA:08X}"] = {"nregs": "two", "nstack": 0, "returns": True}
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SignatureError, match=f"{VA:08X}"):
        signatures.load(path, exe.rows, exe.stem)


def test_signatures_verb_writes_the_table(tmp_path: Path, monkeypatch, capsys):
    exe = stub_exe(TWO_ARGS, TWO_POPS)
    monkeypatch.setattr(attempt, "exe_inputs", lambda *args, **kwargs: exe)
    monkeypatch.setattr(attempt, "ROOTS", attempt.Roots(repo=tmp_path))
    assert cli_main(["signatures", "stub"]) == 0
    out = capsys.readouterr().out
    path = signatures.table_path(tmp_path, "stub")
    assert out.strip() == f"wrote {path} (1 inferred, 1 refused)"
    assert signatures.load(path, exe.rows, "stub").entries == signatures.build(exe)
