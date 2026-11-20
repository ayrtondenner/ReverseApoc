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
