"""Spike 007 q6: the call graph rebuilt independently, checked against CallIndex and against
research Q1's reachability from main_ (D-03: the call-graph route behind the tier drafts).

Edges, rebuilt here from the raw image and fixups (rawle.py) and the committed functions.csv:
- direct: a direct call or jump from a game/thunk row onto another row's start (q1's scan; a
  jump there is a tail call);
- pointer: an off32 or ptr16:32 fixup whose field lies in a game/thunk row and whose target is
  another code row's start (callbacks, comparators, button handlers);
- table: function-pointer slots in the data object (off32/ptr16:32 fixups onto a code row's
  start) grouped into runs (slots at most RUN_GAP bytes apart); every game/thunk row holding an
  off32 fixup into a run's [first slot - RECORD_LEAD, last slot + 4) gets an edge to every slot
  target of the run. The lead-in counts code that addresses the base of a record whose pointer
  field sits a few bytes in. Without it (the strict [first slot, last slot + 4) rule of
  callgraph.py, plan 07-05) the reach is printed as an INFO line.

Claims, per EXE:
- direct-edges-equal-callindex: the direct edge set equals reverseapoc.contextpack.CallIndex's,
  and its size equals research Q1's count;
- reach-direct / reach-pointer / reach-table: the game and thunk rows reached from main_ over
  direct, then + pointer, then + table edges, each within 1% of research Q1. Runtime and
  data-in-code rows are never walked (D-02).

Run from the main checkout:
    uv run python .planning/spikes/007-locate-997-training/q6_callgraph.py [--plant]

--plant expects one direct edge more than research counted; the run must FAIL. Prints addresses,
counts and percentages only. Reads orig/ only, writes nothing.
"""

from __future__ import annotations

import argparse
import sys
from collections import deque
from dataclasses import dataclass, field

from q1_timebase import EXES, Image, Report, direct_callers, hx
from q3_training import data_span

from reverseapoc.contextpack import CallIndex
from reverseapoc.functions import KIND_DATA_IN_CODE

POINTER_KINDS = frozenset({0x06, 0x07})  # LE source types: ptr16:32, off32
OFF32 = 0x07
RUN_GAP = 16  # research Q1: table slots at most 16 bytes apart form one run
RECORD_LEAD = 64  # this spike: record bases seen 4-41 bytes before a run's first slot
TOLERANCE = 0.01  # reachability within 1% of research
WALKED = ("game", "thunk")

# Copied from 07-R1-locate.md Q1 ("What exists", "Reachability", main_ per symbols.csv).
EXPECTED = {
    "UFO2P.EXE": {"main": 0x00010010, "direct_edges": 5288, "walked": 1553,
                  "reach": {"direct": 1128, "pointer": 1412, "table": 1471}},
    "TACP.EXE": {"main": 0x000102A0, "direct_edges": 4885, "walked": 1526,
                 "reach": {"direct": 1224, "pointer": 1479, "table": 1479}},
}  # fmt: skip


@dataclass
class Graph:
    direct: set[tuple[int, int]] = field(default_factory=set)
    pointer: set[tuple[int, int]] = field(default_factory=set)
    table: set[tuple[int, int]] = field(default_factory=set)
    strict: set[tuple[int, int]] = field(default_factory=set)  # table edges without the lead-in
    slots: int = 0
    runs: int = 0
    wired_runs: int = 0
    wired_strict: int = 0


def build(img: Image) -> Graph:
    graph = Graph()
    for callee, callers in direct_callers(img).items():
        graph.direct |= {(caller, callee) for caller in callers}
    code_starts = {r.start for r in img.rows if r.kind != KIND_DATA_IN_CODE}
    lo, hi = data_span(img)
    slots: list[tuple[int, int]] = []
    for fld in img.fields.values():
        if fld.kind not in POINTER_KINDS or fld.target not in code_starts:
            continue
        row = img.row_at(fld.va)
        if row is not None and row.kind in WALKED and fld.target != row.start:
            graph.pointer.add((row.start, fld.target))
        elif lo <= fld.va < hi:
            slots.append((fld.va, fld.target))
    runs = group_runs(sorted(slots))
    graph.slots, graph.runs = len(slots), len(runs)
    refs = [(row.start, fld.target) for fld in img.fields.values() if fld.kind == OFF32
            and (row := img.row_at(fld.va)) is not None and row.kind in WALKED]  # fmt: skip
    for run in runs:
        first, last = run[0][0], run[-1][0] + 4
        users = {src for src, target in refs if first - RECORD_LEAD <= target < last}
        strict = {src for src, target in refs if first <= target < last}
        graph.wired_runs += bool(users)
        graph.wired_strict += bool(strict)
        graph.table |= {(user, target) for user in users for _, target in run if target != user}
        graph.strict |= {(user, target) for user in strict for _, target in run if target != user}
    return graph


def group_runs(slots: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    runs: list[list[tuple[int, int]]] = []
    for slot in slots:
        if runs and slot[0] - runs[-1][-1][0] <= RUN_GAP:
            runs[-1].append(slot)
        else:
            runs.append([slot])
    return runs


def reach(img: Image, start: int, edges: set[tuple[int, int]]) -> set[int]:
    walked = {r.start for r in img.rows if r.kind in WALKED}
    out: dict[int, set[int]] = {}
    for src, dst in edges:
        if dst in walked:
            out.setdefault(src, set()).add(dst)
    seen = {start}
    queue = deque([start])
    while queue:
        for nxt in out.get(queue.popleft(), set()) - seen:
            seen.add(nxt)
            queue.append(nxt)
    return seen


def claim_direct(report: Report, img: Image, graph: Graph, exp: dict) -> None:
    index = CallIndex.build(img.inputs.rows, img.inputs.flat, img.inputs.fixups)
    theirs = {(caller, callee) for caller, callees in index.callees.items() for callee in callees}
    mine = graph.direct
    ok = mine == theirs and len(mine) == exp["direct_edges"]
    report.claim(img.name, ok, "direct-edges-equal-callindex",
                 f"own {len(mine)} CallIndex {len(theirs)} only-own {len(mine - theirs)} "
                 f"only-CallIndex {len(theirs - mine)} expected {exp['direct_edges']}")


def claim_reach(report: Report, img: Image, graph: Graph, exp: dict) -> None:
    walked = sum(r.kind in WALKED for r in img.rows)
    start = exp["main"]
    edges = set(graph.direct)
    for name, extra in (("direct", set()), ("pointer", graph.pointer), ("table", graph.table)):
        edges |= extra
        got = len(reach(img, start, edges))
        want = exp["reach"][name]
        off = abs(got - want) / want
        report.claim(img.name, off <= TOLERANCE and start in img.starts, f"reach-{name}",
                     f"from main_ {hx(start)}: {got} / {walked} walked rows "
                     f"({got / walked:.1%}); research {want} / {exp['walked']}, off {off:.2%}; "
                     f"edges {len(edges)}")  # fmt: skip
    strict = len(reach(img, start, graph.direct | graph.pointer | graph.strict))
    print(f"INFO {img.name} pointer edges {len(graph.pointer)}; table slots {graph.slots} in "
          f"{graph.runs} runs; referenced from game/thunk code {graph.wired_runs} with the "
          f"{RECORD_LEAD}-byte lead-in (edges {len(graph.table)}), {graph.wired_strict} without "
          f"it (edges {len(graph.strict)}, reach {strict})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plant", action="store_true", help="expect one direct edge more")
    args = parser.parse_args(argv)
    report = Report()
    for name in EXES:
        img = Image(name)
        exp = dict(EXPECTED[name])
        if args.plant:
            print(f"PLANT {name} expected direct edges {exp['direct_edges']} -> "
                  f"{exp['direct_edges'] + 1}")
            exp["direct_edges"] += 1
        graph = build(img)
        claim_direct(report, img, graph, exp)
        claim_reach(report, img, graph, exp)
    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
