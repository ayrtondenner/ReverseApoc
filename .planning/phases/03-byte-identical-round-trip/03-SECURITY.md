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
| T-03-SC | Tampering | package installs | low | accept | no dependency change in the phase (`git diff 547faf8..HEAD -- uv.lock pyproject.toml` is empty) | closed |

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

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-20
