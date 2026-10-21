---
phase: 04-compiler-identification
plan: 06
subsystem: tooling
tags: [watcom, wpack, install-watcom, manifest, d-01, cid-01]

requires:
  - phase: 04-compiler-identification (plan 04-03)
    provides: "wpack decoder (join_parts, decode_member, WpackError) and D-01 verdict: LANDED"
  - phase: 04-compiler-identification (plan 04-01)
    provides: "compiler gate (cc) reading config/watcom.toml key files through load_watcom_manifest"
provides:
  - "KeyFile.wpack / KeyFile.wpack_member, validated by load_watcom_manifest (both or neither)"
  - "install-watcom decodes wpack key files inside the .<ver>.partial tree before the final replace"
  - "check-watcom MISMATCH hint for wpack key files: re-run install-watcom <ver> --force"
  - "config/watcom.toml pins the decoded 10.5 BINW/WCC386.EXE (567558 bytes), no longer known_bad"
  - "test_decoded_compiler_matches_manifest: the pin re-derived from the ISO on every real run"
affects: [04-11, 04-12, compiler gate, check-watcom, install-watcom]

actuals:
  tokens: 3984
  tasks: 2
  commits: 4
plan_head_before: 5f2d1866396e45929706467c19f53ad018b4e985
plan_head_after: 6c4681cd48d93433cc84f9bd95245385ee7426ef

tech-stack:
  added: []
  patterns:
    - "A key file can name the archive it is decoded from; install writes the decoded member to the key file's own manifest path, never to an archive-supplied name"
    - "Real-media tests read expected hashes through load_watcom_manifest, never a copied literal"

key-files:
  created: []
  modified:
    - tools/reverseapoc/watcom.py
    - config/watcom.toml
    - tests/test_watcom.py
    - tests/test_wpack_real.py

key-decisions:
  - "The 10.5 BINW/WCC386.EXE pin comes from this plan's own decode (install into build/watcom-scratch, then targets.hash_file); it matches plan 04-03's LANDED values, which were used only as a cross-check"
  - "Task 2's tests were written and committed (RED) before the pin commit, so the pin commit is the GREEN step and still touches only the one manifest entry"
  - "A missing archive part is reported by name before decoding; WpackError (CRC, size, member) is wrapped as WatcomError naming the version, key file and parts, and the existing finally clause removes the partial tree"

patterns-established:
  - "wpack key files: `wpack = [parts...]` plus `wpack_member`, hashes are those of the decoded file"

requirements-completed: [CID-01]

coverage:
  - id: D1
    description: "Manifest accepts and validates wpack/wpack_member on key files (both or neither, non-empty strings)"
    requirement: CID-01
    verification:
      - kind: unit
        ref: "tests/test_watcom.py#test_manifest_wpack_fields_parse"
        status: pass
      - kind: unit
        ref: "tests/test_watcom.py#test_manifest_wpack_validation"
        status: pass
    human_judgment: false
  - id: D2
    description: "install-watcom decodes a wpack key file inside the partial tree and fails cleanly (WatcomError, nothing installed, previous install kept) on a corrupt part, a size mismatch or a missing part"
    requirement: CID-01
    verification:
      - kind: integration
        ref: "tests/test_watcom.py#test_install_decodes_wpack_key_file"
        status: pass
      - kind: integration
        ref: "tests/test_watcom.py#test_install_wpack_corrupt_part_fails_cleanly"
        status: pass
      - kind: integration
        ref: "tests/test_watcom.py#test_install_wpack_size_mismatch_fails"
        status: pass
      - kind: integration
        ref: "tests/test_watcom.py#test_install_wpack_missing_part_fails"
        status: pass
      - kind: integration
        ref: "tests/test_watcom.py#test_install_wpack_failure_keeps_previous_install"
        status: pass
    human_judgment: false
  - id: D3
    description: "check-watcom tells an install holding the old stub to re-run install-watcom --force"
    requirement: CID-01
    verification:
      - kind: unit
        ref: "tests/test_watcom.py#test_check_hint_for_wpack_mismatch"
        status: pass
      - kind: manual_procedural
        ref: "uv run reverseapoc check-watcom 10.5 --dest build/watcom-old (stub copied from the ISO): MISMATCH ... (re-run `uv run reverseapoc install-watcom 10.5 --force` to decode it)"
        status: pass
    human_judgment: false
  - id: D4
    description: "config/watcom.toml pins the decoded 10.5 compiler; a real install checks 8 ok, its banner says Version 10.5, and cc compiles with wcc386@10.5"
    requirement: CID-01
    verification:
      - kind: integration
        ref: "REVERSEAPOC_WATCOM_MEDIA=<main>/third_party/watcom-media uv run pytest -rs tests/test_wpack_real.py#test_decoded_compiler_matches_manifest"
        status: pass
      - kind: unit
        ref: "tests/test_watcom.py#test_default_manifest_pinned_values"
        status: pass
      - kind: e2e
        ref: "uv run reverseapoc check-watcom 10.5 --dest build/watcom-scratch && uv run reverseapoc cc build/cc-105/t.c ... --watcom-dir build/watcom-scratch | grep -q '^OK .*wcc386@10.5.*Version 10.5'"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-10-21
status: complete
---

# Phase 4 Plan 06: Decode and pin the 10.5 compiler Summary

**install-watcom now decodes the 10.5 compiler from its two-part wpack archive inside the partial tree, and config/watcom.toml pins that decoded 567,558-byte BINW/WCC386.EXE in place of the KNOWN BAD stub. The values come from this plan's own decode, and a fresh install checks 8 OK, prints "Version 10.5" and compiles through the cc gate.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-10-21T16:24:35Z
- **Completed:** 2026-10-21T16:34:32Z
- **Tasks:** 2 of 2
- **Files modified:** 4

## Accomplishments

- `KeyFile` gains `wpack` (parts in order) and `wpack_member`. `_parse_wpack` checks both fields: the parts must be a list of non-empty strings, the member must be a string, and the two come together or not at all. Each error names the key file.
- `install_version` calls `_decode_wpack_key_files(media, partial)` after `extract_all` and before the final replace. That runs `decode_member(join_parts(parts), kf.wpack_member, expected_size=kf.size)` and writes the result to `partial / kf.path` only. A missing part, a CRC failure or a size mismatch raises `WatcomError` naming the version, the key file and the parts, and nothing is left behind.
- When a wpack key file is MISMATCH, `VersionCheck.format()` adds `(re-run \`uv run reverseapoc install-watcom <ver> --force\` to decode it)`.
- The 10.5 `BINW/WCC386.EXE` is pinned as one reviewed commit (`6c4681c`) that touches only that entry.

## Real-media evidence (D-01)

All numbers come from this plan's run against the owner's ISO, read-only from the main checkout's `third_party/watcom-media`, installed into the worktree's `build/watcom-scratch`. The scratch tree was deleted afterwards.

| What | Value |
|------|-------|
| install-watcom 10.5 (entry edited, old hashes) | size matched; got md5 `17751042fa2927337ba69bc0bfb16684`, sha1 `a479921bf3bfc6a092710ab291d00752a09d782b`, crc32 `daa1ad2a` |
| targets.hash_file, run separately | `567558 17751042fa2927337ba69bc0bfb16684 a479921bf3bfc6a092710ab291d00752a09d782b daa1ad2a` |
| plan 04-03 LANDED (cross-check only) | 567,558 / `17751042...` / `a479921b...` / `0xDAA1AD2A`: same values |
| Banner, checked before pinning (`BINNT/WCC386.EXE`, no args, exit 1 by design) | `WATCOM C32 Optimizing Compiler  Version 10.5` |
| check-watcom 10.5 after the pin | `8 ok, 0 mismatched, 0 missing, 0 known bad` |
| cc OK line | `OK      build/cc-105/t.c -> build/cc-105/t.obj  wcc386@10.5  WATCOM C32 Optimizing Compiler  Version 10.5` |
| Old install (CD stub copied into a copy of the tree) | `MISMATCH  BINW/WCC386.EXE  size: expected 567558, got 65536; ... (re-run \`uv run reverseapoc install-watcom 10.5 --force\` to decode it)` |

## Task Commits

1. **Task 1 (tracer): install-watcom decodes a wpack key file inside the partial tree**
   - RED `ba5abd8` test(04-06): 15 failing tests (manifest parse/validation, install decode, corrupt/size/missing part, previous install kept, check hint)
   - GREEN `4e1012c` feat(04-06): watcom.py support plus the manifest header comment (comment only)
2. **Task 2: Pin the decoded 10.5 compiler**
   - RED `9480ec5` test(04-06): test_decoded_compiler_matches_manifest and the updated test_default_manifest_pinned_values, failing against the unpinned manifest
   - GREEN `6c4681c` feat(04-06): the pin, config/watcom.toml alone, with the derivation in the message

**Plan metadata:** this SUMMARY commit (docs)

## TDD Gate Compliance

- Task 1 RED: `uv run pytest -q tests/test_watcom.py -k wpack --junitxml=...` exited 1 with 15/15 failing. `gsd-tools check tdd-red-evidence` returned `RED_EVIDENCE_OK` (target `test_install_decodes_wpack_key_file`). Semantic assessment: every test failed on the planned behavior. The decode test got `['mismatch'] == ['ok']`, the validation, corrupt-part, size and missing-part tests got `DID NOT RAISE`, and the hint test failed its `endswith` assertion. The parse test hit an `AttributeError` on the not-yet-existing `KeyFile.wpack` field, which is the missing feature itself, not a setup fault.
- Task 2 RED: with real media, `test_decoded_compiler_matches_manifest` failed on `assert () == (PARTS)` and `test_default_manifest_pinned_values` failed on `65536 == 567558`. The two existing real tests passed and nothing was skipped. The classifier returned `RED_EVIDENCE_OK` (target `test_decoded_compiler_matches_manifest`).
- GREEN commits follow each RED. No refactor commit was needed.

## Files Created/Modified

- `tools/reverseapoc/watcom.py`: KeyFile fields, `_parse_wpack`, `_decode_wpack_key_files`, the decode step in `install_version`, and the re-install hint in `VersionCheck.format()`.
- `config/watcom.toml`: the header documents `wpack`/`wpack_member`. The 10.5 `BINW/WCC386.EXE` entry is pinned to the decoded file and `known_bad` is removed.
- `tests/test_watcom.py`: section 7 (wpack key files, 15 tests) and the updated `test_default_manifest_pinned_values`.
- `tests/test_wpack_real.py`: `test_decoded_compiler_matches_manifest`.

## Decisions Made

- The pin values were derived here. Plan 04-03's numbers served only as a cross-check, and all three sources agree.
- The decoded file is written to the key file's own manifest path. The synthetic test uses a member name (`packed.exe`) that differs from the key path and checks that no file with that name appears.

## Deviations from Plan

**1. [Ordering] Task 2's test commit comes before the pin commit**
- **Found during:** Task 2, steps 4-5
- **Issue:** The plan orders the pin commit (step 4) before the tests (step 5). That would leave a commit where `test_default_manifest_pinned_values` fails, and the new tests would never be seen failing (no RED).
- **Fix:** The values were derived and the banner checked first (steps 2-3), exactly as planned. Then the pinned file was set aside, the HEAD manifest restored, the tests written and run RED against it and committed (`9480ec5`), and finally the pinned manifest restored and committed alone (`6c4681c`).
- **Effect on the plan's checks:** none fail. The pin is still one commit touching only the 10.5 BINW entry, it is still separate from the test commit, and the derivation is in its message.

**2. [Rule 2 - Missing critical] Two extra tests in Task 1**
- `test_install_wpack_missing_part_fails` covers the action's "a missing part raises WatcomError naming it" case, and `test_install_wpack_failure_keeps_previous_install` checks that a failed `--force` re-install leaves the earlier tree in place. Both are in the RED commit.

**Total deviations:** 2 (1 ordering, 1 added coverage). **Impact:** no scope creep, and every planned check still holds.

## Issues Encountered

- Python's `Path.write_text` on Windows wrote CRLF line endings into `watcom.py` during the GREEN edit. I normalized it back to LF before committing, so the committed diff is clean.
- Some combined Bash commands were refused by the worktree-isolation guard. I split them into separate commands. No paths outside the worktree were written; the main checkout's `third_party/watcom-media` was only read.

## Observations for later plans (not changed here)

- The 10.5 `BINNT/WCC386.EXE` entry's note still says "runs BINW/WCC386.EXE (the real LE compiler)". The decoded 10.5 compiler is an LX image (see 04-03). That entry is outside this plan's one-entry pin, so it is left for a docs pass (plan 04-11 or 04-12).
- The main checkout's `third_party/watcom/10.5` still holds the stub, so `check-watcom 10.5` there will report MISMATCH with the `--force` hint until plan 04-11 re-installs it. This is the expected state.

## Verification

- `uv run pytest -q && uv run ruff check .` on the host: 639 passed, 57 skipped, ruff clean. The new real test skips without the media env var, as designed.
- `REVERSEAPOC_WATCOM_MEDIA=<main>/third_party/watcom-media uv run pytest -rs -v tests/test_wpack_real.py`: 3 PASSED (including `test_decoded_compiler_matches_manifest`), no SKIPPED line.
- `uv run pytest -q tests/test_watcom.py -k wpack`: 15 passed.
- Container: `docker compose run --rm test` gave 644 passed, 52 skipped, and `uv run ruff check .` in the build container reported "All checks passed!".
- `grep -v '^#' config/watcom.toml | grep -c known_bad` gives 0. `grep -v '^#' config/watcom.toml | grep -c 'wpack_member = "wcc386.exe"'` gives 1.
- `git show 6c4681c -- config/watcom.toml` changes only lines inside the 10.5 BINW/WCC386.EXE entry.
- `build/watcom-scratch`, `build/watcom-old` and `build/cc-105` were deleted after the gate proof.

## User Setup Required

None. Plan 04-11 runs `uv run reverseapoc install-watcom 10.5 --force` on the main checkout.

## Next Phase Readiness

Plans 04-11 and 04-12 can take their LANDED branches. The 10.5 compiler installs reproducibly from the owner's ISO, it is pinned and gated, and it runs natively.

## Self-Check: PASSED

- Files found: tools/reverseapoc/watcom.py, config/watcom.toml, tests/test_watcom.py, tests/test_wpack_real.py, this SUMMARY.
- Commits on the branch: ba5abd8, 4e1012c, 9480ec5, 6c4681c, 6e1f051. The working tree is clean.

---
*Phase: 04-compiler-identification*
*Completed: 2026-10-21*
