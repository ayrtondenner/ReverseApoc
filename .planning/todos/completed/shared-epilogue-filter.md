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

## Resolution (2026-11-20)

- `splits.interior_branches`: a jump that would propose `merge` but lands where the target row
  decodes zero or more `pop` and then `ret` is a suspect with fix word `shared-epilogue`, and it
  proposes no fix. An `add esp, N` before the pops is not an epilogue under this rule: real switch
  case bodies jump to their parent's `add esp, N; pop ...; ret` (ufo2p 0x25398, tacp 0x385FC). Calls
  and tail-jump stubs (splits) are unchanged.
- Tests (tests/test_splits.py): the interior fixture gains rows K, E, F. F's je to E's
  `pop; pop; ret` and its jne to E's bare `ret` are `shared-epilogue`. K's jumps to `add esp; pop;
  pop; ret` and to `pop; xor; ret` stay `merge`. B and H gain a third xor, so B+4 and H+4 are no
  longer a bare `ret`. Updated: test_interior_branch_suspects, test_interior_branch_fixes,
  test_interior_fix_on_a_matched_row_is_review, test_cli_interior_json_and_text, and
  test_real_interior_branches, which pins 5 real `shared-epilogue` suspects and checks that none
  of the 5 named merges is proposed.
- Measured on orig/ (no statuses, so a fix that would be `review` reads `merge`). With the HEAD
  config (after batch 2), merges went from ufo2p 15 to 9 and tacp 5 to 3; 24 suspects are now
  `shared-epilogue`. The ones that went: ufo2p 0x21800 (bare `ret` 0x219CA), 0x28E20, 0x4A9D0,
  0xAEAB0, 0xAF700, 0xB5FD0 (0xB63B8); tacp 0x34450, 0xAFDF0 (0xB01C5). ufo2p 0x50D70 is still
  proposed: only one of its jumps lands on `pop; pop; ret`. Batch 2 already landed the 6 real
  merges, so they no longer appear with HEAD config. With the pre-batch-2 config (the batch-2
  scratchpad snapshot), all 6 are still proposed with the filter on (ufo2p 0x24470, 0x7DD64; tacp
  0x1F2B0, 0x24B30, 0x38360, 0x43C00), and none of their branches is tagged `shared-epilogue`.
