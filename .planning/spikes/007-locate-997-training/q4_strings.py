"""Spike 007 q4: the UI-text route through get_text, end to end (D-03, D-26).

Almost all UI text sits in one sectioned blob that code reaches only through
get_text(section, index): UFO2P func_00063800 (table 0xF3794), TACP func_0005B360 (table
0x292D18). Watcom passes section in eax and index in edx.

Claims, per EXE:
- get-text-table: the section-pointer table decodes self-consistently. Its extent runs from the
  table to the next address any code row references or to the first nonzero slot without a
  fixup, whichever comes first; null slots inside it are empty sections. Every non-null slot is
  an LE fixup to a string start in the data object, below the table, and no two slots share a
  start. UFO2P: the
  slot count equals EXPECTED and the loop bound of the table's dump routine is research's "50
  sections". TACP: the counts are measured and reported.
- get-text-args: for every direct call (or jump) to get_text, the constant tracker of q1 recovers
  (section, index) in the call's basic block. The rate of fully recovered sites is claimed
  >= 80% (D-03 research target); a lower rate is a finding. Section-only sites (index computed,
  base + i loops) are counted as partial. Recovered pairs that name a null section or an index
  past the section's end are reported (TACP: shared code that asks for UFO2P's numbering).
- speed-labels (TACP): the speed labels of the battlescape (keyword labels pause / slow / normal /
  double / quadruple) by get_text (section, index), their call sites, and the speed value the
  nearest `cmp [speed], v` before each site tests. (q2 did this for UFO2P.)
Then, over both EXEs:
- item <id>: for each of 12 sampled Tier 2-4 items, its EXPECTED keyword is matched (case
  insensitive) inside the data strings. Route S: a string in the get_text blob -> its (section,
  index) -> call sites with that pair fully recovered -> their rows. Route F: a string with an
  exact LE fixup from a game or thunk row (file names, hand-off files) -> that row. The item is
  found when either route gives at least one row. Sites whose section matches but whose index is
  computed are reported as partial and do not count. "q4 found N of 12" closes the sample.

Run from the main checkout:
    uv run python .planning/spikes/007-locate-997-training/q4_strings.py [--plant]

--plant expects an impossible UFO2P slot count (0x10000); the run must FAIL. Prints
addresses, counts, rates, protocol/rate constants and keyword labels only: never a game string,
game bytes or instruction text. Reads orig/ only, writes nothing.
"""

from __future__ import annotations

import argparse
import bisect
import sys
from dataclasses import dataclass, field

from q1_timebase import EXES, Image, Report, hx, hxs, imm, operands, tracked
from q2_tickrule import mem_global
from q3_training import data_span

POINTER_KINDS = frozenset({0x06, 0x07})  # LE source types: ptr16:32, off32
RATE_TARGET = 0.80  # D-03 research: arg recovery for at least 80% of call sites
SHOW_ROWS = 8  # rows printed per route (the count is always printed)
LABEL_KEYWORDS = ("pause", "slow speed", "normal speed", "double speed", "quadruple speed")

# Copied from 07-R1-locate.md (Q2 "Strings": get_text rows and tables, "50 sections"); the
# entries marked "this spike" were measured by this script's first run and are pinned here.
EXPECTED = {
    "UFO2P.EXE": {
        "get_text": 0x00063800,
        "table": 0x000F3794,
        "slots": 52,  # this spike: research's 50 is the dump loop's bound (`dump_bound`)
        "dump_bound": 50,
    },
    "TACP.EXE": {
        "get_text": 0x0005B360,
        "table": 0x00292D18,
        "slots": None,  # measured and reported
        "dump_bound": None,
        "speed": 0x000E6C24,  # q2 (this spike): TACP's speed variable
        "speed_labels": {"pause": 0, "slow speed": 1, "normal speed": 2,
                         "double speed": 4},  # this spike
    },
}  # fmt: skip
PLANT_SLOTS = 0x10000

# The 12-item Tier 2-4 sample of 07-08-PLAN.md (R1 Q4 rows with evidence S, F or H). Each
# keyword is a short label chosen for the item before it is searched; it is printed, the
# strings it matches are not.
SAMPLE = (
    ("263-4", "chrysalis", "eggs and chrysalises hatch"),
    ("263-6", "funding assessment", "weekly funding"),
    ("263-9", "improve relations", "bribes"),
    ("263-13", "combat training", "agent training on base"),
    ("263-15", "transfer", "transfer of agents and items"),
    ("263-22", "tactical.map", "battle map spawn and variation"),
    ("264-3", "score", "nightly score and finances"),
    ("264-10", "kills", "medals and per-battle stats"),
    ("264-16", "treaty", "treaties, raids, storming"),
    ("264-21", "/music/", "dynamic music"),
    ("265-1", "brain.dat", "battle AI (Learning AI files)"),
    ("265-13", "new recruit", "name generator"),
)


# ---- the get_text table ----


@dataclass
class Table:
    va: int
    slots: int
    pointers: dict[int, int]  # slot -> string start
    blob: tuple[int, int]  # [lowest section start, table)
    starts: list[int] = field(default_factory=list)  # sorted section starts
    owner: list[int] = field(default_factory=list)  # slot of each sorted start
    strings: dict[int, int] = field(default_factory=dict)  # slot -> strings in the section
    problems: list[str] = field(default_factory=list)


def code_refs(img: Image) -> dict[int, set[int]]:
    """Target address -> game/thunk rows holding an LE fixup that resolves to it."""
    out: dict[int, set[int]] = {}
    for fld in img.fields.values():
        row = img.row_at(fld.va)
        if row is not None and row.kind in ("game", "thunk"):
            out.setdefault(fld.target, set()).add(row.start)
    return out


def decode_table(img: Image, va: int, refs: dict[int, set[int]]) -> Table:
    nxt = min(t for t in refs if t > va)
    slots = (nxt - va) // 4
    for k in range(slots):
        word = int.from_bytes(img.flat[va + 4 * k : va + 4 * k + 4], "little")
        if word and va + 4 * k not in img.fields:
            slots = k
            break
    lo, hi = data_span(img)
    pointers = {k: f.target for k in range(slots) if (f := img.fields.get(va + 4 * k))}
    table = Table(va, slots, pointers, (min(pointers.values(), default=va), va))
    for k, start in sorted(pointers.items()):
        fld = img.fields[va + 4 * k]
        if fld.kind not in POINTER_KINDS or fld.size != 4:
            table.problems.append(f"slot {k} not an off32")
        if not (lo <= start < va < hi):
            table.problems.append(f"slot {k} outside [data, table)")
        elif start > lo and img.flat[start - 1] != 0:
            table.problems.append(f"slot {k} not at a string start")
    if len(set(pointers.values())) != len(pointers):
        table.problems.append("slots share a start")
    ordered = sorted((s, k) for k, s in pointers.items())
    table.starts = [s for s, _ in ordered]
    table.owner = [k for _, k in ordered]
    ends = table.starts[1:] + [va]
    for (start, k), end in zip(ordered, ends, strict=True):
        table.strings[k] = bytes(img.flat[start:end]).count(0)
    return table


def locate_string(table: Table, img: Image, va: int) -> tuple[int, int] | None:
    """The get_text (section, index) of the string starting at `va`, if it is in the blob."""
    if not table.blob[0] <= va < table.blob[1]:
        return None
    i = bisect.bisect_right(table.starts, va) - 1
    if i < 0:
        return None
    return table.owner[i], bytes(img.flat[table.starts[i] : va]).count(0)


def dump_bounds(img: Image, table: int, refs: dict[int, set[int]]) -> set[int]:
    """Immediates of a `cmp _, imm` right before a backward conditional jump, in the rows that
    reference the table (the routine that dumps the sections loops to this bound)."""
    found = set()
    for start in refs.get(table, ()):
        insns = img.insns(img.starts[start])
        for prev, insn in zip(insns, insns[1:], strict=False):
            dest = img.target(insn) if insn.is_conditional else None
            ops = operands(prev)
            if dest is not None and dest < insn.va and prev.mnemonic == "cmp" and len(ops) == 2:
                if (value := imm(ops[1])) is not None:
                    found.add(value)
    return found


# ---- get_text call sites ----


@dataclass(frozen=True)
class Site:
    va: int
    row: int
    section: int | None
    index: int | None
    guard: int | None  # TACP: the speed value of the nearest `cmp [speed], v` before it


def call_sites(img: Image, get_text: int, speed: int | None) -> list[Site]:
    out = []
    for row in img.walked():
        guard = None
        for insn, regs in tracked(img, row):
            ops = operands(insn)
            if speed is not None and insn.mnemonic == "cmp" and len(ops) == 2 \
                    and mem_global(img, insn) == speed:
                guard = imm(ops[1])
            if (insn.is_call or insn.is_jump) and img.target(insn) == get_text:
                sec, idx = regs.get("eax"), regs.get("edx")
                out.append(Site(insn.va, row.start, sec if isinstance(sec, int) else None,
                                idx if isinstance(idx, int) else None, guard))  # fmt: skip
    return out


def valid(table: Table, site: Site) -> bool:
    return site.section in table.pointers and 0 <= site.index < table.strings[site.section]


# ---- data strings by keyword ----


def strings_matching(img: Image, keyword: str) -> list[int]:
    """Starts of the NUL-terminated data strings holding `keyword`, case insensitive."""
    lo, hi = data_span(img)
    key = keyword.lower().encode()
    low = bytes(img.flat[lo:hi]).lower()
    found = set()
    at = low.find(key)
    while at >= 0:
        start = lo + at
        while start > lo and img.flat[start - 1] != 0:
            start -= 1
        found.add(start)
        at = low.find(key, at + 1)
    return sorted(found)


@dataclass
class Hit:
    s_rows: set[int] = field(default_factory=set)
    f_rows: set[int] = field(default_factory=set)
    partial_rows: set[int] = field(default_factory=set)
    strings: int = 0


def search(img: Image, table: Table, sites: list[Site], refs: dict[int, set[int]],
           keyword: str) -> Hit:  # fmt: skip
    hit = Hit()
    by_pair: dict[tuple[int, int], set[int]] = {}
    by_section: dict[int, set[int]] = {}
    for site in sites:
        if site.section is not None and site.index is not None:
            by_pair.setdefault((site.section, site.index), set()).add(site.row)
        elif site.section is not None:
            by_section.setdefault(site.section, set()).add(site.row)
    for va in strings_matching(img, keyword):
        hit.strings += 1
        hit.f_rows |= refs.get(va, set())
        pair = locate_string(table, img, va)
        if pair is not None:
            hit.s_rows |= by_pair.get(pair, set())
            hit.partial_rows |= by_section.get(pair[0], set())
    hit.partial_rows -= hit.s_rows
    return hit


def rows_text(rows: set[int]) -> str:
    shown = sorted(rows)[:SHOW_ROWS]
    more = f" +{len(rows) - SHOW_ROWS}" if len(rows) > SHOW_ROWS else ""
    return f"{len(rows)} {hxs(shown)}{more}"


# ---- claims ----


def claim_table(report: Report, img: Image, table: Table, exp: dict, refs) -> None:
    bounds = dump_bounds(img, table.va, refs)
    ok = not table.problems
    if exp["slots"] is not None:
        ok = ok and table.slots == exp["slots"] == len(table.pointers)
    if exp["dump_bound"] is not None:
        ok = ok and bounds == {exp["dump_bound"]}
    detail = (f"table {hx(table.va)} slots {table.slots} non-null {len(table.pointers)} "
              f"strings {sum(table.strings.values())} "
              f"blob [{hx(table.blob[0])}..{hx(table.blob[1])}) "
              f"dump-loop bound {sorted(bounds)} expected slots {exp['slots']} "
              f"bound {exp['dump_bound']}; self-consistent {not table.problems}")
    if table.problems:
        detail += " (" + "; ".join(table.problems[:4]) + ")"
    report.claim(img.name, ok, "get-text-table", detail)


def claim_args(report: Report, img: Image, table: Table, sites: list[Site]) -> float:
    full = [s for s in sites if s.section is not None and s.index is not None]
    section_only = sum(s.section is not None and s.index is None for s in sites)
    index_only = sum(s.section is None and s.index is not None for s in sites)
    neither = len(sites) - len(full) - section_only - index_only
    bad = [s for s in full if not valid(table, s)]
    rate = len(full) / len(sites) if sites else 0.0
    rows = len({s.row for s in sites})
    report.claim(img.name, rate >= RATE_TARGET, "get-text-args",
                 f"sites {len(sites)} in {rows} rows; full {len(full)} = {rate:.1%} "
                 f"(target {RATE_TARGET:.0%}); section-only {section_only}, index-only "
                 f"{index_only}, neither {neither}; full pairs past their section {len(bad)} "
                 f"{hxs(s.va for s in bad)}")  # fmt: skip
    return rate


def claim_speed_labels(report: Report, img: Image, table: Table, sites: list[Site],
                       exp: dict) -> None:  # fmt: skip
    found: dict[str, tuple[int, int]] = {}
    lo, hi = table.blob
    for key in LABEL_KEYWORDS:
        for va in strings_matching(img, key):
            text = bytes(img.flat[va : img.flat.index(0, va)]).lower()
            if text == key.encode() and lo <= va < hi:
                found[key] = locate_string(table, img, va)
    parts, speeds = [], {}
    for key, pair in found.items():
        at = [s for s in sites if (s.section, s.index) == pair]
        guards = {s.guard for s in at}
        speeds[key] = next(iter(guards)) if len(guards) == 1 else None
        tested = sorted(g for g in guards if g is not None)
        parts.append(f"{key} {pair[0]}/{pair[1]} sites {hxs(s.va for s in at)} "
                     f"rows {hxs({s.row for s in at})} speed {tested}")
    want = exp["speed_labels"]
    ok = {k: v for k, v in speeds.items() if v is not None} == want
    absent = [k for k in LABEL_KEYWORDS if k not in found]
    report.claim(img.name, ok, "speed-labels",
                 "; ".join(parts) + f"; absent {absent}; expected {want}")


def claim_sample(report: Report, data: dict) -> int:
    found = 0
    for item, keyword, _what in SAMPLE:
        parts, total = [], set()
        for name in EXES:
            img, table, sites, refs = data[name]
            hit = search(img, table, sites, refs, keyword)
            total |= {(name, r) for r in hit.s_rows | hit.f_rows}
            parts.append(f"{name.split('.')[0]}: strings {hit.strings} S rows "
                         f"{rows_text(hit.s_rows)} F rows {rows_text(hit.f_rows)} "
                         f"partial {len(hit.partial_rows)}")
        found += bool(total)
        report.claim("q4", bool(total), "item",
                     f"{item} '{keyword}' rows found {len(total)}; " + "; ".join(parts))
    print(f"q4 found {found} of {len(SAMPLE)}")
    return found


def expected(plant: bool) -> dict:
    exp = {name: dict(values) for name, values in EXPECTED.items()}
    if plant:
        true = exp["UFO2P.EXE"]["slots"]
        print(f"PLANT UFO2P.EXE expected get_text slots {true} -> {PLANT_SLOTS:#x}")
        exp["UFO2P.EXE"]["slots"] = PLANT_SLOTS
    return exp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plant", action="store_true", help="expect an impossible slot count")
    args = parser.parse_args(argv)
    exp_all = expected(args.plant)
    report = Report()
    data = {}
    for name in EXES:
        img = Image(name)
        exp = exp_all[name]
        refs = code_refs(img)
        table = decode_table(img, exp["table"], refs)
        sites = call_sites(img, exp["get_text"], exp.get("speed"))
        claim_table(report, img, table, exp, refs)
        claim_args(report, img, table, sites)
        if "speed_labels" in exp:
            claim_speed_labels(report, img, table, sites, exp)
        data[name] = (img, table, sites, refs)
    claim_sample(report, data)
    return report.finish()


if __name__ == "__main__":
    sys.exit(main())
