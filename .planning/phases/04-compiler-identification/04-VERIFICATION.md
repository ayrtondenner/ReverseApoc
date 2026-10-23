---
phase: 04-compiler-identification
verified: 2026-10-23T01:53:19Z
status: human_needed
score: 24/26 must-haves verified
covered_files: [".planning/phases/04-compiler-identification/04-01-PLAN.md", ".planning/phases/04-compiler-identification/04-01-SUMMARY.md", ".planning/phases/04-compiler-identification/04-02-PLAN.md", ".planning/phases/04-compiler-identification/04-02-SUMMARY.md", ".planning/phases/04-compiler-identification/04-03-PLAN.md", ".planning/phases/04-compiler-identification/04-03-SUMMARY.md", ".planning/phases/04-compiler-identification/04-04-PLAN.md", ".planning/phases/04-compiler-identification/04-04-SUMMARY.md", ".planning/phases/04-compiler-identification/04-05-PLAN.md", ".planning/phases/04-compiler-identification/04-05-SUMMARY.md", ".planning/phases/04-compiler-identification/04-06-PLAN.md", ".planning/phases/04-compiler-identification/04-06-SUMMARY.md", ".planning/phases/04-compiler-identification/04-07-PLAN.md", ".planning/phases/04-compiler-identification/04-07-SUMMARY.md", ".planning/phases/04-compiler-identification/04-08-PLAN.md", ".planning/phases/04-compiler-identification/04-08-SUMMARY.md", ".planning/phases/04-compiler-identification/04-09-PLAN.md", ".planning/phases/04-compiler-identification/04-09-SUMMARY.md", ".planning/phases/04-compiler-identification/04-10-PLAN.md", ".planning/phases/04-compiler-identification/04-10-SUMMARY.md", ".planning/phases/04-compiler-identification/04-11-PLAN.md", ".planning/phases/04-compiler-identification/04-11-SUMMARY.md", ".planning/phases/04-compiler-identification/04-12-PLAN.md", ".planning/phases/04-compiler-identification/04-12-SUMMARY.md", ".planning/phases/04-compiler-identification/04-13-PLAN.md", ".planning/phases/04-compiler-identification/04-13-SUMMARY.md", "config/cflags.txt", "config/tacp/runtime.csv", "config/ufo2p/runtime.csv", "config/watcom.toml", "docs/learnings.md", "docs/matching.md", "docs/research/wpack-format.md", "docs/toolchain.md", "probe/README.md", "probe/cg_basic.c", "tests/conftest.py", "tests/omfimage.py", "tests/test_cc_log.py", "tests/test_cflags.py", "tests/test_cli.py", "tests/test_compiler.py", "tests/test_compiler_real.py", "tests/test_cppscan.py", "tests/test_cppscan_real.py", "tests/test_hygiene.py", "tests/test_libmatch.py", "tests/test_libmatch_real.py", "tests/test_omf.py", "tests/test_omf_real.py", "tests/test_probe.py", "tests/test_probe_real.py", "tests/test_targets.py", "tests/test_watcom.py", "tests/test_wpack.py", "tests/test_wpack_real.py", "tests/wpackimage.py", "tools/reverseapoc/cflags.py", "tools/reverseapoc/cli.py", "tools/reverseapoc/compiler.py", "tools/reverseapoc/cppscan.py", "tools/reverseapoc/libmatch.py", "tools/reverseapoc/omf.py", "tools/reverseapoc/probe.py", "tools/reverseapoc/targets.py", "tools/reverseapoc/watcom.py", "tools/reverseapoc/wpack.py"]
covered_digest: "v3:sha256:7e1ced0832ba4bae89f21e3beadb77e36e581ea42dfa216408dae433eee0f652"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "The exact Watcom version and default flags that built each EXE are known and proven"
    reason: "D-08/D-10: runtime library 10.6 proven byte for byte; game code 10.6 preferred (one toolchain with the 10.6 runtime), 10.5 byte-identical on the probe and kept as first fallback, 11.0 tied at -4r and kept as candidate; flags beyond calling convention, -s and -fpi carried as candidates (-5, -fpi87, -fp3/-fp5, -o* subsets, -zp1/2/4/8, -zm, -j, -d1/-d2) for proof or permutation, listed in docs/toolchain.md 'Fallbacks and candidates'; the first Phase 5 matches settle 10.6 vs 10.5/11.0, -4 vs -5 and -o*"
    accepted_by: "ayrtondenner"
    accepted_at: "2026-10-22T19:25:11Z"
re_verification:
  previous_status: human_needed
  previous_score: 17/19
  gaps_closed:
    - "G-04-2 (04-UAT.md test 2): parallel `reverseapoc cc` lost and tore cc.log lines on the 9p bind mount and the Windows host; closed in code by plan 04-13, owner UAT re-test pending"
    - "Previous human item 1 (goal wording): owner accepted by override (UAT test 1 pass)"
    - "Previous human item 3 (judgment-tier prohibitions 04-01..04-12, A1/T-04-13): owner signed off (UAT test 3 pass)"
  gaps_remaining: []
  regressions: []
behavior_unverified_items: []
human_verification:
  - test: "UAT re-test of G-04-2 (04-UAT.md test 2), which also settles the 04-01 backstop truth: run many `uv run reverseapoc cc` compiles in parallel inside ONE environment (container bind mount, then separately the Windows host), each environment with its own --log, as in the original 1600-compile run"
    expected: "Every compile exits 0; no torn stamp is trusted; cc.log holds exactly one intact line per compile (lines may interleave in order, none lost, none torn); the sidecar cc.log.lock exists and is empty"
    why_human: "The orchestrator states the owner's UAT re-check has not happened; the 04-01 backstop truth is non-inferable (insufficient_spec) and is closed only by observed behaviour, which the owner reported failing before 04-13"
  - test: "Decide on truth 24 / prohibition P1 of 04-13 ('the --log option ... unchanged'): the option's interface (cli.py byte-identical, default build/logs/cc.log) is unchanged, but its behaviour changed for two values (review WR-01, WR-02), both reproduced by the verifier"
    expected: "Owner either accepts the change (add the override suggested at the end of this report and, ideally, note in docs/toolchain.md that --log needs a file name and a directory where <log>.lock can be created), or rejects it, which turns this item into a gap for a small gap-closure plan (refuse a nameless --log before the compile as a CompilerError; skip the lock for a non-regular log such as /dev/null, or check the sidecar before the compile)"
    why_human: "Whether 'unchanged' meant the option's interface (as the plan operationalised it: cli.py, DEFAULT_LOG, _log_line unchanged) or every value's behaviour is a scope reading only the owner can make; the plan's own design (sidecar beside whatever --log names) makes a creatable directory an intrinsic new precondition"
  - test: "Prohibitions of 04-13: test-tier P1 (--log part), P2 (no third-party dependency) and P5 (no prototype import) have no committed test that enforces them; judgment-tier P6 (no protected path edited, no note in place of a step) has a non-authoritative LLM-judge verdict"
    expected: "Owner confirms the verifier's observations: pyproject `dependencies = []` and uv.lock unchanged since c2d4054~1; no 'debug-cclog' reference in the committed tests; config/, docker/, tests/test_compiler.py, tests/test_cli.py unchanged since c2d4054~1; check-orig 3 OK; every gate step logged with exit=0"
    why_human: "unverified-prohibition, human review recommended: a test-tier prohibition without wired enforcement is never passed green, and judgment-tier verdicts are advisory"
---

# Phase 4: Compiler identification Verification Report

**Phase Goal:** The exact Watcom version and default flags that built each EXE are known and proven: runtime library modules match byte for byte, and the codegen probe locates its idioms in the game's own code.
**Verified:** 2026-10-23T01:53:19Z
**Status:** human_needed
**Re-verification:** Yes, after gap closure (plan 04-13, gap G-04-2 from 04-UAT.md)

## What changed since the previous verification

Code changed only in the three 04-13 commits (`git log --since=2026-10-21T23:30Z` over tools/, tests/,
config/, docs/, probe/, docker/, pyproject.toml, uv.lock):
- `c2d4054` test: tests/test_cc_log.py (new, 231 lines), tests/test_compiler_real.py (+47, no line removed);
- `97f75ac` fix: tools/reverseapoc/compiler.py only (+72/-4);
- `53a5021` docs: docs/toolchain.md (+1 bullet), docs/learnings.md (+1 entry).

libmatch, probe, cppscan, omf, wpack, watcom, cflags, cli and every config file are byte-identical to
the previous verification. The goal-wording item was closed by the owner with the override above, and
the judgment-tier prohibitions of 04-01..04-12 were signed off in UAT (04-UAT.md tests 1 and 3).

## Goal Achievement

### Observable Truths

Truths 1-19 are the previous verification's truths (quick regression check, plus full re-check where
04-13 touched the code). Truths 20-26 are the 04-13 must_haves, verified in full.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1 (CID-01): 10.5/10.6/11.0 run under wibo 1.2.0 in `docker compose run`, read-only Watcom trees; hash and banner logged | ✓ VERIFIED | Regression: container suite run by me, 1039 passed, 2 skipped (both `Windows-only: msvcrt lock path`), so every test_compiler_real case ran under wibo; `check-watcom 10.5 10.6 11.0`: 8 / 8 / 10 ok, 0 known bad |
| 2 | SC2 (CID-02): wrapper keyed by `compiler@version` reads `config/cflags.txt` | ✓ VERIFIED | cli.py and cflags.py unchanged since c2d4054~1; `select_rule` path in compiler.py untouched; host and container suites green |
| 3 | SC3a (CID-04): CLIB3R/MATH3R modules match byte for byte, fixups masked | ✓ VERIFIED | libmatch.py and both runtime.csv unchanged; drift test inside both suites passed |
| 4 | SC3b (CID-03): probe idioms located in non-library code of both EXEs | ✓ VERIFIED | `probe scan UFO2P.EXE` run by me: 741,159 non-library bytes, setcc_and 30, setcc_movzx 0, movsd_unrolled 75, rep_movsd_small 4, 40 `__CHK` calls (same as before) |
| 5 | SC4 (CID-05): toolchain.md records version and default flags per EXE with evidence | ✓ VERIFIED | Only the cc bullet was added to the "wibo" section; hygiene tests (toolchain/cflags pins) pass in both suites |
| 6 | SC5 (CID-06): C vs C++ scan confirms `wcc386` | ✓ VERIFIED | `cppscan` run by me: `UFO2P.EXE: C (wcc386): ...; 5 vtable-shaped candidate runs`, `TACP.EXE: C (wcc386): ...; 3 ...` |
| 7 | Goal wording: exact version and default flags "known and proven" | ✓ PASSED (override) | Override: D-08/D-10 bar, accepted by ayrtondenner on 2026-10-22T19:25:11Z (UAT test 1 pass) |
| 8 | 04-01: `cc` wrapper (gate, banner, argv, scrubbed env, path allowlist, cleanup, ordering, atomic stamp) | ✓ VERIFIED | compile_rule unchanged except that `_append_log` now locks; test_compiler.py and test_cli.py unchanged and green |
| 9 | 04-01 backstop: parallel `cc` processes never trust a half-written stamp; the log keeps every line | ⚠️ insufficient_spec (human item 1) | Before: UAT observed the stamp held over 1600 compiles but cc.log lost lines (G-04-2). Now: 16 parallel real `cc` processes sharing one --log and the default stamps pass 6/6 on the host and 6/6 in the container (my runs). The owner re-test has not happened, so this stays a human item |
| 10 | 04-02: stdlib OMF reader | ✓ VERIFIED | omf.py unchanged; test_omf*.py green in both suites |
| 11 | 04-03: wpack doc before decoder, real decode | ✓ VERIFIED | unchanged; test_wpack_real green |
| 12 | 04-04: object and normalized SHA-1 logged; real compiles per version | ✓ VERIFIED | `_log_line` byte-identical to c2d4054~1 (sed/diff check by me); real compile tests green |
| 13 | 04-05: libmatch sweep, runtime.csv format, `config_dir` | ✓ VERIFIED | unchanged; tests green |
| 14 | 04-06: `install-watcom 10.5` decode and pin | ✓ VERIFIED | watcom.toml unchanged; check-watcom 10.5 OK |
| 15 | 04-07: runtime.csv committed, drift test, `_cstart_` at entry | ✓ VERIFIED | unchanged; drift test green |
| 16 | 04-08: clean-room probe, calibrate, ties | ✓ VERIFIED | unchanged; test_probe*.py green |
| 17 | 04-09: cppscan | ✓ VERIFIED | unchanged; CLI verdicts reproduced |
| 18 | 04-10: probe scan with runtime rows excluded, evidence lines with source | ✓ VERIFIED | output reproduced, each evidence line ends in `(source: ...)` |
| 19 | 04-11/04-12: D-03 native vs wibo, spike VALIDATED, docs, gates | ✓ VERIFIED | build/gate/04-12/: 8 logs, all end `exit=0`; `rebuild` three OK and `cmp` silent for UFO2P and TACP (run by me); `check-orig` 3 OK |
| 20 | 04-13: 16 writers x 25 real `_append_log` calls under REPO_ROOT/build leave exactly 400 intact lines with the exact tag set, on host NTFS and the container 9p mount, also under tmp_path; before the fix the build/ case failed on both | ✓ VERIFIED | My runs: host 6/6 green, container 5/5 green (after the fix). Before-fix behaviour reproduced by me: an out-of-tree copy of compiler.py with the pre-fix unlocked append (M1), loaded in the container through PYTHONPATH, fails `[repo-build]` with `torn line start: '0'`. RED logs at c2d4054 exist under build/gate/04-13/red/ (host-1..3, container-1..3) |
| 21 | 04-13: 16 parallel real `reverseapoc cc` (10.6) sharing one --log all exit 0 and leave exactly 16 intact lines naming the 16 objects, native on host and under wibo in container | ✓ VERIFIED | `test_parallel_cc_keeps_one_log_line_per_compile`: host 6 runs + full suite, container 5 runs + full suite, all passed with no skip of this test (it would skip without the 10.6 tree or runner) |
| 22 | 04-13: `_append_log` holds an OS lock on `<log>.lock` from before open to after close; POSIX flock LOCK_EX; win32 LK_NBLCK spin retrying only EACCES; a release-before-close mutant fails the container test | ✓ VERIFIED | compiler.py:453-476 (`with _log_lock(log):` wraps `with log.open("a")`); :423-441 (LK_NBLCK, EACCES only, re-raise otherwise); :445-449 (flock LOCK_EX/LOCK_UN); no LK_LOCK/LK_RLCK. My out-of-tree M2 (open before lock, write+flush inside, close after release) fails `[repo-build]` in the container (`1 failed, 4 passed, 2 skipped`). EBADF test and retry test pass on the host |
| 23 | 04-13: a killed lock holder does not block later appends; a second appender waits while it lives; the sidecar stays, empty, never deleted | ✓ VERIFIED | `test_a_killed_lock_holder_does_not_block_later_appends` passes on host and container (my runs); no unlink/remove of the sidecar anywhere in compiler.py; `test_append_writes_the_log_line_and_an_empty_sidecar_lock` asserts the sidecar exists with size 0 |
| 24 | 04-13: `_log_line`, the bytes-free line content, the `--log` option and the default build/logs/cc.log are unchanged; no dependency added | ? UNCERTAIN (human item 2) | Holds as the plan operationalised it: `_log_line` byte-identical; cli.py, pyproject.toml, uv.lock, tests/test_compiler.py, tests/test_cli.py unchanged since c2d4054~1; `DEFAULT_LOG` line exact; `dependencies = []`. Does NOT hold for two `--log` values (see below) |
| 25 | 04-13: toolchain.md states parallel-safe within one environment, sidecar cc.log.lock, host plus container on one log not supported; learnings.md records O_APPEND not atomic on the 9p mount or the Windows host | ✓ VERIFIED | toolchain.md:321 carries `cc.log.lock` and `same log at the same time is not supported`; first dated learnings heading is `## 2026-10-22: O_APPEND is not atomic on the bind mount or the Windows host ...`; hygiene tests pass |
| 26 | 04-13: done gate green on host and container; concurrency tests 5 runs in a row on each; every step logged under build/gate/04-13/ and reproduced in the SUMMARY | ✓ VERIFIED | build/gate/04-13/01..05 all end `exit=0`; 01: 1035 passed, 6 skipped; 03/04: 1039 passed, 2 skipped; 02 and 05: 5 passing summary lines each. My own runs agree: host `uv run pytest -q -rs && uv run ruff check .` 1035 passed, 6 skipped (platform only), `All checks passed!`; container suite + ruff 1039 passed, 2 Windows-only skips, `All checks passed!`; 5 in a row on each environment |

**Score:** 24/26 truths verified (1 by override; 0 present, behavior-unverified; 1 insufficient_spec, 1 uncertain)

### Truth 24 and the review warnings, stated plainly

The truth says "the `--log` option ... unchanged". The option's interface is unchanged, but its
behaviour changed for two values. I reproduced both:

- **WR-01, `--log .`** (or `C:/`): `compiler._lock_path(Path('.'))` raises
  `ValueError: WindowsPath('.') has an empty name`. `ValueError` is not in `cli._ERRORS`, so
  `reverseapoc cc ... --log .` now ends in a traceback after the compile has run. Before 04-13,
  `open('.', 'a')` raised `PermissionError` (an `OSError`), which `main` printed as a one-line
  `reverseapoc cc: error: ...` and exit 1. Both versions fail; the failure now looks different.
- **WR-02, `--log /dev/null` in the container** (user `dev`): `open('/dev/null', 'a')` still works,
  but `compiler._append_log(Path('/dev/null'), r)` raises
  `PermissionError: [Errno 13] Permission denied: '/dev/null.lock'`. So a compile that used to exit 0
  now exits 1, with the object already written. The same applies to any log in a directory where the
  user cannot create files.

My verdict: this contradicts the literal wording of truth 24 and of prohibition P1 ("MUST NOT change
... the --log option"). It does not contradict their evident purpose:
- the plan's verify block defines "unchanged" as cli.py, `DEFAULT_LOG` and `_log_line` unchanged, and
  all three are unchanged;
- P1 names the rejected design D (moving the default log), and the default log has not moved;
- the gap's own fix list puts "the lock sidecar sits next to whatever --log names" beside "--log
  unchanged".

A creatable directory is therefore an intrinsic new precondition of the planned design. The plan
neither foresaw it nor documented it. Neither value is on a path the project uses: the default log is
a regular file under build/logs, and Phase 5's ninja will use the default. So I do not mark truth 24
FAILED. I also do not mark it VERIFIED, because "unchanged" is literally untrue for these values. It
goes to the owner as human item 2, with an override text below if the owner accepts it.

- **WR-03** (untimed `p.wait()` and `proc.communicate()` in the new tests) contradicts no must_have.
  The tests pass, and the plan chose "no timeout on the lock wait" deliberately. The cost is that a
  future lock regression would hang the gate instead of failing it, and the real parallel test can
  leave processes running after its first failed assert. This is a ⚠️ Warning, with a fix recommended
  (bounded waits, reap in `finally`).
- **IN-01..IN-03** contradict no must_have. IN-03 (the toolchain bullet says "the host" where only a
  Windows host with Docker Desktop has separate lock domains) is a docs-precision point; truth 25 only
  requires that the unsupported case be stated, and it is.

### Required Artifacts

`gsd-tools verify.artifacts` on 04-13-PLAN.md: 5/5 pass (exists, `contains`). The 37 artifacts of
04-01..04-12 are unchanged except compiler.py, docs/toolchain.md, docs/learnings.md and
tests/test_compiler_real.py, which 04-13 extended.

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tools/reverseapoc/compiler.py` | LOCK_SUFFIX, `_lock_path`, platform helpers, `_log_lock`, `_append_log` inside the lock, closing before the release | ✓ VERIFIED | lines 39-49, 417-476; called from compile_rule:530 |
| `tests/test_cc_log.py` | hammer (repo-build, tmp-path), sidecar, default paths, killed holder, two win32 tests | ✓ VERIFIED | 231 lines, 8 tests; collected and run in both suites |
| `tests/test_compiler_real.py` | `test_parallel_cc_keeps_one_log_line_per_compile` | ✓ VERIFIED | lines 235-277; drives `reverseapoc.cli.main` in 16 subprocesses |
| `docs/toolchain.md` | cc.log lock bullet | ✓ VERIFIED | line 321 |
| `docs/learnings.md` | 2026-10-22 O_APPEND entry | ✓ VERIFIED | newest dated entry |

### Key Link Verification

`gsd-tools verify.key-links` returned 0/3 with "Source file not found". The plan's `from:` fields
carry a symbol after the path (`tools/reverseapoc/compiler.py compile_rule`), which the tool does not
parse. I checked the three patterns by hand:

| From | To | Via | Status | Details |
|---|---|---|---|---|
| compiler.py compile_rule | compiler.py `_append_log` | `_append_log(log, result)` | WIRED | compiler.py:530, after every compile; `log = Path(log) if log is not None else DEFAULT_LOG` at :499 |
| compiler.py `_append_log` | compiler.py `_log_lock` | `with _log_lock(log)` | WIRED | compiler.py:474, wrapping `with log.open("a", ...)` at :475 |
| cli.py `_cmd_cc` | compiler.py `compile_source` | `log=args.log` | WIRED | cli.py:96; `--log` defaults to `DEFAULT_LOG` (cli.py:120) |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|---|---|---|---|---|
| cc.log | one line per compile | `_log_line(CompileResult)` from the real compile and gate | yes; the real parallel test counts 16 lines naming the 16 objects | ✓ FLOWING |
| `<log>.lock` | none (lock only) | opened `a+b`, never written | size 0 asserted | ✓ as designed |
| runtime.csv / probe scan / cppscan | unchanged | orig/ + LIB386 | reproduced by me | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Host suite + lint | `uv run pytest -q -rs && uv run ruff check .` | 1035 passed, 6 skipped (test_configure x3, test_hygiene container-only x3), `All checks passed!`, exit 0 | ✓ PASS |
| Container suite + lint | `docker compose run --rm build bash -lc "uv sync --locked -q && uv run pytest -q -rs && uv run ruff check ."` | 1039 passed, 2 skipped (both `Windows-only: msvcrt lock path`), `All checks passed!`, exit 0 | ✓ PASS |
| Concurrency tests x5, host | `uv run pytest -q -rs tests/test_cc_log.py tests/test_compiler_real.py::test_parallel_cc_keeps_one_log_line_per_compile` | `8 passed` five times, plus one earlier run | ✓ PASS |
| Concurrency tests x5, container | same, in `docker compose run --rm build` | `6 passed, 2 skipped` five times, exit 0 | ✓ PASS |
| Mutant M1 (no lock), container, out of tree | `PYTHONPATH=/work/build/verify-04/m1 uv run pytest -q -rs tests/test_cc_log.py` | `3 failed, 2 passed, 2 skipped` (repo-build `torn line start: '0'`, sidecar, killed holder) | ✓ PASS (guard bites) |
| Mutant M2 (release before close), container, out of tree | `PYTHONPATH=/work/build/verify-04/m2 uv run pytest -q -rs tests/test_cc_log.py` | `1 failed, 4 passed, 2 skipped` (repo-build `torn line start: '0'`) | ✓ PASS (guard bites) |
| WR-01 reproduction | `compiler._lock_path(Path('.'))` | `ValueError ... has an empty name` (before: `PermissionError`, an OSError) | ⚠️ behaviour change |
| WR-02 reproduction | `_append_log(Path('/dev/null'), r)` in container as `dev` | `PermissionError ... '/dev/null.lock'` (before: plain append to /dev/null succeeded) | ⚠️ behaviour change |
| Gate, C/C++, probe | `check-watcom 10.5 10.6 11.0`, `cppscan`, `probe scan UFO2P.EXE` | 8/8/10 ok; `C (wcc386)` for both; counts as in toolchain.md | ✓ PASS |
| Phase 3 non-regression | `check-orig`; `rebuild`; `cmp build/X orig/X` | 3 ok; three OK lines; cmp silent for UFO2P and TACP | ✓ PASS |

The mutants ran from copies under the gitignored build/verify-04/, loaded through PYTHONPATH (the writer
subprocesses inherit it, and `import reverseapoc.compiler` printed the copy's path). No tracked file was
touched; `git diff --exit-code -- tools/` stayed clean, and the copies were removed afterwards.

Note on one discarded run: my first host suite and first container check ran at the same time and
shared build/test-cc/<test>/ and build/test-cclog/<test>/. The host's real parallel test then saw
32 lines for 16 compiles (16 from each environment), and one container run failed. That is the
documented unsupported case (host and container on one log) plus a shared test directory, caused by
me. I discarded both runs and re-ran each environment alone, with the results above.

### Probe Execution

No `scripts/*/tests/probe-*.sh` exists or is declared. Step 7c: not applicable.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|---|---|---|---|---|
| CID-01 | 04-01, 04-03, 04-04, 04-06, 04-11, 04-12, 04-13 | compiler runs under wibo in Docker per version; hash and banner logged | ✓ SATISFIED | Truths 1, 11, 12, 14, 19; 04-13 makes the logged record survive parallel compiles (truths 20-23) |
| CID-02 | 04-01, 04-04, 04-12, 04-13 | wrapper + per-file flags table | ✓ SATISFIED | Truths 2, 8, 21 |
| CID-03 | 04-08, 04-10, 04-12 | probe idioms located in both code objects | ✓ SATISFIED | Truths 4, 16, 18 |
| CID-04 | 04-02, 04-05, 04-07, 04-12 | runtime modules match byte for byte (masked) | ✓ SATISFIED | Truths 3, 10, 13, 15 |
| CID-05 | 04-10, 04-11, 04-12 | version and flags in toolchain.md per EXE | ✓ SATISFIED (to the D-08 bar, override) | Truths 5, 7 |
| CID-06 | 04-09, 04-12 | C vs C++ scan confirms wcc386 | ✓ SATISFIED | Truth 6 |

No orphaned requirements: REQUIREMENTS.md maps exactly CID-01..06 to Phase 4, and every one appears in
at least one plan's `requirements`.

### Prohibitions of 04-13

| # | Prohibition | Tier | Enforcement found | Verdict |
|---|---|---|---|---|
| P1 | MUST NOT change `_log_line`, line text, `--log` or DEFAULT_LOG, or move the default log | test | `test_default_log_and_its_lock` pins DEFAULT_LOG; the `_log_line` text is pinned only by the plan's diff check (the sidecar test compares against `_log_line` itself); no test pins `--log` behaviour | ⚠️ flagged: interface held (my diff checks); `--log .` and `--log /dev/null` behaviour changed (WR-01, WR-02); see truth 24 |
| P2 | MUST NOT add a third-party dependency | test | no committed test; my check: pyproject.toml and uv.lock unchanged since c2d4054~1, `dependencies = []`, only stdlib fcntl/msvcrt/contextlib/errno/time imported | ⚠️ flagged (no wired test), observed held |
| P3 | MUST NOT use blocking msvcrt modes or treat every OSError as contention | test | `test_lock_retries_while_busy` (counts LK_NBLCK calls, so it fails under LK_LOCK) and `test_lock_does_not_swallow_other_errors` (M3 fails it); both pass on host | ✓ enforced, held |
| P4 | MUST NOT use mkdir/O_EXCL lock or delete the sidecar | test | killed-holder test (M5 fails it) and the sidecar-exists test; no unlink of the sidecar in compiler.py | ✓ enforced, held |
| P5 | MUST NOT import, run or name the gitignored prototype from a committed test | test | no committed test; my check: no `debug-cclog` in tests/test_cc_log.py or tests/test_compiler_real.py | ⚠️ flagged (no wired test), observed held |
| P6 | MUST NOT edit orig/, third_party/, config/*.toml, Docker files or existing assertions in test_compiler.py/test_cli.py; no note in place of a step | judgment | config/, docker/, test_compiler.py, test_cli.py unchanged since c2d4054~1; check-orig 3 OK; check-watcom OK; every gate and mutant log present with its exit line | LLM-judge (non-authoritative): held; human review recommended |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| (04-13 files) | - | TBD / FIXME / XXX / TODO / HACK | none found | - |
| tools/reverseapoc/compiler.py | 417-418 | `_lock_path` on a nameless `--log` raises an uncaught ValueError after the compile (WR-01) | ⚠️ Warning | edge input only; contradicts the literal "--log unchanged" (truth 24) |
| tools/reverseapoc/compiler.py | 458 | sidecar creation fails where the log's directory refuses new files, e.g. `/dev/null` in the container (WR-02) | ⚠️ Warning | edge input only; a valid object is left with exit 1; same truth-24 point |
| tests/test_cc_log.py, tests/test_compiler_real.py | 130; 266-268 | unbounded `wait()`/`communicate()`; asserts inside the reap loop (WR-03) | ⚠️ Warning | a future lock regression would hang the gate instead of failing it |
| tools/reverseapoc/compiler.py | 423-432 | EACCES covers more than contention; no deadline (IN-01) | ℹ️ Info | accepted design choice (no timeout) |
| tools/reverseapoc/compiler.py | 417-418 | sidecar follows the `--log` spelling, not the resolved file (IN-02) | ℹ️ Info | only with links or subst drives |
| docs/toolchain.md | 321 | "the host" means the Windows host with Docker Desktop (IN-03) | ℹ️ Info | docs precision |

None of these blocks the phase goal or G-04-2. Each comes from the review (04-REVIEW.md, still `open`
in 04-REVIEW-DISPOSITION.md), and I reproduced WR-01 and WR-02 myself.

### Advisory (New Scope, Unevidenced)

None. The re-verification evidence gate had no new-scope 🛑 Blocker to filter: the review findings are
graded ⚠️ Warning / ℹ️ Info above, and WR-01/WR-02 have deterministic reproductions.

### Human Verification Required

### 1. UAT re-test of G-04-2 (also closes the 04-01 backstop truth)

**Test:** Repeat 04-UAT.md test 2: many parallel `uv run reverseapoc cc` compiles inside one
environment (container bind mount; separately the Windows host), each environment with its own `--log`.
**Expected:** All compiles exit 0; no torn stamp trusted; cc.log has exactly one intact line per compile;
`cc.log.lock` exists and is empty.
**Why human:** The owner reported the failure, and the owner's re-check has not happened. The 04-01
backstop truth is non-inferable and needs observed behaviour.

### 2. Truth 24 / P1: `--log` behaviour for nameless and non-creatable-directory paths

**Test:** Read "Truth 24 and the review warnings" above. Decide whether "the --log option ... unchanged"
meant the interface (it holds) or every value's behaviour (WR-01 and WR-02 break it).
**Expected:** Either accept, by adding the override below (ideally with a toolchain.md note that `--log`
needs a file name and a directory where `<log>.lock` can be created), or reject. A rejection makes this
a gap for a small gap-closure plan: check the log name before the compile and raise CompilerError;
take no lock for a non-regular log, or check the sidecar before the compile; bound the test waits
(WR-03).
**Why human:** This is a reading of scope. The planned design (a sidecar beside whatever `--log` names)
makes the new precondition intrinsic.

### 3. 04-13 prohibitions without wired enforcement

**Test:** Confirm P1 (`--log` part), P2 and P5 (test tier, no committed test) and P6 (judgment) from the
table above.
**Expected:** Owner sign-off on the verifier's observations.
**Why human:** A test-tier prohibition with no wired test is never passed green, and judgment verdicts
are advisory.

### Gaps Summary

No blocking gaps. G-04-2 is closed in code:
- `_append_log` opens, writes and closes cc.log inside a stdlib OS lock on `<log>.lock`;
- the 16x25 hammer test and 16 real parallel compiles leave one intact line per call on the Windows host
  and on the container's 9p bind mount (my runs: host 6/6, container 5/5, plus both full suites);
- my own out-of-tree mutants confirm that the regression test bites with no lock and with a release
  before the close;
- every earlier plan's result reproduces unchanged.

Three items remain, all human:
- the owner's UAT re-test of G-04-2;
- a scope decision on truth 24, because the `--log` interface is unchanged but `--log .` and
  `--log /dev/null` behave differently (WR-01, WR-02);
- sign-off on four 04-13 prohibitions without wired enforcement.

WR-03 (untimed waits in the new tests) is a recommended fix, not a gap.

**If the owner accepts the `--log` change,** add to this file's frontmatter `overrides:`:

```yaml
  - must_have: "_log_line, the bytes-free line content (names, paths, argv, SHA-1s, exit codes), the --log option and the default build/logs/cc.log are unchanged, and no dependency is added"
    reason: "--log interface, default and _log_line are byte-identical; the sidecar <log>.lock beside whatever --log names (the planned design) adds the precondition that --log has a file name and its directory accepts new files, so --log . now tracebacks (WR-01) and --log /dev/null fails in the container (WR-02); neither is a path the project uses"
    accepted_by: "{owner}"
    accepted_at: "{ISO timestamp}"
```

---

_Verified: 2026-10-23T01:53:19Z_
_Verifier: Claude (gsd-verifier)_
