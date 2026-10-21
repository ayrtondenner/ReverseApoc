---
phase: 04-compiler-identification
plan: 01
subsystem: tooling
tags: [watcom, wcc386, wibo, compiler-wrapper, cflags, hash-gate, cli]

requires:
  - phase: 02-watcom-media
    provides: "config/watcom.toml key files, watcom.load_watcom_manifest and watcom.check_version"
  - phase: 03-rebuild
    provides: "splice._write_atomic, configure.py's _SAFE_ORIG allowlist idea"
provides:
  - "`uv run reverseapoc cc SRC -o OBJ` (D-11): compiles one source natively on win32 or under wibo on Linux"
  - "config/cflags.txt (D-12) with the `*  wcc386@10.6  -5r -s` default, parsed and validated by tools/reverseapoc/cflags.py"
  - "hash gate (D-13) over BINNT/WCC386.EXE + BINW/WCC386.EXE (10.x) or BINNT/WCCD386.DLL (11.x), banner from a no-argument run, cached in build/cache/watcom-<compiler>-<version>.json"
  - "Watcom-safe guest paths (D-14): root-relative, backslashes, own-tree -i= only, allowlist [A-Za-z0-9._/-]"
  - "compile_rule(rule, src, obj, ...) for plan 04-08's probe calibration; CompileResult.to_json() for plan 04-04"
affects: [04-04, 04-08, 04-11, 04-12, phase-05-configure-ninja, phase-06-hooks]

actuals:
  tokens: 14224
  tasks: 3
  commits: 6
plan_head_before: e24d37a624e84c4cc601e0eff8abc7681673f327
plan_head_after: 1bf0f0465b34278b51474c5cd35287ea56cbd4d4

tech-stack:
  added: []
  patterns:
    - "Injected runner (subprocess.run stand-in) for every compiler call; tests use tests/watcomtree.FakeCompiler"
    - "Child environment rebuilt from scratch (PATH, plus SYSTEMROOT/TEMP/TMP on win32)"
    - "Best-effort atomic stamp cache: a torn, unreadable or wrong-shaped stamp is a miss, a lost write race costs a re-hash"

key-files:
  created:
    - tools/reverseapoc/cflags.py
    - tools/reverseapoc/compiler.py
    - config/cflags.txt
    - tests/test_cflags.py
    - tests/test_compiler.py
    - tests/watcomtree.py
  modified:
    - tools/reverseapoc/cli.py
    - tests/test_cli.py

key-decisions:
  - "Paths are checked before the gate, so a refused source or object never reaches even the banner probe"
  - "The gate stamp write is best effort: splice._write_atomic uses a fixed temp name, so a parallel cc can lose the race; that costs a re-hash, never a failed compile"
  - "With --json, the compiler's own messages go to stderr so stdout stays one JSON document"
  - "cflags errors quote flags with backticks, not repr(), so a backslash is shown as the file spells it"
  - "-i is wrapper-owned only as `-i` or `-i=...`; every other WRAPPER_OWNED entry is a prefix match"

patterns-established:
  - "Compiler wrapper tests: a fake tree plus a manifest written from hashlib digests of made-up bytes; never hashes from config/watcom.toml"
  - "Log line format for build/logs/cc.log: UTC time, spec, banner, path=sha1 pairs in manifest key-file order, argv, exit status, two spaces between fields"

requirements-completed: [CID-01, CID-02]

coverage:
  - id: D1
    description: "`reverseapoc cc` compiles a real source with the 10.6 tree on the Windows host through the gate, prints an OK line naming wcc386@10.6 and the banner, writes the object"
    requirement: CID-01
    verification:
      - kind: unit
        ref: "tests/test_compiler.py#test_cc_compiles_through_gate"
        status: pass
      - kind: unit
        ref: "tests/test_cli.py#test_cc_ok_line_and_exit_code"
        status: pass
      - kind: integration
        ref: "uv run reverseapoc cc build/cc-tracer/t.c -o build/cc-tracer/t.obj --watcom-dir <main checkout>/third_party/watcom"
        status: pass
    human_judgment: false
  - id: D2
    description: "Hash gate refuses missing, mismatched, zero-length and known-bad gated binaries and a missing tree, naming the file and install-watcom; banner must name the version"
    requirement: CID-01
    verification:
      - kind: unit
        ref: "tests/test_compiler.py#test_gate_refuses_known_bad"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_gate_refuses_mismatch"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_gate_refuses_missing"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_missing_tree_refused"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_zero_length_compiler_is_a_mismatch"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_banner_must_name_version"
        status: pass
    human_judgment: false
  - id: D3
    description: "Banner and both gated SHA-1s are appended to build/logs/cc.log with argv and exit status, gate files in manifest key-file order"
    requirement: CID-01
    verification:
      - kind: unit
        ref: "tests/test_compiler.py#test_log_lists_gate_files_in_manifest_order"
        status: pass
      - kind: integration
        ref: "real compile: last cc.log line holds Version 10.6 and two 40-hex SHA-1s"
        status: pass
    human_judgment: false
  - id: D4
    description: "config/cflags.txt rules: `*` first, last match wins, validated per line (compiler, version, flag shape, 9 wrapper-owned flags) with file:line errors"
    requirement: CID-02
    verification:
      - kind: unit
        ref: "tests/test_cflags.py (26 tests, incl. test_wrapper_owned_flags_refused x9)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Two sources compiled through rules that assign different versions and flags reach the runner with their own tree, include path and flags"
    requirement: CID-02
    verification:
      - kind: unit
        ref: "tests/test_compiler.py#test_two_sources_get_their_rules"
        status: pass
    human_judgment: false
  - id: D6
    description: "Argv shape, scrubbed environment, wibo prefix off win32, path allowlist refusals before the runner, own-tree include only"
    verification:
      - kind: unit
        ref: "tests/test_compiler.py#test_argv_shape"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_env_is_scrubbed"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_guest_path_refusals (8 cases)"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_include_is_own_tree_only"
        status: pass
    human_judgment: false
  - id: D7
    description: "Gate stamp: reused while root, size, mtime and manifest SHA-1 match; written via _write_atomic; torn or wrong-shaped stamps are misses"
    verification:
      - kind: unit
        ref: "tests/test_compiler.py -k stamp (8 tests)"
        status: pass
      - kind: integration
        ref: "real compile leaves build/cache/watcom-wcc386-10.6.json"
        status: pass
    human_judgment: false
  - id: D8
    description: "A failed compile leaves no object, keeps the .err next to the object, prints FAILED with the exit status, and cc exits 1"
    verification:
      - kind: unit
        ref: "tests/test_compiler.py#test_failed_compile_cleans_up"
        status: pass
      - kind: unit
        ref: "tests/test_compiler.py#test_err_file_stays_under_object_dir"
        status: pass
      - kind: unit
        ref: "tests/test_cli.py#test_cc_failed_compile_exits_1"
        status: pass
      - kind: integration
        ref: "real compile of a broken source: FAILED exit 3, cc rc 1, bad.err under build/cc-tracer, no .err in the root"
        status: pass
    human_judgment: false
  - id: D9
    description: "The container (wibo) backend compiles for real"
    verification: []
    human_judgment: true
    rationale: "Only unit-tested here (argv with the wibo prefix); the real container run is the phase gate in plan 04-12"

duration: 12min
completed: 2026-10-21
status: complete
---

# Phase 4 Plan 01: Compiler wrapper (`reverseapoc cc`) Summary

**`reverseapoc cc SRC -o OBJ` picks compiler@version and flags from config/cflags.txt, checks the Watcom binaries' size and SHA-1 against config/watcom.toml (cached in an atomic stamp), logs the compiler's own banner with the SHA-1s, and runs BINNT/WCC386.EXE with a rebuilt environment and allowlisted backslash paths, natively on Windows or under wibo.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-10-21T15:20:52Z
- **Completed:** 2026-10-21T15:33:15Z
- **Tasks:** 3 (tracer + 2 expansions)
- **Files modified:** 8 (6 created, 2 modified)

## Accomplishments

- The real 10.6 compiler, read-only from the main checkout, compiled `build/cc-tracer/t.c` on the Windows host: `OK  build/cc-tracer/t.c -> build/cc-tracer/t.obj  wcc386@10.6  WATCOM C32 Optimizing Compiler  Version 10.6`. The cc.log line holds the banner and both gated SHA-1s (BINNT/WCC386.EXE, BINW/WCC386.EXE).
- config/cflags.txt (D-12) is parsed and validated per line; the 9 wrapper-owned flags, bad flag shapes, unknown compilers and versions are refused with `file:line` errors. Two sources get their own tree, include path and flags (CID-02).
- Hash gate (D-13) refuses missing, mismatched, zero-length and known-bad binaries and a missing tree before anything runs; a still-valid stamp skips both the re-hash and the banner probe.
- Paths (D-14) are root-relative with backslashes; a space, leading `-`, `..` segment, path outside the root or a character outside `[A-Za-z0-9._/-]` is refused before the runner. Only the selected version's own `H` reaches `-i=`.
- A real failing compile (broken source) gave `FAILED ... exit 3`, cc exit 1, no object, `bad.err` next to the object and no `.err` in the repository root.

## Task Commits

1. **Task 1: Tracer, `reverseapoc cc` through the hash gate**: `04898bc` (test, RED), `168de28` (feat, GREEN)
2. **Task 2: cflags.txt validation and per-file rules (CID-02)**: `1d2da24` (test, RED), `792c44e` (feat, GREEN)
3. **Task 3: path allowlist, atomic gate stamp, failed-compile cleanup**: `5fbd03e` (test, RED), `1bf0f04` (feat, GREEN)

**Plan metadata:** recorded in the docs(04-01) commit that adds this file.

## TDD Gate Compliance

Every task has a `test(04-01)` commit before its `feat(04-01)` commit; no REFACTOR commits were needed.

- **Task 1 RED:** test_cflags.py and test_compiler.py failed at collection (`cannot import name 'compiler'`); in test_cli.py, `test_cc_help_lists_options` failed its assertion (no `cc` verb) and the three fixture-based cc tests errored on the missing module, while the 42 existing CLI tests stayed green. Semantic assessment: this is the RED the plan asks for ("fail because the modules and the verb do not exist"). It is a load failure, not an assertion failure, for the new modules.
- **Task 2 RED:** 19 new cases failed with `DID NOT RAISE CflagsError` (one `*` line raised an unpacking ValueError), which is the missing validation. `test_two_sources_get_their_rules` passed already because Task 1's rule lookup was correct, as the plan expected.
- **Task 3 RED:** the 8 path-refusal cases and the bad-character and rewrite tests failed with `DID NOT RAISE CompilerError`. `test_stamp_cache_skips_rehash` failed because no stamp file existed, `test_stamp_written_atomically` because `compiler._write_atomic` did not exist yet, and the CLI space test on its assertion. Some guard tests (failed-compile cleanup, missing tree, manifest-order log) already passed from Task 1 and pin that behaviour.
- The `gsd-tools check tdd-red-evidence` classifier was not run. This is a `type: execute` plan with `tdd="true"` tasks and `workflow.tdd_mode` is not set, so the evidence above is from the pytest output.

## Files Created/Modified

- `tools/reverseapoc/cflags.py`: CflagsError, Rule, COMPILERS, WRAPPER_OWNED, DEFAULT_CFLAGS, parse_cflags, load_cflags, select_rule
- `tools/reverseapoc/compiler.py`: CompilerError, Gate, CompileResult, gate_paths, check_gate (with stamp), scrubbed_env, runner_prefix, guest_path, build_argv, compile_rule, compile_source
- `tools/reverseapoc/cli.py`: `cc` verb and `_cmd_cc`; CompilerError and CflagsError map to `reverseapoc cc: error: ...`
- `config/cflags.txt`: the D-12 table with the `*  wcc386@10.6  -5r -s` default
- `tests/watcomtree.py`: fake trees, manifest writer, FakeCompiler runner (shared by test_compiler and test_cli)
- `tests/test_cflags.py`, `tests/test_compiler.py`, `tests/test_cli.py`: 26 + 48 + 7 new tests

## Decisions Made

- Paths are checked before the gate. The plan's Task 1 action said "gate first", but the must-have says unsafe paths are refused before the runner is called, and the banner probe is a runner call. This order meets both.
- The stamp is a best-effort cache (details under Deviations).
- With `--json`, the compiler's messages go to stderr.
- `runner_prefix(platform, *, which=None)` looks up `shutil.which` when it is called rather than binding it as a default, so tests can patch it. Behaviour is otherwise as the plan specifies.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Correctness] Path validation runs before the hash gate**
- **Found during:** Task 1
- **Issue:** The plan's action ordered "Gate first", but the gate runs the compiler once (the banner probe), and the must-have needs unsafe paths refused before any runner call.
- **Fix:** compile_rule computes and checks all guest paths, then the gate, then the compile.
- **Files modified:** tools/reverseapoc/compiler.py
- **Verification:** test_guest_path_refusals (8 cases) and test_guest_path_outside_root_refused assert `runner.calls == []`
- **Committed in:** 168de28, 1bf0f04

**2. [Rule 1 - Bug] Stamp write races between parallel `cc` processes**
- **Found during:** Task 3
- **Issue:** splice._write_atomic always uses the temp name `.<name>.tmp`. Two parallel `cc` processes (ninja -j) can unlink or replace each other's temp file, which raises FileNotFoundError or, on Windows, PermissionError. That would fail a compile over a cache write.
- **Fix:** _write_stamp swallows OSError. The stamp only ever appears whole (os.replace), so the worst outcome is a torn or missing stamp, which the reader treats as a miss and re-hashes.
- **Files modified:** tools/reverseapoc/compiler.py
- **Verification:** test_stamp_written_atomically, and test_stamp_with_the_wrong_shape_is_a_miss (4 cases, empty file included)
- **Committed in:** 1bf0f04

**3. [Rule 2 - Correctness] `--json` keeps stdout parseable**
- **Found during:** Task 1
- **Issue:** Printing the compiler's messages before the JSON document would break `json.loads` on stdout.
- **Fix:** In `--json` mode the messages go to stderr. Text mode prints them to stdout as planned.
- **Files modified:** tools/reverseapoc/cli.py
- **Verification:** tests/test_cli.py#test_cc_json
- **Committed in:** 168de28

**4. [Rule 3 - Blocking] Shared test helper module**
- **Found during:** Task 1
- **Issue:** test_compiler.py and test_cli.py both need the fake tree, the manifest writer and the fake runner, and tests/watcomtree.py is not in the plan's file list.
- **Fix:** Added tests/watcomtree.py, following tests/isoimage.py. It holds made-up bytes only, and the manifest is built from their hashlib digests.
- **Committed in:** 04898bc, 5fbd03e

**5. [Rule 1 - Bug] Flag errors showed backslashes doubled**
- **Found during:** Task 2
- **Issue:** repr() doubled the backslash in `-i=C:\x`, so the error did not show the flag as the file spells it.
- **Fix:** Flags are quoted with backticks.
- **Committed in:** 792c44e

**6. [Test adjustment] test_argv_shape's linux leg uses its own stamp directory**
- **Found during:** Task 3
- **Issue:** Once the cache existed, the linux leg reused the win32 leg's valid stamp, so no wibo banner probe ran for the test to see. That is correct cache behaviour.
- **Fix:** The linux leg passes `stamps=<root>/cache-linux`.
- **Committed in:** 1bf0f04

---

**Total deviations:** 6 (2 Rule 1, 2 Rule 2, 1 Rule 3, 1 test adjustment). **Impact:** all are needed for correctness or testability. Nothing is out of scope: no new options and no new dependency.

## Issues Encountered

- The real 10.6 compiler exits 3 on the broken probe source. The research recorded rc 1 or 2 for 10.6 compile errors. The wrapper treats any non-zero exit as a failure, so nothing depends on the exact code.
- The worktree has no third_party/, so the real compiles used the main checkout's trees read-only through `--watcom-dir`, as the plan's worktree note says.

## Threat Flags

None. Every surface this plan adds is in its threat model (T-04-01 to T-04-06). The stamp trusts unchanged size and mtime, as T-04-04 specifies.

## User Setup Required

None.

## Next Phase Readiness

- Plan 04-04 can add object hashes on top of `CompileResult`/`to_json()`. Plan 04-08 can call `compile_rule` directly. Plan 04-11 replaces the `*` rule's flags.
- The container (wibo) backend is covered by unit tests only. Plan 04-12 proves the real run.
- CID-01 and CID-02 are also declared by sibling plans, so `requirements.ready-ids` reports both as blocked. REQUIREMENTS.md was not changed.

---
*Phase: 04-compiler-identification*
*Completed: 2026-10-21*

## Self-Check: PASSED

- Files found: tools/reverseapoc/cflags.py, tools/reverseapoc/compiler.py, config/cflags.txt, tests/test_cflags.py, tests/test_compiler.py, tests/watcomtree.py, this SUMMARY.
- Commits found on this branch: 04898bc, 168de28, 1d2da24, 792c44e, 5fbd03e, 1bf0f04.
- Last full run: `uv run pytest -q` gave 514 passed, 45 skipped. `uv run ruff check .` was clean. The real host compile (OK line, object, stamp, cc.log line with two SHA-1s, no `.err` in the root) passed.
