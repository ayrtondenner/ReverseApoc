---
title: Flag functions whose code branches into another row
created: 2026-11-18
area: functions
files: tools/reverseapoc/splits.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-agentic-projects.md #4)
---

# Flag functions whose code branches into another row

**Why.** 23 agent notes suspect a bad function boundary (a jump into the next row); such a row cannot match as split.

**Do.** A deterministic check over functions.csv: branches whose targets fall in another row; list them as suspected splits for review.

**Done when.** A report lists suspects; one confirmed fix is landed or the list is shown to be noise.

**Effort / value.** S-M / med-high. Evidence and sources: docs/research/notes-ideas-agentic-projects.md #4.

## Status (2026-11-18)

Status (batch 2026-11-18, U15): `reverseapoc mechanics interior` reports 114 UFO2P / 88 TACP suspects, none on a matched row; the proposed functions.csv splits and merges are listed in the merge report. Left: the owner's rulings on those fixes.

## Status (2026-11-19)

Status (batch 261119-bhi, quick 261119-bhq): the supported fix input landed: `config/<exe>/boundary-fixes.csv` (`action,row,at,ruled_on,evidence`; split or merge), applied by `functions --write` right after reconcile, refusing matched rows (docs/toolchain.md, "Function boundaries"). Both files are header only. All 122 unmatched rows of the current `mechanics interior` split and merge fixes (76 UFO2P, 46 TACP; 14 of them call-split targets) sit on config/handoff.csv with return rule "boundary fixed". Rows only on `review` fixes (a matched row is involved, so no boundary fix will land) stay in the agent queues. Left: the owner's rulings written into boundary-fixes.csv, functions.csv regenerated in the container, and the board rows of each landed fix deleted (a merged-away start is no row start any more, so the drive would refuse its board row).

## Status (2026-11-19, batch 1 landed)

- Splits batch 1 (owner: "Yes, land and re-sign"): the 24 call-split fixes (ufo2p 13, tacp 11) in
  config/<exe>/boundary-fixes.csv, `functions --write` for both EXEs, 14 INCLUDE_ASM markers, the four touched units
  re-gated, cd-map, asm list and tiers 1-3 re-signed (1384736e, 3af7191a, ad55f17a, 3142500d, de90352a, 39afad5f,
  325e2989). tacp 0x000B12E0 at 0x000B13E0 was skipped (a jmp, not a call). Moved pins: asmclass unaligned rows
  213->221 / 216->223; REACH_DIRECT 1128->1133 / 1224->1229; REACH_DIRECT_POINTER 1412->1423 / 1479->1501;
  REACH_DIRECT_POINTER_TABLE 1429->1440 / 1479->1501; CALLINDEX_EDGES 5288->5304 / 4885->4897. Proof: gate --all and
  ninja verify OK (UFO2P e7488bf3... landed 141, TACP 48ef0096... landed 154); host and container suites green
  after the three real-file tests that the splits move were fixed (325e2989). `mechanics interior`: suspects
  202 -> 128, fixes 51 -> 28.
- Merge review: 6 of 22 merge fixes APPLY (ufo2p 0x24470, 0x7DD64; tacp 0x1F2B0 chain from 0x1F270, 0x24B30,
  0x38360 chain from 0x38348, 0x43C00), plus 2 splits surfaced (tacp 0x00038610, ufo2p 0x0002E280); owner ruled
  "Yes, land and re-sign" for batch 2 after the drives. The other 16 were skipped and their 76 board rows returned
  to the queues (owner: "Return them to the queues"): shared-epilogue false positives (ufo2p 0x18577, 0x21800,
  0x28E20, 0x4A9D0, 0x7BB23, 0xAEAB0, 0xAF700; tacp 0x27DB3, 0x34450), callback rows (ufo2p 0x50D70), the
  8-9-row spans (ufo2p 0x51DD0, 0xBBF90, 0xBC220; tacp 0xAFDF0), text noise (ufo2p 0x189C0), and tacp 0x28A13
  (a correct merge held because it crosses units and gains nothing for matching). Evidence:
  the 2026-11-19 merge review (docs/learnings.md, 2026-11-19).
- Left: batch 2; todo shared-epilogue-filter.

## Status (2026-11-20, batch 2 landed, re-signed and proven)

- Splits batch 2 (owner rulings 2026-11-19/20): the 6 APPLY merge chains (ufo2p 0x24470, 0x7DD64; tacp
  0x1F270, 0x24B30, 0x38348, 0x43C00; 25 merge lines) plus the splits tacp 0x000385BB at 0x00038610 and
  ufo2p 0x0002E100 at 0x0002E280 (ret 0x2E279 + filler + aligned prologue, called from 0x2E3A1), in
  config/<exe>/boundary-fixes.csv (108c1ffe). functions --write: only the merged rows and the two new
  rows change; 12 INCLUDE_ASM markers of merged-away rows removed, three units re-gated (splice OK at
  both SHA-1s). Asm list (23 rows removed) and mechanics members (832a0bb5), cd-map (3fc90918), 34
  board rows retired (d1bf4cb0; only tacp 0x000B12E0 stays). `mechanics interior`: suspects 128 -> 80,
  fixes 28 -> 21. Side effect: ufo2p 0x00028AC0 drops from 20 to 19 direct caller rows and is no
  longer a hub, so it becomes a must-match member.
- Done since: the owner re-signed [asm_list] and tiers 1-4 (0b49ec48); todo shared-epilogue-filter
  landed (3febb6e8); the full proof ran on b530130e (host 8,326 passed,
  container 8,362 passed, gate --all and ninja verify OK at both SHA-1s) and CI passed after the push.
- Open: ufo2p 0x0002E100 went back to drive picking in d1bf4cb0, but tests/test_splits.py still pins a
  live interior suspect into it (0x2FAF0 jumps 0x171 bytes in); review it before the next splits
  batch. The 0x2E280 split's ruling is recorded only in the commit messages of 108c1ffe and a896abaa.

## Review (2026-11-24): the 0x0002E100 suspect pinned in tests/test_splits.py

Read-only, at a86b0278: `mechanics interior --exe ufo2p`, `asm UFO2P.EXE` listings and a byte scan
of the code object for fixups and rel8/rel32 call, jmp and jcc targets. No boundary-fixes.csv row
changed.

- The suspect: `ufo2p 0x0002FAF0+0x44C jcc -> 0x0002E100+0x171 ... fix=merge`, and its fix is
  `review` of 33 rows (0x0002E100 to 0x0002FAF0). That merge is wrong.
- The target, 0x0002E271, is the epilogue of 0x0002E100: `add esp, 4; pop edi; pop esi; pop edx;
  pop ecx; pop ebx; ret` (0x2E271 to 0x2E279), the inverse of its prologue `push ebx; push ecx;
  push edx; push esi; push edi; sub esp, 4`.
- The source is not in the function at 0x0002FAF0. That function ends at `ret` 0x2FE02 (its frame
  is `push ebx..ebp; sub esp, 0x4C`), then Watcom filler `lea eax, [eax]; lea edx, [edx]; nop`
  (0x2FE03 to 0x2FE0F), then a 16-aligned prologue at 0x0002FE10 with the same frame as 0x2E100:
  `push ebx; push ecx; push edx; push esi; push edi; sub esp, 4`. The `jne` at 0x2FF3C belongs to
  that second function (0x2FE10 to 0x2FFC0, which loops by `jmp 0x2FF23` and also calls
  0x0002FAF0 at 0x2FF4C).
- Finding, for 0x0002E100: a false positive. The jne is a shared epilogue across functions (the
  tail merge probe/README.md notes for `-4r -s`), so 0x0002E100 needs no split or merge. The
  epilogue filter misses it because the run opens with `add esp, 4` before the pops
  (splits._Facts.epilogue accepts only pops then a ret).
- Finding, for 0x0002FAF0: a real bad split. The row holds two functions; the missed start is
  0x0002FE10. Nothing reaches it: no LE fixup targets 0x2FE10 and no rel call, jmp or jcc in the
  code object does (0x2FAF0 and 0x2E100 have no fixups either; both are reached by rel calls), so
  the capstone pass and Ghidra had no evidence for it. Its row's status is partial (49.07), which
  fits one function's C judged against two.
- Side note: a tail merge into 0x2E100's epilogue means 0x2E100 and 0x2FE10 were most likely
  compiled in one object, while units.csv puts them in u_0002da30 and u_0002faf0.
- Owner rulings needed (none taken here):
  1. land `split,0x0002FAF0,0x0002FE10` (evidence: ret 0x2FE02 + filler + aligned push
     ebx..edi; sub esp 4; no reference) in the next splits batch, or leave the row as it is;
  2. whether `_Facts.epilogue` should also take an `add esp, N` before the pops (it would turn
     this suspect into `shared-epilogue` and change the pin in tests/test_splits.py REAL_INTERIOR
     from `merge`), a test-first tooling change;
  3. whether the u_0002da30/u_0002faf0 unit line is to be reviewed.
