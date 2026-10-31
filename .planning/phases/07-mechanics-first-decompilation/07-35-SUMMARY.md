---
phase: 07-mechanics-first-decompilation
plan: 35
subsystem: agent-instructions
tags: [skill, watcom-decomp, writing-skills, driver-docs, views, flags]

requires:
  - phase: 07-13
    provides: private per-attempt views, REVERSEAPOC_UNIT_FILE, the view-mode hook allowlist
  - phase: 07-14
    provides: the D-15 second sweep stage and its sweep_hit / stage2 output
  - phase: 07-21
    provides: workers, claims, the shared usage-limit pause
  - phase: 07-24
    provides: flags approve and flags default (owner only)
  - phase: 07-26
    provides: the tier queue
  - phase: 07-30
    provides: Opus-then-Fable passes and the drive flags
provides:
  - watcom-decomp skill for view-mode matching sessions (view unit only, no header, placeholders, both sweep stages)
  - tests/test_skill.py pins for the view unit, the src/ rule, the view flags rule, stage 2 and the real sweep output
  - docs/workflow.md Phase 7 "Running the driver", hooks view mode, "Flag rules (D-12, D-14)", "Mechanics data"
affects: [07-39, 07-38, 07-34]

actuals:
  tokens: 19142
  tasks: 2
  commits: 3
plan_head_before: ce7fc2dacd79b9f2cfefe62b4aea4676d34c2c13
plan_head_after: a9428f6367d0c519f0be0c88a04ecadab9157375

tech-stack:
  added: []
  patterns:
    - "A skill's printed-output sample is pinned to the code that prints it (attempt._sweep_summary)"

key-files:
  created: []
  modified:
    - .claude/skills/watcom-decomp/SKILL.md
    - tests/test_skill.py
    - docs/workflow.md

key-decisions:
  - "The skill keeps its nine sections in order (191 lines) and is reference and recipe, not discipline: RED found cost and guessed facts, no rationalization, so no rationalization table"
  - "test_skill_does_not_send_agents_to_src allows a line that names src/<exe>/<unit>.c only when it says never; the view path itself is stripped first"
  - "A matching session writes no proposals.jsonl (the hook allows it): a name idea goes in notes.md, naming is the readability pass (D-19), consistent with watcom-readability"

requirements-completed: [DEC-02, DEC-06]

coverage:
  - id: D1
    description: "watcom-decomp names the view unit (REVERSEAPOC_UNIT_FILE), forbids headers and src/ writes, states the view's flags rule, both sweep stages and placeholder names"
    requirement: DEC-06
    verification:
      - kind: unit
        ref: "tests/test_skill.py (19 tests)"
        status: pass
    human_judgment: true
    rationale: "Whether agents follow the skill is the orchestrator's GREEN re-run of V1-V4 (ruling F20), not a unit test"
  - id: D2
    description: "docs/workflow.md documents the Phase 7 driver, the view-mode hooks, the owner-only cflags files, the flag verbs and the mechanics verbs"
    requirement: DEC-02
    verification:
      - kind: other
        ref: "grep -- --fable-budget-usd / flags approve / REVERSEAPOC_UNIT_FILE docs/workflow.md; uv run pytest -q tests/test_hygiene.py tests/test_listings.py"
        status: pass
    human_judgment: true
    rationale: "'The owner can run Phase 7 nights from the docs alone' is an owner judgment"

duration: 75min
completed: 2026-10-31
status: complete
---

# Phase 7 Plan 35: watcom-decomp for private views, and the Phase 7 driver docs Summary

**The watcom-decomp skill now sends a matching session to its private view unit at `$REVERSEAPOC_UNIT_FILE` and nowhere else. It also gives the rules RED showed agents finding by reading tools/: no header, types declared in the unit, placeholders kept, the view's cflags rule, both sweep stages with the real output, and how a hit becomes a proposal. docs/workflow.md now describes the Phase 7 driver, the view-mode hooks, the flag verbs and the mechanics verbs.**

Execution context nonce: a909b2c906d4afd5

## Performance

- **Duration:** about 75 min
- **Completed:** 2026-10-31T00:53Z
- **Tasks:** 2 (Task 1 a tracer, verified end-to-end before Task 2)
- **Files modified:** 3

## Accomplishments

- **SKILL.md** (147 -> 191 lines, nine sections in order):
  - description: the view unit, without `src/`;
  - quick reference rows: "Your file", "What you may write", "Types you need", "Names", "Flags of your check";
  - the Never list adds headers, the `view/include/` and `view/config/` copies, and renames;
  - one paragraph on what a hook denial costs and what a stray costs.
  - "Flags": the view rule, and the path from sweep hit to `flags propose` to `flags approve`.
  - "Replacing INCLUDE_ASM": the view, the repo-root unit as HEAD's copy, the landing order, the struct recipe, and no renames.
  - "The attempt wrapper": stage 1 and stage 2 (trigger, cells, numbering, spec forms), the real sweep output sample, and the `stage2` JSON.
  - "When to give up": stop at exit `0` (the final view text lands); notes after a hit; notes take name ideas and only facts that were read.
- **tests/test_skill.py**: six new tests, and the JSON-field check now also knows a sweep whose stage 2 ran.
- **docs/workflow.md**:
  - "What changed in Phase 7";
  - the night command, plus the Fable canary step;
  - the `drive lock` and `claims` refusals;
  - the tier dry run;
  - "One attempt" and the reset rules, for views;
  - in the hooks section, the always-layer cflags rows, the build/ exemptions and the view mode;
  - a new "Flag rules (D-12, D-14)" subsection and "Mechanics data".

## Task Commits

1. **Task 1 RED: skill tests** - `1dfc265` (test)
2. **Task 1 GREEN: watcom-decomp for private views (writing-skills)** - `1add168` (docs)
3. **Task 2: Phase 7 driver, hooks and flag rules** - `a9428f6` (docs)

## superpowers:writing-skills

I invoked the skill with the Skill tool and followed it as F20 adapts it:
- **RED:** the orchestrator's baseline in `.superpowers/sdd/let-s-execute-gsd-execute-phase-7-sorted-harp/skill-baseline-decomp-view/`: SCENARIOS.md, V1-red.md to V4-red.md and RED-FINDINGS.md. These are four fresh no-skill agents, 86 tool uses in all.
- **GREEN:** the re-run of V1 to V4 is the orchestrator's (F20).
- **Form:** I classified the failures under "Match the Form to the Failure". There were no rule violations and no rationalizations. The failures were cost (source reads to learn three facts) and guessed facts. So the update is reference and recipe: rows, a struct recipe, the output sample, and a conditional ("after exit `0`, stop").
- **No rationalization table.** RED named two temptations: the view's cflags copy, and a header "because the docs say so". Each gets one sentence, in "Flags" and in "Replacing INCLUDE_ASM".
- **Not done:** the wording micro-tests (5+ reps against a control). They need subagents, which R-D/F20 forbid. The orchestrator's GREEN run is the wording check.

Per-gap table (RED-FINDINGS "What the skill update must teach" and "stale lines"):

| RED gap | Where the skill now answers it | Pinned by |
|---|---|---|
| Teach 1: the one file, at `$REVERSEAPOC_UNIT_FILE`, /goal path; root `src/` is HEAD's copy; no header; types in the unit (recipe); D-19; why a header cannot land | quick reference "Your file", "What you may write", "Types you need"; Never list; "Replacing INCLUDE_ASM" opening, struct paragraph and example | `test_skill_names_the_view_unit`, `test_skill_does_not_send_agents_to_src` |
| Teach 2: the view's `config/cflags.txt` rule (per-unit rules exist); both hook layers deny edits; stage 1 30/60; stage 2 trigger, cells, under 10.6, from 31/61; spec forms; same `sweep_hit` line; harvest from `checks/NNNN.c`; notes after a hit | quick reference "Flags of your check"; "Flags"; "The attempt wrapper" stage list; "When to give up" | `test_skill_states_the_view_flags_rule`, `test_skill_states_the_second_sweep_stage` |
| Teach 3: placeholders stay; name ideas in notes.md, not proposals.jsonl; naming is the readability pass | quick reference "Names"; Never list; "Replacing INCLUDE_ASM" last bullet; notes item 5 | `test_skill_keeps_names_placeholders` |
| Teach 4: a denial costs a turn and a hook block; a stray ends the night | the paragraph after the Never list | judgment (GREEN) |
| Teach 5: the real sweep output | the sample in "The attempt wrapper" (stage 2 cell 42, `-zp4`) | `test_skill_quotes_the_real_sweep_output` (each body line is `attempt._sweep_summary`'s) |
| Teach 6: notes facts are read, never invented | the last paragraph of "When to give up" | judgment (GREEN) |
| V1 wrong 1: the landing order | "Replacing INCLUDE_ASM": copy to `src/`, then lint and gate, put back on failure | judgment |
| V1 wrong 2: a Read of context.md after `attempt context` | wrapper table: "it is printed, so no Read of context.md is needed" | judgment |
| V2 wrong 3/4: who runs `flags propose`, what it reads | "Flags": an executor, every sweep's `checks/NNNN.c`; only the owner approves | `test_skill_states_the_view_flags_rule` |
| V2 wrong 5 / scenario defect 2: the stage from guesswork | stage-2 cell list and "Read the stage from the output" | `test_skill_states_the_second_sweep_stage` |
| V3 wrong 7/8: why no proposals.jsonl; the notes path | "Replacing INCLUDE_ASM" (not applied anywhere; readability, D-19); quick reference (path after `notes:`) | `test_skill_keeps_names_placeholders` |
| V4 wrong 11: a cflags edit is denied, not a night stop | "Flags" and the denial paragraph | judgment |
| V4 wrong 12: "the `*` default held for every match" | "Flags": a few units have per-unit `-oneatx` rules | judgment |
| V4 wrong 14: the stage-2 spec form | spec forms `wcc386@10.6 -4r -oi -s -fpi`, `wcc386@10.6 -4r -s -fpi -zp4` | judgment (forms checked against `check.sweep2_cells`) |
| Stale L3 (description) | the view unit, no `src/` | `test_skill_does_not_send_agents_to_src`, `test_skill_names_the_view_unit` |
| Stale L15 (may write a header) | the view unit and notes.md only, no header | `test_skill_does_not_send_agents_to_src` |
| Stale L20 (default flags only) | "Flags of your check": the unit's rule in the view's file | `test_skill_states_the_view_flags_rule` |
| Stale L26 (Never misses view copies) | Never list names `view/config/` and `view/include/` | `test_skill_does_not_send_agents_to_src` |
| Stale L94 (compiles the claimed unit) | "compiles your view unit (`$REVERSEAPOC_UNIT_FILE`)" | `test_skill_names_the_view_unit` |
| Stale L95 (30 or 60 cells) | "stage 1, and stage 2 after a near miss" | `test_skill_states_the_second_sweep_stage` |
| Stale L117 (`cells[]` only) | `stage2` (`from`, `cells`, `best`); the hit is stage 1's first, else stage 2's | `test_skill_json_fields_exist` (now with a stage-2 sweep) |
| Stale L138 (resets the unit itself) | "abandons the view; the repo-root unit is never yours to reset" | judgment |
| Stale docs/workflow.md L160, 163, 169, 202, 208 | Task 2: "One attempt", reset rules, always-layer table, matching layer | Task 2 grep and hygiene checks |

Every fact was checked against the code in this worktree:
- hooks.py: `matching_write_allowed`, `_view_denial`, `_PROTECTED_FILES`, ATTEMPT_FORMS;
- driver.py: `_make_view`, `_land`, `_judge`, `_reset`, `_Claim.env`, `_sweep_evidence`, the claims and pause classes;
- attempt.py: `_sweep_summary`, `_sweep_line`, `_default_spec`, `_summary`, `cmd_context`;
- check.py: `sweep_cells`, `sweep2_cells` (16 cells from `-4r -s -fpi`, 24 from a cell with an `-o` set), `sweep2_trigger`, `SWEEP2_FLOOR`;
- flags.py: the module docstring and `find_hits`;
- session.py: `goal_prompt`.

The skill keeps the two skills consistent about names: matching keeps placeholders, and readability names through proposals. It says nothing about 07-34's rename landing, so nothing there needs a "planned" mark. The watcom-readability skill already marks it planned.

## Files Created/Modified

- `.claude/skills/watcom-decomp/SKILL.md`: the matching-session skill for views.
- `tests/test_skill.py`: `test_skill_names_the_view_unit`, `test_skill_does_not_send_agents_to_src`, `test_skill_states_the_view_flags_rule`, `test_skill_states_the_second_sweep_stage`, `test_skill_quotes_the_real_sweep_output`, `test_skill_keeps_names_placeholders`; `_stage2_sweep` feeds the JSON-field check too.
- `docs/workflow.md`: the Phase 7 driver, hooks, flag rules and mechanics data.

## Decisions Made

- **Reference and recipe, not discipline** (writing-skills "Match the Form to the Failure"), because RED had no rationalizations.
- **The src/ line rule.** RED-FINDINGS asked for a decision in the RED step. A line may name `src/<exe>/<unit>.c` only if it says "never". The view path, `.../view/src/<exe>/<unit>.c`, is stripped before that check, because it names the session's own file.
- **The sweep sample is pinned to the printer.** The sample's body lines must be exactly what `attempt._sweep_summary` prints for the same cells, so the sample cannot go stale silently.
- **No exact container command for `flags regate`.** The docs say "in the container, for objdiff-cli", as the CLI help does, and do not guess a compose invocation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] A separate RED commit.**
- **Found during:** Task 1.
- **Issue:** the plan names one Task 1 commit, but the phase 7 rules require a failing test commit before GREEN.
- **Fix:** two commits, `test(07-35)` RED (all 6 new tests failing because the content was missing), then `docs(skill)` GREEN with the plan's message. The GREEN commit also refines the src/ test: it strips the view path, which itself contains `src/<exe>/<unit>.c`.
- **Commits:** 1dfc265, 1add168.

**2. [Rule 2 - Missing critical] More skill tests than the plan's two.**
- **Found during:** Task 1.
- **Issue:** RED-FINDINGS' GREEN criteria and the ruling notes (07-14: stage 2 through `sweep_hit`) need the view flags rule, stage 2 and the output sample pinned, or they can go stale.
- **Fix:** four more tests, and the JSON-field check now covers a sweep whose stage 2 ran.
- **Files:** tests/test_skill.py. **Commit:** 1dfc265.

**3. [Rule 1 - Bug] Stale Phase 6 text elsewhere in docs/workflow.md.**
- **Found during:** Task 2.
- **Issue:** the plan named "Running the driver" and the hooks section. RED-FINDINGS also lists the stale "One attempt" (L160, L163), reset rules (L169) and always-layer table (L202) lines, all inside those sections.
- **Fix:** all of them rewritten. The dry-run paragraph also gained the tier picks, and the refusal table gained the existing `drive lock` and `claims` reasons. Ctrl+C now names every live session.
- **Commit:** a9428f6.

**Orchestrator ruling F20:** the orchestrator ran the RED baseline and runs GREEN after this return. No subagents were dispatched, and writing-skills' micro-tests were not run (they need subagents).

**Orchestrator ruling (rulings.md "## 07-35, 07-36", 07-13 note):** the skill no longer allows "a new header under `include/`" and no longer names `src/<exe>/<unit>.c` as the file to edit. Sessions edit only `REVERSEAPOC_UNIT_FILE`.

**Orchestrator ruling (rulings.md "## 07-35, 07-36", 07-14 note):** the skill says `attempt check --sweep` can report a second-stage hit (D-15, up to 24 cells under 10.6 after a near miss) through the same `sweep_hit` field and printed line.

**Total deviations:** 3 auto-fixed (2 missing critical, 1 bug) plus 3 orchestrator rulings applied. **Impact:** test and doc coverage only; no tool code changed.

## Issues Encountered

- The harness refused a compound guard script and a scratchpad Python helper, as too complex to verify inside the worktree. I ran their steps as separate commands or as direct edits.

## Test results

- `uv run pytest -q`: **3873 passed, 251 skipped** (444 s). `uv run ruff check .`: clean.
- `tests/test_skill.py`: 19 passed. `tests/test_hygiene.py tests/test_listings.py`: 108 passed, 3 skipped.
- I did not list the 251 skip reasons, because that needs a second 7-minute run. This plan adds no skipping test: all six new tests run and pass on the host.
- Task 2's `<verify>` greps pass (`--fable-budget-usd`, `flags approve`, `REVERSEAPOC_UNIT_FILE`). `--workers`, `--max-sessions`, `--target-matched` and `mechanics status` are all named.
- Every `reverseapoc <verb>` and every `flags`/`mechanics` subverb in docs/workflow.md exists in the CLI's parser (checked with a script against `build_parser()`).
- No container step: this plan has none.

## Known Stubs

None.

## User Setup Required

None.

## Next Phase Readiness

- Ready for the orchestrator's GREEN re-run of V1 to V4 with the fixed prompts (RED-FINDINGS "Scenario defects"), then 07-39, the first real Phase 7 nights.
- When 07-34 lands the rename step: neither the skill nor docs/workflow.md says that a matching session's proposals are applied. If 07-34 changes that, update the skill's "Replacing INCLUDE_ASM" last bullet.

## Self-Check: PASSED

- FOUND: .claude/skills/watcom-decomp/SKILL.md (191 lines, at most 300)
- FOUND: tests/test_skill.py, docs/workflow.md
- FOUND commits: 1dfc265, 1add168, a9428f6 (ancestors of HEAD)

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-31*
