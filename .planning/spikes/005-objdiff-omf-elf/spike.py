"""Spike 005: does objdiff-cli 3.8.2 diff a Watcom OMF object converted to ELF32 against a
target ELF cut from the LE? The known-good pair is the cmain386 runtime row of each EXE and
Watcom's own SRC/STARTUP/386/CMAIN386.C, read in place from the owner's 10.6 tree (D-01, D-19).

Run (in the reverseapoc-build container, from the repo root):
    uv run python .planning/spikes/005-objdiff-omf-elf/spike.py [--exe NAME ...] [--plants]

Reads orig/ and the Watcom tree only; writes objects under build/spike005/ (gitignored). Prints
names, addresses, counts, booleans, percentages and SHA-1s only, never bytes or instructions.
Exit 1 when any claim fails.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from mkelf import (
    FIELD,
    FIELD_SIZE,
    PC32_ADDEND,
    R_386_32,
    R_386_PC32,
    ElfParts,
    Reloc,
    cut_target,
    find_public,
    from_omf,
    function_parts,
)

from reverseapoc.cflags import load_cflags, select_rule
from reverseapoc.le import LE, SRC_OFF32
from reverseapoc.libmatch import read_runtime_csv, read_target, runtime_csv_path, select_target
from reverseapoc.omf import read_object
from reverseapoc.targets import DEFAULT_MANIFEST, DEFAULT_ORIG, load_manifest

REPO = Path(__file__).resolve().parents[3]
SOURCE = Path("third_party/watcom/10.6/SRC/STARTUP/386/CMAIN386.C")
OUT = Path("build/spike005")
OBJECT = OUT / "cmain386.obj"
MODULE = "cmain386"
PUBLIC = "__CMain"
CALL_REL32 = 0xE8  # opcode byte before a call's rel32 field
OBJDIFF = "objdiff-cli"

# Copied from 05-RESEARCH.md "Pattern 1" (measured on the host, 2026-10-23).
EXPECTED = {
    "starts": {"UFO2P.EXE": 0x000C5C9C, "TACP.EXE": 0x000C7915},
    "compiler": "wcc386@10.6",
    "rule": ("*", "wcc386@10.6", ("-4r", "-s", "-fpi")),
    "size": 79,
    "self_relative": 4,
    "segment_relative": 5,
    "le_fixups": 5,
    "names": {
        "__ASTACKSIZ", "stackavail_", "__ASTACKPTR", "__CommonInit_",
        "____Argv", "____Argc", "main_", "exit_",
    },
    "match_percent": 100.0,
}  # fmt: skip

# Plant P3: made-up bytes in the research probe shape (05-RESEARCH.md "Code Examples"):
# mov eax,[abs32]; call rel32; mov dword [abs32], imm32; ret. Not game bytes.
SYNTH_NAME = "func_00010000_"
SYNTH_CODE = bytes.fromhex("a100000000" "e800000000" "c70500000000" "00000000" "c3")  # fmt: skip
SYNTH_RELOCS = {
    1: (R_386_32, "_D_000D0000"),
    6: (R_386_PC32, "func_00012345_"),
    12: (R_386_32, "_D_000D0010"),  # 1st relocation of the mov: the address
    16: (R_386_32, "_D_000D0020"),  # 2nd relocation of the mov: the imm32
}
SYNTH_OTHER = "_D_000D0030"
P1_FROM, P1_TO = "exit_", "main_"
P2_ADDEND = 4


@dataclass
class Report:
    failures: int = 0

    def claim(self, exe: str, ok: bool, claim: str, detail: str = "") -> bool:
        self.failures += not ok
        print(f"{'PASS' if ok else 'FAIL'} {exe} {claim} {detail}".rstrip())
        return ok


def compile_object(report: Report) -> bytes | None:
    """`reverseapoc cc` on CMAIN386.C in place under the `*` rule; the OK line must name
    wcc386@10.6."""
    rule = select_rule(load_cflags(), SOURCE.as_posix())
    flags = " ".join(rule.flags)
    report.claim("CMAIN386.C", (rule.glob, rule.spec, rule.flags) == EXPECTED["rule"], "rule",
                 f"cflags.txt:{rule.lineno} {rule.glob} {rule.spec} {flags}")  # fmt: skip
    (REPO / OUT).mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["uv", "run", "reverseapoc", "cc", SOURCE.as_posix(), "-o", OBJECT.as_posix()],
        cwd=REPO, capture_output=True, text=True, check=False,
    )  # fmt: skip
    ok_line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("OK")), "")
    spec = re.search(r"wcc386@\S+(\s+-\S+)*", ok_line)
    sha1 = re.search(r"normalized ([0-9a-f]{40})", ok_line)
    ok = proc.returncode == 0 and spec is not None and EXPECTED["compiler"] in spec.group(0)
    detail = f"{spec.group(0) if spec else 'no OK line'} exit {proc.returncode}"
    if sha1:
        detail += f" normalized {sha1.group(1)}"
    if not report.claim("CMAIN386.C", ok, "compile", detail):
        return None
    return (REPO / OBJECT).read_bytes()


def objdiff_percent(target: Path, base: Path, symbol: str) -> float | None:
    """match_percent of `symbol` in left (target) symbols, None when unpaired or absent."""
    proc = subprocess.run(
        [OBJDIFF, "diff", "-1", str(target), "-2", str(base), "-o", "-", symbol],
        cwd=REPO, capture_output=True, text=True, check=False,
    )  # fmt: skip
    if proc.returncode != 0:
        raise RuntimeError(f"{OBJDIFF} exit {proc.returncode} on {target.name} vs {base.name}")
    for entry in json.loads(proc.stdout).get("left", {}).get("symbols", []):
        name = entry.get("name") or entry.get("symbol", {}).get("name")
        if name == symbol:
            return entry.get("match_percent")
    return None


@dataclass
class Pair:
    """One EXE's cmain386 row and our object, with the fields both sides relocate."""

    exe: str
    le: LE
    start: int
    end: int
    base_va: int  # VA of our segment's offset 0
    module: object
    segment: object
    names: dict[int, str]
    call_fields: list[int]


def check_pair(report: Report, exe: str, obj: bytes) -> Pair | None:
    targets = load_manifest()
    target = select_target(targets, exe, DEFAULT_MANIFEST)
    le = LE(read_target(target, DEFAULT_ORIG, DEFAULT_MANIFEST))
    rows = [r for r in read_runtime_csv(runtime_csv_path(target.name)) if r.module == MODULE]
    if not report.claim(exe, len(rows) == 1 and PUBLIC in rows[0].publics, "row",
                        f"{MODULE} rows {len(rows)}"):  # fmt: skip
        return None
    row = rows[0]
    start, end = row.start, row.end
    report.claim(exe, start == EXPECTED["starts"][exe], "row-start", f"{start:#010x}")

    module = read_object(obj)
    seg, pub_offset = find_public(module, PUBLIC)
    size = seg.length - pub_offset
    report.claim(exe, seg.name == "_TEXT" and size == end - start == EXPECTED["size"], "size",
                 f"{seg.name} {size} row {end - start}")  # fmt: skip
    base_va = start - pub_offset

    flat = le.load_flat(relocate=False)
    le_fx = [f for f in le.fixups() if start <= f.src_va < end]
    le_mask = {va for f in le_fx for va in range(f.src_va, f.src_va + f.size)}
    our_mask = {base_va + off for off in seg.mask}
    differ = sum(
        1
        for va in range(start, end)
        if va not in le_mask | our_mask and flat[va] != seg.data[va - base_va]
    )
    report.claim(exe, differ == 0, "bytes", f"{differ} differ outside fixup fields")

    self_rel = [fx for fx in seg.fixups if not fx.segment_relative]
    seg_rel = [fx for fx in seg.fixups if fx.segment_relative]
    report.claim(exe, (len(self_rel), len(seg_rel)) == (EXPECTED["self_relative"],
                 EXPECTED["segment_relative"]), "omf-fixups",
                 f"self-relative {len(self_rel)} segment-relative {len(seg_rel)}")  # fmt: skip
    kinds_ok = all(f.kind == SRC_OFF32 for f in le_fx)
    report.claim(exe, len(le_fx) == EXPECTED["le_fixups"] and kinds_ok, "le-fixups",
                 f"{len(le_fx)} in range, all off32 {kinds_ok}")  # fmt: skip

    names, call_fields = build_name_map(report, exe, seg, base_va, flat, le_fx)
    return Pair(exe, le, start, end, base_va, module, seg, names, call_fields)


def build_name_map(report, exe, seg, base_va, flat, le_fx):
    """address -> linker name, resolved from the pair's own fields (D-19)."""
    le_by_va = {f.src_va: f for f in le_fx}
    found: dict[str, set[int]] = {}
    call_fields: list[int] = []
    opcodes_ok = covered = True
    for fx in seg.fixups:
        va = base_va + fx.offset
        stored = FIELD.unpack_from(seg.data, fx.offset)[0]
        if fx.target_kind != "extern":
            report.claim(exe, False, "name-map", f"{fx.target_kind} target at {va:#010x}")
            continue
        if fx.segment_relative:
            lf = le_by_va.get(va)
            covered &= lf is not None
            address = (lf.target_va if lf else 0) - stored - fx.displacement
        else:
            call_fields.append(va)
            opcodes_ok &= flat[va - 1] == CALL_REL32 and va not in le_by_va
            rel = FIELD.unpack_from(flat, va)[0]
            address = va + FIELD_SIZE + rel - stored - fx.displacement
        found.setdefault(fx.target_name, set()).add(address)
    ours = {base_va + fx.offset for fx in seg.fixups if fx.segment_relative}
    covered &= set(le_by_va) <= ours
    detail = f"{len(call_fields)} self-relative fields follow call rel32, no LE fixup"
    report.claim(exe, opcodes_ok, "call-opcodes", detail)
    report.claim(exe, covered, "le-coverage", "every segment-relative field has its LE fixup "
                 "and every LE fixup in range is ours")  # fmt: skip
    single = all(len(a) == 1 for a in found.values())
    names = {next(iter(a)): n for n, a in sorted(found.items()) if len(a) == 1}
    one_per_address = len(names) == len(found)
    ok = single and one_per_address and set(found) == EXPECTED["names"]
    pairs = " ".join(f"{n} {a:#010x}" for a, n in sorted(names.items(), key=lambda p: p[1]))
    report.claim(exe, ok, "name-map", f"{len(names)} names: {pairs}")
    return names, call_fields


def pair_parts(pair: Pair, *, section_name: str = "_TEXT") -> tuple[ElfParts, ElfParts]:
    """(target, base) for one EXE: the LE cut and our converted object."""
    target = cut_target(pair.le, pair.start, pair.end, PUBLIC, pair.names, pair.call_fields,
                        section_name=section_name)  # fmt: skip
    return target, from_omf(pair.module, PUBLIC)


def diff_parts(folder: str, tag: str, target: ElfParts, base: ElfParts, symbol: str):
    """Write both objects under build/spike005/<folder>/ and return objdiff's match_percent."""
    path = REPO / OUT / folder
    path.mkdir(parents=True, exist_ok=True)
    t, b = path / f"target{tag}.o", path / f"base{tag}.o"
    t.write_bytes(target.to_bytes())
    b.write_bytes(base.to_bytes())
    return objdiff_percent(t, b, symbol)


def folder_of(exe: str) -> str:
    return exe.split(".")[0].lower()


def diff_pair(report: Report, pair: Pair) -> None:
    percent = diff_parts(folder_of(pair.exe), "", *pair_parts(pair), PUBLIC)
    report.claim(pair.exe, percent == EXPECTED["match_percent"], "objdiff",
                 f"{PUBLIC} match_percent {percent}")  # fmt: skip


def below_100(percent: float | None) -> bool:
    return percent is not None and percent < EXPECTED["match_percent"]


def retarget(parts: ElfParts, old: str, new: str, rtype: int) -> bool:
    """Point the first `rtype` relocation naming `old` at `new` instead."""
    for i, r in enumerate(parts.relocs):
        if r.rtype == rtype and parts.symbols[r.symbol].name == old:
            parts.relocs[i] = Reloc(r.section, r.offset, r.rtype, parts.symbol_index(new))
            return True
    return False


def plant_pair(report: Report, pair: Pair) -> None:
    """P1 wrong call symbol in our object, P2 wrong addend in the target, P4 `.text` naming."""
    folder = folder_of(pair.exe)
    target, base = pair_parts(pair)
    done = retarget(base, P1_FROM, P1_TO, R_386_PC32)
    percent = diff_parts(folder, "-p1", target, base, PUBLIC)
    report.claim(pair.exe, done and below_100(percent), "P1-wrong-call-symbol",
                 f"{P1_FROM}->{P1_TO} match_percent {percent} (expect below 100)")  # fmt: skip

    target, base = pair_parts(pair)
    first = min((r for r in target.relocs if r.rtype == R_386_32), key=lambda r: r.offset)
    FIELD.pack_into(target.sections[0][1], first.offset, P2_ADDEND)
    percent = diff_parts(folder, "-p2", target, base, PUBLIC)
    report.claim(pair.exe, below_100(percent), "P2-wrong-addend",
                 f"R_386_32 at {pair.start + first.offset:#010x} addend {P2_ADDEND} "
                 f"match_percent {percent} (expect below 100)")  # fmt: skip

    target, base = pair_parts(pair, section_name=".text")
    percent = diff_parts(folder, "-p4", target, base, PUBLIC)
    detail = f"target section .text, base _TEXT: match_percent {percent} (expect unpaired)"
    report.claim(pair.exe, percent is None, "P4-section-.text", detail)


def synthetic(override: dict[int, str]) -> ElfParts:
    data = bytearray(SYNTH_CODE)
    parts = function_parts("_TEXT", data, SYNTH_NAME, 0, len(data))
    for offset, (rtype, name) in SYNTH_RELOCS.items():
        FIELD.pack_into(data, offset, PC32_ADDEND if rtype == R_386_PC32 else 0)
        sym = parts.symbol_index(override.get(offset, name))
        parts.relocs.append(Reloc(0, offset, rtype, sym))
    return parts


def plant_synthetic(report: Report) -> None:
    """P3: two made-up objects differing only in one relocation's symbol."""
    good = synthetic({})
    control = diff_parts("synthetic", "-p3-control", good, synthetic({12: SYNTH_OTHER}),
                         SYNTH_NAME)  # fmt: skip
    detail = f"symbol at field 12 differs: match_percent {control} (expect below 100)"
    report.claim("synthetic", below_100(control), "P3-control-1st-reloc", detail)
    percent = diff_parts("synthetic", "-p3", good, synthetic({16: SYNTH_OTHER}), SYNTH_NAME)
    report.claim("synthetic", percent == EXPECTED["match_percent"], "P3-blind-spot-2nd-reloc",
                 f"symbol at field 16 (imm32, 2nd reloc of one instruction) differs: "
                 f"match_percent {percent} (expect exactly 100.0)")  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--exe", action="append", help="UFO2P.EXE and/or TACP.EXE (default both)")
    parser.add_argument("--plants", action="store_true", help="also run plants P1-P4")
    args = parser.parse_args(argv)
    exes = args.exe or list(EXPECTED["starts"])
    report = Report()
    obj = compile_object(report)
    if obj is not None:
        for exe in exes:
            pair = check_pair(report, exe, obj)
            if pair is None:
                continue
            diff_pair(report, pair)
            if args.plants:
                plant_pair(report, pair)
    if args.plants:
        plant_synthetic(report)
    print("ALL PASS" if report.failures == 0 else f"{report.failures} FAILED")
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
