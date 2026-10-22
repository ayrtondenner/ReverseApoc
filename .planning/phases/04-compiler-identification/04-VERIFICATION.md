---
phase: 04-compiler-identification
verified: 2026-10-21T23:30:00Z
status: human_needed
score: 17/19 must-haves verified
covered_files: [".planning/phases/04-compiler-identification/04-01-PLAN.md", ".planning/phases/04-compiler-identification/04-01-SUMMARY.md", ".planning/phases/04-compiler-identification/04-02-PLAN.md", ".planning/phases/04-compiler-identification/04-02-SUMMARY.md", ".planning/phases/04-compiler-identification/04-03-PLAN.md", ".planning/phases/04-compiler-identification/04-03-SUMMARY.md", ".planning/phases/04-compiler-identification/04-04-PLAN.md", ".planning/phases/04-compiler-identification/04-04-SUMMARY.md", ".planning/phases/04-compiler-identification/04-05-PLAN.md", ".planning/phases/04-compiler-identification/04-05-SUMMARY.md", ".planning/phases/04-compiler-identification/04-06-PLAN.md", ".planning/phases/04-compiler-identification/04-06-SUMMARY.md", ".planning/phases/04-compiler-identification/04-07-PLAN.md", ".planning/phases/04-compiler-identification/04-07-SUMMARY.md", ".planning/phases/04-compiler-identification/04-08-PLAN.md", ".planning/phases/04-compiler-identification/04-08-SUMMARY.md", ".planning/phases/04-compiler-identification/04-09-PLAN.md", ".planning/phases/04-compiler-identification/04-09-SUMMARY.md", ".planning/phases/04-compiler-identification/04-10-PLAN.md", ".planning/phases/04-compiler-identification/04-10-SUMMARY.md", ".planning/phases/04-compiler-identification/04-11-PLAN.md", ".planning/phases/04-compiler-identification/04-11-SUMMARY.md", ".planning/phases/04-compiler-identification/04-12-PLAN.md", ".planning/phases/04-compiler-identification/04-12-SUMMARY.md", "config/cflags.txt", "config/tacp/runtime.csv", "config/ufo2p/runtime.csv", "config/watcom.toml", "docs/learnings.md", "docs/matching.md", "docs/research/wpack-format.md", "docs/toolchain.md", "probe/README.md", "probe/cg_basic.c", "tests/conftest.py", "tests/omfimage.py", "tests/test_cflags.py", "tests/test_cli.py", "tests/test_compiler.py", "tests/test_compiler_real.py", "tests/test_cppscan.py", "tests/test_cppscan_real.py", "tests/test_hygiene.py", "tests/test_libmatch.py", "tests/test_libmatch_real.py", "tests/test_omf.py", "tests/test_omf_real.py", "tests/test_probe.py", "tests/test_probe_real.py", "tests/test_targets.py", "tests/test_watcom.py", "tests/test_wpack.py", "tests/test_wpack_real.py", "tests/wpackimage.py", "tools/reverseapoc/cflags.py", "tools/reverseapoc/cli.py", "tools/reverseapoc/compiler.py", "tools/reverseapoc/cppscan.py", "tools/reverseapoc/libmatch.py", "tools/reverseapoc/omf.py", "tools/reverseapoc/probe.py", "tools/reverseapoc/targets.py", "tools/reverseapoc/watcom.py", "tools/reverseapoc/wpack.py"]
covered_digest: "v3:sha256:f9d73772cec1c6ca8e18a8c7e311f600adb6be3c0fa2e82ffcb30e7163145f56"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "The exact Watcom version and default flags that built each EXE are known and proven"
    reason: "D-08/D-10: runtime library 10.6 proven byte for byte; game code 10.6 preferred (one toolchain with the 10.6 runtime), 10.5 byte-identical on the probe and kept as first fallback, 11.0 tied at -4r and kept as candidate; flags beyond calling convention, -s and -fpi carried as candidates (-5, -fpi87, -fp3/-fp5, -o* subsets, -zp1/2/4/8, -zm, -j, -d1/-d2) for proof or permutation, listed in docs/toolchain.md 'Fallbacks and candidates'; the first Phase 5 matches settle 10.6 vs 10.5/11.0, -4 vs -5 and -o*"
    accepted_by: "ayrtondenner"
    accepted_at: "2026-10-22T19:25:11Z"
decision_coverage:
  honored: 16
  total: 16
  not_honored: []
human_verification:
  - test: "Decide whether the phase goal's 'exact Watcom version and default flags ... known and proven' is met by what was delivered: runtime library 10.6 proven byte for byte; game code 10.6 with 10.5 byte-identical on the probe and 11.0 tied at -4r on the decisive idioms; flags -4r -s -fpi supported by the scans but labelled 'consistent, not proven' by the project itself; -o*, -zp*, -zm, -fp3/-fp5 candidate, evidence pending"
    expected: "Owner either accepts the result under D-08/D-10 (record an override below, or reword the ROADMAP goal to the D-08/D-10 bar), or reopens the phase to separate 10.6 from 11.0 and -4 from -5 before Phase 5"
    why_human: "All five ROADMAP success criteria are met in the code; the gap is between the goal's literal wording and owner decisions D-08/D-10, which only the owner can reconcile"
  - test: "Backstop truth (04-01): parallel `uv run reverseapoc cc` processes under ninja -j share only the gate stamp and the append-only cc.log; a stamp can never be read half-written"
    expected: "Under concurrent compiles (Phase 5's first `ninja -j`), no compile fails or trusts a torn stamp; cc.log lines may interleave"
    why_human: "reason: insufficient_spec. Unit tests prove the atomic swap (test_stamp_written_atomically) and that a torn or wrong-shaped stamp is a cache miss, but no test runs concurrent processes; a non-inferable truth needs a held-out or observed concurrent run"
  - test: "Judgment-tier prohibitions (31 across plans 04-01..04-12): unverified-prohibition, human review recommended"
    expected: "Owner confirms the non-authoritative LLM-judge verdicts in 'Prohibitions' below (all observed as held), in particular T-04-13/A1: no OWPL code or comments copied into tools/reverseapoc/wpack.py"
    why_human: "Judgment-tier prohibitions are never silently passed; the LLM-judge verdict is advisory"
---

# Phase 4: Compiler identification Verification Report

**Phase Goal:** The exact Watcom version and default flags that built each EXE are known and proven: runtime library modules match byte for byte, and the codegen probe locates its idioms in the game's own code.
**Verified:** 2026-10-21T23:30:00Z
**Status:** human_needed
**Re-verification:** No (initial verification)

## Verdict on the goal wording (asked for explicitly)

The five ROADMAP success criteria are met in the codebase, and every CID requirement has working,
tested code behind it. The phase goal's colon defines "proven" as two things, and both hold:
runtime library modules match byte for byte (fixups masked) against 10.6's LIB386, and the probe's
idioms are located and counted in non-library code of both EXEs.

The words "exact version and default flags ... known and proven" are met only to the bar the owner
set in D-08 and D-10, not literally:

- **Runtime library: exact and proven.** Every runtime row in both EXEs lists 10.6; 11 rows per
  EXE match only 10.6; no row matches only 10.5 or only 11.0 (`config/ufo2p/runtime.csv`,
  `config/tacp/runtime.csv`, drift test green).
- **Game-code compiler: not exact.** 10.5 and 10.6 give byte-identical objects in all 10 flag sets
  (a D-10 tie, acceptable by D-10's own example). 11.0 is also consistent at `-4r -s` and
  `-4r -s -ox` on the decisive idiom families, and the docs call it "candidate, evidence pending:
  the first Phase 5 matches". The 10.6 choice rests on the linked 10.6 runtime (51+11 rows per EXE
  that 11.0's library does not have), which D-07 says to report separately from codegen. That is a
  strong inference, not a codegen proof.
- **Flags: partly proven.** Calling convention `r` (0 3S-only rows), `-s` for most code (40 / 32
  `__CHK` functions excepted) and `-fpi` (EMU387 row) are proven by scan. CPU `-4` rests on a few
  5-dword rep copies (2 in UFO2P, 6 in TACP) and no unrolled 5-dword run; the Flags table says
  "scan evidence", not "proven", even though D-08 lists `-4`/`-5` among the flags Phase 4 proves.
  Memory model is "consistent with `-mf`", not a flag proof. `-o*`, `-zp*`, `-zm`, `-fp3`/`-fp5`
  are "candidate, evidence pending", which D-08 allows. `config/cflags.txt` says its rule
  `*  wcc386@10.6  -4r -s -fpi` is "supported, not proven".

My judgement: the delivered result is honest and complete against D-08/D-10 and the ROADMAP success
criteria, so there is no code gap to plan. The goal sentence claims more than was delivered on
two points (the 10.6 vs 11.0 codegen tie and `-4` vs `-5`). That is an owner decision, so it is a
human-verification item, not a FAILED truth. To accept it, add an override (suggested text at the
end) or reword the goal to the D-08/D-10 bar. Phase 5 SC4 (a byte-identical hand match "with the
identified compiler") is the first point where the residual tie meets real evidence, but Phase 5's
roadmap does not name "separate 10.6 from 11.0" explicitly, so I did not move this item to
`deferred`.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1 (CID-01): for 10.5, 10.6 and 11.0 the original compiler runs under wibo 1.2.0 inside `docker compose run`, read-only from `third_party/watcom/` (10.x: BINNT loader + LX BINW compiler), compiles a test source to an object; each binary's hash and banner are logged | ✓ VERIFIED | `build/gate/04-12/08-container-real-verbose.log`: `test_compile_real[10.5/10.6/11.0]` PASSED under `/usr/local/bin/wibo`; compose mounts `../third_party/watcom:/work/watcom:ro` and `../third_party:/work/third_party:ro`; `build/logs/cc.log` lines carry banner (`Version 11.0` etc.) + gated SHA-1s + argv + exit; `check-watcom 10.5 10.6 11.0` run by me: 8/8/10 ok, 0 known bad; container suite re-run by me after the review fixes (see Spot-checks) |
| 2 | SC2 (CID-02): wrapper keyed by `compiler@version` reads `config/cflags.txt`; a test shows two sources compiled with the version and flags the table assigns to each | ✓ VERIFIED | `tools/reverseapoc/cflags.py` (parse/select, last match wins, `*` first), `compiler.py:482` `select_rule(load_cflags(...))`; `cli.py:89` `_cmd_cc` → `compile_source`; unit test with injected runner (two versions) and real `test_cflags_two_sources_real` (-5r → `and` form, -3r → `movzx` form) PASSED on host and container |
| 3 | SC3a (CID-04): linked CLIB3R/MATH3R modules from one version's LIB386 match the code objects byte for byte, fixups masked | ✓ VERIFIED | `libmatch.py` (KKND CC0 header line 1; uses `read_library`, `le.fixups()`); committed `config/ufo2p/runtime.csv` (121 ranges) and `config/tacp/runtime.csv` (132); every row lists 10.6; `_cstart_` row starts at 0x000C0784 / 0x000C28B0, equal to `parse-le` entry (checked by me); `test_runtime_csv_has_no_drift` re-derives both from orig/ + LIB386 and passes |
| 4 | SC3b (CID-03): the codegen probe compiled with each version locates its idioms in non-library code of both EXEs' code objects | ✓ VERIFIED | `probe/cg_basic.c` (clean-room, owner discretion replaces "mosura" sources); `probe scan UFO2P.EXE` run by me: 741,159 non-library bytes, setcc_and 30, setcc_movzx 0, movsd_unrolled 75, rep_movsd_small 4, 40 `__CHK` calls (matches toolchain.md); TACP 58/0/35/2/32 in evidence log and real tests; calibration over 30 cells (10.5/10.6/11.0 × 10 flag sets) in `03-probe-calibrate.log` |
| 5 | SC4 (CID-05): `docs/toolchain.md` records version and default flags per EXE with per-flag evidence, replacing "To be confirmed in Phase 4" | ✓ VERIFIED | toolchain.md "Result" (one column per EXE) and "Flags" (`| Flag | UFO2P | TACP | Evidence | Status |`), each row citing the reproducing command; stale phrase absent (`test_toolchain_records_the_compiler_result`); cflags `*` rule pinned to toolchain.md and matching.md by hygiene test |
| 6 | SC5 (CID-06): C vs C++ scan reports per EXE and confirms `wcc386` | ✓ VERIFIED | `cppscan UFO2P.EXE` / `TACP.EXE` run by me: `C (wcc386): no XI priority 64, no YI priority 40, no C++-only runtime module, no __wcpp_ or W? strings; 5 / 3 vtable-shaped candidate runs` |
| 7 | Goal wording: exact version and default flags "known and proven" | ? UNCERTAIN | See "Verdict on the goal wording": library version exact; game-code 10.6/11.0 tie at -4r; -4 is scan evidence; -o* etc. pending (D-08 allows). Owner decision requested |
| 8 | 04-01: `cc` wrapper (gate, banner, argv shape, scrubbed env, path allowlist, failed-compile cleanup, ordering, atomic stamp) | ✓ VERIFIED | `compiler.py` (`check_gate`→`watcom.check_version` line 224, `scrubbed_env` line 106, list argv, no `shell=True` anywhere in tools/); test_compiler.py / test_cflags.py / test_cli.py green |
| 9 | 04-01 backstop: parallel `cc` processes share only stamp + log; a stamp is never read half-written | ⚠️ insufficient_spec | os.replace swap and torn-stamp-is-a-miss are unit-tested; no concurrent-process test exists. Human item 2 |
| 10 | 04-02: stdlib OMF reader (LIB walk, FIXUPP threads, LIDATA, Easy OMF, COMDAT32, normalized SHA-1, failures recorded) | ✓ VERIFIED | `omf.py` 931 lines; test_omf.py + test_omf_real.py (CLIB3R module counts 544/549/970, NT/ COFF reported not OMF) green on host |
| 11 | 04-03: wpack format doc before decoder (D-15), independent decoder, real decode of PCK00017 (D-01 LANDED) | ✓ VERIFIED | `43eb1fa` (doc) precedes `b5d8e3d` (code); wpack.py header cites doc and OW as format reference only; test_wpack_real.py green; decoded size 567,558 pinned |
| 12 | 04-04: object + normalized SHA-1 logged; real compiles per version; env-scrub, `-bt=dos`, error path proofs | ✓ VERIFIED | `compiler.py:399` `omf.normalized_object_sha1`; cc.log shows `sha1 ... normalized ...`; test_compiler_real.py all versions PASSED (host; container re-run) |
| 13 | 04-05: `libmatch` sweep, masking, rejection rules, merge/disambiguation, runtime.csv format, `config_dir` (D-16) | ✓ VERIFIED | `libmatch.py` 835 lines, `targets.config_dir` line 94, `_cmd_libmatch` → `write_runtime_csv`; test_libmatch.py green |
| 14 | 04-06: `install-watcom 10.5` decodes BINW/WCC386.EXE in the partial tree; manifest pin; hash from real decode | ✓ VERIFIED | `watcom.py:494-496` `join_parts` + `decode_member` with `expected_size=kf.size`; `config/watcom.toml` 10.5 BINW entry size 567558, sha1 a479921b..., `wpack_member`; distinct from 10.6 (567,698, 183433f9...) and 11.0; check-watcom 10.5 OK |
| 15 | 04-07: both runtime.csv committed, drift test, `_cstart_` at entry, a discriminating module, no overlap, summary, no-bytes CSV test | ✓ VERIFIED | All asserted in `test_libmatch_real.py` (read by me; compares full text) and passing; CSV cells are addresses, names, versions, statuses only |
| 16 | 04-08: clean-room probe, `count_idioms`, `calibrate` over every version × FLAG_SETS, `ties()` | ✓ VERIFIED | `probe.py` `calibrate` line 752 uses `compile_rule`, `object_code` uses `omf.read_object`; calibration log has 10 `tie: ... 10.5 10.6` lines; research-row deviations (register row, switch order) recorded in toolchain.md, not forced |
| 17 | 04-09: `cppscan` (inirt386 XI/YI tables, priorities, C++-only rows, strings, vtable candidates never decide) | ✓ VERIFIED | `cppscan.py` 477 lines; CLI verdicts reproduced by me; XI/YI table addresses and profiles in toolchain.md |
| 18 | 04-10: `probe scan` with runtime rows excluded, `__CHK` by block, flag evidence lines citing their source, `consistent_cells` | ✓ VERIFIED | Output reproduced by me (each evidence line ends with `(source: ...)`); 04-10 real expectation "no 11.0/-4r cell, rep_movsd_small == 0" did not hold and was recorded as measured (4/2; 11.0 -4r consistent), per the plan's "recorded, not forced" clause |
| 19 | 04-11/04-12: D-03 native vs wibo equal; spike 004 VALIDATED; docs updated; host and container gates | ✓ VERIFIED | `build/gate/04-native-vs-wibo.txt` ends `D-03: normalized equal for 10.5, 10.6, 11.0`, no DIFFERENT line; spike README `verdict: VALIDATED`, MANIFEST row 004; host suite run by me: 1027 passed, 6 platform skips (none real-file), ruff clean; `rebuild` three OK and `cmp` silent (run by me) |

**Score:** 17/19 truths verified (0 present, behavior-unverified; 1 insufficient_spec; 1 uncertain, owner decision)

### Required Artifacts

`gsd-tools verify.artifacts` over all 12 plans: 37/37 artifacts pass (exists, size, `contains`).

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tools/reverseapoc/cflags.py` | rules parser, `CflagsError` | ✓ VERIFIED | 163 lines, imported by compiler.py and test_hygiene.py |
| `tools/reverseapoc/compiler.py` | gate, argv, env, compile | ✓ VERIFIED | 494 lines, called by cli `_cmd_cc` and probe `calibrate` |
| `tools/reverseapoc/omf.py` | OMF reader | ✓ VERIFIED | 931 lines, used by libmatch, probe, cppscan, compiler |
| `tools/reverseapoc/wpack.py` | wpack decoder | ✓ VERIFIED | 472 lines, used by watcom.install_version |
| `tools/reverseapoc/libmatch.py` | library matcher | ✓ VERIFIED | 835 lines, CLI `libmatch`, used by probe and cppscan |
| `tools/reverseapoc/probe.py` | calibrate, scan, flag evidence | ✓ VERIFIED | 1109 lines, CLI `probe calibrate|scan` |
| `tools/reverseapoc/cppscan.py` | C/C++ scan | ✓ VERIFIED | 477 lines, CLI `cppscan` |
| `tools/reverseapoc/watcom.py` | wpack decode step, 10.5 pin | ✓ VERIFIED | `decode_member` in install_version |
| `config/cflags.txt` | evidence-backed `*` rule | ✓ VERIFIED | `*  wcc386@10.6  -4r -s -fpi` |
| `config/watcom.toml` | decoded 10.5 BINW pin | ✓ VERIFIED | size 567558, `wpack_member = "wcc386.exe"` |
| `config/ufo2p/runtime.csv`, `config/tacp/runtime.csv` | runtime maps | ✓ VERIFIED | 121 / 132 rows, `_cstart_` at entry |
| `probe/cg_basic.c`, `probe/README.md` | clean-room probe | ✓ VERIFIED | 75 / 106 lines |
| `docs/research/wpack-format.md` | D-15 format doc | ✓ VERIFIED | 350 lines, committed first |
| `docs/toolchain.md`, `docs/matching.md` | CID-05 record | ✓ VERIFIED | Result, Flags, C not C++; matching.md rows per EXE |
| `.planning/spikes/004-wibo-watcom/README.md` | spike record | ✓ VERIFIED | `verdict: VALIDATED` |

### Key Link Verification

`gsd-tools verify.key-links`: 25/26 by pattern. The one miss is a log-pattern artefact.

| From | To | Via | Status | Details |
|---|---|---|---|---|
| cli.py | compiler.py | `compile_source(` | WIRED | cli.py:90 |
| compiler.py | watcom.py | `check_version(` | WIRED | compiler.py:224 |
| compiler.py | cflags.py | `select_rule(` | WIRED | compiler.py:482 |
| compiler.py | omf.py | `normalized_object_sha1(` | WIRED | compiler.py:399 |
| watcom.py | wpack.py | `decode_member(` | WIRED | watcom.py:496 |
| libmatch.py | omf.py / le.py | `read_library(`, `fixups()` | WIRED | libmatch.py:311, 350 |
| cli.py | libmatch.py | `write_runtime_csv(` | WIRED | cli.py:161 |
| probe.py | compiler.py / omf.py | `compile_rule(`, `read_object(` | WIRED | probe.py:802, 580/745 |
| probe.py | runtime.csv | `read_runtime_csv(` | WIRED | probe.py:870 |
| cli.py | probe.py | `consistent_cells(` | WIRED | cli.py:260 |
| cppscan.py | libmatch.py / omf.py | `CPP_LIBRARY_PREFIXES`, `read_library(` | WIRED | cppscan.py:46, 238, 354 |
| tests/test_hygiene.py | config/cflags.txt | `parse_cflags(` | WIRED | test_hygiene.py:133 |
| build/gate/04-12/06-container-suite.log | tests/test_compiler_real.py | container run executes the real compile tests | WIRED (alternate evidence) | 06 is `-q` output without test names; `08-container-real-verbose.log` lists all 12 test_compiler_real cases PASSED under wibo, and my own post-fix container run covers it |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|---|---|---|---|---|
| runtime.csv | rows | `libmatch.scan_exe` over orig/ EXE + LIB386 OMF modules | yes; drift test re-derives from real files | ✓ FLOWING |
| toolchain.md idiom table | counts | `probe scan` over the LE code object minus runtime rows | yes; my run reproduces 30/0/75/4/40 for UFO2P | ✓ FLOWING |
| toolchain.md C/C++ row | verdict | `cppscan` over relocated image + runtime map | yes; my run reproduces both verdict lines | ✓ FLOWING |
| cc.log | banner, SHA-1s | no-arg compiler run + gated file hashes | yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Host suite + lint after review fixes | `uv run pytest -q -rs` ; `uv run ruff check .` | 1027 passed, 6 skipped (test_configure Windows names x3, test_hygiene container-only x3), no real-file skip; ruff clean | ✓ PASS |
| Container suite after review fixes | `docker compose run --rm test bash -lc "uv sync --locked && uv run pytest -q -rs && uv run ruff check ."` | 1033 passed, 0 skipped (every real-file test ran under wibo 1.2.0 with orig/ and the read-only Watcom trees, including the 10.5 cases WR-05 enabled after the 18:39 gate); ruff clean | ✓ PASS |
| Compiler gate | `uv run reverseapoc check-watcom 10.5 10.6 11.0` | 8 / 8 / 10 ok, 0 mismatched, 0 missing, 0 known bad | ✓ PASS |
| C vs C++ | `uv run reverseapoc cppscan UFO2P.EXE` / `TACP.EXE` | `C (wcc386): ...` for both | ✓ PASS |
| Probe scan | `uv run reverseapoc probe scan UFO2P.EXE` | counts equal toolchain.md table; every evidence line names its source | ✓ PASS |
| Entry corroboration | `uv run reverseapoc parse-le orig/{UFO2P,TACP}.EXE` | entry 0x000c0784 / 0x000c28b0 = `_cstart_` row starts | ✓ PASS |
| Phase 3 non-regression | `uv run reverseapoc rebuild` ; `cmp build/X orig/X` | three OK lines; cmp silent for UFO2P, TACP, SMKP | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` exists or is declared by the plans; "probe" in this phase is the codegen probe, exercised above. Step 7c: not applicable.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|---|---|---|---|---|
| CID-01 | 04-01, 04-03, 04-04, 04-06, 04-11, 04-12 | compiler runs under wibo 1.2.0 in Docker per version, read-only | ✓ SATISFIED | Truths 1, 11, 12, 14, 19 |
| CID-02 | 04-01, 04-04, 04-12 | wrapper + per-file flags table | ✓ SATISFIED | Truths 2, 8 |
| CID-03 | 04-08, 04-10, 04-12 | probe idioms located in both code objects (non-library) | ✓ SATISFIED | Truths 4, 16, 18 |
| CID-04 | 04-02, 04-05, 04-07, 04-12 | runtime modules match byte for byte (masked) | ✓ SATISFIED | Truths 3, 10, 13, 15 |
| CID-05 | 04-10, 04-11, 04-12 | version and default flags in toolchain.md with per-flag evidence, per EXE | ✓ SATISFIED (to the D-08 bar) | Truth 5; see goal-wording verdict |
| CID-06 | 04-09, 04-12 | C vs C++ scan confirms wcc386 | ✓ SATISFIED | Truth 6 |

No orphaned requirements: REQUIREMENTS.md maps exactly CID-01..06 to Phase 4, and every one appears in at least one plan's `requirements`.

### Decision Coverage

All trackable CONTEXT.md decisions are honored by shipped artifacts (16/16, `check.decision-coverage-verify`).

### Prohibitions (judgment tier, non-authoritative LLM-judge verdicts; unverified-prohibition, human review recommended)

| Prohibition (grouped) | Plans | LLM-judge verdict | Evidence seen |
|---|---|---|---|
| No compiler, library, object or game bytes printed, logged, committed or in fixtures | 01, 02, 03, 04, 05, 07, 08, 09, 10, 11, 12 | held | cc.log, gate logs and runtime.csv hold names, addresses, counts, SHA-1s only; no tracked .exe/.lib/.obj/.dll/.iso or third_party/orig/build path in `git ls-files`; CSV no-bytes test green |
| Compiler not started through a shell or with inherited environment | 01 | held | no `shell=True`/`os.system`/`os.popen` in tools/; `scrubbed_env`; real env-injection test green |
| No Watcom file in repo, image or config/ | 01, 03 | held | compose mounts third_party read-only; `git ls-files` clean |
| No Open Watcom code copied; KKND derivation headers kept | 02, 03, 05 | held (owner A1 sign-off pending, T-04-13) | libmatch.py line 1 CC0 header; wpack.py header; doc committed before code |
| 10.5 decoder past time box does not block (D-01) | 03 | held (moot: LANDED) | D-01 verdict LANDED |
| Only the 10.5 BINW hash edited in watcom.toml; values from own decode | 06 | held | test_wpack_real compares decoder output to manifest pin via `load_watcom_manifest` |
| No writes into orig/ or third_party/ except via install-watcom | 04, 05, 06, 11, 12 | held | outputs under build/; WR-02 protects default orig/ and Watcom tree |
| runtime.csv never hand-edited; MIN_UNMASKED and disambiguation not tuned to research numbers | 07 | held | drift test regenerates text-identical; deviations recorded as measured |
| Probe/counters not changed to force research rows; ties stay ties, no votes | 08, 10 | held | 04-10 assertions changed to measured values with the reason recorded; consistent cells printed as a list with ties |
| Vtable-shaped runs never decide the verdict | 09 | held | reported as candidates in the verdict line |
| Docs state nothing the logs do not show; candidates labelled | 11 | held | -o*, -zp*, -zm, -fp3/-fp5 "candidate, evidence pending"; 11.0 "candidate"; cflags "supported, not proven" |
| Gate not made to pass by editing protected paths; no note in place of a step | 12 | held | gate logs end `exit=0`; my own re-runs agree |

### Test Quality Audit

| Test file | Linked req | Skipped (host run) | Circular | Assertion level | Verdict |
|---|---|---|---|---|---|
| test_compiler_real.py | CID-01, CID-02 | 0 | no | value (SHA-1 equality, public names, x86 encodings) | OK |
| test_libmatch_real.py | CID-04 | 0 | drift test is self-consistency by design; `_cstart_` at LE entry is an independent oracle | value | OK |
| test_probe_real.py | CID-03, CID-05 | 0 | no; expected rows from research or measured and recorded | value | OK |
| test_cppscan_real.py | CID-06 | 0 | no | value (verdict, counts) | OK |
| test_wpack_real.py, test_omf_real.py | CID-01, CID-04 | 0 | no; manifest pin and known module counts | value | OK |
| test_hygiene.py (toolchain/cflags) | CID-05 | 0 | no | value (text presence) | OK |

Disabled tests on requirements: 0. Circular patterns: 0 blocking. Insufficient assertions: 0.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| (all phase files) | - | TBD / FIXME / XXX | none found | only test_hygiene.py:73 mentions "TBD" in a comment describing the rule against it |
| docs/learnings.md | 50 | stale "(to be confirmed in Phase 4)" inside an older BINNT entry that was edited this phase | ⚠️ Warning | docs only; toolchain.md is clean and the 2026-10-21 entry above it states the fact |
| config/watcom.toml | 37, 106 | 10.5/10.6 BINNT notes say "the real LE compiler" (BINW compilers are LX) | ℹ️ Info | protected manifest, owner item; recorded in learnings.md |
| build/gate/04-12/06-container-suite.log | - | `-q` log cannot show which real tests ran | ℹ️ Info | covered by 08-container-real-verbose.log and my re-run |

### Human Verification Required

### 1. Goal wording vs delivered result

**Test:** Read "Verdict on the goal wording" above and decide whether "exact Watcom version and default flags ... known and proven" is met by: runtime library 10.6 proven; game code 10.6 (10.5 identical on the probe, 11.0 tied at `-4r`); flags `-4r -s -fpi` supported by scans, `-4` not proven; `-o*`/`-zp*`/`-zm`/`-fp3`/`-fp5` pending.
**Expected:** Accept under D-08/D-10 (override or goal reword) or reopen.
**Why human:** The ROADMAP success criteria are met; only the owner can reconcile the goal sentence with D-08/D-10.

### 2. Concurrent `cc` stamp safety (backstop, insufficient_spec)

**Test:** Run several `uv run reverseapoc cc` compiles in parallel (Phase 5's first `ninja -j`), starting with no stamp under `build/cache/`.
**Expected:** Every compile succeeds; no stamp is ever trusted half-written; cc.log lines may interleave.
**Why human:** Unit tests cover the atomic swap and the torn-stamp miss, not concurrent processes.

### 3. Judgment-tier prohibitions

**Test:** Confirm the LLM-judge verdicts in the Prohibitions table, in particular A1 (T-04-13): no OWPL code or comments in `tools/reverseapoc/wpack.py`.
**Expected:** Owner sign-off.
**Why human:** Judgment-tier prohibitions are never passed silently.

### Gaps Summary

No blocking gaps. Every artifact exists, is substantive and is wired; the host suite (1027 passed,
no real-file skip) and the container suite pass after the review fixes; the library map, probe scan
and C/C++ scan reproduce the numbers recorded in docs/toolchain.md. The open points are owner
decisions: whether the goal's "exact ... proven" wording is satisfied by the D-08/D-10 bar (10.6
vs 11.0 tie at `-4r`, `-4` and `-o*` not proven), one non-inferable concurrency truth, and the
judgment-tier prohibitions including the T-04-13 A1 sign-off.

**This looks intentional.** To accept the goal-wording deviation, add to this file's frontmatter:

```yaml
overrides:
  - must_have: "The exact Watcom version and default flags that built each EXE are known and proven"
    reason: "D-08/D-10: runtime library 10.6 proven byte for byte; game code 10.6 with 10.5 identical and 11.0 tied at -4r on the probe, flags beyond calling convention, -s and -fpi carried as candidates; the first Phase 5 matches settle 10.6 vs 11.0, -4 vs -5 and -o*"
    accepted_by: "{owner}"
    accepted_at: "{ISO timestamp}"
```

---

_Verified: 2026-10-21T23:30:00Z_
_Verifier: Claude (gsd-verifier)_
