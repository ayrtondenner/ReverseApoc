"""reverseapoc score: the P16 filter and the easiest-first ranking (D-15). Synthetic LEs only:
every byte below is made up."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import conftest
from conftest import PAGE_SIZE, build_le_image, fixup_record, write_manifest
from reverseapoc.asm import data_ranges
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import FunctionRow, write_functions_csv
from reverseapoc.le import LE, SRC_OFF32, SRC_SEL16
from reverseapoc.score import (
    LE_PAGE_SIZE,
    Candidate,
    ScoreError,
    ScoreReport,
    features,
    rank,
    rejections,
    score,
)
from reverseapoc.symbols import SymbolTable

CODE = 0x10000
DATA = 0x20000
CODE_OBJ = 1
DATA_OBJ = 2
CALLEE = CODE + 0x800  # a game function that only returns
CHK = CODE + 0x900  # the runtime __CHK
DATA_PLAIN = 0x100  # data object offset holding non-string bytes
DATA_STRING = 0x180  # data object offset holding "abc" + NUL (made up)
DATA_PAST_END = 0x3000  # the data object's end: a target in no data range

PUSH_EBP = b"\x55"
MOV_EBP_ESP = b"\x89\xe5"
POP_EBP = b"\x5d"
RET = b"\xc3"
NOP = b"\x90"


@dataclass
class Func:
    """One synthetic function: its bytes, row and the LE fixups (field va, kind, obj, off)."""

    start: int
    code: bytes = b""
    fixups: list[tuple[int, int, int, int | None]] = field(default_factory=list)
    kind: str = "game"
    name: str = ""

    def emit(self, blob: bytes) -> int:
        """Append `blob`; return its linear address."""
        va = self.start + len(self.code)
        self.code += blob
        return va

    def call(self, target: int) -> None:
        va = self.start + len(self.code)
        self.emit(b"\xe8" + struct.pack("<i", target - (va + 5)))

    def load(self, data_off: int, *, obj: int = DATA_OBJ, kind: int = SRC_OFF32) -> None:
        """mov eax, [field]: an off32 field the LE fixes up to obj:data_off (holding data_off,
        the object-relative offset, as wlink stores it)."""
        va = self.emit(b"\xa1" + struct.pack("<I", data_off))
        self.fixups.append((va + 1, kind, obj, data_off))

    @property
    def row(self) -> FunctionRow:
        name = self.name or f"func_{self.start:08X}"
        return FunctionRow(self.start, self.start + len(self.code), name, self.kind, "", "call")


def framed(start: int, *, call: int | None = CALLEE, data: int | None = DATA_PLAIN,
           pad: int = 0, chk: bool = False, kind: str = "game") -> Func:  # fmt: skip
    """push ebp; mov ebp, esp; [call]; [mov eax, [data]]; [nops]; pop ebp; ret, optionally after
    a `push imm32; call __CHK` prologue."""
    f = Func(start, kind=kind)
    if chk:
        f.emit(b"\x68\x10\x00\x00\x00")  # push 0x10
        f.call(CHK)
    f.emit(PUSH_EBP + MOV_EBP_ESP)
    if call is not None:
        f.call(call)
    if data is not None:
        f.load(data)
    f.emit(NOP * pad + POP_EBP + RET)
    return f


def _callee() -> Func:
    return Func(CALLEE, RET)


def _chk() -> Func:
    return Func(CHK, RET, kind="runtime", name="__CHK")


def _records(funcs: list[Func]) -> list[bytes]:
    pages = [b"", b"", b""]
    for f in funcs:
        for va, kind, obj, off in f.fixups:
            for page in sorted({(va - CODE) // PAGE_SIZE, (va + 3 - CODE) // PAGE_SIZE}):
                offset = va - (CODE + page * PAGE_SIZE)
                pages[page] += fixup_record(kind, offset, obj, off, off32=off is not None)
    return pages


def _patches(funcs: list[Func]) -> dict[int, bytes]:
    """Code bytes split at page boundaries, plus the made-up data bytes."""
    patches = {DATA + DATA_PLAIN: b"\x01\x00\x00\x00", DATA + DATA_STRING: b"abc\x00"}
    for f in funcs:
        boundary = (f.start // PAGE_SIZE + 1) * PAGE_SIZE
        head = f.code[: boundary - f.start]
        patches[f.start] = head
        if len(f.code) > len(head):
            patches[boundary] = f.code[len(head) :]
    return patches


def _image(funcs: list[Func]) -> bytes:
    everything = [*funcs, _callee(), _chk()]
    return build_le_image(fixups=_records(everything), patches=_patches(everything)).data


@dataclass
class Inputs:
    flat: bytearray
    fixups: list
    symbols: SymbolTable
    rows: list[FunctionRow]


def _inputs(funcs: list[Func]) -> Inputs:
    le = LE(_image(funcs))
    rows = sorted([f.row for f in [*funcs, _callee(), _chk()]], key=lambda r: r.start)
    symbols = SymbolTable.build(rows, data_ranges=data_ranges(le))
    return Inputs(le.load_flat(relocate=False), le.fixups(), symbols, rows)


def _features(f: Func, funcs: list[Func] | None = None):
    inputs = _inputs(funcs or [f])
    return features(f.row, flat=inputs.flat, fixups=inputs.fixups, symbols=inputs.symbols,
                    chk_targets={CHK})  # fmt: skip


def _reasons(f: Func, *, runtime_starts=frozenset()) -> list[str]:
    return rejections(f.row, _features(f), runtime_starts=runtime_starts)


def test_features():
    f = framed(CODE)
    feats = _features(f)
    assert feats.size == len(f.code)
    assert feats.calls == 1
    assert feats.call_targets_ok
    assert feats.abs_fixups == 1
    assert feats.data_exact
    assert not feats.jump_table
    assert not feats.string_ref
    assert not feats.straddler
    assert not feats.chk
    assert feats.frame
    assert feats.other_fixups == 0
    assert _reasons(f) == []
    # KKND weights: size + 12 per call + 30 per D_ reference
    assert score(feats) == len(f.code) + 12 + 30


def test_chk_prologue_is_seen():
    feats = _features(framed(CODE, chk=True))
    assert feats.chk
    assert feats.frame  # push ebp follows the __CHK pair


# ---- the P16 filter: each case rejected with a named reason ----


def test_filter_rejects_a_runtime_row():
    assert "runtime" in _reasons(framed(CODE, kind="runtime"))
    assert "runtime" in _reasons(framed(CODE), runtime_starts={CODE})


def test_filter_rejects_a_jump_table():
    f = framed(CODE)
    va = f.emit(struct.pack("<I", 0))  # an inline table entry after the ret
    f.fixups.append((va, SRC_OFF32, CODE_OBJ, 0))
    assert "jump table" in _reasons(f)


def test_filter_rejects_a_string_reference():
    assert "string reference" in _reasons(framed(CODE, data=DATA_STRING))


def test_filter_rejects_a_straddling_fixup():
    # the mov's off32 field crosses the page boundary at CODE + PAGE_SIZE
    start = CODE + PAGE_SIZE - 11  # the field sits 9 bytes in: CODE + PAGE_SIZE - 2
    f = framed(start)
    assert f.fixups[0][0] < CODE + PAGE_SIZE < f.fixups[0][0] + 4
    assert "straddling fixup" in _reasons(f)


def test_filter_rejects_no_call():
    assert "no call rel32" in _reasons(framed(CODE, call=None))


def test_filter_rejects_no_absolute_fixup():
    assert "no absolute fixup" in _reasons(framed(CODE, data=None))


def test_filter_rejects_a_call_to_no_function_start():
    reasons = _reasons(framed(CODE, call=CALLEE + 1))
    assert "call target is not a nameable functions.csv start" in reasons


def test_filter_rejects_a_data_target_in_no_data_object():
    assert "data target not at an exact address" in _reasons(framed(CODE, data=DATA_PAST_END))


def test_filter_rejects_a_non_off32_fixup():
    # orchestrator ruling F11: a sel16 site (or any non-off32 fixup) keeps a function out
    f = framed(CODE)
    va = f.emit(b"\x66\xb8\x00\x00")  # mov ax, <sel16>
    f.fixups.append((va + 2, SRC_SEL16, DATA_OBJ, None))
    f.emit(RET)
    feats = _features(f)
    assert feats.other_fixups == 1
    assert "non-off32 fixup" in rejections(f.row, feats, runtime_starts=frozenset())


# ---- ranking ----


def _rank(funcs: list[Func]) -> list[Candidate]:
    inputs = _inputs(funcs)
    return rank(inputs.rows, flat=inputs.flat, fixups=inputs.fixups, symbols=inputs.symbols,
                chk_targets={CHK})  # fmt: skip


def test_rank_easiest_first():
    small = framed(CODE + 0x100)
    big = framed(CODE, pad=8)
    ranked = _rank([small, big])
    assert [c.address for c in ranked] == [small.start, big.start]
    assert ranked[0].score < ranked[1].score


def test_rank_breaks_ties_by_address():
    later = framed(CODE + 0x100)
    earlier = framed(CODE)
    ranked = _rank([later, earlier])
    assert ranked[0].score == ranked[1].score
    assert [c.address for c in ranked] == [CODE, CODE + 0x100]


def test_rank_puts_a_chk_caller_after_a_non_caller():
    chk = framed(CODE, chk=True)
    plain = framed(CODE + 0x100, pad=40)  # larger, so a higher score, and a later address
    ranked = _rank([chk, plain])
    assert ranked[0].score > ranked[1].score
    assert [c.address for c in ranked] == [plain.start, chk.start]


def test_rank_skips_rejected_rows():
    ranked = _rank([framed(CODE), framed(CODE + 0x100, call=None)])
    assert [c.address for c in ranked] == [CODE]  # the callee and __CHK are rejected too


# ---- the verb ----


def _verb_setup(tmp_path: Path, funcs: list[Func]) -> list[str]:
    data = _image(funcs)
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "SYN.EXE").write_bytes(data)
    manifest = write_manifest(tmp_path / "targets.toml", {"SYN.EXE": data})
    functions = tmp_path / "functions.csv"
    rows = sorted([f.row for f in [*funcs, _callee(), _chk()]], key=lambda r: r.start)
    write_functions_csv(functions, rows, "SYN.EXE")
    return ["SYN.EXE", "--orig", str(orig), "--manifest", str(manifest),
            "--functions", str(functions)]  # fmt: skip


def test_score_verb(tmp_path: Path, capsys):
    args = _verb_setup(tmp_path, [framed(CODE), framed(CODE + 0x100, pad=4)])
    rc = cli_main(["score", *args, "--top", "1", "--json"])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    report = json.loads(captured.out)
    assert len(report["candidates"]) == 1
    candidate = report["candidates"][0]
    assert set(candidate) == {"address", "name", "size", "score", "reasons"}
    assert candidate["address"] == f"0x{CODE:08X}"
    assert candidate["name"] == f"func_{CODE:08X}"


def test_score_verb_text(tmp_path: Path, capsys):
    args = _verb_setup(tmp_path, [framed(CODE)])
    rc = cli_main(["score", *args])
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    assert f"func_{CODE:08X}" in captured.out
    assert "\\x" not in captured.out


def test_score_verb_refuses_a_bad_top(tmp_path: Path, capsys):
    args = _verb_setup(tmp_path, [framed(CODE)])
    rc = cli_main(["score", *args, "--top", "0"])
    assert rc == 1
    assert capsys.readouterr().err.startswith("reverseapoc score: error:")


def test_score_error_is_a_value_error():
    with pytest.raises(ValueError):
        raise ScoreError("x")


# ---- 05-REVIEW rows 9a, 9b, 9d ----

SMALL_PAGE = 0x800  # a page size other than wlink's 0x1000, written into LE header field 0x28
OFF32_SIZE = 4  # bytes of an off32 fixup field
# framed(): the mov's off32 field follows push ebp (1), mov ebp, esp (2), call rel32 (5) and the
# mov's own opcode byte (1).
FRAMED_FIELD = 1 + 2 + 5 + 1
FIELD_BEFORE_PAGE = 2  # the field starts this many bytes before a SMALL_PAGE boundary


def _small_page_image(funcs: list[Func]) -> bytes:
    """An LE whose header says SMALL_PAGE: every fixup record and code patch is cut at
    SMALL_PAGE (conftest.PAGE_SIZE is patched by the caller)."""
    pages = [b"", b"", b""]
    patches = {DATA + DATA_PLAIN: b"\x01\x00\x00\x00"}
    for f in funcs:
        for va, kind, obj, off in f.fixups:
            pages[(va - CODE) // SMALL_PAGE] += fixup_record(kind, (va - CODE) % SMALL_PAGE, obj,
                                                             off, off32=True)  # fmt: skip
        boundary = (f.start // SMALL_PAGE + 1) * SMALL_PAGE
        patches[f.start] = f.code[: boundary - f.start]
        if len(f.code) > boundary - f.start:
            patches[boundary] = f.code[boundary - f.start :]
    return build_le_image(fixups=pages, patches=patches).data


def test_score_takes_the_page_size_from_the_le(tmp_path: Path, monkeypatch, capsys):
    """Row 9a: `score` checks straddling against the LE header's page size, not 0x1000."""
    # build_le_image reads the page size from the conftest.PAGE_SIZE global (header field 0x28,
    # page layout and patch mapping alike) and takes no page-size parameter; patching that one
    # global keeps the three consistent without changing the shared builder.
    monkeypatch.setattr(conftest, "PAGE_SIZE", SMALL_PAGE)
    callee = Func(CODE + 0x100, RET)
    f = framed(CODE + SMALL_PAGE - FIELD_BEFORE_PAGE - FRAMED_FIELD, call=callee.start)
    field_va = f.fixups[0][0]
    last = field_va + OFF32_SIZE - 1
    assert field_va < CODE + SMALL_PAGE <= last  # crosses a SMALL_PAGE boundary ...
    assert field_va // LE_PAGE_SIZE == last // LE_PAGE_SIZE  # ... but no LE_PAGE_SIZE one
    data = _small_page_image([f, callee])
    assert LE(data).page_size == SMALL_PAGE
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "SYN.EXE").write_bytes(data)
    manifest = write_manifest(tmp_path / "targets.toml", {"SYN.EXE": data})
    functions = tmp_path / "functions.csv"
    write_functions_csv(functions, [callee.row, f.row], "SYN.EXE")
    rc = cli_main(["score", "SYN.EXE", "--orig", str(orig), "--manifest", str(manifest),
                   "--functions", str(functions), "--json"])  # fmt: skip
    captured = capsys.readouterr()
    assert rc == 0, captured.err
    report = json.loads(captured.out)
    assert report["rejected"].get("straddling fixup") == 1
    assert report["candidates"] == []


def test_top_is_checked_once(tmp_path: Path, monkeypatch, capsys):
    """Row 9b: ScoreReport.build is the one place that refuses a --top below 1."""
    args = _verb_setup(tmp_path, [framed(CODE)])
    calls = []
    build = ScoreReport.build

    def spy(*a, **k):
        calls.append(a)
        return build(*a, **k)

    monkeypatch.setattr(ScoreReport, "build", staticmethod(spy))
    rc = cli_main(["score", *args, "--top", "0"])
    err = capsys.readouterr().err
    assert rc == 1
    assert len(calls) == 1  # the refusal came from build, not from an earlier check in cli
    assert err.count("--top must be at least 1, not 0") == 1


@pytest.mark.parametrize(
    "push",
    [
        b"\x50",  # push eax
        b"\xff\x35" + struct.pack("<I", DATA_PLAIN),  # push dword ptr [DATA_PLAIN]
    ],
    ids=["register", "memory"],
)
def test_has_chk_needs_a_chk_call(push: bytes):
    """Row 9d: only `push <immediate>; call __CHK` is a stack-check prologue; a register or
    memory push before the call is not."""
    f = Func(CODE)
    f.emit(push)
    f.call(CHK)
    f.emit(PUSH_EBP + MOV_EBP_ESP)
    f.call(CALLEE)
    f.load(DATA_PLAIN)
    f.emit(POP_EBP + RET)
    assert not _features(f).chk
    assert _features(framed(CODE, chk=True)).chk  # push 0x10; call __CHK still counts
