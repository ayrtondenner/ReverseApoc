# SPDX-License-Identifier: GPL-3.0-or-later
"""Phase 7.1 measurement gate (D-08, D-09, D-27): one curve point over Tier 1 and the fixed sample.

    uv run python .planning/phases/07.1-matching-tooling/measure_curve.py --point N
    uv run python .planning/phases/07.1-matching-tooling/measure_curve.py --self-check [--plant]

`--point N` lifts every Tier 1 member with the lifter's defaults into build/curve/<N>/src, retrying
a refused row with holes, runs
`reverseapoc batch` on them under the committed rule and CELL, runs `search.run_search` on each
sample row with a compiled draft that is not exact (the Tier 1 number stays converter-only, D-27),
and writes the point's row and section into 07.1-CURVE.md, with the not-matched rows by class and
route from the batch records and the lift's refusals. The first run also draws
07.1-SAMPLE.csv, which is never redrawn.
`--self-check` runs the pure functions on canned records; `--plant` flips one expectation, so the
self-check must fail. Generated C stays under the gitignored build/. Run from anywhere.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import random
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from reverseapoc import batch, classify, cli, mechanics, search
from reverseapoc.cflags import load_cflags
from reverseapoc.check import DEFAULT_CONFIG
from reverseapoc.lift import CACHE_DIR, HOLE_MARK, Lifter, Unliftable, result_used
from reverseapoc.targets import REPO_ROOT
from reverseapoc.watcom import DEFAULT_INSTALL

SEED = 20261103
PER_BUCKET = 40
TIER = 1
CELL = "-4r -oneatx -s -fpi"
NEAR = 90.0
BUCKETS = ((0, 64, "<64"), (64, 256, "64-255"), (256, 1024, "256-1023"), (1024, 1 << 30, ">=1024"))
SAMPLED = BUCKETS[1:]
OUTCOMES = ("exact", "near", "compiled", "compile-failed", "hole-draft", "refused", "crash")
TOOLS = ("converter", "search", "slots", "classify")
NO_CLASS = "none"  # an exact, refused or failed row: nothing to class
SEARCHED = ("near", "compiled")  # a compiled draft that is not exact: the rows search runs on
NUMBERS = ("t1 exact", "t1 near", "s exact", "s near")
COLUMNS = (
    "point",
    "plan",
    "head",
    "cflags sha256",
    "result-used sha256",
    "tools",
    *NUMBERS,
    "moved",
    "flat streak",
    "stop rule",
)
SAMPLE_FIELDS = ("exe", "address", "unit", "size", "bucket")
WORKERS = "12"
STOP_STREAK = 2
LAST_CHECKED = 3  # D-27: the stop rule is checked through plan 3 only
STOP_RULE = "stop the phase after two plans in a row that move nothing"

PHASE_DIR = Path(__file__).resolve().parent
SAMPLE = PHASE_DIR / "07.1-SAMPLE.csv"
CURVE = PHASE_DIR / "07.1-CURVE.md"
BUILD = REPO_ROOT / "build" / "curve"
CFLAGS = DEFAULT_CONFIG / "cflags.txt"


def summary_row(cells) -> str:
    """One table line, each cell written as given."""
    return f"| {' | '.join(str(cell) for cell in cells)} |"


HOLE_NOTE = (
    "`hole-draft` rows are refused rows that lifted with holes. They can never be exact and are "
    "never searched, so `refused` falls by them with no real gain. The reasons below count each "
    "such row's strict lift, so the retry lowers no first-refusal count."
)
HEADER = f"""# Phase 7.1 curve

What the tools reach, point by point. `measure_curve.py` writes this file; point 0 is the base,
recorded before the phase's first tooling commit, and each plan adds one point (D-08, D-09).

- **Seed and sample:** seed {SEED}. `07.1-SAMPLE.csv` holds {PER_BUCKET} rows per bucket from 64 B
  up, drawn from the not-matched, not-held Tier 1 rows. Its rows stay fixed, even if one matches
  later, and named near-miss targets stay out of it.
- **Cells:** the unit's committed rule and `{CELL}`. A row is exact when either cell is.
- **Outcomes:** `exact`; `near`, compiled with a raw score of at least {NEAR:.0f}; `compiled`, with
  a lower score; `compile-failed`; `hole-draft`, a refused row that lifted with holes, which can
  never be exact; `refused`, the lifter raised `Unliftable` with holes too; `crash`, the lifter
  raised anything else. `matched` is a status, not an outcome, so matched rows get their own line.
- **Judge-exact:** every `exact` here is the judge's. A row can be judge-exact and still not land:
  tail merging and sibling regressions are the gate's to find.
- **Move (D-27):** the Tier 1 number stays converter-only, and the sample runs each row through
  every tool built so far, at a fixed budget. A change in `exact` or `near` on either number is
  movement, in either direction, and the `moved` cell shows each change's sign. The stop rule is
  checked through plan 3 only: {STOP_RULE}. Points 4 to 6 are exempt.
- **A searched row:** the sample reads the draft's records and the winner's together, never a
  variant that did not win.

{summary_row(COLUMNS)}
{summary_row(["---"] * len(COLUMNS))}
"""


# ---- pure functions (--self-check runs these) ----


def bucket_of(size: int) -> str:
    return next(name for low, high, name in BUCKETS if low <= size < high)


def outcome_of(records: list[dict]) -> str:
    """A row's cell records to one outcome. `near` reads the raw score, never a masked one."""
    if any(record["exact"] for record in records):
        return "exact"
    scores = [record["score"] for record in records if record["compiled"]]
    if not scores:
        return "compile-failed"
    return "near" if max(scores) >= NEAR else "compiled"


def draft_outcome(text: str, records: list[dict]) -> str:
    """A draft's outcome. No C stands for a hole, so a draft holding one can never be exact, and
    counting it as `compiled` would flatter the plan: its records decide nothing."""
    return "hole-draft" if HOLE_MARK in text else outcome_of(records)


def searched_outcome(draft: list[dict], winner: list[dict]) -> str:
    """A searched row counts what the tools hand over, the draft and the winner together. Read
    alone, a winner ranked on the stack score could drop a draft out of `near`, and D-27 would
    count that side effect of the ranking as movement."""
    return outcome_of([*draft, *winner])


def _matched_line(rows: list[dict]) -> str:
    """Matched rows as exact, compiled (near included) and refused, plus any other outcome."""
    counts = Counter(row["outcome"] for row in rows)
    counts["compiled"] += counts.pop("near", 0)
    shown = [f"{counts.pop(name, 0)} {name}" for name in ("exact", "compiled", "refused")]
    shown += [f"{counts[name]} {name}" for name in OUTCOMES if counts[name]]
    return f"Matched rows ({len(rows)}): {', '.join(shown)}."


def table(rows: list[dict]) -> str:
    """Outcome by bucket with totals for not-matched rows, then the matched rows' own line."""
    names = [name for _, _, name in BUCKETS]
    waiting = [row for row in rows if not row["matched"]]
    counts = Counter((row["outcome"], row["bucket"]) for row in waiting)
    sizes = Counter(row["bucket"] for row in waiting)
    lines = [summary_row(["outcome", *names, "all"]), summary_row(["---"] * (len(names) + 2))]
    for outcome in OUTCOMES:
        cells = [counts[outcome, name] for name in names]
        lines.append(summary_row([outcome, *cells, sum(cells)]))
    lines.append(summary_row(["rows", *(sizes[name] for name in names), len(waiting)]))
    matched = [row for row in rows if row["matched"]]
    if matched:
        lines += ["", _matched_line(matched)]
    return "\n".join(lines)


def moved(previous: dict, current: dict) -> bool:
    """D-27: a change in `exact` or `near` on either number, in either direction."""
    return any(previous[name] != current[name] for name in NUMBERS)


def changes(previous: dict, current: dict) -> list[str]:
    """Each of the four numbers that changed, with its sign. It reports and counts nothing."""
    return [
        f"{name} {current[name] - previous[name]:+d}"
        for name in NUMBERS
        if current[name] != previous[name]
    ]


def next_streak(point: int, streak: int, is_moved: bool) -> int:
    """A moved point resets the streak, a flat one adds 1, and an exempt one leaves it alone."""
    if is_moved:
        return 0
    return streak if point > LAST_CHECKED else streak + 1


def stop_line(point: int, flat_streak: int) -> str:
    """The summary row's last cell."""
    if point == 0:
        return "base"
    if point > LAST_CHECKED:
        return "exempt (D-27)"
    return "STOP" if flat_streak >= STOP_STREAK else STOP_RULE


def summary_rows(text: str) -> dict[int, dict[str, str]]:
    """The summary table of a curve file: point -> {column: cell}."""
    lines = text.splitlines()
    body = lines[lines.index(summary_row(COLUMNS)) + 2 :]
    found = {}
    for line in itertools.takewhile(lambda ln: ln.startswith("|"), body):
        cells = dict(zip(COLUMNS, (c.strip() for c in line.strip("|").split("|")), strict=True))
        found[int(cells["point"])] = cells
    return found


def with_row(text: str, row: str) -> str:
    """`text` with `row` as the summary table's last line."""
    lines = text.split("\n")
    top = lines.index(summary_row(COLUMNS)) + 2
    held = sum(1 for _ in itertools.takewhile(lambda ln: ln.startswith("|"), lines[top:]))
    lines.insert(top + held, row)
    return "\n".join(lines)


def draw(rows: list[dict]) -> list[dict]:
    """The sample: PER_BUCKET rows per bucket from 64 B up. `rows` come sorted, in row_key order."""
    rng = random.Random(SEED)
    picked = []
    for _, _, name in SAMPLED:
        pool = [r for r in rows if r["bucket"] == name and not r["matched"] and not r["held"]]
        picked += rng.sample(pool, min(PER_BUCKET, len(pool)))
    return picked


# ---- one point ----


def _tier_row(member, exe, statuses: dict, held: frozenset) -> dict:
    row = batch.row_at(exe, member.address)
    key = (member.exe, member.address)
    return {
        "exe": member.exe,
        "address": f"0x{member.address:08X}",
        "unit": row.unit,
        "size": row.end - row.start,
        "bucket": bucket_of(row.end - row.start),
        "matched": statuses.get(key) == "matched",
        "held": key in held,
        "row": row,
    }


def tier_rows(exes: dict) -> list[dict]:
    """Every Tier 1 member in row_key order. The order is fixed: `sigs` is order-sensitive."""
    mech, members = mechanics.read_committed(DEFAULT_CONFIG)
    statuses = mechanics.read_statuses(DEFAULT_CONFIG, mechanics.EXES)
    held = mechanics.signed_held(DEFAULT_CONFIG, mech)
    ids = mechanics._tier_ids(mech, TIER)
    tier = [
        m for m in members if m.role == mechanics.ROLE_MEMBER and ids.intersection(m.member_items)
    ]
    tier.sort(key=mechanics.row_key)
    return [_tier_row(m, exes[m.exe], statuses, held) for m in tier]


def sample_keys(rows: list[dict]) -> list[tuple[str, str]]:
    """The fixed sample's (exe, address) keys, drawing the file only when it is absent."""
    if not SAMPLE.is_file():
        with SAMPLE.open("w", newline="", encoding="ascii") as fh:
            writer = csv.DictWriter(fh, fieldnames=SAMPLE_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows({name: row[name] for name in SAMPLE_FIELDS} for row in draw(rows))
    with SAMPLE.open(newline="", encoding="ascii") as fh:
        return [(row["exe"], row["address"]) for row in csv.DictReader(fh)]


def lifted(row: dict, exe, sigs: dict, **options) -> str | None:
    """The row's C, or None with its outcome and reason set."""
    try:
        return Lifter(exe, row["row"], sigs, **options).lift()
    except Unliftable as exc:
        row.update(outcome="refused", reason=str(exc))
    except Exception as exc:  # a crash is an outcome of this measurement, not an error
        row.update(outcome="crash", reason=f"{type(exc).__name__}: {exc}")
    return None


def lift_into(row: dict, exe, sigs: dict, src: Path) -> None:
    """Write the row's C, or set its outcome and reason. Every row is counted, never dropped. A
    refused row is retried with holes on a copy of `sigs`, so a later row's strict lift reads what
    it would have read without the retry, and its strict reason stays in `reason`: the retry must
    not lower a first-refusal count."""
    text = lifted(row, exe, sigs)
    if text is None and row["outcome"] == "refused":
        text = lifted(row, exe, dict(sigs), holes=True)
    if text is None:
        return
    row["draft"] = text
    path = src / row["exe"] / f"f_{row['row'].start:08x}.c"
    path.write_text(text, encoding="ascii", newline="\n")


def run_batch(src: Path, out: Path) -> dict[tuple[str, str], list[dict]]:
    """`reverseapoc batch` over `src`: (exe, address) -> its cell records."""
    args = ["batch", str(src), "--cell", CELL, "--workers", WORKERS, "--out", str(out)]
    code = cli.main(args)
    if code != 0:
        raise SystemExit(f"measure_curve: reverseapoc batch exited {code}")
    found: dict[tuple[str, str], list[dict]] = {}
    for line in out.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        found.setdefault((record["exe"], record["address"]), []).append(record)
    return found


def search_sample(sample: list[dict], records: dict, exes: dict, src: Path) -> None:
    """Replace the outcome of each sample row with a compiled draft that is not exact. `refused`,
    `crash` and `compile-failed` rows have no object to search and keep theirs. `sample` holds
    its own row dicts, so the Tier 1 rows stay converter-only."""
    rules = load_cflags()
    for row in sample:
        if row["outcome"] not in SEARCHED:
            continue
        path = src / row["exe"] / f"f_{row['row'].start:08x}.c"
        text = path.read_text(encoding="ascii")
        result = search.run_search(exes[row["exe"]], row["row"], text, rules,
                                   watcom_dir=DEFAULT_INSTALL)  # fmt: skip
        draft = records[row["exe"], row["address"]]
        row["outcome"] = searched_outcome(draft, list(result.records))


def _waiting_count(rows: list[dict], outcome: str) -> int:
    return sum(1 for row in rows if not row["matched"] and row["outcome"] == outcome)


def numbers(tier: list[dict], sample: list[dict]) -> dict[str, int]:
    return {
        "t1 exact": _waiting_count(tier, "exact"),
        "t1 near": _waiting_count(tier, "near"),
        "s exact": _waiting_count(sample, "exact"),
        "s near": _waiting_count(sample, "near"),
    }


def row_labels(row: dict, records: dict) -> tuple[str, str]:
    """A row's class and route, read from its best cell. A row with no record has no draft: a
    refused row is the converter's to widen, and a crash falls to the table's last line, an
    agent."""
    cells = records.get((row["exe"], row["address"]))
    if cells is None:
        return NO_CLASS, "converter" if row["outcome"] == "refused" else "agent"
    best = classify.best_cell(cells)
    return best.get("class", NO_CLASS), best["route"]


def route_table(rows: list[dict], records: dict) -> str:
    """Not-matched rows by class and route, each row once. It moves neither curve number."""
    counts = Counter(row_labels(row, records) for row in rows if not row["matched"])
    classes = (*classify.CLASSES, NO_CLASS)
    lines = [
        summary_row(["class", *classify.ROUTES, "all"]),
        summary_row(["---"] * (len(classify.ROUTES) + 2)),
    ]
    for klass in classes:
        cells = [counts[klass, route] for route in classify.ROUTES]
        lines.append(summary_row([klass, *cells, sum(cells)]))
    totals = [sum(counts[klass, route] for klass in classes) for route in classify.ROUTES]
    lines.append(summary_row(["rows", *totals, sum(totals)]))
    return "\n".join(lines)


def reasons_table(rows: list[dict]) -> str:
    """Why the lifter gave up on not-matched rows, most common first."""
    counts = Counter(row["reason"] for row in rows if not row["matched"] and "reason" in row)
    lines = [summary_row(["reason", "rows"]), summary_row(["---", "---"])]
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return "\n".join(lines + [summary_row(item) for item in ordered])


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def head() -> str:
    args = ["git", "rev-parse", "HEAD"]
    return subprocess.run(
        args, cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def point_row(point: int, previous: dict | None, current: dict) -> tuple[list, str]:
    """The point's summary row and the stop-rule cell. Read after the lift: the lifter reads the
    result-used caches, and rebuilds one that is absent."""
    is_moved = previous is not None and moved(previous, current)
    streak = 0
    if previous is not None:
        streak = next_streak(point, int(previous["flat streak"]), is_moved)
    stop = stop_line(point, streak)
    used = " ".join(
        f"{stem} {sha256_of(CACHE_DIR / f'result-used-{stem}.json')}" for stem in mechanics.EXES
    )
    moved_cell = f"yes {', '.join(changes(previous, current))}" if is_moved else "no"
    plan = f"07.1-{point:02d}" if point else "none"
    cells = [
        point,
        plan,
        head(),
        sha256_of(CFLAGS),
        used,
        ", ".join(TOOLS),
        *(current[name] for name in NUMBERS),
        moved_cell,
        streak,
        stop,
    ]
    return cells, stop


def point_section(point: int, tier: list[dict], sample: list[dict], records: dict) -> str:
    return "\n\n".join(
        [
            f"## Point {point}",
            f"Tier 1, {len(tier)} members, converter only:",
            table(tier),
            f"Sample, {len(sample)} rows, tools: {', '.join(TOOLS)}:",
            table(sample),
            HOLE_NOTE,
            "Not-matched Tier 1 rows by class and route:",
            route_table(tier, records),
            "Refusal reasons over the not-matched Tier 1 rows:",
            reasons_table(tier),
        ]
    )


def previous_numbers(row: dict[str, str]) -> dict:
    """A summary row with its four numbers as integers: comparison survives a clean build/."""
    return {**row, **{name: int(row[name]) for name in NUMBERS}}


def measure(point: int) -> int:
    text = CURVE.read_text(encoding="ascii") if CURVE.is_file() else HEADER
    known = summary_rows(text)
    if point in known:
        raise SystemExit(f"measure_curve: point {point} is already in {CURVE.name}")
    if point and point - 1 not in known:
        raise SystemExit(f"measure_curve: point {point - 1} is not in {CURVE.name}")
    exes = {stem: batch.load_exe_inputs(stem) for stem in mechanics.EXES}
    tier = tier_rows(exes)
    keys = sample_keys(tier)
    root = BUILD / str(point)
    if root.exists():
        shutil.rmtree(root)  # a row refused this run must not keep an older run's C
    src = root / "src"
    sigs = {stem: {} for stem in exes}
    for stem, exe in exes.items():
        (src / stem).mkdir(parents=True)
        result_used(exe)  # a rebuilt census ends before any row lifts
    for row in tier:
        lift_into(row, exes[row["exe"]], sigs[row["exe"]], src)
    records = run_batch(src, root / "results.jsonl")
    for row in tier:
        if "draft" in row:
            row["outcome"] = draft_outcome(row.pop("draft"), records[row["exe"], row["address"]])
    by_key = {(row["exe"], row["address"]): row for row in tier}
    sample = [{**by_key[key], "matched": False} for key in keys]  # rows stay fixed: D-27
    search_sample(sample, records, exes, src)
    current = numbers(tier, sample)
    previous = previous_numbers(known[point - 1]) if point else None
    cells, stop = point_row(point, previous, current)
    section = point_section(point, tier, sample, records)
    updated = with_row(text, summary_row(cells)).rstrip("\n")
    CURVE.write_text(f"{updated}\n\n{section}\n", encoding="ascii", newline="\n")
    print(section)
    print(f"point {point}: {current}, stop rule: {stop}")
    return 0


# ---- self-check ----


def _record(score: float, *, compiled: bool = True, exact: bool = False) -> dict:
    return {"score": score, "compiled": compiled, "exact": exact, "stack_score": 100.0}


def _canned_rows() -> list[dict]:
    """Enough rows of each bucket for draw, with one matched and one held row per size."""
    rows = []
    for index in range(240):
        size = (16, 100, 500, 2000)[index % 4]
        rows.append(
            {
                "exe": "ufo2p",
                "address": f"0x{index:08X}",
                "size": size,
                "bucket": bucket_of(size),
                "matched": index < 4,
                "held": 4 <= index < 8,
            }
        )
    return rows


def _canned_table() -> str:
    rows = [
        {"bucket": "<64", "outcome": "exact", "matched": False},
        {"bucket": ">=1024", "outcome": "crash", "matched": False},
        {"bucket": "64-255", "outcome": "exact", "matched": True},
        {"bucket": "64-255", "outcome": "near", "matched": True},
        {"bucket": "256-1023", "outcome": "hole-draft", "matched": False},
    ]
    return table(rows)


def _labelled(score: float, route: str, klass: str | None = None, *, exact: bool = False) -> dict:
    labels = {"route": route} if klass is None else {"route": route, "class": klass}
    return {**_record(score, exact=exact), **labels}


def _route_row(outcome: str, index: int = 0, *, matched: bool = False) -> dict:
    return {"exe": "ufo2p", "address": f"0x{index:08X}", "outcome": outcome, "matched": matched}


def _canned_routes() -> str:
    """Eight not-matched rows and a matched one. Row 3's two cells disagree, and its best cell
    says register and converter; row 5 is a hole draft whose record says agent."""
    cells = {
        1: [_labelled(100.0, "converter", exact=True)],
        2: [_labelled(40.0, "search", "slot")],
        3: [_labelled(50.0, "agent", "size"), _labelled(93.0, "converter", "register")],
        4: [_labelled(30.0, "agent", "size")],
        5: [_labelled(70.0, "agent", "size")],
        6: [_labelled(0.0, "agent")],
        9: [_labelled(100.0, "converter", exact=True)],
    }
    outcomes = {1: "exact", 2: "compiled", 3: "near", 4: "compiled", 5: "hole-draft",
                6: "compile-failed", 7: "refused", 8: "crash"}  # fmt: skip
    rows = [_route_row(outcome, index) for index, outcome in outcomes.items()]
    rows.append(_route_row("exact", 9, matched=True))
    records = {("ufo2p", f"0x{index:08X}"): value for index, value in cells.items()}
    return route_table(rows, records)


def _point_numbers(t1_exact: int, t1_near: int, s_exact: int, s_near: int) -> dict[str, int]:
    return dict(zip(NUMBERS, (t1_exact, t1_near, s_exact, s_near), strict=True))


def _stop_row(point: int) -> str:
    return summary_row([point, *["x"] * (len(COLUMNS) - 2), stop_line(point, 2)])


def _round_trip() -> list[str]:
    cells = [1, *["x"] * (len(COLUMNS) - 1)]
    text = with_row(with_row(HEADER, summary_row([0, *cells[1:]])), summary_row(cells))
    text += "\n## Point 0\n\n| exact | 1 | 2 | 3 | 4 | 10 |\n"
    return [str(point) for point in summary_rows(text)]


def cases() -> list[tuple[str, object, object]]:
    """(name, got, expected) per check."""
    base = _point_numbers(16, 4, 3, 2)
    fall = _point_numbers(16, 4, 3, 0)
    rise = _point_numbers(17, 4, 3, 2)
    picked = draw(_canned_rows())
    canned = _canned_table().split("\n")
    holed = f"{HOLE_MARK}0x1000: op: movsd */"
    strict = {"matched": False, "outcome": "hole-draft", "reason": "op: movsd"}
    routes = _canned_routes().split("\n")
    exact_row = _route_row("exact")
    refused = _route_row("refused")
    cells = {(exact_row["exe"], exact_row["address"]): [_labelled(100.0, "converter", exact=True)]}
    return [
        ("exact when any cell is", outcome_of([_record(10.0), _record(100, exact=True)]), "exact"),
        ("near at the threshold", outcome_of([_record(NEAR), _record(10.0)]), "near"),
        ("compiled under it", outcome_of([_record(89.9)]), "compiled"),
        ("a masked score decides nothing", outcome_of([_record(50.0)]), "compiled"),
        ("no object", outcome_of([_record(0.0, compiled=False)]), "compile-failed"),
        (
            "a failed cell does not hide a near one",
            outcome_of([_record(0.0, compiled=False), _record(91.0)]),
            "near",
        ),
        (
            "a draft at raw 91 and a winner at raw 88 stay near",
            searched_outcome([_record(91.0)], [_record(88.0)]),
            "near",
        ),
        (
            "an exact winner makes the row exact",
            searched_outcome([_record(50.0)], [_record(100.0, exact=True)]),
            "exact",
        ),
        ("a near winner lifts a draft", searched_outcome([_record(50.0)], [_record(92.0)]), "near"),
        (
            "a winner under NEAR adds nothing",
            searched_outcome([_record(50.0)], [_record(60.0)]),
            "compiled",
        ),
        ("only a compiled draft is searched", SEARCHED, ("near", "compiled")),
        ("the tools named are all four", TOOLS, ("converter", "search", "slots", "classify")),
        ("table counts an outcome by bucket", canned[2], "| exact | 1 | 0 | 0 | 0 | 1 |"),
        ("table totals its rows", canned[9], "| rows | 1 | 0 | 1 | 1 | 3 |"),
        ("hole-draft has its own row", canned[6], "| hole-draft | 0 | 0 | 1 | 0 | 1 |"),
        (
            "a hole draft is never exact, whatever its record says",
            draft_outcome(holed, [_record(100.0, exact=True)]),
            "hole-draft",
        ),
        ("a hole draft is never compiled", draft_outcome(holed, [_record(50.0)]), "hole-draft"),
        ("a hole draft is never near", draft_outcome(holed, [_record(95.0)]), "hole-draft"),
        ("a draft with no hole is judged", draft_outcome("int f;", [_record(95.0)]), "near"),
        ("a hole draft is never searched", "hole-draft" in SEARCHED, False),
        (
            "a hole draft's strict reason still counts",
            reasons_table([strict]).split("\n")[2],
            "| op: movsd | 1 |",
        ),
        (
            "matched rows have their own line",
            canned[-1],
            "Matched rows (2): 1 exact, 1 compiled, 0 refused.",
        ),
        ("equal numbers did not move", moved(base, dict(base)), False),
        ("a fall in s near alone moved", moved(base, fall), True),
        ("changes shows the minus sign", changes(base, fall), ["s near -2"]),
        ("changes shows the plus sign", changes(base, rise), ["t1 exact +1"]),
        ("flat adds one", next_streak(1, 0, False), 1),
        ("moved resets", next_streak(2, 1, True), 0),
        ("exempt does not grow", next_streak(4, 1, False), 1),
        ("point 0 is the base", stop_line(0, 0), "base"),
        ("point 1 names the rule", stop_line(1, 1), STOP_RULE),
        ("a streak of 1 does not stop", stop_line(2, 1), STOP_RULE),
        ("point 2 stops", stop_line(2, 2), "STOP"),
        ("point 3 stops", stop_line(3, 2), "STOP"),
        ("point 4 is exempt", stop_line(4, 2), "exempt (D-27)"),
        ("point 6 is exempt", stop_line(6, 5), "exempt (D-27)"),
        ("cells are written as given", summary_row(["a", "b"]), "| a | b |"),
        ("point 2 row starts", _stop_row(2).startswith("| 2 |"), True),
        ("point 2 row ends", _stop_row(2).endswith("| STOP |"), True),
        ("point 3 row starts", _stop_row(3).startswith("| 3 |"), True),
        ("point 3 row ends", _stop_row(3).endswith("| STOP |"), True),
        ("the summary reads back, section tables apart", _round_trip(), ["0", "1"]),
        (
            "the sample holds 40 rows per bucket",
            Counter(row["bucket"] for row in picked),
            Counter({"64-255": 40, "256-1023": 40, ">=1024": 40}),
        ),
        (
            "the sample leaves out matched and held rows",
            any(row["matched"] or row["held"] for row in picked),
            False,
        ),
        ("the sample is the same every time", draw(_canned_rows()), picked),
        ("a class counts by route", routes[2], "| tail | 0 | 0 | 0 | 0 |"),
        ("slot goes to the search", routes[3], "| slot | 0 | 1 | 0 | 1 |"),
        ("size goes to an agent", routes[4], "| size | 0 | 0 | 2 | 2 |"),
        ("a row counts once, by its best cell", routes[5], "| register | 1 | 0 | 0 | 1 |"),
        ("rows with no class count too", routes[8], "| none | 2 | 0 | 2 | 4 |"),
        ("the totals are the not-matched rows", routes[9], "| rows | 3 | 1 | 4 | 8 |"),
        ("an exact row is the converter's", row_labels(exact_row, cells), ("none", "converter")),
        ("a refused row is the converter's", row_labels(refused, {}), ("none", "converter")),
        ("a crash has no record", row_labels(_route_row("crash"), {}), ("none", "agent")),
    ]


def self_check(plant: bool) -> int:
    checks = cases()
    if plant:
        name, got, _expected = checks[0]
        checks[0] = (name, got, "planted")
    failed = [(name, got, want) for name, got, want in checks if got != want]
    for name, got, want in failed:
        print(f"FAIL {name}: got {got!r}, expected {want!r}")
    print(f"{len(failed)} FAILED" if failed else "ALL PASS")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 7.1 measurement gate")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--point", type=int, choices=range(8), help="the curve point to measure")
    mode.add_argument("--self-check", action="store_true", help="run the pure functions")
    parser.add_argument("--plant", action="store_true", help="flip one self-check expectation")
    args = parser.parse_args()
    return self_check(args.plant) if args.self_check else measure(args.point)


if __name__ == "__main__":
    sys.exit(main())
