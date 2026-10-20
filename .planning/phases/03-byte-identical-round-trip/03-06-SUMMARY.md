---
phase: 03-byte-identical-round-trip
plan: 06
subsystem: tooling
tags: [configure, ninja, splice, gap-closure, code-review, phase-gate]
gap_closure: true
gap_ids: [G-03-3]

requires:
  - phase: 03-byte-identical-round-trip
    provides: "plans 03-02 (verify edge), 03-03 (splice masking), 03-04 (--json contract), 03-05 (phase gate); 03-REVIEW.md WR-02/WR-05/WR-06; UAT gap G-03-3 with its diagnosis"
provides:
  - "configure.py: render(exes, *, orig='orig') emits --orig <dir> in the check_orig and rebuild commands; ConfigureError refuses executable names holding |, LF or CR and an --orig path outside [A-Za-z0-9._/:-]; main() exits 1 before writing anything"
  - "rebuild_target: masked_fields counts distinct fixup fields (WR-02); key name, 8-key --json contract and SpliceResult.masked shape unchanged"
  - "docs/learnings.md entry: ninja quotes $in, nothing else"
  - "Phase gate re-run on the main checkout with a seventh step: ninja verify through a non-default --orig"
affects: [phase-5-landing, phase-6-driver]

actuals:
  tasks: 3
  commits: 4
plan_head_before: 9158a037746bdba4163ebfc631b2be1eb2fd3893
plan_head_after: ee1dcaa

tech-stack:
  added: []
  patterns:
    - "Refuse what a generator cannot represent (ConfigureError before any write) instead of quoting for one shell"
    - "An end-to-end host test runs the generated ninja commands through reverseapoc.cli.main to prove they read the --orig dir"

key-files:
  created: []
  modified:
    - configure.py
    - tests/test_configure.py
    - docs/learnings.md
    - tools/reverseapoc/splice.py
    - tests/test_splice.py
    - .planning/phases/03-byte-identical-round-trip/03-REVIEW-DISPOSITION.md

key-decisions:
  - "WR-06 follows the corrected mechanism: parse-le $in stays unquoted (ninja shell-quotes it); configure.py refuses names ninja 1.11 cannot write and an --orig path it would have to quote, because no quoting works on both /bin/sh and Windows CreateProcess"
  - "masked_fields keeps its name and the 8-key --json contract; only its count changes to distinct fixup fields"
  - "The gate adds step 7 (ninja verify through --orig ../tmp/alt-orig in the container), the only real-ninja proof that --orig reaches verify"

patterns-established:
  - "Gap-closure gate logs go under build/gate/<plan>/ so earlier gate logs stay"

requirements-completed: [RT-02, RT-03]

coverage:
  - id: D1
    description: "configure.py --orig reaches the check-orig and verify (rebuild) commands; the generated commands read the --orig dir"
    requirement: RT-03
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_main_passes_orig_to_check_orig_and_rebuild"
        status: pass
      - kind: integration
        ref: "tests/test_configure.py#test_generated_commands_read_the_orig_dir"
        status: pass
      - kind: other
        ref: "build/gate/03-06/07-container-ninja-alt-orig.log (ninja -t commands shows --orig ../tmp/alt-orig; ninja verify OK x3)"
        status: pass
    human_judgment: false
  - id: D2
    description: "configure.py refuses executable names holding |, LF or CR and an unsafe --orig path with a clear error and writes nothing; parse-le $in stays unquoted and names with spaces keep working"
    requirement: RT-03
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_render_refuses_names_ninja_cannot_represent"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_render_refuses_an_unsafe_orig_dir"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_main_refuses_an_unsafe_orig_dir"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_main_keeps_names_with_spaces"
        status: pass
    human_judgment: false
  - id: D3
    description: "rebuild_target's masked_fields counts distinct fixup fields (touching, three-patch, straddling, two-field and mixed cases) in the text line and --json"
    requirement: RT-02
    verification:
      - kind: unit
        ref: "tests/test_splice.py#test_mask_count_counts_distinct_fields"
        status: pass
    human_judgment: false
  - id: D4
    description: "Phase gate re-run on the main checkout: host suite, rebuild, cmp, container test, container suite, ninja verify, ninja verify through a non-default --orig; all exit 0 with no real-file skip"
    requirement: RT-03
    verification:
      - kind: other
        ref: "build/gate/03-06/01..07 logs, reproduced under '## Phase gate output'"
        status: pass
    human_judgment: false

duration: about 25 min (Tasks 1-2 in a worktree 22:58-23:05 UTC; merge and gate on the main checkout)
completed: 2026-10-20
---

# Phase 3 Plan 06: Gap closure G-03-3 (review warnings WR-02, WR-05, WR-06) Summary

**`configure.py --orig` now reaches the check-orig and verify edges, which ninja 1.11.1 proves in the container. build.ninja refuses names and paths it cannot carry instead of writing a broken file. `masked_fields` counts distinct fixup fields. The phase gate passed again on the main checkout with a seventh step.**

## Performance

- **Tasks:** 3 (Tasks 1-2 by the worktree executor, Task 3 by the orchestrator on the main checkout)
- **Commits:** 4 (21d372a, 918b4f9, 9f880bb, ee1dcaa), merged in 53a94d4
- **Files:** 5 source/test/doc files modified (+230 / -11) plus the disposition record

## Accomplishments

- **WR-05:**
  - `render(exes, *, orig="orig")` writes `--orig <dir>` into the `check_orig` and `rebuild` commands. The dir is relative to build.ninja, like the exe paths.
  - `HEADER` is a template in exactly those two command lines; the rest is byte-identical.
  - `tests/test_configure.py` line 73 was updated on purpose to expect `--orig orig`; it was the only existing line removed.
- **WR-06 (corrected mechanism):**
  - `ninja_path` refuses `|`, LF and CR, naming the full path.
  - `_check_orig_dir` accepts only `[A-Za-z0-9._/:-]`, and `ConfigureError` explains the /bin/sh and CreateProcess reason.
  - `main()` prints `configure.py: error: ...` and exits 1 before writing.
  - `parse-le $in` stays unquoted, pinned by an exact-line test, and names with spaces keep working.
- **WR-02:** `masked = len({m.fixup for m in result.masked})`. The `masked_fields` key, `_masked_note`, `to_json` with its 8 keys, and the per-(patch, field) `SpliceResult.masked` are unchanged. `tests/test_cli.py` is byte-identical.
- **docs/learnings.md:** new entry "2026-10-20: ninja quotes $in, nothing else (Phase 3 review WR-05, WR-06)".
- **Disposition:** WR-02, WR-05 and WR-06 are now `fixed` in 03-REVIEW-DISPOSITION.md, and `open` went from 11 to 8. WR-01, WR-03 and WR-04 stay `deferred` to Phases 5 and 6.

## Task Commits

1. **Task 1 (tracer, TDD): WR-05 and WR-06 in configure.py.**
   - RED `21d372a`: test(03-06): add failing tests for --orig in check-orig/verify and unsafe build.ninja paths.
   - GREEN `918b4f9`: fix(03-06): pass --orig to check-orig and verify, refuse paths build.ninja cannot carry.
2. **Task 2 (TDD): WR-02 in splice.py.**
   - RED `9f880bb`: test(03-06): add failing test for masked_fields counting distinct fixup fields.
   - GREEN `ee1dcaa`: fix(03-06): count distinct fixup fields in masked_fields.
3. **Task 3: gate on the main checkout and the disposition update.** No source commit; the record is this SUMMARY plus the ledger, committed together.

## TDD record

**Task 1 RED at 21d372a:** 20 failed, 9 passed, 2 skipped.
- The line-73 expectation now asks for `--orig orig`.
- `render() got an unexpected keyword argument 'orig'`.
- The `check-orig` command lacked `--orig elsewhere` / `--orig ../elsewhere`.
- No REFUSED line: without `--orig`, rebuild read the repo's orig/.
- `configure` has no `ConfigureError`.
- `main` wrote build.ninja (`assert 0 == 1`).

`gsd-tools check tdd-red-evidence` gave RED_EVIDENCE_OK for `test_generated_commands_read_the_orig_dir` and `test_main_passes_orig_to_check_orig_and_rebuild[same-dir]`. GREEN: test_configure.py 29 passed, 2 skipped (Windows-only skipif).

**Task 2 RED at 9f880bb:** 4 failed and the two-fields control passed.
- touching: `assert 2 == 1`
- three-patches: `assert 3 == 1`
- straddling: `assert 2 == 1`
- mixed: `assert 3 == 2`

RED_EVIDENCE_OK for `[touching]`. GREEN: splice and CLI tests 108 passed.

## Mutants (never committed; `git diff --exit-code` clean after each)

| Mutant | Change | Tests that failed |
|---|---|---|
| T1-M1 | main() passes plain `"orig"` | `test_main_passes_orig_to_check_orig_and_rebuild[same-dir, sub-dir]`, `test_generated_commands_read_the_orig_dir`, `test_main_refuses_an_unsafe_orig_dir[my orig, a;b]` |
| T1-M2 | orig-path check skipped | `test_render_refuses_an_unsafe_orig_dir` (all 9 ids), `test_main_refuses_an_unsafe_orig_dir[my orig, a;b]` |
| T1-M3 | `\|`/LF/CR refusal disabled | `test_render_refuses_names_ninja_cannot_represent[pipe, lf, cr]`, `test_main_refuses_names_ninja_cannot_represent` |
| T1-M4 | `"$in"` quoted in the parse_le rule | `test_render_has_phony_targets_and_phase5_note`, `test_render_passes_orig_to_check_orig_and_rebuild` |
| T2-M1 | count distinct `m.patch_va` | touching, three-patches, straddling, mixed |
| T2-M2 | `min(1, len({m.fixup ...}))` | two-fields, mixed |
| T2-M3 | back to `len(result.masked)` | touching, three-patches, straddling, mixed |

## Files Created/Modified

- `configure.py`: ConfigureError, `_SAFE_ORIG`/`_check_orig_dir`, `ninja_path` refusal, HEADER template, `render(..., orig=)`, `main()` error path.
- `tests/test_configure.py`: +151 lines. New tests and the helpers `_command`, `_orig_from_parse_le_edge`, `CHECK_ORIG_CMD`, `REBUILD_CMD`. Only line 73 was removed and replaced.
- `tools/reverseapoc/splice.py`: distinct-field count and two comment updates.
- `tests/test_splice.py`: `test_mask_count_counts_distinct_fields`, parametrized over 5 cases; no line removed.
- `docs/learnings.md`: the new entry.
- `.planning/phases/03-byte-identical-round-trip/03-REVIEW-DISPOSITION.md`: WR-02, WR-05 and WR-06 set to fixed, `open: 8`.

## Decisions Made

- Refusal instead of quoting for `--orig`. The same build.ninja must work under /bin/sh in the container and under CreateProcess on the Windows host, and no single quoting serves both.
- In the render loop, the full exe path goes through `ninja_path` before the bare name, so a refusal names the whole path.

## Deviations from Plan

- **[Mechanical] Literal `REVERSEAPOC_ORIG`.** The worktree sandbox refuses `$(git ...)` substitution, so the real-file and full-suite runs used the literal main-checkout path `.../.git/../orig`, read-only. Compound verify commands were split into separate calls with the same commands.
- **[Additive] Test-shape choices.** `test_main_passes_orig_to_check_orig_and_rebuild` is parametrized (same-dir, sub-dir). Small helpers were added to tests/test_configure.py; only lines were added, besides line 73.
- **[Rule 1] Full exe path first.** The render loop passes the full exe path to `ninja_path` first, as the planned test requires the full path in the message.

**Total deviations:** 3, all mechanical or within the plan's behaviour. **Impact:** none on scope. WR-01, WR-03, WR-04 and IN-01..IN-08 are untouched. orig/, config/ and the Docker files were never edited, and no package was installed.

## Verification

- Worktree, with the real-file override: 343 passed, 11 skipped. None of the skips is for orig/: 2 are the Windows-only skipif, 3 container-only, 6 missing Watcom media. ruff is clean.
- tests/test_splice_real.py: 21 passed, no SKIPPED.
- Main checkout (below): host 349 passed, 5 skipped (2 Windows-only, 3 container-only). Container 354 passed with no skip, which includes the `|`/LF name tests Windows cannot create.

## Phase gate output

Run on the main checkout (`test "$(git rev-parse --path-format=absolute --git-dir)" = "$(git rev-parse --path-format=absolute --git-common-dir)"` exited 0), with Docker Desktop 29.6.2 up. Nothing was edited between the steps.

**Preconditions:**
- this is the main checkout;
- `grep -q "class ConfigureError" configure.py` passed;
- `grep -q test_mask_count_counts_distinct_fields tests/test_splice.py` passed;
- `uv run reverseapoc check-orig` printed "3 ok, 0 mismatched, 0 missing";
- `docker info` succeeded.

Each step ran in a subshell, with stdout and stderr redirected on the host into `build/gate/03-06/0N-*.log`, followed by one `exit=STATUS` line. The seven logs are reproduced verbatim.

### 1. Host suite: `uv run pytest -q -rs && uv run ruff check .` (build/gate/03-06/01-host-suite.log)

```
...........................................ss........................... [ 20%]
............sss......................................................... [ 40%]
........................................................................ [ 61%]
........................................................................ [ 81%]
..................................................................       [100%]
=========================== short test summary info ===========================
SKIPPED [2] tests\test_configure.py:196: Windows file names cannot hold | or LF
SKIPPED [3] tests\test_hygiene.py:180: only inside the container
349 passed, 5 skipped in 4.00s
All checks passed!
exit=0
```

### 2. Host rebuild: `uv run reverseapoc rebuild` (build/gate/03-06/02-rebuild.log)

```
OK        UFO2P.EXE  sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 == manifest
OK        TACP.EXE   sha1 48ef00969d8880a0a152de1b652853fa7ac27393 == manifest
OK        SMKP.EXE   sha1 efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc == manifest
exit=0
```

### 3. Byte compare: `cmp build/UFO2P.EXE orig/UFO2P.EXE && cmp build/TACP.EXE orig/TACP.EXE && cmp build/SMKP.EXE orig/SMKP.EXE` (build/gate/03-06/03-cmp.log)

```
exit=0
```

### 4. Container test service: `docker compose run --rm test` (build/gate/03-06/04-container-test.log)

```
 Container reverseapoc-test-run-5ee8770966ae Creating 
 Container reverseapoc-test-run-5ee8770966ae Created 
Resolved 8 packages in 6ms
Checked 7 packages in 7ms
........................................................................ [ 20%]
........................................................................ [ 40%]
........................................................................ [ 61%]
........................................................................ [ 81%]
..................................................................       [100%]
354 passed in 5.26s
exit=0
```

### 5. Container suite: `docker compose run --rm build bash -lc "uv sync --locked && uv run pytest -q -rs && uv run ruff check ."` (build/gate/03-06/05-container-suite.log)

```
 Container reverseapoc-build-run-62de9ed2f464 Creating 
 Container reverseapoc-build-run-62de9ed2f464 Created 
Resolved 8 packages in 2ms
Checked 7 packages in 3ms
........................................................................ [ 20%]
........................................................................ [ 40%]
........................................................................ [ 61%]
........................................................................ [ 81%]
..................................................................       [100%]
354 passed in 5.16s
All checks passed!
exit=0
```

### 6. Container ninja verify: `docker compose run --rm build bash -lc "uv run python configure.py && ninja verify"` (build/gate/03-06/06-container-ninja-verify.log)

```
 Container reverseapoc-build-run-c30a2823125e Creating 
 Container reverseapoc-build-run-c30a2823125e Created 
wrote /work/build.ninja (3 executable(s) for parse-le)
[0/1] REBUILD build/
OK        UFO2P.EXE  sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 == manifest
OK        TACP.EXE   sha1 48ef00969d8880a0a152de1b652853fa7ac27393 == manifest
OK        SMKP.EXE   sha1 efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc == manifest
exit=0
```

### 7. Container ninja verify through a non-default --orig: `docker compose run --rm build bash -lc 'mkdir -p /tmp/alt-orig && ln -sf /work/orig/UFO2P.EXE /work/orig/TACP.EXE /work/orig/SMKP.EXE /tmp/alt-orig/ && uv run python configure.py --orig /tmp/alt-orig && ninja -t commands verify check-orig && ninja verify; status=$?; uv run python configure.py; exit $status'` (build/gate/03-06/07-container-ninja-alt-orig.log)

```
 Container reverseapoc-build-run-ca42f14b7817 Creating 
 Container reverseapoc-build-run-ca42f14b7817 Created 
wrote /work/build.ninja (3 executable(s) for parse-le)
uv run reverseapoc rebuild --orig ../tmp/alt-orig
uv run reverseapoc check-orig --orig ../tmp/alt-orig
[0/1] REBUILD build/
OK        UFO2P.EXE  sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 == manifest
OK        TACP.EXE   sha1 48ef00969d8880a0a152de1b652853fa7ac27393 == manifest
OK        SMKP.EXE   sha1 efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc == manifest
wrote /work/build.ninja (3 executable(s) for parse-le)
exit=0
```

### Task 3 verify (run as written in the plan)

All eight checks passed:
- main checkout;
- seven logs, each ending `exit=0`;
- three host OK lines;
- three `ninja verify` OK lines;
- the alt `--orig` command lines plus three OK lines;
- `03-cmp.log` is exactly `exit=0`;
- both suites ran with no real-file skip;
- the disposition record shows WR-02, WR-05 and WR-06 fixed and WR-01, WR-03 and WR-04 deferred.

Afterwards, the default build.ninja carries `check-orig --orig orig` and `rebuild --orig orig`.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

Gap G-03-3 is closed and ready for `/gsd-verify-work 3`. WR-01 and WR-03 (Phase 5) and WR-04 (Phase 6) stay deferred in STATE.md concerns.

## Self-Check: PASSED

- Commits 21d372a, 918b4f9, 9f880bb and ee1dcaa are on main, merged in 53a94d4.
- `class ConfigureError`, `test_mask_count_counts_distinct_fields` and `rebuild --orig orig` are present.
- The seven gate logs each end `exit=0` and are reproduced above.
- 03-REVIEW-DISPOSITION.md shows 3 fixed and 3 deferred, with `open: 8`.
