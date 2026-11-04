"""classify.py, the failure classes and the route table.

Every pair is a clean-room encoding written here, never game bytes. A body has a real row's shape,
a saved register, a frame, the code under test, then the frame and the register back, because the
stack mask reads the prologue and the epilogue too.
"""

from __future__ import annotations

from reverseapoc import classify

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
