---
phase: 03-byte-identical-round-trip
verified: 2026-10-20T23:17:11Z
status: human_needed
score: 63/63 must-haves verified
covered_files:
  - .planning/phases/03-byte-identical-round-trip/03-01-PLAN.md
  - .planning/phases/03-byte-identical-round-trip/03-01-SUMMARY.md
  - .planning/phases/03-byte-identical-round-trip/03-02-PLAN.md
  - .planning/phases/03-byte-identical-round-trip/03-02-SUMMARY.md
  - .planning/phases/03-byte-identical-round-trip/03-03-PLAN.md
  - .planning/phases/03-byte-identical-round-trip/03-03-SUMMARY.md
  - .planning/phases/03-byte-identical-round-trip/03-04-PLAN.md
  - .planning/phases/03-byte-identical-round-trip/03-04-SUMMARY.md
  - .planning/phases/03-byte-identical-round-trip/03-05-PLAN.md
  - .planning/phases/03-byte-identical-round-trip/03-05-SUMMARY.md
  - .planning/phases/03-byte-identical-round-trip/03-06-PLAN.md
  - .planning/phases/03-byte-identical-round-trip/03-06-SUMMARY.md
  - configure.py
  - docs/learnings.md
  - docs/toolchain.md
  - tests/conftest.py
  - tests/test_cli.py
  - tests/test_configure.py
  - tests/test_hygiene.py
  - tests/test_le.py
  - tests/test_splice.py
  - tests/test_splice_real.py
  - tools/reverseapoc/cli.py
  - tools/reverseapoc/le.py
  - tools/reverseapoc/splice.py
covered_digest: "v3:sha256:34f8a52a8cfbda2adbd91a3a96a49cff7208c75e46e15d2f35132c07c28fb57a"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 54/55
  gaps_closed:
    - "G-03-3 (UAT test 3): code-review warnings WR-02, WR-05 and WR-06 are fixed in Phase 3 (plan 03-06)"
    - "03-01 backstop truth (concurrent rebuilds never false-OK): owner accepted the single-user-CLI argument in UAT test 2"
    - "03-05 judgment prohibition (facts pinned only from spikes): owner passed UAT test 1"
  gaps_remaining: []
  regressions: []
coincidental_reliance_items:
  - truth: "splice(le, {va: bytes}) applies linear-address patches in flat address space (D-01) and the rebuild gate reports any patched byte as a mismatch"
    reason: undeclared-precondition
    harden: "Objects must own disjoint logical pages and disjoint VA ranges; layout()/splice() do not enforce it (03-REVIEW WR-01). The three real targets satisfy it (identity page map pinned by test_measured_facts). Owner-deferred to Phase 5: refuse shared logical pages and overlapping objects in layout() before splice() lands real patches."
human_verification:
  - test: "Judgment-tier prohibition (03-06): WR-01, WR-03, WR-04 and IN-01..IN-08 behaviour is unchanged by plan 03-06"
    expected: "`git diff 9158a03 HEAD -- tools/reverseapoc/splice.py tools/reverseapoc/cli.py` shows only the masked-count line (splice.py:635) and two comments; cli.py has no change; configure.py HEADER comments and descriptions (IN-08 wording) are byte-identical apart from the two `--orig {orig}` command lines"
    why_human: "verification: judgment. Non-authoritative verifier verdict: HOLDS (diff read line by line; tests/test_cli.py and tools/reverseapoc/cli.py have no change since 9158a03). unverified-prohibition - human review recommended."
  - test: "Judgment-tier prohibition (03-06): orig/, config/targets.toml and the Docker files were not edited, and configure.py was not edited during the Task 3 gate"
    expected: "No commit after 918b4f9 (2026-10-20 20:01 -0300) touches configure.py; the gate logs are stamped 20:06 local; `git diff 9158a03 HEAD -- config docker compose.yaml` is empty; orig/ SHA-1s equal the manifest"
    why_human: "verification: judgment. Non-authoritative verifier verdict: HOLDS (all four checks above were run by the verifier and hold; working tree is clean apart from .planning/milestone.lock). unverified-prohibition - human review recommended."
  - test: "Owner triage of the four new open review findings in 03-REVIEW-DISPOSITION.md: WR-07, IN-09, IN-10, IN-11 (and IN-01..IN-08, still open)"
    expected: "Each set to fixed, deferred (with reason) or skipped. Verifier judgment: none breaks a Phase 3 must-have or ROADMAP success criterion. WR-07 is a real hole next to the WR-06 contract (reproduced: a surrogate-bearing exe name raises UnicodeEncodeError and leaves build.ninja empty) but lies outside the WR-06 truth as written (| LF CR and the --orig allowlist) and cannot occur with the three ASCII-named targets"
    why_human: "Disposition is an owner decision; the review is advisory."
---

# Phase 3: Byte-identical round trip Verification Report

**Phase Goal:** UFO2P.EXE and TACP.EXE (plus SMKP.EXE, as a second layout without a trailer) are rebuilt from decomposed parts through a KKND-style in-place page splice and proven SHA-1 identical to the originals, by a gate that demonstrably fails on any one-byte change.
**Verified:** 2026-10-20T23:17:11Z
**Status:** human_needed
**Re-verification:** Yes. The previous report (human_needed, 54/55) went stale when gap-closure plan 03-06 changed configure.py, splice.py, test_configure.py and test_splice.py. This report covers the current tree (HEAD 83bc0b3) and adds 03-06's must-haves.

The verifier ran every check below in its own process on the main checkout. orig/ was only read.
Outputs went to build/ (scratch dirs were removed afterwards) and to the session scratchpad.
build.ninja was backed up before the container runs and is byte-identical afterwards. No source
file was edited. SUMMARY claims were used as leads, not as evidence.

## Goal Achievement

### ROADMAP success criteria

| # | Success criterion | Status | Evidence (verifier-run, this session) |
|---|---|---|---|
| SC1 | `rebuild` writes build/UFO2P.EXE, TACP.EXE, SMKP.EXE; `cmp` silent; SHA-1 == `config/targets.toml`; reassembled, not copied (RT-01, RT-03) | VERIFIED | Deleted the three build/*.EXE, ran `uv run reverseapoc rebuild`: three `OK ... == manifest` lines, exit 0. `cmp` exit 0 for all three. `sha1sum` of orig/ and build/ equals manifest lines 19/29/38. 03-06 changed only the masked-count line in splice.py, so the fresh-buffer `assemble()` path from the previous verification is unchanged (diff read) |
| SC2 | Round-trip pytest for both EXEs, skipped without orig/, passes on host and in `docker compose run --rm test` (RT-03) | VERIFIED | Host `uv run pytest -q -rs`: 349 passed, 5 skipped (2 Windows-only `\|`/LF name tests, 3 container-only hygiene). No real-file skip. `docker compose run --rm test` re-run: 354 passed, exit 0. `REVERSEAPOC_ORIG=<empty dir>` on test_splice_real.py + test_le_real.py: 33 skipped, 0 failed |
| SC3 | One-byte mutations (mid-page, page edge, short last page, across a boundary) change the SHA-1 and name the offset; splice refuses out-of-page writes and length change; straddlers in flat space (RT-02, RT-04) | VERIFIED | Covered by the D-13 synthetic suite and the real-file control in test_splice_real.py, all passing in the run above. The previous verification's real-file spot-checks on all three EXEs exercised code 03-06 did not touch. 03-06's WR-02 change alters only the reported count, never the bytes written |
| SC4 | Region map tiles every byte; coverage test fails on unassigned or double-assigned byte (RT-05) | VERIFIED | `layout()`/`check_tiling()` unchanged since the previous verification. test_check_tiling_rejects_gap/_overlap and test_layout_tiles_real_file pass |
| SC5 | docs/toolchain.md records confirmed edge cases as offsets, lengths, hashes only; EOF and "To be confirmed" lines removed (RT-05) | VERIFIED | docs/toolchain.md unchanged by 03-06; test_toolchain_records_the_confirmed_le_layout passes |

### Plan must-have truths

| Plan | Truths | Status | Notes |
|---|---|---|---|
| 03-01 | 17 | 17 VERIFIED | Regression check: suite green, fresh rebuild OK. The `backstop` truth (concurrent rebuilds never false-OK) was resolved by the owner in UAT test 2 (single-user-CLI argument accepted; atomic write is WR-03, deferred to Phase 5) |
| 03-02 | 4 | 4 VERIFIED | `rule rebuild` in the console pool, `build verify: phony $builddir/always/verify`, header lists `ninja verify`. The rebuild command now reads `rebuild --orig orig` (03-06 superseded the bare form deliberately). Hash guard + planted-hash self-test pass |
| 03-03 | 14 | 14 VERIFIED | splice.py splice()/masking unchanged by 03-06 (diff: count line + two comments). All D-13/D-02/D-04/D-18 tests pass |
| 03-04 | 7 | 7 VERIFIED | `--json` 8-key contract: tests/test_cli.py unchanged since 9158a03, JSON tests pass; `rebuild --json --exe tacp.exe` printed the 8 keys, status ok |
| 03-05 | 8 | 8 VERIFIED | Real-file round trip, control, straddler/cut sweeps and FACTS pass. 03-05 gate logs remain under build/gate/. FACTS provenance (judgment prohibition) passed by the owner in UAT test 1 |
| 03-06 | 8 | 8 VERIFIED | See next table |

#### 03-06 truths (gap closure G-03-3)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | WR-05: `configure.py --orig DIR` writes `check-orig --orig REL` and `rebuild --orig REL`, REL relative to build.ninja's dir, default `--orig orig` | VERIFIED | configure.py:36/46 template, :103 `HEADER.format(orig=_check_orig_dir(orig))`, :136 `render(exes, orig=_relative(args.orig, base))`. CLI smoke: `configure.py --orig build/verify-smoke/elsewhere --output build/verify-smoke/build.ninja` gave both lines with `--orig elsewhere` (grep -x). Default build.ninja lines 15 and 25 carry `--orig orig`. In-process mutant (render ignores orig): 15 test_configure tests fail |
| 2 | WR-05 end to end: commands from a generated build.ninja read the --orig dir (host CLI test; container ninja 1.11.1) | VERIFIED | test_generated_commands_read_the_orig_dir passes. Container step 7 re-run by the verifier: `ninja -t commands` shows `--orig ../tmp/alt-orig` for both, `ninja verify` 3 OK lines, exit 0. Falsification run (verifier-added): `--orig /tmp/fake-orig` holding a 12-byte non-game marker made `ninja verify` print REFUSED/MISSING and exit 1, and `ninja check-orig` print `checking ../tmp/fake-orig` + MISMATCH and exit 1. So ninja really reads the --orig dir; it does not fall back to orig/ |
| 3 | WR-06: `configure.py: error:`, exit 1, no build.ninja for an exe path with `\|` LF CR, or an --orig path outside `[A-Za-z0-9._/:-]` | VERIFIED | configure.py:60/70-75 and :65/79-86, :137-139 return before write. CLI smoke: `--orig "build/verify-smoke/my orig"` exit 1, error line, existing sentinel file unchanged, new output not created. Tests: render/main refusal tests (pipe/lf/cr, 9 unsafe dirs, sentinel) pass; POSIX real-name tests pass in the container (354 passed, none skipped). In-process mutant (refusals off): 15 tests fail |
| 4 | WR-06: names with spaces keep working; parse_le rule exactly `command = uv run reverseapoc parse-le $in` | VERIFIED | test_main_keeps_names_with_spaces and the exact-line assertion (tests/test_configure.py:120) pass; build.ninja:20 holds the unquoted rule |
| 5 | WR-02: masked_fields (text and --json) counts distinct fixup fields; SpliceResult.masked keeps per-(patch, field) entries; 8 JSON keys | VERIFIED | splice.py:635 `len({m.fixup for m in result.masked})`, feeding :637/:639 `masked_fields=masked`. test_mask_count_counts_distinct_fields (5 ids) passes; in-process mutant back to `len(result.masked)`: touching, three-patches, straddling, mixed fail, two-fields passes (matches the SUMMARY). JSON_KEYS tests pass |
| 6 | Existing assertions stay: test_configure.py loses only its line-73 rebuild expectation; test_splice.py only gains; test_cli.py unchanged | VERIFIED | `git diff -U0 9158a03 HEAD -- tests/test_configure.py` removes exactly one line (`assert "command = uv run reverseapoc rebuild" in block`); test_splice.py diff is +23/-0; `git diff --stat 9158a03 HEAD -- tests/test_cli.py` is empty |
| 7 | Phase gate re-run on the main checkout: 7 steps each exit 0, logs under build/gate/03-06/, reproduced in the SUMMARY | VERIFIED | Seven logs exist, each ends `exit=0`; 03-cmp.log is exactly `exit=0`. Every line of every log appears verbatim in the SUMMARY's "## Phase gate output" section (scripted line check, 0 missing), with 7 `exit=0` and no non-zero exit. Logs are stamped after the last configure.py commit. The verifier independently re-ran steps 1, 2, 3, 4 and 7 with the same results |
| 8 | 03-REVIEW-DISPOSITION.md records WR-02/05/06 fixed citing 03-06; WR-01/03/04 deferred | VERIFIED | Rows 87-89 `fixed` with "fixed in plan 03-06 (918b4f9, ee1dcaa)"; rows 94-96 `deferred` with Phase 5/6 reasons. `open: 12` = the plan's 8 plus WR-07 and IN-09..IN-11 added by the re-review |

**Score:** 63/63 truths verified (5 SCs + 58 plan truths; 0 present-but-behavior-unverified).
The behavior-dependent truths each have a passing named test in this session's suite run. The
WR-02 count and the WR-05/WR-06 guards were also falsified with in-process mutants, and the
source was left untouched.

### Prohibitions

| Plan | Prohibition | Tier | Disposition |
|---|---|---|---|
| 03-01/03-04 | No write under orig/ | test | VERIFIED: `_refuse_inside_orig` guard + test; orig/ SHA-1s equal the manifest after all verifier runs, container mount read-only |
| 03-01/03-03 | No copy-then-overwrite of the original buffer | test | VERIFIED (unchanged by 03-06). Caveat as before: a copy-then-overwrite-pages `reassemble()` is output-equivalent and only the `assemble()` signature prevents it |
| 03-01/03-05 | Trailer never regenerated | test | VERIFIED |
| all | No game bytes in messages, reports, JSON, docs, tests, logs | test | VERIFIED. Report-level guards (test_mask_report_has_no_bytes, test_mutation_report_names_offset_without_bytes, test_parse_le_reports_trailer_without_bytes) pass. 03-06's new tests use the synthetic fixture and a `b"not the game"` marker. The gate logs hold only pytest/ruff summaries, manifest SHA-1s and command lines |
| 03-02/03-05/03-06 | No edit to config/targets.toml or the Docker files; no copied hashes | test | VERIFIED: no change to config/ or docker/ since 9158a03; test_round_trip_tests_never_copy_manifest_hashes passes |
| 03-06 | No rename of masked_fields, no --json key change, SpliceResult.masked stays per (patch, field) | test | VERIFIED: JSON_KEYS tests + the `entries` assertion in test_mask_count_counts_distinct_fields |
| 03-06 | No quoted `$in` | test | VERIFIED: the exact parse_le rule line is pinned (test_configure.py:19 and :120) |
| 03-05 | No fact pinned unless a spike confirms it | judgment | RESOLVED by the owner (UAT test 1 pass) |
| 03-06 | WR-01/03/04, IN-01..08 behaviour unchanged | judgment | FLAGGED: non-authoritative verdict HOLDS; human review recommended |
| 03-06 | No edit to orig/, config, Docker; configure.py not edited during the gate | judgment | FLAGGED: non-authoritative verdict HOLDS; human review recommended |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tools/reverseapoc/splice.py` | region map, assembly, splice, rebuild, distinct masked count | VERIFIED | verify.artifacts passes for 03-01/03/04/06; contains `m.fixup for m in result.masked` |
| `tools/reverseapoc/le.py`, `tools/reverseapoc/cli.py` | helpers, rebuild verb with --json/--exe | VERIFIED | Unchanged by 03-06 |
| `configure.py` | rule rebuild + phony verify; ConfigureError; --orig in check_orig/rebuild | VERIFIED | Contains `class ConfigureError`, `build verify: phony` |
| `tests/test_configure.py`, `tests/test_splice.py`, `tests/test_splice_real.py`, `tests/test_cli.py`, `tests/test_le.py`, `tests/test_hygiene.py`, `tests/conftest.py` | plan-named tests | VERIFIED | verify.artifacts 24/24 across the six plans |
| `docs/toolchain.md`, `docs/learnings.md` | confirmed LE layout; "ninja quotes $in" entry | VERIFIED | learnings.md:14 entry present, test_hygiene passes |
| `03-05-SUMMARY.md`, `03-06-SUMMARY.md` | "## Phase gate output" | VERIFIED | Both sections present; 03-06 section matches the logs line for line |

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| cli.py | splice.py | `rebuild(...)`, `to_json()` / `format()` | WIRED (verify.key-links) |
| splice.py | le.py | `check_loadable(`, `fixups()` | WIRED |
| splice.py | targets.py | `hash_file(out_path)` vs `Target.sha1` | WIRED |
| configure.py | cli.py | `uv run reverseapoc rebuild --orig {orig}` / `check-orig --orig {orig}` | WIRED (ran through ninja 1.11.1 in the container, real and fake --orig) |
| configure.py main() | render() | `render(exes, orig=_relative(args.orig, base))` (configure.py:136) | WIRED (manual; the tool cannot parse a function-name `from`) |
| splice.py rebuild_target | RebuildResult.masked_fields / to_json | `masked_fields=masked` (splice.py:637, :639) | WIRED (manual, same tool limitation) |
| test_splice_real.py, test_hygiene.py | config/targets.toml | `load_manifest()` | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|---|---|---|---|---|
| RebuildResult OK line | sha1 | `hash_file(out_path)` on the written file | yes | FLOWING |
| masked_fields (text + JSON) | distinct fixup count | `splice().masked`, fixups from `le.fixups()` | yes (mutant shows the value changes the output) | FLOWING |
| build.ninja check_orig/rebuild commands | orig dir | `--orig` argv, then `_relative`, then `_check_orig_dir`, then the HEADER template | yes (fake-orig run reaches the CLI) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Host suite + ruff | `uv run pytest -q -rs && uv run ruff check .` | 349 passed, 5 skipped (none real-file); ruff clean | PASS |
| Fresh rebuild | `rm build/*.EXE; uv run reverseapoc rebuild` | 3 OK lines, exit 0 | PASS |
| Byte identity | `cmp` x3, `sha1sum` | silent; equal to manifest | PASS |
| Container test service | `docker compose run --rm test` | 354 passed, exit 0 | PASS |
| ninja verify via alt --orig (gate step 7) | container, symlinked /tmp/alt-orig | `--orig ../tmp/alt-orig` in both commands, 3 OK, exit 0 | PASS |
| ninja verify via fake --orig (falsification) | container, /tmp/fake-orig with a marker file | verify exit 1 (REFUSED/MISSING), check-orig exit 1 (`checking ../tmp/fake-orig`, MISMATCH) | PASS (gate fails as it should) |
| configure --orig smoke | `configure.py --orig build/verify-smoke/elsewhere` | both rules `--orig elsewhere` | PASS |
| configure unsafe-dir refusal | `configure.py --orig ".../my orig"` | exit 1, `configure.py: error:`, sentinel kept, no new file | PASS |
| WR-02 named test | `pytest tests/test_splice.py -k distinct_fields` | 5 passed | PASS |
| WR-02 mutant (in-process) | rebuild_target counts `len(result.masked)` | 4 failed, 1 passed (two-fields control) | PASS (test can fail) |
| WR-05 / WR-06 mutants (in-process) | render ignores orig / refusals disabled | 15 failures each | PASS (tests can fail) |
| Skip without orig/ | `REVERSEAPOC_ORIG=<empty>` | 33 skipped, 0 failed | PASS |
| WR-07 repro | `find_executables` patched to a surrogate name, sentinel output in build/ | `UnicodeEncodeError`, output emptied | Confirms the review finding (see Anti-Patterns) |

### Probe Execution

No `scripts/*/tests/probe-*.sh` exists and no plan declares one. Step 7c does not apply.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| RT-01 | 03-01, 03-05 | Rebuilt from decomposed parts, not a copy | SATISFIED | SC1 |
| RT-02 | 03-03, 03-05, 03-06 | Linear-address splice API, refusals, straddlers in flat space | SATISFIED | SC3; 03-06 truth 5 (masked-field report) |
| RT-03 | 03-01, 03-02, 03-04, 03-05, 03-06 | CLI verb rebuilds the three EXEs, SHA-1 vs manifest, silent cmp | SATISFIED | SC1/SC2; `ninja verify` with default and non-default --orig |
| RT-04 | 03-03, 03-05 | Negative tests prove the gate can fail and name the offset | SATISFIED | SC3; fake-orig ninja run also fails the gate end to end |
| RT-05 | 03-01, 03-04, 03-05 | Region map tiles every byte; edge cases confirmed and documented | SATISFIED | SC4/SC5 |

No orphaned requirements: REQUIREMENTS.md maps exactly RT-01..RT-05 to Phase 3, and every one is
claimed by a plan. The REQUIREMENTS.md checkboxes (lines 27-31) and traceability rows (121-125)
still read Pending; updating them is the orchestrator's job.

### Anti-Patterns Found

No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER marker in configure.py, splice.py, test_configure.py,
test_splice.py or docs/learnings.md. No stubs.

| File | Line | Pattern | Severity | Impact on must-haves |
|---|---|---|---|---|
| configure.py | 134-140 | WR-07: a non-UTF-8 (surrogate) exe name passes `render()` and fails in `write_text` after truncation, leaving an empty build.ninja and a traceback. Reproduced by the verifier | Warning | Does not break the WR-06 truth as written (it names `\|`, LF, CR and the --orig allowlist). It is a hole in the same "refuse, don't write a broken build.ninja" contract. It cannot occur with the three ASCII-named targets. Owner triage |
| configure.py | 65, 79-86 | IN-09: `--orig` allowlist accepts a leading `-` (argparse reads it as an option) | Info | Truth 3 is a character-set statement and holds. Default and normal layouts are unaffected |
| configure.py | 25, 37 | IN-10: descriptions/comments still say `orig/` | Info | Cosmetic. The commands are correct, as the fake-orig run shows (`[0/1] CHECK-ORIG orig/` label, `checking ../tmp/fake-orig` body) |
| configure.py | 33, 45-48 | IN-11: `--output` does not reach rebuild's out dir | Info | Not in any must-have. Phony outputs are never written |
| tools/reverseapoc/splice.py | 527, 531 | MISSING/REFUSED lines hard-code `orig/<NAME>` even with a non-default `--orig` (seen in the fake-orig run: "REFUSED UFO2P.EXE orig/UFO2P.EXE does not match ...") | Info | Pre-existing label. Not raised by the review. Same family as IN-10. Status and exit code are correct |
| tools/reverseapoc/splice.py | 147-162, 245-264 | WR-01 (owner-deferred to Phase 5): shared logical pages accepted; patch into the second owner dropped | Warning (deferred) | Unreachable on the three real targets. Recorded as coincidental reliance |
| tools/reverseapoc/splice.py | 580-633 | WR-03 (owner-deferred to Phase 5): path-based orig guard, non-atomic write | Warning (deferred) | Backstop truth accepted by the owner (UAT test 2) |
| tools/reverseapoc/cli.py | 52-58 | WR-04 (owner-deferred to Phase 6): `--json` empty on LEError | Warning (deferred) | No real target hits the path |

**Does WR-07 or any open item undermine a must-have or a ROADMAP SC?** No. WR-07 is the closest.
The 03-06 objective says build.ninja should not be "corrupted by a file name", and WR-07 is a file
name that empties it. But the must-have truth enumerates the refused inputs (`|`, LF, CR, and the
--orig allowlist), and every one of those is refused before any write, as both the tests and the
CLI smoke show. The round trip, the ninja `verify` edge and the gate all run on the three manifest
targets, whose names are ASCII. Whether WR-07 is fixed now or deferred is an owner decision, so it
is listed under Human Verification and not as a gap.

### Human Verification Required

#### 1. Judgment-tier prohibition (03-06): nothing outside WR-02/05/06 changed

**Test:** Read `git diff 9158a03 HEAD -- tools/reverseapoc/splice.py tools/reverseapoc/cli.py configure.py`.
**Expected:** splice.py changes only the masked-count line and two comments. cli.py is unchanged. In configure.py, the HEADER comments and descriptions are unchanged apart from the two `--orig {orig}` command lines.
**Why human:** `verification: judgment`. Non-authoritative verifier verdict: HOLDS.

#### 2. Judgment-tier prohibition (03-06): no protected edits, configure.py frozen during the gate

**Test:** Confirm that no commit after 918b4f9 touches configure.py, that config/ and the Docker files are unchanged since 9158a03, and that the gate logs (20:06 local) postdate the last configure.py commit (20:01 local).
**Expected:** All hold. The verifier checked each one, and orig/ SHA-1s equal the manifest.
**Why human:** `verification: judgment`. Non-authoritative verifier verdict: HOLDS.

#### 3. Owner triage of the open review findings

**Test:** Set WR-07, IN-09, IN-10 and IN-11 (and IN-01..IN-08, still `open`) in 03-REVIEW-DISPOSITION.md to fixed, deferred (with reason) or skipped.
**Expected:** Verifier judgment: none breaks a Phase 3 must-have or SC. WR-07 and IN-09 sit next to the WR-06 contract, so they are natural candidates to fold into the Phase 5 configure.py work, along with the hard-coded `orig/` labels (IN-10 and splice.py:527/531).
**Why human:** Disposition is an owner decision; the review is advisory.

### Gaps Summary

No gaps. Gap G-03-3 is closed in the code, not just in the SUMMARY:

- `--orig` reaches check-orig and verify. Real ninja proves it in the container: with an alternate directory the gate passes, and with a fake one it fails.
- configure.py refuses `|`/LF/CR names and unsafe --orig paths before writing anything.
- `masked_fields` counts distinct fields, and the per-entry detail and the 8-key JSON contract are unchanged.
- Mutants confirm that each new guard's tests can fail.

The phase goal still holds on the current tree:

- The three EXEs are rebuilt from decomposed parts, byte-identical on the host and in the container.
- `ninja verify` passes.
- The gate fails on one-byte changes and on a wrong input.

Status is `human_needed`, not `passed`, because of two judgment-tier prohibitions from 03-06 (both
with a non-authoritative verdict of HOLDS) and the owner triage of the new open review findings
(WR-07, IN-09..IN-11).

---

_Verified: 2026-10-20T23:17:11Z_
_Verifier: Claude (gsd-verifier)_
