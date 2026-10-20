---
phase: 03-byte-identical-round-trip
plan: 05
subsystem: tooling
tags: [le, rebuild, real-files, region-map, trailer, docs, phase-gate, docker, ninja]

requires:
  - phase: 03-byte-identical-round-trip
    provides: "plan 03-01: layout/check_tiling/region_at, rebuild_target, REVERSEAPOC_ORIG override; plan 03-02: ninja verify edge, manifest-hash guard; plan 03-03: splice(), MaskedField, mismatch report; plan 03-04: rebuild --json/--exe, LE.summary()['trailer']"
  - phase: spikes
    provides: ".planning/spikes/001 + 002 (LE edge-case spike, VALIDATED) and 003 (27-byte trailer spike, PARTIAL: facts confirmed, meaning unknown)"
provides:
  - "tests/test_splice_real.py: per-target real-file round trip, rebuild_target byte identity, one-byte control mutation, straddler and page-cut masking sweeps, spike-confirmed FACTS"
  - "docs/toolchain.md LE layout section: SMKP column, confirmed edge cases, byte-region map, trailer facts per D-12 with the spike 003 verdict, rebuild/ninja verify sentence"
  - "tests/test_hygiene.py::test_toolchain_records_the_confirmed_le_layout"
  - "Phase gate run on the main checkout, host and container, logged under build/gate/ (reproduced below)"
affects: [phase-4-compiler-id, phase-5-landing, phase-6-driver]

actuals:
  tasks: 3
  commits: 3
plan_head_before: 8ac57f79f6dc90db27b7436e0f445faa3fe8f468
plan_head_after: 0a9e8d2

tech-stack:
  added: []
  patterns:
    - "Real-file tests parametrized over load_manifest() with a per-target skipif, so SMKP (no trailer) runs through the same path and a missing file skips only its own param"
    - "Straddlers and page-cut fields are computed from le.fixups() and the page geometry in the test, never hard-coded; the FACTS dict pins the spike values separately and the two must agree"
    - "Real-file assertions compare offsets, VAs, counts, booleans and filecmp results only"

key-files:
  created:
    - tests/test_splice_real.py
  modified:
    - tests/test_hygiene.py
    - docs/toolchain.md

key-decisions:
  - "Task 3 (the phase gate) ran on the main checkout after the worktree merge, as the plan's precondition requires; the worktree executor stopped at the precondition by design and wrote no SUMMARY"
  - "The trailer is documented as an opaque structured record (u16 value/complement pairs at trailer offsets 0, 4, 8; also on the 1997 CD builds); the rebuild carries it unchanged (D-10)"
  - "The 'OpenApoc CRC mismatch' section of docs/toolchain.md was left unchanged although spike 003 contradicts its store-installer claim; correcting it is an owner decision"

patterns-established:
  - "A phase gate is a fixed list of command lines, each logged with its exit status under build/gate/ and reproduced verbatim in the SUMMARY"

requirements-completed: [RT-01, RT-02, RT-03, RT-04, RT-05]

coverage:
  - id: D1
    description: "Every manifest target round-trips on the real files: layout() tiles the file, splice(le, {}) hashes to the load_manifest() SHA-1, rebuild_target writes a file byte-identical to orig/NAME"
    requirement: RT-01
    verification:
      - kind: integration
        ref: "tests/test_splice_real.py#test_layout_tiles_real_file"
        status: pass
      - kind: integration
        ref: "tests/test_splice_real.py#test_every_manifest_target_round_trips"
        status: pass
      - kind: integration
        ref: "tests/test_splice_real.py#test_rebuild_writes_identical_file"
        status: pass
    human_judgment: false
  - id: D2
    description: "A real one-byte mid-page mutation is reported at page.file_offset + delta with its region label and VA, a count of 1 and no masked field; an unpatched rebuild is ok again"
    requirement: RT-04
    verification:
      - kind: integration
        ref: "tests/test_splice_real.py#test_control_mutation_is_reported"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every page-straddling fixup field keeps its original bytes and is reported straddles_page; every field cut by the end of page data keeps its backed bytes and is reported clipped"
    requirement: RT-02
    verification:
      - kind: integration
        ref: "tests/test_splice_real.py#test_straddling_fields_are_masked"
        status: pass
      - kind: integration
        ref: "tests/test_splice_real.py#test_fields_cut_by_page_data_are_clipped"
        status: pass
    human_judgment: false
  - id: D4
    description: "The spike-confirmed LE facts are pinned per target and docs/toolchain.md records them, the region map and the trailer (offset, length, first 4 bytes, SHA-1) without the outdated EOF and 'To be confirmed' lines"
    requirement: RT-05
    verification:
      - kind: integration
        ref: "tests/test_splice_real.py#test_measured_facts"
        status: pass
      - kind: unit
        ref: "tests/test_hygiene.py#test_toolchain_records_the_confirmed_le_layout"
        status: pass
    human_judgment: false
  - id: D5
    description: "Phase gate on the main checkout: host suite, rebuild (3 OK lines), silent cmp, docker compose run --rm test, container suite, ninja verify (3 OK lines), all exit 0 with no real-file skip"
    requirement: RT-03
    verification:
      - kind: other
        ref: "build/gate/01..06 logs, reproduced under '## Phase gate output'"
        status: pass
    human_judgment: false

duration: about 35 min (Tasks 1-2 in a worktree 21:38-21:45 UTC; merge and gate on the main checkout)
completed: 2026-10-20
---

# Phase 3 Plan 05: Real-file proof, pinned LE facts, docs and the phase gate Summary

**The real UFO2P.EXE, TACP.EXE and SMKP.EXE rebuild byte-identical from their region maps on the host and in the container. A real one-byte mutation is reported at its exact offset and VA. Every straddling and page-cut fixup field is masked. The spike-confirmed LE facts are pinned in tests and recorded in docs/toolchain.md.**

## Performance

- **Tasks:** 3 (Tasks 1-2 by the worktree executor, Task 3 by the orchestrator on the main checkout)
- **Commits:** 3 (9d93101, 2f47759, 0a9e8d2), merged in 2347cea
- **Files:** 1 created, 2 modified

## Accomplishments

- `tests/test_splice_real.py`: six real-file tests plus `test_measured_facts`, each parametrized over `load_manifest()` with a per-target skip. There are no hash strings in the file, and outputs go to `tmp_path` only.
- `docs/toolchain.md` "LE layout" now has:
  - an SMKP.EXE column and the extender described as an MZ loader plus BW modules (spike 001);
  - "Bytes after the last page" replacing the EOF row;
  - the confirmed edge cases replacing the "To be confirmed" bullet;
  - the byte-region map table and the trailer verdict;
  - the `rebuild` / `ninja verify` sentence.
- The phase gate passed on the main checkout: 324 passed on the host and 327 passed with no skip in the container. `rebuild` and `ninja verify` each print three OK lines, and `cmp` is silent.

## Task Commits

1. **Task 1: real-file round trip, control mutation and masking (tracer).** Commit `9d93101`: test(03-05): round-trip, control mutation and masking on the real EXEs.
2. **Task 2: pin the confirmed facts, correct docs/toolchain.md.**
   - RED `2f47759`: test(03-05): pin the spike-confirmed LE facts and add a failing doc check.
   - GREEN `0a9e8d2`: docs(03-05): record the spike-confirmed LE layout and byte-region map.
3. **Task 3: phase gate on the main checkout.** No commit by design: `build/` is gitignored, and the logs are reproduced below.

## Mutants and negative proofs (Tasks 1-2, never committed)

| Mutant | Change | Result |
|---|---|---|
| Masking off | `covered = []` in `tools/reverseapoc/splice.py` | 6 failed / 12 passed: `test_straddling_fields_are_masked` and `test_fields_cut_by_page_data_are_clipped` failed for all three EXEs, naming the VAs whose bytes changed (0x13e27c.., 0x2b6538.., 0x32ff6.. for the cut fields). Restored with `git checkout`; `git diff --exit-code -- tools/reverseapoc/splice.py` exited 0 |
| Control offset +1 | expected offset in `test_control_mutation_is_reported` shifted by one | 3 failed / 15 passed (UFO2P.EXE, TACP.EXE, SMKP.EXE); reverted |
| Wrong pinned fact | SMKP straddler 0x1CFFE changed to 0x1CFFF in FACTS | `test_measured_facts[SMKP.EXE]` failed: `assert (73725, 118782) == (73725, 118783)`; reverted |
| Doc check RED | `test_toolchain_records_the_confirmed_le_layout` against the old doc | failed with `AssertionError: assert ['runs exactl...in Phase 2/3'] == []` |

## Facts pinned (spike source)

| Fact | UFO2P | TACP | SMKP | Spike |
|---|---|---|---|---|
| Pages, all physical, identity map | 303 | 666 | 21 | 001 |
| Extender end | 0x352A4 | 0x352A4 | 0x26654 | 001 / 002 |
| Data pages start | 0x724A4 | 0x6A8A4 | 0x2D454 | 002 |
| Zero padding (bytes) | 362 | 403 | 223 | 002 |
| obj1 page bytes past vsize (all zero) | 0x523 | 0xAB1 | 0xC80 | 002 |
| Trailer (offset, length) | 0x1A0723, 27 | 0x303DDF, 27 | none (summary length 0) | 002 / 003 |
| Page-straddling off32 fields | 14 | 11 | 2 (0x11FFD, 0x1CFFE) | 001 |
| Fields cut by the end of page data (VA, backed bytes) | 0x13E27C, 3 | 0x2B6538, 3 | 0x32FF6, 2 | 001 |
| off32 / sel16 / ptr16:32 / rel32 | 28,183 / 10 / 4 / 0 | 24,424 / 10 / 4 / 0 | 2,297 / 0 / 0 / 0 | 001 |

## Files Created/Modified

- `tests/test_splice_real.py` (new, 324 lines): helpers `_page_offset`, `_file_offset`, `_page_backed_end`, `_covered`, `_straddlers` and `_cut_fields`; the six real-file tests; FACTS and `test_measured_facts`.
- `tests/test_hygiene.py` (+9): `test_toolchain_records_the_confirmed_le_layout`.
- `docs/toolchain.md` (+36 / -15): LE layout section only. "Getting the Watcom compilers" and "OpenApoc CRC mismatch" are byte-identical to base 8ac57f7.

## Decisions Made

- Task 3 ran on the main checkout. The worktree executor ran the precondition (git-dir differs from git-common-dir), recorded that it fails as designed and stopped before any gate step.
- The trailer verdict in the doc summarizes spike 003's results:
  - a structured record with u16 value/complement pairs at trailer offsets 0, 4 and 8, also present on the 1997 CD builds;
  - not a tested checksum or CRC, not a DOS/4GW bind record and not an install-time stamp;
  - its meaning is unknown, and it is carried unchanged.

## Deviations from Plan

- **[Mechanical] Literal orig/ path.** The worktree sandbox refuses `git` inside `$(...)`, so the real-file verifies used the literal main-checkout orig/ path, which is the same directory. It was read only.
- **[Mechanical] Task 3 precondition in Python.** The sandbox refused the literal `test "A" = "B"` line naming `.git` paths, so the executor compared the two values in Python. On the main checkout, Task 3's verify ran the line as written and it passed.
- **[Rule 2 - added check] Wrong-fact run.** A temporary wrong-fact run proved `test_measured_facts` can fail. It was not committed.
- **[Mechanical] Commit type.** Task 2's GREEN commit is typed `docs(03-05)`, because it changes only documentation. This is a `type: execute` plan.

**Total deviations:** 4, all mechanical or additive checks. **Impact:** none on scope or behaviour.

## Verification

The plan-level verification steps 1-6 are the gate below. Step 7 is this section's `exit=0` count. Task 1-2 verifies, run in the worktree with the real-file override:
- `tests/test_splice_real.py -rs`: 18 passed, no SKIPPED.
- `-k "layout or facts"`: 6 passed, no SKIPPED.
- Full suite: 318 passed, 9 skipped. The skips are 3 container-only hygiene tests and 6 for absent Watcom media.
- `ruff check .`: clean.
- `tests/test_hygiene.py`: 27 passed, 3 skipped.
- The "runs exactly to EOF" and "To be confirmed in Phase 2/3" greps no longer match; 0x1A0723 and 0x303DDF each match.

## Phase gate output

Run on the main checkout (`test "$(git rev-parse --path-format=absolute --git-dir)" = "$(git rev-parse --path-format=absolute --git-common-dir)"` exited 0), with Docker Desktop 29.6.2 up. Nothing was edited between the steps.

**Preconditions:**
- this is the main checkout;
- `grep -q test_measured_facts tests/test_splice_real.py` passed;
- `uv run reverseapoc check-orig` printed "3 ok, 0 mismatched, 0 missing";
- `docker info` succeeded.

Each step ran in a subshell, with stdout and stderr redirected on the host into `build/gate/0N-*.log`, followed by one `exit=STATUS` line. The six logs are reproduced verbatim.

### 1. Host suite: `uv run pytest -q -rs && uv run ruff check .` (build/gate/01-host-suite.log)

```
..............................................................sss....... [ 22%]
........................................................................ [ 44%]
........................................................................ [ 66%]
........................................................................ [ 88%]
.......................................                                  [100%]
=========================== short test summary info ===========================
SKIPPED [3] tests\test_hygiene.py:180: only inside the container
324 passed, 3 skipped in 4.92s
All checks passed!
exit=0
```

### 2. Host rebuild: `uv run reverseapoc rebuild` (build/gate/02-rebuild.log)

```
OK        UFO2P.EXE  sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 == manifest
OK        TACP.EXE   sha1 48ef00969d8880a0a152de1b652853fa7ac27393 == manifest
OK        SMKP.EXE   sha1 efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc == manifest
exit=0
```

### 3. Byte compare: `cmp build/UFO2P.EXE orig/UFO2P.EXE && cmp build/TACP.EXE orig/TACP.EXE && cmp build/SMKP.EXE orig/SMKP.EXE` (build/gate/03-cmp.log)

```
exit=0
```

### 4. Container test service: `docker compose run --rm test` (build/gate/04-container-test.log)

```
 Container reverseapoc-test-run-2ac2324503f8 Creating 
 Container reverseapoc-test-run-2ac2324503f8 Created 
Resolved 8 packages in 5ms
   Building reverseapoc @ file:///work
      Built reverseapoc @ file:///work
Prepared 1 package in 1.24s
Uninstalled 1 package in 3ms
Installed 1 package in 1ms
 ~ reverseapoc==0.0.1 (from file:///work)
........................................................................ [ 22%]
........................................................................ [ 44%]
........................................................................ [ 66%]
........................................................................ [ 88%]
.......................................                                  [100%]
327 passed in 5.23s
exit=0
```

### 5. Container suite: `docker compose run --rm build bash -lc "uv sync --locked && uv run pytest -q -rs && uv run ruff check ."` (build/gate/05-container-suite.log)

```
 Container reverseapoc-build-run-2d3332636b5b Creating 
 Container reverseapoc-build-run-2d3332636b5b Created 
Resolved 8 packages in 2ms
Checked 7 packages in 3ms
........................................................................ [ 22%]
........................................................................ [ 44%]
........................................................................ [ 66%]
........................................................................ [ 88%]
.......................................                                  [100%]
327 passed in 5.04s
All checks passed!
exit=0
```

### 6. Container ninja verify: `docker compose run --rm build bash -lc "uv run python configure.py && ninja verify"` (build/gate/06-container-ninja-verify.log)

```
 Container reverseapoc-build-run-3127290cd3cb Creating 
 Container reverseapoc-build-run-3127290cd3cb Created 
wrote /work/build.ninja (3 executable(s) for parse-le)
[0/1] REBUILD build/
OK        UFO2P.EXE  sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 == manifest
OK        TACP.EXE   sha1 48ef00969d8880a0a152de1b652853fa7ac27393 == manifest
OK        SMKP.EXE   sha1 efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc == manifest
exit=0
```

### Task 3 verify (run as written in the plan)

All six checks passed:
- main checkout;
- six logs, each ending `exit=0`;
- three host OK lines;
- three `ninja verify` OK lines;
- `03-cmp.log` is exactly `exit=0`;
- both suites ran with no real-file skip.

`sha1sum orig/*.EXE build/*.EXE` gives the same three SHA-1s on each side, equal to `config/targets.toml`.

## Issues Encountered

None in this plan. Spike 003 found that docs/toolchain.md's "OpenApoc CRC mismatch" paragraph is wrong: the installed EXEs are the CD's `XCOM3/UFOEXE/UFO2P4.EXE` and `XCOM3/TACEXE/TACP4.EXE`. The paragraph is left for the owner to decide.

## User Setup Required

None.

## Next Phase Readiness

Phase complete; ready for `/gsd-verify-work 3`. The `splice(le, {va: bytes})` primitive and the `rebuild` verb are what Phase 5 lands matched functions with.

## Self-Check: PASSED

- `tests/test_splice_real.py` exists, and `test_measured_facts` is present.
- Commits 9d93101, 2f47759 and 0a9e8d2 are on main, merged in 2347cea.
- Every acceptance criterion of Tasks 1-3 was re-run and passes.
- The six gate logs each end `exit=0` and are reproduced above.
