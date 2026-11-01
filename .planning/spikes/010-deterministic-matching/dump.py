# SPDX-License-Identifier: GPL-3.0-or-later
"""Spike 010 local probe: print one row's instructions to the terminal (never to a file), with
fixup targets named as the converter names them. For reading codegen idioms while building the
converter; its output is not committed.

    uv run python .planning/spikes/010-deterministic-matching/dump.py ufo2p 0x000A3980 [obj]

With an object path, also prints our compiled function for the same row.
"""

from __future__ import annotations

import sys
from pathlib import Path

from common import exe_inputs, row_at

from reverseapoc.check import defined_functions, parse_module
from reverseapoc.x86 import decode


def main() -> None:
    stem, start = sys.argv[1], int(sys.argv[2], 16)
    exe = exe_inputs(stem)
    row = row_at(exe, start)
    fix = {f.src_va: f for f in exe.fixups if row.start <= f.src_va < row.end}
    print(f"{row.name} {row.kind} unit={row.unit} size={row.end - row.start}")
    for insn in decode(exe.flat[row.start : row.end], row.start):
        names = []
        for va in range(insn.va, insn.va + insn.size):
            if va in fix:
                t = fix[va].target_va
                names.append(exe.symbols.c_name(t, data=not _is_code(exe, t)))
        call = ""
        if insn.is_call and insn.branch_target is not None:
            call = exe.symbols.c_name(insn.branch_target)
        print(f"  {insn.va:08X}  {insn.mnemonic:7} {insn.op_str:40} {' '.join(names)} {call}")
    if len(sys.argv) > 3:
        obj = Path(sys.argv[3])
        module = parse_module(obj.read_bytes(), obj)
        for d in defined_functions(module, [row], exe.symbols):
            print("ours:")
            for insn in decode(d.ours, row.start):
                print(f"  {insn.va:08X}  {insn.mnemonic:7} {insn.op_str}")


def _is_code(exe, va: int) -> bool:
    return any(r.start <= va < r.end and r.kind != "data-in-code" for r in exe.rows)


if __name__ == "__main__":
    main()
