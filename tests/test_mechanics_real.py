"""The mechanics map against the real executables (DEC-01, D-02; research 07-R1 §Q1).

These tests read orig/<EXE> (conftest.ORIG_DIR, or REVERSEAPOC_ORIG pointing at a main checkout's
orig/) and need capstone; each EXE skips on its own when its file is absent, and they never run in
CI because the game files are never committed. They assert on addresses and counts only, never on
bytes, so a failure never prints game code.

- Reachability from `main_` over direct, direct + pointer and direct + pointer + table edges,
  within 1% (orchestrator ruling F14: research measured those three kinds only; the `midrow`
  kind of 07-05 is left out of the pin). Research Q1's numbers, except UFO2P's table step (see
  REACH_DIRECT_POINTER_TABLE).
- The graph's direct edges are exactly contextpack.CallIndex's callees onto game/thunk rows, and
  CallIndex's edge count is research's 5,288 / 4,885.
- When config/mechanics-members.csv is committed, regenerating it gives the same bytes (the
  drift test). Before plan 07-22 writes it there is nothing to compare, and the test passes (F32).
"""

from __future__ import annotations

from functools import cache

import pytest

from conftest import ORIG_DIR, REPO_ROOT, requires_capstone
from reverseapoc import callgraph, mechanics
from reverseapoc.callgraph import DIRECT, POINTER, TABLE, CallGraph
from reverseapoc.contextpack import CallIndex
from reverseapoc.functions import read_symbols_csv

CONFIG = REPO_ROOT / "config"
MANIFEST = CONFIG / "targets.toml"
EXES = {"ufo2p": "UFO2P.EXE", "tacp": "TACP.EXE"}
# research 07-R1 Q1: game + thunk rows reachable from main_
REACH_DIRECT = {"ufo2p": 1_128, "tacp": 1_224}
REACH_DIRECT_POINTER = {"ufo2p": 1_412, "tacp": 1_479}
# Research's table step reached 1,471 in UFO2P. callgraph.py (plan 07-05) wires a pointer run only
# from the game/thunk rows that reference it, so the 31 game targets of runs referenced only from
# runtime code are not reached, and the step stops at 1,429 (taking those runs as reached gives
# 1,480). The pin follows the built rule; plan 07-22 records the difference (07-10 SUMMARY).
REACH_DIRECT_POINTER_TABLE = {"ufo2p": 1_429, "tacp": 1_479}
CALLINDEX_EDGES = {"ufo2p": 5_288, "tacp": 4_885}
TOLERANCE = 0.01


def _param(exe: str):
    name = EXES[exe]
    return pytest.param(exe, id=exe, marks=pytest.mark.skipif(
        not (ORIG_DIR / name).is_file(),
        reason=f"orig/{name} not present (run uv run reverseapoc ingest or set REVERSEAPOC_ORIG)"))


PARAMS = [_param(exe) for exe in EXES]


@cache
def _inputs(exe: str):
    from reverseapoc.check import load_exe, select_exe
    from reverseapoc.targets import load_manifest

    target = select_exe(load_manifest(MANIFEST), exe, MANIFEST)
    return load_exe(target, orig_dir=ORIG_DIR, manifest=MANIFEST, config_root=CONFIG)


@cache
def _graph(exe: str) -> CallGraph:
    return callgraph.build_for(_inputs(exe))


@pytest.fixture(params=PARAMS)
def exe(request) -> str:
    requires_capstone()
    return request.param


def _only(graph: CallGraph, kinds: tuple[str, ...]) -> CallGraph:
    return CallGraph(edges={start: tuple(e for e in edges if e.kind in kinds)
                            for start, edges in graph.edges.items()})  # fmt: skip


def _main(exe: str) -> int:
    rows = read_symbols_csv(CONFIG / exe / "symbols.csv")
    (address,) = [row.address for row in rows if row.name == "main_"]
    return address


def _within(got: int, want: int) -> bool:
    return abs(got - want) <= want * TOLERANCE


def test_reachability_from_main_within_one_percent(exe):
    graph, main = _graph(exe), _main(exe)
    walked = frozenset(graph.edges)
    pins = ((REACH_DIRECT, (DIRECT,)), (REACH_DIRECT_POINTER, (DIRECT, POINTER)),
            (REACH_DIRECT_POINTER_TABLE, (DIRECT, POINTER, TABLE)))  # fmt: skip
    for want, kinds in pins:
        got = len(callgraph.closure(_only(graph, kinds), [main]) & walked)
        assert _within(got, want[exe]), (kinds, got, want[exe])


def test_direct_edges_equal_callindex(exe):
    inputs, graph = _inputs(exe), _graph(exe)
    index = CallIndex.build(inputs.rows, inputs.flat, inputs.fixups)
    assert sum(len(targets) for targets in index.callees.values()) == CALLINDEX_EDGES[exe]
    walked = frozenset(graph.edges)
    want = {(src, dst) for src, targets in index.callees.items() for dst in targets
            if dst in walked}  # fmt: skip
    got = {(e.src, e.dst) for edges in graph.edges.values() for e in edges if e.kind == DIRECT}
    assert got == want


def test_members_csv_has_no_drift():
    committed = CONFIG / mechanics.MEMBERS_CSV
    if not committed.is_file():
        return  # plan 07-22 writes it; nothing to compare yet (F32)
    requires_capstone()
    missing = [name for name in EXES.values() if not (ORIG_DIR / name).is_file()]
    if missing:
        pytest.skip(f"orig/{missing[0]} not present (run uv run reverseapoc ingest or set "
                    "REVERSEAPOC_ORIG)")  # fmt: skip
    rows = mechanics.generate(CONFIG, ORIG_DIR, MANIFEST)
    assert mechanics.format_members_csv(rows) == committed.read_text(encoding="utf-8")
