---
title: A nightly control that only the relocation check can fail
created: 2026-11-19
area: driver
files: tools/reverseapoc/driver.py, tests/test_driver.py
source: coordinator, after the 2026-11-18/19 drives
---

# The controls never exercise the relocation check

Each session night starts with two controls (`driver.run_controls`, todo
nightly-gold-null-controls): the gold control checks the committed C of ufo2p func_000A3980
and must exit 0; the null control adds one volatile local and must exit 1 below 100%. The null
fails on bytes, size and relocations at once (run 20261118-256's preflight.log: objdiff 0%,
`reloc FAILED`, `bytes FAILED (21 differ)`, 26 B against 13 B), so no control shows that the
relocation check alone catches a wrong target. The byte compare ignores a relocated operand
(watcom-decomp skill: a wrong target there shows in `reloc.problems`, never in the window), so
a checker whose relocation compare broke would still pass both controls.

Do, test first:
- add a third control: the gold unit with one relocation pointed at another symbol of the same
  kind (a different global or callee), so the C compiles to the same bytes and size and only
  the relocation target differs;
- it must exit 1 (MISMATCH) with `bytes ok` and `reloc FAILED`; any other result refuses the
  night, like the other two;
- record its exit beside `gold` and `null` in the STARTED record's `controls` and in the
  `stats` environment line, keeping older records readable.
