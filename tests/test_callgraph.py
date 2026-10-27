"""The typed call graph (DEC-01, D-02): synthetic LE images only, every byte and address made up.

The images use the conftest objects: code at 0x10000 (two pages), data at 0x20000 (one short page).
Each test builds the rows it needs and patches made-up instructions over the page fill.
"""

from __future__ import annotations

import struct
from types import SimpleNamespace

import pytest

from conftest import build_le_image, fixup_record
from reverseapoc import callgraph, contextpack
from reverseapoc.callgraph import DIRECT, POINTER, CallGraph, Edge, closure
from reverseapoc.functions import KIND_GAME, KIND_RUNTIME, KIND_THUNK, FunctionRow
from reverseapoc.le import LE, SRC_OFF32

CODE = 0x10000  # object 1
DATA = 0x20000  # object 2
CODE_RANGE = (CODE, CODE + 0x1800)
DATA_RANGE = (DATA, DATA + 0x3000)
_CALL = b"\xe8"  # call rel32
_JMP = b"\xe9"  # jmp rel32
_PUSH_IMM32 = b"\x68"  # push imm32
_RET = b"\xc3"
_NOP = b"\x90"
_INSN_REL32 = 5  # opcode + rel32
_IMM_FIELD = 1  # the imm32 of push sits one byte into the instruction


def _rel(opcode: bytes, at: int, to: int) -> bytes:
    return opcode + struct.pack("<i", to - (at + _INSN_REL32))


def _row(start: int, end: int, kind: str = KIND_GAME) -> FunctionRow:
    return FunctionRow(start, end, f"func_{start:08X}", kind, f"u_{start:08x}", "call")


def _code_fixup(field: int, target: int) -> bytes:
    """One off32 fixup record on the first code page, field -> a code address."""
    return fixup_record(SRC_OFF32, field - CODE, 1, target - CODE)


def _inputs(patches: dict[int, bytes], code_fixups: bytes, data_fixups: bytes = b""):
    image = build_le_image(fixups=[code_fixups, b"", data_fixups], patches=patches)
    le = LE(image.data)
    return le, le.load_flat(relocate=False), le.fixups()


def _padded(code: bytes, size: int) -> bytes:
    return code + _NOP * (size - len(code))


def _edge_set(graph: CallGraph) -> set[tuple[int, int, str]]:
    return {(e.src, e.dst, e.kind) for edges in graph.edges.values() for e in edges}


def _assert_edges(graph: CallGraph, expected: set[tuple[int, int, str]]) -> None:
    """The exact typed edge set: an edge missing or extra fails."""
    assert _edge_set(graph) == expected


# ---- task 1 image: direct calls, a tail jump, a code pointer, a runtime row, a thunk ----

A = CODE  # push offset D; call B; call R; jmp C
B = CODE + 0x20  # call F; ret
C = CODE + 0x40  # ret
D = CODE + 0x60  # call TH; ret
E = CODE + 0x80  # ret
R = CODE + 0xA0  # runtime: call E; ret
TH = CODE + 0xC0  # thunk: jmp E
F = CODE + 0xE0  # ret
END = CODE + 0x100
ROWS = [
    _row(A, B), _row(B, C), _row(C, D), _row(D, E), _row(E, R),
    _row(R, TH, KIND_RUNTIME), _row(TH, F, KIND_THUNK), _row(F, END),
]  # fmt: skip
PATCHES = {
    A: _padded(_PUSH_IMM32 + struct.pack("<I", D - CODE)
               + _rel(_CALL, A + 5, B) + _rel(_CALL, A + 10, R) + _rel(_JMP, A + 15, C), 0x20),
    B: _padded(_rel(_CALL, B, F) + _RET, 0x20),
    C: _padded(_RET, 0x20),
    D: _padded(_rel(_CALL, D, TH) + _RET, 0x20),
    E: _padded(_RET, 0x20),
    R: _padded(_rel(_CALL, R, E) + _RET, 0x20),
    TH: _padded(_rel(_JMP, TH, E), 0x20),
    F: _padded(_RET, 0x20),
}  # fmt: skip
FIXUPS = _code_fixup(A + _IMM_FIELD, D)  # push offset D


def _graph() -> CallGraph:
    _, flat, fixups = _inputs(PATCHES, FIXUPS)
    return CallGraph.build(ROWS, flat, fixups, code=CODE_RANGE, data=DATA_RANGE)


def test_edge_kinds_weakest_last():
    assert callgraph.EDGE_KINDS == ("direct", "pointer", "table", "midrow", "hand")
    assert (callgraph.DIRECT, callgraph.POINTER, callgraph.TABLE, callgraph.MIDROW,
            callgraph.HAND) == callgraph.EDGE_KINDS  # fmt: skip


def test_direct_and_tail_edges():
    graph = _graph()
    assert Edge(A, B, DIRECT) in graph.callees(A)
    assert Edge(A, C, DIRECT) in graph.callees(A)  # the tail jump
    _, flat, fixups = _inputs(PATCHES, FIXUPS)
    index = contextpack.CallIndex.build(ROWS, flat, fixups)
    walked = {row.start for row in ROWS if row.kind in (KIND_GAME, KIND_THUNK)}
    from_index = {(src, dst) for src, dsts in index.callees.items()
                  for dst in dsts if dst in walked}  # fmt: skip
    direct = {(src, dst) for src, dst, kind in _edge_set(graph) if kind == DIRECT}
    assert direct == from_index


def test_pointer_edge():
    assert Edge(A, D, POINTER) in _graph().callees(A)


def test_runtime_row_is_a_leaf():
    graph = _graph()
    assert all(edge.dst != R for edges in graph.edges.values() for edge in edges)
    assert graph.callees(R) == ()
    assert graph.callers(R) == ()


def test_thunk_rows_are_walked():
    graph = _graph()
    assert graph.callees(TH) == (Edge(TH, E, DIRECT),)
    assert graph.callers(E) == (TH,)  # the runtime row's call into E is not an edge


def test_exact_edge_set():
    _assert_edges(_graph(), {
        (A, B, DIRECT), (A, C, DIRECT), (A, D, POINTER), (B, F, DIRECT), (D, TH, DIRECT),
        (TH, E, DIRECT),
    })  # fmt: skip


def test_planted_edge_fails():
    expected = {
        (A, B, DIRECT), (A, C, DIRECT), (A, D, POINTER), (B, F, DIRECT), (D, TH, DIRECT),
        (TH, E, DIRECT),
    }  # fmt: skip
    with pytest.raises(AssertionError):
        _assert_edges(_graph(), expected | {(A, E, DIRECT)})
    with pytest.raises(AssertionError):
        _assert_edges(_graph(), expected - {(A, D, POINTER)})


def test_callees_are_sorted_and_callers_reverse_them():
    graph = _graph()
    assert graph.callees(A) == (Edge(A, B, DIRECT), Edge(A, C, DIRECT), Edge(A, D, POINTER))
    assert graph.callers(B) == (A,)
    assert graph.callers(A) == ()


def test_closure_follows_edges_and_stops():
    graph = _graph()
    assert closure(graph, {A}) == frozenset({A, B, C, D, TH, E, F})
    stopped = closure(graph, {A}, stop=frozenset({B}))
    assert B in stopped
    assert F not in stopped  # B's only callee
    assert stopped == frozenset({A, B, C, D, TH, E})


def test_build_is_deterministic():
    assert _graph() == _graph()


def test_build_for_takes_ranges_from_the_le_objects():
    le, flat, fixups = _inputs(PATCHES, FIXUPS)
    exe = SimpleNamespace(le=le, flat=flat, fixups=tuple(fixups), rows=tuple(ROWS))
    assert callgraph.build_for(exe) == _graph()
