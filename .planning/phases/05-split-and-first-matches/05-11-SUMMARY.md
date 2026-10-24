---
phase: 05-split-and-first-matches
plan: 11
subsystem: tooling
tags: [capstone, x86, asm-listings, scorer, p16-filter, cli]

requires:
  - phase: 05-split-and-first-matches
    provides: "05-03 x86.decode/Insn (raw, rel32_field, data_sites); 05-04 FunctionRow, functions/symbols.csv readers, SymbolTable (c_name, linker_name, address_of, containing)"
provides:
  - "tools/reverseapoc/asm.py: walk (instructions, inline fixup data, raw bytes), listing, select_rows, write_listings, AsmReport, AsmError, FixupIndex, data_ranges, target_name"
  - "tools/reverseapoc/score.py: Features, features, rejections, score (KKND weights), Candidate, assess, candidates, rank, ScoreReport, ScoreError"
  - "`reverseapoc asm EXE [--orig] [--manifest] [--functions] [--symbols] [--out] [--only ADDR] [--json]`"
  - "`reverseapoc score EXE [--orig] [--manifest] [--functions] [--symbols] [--top N] [--json]`"
affects: [05-16, 05-18, 05-19, first-match-selection, asm-listings]

actuals:
  tokens: 13100
  tasks: 2
  commits: 4
plan_head_before: 532a74582239727dd92c0ee200d1d3e8d81b87cf
plan_head_after: f60f88058ce037f966187a4bd252313ac92e1c39

tech-stack:
  added: []
  patterns:
    - "One walker (asm.walk over x86.decode, LE fixup sites at instruction starts as data) feeds both the listings and the scorer"
    - "Fixup operands are found by the raw (object-relative) field value in capstone's text and replaced by the name of le.fixups() target_va; an unmatched field becomes a `; <kind> -> <name>` note, never a raw address"
    - "Split verbs share _split_inputs (manifest-checked EXE, functions.csv, symbols.csv, SymbolTable with LE data ranges)"

key-files:
  created:
    - tools/reverseapoc/asm.py
    - tools/reverseapoc/score.py
    - tests/test_asm.py
    - tests/test_score.py
  modified:
    - tools/reverseapoc/cli.py

key-decisions:
  - "KKND weights taken verbatim from score_functions.py @ 4dfd5b10: size + 12/call + 80/cs: operand + 40/x87 insn + 30/D_ ref + 20 ret N + 200 retf/iretd + 100 no push ebp frame; ranking key is (__CHK prologue, score, address)"
  - "A fixup target is code when it lies in a functions.csv row that is not data-in-code (jump table); anything else is data, and a data target whose _D_ name does not resolve fails data_exact"
  - "Straddling fixup = a field crossing a 4 KiB LE page or the row's own boundary"
  - "The push ebp frame test skips a leading push imm32; call __CHK pair; __CHK addresses come from rows named __CHK and the runtime public of that name"
  - "runtime_starts come from the committed runtime.csv when present; any row whose kind is not game is rejected as well"

patterns-established:
  - "asm listings: `# <name>  0xSTART..0xEND  N bytes, kind`, then `  0xVA  mnemonic operands`, `.LXXXXXXXX:` labels for local jumps, `dd <symbol>` for inline fixup data, `db 0xNN` for undecodable bytes"

requirements-completed: [SPL-05]

coverage:
  - id: D1
    description: "asm verb writes one symbolic Intel listing per functions.csv row into <out>/<exe stem>/, prints one summary line, refuses an output inside orig/"
    requirement: SPL-05
    verification:
      - kind: unit
        ref: "tests/test_asm.py#test_asm_verb_writes_listings"
        status: pass
      - kind: unit
        ref: "tests/test_asm.py#test_refuses_out_in_orig"
        status: pass
      - kind: unit
        ref: "tests/test_asm.py#test_listing_names_call_and_data_operands"
        status: pass
      - kind: unit
        ref: "tests/test_asm.py#test_inline_data_line"
        status: pass
      - kind: other
        ref: "git check-ignore -q asm/ufo2p/func_00010000.s (rc 0)"
        status: pass
    human_judgment: false
  - id: D2
    description: "asm --only ADDR lists the row containing ADDR and refuses an address in no row (ruling F3)"
    verification:
      - kind: unit
        ref: "tests/test_asm.py#test_only_lists_the_row_containing_the_address"
        status: pass
      - kind: unit
        ref: "tests/test_asm.py#test_only_refuses_an_address_in_no_row"
        status: pass
      - kind: unit
        ref: "tests/test_asm.py#test_asm_verb_only"
        status: pass
    human_judgment: false
  - id: D3
    description: "P16 filter with a named reason per case (runtime, jump table, string, straddler, non-off32 fixup, no call, no absolute fixup, call target, data exactness) and KKND easiest-first ranking"
    verification:
      - kind: unit
        ref: "tests/test_score.py -k 'filter or rank or features'"
        status: pass
    human_judgment: false
  - id: D4
    description: "score verb prints candidates as address, name, size, score, reasons only (JSON and text)"
    verification:
      - kind: unit
        ref: "tests/test_score.py#test_score_verb"
        status: pass
      - kind: unit
        ref: "tests/test_score.py#test_score_verb_text"
        status: pass
    human_judgment: false
  - id: D5
    description: "Quality of the easiest-first pick on real Watcom game code (research A5)"
    verification: []
    human_judgment: true
    rationale: "Real rankings need the committed functions.csv from 05-09; plan 05-18 produces and judges them"

duration: 9min
completed: 2026-10-24
status: complete
---

# Phase 5 Plan 11: asm listings and the P16 scorer Summary

**`reverseapoc asm` writes symbolic per-function Intel listings into the gitignored asm/ tree, and `reverseapoc score` applies the P16 filter (plus ruling F11) and ranks survivors easiest-first with the KKND weights. Both read the same instructions through one walker over x86.decode and name every operand through SymbolTable.**

Execution context nonce: b71f353e8c66840c

## Performance

- **Duration:** about 9 min
- **Started:** 2026-10-24T00:56:38Z
- **Completed:** 2026-10-24T01:05:04Z
- **Tasks:** 2
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments

- asm.py: `walk` gives instructions, inline data and raw bytes. An LE fixup site at an instruction start becomes a `DataItem` and decoding resumes after it. `listing` names call and jump destinations through `SymbolTable.c_name`: a row start by its name, a mid-row address as name+offset, a local jump as a `.L` label. A fixup operand is named after its `target_va`. The raw object-relative field is used only to find the operand text (Pitfall 1). `write_listings` writes each file atomically.
- score.py: `features` reads size, direct calls, call-target nameability, D_ references, data exactness, jump table, string reference, straddler, non-off32 fixups, __CHK prologue, x87, ret N, far return, push ebp frame and cs: operands. `rejections` names every P16 reason. `score` uses the KKND weights. `rank` and `ScoreReport` order by (__CHK, score, address).
- cli.py: the `asm` and `score` verbs share `_split_inputs`, which loads the manifest-checked EXE, functions.csv, symbols.csv and the SymbolTable with the LE data ranges. `asm` refuses an output inside orig/ or the Watcom tree. Both verbs print counts, addresses and names only. The 05-02 `omf2elf` verb is unchanged.
- Smoke run on the real UFO2P.EXE, counts only, with crude rows (direct call targets of a linear decode): `assess` and the listings ran without error. 12 of about 35k named operands fell back to a `; kind -> name` note, which supports the Pitfall 1 premise (the raw field equals the target offset).

## Task Commits

1. **Task 1 (tracer): `reverseapoc asm` writes a symbolic listing for a synthetic EXE into asm/** - RED `b933e9b` (test), GREEN `c0f9bae` (feat)
2. **Task 2: the P16 filter, the easiest-first score and the `score` verb** - RED `2b720c5` (test), GREEN `f60f880` (feat)

Tracer gate (Task 1): interactive, `human_verify_mode` end-of-phase, automated-only verify. Both verify commands were re-run and passed: `uv run pytest -q tests/test_asm.py`, and `asm --help` holds `--only`. Expansion then went ahead.

## TDD notes

Both RED commits failed at import because the new module did not exist yet. That is the normal first RED for a new Python module. The plan is `type: execute` and `workflow.tdd_mode` is off, so the tdd-red-evidence classifier gate does not apply. One assertion failed inside GREEN: a data target past the data object was classified as a jump table. That failure drove the code/data classification rule below.

## Files Created/Modified

- `tools/reverseapoc/asm.py`: listings, walker, fixup index, `--only` row selection
- `tools/reverseapoc/score.py`: features, P16 rejections, KKND score, ranking, report
- `tools/reverseapoc/cli.py`: `asm` and `score` verbs, `_split_inputs`, and FunctionsError, SymbolError, AsmError and ScoreError registered in `_ERRORS`
- `tests/test_asm.py`: 8 synthetic tests
- `tests/test_score.py`: 19 synthetic tests

## Decisions Made

See key-decisions in the frontmatter. The KKND weights were read from score_functions.py at the pinned commit (CC0). Both new files carry the KKND derivation header on line 1.

## Deviations from Plan

**Orchestrator ruling F11: the P16 filter excludes any function with a non-off32 LE fixup.** `Features.other_fixups` counts them, and `rejections` names `non-off32 fixup`. Test: `test_filter_rejects_a_non_off32_fixup` (a sel16 site). Commit `f60f880`.

**Orchestrator ruling F3: `asm --only ADDR` lists the row that CONTAINS ADDR** through `SymbolTable.containing`. It refuses only when no row contains the address (`AsmError: no functions.csv row contains 0x...`). Tests: `test_only_lists_the_row_containing_the_address`, `test_only_refuses_an_address_in_no_row`, `test_asm_verb_only`. Commit `c0f9bae`.

### Auto-fixed Issues

**1. [Rule 1 - Bug] A data target outside every data object was read as a jump table**
- **Found during:** Task 2 (GREEN)
- **Issue:** A first rule ("not in a data object, so code") put an off32 target past the data object's end under `jump table`, so the `data_exact` check never ran.
- **Fix:** A target is code only when a functions.csv row (not data-in-code) contains it. Every other target is data, and `data_exact` requires its `_D_` name to resolve back to it.
- **Files modified:** tools/reverseapoc/score.py
- **Verification:** `test_filter_rejects_a_data_target_in_no_data_object`, `test_filter_rejects_a_jump_table`
- **Committed in:** `f60f880`

**2. [Rule 1 - Bug] Quadratic fixup scan per instruction in `listing`**
- **Found during:** Task 2 (smoke run on real UFO2P, counts only)
- **Issue:** Each instruction scanned every fixup near its row.
- **Fix:** Each instruction now looks up only the field addresses that can overlap it. The full-object listing time fell from 19.8 s to 8.0 s.
- **Files modified:** tools/reverseapoc/asm.py
- **Committed in:** `f60f880`

**3. Signature and key-link notes (no behaviour beyond the plan)**
- `features()` has no `functions` parameter: `SymbolTable` already holds the rows. Two keyword arguments were added: `page_size` (straddler pages) and `chk_targets`. `Features` also has `other_fixups` (F11) and `far_return` (the KKND retf/iretd weight).
- score.py does not call `decode(` directly. It reads instructions through `asm.walk`, which calls `x86.decode` with the LE fixup sites as data, so the listing and the scorer cannot disagree on instruction boundaries. The plan's key-link grep `decode\(` on score.py therefore does not match. The link holds through asm.walk.
- `rank` and `assess` also take `runtime_starts`. The CLI reads them from the committed runtime.csv when it exists, and every row whose kind is not game is rejected as well.

---

**Total deviations:** 2 orchestrator rulings applied, 2 auto-fixed (both Rule 1), plus the signature notes above.
**Impact on plan:** No scope creep. The rulings and fixes are needed for correctness.

## Issues Encountered

None.

## Known Stubs

None.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- 05-18 can run `uv run reverseapoc score UFO2P.EXE` and `asm` once 05-09 has committed config/<exe>/functions.csv. Neither verb has run on a real functions.csv yet.
- 05-16 can use `asm --only ADDR` on addresses that are not row starts.
- The SymbolTable is built without runtime aliases (they need LIB386). Calls land on row starts, and those resolve by row name, so the scorer does not need aliases.

---
*Phase: 05-split-and-first-matches*
*Completed: 2026-10-24*

## Self-Check: PASSED

## Review fixes (round 1)

**Important: `_branch_target` was duplicated in score.py.** asm.py now holds the only copy, as the public `branch_target(insn, fixups)`. score.py imports it with the other asm helpers, and its copy is gone. Behaviour is unchanged. Commit `03af90b`.

Commands and output:
- `uv run pytest -q tests/test_asm.py tests/test_score.py`: `27 passed in 0.93s`
- `uv run pytest -q`: `1027 passed, 177 skipped in 13.80s`
- `uv run ruff check .`: `All checks passed!`
