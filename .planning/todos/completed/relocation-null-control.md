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

## Resolution (2026-11-19)

Done in batch 261119-bhi (quick 261119-bhk): RED 20aff621, GREEN 63ce2399. driver.run_controls
runs a third control (attempt-3, `reloc`): the canary unit with `extern signed char D_0012EFAC`
(declaration and use, comments untouched) repointed to `D_001277E5`, the scalar `extern signed
char` the matched src/ufo2p/u_00092250.c reads, not renamed in symbols.csv. It must exit 1 and
its last checks.jsonl line must say bytes_ok true and reloc_ok false; exit 0, bytes failed, reloc
ok or no line refuses the night. STARTED `controls` gains an optional `reloc` exit (records
without it still validate), and `stats --run` appends `, reloc N`.

Evidence (worktree, Watcom 10.6, no orig/): both units compiled with `reverseapoc cc`; `_TEXT`
is 24 bytes in each and byte-identical (fixup fields included), publics identical
(func_000A3980_ at 0xb, 13 bytes, `0f be 05` movsx before the field); the only difference is the
fixup at _TEXT+0x13 (`_D_0012EFAC` -> `_D_001277E5`), and `reverseapoc compare-objects` reports
`differ: _TEXT+0x13: relocation: target differs`. The full attempt check against orig/ (bytes ok,
reloc FAILED) is left to the coordinator in the main checkout.
