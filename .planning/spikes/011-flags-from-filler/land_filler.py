# SPDX-License-Identifier: GPL-3.0-or-later
"""Put rows that are exact under the committed rule once 07-48 keeps the original's trailing
Watcom filler into their committed units (src/<exe>/<unit>.c), ready for `gate`.

    uv run python .planning/spikes/011-flags-from-filler/land_filler.py CANDIDATES.json \
        [--agent EXE:0xADDR:FILE ...] [--hold EXE:0xADDR ...] [--dry-run]

CANDIDATES.json is a list of [exe, "0xADDR"]. Each row's C comes from the spike 011 converter
arms (build/spike-011/all/committed, then committed+void); an --agent row brings its own file.
The successor of land_converter.py, rebuilt on tools/: compiles go through batch.compile_batch
under the unit's committed rule, and the verdict is check's own (with_relocs over all of the
unit's rows, then compare_bytes), so sibling calls resolve through the unit's public map as in
`gate`.

Rows are added to each unit one at a time, in address order. A row stays only when, with it in
the unit, it and every row already kept and every row status.csv marks matched are exact; else
the unit is put back as it was and the row is held, with the reason (a recut candidate when a
sibling regresses). `gate` (in the container) is the real verdict and the only writer of
status.csv. Holds addresses and names only, never bytes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from land_converter import matched_starts, merge

from reverseapoc import batch
from reverseapoc.cflags import DEFAULT_CFLAGS, load_cflags
from reverseapoc.check import (
    ExeInputs,
    checked_functions,
    compare_bytes,
    parse_module,
)
from reverseapoc.targets import REPO_ROOT
from reverseapoc.units import scaffold_unit

ARMS = ("committed", "committed+void")
ARM_ROOT = REPO_ROOT / "build" / "spike-011" / "all"
WORK = REPO_ROOT / "build" / "spike-011" / "land-filler"


@dataclass(frozen=True)
class Candidate:
    stem: str
    start: int
    source: Path
    author: str  # the Matched-By trailer value


def _addr(text: str) -> int:
    return int(text, 16)


def _arm_source(stem: str, start: int) -> Path | None:
    for arm in ARMS:
        path = ARM_ROOT / arm / stem / f"f_{start:08x}.c"
        if path.is_file():
            return path
    return None


def unit_verdicts(exe: ExeInputs, obj: Path, unit: str, starts: set[int]) -> dict[int, bool]:
    """check's verdict for each of `starts` in our object of `unit`: the relocation check over
    the unit's rows (its public map, its leading table) and the byte compare."""
    module = parse_module(obj.read_bytes(), obj)
    out = dict.fromkeys(starts, False)
    for d, reloc in checked_functions(module, exe.unit_rows(unit), exe):
        if d.row.start in out:
            out[d.row.start] = reloc.ok and compare_bytes(d.ours, d.row, exe.flat, reloc).ok
    return out


def _insert(text: str, name: str, c: str) -> str | None:
    marker = re.compile(rf"^INCLUDE_ASM\({re.escape(name)}\);$", re.M)
    if not marker.search(text):
        return None
    body = merge(text, c)
    return marker.sub(lambda _: f"\n{body}", text, count=1)


def _compile(exe: ExeInputs, rules, path: Path, unit: str) -> Path | None:
    obj = WORK / exe.stem / f"{unit}.obj"
    obj.parent.mkdir(parents=True, exist_ok=True)
    job = batch.Job(path, obj, batch.committed_rule(rules, exe.stem, unit))
    result = batch.compile_batch([job], 1)
    return obj if result.compiled[0].ok else None


def land_unit(exe: ExeInputs, rules, unit: str, cands: list[Candidate], dry: bool):
    """(kept, held) for one unit; the file ends with every kept row in it (or as it was)."""
    path = REPO_ROOT / "src" / exe.stem / f"{unit}.c"
    original = path.read_text(encoding="utf-8") if path.is_file() else None
    text = original if original is not None else scaffold_unit(
        exe.target.name, next(u for u in exe.units if u.unit == unit), exe.rows)
    matched = set(matched_starts(exe.stem, unit))
    kept: list[Candidate] = []
    held: list[tuple[Candidate, str]] = []
    for cand in sorted(cands, key=lambda c: c.start):
        row = batch.row_at(exe, cand.start)
        trial = _insert(text, row.name, cand.source.read_text(encoding="utf-8"))
        if trial is None:
            held.append((cand, f"no INCLUDE_ASM({row.name}) marker in {path.name}"))
            continue
        path.write_text(trial, encoding="utf-8", newline="\n")
        obj = _compile(exe, rules, path, unit)
        want = {cand.start} | {k.start for k in kept} | matched
        verdicts = unit_verdicts(exe, obj, unit, want) if obj else dict.fromkeys(want, False)
        bad = sorted(s for s, ok in verdicts.items() if not ok)
        if not bad:
            text = trial
            kept.append(cand)
            continue
        if obj is None:
            reason = "the unit does not compile with it"
        elif cand.start in bad:
            reason = "not exact inside its unit"
        else:
            reason = "regresses " + ", ".join(f"0x{s:08X}" for s in bad) + " (recut candidate)"
        held.append((cand, reason))
    if kept and not dry:
        path.write_text(text, encoding="utf-8", newline="\n")
    elif original is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(original, encoding="utf-8", newline="\n")
    return kept, held


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidates", type=Path)
    ap.add_argument("--agent", action="append", default=[], metavar="EXE:0xADDR:FILE")
    ap.add_argument("--hold", action="append", default=[], metavar="EXE:0xADDR",
                    help="an owner-held row (e.g. a ruled recut), skipped with that reason")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    holds = {(e.lower(), _addr(a)) for e, a in (h.split(":") for h in args.hold)}
    cands: list[Candidate] = []
    held: list[tuple[Candidate, str]] = []
    for stem, addr in json.loads(args.candidates.read_text(encoding="utf-8")):
        start = _addr(addr)
        source = _arm_source(stem, start)
        if source is None:
            print(f"SKIP {stem} 0x{start:08X}: no converter source")
            continue
        cands.append(Candidate(stem, start, source, "reverseapoc lift"))
    for spec in args.agent:
        stem, addr, file = spec.split(":", 2)
        cands.append(Candidate(stem.lower(), _addr(addr), Path(file),
                               "claude subagent (spike 011)"))  # fmt: skip
    rules = load_cflags(DEFAULT_CFLAGS)
    kept: list[Candidate] = []
    for stem in sorted({c.stem for c in cands}):
        exe = batch.load_exe_inputs(stem)
        mine = [c for c in cands if c.stem == stem]
        by_unit: dict[str, list[Candidate]] = {}
        for c in mine:
            if (stem, c.start) in holds:
                held.append((c, "held by owner ruling"))
                continue
            by_unit.setdefault(batch.row_at(exe, c.start).unit, []).append(c)
        for unit, group in sorted(by_unit.items()):
            k, h = land_unit(exe, rules, unit, group, args.dry_run)
            kept += k
            held += h
            for c in k:
                print(f"OK   {stem} 0x{c.start:08X} {unit} ({c.author})")
            for c, why in h:
                print(f"HELD {stem} 0x{c.start:08X} {unit}: {why}")
    for c, why in held:
        if why == "held by owner ruling":
            print(f"HELD {c.stem} 0x{c.start:08X}: {why}")
    units = sorted({f"src/{c.stem}/{batch.row_at(batch.load_exe_inputs(c.stem), c.start).unit}.c"
                    for c in kept})  # fmt: skip
    print(f"kept {len(kept)}, held {len(held)}")
    print("units ready for gate:", " ".join(units) if not args.dry_run else "(dry run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
