# SPDX-License-Identifier: GPL-3.0-or-later
"""The converter: one Watcom 10.6 `-4r` function row to C89, from le.py bytes and fixups, decoded
with capstone (the same pinned instance as reverseapoc.x86).

Moved from spike 010 (.planning/spikes/010-deterministic-matching/lift.py), which keeps its own
copy.

Design (the spike's README, "Q3"): basic blocks; symbolic execution per block, where a register
holds a C expression tree; registers live across a block edge become C variables named after the
register (`r_ebx`), and register arguments are parameters with those names; stores, calls,
branches and returns become statements; branches are `if (c) goto L;`. Stack slots are locals
typed by their access width. Globals are `extern char D_<target>[]` read through casts. Anything
else raises Unliftable with a short reason, which the harness counts as a failure group.
"""

from __future__ import annotations

import bisect
import itertools
import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from capstone import CS_AC_WRITE
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG

from .asm import FixupIndex
from .check import ExeInputs
from .fileio import write_atomic
from .functions import KIND_DATA_IN_CODE, KIND_GAME, KIND_THUNK, FunctionRow
from .targets import REPO_ROOT
from .x86 import _disassembler, decode, is_alignment_filler

CACHE_DIR = REPO_ROOT / "build" / "lift"
ARG_REGS = ("eax", "edx", "ebx", "ecx")
GP = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp")
SUB = {
    "al": ("eax", 1),
    "ah": ("eax", -1),
    "ax": ("eax", 2),
    "bl": ("ebx", 1),
    "bh": ("ebx", -1),
    "bx": ("ebx", 2),
    "cl": ("ecx", 1),
    "ch": ("ecx", -1),
    "cx": ("ecx", 2),
    "dl": ("edx", 1),
    "dh": ("edx", -1),
    "dx": ("edx", 2),
    "si": ("esi", 2),
    "di": ("edi", 2),
    "bp": ("ebp", 2),
}
HIGH_BYTES = frozenset(name for name, (_, size) in SUB.items() if size < 0)
LOW_PARTS = {(full, size): name for name, (full, size) in SUB.items() if size > 0}
WORD = 2  # the bytes of `ax`, which a high byte write reaches
FULL_WIDTH = 4
HIGH_SHIFT = 8
BYTE_MASK = 0xFF
HIGH_KEEP = ~(BYTE_MASK << HIGH_SHIFT) & 0xFFFFFFFF  # every byte of a register but the high byte
TABLE_ENTRY = 4  # a jump table's entry: one off32 fixup
HOLE_MARK = "/* HOLE "  # the one spelling of a hole, for whatever asks if a draft holds one
INT_MIN = -(1 << 31)
INT_MIN_TEXT = "(-2147483647 - 1)"
FLOAT = None  # the third kind of number SIZE_TYPE names, beside signed and unsigned
SIZE_TYPE = {
    (1, True): "signed char",
    (1, False): "unsigned char",
    (2, True): "short",
    (2, False): "unsigned short",
    (4, True): "int",
    (4, False): "unsigned",
    (4, FLOAT): "float",
    (8, FLOAT): "double",
}
TYPE_SIZE = {name: size for (size, _), name in SIZE_TYPE.items()}
JCC = {
    "je": "==",
    "jne": "!=",
    "jl": "<",
    "jge": ">=",
    "jg": ">",
    "jle": "<=",
    "jb": "<u",
    "jae": ">=u",
    "ja": ">u",
    "jbe": "<=u",
    "js": "<0",
    "jns": ">=0",
}

MIN_SKIP = frozenset({"jle", "jl", "jbe", "jb"})  # `cmp a, b` then one of these skips `mov a, b`
MAX_SKIP = frozenset({"jge", "jg", "jae", "ja"})
X87_ARITHMETIC = {"fadd": "+", "fsub": "-", "fsubr": "-", "fmul": "*", "fdiv": "/", "fdivr": "/"}
X87_POPPING = {f"{name}p": name for name in X87_ARITHMETIC}
X87_FORMS = frozenset({*X87_ARITHMETIC, *X87_POPPING, "fld", "fild", "fst", "fstp", "fistp", "fchs",
                       "fabs", "fcomp", "fcompp", "fnstsw", "sahf"})  # fmt: skip
X87_POPPING_STORES = frozenset({"fstp", "fistp"})
X87_STORES = X87_POPPING_STORES | {"fst"}  # capstone calls these operands reads
_STACK_NAME = re.compile(r"\b(?:s_[0-9a-f]+|r_p\d+)\b")  # a local slot or a stack parameter


class Unliftable(Exception):
    """The converter cannot express this function (yet); str(exc) is the failure group."""


# ---- expressions ----


@dataclass(frozen=True)
class E:
    text: str
    atom: bool = False  # a name or a constant: free to repeat
    pure: bool = True  # no memory read or call inside (may move across a store)
    const: int | None = None
    size: int = 4
    signed: bool = True
    scaled: tuple | None = None  # (index E, scale) for a value made by lea r, [index*scale]
    boolean: bool = False  # a compare's 0 or 1, which masking to a byte leaves as it is
    sign_of: bool = False  # edx after a cdq of eax, which C can only say as part of a divide
    written: int = 0  # the bytes a narrow write set: a note prints the value at that width
    partial: bool = False  # the register's other bytes hold something the text does not say
    guess: bool = False  # worked out from bytes the text does not say: no note prints it
    sign: tuple | None = None  # (value E, n): the value's sign, 0 or -1, shifted left by n bits
    bias: tuple | None = None  # (value E, n): the value plus 2^n - 1 when negative, for a sar n

    def __str__(self) -> str:
        return self.text


def const(v: int) -> E:
    v &= 0xFFFFFFFF
    s = v - (1 << 32) if v & 0x80000000 else v
    if s == INT_MIN:
        return E(INT_MIN_TEXT, atom=True, const=s)  # C has no negative literal this wide
    return E(str(s) if s < 65536 else f"0x{v:x}", atom=True, const=s)


def var(name: str, size: int = 4, signed: bool = True) -> E:
    return E(name, atom=True, size=size, signed=signed)


def paren(e: E) -> str:
    return e.text if e.atom else f"({e.text})"


def binop(op: str, a: E, b: E) -> E:
    if op in "+-" and b.const == 0:
        return a
    if op == "*" and b.const == 1:
        return a
    return E(f"{paren(a)} {op} {paren(b)}", pure=a.pure and b.pure)


def cast(type_: str, e: E, size: int, signed: bool) -> E:
    return E(f"({type_}){paren(e)}", pure=e.pure, size=size, signed=signed)


def load(addr: E, size: int, signed: bool) -> E:
    return E(f"*({SIZE_TYPE[size, signed]} *){paren(addr)}", pure=False, size=size, signed=signed)


def high_byte(full: E) -> E:
    """The value of `ah`, given `eax`."""
    e = binop("&", binop(">>", full, const(HIGH_SHIFT)), const(BYTE_MASK))
    return E(e.text, pure=e.pure, size=1, signed=False)


def with_high_byte(full: E, byte: E) -> E:
    """`eax` after a write of `byte` to `ah`: its other bytes stay."""
    keep = binop("&", full, const(HIGH_KEEP))
    if byte.const == 0:
        return keep
    return binop("|", keep, binop("<<", binop("&", byte, const(BYTE_MASK)), const(HIGH_SHIFT)))


def low_part(e: E, size: int) -> E:
    """The value of `al` or `ax`, given `eax`: a value of that width or less reads as it is."""
    if e.const is not None or e.size <= size or e.boolean:
        return E(e.text, e.atom, e.pure, e.const, size, e.signed, e.scaled, e.boolean)
    return cast(SIZE_TYPE[size, size != 1], e, size, size != 1)


# ---- the converter ----


@dataclass
class Sig:
    nregs: int
    nstack: int
    returns: bool


@dataclass
class Block:
    start: int
    insns: list = field(default_factory=list)
    succ: list = field(default_factory=list)


class Lifter:
    def __init__(
        self,
        exe: ExeInputs,
        row: FunctionRow,
        sigs: dict[int, Sig] | None = None,
        *,
        holes: bool = False,
    ):
        self.exe, self.row = exe, row
        self.holes = holes
        self.sigs = sigs if sigs is not None else {}
        self.fix = {f.src_va: f for f in _fixup_index(exe).overlapping(row.start, row.end)}
        self.externs: dict[str, str] = {}
        self.locals: dict[str, str] = {}
        self.taken: set[int] = set()  # the slots whose address the row takes, by frame offset
        self.labels: set[int] = set()
        self.tables: dict[int, dict[int, int]] = {}  # table jump -> {case: target}
        self.guards: dict[int, object] = {}  # table jump -> the `ja` its `default:` stands for
        self.compared: dict[int, str | None] = {}  # table jump -> what its guard compared
        self.unfolded = False  # a guard turned out to test something else: run the blocks again
        self.hole_vars: set[str] = set()  # the h_<va> locals a hole left behind
        self.temps: dict[str, str] = {}  # t_<n> -> its C type, for a value kept past an overwrite
        self.before: dict[int, set] = {}  # the registers an instruction, or anything after, reads
        self.word_reads: dict[str, bool] = {}  # slot -> was every read a sign-extended word?
        self.call_values: dict[int, dict[str, str]] = {}  # call -> argument register -> its text
        self.drifted: set[int] = set()  # the blocks not entered at esp0, as far as anything says

    # -- decoding and frame --

    def decode(self):
        md = _disassembler()
        code = self.exe.flat[self.row.start : self.row.end]
        insns = list(md.disasm(code, self.row.start))
        if not insns or insns[-1].address + insns[-1].size != self.row.end:
            raise Unliftable("decode: row does not decode to its end")
        # Watcom alignment filler (lea eax,[eax], mov ebx,ebx, ...) is a no-op: drop it all,
        # trailing and mid-function, so it reads no register. A fixup on the displacement means
        # the field only reads as 0, so that one is no filler.
        filler = {
            i.va
            for i in decode(code, self.row.start)
            if is_alignment_filler(i) and not (i.disp_offset and i.va + i.disp_offset in self.fix)
        }
        body = [ci for ci in insns if ci.address not in filler]
        if not body:
            raise Unliftable("decode: empty")
        return body

    def frame(self, insns):
        saved, i = [], 0
        while (
            i < len(insns)
            and insns[i].mnemonic == "push"
            and insns[i].operands[0].type == X86_OP_REG
        ):
            saved.append(insns[i].reg_name(insns[i].operands[0].reg))
            i += 1
        if (
            "ebp" in saved
            and i < len(insns)
            and insns[i].mnemonic == "mov"
            and insns[i].op_str == "ebp, esp"
        ):
            raise Unliftable("frame: ebp frame")
        frame = 0
        if i < len(insns) and insns[i].mnemonic == "sub" and insns[i].op_str.startswith("esp, "):
            frame = _esp_step(insns[i])
            i += 1
        return saved, frame, i

    # -- the signature pass --

    def prepare(self, ret_live: frozenset = frozenset({"eax"}), strict: bool = True):
        insns = self.decode()
        saved, frame, first = self.frame(insns)
        body = insns[first:]
        if not body:
            raise Unliftable("decode: prologue only")
        blocks, order = self.blocks(body, strict)
        live_in, after = self.liveness(blocks, order, ret_live)
        return insns, saved, frame, blocks, order, live_in, after

    def signature(self) -> Sig:
        """Tolerant: a switch or a tail jump ends its block instead of refusing the row."""
        _, saved, _, blocks, order, live_in, _ = self.prepare(frozenset(), strict=False)
        written = set()
        for s in order:
            for ci in blocks[s].insns:
                if ci.mnemonic in ("pop", "ret", "fnstsw"):  # a status word returns nothing
                    continue
                written |= _use_def(ci)[1]
        entry = live_in[order[0]]
        nregs = 0
        for idx, reg in enumerate(ARG_REGS):
            if reg in entry:
                nregs = idx + 1
        pops = {
            ci.operands[0].imm if ci.operands else 0
            for s in _reachable(blocks, order[0])
            for ci in blocks[s].insns
            if ci.mnemonic == "ret"
        }
        if len(pops) > 1:  # one function has one stack count: no value here is the row's
            raise Unliftable("stack: reachable returns pop different amounts")
        nstack = max(pops, default=0) // 4
        if nstack:
            nregs = 4
        returns = "eax" in written and "eax" not in saved
        used = result_used(self.exe)
        if (
            returns
            and used is not None
            and self.row.start in used[1]
            and self.row.start not in used[0]
        ):
            returns = False
        if returns:  # a path that returns an argument unchanged makes eax live at entry
            live_in = self.prepare(frozenset({"eax"}), strict=False)[5]
            if "eax" in live_in[order[0]]:
                nregs = max(nregs, 1)
        return Sig(nregs, nstack, returns)

    # -- names --

    def data_name(self, va: int) -> str:
        if self._is_code(va):
            row = _index(self.exe)[0].get(va)
            if row is None or row.kind == KIND_DATA_IN_CODE:
                raise Unliftable("ref: code address not at a function start")
            name = _called_name(self.exe.symbols.c_name(va))
            self.externs.setdefault(name, f"int {name}();")
            return name
        name = self.exe.symbols.c_name(va, data=True)
        self.externs.setdefault(name, f"extern char {name}[];")
        return name

    def in_row(self, va: int | None) -> bool:
        if va is None:
            raise Unliftable("jump: indirect (switch table)")
        return self.row.start <= va < self.row.end

    def _row_holding(self, va: int) -> FunctionRow | None:
        starts, rows = _index(self.exe)[1:]
        k = bisect.bisect_right(starts, va) - 1
        return rows[k] if k >= 0 and rows[k].start <= va < rows[k].end else None

    def _is_code(self, va: int) -> bool:
        return self._row_holding(va) is not None

    def callee(self, va: int) -> tuple[str, Sig]:
        row = _index(self.exe)[0].get(va)
        if row is None:
            raise Unliftable("call: target is not a row start")
        name = self.exe.symbols.c_name(va)
        if name.startswith("_") or not name.replace("_", "a").isidentifier():
            raise Unliftable("call: stack-convention or odd callee name")
        name = _called_name(name)
        if va in self.sigs:
            return name, self.sigs[va]  # None: unknown or still being computed (a cycle)
        self.sigs[va] = None
        try:
            sig = Lifter(self.exe, row, self.sigs).signature()
        except Unliftable:
            sig = None
        self.sigs[va] = sig
        return name, sig  # None: unknown, the call site decides

    def call_sig(self, ci) -> Sig | None:
        """The signature of what the call `ci` reaches, if anything says."""
        t = _branch_target(ci)
        try:
            return self.callee(t)[1] if t is not None else None
        except Unliftable:
            return None

    def call_nregs(self, ci, insns) -> int:
        """How many argument registers the call `ci` (in the block `insns`) passes."""
        sig = self.call_sig(ci)
        if sig is not None and sig.nstack:
            return 4
        return max(sig.nregs if sig else 0, _evidence(insns, ci))

    # -- switch tables --

    def table_start(self, ci) -> int | None:
        """Where the table of `jmp [index*4 + table]` starts, when a data-in-code row holds it."""
        if ci.mnemonic != "jmp" or ci.operands[0].type != X86_OP_MEM:
            return None
        m = ci.operands[0].mem
        fx = self.fix.get(ci.address + ci.disp_offset) if ci.disp_offset else None
        if fx is None or m.base or not m.index or m.scale != TABLE_ENTRY:
            return None
        row = self._row_holding(fx.target_va)
        return fx.target_va if row is not None and row.kind == KIND_DATA_IN_CODE else None

    def table_cases(self, start: int, end: int) -> dict[int, int]:
        """{case: target} from the off32 fixups of [start, end). Empty when a field there is no
        entry: sizes and places come from the binary, so a bent table is no table."""
        fields = _fixup_index(self.exe).overlapping(start, end)
        if any(fx.size != TABLE_ENTRY or (fx.src_va - start) % TABLE_ENTRY for fx in fields):
            return {}
        cases = {(fx.src_va - start) // TABLE_ENTRY: fx.target_va for fx in fields}
        return cases if sorted(cases) == list(range(len(cases))) else {}

    def find_tables(self, insns) -> None:
        """Fill `tables` and `guards`. A table runs to the next table of this row or to the end
        of the row that holds it: one data-in-code row can hold several."""
        heads = {ci.address: self.table_start(ci) for ci in insns}
        heads = {address: start for address, start in heads.items() if start is not None}
        self.tables, self.guards = {}, {}
        for k, ci in enumerate(insns):
            start = heads.get(ci.address)
            if start is None:
                continue
            later = [s for s in heads.values() if s > start]
            cases = self.table_cases(start, min([*later, self._row_holding(start).end]))
            if cases:
                self.tables[ci.address] = cases
                guard = self.table_guard(insns, k)
                if guard is not None:
                    self.guards[ci.address] = guard

    def table_guard(self, insns, k: int):
        """The `cmp r, imm; ja` closing the block before the table jump insns[k], if there is
        one: Watcom writes that compare for a switch with a `default:`. The run drops it if it
        turns out to compare anything but the switch's index."""
        for n in range(k - 1, 0, -1):
            ci = insns[n]
            if not (ci.group(1) or ci.group(3) or ci.mnemonic == "call"):
                continue
            before = insns[n - 1]
            bounded = before.mnemonic == "cmp" and before.operands[1].type == X86_OP_IMM
            return ci if ci.mnemonic == "ja" and bounded and not self._tail_jump(ci) else None
        return None

    # -- CFG and liveness --

    def blocks(self, insns, strict: bool = True):
        self.find_tables(insns)
        starts = {insns[0].address}
        for k, ci in enumerate(insns):
            if ci.group(1) or ci.group(3):  # jump / ret
                if k + 1 < len(insns):
                    starts.add(insns[k + 1].address)
                if ci.group(1):
                    t = _branch_target(ci)
                    if t is None:
                        starts.update(self.tables.get(ci.address, {}).values())
                        if strict and ci.address not in self.tables:
                            raise Unliftable("jump: indirect (switch table)")
                        continue
                    if not (self.row.start <= t < self.row.end):
                        continue  # a tail jump: no successor in the row
                    starts.add(t)
        blocks: dict[int, Block] = {}
        cur = None
        for ci in insns:
            if ci.address in starts:
                cur = blocks.setdefault(ci.address, Block(ci.address))
            cur.insns.append(ci)
        order = sorted(blocks)
        for n, s in enumerate(order):
            b = blocks[s]
            last = b.insns[-1]
            if last.group(1):
                t = _branch_target(last)
                if t is not None and self.row.start <= t < self.row.end:
                    if t not in blocks:
                        raise Unliftable("jump: into an instruction")
                    b.succ.append(t)
                for t in dict.fromkeys(self.tables.get(last.address, {}).values()):
                    if t not in blocks:
                        raise Unliftable("jump: into an instruction")
                    b.succ.append(t)
                if last.mnemonic != "jmp" and n + 1 < len(order):
                    b.succ.append(order[n + 1])
            elif not last.group(3) and n + 1 < len(order):
                b.succ.append(order[n + 1])
        return blocks, order

    def _tail_jump(self, ci) -> bool:
        t = _branch_target(ci) if ci.group(1) else None
        return t is not None and not (self.row.start <= t < self.row.end)

    def _tail_end(self, b) -> bool:
        last = b.insns[-1]
        t = _branch_target(last) if last.mnemonic == "jmp" else None
        return t is not None and not (self.row.start <= t < self.row.end)

    def liveness(self, blocks, order, ret_live=frozenset({"eax"})):
        """Live-in register sets per instruction address (full 32-bit names)."""
        use_def = {}
        for s in order:
            for ci in blocks[s].insns:
                use_def[ci.address] = _use_def(ci)
                if ci.mnemonic == "call" or self._tail_jump(ci):
                    n = self.call_nregs(ci, blocks[s].insns)
                    use_def[ci.address] = (set(ARG_REGS[:n]), {"eax"})
        live_in: dict[int, set] = {s: set() for s in order}
        changed = True
        while changed:
            changed = False
            for s in reversed(order):
                b = blocks[s]
                live = set().union(*(live_in[t] for t in b.succ)) if b.succ else set()
                if b.insns[-1].group(3) or self._tail_end(b):
                    live = set(ret_live) if b.insns[-1].group(3) else set()
                for ci in reversed(b.insns):
                    u, d = use_def[ci.address]
                    live = (live - d) | u
                if live != live_in[s]:
                    live_in[s], changed = live, True
        after: dict[int, set] = {}
        for s in order:
            b = blocks[s]
            live = set().union(*(live_in[t] for t in b.succ)) if b.succ else set()
            if b.insns[-1].group(3) or self._tail_end(b):
                live = set(ret_live) if b.insns[-1].group(3) else set()
            for ci in reversed(b.insns):
                after[ci.address] = set(live)
                u, d = use_def[ci.address]
                live = (live - d) | u
                self.before[ci.address] = set(live)
        return live_in, after

    # -- esp across blocks --

    def esp_after(self, b: Block, esp: int) -> int | None:
        """esp at the end of `b`, entered at `esp`: None when an instruction leaves it unknown."""
        for ci in b.insns:
            step = _esp_change(ci)
            if ci.mnemonic == "call":
                sig = self.call_sig(ci)
                step = None if sig is None else 4 * sig.nstack
            if step is None:
                return None
            esp += step
        return esp

    def drifted_blocks(self, blocks, order) -> set[int]:
        """The blocks entered with esp other than esp0, or with nothing to say what it is. A run
        starts every block at esp0: a draft proves that by compiling, and a note cannot, so this
        says which blocks a note must not trust. It changes no draft."""
        entry: dict[int, int | None] = {order[0]: self.esp0}
        todo = [order[0]]
        while todo:
            s = todo.pop()
            esp = entry[s]
            out = None if esp is None else self.esp_after(blocks[s], esp)
            for t in blocks[s].succ:
                met = out if t not in entry or entry[t] == out else None
                if t not in entry or entry[t] != met:
                    entry[t] = met
                    todo.append(t)
        return {s for s in order if entry.get(s) != self.esp0}

    # -- the lift --

    def param_types(self, blocks, start: int, params) -> dict[str, str]:
        """A register parameter that every path only reads through its low byte or word, until
        it is written, is `unsigned char` / `short` (movsx: signed, a plain or zero-extending
        read: unsigned)."""
        reads: dict[str, set] = {r: set() for r in params}
        seen = set()
        todo = [(start, frozenset())]
        while todo:
            s, written = todo.pop()
            if (s, written) in seen:
                continue
            seen.add((s, written))
            written = _note_reads(blocks[s].insns, reads, written)
            todo += [(t, written) for t in blocks[s].succ]
        out = {}
        for r, found in reads.items():
            sizes = {size for size, _ in found}
            if len(sizes) == 1 and sizes < {1, 2}:
                (size,) = sizes
                signed = (
                    all(mn == "movsx" for _, mn in found)
                    if size == 1
                    else not any(mn == "movzx" for _, mn in found)
                )
                out[r] = SIZE_TYPE[size, signed]
        return out

    def ret_type(self, blocks, order) -> str:
        """`unsigned char` / `short` when every non-call write of eax writes only al / ax."""
        sizes = set()
        for s in order:
            for ci in blocks[s].insns:
                if (
                    ci.mnemonic in ("call", "pop", "push", "ret", "cdq", "idiv", "div", "fnstsw")
                    or not ci.operands
                ):
                    continue
                op = ci.operands[0]
                if (
                    op.type == X86_OP_REG
                    and _full(ci.reg_name(op.reg)) == "eax"
                    and ci.mnemonic not in ("cmp", "test")
                ):
                    sizes.add(_reach(ci.reg_name(op.reg), op.size))
        if sizes == {1}:
            return "unsigned char"
        if sizes == {2}:
            return "short"
        return "int"

    def lift(self) -> str:
        sig = self.signature()
        self.sig = sig
        ret_live = frozenset({"eax"}) if sig.returns else frozenset()
        insns, saved, frame, blocks, order, live_in, self.after = self.prepare(ret_live)
        self.saved = saved
        self.frame_top = -4 * len(saved)
        self.esp0 = self.frame_top - frame  # esp after the prologue, relative to entry esp
        self.drifted = self.drifted_blocks(blocks, order)
        params = list(ARG_REGS[: sig.nregs])
        self.vartype = self.param_types(blocks, order[0], params)
        self.regvars = set(params)
        preds: dict[int, list[int]] = {s: [] for s in order}
        for s in order:
            for t in blocks[s].succ:
                preds[t].append(s)
        self.merge = {s for s in order[1:] if len(preds[s]) != 1 or preds[s][0] >= s}
        if preds[order[0]]:  # a jump back to the top: the entry is one way in of several
            self.merge.add(order[0])
        for s in self.merge:
            self.regvars |= live_in[s] & set(GP)
        self.live_in = live_in
        regvars = set(self.regvars)
        body = self.emit(blocks, order, preds)
        again = bool(self.taken)  # that run was the pre-pass: with every array known, run again
        while again or self.unfolded:
            again, self.unfolded = False, False
            self.regvars = set(regvars)
            body = self.emit(blocks, order, preds)
        used = {lab for lab in self.labels if any(f"goto L{lab:X};" in line for line in body)}
        body = [
            line for line in body if not (line.endswith(":;") and int(line[1:-2], 16) not in used)
        ]
        self.locals |= {name: "short" for name, short in self.word_reads.items() if short}
        ret = self.ret_type(blocks, order) if sig.returns else "void"
        params += [f"p{n + 5}" for n in range(sig.nstack)]
        args = ", ".join(f"{self.vartype.get(r, 'int')} r_{r}" for r in params) or "void"
        name = self.exe.symbols.c_name(self.row.start)
        self.externs.pop(name, None)  # the definition is its own declaration
        decls = [f"    int r_{r};" for r in sorted(self.regvars - set(params))]
        # Nearest the entry first: a frame of one size puts the first declared highest (probe M2).
        slots = sorted(self.locals.items(), key=lambda local: int(local[0].removeprefix("s_"), 16))
        dims = self.array_dims()
        decls += [f"    {t} {n}{dims.get(n, '')};" for n, t in slots]
        decls += [f"    int {n};" for n in sorted(self.hole_vars)]
        decls += [f"    {t} {n};" for n, t in self.temps.items()]
        lines = [f"/* IDIOM {hit} */" for hit in self.idioms()]
        lines += list(self.externs.values()) + ["", f"{ret} {name}({args})", "{"] + decls
        if decls:
            lines.append("")
        lines += [("    " + line if not line.endswith(":;") else line) for line in body]
        lines.append("}")
        return "\n".join(lines) + "\n"

    def emit(self, blocks, order, preds) -> list[str]:
        """Run every block into C statements. An address-taken slot found here is in `taken`."""
        self.locals = {_slot_name(off): "char" for off in self.taken}
        self.hole_vars, self.word_reads, self.temps = set(), {}, {}
        end_state: dict[int, dict] = {}
        lost: set[int] = set()  # the blocks that ended with esp_lost
        body: list[str] = []
        targets = {t for b in blocks.values() if b.insns[-1].group(1) for t in self.jumped_to(b)}
        carried = None
        for s in order:
            b = blocks[s]
            if s != order[0] or s in self.merge:
                self.labels.add(s)
                body.append(f"L{s:X}:;")
            run = Block_(self, b.insns, s)
            run.esp_lost = s in self.drifted
            if s != order[0] and s not in self.merge:
                run.regs = dict(end_state[preds[s][0]])  # one forward predecessor: inherit
                run.esp_lost |= preds[s][0] in lost  # its text comes along
            if carried is not None and s not in targets:
                run.flags = carried
            body += run.run(blocks, self.live_in)
            end_state[s] = dict(run.regs)
            if run.esp_lost:
                lost.add(s)
            last = b.insns[-1]
            carried = run.flags if last.mnemonic in JCC else None
        return body

    def jumped_to(self, b) -> list[int]:
        """The successors the jump closing `b` reaches, past any fall through."""
        return b.succ if b.insns[-1].address in self.tables else b.succ[:1]

    # -- idioms --

    def idioms(self) -> list[str]:
        """One line per inlined boolean helper or written-out MIN/MAX, with the address of its
        conditional jump. It detects and names, and rewrites nothing."""
        insns = self.decode()
        blocks, order = self.blocks(insns[self.frame(insns)[2] :])
        hits = []
        for s, nxt in itertools.pairwise(order):
            b = blocks[s]
            last = b.insns[-1]
            if last.mnemonic not in JCC:
                continue
            taken = blocks.get(_branch_target(last))
            name = None if taken is None else _idiom(b, blocks[nxt], taken)
            if name is not None:
                hits.append(f"0x{last.address:X}: {name}")
        return hits

    # -- address-taken slots --

    def array_at(self, off: int) -> int | None:
        """The address-taken slot whose array holds the frame offset `off`, if any: an array runs
        to the next address-taken slot or the frame's end, because no single access shows its
        extent."""
        below = [t for t in self.taken if t <= off]
        return max(below) if below and off < self.frame_top else None

    def array_dims(self) -> dict[str, str]:
        edges = sorted(self.taken) + [self.frame_top]
        return {_slot_name(a): f"[{b - a}]" for a, b in itertools.pairwise(edges)}


class Block_:
    """The symbolic run of one basic block."""

    def __init__(self, lf: Lifter, insns, start: int):
        self.lf, self.insns, self.start = lf, insns, start
        # Sorted: this order is the order `flush` writes statements in, and a set's follows the
        # string hash, which would make the draft differ from run to run.
        self.regs: dict[str, E] = {r: _typed_var(lf, r) for r in sorted(lf.regvars)}
        self.out: list[str] = []
        self.flags: tuple | None = None
        self.esp = lf.esp0
        self.esp_lost = False  # esp may not be what `self.esp` says: no slot name is vouched for
        self.read_guess = False  # this instruction read a guess, or past a partial write
        self.pushes: list[E] = []
        self.k = 0  # the place in this block of the instruction being run
        self.fstack: list[E] = []  # the x87 stack's expressions, st(0) last
        self.fcompare: tuple | None = None  # the last x87 compare, for `fnstsw ax`
        self.status: tuple | None = None  # what `fnstsw ax` read, for `sahf`
        self.needed: set[str] = set()  # the registers still read from here on
        self.assigning: set[str] = set()  # registers whose assignment waits on their readers

    # registers

    def held(self, name: str) -> E:
        """What the full register `name` holds, as a value to look at, not an operand read."""
        if name not in self.regs:
            raise Unliftable(f"reg: {name} read before any write")
        e = self.regs[name]
        if e.sign_of:
            raise Unliftable("op: cdq")
        return e

    def get(self, name: str) -> E:
        full, size = SUB.get(name, (name, FULL_WIDTH))
        e = self.held(full)
        self.read_guess |= e.guess or (e.partial and not 0 < size <= e.written)
        if name not in SUB:
            return e
        return high_byte(e) if name in HIGH_BYTES else low_part(e, size)

    def set(self, name: str, e: E) -> None:
        if name in SUB:
            full, size = SUB[name]
            if name in HIGH_BYTES:
                old = self.held(full)
                new = with_high_byte(old, e)
                self.regs[full] = replace(new, written=WORD if old.written else 0,
                                          partial=old.partial, guess=old.guess)  # fmt: skip
                return
            old = self.regs.get(full)
            zero = old is not None and old.const == 0
            over_zero = zero or (old is not None and old.written > 0 and not old.partial)
            self.regs[full] = E(e.text, e.atom, e.pure, e.const, size, False if zero else e.signed,
                                boolean=e.boolean, written=size, partial=not over_zero)  # fmt: skip
            return
        self.regs[name] = e

    def widened(self, name: str) -> E:
        """What a cast to the width of `al`, `ax` or `ah` reads: the cast does the narrowing."""
        e = self.get(name)
        return e if name in HIGH_BYTES else self.held(_full(name))

    def flush(self, ci) -> None:
        """Before a side effect: registers holding an impure value that is still needed become
        their variable."""
        live = self.lf.after.get(ci.address, set())
        for r in list(self.regs):
            if self.regs[r].pure or r not in live:
                continue
            self.assign(r)

    def assign(self, r: str) -> None:
        name = f"r_{r}"
        if self.regs[r].text == name:
            return
        if self.regs[r].sign_of:
            raise Unliftable("op: cdq")
        self.assigning.add(r)
        self.keep_readers(name, r, self.needed)
        self.assigning.discard(r)
        e = self.regs[r]
        self.keep_held(name, e.text)
        self.keep_flags(name, e.text)
        self.lf.regvars.add(r)
        self.out.append(f"{name} = {e};")
        self.regs[r] = var(name, e.size, e.signed)
        self.rebind(e, self.regs[r])

    def keep_readers(self, name: str, owner: str | None, needed: set[str]) -> None:
        """`name` is about to change. Every other needed register reading it becomes its own
        variable first; one already waiting on this assignment is a cycle, and reads a temporary."""
        for other in list(self.regs):
            if other == owner or not _reads(self.regs[other], name):
                continue
            if other in self.assigning:
                self.regs[other] = _renamed(self.regs[other], name, self.temp(name))
            elif other in needed:
                self.assign(other)

    def keep_held(self, name: str, value: str = "") -> None:
        """`name` is about to change: a pending push or x87 register reading it reads a temporary,
        unless it is the `value` that takes the name."""
        for held in (self.pushes, self.fstack):
            stale = [n for n, e in enumerate(held) if e.text != value and _reads(e, name)]
            for n in stale:
                held[n] = _renamed(held[n], name, self.temp(name))

    def keep_flags(self, name: str, value: str = "") -> None:
        """`name` is about to change: a flag operand reading it reads a temporary, unless it is the
        `value` that takes the name. Flags nothing reads go, since no temporary should print."""
        if self.flags is None:
            return
        held = self.flags[1:]
        if not any(e.text != value and _reads(e, name) for e in held):
            return
        if self.flags_reader(self.k) is None:
            self.flags = None
            return
        t = self.temp(name)
        kept = (e if e.text == value else _renamed(e, name, t) for e in held)
        self.flags = (self.flags[0], *kept)

    def flags_reader(self, k: int):
        """The instruction of this block that reads the flags, from place `k` on, before anything
        writes them."""
        for ci in self.insns[k:]:
            regs_read, regs_write = ci.regs_access()
            if any(ci.reg_name(r) == "eflags" for r in regs_read):
                return ci
            if ci.mnemonic == "call" or any(ci.reg_name(r) == "eflags" for r in regs_write):
                return None
        return None

    def temp(self, name: str) -> str:
        """A new variable holding what `name` holds now."""
        t = f"t_{len(self.lf.temps)}"
        self.lf.temps[t] = self.lf.locals.get(name, "int")
        self.out.append(f"{t} = {name};")
        return t

    def rebind(self, value: E, new: E) -> None:
        """`new` holds `value` now, and what held `value` reads it from there. A name or a
        constant repeats freely, so only a name about to change moves."""
        same = not value.atom or value.text in {f"r_{r}" for r in self.assigning}

        def moved(e: E) -> E:
            return new if same and e.text == value.text else e

        self.pushes[:] = map(moved, self.pushes)
        self.fstack[:] = map(moved, self.fstack)
        if self.flags is not None:
            self.flags = (self.flags[0], *map(moved, self.flags[1:]))

    def keep_slot(self, ci, op) -> None:
        """A store to a scalar slot overwrites a name as an assignment does. Its own statement
        reads the value first, so only what is read after it needs keeping."""
        name = self.scalar_name(ci, op)
        if name is None:
            return
        self.keep_readers(name, None, self.lf.after.get(ci.address, set()))
        popping = ci.mnemonic in X87_POPPING_STORES and self.fstack
        self.keep_held(name, self.fstack[-1].text if popping else "")
        self.keep_flags(name)

    def scalar_name(self, ci, op) -> str | None:
        """The C variable a store to the memory operand `op` overwrites, if it has one."""
        m = op.mem
        if not m.base or ci.reg_name(m.base) != "esp" or m.index:
            return None
        off = self.esp + m.disp
        if self.lf.array_at(off) is not None:
            return None
        return f"r_p{(off - 4) // 4 + 5}" if off >= 4 else _slot_name(off)

    # operands

    def lvalue(self, ci, op, signed: bool) -> E:
        """The C lvalue for a memory operand: an array element `((T *)base)[i]` when the address
        is base + index*size (as an index or a lea-scaled register), else `*(T *)addr`."""
        m = op.mem
        size = op.size
        t = SIZE_TYPE[size, signed]
        fx = self._field(ci, ci.disp_offset) if m.disp or ci.disp_offset else None
        base = ci.reg_name(m.base) if m.base else None
        if fx is not None and base != "esp":
            arr = var(self.lf.data_name(fx.target_va))
            if m.index and m.scale == size and size in (2, 4) and not base:
                i = self.get(ci.reg_name(m.index))
                return E(f"(({t} *){arr.text})[{i}]", pure=False, size=size, signed=signed)
            if base and not m.index:
                b = self.get(base)
                if b.scaled is not None and b.scaled[1] == size:
                    return E(
                        f"(({t} *){arr.text})[{b.scaled[0]}]", pure=False, size=size, signed=signed
                    )
        return load(self.mem_addr(ci, op), size, signed)

    def mem_addr(self, ci, op) -> E:
        m = op.mem
        parts: list[E] = []
        fx = self._field(ci, ci.disp_offset) if m.disp or ci.disp_offset else None
        base = ci.reg_name(m.base) if m.base else None
        if fx is not None:
            parts.append(var(self.lf.data_name(fx.target_va)))
        if base:
            parts.append(self.get(base))
        if m.index:
            idx = self.get(ci.reg_name(m.index))
            parts.append(binop("*", idx, const(m.scale)) if m.scale != 1 else idx)
        if fx is None and m.disp:
            if not parts:
                raise Unliftable("mem: absolute address without a fixup")
            parts.append(const(m.disp))
        if not parts:
            raise Unliftable("mem: empty address")
        addr = parts[0]
        if fx is not None:
            addr = E(f"({addr.text}" + "".join(f" + {paren(p)}" for p in parts[1:]) + ")")
            return E(addr.text, pure=all(p.pure for p in parts))
        for p in parts[1:]:
            addr = binop("+", addr, p)
        if len(parts) > 1 or not addr.atom:
            return E(
                f"(char *){paren(addr)}"
                if len(parts) == 1
                else "(char *)" + paren(parts[0]) + "".join(f" + {paren(p)}" for p in parts[1:]),
                pure=all(p.pure for p in parts),
            )
        return E(f"(char *){addr.text}", pure=addr.pure)

    def _field(self, ci, offset: int):
        if not offset:
            return None
        return self.lf.fix.get(ci.address + offset)

    def take(self, off: int) -> str:
        """The array local at the frame offset `off`, noted for the run that declares it."""
        if not self.lf.esp0 <= off < self.lf.frame_top:
            raise Unliftable("stack: address outside the frame")
        self.lf.taken.add(off)
        return _slot_name(off)

    def slot(self, ci, op, signed: bool) -> E:
        """The C lvalue for an esp-based operand: a parameter, a scalar local, or a typed access
        through the array that holds it."""
        m = op.mem
        off = self.esp + m.disp
        if m.index:
            self.take(off)
        base = self.lf.array_at(off)
        if base is not None:
            return self.element(ci, op, base, off, signed)
        if off >= 4:
            n = (off - 4) // 4
            if (off - 4) % 4 or n >= self.lf.sig.nstack:
                raise Unliftable("stack: slot above the frame that is no parameter")
            return var(f"r_p{n + 5}", 4, signed)
        if off >= 0:
            raise Unliftable("stack: return address slot")
        if off >= self.lf.frame_top:
            raise Unliftable("stack: saved register slot")
        name = _slot_name(off)
        self.lf.locals.setdefault(name, SIZE_TYPE[op.size, signed])
        return var(name, op.size, signed)

    def element(self, ci, op, base: int, off: int, signed: bool) -> E:
        """The access `op` makes at `off`, inside the array at `base`."""
        m, size = op.mem, op.size
        array = var(_slot_name(base))
        if not m.index:
            return load(binop("+", array, const(off - base)), size, signed)
        i = self.get(ci.reg_name(m.index))
        if m.scale == size:
            t = SIZE_TYPE[size, signed]
            return E(f"(({t} *){array.text})[{i}]", pure=False, size=size, signed=signed)
        return load(binop("+", array, binop("*", i, const(m.scale))), size, signed)

    def place(self, ci, op, signed: bool | None) -> E:
        """The C lvalue of a memory operand."""
        if op.mem.base and ci.reg_name(op.mem.base) == "esp":
            return self.slot(ci, op, signed)
        return self.lvalue(ci, op, signed)

    def read(self, ci, op, signed: bool = True) -> E:
        if op.type == X86_OP_REG:
            return self.get(ci.reg_name(op.reg))
        if op.type == X86_OP_IMM:
            fx = self._field(ci, ci.imm_offset)
            if fx is not None:
                return E(f"(int){self.lf.data_name(fx.target_va)}", atom=True)
            return const(op.imm)
        if op.type == X86_OP_MEM:
            e = self.place(ci, op, signed)
            if e.text in self.lf.locals:
                short = self.lf.word_reads.get(e.text, True) and self.sign_extends_word(ci, op)
                self.lf.word_reads[e.text] = short
                if op.size > TYPE_SIZE[self.lf.locals[e.text]] and not short:
                    raise Unliftable("stack: slot read at two widths")
            return e
        raise Unliftable("operand: unknown")

    def sign_extends_word(self, ci, op) -> bool:
        """`movsx r, word ptr`, or a word load into ax that the next instruction's cwde widens."""
        if op.size != 2:
            return False
        following = self.insns[self.k + 1 : self.k + 2]
        widened = bool(following) and following[0].mnemonic == "cwde"
        return ci.mnemonic == "movsx" or (widened and ci.op_str.startswith("ax, "))

    def write(self, ci, op, e: E) -> E:
        """Put `e` in `op`, and return where it reads from now: a store has already flushed, in
        `step`, because the operands it reads must see what the flush assigned."""
        if op.type == X86_OP_REG:
            self.set(ci.reg_name(op.reg), e)
            return e
        if op.type == X86_OP_MEM:
            esp = op.mem.base and ci.reg_name(op.mem.base) == "esp"
            target = self.slot(ci, op, True) if esp else self.lvalue(ci, op, e.signed)
            self.out.append(f"{target} = {e};")
            return target
        raise Unliftable("write: operand")

    # the run

    def run(self, blocks, live_in) -> list[str]:
        for k, ci in enumerate(self.insns):
            self.attempt(ci, k)
        last = self.insns[-1]
        if not (last.group(1) or last.group(3)):
            self.needed = self.lf.after.get(last.address, set())
            self.flags = None  # only a block ending in a jump hands its flags on
            self.end_assign(live_in, blocks)
        return self.out

    def attempt(self, ci, k) -> None:
        """One step. With `holes`, a refusal here costs this instruction, not the row."""
        try:
            self.read_guess = False
            self.step(ci, k)
            self.keep_guess(ci)
            if self.fstack and k == len(self.insns) - 1:
                raise Unliftable("x87: stack live across a block end")
        except Unliftable as exc:
            if not self.lf.holes:
                raise
            self.hole(ci, str(exc))

    def keep_guess(self, ci) -> None:
        """What `ci` worked out from a guess is one too. A call's result is the callee's, and a
        whole register's copy is the same value, at the width it already prints."""
        copied = ci.mnemonic == "mov" and ci.operands[1].type == X86_OP_REG
        if not self.read_guess or ci.mnemonic == "call" or (copied and ci.operands[1].size == 4):
            return
        for r in _use_def(ci)[1] & self.regs.keys():
            self.regs[r] = replace(self.regs[r], guess=True)

    def hole(self, ci, reason: str) -> None:
        """What `ci` wrote is unknown, so each register it wrote reads as a fresh local, and the
        flags are gone. No C stands for the instruction, so this draft can never be exact. A
        stack effect the run did not apply makes every later slot name a guess."""
        self.out.append(f"{HOLE_MARK}0x{ci.address:X}: {reason} */")
        self.esp_lost |= _writes_esp(ci)
        name = f"h_{ci.address:x}"
        written = _use_def(ci)[1]
        self.regs.update(dict.fromkeys(sorted(written), var(name)))
        if written:
            self.lf.hole_vars.add(name)
        self.flags = None

    def end_assign(self, live_in, blocks) -> None:
        succ = [t for t in blocks[self.start].succ if t in self.lf.merge]
        live = set().union(*(live_in[t] for t in succ)) if succ else set()
        for r in sorted(live & set(GP)):
            if r in self.regs:
                self.assign(r)

    def step(self, ci, k) -> None:
        self.k = k
        self.needed = self.lf.before.get(ci.address, set())
        mn, ops = ci.mnemonic, ci.operands
        if mn in ("mov", "lea") and _writes_esp(ci):
            self.esp_lost = True  # these lift, and self.esp does not follow them
        if _stores(ci):
            self.flush(ci)
            self.keep_slot(ci, ops[0])
        if mn == "ret":
            self.ret()
            return
        if mn == "pop":
            self.pop(ci, k)
            return
        if _frees_stack(ci):
            step = _esp_step(ci)
            self.esp += step
            del self.pushes[max(len(self.pushes) - step // 4, 0) :]
            return
        if mn == "mov" and ops[1].type == X86_OP_REG and ci.reg_name(ops[1].reg) == "esp":
            self.write(ci, ops[0], E(f"(int){self.take(self.esp)}", atom=True))
        elif mn == "mov":
            self.write(ci, ops[0], self.read(ci, ops[1], ops[1].size == 4))
        elif mn in ("movsx", "movzx"):
            signed = mn == "movsx"
            if ops[1].type == X86_OP_REG:
                src = self.widened(ci.reg_name(ops[1].reg))
                src = cast(SIZE_TYPE[ops[1].size, signed], src, ops[1].size, signed)
            else:
                src = self.read(ci, ops[1], signed)
            self.write(ci, ops[0], E(src.text, src.atom, src.pure, src.const, ops[1].size, signed))
        elif mn == "lea":
            m = ops[1].mem
            if m.base and ci.reg_name(m.base) == "esp":
                if m.index:
                    raise Unliftable("lea: indexed stack address")
                self.write(ci, ops[0], E(f"(int){self.take(self.esp + m.disp)}", atom=True))
                return
            if (
                m.index
                and not m.base
                and not m.disp
                and m.scale in (2, 4)
                and not self._field(ci, ci.disp_offset)
            ):
                i = self.get(ci.reg_name(m.index))
                e = binop("*", i, const(m.scale))
                self.write(ci, ops[0], E(e.text, pure=e.pure, scaled=(i, m.scale)))
                return
            addr = self.mem_addr(ci, ops[1])
            self.write(ci, ops[0], E(f"(int){paren(addr)}", pure=addr.pure))
        elif mn in ("add", "sub", "and", "or", "xor", "imul", "shl", "sar", "shr"):
            self.arith(ci, mn, ops)
        elif mn in ("inc", "dec", "neg", "not"):
            a = self.read(ci, ops[0])
            e = {
                "inc": lambda: binop("+", a, const(1)),
                "dec": lambda: binop("-", a, const(1)),
                "neg": lambda: E(f"-({a})", pure=a.pure),
                "not": lambda: E(f"~{paren(a)}", pure=a.pure),
            }[mn]()
            target = self.write(ci, ops[0], e)
            if mn != "not":  # the one of these that leaves the flags alone
                self.flags = ("res", target)
        elif mn == "cmp":
            self.cmp(ci, ops)
        elif mn == "test":
            a, b = self.read(ci, ops[0]), self.read(ci, ops[1])
            self.flags = ("test", a if a.text == b.text else binop("&", a, b))
        elif mn == "cwde":
            self.set("eax", cast("short", self.widened("ax"), 2, True))
        elif mn == "cdq":
            a = self.get("eax")
            self.regs["edx"] = E(f"__cdq({a.text})", pure=a.pure, sign_of=True, sign=(a, 0))
        elif mn in ("idiv", "div"):
            self.divide(ci, mn, ops)
        elif mn == "call":
            self.call(ci)
        elif mn == "jmp" and ci.address in self.lf.tables:
            self.switch(ci)
        elif mn == "jmp":
            t = _branch_target(ci)
            if not self.lf.in_row(t):
                self.out.append(self.tail(ci, t))
                return
            self.end_assign_jump(ci)
            self.out.append(f"goto L{t:X};")
        elif mn in JCC:
            self.jcc(ci, mn)
        elif mn == "push":
            self.pushes.append(self.read(ci, ops[0]))
            self.esp -= 4
        elif mn.startswith("set") and f"j{mn[3:]}" in JCC:
            self.write(ci, ops[0], self.compare(f"j{mn[3:]}"))
        elif mn == "sbb":
            self.sbb(ci, ops)
        elif mn in X87_FORMS:
            self.x87(ci, mn, ops)
        else:
            raise Unliftable(f"op: {mn}")

    def cmp(self, ci, ops) -> None:
        """A narrow memory operand reads as the condition does, and the immediate fits what it
        is compared with: a C compare widens both first."""
        unsigned = _unsigned_reader(self.flags_reader(self.k + 1))
        a, b = (self.read(ci, op, op.size == 4 or not unsigned) for op in ops)
        if b.const is not None and ops[0].size < 4:
            b = const(_narrowed(b.const, ops[0].size, a.signed))
        self.flags = ("cmp", a, b)

    def pop(self, ci, k: int) -> None:
        """The value pushed in this block, or a saved register on the way out of the row."""
        if self.pushes:
            self.write(ci, ci.operands[0], self.pushes.pop())
        elif not self.restores_saved(ci, k):
            raise Unliftable("pop: value not pushed in the block")
        self.esp += 4

    def restores_saved(self, ci, k: int) -> bool:
        """True for a pop of a register the prologue saved, with only the row's end after it."""
        op = ci.operands[0]
        if op.type != X86_OP_REG or ci.reg_name(op.reg) not in self.lf.saved:
            return False
        return all(
            after.mnemonic in ("pop", "ret") or _frees_stack(after) or self.lf._tail_jump(after)
            for after in self.insns[k + 1 :]
        )

    # the x87

    def st(self, n: int) -> E:
        if n >= len(self.fstack):
            raise Unliftable("x87: stack read before any load")
        return self.fstack[-1 - n]

    def float_read(self, ci, op) -> E:
        """An x87 operand: a stack register, or memory at the size it names."""
        if op.type == X86_OP_REG:
            return self.st(_st_number(ci, op))
        if (op.size, FLOAT) not in SIZE_TYPE:
            raise Unliftable(f"op: {ci.mnemonic}")
        return self.read(ci, op, FLOAT)

    def float_store(self, ci, op, e: E, signed: bool | None) -> None:
        if (op.size, signed) not in SIZE_TYPE:
            raise Unliftable(f"op: {ci.mnemonic}")
        self.out.append(f"{self.place(ci, op, signed)} = {e};")

    def x87(self, ci, mn, ops) -> None:
        if mn in X87_ARITHMETIC or mn in X87_POPPING:
            self.float_arith(ci, mn, ops)
        elif mn == "fld":
            self.fstack.append(self.float_read(ci, ops[0]))
        elif mn == "fild":
            if (ops[0].size, True) not in SIZE_TYPE:
                raise Unliftable("op: fild")
            self.fstack.append(cast("double", self.read(ci, ops[0], True), 8, FLOAT))
        elif mn in ("fst", "fstp"):
            self.float_move(ci, mn, ops[0])
        elif mn == "fistp":
            if (ops[0].size, True) not in SIZE_TYPE:
                raise Unliftable("op: fistp")
            t = SIZE_TYPE[ops[0].size, True]
            self.float_store(ci, ops[0], cast(t, self.st(0), ops[0].size, True), True)
            self.fstack.pop()
        elif mn == "fchs":
            self.fstack[-1] = E(f"-{paren(self.st(0))}", pure=self.st(0).pure)
        elif mn == "fabs":
            self.lf.externs.setdefault("fabs", "double fabs(double);")
            self.fstack[-1] = E(f"fabs({self.st(0)})", pure=self.st(0).pure)
        else:
            self.float_status(ci, mn, ops)

    def float_arith(self, ci, mn, ops) -> None:
        """`op st(0), x` by default; two registers, or a popping form, write `st(i)` instead."""
        name = X87_POPPING.get(mn, mn)
        popping = mn in X87_POPPING
        into = _st_number(ci, ops[0]) if popping or len(ops) == 2 else 0
        a = self.st(into)
        b = self.st(0) if popping else self.float_read(ci, ops[-1])
        if name.endswith("r"):
            a, b = b, a
        self.fstack[-1 - into] = binop(X87_ARITHMETIC[name], a, b)
        if popping:
            self.fstack.pop()

    def float_move(self, ci, mn, op) -> None:
        """`fst` and `fstp`, to memory or to a stack register."""
        e = self.st(0)
        if op.type == X86_OP_REG:
            n = _st_number(ci, op)
            self.st(n)  # the register must hold something for the store to replace
            self.fstack[-1 - n] = e
        else:
            self.float_store(ci, op, e, FLOAT)
        if mn == "fstp":
            self.fstack.pop()

    def float_status(self, ci, mn, ops) -> None:
        """A compare reaches the flags in three steps: fcomp, `fnstsw ax`, sahf."""
        if mn == "fcomp":
            self.fcompare = ("fcmp", self.st(0), self.float_read(ci, ops[0]))
            self.fstack.pop()
        elif mn == "fcompp":
            self.fcompare = ("fcmp", self.st(0), self.st(1))
            del self.fstack[-2:]
        elif mn == "fnstsw":
            if self.fcompare is None or ops[0].type != X86_OP_REG:
                raise Unliftable("op: fnstsw")
            self.status, self.fcompare = self.fcompare, None
            self.regs.pop("eax", None)  # ax holds the status word now, which only sahf may read
        else:
            if self.status is None:
                raise Unliftable("op: sahf")
            self.flags, self.status = self.status, None

    def divide(self, ci, mn, ops) -> None:
        a, hi, b = self.get("eax"), self.regs.get("edx"), self.read(ci, ops[0])
        if mn == "idiv":
            if hi is None or hi.text != f"__cdq({a.text})":
                raise Unliftable("idiv: dividend is not a cdq of eax")
        else:
            if hi is None or hi.const != 0:
                raise Unliftable("div: edx is not zero")
            a, b = cast("unsigned", a, 4, False), cast("unsigned", b, 4, False)
        self.regs["eax"] = binop("/", a, b)
        self.regs["edx"] = binop("%", a, b)
        self.flags = None

    def arith(self, ci, mn, ops) -> None:
        if (
            mn == "xor"
            and ops[0].type == X86_OP_REG
            and ops[1].type == X86_OP_REG
            and ops[0].reg == ops[1].reg
        ):
            self.flags = ("res", self.write(ci, ops[0], const(0)))
            return
        if mn == "sub" and self.biases(ci, ops, shift=0, count=1):
            return
        if mn == "sar" and self.quotient(ci, ops):
            return
        if mn == "imul" and len(ops) == 3:
            a, b = self.read(ci, ops[1]), self.read(ci, ops[2])
        elif mn == "imul" and len(ops) == 1:
            raise Unliftable("op: one-operand imul")
        else:
            a, b = self.read(ci, ops[0]), self.read(ci, ops[1])
        if mn == "and" and a.boolean and b.const == BYTE_MASK:  # the `-4r` end of a setcc
            self.write(ci, ops[0], E(a.text, pure=a.pure, boolean=True))
            self.flags = ("res", a)
            return
        if (
            mn == "sar"
            and b.const == 31
            and ops[0].type == X86_OP_REG
            and ci.reg_name(ops[0].reg) == "edx"
            and "eax" in self.regs
            and self.regs["eax"].text == a.text
        ):
            self.regs["edx"] = E(f"__cdq({a.text})", pure=a.pure, sign_of=True, sign=(a, 0))
            self.flags = None
            return
        sym = {
            "add": "+",
            "sub": "-",
            "and": "&",
            "or": "|",
            "xor": "^",
            "imul": "*",
            "shl": "<<",
            "sar": ">>",
            "shr": ">>",
        }[mn]
        if mn == "shr":
            a = cast("unsigned", a, 4, False)
        target = self.write(ci, ops[0], binop(sym, a, b))
        # A sub is its compare, carry and all, while its first operand can still be read.
        self.flags = ("cmp", a, b) if mn == "sub" and ops[0].type == X86_OP_REG else ("res", target)

    # signed divide by a power of two: `sar 31` or cdq, then `sub; sar 1` or `shl n; sbb; sar n`

    def biases(self, ci, ops, shift: int, count: int) -> bool:
        """`sub r, s` or `sbb r, s`, where s holds the sign of r's value shifted left by `shift`
        and the next instruction is `sar r, count`: r holds the value biased toward zero, which
        only that sar reads. Anything else reading it refuses `op: cdq`."""
        regs = _full_regs(ci, ops)
        if regs is None or regs[0] == regs[1] or not self.closed_by_sar(regs[0], count):
            return False
        r, s = regs
        sign = self.regs.get(s)  # peeked: get refuses a sign
        if sign is None or sign.sign is None or sign.sign[1] != shift:
            return False
        v = sign.sign[0]
        if self.get(r).text != v.text:
            return False
        self.regs[r] = E(f"__bias({v.text})", pure=v.pure, sign_of=True, bias=(v, count))
        self.flags = None
        return True

    def closed_by_sar(self, r: str, count: int) -> bool:
        """The next instruction of the block is `sar r, count`."""
        following = self.insns[self.k + 1 : self.k + 2]
        if not following or following[0].mnemonic != "sar" or len(following[0].operands) != 2:
            return False
        nxt = following[0]
        dst, n = nxt.operands
        same = dst.type == X86_OP_REG and nxt.reg_name(dst.reg) == r
        return same and n.type == X86_OP_IMM and n.imm == count

    def quotient(self, ci, ops) -> bool:
        """`sar r, n` of a value biased for it: the value divided by 2^n."""
        if ops[0].type != X86_OP_REG or ops[1].type != X86_OP_IMM:
            return False
        e = self.regs.get(ci.reg_name(ops[0].reg))
        if e is None or e.bias is None or e.bias[1] != ops[1].imm:
            return False
        v, n = e.bias
        self.read_guess |= e.guess
        target = self.write(ci, ops[0], binop("/", v, const(1 << n)))
        self.flags = ("res", target)
        return True

    def cond(self, mn) -> str:
        if self.flags is None:
            raise Unliftable("jcc: no flag source")
        rel = JCC[mn]
        unsigned = rel.endswith("u")
        if unsigned and self.flags[0] == "res":
            raise Unliftable("jcc: carry of a result")
        rel = rel.rstrip("u")
        float_compare = self.flags[0] == "fcmp"  # sahf reads it through the unsigned conditions
        a, b = self.flags[1], self.flags[2] if len(self.flags) == 3 else const(0)
        if rel in ("<0", ">=0"):  # the sign of the result, which after a cmp is a - b
            a, b, rel = binop("-", a, b), const(0), rel[:-1]
        if unsigned and not float_compare:
            a = cast("unsigned", a, 4, False)
            b = cast("unsigned", b, 4, False) if not b.atom or b.const is None else b
        return f"{paren(a)} {rel} {paren(b)}"

    def compare(self, mn) -> E:
        """The condition of the jump `mn` as a 0-or-1 value."""
        c = self.cond(mn)
        return E(c, pure=all(e.pure for e in self.flags[1:]), boolean=True)

    def sbb(self, ci, ops) -> None:
        """`sbb r, r` after a compare is minus the unsigned borrow. No other form lifts."""
        same = ops[0].type == ops[1].type == X86_OP_REG and ops[0].reg == ops[1].reg
        if not same or (self.flags is not None and self.flags[0] != "cmp"):
            raise Unliftable("op: sbb")
        borrow = self.compare("jb")
        e = E(f"-({borrow})", pure=borrow.pure)
        self.write(ci, ops[0], e)
        self.flags = ("res", e)

    def switch(self, ci) -> None:
        """A table jump: one `case` per entry, and the guard's target as the `default:`."""
        index = ci.reg_name(ci.operands[0].mem.index)
        if ci.address in self.lf.guards and self.lf.compared[ci.address] != self.get(index).text:
            del self.lf.guards[ci.address]
            self.lf.unfolded = True
        self.flush(ci)
        cases = self.lf.tables[ci.address]
        merged = [t for t in cases.values() if t in self.lf.merge]
        live = set().union(*(self.lf.live_in[t] for t in merged))
        for r in sorted(live & set(GP)):
            if r in self.regs:
                self.assign(r)
        self.out.append(f"switch ({self.get(index)}) {{")
        self.out += [f"case {k}: goto L{t:X};" for k, t in cases.items()]
        guard = self.lf.guards.get(ci.address)
        if guard is not None:
            self.out.append(f"default: goto L{_branch_target(guard):X};")
        self.out.append("}")

    def jcc(self, ci, mn) -> None:
        self.flush(ci)
        jump = next((j for j, g in self.lf.guards.items() if g.address == ci.address), None)
        if jump is not None:
            self.end_assign_jump(ci)  # its test is the switch's own: the compiler writes it again
            self.lf.compared[jump] = self.flags[1].text if self.flags else None
            return
        t = _branch_target(ci)
        if not self.lf.in_row(t):
            self.out.append(f"if ({self.cond(mn)}) {{ {self.tail(ci, t)} }}")
            return
        self.end_assign_jump(ci)
        self.out.append(f"if ({self.cond(mn)}) goto L{t:X};")

    def end_assign_jump(self, ci) -> None:
        """Before leaving the block: every register live into a merge successor is its variable
        (a successor with this block as its only predecessor inherits the expressions)."""
        t = _branch_target(ci)
        succ = [x for x in (t,) if x is not None and x in self.lf.merge]
        if ci.mnemonic != "jmp":
            succ += (
                [x for x in self.lf.live_in if x > ci.address and x in self.lf.merge][:1]
                if self._falls_into_merge(ci)
                else []
            )
        live = set().union(*(self.lf.live_in[x] for x in succ)) if succ else set()
        for r in sorted(live & set(GP)):
            if r in self.regs:
                self.assign(r)

    def _falls_into_merge(self, ci) -> bool:
        nxt = next((x for x in sorted(self.lf.live_in) if x > ci.address), None)
        return nxt is not None and nxt in self.lf.merge

    def note_values(self, ci) -> None:
        """What each argument register holds at the call `ci`, for call_notes. Only a register
        something still reads: every block starts with the name of each variable, and only a
        needed register is kept right when a name it reads changes, so any other text here would
        be a guess. A narrow write prints at its width: `al=5` is true where `eax=5` is not, and
        once esp is lost, text reading a stack name goes, as a guess always does. A later run
        overwrites an earlier one."""
        known = [
            r
            for r in ARG_REGS
            if r in self.regs
            and r in self.needed
            and not self.regs[r].guess
            and not (self.esp_lost and _STACK_NAME.search(self.regs[r].text))
        ]
        self.lf.call_values[ci.address] = {
            LOW_PARTS.get((r, self.regs[r].written), r): self.regs[r].text for r in known
        }

    def call(self, ci) -> None:
        self.note_values(ci)
        t = _branch_target(ci)
        if t is None:
            raise Unliftable("call: indirect")
        name, sig = self.lf.callee(t)
        nregs = max(sig.nregs if sig else 0, _evidence(self.insns, ci))
        if sig is None:
            self.esp_lost = True  # nothing says what the callee pops
            sig = Sig(nregs, 0, True)
        if len(self.pushes) < sig.nstack:
            raise Unliftable("call: stack arguments not pushed in the block")
        self.flush(ci)
        live = self.lf.after.get(ci.address, set())
        if "eax" in live:
            if not sig.returns:
                raise Unliftable("call: result of a void callee is used")
            self.keep_readers("r_eax", "eax", live)
        args = [self.get(r) for r in ARG_REGS[: min(nregs, 4)]]
        if sig.nstack:
            stack = self.pushes[-sig.nstack :][::-1]
            del self.pushes[-sig.nstack :]
            args += stack
            self.esp += 4 * sig.nstack
        text = f"{name}({', '.join(str(a) for a in args)})"
        self.lf.externs.setdefault(
            name,
            f"{'int' if sig.returns else 'void'} {name}"
            f"({', '.join('int' for _ in args) or 'void'});",
        )
        # Watcom callees keep every register but eax.
        for r in list(self.regs):
            if r == "eax":
                del self.regs[r]
        if "eax" in live:
            self.keep_held("r_eax")
            self.lf.regvars.add("eax")
            self.out.append(f"r_eax = {text};")
            self.regs["eax"] = var("r_eax")
        else:
            self.out.append(f"{text};")
        self.flags = None

    def tail(self, ci, t: int) -> str:
        """`return f(args);` for a tail jump to the row at `t`."""
        name, sig = self.lf.callee(t)
        nregs = max(sig.nregs if sig else 0, _evidence(self.insns, ci))
        if sig is not None and sig.nstack:
            raise Unliftable("tail: callee with stack arguments")
        args = ", ".join(str(self.get(r)) for r in ARG_REGS[:nregs])
        returns = self.lf.sig.returns
        self.lf.externs.setdefault(
            name,
            f"{'int' if returns else 'void'} {name}"
            f"({', '.join('int' for _ in range(nregs)) or 'void'});",
        )
        return f"return {name}({args});" if returns else f"{name}({args}); return;"

    def ret(self) -> None:
        if self.lf.sig.returns:
            self.out.append(f"return {self.get('eax')};")
        else:
            self.out.append("return;")


# ---- helpers ----


def _full(name: str) -> str:
    return SUB[name][0] if name in SUB else name


def _full_regs(ci, ops) -> tuple[str, str] | None:
    """The two full general registers a two-operand instruction names, or None."""
    if len(ops) != 2 or any(op.type != X86_OP_REG for op in ops):
        return None
    names = (ci.reg_name(ops[0].reg), ci.reg_name(ops[1].reg))
    return names if all(name in GP for name in names) else None


def _reads(e: E, name: str) -> bool:
    return re.search(rf"\b{name}\b", e.text) is not None


def _renamed(e: E, name: str, new: str) -> E:
    return replace(e, text=re.sub(rf"\b{name}\b", new, e.text), scaled=None, sign=None, bias=None)


def _unsigned_reader(ci) -> bool:
    """True for a flag reader that takes the carry: `jb`, `seta`, `sbb` and their kind."""
    if ci is None:
        return False
    mn = ci.mnemonic
    return mn == "sbb" or JCC.get(f"j{mn[3:]}" if mn.startswith("set") else mn, "").endswith("u")


def _narrowed(v: int, size: int, signed: bool) -> int:
    """The `size`-byte immediate `v` as a C value of that width."""
    bits = 8 * size
    v &= (1 << bits) - 1
    return v - (1 << bits) if signed and v >> (bits - 1) else v


def _called_name(name: str) -> str:
    """The C name of a function, whose symbol may carry the register convention's `_`."""
    return name.removesuffix("_")


def _esp_step(ci) -> int:
    """The N of `sub esp, N` or `add esp, N`."""
    if ci.operands[1].type != X86_OP_IMM:
        raise Unliftable("stack: esp moved by a register")
    return ci.operands[1].imm


def _frees_stack(ci) -> bool:
    return ci.mnemonic == "add" and ci.op_str.startswith("esp, ")


def _writes_esp(ci) -> bool:
    return any(ci.reg_name(r) == "esp" for r in ci.regs_access()[1])


def _esp_change(ci) -> int | None:
    """What `ci` adds to esp, or None when the instruction alone does not say."""
    if not _writes_esp(ci):
        return 0
    if ci.mnemonic in ("push", "pop"):
        return 4 if ci.mnemonic == "pop" else -4
    moved = ci.mnemonic in ("add", "sub") and ci.op_str.startswith("esp, ")
    if not moved or ci.operands[1].type != X86_OP_IMM:
        return None
    return _esp_step(ci) if ci.mnemonic == "add" else -_esp_step(ci)


def _stores(ci) -> bool:
    """True when `ci` writes memory through its first operand."""
    if not ci.operands or ci.operands[0].type != X86_OP_MEM:
        return False
    return bool(ci.operands[0].access & CS_AC_WRITE) or ci.mnemonic in X87_STORES


def _st_number(ci, op) -> int:
    """3 for the register `st(3)`."""
    return int(ci.reg_name(op.reg).removeprefix("st(").removesuffix(")"))


def _slot_name(off: int) -> str:
    return f"s_{-off:x}"


def _operand_reads(ci):
    """(register name, width) of what `ci` reads through its operands: a memory operand's base
    and index are read whole, whatever the access's width."""
    moves = len(ci.operands) > 1 and ci.mnemonic in ("mov", "movsx", "movzx", "lea")
    for op in ci.operands[1:] if moves else ci.operands:
        if op.type == X86_OP_REG:
            name = ci.reg_name(op.reg)
            yield name, _reach(name, op.size)
    for op in ci.operands:
        if op.type == X86_OP_MEM:
            for reg in (op.mem.base, op.mem.index):
                if reg:
                    yield ci.reg_name(reg), 4


def _note_reads(insns, reads: dict, written: frozenset) -> frozenset:
    """Add what `insns` read of the registers in `reads` and not in `written`, as (width,
    mnemonic). Returns `written` with what they write."""
    for ci in insns:
        for name, width in _operand_reads(ci):
            full = _full(name)
            if full in reads and full not in written:
                reads[full].add((width, ci.mnemonic))
        written |= _use_def(ci)[1] & reads.keys()
    return written


def _reach(name: str, size: int) -> int:
    """The width a value needs to hold this operand: `ah` is one byte, but no byte or word holds
    it, because it sits above the low byte."""
    return 4 if name in HIGH_BYTES else size


def _const_write(b: Block) -> tuple[str, int] | None:
    """(register, value) when `b` only writes a constant to a register, and perhaps jumps."""
    body = b.insns[:-1] if b.insns[-1].mnemonic == "jmp" else b.insns
    if len(body) != 1:
        return None
    ci = body[0]
    ops = ci.operands
    if len(ops) != 2 or ops[0].type != X86_OP_REG:
        return None
    if ci.mnemonic == "mov" and ops[1].type == X86_OP_IMM:
        return ci.reg_name(ops[0].reg), ops[1].imm
    if ci.mnemonic == "xor" and ops[1].type == X86_OP_REG and ops[0].reg == ops[1].reg:
        return ci.reg_name(ops[0].reg), 0
    return None


def _boolean_helper(fall: Block, taken: Block) -> bool:
    """Both arms of a diamond write 0 and 1 to one register, then join."""
    a, b = _const_write(fall), _const_write(taken)
    if a is None or b is None or a[0] != b[0] or {a[1], b[1]} != {0, 1}:
        return False
    return len(fall.succ) == len(taken.succ) == 1 and fall.succ == taken.succ


def _min_max(b: Block, fall: Block, taken: Block) -> str | None:
    """`cmp a, b`, a conditional skip of one `mov a, b`. A swapped compare swaps the name."""
    compare, skip = (b.insns[-2], b.insns[-1]) if len(b.insns) > 1 else (None, None)
    move = fall.insns[0]
    if compare is None or compare.mnemonic != "cmp" or len(fall.insns) != 1:
        return None
    if move.mnemonic != "mov" or fall.succ != [taken.start]:
        return None
    swapped = ", ".join(reversed(compare.op_str.split(", ")))
    if move.op_str not in (compare.op_str, swapped):
        return None
    if skip.mnemonic not in MIN_SKIP | MAX_SKIP:
        return None
    least = (skip.mnemonic in MIN_SKIP) == (move.op_str == compare.op_str)
    return "MIN" if least else "MAX"


def _idiom(b: Block, fall: Block, taken: Block) -> str | None:
    if _boolean_helper(fall, taken):
        return "inlined boolean helper"
    name = _min_max(b, fall, taken)
    return None if name is None else f"{name} written out"


def _reachable(blocks, start: int) -> set[int]:
    """The blocks a path from `start` reaches."""
    seen, todo = set(), [start]
    while todo:
        s = todo.pop()
        if s not in seen:
            seen.add(s)
            todo += blocks[s].succ
    return seen


def _branch_target(ci) -> int | None:
    ops = ci.operands
    if len(ops) == 1 and ops[0].type == X86_OP_IMM:
        return ops[0].imm & 0xFFFFFFFF
    return None


_RESULT_USED: dict[str, tuple] = {}
_BUILDING: set[str] = set()


def result_used(exe: ExeInputs) -> tuple[set, set] | None:
    """(callees whose result some caller reads, callees with any direct caller) over every
    game row of the EXE, cached in CACHE_DIR / result-used-<exe>.json. Signatures made during
    the build skip the demotion this census feeds, so they stay in a dict of its own."""
    stem = exe.stem
    if stem in _BUILDING:
        return _RESULT_USED.get(stem)
    found = _read_census(stem)
    if found is not None:
        return found
    _BUILDING.add(stem)
    try:
        used, called = _census(exe)
    finally:
        _BUILDING.discard(stem)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    census = {"used": sorted(used), "called": sorted(called)}
    write_atomic(_census_file(stem), json.dumps(census).encode("ascii"))
    _RESULT_USED[stem] = (used, called)
    return _RESULT_USED[stem]


def _census_file(stem: str) -> Path:
    return CACHE_DIR / f"result-used-{stem}.json"


def _read_census(stem: str) -> tuple[set, set] | None:
    """The census of `stem` from memory or from a valid file, or None. It never builds one."""
    if stem in _RESULT_USED:
        return _RESULT_USED[stem]
    cache = _census_file(stem)
    if not cache.is_file():
        return None
    try:
        data = json.loads(cache.read_text(encoding="utf-8"))
        _RESULT_USED[stem] = (set(data["used"]), set(data["called"]))
    except ValueError, KeyError, TypeError:
        return None  # a truncated file, or one of another shape, is no census
    return _RESULT_USED[stem]


def _census(exe: ExeInputs) -> tuple[set, set]:
    used, called = set(), set()
    census_sigs: dict[int, Sig] = {}
    for row in exe.rows:
        if row.kind not in (KIND_GAME, KIND_THUNK):
            continue
        try:
            lf = Lifter(exe, row, census_sigs)
            _, _, _, blocks, order, _, after = lf.prepare(frozenset({"eax"}), strict=False)
        except Unliftable:
            continue
        for b in blocks.values():
            for ci in b.insns:
                t = _branch_target(ci) if ci.mnemonic == "call" else None
                if t is None:
                    continue
                called.add(t)
                if "eax" in after.get(ci.address, set()):
                    used.add(t)
    return used, called


_INDEX: dict[int, tuple] = {}


def _index(exe: ExeInputs) -> tuple[dict, list, list]:
    """{start: row}, sorted starts and rows of an EXE, built once."""
    key = id(exe)
    if key not in _INDEX:
        rows = sorted(exe.rows, key=lambda r: r.start)
        _INDEX[key] = ({r.start: r for r in rows}, [r.start for r in rows], rows)
    return _INDEX[key]


_FIXUPS: dict[int, FixupIndex] = {}


def _fixup_index(exe: ExeInputs) -> FixupIndex:
    """The EXE's fixups by field address, built once."""
    key = id(exe)
    if key not in _FIXUPS:
        _FIXUPS[key] = FixupIndex(exe.fixups)
    return _FIXUPS[key]


def _typed_var(lf, r: str) -> E:
    t = lf.vartype.get(r, "int")
    size = {"unsigned char": 1, "signed char": 1, "short": 2, "unsigned short": 2}.get(t, 4)
    return var(f"r_{r}", size, not t.startswith("unsigned"))


def _evidence(insns, call) -> int:
    """1 + the index of the last argument register written since the previous call (or the
    block start) and not read before `call`: the call site's own evidence of its arguments."""
    n, pending = 0, set()
    for ci in insns:
        if ci.address == call.address:
            break
        if ci.mnemonic == "call":
            pending = set()
            continue
        u, d = _use_def(ci)
        pending = (pending - (u - d)) | (d & set(ARG_REGS))
    for idx, reg in enumerate(ARG_REGS):
        if reg in pending:
            n = idx + 1
    return n


def _use_def(ci) -> tuple[set, set]:
    regs_read, regs_write = ci.regs_access()
    u = {_full(ci.reg_name(r)) for r in regs_read} & set(GP)
    d = {_full(ci.reg_name(r)) for r in regs_write} & set(GP)
    if (
        ci.mnemonic in ("xor", "sbb")  # sbb r, r reads the carry flag, never r
        and len(ci.operands) == 2
        and ci.operands[0].type == X86_OP_REG
        and ci.operands[0].reg == ci.operands[1].reg
    ):
        u = set()
    # A high byte write keeps the register's other bytes: it is a use of the full register too.
    u |= {_full(ci.reg_name(r)) for r in regs_write if ci.reg_name(r) in HIGH_BYTES}
    if ci.mnemonic == "call":
        u = {"eax", "edx", "ebx", "ecx"} & u  # refined per callee in the run
        d = {"eax"}
    return u, d


def lift_row(exe: ExeInputs, start: int) -> str:
    row = next(r for r in exe.rows if r.start == start)
    return Lifter(exe, row).lift()


def call_notes(exe: ExeInputs, row: FunctionRow) -> dict[int, str]:
    """`eax=<expr> dl=<expr>` by the address of each call of `row` with a known register. A
    refusal costs what comes after it, never what came before. This runs in a live session, so
    it must not build the census, and a stem in _BUILDING is what stops result_used doing so. A
    valid census is read: it decides `void`, and through that which registers are arguments, so
    the notes can differ without one."""
    if row.kind == KIND_DATA_IN_CODE:
        return {}  # its bytes only happen to decode
    lifter = Lifter(exe, row, holes=True)
    if _read_census(exe.stem) is None:
        _BUILDING.add(exe.stem)
    try:
        lifter.lift()
    except Unliftable:
        pass  # the lifter's own refusal: the notes gathered so far are the answer
    finally:
        _BUILDING.discard(exe.stem)
    return {
        va: " ".join(f"{reg}={text}" for reg, text in values.items())
        for va, values in lifter.call_values.items()
        if values
    }
