---
title: Do not propose a merge for a jump into another function's shared epilogue
created: 2026-11-19
area: functions
files: tools/reverseapoc/splits.py, tests/test_splits.py
source: splits batch 2 merge review (2026-11-19)
---

# Shared epilogues read as merges

**Why.** The 2026-11-19 merge review ruled 16 of 22 `mechanics interior` merge fixes SKIP. Most were
one Watcom pattern: a function jumps (jmp or jcc) into the shared `ret` or the matching
`pop ...; ret` epilogue of the function before it, or an `if (flag) return;` jumps to a bare `ret`
elsewhere. Examples: ufo2p 0x28E20..0x29830 and tacp 0x34450..0x34DD0 (shared `pop edx; pop ecx;
pop ebx; ret`), ufo2p 0x4A9D0..0x4AB10 (bare `ret` at 0x4AA86), ufo2p 0xAEAB0 and 0xAF700.

**Do.** Test first: a jump whose target is an epilogue (a run of pops ending in `ret`, or a bare
`ret`) in another row proposes no merge; keep it as a suspect with a `shared-epilogue` note, or
skip it like content rows.

**Done when.** The real-file run no longer proposes those merges and still proposes the 6 real ones
(ufo2p 0x24470, 0x7DD64; tacp 0x1F2B0 chain, 0x24B30, 0x38360 chain, 0x43C00) until batch 2 lands.
