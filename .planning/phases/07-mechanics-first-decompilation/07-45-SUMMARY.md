---
phase: 07-mechanics-first-decompilation
plan: 45
subsystem: mechanics
tags: [split-rows, fall-through, asm-list, tier-signoff, watcom, gap-closure]

requires:
  - phase: 07-44
    provides: the signed asm list with data-in-code verdicts, the hold rule (held_pairs, signed_held)
  - phase: 07-43
    provides: tier sign-off and digest workflow (F36)
  - phase: 07-32
    provides: the mechanics members and tier machinery
provides:
  - "`mechanics splits [--exe E] [--json]`: every split pair of both EXEs with its evidence and class (tools/reverseapoc/splits.py)"
  - "owner verdicts on all 7 queue-held rows (4 members, 3 hubs); held count 0 in every tier and in the queue"
  - "ufo2p 0x0009A5B0 recut into u_0009a5d0 (units.csv, reason hand)"
  - "[asm_list] re-signed (list_sha256 332908805a...) and Tier 3 re-signed (e53efeee..., 412 -> 413)"
  - "docs/matching.md: the 07-45 fall-through rule, backed by a clean-room wcc386 10.6 calibration"
affects: [07-39, 07-41, 07-40, rulings.md]

actuals:
  tokens: 11045
  tasks: 8
  commits: 3
plan_head_before: d966610383a612e9759ac6a837ff918d650b1a75
plan_head_after: 71229738090674e7343d06e12836dcbffda321cb

tech-stack:
  added: []
  patterns:
    - "Split-pair classes decided in a fixed order (data, fall-through, label, unclear); a taken address counts as function evidence only when B looks like a function"
    - "Owner rulings cross two blocking checkpoints as parked patches; every commit lands after the last ruling"

key-files:
  created:
    - tools/reverseapoc/splits.py
    - tests/test_splits.py
  modified:
    - tools/reverseapoc/cli.py
    - docs/workflow.md
    - docs/matching.md
    - config/asm-functions.csv
    - config/mechanics.toml
    - config/mechanics-members.csv
    - config/ufo2p/units.csv
    - config/ufo2p/functions.csv

key-decisions:
  - "Owner (Task 3): every pair kept except the ufo2p 0x0009A5B0 recut; no merge, so the merges.csv override was not built"
  - "Owner (Task 3): the 4 held Tier 1 members are fall-through C (verdict c); hubs ufo2p 0x00028320 and tacp 0x000615A0 are c; tacp 0x00024B20 (a pointer table) is asm"
  - "Owner (Task 3): 9 of the 10 07-44 conflict rows confirmed asm; ufo2p 0x0005CCF0 re-ruled c, which re-adds it to Tier 3"
  - "Owner (Task 6): re-sign [asm_list] and Tier 3 only; Tiers 1, 2 and 4 keep their sign-offs"

patterns-established:
  - "A fall-through pair (A without ret, B called or address-taken) is C ending in a call to B and matches only together with B in one unit (F-0005, 07-45 calibration)"

requirements-completed: [DEC-01, DEC-02, DEC-03]

coverage:
  - id: D1
    description: "`mechanics splits` lists every split pair of both EXEs with evidence and class"
    requirement: DEC-01
    verification:
      - kind: unit
        ref: "tests/test_splits.py (18 tests, incl. test_split_pairs_classes, test_real_split_pairs)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Owner rulings applied through the generators; [asm_list] and Tier 3 re-signed; held 0 in every tier"
    requirement: DEC-03
    verification:
      - kind: other
        ref: "Task 7 <automated> verify (mechanics check, signed tiers (1,2,3,4), status held = 45-held-expected.json, digests = owner-seen values)"
        status: pass
      - kind: integration
        ref: "uv run pytest -q (host 4222 passed) and container suite (4260 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Both EXEs rebuild from clean SHA-1 identical under the new rulings"
    requirement: DEC-02
    verification:
      - kind: e2e
        ref: "container: ninja -t clean && ninja verify; reverseapoc gate --all; reverseapoc rebuild && cmp"
        status: pass
    human_judgment: false
  - id: D4
    description: "docs/matching.md fall-through rule and docs/workflow.md `mechanics splits` entry"
    verification: []
    human_judgment: true
    rationale: "Prose accuracy of the rule in our own words needs a human reader"

duration: 2h 0m
completed: 2026-10-31
status: complete
---

# Phase 7 Plan 45: Split-row rulings and re-sign Summary

**A read-only `mechanics splits` detector lists 104 split pairs. A clean-room wcc386 10.6 build shows that Watcom drops a tail call into the next function. The owner ruled all 7 queue-held rows (4 Tier 1 members `c`, hubs `c`/`c`/`asm`), recut ufo2p 0x0009A5B0 into u_0009a5d0 and re-ruled one 07-44 conflict row `c`. [asm_list] and Tier 3 are re-signed, and held is now 0 in every tier.**

Execution context nonce: 2280c608151c6326

## Performance

- **Duration:** 2h 0m wall clock, owner checkpoints included (Task 1 start 2026-10-31T20:02:39Z, SUMMARY 2026-10-31T22:02Z)
- **Tasks:** 8 (6 executor tasks, 2 owner checkpoints)
- **Files modified:** 10 tracked (2 new)

## Owner rulings, verbatim

1. 2026-10-31: "Gap plan 07-45 now".
2. 2026-10-31, the hub-row addition, as rulings.md records it: the 3 held hubs (ufo2p 0x00028320, tacp 0x00024B20, tacp
   0x000615A0), which 07-44 never showed the owner, are ruled at 07-45's checkpoint.
3. Task 3 (ayrtondenner, 2026-10-31): "I agree, we can continue with your suggestions". It answered the orchestrator's
   checkpoint, which offered drafted files. It is taken as the plan's form `rulings written by ayrtondenner on
   2026-10-31`. At the owner's instruction, the orchestrator copied 45-pairs-suggested.csv over 45-pairs-owner.csv
   (sha256 631f1e17...) and 45-asm-suggested.csv over 45-asm-owner.csv (sha256 332908805a...).
4. Task 6 (ayrtondenner, 2026-10-31): "Re-sign (ayrtondenner)". It is taken as `re-sign by ayrtondenner on 2026-10-31`.
   The question showed, and the owner re-signed, only:
   - [asm_list] list_sha256 332908805a55b7c73def9f7e99586ef110efab913285771a3fb2827475376488;
   - Tier 3 members_sha256 e53efeeef88245471835b9b3b482674cd70bcc0ebdcf23765f36ae6a358c4a62 (412 -> 413).

   Tiers 1, 2 and 4 keep their sign-off lines unchanged.

## Accomplishments

### Split pairs (Task 1; 45-splits.json)

| EXE | pairs | data | fall-through | label | unclear |
|-----|-------|------|--------------|-------|---------|
| ufo2p | 46 | 30 | 13 | 3 | 0 |
| tacp | 58 | 33 | 9 | 2 | 14 |

There are 10 conflict pairs, the same set as the planning probe: ufo2p 0x000477B0, 0x0005CCF0, 0x000880B0, 0x000A634C;
tacp 0x0002936A (label), 0x000296A1, 0x0005B6D0, 0x0007BC70, 0x000891E4, 0x000AA4F8. 45-pairs-owner.csv holds 41
non-data pairs.

### Calibration (Part C; container, our own C)

`CALIB fall-through reproduced: wcc386@10.6 -4r -s -fpi; wcc386@10.6 -4r -ot -s -fpi; wcc386@10.6 -4r -oneatx -s -fpi`.

- **T2 (the deciding case).** `b` calls an extern. Under all three rules, `a` keeps no call and no ret or jmp, and `b`
  is laid out right after it.
- **Controls.** C1 (`b` defined first) and C2 (`b` extern) end in jmp under every rule.
- **T1 and T3.** Supporting only.

### Part H: the 7 queue-held rows and the owner's verdicts

| row | role | evidence (short) | verdict |
|-----|------|------------------|---------|
| ufo2p 0x00051D80 | member T1-4 | no ret; runs into 0x00051DA0, whose address is taken twice | c |
| ufo2p 0x00061F30 | member T1-4 | no ret; 0x00061F50 is called once and tail-jumped twice | c |
| ufo2p 0x0009A5B0 | member T1-3 must-match | no ret; 0x0009A5D0 is called once and is an [[entry]]; cross-unit | c (and recut) |
| ufo2p 0x000B78A0 | member T1-3 must-match | no ret; 0x000B78D0 (ret only) has its address taken | c |
| ufo2p 0x00028320 | hub | prologue, 5 terminators, 20 caller rows; text-run false positive | c |
| tacp 0x000615A0 | hub | prologue, 21 terminators, ends in ret; text-run false positive | c |
| tacp 0x00024B20 | hub | no instruction, 4 pointer items: a pointer table | asm |

### Rulings applied (Tasks 4-5, landed in Task 7)

- **Pair rulings (41).** keep 40, recut 1, merge 0. Conflict cells: 9 `confirm`, 1 `re-rule` (ufo2p 0x0005CCF0, asm
  -> c, reason "owner 2026-10-31: re-ruled: called twice; cwde then falls into 0x0005CD00; code not data").
- **Recut ufo2p 0x0009A5B0 -> 0x0009A5D0.**
  - u_0009a420 0x0009A420-0x0009A5D0 becomes 0x0009A420-0x0009A5B0 (alignment-gap).
  - u_0009a5d0 0x0009A5D0-0x0009B0B0 (data-order) becomes 0x0009A5B0-0x0009B0B0 (hand). It keeps its name.
  - `functions --write` changed only that row's unit cell. boundaries.csv and the feed are byte-identical.
- **Merge override.** Not built: no merge was ruled. There is no config/<exe>/merges.csv, and functions.py is unchanged.
- **Verdict counts (8 cells changed).** asm 280 / c 15 / unclear 212 became asm 280 / c 22 / unclear 205.
- **list_sha256.** 8cb4649b4907678075cff7ae0a03bc6dfac0bfde0b040aec048e09b083d62578 became
  332908805a55b7c73def9f7e99586ef110efab913285771a3fb2827475376488.

### Tiers

| tier | digest old | digest new | must-match | change | held after |
|------|-----------|-----------|-----------|--------|------------|
| 1 | 5334aaf5... | unchanged | 943 -> 943 | none | 0 (was 4) |
| 2 | a49192bf... | unchanged | 403 -> 403 | none | 0 (was 2) |
| 3 | fa5ae9aa491cf5c619feb453256064561a3d608eeae72a690c61f5c6efcb83f8 | e53efeeef88245471835b9b3b482674cd70bcc0ebdcf23765f36ae6a358c4a62 | 412 -> 413 | gained ufo2p 0x0005CCF0 `readded` | 0 (was 2) |
| 4 | 142dc508... | unchanged | 248 -> 248 | none | 0 (was 0) |

**Attribution (45-signoff.txt ALL PASS).**
- The recut moved no tier, and neither did the hub verdicts, the c/unclear changes or `asm_in` (tacp 0x00024B20, a hub).
- `asm_out` (ufo2p 0x0005CCF0) moved Tier 3.
- There was no lost row and no `UNEXPECTED MOVE`.
- The expected queue-held list is empty (it was 7 rows). 70 held rows remain on the list, all of them closure rows,
  which the queue never holds.

## Task Commits

1. **Task 7 (a): RED tests.** `1d60b13` `test(07-45): the split-row detector (RED)`
2. **Task 7 (b): the detector and docs.** `3ca3470` `feat(07-45): mechanics splits, the split-row detector (owner ruling 2026-10-31)`
3. **Task 7 (c): owner data and sign-offs.** `7122973` `data(07-45): split-row and held-row rulings; asm list signed by ayrtondenner; tier 3 re-signed (D-23, D-11, F36)`

The SUMMARY commit is `docs(07-45): complete the split-row rulings and re-sign plan`. By plan design, no commit was made
before Task 7.

## RED evidence assessment

- **Record.** 45-red-record.json, target `test_split_pairs_classes[a]`: `RED_EVIDENCE_OK` (target_test_failed). All 18
  tests failed on HEAD d966610.
- **Semantic assessment.** The target ran and failed in its call phase on `ModuleNotFoundError: reverseapoc.splits`. HEAD
  lists no split pair, which is exactly the planned missing behaviour. There was no collection or fixture fault.
- **The Task 7 test fix.** It touched only `test_real_split_pairs` pins, not the target.
- **Merge override.** None built, so there is no merge RED record.

## Suite and gate results (all logs head=7122973)

- **Host** (`uv run pytest -q -rs`): 4222 passed, 40 skipped, exit 0. Every skip reason is R-A, and none is new. Ruff:
  All checks passed.
- **Container** (`docker compose build`, then `uv sync --locked && uv run pytest -q -rs && uv run ruff check .`): 4260
  passed, 2 skipped (both `Windows-only: msvcrt lock path`), exit 0.
- **Container, from clean:**
  - `ninja -t clean && ninja verify`: exit 0. UFO2P.EXE sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 (6 landed);
    TACP.EXE sha1 48ef00969d8880a0a152de1b652853fa7ac27393 (4 landed).
  - `reverseapoc gate --all`: exit 0 (ok).
  - `reverseapoc rebuild && cmp build/UFO2P.EXE orig/UFO2P.EXE && cmp build/TACP.EXE orig/TACP.EXE`: exit 0. UFO2P,
    TACP and SMKP sha1 equal the manifest.
- **Task 7 targeted suite:** 425 passed, exit 0 (run 2; see Deviations for run 1).
- `mechanics check`: no problems. The signed tiers are (1, 2, 3, 4).

## 07-39 done condition, re-read

`mechanics status` (45-status-after.txt):
- Tier 1: 943 members, 3 matched, 6 partial, 934 unmatched, **held 0**. `--require-matched` exits 1 (940 of 943 not
  matched), as expected while members are unmatched.
- Tier 2: 403 members, 1 matched, 0 partial, 402 unmatched, held 0.
- Tier 3: 413 members, 2 matched, 2 partial, 409 unmatched, held 0.
- Tier 4: 248 members, 0 matched, 1 partial, 247 unmatched, held 0.
- The expected queue-held list (members and hubs, `picker._held_in_order`) is **empty**. Held is 0 in every tier.

**07-39 nights can resume with held 0.**

Each `fall-through` row ruled `c` matches only together with its partner (F-0005), and the unit claim covers both rows:

| A (ruled c) | -> B (partner) | unit | joined by a recut? |
|-------------|----------------|------|--------------------|
| ufo2p 0x00051D80 | 0x00051DA0 | u_00051d00 | no (same unit already) |
| ufo2p 0x00061F30 | 0x00061F50 | u_00060c50 | no (same unit already) |
| ufo2p 0x0009A5B0 | 0x0009A5D0 | u_0009a5d0 | **yes** (was u_0009a420 -> u_0009a5d0) |
| ufo2p 0x000B78A0 | 0x000B78D0 | u_000b7740 | no (same unit already) |
| ufo2p 0x0005CCF0 | 0x0005CD00 | u_0005c940 | no (same unit already); a 07-44 conflict row re-ruled asm -> c (Tier 3) |

The other fall-through pairs keep their A as `unclear` or `asm`, and none of them is a queued member or hub:
- `unclear`: ufo2p 0x000189E6, 0x000260B0, 0x00026FB2, 0x00030100, 0x000784A0; tacp 0x0001028F, 0x00032B60, 0x000505C4,
  0x000A5D70;
- `asm`: the 8 confirmed fall-through conflicts.

The context-pack and watcom-decomp hint for these pairs is a later plan (writing-skills only). No skill was edited here.

## Files Created/Modified

- `tools/reverseapoc/splits.py`: SplitPair, classify_splits, signed_list, format_splits, splits_json (new).
- `tools/reverseapoc/cli.py`: `mechanics splits`.
- `tests/test_splits.py`: synthetic classes, the CLI shape, the no-bytes check, the real-file pins (new).
- `docs/workflow.md`: `mechanics splits` in the Mechanics data list. `docs/matching.md`: the 07-45 fall-through rule.
- `config/asm-functions.csv`: 8 owner verdict and reason cells. `config/mechanics.toml`: [asm_list] list_sha256 and Tier 3
  members_sha256.
- `config/mechanics-members.csv`: ufo2p 0x0005CCF0 changes from asm to member (264-21), and tacp 0x00024B20 from hub to
  asm.
- `config/ufo2p/units.csv` and `config/ufo2p/functions.csv`: the recut, through `functions --write`.

## Decisions Made

All rulings are the owner's (above). The executor wrote no ruling, verdict, reason or sign-off value of its own.
- **Recomputed before signing.** The executor recomputed every value before signing. asm_list_sha256, the members file
  and the four digests equal the owner-seen values.
- **Sign-off lines.** In [asm_list] and Tier 3, `signed_off_by` and `signed_off_date` already held `ayrtondenner` and
  `2026-10-31`. The re-sign therefore changed only the `list_sha256` and `members_sha256` lines.

## Deviations from Plan

- **Deferred commits (by plan design).** All three commits land in Task 7. The work crossed both owner checkpoints as
  45-work.patch (sha256 a75dd533...) and 45-work2.patch (sha256 85402e93...).
- **Difference from the planning probe.** tacp 0x0001028F -> 0x000102A0 is `fall-through` (B is called, starts with a
  prologue and decodes a terminator). The probe had it `unclear`. So tacp shows 9 fall-through / 14 unclear, against the
  probe's 8 / 15. tacp 0x000615A0 shows 4 caller rows (every call-graph edge kind), where the probe counted 3 calls.
- **Merge override not built.** No merge was ruled (45-merge-mechanism.txt).
- **Tests added beyond the plan's list (Task 1).** `test_split_pair_count_and_conflict_needs_the_list` and
  `test_cli_splits_writes_nothing`.

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stale real-file pins in test_real_split_pairs after the owner's rulings**
- **Found during:** Task 7, step 3. Targeted suite run 1 (45-t7-pytest-run1.txt): 1 failed, 424 passed.
- **Issue:** two pins described the planning-time state, which the owner's rulings changed.
  - ufo2p 0x0009A5B0 -> 0x0009A5D0 was pinned `same_unit False`. The ruled recut put both rows in u_0009a5d0, so True
    is correct.
  - The conflict pin was ufo2p 0x0005CCF0. The owner re-ruled it `c`, so by definition it is no longer a conflict.
  - Task 5's applied-tree test run (test_functions_real, test_units, test_drift) did not include test_splits.
- **Fix:** test only, with no production change. The recut pair now pins `same_unit True`. `REAL_CONFLICT` is now ufo2p
  0x000477B0 (07-44 asm, owner `confirm`). A new `REAL_RERULED` pin asserts that 0x0005CCF0 has `a_verdict` `c` and
  `conflict` False.
- **Files modified:** tests/test_splits.py (in the RED commit 1d60b13; the RED target is untouched).
- **Verification:** tests/test_splits.py passed 18 of 18. Targeted suite run 2: 425 passed, exit 0. Ruff is clean.

The earlier Task 1 test-only fix (the operand check in test_split_output_has_no_bytes) is recorded in 45-notes.txt.

**Total deviations:** 1 auto-fixed in this context (Rule 1, test only). **Impact:** none on code or data. The pins now
follow the owner's committed rulings.

No fix-forward commit was needed in Task 8.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None.

## Next Phase Readiness / orchestrator steps

- **R-C, not run here.** On a fully clean tree (commit flag removed), run `uv run reverseapoc drive --dry-run --json >
  build/gate/07-evidence/45-dryrun.json`. Its `held_starts` must equal 45-held-expected.json's `queue`, which is `[]`
  (held 0).
- **07-39.** Task 3 can resume. The owner's first step is `drive --dry-run`, which should print `held: 0`.
- **07-41.**
  - Its precondition should name 07-44 and 07-45.
  - Its STATE and 07-VALIDATION rows should cite the 07-45 items: the detector, the pair rulings, the [asm_list] and
    Tier 3 re-sign, and held 0.
  - Its phase-gate steps run only on a tree with a signed asm list.
  - Its rebuild + cmp also proves the ufo2p 0x0009A5B0 recut.
- **rulings.md.** Add a 07-45 section:
  - F36 applied to [asm_list] and Tier 3;
  - merges.csv not built (no merge ruled).
- **Later plans.**
  - A context-pack or watcom-decomp hint for fall-through pairs (through writing-skills).
  - A filler study for the rows that end open after a terminator (about 777 / 753).
  - A `pointer-table` data tag (tacp 0x00024B20).
- **STATE.md and ROADMAP.md.** Not updated here, per the dispatch.

## Self-Check: PASSED

- The created files exist: tools/reverseapoc/splits.py, tests/test_splits.py and this SUMMARY.
- The commits 1d60b13, 3ca3470 and 7122973 are ancestors of HEAD. `git rev-list --count d966610..7122973` = 3.
- The Task 7 and Task 8 automated verifies passed. The Task 8 verify is re-run after this commit.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-31*
