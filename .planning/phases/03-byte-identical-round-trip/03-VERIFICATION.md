---
phase: 03-byte-identical-round-trip
verified: 2026-10-21T02:59:43Z
status: human_needed
score: 87/87 must-haves verified
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
  - .planning/phases/03-byte-identical-round-trip/03-07-PLAN.md
  - .planning/phases/03-byte-identical-round-trip/03-07-SUMMARY.md
  - .planning/phases/03-byte-identical-round-trip/03-08-PLAN.md
  - .planning/phases/03-byte-identical-round-trip/03-08-SUMMARY.md
  - .planning/phases/03-byte-identical-round-trip/03-09-PLAN.md
  - .planning/phases/03-byte-identical-round-trip/03-09-SUMMARY.md
  - .planning/phases/03-byte-identical-round-trip/03-10-PLAN.md
  - .planning/phases/03-byte-identical-round-trip/03-10-SUMMARY.md
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
  - tests/test_targets.py
  - tools/reverseapoc/cli.py
  - tools/reverseapoc/le.py
  - tools/reverseapoc/splice.py
  - tools/reverseapoc/targets.py
covered_digest: "v3:sha256:9c8a0e4454dc97c282a82032650fc9338a9da70ee8ffc2f9c0105e6ecaf2d2ed"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 63/63
  gaps_closed:
    - "G-03-6 (UAT test 6): WR-07, IN-01..IN-11 and VN-01 are fixed in Phase 3 (plans 03-07, 03-08, 03-09; gate and disposition in 03-10)"
    - "Previous human item 3 (owner triage of WR-07, IN-01..IN-11): resolved by the owner in UAT test 6 ('Fix now for them all') and closed by 03-07..03-10"
    - "Previous human items 1-2 (03-06 judgment prohibitions): passed by the owner in UAT tests 4 and 5"
  gaps_remaining: []
  regressions:
    - "Behaviour regression on malformed input only (WR-08, reproduced by the verifier): with an LE header whose last_page_size exceeds page_size, splice() of a byte past vsize beyond the page slot raised SpliceError at 0269b2a and raises TypeError at HEAD (03-08 rewrote _unwritable_reason). No must-have truth fails on a well-formed LE; see human_verification item 1"
coincidental_reliance_items:
  - truth: "splice(le, {va: bytes}) applies linear-address patches in flat address space (D-01) and the rebuild gate reports any patched byte as a mismatch"
    reason: undeclared-precondition
    harden: "Objects must own disjoint logical pages and disjoint VA ranges, and every page must hold at most page_size bytes; layout()/splice() enforce neither (03-REVIEW WR-01, deferred to Phase 5; WR-08, open). The three real targets satisfy both (FACTS pins the identity page map and page sizes)."
human_verification:
  - test: "Owner triage of the two open review findings in 03-REVIEW-DISPOSITION.md: WR-08 (warning) and IN-12 (info)"
    expected: "Each set to fixed, deferred (with phase and reason) or skipped. Verifier judgment: neither breaks a Phase 3 must-have or ROADMAP success criterion. WR-08 is real and was introduced by 03-08 (verifier reproduced it at HEAD and confirmed SpliceError at 0269b2a), but it needs a header that violates the LE format (last_page_size > page_size), it only affects the error type of a refusal (nothing is written; the round-trip half yields MISMATCH, never a false OK), and the Phase 3 CLI passes no patches. It belongs naturally with WR-01/WR-03 before Phase 5 feeds real patches through splice(). IN-12 is a hint-text issue next to VN-01"
    why_human: "Disposition is an owner decision; the review is advisory."
  - test: "Judgment-tier prohibition (03-07): orig/, config/targets.toml and the Docker files were not edited, and no test holds game bytes"
    expected: "`git diff --stat 0269b2a HEAD -- config docker compose.yaml` is empty; the new tests use build_le_image, b\"x\" or b\"not the game\" markers only; test_hygiene's manifest-hash guard passes"
    why_human: "verification: judgment. Non-authoritative verifier verdict: HOLDS (all three checks run). unverified-prohibition - human review recommended."
  - test: "Judgment-tier prohibition (03-08): WR-01, WR-03 and WR-04 were not implemented"
    expected: "`git diff 0269b2a HEAD -- tools/reverseapoc/splice.py` adds no shared-page or overlapping-object refusal, leaves the write path (out_path.write_bytes, the path-based orig guard, the double read) as it was apart from source=/common, and tools/reverseapoc/cli.py is unchanged"
    why_human: "verification: judgment. Non-authoritative verifier verdict: HOLDS (diff read line by line; cli.py unchanged since 0269b2a). unverified-prohibition - human review recommended."
  - test: "Judgment-tier prohibition (03-09): real-file tests never print or assert on byte slices of the real files"
    expected: "tests/test_splice_real.py asserts on offsets, VAs, counts, booleans and filecmp only; the new _page_at assert message names the VA only"
    why_human: "verification: judgment. Non-authoritative verifier verdict: HOLDS. unverified-prohibition - human review recommended."
  - test: "Judgment-tier prohibitions (03-10): no source, test, config or Docker edit to make a gate step pass; no game bytes in the gate logs or SUMMARY"
    expected: "No file outside .planning/ changed after edd85b5 (the gate HEAD); the eight build/gate/03-10/ logs are stamped 23:41 local, after the last source merge (51b6f07, 23:40:05) and before the docs(03-10) commit (23:43:20); the logs hold pytest/ruff summaries, command lines, file sizes and manifest SHA-1s only"
    why_human: "verification: judgment. Non-authoritative verifier verdict: HOLDS (all checks run by the verifier). unverified-prohibition - human review recommended."
---

# Phase 3: Byte-identical round trip Verification Report

**Phase Goal:** UFO2P.EXE and TACP.EXE (plus SMKP.EXE, as a second layout without a trailer) are rebuilt from decomposed parts through a KKND-style in-place page splice and proven SHA-1 identical to the originals, by a gate that demonstrably fails on any one-byte change.
**Verified:** 2026-10-21T02:59:43Z
**Status:** human_needed
**Re-verification:** Yes. The previous report (human_needed, 63/63, HEAD 83bc0b3) went stale when gap-closure plans 03-07..03-10 changed configure.py, targets.py, splice.py, their tests, test_splice_real.py and docs/toolchain.md. This report covers the current tree (HEAD 39b835e) and adds the must-haves of 03-07..03-10.

The verifier ran every check below in its own process on the main checkout. orig/ was only read.
Outputs went to build/verify-03/ and build/cfg-verify-03/ (gitignored) and to the session
scratchpad. A temporary git worktree of 0269b2a (used to confirm the WR-08 regression) was
removed afterwards. build.ninja has the same SHA-1 before and after the container runs. No
source file was edited. SUMMARY claims were used as leads, not as evidence.

## Goal Achievement

### ROADMAP success criteria

| # | Success criterion | Status | Evidence (verifier-run, this session) |
|---|---|---|---|
| SC1 | `rebuild` writes build/UFO2P.EXE, TACP.EXE, SMKP.EXE; `cmp` silent; SHA-1 == manifest; reassembled, not copied (RT-01, RT-03) | VERIFIED | Deleted the three build/*.EXE, ran `uv run reverseapoc rebuild`: three `OK ... == manifest` lines, exit 0. `cmp` exit 0 for all three; `sha1sum` of build/ equals orig/ and config/targets.toml lines 19/29/38. `git diff 83bc0b3 HEAD -- tools/reverseapoc/splice.py` leaves decompose/assemble/reassemble untouched (only labels, `_unwritable_reason`, the report fields and the bare-name delegate changed), so the fresh-buffer assembly verified earlier still produces the output |
| SC2 | Round-trip pytest for both EXEs, skipped without orig/, passes on host and in `docker compose run --rm test` (RT-03) | VERIFIED | Host `uv run pytest -q -rs`: 401 passed, 6 skipped (2 Windows-only `\|`/LF, 1 Linux-only non-UTF-8, 3 container-only hygiene); no real-file skip. `docker compose run --rm test`: 407 passed, 0 skipped, exit 0. `tests/test_splice_real.py tests/test_le_real.py`: 33 passed with orig/, 33 skipped with `REVERSEAPOC_ORIG=<empty dir>` |
| SC3 | One-byte mutations change the SHA-1 and name the offset; splice refuses out-of-page writes and length change; straddlers in flat space (RT-02, RT-04) | VERIFIED | D-13 synthetic suite and the real-file control mutation (now located through the independent `le.page_va` index) pass in the runs above. End to end, a container `ninja verify` against a fake orig dir (a 12-byte non-game marker) fails with REFUSED/MISSING and exit 1. WR-08 (malformed header, wrong exception type for a refused write) does not touch this criterion: the write is still refused and the gate still fails rather than passing; see Anti-Patterns |
| SC4 | Region map tiles every byte; coverage test fails on unassigned or double-assigned byte (RT-05) | VERIFIED | `layout()` code unchanged (docstring only, IN-03; the new text matches `_page_regions` and the `end > start` filter). test_check_tiling_rejects_gap/_overlap and test_layout_tiles_real_file pass |
| SC5 | docs/toolchain.md records confirmed edge cases as offsets, lengths, hashes only; EOF and "To be confirmed" lines removed (RT-05) | VERIFIED | `git diff -U0 0269b2a HEAD -- docs/toolchain.md` changes exactly one line (the container orig/ row now lists SMKP.EXE, IN-04). test_toolchain_records_the_confirmed_le_layout passes |

### Plan must-have truths

| Plan | Truths | Status | Notes |
|---|---|---|---|
| 03-01 | 17 | 17 VERIFIED | Regression: suite green, fresh rebuild OK. "Refuses a non-bare target name before writing anything" now holds through `load_manifest` (ManifestError) and the kept `rebuild_target` guard; test_rebuild_refuses_target_name_with_a_path passes. The `backstop` truth was resolved by the owner in UAT test 2 |
| 03-02 | 4 | 4 VERIFIED | `rule rebuild` in the console pool, phony `verify`, header lists `ninja verify`. The command now reads `rebuild --orig orig --out build` (03-06 and 03-07 superseded the bare form on purpose). Hash guard and planted-hash self-test pass |
| 03-03 | 14 | 14 VERIFIED | splice()/masking unchanged. The pinned 03-03 refusal substrings (`BSS of object 2`, `0x11800 is past the end of object 1`, `is not in any object`, `crosses from object 1 into object 2`) and every object-1 label still pass. WR-08 is a malformed-header edge outside these truths (owner triage, human item 1) |
| 03-04 | 7 | 7 VERIFIED | tests/test_cli.py JSON_KEYS unchanged; test_rebuild_json_* pass, including the new refused-JSON control |
| 03-05 | 8 | 8 VERIFIED | FACTS block byte-identical to 0269b2a (`cmp` of the extracted block); real-file round trip, control, straddler and cut-field sweeps pass |
| 03-06 | 8 | 8 VERIFIED | WR-05/WR-06 tests still pass after 03-07 edited HEADER and `_check_orig_dir`; the 03-06 gate logs remain under build/gate/03-06/ |
| 03-07 | 7 | 7 VERIFIED | See next table |
| 03-08 | 7 | 7 VERIFIED | See next table |
| 03-09 | 5 | 5 VERIFIED | See next table |
| 03-10 | 5 | 5 VERIFIED | See next table |

#### 03-07 truths (configure.py half of G-03-6)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | WR-07: a non-UTF-8 exe path gives `configure.py: error:` naming the repr, exit 1, build.ninja byte-identical, no traceback | VERIFIED | configure.py:76-81 (UTF-8 check in `ninja_path`), :152-157 (one except for ConfigureError and UnicodeEncodeError). Named tests pass on the host; the Linux real-name test passes in the container (407 passed, 0 skipped). Mutant (UTF-8 check removed): 2 render tests fail, the main-level test still passes through the encode guard, as the SUMMARY says |
| 2 | WR-07: main() encodes before opening the output | VERIFIED | configure.py:154 encodes inside the try, :158 `write_bytes` after it; no `write_text` left. Source-level mutant (open and write text before encoding): test_main_never_truncates_on_an_encoding_failure fails |
| 3 | IN-09: leading `-` in the orig dir or an exe path refused, nothing written | VERIFIED | `_refuse_option_like` (:85-92) called from `_check_orig_dir` (:102) and `render` (:129). CLI smoke: `--orig build/verify-03/smoke/-h` gives exit 1, the error line, and the sentinel `# sentinel` unchanged. Mutant (helper made identity): 7 tests fail |
| 4 | IN-10: `CHECK-ORIG <orig>` description; no header comment names a fixed `orig/` | VERIFIED | configure.py:37; header lines 25-26 say "the orig dir". CLI smoke output: `description = CHECK-ORIG elsewhere`. Container run: `[0/1] CHECK-ORIG ../../orig` |
| 5 | IN-11: rebuild rule passes `--out build`; `ninja verify` writes into the builddir next to its build.ninja | VERIFIED | configure.py:46. test_generated_rebuild_writes_into_builddir passes. Verifier re-ran the gate-step-8 shape in the container (ninja 1.11.1): build.ninja in build/cfg-verify-03/, command `uv run reverseapoc rebuild --orig ../../orig --out build`, three OK lines, and `cmp` of build/cfg-verify-03/build/<NAME> against orig/ silent for all three. Mutant (drop `--out build`): 15 tests fail |
| 6 | IN-08: no earlier-phase skeleton wording; Phase 5 note, `REBUILD build/`, `builddir = build`, unquoted `parse-le $in` kept | VERIFIED | Lines 4, 24, 29, 33, 41, 47; test_no_stale_phase_wording passes; no quoted `$in`, `--orig=` or `--` separator in configure.py |
| 7 | test_configure.py removes exactly five lines, all rebuild-command pins | VERIFIED | `git diff -U0 0269b2a HEAD -- tests/test_configure.py` removes exactly the five `rebuild` assertions (:80, :115, :118, :146, :214 forms); every other change is an added line |

#### 03-08 truths (tooling half of G-03-6)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | IN-06: invalid TOML, non-UTF-8 bytes, wrong `targets` shape are ManifestError naming the path; CLI prints `reverseapoc <verb>: error:` and exits 1 | VERIFIED | targets.py:121-130. CLI smoke: `rebuild`, `rebuild --json` and `check-orig` with an invalid-TOML manifest each print one error line naming the file, exit 1, no out dir created; `targets = 5` gives the "array of tables" error. In-process mutant (no wrap, no shape check): 6 tests fail |
| 2 | IN-07: non-bare and Windows-reserved names refused on every host; rebuild_target guard kept; real manifest loads | VERIFIED | `check_bare_name` (targets.py:76-91) uses `ntpath.isreserved` and both Pure path classes; `_parse_target` (:97-100); `splice._check_bare_name` delegates (splice.py:612-614). 14-name test passes; real manifest loads (real-file tests run). Mutant (check disabled): 14 tests fail |
| 3 | IN-01: labels count pages within the object; object-1 labels unchanged | VERIFIED | `_page_label` (splice.py:101-108), `Region.describe` (:127-135). Mutant (old global-logical label): 3 tests fail; object-1 label tests pass at HEAD |
| 4 | IN-02: refusal reasons locate the page; 03-03 substrings kept | VERIFIED | `_unwritable_reason` (:333-354); test_unwritable_reason_names_the_page (4 ids) and the 03-03 refusal tests pass. Edge outside the truth: WR-08 (human item 1) |
| 5 | IN-03: layout() docstring corrected, behaviour unchanged | VERIFIED | Docstring (:178-180) read against `_page_regions` (every page yields a region) and the `end > start` filter on fixed spans: they agree. `layout()` body unchanged |
| 6 | VN-01: REFUSED/MISSING name the checked input and the manifest; not in to_json | VERIFIED | `RebuildResult.source`, `RebuildReport.manifest`, `format(width, manifest)` (:539, :562-569, :597, :605, :710); to_json unchanged. Container falsification: `ninja verify` with a fake orig printed `REFUSED   UFO2P.EXE  ../../../tmp/fake/UFO2P.EXE does not match /work/config/targets.toml` and MISSING lines naming `../../../tmp/fake/<NAME>`. Mutant (format ignores source and manifest): 3 tests fail |
| 7 | test files lose no line except imports; real-file suites pass with no skip | VERIFIED | Only removed line across test_targets/test_cli/test_splice is `from reverseapoc.targets import load_manifest` (merged into a wider import). Real-file subset 33 passed |

#### 03-09 truths (real-file helpers and docs)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | IN-05: helpers derive from le.py's reader, not splice.py's arithmetic | VERIFIED | `_page_index` (`le.page_va`), `_page_at` (bisect), `_page_offset`, `_page_backed_end` (object-table page range), `_straddles` (page identity), `_covered` (plain scan) in tests/test_splice_real.py:125-176. No `page_count - 2`, `MAX_FIELD` or `SRC_SIZE` left |
| 2 | FACTS and expected values unchanged; 21 real-file tests, no skip | VERIFIED | FACTS block `cmp`-identical to 0269b2a; real-file run passes with no SKIPPED line |
| 3 | The suite still catches an implementation error, and FACTS pins the helpers (mutants reverted) | VERIFIED | Re-run by the verifier in process (no file edited): `splice._page_backed_end` treating the last page as full fails test_fields_cut_by_page_data_are_clipped for all three EXEs (3 failed); the test helper `_page_backed_end` + 1 fails test_measured_facts x3, test_straddling_fields_are_masked x3 and the SMKP cut-field test (7 failed). Both counts equal the SUMMARY's. `git diff 0269b2a HEAD -- tools/` shows no leftover |
| 4 | Control test expects `page K of object 1`, K within the object | VERIFIED | test_control_mutation_is_reported computes K from `(va - obj.base) // page_size + 1` and passes for all three EXEs |
| 5 | IN-04: toolchain.md ninja row lists the three EXEs; nothing else changed | VERIFIED | One-line diff (see SC5) |

#### 03-10 truths (gate and disposition)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Six 03-05 gate steps exit 0, no real-file skip, three OK lines per rebuild | VERIFIED | build/gate/03-10/01..06 exist, each ends `exit=0`; 03-cmp.log is exactly `exit=0`. The verifier independently reproduced steps 1-4 and the container suite outcome (401/6 host, 407/0 container) |
| 2 | Step 7: alt `--orig` reaches rebuild (with `--out build`) and check-orig; `CHECK-ORIG ../tmp/alt-orig`, `checking ../tmp/alt-orig` | VERIFIED | 07-container-ninja-alt-orig.log holds both command lines, three OK lines, the CHECK-ORIG status line, `checking ../tmp/alt-orig` and `3 ok, 0 mismatched, 0 missing` |
| 3 | Step 8: build.ninja in build/cfg-03-10/ writes build/cfg-03-10/build/<NAME> byte-identical | VERIFIED | 08 log holds `--orig ../../orig --out build` and three OK lines; build/cfg-03-10/build/ holds the three EXEs. Re-run independently in build/cfg-verify-03/ with the same result |
| 4 | Each step logged with `exit=STATUS`; SUMMARY reproduces the eight logs verbatim | VERIFIED | Scripted line check: every line of every 03-10 log appears verbatim in the SUMMARY's "## Phase gate output" section (0 missing); 8 `exit=0`, no non-zero exit |
| 5 | Disposition: WR-07, IN-01..IN-11, VN-01 fixed with plan, commit and build/gate/03-10/; WR-01/03/04 deferred; WR-02/05/06 fixed; `open: 0` | VERIFIED | 13 fixed rows, 3 deferred, 3 earlier-fixed rows (grep counts). The six cited commits are ancestors of HEAD. `open: 0`, `total: 19` at 7c603f0; the re-review then added WR-08 and IN-12 as new open rows (`open: 2`, `total: 21`), which is new scope, not a reopening. The rows the ledger script dropped (IN-08 decision, VN-01) are present again after 39b835e |

**Score:** 87/87 truths verified (5 SCs + 82 plan truths; 0 present-but-behavior-unverified).
The behaviour-dependent truths each have a passing named test in this session's suite run, and
the new guards (UTF-8 refusal, encode before open, option-like refusal, `--out build`, bare
names, manifest wrap and shape, within-object labels, REFUSED/MISSING source and manifest) were
each falsified with an in-process mutant. Source was left untouched.

### Prohibitions

| Plan | Prohibition | Tier | Disposition |
|---|---|---|---|
| 03-01/03-04 | No write under orig/ | test | VERIFIED: orig/ SHA-1s equal the manifest after all runs; container mount read-only |
| 03-01/03-03 | No copy-then-overwrite of the original buffer | test | VERIFIED (assembly code unchanged since the previous verification) |
| 03-01/03-05 | Trailer never regenerated | test | VERIFIED |
| all | No game bytes in messages, reports, JSON, docs, tests, logs | test | VERIFIED: report-level guards pass; new tests use synthetic images and short markers; gate logs hold summaries, sizes and manifest SHA-1s |
| 03-02/03-05/03-06 | No edit to config/targets.toml or the Docker files; no copied hashes | test | VERIFIED: `git diff --stat 0269b2a HEAD -- config docker compose.yaml` empty; manifest-hash guard passes |
| 03-06 | No rename of masked_fields, no --json key change | test | VERIFIED |
| 03-06/03-07 | No quoted `$in`; no `--orig=PATH` or `--` separator | test | VERIFIED: the exact parse_le rule is pinned; grep finds neither form in a rule |
| 03-07 | No edit under tools/ | test | VERIFIED: 231ee0d and bf341b5 touch configure.py only (their test commits touch tests/test_configure.py) |
| 03-08 | No --json key added; new fields out of to_json | test | VERIFIED: JSON_KEYS tests and test_rebuild_result_names_the_input_path's 8-key assertion |
| 03-08 | No object-1 label or 03-03 substring change; le.py and watcom.py untouched | test | VERIFIED: `git diff 0269b2a HEAD -- tools/reverseapoc/le.py tools/reverseapoc/watcom.py tools/reverseapoc/cli.py` empty |
| 03-08 | No manifest hash or game bytes in tests; no orig/config/Docker edit | test | VERIFIED |
| 03-09 | FACTS, expected values and the D-15 rule unchanged | test | VERIFIED (FACTS `cmp`) |
| 03-09 | No edit under tools/, the Watcom docs section, orig/, config, Docker | test | VERIFIED (e3abcc6 and 154a73c touch one file each; toolchain.md diff is one line) |
| 03-10 | WR-01/03/04 and WR-02/05/06 rows unchanged | test | VERIFIED |
| 03-07 | No orig/config/Docker edit; no game bytes in a test | judgment | FLAGGED: non-authoritative verdict HOLDS; human review recommended |
| 03-08 | WR-01, WR-03, WR-04 not implemented | judgment | FLAGGED: non-authoritative verdict HOLDS; human review recommended |
| 03-09 | No byte slices printed or asserted | judgment | FLAGGED: non-authoritative verdict HOLDS; human review recommended |
| 03-10 | No edits to make a gate step pass; no game bytes in logs/SUMMARY | judgment | FLAGGED: non-authoritative verdict HOLDS; human review recommended |
| 03-05, 03-06 | (earlier judgment prohibitions) | judgment | RESOLVED by the owner (UAT tests 1, 4, 5) |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `configure.py` | refusals, encode before open, CHECK-ORIG {orig}, `--out build` | VERIFIED | verify.artifacts passes for 03-02/06/07; contains `--out build`, `class ConfigureError`, `build verify: phony` |
| `tools/reverseapoc/targets.py` | manifest wrap and shape, `check_bare_name` | VERIFIED | contains `isreserved`, `TOMLDecodeError` |
| `tools/reverseapoc/splice.py` | region map, assembly, splice, rebuild, page labels, source/manifest | VERIFIED | contains `(logical page `, `m.fixup for m in result.masked` |
| `tools/reverseapoc/le.py`, `tools/reverseapoc/cli.py` | helpers, rebuild verb | VERIFIED | unchanged since 0269b2a |
| `tests/test_configure.py`, `tests/test_targets.py`, `tests/test_splice.py`, `tests/test_cli.py`, `tests/test_splice_real.py`, `tests/test_hygiene.py`, `tests/conftest.py`, `tests/test_le.py` | plan-named tests | VERIFIED | verify.artifacts 35/35 across the ten plans |
| `docs/toolchain.md`, `docs/learnings.md` | confirmed LE layout, SMKP row, ninja-quoting entry | VERIFIED | |
| `03-05/03-06/03-10-SUMMARY.md` | "## Phase gate output" | VERIFIED | 03-10 section matches its logs line for line |
| `03-REVIEW-DISPOSITION.md` | VN-01 row, 13 fixed | VERIFIED | contains `\| VN-01 \| info \| fixed \|` |

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| cli.py | splice.py | `rebuild(...)`, `to_json()` / `format()` | WIRED (verify.key-links) |
| splice.py | le.py / targets.py | `check_loadable(`, `fixups()`, `hash_file(` | WIRED (verify.key-links) |
| configure.py HEADER rule rebuild | cli.py rebuild `--out` | `rebuild --orig {orig} --out build` (configure.py:46; cli.py:166 accepts `--out`) | WIRED (manual; proven through ninja 1.11.1 from a sub-directory) |
| configure.py main() | render() / ninja_path() | ConfigureError raised in render, caught at :155 before `write_bytes` | WIRED (manual) |
| targets.py load_manifest | cli.py main() except tuple | `raise ManifestError` (targets.py:100, :125, :128, :130) caught at cli.py:183 | WIRED (manual; CLI smoke) |
| splice.py Region.describe | RebuildResult.first_diff_region / to_json | `region.describe(offset)` (:639), `"region": self.first_diff_region` (:578) | WIRED (manual) |
| splice.py rebuild() | RebuildReport.format -> RebuildResult.format | `RebuildReport(out_dir, results, manifest)` (:710), `r.format(width, self.manifest)` (:605) | WIRED (manual; container REFUSED line names /work/config/targets.toml) |
| test_splice_real.py helpers | le.py LE.page_va / LEPage | `le.page_va(` (:129, :159) | WIRED (manual) |
| test_splice_real.py FACTS | .planning/spikes/001-003 | `FACTS = {` (:66), owner-checked in UAT test 1, unchanged since | WIRED |
| build/gate/03-10/*.log | 03-10-SUMMARY.md | verbatim reproduction | WIRED (scripted check, 0 missing lines) |
| 03-07/08/09 Task Commits | disposition Source cells | `fixed in plan 03-0N (<hash>)` | WIRED (16 matches incl. the 03-06 rows; six hashes are ancestors of HEAD) |

The gsd-tools key-link verb cannot parse a `from` that names a function or a log glob, so those
links were checked by hand as listed.

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|---|---|---|---|---|
| RebuildResult OK line | sha1 | `hash_file(out_path)` on the written file | yes | FLOWING |
| REFUSED/MISSING lines | input path, manifest | `check.path` from `check_target(target, orig_dir / name)`; `manifest` from `rebuild()` | yes (container fake-orig run shows the real paths) | FLOWING |
| build.ninja rebuild/check-orig commands | orig dir, out dir | `--orig` argv -> `_relative` -> `_check_orig_dir` -> HEADER; `--out build` literal equal to `builddir` | yes (sub-directory run writes into its own builddir) | FLOWING |
| mismatch region label | page K of object M | `_page_label(obj, page)` from the region map | yes (label mutant changes test outcomes) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Host suite + ruff (run once) | `uv run pytest -q -rs && uv run ruff check .` | 401 passed, 6 skipped (none real-file); ruff clean | PASS |
| Container test service | `docker compose run --rm test` | 407 passed, exit 0 | PASS |
| Fresh rebuild | `rm build/*.EXE; uv run reverseapoc rebuild` | 3 OK lines, exit 0 | PASS |
| Byte identity | `cmp` x3, `sha1sum` | silent; equal to manifest | PASS |
| Real-file subset / skip without orig/ | `pytest tests/test_splice_real.py tests/test_le_real.py`, then with `REVERSEAPOC_ORIG=<empty>` | 33 passed; 33 skipped | PASS |
| IN-11 through ninja 1.11.1 from a sub-directory | container, build/cfg-verify-03/ | `--out build` command, 3 OK, `CHECK-ORIG ../../orig`, 3 ok check-orig, cmp silent | PASS |
| Gate fails on a wrong input (falsification) | container, `--orig /tmp/fake` (non-game marker) | REFUSED/MISSING naming the real paths, ninja exit 1 | PASS (gate fails as it should) |
| configure `-h` orig dir | CLI with a sentinel output | exit 1, error line, sentinel unchanged | PASS |
| configure `--orig elsewhere` | CLI | `rebuild --orig elsewhere --out build`, `CHECK-ORIG elsewhere` | PASS |
| Malformed manifest | `rebuild`, `rebuild --json`, `check-orig` with invalid TOML; `check-orig` with `targets = 5` | one error line each, exit 1, no out dir | PASS |
| Mutants (in-process, not committed) | option-like, UTF-8, `--out build`, bare name, manifest wrap/shape, page label, REFUSED/MISSING source | 7, 2(+1 expected pass), 15, 14, 6, 3, 3 failures | PASS (tests can fail) |
| Mutant (source-level, in memory) | open and write build.ninja before encoding | test_main_never_truncates_on_an_encoding_failure fails | PASS |
| 03-09 mutants (in-process) | splice full last page; test helper page-backed end + 1 | 3 failed; 7 failed (equal to the SUMMARY) | PASS (real-file suite can fail, FACTS pins the helpers) |
| WR-08 reproduction | synthetic LE with last_page_size 0x1400 > page_size; splice at 0x21000/0x21200 | HEAD: TypeError; 0269b2a: SpliceError | Confirms the review finding and that 03-08 introduced it |

### Probe Execution

No `scripts/*/tests/probe-*.sh` exists and no plan declares one. Step 7c does not apply.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| RT-01 | 03-01, 03-05, 03-10 | Rebuilt from decomposed parts, not a copy | SATISFIED | SC1 |
| RT-02 | 03-03, 03-05, 03-06, 03-08 | Linear-address splice API, refusals, straddlers in flat space | SATISFIED | SC3; IN-02 reasons; WR-08 is a malformed-header error-type edge (human item 1) |
| RT-03 | 03-01, 03-02, 03-04..03-10 | CLI verb rebuilds the three EXEs, SHA-1 vs manifest, silent cmp | SATISFIED | SC1/SC2; `ninja verify` default, alt --orig and sub-directory |
| RT-04 | 03-03, 03-05, 03-08 | Negative tests prove the gate can fail and name the offset | SATISFIED | SC3; fake-orig ninja run fails end to end |
| RT-05 | 03-01, 03-04, 03-05, 03-09 | Region map tiles every byte; edge cases confirmed and documented | SATISFIED | SC4/SC5; independent real-file helpers |

No orphaned requirements: REQUIREMENTS.md maps exactly RT-01..RT-05 to Phase 3 and every one is
claimed by at least one plan. The REQUIREMENTS.md checkboxes (lines 27-31) and traceability rows
(121-125) still read Pending; updating them is the orchestrator's job.

### Anti-Patterns Found

No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER marker in any file changed by 03-07..03-10. No stubs.

| File | Line | Pattern | Severity | Impact on must-haves |
|---|---|---|---|---|
| tools/reverseapoc/splice.py | 344-345 | WR-08 (open): `off, page = _page_slot(...)` unpacks None when an LE header declares last_page_size > page_size, raising TypeError instead of SpliceError. The verifier reproduced it at HEAD and confirmed the same input gave SpliceError at 0269b2a, so 03-08's IN-02 rewrite introduced it. The round-trip half (an oversized page that is not its object's last page) predates Phase 3 gap closure and shows as MISMATCH | Warning | No truth fails on a well-formed LE. The header violates the LE format; nothing is written; the gate never reports a false OK; the Phase 3 CLI passes no patches; FACTS pins the real page sizes. It does weaken the 03-03 "refused with SpliceError" contract on input `layout()` accepts, which Phase 5 callers will rely on. Owner triage |
| tools/reverseapoc/splice.py | 564, 566-569 | IN-12 (open): REFUSED/MISSING hints say `run uv run reverseapoc check-orig` / `ingest` without the `--orig`/`--manifest` that produced the line (seen in the container fake-orig run) | Info | The VN-01 truth covers the named path and manifest, which are correct. Hint text only |
| tools/reverseapoc/splice.py | 159-174, 259-278 | WR-01 (deferred to Phase 5) | Warning (deferred) | Recorded as coincidental reliance |
| tools/reverseapoc/splice.py | 617-619, 655-670 | WR-03 (deferred to Phase 5) | Warning (deferred) | Backstop truth accepted by the owner (UAT test 2) |
| tools/reverseapoc/cli.py | 52-58 | WR-04 (deferred to Phase 6) | Warning (deferred) | No real target hits the path |
| .planning/.../03-REVIEW-DISPOSITION.md | - | The ledger helper recognises only CR/BL/WR/IN ids and dropped the IN-08 decision and the VN-01 row on re-run; restored by hand in 39b835e | Info | Record is correct now (13 fixed rows). A future re-run of the helper may drop VN-01 again |
| tests/test_splice_real.py | 129, 159 | `LE.page_va` and `splice._page_regions` share the `base + (logical - page_index) * page_size` formula (review residual note) | Info | FACTS guards it |

**Does WR-08 or IN-12 undermine a must-have or a ROADMAP SC?** No, in the verifier's judgment.
WR-08 is the closer one, and it is a real regression introduced by this gap closure. But the
must-have truths and SC3 concern well-formed LE files and the outcome of a refused write. The
write is still refused, nothing reaches the output, and the SHA-1 gate never passes a wrong
file. The failure needs a header that breaks the LE format (last page larger than the page
size), and the Phase 3 CLI never passes patches. WR-08 does break the spirit of "every refusal is
a SpliceError" on input that `layout()` accepts. Phase 5 will call `splice()` with real patches
and catch SpliceError/LEError, so the finding should be closed before then, as WR-01 and WR-03
are. Fixing it now or deferring it to Phase 5 is an owner decision, so it is listed under Human
Verification rather than as a gap. IN-12 is hint text and touches no truth.

### Human Verification Required

#### 1. Owner triage of WR-08 and IN-12

**Test:** Set WR-08 and IN-12 in 03-REVIEW-DISPOSITION.md to fixed, deferred (with phase and reason) or skipped.
**Expected:** Verifier judgment: neither breaks a Phase 3 must-have or SC. WR-08 was introduced by 03-08 (TypeError at HEAD, SpliceError at 0269b2a on the same synthetic header). It fits with the Phase 5 WR-01/WR-03 work: refuse last_page_size > page_size in `_check_mappable` or the LE constructor, and turn a None `_page_slot` into a SpliceError. IN-12 is a hint-text follow-up to VN-01.
**Why human:** Disposition is an owner decision; the review is advisory.

#### 2. Judgment-tier prohibition (03-07): no protected edits, no game bytes in tests

**Test:** Check `git diff --stat 0269b2a HEAD -- config docker compose.yaml` and the new tests in tests/test_configure.py.
**Expected:** Empty diff; tests use build_le_image and short non-game markers.
**Why human:** `verification: judgment`. Non-authoritative verifier verdict: HOLDS.

#### 3. Judgment-tier prohibition (03-08): WR-01/03/04 not implemented

**Test:** Read `git diff 0269b2a HEAD -- tools/reverseapoc/splice.py tools/reverseapoc/cli.py`.
**Expected:** No shared-page/overlap refusal, write path unchanged apart from `source=`/`common`, cli.py unchanged.
**Why human:** `verification: judgment`. Non-authoritative verifier verdict: HOLDS.

#### 4. Judgment-tier prohibition (03-09): no byte slices in real-file tests

**Test:** Read tests/test_splice_real.py's assertions and assert messages.
**Expected:** Offsets, VAs, counts, booleans and filecmp only.
**Why human:** `verification: judgment`. Non-authoritative verifier verdict: HOLDS.

#### 5. Judgment-tier prohibitions (03-10): gate integrity and no game bytes in logs

**Test:** Confirm no file outside .planning/ changed after edd85b5, the 03-10 logs postdate the last source merge, and the logs hold only summaries, command lines, sizes and manifest SHA-1s.
**Expected:** All hold (logs 23:41 local; last source merge 23:40:05; docs commit 23:43:20).
**Why human:** `verification: judgment`. Non-authoritative verifier verdict: HOLDS.

### Gaps Summary

No gaps. Gap G-03-6 is closed in the code, not just in the SUMMARYs:

- configure.py refuses non-UTF-8 and option-like paths with one error line and never truncates build.ninja (encode before open, proven by a mutant).
- `CHECK-ORIG` names the orig dir, and `ninja verify` writes into the builddir of the build.ninja it runs from. Real ninja 1.11.1 proves this from a sub-directory.
- A malformed manifest or a non-bare/reserved target name is one ManifestError line on every host.
- Labels and refusal reasons count pages within their object, and REFUSED/MISSING name the real input and manifest while the 8-key JSON contract holds.
- The real-file helpers no longer copy splice.py's arithmetic, and FACTS is unchanged.

The phase goal still holds on the current tree:

- The three EXEs are rebuilt from decomposed parts, byte-identical on the host and in the container.
- `ninja verify` passes with the default, an alternate and a sub-directory build.ninja.
- The gate fails on one-byte changes and on a wrong input.

Status is `human_needed`, not `passed`, because of four judgment-tier prohibitions from 03-07..03-10
(each with a non-authoritative verdict of HOLDS) and the owner triage of the two new open review
findings (WR-08, a real but malformed-input-only regression from 03-08, and IN-12).

---

_Verified: 2026-10-21T02:59:43Z_
_Verifier: Claude (gsd-verifier)_
