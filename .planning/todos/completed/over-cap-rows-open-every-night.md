---
title: The same over-cap rows open every Codex night
created: 2026-11-23
area: driver
files: tools/reverseapoc/driver.py, tools/reverseapoc/attempt.py, docs/workflow.md, tests/test_driver_workers.py, tests/test_attempt_wrapper.py
source: todo limit-burst-at-start measurements (runs 20261120-codex2, 20261121-codex, 20261123-codex)
---

# About 80 skipped picks at each night's start

**Why.** At the start of 20261120-codex2, 78 of the 86 "started" lines (65 terra, 13 luna) were
picks whose pack was over the 24,576-byte cap. Each was "left for tonight" before any session ran.
The same 78-80 over-cap lines open 20261121-codex and 20261123-codex too, because the rows stay at
the head of the queue and come back every night.

**Do.** Measure which rows they are and why their packs pass the cap (function size, context
blocks). Then pick, with the owner, the smallest fix: skip known over-cap rows when the queue is
built, record them once so the next night does not retry them, or route them to an arm with a
larger cap.

**Done when.** A night's start does not re-try rows already known to be over the cap, and a test
pins it.

## Measured (2026-11-24), from the drive log of run 20261124-codex2

80 over-cap lines, 80 distinct rows (47 tacp, 33 ufo2p), 67 on gpt-6.1-terra and 13 on
gpt-6-luna: each row is refused once and then parked on every arm, so the split is only which
arm's worker picked it first. Sizes with every optional section cut: 24,765 to 105,849 bytes,
median 32,642 (1.3 times the cap). What is left at that point is the required sections (the
listing, the unit, the callees, externs, struct shapes, common.h, the idioms, the hint) and the
frame, so these are the large functions, whose listing alone passes the cap. The cap is
`contextpack.PACK_CAP` (24,576), one constant for every arm: backends.toml has no per-arm cap.

## Owner ruling (2026-11-24)

Question: "How should a night stop re-trying rows already known to be over the cap?" Options:
a pre-filter at queue build; remember the verdict; route the rows to an arm with a larger cap.
Chosen: **"Remember the verdict"**. Store "over cap for arm X" per row under build/driver/,
keyed on the pack's inputs (exe, row, arm and a hash of the inputs that decide pack size).
Later nights skip those rows without building the pack. A changed input means a different
key, so the pack is rebuilt and checked again.

## Resolution (2026-11-24)

- **The file.** `build/driver/over-cap.json` (`driver.OVER_CAPS`, gitignored with build/, so
  the drive's audit never sees it): `{"over_cap": [{exe, start, arm, inputs, cap, size}]}`,
  one entry per (exe, start, arm), the latest verdict. `load_over_caps` / `save_over_caps`
  sit next to difficult.json's helpers. A malformed file refuses the drive at start
  ("over-cap list" in the REFUSED report); the file is written atomically, so only a hand
  edit can break it. A pack that fits drops its arm's verdict (`_forget_over_cap`).
- **The key.** `attempt.pack_key(data, row, src=, roots=)`, the sha256 of: the row (exe,
  start, end), `contextpack.PACK_CAP`, the digests of the code that builds the pack
  (`attempt.PACK_CODE`: attempt.py, contextpack.py and every package module contextpack
  imports, structs' lift, and configure.py, which contextpack.definitions loads), and of
  every file the pack's required sections and frame come from. That is the file list of the
  existing `attempt context` cache key (manifest, EXE, functions/units/symbols CSVs,
  status.csv, common.h, matching.md, the hints file, the signature table, the struct shapes),
  plus the row's listing, its Ghidra draft and every unit file of the EXE (the callees
  section shows matched callees' prototypes from other units). `_cache_key` and `pack_key`
  now share `_exe_paths` and `_context_paths`.
  - Left out, on purpose: the earlier notes and attempt records. They are optional sections,
    cut before PackOverCap is raised, so more of them only add cut marks to an over-cap pack
    and never make it fit, and reading attempts.jsonl for every pick would cost the most.
    The one edge: pruning old notes by hand shortens the "cut (N items)" marks by a byte or
    two, which could make a pack within those bytes of the cap fit while its key is unchanged.
    Also left out: the whole package's version (`_tool_files`). With it, any driver commit
    (77 since 2026-11-10) would re-check every over-cap row the next night.
  - The arm is in the verdict's place, not the digest: (exe, start, arm). A verdict only
    skips the row on the arm that recorded it, so a row never skips on an arm that has no
    verdict, a larger cap included (today every arm has the same cap).
- **src/ as HEAD.** The pack reads a view made from HEAD. The key reads the checkout's src/
  under the gate lock (`_Night._pack_key`), where src/ equals HEAD, and a unit missing at
  HEAD is scaffolded from the CSVs the key already covers. On PackOverCap, `_over_cap` reads
  HEAD and the key under the gate lock and keeps the verdict only when HEAD is still the
  view's commit, so a landing in between never leaves a verdict for inputs the pack never
  read. No key is computed on a launch whose pack fits.
- **The skip.** `_announced` asks `_known_over_cap` first: a verdict for (exe, start, the
  attempt's arm) whose inputs equal the pick's key now. The key is only computed when such a
  verdict exists. The pass then ends KNOWN_OVER_CAP before any claim, view or pack, with
  nothing printed for the pick. The slot goes back as for OVER_CAP, the coordinator parks the
  row on its own lane only (`_Lane.park`; a fresh OVER_CAP still parks every lane), and the
  report's `over_cap` counts it. The night prints one line at its end,
  `skipped N picks known over the pack cap (build/driver/over-cap.json)`. A key that cannot
  be read stops the night naming the pick (`_Stop` ERROR).
- **Not on a cascade night.** A cascade pass is the whole row of arms, so a skip would end it
  for the rungs with no verdict too. A cascade night keeps verdicts but never skips on them.
- **Wiring.** `Deps.pack_key` (default: none known, so nothing is kept or skipped),
  `ExeWorld.pack_key` from `load_world`, which calls `attempt.pack_key` over roots.src.
- docs/workflow.md: one bullet next to the difficult-list one.

### Tests

- tests/test_driver_workers.py: `test_an_over_cap_verdict_is_remembered_until_an_input_changes`
  (e2e on the fake clock: night 1 keeps the verdict, night 2 skips the pick with no pack try,
  no claim and no line of its own but the one summary line, night 3 with a changed key packs
  it again), `test_a_pack_refused_after_a_landing_moved_head_is_not_remembered`,
  `test_a_pack_that_fits_drops_its_arms_verdict` (a stale key skips nothing),
  `test_an_over_cap_verdict_never_skips_the_row_on_another_arm` (two `--arm` lanes, a HAIKU
  verdict: HAIKU skips, SONNET packs and runs it),
  `test_a_cascade_night_never_skips_on_a_kept_verdict`,
  `test_the_over_cap_file_round_trips_and_refuses_a_bad_one`,
  `test_a_bad_over_cap_file_refuses_the_night`.
- tests/test_attempt_wrapper.py: `test_the_pack_key_changes_with_each_input_that_decides_the_pack`
  (17 inputs, the cap included), `test_the_pack_key_ignores_what_never_decides_an_over_cap_pack`
  (7: notes, records, another row's listing, the census),
  `test_the_pack_key_follows_the_pack_code_alone`, `test_the_pack_key_is_the_rows_own`,
  `test_the_pack_code_holds_every_module_contextpack_imports`.

Not done here: a real night. The next Codex night after this lands should still print the
~80 over-cap lines once (no verdicts kept yet). The night after that should print one
"skipped" line instead, unless a match or a pack-code change moved the keys.
