---
phase: 07-mechanics-first-decompilation
plan: 44
subsystem: mechanics
tags: [asmclass, d-23, data-in-code, tier-queue, picker, driver, mechanics-status, sign-off, f36]
requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-43 (tiers 1-4 signed 2026-10-30), 07-32 (asm list / D-23 detector), 07-38 (tier queue as built)"
provides:
  - "four data-in-code evidence tags in the D-23 detector (no-terminator, text-run, zero-fill, bad-decode) and asmclass.data_facts"
  - "mechanics.DATA_TAGS, held_pairs, signed_held, TierStatus.held_starts, tier_status(held=), the held line in done_problems"
  - "picker.tier_queue(held=) and TierQueue.held: a signed `unclear` row with a data tag is never queued and never waited for"
  - "drive --dry-run reports held / held_starts and a `held: N` text line; mechanics status shows held per tier"
  - "config/asm-functions.csv regenerated with data evidence and the owner's verdicts; [asm_list] and tiers 1-4 re-signed by the owner on 2026-10-31"
affects: [07-39, 07-41, mechanics, driver, progress page]
actuals:
  tokens: 26010
  tasks: 7
  commits: 3
plan_head_before: de936e9e964f356fb31ebb9702afaba743eb87f8
plan_head_after: 69041410a9132a4e3a2d63301c5ff28906835b9c
tech-stack:
  added: []
  patterns:
    - "A queue filter keyed on an owner-pending verdict plus tool-owned evidence, read only through the signed list's sign-off check; it changes no members row, digest or check"
    - "Work parked as sha-pinned patches across owner checkpoints; every commit lands in the final task"
key-files:
  created:
    - .planning/phases/07-mechanics-first-decompilation/07-44-SUMMARY.md
  modified:
    - tools/reverseapoc/asmclass.py
    - tools/reverseapoc/mechanics.py
    - tools/reverseapoc/picker.py
    - tools/reverseapoc/driver.py
    - tools/reverseapoc/cli.py
    - tests/test_asmclass.py
    - tests/test_mechanics.py
    - tests/test_driver_pick.py
    - tests/test_drive_real.py
    - config/asm-functions.csv
    - config/mechanics-members.csv
    - config/mechanics.toml
    - docs/workflow.md
key-decisions:
  - "Owner Task 4 ruling (2026-10-31, ayrtondenner): the orchestrator's drafted verdicts were adopted as written: 35 data rows asm, 15 rows c, 4 rows kept unclear with an owner reason"
  - "Owner Task 6 ruling (2026-10-31, ayrtondenner): re-sign [asm_list] (list_sha256 8cb4649b...) and tiers 1-4 with the new digests; must-match 973/409/428/253 -> 943/403/412/248"
  - "The hold keys on verdict `unclear` plus a DATA_TAGS token on the signed list only; an owner `c` always queues a row and only an owner `asm` takes it out of must-match"
  - "Held rows stay in every total and in --require-matched, so a hold can never make a tier done (D-05)"
patterns-established:
  - "Data-in-code evidence is tool-owned; only the owner turns a data row into asm or c (D-23)"
requirements-completed: [DEC-01, DEC-02, DEC-03]
coverage:
  - id: D1
    description: "The D-23 detector tags data-in-code evidence and proposes such rows unclear; data tags never make a verdict asm; the merge keeps every verdict and reason"
    requirement: DEC-02
    verification:
      - kind: unit
        ref: "tests/test_asmclass.py#test_data_tags, test_data_rows_are_proposed_unclear, test_merge_adds_data_tags_and_keeps_rulings, test_tag_and_verdict_vocabulary"
        status: pass
      - kind: integration
        ref: "tests/test_asmclass.py#test_asm_list_has_no_drift, test_matched_rows_with_data_evidence_are_ruled_c (real files, main checkout)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The tier queue holds signed unclear data rows (never queued, never waited for) without changing any members row, digest or check"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_tier_queue_holds_unclear_data_rows, test_held_pairs, test_a_row_ruled_c_is_queued, test_signed_held_refuses_an_unsigned_or_changed_list, test_hold_keeps_the_tier_signed"
        status: pass
      - kind: integration
        ref: "tests/test_drive_real.py#test_real_tier_queue_holds_the_signed_tiers_members"
        status: pass
    human_judgment: false
  - id: D3
    description: "drive --dry-run and mechanics status report held / held_starts; a changed asm list refuses both"
    requirement: DEC-03
    verification:
      - kind: unit
        ref: "tests/test_driver_pick.py#test_dry_run_counts_held_rows, test_dry_run_refuses_a_changed_asm_list; tests/test_mechanics.py#test_status_reports_held, test_a_held_row_changes_no_check"
        status: pass
      - kind: other
        ref: "uv run reverseapoc mechanics status --json == build/gate/07-evidence/44-held-expected.json for tiers 1-4"
        status: pass
    human_judgment: false
  - id: D4
    description: "The owner's verdicts and re-sign landed: [asm_list] and tiers 1-4 signed with exactly the values the owner saw; mechanics check exits 0"
    requirement: DEC-01
    verification:
      - kind: other
        ref: "uv run reverseapoc mechanics check (no problems); mechanics digest --tier N == 44-digest-new-N.txt; config files == 44-asm-final.csv / 44-members-new.csv; TOML diff limited to sign-off lines"
        status: pass
    human_judgment: false
  - id: D5
    description: "Host suite + ruff and container suite green with only R-A skips"
    verification:
      - kind: other
        ref: "uv run pytest -q -rs (4204 passed, 40 skipped); uv run ruff check .; docker compose run --rm build ... (4242 passed, 2 skipped)"
        status: pass
    human_judgment: false
duration: 37min (Task 7 context); plan spanned three executor contexts on 2026-10-31
completed: 2026-10-31
status: complete
---

# Phase 7 Plan 44: Data-in-code rows held and reclassified Summary

**The D-23 detector now tags data-in-code rows (no-terminator, text-run, zero-fill, bad-decode). The tier queue holds signed `unclear` data rows until the owner rules them. The owner ruled 54 rows (35 asm, 15 c, 4 kept unclear) and re-signed [asm_list] and tiers 1-4, so Tier 1's must-match set drops from 973 to 943 and 4 rows stay held.**

Execution context nonce: a530f5bd60cfbd6d

## Performance

- **Duration:** Task 7 context 2026-10-31T17:52:53Z to 2026-10-31T18:29:26Z (37 min, mostly the two full suites). Tasks 1-3 and 5 ran in earlier contexts the same day.
- **Tasks:** 7 of 7. Tasks 4 and 6 were owner checkpoints.
- **Files modified:** 13 tracked files in 3 code/data commits, plus this SUMMARY.

## The owner's rulings, verbatim

1. **2026-10-31, before the plan** (owner ayrtondenner): "Reclassify in 07-44".
2. **Task 4** (owner ayrtondenner, 2026-10-31): "I agree, let's follow your suggestion". This answered the orchestrator's Task 4 checkpoint, which offered the drafted build/gate/07-evidence/44-asm-suggested.csv: asm for 35 data rows; c for 15 rows (8 large text-run false positives, among them the entry tacp 0x00067B60, plus the 7 Part B helpers); unclear for 4 rows (ufo2p 0x00051D80, 0x00061F30, 0x0009A5B0, 0x000B78A0, which are code without ret, from boundary splits). It is taken as the plan's form "verdicts written by ayrtondenner on 2026-10-31". At the owner's instruction the orchestrator copied 44-asm-suggested.csv over 44-asm-owner.csv. Both have sha256 8cb4649b4907678075cff7ae0a03bc6dfac0bfde0b040aec048e09b083d62578.
3. **Task 6** (owner ayrtondenner, 2026-10-31): "Re-sign (ayrtondenner)". This answered the orchestrator's re-sign question. It is taken as the plan's form "re-sign by ayrtondenner on 2026-10-31". The question showed these values, and the owner re-signed them and only them:
   - [asm_list] list_sha256 = 8cb4649b4907678075cff7ae0a03bc6dfac0bfde0b040aec048e09b083d62578
   - tier 1 members_sha256 = 5334aaf5b0c0ef0b2233b52a78e87d7f7f29ef589380ebdd72cd4afcc1f52c69 (973 -> 943)
   - tier 2 = a49192bfb6b392ed93dfa88eb9adb9aa44036aaa73a8708e1bcb3e32e9bbc333 (409 -> 403)
   - tier 3 = fa5ae9aa491cf5c619feb453256064561a3d608eeae72a690c61f5c6efcb83f8 (428 -> 412)
   - tier 4 = 142dc5088f393f160e318b74b4cfe7b9c4bfcf6cbfc5b031a58e83e2f6d40132 (253 -> 248)

   I recomputed every value after applying 44-work2.patch (`mechanics write`, then `mechanics digest --tier N`) and each one matched what the owner saw. No value the owner did not see was signed (F36).

## Accomplishments

- **Detector (asmclass.py).** TAGS ends with mechanics.DATA_TAGS. New constants: TERMINATORS, TEXT_RUN = 6, ZERO_RUN = ALIGNMENT = 16, MAX_INSN_BYTES = 15. `data_facts` decodes each row once and returns counts and mnemonics only, never bytes. `classify` now lists any game row that has a data tag, and a row listed for data evidence alone is proposed `unclear`.
- **Hold.** mechanics `held_pairs` / `signed_held` read the list only through its [asm_list] sign-off. `picker.tier_queue(held=)` drops held rows before the callees-first levels, so no caller waits on one, and `TierQueue.held` lists them. `driver.tier_source` passes the held set, so nights, draft picks and the dry run all share it.
- **Reporting.** The dry run's JSON gains `held` and `held_starts`, and its text gains a `held: N (...)` line. `mechanics status` adds held per tier and keeps every total. `--require-matched` names the held count. An unsigned or changed list refuses `drive` (reason `picks`) and `mechanics status` (exit 2).
- **Data.** The asm list went from 435 to 507 rows (72 added, 48 rows' evidence grown). With the owner's verdicts the counts went from asm 245 / c 0 / unclear 190 to asm 280 / c 15 / unclear 212. The members file has 2543 rows as before, 40 of them changed: 35 rows member -> asm, and 5 rows reached only through ufo2p 0x000A3000 lose their tier 3 items. [asm_list] and tiers 1-4 are re-signed. The page now draws 142 / 138 assembler functions (125 / 120 before), which equals the signed list's asm counts.

## Task Commits

1. **Tasks 1-2 tests (RED):** `c99c094` test(07-44): data-in-code evidence and the tier-queue hold (RED)
2. **Tasks 1-3 implementation and docs:** `5fa6806` feat(07-44): data-in-code evidence tags; the tier queue holds unclear data rows until the owner rules (owner ruling 2026-10-31)
3. **Tasks 3, 5 and 7 data and sign-offs:** `6904141` data(07-44): asm list with data-in-code evidence signed by ayrtondenner; tiers 1, 2, 3, 4 re-signed (D-23, F36)

**Plan metadata:** this SUMMARY commit (docs). Nothing is pushed: the orchestrator pushes.

## Tag counts and the negative control

- **Rows per data tag** on the regenerated list: no-terminator 104, text-run 54, zero-fill 57, bad-decode 1.
- **Rows with a data tag:** ufo2p 53 and tacp 67. The proposed list held 120 rows (verdict unclear with a data tag). After the owner's verdicts, 77 list rows qualify for the hold (verdict unclear plus a data tag) across both EXEs. The tier queue holds 7 of them, the ones a signed tier would queue: 4 unmatched must-match members and 3 hubs (see "Held rows" below).
- **Negative control** (`test_matched_rows_with_data_evidence_are_ruled_c`, real files, main): no status.csv `matched` game row carries a data tag. No threshold changed.
- **Proposal check** (44-proposal-check.txt): ALL PASS. All 435 old rows are present with the same verdict and reason. 48 rows' evidence grew by data tags only, in TAGS order. 72 rows were added, all unclear with an empty reason. None were removed. All 14 expected Tier 1 rows have a data tag.

## Report summary (44-data-report.txt, ALL PASS)

| Tier | must-match (HEAD) | Part A (data tag) | no-term | text-run | zero-fill | bad-decode | weak no-term only | weak text-run only | Part B (other unclear) | entries |
|------|------|------|------|------|------|------|------|------|------|------|
| 1 | 973 | 39 | 32 | 13 | 11 | 1 | 21 | 5 | 4 | 1 |
| 2 | 409 | 11 | 8 | 5 | 4 | 0 | 3 | 3 | 2 | 0 |
| 3 | 428 | 17 | 12 | 8 | 6 | 0 | 6 | 4 | 5 | 0 |
| 4 | 253 | 7 | 4 | 3 | 1 | 1 | 3 | 2 | 4 | 0 |

Across tiers 1-4 there are 54 distinct rows: 47 in Part A and 7 in Part B. All 16 Tier 1 `unclear` rows appear in the report. The report also gave an informational what-if, which was never signed: ruling every held row asm would have cost 55 / 18 / 43 / 15 must-match rows. The held entry tacp 0x00067B60 could not become asm (D-31), and the owner ruled it `c`.

## list_sha256, digests, totals and held counts

- **list_sha256:** 0f7093230df88290a923c0fdaf3eb8ec04b1916843b3692a493a847722790c09 (signed 2026-10-27) -> 8cb4649b4907678075cff7ae0a03bc6dfac0bfde0b040aec048e09b083d62578 (signed 2026-10-31)

| Tier | members_sha256 old | members_sha256 new | total old -> new | lost (self / through) | matched | partial | unmatched | held |
|------|------|------|------|------|------|------|------|------|
| 1 | dfa42a061a3b44248387a1cc6284354879a3e126fa8589c7d684adc8087b1da6 | 5334aaf5b0c0ef0b2233b52a78e87d7f7f29ef589380ebdd72cd4afcc1f52c69 | 973 -> 943 | 30 / 0 | 3 | 6 | 934 | 4 |
| 2 | 8ab76363ba3a87165efdfef2b902441a0ad483fcb4a7e1fcc8eb4302b8191cd6 | a49192bfb6b392ed93dfa88eb9adb9aa44036aaa73a8708e1bcb3e32e9bbc333 | 409 -> 403 | 6 / 0 | 1 | 0 | 402 | 2 |
| 3 | 5758c10f47f2e1b5c287153e9318438d0a3e0526ed5e837b73c91328da8e6313 | fa5ae9aa491cf5c619feb453256064561a3d608eeae72a690c61f5c6efcb83f8 | 428 -> 412 | 11 / 5 | 2 | 2 | 408 | 2 |
| 4 | 2d6a489a28f09b001a560b89b4377b4870d5751f4077ff85f5470b1b13642d4e | 142dc5088f393f160e318b74b4cfe7b9c4bfcf6cbfc5b031a58e83e2f6d40132 | 253 -> 248 | 5 / 0 | 0 | 1 | 247 | 0 |

The held column in the table counts must-match members only (4 / 2 / 2 / 0). Held members, from `mechanics status --json`, which equals 44-held-expected.json:
- Tier 1: ufo2p 0x00051D80, 0x00061F30, 0x0009A5B0, 0x000B78A0.
- Tiers 2 and 3: ufo2p 0x0009A5B0, 0x000B78A0.
- Tier 4: none.

**The queue holds 7 rows in all, not 4 (review fix round 1).** Besides the 4 members above it holds 3 hubs. Hubs are not must-match, so `mechanics status` does not count them, and they were never in the owner's report (Part A and Part B list must-match rows only):
- ufo2p 0x00028320: text-run only; a hub of tiers 1-4 with 20 or more direct callers;
- tacp 0x00024B20: no-terminator only;
- tacp 0x000615A0: text-run only.

The owner ruled on 2026-10-31 that these 3 hubs are ruled at 07-45's owner checkpoint. Until then the nights skip them. No done condition is affected, because hubs are not must-match.

All four night rows have left Tier 1 as owner `asm`: ufo2p 0x000126F0, 0x000129F0, 0x000129F3 and 0x00012A33.

## `mechanics check` and `mechanics status` after landing

```
$ uv run reverseapoc mechanics check
mechanics: no problems
$ uv run reverseapoc mechanics status
tier 1: 943 members, 3 matched, 6 partial, 934 unmatched (4 of them held for an asm-list ruling)
tier 2: 403 members, 1 matched, 0 partial, 402 unmatched (2 of them held for an asm-list ruling)
tier 3: 412 members, 2 matched, 2 partial, 408 unmatched (2 of them held for an asm-list ruling)
tier 4: 248 members, 0 matched, 1 partial, 247 unmatched
```

Signed tiers: (1, 2, 3, 4). `mechanics status --tier 1 --require-matched` exits 1. It reports 940 of 943 members not matched, and its held line names 4 (44-tier1-require.txt).

## 07-39 done condition, re-read

07-39 is done when `mechanics status --tier 1 --require-matched` exits 0 (D-05). Against the new Tier 1 set:
- **Tier 1:** 943 must-match members, down from 973 (30 owner-`asm` data rows left, and none were added). 3 are matched, 6 partial and 934 unmatched, so 940 are not matched. 4 of those are held: ufo2p 0x00051D80, 0x00061F30, 0x0009A5B0 and 0x000B78A0, which the owner kept `unclear` with a reason ("code without ret: boundary splits").
- **What done needs.** Every one of the 936 non-held, not-matched members must match through the nights. On top of that, the owner must rule each of the 4 held rows: `c` queues it for the nights, and `asm` takes it out of must-match. A held row is never queued, so the nights cannot match it while it stays held. **07-39 therefore cannot finish while held rows remain, but its nights can run.**
- **Stall rule.** The rule counts Tier 1's `matched` value, and the hold does not affect it. Held rows are never queued, so they cannot end a night flat by burning passes, and they never change `matched`.
- **Held hubs.** The queue also holds 3 hubs: ufo2p 0x00028320, tacp 0x00024B20 and tacp 0x000615A0. They are ruled at 07-45's owner checkpoint (owner ruling 2026-10-31). Hubs are not must-match, so they affect neither the done condition nor the stall rule.
- **Other tiers.**
  - Tier 2: 403 members, 1 matched, 402 unmatched, 2 held (ufo2p 0x0009A5B0, 0x000B78A0).
  - Tier 3: 412 members, 2 matched, 2 partial, 408 unmatched, 2 held (the same two rows).
  - Tier 4: 248 members, 0 matched, 1 partial, 247 unmatched, 0 held.

## RED evidence assessment

- **Record:** build/gate/07-evidence/44-red-record.json. The classifier printed RED_EVIDENCE_OK (reason target_test_failed).
- **Command:** `uv run pytest -q tests/test_driver_pick.py --junitxml=build/gate/07-evidence/44-red.xml -p no:cacheprovider`, run on HEAD's code with exit 1: 14 failed, 59 passed.
- **The target.** `test_tier_queue_holds_unclear_data_rows` ran; 44-red.xml shows a failure in its call phase, not a collection error. Its unheld baseline ([B, D, A]) passed first. It then failed at the planned hold with a TypeError, because HEAD's `tier_queue` has no `held=` parameter.
- **Assertion-level failures:** `test_dry_run_counts_held_rows` (HEAD picks TC, TB, TA) and `test_dry_run_refuses_a_changed_asm_list` (HEAD exits 0).
- **Missing-API failures:** the other failures name the planned API (`held_pairs`, `signed_held`, and the `held` dry-run key).
- **No unrelated test failed.**
- **Task 2's RED run:** 10 failed and 100 passed, failing on the missing tags, the missing status fields and `data_facts`.
- **TDD gate compliance:** the RED commit c99c094 comes before the GREEN commit 5fa6806. Its tree is HEAD's code plus the new tests.

## Deviations from Plan

- **Commits deferred to Task 7 (by plan design).** No commit was made before Task 7. The work crossed both owner checkpoints as 44-work.patch (sha256 d5926b7c2ebb0a0f76227f7dd609b6ebb1bc5045bffbe6df8931284d469e2250) and 44-work2.patch (sha256 f565e7b4bd8a3aec5050bf0a9a78eb72b372154bd32b072c8861a826913496aa).
- **[Rule 1 - test expectation] `test_dry_run_counts_held_rows` (Task 1).** The plan expected "picks [TC, TA] (TA now at level 1)". That contradicts the plan's own must_have, which drops a held row before the levels. With TA -> TB -> TC and TB held, TA and TC are both level 0, and rank puts TA first. The test asserts [TA (0), TC (0)], held 1, held_starts [TB]. I also added `test_dry_run_without_a_signed_tier_holds_nothing` to test the plan's "without a signed tier" clause on its own.
- **Tests added beyond the plan's list:** `test_data_facts_hold_counts_and_mnemonics` (Task 2: data_facts is the report's input).
- **Fixture fix (Task 2, test-only).** The bad-decode case first padded with 16 NOPs, which also fired `nop-pad`. It now uses eight `xor eax, eax`. No threshold changed.
- **Report addition (Task 3).** A second "weak" note marks a row whose only data tag is text-run while a ret or jmp decodes.
- **Owner-check script fix (Task 5).** This was my script, not the owner's data. The no-comma rule first ran on every row and flagged 34 unedited tacp reasons that HEAD's signed list already holds. It now applies only to edited cells. No owner cell was touched.
- **Owner copy provenance (Task 4).** The orchestrator drafted the verdicts. The owner adopted them verbatim ("I agree, let's follow your suggestion"), and the orchestrator copied the draft at the owner's instruction. The executor wrote no verdict or reason cell.
- **No threshold change, and no fix-forward commit.** Both full suites were green on the first run.
- **Orchestrator rulings applied:** R-A (skip reasons only), R-C (` M .planning/config.json` never staged, and the real `drive --dry-run` is left to the orchestrator), R-D (no subagents), and F36 (only owner-seen values signed, for [asm_list] and all four tiers).

**Total deviations:** 1 Rule-1 test-expectation fix and 3 small test/script/report additions, none of which changed scope. **Impact:** none on the owner-signed data. Every signed value equals what the owner saw.

## Issues Encountered

None that blocked. The background-wait loops hit the Bash tool's auto-background limit, and polling with short loops handled it.

## Verification

- Task 7 `<automated>` verify: exit 0. It covered:
  - `mechanics check`; signed tiers (1, 2, 3, 4);
  - held equal to 44-held-expected.json;
  - digests equal to 44-digest-new-N;
  - list and members files equal to the owner-seen files;
  - page counts;
  - the data commit's TOML diff limited to sign-off lines, and its files limited to the three config files;
  - a clean tree (except R-C's flag);
  - suite logs and skip reasons.
- Targeted suite (44-t7-pytest.txt): 505 passed, exit=0.
- **Host:** `uv run pytest -q -rs` 4204 passed, 40 skipped, exit=0. `uv run ruff check .`: All checks passed.
  - Skip reasons, all R-A: GHIDRA_INSTALL_DIR / run in the container (Ghidra, clang, ninja, objdiff-cli), only inside the container, POSIX-only (2 reasons), Windows file names cannot hold, non-UTF-8 byte names, symlink creation needs privileges on this host.
  - No new skip reason, and the orig-absent reason did not fire.
- **Container:** `docker compose build` exit 0. `docker compose run --rm build bash -lc "uv sync --locked && uv run pytest -q -rs && uv run ruff check ."` gave 4242 passed and 2 skipped (both `Windows-only: msvcrt lock path`), ruff All checks passed, exit=0.
- **Page:** `uv run python -I tools/progress.py --out build/gate/07-evidence/44-site` exit 0. assembler_functions ufo2p 142 / tacp 138 = the signed list's asm counts.

## Orchestrator steps (not run here)

1. **Real dry run (R-C, needs a fully clean tree).** Once the commit flag is cleared, run `uv run reverseapoc drive --dry-run --json > build/gate/07-evidence/44-dryrun.json`. Every key in 44-held-expected.json's `held_starts` (tiers 1-4) must appear in the dry run's `held_starts`. The dry run counts queue rows, members and hubs each once, so its count is higher: it should report 7 held, the 4 members plus the 3 hubs ufo2p 0x00028320, tacp 0x00024B20 and tacp 0x000615A0.
2. **Push** the three 07-44 commits and this SUMMARY together.
3. **07-39.** Task 3 (the owner's nights) may resume now. The owner's first step is `drive --dry-run`, which now prints `held: N`, with N = 7:
   - the 4 held Tier 1 members (ufo2p 0x00051D80, 0x00061F30, 0x0009A5B0, 0x000B78A0), which need an owner ruling before Tier 1 can be done;
   - the 3 held hubs (ufo2p 0x00028320, tacp 0x00024B20, tacp 0x000615A0), which the owner ruled on 2026-10-31 are ruled at 07-45's owner checkpoint. Until then the nights skip them. They affect no done condition, because hubs are not must-match.

   Tier 1 has 943 members.
4. **07-41 follow-ups:**
   - its precondition names 07-44;
   - its STATE decision line and 07-VALIDATION rows cite 07-44: the asm list re-signed with data-in-code evidence, tiers 1-4 re-signed, held members 4 / 2 / 2 / 0, and 7 held queue rows in all (the 4 members plus the 3 hubs);
   - its phase-gate steps (`mechanics status --tier 1 --require-matched`, any `drive --dry-run`, the page render) run only on a tree whose asm list is signed. `mechanics status` now exits 2, and `drive` refuses with reason `picks`, on an unsigned or changed list;
   - the review's other Minors are deferred to 07-41: `tier_held` builds the queue twice in the dry run, and `held_pairs` splits evidence on `_LIST`.
5. **rulings.md:** note that F36 applied to [asm_list] and tiers 1-4 in 07-44.
6. **07-45** (the boundary-split merge, being planned) also takes the 3 held hubs: ufo2p 0x00028320, tacp 0x00024B20 and tacp 0x000615A0. They are ruled at its owner checkpoint (owner ruling 2026-10-31).
7. **Later plans, not this one:**
   - a separate `data` verdict;
   - re-kinding data rows as `data-in-code` in functions.csv;
   - re-pointing an [[entry]] that is data;
   - ruling the 4 held members.

## Known Stubs

None.

## User Setup Required

None.

## Next Phase Readiness

The hold and the signed data are in place. 07-39 Task 3 can resume. The 4 held Tier 1 members remain for an owner ruling. The 3 held hubs (ufo2p 0x00028320, tacp 0x00024B20, tacp 0x000615A0) are ruled at 07-45's owner checkpoint, and until then the nights skip them.

## Self-Check: PASSED

- Files: all 13 modified tracked files exist and are committed. Evidence files 44-data-commit.txt, 44-status-after.json/.txt, 44-tier1-require.txt, 44-host.log, 44-ruff.log, 44-container.log, 44-check-signed.txt and 44-write-final.txt exist.
- Commits: c99c094, 5fa6806 and 6904141 are ancestors of HEAD, newest first and consecutive; `git rev-list --count de936e9..HEAD` = 3 before this SUMMARY commit.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-31*
