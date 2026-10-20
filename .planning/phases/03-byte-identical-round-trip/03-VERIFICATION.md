---
phase: 03-byte-identical-round-trip
verified: 2026-10-20T22:30:00Z
status: human_needed
score: 54/55 must-haves verified
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
  - configure.py
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
covered_digest: "v3:sha256:8f0e978dfc664acdd6cb9faf991a2539d7ab27be2b438add9d5211ed30091288"
behavior_unverified: 0
overrides_applied: 0
coincidental_reliance_items:
  - truth: "splice(le, {va: bytes}) applies linear-address patches in flat address space (D-01) and the rebuild gate reports any patched byte as a mismatch"
    reason: undeclared-precondition
    harden: "Objects must own disjoint logical pages and disjoint VA ranges. Nothing in layout()/splice() enforces it (03-REVIEW WR-01): with two objects sharing a logical page, a patch into the second owner is written to an image reassemble() never reads, splice() returns the input unchanged and rebuild reports OK. The three real targets satisfy the precondition (spikes 001/002, identity page map pinned by test_measured_facts). Declare it by refusing shared logical pages and overlapping object ranges in layout() before Phase 5 lands patches through splice()."
human_verification:
  - test: "Judgment-tier prohibition (03-05): confirm no pinned real-file fact in tests/test_splice_real.py FACTS was chosen to match the code rather than the spike READMEs"
    expected: "Every FACTS value (pages, extender end, data-pages start, padding, obj1 tail past vsize, trailer offset/length, straddler VAs, cut fields, fixup-kind counts) appears in .planning/spikes/001, 002 or 003 README.md with the same value"
    why_human: "Prohibition is verification: judgment. Non-authoritative verifier verdict: HOLDS. Spike 001/002 verdicts are VALIDATED, 003 PARTIAL with facts confirmed; a grep of the spike READMEs finds 0x13E27C, 0x2B6538, 0x32FF6, 0x523, 0xAB1, 0xC80, 362/403/223, 28,183/24,424/2,297 and the trailer offset. unverified-prohibition - human review recommended."
  - test: "Backstop truth (03-01): two `reverseapoc rebuild` processes writing the same build/<NAME> at once can only show MISMATCH, never a false OK"
    expected: "Owner accepts the single-user-CLI argument: each run hashes the file it just wrote (hash_file(out_path)), so OK requires the full manifest bytes on disk at hash time; or asks for an atomic write (03-REVIEW WR-03)"
    why_human: "Truth is tagged verification: backstop (insufficient_spec). No held-out or property test exercises concurrent writers; presence plus wiring does not qualify. Note: write_bytes is in place and not atomic (WR-03), so a reader of build/<NAME> during a run can see a truncated file."
  - test: "Owner triage of the six open code-review warnings (03-REVIEW-DISPOSITION.md, all `open`)"
    expected: "Each of WR-01..WR-06 is set to fixed, deferred (with reason) or skipped. Verifier judgment: none breaks a Phase 3 must-have or ROADMAP success criterion on the three real targets; WR-01 and WR-03 should be closed before Phase 5 feeds real patches through splice()"
    why_human: "Disposition is an owner decision; the review is advisory."
---

# Phase 3: Byte-identical round trip Verification Report

**Phase Goal:** UFO2P.EXE and TACP.EXE (plus SMKP.EXE, as a second layout without a trailer) are rebuilt from decomposed parts through a KKND-style in-place page splice and proven SHA-1 identical to the originals, by a gate that demonstrably fails on any one-byte change.
**Verified:** 2026-10-20T22:30:00Z
**Status:** human_needed
**Re-verification:** No (initial verification)

Every check below was run by the verifier in its own process on the main checkout. orig/ was only
read, and outputs went to build/ only. No source file was edited. SUMMARY claims were used as leads,
not as evidence.

## Goal Achievement

### ROADMAP success criteria

| # | Success criterion | Status | Evidence (verifier-run) |
|---|---|---|---|
| SC1 | `rebuild` writes build/UFO2P.EXE, TACP.EXE, SMKP.EXE; `cmp` silent; SHA-1 == `config/targets.toml`; reassembled from prefix regions + re-paged object images, not copied (RT-01, RT-03) | VERIFIED | Deleted build/*.EXE, ran `uv run reverseapoc rebuild`: three `OK ... == manifest` lines, exit 0. `cmp` exit 0 for all three. `sha1sum` of orig/ and build/ equal to the manifest sha1 lines 19/29/38. Code: `reassemble()` -> `assemble(len, _pieces)` starts from `bytearray(size)` and takes no original buffer (splice.py:214-269). Pages come from `decompose()` images placed at `LEPage.file_offset`. In-process copy-only mutant (reassemble returns `le.data`): 30 tests fail, real-file control and straddler tests included |
| SC2 | Round-trip pytest for both EXEs, skipped without orig/, passes on host and in `docker compose run --rm test` (RT-03) | VERIFIED | Host: `uv run pytest -q -rs` gives 324 passed, 3 skipped (container-only hygiene). No real-file skip. Container (re-run by verifier): `docker compose -f docker/compose.yaml run --rm test` gives 327 passed, exit 0. With `REVERSEAPOC_ORIG` pointed at an empty dir: tests/test_splice_real.py + tests/test_le_real.py give 33 skipped, 0 failed |
| SC3 | Negative tests: one-byte mutation mid-page, page edge, short last page, across a boundary each change the SHA-1 and the failure names the offset; splice refuses writes outside page data and length change; straddling fields handled in flat space (RT-02, RT-04) | VERIFIED | Synthetic: test_mutation_page_edges, test_mutation_spanning_permuted_map, test_short_page_last_byte_ok, test_refuse_*, test_mask_* all pass. Real files, verifier spot-check via `rebuild_target(..., patches=)`: mid-page, last byte of a page, first byte of the next, 4 bytes across a boundary, and the last backed byte of the short last page each gave `mismatch`, the exact first_diff/VA, a region label and the right diff_bytes (1 or 4) on UFO2P, TACP and SMKP. Unpatched control gave `ok`. Byte flips injected in the trailer, LE header and padding gave `mismatch` labelled `trailer` / `LE header` / `padding`. A one-byte change in the input gave `REFUSED` |
| SC4 | Byte-region map tiles every byte; coverage test fails on an unassigned or double-assigned byte (RT-05) | VERIFIED | `layout()` + `check_tiling()` (splice.py:165-199). test_check_tiling_rejects_gap / _overlap / accepts_touching and test_assemble_rejects_gap_and_overlap pass. test_layout_tiles_real_file passes for all three EXEs. `decompose()` calls `check_tiling` on every rebuild |
| SC5 | docs/toolchain.md records confirmed edge cases (page types, 14/11 straddlers, 27-byte trailer) as offsets, lengths, hashes only; EOF and "To be confirmed in Phase 2/3" lines removed (RT-05) | VERIFIED | grep finds neither old line. The LE layout section has the SMKP column, identity page map, 14/11/2 straddlers, cut fields, 0x1A0723/0x303DDF trailers (offset, length, first 4 bytes, SHA-1 per D-12), byte-region map table and the spike 003 verdict. test_toolchain_records_the_confirmed_le_layout passes |

### Plan must-have truths (50, merged under the SCs above)

| Plan | Truths | Status | Notes |
|---|---|---|---|
| 03-01 | 17 | 16 VERIFIED, 1 insufficient_spec | Rebuild verb, D-08 OK line, fresh-buffer assembly, full-page images (tail past vsize carried), header-derived tiling, adjacency/ordering/empty/purity edges, D-19 and loader-section refusals, out-inside-orig / non-bare-name / MISSING / REFUSED guards, mutant-proven tests, REVERSEAPOC_ORIG override. Idempotent rebuild: test_rebuild_is_idempotent passes. The concurrent-writer truth is a `backstop` and goes to human verification |
| 03-02 | 4 | 4 VERIFIED | configure.py has `rule rebuild` (console pool) and `build verify: phony $builddir/always/verify`. Header lists `ninja verify`. The hash guard and its planted-hash self-test pass. `ninja verify` re-run in the container by the verifier: 3 OK lines, exit 0 |
| 03-03 | 14 | 14 VERIFIED | splice(): linear-address patches, D-18 refusals (BSS / past end / no object / cross-object), D-04 overlap also for identical bytes, D-02 masking (straddling, ptr16:32, sel16, rel32, clipped), MaskedField flags, D-08 mismatch fields, no input mutation, order independence. In-process no-mask mutant: 17 tests fail, including all six real-file masking params |
| 03-04 | 7 | 7 VERIFIED | `--json` (8 keys), `--exe` case-insensitive with known-name error, CLI mismatch line + JSON first_diff, defaults, parse-le trailer row/JSON, truncated-file clamp, no trailer bytes in output |
| 03-05 | 8 | 8 VERIFIED | test_splice_real.py parametrized over load_manifest() with a per-target skip. Control mutation, straddler and cut-field sweeps, and FACTS all match the spike READMEs. Docs updated. Gate logs build/gate/01..06 each end `exit=0` and are reproduced in 03-05-SUMMARY.md. The verifier independently re-ran the host suite, rebuild, cmp, the container test service and `ninja verify` |

**Score:** 54/55 truths verified (0 present-but-behavior-unverified; 1 `backstop` truth routed to
human verification as insufficient_spec). The behavior-dependent truths (purity, no input mutation,
order independence, idempotence, refusal-before-write) each have a passing named test in the suite run.

### Prohibitions

| Plan | Prohibition | Tier | Disposition |
|---|---|---|---|
| 03-01/03-04 | No write under orig/ | test | VERIFIED: `_refuse_inside_orig` in `rebuild()` and `rebuild_target()`, test_rebuild_refuses_out_inside_orig, Docker `../orig:/work/orig:ro`. orig/ SHA-1s still equal the manifest after all verifier runs |
| 03-01/03-03 | No copy-then-overwrite of the original buffer | test | VERIFIED, with a caveat. The code holds by construction (`assemble()` has no access to the original). The pure-copy mutant is caught by 30 tests, and the "splice bypasses reassemble" mutant by test_splice_output_is_reassembled. A `reassemble()` rewritten as copy-then-overwrite-pages passes the whole suite: it is output-equivalent, because non-page regions come from the original in either form. Only code structure enforces this, not a test (see Anti-Patterns) |
| 03-01/03-05 | Trailer never regenerated | test | VERIFIED: trailer region is a `le.data` slice in `_pieces()`. Real-file SHA-1 match covers it |
| 03-01/03-03/03-04/03-05 | No game bytes in messages, reports, JSON, docs | test | VERIFIED: test_mutation_report_names_offset_without_bytes, test_mask_report_has_no_bytes, test_parse_le_reports_trailer_without_bytes. Docs give the trailer as offset, length, first 4 bytes and SHA-1 only (D-12) |
| 03-02/03-05 | No edit to config/targets.toml, no copied hashes | test | VERIFIED: `git log -- config/targets.toml` shows the last change in Phase 2 (8418027). test_round_trip_tests_never_copy_manifest_hashes passes |
| 03-05 | No fact pinned unless a spike confirms it | judgment | FLAGGED: the non-authoritative verdict is that it holds, but this is an unverified prohibition, so human review is recommended (see Human Verification) |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tools/reverseapoc/splice.py` | region map, assembly, splice, rebuild | VERIFIED | 671 lines. Imported by cli.py and used by `_cmd_rebuild` |
| `tools/reverseapoc/le.py` | check_loadable, pages_end, D-19 constants, trailer summary | VERIFIED | Read helpers only (D-05). `load_flat` calls the public check_loadable |
| `tools/reverseapoc/cli.py` | `rebuild` with --orig/--manifest/--out/--exe/--json | VERIFIED | `_cmd_rebuild` -> `rebuild(...)` -> `format()` / `to_json()` |
| `configure.py` | rule rebuild + phony verify | VERIFIED | Verified by running `ninja verify` in the container |
| `tests/conftest.py` | fixture options, SYNTHETIC_TRAILER, REVERSEAPOC_ORIG | VERIFIED | |
| `tests/test_splice.py`, `tests/test_splice_real.py`, `tests/test_cli.py`, `tests/test_le.py`, `tests/test_hygiene.py`, `tests/test_configure.py` | all plan-named tests | VERIFIED | All 87 plan-named test functions were found in `pytest --collect-only` |
| `docs/toolchain.md` | confirmed LE layout | VERIFIED | |

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| cli.py | splice.py | `rebuild(args.orig, args.out, args.manifest, exe=args.exe)`, then `to_json()` / `format()` | WIRED |
| splice.py | le.py | `le.check_loadable(obj, page)` in `_page_regions`. `le.fixups()` read once per splice | WIRED |
| splice.py | targets.py | `check_target` on the input, `hash_file(out_path)` on the written file, compared with `Target.sha1` from `load_manifest` | WIRED |
| configure.py | cli | `command = uv run reverseapoc rebuild` | WIRED (ran in the container) |
| test_splice_real.py | config/targets.toml | `TARGETS = load_manifest()` | WIRED |
| test_hygiene.py | config/targets.toml | `_manifest_hash_needles()` from `load_manifest()` | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|---|---|---|---|---|
| RebuildResult OK line | sha1 | `hash_file(out_path)` on the written file, not on the in-memory buffer | yes | FLOWING |
| Page bytes in output | page regions | `decompose()` images, then `_pieces()`, then `assemble()` | yes (copy-only mutant breaks 30 tests) | FLOWING |
| parse-le trailer | offset/length/sha1 | `LE._trailer()` from `pages_end` and `data` | yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full suite + ruff, host | `uv run pytest -q -rs && uv run ruff check .` | 324 passed, 3 container-only skips; ruff clean | PASS |
| Fresh rebuild | `rm build/*.EXE; uv run reverseapoc rebuild` | 3 OK lines, exit 0 | PASS |
| Byte identity | `cmp build/N orig/N` (x3), `sha1sum` | silent, hashes equal the manifest | PASS |
| Container test service | `docker compose -f docker/compose.yaml run --rm test` | 327 passed, exit 0 | PASS |
| Container real-file tests + ninja verify | `pytest tests/test_splice_real.py tests/test_le_real.py`; `configure.py --output build/verify-check.ninja && ninja -f ... verify`; cmp | 33 passed; 3 OK lines; ninja exit 0; cmp silent | PASS |
| Skip without orig/ | `REVERSEAPOC_ORIG=<empty dir> pytest tests/test_*_real.py` | 33 skipped, 0 failed | PASS |
| Real one-byte mutations (mid, page edges, across a boundary, short last page) x 3 EXEs | scratch script, `rebuild_target(..., patches=)` into build/verify-scratch (since removed) | every case `mismatch`, exact offset/VA/region, diff_bytes 1 (or 4); unpatched `ok` | PASS |
| Output flip in trailer / header / padding | monkeypatched reassemble | `mismatch` labelled with the right region | PASS |
| Tampered input | one byte flipped in a copy under build/ | `REFUSED`, ok=False | PASS |
| Copy-only mutant (in-process, source untouched) | `reassemble = lambda le, d: bytes(le.data)` | 30 failures | PASS (gate can fail) |
| No-mask mutant (in-process) | `_masked_fields` yields nothing | 17 failures | PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` exists and no plan declares one. Step 7c does not apply.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| RT-01 | 03-01, 03-05 | Rebuilt from decomposed parts, not a copy | SATISFIED | SC1. Fresh-buffer `assemble()`, copy-only mutant caught |
| RT-02 | 03-03, 03-05 | Linear-address splice API with refusals; straddlers in flat space | SATISFIED | SC3, 03-03 truths. Patches go into copies of the page data (object images), the original buffer is never mutated (D-16 refines "into a copy of the original") |
| RT-03 | 03-01, 03-02, 03-04, 03-05 | CLI verb rebuilds the three EXEs into build/, SHA-1 vs manifest, silent cmp | SATISFIED | SC1/SC2, `ninja verify` in the container |
| RT-04 | 03-03, 03-05 | Negative tests prove the gate can fail and name the offset | SATISFIED | SC3, verifier real-file spot-checks |
| RT-05 | 03-01, 03-04, 03-05 | Region map tiles every byte; edge cases confirmed and documented | SATISFIED | SC4/SC5, test_measured_facts |

No orphaned requirements: REQUIREMENTS.md maps exactly RT-01..RT-05 to Phase 3, and every one is
claimed by a plan. The checkboxes in REQUIREMENTS.md (lines 27-31, 121-125) still read Pending;
updating the traceability belongs to the orchestrator.

### Anti-Patterns Found

No TBD/FIXME/XXX/TODO/HACK markers in any file modified by the phase. No stubs.

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| tools/reverseapoc/splice.py | 147-162, 245-264 | WR-01: objects sharing a logical page are accepted; a patch into the second owner is silently dropped and the rebuild reports OK | Warning | Unreachable on the three real targets (disjoint objects, identity map). It is a false-pass path for Phase 5 on malformed input. Recorded as coincidental reliance |
| tools/reverseapoc/splice.py | 483-487, 634 | WR-02: `masked_fields` counts (patch, field) pairs | Warning | Only touching patches that split one field over-count. No must-have depends on the exact count in that case |
| tools/reverseapoc/splice.py | 580-582, 621-633 | WR-03: orig guard is path-based (a hardlink defeats it), write not atomic, input read twice | Warning | The must-have ("refuses an --out that resolves into --orig") holds as written. A hardlinked build/<NAME> would be written through on the host (the container mounts orig/ read-only). The TOCTOU case yields a mismatch, never a false OK |
| tools/reverseapoc/cli.py | 52-58 | WR-04: `--json` prints nothing when a target raises | Warning | MISSING/REFUSED statuses do appear in the JSON. Only LEError paths lose it. No real target hits that path |
| configure.py | 32-82 | WR-05: `configure.py --orig` does not reach `verify` | Warning | The `verify` edge is exactly what D-09 specifies. Inconsistent only with a non-default `--orig` |
| configure.py | 37-40, 78 | WR-06: `$in` unquoted (predates Phase 3) | Warning | Out of phase scope |
| tools/reverseapoc/splice.py | 214-269 | Copy-then-overwrite inside `reassemble()` is output-equivalent and passes the suite | Info | Only the code structure (`assemble()` signature) enforces D-16 item 1. Tests enforce the pure-copy and splice-bypass forms |
| tests/test_splice_real.py | 312 | `assert not any(le.data[start : start + length])` | Info | On failure, pytest's assertion rewriting would show the padding slice in the failure message. That is file bytes in test output (Pitfall I). The test passes today. A generator form, like line 315, avoids it |
| docs/toolchain.md | 136 | IN-04: container orig/ row lists only UFO2P/TACP | Info | `ninja verify` needs SMKP.EXE too |

**Do any review warnings undermine a must-have or ROADMAP SC?** No. Each warning was checked
against the truth text. WR-01 and WR-03 are the closest. WR-01 is a false-pass path for splice()
on LE layouts the real targets do not have. WR-03 is a write-through risk via a hardlink the user
would have to create. Neither path is taken by the round trip of UFO2P/TACP/SMKP. Both should be
closed before Phase 5 lands real patches, and the owner should set their disposition.

### Human Verification Required

#### 1. Judgment-tier prohibition: facts pinned only from spikes

**Test:** Compare `FACTS` in tests/test_splice_real.py with .planning/spikes/001, 002 and 003 README.md.
**Expected:** Every value is stated by a spike README. None was adjusted to match the code.
**Why human:** This prohibition has `verification: judgment`. The verifier's non-authoritative check
found every value in the READMEs (spikes 001/002 VALIDATED, 003 PARTIAL, facts confirmed).

#### 2. Backstop truth: concurrent rebuilds never false-OK

**Test:** Decide whether the single-user-CLI argument is acceptable, or require an atomic write.
**Expected:** OK is reported only when the file on disk hashes to the manifest at hash time.
**Why human:** The truth is tagged `backstop`. No test exercises concurrent writers.

#### 3. Code-review warning disposition

**Test:** Set WR-01..WR-06 in 03-REVIEW-DISPOSITION.md to fixed, deferred or skipped.
**Expected:** WR-01 and WR-03 are scheduled before Phase 5 feeds patches through splice().
**Why human:** Owner decision. The review is advisory.

### Gaps Summary

No gaps. The phase goal is achieved and was verified independently:

- All three EXEs are rebuilt from a header-derived region map and page-mapped object images into a
  fresh buffer.
- The rebuilt files are byte-identical (cmp, SHA-1 against the manifest) on the host and in the
  container, and through `ninja verify`.
- The gate fails, with the exact offset, VA and region, on one-byte changes in pages, at page edges,
  across a page boundary, in the short last page, and in non-page regions. It refuses a tampered input.
- Copy-only and no-mask mutants break the suite.

Status is `human_needed`, not `passed`, because of three items: one judgment-tier prohibition, one
backstop truth, and the owner's triage of six open advisory review warnings.

---

_Verified: 2026-10-20T22:30:00Z_
_Verifier: Claude (gsd-verifier)_
