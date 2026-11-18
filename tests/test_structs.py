"""structs.py on hand-written encodings and a stub EXE. Every encoding is written here, never game
bytes; every file is written under pytest's tmp_path."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from reverseapoc import batch, lift, structs
from reverseapoc.cli import main
from reverseapoc.functions import FunctionRow
from reverseapoc.le import Fixup
from reverseapoc.structs import ARG, OBJECT, POINTER, RESULT, Base, Field, Shape, Shapes

VA = 0x1000
ROW_SPACING = 0x100  # one row per slot, so a row's address does not depend on the one before it
SECOND = VA + ROW_SPACING
DATA_VA = 0x8000  # a made-up global, outside every row
FIELD_SIZE = 4
CALL_SIZE = 5  # e8 rel32


class StubSymbols:
    def c_name(self, va: int, *, data: bool = False) -> str:
        return f"{'D' if data else 'func'}_{va:08x}"


@dataclass
class StubExe:
    flat: bytes
    rows: tuple[FunctionRow, ...]
    fixups: tuple[Fixup, ...]
    symbols: StubSymbols
    stem: str = "stub"


def stub_exe(*codes: str, fixups: tuple[Fixup, ...] = ()) -> StubExe:
    """One game row per hex string, the first at VA, each ROW_SPACING after the one before."""
    flat = bytearray(VA + ROW_SPACING * len(codes))
    rows = []
    for n, text in enumerate(codes):
        code = bytes.fromhex(text)
        start = VA + ROW_SPACING * n
        flat[start : start + len(code)] = code
        rows.append(FunctionRow(start, start + len(code), f"row{n}", "game", "u_stub", "test"))
    return StubExe(bytes(flat), tuple(rows), fixups, StubSymbols())


def data_fixup(src_va: int, target_va: int = DATA_VA) -> Fixup:
    return Fixup(src_va, 7, target_va, 2, target_va, FIELD_SIZE)


def call_to(src: int, target: int) -> str:
    """`call target` at `src`, as hex."""
    return "e8" + (target - (src + CALL_SIZE)).to_bytes(4, "little", signed=True).hex()


@pytest.fixture(autouse=True)
def fresh_lifter(monkeypatch, tmp_path):
    """lift's caches key on a stem and on id(exe): a stub must never read stale rows or write
    the real census."""
    monkeypatch.setattr(lift, "CACHE_DIR", tmp_path / "lift")
    for cache in (lift._RESULT_USED, lift._BUILDING, lift._INDEX, lift._FIXUPS):
        cache.clear()
    yield
    for cache in (lift._RESULT_USED, lift._BUILDING, lift._INDEX, lift._FIXUPS):
        cache.clear()


def fields(shape: Shape) -> list[tuple[int, int, str]]:
    return [(f.offset, f.width, f.sign) for f in shape.fields]


def only(shapes: Shapes) -> Shape:
    assert len(shapes.shapes) == 1, shapes.shapes
    return shapes.shapes[0]


# ---- one function ----


def test_an_argument_dereferenced_at_two_offsets_is_a_shape():
    # mov ecx, [eax + 4]; movsx edx, word ptr [eax + 8]; ret
    shapes = structs.analyze(stub_exe("8b4804 0fbf5008 c3"))
    shape = only(shapes)
    assert shape.name == "shape_func_00001000_arg0"
    assert shape.bases == (Base(ARG, VA, 0),)
    assert fields(shape) == [(4, 4, ""), (8, 2, "s")]
    assert shape.functions == (VA,)
    assert shape.size == 10
    assert (shapes.rows, shapes.skipped, shapes.bases) == (1, 0, 1)


def test_one_offset_is_no_shape_but_its_base_is_seen():
    shapes = structs.analyze(stub_exe("8b4804 c3"))  # mov ecx, [eax + 4]; ret
    assert shapes.shapes == ()
    assert shapes.bases == 1


def test_copies_and_lea_carry_the_base_and_its_offset():
    # mov esi, eax; mov al, [esi + 12]; lea ebx, [esi + 16]; mov eax, [ebx + 4]; ret
    shape = only(structs.analyze(stub_exe("89c6 8a460c 8d5e10 8b4304 c3")))
    assert fields(shape) == [(12, 1, ""), (20, 4, "")]


def test_add_moves_the_offset_and_a_write_ends_the_base():
    # add eax, 8; mov ecx, [eax + 4]; mov edx, [eax]; mov eax, 0; mov ecx, [eax + 32]; ret
    shape = only(structs.analyze(stub_exe("83c008 8b4804 8b10 b800000000 8b4820 c3")))
    assert fields(shape) == [(8, 4, ""), (12, 4, "")]


def test_movzx_and_x87_say_how_a_field_is_read():
    # movzx ecx, byte ptr [eax + 1]; fld qword ptr [eax + 8]; fild dword ptr [eax + 16]; ret
    shape = only(structs.analyze(stub_exe("0fb64801 dd4008 db4010 c3")))
    assert fields(shape) == [(1, 1, "u"), (8, 8, "f"), (16, 4, "s")]


def test_an_indexed_access_records_its_scale():
    # mov ecx, [eax + ebx*4]; mov edx, [eax + 64]; ret
    shape = only(structs.analyze(stub_exe("8b0c98 8b5040 c3")))
    assert [(f.offset, f.strides) for f in shape.fields] == [(0, (4,)), (64, ())]


def test_a_string_move_is_no_field_access():
    # mov esi, eax; movsd; mov ecx, [eax + 4]; mov ecx, [eax + 8]; ret
    shape = only(structs.analyze(stub_exe("89c6 a5 8b4804 8b4808 c3")))
    assert fields(shape) == [(4, 4, ""), (8, 4, "")]


def test_a_displacement_with_a_fixup_is_an_array_not_a_field():
    # mov ecx, [eax + D]; mov edx, [eax + 4]; ret: the first displacement is an address
    exe = stub_exe("8b8800000000 8b5004 c3", fixups=(data_fixup(VA + 2),))
    assert structs.analyze(exe).shapes == ()


@pytest.mark.parametrize(("middle", "kept"), [("89d0", False), ("89d1", True)])
def test_a_join_keeps_a_base_only_when_every_path_agrees(middle, kept):
    # test edx, edx; je L; <middle>; L: mov ecx, [eax + 4]; mov ecx, [eax + 8]; ret
    shapes = structs.analyze(stub_exe(f"85d2 7402 {middle} 8b4804 8b4808 c3"))
    assert len(shapes.shapes) == (1 if kept else 0)


def test_a_row_the_lifter_refuses_is_skipped_and_counted():
    # push ebp; mov ebp, esp; pop ebp; ret (an ebp frame)
    shapes = structs.analyze(stub_exe("55 89e5 5d c3", "8b4804 8b4808 c3"))
    assert (shapes.rows, shapes.skipped) == (2, 1)
    assert len(shapes.shapes) == 1


# ---- across functions ----


def test_an_argument_passed_on_shares_the_callees_fields():
    # row0: mov edx, [eax + 4]; call row1; ret.  row1: mov eax, [eax + 8]; ret
    caller = f"8b5004 {call_to(VA + 3, SECOND)} c3"
    shapes = structs.analyze(stub_exe(caller, "8b4008 c3"))
    shape = only(shapes)
    assert shape.name == "shape_func_00001000_arg0"
    assert shape.bases == (Base(ARG, VA, 0), Base(ARG, SECOND, 0))
    assert fields(shape) == [(4, 4, ""), (8, 4, "")]
    assert shape.functions == (VA, SECOND)
    assert shapes.bases == 2
    assert shapes.links == 1  # row0's own result: no caller reads it


def test_a_register_the_callee_does_not_take_is_no_link():
    # row0: mov ecx, [ebx + 4]; mov ecx, [ebx + 8]; mov eax, 1; call row1; ret (ebx survives
    # the call). row1: mov ecx, [eax + 4]; mov ecx, [eax + 8]; ret (it takes eax only)
    caller = f"8b4b04 8b4b08 b801000000 {call_to(VA + 11, SECOND)} c3"
    shapes = structs.analyze(stub_exe(caller, "8b4804 8b4808 c3"))
    assert [shape.bases for shape in shapes.shapes] == [(Base(ARG, VA, 2),),
                                                        (Base(ARG, SECOND, 0),)]  # fmt: skip


def test_an_argument_no_function_dereferences_joins_nothing():
    # row0 and row1 each read their eax at +4 and +8 and pass it to row2, which reads only
    # ebx (so its signature takes eax and edx too): row2's eax must not merge the two structs.
    # row2: mov ecx, [ebx]; ret
    third = VA + 2 * ROW_SPACING
    first = f"8b4804 8b4808 {call_to(VA + 6, third)} c3"
    second = f"8b4804 8b4808 {call_to(SECOND + 6, third)} c3"
    shapes = structs.analyze(stub_exe(first, second, "8b0b c3"))
    assert [shape.bases for shape in shapes.shapes] == [(Base(ARG, VA, 0),),
                                                        (Base(ARG, SECOND, 0),)]  # fmt: skip
    assert shapes.links == 2  # only the ebx each passes on, which row2 does read


def test_an_argument_passed_on_to_one_that_reads_it_still_joins():
    # row0: mov ecx, [eax + 4]; call row1; ret.  row1: call row2; ret.  row2: mov ecx, [eax + 8];
    # ret: row1 never reads its eax, but row2 does
    third = VA + 2 * ROW_SPACING
    first = f"8b4804 {call_to(VA + 3, SECOND)} c3"
    shape = only(structs.analyze(stub_exe(first, f"{call_to(SECOND, third)} c3", "8b4808 c3")))
    assert shape.bases == (Base(ARG, VA, 0), Base(ARG, SECOND, 0), Base(ARG, third, 0))
    assert fields(shape) == [(4, 4, ""), (8, 4, "")]


def test_a_link_whose_widths_disagree_is_refused():
    # row0: mov ecx, [eax + 4]; mov ecx, [eax + 8]; call row1; ret
    # row1: mov cl, [eax + 4]; mov ecx, [eax + 8]; ret: a byte where row0 reads a dword
    caller = f"8b4804 8b4808 {call_to(VA + 6, SECOND)} c3"
    shapes = structs.analyze(stub_exe(caller, "8a4804 8b4808 c3"))
    assert len(shapes.shapes) == 2
    assert (shapes.links, shapes.refused) == (0, 1)


def test_a_global_pointer_read_in_two_functions_is_one_shape():
    # row0: mov eax, [D]; mov ecx, [eax + 4]; ret.  row1: mov eax, [D]; mov edx, [eax + 8]; ret
    exe = stub_exe("a100000000 8b4804 c3", "a100000000 8b5008 c3",
                   fixups=(data_fixup(VA + 1), data_fixup(SECOND + 1)))  # fmt: skip
    shape = only(structs.analyze(exe))
    assert shape.name == "shape_D_00008000_target"
    assert shape.bases == (Base(POINTER, DATA_VA),)
    assert shape.functions == (VA, SECOND)


def test_the_address_of_a_global_passed_on_is_its_object():
    # row0: mov eax, offset D; call row1; ret.  row1: mov ecx, [eax + 4]; mov ecx, [eax + 8]; ret
    caller = f"b800000000 {call_to(VA + 5, SECOND)} c3"
    exe = stub_exe(caller, "8b4804 8b4808 c3", fixups=(data_fixup(VA + 1),))
    shape = only(structs.analyze(exe))
    assert shape.name == "shape_D_00008000"
    assert shape.bases == (Base(OBJECT, DATA_VA), Base(ARG, SECOND, 0))


def test_a_returned_pointer_joins_what_the_callee_returns():
    # row0: call row1; mov ecx, [eax + 4]; mov edx, [eax + 8]; ret.  row1: mov eax, [D]; ret
    caller = f"{call_to(VA, SECOND)} 8b4804 8b5008 c3"
    exe = stub_exe(caller, "a100000000 c3", fixups=(data_fixup(SECOND + 1),))
    shape = only(structs.analyze(exe))
    assert shape.bases == (Base(POINTER, DATA_VA), Base(RESULT, SECOND))
    assert shape.functions == (VA,)


# ---- the header ----

A, B = 0x1000, 0x1100


def made_up_shapes() -> Shapes:
    shape = Shape("shape_made_up", (Base(ARG, A, 0), Base(ARG, B, 1)), (
        Field(0, 4, "", (), (A,)),
        Field(4, 2, "s", (), (A, B)),
        Field(8, 4, "", (), (A, B)),
        Field(8, 1, "u", (), (A,)),
        Field(10, 2, "", (), (B,)),
        Field(16, 8, "f", (4,), (A,)),
    ))  # fmt: skip
    return Shapes("stub", (shape,), rows=2, skipped=0, bases=2, links=1, refused=0)


def test_the_header_lays_the_fields_out_with_padding():
    text = structs.header(made_up_shapes(), matched=frozenset({A}))
    body = text[text.index("struct shape_made_up {") :]
    lines = [line.split(";")[0].strip() for line in body.splitlines()[1:]
             if ";" in line and not line.strip().startswith(("}", "/*"))]  # fmt: skip
    assert lines == ["int f_0000", "short f_0004", "unsigned char pad_0006[2]", "int f_0008",
                     "unsigned char pad_000C[4]", "double f_0010"]  # fmt: skip
    assert "+0x0008: also 1 byte" in text
    assert "+0x000A: 2 bytes, overlaps (sign unknown; 1 function (0 matched))" in text
    assert "2 functions (1 matched)" in text
    assert "//" not in text
    assert text.startswith("/*") and "#ifndef" in text
    assert text.rstrip().endswith("#endif /* REVERSEAPOC_STRUCTS_STUB_H */")


def test_shapes_round_trip_through_json(tmp_path):
    shapes = made_up_shapes()
    header, data = structs.write(shapes, frozenset({A}), repo=tmp_path)
    assert header == tmp_path / "build" / "structs" / "stub" / "structs.h"
    assert data == structs.shapes_path(tmp_path, "stub")
    assert structs.load(tmp_path, "stub") == shapes


def test_a_missing_file_loads_as_none(tmp_path):
    assert structs.load(tmp_path, "stub") is None


@pytest.mark.parametrize("text", ["{", "[]", '{"format": 0, "exe": "stub", "shapes": []}',
                                  '{"format": 1, "exe": "stub", "shapes": [{"name": 1}]}'])
def test_a_malformed_file_is_an_error_naming_it(tmp_path, text):
    path = structs.shapes_path(tmp_path, "stub")
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(structs.StructsError, match="structs.json"):
        structs.load(tmp_path, "stub")


# ---- the pack section ----


def test_the_section_shows_the_shapes_the_function_touches():
    body = structs.section(made_up_shapes(), B, frozenset({A}))
    assert "### shape_made_up: 6 fields, 2 functions (1 matched)" in body
    assert "build/structs/stub/structs.h" in body
    assert "- +0x0004 2 short (2 functions, this one)" in body
    assert "- +0x0000 4 int (1 function)" in body
    assert "- +0x000A 2 short (1 function, sign unknown, this one)" in body
    assert "bases: 0x00001000 arg 0, 0x00001100 arg 1" in body


def test_the_section_says_none_for_an_untouched_function():
    assert structs.section(made_up_shapes(), 0x9999, frozenset()) == "none"


def test_the_section_says_how_to_build_missing_shapes():
    body = structs.section(None, A, frozenset())
    assert "reverseapoc structs" in body and "structs.json" in body


def test_the_section_cuts_long_field_lists():
    many = tuple(Field(4 * n, 4, "", (), (A,)) for n in range(structs.FIELDS_TOP + 3))
    shapes = Shapes("stub", (Shape("shape_long", (Base(ARG, A, 0),), many),), rows=1,
                    skipped=0, bases=1, links=0, refused=0)  # fmt: skip
    body = structs.section(shapes, A, frozenset())
    assert body.count("\n- +0x") == structs.FIELDS_TOP
    assert "... 3 more fields in build/structs/stub/structs.h" in body


# ---- the verb ----


def test_the_verb_writes_the_header_and_prints_counts(monkeypatch, capsys, tmp_path):
    caller = f"8b5004 {call_to(VA + 3, SECOND)} c3"
    exe = stub_exe(caller, "8b4008 c3")
    monkeypatch.setattr(batch, "load_exe_inputs", lambda *_args, **_kwargs: exe)
    assert main(["structs", "stub", "--repo", str(tmp_path), "--config", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "2 rows read, 0 skipped; 2 base pointers seen; 1 link merged, 0 refused" in out
    assert "1 struct shape" in out
    assert "shape_func_00001000_arg0: 2 fields, 2 functions (0 matched)" in out
    header = Path(tmp_path, "build", "structs", "stub", "structs.h")
    assert "struct shape_func_00001000_arg0 {" in header.read_text(encoding="utf-8")
    saved = json.loads(structs.shapes_path(tmp_path, "stub").read_text(encoding="utf-8"))
    assert saved["exe"] == "stub"
