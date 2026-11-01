# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 010 side probe: how many not-matched Tier 1 must-match rows end in Watcom filler, per
size bucket and per kind of cflags rule. Under the `*` default (no -o option) Watcom 10.6 puts no
filler between two functions of one object (measured: four kinds of next function on tacp
0x000A68B0), so such a row most likely ends an original object, and `check`'s length rule (row
length, filler included) refuses any C for it until the row or the unit is recut.

    uv run python .planning/spikes/010-deterministic-matching/filler_census.py
"""

from __future__ import annotations

from collections import Counter

from common import CONFIG, bucket_of, exe_inputs, rule_for

from reverseapoc import mechanics
from reverseapoc.x86 import decode, is_filler

_SELF = ("mov", "lea")


def ends_in_filler(exe, row) -> bool:
    insns = list(decode(exe.flat[row.start : row.end], row.start))
    if not insns:
        return False
    last = insns[-1]
    ops = last.op_str.replace("dword ptr ", "").split(", ")
    self_move = last.mnemonic in _SELF and len(ops) == 2 and ops[1].strip("[]") == ops[0]
    return is_filler(last) or last.mnemonic == "nop" or self_move


def main() -> None:
    mech, members = mechanics.read_committed(CONFIG)
    statuses = mechanics.read_statuses(CONFIG, ("ufo2p", "tacp"))
    ids = mechanics._tier_ids(mech, 1)
    counts: Counter = Counter()
    for m in members:
        if m.role != mechanics.ROLE_MEMBER or not ids.intersection(m.member_items):
            continue
        if statuses.get((m.exe, m.address)) == "matched":
            continue
        exe = exe_inputs(m.exe)
        row = next(r for r in exe.rows if r.start == m.address)
        opt = any(f.startswith("-o") for f in rule_for(m.exe, row.unit).flags)
        b = bucket_of(row.end - row.start)
        counts[b, "all"] += 1
        if ends_in_filler(exe, row):
            counts[b, "filler, -o rule" if opt else "filler, default rule"] += 1
    for b in ("<64", "64-255", "256-1023", ">=1024"):
        print(
            f"{b:9} not matched {counts[b, 'all']:4}  ending in filler: default rule "
            f"{counts[b, 'filler, default rule']:4}, -o rule {counts[b, 'filler, -o rule']:3}"
        )


if __name__ == "__main__":
    main()
