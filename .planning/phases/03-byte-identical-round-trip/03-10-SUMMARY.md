---
phase: 03-byte-identical-round-trip
plan: 10
subsystem: tooling
tags: [phase-gate, gap-closure, code-review, docker, ninja]
gap_closure: true
gap_ids: [G-03-6]

requires:
  - phase: 03-byte-identical-round-trip
    provides: "plans 03-07 (configure.py: WR-07, IN-08..IN-11), 03-08 (targets.py, splice.py: IN-01..IN-03, IN-06, IN-07, VN-01), 03-09 (real-file tests and docs: IN-04, IN-05), all merged on main"
provides:
  - "Phase gate re-run on the main checkout after the G-03-6 fixes: eight steps, including ninja check-orig through a non-default --orig and ninja verify from a build.ninja in a sub-directory (the real-ninja proofs of IN-10 and IN-11)"
  - "03-REVIEW-DISPOSITION.md: the 13 G-03-6 findings set to fixed with their commits, VN-01 added as row 19, open: 0, total: 19"
affects: [phase-5-landing, phase-6-driver]

actuals:
  tasks: 2
  commits: 1
plan_head_before: edd85b5
plan_head_after: edd85b5

tech-stack:
  added: []
  patterns:
    - "Each gap-closure gate keeps its own build/gate/<plan>/ logs, so earlier gate logs stay"

key-files:
  created: []
  modified:
    - .planning/phases/03-byte-identical-round-trip/03-REVIEW-DISPOSITION.md

key-decisions:
  - "Per the plan checker's advisory, the IN-03, IN-04 and IN-05 disposition rows name their proof (docstring or docs grep that fails at HEAD; reverted mutants for the test refactor), since no RED test exists for them"

patterns-established: []

requirements-completed: [RT-01, RT-03]

coverage:
  - id: D1
    description: "Phase gate on the main checkout after the G-03-6 fixes: host suite, rebuild, cmp, container test, container suite, ninja verify, ninja verify + check-orig through a non-default --orig, ninja verify from a sub-directory build.ninja; all exit 0 with no real-file skip"
    requirement: RT-03
    verification:
      - kind: other
        ref: "build/gate/03-10/01..08 logs, reproduced under '## Phase gate output'"
        status: pass
    human_judgment: false
  - id: D2
    description: "Disposition record: WR-07, IN-01..IN-11 and VN-01 fixed with commit hashes; WR-01/03/04 deferred and WR-02/05/06 fixed unchanged; open: 0, total: 19"
    requirement: RT-01
    verification:
      - kind: other
        ref: "03-10-PLAN.md Task 2 verify (four greps), all pass"
        status: pass
    human_judgment: false

duration: about 10 min (on the main checkout, after the 03-07..03-09 merge)
completed: 2026-10-21
---

# Phase 3 Plan 10: Gate re-run and disposition after G-03-6 Summary

**After 03-07, 03-08 and 03-09 merged, the gate passed on the main checkout. Host: 401 passed. Container: 407 passed with no skip, including the Linux-only non-UTF-8 test. The rebuild, `ninja verify`, `ninja verify` with `ninja check-orig` through `--orig ../tmp/alt-orig`, and `ninja verify` from `build/cfg-03-10/` each print three OK lines, and every cmp is silent. All 13 G-03-6 findings are recorded as fixed.**

## Performance

- **Tasks:** 2, both by the orchestrator on the main checkout.
- **Commits:** 1 (this SUMMARY together with 03-REVIEW-DISPOSITION.md). The gate logs live in gitignored build/.

## Preconditions (as checked, all PASS)

- `test "$(git rev-parse --path-format=absolute --git-dir)" = "$(git rev-parse --path-format=absolute --git-common-dir)"`: main checkout.
- `grep -qF -- '--out build' configure.py`, `grep -q isreserved tools/reverseapoc/targets.py`, `grep -qF '(logical page ' tools/reverseapoc/splice.py`, `grep -qF '.page_va(' tests/test_splice_real.py`, `grep -qF 'SMKP.EXE from your install' docs/toolchain.md`.
- 03-07, 03-08 and 03-09 SUMMARYs present.
- `uv run reverseapoc check-orig`: 3 ok.
- `docker info`: Docker Desktop 29.6.2.

## Disposition update (Task 2)

Commits were cross-checked as ancestors of main with `git merge-base --is-ancestor`.

| Finding | Fixed in | GREEN commit |
|---|---|---|
| WR-07, IN-09 | 03-07 Task 1 | `231ee0d` |
| IN-10, IN-11, IN-08 | 03-07 Task 2 | `bf341b5` |
| IN-06, IN-07 | 03-08 Task 1 | `51a6efc` |
| IN-01, IN-02, IN-03, VN-01 | 03-08 Task 2 | `09781cf` (IN-03 proof: a docstring grep that fails at HEAD) |
| IN-05 | 03-09 Task 1 | `e3abcc6` (proof: reverted mutants; it is a test refactor) |
| IN-04 | 03-09 Task 2 | `154a73c` (proof: a docs grep that fails at HEAD) |

- VN-01, the verifier's note, gained its row (19th) and a frontmatter entry.
- The record now has `open: 0` and `total: 19`.
- WR-01, WR-03 and WR-04 stay deferred to Phases 5 and 6. WR-02, WR-05 and WR-06 stay fixed by 03-06. Both kept their exact wording.
- Task 2 verify: all four checks pass. They require 13 fixed rows; 3 deferred plus the 3 earlier fixed rows unchanged; `open: 0`, `total: 19` and no open row; and 13 `fixed in plan 03-0N (hash)` references.

## Task 1 verify

All eight checks in the plan pass:
- all eight logs end `exit=0`;
- three OK lines each on the host, from `ninja verify`, through the alt `--orig`, and from the sub-directory;
- step 7 holds the `--orig ../tmp/alt-orig --out build` and check-orig command lines, `CHECK-ORIG ../tmp/alt-orig`, `checking ../tmp/alt-orig` and `3 ok, 0 mismatched, 0 missing`;
- step 8 holds `--orig ../../orig --out build` with cmp silent;
- `03-cmp.log` is exactly `exit=0`;
- no real-file skip on the host or in the container.

The default build.ninja was regenerated at the end of step 7.

## Deviations from Plan

**[Additive, plan checker advisory]** The IN-03, IN-04 and IN-05 disposition rows add a "proof:" note after the plan's suffix. The plan's Source suffix and every Task 2 check are unaffected.

**Total deviations:** 1, additive. **Impact:** none.

## Phase gate output

The gate ran on the main checkout at HEAD edd85b5 with Docker Desktop 29.6.2 up. Nothing was edited between the steps. Each step ran in a subshell, with stdout and stderr redirected on the host into `build/gate/03-10/0N-*.log`, followed by one `exit=STATUS` line. The eight logs are reproduced verbatim.

### 1. Host suite: `uv run pytest -q -rs && uv run ruff check .` (build/gate/03-10/01-host-suite.log)

```
.................................................ss...............s..... [ 17%]
...................................sss.................................. [ 35%]
........................................................................ [ 53%]
........................................................................ [ 70%]
........................................................................ [ 88%]
...............................................                          [100%]
=========================== short test summary info ===========================
SKIPPED [2] tests\test_configure.py:199: Windows file names cannot hold | or LF
SKIPPED [1] tests\test_configure.py:273: needs a file system that stores non-UTF-8 byte names
SKIPPED [3] tests\test_hygiene.py:180: only inside the container
401 passed, 6 skipped in 4.36s
All checks passed!
exit=0
```

### 2. Host rebuild: `uv run reverseapoc rebuild` (build/gate/03-10/02-rebuild.log)

```
OK        UFO2P.EXE  sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 == manifest
OK        TACP.EXE   sha1 48ef00969d8880a0a152de1b652853fa7ac27393 == manifest
OK        SMKP.EXE   sha1 efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc == manifest
exit=0
```

### 3. Byte compare: `cmp build/UFO2P.EXE orig/UFO2P.EXE && cmp build/TACP.EXE orig/TACP.EXE && cmp build/SMKP.EXE orig/SMKP.EXE` (build/gate/03-10/03-cmp.log)

```
exit=0
```

### 4. Container test service: `docker compose run --rm test` (build/gate/03-10/04-container-test.log)

```
 Container reverseapoc-test-run-4db06d315a43 Creating 
 Container reverseapoc-test-run-4db06d315a43 Created 
Resolved 8 packages in 5ms
Checked 7 packages in 6ms
........................................................................ [ 17%]
........................................................................ [ 35%]
........................................................................ [ 53%]
........................................................................ [ 70%]
........................................................................ [ 88%]
...............................................                          [100%]
407 passed in 5.72s
exit=0
```

### 5. Container suite: `docker compose run --rm build bash -lc "uv sync --locked && uv run pytest -q -rs && uv run ruff check ."` (build/gate/03-10/05-container-suite.log)

```
 Container reverseapoc-build-run-81d04d1528af Creating 
 Container reverseapoc-build-run-81d04d1528af Created 
Resolved 8 packages in 2ms
Checked 7 packages in 3ms
........................................................................ [ 17%]
........................................................................ [ 35%]
........................................................................ [ 53%]
........................................................................ [ 70%]
........................................................................ [ 88%]
...............................................                          [100%]
407 passed in 5.53s
All checks passed!
exit=0
```

### 6. Container ninja verify: `docker compose run --rm build bash -lc "uv run python configure.py && ninja verify"` (build/gate/03-10/06-container-ninja-verify.log)

```
 Container reverseapoc-build-run-934efefb42bd Creating 
 Container reverseapoc-build-run-934efefb42bd Created 
wrote /work/build.ninja (3 executable(s) for parse-le)
[0/1] REBUILD build/
OK        UFO2P.EXE  sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 == manifest
OK        TACP.EXE   sha1 48ef00969d8880a0a152de1b652853fa7ac27393 == manifest
OK        SMKP.EXE   sha1 efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc == manifest
exit=0
```

### 7. Container ninja verify and check-orig through a non-default --orig: `docker compose run --rm build bash -lc 'mkdir -p /tmp/alt-orig && ln -sf /work/orig/UFO2P.EXE /work/orig/TACP.EXE /work/orig/SMKP.EXE /tmp/alt-orig/ && uv run python configure.py --orig /tmp/alt-orig && ninja -t commands verify check-orig && ninja verify && ninja check-orig; status=$?; uv run python configure.py; exit $status'` (build/gate/03-10/07-container-ninja-alt-orig.log)

```
 Container reverseapoc-build-run-411a31c2fb62 Creating 
 Container reverseapoc-build-run-411a31c2fb62 Created 
wrote /work/build.ninja (3 executable(s) for parse-le)
uv run reverseapoc rebuild --orig ../tmp/alt-orig --out build
uv run reverseapoc check-orig --orig ../tmp/alt-orig
[0/1] REBUILD build/
OK        UFO2P.EXE  sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 == manifest
OK        TACP.EXE   sha1 48ef00969d8880a0a152de1b652853fa7ac27393 == manifest
OK        SMKP.EXE   sha1 efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc == manifest
[0/1] CHECK-ORIG ../tmp/alt-orig
checking ../tmp/alt-orig
  OK        UFO2P.EXE  1705790 bytes  sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56
  OK        TACP.EXE   3161594 bytes  sha1 48ef00969d8880a0a152de1b652853fa7ac27393
  OK        SMKP.EXE   271436 bytes  sha1 efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc
3 ok, 0 mismatched, 0 missing
wrote /work/build.ninja (3 executable(s) for parse-le)
exit=0
```

### 8. Container ninja verify from a sub-directory build.ninja: `docker compose run --rm build bash -lc 'rm -rf build/cfg-03-10 && mkdir -p build/cfg-03-10 && uv run python configure.py --output build/cfg-03-10/build.ninja && cd build/cfg-03-10 && ninja -t commands verify && ninja verify && cmp build/UFO2P.EXE ../../orig/UFO2P.EXE && cmp build/TACP.EXE ../../orig/TACP.EXE && cmp build/SMKP.EXE ../../orig/SMKP.EXE'` (build/gate/03-10/08-container-ninja-subdir.log)

```
 Container reverseapoc-build-run-2323251a66cf Creating 
 Container reverseapoc-build-run-2323251a66cf Created 
wrote build/cfg-03-10/build.ninja (3 executable(s) for parse-le)
uv run reverseapoc rebuild --orig ../../orig --out build
[0/1] REBUILD build/
OK        UFO2P.EXE  sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 == manifest
OK        TACP.EXE   sha1 48ef00969d8880a0a152de1b652853fa7ac27393 == manifest
OK        SMKP.EXE   sha1 efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc == manifest
exit=0
```

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

G-03-6 is closed. Ready for the re-review, re-verification and `/gsd-verify-work 3` (test 6). WR-01 and WR-03 (Phase 5) and WR-04 (Phase 6) stay deferred in STATE.md concerns.

## Self-Check: PASSED

- The eight gate logs each end `exit=0` and are reproduced above.
- 03-REVIEW-DISPOSITION.md: 13 rows fixed, 3 deferred, 3 earlier fixes unchanged, `open: 0`, `total: 19`.
- The six GREEN commits are on main.
