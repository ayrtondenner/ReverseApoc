"""classify.py, the failure classes and the route table.

Every pair is a clean-room encoding written here, never game bytes. A body has a real row's shape,
a saved register, a frame, the code under test, then the frame and the register back, because the
stack mask reads the prologue and the epilogue too.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

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
