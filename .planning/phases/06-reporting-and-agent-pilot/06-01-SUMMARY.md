---
phase: 06-reporting-and-agent-pilot
plan: 01
subsystem: agent-layer
tags: [decomp.wtf, fork-mode, spike, wsl2, agt-10]

requires: []
provides:
  - "Spike 006 record (.planning/spikes/006-decompwtf-fork-stub/README.md) with verdict INVALIDATED"
  - "Two stdlib claim checkers over the pinned decomp.wtf v0.10.6 source, each of which can fail (--plant)"
  - "MANIFEST idea reporting-and-agent-pilot and row 006; docs/tools.md decomp.wtf row records the result"
  - "AGT-10 branch fixed for the rest of Phase 6: the own agent layer (D-03, D-04)"
affects: [06-reporting-and-agent-pilot, phase-7-claims, docs/tools.md]

actuals:
  tokens: 9000
  tasks: 2
  commits: 2
plan_head_before: 021a58ba7441665b1eb5486caef92c91f23ad9c2
plan_head_after: b3b4636a0b8118f57ac88bb004656f029195b7b0

tech-stack:
  added: []
  patterns:
    - "Third-party source read as untrusted text: Path.read_text + ast.parse, f-string patterns rebuilt from literal parts, never imported"

key-files:
  created:
    - .planning/spikes/006-decompwtf-fork-stub/README.md
    - .planning/spikes/006-decompwtf-fork-stub/stub_regex.py
    - .planning/spikes/006-decompwtf-fork-stub/linker_name.py
  modified:
    - .planning/spikes/MANIFEST.md
    - docs/tools.md

key-decisions:
  - "Spike 006 verdict INVALIDATED (D-02): unpatched fork mode stops at its own setup (auto False) and at check (no objdiff.json), registers no function, so compile_and_diff answers 'no function'; no build in WSL2 (ninja, wibo, objdiff-cli missing)"
  - "Even with a build, the code evidence refuses the submission: _names spells the function func_X_ (objdiff's name), the C finder needs func_X(, and the _stub regex misses bare INCLUDE_ASM(func_X); so _attempt writes it through _insert_in_order (stub kept), and marker plus definition is what configure.check_unit_source refuses"
  - "Phase 6 uses the own agent layer (D-03, D-04); decomp.wtf is re-evaluated for Phase 7 claims (DEC-02/DEC-06)"

patterns-established:
  - "Spike claim checkers over third-party code: ast-only extraction, cross-checked against the repo's own configure.py loaded by path"

requirements-completed: []  # AGT-10 partial (spike only); 06-20, 06-21 and 06-27 also carry AGT-10

coverage:
  - id: D1
    description: "stub_regex.py: bare INCLUDE_ASM(func_X); is not found by decomp.wtf's _stub, the quoted form is, class [\"/,\\s]; none of the 12 repo markers is found; --plant fails"
    requirement: AGT-10
    verification:
      - kind: other
        ref: "uv run python .planning/spikes/006-decompwtf-fork-stub/stub_regex.py build/spike006/src/decomp.wtf-0.10.6/ (ALL PASS, exit 0; --plant: 1 FAILED, exit 1)"
        status: pass
    human_judgment: false
  - id: D2
    description: "linker_name.py: func_X_ lookup vs func_X( finder, _CHEAT on submissions only, _attempt inserts through _insert_in_order with the stub kept (planted control refused, csource.replace unused), configure refuses marker+definition; --plant fails"
    requirement: AGT-10
    verification:
      - kind: other
        ref: "uv run python .planning/spikes/006-decompwtf-fork-stub/linker_name.py build/spike006/src/decomp.wtf-0.10.6/ (ALL PASS, exit 0; --plant: 1 FAILED, exit 1)"
        status: pass
    human_judgment: false
  - id: D3
    description: "WSL2 smoke run recorded and the D-02 verdict INVALIDATED with the D-03 consequence in README, MANIFEST and docs/tools.md"
    requirement: AGT-10
    verification:
      - kind: other
        ref: "grep verdict/compile_and_diff/| 006 /### reporting-and-agent-pilot; grep Spike 006 docs/tools.md; uv run pytest -q tests/test_hygiene.py"
        status: pass
    human_judgment: true
    rationale: "The verdict is a recorded judgement against D-02's scale (edge probe AGT-10 stays unresolved per the plan); the smoke run was executed by the orchestrator, not by this executor"

duration: 20min
completed: 2026-10-24
status: complete
---

# Phase 6 Plan 01: decomp.wtf fork-mode spike (006) Summary

**Spike 006: INVALIDATED. Unpatched decomp.wtf v0.10.6 fork mode clones the repo and then stops at its own setup with no objdiff.json, so no build runs in WSL2 (ninja, wibo and objdiff-cli are missing). The code evidence shows a submission would be refused even with a build: fork mode spells the function func_X_, its stub regex misses `INCLUDE_ASM(func_X);`, and `_insert_in_order` would add the definition with the stub kept, which the D-12 check refuses. Phase 6 uses the own agent layer.**

## Performance

- **Duration:** about 20 min of executor time. The checkpoint wait for the orchestrator's WSL2 run is not counted.
- **Started:** 2026-10-25T01:06:42Z
- **Completed:** 2026-10-25T01:26:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Pinned tarball `https://github.com/i12bp8/decomp.wtf/archive/refs/tags/v0.10.6.tar.gz`, sha256 `0eb7bddd809217222664509bd51c5ebc2be10864d361baeacb521cb49ce11b86`. It is extracted only under the gitignored `build/spike006/` and read as text.
- `stub_regex.py` prints ALL PASS. `_stub`'s class before the name is `[\"/,\s]`, so `INCLUDE_ASM(func_000A34F0);` does not match and the quoted form does. None of the 12 INCLUDE_ASM markers under `src/` is found.
- `linker_name.py` prints ALL PASS on 14 claims (10 originally, 13 after fix round 1):
  - `_names` ends with `meta["symbol"]`, which is objdiff's `f["name"]`, here `func_000A3980_`, and nothing strips the underscore.
  - `csource.find("func_000A3980_")` misses `int func_000A3980(void) {`.
  - `_attempt` raises when the submission has no span.
  - `_CHEAT.search` runs only on `source` in `_attempt` and on `new` in `edit_file`.
  - With no span in the unit file, `_attempt` calls `_insert_in_order`, which inserts the definition with the stub kept. All 3 of its returns keep all of the file text. A planted return that drops the span is refused, and nothing calls `csource.replace`.
  - Our `check_unit_source` returns `func_000A3980 is both defined in C and marked INCLUDE_ASM`.
- Smoke-run failure, quoted verbatim from `build/spike006/smoke.log`:
  - `STEP setup: ERROR NetworkError: this project has its own setup: follow its README, then click Check again`
  - `STEP check: ERROR NetworkError: no objdiff.json yet. The project's build creates it (often `python configure.py` or `make`); see its README`
  - `STEP compile_and_diff: OK error: no function 'func_000A3980' in 'reverseapoc'`. The same answer comes back for `func_000A3980_`.
- WSL2 tools: ninja, wibo and objdiff-cli are MISSING. uv, claude and git are present. D-01 expected claude to be missing; it is not.

## Task Commits

1. **Task 1: Tracer, the D-01 code claims through two claim checkers** - `f0f79ea` (test)
2. **Task 2: WSL2 smoke run, D-02 verdict, MANIFEST row, docs/tools.md result** - `b3b4636` (docs)

## Files Created/Modified

- `.planning/spikes/006-decompwtf-fork-stub/stub_regex.py`: the stub-regex claim checker (`SRC [--plant]`).
- `.planning/spikes/006-decompwtf-fork-stub/linker_name.py`: checks the linker-name, `_CHEAT`, `_attempt`/`_insert_in_order` (stub kept) and configure.py claims (`SRC [--plant]`).
- `.planning/spikes/006-decompwtf-fork-stub/README.md`: the spike record, with `verdict: INVALIDATED`.
- `.planning/spikes/MANIFEST.md`: the `### reporting-and-agent-pilot` idea entry and the `| 006 |` row.
- `docs/tools.md`: the decomp.wtf row now records the spike 006 result and the D-03 consequence. Its status column reads "Phase 6: not used (spike 006); re-evaluated in Phase 7".

## Decisions Made

- The verdict is INVALIDATED and rests only on D-02's "no build in WSL2" clause. The two patches the code evidence points to, the stub regex and the `name_` to `name` lookup, are exactly the patches D-02 lists for PARTIAL. They were not written or sized here; sizing them is left for the Phase 7 re-evaluation (D-03). D-03 treats PARTIAL like INVALIDATED for the pilot in any case.
- The smoke driver calls the same `tools.call` handlers that `decomp mcp` dispatches to, without the stdio transport. v0.10.6 has no CLI for `compile_and_diff`; fork mode is reached through the GUI API or MCP.

## Deviations from Plan

**1. [Rule 3 - Blocking] The orchestrator ran the WSL2 smoke run, with the owner's authorization**
- **Found during:** Task 2
- **Issue:** the worktree isolation guard refuses every `wsl` call from the executor.
- **Fix:** the executor wrote `build/spike006/smoke_wsl.sh` (gitignored, sha256 `8a50e8d18849f053346a63ada8c379ae111161ae0ae14fbf4267e8faca1d055a`) and returned a checkpoint. The orchestrator ran `MSYS_NO_PATHCONV=1 wsl -d ubuntu-recovered -- bash -l /mnt/c/.../build/spike006/smoke_wsl.sh > build/spike006/smoke.log 2>&1` once from the main session, with exit 0. A first attempt without `MSYS_NO_PATHCONV=1` failed before the script started, because Git Bash rewrote the `/mnt/c` path. The verdict rests only on the log and the Task 1 evidence.
- **Commit:** b3b4636

**2. [Rule 3 - Blocking] The verify lines containing `$(...)` were run with literal paths**
- **Found during:** Task 1
- **Issue:** the harness refused the plan's `SRC="$(ls -d build/spike006/src/*/ | head -n 1)" && ...` commands.
- **Fix:** I ran the same steps with `build/spike006/src/decomp.wtf-0.10.6/` and the same redirections to `build/spike006/*.out`, with the same exit and grep checks.

**3. [Rule 2 - Missing critical] Added a repo-markers claim to stub_regex.py and a planted failure for linker_name.py**
- The `repo-markers` claim runs the rebuilt `_stub` against every real marker under `src/`.
- linker_name.py's `--plant` flips `finder-linker-name`. It printed `1 FAILED` and exited 1, so both checkers are shown to be able to fail.

Orchestrator rulings applied: none. rulings.md has no `## 06-01` section, and R-A and R-B did not apply; R-B takes effect only after 06-12.

**Total deviations:** 3 (2 blocking environment workarounds, 1 additional evidence claim). **Impact:** none on scope. The evidence is the same or stronger.

## Issues Encountered

- The start of `smoke.log` is lost, including the `== tools before install` block and part of the `setup` traceback. stdout and stderr went to one file through `wsl`, and uv's progress output overwrote the start. So the log cannot show whether uv was present before the run. The lost block can only be recovered by another WSL2 run, which the executor cannot do (the worktree guard blocks `wsl`). A future run should send stderr to its own file inside smoke_wsl.sh. The `== tools after install` block is intact and is what the README quotes.
- `uv run` created `.venv` in the worktree. It is gitignored and untracked.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- AGT-10 follows the own-agent-layer branch: the driver, hooks, `watcom-decomp` skill, context pack and CLI calls through the Bash allowlist (D-04, D-44). The other Phase 6 plans were already planned for it.
- decomp.wtf goes to Phase 7 for claims (DEC-02/DEC-06). That evaluation has to size the stub-regex and `name_` lookup patches against D-02's PARTIAL budget, and provide a WSL2 build. `objdiff.json` is not an obstacle: configure.py writes it at the repo root, where `check` looks.

## Threat Flags

None. No new surface: nothing from decomp.wtf is tracked (`git ls-files build/` is empty), and the README quotes tool messages, names and addresses only.

Execution context nonce: c222325c277cc369

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-24*

## Self-Check: PASSED

- FOUND: .planning/spikes/006-decompwtf-fork-stub/README.md, stub_regex.py, linker_name.py
- FOUND: f0f79ea, b3b4636 (ancestors of HEAD)
- Verified after commit b3b4636: `uv run ruff check .` passed, `uv run pytest -q` passed (1416 passed, 215 skipped), and `tests/test_hygiene.py` passed.

## Fix round 1

Review: `review-06-01.md`, FIX_BASE 9aa28e0. The verdict letter is unchanged.

| # | Finding | Fix | Commit |
|---|---------|-----|--------|
| I1 | Third D-01 claim proven through `csource.replace`, which nothing calls | `replace-appends` replaced by `attempt-inserts` (`old_span` from `self._find(before, ...)`, else `_insert_in_order`) and `insert-keeps-stub` (all 3 returns keep all of `text`; fail-closed only for the shapes it checks, narrowed in fix round 2). Added an `insert-control` planted span-dropping return (refused) and `replace-unused` (0 callers). Both checkers and both `--plant` runs re-run (ALL PASS / `1 FAILED`, exit 1). README output block refreshed from the new `linker_name.out`; README What-This-Validates, step 3, and SUMMARY key-decision, one-liner and accomplishments reworded to "inserted by `_insert_in_order` (stub kept)" | 013cbc8 (scripts), 81f2c3c (README), this commit (SUMMARY) |
| I2 | PARTIAL ruled out by counting the toolchain against the patch budget | The verdict rests only on D-02's "no build in WSL2". The stub-regex and `name_` patches are named as D-02's PARTIAL list, unsized, left for the Phase 7 re-evaluation (D-03). README verdict, SUMMARY decision and docs/tools.md row updated | 81f2c3c, this commit |
| m1 | `objdiff.json` placement called an obstacle | README and SUMMARY now say configure.py writes it next to `build.ninja` at the repo root, where `check` looks; it was missing only because no build ran | 81f2c3c, this commit |
| m3 | `requirements-completed: [AGT-10]` premature | Set to `[]`, with a note: AGT-10 partial (spike only); 06-20, 06-21 and 06-27 also carry it | this commit |
| m5 | EXPECTED comments in stub_regex.py read opposite to their values | Phrased as the question each value answers | 013cbc8 |
| m6 | Shape errors always labelled `forkengine.py` | `shaped()` names the file each SpikeError came from (checked against an empty SRC: `FAIL forkengine.py shape expected one app/forkengine.py ...`) | 013cbc8 |
| m2 | `_FINDER_PREFIX` copied 31 chars of decomp.wtf regex | Removed. The plain-name pattern is now located structurally, as the `re.compile` in the `else` of `find`'s `if "::" in name`. The README output lines that quote `ast.unparse` excerpts are kept and labelled (fix round 2) | 013cbc8, 612cd9d |
| m4 | Lost `tools before install` block | Recorded under Issues Encountered: it can only be recovered by another WSL2 run, which the executor cannot do. A future run should send stderr to its own file. Not run | this commit |

After the fixes: `uv run ruff check .` passed, `uv run pytest -q` passed (1416 passed, 215 skipped), and `tests/test_hygiene.py` passed.

## Fix round 2

Re-review: `rereview-06-01-r1.md`, FIX_BASE 43a54aa. Both Important findings were confirmed fixed. The verdict is unchanged.

| # | Finding | Fix | Commit |
|---|---------|-----|--------|
| N1 | Two stub-dropping mutations still printed ALL PASS, so "fail-closed" said more than the checker proved | Partly hardened: `insert-keeps-stub` now also refuses any store to `text` in `_insert_in_order`. A scratchpad mutant with `text = text.replace("INCLUDE_ASM", "")` now gives `FAIL ... text rebound at lines [1999]`, exit 1. A new `finder-on-marker` claim shows the plain-name finder misses `INCLUDE_ASM(func_000A3980);` for both spellings. The rewrite of `after` in `_attempt` (the `_with_includes` step) is still not checked. The README and this SUMMARY now say "fail-closed only for the shapes it checks", and list what is confirmed by reading the pinned source only, with no claim: `_with_includes` (forkengine.py:278-287) only inserts; `_find` calls `csource.find` (:1499-1504); `find` falls back to `_stub` (csource.py:91) | fd3e056 (script), 612cd9d (README), this commit |
| m2 | README output lines quote `ast.unparse` excerpts of decomp.wtf | One sentence above the linker_name.py block: those lines quote short excerpts of decomp.wtf v0.10.6 (MIT, © Sam Wolfs) for verification only. m2 row above updated | 612cd9d, this commit |
| N2 | linker_name.py docstring named only two files | The docstring lists every file read: forkengine.py, csource.py, every `src/decompnet/**/*.py`, our configure.py, and reverseapoc.functions/symbols | fd3e056 |
| N3 | `replace_callers` could pass on an empty glob | It raises a shape error unless `src/decompnet/app/forkengine.py` is among the scanned files. A scratchpad layout without `src/decompnet/` gives `FAIL package shape src/decompnet/**/*.py ... (0 files) lacks forkengine.py`, exit 1 | fd3e056 |
| N4 | README.md:161 overlong | Rewrapped; no README prose line is over 100 chars | 612cd9d |

Re-runs: `stub_regex.py` ALL PASS (exit 0), with `--plant` 1 FAILED (exit 1). `linker_name.py` ALL PASS on 14 claims (exit 0), with `--plant` 1 FAILED, `finder-linker-name` only (exit 1). The README linker_name.py block was rebuilt from the new `linker_name.out`; the stub_regex.py output did not change. `uv run ruff check .` and `tests/test_hygiene.py` (60 passed, 3 skipped) pass.
