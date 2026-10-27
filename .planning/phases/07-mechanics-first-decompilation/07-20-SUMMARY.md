---
phase: 07-mechanics-first-decompilation
plan: 20
subsystem: data
tags: [mechanics, asm-list, d-23, dec-01, dec-03, sign-off]

requires:
  - phase: 07-mechanics-first-decompilation
    provides: "07-10 mechanics.py (load, asm_list_sha256, read_asm_list, check_committed, the `mechanics check` verb); 07-12 asmclass.py and `mechanics asm --write`"
provides:
  - "config/asm-functions.csv: the owner-signed D-23 asm list (435 rows; UFO2P 125 asm / 93 unclear, TACP 120 asm / 97 unclear)"
  - "config/mechanics.toml: `schema = 1` and the signed `[asm_list]` (signed_off_by, signed_off_date, list_sha256)"
affects: [07-22, 07-25, 07-28, 07-32, 07-15, 07-39, 07-41]

actuals:
  tokens: 5800
  tasks: 3
  commits: 1

tech-stack:
  added: []
  patterns:
    - "Generated list with owner-owned verdict/reason cells; a sign-off hash that `mechanics check` re-verifies in CI"

key-files:
  created:
    - config/asm-functions.csv
    - config/mechanics.toml
  modified: []

key-decisions:
  - "Owner ruling (2026-10-27): sign-with-changes by ayrtondenner. All 34 TACP u_000c483f rows flip unclear -> asm (vendor sound C wrapper, other compiler; matches UFO2P u_000c1b4b); every other row as proposed"
  - "Rows the owner did not mark asm stay `unclear` and stay in the C queue (D-23)"

patterns-established:
  - "Owner reasons are written `owner YYYY-MM-DD: <their words>`; executor notes are written `spot-check: <our own words>`; both stay within the 120-character cap"

requirements-completed: [DEC-01, DEC-03]

coverage:
  - id: D1
    description: "The asm list generated from the user's own EXEs, with evidence tags, proposed verdicts and spot-check notes (6 UFO2P, 5 TACP)"
    requirement: DEC-01
    verification:
      - kind: integration
        ref: "uv run pytest -q tests/test_asmclass.py (real drift test included; 19 passed, 0 skipped on main)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The owner's verdicts on the list (D-23)"
    requirement: DEC-03
    verification: []
    human_judgment: true
    rationale: "Only the owner decides which rows leave the must-match sets; the ruling is quoted verbatim below and in commit ccff87e"
  - id: D3
    description: "The signed [asm_list] in config/mechanics.toml, checked by `mechanics check`"
    requirement: DEC-01
    verification:
      - kind: other
        ref: "uv run reverseapoc mechanics check (mechanics: no problems)"
        status: pass
      - kind: unit
        ref: "uv run pytest -q tests/test_mechanics.py tests/test_asmclass.py (77 passed)"
        status: pass
      - kind: other
        ref: "uv run python -I tools/progress.py --out build/gate/07-evidence/20-site (exit 0)"
        status: pass
    human_judgment: false

duration: 24min
completed: 2026-10-27
status: complete
plan_head_before: aaa81213cfcc46c1f9028bfa077e5ce67b41d9c3
plan_head_after: ccff87efab1ea4ae341771dd627ccbe0a7f28b66
---

# Phase 7 Plan 20: The D-23 asm list, signed off Summary

**The owner signed the D-23 asm list on 2026-10-27, with one change. `config/asm-functions.csv` holds 435 detector rows: UFO2P 125 asm / 93 unclear, TACP 120 asm / 97 unclear, after the owner flipped TACP's 34-row vendor sound C wrapper unit to asm. `config/mechanics.toml` records the sign-off: signer, date and the list's LF SHA-256. `mechanics check` re-verifies it in CI.**

Execution context nonce: 1dbb74bac9b90928

## Performance

- **Duration:** about 24 min of work, over two dispatches:
  - Task 1: 2026-10-27T18:52:52Z to 18:57:42Z, then the checkpoint;
  - Task 3: resumed after the owner's ruling, committed `ccff87e`, then a 14-minute host suite.
- **Tasks:** 3. Task 1 was the tracer, Task 2 the owner's checkpoint, Task 3 the sign-off.
- **Files:** 2 created.

## The owner's ruling (Task 2, verbatim as relayed)

> sign-with-changes by ayrtondenner (2026-10-27): TACP u_000c483f — flip every row of this unit (34 rows, currently unclear) to asm, reason "vendor sound C wrapper, other compiler; matches UFO2P u_000c1b4b". Every other row as proposed (UFO2P u_000c1b4b stays asm).

## Accomplishments

- **Running the detector.** `uv run reverseapoc mechanics asm --write --json` ran on the main checkout. The evidence is in the gitignored `build/gate/07-evidence/20-asm.json`. Totals: 435 rows, 211 proposed asm and 224 unclear, matching 07-12's measurement.
- **Spot-checks.**
  - I read rows from the gitignored listings (`reverseapoc asm UFO2P.EXE`: 1892 listings; `TACP.EXE`: 1874).
  - I wrote `spot-check:` notes in our own words, with no instruction text.
  - Final count: 6 UFO2P (2 unclear) and 5 TACP (2 unclear). See deviation 2 for the TACP count.
- **Owner summary.** `build/gate/07-evidence/20-asm-summary.txt` (gitignored) holds:
  - per-EXE verdict and tag counts;
  - rows per unit;
  - the library spans;
  - every unclear address;
  - the spot-check notes.
- **The owner's change.** 34 TACP rows in u_000c483f (0x000C483F-0x000C75F5) went from unclear to asm. Each reason reads `owner 2026-10-27: vendor sound C wrapper, other compiler; matches UFO2P u_000c1b4b` (82 characters, so not shortened).
- **The sign-off.** `[asm_list]`:
  - signed_off_by = "ayrtondenner"
  - signed_off_date = 2026-10-27
  - list_sha256 = `0f7093230df88290a923c0fdaf3eb8ec04b1916843b3692a493a847722790c09`, the value of `mechanics.asm_list_sha256`.

Final list:

| | UFO2P | TACP |
|---|---|---|
| rows | 218 | 217 |
| asm / unclear / c | 125 / 93 / 0 | 120 / 97 / 0 |
| asm by library span | 99 | 9 |
| asm by the owner's ruling | 0 | 34 (u_000c483f) |
| spot-check notes | 6 | 5 |

## Task Commits

1. **Task 1 (tracer): generate, spot-check, summarise.**
   - No commit, by ruling F38: both files stayed uncommitted until the ruling.
   - Tracer gate: the run was interactive in end-of-phase mode with an automated-only verify, so I re-ran it. It was green.
2. **Task 2: the owner's ruling.** A checkpoint; nothing to commit.
3. **Task 3: record the sign-off.** `ccff87e`: `data(07-20): asm list signed off by ayrtondenner (D-23)`. It contains exactly config/asm-functions.csv and config/mechanics.toml, and the body quotes the ruling.

## Files Created/Modified

- `config/asm-functions.csv`: 435 rows of exe, address, evidence, verdict and reason. Addresses, tags, verdicts and short notes only.
- `config/mechanics.toml`: a comment header (our own words, from mechanics.py's docstring; 07-10's plan has no ready-made header), `schema = 1` and `[asm_list]`.

## Decisions Made

- The owner's ruling above. The owner also kept UFO2P u_000c1b4b as asm, so the two copies of the sound library's C wrapper now agree.
- The executor changed no verdict. The detector's 211 asm verdicts stand, plus the owner's 34.

## Deviations from Plan

**Orchestrator ruling F38:** Task 1 did not commit `data(07-20): propose the asm list`.
- Both files stayed uncommitted until the owner ruled. Task 3 then committed them in one commit.
- So the Task 1 acceptance item "`git status --porcelain` is empty after the commit" read instead as: dirty only with those two files plus R-C's ` M .planning/config.json`.
- Main was never red. While the files were uncommitted, `mechanics check` and `test_committed_mechanics_check` failed in the working tree only, as F38 expects.

**Orchestrator ruling F2:** Task 3's verify also ran `uv run python -I tools/progress.py --out build/gate/07-evidence/20-site`.
- It exited 0 with the schema plus `[asm_list]` toml and no members file.
- It wrote index.html, progress.json, progress.svg and the shields under the gitignored build/.

**Orchestrator note (07-10 as built): reasons are capped at 120 characters.**
- Every spot-check note is at most 113 characters. The owner's reason is 82.
- Both scripts asserted the cap before writing, and `read_asm_list` re-read the file after each write.

**1. [Rule 2 - Missing critical] A fifth TACP spot-check after the owner's flip**
- **Found during:** Task 3.
- **Issue:** two TACP spot-check rows lie inside u_000c483f: 0x000C483F, and 0x000C6287 (the pilot row). The owner's instruction replaced their notes with the owner reason. That left TACP with 4 spot-check notes, below the plan's minimum of five per EXE.
- **Fix:** I added a note to TACP 0x00028C98, a row the ruling does not touch: "a 7-byte byte-copy loop on a counted-loop instruction Watcom does not emit; in the VESA unit; looks asm". Its verdict stays unclear, as the ruling ("every other row as proposed") requires.
- **What the replaced notes said** (they are in the Task 1 checkpoint report):
  - 0x000C483F: empty body, compiler output.
  - 0x000C6287: compiler-like, the pilot capped at 61.87%.
- **Files modified:** config/asm-functions.csv.
- **Verification:** the script asserted that no exe, address, evidence or verdict changed. The list reads back clean.
- **Committed in:** `ccff87e`.

**2. Plan text "Run the asm drift real test"**
- This ran in Task 1 inside `tests/test_asmclass.py` against the main checkout's orig/: 19 passed, 0 skipped.
- It ran again in Task 3 with the owner's verdicts. The merge keeps hand verdicts, so there was no drift.

---

**Total deviations:** the 3 orchestrator rulings and notes applied (F38, F2, the 120-character cap), plus 1 Rule 2 fix.
**Impact:** the list and the sign-off are as planned. No scope creep.

## Issues Encountered

**Observations for 07-22 and later. These are heuristics; nothing was changed for them.**
- Many `unclear` rows do not look like functions. A rough classification of the listings (before the owner's flip):
  - UFO2P's 93: 8 data-like, 4 jump or pointer tables, 50 starting mid-body (case arms, tails), 31 with a push-style start.
  - TACP's 131: 27 data-like, 3 tables, 45 mid-body, 56 push-style.
  - Examples: UFO2P 0x000129F3 is text in the code section. UFO2P 0x0009D1DB is one of 15 case-arm tails. The TACP u_00029340 rows are a text table.
- They stay in the C queue, where they cannot match as functions. A functions.csv re-cut or a new verdict would be the remedy; neither is in this plan's scope.
- The verdict counts in this summary come from the committed file. The heuristic breakdown is not committed anywhere.

**Host suite, run once on main after `ccff87e` (no container):**
- `uv run pytest -q`: 3315 passed, 38 skipped.
- `uv run ruff check .`: All checks passed.
- The skips are the existing F2-allowed reasons:
  - objdiff-cli, ninja, clang and Ghidra (each "run in the container");
  - POSIX-only;
  - Windows file names;
  - non-UTF-8 byte names;
  - symlink privileges;
  - only inside the container.
- No new skip reason. The orig/ real tests ran, because orig/ is present on main.

**Container step deferred to the orchestrator** (R-B): `docker compose build && docker compose run --rm test`.

## User Setup Required

None.

## Known Stubs

None.

## Threat Flags

None. T-07-58 is mitigated as planned:
- the blocking-human ruling;
- `list_sha256` recorded, with `mechanics check` failing on any later change.

T-07-59 is mitigated: the notes are in our own words, with no instruction text, no function names and no game strings.

## Next Phase Readiness

- 07-22 can compute Tier 1's must-match set. `mechanics.signed_asm` now returns the 245 asm rows (125 UFO2P, 120 TACP), and `mechanics write` no longer refuses an unsigned list.
- Any later `mechanics asm --write` that changes the file breaks the sign-off. `mechanics check` then asks for a re-sign of `[asm_list]`.

## Self-Check: PASSED

- config/asm-functions.csv, config/mechanics.toml and this SUMMARY exist.
- Commit `ccff87e` is on HEAD (`git rev-list --count aaa8121..HEAD` = 1 before this SUMMARY's commit).
- `mechanics check` reports no problems, and 77 mechanics and asm tests pass.

---
*Phase: 07-mechanics-first-decompilation*
*Completed: 2026-10-27*
