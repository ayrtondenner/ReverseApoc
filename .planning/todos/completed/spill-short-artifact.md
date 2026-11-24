---
title: Re-prove the M5 'short beside a short moves with its declaration' claim
created: 2026-11-18
area: search
source: batch 2026-11-18 worker reports
---

# Re-prove the M5 'short beside a short moves with its declaration' claim

U12 (batch 2026-11-18) found that pr_spill_short and pr_spill_short_rev differ only in trailing alignment filler because pr_spill_short_rev is the probe's last function. Appending frames after it made both compile identically. search._readable's refusal built on M5 is on the safe side, but the claim is unproven: add frames that test it away from the file's end.

## Result (2026-11-24): the claim is refuted

- Measured in the Watcom container (wcc386 10.6, both cells `-4r -s -fpi` and `-4r -oneatx -s -fpi`).
  A scratch file (gitignored build/) compiled the pair with and without a frame after it: as the
  last function, `pr_spill_short_rev` differs under `-oneatx` only by the trailing filler
  (`lea eax, [eax]; lea edx, [edx]; nop` past the `ret`) and the instructions before it are
  equal; with any function after it, the twins compile identically in both cells. Three more
  declaration-only twins away from the end gave identical code in both cells too: shorts in the
  other declaration order, all-short frames and all-char-beside-int frames.
- Landed: probe/cg_slots.c gains `pr_spill_char`/`_rev`, `pr_spill_shorts`/`_rev` and
  `pr_last_guard`, kept last so no measured function carries the object's filler.
  tests/test_slots_real.py drops `test_a_short_beside_a_short_moves_with_its_declaration` and
  puts the three pairs in SAME_CODE (test first: the `pr_spill_short` pair failed under
  `-oneatx` before the guard, and passes after; the file is 392 passed in the container).
  probe/README.md, docs/matching.md and the docstrings of slots.py, search._readable and
  tests/test_search.py no longer state the exception.
- Not changed: `search._readable` still refuses a frame with a plain local under 4 bytes that
  is not in `memory`. It now rests on no measurement, only the safe side (some compiles spent
  on moves that do nothing). Lifting it is an owner ruling: keep the refusal, or let the scalar
  skip and the "cannot reach" line run for such frames (a behaviour change of the search, with
  its own test-first change of tests/test_search.py
  `test_declaration_axis_falls_back_beside_a_plain_small_local`).
