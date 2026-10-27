"""Spike 007 q3: the #263-1 battle-to-agent training rule (D-26: it goes through
scenario/unitr.dat; EXPERIEN/BRAIN/WEAPEXP.DAT are the Learning AI files of #265, not #263-1).

Claims:
- unitr-reader (UFO2P) / unitr-writer (TACP): the one string holding the keyword `unitr.dat` has
  exact fixup references from the reader / writer row only, and that row passes it to a file
  call together with a buffer (reported by address, with the writer's byte count).
- record-layout (TACP): the writer walks the unit array and the result buffer in step, and the
  byte count is units x record size.
- stat-update (UFO2P): the rows reached from the reader (two calls deep) that copy at least
  MIN_COPIES fields from the loaded buffer into another record: the stat update. Reported with
  the destination array.
- handoff-fields-agree: every buffer field the stat update copies is filled by the TACP writer.
- android-label (UFO2P): the get_text (section, index) of the label at 0xF12B6 (it holds the
  keywords `android` and `training`), its call sites, and the record-field compare that guards
  each site; android-string: the plain `android` string is referenced only by func_0009B840.
- accrual-sites (TACP): rows that refer to the unit array and either write a field the writer
  serialises through the array base, or add to / subtract from a field the stat update applies
  through a register base. A heuristic lead: writes through a unit pointer passed in from a
  caller are not resolved here.
- learning-ai-files: the rows referencing EXPERIEN/BRAIN/WEAPEXP.DAT are research's rows, and the
  reader / writer reaches none of them except, in UFO2P, through the savegame loader.

Run from the main checkout:
    uv run python .planning/spikes/007-locate-997-training/q3_training.py [--plant]

--plant uses a wrong writer address; the run must FAIL. Prints addresses, counts, offsets and
keyword labels only: no string longer than the keyword it searched for, no game bytes, no
instruction text. Reads orig/ only, writes nothing.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import deque
from dataclasses import dataclass

from q1_timebase import EXES, Image, Report, hx, hxs, operands, reg_part, tracked
from q2_tickrule import mem_global, sections, string_at

from reverseapoc.functions import FunctionRow
from reverseapoc.x86 import Insn

OBJ_EXECUTABLE = 0x0004  # LE object flag
UNITR = "unitr.dat"
ANDROID = "android"
TRAINING = "training"
LEARNING_AI = ("EXPERIEN.DAT", "BRAIN.DAT", "WEAPEXP.DAT")
MIN_COPIES = 8  # field copies that make a row a record-to-record transfer
COPY_LOOKAHEAD = 3  # instructions between a field load and its store
ARGS_LOOKBACK = 6  # instructions searched back from a call for its register arguments
GUARD_LOOKBACK = 12  # instructions searched back from a get_text call for its guard
CALL_DEPTH = 2
MEM = re.compile(r"^(byte|word|dword) ptr \[(e[a-z]{2})(?: \+ (0x[0-9a-f]+|\d+))?\]$")
SIZE = {"byte": 1, "word": 2, "dword": 4}
RMW = frozenset({"add", "adc", "sub", "sbb", "inc", "dec"})
WRITES = RMW | {"mov", "or", "and", "xor", "shl", "shr", "sar", "neg", "not"}

# Copied from 07-R1-locate.md (Q2 hand-off table, training strings, Learning AI rows); the
# entries marked "this spike" were measured by this script's first run and are pinned here.
EXPECTED = {
    "UFO2P.EXE": {
        "reader": 0x000B2A90,
        "buffer": 0x00241D98,  # this spike
        "stat_update": {0x000B2E80},  # this spike
        "agent_array": 0x00144918,  # this spike: the stat update's destination
        "get_text": 0x00063800,
        "section_table": 0x000F3794,
        "sections": 50,
        "android_label": 0x000F12B6,
        "android_sites": {0x0004F41A},  # this spike
        "android_guards": {0x0004F3F5},  # this spike
        "android_string_rows": {0x0009B840},
        "learning_ai_rows": {0x000A5F40, 0x000A6040, 0x000A61E0},
        "learning_ai_reached": {0x000A6040},  # this spike: through the savegame loader only
        "savegame_loader": 0x000A49D0,
    },
    "TACP.EXE": {
        "writer": 0x000156A0,
        "buffer": 0x002B9310,  # this spike
        "unit_array": 0x00109ED0,  # this spike
        "unit_stride": 0x49C,  # this spike
        "record": 0x92,  # this spike
        "units": 60,  # this spike
        "accrual": {0x00060080, 0x000B26F0},  # this spike (heuristic)
        "learning_ai_rows": {0x00078FE0, 0x00079050, 0x00014AF0, 0x000B20B0},
        "learning_ai_reached": set(),
    },
}  # fmt: skip
PLANT = ("TACP.EXE", "writer", 0x000156B0)


# ---- helpers ----


def data_span(img: Image) -> tuple[int, int]:
    obj = next(o for o in img.raw.objects if not o.flags & OBJ_EXECUTABLE)
    return obj.base, obj.base + obj.vsize


def strings_with(img: Image, keyword: str, *, exact: bool = False) -> list[int]:
    """Starts of the NUL-terminated data strings holding `keyword` (or equal to it)."""
    lo, hi = data_span(img)
    key = keyword.encode()
    found = set()
    at = img.flat.find(key, lo, hi)
    while at >= 0:
        start = at
        while start > lo and img.flat[start - 1] != 0:
            start -= 1
        if not exact or string_at(img, start) == key:
            found.add(start)
        at = img.flat.find(key, at + 1, hi)
    return sorted(found)


def ref_rows(img: Image, va: int) -> set[int]:
    return {row.start for f in img.fields.values() if f.target == va and (row := img.row_at(f.va))}


def imm_target(img: Image, insn: Insn) -> int | None:
    """The linear address an instruction's immediate names (an LE fixup on it), else None."""
    if not insn.imm_offset:
        return None
    fld = img.fields.get(insn.va + insn.imm_offset)
    return fld.target if fld is not None else None


def call_args(img: Image, insns: list[Insn], k: int) -> dict[str, int]:
    """Register -> linear address (fixup) or constant set by `mov reg, imm` before call k."""
    args: dict[str, int] = {}
    for insn in reversed(insns[max(0, k - ARGS_LOOKBACK) : k]):
        ops = operands(insn)
        if insn.is_call:
            break
        if insn.mnemonic != "mov" or len(ops) != 2 or ops[0] in args or not reg_part(ops[0]):
            continue
        value = imm_target(img, insn)
        if value is None:
            try:
                value = int(ops[1], 0)
            except ValueError:
                continue
        args[ops[0]] = value
    return args


def file_call(img: Image, row: int, string: int) -> tuple[int, dict[str, int]] | None:
    """(callee, its register arguments) of the call that takes `string` in a register."""
    insns = img.insns(img.starts[row])
    for k, insn in enumerate(insns):
        if insn.is_call and string in call_args(img, insns, k).values():
            return img.target(insn), call_args(img, insns, k)
    return None


def base_registers(img: Image, row: FunctionRow) -> dict[str, int]:
    """Register -> linear address, for each `mov reg, imm` whose immediate carries a fixup."""
    out = {}
    for insn in img.insns(row):
        ops = operands(insn)
        target = imm_target(img, insn)
        if insn.mnemonic == "mov" and target is not None and ops and ops[0] not in out:
            out[ops[0]] = target
    return out


@dataclass(frozen=True)
class Copy:
    src: str
    src_off: int
    dst: str
    dst_off: int


def copies(img: Image, row: FunctionRow) -> list[Copy]:
    """`mov r, [S + j]` followed (within COPY_LOOKAHEAD, r untouched) by `mov [D + k], r`."""
    insns = img.insns(row)
    out = []
    for k, insn in enumerate(insns):
        ops = operands(insn)
        if insn.mnemonic != "mov" or len(ops) != 2 or not reg_part(ops[0]):
            continue
        src = MEM.match(ops[1])
        if not src:
            continue
        for later in insns[k + 1 : k + 1 + COPY_LOOKAHEAD]:
            lops = operands(later)
            dst = MEM.match(lops[0]) if lops else None
            if later.mnemonic == "mov" and dst and len(lops) == 2 and lops[1] == ops[0]:
                if dst.group(2) != src.group(2):
                    out.append(Copy(src.group(2), int(src.group(3) or "0", 0),
                                    dst.group(2), int(dst.group(3) or "0", 0)))  # fmt: skip
                break
            if lops and reg_part(lops[0]) and reg_part(lops[0])[0] == reg_part(ops[0])[0]:
                break
    return out


def transfers(img: Image, row: FunctionRow, src_base: int) -> list[Copy]:
    """The copies of `row` whose source register holds `src_base`."""
    bases = base_registers(img, row)
    return [c for c in copies(img, row) if bases.get(c.src) == src_base]


def callees(img: Image, start: int) -> set[int]:
    row = img.starts[start]
    return {t for i in img.insns(row) if (t := img.target(i)) in img.starts
            and img.starts[t].kind in ("game", "thunk")
            and not row.start <= t < row.end}  # fmt: skip


def closure(img: Image, start: int, *, skip: frozenset[int] = frozenset(),
            depth: int | None = None) -> set[int]:  # fmt: skip
    seen = {start}
    queue = deque([(start, 0)])
    while queue:
        va, level = queue.popleft()
        if depth is not None and level >= depth:
            continue
        for nxt in callees(img, va) - seen - skip:
            seen.add(nxt)
            queue.append((nxt, level + 1))
    return seen


def section_index(img: Image, exp: dict, va: int) -> tuple[int, int] | None:
    """The get_text (section, index) whose string starts at `va`."""
    starts = sections(img, exp["section_table"], exp["sections"])
    owner = max(((s, n) for n, s in enumerate(starts) if s is not None and s <= va), default=None)
    if owner is None:
        return None
    at, index = owner[0], 0
    while at < va:
        at = img.flat.index(0, at) + 1
        index += 1
    return (owner[1], index) if at == va else None


def guard(img: Image, insns: list[Insn], k: int) -> int | None:
    """The nearest `cmp <size> ptr [reg + off], imm` before call k whose conditional jump skips
    past the call (so the call runs only on the fall-through)."""
    window = insns[max(0, k - GUARD_LOOKBACK) : k]
    for n in range(len(window) - 1, 0, -1):
        jump, cmp = window[n], window[n - 1]
        dest = img.target(jump) if jump.is_conditional else None
        ops = operands(cmp)
        if dest is None or dest <= insns[k].va or cmp.mnemonic != "cmp" or len(ops) != 2:
            continue
        if MEM.match(ops[0]) and not ops[0].endswith("[esp]") and "esp" not in ops[0]:
            return cmp.va
    return None


# ---- claims ----


def claim_handoff(report: Report, img: Image, role: str, exp: dict) -> tuple[int, dict] | None:
    found = strings_with(img, UNITR)
    rows = set().union(*(ref_rows(img, s) for s in found)) if found else set()
    call = file_call(img, min(rows), found[0]) if len(found) == 1 and len(rows) == 1 else None
    args = call[1] if call else {}
    buffer = next((v for r, v in args.items() if v != found[0] and r != "ebx"), None)
    ok = rows == {exp[role]} and buffer == exp["buffer"]
    size = f" bytes {args['ebx']:#x}" if "ebx" in args else ""
    report.claim(img.name, ok, f"unitr-{role}",
                 f"keyword {UNITR} strings {len(found)} at {hxs(found)} refs from {hxs(rows)} "
                 f"expected {hx(exp[role])}; call {hx(call[0]) if call else '-'} buffer "
                 f"{hx(buffer) if buffer else '-'}{size}")  # fmt: skip
    return call


def claim_layout(report: Report, img: Image, exp: dict, call) -> None:
    row = img.starts.get(exp["writer"])
    if row is None:
        report.claim(img.name, False, "record-layout", f"{hx(exp['writer'])} is not a row start")
        return
    steps = {}
    bases = base_registers(img, row)
    for insn in img.insns(row):
        ops = operands(insn)
        if insn.mnemonic == "add" and len(ops) == 2 and ops[0] in bases:
            steps.setdefault(bases[ops[0]], set()).add(int(ops[1], 0) if ops[1][0].isdigit()
                                                        else None)  # fmt: skip
    size = call[1].get("ebx") if call else None
    ok = exp["unit_stride"] in steps.get(exp["unit_array"], set()) \
        and exp["record"] in steps.get(exp["buffer"], set()) \
        and size == exp["units"] * exp["record"]
    report.claim(img.name, ok, "record-layout",
                 f"unit array {hx(exp['unit_array'])} step {exp['unit_stride']:#x}, buffer step "
                 f"{exp['record']:#x}, bytes {size:#x} = {exp['units']} x {exp['record']:#x}"
                 if size else "no byte count")  # fmt: skip


def claim_stat_update(report: Report, img: Image, exp: dict) -> set[int]:
    reached = closure(img, exp["reader"], depth=CALL_DEPTH)
    found, dests, read = set(), set(), set()
    for start in sorted(reached):
        moved = transfers(img, img.starts[start], exp["buffer"])
        if len(moved) >= MIN_COPIES:
            found.add(start)
            bases = base_registers(img, img.starts[start])
            dests |= {bases.get(c.dst) for c in moved if bases.get(c.dst)}
            read |= {c.src_off for c in moved}
    ok = found == exp["stat_update"] and exp["agent_array"] in dests
    report.claim(img.name, ok, "stat-update",
                 f"rows copying >= {MIN_COPIES} fields from {hx(exp['buffer'])} {hxs(found)} "
                 f"({len(read)} buffer fields) into {hxs(dests)}; reached {len(reached)} rows")
    return read


def claim_android(report: Report, img: Image, exp: dict) -> None:
    label = exp["android_label"]
    text = string_at(img, label).lower()
    keyed = ANDROID.encode() in text and TRAINING.encode() in text
    where = section_index(img, exp, label)
    sites, guards = set(), set()
    for row in img.walked():
        insns = img.insns(row)
        for k, (insn, regs) in enumerate(tracked(img, row)):
            if insn.is_call and img.target(insn) == exp["get_text"] \
                    and (regs.get("eax"), regs.get("edx")) == where:
                sites.add(insn.va)
                if (g := guard(img, insns, k)) is not None:
                    guards.add(g)
    ok = keyed and where is not None and sites == exp["android_sites"] \
        and guards == exp["android_guards"]
    report.claim(img.name, ok, "android-label",
                 f"label {hx(label)} keywords {ANDROID}+{TRAINING} {keyed} get_text "
                 f"{where[0] if where else '-'}/{where[1] if where else '-'} sites {hxs(sites)} "
                 f"guard compares {hxs(guards)}")  # fmt: skip
    plain = strings_with(img, ANDROID, exact=True)
    rows = set().union(*(ref_rows(img, s) for s in plain)) if plain else set()
    report.claim(img.name, rows == exp["android_string_rows"], "android-string",
                 f"keyword {ANDROID} exact strings {hxs(plain)} refs from {hxs(rows)}")


def claim_fields(report: Report, ufo: Image, tacp: Image, read: set[int]) -> set[int]:
    exp = EXPECTED["TACP.EXE"]
    row = tacp.starts[exp["writer"]] if exp["writer"] in tacp.starts else None
    moved = transfers(tacp, row, exp["unit_array"]) if row else []
    bases = base_registers(tacp, row) if row else {}
    filled = {c.dst_off: c.src_off for c in moved if bases.get(c.dst) == exp["buffer"]}
    applied = {filled[b] for b in read if b in filled}
    ok = bool(read) and read <= set(filled)
    report.claim(tacp.name, ok, "handoff-fields-agree",
                 f"writer fills {len(filled)} buffer fields from the unit array; the UFO2P stat "
                 f"update ({ufo.name}) copies {len(read)}, all filled {read <= set(filled)}; "
                 f"{len(applied)} unit fields reach agents")  # fmt: skip
    return applied


def accrual(img: Image, exp: dict, serialised: set[int], applied: set[int]) -> set[int]:
    lo = exp["unit_array"]
    hi = lo + exp["unit_stride"] * exp["units"]
    refs = {img.row_at(f.va).start for f in img.fields.values()
            if lo <= f.target < hi and img.row_at(f.va)}  # fmt: skip
    found = set()
    for start in sorted(refs):
        row = img.starts[start]
        if row.kind not in ("game", "thunk") or start == exp["writer"]:
            continue
        for insn in img.insns(row):
            ops = operands(insn)
            if not ops or insn.mnemonic not in WRITES or "[" not in ops[0]:
                continue
            target = mem_global(img, insn)
            if target is not None and lo <= target < hi:
                if (target - lo) % exp["unit_stride"] in serialised:
                    found.add(start)
            elif insn.mnemonic in RMW and (m := MEM.match(ops[0])) and m.group(3) \
                    and int(m.group(3), 0) in applied and m.group(2) != "esp":
                found.add(start)
    return found


def claim_accrual(report: Report, img: Image, exp: dict, applied: set[int]) -> None:
    row = img.starts.get(exp["writer"])
    moved = transfers(img, row, exp["unit_array"]) if row else []
    serialised = {c.src_off for c in moved}
    found = accrual(img, exp, serialised, applied)
    report.claim(img.name, found == exp["accrual"], "accrual-sites",
                 f"{len(found)} rows {hxs(found)} (serialised unit fields {len(serialised)}, "
                 f"applied {len(applied)}; heuristic, data-field)")  # fmt: skip


def claim_learning_ai(report: Report, img: Image, exp: dict, start: int) -> None:
    if start not in img.starts:
        report.claim(img.name, False, "learning-ai-files", f"{hx(start)} is not a row start")
        return
    strings = [s for key in LEARNING_AI for s in strings_with(img, key)]
    rows = set().union(*(ref_rows(img, s) for s in strings)) if strings else set()
    reached = closure(img, start) & rows
    skip = frozenset({exp["savegame_loader"]}) if "savegame_loader" in exp else frozenset()
    without = closure(img, start, skip=skip) & rows
    ok = rows == exp["learning_ai_rows"] and reached == exp["learning_ai_reached"] and not without
    via = f" (none without {hx(exp['savegame_loader'])}: {not without})" if skip else ""
    report.claim(img.name, ok, "learning-ai-files",
                 f"keyword strings {len(strings)} refs from {hxs(rows)}; reached from "
                 f"{hx(start)} {hxs(reached)}{via}")  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plant", action="store_true", help="a wrong writer address")
    args = parser.parse_args(argv)
    if args.plant:
        name, key, wrong = PLANT
        print(f"PLANT {name} expected {key} {hx(EXPECTED[name][key])} -> {hx(wrong)}")
        EXPECTED[name][key] = wrong
    report = Report()
    ufo, tacp = (Image(name) for name in EXES)
    uexp, texp = EXPECTED["UFO2P.EXE"], EXPECTED["TACP.EXE"]
    claim_handoff(report, ufo, "reader", uexp)
    read = claim_stat_update(report, ufo, uexp)
    claim_android(report, ufo, uexp)
    claim_learning_ai(report, ufo, uexp, uexp["reader"])
    call = claim_handoff(report, tacp, "writer", texp)
    claim_layout(report, tacp, texp, call)
    applied = claim_fields(report, ufo, tacp, read)
    claim_accrual(report, tacp, texp, applied)
    claim_learning_ai(report, tacp, texp, texp["writer"])
    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
