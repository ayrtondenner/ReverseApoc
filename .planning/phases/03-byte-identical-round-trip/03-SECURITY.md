---
phase: "3"
slug: "byte-identical-round-trip"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-10-20"
---

# Phase 3 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> The register is the union of the `<threat_model>` blocks of plans 03-01..03-05, authored at plan time. The executor SUMMARYs raised no threat flags. ASVS level 1: each mitigation was verified at grep depth against the merged tree on the main checkout, and the cited tests ran green there.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| orig/ game files → tool and tests | the oracle input; real bytes are read, never written | copyrighted game bytes (must not leave as bytes; only offsets, lengths, counts, labels and SHA-1s) |
| manifest (config/targets.toml) → rebuild and tests | expected SHA-1s and target names | hashes; names that must stay bare file names |
| CLI arguments (--orig, --out, --exe, --json) → filesystem | user-supplied paths and names | paths (must not reach orig/), a target name (never a path) |
| splice patches → page images | linear-address patch bytes from Phase 5 callers | bytes written only into writable page data, never over fixup fields |
| spike READMEs → pinned facts and docs | measured facts become regression tests | offsets and counts; a stale fact must not be pinned |
| test runs, gate logs → filesystem and git | outputs of real-file tests and the phase gate | rebuilt EXEs (gitignored build/, tmp_path), logs (gitignored build/gate/) |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-03-01 | Tampering | rebuild_target output path | high | mitigate | bare-name check before any write; `tests/test_cli.py::test_rebuild_refuses_target_name_with_a_path` | closed |
| T-03-02 | Tampering | rebuild --out versus orig/ | high | mitigate | out-under-orig refusal; `tests/test_cli.py::test_rebuild_refuses_out_inside_orig`; `docker/compose.yaml` mounts `../orig:/work/orig:ro` | closed |
| T-03-03 | Denial of service | layout()/decompose() on a malformed LE | medium | mitigate | `check_loadable` and `LEUnsupportedError` refusals and `check_tiling` in `tools/reverseapoc/splice.py` | closed |
| T-03-04 | Information disclosure | error messages and report lines | medium | mitigate | no-bytes report tests in `tests/test_splice.py` (`*_without_bytes`, `*_no_bytes`) | closed |
| T-03-05 | Repudiation | reassembly (the oracle's input) | high | mitigate | `test_reassemble_sources_pages_from_images`, `test_reassemble_places_pages_through_permuted_map`, `test_round_trip_keeps_page_tail_past_vsize`; copy-only, vsize and logical-offset mutants recorded in 03-01-SUMMARY | closed |
| T-03-06 | Tampering | expected SHA-1s used by round-trip tests | high | mitigate | `tests/test_hygiene.py::test_round_trip_tests_never_copy_manifest_hashes` with its planted-hash self-test | closed |
| T-03-07 | Elevation of privilege | `rule rebuild` in build.ninja | low | accept | fixed command `uv run reverseapoc rebuild` (configure.py line 43), no interpolated path | closed |
| T-03-08 | Tampering | splice() patch resolution | high | mitigate | writable spans clipped to vsize; `test_refuse_*` refusal tests, each with an unpatched control | closed |
| T-03-09 | Tampering | overlapping patches | medium | mitigate | `test_refuse_overlap*` (including identical bytes) | closed |
| T-03-10 | Tampering | fixup fields in patched pages | high | mitigate | `test_mask_*` (straddling, ptr16:32, page-cut); real-file sweeps `test_straddling_fields_are_masked`, `test_fields_cut_by_page_data_are_clipped` | closed |
| T-03-11 | Information disclosure | MaskedField and mismatch report | medium | mitigate | `test_mask_report_has_no_bytes`, `test_mutation_report_names_offset_without_bytes` | closed |
| T-03-12 | Denial of service | patch inputs | low | mitigate | key and value validation before resolution; `bisect` lookups in `tools/reverseapoc/splice.py` | closed |
| T-03-13 | Information disclosure | parse-le trailer row and JSON field | medium | mitigate | `test_parse_le_reports_trailer_without_bytes` (text and hex of the synthetic trailer absent from both outputs) | closed |
| T-03-14 | Tampering | rebuild --exe | medium | mitigate | selection by name only; `test_rebuild_unknown_exe_lists_known_names`, `test_rebuild_exe_filter_case_insensitive` | closed |
| T-03-15 | Information disclosure | rebuild --json | low | mitigate | `to_json` carries names, statuses, paths, numbers, labels and SHA-1s only (`tools/reverseapoc/splice.py`) | closed |
| T-03-16 | Information disclosure | docs/toolchain.md trailer facts | medium | mitigate | docs/toolchain.md line 56 records offset, length, first 4 bytes and SHA-1 only; no run of 5+ hex bytes anywhere in the file | closed |
| T-03-17 | Repudiation | pinned real-file facts | medium | mitigate | spike READMEs 001/002 (VALIDATED) and 003 (PARTIAL, facts confirmed) committed before 03-05 Task 2; FACTS cite them | closed |
| T-03-18 | Tampering | real-file test outputs | high | mitigate | `tests/test_splice_real.py` writes under `tmp_path` only; orig/ read-only in Docker | closed |
| T-03-19 | Information disclosure | real-file test failures | medium | mitigate | no raw-slice equality assertion in `tests/test_splice_real.py` (0 matches); offsets, VAs, counts, booleans and filecmp only | closed |
| T-03-20 | Information disclosure | gate logs under build/gate/ and the SUMMARY's gate section | low | mitigate | build/ is gitignored; cmp ran without `-l`; logs hold summaries, OK lines with manifest SHA-1s, exit lines | closed |
| T-03-21 | Repudiation | phase gate claim | medium | mitigate | six logs each ending `exit=0`, reproduced verbatim under `## Phase gate output` in 03-05-SUMMARY.md; verification step 7 passed | closed |
| T-03-22 | Elevation of privilege | configure.py render(): --orig path written unquoted into check_orig and rebuild commands | medium | mitigate | `_SAFE_ORIG` allowlist and `_check_orig_dir` (configure.py:65, :79) raise ConfigureError; main() writes nothing; `test_render_refuses_an_unsafe_orig_dir`, `test_main_refuses_an_unsafe_orig_dir`; supersedes T-03-07's fixed-string acceptance | closed |
| T-03-23 | Tampering | configure.py ninja_path(): executable names in build lines | medium | mitigate | `\|`/LF/CR names raise ConfigureError (`test_render_refuses_names_ninja_cannot_represent`, `test_main_refuses_*names_ninja_cannot_represent`, run without skip in the container); `parse-le $in` stays unquoted, pinned at tests/test_configure.py:120 | closed |
| T-03-24 | Repudiation | rebuild report masked_fields (text and --json) | low | mitigate | `len({m.fixup ...})` at splice.py:635; `test_mask_count_counts_distinct_fields` (5 cases); key and 8-key contract unchanged (tests/test_cli.py untouched) | closed |
| T-03-25 | Tampering | gate step 7 (container, non-default --orig) | low | mitigate | orig/ mounted `:ro` (docker/compose.yaml:16); /tmp/alt-orig holds symlinks only; default build.ninja regenerated (`--orig orig` after the gate) | closed |
| T-03-26 | Information disclosure | gate logs build/gate/03-06/ and 03-06-SUMMARY gate section | low | mitigate | build/ gitignored; cmp without -l; 0 runs of 5+ hex bytes in the seven logs | closed |
| T-03-27 | Denial of service | configure.py main(): a non-UTF-8 executable name | low | mitigate | `test_render_refuses_names_that_are_not_utf8`, `test_main_never_truncates_on_an_encoding_failure`, Linux-only `test_main_refuses_real_names_that_are_not_utf8` (ran in the container, 407 passed) | closed |
| T-03-28 | Tampering | configure.py render(): orig dir or exe path starting with `-` | medium | mitigate | `test_render_refuses_an_option_like_orig_dir`, `test_render_refuses_an_option_like_exe_path`, `test_main_refuses_an_option_like_*` | closed |
| T-03-29 | Tampering | configure.py rebuild rule: verify output directory | low | mitigate | `--out build` (`test_rebuild_out_is_the_builddir`, `test_generated_rebuild_writes_into_builddir`); gate 03-10 step 8 cmp silent from build/cfg-03-10/ | closed |
| T-03-30 | Repudiation | configure.py HEADER: status line and comments | low | mitigate | `CHECK-ORIG {orig}` (`test_render_check_orig_description_names_the_orig_dir`, `test_header_comments_name_no_fixed_orig_dir`); gate 03-10 step 7 shows `CHECK-ORIG ../tmp/alt-orig` | closed |
| T-03-31 | Denial of service | targets.load_manifest: malformed TOML, non-UTF-8, wrong shape | low | mitigate | ManifestError (`test_malformed_manifest_raises_manifest_error`, CLI `test_malformed_manifest_is_an_error_line`) | closed |
| T-03-32 | Tampering | targets.check_bare_name / splice._check_bare_name | medium | mitigate | `ntpath.isreserved` + POSIX and Windows path rules (`test_manifest_refuses_a_non_bare_target_name`, `test_rebuild_target_refuses_a_non_bare_name`); real manifest still loads | closed |
| T-03-33 | Repudiation | splice.Region.describe and _unwritable_reason | low | mitigate | `test_region_labels_count_pages_within_the_object`, `test_mismatch_label_in_a_later_object`, `test_unwritable_reason_names_the_page`; object-1 labels and 03-03 substrings unchanged | closed |
| T-03-34 | Repudiation | RebuildResult.format REFUSED/MISSING lines | low | mitigate | `test_rebuild_result_names_the_input_path`, `test_rebuild_refused_names_the_input_and_manifest`, `test_rebuild_missing_names_the_input`; `test_rebuild_json_refused_keeps_the_eight_keys` | closed |
| T-03-35 | Repudiation | tests/test_splice_real.py helpers | low | mitigate | no `page_count - 2` / `max(SRC_SIZE` left; helpers use `le.page_va`; FACTS byte-identical (cmp in 03-09); 21 real-file tests pass, no skip | closed |
| T-03-36 | Information disclosure | real-file test assertions and messages | low | mitigate | assertions on offsets, VAs, counts, booleans and filecmp only; `_page_at` message names the VA only | closed |
| T-03-37 | Tampering | gate steps 7 and 8 (container) | low | mitigate | orig/ `:ro`; /tmp/alt-orig symlinks only; step 8 writes only build/cfg-03-10/ (gitignored); default build.ninja regenerated | closed |
| T-03-38 | Information disclosure | gate logs build/gate/03-10/ and 03-10-SUMMARY | low | mitigate | build/ gitignored; cmp without -l; 0 runs of 5+ hex bytes in the eight logs | closed |
| T-03-39 | Repudiation | 03-REVIEW-DISPOSITION.md | low | mitigate | each fixed row cites plan, GREEN commit (`git merge-base --is-ancestor` checked) and build/gate/03-10/; 03-10 Task 2 verify passed | closed |
| T-03-SC | Tampering | package installs | low | accept | no dependency change in the phase (`git diff 547faf8..HEAD -- uv.lock pyproject.toml` is empty; 03-06 adds only the stdlib `re` and `sys`) | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-03-01 | T-03-07 | The ninja `rebuild` rule runs a fixed command with no interpolated input, and build.ninja is generated and gitignored | plan 03-02 threat model (plan checker passed, owner plan review) | 2026-10-20 |
| AR-03-02 | T-03-SC | The phase installs no package: stdlib only, with pytest and ruff already locked in uv.lock | plans 03-01..03-05 threat models (owner plan review) | 2026-10-20 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-20 | 22 | 22 | 0 | /gsd-secure-phase 3 (orchestrator, L1 grep-depth short-circuit) |
| 2026-10-20 | 27 | 27 | 0 | gap closure 03-06 re-audit (orchestrator, L1, T-03-22..26 added) |
| 2026-10-21 | 40 | 40 | 0 | gap closure 03-07..03-10 re-audit (orchestrator, L1, T-03-27..39 added) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-20

## Security Audit 2026-10-20

| Metric | Count |
|---|---|
| Threats found | 27 |
| Closed | 27 |
| Open | 0 |

## Security Audit 2026-10-21

| Metric | Count |
|---|---|
| Threats found | 40 |
| Closed | 40 |
| Open | 0 |
