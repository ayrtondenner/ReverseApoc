---
phase: 07-mechanics-first-decompilation
plan: 36
subsystem: agent-skills
tags: [skill, writing-skills, readlint, proposals, readability, docs]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-19 proposals.py (rename/header format), 07-27 readlint.py (RL01-RL06, WAIVER, RL03 form), 07-31 attempt.py readability check (pending renames, F18)"
provides:
  - ".claude/skills/watcom-readability/SKILL.md: the readability session skill (D-17..D-21, D-30), written through superpowers:writing-skills"
  - "tests/test_skill_readability.py: shape, paths, verbs, wrapper forms, and every stated format checked against the code that parses it"
  - "docs/ceremonies.md: the readability pass in 'Which pass runs where'"
  - "docs/tools.md item 4 lists watcom-readability (F29)"
affects: [07-38 readability session kind, 07-34 rename step, 07-40 allowlist]

actuals:
  tokens: 8300
  tasks: 2
  commits: 3
plan_head_before: 5f5bbb2f564847cc9863bfa887e76cfa40aa7c6a
plan_head_after: b1eca061ee5ca91767e6c725b6a4c013701bb7db

tech-stack:
  added: []
  patterns:
    - "A skill's examples are executable: the example unit is linted by the real readlint, and the example output must equal attempt.Lint.lines() for the same hits"

key-files:
  created:
    - .claude/skills/watcom-readability/SKILL.md
    - tests/test_skill_readability.py
  modified:
    - docs/ceremonies.md
    - docs/tools.md

key-decisions:
  - "A new skill rather than a watcom-decomp section (plan's flagged assumption; watcom-decomp is pinned to nine sections)"
  - "No per-check time figure (no '90 s'): the watcom-decomp M1 precedent; budget by the elapsed seconds the wrapper prints"
  - "Driver behaviour not built yet (07-34 rename rewrite, 07-38 landing outcomes) is stated as planned"
  - ".claude/rules/workflow.md not edited (F29): the owner may add watcom-readability to its list"

patterns-established:
  - "Skill output examples are generated-format pins: the test builds the Lint the example shows and asserts each line verbatim"

requirements-completed: [DEC-04]

coverage:
  - id: D1
    description: "watcom-readability skill: allowed edits, RL03 header, D-21 name sources, proposal formats, constants, readlint table, wrapper forms, real output, planned landing"
    requirement: DEC-04
    verification:
      - kind: unit
        ref: "tests/test_skill_readability.py (14 tests)"
        status: pass
    human_judgment: true
    rationale: "Whether sessions follow the skill is the writing-skills GREEN run, which the orchestrator performs after return (ruling F20)"
  - id: D2
    description: "docs/ceremonies.md lists the readability pass with readlint as the readability judge and gate for bytes"
    verification:
      - kind: other
        ref: "grep -q watcom-readability docs/ceremonies.md && uv run pytest -q tests/test_hygiene.py"
        status: pass
    human_judgment: false

duration: 75min
completed: 2026-10-30
status: complete
---

# Phase 7 Plan 36: watcom-readability skill Summary

**A readability-session skill whose every format (proposal lines, RL03 header, `/* lit: */` waiver, the readability `attempt check` output) is executed by its test against proposals.py, readlint.py and attempt.py, plus the readability pass in docs/ceremonies.md**

Execution context nonce: 692cf2bc786291ac

## Performance

- **Duration:** about 75 min
- **Started:** 2026-10-30T19:15Z (approximate)
- **Completed:** 2026-10-30T20:40Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `.claude/skills/watcom-readability/SKILL.md` (225 lines, the seven sections in the plan's order), written through superpowers:writing-skills with the orchestrator's RED baseline as the RED phase (ruling F20; no subagents dispatched).
- `tests/test_skill_readability.py` (14 tests), written first and committed failing (RED, 12 failing on the missing file), then green with the skill. It checks the frontmatter, the 300-line cap, the sections, that every path, anchor and `reverseapoc` verb exists, and that every wrapper command is a `hooks.ATTEMPT_FORMS` form with all five quoted. Beyond the plan, it also runs every format the skill shows through the code:
  - the example proposal lines pass `parse_line`, `name_problem` and `header_problem`;
  - the example header passes readlint's RL03 check;
  - every waiver matches `readlint.WAIVER`;
  - the example view unit, linted by the real `run_readlint` as a matched unit, gives exactly the hits and the one waiver that the output example shows;
  - the output example contains `attempt.Lint.lines()` for those hits verbatim, plus the real readability verdict and check-half texts;
  - the budgets are read from `attempt.CHECK_BUDGET`, `session.MAX_TURNS`, `hooks.CHECK_TIMEOUT_MS`, `EVIDENCE_TEXT_MAX` and `NAME_MAX`.
- A scratch mutation check confirmed that 8 of 8 single-fact mutations of the skill make the test fail. The mutations: `UFO2P` without `.EXE`, a wrong count word, a non-waiver comment, a short address, the dropped budget, a wrong line number, a non-wrapper command, and the dropped landing re-check.
- docs/ceremonies.md, "Which pass runs where": a readability-pass row and a note. The note says who runs the pass (driver readability sessions on owner-started nights) and on what (matched units, Tier 1 first, bottom-up). It lists what a session may touch: names and shared headers only through proposals (D-19). The gate decides bytes and readlint decides readability, and the note points to the skill. "The one rule" is unchanged.

## Task Commits

1. **Task 1 RED: skill test** - `a504b54` (test)
2. **Task 1 GREEN: the skill (and the test aligned to the final example unit)** - `07f69d6` (docs)
3. **Task 2: readability pass in ceremonies, docs/tools.md F29** - `b1eca06` (docs)

## writing-skills: RED baseline gaps and what closes them

RED is the orchestrator's baseline in `.superpowers/sdd/let-s-execute-gsd-execute-phase-7-sorted-harp/skill-baseline-readability/`: SCENARIOS.md, S1-red.md to S4-red.md and RED-FINDINGS.md. Four fresh agents ran without the skill and used 78 tool uses in total. No hard rule was violated. The gaps were cost (reading tools/*.py to learn formats), F18 and landing knowledge, and loose evidence use. GREEN (re-running S1 to S4 with the skill) is the orchestrator's step after return.

| Baseline gap (RED-FINDINGS) | Skill part |
|---|---|
| All four read proposals.py, readlint.py and attempt.py to learn the formats (78 tool uses) | Intro: "never read `tools/` to learn one". Quick reference table, plus both proposal line examples, the key set, value forms, name rules and refusal causes |
| Proposal format (priority 1) | "Names, evidence and proposals": rename and header examples (tested through `parse_line`, `name_problem` and `header_problem`). Exact keys, `0x%08X` upper case, the 200-character evidence limit, the 63-character name limit. "The last line for a row wins." |
| RL03 form, and item 9: `UFO2P` vs `UFO2P.EXE` | "Header comments": `Address: <UFO2P.EXE|TACP.EXE> 0x%08X` spelled out, with a full example unit that passes RL03 under the real readlint. It also says where the header must sit (the last comment after `;`, `}` or a directive). |
| Item 5: does the rename rewrite the header's first line? (S1, S3) | "Write the current placeholder name ... the driver's rename step (planned) rewrites every whole-word use ..., comments included" |
| Item 1: S3 ran the check before writing proposals; F18 unknown | "Write the proposals before you run `attempt check`", with what `pending rename` and `rename proposal refused: <why>` mean. Names are "re-checked at landing, after the driver applies the proposals (planned)" (07-36 note, 07-31 as built) |
| Item 2: S1 counted pending per name | Output example with 4 pending lines for 2 names. "pending renames are counted per hit, not per name" |
| Item 6: S4 read invented output | "The attempt wrapper": the real readability output, pinned line for line to `attempt.Lint.lines()` and the verdict tables, and produced by the real readlint on the example unit |
| Item 3: S2 called `36` for `0x24` "also fine" | "Constants without changing bytes": copy the token exactly, with the C89 reason (spelling and suffix pick the type). Why not `static const` or `enum` |
| Waiver form known only from source (S2) | `/* lit: <reason> */`, on the literal's line, whole comment (every waiver in the skill matches `readlint.WAIVER`) |
| Soft violation: S1's `table:` citing mechanics.toml; S2's `call:` without addresses | Evidence-kind table: what each kind's text names (EXE addresses; `vocab:` a word only). "Project records such as `config/mechanics.toml` are not an evidence kind: cite the game fact they record, by its address." |
| Soft violation: S4's name without a module prefix | Style line: `snake_case` with a module prefix (`docs/coding-style.md#naming`) |
| Item 7: budgets unknown, turn counting | Quick reference: 40 turns, 25 checks, 30 minutes, elapsed seconds per check. Stop rule: about 25 of 30 minutes or 35 of 40 turns |
| Item 8: what lands; S4 re-checked restored text | "When to stop": the final view text lands, not the best check (planned). LANDED, PARTIAL or REFUSED. End on byte-identical text; restore from `<attempt dir>/checks/NNNN.c`, with no re-check needed |
| Priority 5: which type changes are allowed | "What you may change": no type change to an existing declaration (`jl`/`jge` vs `jb`/`jae`, load widths); an alias typedef keeps the bytes; never change the defined or `INCLUDE_ASM` set |
| Unnamed callees (D-30) | Placeholder stays; list it in notes.md for `config/readlint-allow.csv`, which sessions never edit. Allowlisted references explained |
| Bash forms | All five `hooks.ATTEMPT_FORMS` quoted with their use in a readability session (`--sweep` marked "no use here"). The 600000 timeout, foreground only |
| Form (writing-skills "Match the Form to the Failure") | No rationalization table, because the baseline shows none. Recipes and reference tables, plus a short "Never" list for the prohibitions RED-FINDINGS names |

## Decisions Made

- **No "about 90 s per check"** although RED-FINDINGS item 8 lists it. The watcom-decomp skill's M1 rule (tests/test_skill.py asserts "90 s" is absent) forbids an unmeasured per-check figure. The skill tells sessions to budget by the elapsed seconds and checks left that each check prints. The test pins this too.
- The example uses made-up addresses (0x00012340, 0x00012400, 0x000D1230, 0x00011000), so the skill states no unverified game fact.
- `attempt check --sweep` is quoted (every form is quoted) but marked "no use here". A sweep never runs readlint and costs a check.

## Deviations from Plan

- **Orchestrator ruling F20:** RED came from the orchestrator's baseline files. No subagents were dispatched, and GREEN is run by the orchestrator after return.
- **Orchestrator ruling F18 (07-36 note):** the skill says in-session `pending rename` is not a guarantee, and that names are re-checked at landing after the driver applies the proposals (07-34) and can be refused there.
- **Orchestrator ruling F29:** watcom-readability is added to docs/tools.md "Skill installation decisions" item 4. `.claude/rules/workflow.md` is not edited: the owner may add `watcom-readability` to its list of project skills (only `watcom-decomp` and `apoc-spec` are named there now). docs/tools.md is outside the plan's files_modified, as the ruling directs.
- **[Rule 2 - Missing critical] A separate RED commit.** The plan names one Task 1 commit, but the phase 7 rules require a failing test commit before GREEN. So Task 1 has two commits: `test(07-36)` RED, then `docs(skill)` GREEN with the plan's message. The GREEN commit also aligns the test's example lint with the final example unit (line numbers and a second failing hit, the callee prototype).
- **[Rule 2] Stronger test than the plan lists.** It runs the real readlint over the example unit and pins the output example to `attempt.Lint.lines()`, so the shown formats cannot drift from the code (RED item 6).

**Total deviations:** 3 orchestrator rulings applied, 2 Rule-2 additions. **Impact:** no scope creep beyond F29's one-line docs/tools.md edit.

## Issues Encountered

- The worktree harness refused compound git commands and runtime-computed sed. The worktree guard was run as separate commands (all checks passed: branch `worktree-agent-a69307fce5b235cd9`, base 5f5bbb2), and the mutation check ran as a scratch Python script that restored the skill byte for byte.

## Verification

- `uv run pytest -q tests/test_skill_readability.py`: 14 passed.
- `grep -q "watcom-readability" docs/ceremonies.md && uv run pytest -q tests/test_hygiene.py`: 77 passed, 3 skipped (pre-existing).
- `uv run pytest -q` (host, worktree): 3737 passed, 248 skipped in 452 s. Every skip is a pre-existing real-file reason (`orig/<EXE> not present`, the Watcom 10.6 tree or watcom-media under the worktree's absent third_party/, and the like); this plan adds none.
- `uv run ruff check .`: all checks passed.
- Container step deferred to the orchestrator: `docker compose build && docker compose run --rm test`. The new test needs no real files.

## User Setup Required

None. The owner may optionally add `watcom-readability` to `.claude/rules/workflow.md` (F29).

## Next Phase Readiness

- 07-38 can append `.claude/skills/watcom-readability/SKILL.md` to readability sessions. session.py's `SKILL` constant names only watcom-decomp today; 07-38 wires the per-kind skill.
- When 07-34 and 07-38 land, update the skill's "planned" markers (writing-skills again) and re-check the LANDED, PARTIAL and REFUSED wording against the built driver.
- GREEN: the orchestrator re-runs S1 to S4 with the skill, using the criteria in RED-FINDINGS.md.

## Self-Check: PASSED

- FOUND: .claude/skills/watcom-readability/SKILL.md (tracked)
- FOUND: tests/test_skill_readability.py
- FOUND: commits a504b54, 07f69d6, b1eca06 on HEAD
