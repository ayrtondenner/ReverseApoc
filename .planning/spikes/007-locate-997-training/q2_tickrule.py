"""Spike 007 q2: from the BIOS-tick readers to the time-advance loop and its rate constants
(#997; D-26: start from the BIOS tick, look for PR #1688's "36 units per game second").

Method, per EXE:
1. The readers are q1's: the rows that call int386_ with 0x1A.
2. Loop candidates are the backward branches (a loop head at or before the branch, inside the
   row) whose span covers a call to a reader, or a reader's own int386_ 0x1A call.
3. In each loop row, and in the functions called inside the loop span (two calls deep), look
   for an accumulator: `add R, X` where R was loaded from global A and X from global S, then
   `cmp R, M` and a later `sub _, M`, with a store back to A. The function holding it is the
   clock function, S the speed variable, M the modulus (units per game second).
4. The frame step is the row calling the clock function; it paces on the BIOS tick when it holds
   a backward branch over an int386_ 0x1A call (a busy-wait on the tick).
5. UFO2P only: the speed labels are found through get_text's section table (never by scanning
   string bytes for xrefs), their get_text call sites, the `cmp [S], v` that guards each site,
   and the speed-indexed jump tables of the loop row (one slot per speed 1..N).

Claims: loop-located-<exe>, accumulator-modulus-is-36 (PR #1688), one-second-per-frame,
paces-on-bios-tick (TACP: "TACP paces on the same BIOS tick"), speed-table-one-entry-per-label
(UFO2P), research-candidates (07-R1 A2). A FAIL is a finding: every claim is still printed.

Run from the main checkout:
    uv run python .planning/spikes/007-locate-997-training/q2_tickrule.py [--plant]

--plant flips the expected modulus to 144 (the OpenApoc assumption); the run must FAIL.
Prints addresses, counts, the modulus, speed values (rate constants), slot counts and keyword
labels only; never strings, game bytes or instruction text. Reads orig/ only, writes nothing.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass

from q1_timebase import (
    EXES,
    INT_BIOS_TICK,
    Image,
    Report,
    hx,
    hxs,
    imm,
    operands,
    readers_found,
    reg_part,
    scan,
    tracked,
)

from reverseapoc.functions import FunctionRow
from reverseapoc.x86 import Insn

CALL_DEPTH = 2  # functions called inside a loop span, then their callees
ADD_WINDOW = 4  # instructions between the `add` and the `cmp` of an accumulator
SUB_WINDOW = 12  # instructions between the `cmp` and the `sub` of the same modulus
TABLE_WINDOW = 9  # instructions between a speed load and the jump-table `jmp` it indexes
GUARD_WINDOW = 10  # instructions before a busy-wait head searched for its skip tests
LOAD_OPS = frozenset({"mov", "movsx", "movzx"})
JUMP_TABLE = re.compile(r"^dword ptr cs:\[(e[a-z]{2})\*4 \+ 0x[0-9a-f]+\]$|^dword ptr \[(e[a-z]{2})"
                        r"\*4 \+ 0x[0-9a-f]+\]$")  # fmt: skip
SPEED_KEYWORD = "speed"
LABEL_KEYWORDS = ("slow", "normal", "double", "quadruple")

# Copied from 07-R1-locate.md (#997 FINDING, Q2) for the research half; the located half
# ("located by this spike") was found by this script's first run and is pinned here.
EXPECTED = {
    "modulus": 36,  # OpenApoc PR #1688: 36 units make one game second
    "UFO2P.EXE": {
        "loop": 0x00010940,  # located by this spike (frame loop with an inline int386 0x1A)
        "clock": 0x0004AB30,  # located by this spike
        "accumulator": 0x000D4D6E,
        "speed": 0x000D4D58,
        "no_wait": 0x000D4D5C,  # fix round 1: the no-wait frame counter
        "speed_setters": {0x00050920, 0x00050970, 0x000509C0, 0x00050A20, 0x00050A80,
                          0x00050AE0},
        "get_text": 0x00063800,
        "section_table": 0x000F3794,
        "sections": 50,
        "label_span": (0x000F14BF, 0x000F14E4),
        "labels": 4,
        "research_loop": 0x00022EF0,  # A2 candidate (with the wait in func_00026B80)
        "research_wait": 0x00026B80,
        "research_table": 0x001303E0,  # A2 speed-table candidate, used by func_000ACDC0
    },
    "TACP.EXE": {
        "loop": None,  # unknown before the spike: the claim reports what is found
        "clock": None,
        "accumulator": None,
        "speed": None,
    },
}
PLANT_MODULUS = 144  # OpenApoc's assumed ticks per second


@dataclass(frozen=True)
class Accumulator:
    function: int
    accumulator: int  # global A
    speed: int  # global S
    modulus: int
    cmp_at: int
    subs: int  # `sub _, modulus` instructions in the function


@dataclass(frozen=True)
class Loop:
    row: int
    head: int
    back: int


# ---- helpers ----


def mem_global(img: Image, insn: Insn) -> int | None:
    """The linear address an instruction's memory displacement names (an LE fixup on it)."""
    if not insn.disp_offset:
        return None
    fld = img.fields.get(insn.va + insn.disp_offset)
    return fld.target if fld is not None else None


def full(op: str) -> str | None:
    part = reg_part(op)
    return part[0] if part else None


def int1a_sites(img: Image, row: FunctionRow) -> list[int]:
    int386 = {img.named[n] for n in ("int386_", "int386x_") if n in img.named}
    return [insn.va for insn, regs in tracked(img, row)
            if insn.is_call and img.target(insn) in int386 and regs.get("eax") == INT_BIOS_TICK]


def backward_loops(img: Image, row: FunctionRow, sites: list[int]) -> list[Loop]:
    found = []
    for insn in img.insns(row):
        dest = img.target(insn) if insn.is_jump else None
        if dest is None or not row.start <= dest <= insn.va:
            continue
        if any(dest <= va <= insn.va for va in sites):
            found.append(Loop(row.start, dest, insn.va))
    return found


def calls_in(img: Image, row: FunctionRow, lo: int, hi: int) -> set[int]:
    return {dest for insn in img.insns(row)
            if insn.is_call and lo <= insn.va <= hi
            and (dest := img.target(insn)) in img.starts
            and img.starts[dest].kind in ("game", "thunk")}  # fmt: skip


def reached(img: Image, loop: Loop) -> set[int]:
    """The loop row and the game functions called inside its span, CALL_DEPTH calls deep."""
    seen = {loop.row}
    frontier = calls_in(img, img.starts[loop.row], loop.head, loop.back)
    for _ in range(CALL_DEPTH):
        frontier -= seen
        seen |= frontier
        frontier = {d for f in frontier for d in calls_in(img, img.starts[f], 0, 1 << 32)}
    return seen


def last_load(img: Image, insns: list[Insn], before: int, reg: str) -> int | None:
    """The global the last instruction before index `before` that writes `reg` loaded from."""
    for insn in reversed(insns[max(0, before - 8) : before]):
        ops = operands(insn)
        if not ops or full(ops[0]) != reg:
            continue
        return mem_global(img, insn) if insn.mnemonic in LOAD_OPS else None
    return None


def accumulators(img: Image, start: int) -> list[Accumulator]:
    insns = img.insns(img.starts[start])
    stores = {mem_global(img, i) for i in insns if i.mnemonic == "mov"
              and "[" in operands(i)[0]}  # fmt: skip
    found = []
    for k, insn in enumerate(insns):
        ops = operands(insn)
        if insn.mnemonic != "cmp" or len(ops) != 2 or full(ops[0]) is None:
            continue
        modulus = imm(ops[1])
        if not modulus or modulus < 2:
            continue
        acc = _accumulator(img, insns, k, full(ops[0]), modulus, stores)
        if acc is not None:
            found.append(acc)
    return found


def _accumulator(img, insns, k, reg, modulus, stores) -> Accumulator | None:
    for j in range(max(0, k - ADD_WINDOW), k):
        ops = operands(insns[j])
        if insns[j].mnemonic != "add" or len(ops) != 2 or full(ops[0]) != reg:
            continue
        other = full(ops[1])
        acc_global = last_load(img, insns, j, reg)
        speed_global = last_load(img, insns, j, other) if other else None
        tail = insns[k + 1 : k + 1 + SUB_WINDOW]
        sub = any(i.mnemonic == "sub" and imm(operands(i)[-1]) == modulus for i in tail)
        if acc_global and speed_global and sub and acc_global in stores:
            subs = sum(1 for i in insns if i.mnemonic == "sub" and len(operands(i)) == 2
                       and imm(operands(i)[1]) == modulus)  # fmt: skip
            return Accumulator(insns[0].va, acc_global, speed_global, modulus, insns[k].va, subs)
    return None


# ---- locating ----


@dataclass
class Found:
    loops: list[Loop]
    clocks: dict[int, Accumulator]  # clock function -> accumulator
    by_loop: dict[int, set[int]]  # loop row -> clock functions it reaches
    advancing: list[Loop]  # the loops whose span reaches a clock function


def locate(img: Image) -> Found:
    sites = scan(img)
    direct, via = readers_found(sites)
    readers = direct | via
    loops: list[Loop] = []
    for row in img.walked():
        calls = [i.va for i in img.insns(row) if i.is_call and img.target(i) in readers]
        if row.start in readers:
            calls += int1a_sites(img, row)
        if calls:
            loops += backward_loops(img, row, calls)
    clocks: dict[int, Accumulator] = {}
    by_loop: dict[int, set[int]] = {}
    advancing: list[Loop] = []
    for loop in loops:
        for fn in sorted(reached(img, loop)):
            for acc in accumulators(img, fn):
                clocks.setdefault(fn, acc)
                by_loop.setdefault(loop.row, set()).add(fn)
                if not advancing or advancing[-1] != loop:
                    advancing.append(loop)
    return Found(loops, clocks, by_loop, advancing)


def frame_steps(img: Image, clock: int) -> dict[int, Loop | None]:
    """Rows calling the clock function -> their busy-wait on the BIOS tick: the narrowest
    backward branch over an int386_ 0x1A call, or None."""
    out = {}
    for row in img.walked():
        if any(i.is_call and img.target(i) == clock for i in img.insns(row)):
            loops = backward_loops(img, row, int1a_sites(img, row))
            out[row.start] = min(loops, key=lambda lp: lp.back - lp.head) if loops else None
    return out


def speed_values(img: Image, speed: int) -> tuple[set[int], set[int]]:
    """(constants stored to the speed variable, constants it is compared with), all rows."""
    stored, compared = set(), set()
    for row in img.walked():
        for insn, regs in tracked(img, row):
            ops = operands(insn)
            if len(ops) != 2 or mem_global(img, insn) != speed or "[" not in ops[0]:
                continue
            value = imm(ops[1])
            if insn.mnemonic == "mov":
                value = value if value is not None else regs.get(ops[1])
                if isinstance(value, int):
                    stored.add(value)
            elif insn.mnemonic == "cmp" and value is not None:
                compared.add(value)
    return stored, compared


# ---- get_text labels and the speed table (UFO2P) ----


def sections(img: Image, table: int, count: int) -> list[int | None]:
    return [f.target if (f := img.fields.get(table + 4 * k)) else None for k in range(count)]


def string_at(img: Image, va: int) -> bytes:
    return bytes(img.flat[va : img.flat.index(0, va)])


def labels(img: Image, exp: dict) -> dict[str, tuple[int, int, int]]:
    """keyword -> (section, index, address) for the speed labels inside the label span."""
    lo, hi = exp["label_span"]
    out = {}
    for sec, start in enumerate(sections(img, exp["section_table"], exp["sections"])):
        if start is None:
            continue
        va = start
        for index in range(1 << 12):
            if va > hi:
                break
            text = string_at(img, va).lower()
            if lo <= va <= hi and SPEED_KEYWORD.encode() in text:
                key = next((k for k in LABEL_KEYWORDS if k.encode() in text), None)
                if key is not None:
                    out[key] = (sec, index, va)
            va += len(text) + 1
    return out


def label_sites(img: Image, exp: dict, found: dict) -> dict[str, list[tuple[int, int | None]]]:
    """keyword -> [(get_text call site, the speed value the nearest `cmp [S], v` before it
    tests)] over all rows."""
    want = {(sec, idx): key for key, (sec, idx, _) in found.items()}
    out: dict[str, list[tuple[int, int | None]]] = {}
    for row in img.walked():
        guard = None
        for insn, regs in tracked(img, row):
            ops = operands(insn)
            if insn.mnemonic == "cmp" and len(ops) == 2 and mem_global(img, insn) == exp["speed"]:
                guard = imm(ops[1])
            if not (insn.is_call and img.target(insn) == exp["get_text"]):
                continue
            key = want.get((regs.get("eax"), regs.get("edx")))
            if key is not None:
                out.setdefault(key, []).append((insn.va, guard))
    return out


def speed_tables(img: Image, loop: int, speed: int) -> list[tuple[int, int, set[int]]]:
    """(table address, slots, active speeds) for each `jmp [reg*4 + T]` in the loop row that
    follows a load of the speed variable. The bounds check `cmp reg, N` / `ja default` gives
    N + 1 slots; slot k is speed k+1, and a slot is active unless it lands on the default."""
    insns = img.insns(img.starts[loop])
    out = []
    for k, insn in enumerate(insns):
        if insn.mnemonic != "jmp" or not JUMP_TABLE.match(insn.op_str):
            continue
        window = insns[max(0, k - TABLE_WINDOW) : k]
        if not any(mem_global(img, i) == speed for i in window):
            continue
        default = next((img.target(i) for i in reversed(window) if i.mnemonic == "ja"), None)
        bound = next((imm(operands(i)[1]) for i in reversed(window)
                      if i.mnemonic == "cmp" and len(operands(i)) == 2), None)  # fmt: skip
        table = mem_global(img, insn)
        if default is None or bound is None or table is None:
            continue
        slots = [img.fields[table + 4 * n].target for n in range(bound + 1)
                 if table + 4 * n in img.fields]  # fmt: skip
        active = {n + 1 for n, dest in enumerate(slots) if dest != default}
        out.append((table, len(slots), active))
    return out


# ---- claims ----


def claim_loop(report: Report, img: Image, found: Found, exp: dict) -> Accumulator | None:
    rows = set(found.by_loop)
    clocks = set(found.clocks)
    expected_loop = exp["loop"]
    if expected_loop is None:
        ok = len(clocks) == 1 and bool(rows)
    else:
        ok = expected_loop in rows and clocks == {exp["clock"]}
    acc = found.clocks[min(clocks)] if len(clocks) == 1 else None
    widest: dict[int, Loop] = {}
    for lp in found.advancing:  # one loop per row: the widest that reaches the clock
        best = widest.get(lp.row)
        if best is None or lp.back - lp.head > best.back - best.head:
            widest[lp.row] = lp
    spans = " ".join(f"{hx(r)}:{hx(lp.head)}..{hx(lp.back)}" for r, lp in sorted(widest.items()))
    detail = (f"loop rows {len(rows)} [{spans}] clock {hxs(clocks)} "
              f"accumulator {hx(acc.accumulator) if acc else '-'} "
              f"speed {hx(acc.speed) if acc else '-'} expected loop "
              f"{hx(expected_loop) if expected_loop else 'None (report)'}")  # fmt: skip
    if acc and exp["accumulator"] is not None:
        ok = ok and (acc.accumulator, acc.speed) == (exp["accumulator"], exp["speed"])
    report.claim(img.name, ok, f"loop-located-{img.name.split('.')[0].lower()}", detail)
    return acc


def claim_modulus(report: Report, img: Image, acc: Accumulator | None, modulus: int) -> None:
    got = acc.modulus if acc else None
    report.claim(img.name, got == modulus, "accumulator-modulus-is-36",
                 f"modulus {got} at {hx(acc.cmp_at) if acc else '-'} expected {modulus} "
                 f"(PR #1688)")  # fmt: skip
    where = hx(acc.function) if acc else "-"
    report.claim(img.name, bool(acc) and acc.subs == 1, "one-second-per-frame",
                 f"`sub _, {got}` count {acc.subs if acc else 0} in {where}"
                 f" (one per call: at most one game second per frame)")  # fmt: skip


def claim_pacing(report: Report, img: Image, acc: Accumulator | None) -> None:
    steps = frame_steps(img, acc.function) if acc else {}
    waits = " ".join(f"{hx(va)}:{hx(lp.head)}..{hx(lp.back)}"
                     for va, lp in sorted(steps.items()) if lp)  # fmt: skip
    name = "tacp-paces-on-same-bios-tick" if img.name == "TACP.EXE" else "paces-on-bios-tick"
    report.claim(img.name, bool(waits), name,
                 f"rows calling the clock {hxs(steps)}; busy-wait on int386 0x1A [{waits}]")
    claim_wait_skip(report, img, acc, steps)


def wait_guards(img: Image, row: int, wait: Loop) -> set[int]:
    """Globals read just before the busy-wait head by a test whose conditional jump lands past
    the wait (the conditions under which a frame does not wait)."""
    insns = img.insns(img.starts[row])
    k = next(n for n, i in enumerate(insns) if i.va == wait.head)
    window = insns[max(0, k - GUARD_WINDOW) : k]
    found: set[int] = set()
    last_skip = 0
    for n, insn in enumerate(window):
        dest = img.target(insn) if insn.is_conditional else None
        if dest is None or dest <= wait.back or n == 0:
            continue
        last_skip = n
        test = window[n - 1]
        if (g := mem_global(img, test)) is not None:
            found.add(g)
            continue
        tested = full(operands(test)[0]) if test.op_str else None
        for prior in reversed(window[max(0, n - 4) : n - 1]):
            ops = operands(prior)
            if ops and full(ops[0]) == tested:
                if (g := mem_global(img, prior)) is not None:
                    found.add(g)
                break
    if not found:  # the skip tests a flag computed earlier: every global read before it
        found = {g for i in window[:last_skip] if (g := mem_global(img, i)) is not None}
    return found


def claim_wait_skip(report: Report, img: Image, acc: Accumulator | None, steps: dict) -> None:
    """Fix round 1: the frame does not always wait. Report the globals guarding the wait and,
    for UFO2P, that every speed setter also writes the no-wait counter."""
    guards = set().union(*(wait_guards(img, va, lp) for va, lp in steps.items() if lp)) \
        if steps else set()
    exp = EXPECTED[img.name]
    setters = set()
    if acc is not None and exp.get("no_wait") is not None:
        for row in img.walked():
            hits = {mem_global(img, i) for i in img.insns(row)
                    if i.mnemonic == "mov" and i.op_str and "[" in operands(i)[0]}
            if {acc.speed, exp["no_wait"]} <= hits:
                setters.add(row.start)
    if exp.get("no_wait") is None:
        ok = bool(guards)
    else:
        ok = exp["no_wait"] in guards and exp["speed_setters"] <= setters
    detail = f"globals tested right before the busy-wait by a jump past it {hxs(guards)}"
    if exp.get("no_wait") is not None:
        detail += (f"; rows writing both the speed and {hx(exp['no_wait'])}: {len(setters)}, "
                   f"the 6 speed setters among them {exp['speed_setters'] <= setters}")
    report.claim(img.name, ok, "wait-skip-guards", detail)


def claim_speeds(report: Report, img: Image, acc: Accumulator | None) -> None:
    if acc is None:
        report.claim(img.name, False, "speed-values", "no speed variable located")
        return
    stored, compared = speed_values(img, acc.speed)
    report.claim(img.name, bool(stored | compared), "speed-values",
                 f"stored {sorted(stored)} compared {sorted(compared)} at {hx(acc.speed)}")


def claim_labels(report: Report, img: Image, exp: dict, acc: Accumulator | None) -> None:
    table = sections(img, exp["section_table"], exp["sections"])
    decoded = sum(s is not None for s in table)
    report.claim(img.name, decoded == exp["sections"], "get-text-sections",
                 f"{decoded} of {exp['sections']} section pointers at {hx(exp['section_table'])}")
    found = labels(img, exp)
    sites = label_sites(img, exp, found)
    label_speed = {key: {g for _, g in sites.get(key, [])} for key in found}
    tables = speed_tables(img, exp["loop"], exp["speed"]) if acc else []
    parts = [f"{k} {found[k][0]}/{found[k][1]} sites {hxs(va for va, _ in sites.get(k, []))} "
             f"speed {sorted(label_speed[k])}" for k in LABEL_KEYWORDS if k in found]
    speeds = {next(iter(v)) for v in label_speed.values() if len(v) == 1}
    actives = [active for _, _, active in tables]
    ok = len(found) == exp["labels"] and len(speeds) == exp["labels"] and bool(tables) \
        and all(active == speeds for active in actives)
    report.claim(img.name, ok, "speed-table-one-entry-per-label",
                 f"labels {len(found)}: " + "; ".join(parts)
                 + f"; tables {[(hx(t), n, sorted(a)) for t, n, a in tables]}")  # fmt: skip


def claim_research(report: Report, img: Image, exp: dict, found: Found) -> None:
    clock = exp["clock"]
    reach = {}
    for cand in (exp["research_loop"], exp["research_wait"]):
        row = img.starts[cand]
        reach[cand] = clock in reached(img, Loop(cand, row.start, row.end))
    table_users = {img.row_at(f.va).start for f in img.fields.values()
                   if f.target == exp["research_table"] and img.row_at(f.va)}  # fmt: skip
    in_loop = bool(table_users & ({exp["loop"]} | set(found.clocks)))
    ok = not any(reach.values()) and not in_loop
    report.claim(img.name, ok, "research-candidates-refuted",
                 f"{hx(exp['research_loop'])} reaches clock {reach[exp['research_loop']]}; "
                 f"{hx(exp['research_wait'])} reaches clock {reach[exp['research_wait']]}; "
                 f"table {hx(exp['research_table'])} users {hxs(table_users)} "
                 f"in loop/clock {in_loop}")  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plant", action="store_true", help="expect modulus 144 instead of 36")
    args = parser.parse_args(argv)
    modulus = EXPECTED["modulus"]
    if args.plant:
        print(f"PLANT expected modulus {modulus} -> {PLANT_MODULUS}")
        modulus = PLANT_MODULUS
    report = Report()
    for name in EXES:
        img = Image(name)
        exp = EXPECTED[name]
        found = locate(img)
        acc = claim_loop(report, img, found, exp)
        claim_modulus(report, img, acc, modulus)
        claim_pacing(report, img, acc)
        claim_speeds(report, img, acc)
        if name == "UFO2P.EXE":
            claim_labels(report, img, exp, acc)
            claim_research(report, img, exp, found)
    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
