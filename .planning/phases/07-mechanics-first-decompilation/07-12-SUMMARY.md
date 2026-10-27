---
phase: 07-mechanics-first-decompilation
plan: 12
subsystem: tooling
tags: [mechanics, locate, get_text, int386, asm-list, d-23, dec-01, capstone]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-05 callgraph.py (WALKED_KINDS, POINTER_FIXUPS, the strict table rule); 07-08 spike 007 q1/q3/q4/q6 (the locate route, GET_TEXT facts, 0x1A readers); 07-10 mechanics.py (AsmRow, ASM_COLUMNS, format_asm_csv, read_asm_list, the mechanics verb)"
provides:
  - "tools/reverseapoc/locate.py: LocateError, StringRef, Site, TextSection, GET_TEXT, load_inputs, string_refs, table_refs, interrupt_callers, get_text_sections, get_text_index, get_text_sites, report_* and format_report"
  - "tools/reverseapoc/asmclass.py: TAGS, ALIGNMENT, LIBRARY_UNITS, AsmClassError, classify, merge, verdict_counts"
  - "`reverseapoc mechanics locate --exe EXE (--string K | --va 0xA | --range 0xA 0xB | --get-text S I | --int 0x1A) [--json]`"
  - "`reverseapoc mechanics asm [--write] [--json]`"
affects: [07-20, 07-22, 07-25, 07-28, 07-32]

actuals:
  tokens: 16600
  tasks: 3
  commits: 7

tech-stack:
  added: []
  patterns:
    - "Per-basic-block register tracker for Watcom register arguments (mov imm, xor/sub r,r, mov r,r; reset at in-row labels and after terminal instructions; calls forget eax/edx)"
    - "Seam `locate.load_inputs` (monkeypatched in tests, like mechanics.load_graphs)"
    - "Tool-owned vs owner-owned CSV columns: merge never compares verdict/reason (F17)"

key-files:
  created:
    - tools/reverseapoc/locate.py
    - tools/reverseapoc/asmclass.py
    - tests/test_locate.py
    - tests/test_asmclass.py
  modified:
    - tools/reverseapoc/cli.py

key-decisions:
  - "GET_TEXT slot count is 52 for both EXEs (spike 007 q4); research's 50 is the dump loop bound, so the real pin is 52 UFO2P sections (21 TACP)"
  - "get_text and int386 arguments are recovered per basic block only; a register set earlier in the row is not guessed (UFO2P 735/997 full sites vs the spike's 742)"
  - "The asm list's address column is tool-owned: a row the detector no longer proposes is removed and reported; verdict and reason of a kept row are never compared (F17)"
  - "callgraph.py's strict table rule is unchanged; locate.table_refs takes exactly the caller's range, so the spike's 64-byte record lead-in is a by-hand --range query until 07-22 decides"

patterns-established:
  - "Locator reports carry addresses, counts, interrupt numbers, (section, index) pairs and the caller's keyword only"

requirements-completed: [DEC-01]

coverage:
  - id: D1
    description: "string, table and interrupt locators and the `mechanics locate` subcommand"
    requirement: DEC-01
    verification:
      - kind: unit
        ref: "tests/test_locate.py#test_string_refs, test_table_refs, test_interrupt_callers, test_no_match_is_empty, test_cli_locate_string_json, test_cli_locate_range_va_and_int_json"
        status: pass
      - kind: integration
        ref: "REVERSEAPOC_ORIG=<main>/orig uv run pytest -q tests/test_locate.py#test_interrupt_0x1a_callers"
        status: pass
    human_judgment: false
  - id: D2
    description: "get_text route: section table decode, string index, call-site (section, index) recovery with partial sites"
    requirement: DEC-01
    verification:
      - kind: unit
        ref: "tests/test_locate.py#test_get_text_sections, test_get_text_index, test_get_text_sites_constant, test_get_text_sites_xor, test_get_text_sites_computed, test_planted_section_count_fails"
        status: pass
      - kind: integration
        ref: "REVERSEAPOC_ORIG=<main>/orig uv run pytest -q tests/test_locate.py#test_ufo2p_get_text_has_52_sections, test_tacp_get_text_has_21_sections, test_get_text_caller_rows, test_speed_label_sites"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-23 asm detector and `mechanics asm --write` with the verdict-preserving merge"
    requirement: DEC-01
    verification:
      - kind: unit
        ref: "tests/test_asmclass.py#test_tags, test_exact_proposal, test_unaligned_only_is_unclear, test_library_span_rows, test_merge_keeps_hand_verdicts, test_cli_asm_write"
        status: pass
      - kind: integration
        ref: "REVERSEAPOC_ORIG=<main>/orig uv run pytest -q tests/test_asmclass.py#test_unaligned_counts_match_research"
        status: pass
    human_judgment: false
  - id: D4
    description: "The asm proposal itself (125 asm / 93 unclear UFO2P, 86 / 131 TACP) is evidence for the owner, not a ruling"
    verification: []
    human_judgment: true
    rationale: "D-23: only the owner's sign-off at 07-20 decides which rows leave the must-match sets; the heuristics (research A5) are unproven per row"

duration: 30min
completed: 2026-10-27
status: complete
plan_head_before: 7469bf1211abaaf1037bea1a8e1407451b2628d8
plan_head_after: dc35f311d73dfa3ce8767f171db8c654c7930d11
---

# Phase 7 Plan 12: Locate and asm-detector tools Summary

**`mechanics locate` finds entry candidates by string fixups, table ranges, int386_(0x1A) callers and get_text (section, index) call sites; `mechanics asm` proposes the D-23 asm list (unaligned and library-unit game rows with evidence tags) and merges re-runs without touching owner verdicts.**

Execution context nonce: 4c21cd77dc1fc281

## Performance

- **Duration:** about 30 min (first timestamp 2026-10-27T17:51:12Z after the required reading; last commit 18:10Z)
- **Tasks:** 3 (tracer + 2 auto, all TDD)
- **Files:** 4 created, 1 modified (1,553 insertions)

## Accomplishments

- `locate.py`, the production form of spike 007's routes:
  - `string_refs(exe, keyword)`: NUL-terminated data strings holding the keyword (case-insensitive), each with the game/thunk rows that have an exact fixup to its first byte. Unreferenced strings come back with `rows=()` (UI text goes through get_text).
  - `table_refs(exe, lo, hi)`: game/thunk rows with a fixup into [lo, hi). An empty range is refused.
  - `interrupt_callers(exe, vector)`: calls (or tail jumps) to `int386_`/`int386x_` whose basic block last set eax to the vector. With no such runtime row the result is empty.
  - `GET_TEXT`, `get_text_sections`, `get_text_index`, `get_text_sites`. The table check refuses:
    - a slot that is not an off32 to a string start below the table;
    - two slots that share a start;
    - a nonzero slot with no fixup (the count is too large);
    - a text pointer in the slot past the last (the count is too small).
- `mechanics locate --exe ufo2p|tacp (--string | --va | --range | --get-text | --int) [--json]`:
  - It prints addresses, counts and the typed keyword only.
  - `--va` on a text string adds its (section, index), the sites that ask for it and the section-only rows.
  - An empty result prints `0 rows` and exits 0.
- `asmclass.py`:
  - `classify` tags every unaligned game row and every game row in a library unit, and proposes `asm` (library-span, or unaligned plus an asm tag) or `unclear` (unaligned only).
  - The tags are unaligned, stack-frame, enter, pushal, iretd, nop-pad and library-span.
  - `LIBRARY_UNITS` is checked against the committed units.csv.
- `mechanics asm [--write] [--json]`:
  - Without `--write` it is a dry run.
  - `--write` writes `config/asm-functions.csv` atomically through `format_asm_csv`, keeping every existing verdict and reason.
  - It reports only tool-owned changes.
- Real runs, read-only against the main checkout's orig/:

  | Check | UFO2P | TACP |
  |---|---|---|
  | 0x1A callers | `0x00011430` | `0x00011500`, `0x000116B0` |
  | `tactical.map` fixup rows | `0x000B0F70`, `0x000B4590` | `0x000141A0` |
  | get_text sections | 52 | 21 of 52 |
  | get_text sites (rows) | 997 (180) | 315 (88) |
  | sites with both arguments recovered | 735 = 73.7% | 255 = 81.0% |
  | section only | 227 | 47 |
  | index only | 7 | 1 |
  | neither | 28 | 12 |
  | full pairs past their section | 0 | 3 (`0x0003600C`, `0x000537CA`, `0x000539E7`, as the spike found) |
  | asm proposal rows | 218 | 217 |
  | unaligned (research: 213 / 216) | 213 | 216 |
  | library rows (of them aligned) | 99 (5) | 9 (1) |
  | proposed asm / unclear | 125 / 93 | 86 / 131 |

  - Tag counts, UFO2P: enter 59, pushal 60, stack-frame 23, nop-pad 14, iretd 1.
  - Tag counts, TACP: enter 56, pushal 57, stack-frame 23, nop-pad 14, iretd 1.
  - The list was **not written**. Plan 07-20 writes it and commits it after the owner's ruling (F38).

## Task Commits

1. **Task 1 (tracer): `mechanics locate --string` end to end**
   - RED `57a1f73`, GREEN `0827206`.
   - Tracer gate (interactive, end-of-phase, automated-only verify): verify re-run green (14 passed), expanded.
2. **Task 2: the get_text route**
   - RED `f00ced7`, GREEN `d2b4631`.
   - REFACTOR `0cb5b89`: the `GET_TEXT = {` spelling the acceptance grep reads. No behaviour change.
3. **Task 3: the asm detector and `mechanics asm --write`**
   - RED `86eb805`, GREEN `dc35f31`.

## TDD Gate Compliance

Each task has a `test(07-12)` commit before its `feat(07-12)` commit. The RED commits carried API stubs only, the precedent from 07-10.

RED semantic assessment (`workflow.tdd_mode` is not set, so the classifier gate does not apply; this is the pytest run at each RED commit):

- **Task 1:** 11 failed, 3 passed.
  - The failures are assertion failures on the planned behaviour: empty stub results, and the CLI printing nothing (JSON decode of empty output).
  - The 3 passes are characterization: the planted-failure check, the empty result with no int386_ row, and argparse exclusivity.
- **Task 2:** 20 failed, 16 passed.
  - Every get_text test fails on its assertion (empty sections, None index, missing sites, no LocateError), and so do the real pins.
  - The passes are the Task 1 tests and the GET_TEXT address pin (stub constants).
- **Task 3:** 11 failed, 6 passed.
  - Failures: empty proposal, no-op merge, no CLI output.
  - Passes, all characterization: the vocabulary constants, the planted-failure check, the empty-EXE case, the committed units.csv test, the vacuous drift test (F32), and the on-disk hand-verdict test (the stub writes nothing).

## Files Created/Modified

- `tools/reverseapoc/locate.py`: the string, table, interrupt and get_text locators, the register tracker, the report builders and the `load_inputs` seam.
- `tools/reverseapoc/asmclass.py`: the D-23 detector, the merge and the verdict counts.
- `tools/reverseapoc/cli.py`: the `mechanics locate` and `mechanics asm` verbs. `LocateError` and `AsmClassError` exit 2.
- `tests/test_locate.py`:
  - 28 synthetic tests;
  - 8 real pins (skip without orig/): sections, caller rows, speed-label sites, 0x1A callers.
- `tests/test_asmclass.py`:
  - 17 synthetic and committed-data tests;
  - 2 real pins: the unaligned counts;
  - the drift test, which passes vacuously while there is no committed list.

## Decisions Made

See key-decisions in the frontmatter. In addition:

- `interrupt_callers` and `get_text_sites` count tail jumps (`jmp get_text`) as sites.
- `INT386_NAMES` holds both `int386_` and `int386x_`, which take the number in eax, as spike q1 did.
- Address arguments (`--va`, `--range`) are read as hex, like `asm --start`. `--int` and `--get-text` take `0x..` or decimal.

## Deviations from Plan

**Orchestrator ruling F17: "changed" means a tool-owned change.**
- A change is new evidence, a row added, or a row removed.
- An existing row's verdict and reason are never compared with the new proposal.
- Tests: `test_merge_keeps_hand_verdicts` covers owner flips unclear -> asm and asm -> c, which are not reported. `test_merge_reports_tool_column_changes_and_removed_rows` and `test_cli_asm_keeps_a_hand_verdict_on_disk` cover the rest.

**Orchestrator ruling F32: the drift test passes when there is no committed list.**
- `test_asm_list_has_no_drift` passes ("nothing to check") without `config/asm-functions.csv` instead of skipping.
- Once 07-20 commits the list, it needs orig/ and skips with the orig reason.

**1. [Rule 1 - Bug] UFO2P has 52 get_text sections, not 50**
- **Found during:** Task 2.
- **Issue:** The plan pins `test_ufo2p_get_text_has_50_sections` and `GET_TEXT` "50". Spike 007 q4 measured 52 slots, all filled in UFO2P. Research's 50 is the loop bound of the dump routine next to get_text. Sections 50 and 51 exist and are called.
- **Fix:**
  - `GET_TEXT` holds 52 slots for both EXEs (the plan said to take TACP's N from the README; it is also 52).
  - The pin is `test_ufo2p_get_text_has_52_sections`, plus `test_tacp_get_text_has_21_sections`.
  - A wrong count is refused both ways (planted 3 and 5 slots).
- **Verification:** both real pins pass against orig/.
- **Commits:** `f00ced7`, `d2b4631`.

**2. [Rule 2 - Missing critical] Extra real pins and refusals**
- **Added real pins:**
  - get_text caller rows 180 / 88;
  - the speed-label sites (UFO2P 38/43-46, TACP 36/0-3);
  - the unaligned counts 213 / 216;
  - the library units against the committed units.csv. This test needs no game files and also checks research's VESA span 0x161B4-0x18970.
- **Added refusals:** an empty or non-ASCII keyword, an empty range, a library unit missing from units.csv.
- **Commits:** `f00ced7`, `86eb805`, `dc35f31`.

**3. [Rule 3 - Blocking] The `load_inputs` seam lives in locate.py**
- The plan says to load "through the same seam as mechanics.load_graphs". mechanics.py is outside this plan's files.
- So `locate.load_inputs` is the seam for both verbs, and the tests monkeypatch it.
- `asmclass.classify` takes a `library=` override, so synthetic tests need no real unit names.

**4. Refactor commit `0cb5b89`**
- The acceptance check greps the literal `GET_TEXT = {`. The first GREEN annotated the name.

**5. The asm list row set is tool-owned**
- A listed row the detector no longer proposes is removed and reported ("removed"). This follows `ASM_COMMENT`: the tool owns exe, address and evidence.
- This loses that row's verdict. It cannot pass silently: any write changes the list's bytes, which breaks the `[asm_list]` sign-off, and `mechanics write`/`check` then refuse until the owner re-signs.

---

**Total deviations:** 2 orchestrator rulings applied, plus 1 Rule 1, 1 Rule 2, 1 Rule 3 and 1 refactor commit.

**Impact:** the GET_TEXT count follows the spike's measurement instead of the plan's stale "50". No scope creep.

## Differences to report

**get_text recovery.** UFO2P has 735 full sites, against spike q4's 742.
- The spike also tracked registers pinned once per row and stack slots.
- This plan recovers per basic block, as the plan words it: "the last `mov eax/edx, imm` or `xor reg, reg` in the basic block".
- That leaves 7 UFO2P sites index-only: their section comes from a register set before the block.
- TACP is identical to the spike (255 / 315).

**Table lead-in (for 07-22).** `callgraph.py`'s strict table rule is unchanged, as instructed. `locate.table_refs` uses exactly the range the caller gives.
- Spike q6 needed references up to 64 bytes before a run's first slot (a record lead-in) to reproduce research's reach (UFO2P 1,471, 10 / 8 referenced runs). The strict rule gives 1,429 (3 / 2 runs).
- A reader can find a run's lead-in referrers today with `mechanics locate --range <first slot - 0x40> <end of run>`.
- Plan 07-22 decides the rule with the owner.

**`int386_` 0x1A callers.** The callers match research and q1's "immediate in block" readers exactly. UFO2P `func_00010940`, which passes 0x1A through a register set once per row (q1's "pinned" reader), is not reported. That is by design: the tracker does not guess values set before the block.

**asm reason cells (07-20).** `mechanics.read_asm_list` caps reasons at 120 characters (the 07-10 note). The detector writes empty reasons; the owner's reasons must stay within the cap.

## Issues Encountered

- The worktree harness refused compound shell commands that write into the `.git/worktrees/...` directory. So the commit ledger file of protocol 0c could not be written.
- The base is taken from the dispatch's expected base, `7469bf1`. The commit count, 7, is measured with `git rev-list --count 7469bf1..HEAD`.

## Verification

Plan `<verify>` commands, all green:
- `uv run pytest -q tests/test_locate.py`: 28 passed, 8 skipped (no orig/ in the worktree).
- With `REVERSEAPOC_ORIG=<main>/orig`: `tests/test_locate.py` and `tests/test_asmclass.py` give 55 passed.
- Full host suite `uv run pytest -q`: 3046 passed, 246 skipped, 0 failed.
- `uv run ruff check .`: all checks passed.

New skips:
- **Reason:** `orig/<EXE> not present (run uv run reverseapoc ingest or set REVERSEAPOC_ORIG)`. That is the same text as 07-10's `test_mechanics_real.py`.
- **Count:** 10 in total. `test_locate.py` has 8 and `test_asmclass.py` has 2.
- **In the container:** they run there only if orig/ is mounted. Otherwise they skip like every existing orig/ test.
- **R-A:** this orig/ reason is not in its F2 list. It follows the existing real-file convention (rules/tools.md: "real-file tests skip unless `orig/` is present").

Acceptance checks:
- `mechanics locate --help` lists `--string`, `--va`, `--range`, `--get-text` and `--int`.
- `mechanics asm --help` lists `--write`.
- locate.py contains `GET_TEXT = {` and `def get_text_sites(`.
- asmclass.py contains `def classify(` and `def merge(`.

**Container step deferred to the orchestrator:** `docker compose build && docker compose run --rm test`.

## User Setup Required

None.

## Known Stubs

None. The RED stubs were replaced in each GREEN commit.

## Next Phase Readiness

- 07-20 can run `uv run reverseapoc mechanics asm --write`, review the proposal with the owner, then sign `[asm_list]` with `asm_list_sha256`.
- 07-22, 07-25, 07-28 and 07-32 can cite `mechanics locate` commands as the evidence of each `[[entry]]`.

## Self-Check: PASSED

- All four created files exist; cli.py is modified.
- Commits `57a1f73`, `0827206`, `f00ced7`, `d2b4631`, `0cb5b89`, `86eb805` and `dc35f31` are on this branch.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
