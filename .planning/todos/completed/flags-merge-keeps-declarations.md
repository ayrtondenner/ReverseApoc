---
title: flags propose's merge drops the hitting C's declarations, so merged candidates do not compile
created: 2026-11-20
area: flags
files: tools/reverseapoc/flags.py, tools/reverseapoc/contextpack.py, tools/reverseapoc/driver.py
source: flag-blocked-rows analysis (2026-11-20)
---

# Merged flags candidates lose their declarations

`flags._merge` puts a later hit's function into the open proposal's candidate with
`contextpack.splice_definition`. That call copies the definition only. The structs, externs and
prototypes the hitting C declared at file scope are dropped. Of the 11 proposals that failed
their re-gate with `compile failed`, 10 merge functions from more than one attempt directory
(F-0005, F-0014, F-0019, F-0020, F-0022, F-0028, F-0029, F-0030, F-0034, F-0040), and their
errors are E1011 (undeclared), E1031 (field not in struct) and E1032/E1033.

Open proposals built the same way: F-0088 (func_00060BD0 has lost six declarations, so its
re-gate is predicted to fail with E1011), F-0013 (four D_ names used with no declaration) and
F-0018 (no undeclared name found). See flag-blocked-rows.md, Update 2026-11-20, finding 3.

Fix (TDD, after the drive):
- Carry over each file-scope declaration of the hitting file that the candidate does not hold
  verbatim. Place it before the spliced definition, so it comes before its first use.
- If the same struct tag, typedef or extern name is declared differently on the two sides, fail
  the proposal with a reason that names both files. F-0020's `unk_00C0` and F-0030's `unk_000A`
  are that case. Do not guess a merge of the two.
- Check whether `driver.py` `--land-held` (the second held function of a unit, line ~6216)
  needs the same fix.
- Decide how existing failed or open proposals get a rebuilt candidate. Today a re-run of
  `flags propose` adds nothing for evidence the queue already holds.

## Resolution (2026-11-20)

- `contextpack.splice_definition` now puts the definition in after the file-scope items of the
  hitting file that it uses, transitively (`_needed`, the same rule twins uses): structs,
  typedefs, externs, prototypes, macros, includes. An item the unit already holds before the
  splice point stays where it is. One the unit holds only further down moves up, so it is
  there once. An item that only declares the spliced function is left to its definition. A
  name the two files declare differently raises `SpliceConflict`. The item parser moved from
  twins.py to contextpack.py (twins imports it; test_twins pins it). Only the items the
  definition uses are carried, not every declaration of the file: the file's other
  definitions are not spliced, so their declarations are not needed and could only add
  conflicts.
- `flags._merge` fails such a proposal with `<hitting checks/NNNN.c> (for <function>) and
  <candidate> declare <names> differently; merge them by hand`. Comparison drops comments and
  collapses blanks; any other difference counts.
- `driver.py` `--land-held` (`_held_text`) had the same defect and goes through the same
  splice. A conflict is a REFUSED landing whose reason names the exact check C and the unit.
- Existing proposals: `uv run reverseapoc flags rebuild <ID>...` (host) makes an open sweep
  proposal again from its evidence, in order, and voids its re-gate. Then
  `flags regate <ID>` in the container. See docs/workflow.md.
- Dry check on the checkout's real evidence (2026-11-20, no compile). F-0086, F-0087, F-0089,
  F-0090 and F-0091 have one hit each, so the rebuilt candidate is byte-identical to the
  queued one. F-0088 gets the six declarations finding 3 named (`D_0017FB4C`, `D_000D9443`,
  `D_000D4CBC`, `func_00060C80`, `func_00010300`, `exit`), before func_00060BD0, and stays
  proposed. F-0013 gets its four D_ externs. Of the compile-failed ones, F-0019, F-0022 and
  F-0028 rebuild to a proposed candidate. F-0018, F-0020, F-0029, F-0030, F-0034 and F-0040
  are refused on a real type difference, F-0014 too (for example F-0030 `unk_000A`, F-0029
  `unk_007E`, F-0018 `char` against `unsigned char D_002A18EC[]`, F-0020 two prototypes of
  func_0004C1D0). F-0005 stays failed with no rule in common.
