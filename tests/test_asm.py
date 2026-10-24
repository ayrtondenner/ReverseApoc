"""reverseapoc asm: per-function listings with symbolic operands (SPL-05). Synthetic LEs only:
every byte below is made up."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import build_le_image, fixup_record, write_manifest
from reverseapoc.asm import AsmError, listing, select_rows, write_listings
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import FunctionRow, write_functions_csv
from reverseapoc.le import LE
from reverseapoc.symbols import SymbolTable

CODE = 0x10000
DATA = 0x20000
FUNC1 = CODE
FUNC2 = CODE + 0x10
FUNC3 = CODE + 0x20
END = CODE + 0x30

# func_00010000: push ebp; mov ebp, esp; call func_00010010; mov eax, [D_00020100]; pop ebp; ret
# The off32 field of the mov (at FUNC1 + 9) holds the object-relative offset 0x100, as wlink
# stores it; the listing must name the fixup's linear target instead.
FUNC1_BYTES = (
    b"\x55"  # push ebp
    + b"\x89\xe5"  # mov ebp, esp
    + b"\xe8\x08\x00\x00\x00"  # call FUNC2 (rel32 8 from FUNC1 + 8)
    + b"\xa1\x00\x01\x00\x00"  # mov eax, [0x100] (off32 field, LE fixup -> DATA + 0x100)
    + b"\x5d"  # pop ebp
    + b"\xc3"  # ret
    + b"\x90"  # nop
)
FUNC1_DATA_FIELD = 0x009  # page offset of the mov's off32 field
FUNC2_BYTES = b"\xc3" + b"\x90" * 15
# func_00010020: ret, three nops, then an inline off32 table entry pointing at FUNC3, then nops.
FUNC3_BYTES = b"\xc3\x90\x90\x90" + b"\x20\x00\x00\x00" + b"\x90" * 8
FUNC3_TABLE_FIELD = 0x024


def _image(*, table: bool = False) -> bytes:
    records = fixup_record(7, FUNC1_DATA_FIELD, 2, 0x100)
    if table:
        records += fixup_record(7, FUNC3_TABLE_FIELD, 1, 0x20)
    synthetic = build_le_image(
        fixups=[records, b"", b""],
        patches={FUNC1: FUNC1_BYTES, FUNC2: FUNC2_BYTES, FUNC3: FUNC3_BYTES},
    )
    return synthetic.data


def _rows() -> list[FunctionRow]:
    return [
        FunctionRow(FUNC1, FUNC2, "func_00010000", "game", "", "call"),
        FunctionRow(FUNC2, FUNC3, "func_00010010", "game", "", "call"),
        FunctionRow(FUNC3, END, "func_00010020", "game", "", "call"),
    ]


def _inputs(data: bytes):
    le = LE(data)
    rows = _rows()
    data_ranges = [(obj.base, obj.end) for obj in le.objects if not obj.flags & 0x4]
    symbols = SymbolTable.build(rows, data_ranges=data_ranges)
    return le.load_flat(relocate=False), le.fixups(), symbols, rows


def _instruction_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("  0x")]


def test_listing_names_call_and_data_operands():
    flat, fixups, symbols, rows = _inputs(_image())
    text = listing(rows[0], flat=flat, fixups=fixups, symbols=symbols)
    assert text.splitlines()[0].startswith("# func_00010000")
    lines = _instruction_lines(text)
    assert any("call" in line and line.endswith("func_00010010") for line in lines)
    assert any("mov" in line and "D_00020100" in line for line in lines)
    # the raw object-relative field never shows up as an operand
    assert not any("0x100]" in line for line in lines)


def test_inline_data_line():
    flat, fixups, symbols, rows = _inputs(_image(table=True))
    text = listing(rows[2], flat=flat, fixups=fixups, symbols=symbols)
    assert f"  0x{CODE + FUNC3_TABLE_FIELD:08X}  dd func_00010020" in text.splitlines()


def test_asm_verb_writes_listings(tmp_path: Path, capsys):
    data = _image()
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "SYN.EXE").write_bytes(data)
    manifest = write_manifest(tmp_path / "targets.toml", {"SYN.EXE": data})
    functions = tmp_path / "functions.csv"
    write_functions_csv(functions, _rows()[:2], "SYN.EXE")
    out = tmp_path / "asm"
    rc = cli_main(["asm", "SYN.EXE", "--orig", str(orig), "--manifest", str(manifest),
                   "--functions", str(functions), "--out", str(out)])  # fmt: skip
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    first = out / "syn" / "func_00010000.s"
    assert first.is_file()
    assert (out / "syn" / "func_00010010.s").is_file()
    text = first.read_text(encoding="utf-8")
    assert any(line.endswith("call func_00010010") for line in text.splitlines())
    assert "D_00020100" in text
    lines = captured.out.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("wrote 2 listings to ")


def test_refuses_out_in_orig(tmp_path: Path, capsys):
    data = _image()
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "SYN.EXE").write_bytes(data)
    manifest = write_manifest(tmp_path / "targets.toml", {"SYN.EXE": data})
    functions = tmp_path / "functions.csv"
    write_functions_csv(functions, _rows()[:2], "SYN.EXE")
    rc = cli_main(["asm", "SYN.EXE", "--orig", str(orig), "--manifest", str(manifest),
                   "--functions", str(functions), "--out", str(orig / "asm")])  # fmt: skip
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.err.startswith("reverseapoc asm: error:")
    assert not (orig / "asm").exists()


# ---- --only ADDR (orchestrator ruling F3) ----


def test_only_lists_the_row_containing_the_address():
    _, _, symbols, rows = _inputs(_image())
    assert select_rows(rows, symbols, only=FUNC2 + 3) == [rows[1]]
    assert select_rows(rows, symbols, only=FUNC1) == [rows[0]]


def test_only_refuses_an_address_in_no_row():
    _, _, symbols, rows = _inputs(_image())
    with pytest.raises(AsmError, match="0x00010030"):
        select_rows(rows, symbols, only=END)


def test_asm_verb_only(tmp_path: Path, capsys):
    data = _image()
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "SYN.EXE").write_bytes(data)
    manifest = write_manifest(tmp_path / "targets.toml", {"SYN.EXE": data})
    functions = tmp_path / "functions.csv"
    write_functions_csv(functions, _rows(), "SYN.EXE")
    out = tmp_path / "asm"
    rc = cli_main(["asm", "SYN.EXE", "--orig", str(orig), "--manifest", str(manifest),
                   "--functions", str(functions), "--out", str(out),
                   "--only", "0x10013"])  # fmt: skip
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    assert sorted(p.name for p in (out / "syn").iterdir()) == ["func_00010010.s"]
    assert captured.out.startswith("wrote 1 listing to ")


def test_write_listings_report(tmp_path: Path):
    flat, fixups, symbols, rows = _inputs(_image())
    report = write_listings(rows, flat=flat, fixups=fixups, symbols=symbols, out_dir=tmp_path / "x")
    assert report.count == 3
    assert report.to_json() == {"count": 3, "directory": str(tmp_path / "x")}
    assert sorted(p.name for p in (tmp_path / "x").iterdir()) == [
        "func_00010000.s",
        "func_00010010.s",
        "func_00010020.s",
    ]
