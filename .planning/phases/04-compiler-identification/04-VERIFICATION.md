---
phase: 04-compiler-identification
verified: 2026-10-23T19:29:44Z
status: passed
score: 26/26 must-haves verified
covered_files: [".planning/phases/04-compiler-identification/04-01-PLAN.md", ".planning/phases/04-compiler-identification/04-01-SUMMARY.md", ".planning/phases/04-compiler-identification/04-02-PLAN.md", ".planning/phases/04-compiler-identification/04-02-SUMMARY.md", ".planning/phases/04-compiler-identification/04-03-PLAN.md", ".planning/phases/04-compiler-identification/04-03-SUMMARY.md", ".planning/phases/04-compiler-identification/04-04-PLAN.md", ".planning/phases/04-compiler-identification/04-04-SUMMARY.md", ".planning/phases/04-compiler-identification/04-05-PLAN.md", ".planning/phases/04-compiler-identification/04-05-SUMMARY.md", ".planning/phases/04-compiler-identification/04-06-PLAN.md", ".planning/phases/04-compiler-identification/04-06-SUMMARY.md", ".planning/phases/04-compiler-identification/04-07-PLAN.md", ".planning/phases/04-compiler-identification/04-07-SUMMARY.md", ".planning/phases/04-compiler-identification/04-08-PLAN.md", ".planning/phases/04-compiler-identification/04-08-SUMMARY.md", ".planning/phases/04-compiler-identification/04-09-PLAN.md", ".planning/phases/04-compiler-identification/04-09-SUMMARY.md", ".planning/phases/04-compiler-identification/04-10-PLAN.md", ".planning/phases/04-compiler-identification/04-10-SUMMARY.md", ".planning/phases/04-compiler-identification/04-11-PLAN.md", ".planning/phases/04-compiler-identification/04-11-SUMMARY.md", ".planning/phases/04-compiler-identification/04-12-PLAN.md", ".planning/phases/04-compiler-identification/04-12-SUMMARY.md", ".planning/phases/04-compiler-identification/04-13-PLAN.md", ".planning/phases/04-compiler-identification/04-13-SUMMARY.md", "config/cflags.txt", "config/tacp/runtime.csv", "config/ufo2p/runtime.csv", "config/watcom.toml", "docs/learnings.md", "docs/matching.md", "docs/research/wpack-format.md", "docs/toolchain.md", "probe/README.md", "probe/cg_basic.c", "tests/conftest.py", "tests/omfimage.py", "tests/test_cc_log.py", "tests/test_cflags.py", "tests/test_cli.py", "tests/test_compiler.py", "tests/test_compiler_real.py", "tests/test_cppscan.py", "tests/test_cppscan_real.py", "tests/test_hygiene.py", "tests/test_libmatch.py", "tests/test_libmatch_real.py", "tests/test_omf.py", "tests/test_omf_real.py", "tests/test_probe.py", "tests/test_probe_real.py", "tests/test_targets.py", "tests/test_watcom.py", "tests/test_wpack.py", "tests/test_wpack_real.py", "tests/wpackimage.py", "tools/reverseapoc/cflags.py", "tools/reverseapoc/cli.py", "tools/reverseapoc/compiler.py", "tools/reverseapoc/cppscan.py", "tools/reverseapoc/libmatch.py", "tools/reverseapoc/omf.py", "tools/reverseapoc/probe.py", "tools/reverseapoc/targets.py", "tools/reverseapoc/watcom.py", "tools/reverseapoc/wpack.py"]
covered_digest: "v3:sha256:63f02d16c0450ac4582866da237ba2016b4fb97492153837e8df72916ffbad2a"
behavior_unverified: 0
overrides_applied: 2
overrides:
  - must_have: "The exact Watcom version and default flags that built each EXE are known and proven"
    reason: "D-08/D-10: runtime library 10.6 proven byte for byte; game code 10.6 preferred (one toolchain with the 10.6 runtime), 10.5 byte-identical on the probe and kept as first fallback, 11.0 tied at -4r and kept as candidate; flags beyond calling convention, -s and -fpi carried as candidates (-5, -fpi87, -fp3/-fp5, -o* subsets, -zp1/2/4/8, -zm, -j, -d1/-d2) for proof or permutation, listed in docs/toolchain.md 'Fallbacks and candidates'; the first Phase 5 matches settle 10.6 vs 10.5/11.0, -4 vs -5 and -o*"
    accepted_by: "ayrtondenner"
    accepted_at: "2026-10-22T19:25:11Z"
  - must_have: "_log_line, the bytes-free line content (names, paths, argv, SHA-1s, exit codes), the --log option and the default build/logs/cc.log are unchanged, and no dependency is added"
    reason: "_log_line, DEFAULT_LOG, cli.py and the --log interface are byte-identical to c2d4054~1 and dependencies = []. Behaviour as shipped after review fixes WR-01/WR-02: a --log without a file name (., /) is refused before the compile (CompilerError, one error line, no object); a device log such as /dev/null is appended without the lock and gets no sidecar; a regular log needs a directory where <log>.lock can be created (documented in docs/toolchain.md:321); an existing folder as --log fails after the compile as it did before 04-13. Owner accepted the changed behaviour in 04-UAT.md test 5; a docs note on the nameless and folder cases is deferred to ROADMAP backlog 999.1 (commit 6ab386b)"
    accepted_by: "ayrtondenner"
    accepted_at: "2026-10-23"
re_verification:
  previous_status: human_needed
  previous_score: 24/26
  gaps_closed:
    - "Human item 1 (G-04-2 re-test, also the 04-01 backstop truth): owner re-test passed after every fix commit (04-UAT.md test 4): 320/320 parallel cc compiles per environment, cc.log 320 intact lines each, sidecar empty"
    - "Human item 2 (truth 24 / P1, --log behaviour): owner accepted the behaviour shipped after WR-01/WR-02 (04-UAT.md test 5); recorded as the second override"
    - "Human item 3 (04-13 prohibitions P1/P2/P5/P6 without wired enforcement): owner confirmed at HEAD (04-UAT.md test 6); verifier re-check agrees"
  gaps_remaining: []
  regressions: []
  earlier_rounds:
    - verified: 2026-10-23T01:53:19Z
      previous_status: human_needed
      previous_score: 17/19
      gaps_closed:
        - "G-04-2 (04-UAT.md test 2): parallel `reverseapoc cc` lost and tore cc.log lines on the 9p bind mount and the Windows host; closed in code by plan 04-13, owner UAT re-test pending"
        - "Previous human item 1 (goal wording): owner accepted by override (UAT test 1 pass)"
        - "Previous human item 3 (judgment-tier prohibitions 04-01..04-12, A1/T-04-13): owner signed off (UAT test 3 pass)"
behavior_unverified_items: []
---

# Phase 4: Compiler identification Verification Report

**Phase Goal:** The exact Watcom version and default flags that built each EXE are known and proven: runtime library modules match byte for byte, and the codegen probe locates its idioms in the game's own code.
**Verified:** 2026-10-23T19:29:44Z
**Status:** passed
**Re-verification:** Yes. The previous report (2026-10-23T01:53:19Z, human_needed, 24/26) went stale when the 04-13 review fixes changed covered files. This run re-checks those changes and closes the three human items with the owner's UAT evidence (04-UAT.md tests 4-6).

## What changed since the previous verification

`git diff ff8fdb6 HEAD` over tools/, tests/, docs/, config/, probe/, docker/, pyproject.toml and uv.lock
touches exactly five files, all from the review-fix commits:

| Commit | File | Change |
|---|---|---|
| 37b104f (WR-01) | tools/reverseapoc/compiler.py | `_check_log_name(log)` raises `CompilerError` for a `--log` with no name. It is called in `compile_rule` (:521), before the gate, the unlink and the runner |
| 37b104f (WR-01) | tests/test_cli.py | +17 lines, no line removed: `test_cc_log_without_a_name_is_an_error_line[.]` and `[/]` (one error line, no traceback, `runner.calls == []`) |
| 83053f9 (WR-02) | tools/reverseapoc/compiler.py | `_append_log`: `if log.exists() and not log.is_file()` appends without `_log_lock` (:487-490). The regular-file path is still `with _log_lock(log): with log.open("a")` (:491-493) |
| 83053f9 (WR-02) | tests/test_cc_log.py | `test_a_device_log_is_appended_without_the_lock` (os.devnull, monkeypatched `_log_lock` raises if taken); POSIX-only `test_dev_null_log_works_and_leaves_no_sidecar` |
| c01df4c (WR-03) | tests/test_cc_log.py, tests/test_compiler_real.py | bounded `wait(timeout=120)` / `communicate(timeout=300)`, and `_reap` in `finally` |
| 1ad7417 (IN-01) | tools/reverseapoc/compiler.py | `_try_lock` docstring only |
| 862159b, 9f4f5bc (IN-03, IN-02) | docs/toolchain.md:321 | the cc.log bullet now covers the writable-directory requirement, device logs, the same-path rule and "the Windows host" |

`_log_line` is byte-identical to c2d4054~1 (extracted and diffed). `DEFAULT_LOG` is unchanged. cli.py,
pyproject.toml, uv.lock, config/, the Docker files and tests/test_compiler.py are all unchanged since
c2d4054~1. libmatch, probe, cppscan, omf, wpack, watcom and cflags are unchanged since the previous report.

## Goal Achievement

### Observable Truths

Truths 1-19 come from the earlier rounds (regression check). Truths 20-26 are the 04-13 must_haves. Each
truth whose files the fixes touched (8, 9, 20-26) was re-checked in full.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1 (CID-01): 10.5/10.6/11.0 run under wibo 1.2.0 in `docker compose run`, read-only Watcom trees; hash and banner logged | ✓ VERIFIED | Container suite (my run): 1043 passed, 2 skipped (both `Windows-only: msvcrt lock path`), so every test_compiler_real case ran under wibo. `check-watcom 10.5 10.6 11.0`: 8 / 8 / 10 ok, 0 known bad |
| 2 | SC2 (CID-02): wrapper keyed by `compiler@version` reads `config/cflags.txt` | ✓ VERIFIED | cli.py, cflags.py and config/cflags.txt unchanged; rule selection in compiler.py untouched by the fixes; both suites green |
| 3 | SC3a (CID-04): CLIB3R/MATH3R modules match byte for byte, fixups masked | ✓ VERIFIED | libmatch.py and both runtime.csv unchanged; the drift test passed in both suites |
| 4 | SC3b (CID-03): probe idioms located in non-library code of both EXEs | ✓ VERIFIED | `probe scan` run by me. UFO2P: setcc_and 30, setcc_movzx 0, movsd_unrolled 75, rep_movsd_small 4, 40 `__CHK`. TACP: 58 / 0 / 35 / 2, 32 `__CHK`. Every evidence line carries `(source: ...)` |
| 5 | SC4 (CID-05): toolchain.md records version and default flags per EXE with evidence | ✓ VERIFIED | toolchain.md:116-117 (game code 10.6, 10.5 identical, 11.0 tied at -4r; runtime 10.6 with no mix, 11 10.6-only modules). The fixes only edited the cc.log bullet (:321); hygiene tests green |
| 6 | SC5 (CID-06): C vs C++ scan confirms `wcc386` | ✓ VERIFIED | `cppscan` run by me: `UFO2P.EXE: C (wcc386): ...; 5 vtable-shaped candidate runs`, `TACP.EXE: C (wcc386): ...; 3 ...` |
| 7 | Goal wording: exact version and default flags "known and proven" | ✓ PASSED (override) | Override: D-08/D-10 bar, accepted by ayrtondenner on 2026-10-22T19:25:11Z (UAT test 1 pass) |
| 8 | 04-01: `cc` wrapper (gate, banner, argv, scrubbed env, path allowlist, cleanup, ordering, atomic stamp) | ✓ VERIFIED | The new `_check_log_name` sits beside `_check_object_name`, before the gate, and keeps the "refused path never reaches the runner" ordering (test_cli `runner.calls == []`). test_compiler.py unchanged and green |
| 9 | 04-01 backstop: parallel `cc` processes never trust a half-written stamp; the log keeps every line | ✓ VERIFIED | Owner-observed behaviour, 04-UAT.md test 4: 320 parallel compiles per environment (round 1 with no stamp, round 2 with a torn stamp planted), 320/320 exit 0. I checked the artifacts in build/uat-retest/: container/cc.log and host/cc.log each hold 320 lines matching the timestamp pattern and `exit 0`, 0 duplicate `-fo=` objects, `cc.log.lock` 0 bytes. File times (14:07-14:08 local) come after the last code fix (83053f9, 11:51 -0300), so the fixes do not invalidate the observation |
| 10 | 04-02: stdlib OMF reader | ✓ VERIFIED | omf.py unchanged; test_omf*.py green in both suites |
| 11 | 04-03: wpack doc before decoder, real decode | ✓ VERIFIED | unchanged; test_wpack_real green |
| 12 | 04-04: object and normalized SHA-1 logged; real compiles per version | ✓ VERIFIED | `_log_line` byte-identical; real compile tests green in both suites |
| 13 | 04-05: libmatch sweep, runtime.csv format, `config_dir` | ✓ VERIFIED | unchanged; tests green |
| 14 | 04-06: `install-watcom 10.5` decode and pin | ✓ VERIFIED | watcom.toml unchanged; check-watcom 10.5 8 ok |
| 15 | 04-07: runtime.csv committed, drift test, `_cstart_` at entry | ✓ VERIFIED | unchanged; drift test green |
| 16 | 04-08: clean-room probe, calibrate, ties | ✓ VERIFIED | unchanged; test_probe*.py green |
| 17 | 04-09: cppscan | ✓ VERIFIED | unchanged; verdicts reproduced (truth 6) |
| 18 | 04-10: probe scan with runtime rows excluded, evidence lines with source | ✓ VERIFIED | output reproduced (truth 4) |
| 19 | 04-11/04-12: D-03 native vs wibo, spike VALIDATED, docs, gates | ✓ VERIFIED | unchanged; `check-orig` 3 ok, 0 mismatched (my run) |
| 20 | 04-13: 16 writers x 25 real `_append_log` calls leave exactly 400 intact lines with the exact tag set, under build/ and tmp_path, host and container; failed before the fix | ✓ VERIFIED | `test_concurrent_appends_keep_every_line[repo-build]` and `[tmp-path]` pass in my host suite and in the container (my subset and full runs). The waits are now bounded. The pre-fix red logs and the previous round's out-of-tree mutant M1 still stand, because the regular-file lock path is unchanged |
| 21 | 04-13: 16 parallel real `reverseapoc cc` (10.6) sharing one --log all exit 0, 16 intact lines naming the 16 objects, host native and container wibo | ✓ VERIFIED | `test_parallel_cc_keeps_one_log_line_per_compile` passed with no skip in my host suite and in my container runs. It is now bounded by `communicate(timeout=300)` and reaped in `finally`. The owner's 320-compile re-test agrees (truth 9) |
| 22 | 04-13: `_append_log` holds the OS lock on `<log>.lock` from before open to after close; flock LOCK_EX; win32 LK_NBLCK spin retrying only EACCES; release-before-close mutant fails | ✓ VERIFIED | For any log that is not an existing non-regular file, compiler.py:491-493 is still `with _log_lock(log): with log.open("a") ...`. `_try_lock` code is unchanged (only its docstring); `_acquire`/`_release` unchanged. The new device branch (:487-490) bypasses the lock only for `exists() and not is_file()` (devices, FIFOs, directories), not for a regular cc.log. EACCES-only and retry tests green on the host |
| 23 | 04-13: a killed lock holder does not block later appends; a second appender waits; the sidecar stays, empty, never deleted | ✓ VERIFIED | `test_a_killed_lock_holder_does_not_block_later_appends` passes on host and container (it now uses the shared `_reap`). There is still no unlink of the sidecar in compiler.py. The owner's re-test left `cc.log.lock` at 0 bytes in both environments |
| 24 | 04-13: `_log_line`, the bytes-free line content, the `--log` option and the default build/logs/cc.log are unchanged; no dependency added | ✓ PASSED (override) | The interface holds: `_log_line` diff empty, `DEFAULT_LOG` line exact, cli.py/pyproject.toml/uv.lock unchanged since c2d4054~1, `dependencies = []`. Behaviour changed for edge values (nameless `--log` now refused before the compile; a log whose directory refuses new files fails). Override: owner accepted in UAT test 5, accepted by ayrtondenner on 2026-10-23 |
| 25 | 04-13: toolchain.md states parallel-safe within one environment, sidecar cc.log.lock, host plus container on one log not supported; learnings.md records O_APPEND not atomic on 9p and the Windows host | ✓ VERIFIED | toolchain.md:321 still carries `cc.log.lock`, "parallel `cc` processes in one environment", and "The Windows host and a container writing the same log at the same time is not supported". learnings.md:14 is `## 2026-10-22: O_APPEND is not atomic on the bind mount or the Windows host ...` |
| 26 | 04-13: done gate green on host and container; concurrency tests 5 in a row on each; every step logged under build/gate/04-13/ and in the SUMMARY | ✓ VERIFIED | build/gate/04-13/01..05 all end `exit=0`. The gate also holds at HEAD, after the fixes (my runs). Host: `uv run pytest -q -rs` 1038 passed, 7 skipped (platform/container-only only), `ruff check .` All checks passed. Container: full suite + ruff 1043 passed, 2 Windows-only skips, All checks passed. The POSIX-only `/dev/null` test ran (not skipped) there as user `dev` |

**Score:** 26/26 truths verified (2 by override; 0 present, behavior-unverified)

### Required Artifacts

`gsd-tools query verify.artifacts` on every plan: 04-01 4/4, 04-02 4/4, 04-03 4/4, 04-04 2/2, 04-05 4/4,
04-06 2/2, 04-07 3/3, 04-08 4/4, 04-09 2/2, 04-10 2/2, 04-11 5/5, 04-12 1/1, 04-13 5/5. That is 42/42, with
no issues.

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tools/reverseapoc/compiler.py` | LOCK_SUFFIX, `_lock_path`, platform helpers, `_log_lock`, `_append_log` inside the lock; now also `_check_log_name` and the device branch | ✓ VERIFIED | :47-48, :306-310, :424-493; called from compile_rule :521 and :548 |
| `tests/test_cc_log.py` | hammer, sidecar, default paths, killed holder, win32 tests; now device tests and bounded waits | ✓ VERIFIED | runs in both suites (2 win32 tests skip in the container, 1 POSIX test skips on the host) |
| `tests/test_compiler_real.py` | `test_parallel_cc_keeps_one_log_line_per_compile` | ✓ VERIFIED | bounded and reaped; passed in both environments |
| `tests/test_cli.py` | (WR-01 addition) nameless `--log` is one error line | ✓ VERIFIED | 2 parametrized cases pass on both |
| `docs/toolchain.md` | cc.log lock bullet | ✓ VERIFIED | line 321 |
| `docs/learnings.md` | 2026-10-22 O_APPEND entry | ✓ VERIFIED | line 14 |

### Key Link Verification

The `from:` fields in 04-13 carry a symbol after the path, which `verify.key-links` does not parse (as
in the previous round). I checked each one by hand:

| From | To | Via | Status | Details |
|---|---|---|---|---|
| compiler.py compile_rule | compiler.py `_append_log` | `_append_log(log, result)` | WIRED | compiler.py:548, after every compile |
| compiler.py compile_rule | compiler.py `_check_log_name` | `_check_log_name(log)` | WIRED | compiler.py:521, before `check_gate` and the runner |
| compiler.py `_append_log` | compiler.py `_log_lock` | `with _log_lock(log)` | WIRED | compiler.py:491 for every regular or new log |
| cli.py `_cmd_cc` | compiler.py `compile_source` | `log=args.log` | WIRED | cli.py:96; `CompilerError` and `OSError` are both in `cli._ERRORS` (:469-482) |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|---|---|---|---|---|
| cc.log | one line per compile | `_log_line(CompileResult)` from the real compile and gate | yes: 16 lines in the real parallel test; 320 in each of the owner's re-test logs | ✓ FLOWING |
| `<log>.lock` | none (lock only) | opened `a+b`, never written | 0 bytes in tests and in build/uat-retest/ | ✓ as designed |
| runtime.csv / probe scan / cppscan | measured verdicts | orig/ + LIB386 | reproduced by me | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Host suite + lint (one full run) | `uv run pytest -q -rs` then `uv run ruff check .` | 1038 passed, 7 skipped (test_cc_log:190 POSIX-only, test_configure x3, test_hygiene container-only x3); `All checks passed!` | ✓ PASS |
| Container changed-file subset | `docker compose run --rm build bash -lc "uv sync --locked -q && uv run pytest -q -rs tests/test_cc_log.py tests/test_cli.py tests/test_compiler_real.py && uv run ruff check ."` | user `dev`; 123 passed, 2 skipped (Windows-only); `All checks passed!` | ✓ PASS |
| Container full suite + lint | same container, `uv run pytest -q -rs && uv run ruff check .` | 1043 passed, 2 skipped (Windows-only); `All checks passed!`, exit 0 | ✓ PASS |
| Totals consistency | 1038+7 = 1043+2 = 1045 = previous 1041 + 4 new tests (device, /dev/null, cli x2) | consistent | ✓ PASS |
| Owner re-test artifacts | grep of build/uat-retest/{container,host}/cc.log | 320 intact `exit 0` lines each, 0 duplicate objects, sidecar 0 bytes | ✓ PASS |
| CID checks | `check-watcom 10.5 10.6 11.0`; `cppscan` x2; `probe scan` x2; `check-orig` | 8/8/10 ok; `C (wcc386)` for both; idiom counts as in toolchain.md; 3 ok | ✓ PASS |

The host and container runs were sequential, never at the same time, so they did not share
build/test-cc/ (that problem invalidated one run in the previous round). `git status` after all runs shows only
the pre-existing untracked `.planning/milestone.lock`.

### Probe Execution

No `scripts/*/tests/probe-*.sh` exists or is declared. Step 7c: not applicable.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|---|---|---|---|---|
| CID-01 | 04-01, 04-03, 04-04, 04-06, 04-11, 04-12, 04-13 | compiler runs under wibo in Docker per version; hash and banner logged | ✓ SATISFIED | Truths 1, 9, 11, 12, 14, 19-23 |
| CID-02 | 04-01, 04-04, 04-12, 04-13 | wrapper + per-file flags table | ✓ SATISFIED | Truths 2, 8, 21, 24 (override) |
| CID-03 | 04-08, 04-10, 04-12 | probe idioms located in both code objects | ✓ SATISFIED | Truths 4, 16, 18 |
| CID-04 | 04-02, 04-05, 04-07, 04-12 | runtime modules match byte for byte (masked) | ✓ SATISFIED | Truths 3, 10, 13, 15 |
| CID-05 | 04-10, 04-11, 04-12 | version and flags in toolchain.md per EXE | ✓ SATISFIED (to the D-08 bar, override) | Truths 5, 7 |
| CID-06 | 04-09, 04-12 | C vs C++ scan confirms wcc386 | ✓ SATISFIED | Truth 6 |

No orphaned requirements. REQUIREMENTS.md maps exactly CID-01..06 to Phase 4 (all `Complete`), and each
appears in at least one plan's `requirements`.

### Prohibitions of 04-13

| # | Prohibition | Tier | Enforcement | Verdict |
|---|---|---|---|---|
| P1 | MUST NOT change `_log_line`, line text, `--log` or DEFAULT_LOG, or move the default log | test | `test_default_log_and_its_lock` pins DEFAULT_LOG; `test_cc_log_without_a_name_is_an_error_line` pins the nameless case; `_log_line` diff empty | Interface held; the edge-value behaviour change is owner-accepted (truth 24 override, UAT test 5) |
| P2 | MUST NOT add a third-party dependency | test | no committed test | No wired test. The owner confirmed it at HEAD (UAT test 6), and my re-check agrees: `dependencies = []`, pyproject.toml/uv.lock unchanged since c2d4054~1 |
| P3 | MUST NOT use blocking msvcrt modes or treat every OSError as contention | test | `test_lock_retries_while_busy`, `test_lock_does_not_swallow_other_errors` | ✓ enforced, held (`_try_lock` code unchanged) |
| P4 | MUST NOT use mkdir/O_EXCL lock or delete the sidecar | test | killed-holder test, sidecar-exists test | ✓ enforced, held |
| P5 | MUST NOT import, run or name the gitignored prototype from a committed test | test | no committed test | No wired test. The owner confirmed it (UAT test 6), and my grep agrees: no `debug-cclog`/`debug_cclog` anywhere in tests/ |
| P6 | MUST NOT edit orig/, third_party/, config/*.toml, Docker files or existing assertions in test_compiler.py/test_cli.py; no note in place of a step | judgment | the owner signed off (UAT test 6) | Human-resolved. My re-check agrees: config/, the Docker files and test_compiler.py are unchanged; test_cli.py has +17 lines and 0 removed (WR-01 only); check-orig 3 ok; gate logs 01..05 exit=0 |

P2 and P5 have no wired test, so they are not green on test evidence. The owner resolved them in UAT test
6, as the previous round's human item 3 asked. They are carried here as human-resolved, not test-enforced.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| (5 changed files) | - | TBD / FIXME / XXX / TODO / HACK | none found | - |
| tools/reverseapoc/compiler.py | 306-310, 487-490 | `--log <existing directory>` compiles, then fails at the append and leaves the object (IN-08) | ℹ️ Info | behaves as before 04-13; owner accepted; docs note in backlog 999.1 |
| tools/reverseapoc/compiler.py | 469 | an unwritable log directory still fails after the compile (IN-09) | ℹ️ Info | documented at toolchain.md:321; inside the truth-24 override |
| tests/test_compiler_real.py | 252-258 | `_reap` kills the Python `cc` only, not its wcc386/wibo child (IN-10) | ℹ️ Info | the lock is taken after the compile, so the WR-03 hang case is still covered |
| tests/test_cc_log.py | 190-196 | the `/dev/null` test would turn a regression into a skip when run as root (IN-11) | ℹ️ Info | the project container runs as `dev`, where it fails properly |
| tools/reverseapoc/compiler.py | 481-482 | docstring still says "the host" rather than "the Windows host" (IN-12) | ℹ️ Info | docs precision only |
| tests/test_cli.py | 733-743 | `assert not obj.exists()` cannot fail (IN-13) | ℹ️ Info | `runner.calls == []` still pins the ordering that matters |

All six come from 04-REVIEW.md (0 critical, 0 warning), and all are `open` in 04-REVIEW-DISPOSITION.md.
None of them contradicts a must_have. WR-01, WR-02 and WR-03 from the previous round are fixed in code
and covered by the tests above.

### Advisory (New Scope, Unevidenced)

None. No new-scope 🛑 Blocker was raised in this round. The review findings are Info, and the evidence gate
had nothing to filter.

### Human Verification Required

None open. The previous round's three items were each confirmed by the owner in 04-UAT.md (status
complete): test 4 (G-04-2 re-test and backstop truth), test 5 (truth 24 / P1, now an override), and test 6
(prohibitions P1/P2/P5/P6). No code change after those observations affects them. The re-test artifacts
post-date the last code fix, and test 6 was taken at HEAD.

### Gaps Summary

There are no gaps. The phase goal is met to the bar the owner accepted (override 1):
- runtime library 10.6, matched byte for byte (masked) in both EXEs;
- the clean-room probe's idioms located in both EXEs' non-library code;
- C (`wcc386`) confirmed for both EXEs;
- version and flags recorded per EXE in docs/toolchain.md.

G-04-2 is closed in code and by owner observation: 320/320 parallel compiles per environment, every log
line intact. The 04-13 review fixes keep the regular-file lock path intact. They only add a pre-compile
name check and a lock-free branch for devices. The host and the container are green at HEAD.

Open but non-blocking: six Info review findings (IN-08..IN-13), and backlog 999.1, the docs note on
nameless and folder `--log` values.

---

_Verified: 2026-10-23T19:29:44Z_
_Verifier: Claude (gsd-verifier)_
