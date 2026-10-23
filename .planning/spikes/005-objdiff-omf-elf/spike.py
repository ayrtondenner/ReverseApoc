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

from mkelf import FIELD, FIELD_SIZE, ElfParts, cut_target, find_public, from_omf

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


def write_pair(pair: Pair, *, section_name: str = "_TEXT", tag: str = "") -> tuple[Path, Path]:
    folder = REPO / OUT / pair.exe.split(".")[0].lower()
    folder.mkdir(parents=True, exist_ok=True)
    target = cut_target(pair.le, pair.start, pair.end, PUBLIC, pair.names, pair.call_fields,
                        section_name=section_name)  # fmt: skip
    base = from_omf(pair.module, PUBLIC)
    return _write(folder, f"target{tag}.o", target), _write(folder, f"base{tag}.o", base)


def _write(folder: Path, name: str, parts: ElfParts) -> Path:
    path = folder / name
    path.write_bytes(parts.to_bytes())
    return path


def diff_pair(report: Report, pair: Pair) -> None:
    target, base = write_pair(pair)
    percent = objdiff_percent(target, base, PUBLIC)
    report.claim(pair.exe, percent == EXPECTED["match_percent"], "objdiff",
                 f"{PUBLIC} match_percent {percent}")  # fmt: skip


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
            if pair is not None:
                diff_pair(report, pair)
    print("ALL PASS" if report.failures == 0 else f"{report.failures} FAILED")
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
