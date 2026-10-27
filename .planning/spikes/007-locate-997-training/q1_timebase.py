"""Spike 007 q1: what paces game time in UFO2P.EXE and TACP.EXE (D-03 as refined by D-26).

Claims, per EXE:
- raw-image: the flat image and fixups read by the independent rawle.py equal le.py's view;
- pit-int8-sites: every PIT port write (0x43 mode, 0x40 counter 0) and every INT 8 vector
  get/set with a constant vector (DPMI 0200h/0201h/0204h/0205h with BL=8, DOS 35h/25h with AL=8,
  inline or through int386_ / _dos_getvect_ / _dos_setvect_) lies inside the sound-library span;
- unresolved-vectors: vector get/set sites whose vector is not a constant sit only in the
  keyboard-handler installers (their vector comes from the DPMI PIC base at run time);
- int1a-readers: the game rows that call the runtime int386_ with 0x1A (BIOS tick) in eax at the
  call are exactly the EXPECTED readers (immediate in the block, or a register the row sets once);
- callers-<addr>: each reader's direct caller count, from this script's own call scan, equals
  EXPECTED and the count reverseapoc.contextpack.CallIndex reports;
- no-46c-read: no game or thunk row reads the BIOS tick word at linear 0x46C directly;
- bios-chain-cadence (fix round 1): while the sound library owns INT 8, the BIOS tick still
  advances at 18.2 Hz. The install saves the old INT 8 vector; one row far-returns into it (the
  chain); an event callback calls that row and the timer init registers it; the rows that set
  the event increments divide 0x123333 (18.2 in 16.16) by the PIT rate for that event (and store
  0x10000, one fire per interrupt, at the DOS rate); a callback the init installs adds the
  increments to the event accumulators (that the INT 8 handler calls it on every interrupt is
  hand-read, not checked here).

Run from the main checkout (orig/ is gitignored):
    uv run python .planning/spikes/007-locate-997-training/q1_timebase.py
        [--plant] [--mutant] [--plant-chain]

--plant swaps one EXPECTED reader address for a wrong one; --mutant zeroes every `mov reg, 0x1a`
immediate of the game rows in an in-memory copy of the flat image; --plant-chain expects the PIT
clock (0x1234DC) instead of 0x123333 as the chain dividend, i.e. a BIOS tick that follows the
PIT rate. All three runs must FAIL.

Reads orig/ only and writes nothing. Prints addresses, counts, booleans and protocol constants
(interrupt numbers, ports, function codes), never game bytes or instruction text.

The other spike 007 scripts import the shared reader below (Image, insns, Regs, Report).
"""

from __future__ import annotations

import argparse
import bisect
import importlib.util
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from reverseapoc import check, targets
from reverseapoc.contextpack import CallIndex
from reverseapoc.functions import KIND_GAME, KIND_THUNK, FunctionRow
from reverseapoc.x86 import Insn, decode

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RAWLE = HERE.parent / "001-le-pages-and-fixups" / "rawle.py"
EXES = ("UFO2P.EXE", "TACP.EXE")
WALKED = (KIND_GAME, KIND_THUNK)


def _load_rawle():
    """rawle.py by path, registered in sys.modules before exec (its dataclasses need that)."""
    spec = importlib.util.spec_from_file_location("rawle", RAWLE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["rawle"] = module
    spec.loader.exec_module(module)
    return module


rawle = _load_rawle()

# Protocol constants (BIOS, PIT, DOS, DPMI), not game data.
INT_BIOS_TICK = 0x1A
INT_DOS = 0x21
INT_DPMI = 0x31
IRQ0_VECTOR = 8
PIT_PORTS = frozenset({0x40, 0x43})  # counter 0 data, mode/command
DPMI_VECTOR_FUNCS = frozenset({0x200, 0x201, 0x204, 0x205})  # get/set real/protected vector
DOS_VECTOR_FUNCS = frozenset({0x25, 0x35})  # AH: set / get interrupt vector
BIOS_TICK_WORD = 0x46C  # linear address of the BIOS tick count
REGS_AX = 0  # union REGS: eax/ax at offset 0, ebx/bx/bl at offset 4
REGS_BX = 4
VECTOR_RUNTIME = ("_dos_getvect_", "_dos_setvect_")
VECTOR_GETS = ("ax-0x200", "ax-0x204", "ah-0x35")  # site labels of a vector *get*
GET_WINDOW = 2  # stores of the old vector right after the get
DIV_WINDOW = 3  # instructions between a dividend load and its `div`
PIT_CLOCK = 0x1234DC  # 1,193,180: the PIT input clock as the sound library writes it
DOS_RATE_MARKER = 0xFF00  # the sound library's "DOS rate" event rate
CHAIN_ONE = 0x10000  # an event fires when its 16.16 accumulator passes 1.0
CHAIN_DIVIDEND = 0x123333  # 18.2 in 16.16 (this spike): chain increment = it / PIT Hz
INT386 = ("int386_", "int386x_")

# Copied from 07-R1-locate.md "#997 FINDING" and Q2 "Timer"; `pinned_readers` is this spike's
# own finding (a 0x1A passed through a register the row sets once), recorded in the README.
EXPECTED = {
    "UFO2P.EXE": {
        "sound_span": (0x000C8E41, 0x000C90F3),
        "pit_int8_rows": {0x000C8EBD, 0x000C8F03, 0x000C901D},
        "keyboard_rows": {0x000B7280, 0x000B73D0},
        "readers": {0x00011430},
        "pinned_readers": {0x00010940},
        "callers": {0x00011430: 28},
        "chain": {"chain_row": 0x000C9099, "thunk": 0x000C3692, "slot_writer": 0x000C2F1F,
                  "rate_rows": {0x000C3035, 0x000C33BA}, "adder": 0x000C35C8,
                  "constant": CHAIN_DIVIDEND},  # this spike
    },
    "TACP.EXE": {
        "sound_span": (0x000CC151, 0x000CC402),
        "pit_int8_rows": {0x000CC1CD, 0x000CC213, 0x000CC32D},
        "keyboard_rows": {0x000A5750, 0x000A58A0},
        "readers": {0x00011500, 0x000116B0},
        "pinned_readers": set(),
        "callers": {0x00011500: 35, 0x000116B0: 10},
        "chain": {"chain_row": 0x000CC3A9, "thunk": 0x000C6386, "slot_writer": 0x000C5C13,
                  "rate_rows": {0x000C5D29, 0x000C60AE}, "adder": 0x000C62BC,
                  "constant": CHAIN_DIVIDEND},  # this spike
    },
}
PLANT = ("UFO2P.EXE", 0x00011430, 0x00011440)  # (exe, true reader, planted wrong address)


# ---- report ----


@dataclass
class Report:
    failures: int = 0

    def claim(self, exe: str, ok: bool, claim: str, detail: str = "") -> bool:
        self.failures += not ok
        print(f"{'PASS' if ok else 'FAIL'} {exe} {claim} {detail}".rstrip())
        return ok

    def finish(self) -> int:
        print("ALL PASS" if self.failures == 0 else f"{self.failures} FAILED")
        return 1 if self.failures else 0


def hx(va: int) -> str:
    return f"0x{va:08X}"


def hxs(vas) -> str:
    return "[" + " ".join(hx(va) for va in sorted(vas)) + "]"


# ---- the image, read raw ----


@dataclass(frozen=True)
class Field:
    """One raw LE fixup field: where it sits and the linear address it resolves to."""

    va: int
    size: int
    target: int
    kind: int


def raw_flat(raw) -> bytearray:
    """Each object's page bytes copied to its base (identity page map, spike 001)."""
    flat = bytearray(max(o.base + o.vsize for o in raw.objects))
    for obj in raw.objects:
        va = obj.base
        for logical in range(obj.page_index, obj.page_index + obj.page_count):
            number = raw.pages[logical - 1].number_be24
            size = raw.page_size_of(number)
            at = raw.page_file_offset(number)
            chunk = raw.data[at : at + size][: max(0, len(flat) - va)]
            flat[va : va + len(chunk)] = chunk
            va += raw.page_size
    return flat


def raw_fields(raw) -> dict[int, Field]:
    """Every fixup field once (a page-straddling field is listed on both pages)."""
    out: dict[int, Field] = {}
    for rec in raw.fixup_records():
        target = raw.objects[rec.target_obj - 1].base + rec.target_off
        out.setdefault(rec.va, Field(rec.va, rec.size, target, rec.kind))
    return out


class Image:
    """One EXE: bytes and fixups from rawle.py, function rows from load_exe (functions.csv)."""

    def __init__(self, name: str) -> None:
        manifest = targets.load_manifest()
        target = next(t for t in manifest if t.name == name)
        self.name = name
        self.inputs = check.load_exe(target, orig_dir=REPO / "orig",
                                     manifest=targets.DEFAULT_MANIFEST,
                                     config_root=REPO / "config")  # fmt: skip
        self.raw = rawle.RawLE((REPO / "orig" / name).read_bytes())
        self.flat = raw_flat(self.raw)
        self.fields = raw_fields(self.raw)
        self.sites = sorted(self.fields)
        self.rows: tuple[FunctionRow, ...] = self.inputs.rows
        self.starts = {row.start: row for row in self.rows}
        self.named = {row.name: row.start for row in self.rows}
        self._row_starts = [row.start for row in self.rows]
        self._insns: dict[int, list[Insn]] = {}

    def walked(self) -> Iterator[FunctionRow]:
        return (row for row in self.rows if row.kind in WALKED)

    def row_at(self, va: int) -> FunctionRow | None:
        """The functions.csv row containing `va`."""
        i = bisect.bisect_right(self._row_starts, va) - 1
        if i >= 0 and self.rows[i].start <= va < self.rows[i].end:
            return self.rows[i]
        return None

    def fields_in(self, start: int, end: int) -> list[Field]:
        lo = bisect.bisect_left(self.sites, start)
        hi = bisect.bisect_left(self.sites, end)
        return [self.fields[va] for va in self.sites[lo:hi]]

    def insns(self, row: FunctionRow, flat: bytes | bytearray | None = None) -> list[Insn]:
        """The row's instructions; a fixup field at an instruction start is inline data."""
        if flat is None and row.start in self._insns:
            return self._insns[row.start]
        found = list(walk(self, row, self.flat if flat is None else flat))
        if flat is None:
            self._insns[row.start] = found
        return found

    def target(self, insn: Insn) -> int | None:
        """A direct branch's destination; an LE rel32 fixup on its field wins."""
        if insn.branch_target is None:
            return None
        fld = self.fields.get(insn.rel32_field) if insn.rel32_field is not None else None
        return fld.target if fld is not None else insn.branch_target


def walk(img: Image, row: FunctionRow, flat: bytes | bytearray) -> Iterator[Insn]:
    sites = frozenset(f.va for f in img.fields_in(row.start, row.end))
    code = bytes(flat[row.start : row.end])
    pos = row.start
    while pos < row.end:
        if pos in sites:
            pos += img.fields[pos].size
            continue
        before = pos
        for insn in decode(code[pos - row.start :], pos, data_sites=sites):
            yield insn
            pos = insn.va + insn.size
        if pos == before:
            pos += 1


# ---- a spike-grade constant tracker ----

REG32 = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp")
SUBREG = {
    "ax": ("eax", 0xFFFF, 0), "al": ("eax", 0xFF, 0), "ah": ("eax", 0xFF, 8),
    "bx": ("ebx", 0xFFFF, 0), "bl": ("ebx", 0xFF, 0), "bh": ("ebx", 0xFF, 8),
    "cx": ("ecx", 0xFFFF, 0), "cl": ("ecx", 0xFF, 0), "ch": ("ecx", 0xFF, 8),
    "dx": ("edx", 0xFFFF, 0), "dl": ("edx", 0xFF, 0), "dh": ("edx", 0xFF, 8),
    "si": ("esi", 0xFFFF, 0), "di": ("edi", 0xFFFF, 0), "bp": ("ebp", 0xFFFF, 0),
}  # fmt: skip
FULL = 0xFFFFFFFF
NO_WRITE = frozenset({"cmp", "test", "push", "out", "bt"})
# Instructions that write registers not named as their first operand (the last word of the
# mnemonic, so `rep movsd` counts as movsd).
STRING_OP = re.compile(r"^(?:movs|stos|lods|scas|cmps|ins|outs)[bwd]$")
IMPLICIT = {
    frozenset({"cdq", "cwd", "cbw", "cwde", "mul", "imul", "div", "idiv", "lahf", "xlatb", "in",
               "cpuid", "rdtsc", "aaa", "aas", "aam", "aad", "daa", "das"}): ("eax", "edx"),
    frozenset({"loop", "loope", "loopne", "jecxz"}): ("ecx",),
    frozenset({"pusha", "popa", "pushal", "popal", "xchg", "cmpxchg", "xadd"}): REG32,
}  # fmt: skip
STACK_MEM = re.compile(r"^(?:byte|word|dword) ptr \[esp(?: \+ (0x[0-9a-f]+|\d+))?\]$")
LEA_ESP = re.compile(r"^\[esp(?: \+ (0x[0-9a-f]+|\d+))?\]$")
SIZE_MASK = {"byte": 0xFF, "word": 0xFFFF, "dword": FULL}


def operands(insn: Insn) -> list[str]:
    return [op.strip() for op in insn.op_str.split(",")] if insn.op_str else []


def imm(text: str) -> int | None:
    try:
        return int(text, 0)
    except ValueError:
        return None


def reg_part(op: str) -> tuple[str, int, int] | None:
    if op in REG32:
        return op, FULL, 0
    return SUBREG.get(op)


def implicit_writes(mnemonic: str) -> tuple[str, ...]:
    word = mnemonic.split()[-1]
    if STRING_OP.match(word):
        return ("eax", "ecx", "esi", "edi")
    for names, regs in IMPLICIT.items():
        if word in names:
            return regs
    return ()


def pinned_registers(insns: list[Insn]) -> dict[str, tuple[int, int]]:
    """Registers (not eax/esp) whose only write in the row is one `mov reg, imm`, besides
    prologue/epilogue push/pop: register -> (value, address of the write)."""
    writes: dict[str, list[tuple[int, int | None]]] = {}
    for insn in insns:
        ops = operands(insn)
        for reg in implicit_writes(insn.mnemonic):
            writes.setdefault(reg, []).append((insn.va, None))
        if not ops or insn.mnemonic in NO_WRITE or insn.mnemonic == "pop":
            continue
        part = reg_part(ops[0])
        if part is None or insn.is_jump or insn.is_call:
            continue
        value = imm(ops[1]) if insn.mnemonic == "mov" and len(ops) == 2 else None
        if part[1] != FULL:
            value = None
        writes.setdefault(part[0], []).append((insn.va, value))
    return {reg: (found[0][1], found[0][0]) for reg, found in writes.items()
            if reg not in ("eax", "esp") and len(found) == 1
            and found[0][1] is not None}  # fmt: skip


@dataclass
class Regs:
    """Register and esp-slot constants along a linear walk of one row. Values are ints, or
    ("esp", k) for an address k bytes above esp. Everything is forgotten at a jump target and
    at an esp change, eax/edx at a call (Watcom returns there), eax-edx after an `int`; a
    pinned register (see pinned_registers) keeps its value after its one write."""

    pinned: dict[str, tuple[int, int]]
    vals: dict[str, object] = field(default_factory=dict)
    parts: dict[tuple[str, int, int], int] = field(default_factory=dict)
    stack: dict[int, tuple[object, int]] = field(default_factory=dict)

    def reset(self, va: int) -> None:
        self.vals = {r: v for r, (v, at) in self.pinned.items() if at < va}
        self.parts = {}
        self.stack = {}

    def get(self, op: str):
        part = reg_part(op)
        if part is None:
            return None
        reg, mask, shift = part
        full = self.vals.get(reg)
        if isinstance(full, int):
            return (full >> shift) & mask
        if mask == FULL:
            return full
        return self.parts.get(part)

    def put(self, op: str, value) -> None:
        part = reg_part(op)
        if part is None:
            return
        reg, mask, shift = part
        self.parts = {k: v for k, v in self.parts.items() if k[0] != reg or k == part}
        if mask == FULL:
            self.parts = {k: v for k, v in self.parts.items() if k[0] != reg}
            self._set(reg, value)
            return
        full = self.vals.get(reg)
        if isinstance(full, int) and isinstance(value, int):
            self.vals[reg] = (full & ~(mask << shift)) | ((value & mask) << shift)
            return
        self.vals.pop(reg, None)
        if isinstance(value, int):
            self.parts[part] = value & mask
        else:
            self.parts.pop(part, None)

    def _set(self, reg: str, value) -> None:
        if value is None:
            self.vals.pop(reg, None)
        else:
            self.vals[reg] = value & FULL if isinstance(value, int) else value

    def slot(self, offset: int, mask: int):
        """The constant stored at [esp + offset], masked, or None."""
        found = self.stack.get(offset)
        if found is None or not isinstance(found[0], int):
            return None
        return found[0] & mask & found[1]

    def step(self, insn: Insn, labels: frozenset[int]) -> None:
        """Advance over `insn` (call this after reading the state before it)."""
        ops = operands(insn)
        mn = insn.mnemonic
        if insn.is_call:
            self.vals.pop("eax", None)
            self.vals.pop("edx", None)
            self.parts = {k: v for k, v in self.parts.items() if k[0] not in ("eax", "edx")}
            self.stack = {}
            return
        if mn == "int":
            for reg in ("eax", "ebx", "ecx", "edx"):
                self.put(reg, None)
            return
        for reg in implicit_writes(mn):
            self.put(reg, None)
        if mn in ("push", "pop", "pushal", "popal", "pushfd", "popfd") or (ops and ops[0] == "esp"):
            self.stack = {}
        if not ops or mn in NO_WRITE or insn.is_jump:
            return
        if len(ops) == 2 and (m := STACK_MEM.match(ops[0])) and mn == "mov":
            size = ops[0].split(" ", 1)[0]
            src = imm(ops[1])
            if src is None and reg_part(ops[1]):
                src = self.get(ops[1])
            self.stack[int(m.group(1) or "0", 0)] = (src, SIZE_MASK[size])
            return
        if reg_part(ops[0]) is None:
            return
        self.put(ops[0], self._value(mn, ops))

    def _value(self, mn: str, ops: list[str]):
        if mn == "mov" and len(ops) == 2:
            value = imm(ops[1])
            if value is not None:
                return value
            if ops[1] == "esp":
                return ("esp", 0)
            return self.get(ops[1]) if reg_part(ops[1]) else None
        if mn in ("xor", "sub") and len(ops) == 2 and ops[0] == ops[1]:
            return 0
        if mn == "lea" and len(ops) == 2 and (m := LEA_ESP.match(ops[1])):
            return ("esp", int(m.group(1) or "0", 0))
        return None


def jump_targets(img: Image, insns: list[Insn]) -> frozenset[int]:
    return frozenset(t for i in insns if i.is_jump and (t := img.target(i)) is not None)


def tracked(img: Image, row: FunctionRow, flat=None) -> Iterator[tuple[Insn, Regs]]:
    """Each instruction of the row with the register state just before it."""
    insns = img.insns(row, flat)
    labels = jump_targets(img, insns)
    regs = Regs(pinned_registers(insns))
    regs.reset(row.start)
    for insn in insns:
        if insn.va in labels:
            regs.reset(insn.va)
        yield insn, regs
        regs.step(insn, labels)


def direct_callers(img: Image) -> dict[int, set[int]]:
    """Rows whose direct call or jump lands on another row's start (a jump there is a tail
    call), rebuilt here as CallIndex defines it but from the raw image and fixups."""
    callers: dict[int, set[int]] = {}
    for row in img.walked():
        for insn in img.insns(row):
            dest = img.target(insn)
            if dest in img.starts and not row.start <= dest < row.end:
                callers.setdefault(dest, set()).add(row.start)
    return callers


# ---- q1 scans ----


@dataclass
class Sites:
    pit: dict[int, int] = field(default_factory=dict)  # site -> port
    int8: dict[int, str] = field(default_factory=dict)  # site -> how
    unresolved: dict[int, str] = field(default_factory=dict)
    readers: dict[int, list[int]] = field(default_factory=dict)  # row -> int386 0x1A sites
    pinned: set[int] = field(default_factory=set)  # rows whose 0x1A came via a pinned reg


def scan(img: Image, flat=None) -> Sites:
    sites = Sites()
    int386 = {img.named[n] for n in INT386 if n in img.named}
    vector_rt = {img.named[n] for n in VECTOR_RUNTIME if n in img.named}
    for row in img.walked():
        for insn, regs in tracked(img, row, flat):
            _pit(sites, insn, regs)
            _inline_int(sites, insn, regs)
            dest = img.target(insn) if insn.is_call else None
            if dest in vector_rt:
                _vector_call(sites, insn, regs, img.starts[dest].name)
            if dest in int386:
                _int386_call(sites, row, insn, regs)
    return sites


def _pit(sites: Sites, insn: Insn, regs: Regs) -> None:
    if insn.mnemonic != "out":
        return
    port_op = operands(insn)[0]
    port = regs.get("dx") if port_op == "dx" else imm(port_op)
    if port in PIT_PORTS:
        sites.pit[insn.va] = port


def _vector_op(sites: Sites, va: int, how: str, vector) -> None:
    if vector == IRQ0_VECTOR:
        sites.int8[va] = how
    elif vector is None:
        sites.unresolved[va] = how


def _inline_int(sites: Sites, insn: Insn, regs: Regs) -> None:
    if insn.mnemonic != "int":
        return
    number = imm(operands(insn)[0])
    if number == INT_DPMI and regs.get("ax") in DPMI_VECTOR_FUNCS:
        _vector_op(sites, insn.va, f"int-0x31-ax-{regs.get('ax'):#x}", regs.get("bl"))
    if number == INT_DOS and regs.get("ah") in DOS_VECTOR_FUNCS:
        _vector_op(sites, insn.va, f"int-0x21-ah-{regs.get('ah'):#x}", regs.get("al"))


def _vector_call(sites: Sites, insn: Insn, regs: Regs, name: str) -> None:
    vector = regs.get("eax")
    _vector_op(sites, insn.va, name, vector if isinstance(vector, int) else None)


def _int386_call(sites: Sites, row: FunctionRow, insn: Insn, regs: Regs) -> None:
    number = regs.get("eax")
    if number == INT_BIOS_TICK:
        sites.readers.setdefault(row.start, []).append(insn.va)
        if any(value == INT_BIOS_TICK for value, _ in regs.pinned.values()):
            sites.pinned.add(row.start)
        return
    inregs = regs.get("edx")
    if number not in (INT_DPMI, INT_DOS) or not isinstance(inregs, tuple):
        return
    base = inregs[1]
    ax = regs.slot(base + REGS_AX, 0xFFFF)
    vec = regs.slot(base + REGS_BX, 0xFF)
    if number == INT_DPMI and ax in DPMI_VECTOR_FUNCS:
        _vector_op(sites, insn.va, f"int386-0x31-ax-{ax:#x}", vec)
    if number == INT_DOS and ax is not None and ax >> 8 in DOS_VECTOR_FUNCS:
        _vector_op(sites, insn.va, f"int386-0x21-ah-{ax >> 8:#x}", ax & 0xFF)


def readers_found(sites: Sites) -> tuple[set[int], set[int]]:
    """(rows with 0x1A as an immediate in the block, rows with it via a pinned register)."""
    via = set(sites.pinned)
    return set(sites.readers) - via, via


def abs_46c_reads(img: Image) -> list[int]:
    """Game/thunk instructions with an absolute [0x46c] memory operand and no fixup on it."""
    pattern = re.compile(rf"\[(?:[a-z]s:)?{BIOS_TICK_WORD:#x}\]")
    out = []
    for row in img.walked():
        for insn in img.insns(row):
            if not pattern.search(insn.op_str):
                continue
            if not img.fields_in(insn.va, insn.va + insn.size):
                out.append(insn.va)
    return out


def mutant_flat(img: Image) -> bytearray:
    """A copy of the flat image with the immediate of every `mov reg, 0x1a` in a game or thunk
    row zeroed (the mutant must lose every BIOS-tick reader)."""
    flat = bytearray(img.flat)
    for row in img.walked():
        for insn in img.insns(row):
            ops = operands(insn)
            if insn.mnemonic == "mov" and len(ops) == 2 and reg_part(ops[0]) \
                    and imm(ops[1]) == INT_BIOS_TICK and insn.imm_offset:
                flat[insn.va + insn.imm_offset] = 0
    return flat


# ---- claims ----


def claim_image(report: Report, img: Image) -> None:
    le = img.inputs.le
    same = all(img.flat[o.base : o.base + o.vsize] == img.inputs.flat[o.base : o.base + o.vsize]
               for o in le.objects)  # fmt: skip
    ours = {(f.va, f.target) for f in img.fields.values()}
    theirs = {(f.src_va, f.target_va) for f in img.inputs.fixups}
    report.claim(img.name, same and ours == theirs, "raw-image",
                 f"objects {len(img.raw.objects)} bytes-equal {same} "
                 f"fixups {len(ours)} equal-to-le.py {ours == theirs}")  # fmt: skip


def claim_sites(report: Report, img: Image, sites: Sites, exp: dict) -> None:
    lo, hi = exp["sound_span"]
    every = set(sites.pit) | set(sites.int8)
    inside = all(lo <= va < hi for va in every)
    rows = {img.row_at(va).start for va in every}
    report.claim(img.name, inside and bool(every) and rows == exp["pit_int8_rows"],
                 "pit-int8-sites",
                 f"pit {len(sites.pit)} int8 {len(sites.int8)} all in {hx(lo)}..{hx(hi)} "
                 f"{inside} rows {hxs(rows)}")  # fmt: skip
    urows = {img.row_at(va).start for va in sites.unresolved}
    report.claim(img.name, urows <= exp["keyboard_rows"], "unresolved-vectors",
                 f"{len(sites.unresolved)} sites in rows {hxs(urows)}")


def claim_readers(report: Report, img: Image, sites: Sites, exp: dict) -> None:
    direct, via = readers_found(sites)
    report.claim(img.name, direct == exp["readers"], "int1a-readers",
                 f"immediate {hxs(direct)} expected {hxs(exp['readers'])}")
    report.claim(img.name, via == exp["pinned_readers"], "int1a-pinned-readers",
                 f"via a register set once {hxs(via)} expected {hxs(exp['pinned_readers'])}")


def claim_callers(report: Report, img: Image, exp: dict) -> None:
    ours = direct_callers(img)
    index = CallIndex.build(img.inputs.rows, img.inputs.flat, img.inputs.fixups)
    for reader, count in sorted(exp["callers"].items()):
        mine = len(ours.get(reader, ()))
        theirs = len(index.callers_of(reader))
        report.claim(img.name, mine == count == theirs, f"callers-{hx(reader)}",
                     f"own scan {mine} CallIndex {theirs} expected {count}")


def claim_46c(report: Report, img: Image) -> None:
    found = abs_46c_reads(img)
    report.claim(img.name, not found, "no-46c-read", f"absolute [0x46c] reads {len(found)}")


# ---- the BIOS-tick cadence while the sound timer owns INT 8 (fix round 1) ----


def _field_target(img: Image, insn: Insn, offset: int) -> int | None:
    if not offset:
        return None
    fld = img.fields.get(insn.va + offset)
    return fld.target if fld is not None else None


def saved_vector(img: Image, sites: Sites) -> set[int]:
    """The globals the INT 8 install stores right after its vector *get* (the old handler's
    offset and selector): `mov [G], reg` within GET_WINDOW instructions of the get site."""
    found: set[int] = set()
    for va, how in sites.int8.items():
        if not how.endswith(VECTOR_GETS):
            continue
        insns = img.insns(img.row_at(va))
        k = next(n for n, i in enumerate(insns) if i.va == va)
        for insn in insns[k + 1 : k + 1 + GET_WINDOW]:
            target = _field_target(img, insn, insn.disp_offset)
            if insn.mnemonic == "mov" and target is not None and "[" in operands(insn)[0]:
                found.add(target)
    return found


@dataclass
class Chain:
    saved: set[int]
    chain_rows: set[int]  # load the saved old vector and far-return into it
    thunks: set[int]  # call a chain row (the event callback)
    slot_writers: set[int]  # store a thunk's address (register the event)
    rate_rows: set[int]  # same unit: compare with the DOS-rate marker and divide
    constants: set[int]  # the dividend of the chain increment (not the PIT clock)
    increments: set[int]  # arrays the rate rows store 0x10000 (one fire per interrupt) into
    adders: set[int]  # same unit: rows adding an increment-array entry to an accumulator
    installed: set[int]  # code addresses the slot writers pass as immediates (ISR callback)


def bios_chain(img: Image, sites: Sites) -> Chain:
    saved = saved_vector(img, sites)
    chain_rows = set()
    for row in img.walked():
        insns = img.insns(row)
        loads = any(_field_target(img, i, i.disp_offset) in saved for i in insns
                    if i.mnemonic == "mov" and reg_part(operands(i)[0] if i.op_str else ""))
        if loads and any(i.mnemonic == "retf" for i in insns):
            chain_rows.add(row.start)
    thunks = {row.start for row in img.walked()
              if any(i.is_call and img.target(i) in chain_rows for i in img.insns(row))}
    writers = {row.start for row in img.walked()
               if any(_field_target(img, i, i.imm_offset) in thunks for i in img.insns(row))}
    units = {img.starts[w].unit for w in writers}
    rate_rows, constants = set(), set()
    for row in img.walked():
        if row.unit not in units:
            continue
        insns = img.insns(row)
        if not any(i.mnemonic == "cmp" and imm(operands(i)[-1]) == DOS_RATE_MARKER
                   for i in insns if i.op_str):
            continue
        for k, insn in enumerate(insns):
            ops = operands(insn)
            if insn.mnemonic != "mov" or ops[:1] != ["eax"] or imm(ops[-1]) in (None, PIT_CLOCK):
                continue
            if any(i.mnemonic == "div" for i in insns[k + 1 : k + 1 + DIV_WINDOW]):
                rate_rows.add(row.start)
                constants.add(imm(ops[-1]))
    increments = {t for va in rate_rows for i in img.insns(img.starts[va])
                  if i.mnemonic == "mov" and i.op_str and imm(operands(i)[-1]) == CHAIN_ONE
                  and (t := _field_target(img, i, i.disp_offset)) is not None}  # fmt: skip
    adders = {row.start for row in img.walked() if row.unit in units
              and _adds_from(img, img.insns(row), increments)}  # fmt: skip
    installed = {t for w in writers for i in img.insns(img.starts[w])
                 if (t := _field_target(img, i, i.imm_offset)) in img.starts}  # fmt: skip
    return Chain(saved, chain_rows, thunks, writers, rate_rows, constants, increments, adders,
                 installed)


def _adds_from(img: Image, insns: list[Insn], arrays: set[int]) -> bool:
    """`mov r, [x + A]` (A in arrays) followed by `add [y + B], r` within DIV_WINDOW."""
    for k, insn in enumerate(insns):
        ops = operands(insn)
        if insn.mnemonic != "mov" or len(ops) != 2 or not reg_part(ops[0]):
            continue
        if _field_target(img, insn, insn.disp_offset) not in arrays:
            continue
        for later in insns[k + 1 : k + 1 + DIV_WINDOW]:
            lops = operands(later)
            if later.mnemonic == "add" and len(lops) == 2 and "[" in lops[0] and lops[1] == ops[0]:
                return True
    return False


def claim_chain(report: Report, img: Image, sites: Sites, exp: dict) -> None:
    chain = bios_chain(img, sites)
    want = exp["chain"]
    found = (chain.chain_rows, chain.thunks, chain.slot_writers, chain.rate_rows, chain.adders)
    ok = found == ({want["chain_row"]}, {want["thunk"]}, {want["slot_writer"]},
                   want["rate_rows"], {want["adder"]}) \
        and chain.constants == {want["constant"]} and bool(chain.increments) \
        and chain.adders <= chain.installed
    rate = ", ".join(f"{c:#x}/0x10000 = {c / CHAIN_ONE:.4f} Hz" for c in sorted(chain.constants))
    report.claim(img.name, ok, "bios-chain-cadence",
                 f"saved old INT 8 vector {hxs(chain.saved)}; chain rows {hxs(chain.chain_rows)} "
                 f"via event callback {hxs(chain.thunks)} registered by "
                 f"{hxs(chain.slot_writers)}; increment dividend in {hxs(chain.rate_rows)}: "
                 f"{rate or '-'} (expected {want['constant']:#x}); increments "
                 f"{hxs(chain.increments)} added in {hxs(chain.adders)}, a callback the same "
                 f"writer installs: {chain.adders <= chain.installed}")


def expected(plant: bool, plant_chain: bool = False) -> dict:
    exp = {name: {k: (set(v) if isinstance(v, set) else dict(v) if isinstance(v, dict) else v)
                  for k, v in values.items()} for name, values in EXPECTED.items()}  # fmt: skip
    if plant:
        name, true, wrong = PLANT
        exp[name]["readers"] = (exp[name]["readers"] - {true}) | {wrong}
        print(f"PLANT {name} expected reader {hx(true)} -> {hx(wrong)}")
    if plant_chain:
        for name in EXES:
            exp[name]["chain"] = dict(exp[name]["chain"], constant=PIT_CLOCK)
        print(f"PLANT expected chain dividend {CHAIN_DIVIDEND:#x} -> {PIT_CLOCK:#x} "
              "(the BIOS tick would follow the PIT rate)")
    return exp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plant", action="store_true", help="one wrong EXPECTED reader")
    parser.add_argument("--mutant", action="store_true", help="zero the 0x1A immediates")
    parser.add_argument("--plant-chain", action="store_true",
                        help="expect the PIT clock as the BIOS-chain dividend")  # fmt: skip
    args = parser.parse_args(argv)
    exp_all = expected(args.plant, args.plant_chain)
    report = Report()
    for name in EXES:
        img = Image(name)
        exp = exp_all[name]
        flat = mutant_flat(img) if args.mutant else None
        if args.mutant:
            print(f"MUTANT {name} 0x1A immediates zeroed in an in-memory copy")
        claim_image(report, img)
        sites = scan(img, flat)
        claim_sites(report, img, sites, exp)
        claim_readers(report, img, sites, exp)
        claim_callers(report, img, exp)
        claim_46c(report, img)
        claim_chain(report, img, sites, exp)
    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
