---
phase: 03-byte-identical-round-trip
plan: 02
subsystem: infra
tags: [ninja, configure.py, pytest, hygiene, manifest, D-09, D-15, D-21]

# Dependency graph
requires:
  - phase: 02-container-and-target-ingest
    provides: "configure.py build.ninja skeleton (check-orig, parse-le), targets.load_manifest, tests/test_targets.py manifest pin"
provides:
  - "build.ninja `rule rebuild` (uv run reverseapoc rebuild, console pool) and the phony `verify` edge"
  - "D-15 guard: no file under tests/ except tests/test_targets.py restates a [[targets]] md5/sha1 or its 8-hex prefix"
  - "self-test proving the hash scan can fail"
affects: [03-01 rebuild verb, 03-05 phase gate (`ninja verify` in the container), Phase 6 driver]

actuals:
  tokens: 1619
  tasks: 2
  commits: 4
plan_head_before: 0eb58d6fab08caa1f672ef7a6630d8712c292474
plan_head_after: dd00383ec0cb559ce3e0f0595247c5919a5eb520

tech-stack:
  added: []
  patterns:
    - "Never-written $builddir/always/<name> output plus a phony alias, so a ninja edge runs on every request"
    - "Hygiene guards read the oracle (load_manifest) at test time and carry a tmp_path self-test that proves they can fail"

key-files:
  created: []
  modified:
    - configure.py
    - tests/test_configure.py
    - tests/test_hygiene.py

key-decisions:
  - "Header comment line for `ninja verify` shortened to fit ruff's 100-column limit: 'rebuild every target into build/ and check its SHA-1 (config/targets.toml)'"
  - "The hash scan lower-cases file text before matching, so an upper-case copy of a manifest hash is caught too"
  - "The planted-hash self-test uses the real needle builder (_manifest_hash_needles), so it also proves the 8-digit prefixes are in the needle set"
  - "RED for Task 2 used a do-nothing helper stub returning [] so the target test failed on its assertion, not on a NameError"

patterns-established:
  - "Guard + self-test pair: every scan-style hygiene test ships with a tmp_path test that plants the forbidden content and expects the scan to report it"

requirements-completed: [RT-03]

coverage:
  - id: D1
    description: "`python configure.py` writes build.ninja with `rule rebuild` (uv run reverseapoc rebuild, REBUILD build/, console pool), `build $builddir/always/verify: rebuild` and `build verify: phony $builddir/always/verify`; header lists `ninja verify`; existing edges and strings unchanged"
    requirement: "RT-03"
    verification:
      - kind: unit
        ref: "tests/test_configure.py#test_render_has_verify_edge"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_render_without_executables_still_defines_verify"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_main_writes_verify_edge"
        status: pass
      - kind: unit
        ref: "tests/test_configure.py#test_render_has_phony_targets_and_phase5_note"
        status: pass
    human_judgment: false
  - id: D2
    description: "`ninja verify` actually runs the rebuild verb end to end in the container (ninja is not on the host; the verb comes from plan 03-01)"
    requirement: "RT-03"
    verification: []
    human_judgment: true
    rationale: "Only the generated build.ninja text is tested here; the container run belongs to plan 03-05's phase gate after 03-01's `rebuild` verb is merged"
  - id: D3
    description: "D-15/D-21 guard: no *.py under tests/ other than tests/test_targets.py contains a manifest md5/sha1 in full or as its first 8 hex digits; the scan is proven able to fail"
    verification:
      - kind: unit
        ref: "tests/test_hygiene.py#test_round_trip_tests_never_copy_manifest_hashes"
        status: pass
      - kind: unit
        ref: "tests/test_hygiene.py#test_manifest_hashes_scan_detects_a_planted_hash"
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-10-20
status: complete
---

# Phase 3 Plan 02: Ninja verify edge and manifest-hash guard Summary

**build.ninja gains `rule rebuild` and a phony `verify` edge that runs `uv run reverseapoc rebuild`. A new hygiene test scans tests/ for any copied manifest md5/sha1 (in full or as an 8-hex prefix), and a planted-hash self-test proves the scan can fail.**

## Performance

- **Duration:** about 4 min of execution (after context loading)
- **Started:** 2026-10-20T20:37:57Z
- **Completed:** 2026-10-20T20:41:33Z
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments

- `configure.py`: `rule rebuild` (command `uv run reverseapoc rebuild`, description `REBUILD build/`, `pool = console`) after `rule parse_le`. Edges `build $builddir/always/verify: rebuild` and `build verify: phony $builddir/always/verify` sit right after the check-orig pair. The header comment lists `ninja verify`, and the "never written" sentence now names verify too. `ninja_required_version`, `builddir = build`, the Phase 5 note, the check-orig and parse-le edges and `default check-orig` are unchanged (D-09, RT-03).
- `tests/test_hygiene.py`: `_manifest_hash_needles()` builds 12 needles from `load_manifest()` (3 targets x md5/sha1 x full/8-digit prefix). `_files_with_manifest_hashes(root, needles, exclude)` is a recursive, case-insensitive scan that skips `__pycache__`. `test_round_trip_tests_never_copy_manifest_hashes` asserts the scan of tests/ (excluding `test_targets.py`, D-21) is empty (D-15, T-03-06).
- The guard is proven able to fail in three ways, listed under "How the hash guard was proven able to fail" below.

## Task Commits

1. **Task 1 RED: failing tests for the verify edge**: `ffddbff` (test)
2. **Task 1 GREEN: rule rebuild and the phony verify edge**: `700c6bd` (feat)
3. **Task 2 RED: failing self-test for the manifest-hash scan**: `db20946` (test)
4. **Task 2 GREEN: the D-15 guard over tests/**: `dd00383` (feat)

No REFACTOR commits: nothing needed cleaning after GREEN.

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR |
|------|-----|-------|----------|
| 1 (tracer) | `ffddbff` | `700c6bd` | not needed |
| 2 | `db20946` | `dd00383` | not needed |

- **Task 1 RED:** `uv run pytest -q tests/test_configure.py -k verify --junitxml=build/red/t1.xml` exited 1 with 3 failed. The target `test_render_has_verify_edge` failed on `assert 'rule rebuild' in ...`, and the other two failed on `assert 'build verify: phony' in ...`. Classifier: `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` (format junit, reason target_test_failed). Semantic assessment: every failure was the planned assertion on missing build.ninja text, with no import, collection or fixture faults.
- **Task 1 tracer gate:** interactive run, `human_verify_mode=end-of-phase`, verify is `<automated>` only. The verify was re-run after the GREEN commit: 9 passed, ruff clean. Expansion continued with no checkpoint.
- **Task 2 RED:** `uv run pytest -q tests/test_hygiene.py -k manifest_hashes --junitxml=build/red/t2.xml` exited 1 with 1 failed. The target `test_manifest_hashes_scan_detects_a_planted_hash` failed on `assert [] == ['sub/test_prefix.py', 'test_full.py']`. Classifier: `RED_EVIDENCE_OK`. Semantic assessment: the failure is the planned assertion against a stub helper that reports nothing.
- **GREEN:** `uv run pytest -q` gives 186 passed, 21 skipped. `uv run ruff check .` reports "All checks passed!".

## How the hash guard was proven able to fail

1. **Planted-hash self-test (committed):** a tmp_path tree holds a file with a full manifest SHA-1, a nested file with only its first 8 hex digits, an excluded file with the full SHA-1, a clean file and a `__pycache__` copy. The scan reports exactly `["sub/test_prefix.py", "test_full.py"]`. The planted hash is read through `load_manifest()` at run time and written only under tmp_path, so no hash is committed in tests/.
2. **Emptied needle set (by hand, not committed):** with `_manifest_hash_needles()` temporarily returning `set()`, the self-test failed (`1 failed, 1 passed`) and the guard passed trivially. That is the hole the self-test closes. The edit was reverted before the GREEN commit.
3. **Real tree without the exemption (read-only check):** scanning `tests/` with `exclude=set()` reports `['test_targets.py']`, the one file that pins the manifest (D-21). Only file names were printed, never hashes.

## Files Created/Modified

- `configure.py`: `rule rebuild`, the verify edges, the header comment line and the never-written sentence.
- `tests/test_configure.py`: `_rule_block` helper, `test_render_has_verify_edge`, `test_render_without_executables_still_defines_verify`, `test_main_writes_verify_edge`.
- `tests/test_hygiene.py`: `load_manifest` import, `_HASH_PREFIX_DIGITS`, `_manifest_hash_needles`, `_files_with_manifest_hashes`, `test_manifest_hashes_scan_detects_a_planted_hash`, `test_round_trip_tests_never_copy_manifest_hashes`.

## Decisions Made

- The header comment line is worded "rebuild every target into build/ and check its SHA-1 (config/targets.toml)". The plan's wording ("... against config/targets.toml") made the line 103 characters long, and ruff E501 caps lines at 100.
- The scan matches case-insensitively, so it also catches an upper-case copy of a hash.
- The self-test uses the real `_manifest_hash_needles()`, so emptying or breaking the needle builder (for example by dropping the prefixes) fails it.
- `test_render_has_verify_edge` checks `pool = console` inside the `rule rebuild` block (`_rule_block` helper), not anywhere in the file, as the behaviour spec requires.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Header comment line exceeded ruff's line length**
- **Found during:** Task 1 GREEN
- **Issue:** the plan's literal comment line `#   ninja verify       rebuild every target into build/ and check its SHA-1 against config/targets.toml` is 103 characters, and `uv run ruff check` failed with E501.
- **Fix:** I reworded it to `... check its SHA-1 (config/targets.toml)`. It still contains `ninja verify`, which the test asserts.
- **Files modified:** configure.py
- **Verification:** ruff clean, 9 configure tests pass.
- **Committed in:** `700c6bd`

**2. [Rule 1 - TDD correctness] RED against a stub instead of a missing name**
- **Found during:** Task 2 RED
- **Issue:** the plan says to write the self-test "against a helper that does not exist yet". A NameError is a load-style fault, not a failure on the planned assertion, so it would not be valid RED evidence.
- **Fix:** the RED commit added a one-line stub `_files_with_manifest_hashes` that returns `[]`, so the target test failed on its assertion (RED_EVIDENCE_OK). GREEN replaced the stub.
- **Files modified:** tests/test_hygiene.py
- **Committed in:** `db20946` (RED), `dd00383` (GREEN)

---

**Total deviations:** 2 auto-fixed (1 blocking lint, 1 TDD-evidence correctness).
**Impact on plan:** cosmetic wording plus stronger RED evidence. No scope change, and no file outside the plan's three was touched.

## Issues Encountered

- The session scratchpad is shared with the parallel 03-01 executor, which overwrote two commit-message files (`msg1.txt`, `msg2.txt`) after my commits had used them. The commits are unaffected (`git log` shows the 03-02 subjects and the trailer). Later message files used a `0302-` prefix.
- REQUIREMENTS.md was not changed: `requirements.ready-ids` reports RT-03 as blocked because sibling plans 03-01, 03-04 and 03-05 also declare it and have no SUMMARY yet.

## Verification Results

- `uv run pytest -q -rs`: 186 passed, 21 skipped. All skips are expected in this worktree: 3 container-only, 12 in `tests/test_le_real.py` (orig/ not present), 6 in `tests/test_watcom_real.py` (third_party/watcom-media not present).
- `uv run ruff check .`: "All checks passed!".
- `git diff --exit-code -- config/targets.toml tests/test_targets.py`: exit 0 (neither changed).
- `grep -n "build verify: phony" configure.py` matches at line 72, and `grep -n "command = uv run reverseapoc rebuild" configure.py` matches at line 43.
- Not run here, by design: `ninja verify`. Ninja is not on the host, and the container gate runs from the main checkout in plan 03-05.

## User Setup Required

None. No external service configuration is required.

## Next Phase Readiness

- The `verify` edge calls `uv run reverseapoc rebuild`, which plan 03-01 adds. After both plans merge, `python configure.py && ninja verify` in the container is the RT-03 end-to-end check for plan 03-05.
- From now on, any new test under tests/ that hard-codes a manifest hash fails the suite. Round-trip tests must read expected SHA-1s through `load_manifest`.

## Self-Check: PASSED

- Files present: configure.py, tests/test_configure.py, tests/test_hygiene.py, this SUMMARY.
- Commits on this branch: `ffddbff`, `700c6bd`, `db20946`, `dd00383`, and the SUMMARY commit `00c8421`.
- `uv run pytest -q tests/test_hygiene.py` after the SUMMARY was written: 26 passed, 3 skipped (container-only). The phase-zero and TBD doc checks still pass with this file in .planning/.
- Working tree clean after the commits.

---
*Phase: 03-byte-identical-round-trip*
*Completed: 2026-10-20*
