"""classify.py, the failure classes and the route table.

Every pair is a clean-room encoding written here, never game bytes. A body has a real row's shape,
a saved register, a frame, the code under test, then the frame and the register back, because the
stack mask reads the prologue and the epilogue too.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from relocpair import CALLEES, CODE_BASE, call, game_row, original, our_object, table
from reverseapoc import batch, classify

VA = 0x1000
NO_RELOCS: set[int] = set()

LOAD_SLOT_4 = "8b442404"  # mov eax, [esp + 4]
LOAD_SLOT_8 = "8b442408"  # mov eax, [esp + 8]


def body(code: str, frame: int = 0x10) -> bytes:
    """push ebx; sub esp, frame; `code`; add esp, frame; pop ebx; ret."""
    return bytes.fromhex(f"53 83ec{frame:02x} {code} 83c4{frame:02x} 5b c3")


def record(**fields) -> dict:
    """A compiled, not-exact record, as far as the classifier reads one."""
    return {"compiled": True, "exact": False, "exact_trim": False, "score": 50.0,
            "key": "mov R, R | mov R, R", **fields}  # fmt: skip


def classed(ours: bytes, theirs: bytes, **options) -> str:
    return classify.classify_pair(ours, theirs, VA, NO_RELOCS, **options)


def test_stack_offsets_alone_are_class_slot():
    assert classed(body(LOAD_SLOT_4), body(LOAD_SLOT_8)) == "slot"


def test_slot_routes_to_the_search():
    assert classify.route(record(score=95.0), "slot") == "search"


def test_exact_routes_to_the_converter():
    labelled = classify.with_class(record(exact=True, score=100.0), None, VA, None)
    assert labelled["route"] == "converter"
    assert "class" not in labelled


# ---- the other classes ----

FILLER = bytes.fromhex("8bc0")  # mov eax, eax
LOAD_SLOT_0 = "8b0424"  # mov eax, [esp]
COPY_ESP = "89e0"  # mov eax, esp, the address of slot 0
LEA_SLOT_4 = "8d442404"  # lea eax, [esp + 4]
MOVE_EBX_TO_EAX = "89d8"
MOVE_EBX_TO_EDX = "89da"
INC_EAX = "40"
DEC_EAX = "48"
JE = "7402"  # je past the two bytes after it
JNE = "7502"
RELOCATED = {"ours": "b801000000", "theirs": "b802000000"}  # mov eax, imm32
RELOCATED_FIELD = set(range(VA + 5, VA + 9))  # the imm32, behind push ebx and sub esp, 0x10


def ebp_body(code: str, frame: int = 0x10) -> bytes:
    """push ebp; mov ebp, esp; sub esp, frame; `code`; mov esp, ebp; pop ebp; ret."""
    return bytes.fromhex(f"55 89e5 83ec{frame:02x} {code} 89ec 5d c3")


def test_exact_trim_is_class_tail():
    ours = body(MOVE_EBX_TO_EAX)
    theirs = body(MOVE_EBX_TO_EDX)
    assert classed(ours, theirs, exact_trim=True) == "tail"


@pytest.mark.parametrize("swap", [False, True])
def test_a_prefix_is_class_tail(swap):
    pair = (body(LOAD_SLOT_4), body(LOAD_SLOT_4) + FILLER)
    assert classed(*(reversed(pair) if swap else pair)) == "tail"


def test_equal_tokens_are_not_class_tail():
    """R10d: the prefix is strict. A relocation-only failure has equal token lists, and no stack
    offset differs either, so it is not class slot and no tool's class fits it."""
    ours, theirs = body(RELOCATED["ours"]), body(RELOCATED["theirs"])
    assert classify.classify_pair(ours, theirs, VA, RELOCATED_FIELD) == "mixed"


def test_equal_tokens_of_different_lengths_are_class_size():
    short_jump, near_jump = "eb00", "e900000000"  # jmp to the next instruction, two encodings
    assert classed(body(short_jump), body(near_jump)) == "size"


def test_equal_but_for_the_frame_is_class_size():
    assert classed(body(LOAD_SLOT_4, 0x10), body(LOAD_SLOT_4, 0x14)) == "size"


def test_a_second_sub_esp_is_part_of_the_frame():
    ours = body(f"83ec04 {LOAD_SLOT_4} 83c404")
    theirs = body(f"83ec08 {LOAD_SLOT_4} 83c408")
    assert classed(ours, theirs) == "size"


def test_a_different_frame_is_class_size_whatever_else_differs():
    assert classed(body(MOVE_EBX_TO_EAX, 0x10), body(MOVE_EBX_TO_EDX, 0x14)) == "size"
    assert classed(body(INC_EAX, 0x10), body(DEC_EAX, 0x14)) == "size"


def test_different_length_is_class_size():
    assert classed(body(INC_EAX), body(DEC_EAX + DEC_EAX)) == "size"


@pytest.mark.parametrize(
    ("ours", "theirs"),
    [
        (body(LOAD_SLOT_0), body(LOAD_SLOT_4)),  # a bare [esp], one byte shorter
        (body(COPY_ESP), body(LEA_SLOT_4)),  # the two spellings of a slot's address
        (ebp_body("8b45fc"), ebp_body("8b45f8")),  # [ebp - 4] and [ebp - 8] under an ebp frame
    ],
)
def test_every_spelling_of_a_stack_slot_is_class_slot(ours, theirs):
    assert classed(ours, theirs) == "slot"


def test_an_ebp_frame_of_another_size_is_class_size():
    assert classed(ebp_body("8b45fc", 0x10), ebp_body("8b45fc", 0x14)) == "size"


def test_register_names_alone_are_class_register():
    assert classed(body(MOVE_EBX_TO_EAX), body(MOVE_EBX_TO_EDX)) == "register"


def test_stack_and_register_together_are_class_register():
    ours = body(f"{LOAD_SLOT_4} {MOVE_EBX_TO_EAX}")
    theirs = body(f"{LOAD_SLOT_8} {MOVE_EBX_TO_EDX}")
    assert classed(ours, theirs) == "register"


def test_esp_is_no_register_choice():
    """`[esp + N]` must not read as a relocated `[ebx + N]`: no allocator picks esp."""
    theirs = body("8b8345230100")  # mov eax, [ebx + 0x12345], its displacement relocated
    field = set(range(VA + 6, VA + 10))
    assert classify.classify_pair(body(LOAD_SLOT_4), theirs, VA, field) == "size"


def test_a_jcc_difference_is_class_branch():
    tail = f"{MOVE_EBX_TO_EAX} {INC_EAX}"
    assert classed(body(f"{JE} {tail}"), body(f"{JNE} {tail}")) == "branch"


def test_a_jump_and_a_register_together_are_class_branch():
    ours = body(f"{JE} {MOVE_EBX_TO_EAX}")
    theirs = body(f"{JNE} {MOVE_EBX_TO_EDX}")
    assert classed(ours, theirs) == "branch"


def test_nothing_fits_is_class_mixed():
    assert classed(body(INC_EAX), body(DEC_EAX)) == "mixed"


def test_no_function_in_the_object_is_class_mixed(monkeypatch):
    monkeypatch.setattr(batch, "function_body", lambda *a: "not defined")
    compiled = SimpleNamespace(job=SimpleNamespace(obj=None))
    labelled = classify.with_class(record(key="not defined", score=0.0), None, VA, compiled)
    assert (labelled["class"], labelled["route"]) == ("mixed", "agent")


# ---- the other routes ----


def test_mixed_routes_to_an_agent():
    assert classify.route(record(), "mixed") == "agent"


def test_near_routes_to_the_converter():
    assert classify.route(record(score=classify.NEAR), "size") == "converter"
    assert classify.route(record(score=classify.NEAR - 0.01), "size") == "agent"


def test_a_hole_draft_routes_to_an_agent():
    assert classify.route(record(score=95.0), "slot", hole=True) == "agent"


def test_the_best_cell_is_exact_then_the_higher_raw_score():
    near, low, exact = record(score=92.0), record(score=40.0), record(exact=True, score=99.0)
    assert classify.best_cell([low, near]) is near
    assert classify.best_cell([near, exact]) is exact


# ---- what a mask must not hide from class slot ----

JE_OVER_THE_MOVE = "7402"  # lands on INC_EAX
JE_OVER_BOTH = "7403"  # lands on the load after INC_EAX
JMP_RELOCATED = {"ours": "e900000000", "theirs": "e940000000"}  # rel32, at RELOCATED_FIELD


def test_another_jump_target_is_not_class_slot():
    tail = f"{MOVE_EBX_TO_EAX} {INC_EAX}"
    ours = body(f"{JE_OVER_THE_MOVE} {tail} {LOAD_SLOT_4}")
    theirs = body(f"{JE_OVER_BOTH} {tail} {LOAD_SLOT_8}")
    assert classed(ours, theirs) == "mixed"


def test_a_jump_over_a_shifted_slot_is_class_slot():
    """The bare `[esp]` is one byte shorter, so the jump's bytes differ and its target does not."""
    ours = body(f"7403 {LOAD_SLOT_0} {INC_EAX}")
    theirs = body(f"7404 {LOAD_SLOT_4} {INC_EAX}")
    assert classed(ours, theirs) == "slot"


def test_a_relocated_jump_is_left_to_the_relocation_check():
    """Our rel32 is a placeholder until it links, so its target says nothing."""
    ours = body(f"{JMP_RELOCATED['ours']} {LOAD_SLOT_4}")
    theirs = body(f"{JMP_RELOCATED['theirs']} {LOAD_SLOT_8}")
    assert classify.classify_pair(ours, theirs, VA, RELOCATED_FIELD) == "slot"


@pytest.mark.parametrize(
    ("ours", "theirs"),
    [
        (body(f"{LOAD_SLOT_4} 83c408"), body(f"{LOAD_SLOT_4} 83c40c")),
        (bytes.fromhex("53 83ec10 83c410 5b c3"), bytes.fromhex("53 83ec10 83c414 5b c3")),
    ],
    ids=["after a call", "in the epilogue"],
)
def test_an_add_esp_difference_alone_is_not_class_slot(ours, theirs):
    assert classed(ours, theirs) == "size"


# ---- what decoded is all a class may read ----

UNREADABLE = "ffff"  # capstone stops here


@pytest.mark.parametrize("swap", [False, True])
def test_an_empty_body_is_not_class_tail(swap):
    pair = (b"", body(LOAD_SLOT_4))
    assert classed(*(reversed(pair) if swap else pair)) == "size"


def test_a_decode_that_stops_short_is_not_class_tail():
    """Equal lengths, and `theirs` reads as `ours` cut after the frame."""
    ours = body(f"{INC_EAX} {INC_EAX} {LOAD_SLOT_4}")
    theirs = body(f"{UNREADABLE} {LOAD_SLOT_4}")
    assert classed(ours, theirs) == "mixed"


@pytest.mark.parametrize(
    ("after", "klass"), [(DEC_EAX, "mixed"), (DEC_EAX * 3, "size")], ids=["equal", "longer"]
)
def test_a_decode_that_stops_short_is_not_class_slot(after, klass):
    """Only a stack offset differs before the stop, and other code follows it."""
    ours = body(f"{LOAD_SLOT_4} {UNREADABLE} {INC_EAX}")
    theirs = body(f"{LOAD_SLOT_8} {UNREADABLE} {after}")
    assert classed(ours, theirs) == klass


def test_exact_trim_needs_no_decode():
    """exact_trim is check's own verdict on the bytes, so it stands on an unreadable body."""
    assert classed(body(UNREADABLE), body(INC_EAX), exact_trim=True) == "tail"


# ---- the class of an object, through the real relocation check ----

ROW = CODE_BASE + 0x30  # clear of the CALLEES rows
CALLED, OTHER = CALLEES[1], CALLEES[0]
CALL_AT = 4  # behind push ebx and sub esp, 0x10
CALL_FIELD = CALL_AT + 1
PLACEHOLDER = "e800000000"  # a call until it links
LINKED = b"\xe8" + (CALLED.start - (ROW + CALL_FIELD + 4)).to_bytes(4, "little", signed=True)


def class_of_object(tmp_path, ours: bytes, theirs: bytes, callee: str | None = None) -> str:
    """`_class_of` with `ours` in an OMF object on disk and `theirs` as the row of a synthetic EXE.
    `callee` is the extern our call at CALL_FIELD names."""
    row = game_row(ROW, ROW + len(theirs))
    orig = original({ROW: theirs})
    symbols = table(row)
    exe = SimpleNamespace(rows=(row,), flat=orig.flat, fixups=tuple(orig.fixups), symbols=symbols,
                          target=SimpleNamespace(name="SYNTH.EXE"))  # fmt: skip
    obj = tmp_path / "f.obj"
    fixups, externs = ([call(CALL_FIELD, 1)], [callee]) if callee else ([], [])
    publics = [(symbols.linker_name(ROW), 0)]
    obj.write_bytes(our_object(ours, fixups, externs, publics=publics))
    return classify._class_of(exe, ROW, SimpleNamespace(job=SimpleNamespace(obj=obj)), False)


def test_a_stack_offset_fails_the_relocation_check_and_stays_class_slot(tmp_path):
    """The check fails on any byte outside a field, so `reloc.ok` alone would end class slot."""
    assert class_of_object(tmp_path, body(LOAD_SLOT_4), body(LOAD_SLOT_8)) == "slot"


def test_a_shifted_body_with_no_relocation_stays_class_slot(tmp_path):
    assert class_of_object(tmp_path, body(LOAD_SLOT_0), body(LOAD_SLOT_4)) == "slot"


def test_a_right_relocation_stays_class_slot(tmp_path):
    ours = body(f"{PLACEHOLDER} {LOAD_SLOT_4}")
    theirs = body(f"{LINKED.hex()} {LOAD_SLOT_8}")
    assert class_of_object(tmp_path, ours, theirs, f"{CALLED.name}_") == "slot"


def test_a_wrong_relocation_is_not_class_slot(tmp_path):
    ours = body(f"{PLACEHOLDER} {LOAD_SLOT_4}")
    theirs = body(f"{LINKED.hex()} {LOAD_SLOT_8}")
    assert class_of_object(tmp_path, ours, theirs, f"{OTHER.name}_") == "mixed"


def test_a_shift_leaves_a_relocation_unread_so_it_is_not_class_slot(tmp_path):
    """Another length stops the check before any field, so the mask may hide a wrong target."""
    ours = body(f"{PLACEHOLDER} {LOAD_SLOT_0}")
    theirs = body(f"{LINKED.hex()} {LOAD_SLOT_4}")
    assert class_of_object(tmp_path, ours, theirs, f"{CALLED.name}_") == "mixed"


# ---- a row's trailing filler changes no class ----


@pytest.mark.parametrize(
    ("ours", "theirs", "klass"),
    [
        (body(LOAD_SLOT_4), body(LOAD_SLOT_4), "tail"),
        (body(LOAD_SLOT_4), body(LOAD_SLOT_8), "slot"),
        (body(MOVE_EBX_TO_EAX), body(MOVE_EBX_TO_EDX), "register"),
        (body(f"{JE} {MOVE_EBX_TO_EAX} {INC_EAX}"), body(f"{JNE} {MOVE_EBX_TO_EAX} {INC_EAX}"),
         "branch"),
        (body(LOAD_SLOT_4, 0x10), body(LOAD_SLOT_4, 0x14), "size"),
        (body(INC_EAX), body(DEC_EAX + DEC_EAX), "size"),
        (body(INC_EAX), body(DEC_EAX), "mixed"),
    ],
    ids=["tail", "slot", "register", "branch", "frame", "length", "mixed"],
)  # fmt: skip
def test_a_filler_tail_changes_no_class(tmp_path, ours, theirs, klass):
    assert class_of_object(tmp_path, ours, theirs + FILLER) == klass


def test_an_undecodable_tail_is_not_cut(tmp_path):
    """Decode stops at the unread bytes, so the filler before them is no row's end."""
    theirs = body(LOAD_SLOT_8) + FILLER + bytes.fromhex(UNREADABLE)
    assert class_of_object(tmp_path, body(LOAD_SLOT_4), theirs) == "size"


def test_a_right_relocation_on_a_filler_row_is_class_slot(tmp_path):
    """18 bytes and 14 of filler end the row 16-aligned at ROW, so the filler rule accepts it."""
    ours = body(f"{PLACEHOLDER} {LOAD_SLOT_4}")
    theirs = body(f"{LINKED.hex()} {LOAD_SLOT_8}") + FILLER * 7
    assert class_of_object(tmp_path, ours, theirs, f"{CALLED.name}_") == "slot"


def test_a_wrong_relocation_on_a_filler_row_is_not_class_slot(tmp_path):
    ours = body(f"{PLACEHOLDER} {LOAD_SLOT_4}")
    theirs = body(f"{LINKED.hex()} {LOAD_SLOT_8}") + FILLER * 7
    assert class_of_object(tmp_path, ours, theirs, f"{OTHER.name}_") == "mixed"


def test_a_relocation_on_a_row_ending_off_16_stays_mixed(tmp_path):
    """The row's end is off 16, so the length problem stops the check before it reads the fields,
    and the mask may hide a wrong target."""
    ours = body(f"{PLACEHOLDER} {LOAD_SLOT_4}")
    theirs = body(f"{LINKED.hex()} {LOAD_SLOT_8}") + FILLER
    assert class_of_object(tmp_path, ours, theirs, f"{CALLED.name}_") == "mixed"


def test_classify_pair_still_reads_a_filler_tail_as_another_length():
    """The cut lives in _class_of, and classify_pair's contract does not change."""
    assert classed(body(LOAD_SLOT_4), body(LOAD_SLOT_8) + FILLER) == "size"
