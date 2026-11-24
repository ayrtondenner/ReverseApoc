---
title: Cross-EXE look-alikes inside the context pack
created: 2026-11-18
area: context-pack
files: tools/reverseapoc/contextpack.py, tools/reverseapoc/attempt.py, tools/reverseapoc/cli.py, tests/test_contextpack.py, tests/test_attempt_wrapper.py
source: batch 2026-11-18 worker reports
---

# Cross-EXE look-alikes inside the context pack

U4 (batch 2026-11-18) made picking similarity cross-EXE but the pack's Look-alikes section still uses same-EXE rows. Give _lookalike_inputs an `others` mapping (the other EXE's matched rows and C) and label each entry (tacp)/(ufo2p).

## Resolution (2026-11-24)

### The change

- contextpack: `Candidate` (a matched row's name, start, mnemonic sequence and C) and
  `lookalike_candidates(rows, flat, fixups, symbols, status, unit_texts)`, built on the same
  `_candidates` walk the own-EXE look-alikes use. `gather(..., others=)` takes each other
  EXE's candidates by stem; `_lookalike_inputs` ranks them with the own EXE's rows in one
  `lookalikes` call (the same difflib metric, floor 0.6 and top 3), keyed (EXE, start) with ""
  for the own EXE, so an equal ratio puts the own row first.
- Labels: only a cross-EXE entry is labelled, `### func_00010010 (tacp, 0x00010010, similarity
  1.000)`, and its cut line reads `look-alike func_00010010 (tacp)`. Own-EXE entries keep
  today's head, so a pack with no cross-EXE look-alike is byte-identical (pinned by sha256).
- attempt.make_pack passes `others` from `_other_candidates`: every other manifest EXE with a
  config/<exe>/units.csv (twins.plan_twins's rule), its status from the same config, its C
  from the same src root (a session's view, which holds HEAD's whole src/). An EXE with no
  matched row is not loaded. `reverseapoc context` loads the other EXE from its own `--orig`
  and `--manifest`.
- The view's `attempt context` cache key now covers each other EXE's image, functions/units/
  symbols.csv and status.csv; its unit files are derived digests (from its functions.csv).

New pack inputs (for any hash of a pack's inputs): the other EXE's orig image,
config/<other>/functions.csv, units.csv, symbols.csv, status.csv, and src/<other>/<unit>.c.

### Tests

- tests/test_contextpack.py: test_a_pack_with_no_cross_exe_lookalike_is_unchanged (sha256
  pin taken at a86b0278), test_no_cross_exe_lookalike_leaves_the_pack_as_it_was,
  test_lookalike_candidates_are_the_matched_rows_with_c,
  test_a_lookalike_matched_only_in_the_other_exe_is_labelled_with_it,
  test_an_equal_cross_exe_lookalike_ranks_after_the_own_exe_one,
  test_a_cut_cross_exe_lookalike_names_its_exe.
- tests/test_attempt_wrapper.py: test_context_packs_a_lookalike_matched_in_the_other_exe,
  test_an_other_exe_with_nothing_matched_is_not_loaded,
  test_view_context_cache_misses_on_the_other_exes_inputs (status change, view unit change).

Not done here: a measure of how often a real pack gains a cross-EXE look-alike (needs orig/).
Each pack build now loads the other EXE once when it has matched rows (one more LE load per
session launch).
