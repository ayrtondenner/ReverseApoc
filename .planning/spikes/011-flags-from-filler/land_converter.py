# SPDX-License-Identifier: GPL-3.0-or-later
"""Put converter matches into their committed units (src/<exe>/<unit>.c), ready for `gate`.

    uv run python .planning/spikes/011-flags-from-filler/land_converter.py [--dry-run]

For each CANDIDATE: lift the row with its choice points, scaffold the unit file if the committed
tree has none (as `reverseapoc units --write-src` does), and replace the row's
`INCLUDE_ASM(func_X);` with the C. A name the unit already declares keeps the unit's
declaration: our extern line is dropped and our uses become `((char *)&name)`, the same address,
so the code does not change. Each edited unit is then compiled with its committed rule and
judged by the spike 010 harness; a unit whose candidate is not exact is restored. Prints what
stayed. `gate` (in the container) is the real verdict and the only writer of status.csv.
"""

from __future__ import annotations

import argparse
import re
import sys

import s011  # noqa: F401  (puts spike 010 on sys.path)
from common import REPO_ROOT, Job, compile_all, exe_inputs, judge, rule_for
from lift import Lifter

from reverseapoc.unitdefs import file_scope_names
from reverseapoc.units import scaffold_unit

VOID = {"force_ret": "void", "once": True}
# Exact under the committed rule: spike 011 all_tier1.py (committed / committed+void arms) and
# spike 010 Q5 (views 3-5, passed the real check in the container).
CANDIDATES = (
    ("ufo2p", 0x0002F720, VOID),
    # 0x000520A0, 0x000520C0 and 0x000520E0 are each exact alone in u_00052080, but next to a
    # sibling with the same tail (including the unit's matched func_00052080) Watcom merges the
    # tails (13 bytes and a jmp; gate refused the regression). The original did not compile
    # them together: they wait for a unit recut.
    ("ufo2p", 0x0006F800, {}),
    ("ufo2p", 0x000B5FB0, {}),
    ("tacp", 0x000456D0, {}),
    ("tacp", 0x000A6000, VOID),
    ("tacp", 0x000A6080, VOID),
)
_EXTERN = re.compile(r"^(?:extern\s+)?[A-Za-z_][\w\s\*]*?\b([A-Za-z_]\w*)\s*(?:\[\]|\([^;]*\))?;$")


def merge(unit_text: str, c: str) -> str:
    """The converter's C with every declaration the unit already makes dropped and its uses
    taken through the unit's declaration (`(char *)&name`)."""
    known = file_scope_names(unit_text)
    lines, reuse = [], set()
    for line in c.splitlines():
        m = _EXTERN.match(line.strip())
        if m and m.group(1) in known:
            reuse.add(m.group(1))
            continue
        lines.append(line)
    body = "\n".join(lines)
    for name in reuse:
        if name.startswith("D_") or not body.count(f"{name}("):
            body = re.sub(rf"\b{re.escape(name)}\b(?!\s*\()", f"((char *)&{name})", body)
    # The unit may declare a reused name only after the marker: repeat its own declaration (a
    # repeated identical extern is valid C89) in front of our function.
    repeats = [m.group(0) for name in sorted(reuse) for m in re.finditer(
        rf"^extern\b[^;{{}}]*\b{re.escape(name)}\b[^;{{}}]*;$", unit_text, re.M)][:len(reuse) * 2]
    return "\n".join([*dict.fromkeys(repeats), body.strip()]) + "\n"


def matched_starts(stem: str, unit: str) -> list[int]:
    """The starts status.csv marks matched in `unit`."""
    path = REPO_ROOT / "config" / stem / "status.csv"
    rows = [line.split(",") for line in path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith(("#", "start,"))]
    return [int(r[0], 16) for r in rows if r[2] == unit and r[3] == "matched"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    edits: dict = {}  # unit path -> original text (None: scaffolded)
    landed = []
    for stem, start, opts in CANDIDATES:
        exe = exe_inputs(stem)
        row = next(r for r in exe.rows if r.start == start)
        path = REPO_ROOT / "src" / stem / f"{row.unit}.c"
        if path not in edits:
            edits[path] = path.read_text(encoding="utf-8") if path.is_file() else None
        text = path.read_text(encoding="utf-8") if path.is_file() else scaffold_unit(
            exe.target.name, next(u for u in exe.units if u.unit == row.unit), exe.rows)
        marker = re.compile(rf"^INCLUDE_ASM\({re.escape(row.name)}\);$", re.M)
        if not marker.search(text):
            print(f"SKIP {stem} {row.name}: no INCLUDE_ASM marker in {path.name}")
            continue
        c = merge(text, Lifter(exe, row, {}, **opts).lift())
        path.write_text(marker.sub(f"\n{c}".replace("\\", "\\\\"), text, count=1),
                        encoding="utf-8", newline="\n")
        landed.append((stem, start, row, path))
    jobs = {path: Job(path, REPO_ROOT / "build" / "spike-011" / "land" / path.parent.name /
                      f"{path.stem}.obj", rule_for(path.parent.name, path.stem))
            for path in {p for *_, p in landed}}
    done, _ = compile_all(list(jobs.values()), 8)
    ok_units = {c.job.src for c in done if c.ok}
    bad_units = set()
    for stem, start, row, path in landed:
        ok = path in ok_units and judge(stem, jobs[path].obj, start).exact
        print(f"{'OK  ' if ok else 'FAIL'} {stem} {row.name} in {path.name}")
        if not ok:
            bad_units.add(path)
    # As gate does: every function the unit already matched must stay exact too (a new
    # function can change a sibling, e.g. by tail merging).
    for path in ok_units - bad_units:
        stem = path.parent.name
        for start in matched_starts(stem, path.stem):
            if not judge(stem, jobs[path].obj, start).exact:
                print(f"FAIL {stem} 0x{start:08X} (already matched) regressed in {path.name}")
                bad_units.add(path)
    for path in bad_units | (set(edits) if args.dry_run else set()):
        original = edits[path]
        if original is None:
            path.unlink()
        else:
            path.write_text(original, encoding="utf-8", newline="\n")
        print(f"restored {path.relative_to(REPO_ROOT).as_posix()}")
    kept = sorted({p.relative_to(REPO_ROOT).as_posix() for p in jobs} - {
        p.relative_to(REPO_ROOT).as_posix() for p in bad_units})
    print("units ready for gate:", " ".join(kept) if not args.dry_run else "(dry run)")
    return 0 if not bad_units else 1


if __name__ == "__main__":
    sys.exit(main())
