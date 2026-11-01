# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 011: compile one C file for one row with the real wcc386 10.6 and judge it like `check`
(spike 010's harness), under the inferred cell and under the committed rule.

    uv run python .planning/spikes/011-flags-from-filler/judge_cli.py <exe> <0xADDR> <file.c>

The file holds the function (named as lift.py names it) and the declarations it needs, C89, no
#pragma, no inline asm. A row whose original ends in filler gets a trailing pad function under a
t-optimisation cell, so Watcom aligns it as in the original (spike 010 iteration 7). Prints one
line per cell: exact, score, length ours/row, first differing instruction shapes. Writes the
object under build/spike-011/judge/. Exit 0 when the inferred cell is exact.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import s011
from common import Job, compile_all, exe_inputs, judge, rule_for

_BANNED = re.compile(r"#\s*pragma|\b_asm\b|\b__asm\b")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", choices=("ufo2p", "tacp"))
    ap.add_argument("address")
    ap.add_argument("file", type=Path)
    args = ap.parse_args()
    start = int(args.address, 16)
    exe = exe_inputs(args.exe)
    row = next(r for r in exe.rows if r.start == start)
    text = args.file.read_text(encoding="ascii")
    if _BANNED.search(text):
        print("refused: #pragma and inline assembly are not allowed")
        return 2
    out = s011.OUT / "judge" / args.exe / f"{start:08x}"
    cells = (
        ("inferred", s011.rule(args.exe, row, True)),
        ("committed", rule_for(args.exe, row.unit)),
    )
    code = 1
    for name, rule_ in cells:
        body = text + (s011.s010_run.PAD if s011.needs_pad(args.exe, row, rule_) else "")
        src = out / f"{name}.c"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(body, encoding="ascii")
        (c,), _ = compile_all([Job(src.resolve(), src.resolve().with_suffix(".obj"), rule_)], 1)
        flags = " ".join(rule_.flags)
        if not c.ok:
            errors = [ln for ln in c.output.splitlines() if "Error" in ln or "Warning" in ln]
            print(f"{name:9} [{flags}] COMPILE FAILED: " + " | ".join(errors[:4]))
            continue
        v = judge(args.exe, c.job.obj, start)
        print(
            f"{name:9} [{flags}] exact={v.exact} score={v.score} len ours/row="
            f"{v.len_ours}/{v.len_row} first diff: {v.key or '-'}"
        )
        if name == "inferred" and v.exact:
            code = 0
    return code


if __name__ == "__main__":
    sys.exit(main())
