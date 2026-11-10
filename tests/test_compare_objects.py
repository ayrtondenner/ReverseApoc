"""`reverseapoc compare-objects` (D-08, D-23; plan 07.2-08): two compiles of one unit compare by
code bytes, lengths, relocations and public offsets, with names resolved to their original
addresses through each tree's symbol table. Every object is built here from named OMF records
(tests/omfimage.py); every byte is made up, never a game byte."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omfimage import (
    comdat32,
    coment,
    extdef,
    fixup,
    fixupp32,
    ledata32,
    lnames,
    module,
    pubdef32,
    segdef32,
)
from reverseapoc import cli
from reverseapoc.compare_objects import CompareError, compare
from reverseapoc.functions import (
    FunctionRow,
    SymbolRow,
    write_functions_csv,
    write_symbols_csv,
)
from reverseapoc.omf import COMENT_DEPENDENCY
from reverseapoc.symbols import SymbolTable

EXE = "ufo2p"
MANIFEST_NAME = "UFO2P.EXE"
FUNC = 0x0008A0E0  # the unit's one function
CALLEE = 0x0008A200  # a function it calls
OTHER = 0x0008A300  # another function, for a retargeted call
DATA = 0x000C1000  # a global it reads
DATA_OBJECT = (0x000C0000, 0x000D0000)  # a made-up LE data object holding DATA

PLACEHOLDER = "func_0008A0E0_"
RENAMED = "clock_tick_"
DATA_PLACEHOLDER = "_D_000C1000"
DATA_RENAMED = "_frame_wrap"
CALLEE_NAME = "func_0008A200_"
OTHER_NAME = "func_0008A300_"
RUNTIME_EXTERN = "__CHK"  # a runtime external no table names

# _TEXT: two relocated 32-bit fields at 0 and 4 (their addend, zero), then 4 made-up code bytes.
CODE = bytes(8) + bytes([0x5A, 0x5B, 0x5C, 0x5D])
CODE_BYTE_AT = 9  # offset of the one byte the code-change test flips (under no fixup)
TEXT_LEN = len(CODE)
DATA_BYTES = bytes([0x01, 0x02, 0x03, 0x04])

ROWS = (
    FunctionRow(FUNC, FUNC + 0x10, "func_0008A0E0", "game", "u_0008a0e0", "call"),
    FunctionRow(CALLEE, CALLEE + 0x10, "func_0008A200", "game", "u_0008a200", "call"),
    FunctionRow(OTHER, OTHER + 0x10, "func_0008A300", "game", "u_0008a300", "call"),
)
RENAMES = (SymbolRow(FUNC, RENAMED, "func"), SymbolRow(DATA, DATA_RENAMED, "data"))


def obj(
    *,
    public: str = PLACEHOLDER,
    public_at: int = 0,
    data_name: str = DATA_PLACEHOLDER,
    callee: str = CALLEE_NAME,
    runtime: str = RUNTIME_EXTERN,
    code: bytes = CODE,
    data: bytes = DATA_BYTES,
    source: str = "src/ufo2p/u_0008a0e0.c",
    stamp: bytes = b"\x00\x00\x00\x00",
    extra: tuple[bytes, ...] = (),
) -> bytes:
    """_TEXT (segment 1, code) and _DATA (segment 2), the public at `public_at`, externs
    1 `data_name`, 2 `callee`, 3 `runtime`. The fixup at 0 reads extern 1 (a 32-bit offset), the
    one at 4 calls extern 2 (self-relative), and _DATA's one fixup at 0 points at extern 3."""
    return module(
        source,
        coment(COMENT_DEPENDENCY, stamp + source.encode("latin-1")),
        lnames("", "_TEXT", "CODE", "_DATA", "DATA"),
        segdef32(2, 3, len(code)),
        segdef32(4, 5, len(data)),
        extdef(data_name, callee, runtime),
        pubdef32(1, [(public, public_at)]),
        ledata32(1, 0, code),
        fixupp32(fixup(0, target=(2, 1), displacement=0),
                 fixup(4, segment_relative=False, target=(2, 2))),  # fmt: skip
        ledata32(2, 0, data),
        fixupp32(fixup(0, target=(2, 3), displacement=0)),
        *extra,
    )


def table(symbols: tuple[SymbolRow, ...] = ()) -> SymbolTable:
    return SymbolTable.build(ROWS, symbols, data_ranges=[DATA_OBJECT])


BASE_TABLE = table()
HEAD_TABLE = table(RENAMES)


def renamed_obj(**changes) -> bytes:
    return obj(public=RENAMED, data_name=DATA_RENAMED, **changes)


def flipped(code: bytes, at: int) -> bytes:
    return code[:at] + bytes([code[at] ^ 0xFF]) + code[at + 1:]


# ---- the compare ----


def test_rename_only_compare_is_ok():
    result = compare(obj(), renamed_obj(), base_symbols=BASE_TABLE, head_symbols=HEAD_TABLE)
    assert result.ok
    assert result.first_difference is None


def test_same_names_without_the_rename_rows_differ():
    """The head's rename is believed only through its own symbol table: a head object with the
    new names but no symbols.csv row for them resolves them to nothing and differs."""
    result = compare(obj(), renamed_obj(), base_symbols=BASE_TABLE, head_symbols=BASE_TABLE)
    assert not result.ok


def test_comment_only_compare_is_ok():
    """THEADR and COMENT 0xE9 (the source path and its timestamp) are not compared."""
    head = obj(source="other/path.c", stamp=b"\x11\x22\x33\x44")
    assert compare(obj(), head, base_symbols=BASE_TABLE, head_symbols=BASE_TABLE).ok


def test_code_byte_change_names_segment_and_offset():
    head = renamed_obj(code=flipped(CODE, CODE_BYTE_AT))
    diff = compare(obj(), head, base_symbols=BASE_TABLE, head_symbols=HEAD_TABLE).first_difference
    assert (diff.segment, diff.offset, diff.kind) == ("_TEXT", CODE_BYTE_AT, "code bytes")
    assert diff.detail == f"1 of {TEXT_LEN} bytes differ"


def test_data_segment_byte_change_differs():
    head = obj(data=flipped(DATA_BYTES, 2))
    diff = compare(obj(), head, base_symbols=BASE_TABLE, head_symbols=BASE_TABLE).first_difference
    assert (diff.segment, diff.offset, diff.kind) == ("_DATA", 2, "data bytes")


def test_relocation_target_change_names_the_fixup():
    head = obj(callee=OTHER_NAME)
    diff = compare(obj(), head, base_symbols=BASE_TABLE, head_symbols=BASE_TABLE).first_difference
    assert (diff.segment, diff.offset, diff.kind) == ("_TEXT", 4, "relocation")


def test_unresolved_names_compare_by_name():
    same = compare(obj(), obj(), base_symbols=BASE_TABLE, head_symbols=BASE_TABLE)
    assert same.ok
    other = compare(obj(), obj(runtime="__STK"), base_symbols=BASE_TABLE, head_symbols=BASE_TABLE)
    diff = other.first_difference
    assert (diff.segment, diff.offset, diff.kind) == ("_DATA", 0, "relocation")


def test_public_moved_fails():
    head = renamed_obj(public_at=2)
    diff = compare(obj(), head, base_symbols=BASE_TABLE, head_symbols=HEAD_TABLE).first_difference
    assert (diff.segment, diff.kind) == ("_TEXT", "public")


def test_extra_fixup_differs():
    """A fixup only the head has (bytes 8-11 rewritten unchanged under it)."""
    relocated = (ledata32(1, 8, CODE[8:]), fixupp32(fixup(0, target=(2, 3), displacement=0)))
    head = obj(extra=relocated)
    diff = compare(obj(), head, base_symbols=BASE_TABLE, head_symbols=BASE_TABLE).first_difference
    assert (diff.segment, diff.offset, diff.kind) == ("_TEXT", 8, "relocation")
    assert diff.detail == "2 fixups at base, 3 at head"


def test_extra_public_differs():
    head = obj(extra=(pubdef32(1, [("entry_", 8)]),))
    diff = compare(obj(), head, base_symbols=BASE_TABLE, head_symbols=BASE_TABLE).first_difference
    assert (diff.segment, diff.offset, diff.kind) == ("_TEXT", 8, "public")
    assert diff.detail == "1 publics at base, 2 at head"


def test_segment_length_differs():
    head = obj(code=CODE + bytes(1))
    diff = compare(obj(), head, base_symbols=BASE_TABLE, head_symbols=BASE_TABLE).first_difference
    assert (diff.segment, diff.offset, diff.kind) == ("_TEXT", None, "length")


def test_comdat_is_refused():
    """COMDAT blocks are not compared, so an object holding one is a tool error, never a pass."""
    with pytest.raises(CompareError, match="COMDAT"):
        compare(obj(), obj(extra=(comdat32(2, bytes(2)),)), base_symbols=BASE_TABLE,
                head_symbols=BASE_TABLE)  # fmt: skip


def test_truncated_object_raises():
    with pytest.raises(CompareError, match="base"):
        compare(obj()[:-3], obj(), base_symbols=BASE_TABLE, head_symbols=BASE_TABLE)


# ---- the verb ----


def write_config(root: Path, symbols: tuple[SymbolRow, ...]) -> Path:
    """A tree's config/: <exe>/functions.csv and, with rows, <exe>/symbols.csv."""
    config = root / "config"
    write_functions_csv(config / EXE / "functions.csv", ROWS, MANIFEST_NAME)
    if symbols:
        write_symbols_csv(config / EXE / "symbols.csv", symbols, MANIFEST_NAME)
    return config


def run_verb(tmp_path: Path, base: bytes, head: bytes, *extra: str,
             head_symbols: tuple[SymbolRow, ...] = RENAMES) -> int:  # fmt: skip
    base_obj, head_obj = tmp_path / "base.obj", tmp_path / "head.obj"
    base_obj.write_bytes(base)
    head_obj.write_bytes(head)
    base_config = write_config(tmp_path / "base", ())
    head_config = write_config(tmp_path / "head", head_symbols)
    return cli.main(["compare-objects", str(base_obj), str(head_obj),
                     "--base-config", str(base_config), "--head-config", str(head_config),
                     "--exe", EXE, *extra])  # fmt: skip


def test_rename_only_passes(tmp_path, capsys):
    """The verb reads each tree's own CSVs; the runner has no LE, so a data placeholder stands
    for the address it spells."""
    assert run_verb(tmp_path, obj(), renamed_obj()) == 0
    assert capsys.readouterr().out.strip() == "same: code, relocations and publics match"


def test_comment_only_passes(tmp_path):
    head = obj(source="elsewhere.c", stamp=b"\x55\x66\x77\x10")
    assert run_verb(tmp_path, obj(), head, head_symbols=()) == 0


def test_code_byte_change_fails(tmp_path, capsys):
    """Exit 1 naming the segment, the offset and the count of differing bytes; never a byte
    value, so no game byte reaches a CI log."""
    head = renamed_obj(code=flipped(CODE, CODE_BYTE_AT))
    assert run_verb(tmp_path, obj(), head) == 1
    out = capsys.readouterr().out
    assert out.strip() == f"differ: _TEXT+0x9: code bytes: 1 of {TEXT_LEN} bytes differ"
    for value in (CODE[CODE_BYTE_AT], CODE[CODE_BYTE_AT] ^ 0xFF):
        assert f"{value:#04x}" not in out and f"{value:02x}" not in out.lower()


def test_relocation_target_change_fails(tmp_path, capsys):
    assert run_verb(tmp_path, obj(), obj(callee=OTHER_NAME), head_symbols=()) == 1
    out = capsys.readouterr().out
    assert out.startswith("differ: _TEXT+0x4: relocation")


def test_unresolved_runtime_name_fails_when_changed(tmp_path):
    assert run_verb(tmp_path, obj(), obj(runtime="__STK"), head_symbols=()) == 1


def test_public_moved_fails_in_the_verb(tmp_path, capsys):
    assert run_verb(tmp_path, obj(), renamed_obj(public_at=2)) == 1
    assert "public" in capsys.readouterr().out


def test_json_report(tmp_path, capsys):
    head = renamed_obj(code=flipped(CODE, CODE_BYTE_AT))
    assert run_verb(tmp_path, obj(), head, "--json") == 1
    doc = json.loads(capsys.readouterr().out)
    difference = {"segment": "_TEXT", "offset": CODE_BYTE_AT, "kind": "code bytes",
                  "detail": f"1 of {TEXT_LEN} bytes differ"}  # fmt: skip
    assert doc == {"ok": False, "difference": difference}


def test_tool_error_truncated_object(tmp_path, capsys):
    assert run_verb(tmp_path, obj()[:-3], obj()) == 2
    assert capsys.readouterr().err.startswith("reverseapoc compare-objects: error:")


def test_tool_error_missing_file(tmp_path, capsys):
    base_config = write_config(tmp_path / "base", ())
    code = cli.main(["compare-objects", str(tmp_path / "nope.obj"), str(tmp_path / "nope2.obj"),
                     "--base-config", str(base_config), "--head-config", str(base_config),
                     "--exe", EXE])  # fmt: skip
    assert code == 2
    assert capsys.readouterr().err.startswith("reverseapoc compare-objects: error:")


def test_tool_error_missing_functions_csv(tmp_path, capsys):
    (tmp_path / "base.obj").write_bytes(obj())
    code = cli.main(["compare-objects", str(tmp_path / "base.obj"), str(tmp_path / "base.obj"),
                     "--base-config", str(tmp_path / "none"),
                     "--head-config", str(tmp_path / "none"), "--exe", EXE])  # fmt: skip
    assert code == 2
    assert capsys.readouterr().err.startswith("reverseapoc compare-objects: error:")
