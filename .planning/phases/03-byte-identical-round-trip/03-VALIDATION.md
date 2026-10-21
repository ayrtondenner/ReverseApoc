---
phase: "3"
slug: "byte-identical-round-trip"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-10-20"
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `03-RESEARCH.md` § Validation Architecture; task IDs bound by the plans; audited against the executed phase on 2026-10-20.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 (`[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["."]`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest -q tests/test_splice.py` |
| **Full suite command** | `uv run pytest -q && uv run ruff check .` |
| **Container command** | `docker compose run --rm test` (orig/ mounted read-only; real-file tests run there) |
| **Estimated runtime** | ~10 seconds host suite (real files: ~0.2 s per EXE for `fixups()` plus ~30 ms reassembly) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q tests/test_splice.py` (plus the touched test file) and `uv run ruff check .`
- **After every plan wave:** Run `uv run pytest -q && uv run ruff check .`
- **Before `/gsd-verify-work 3`:** Full suite green on the host, `docker compose run --rm test` green, `uv run reverseapoc rebuild` prints three OK lines (exit 0), `cmp` silent for UFO2P/TACP/SMKP, `ninja verify` green in the container
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

Requirement-level map (task IDs are bound by the planner; every task that touches a row runs its command).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-T1, 03-01-T3 | 03-01 | 1 | RT-01 | T-03-05 | fresh-buffer reassembly; copy-only, vsize and logical-offset mutants fail | unit (synthetic) | `uv run pytest -q tests/test_splice.py -k "assemble or reassemble or permuted or tail or round_trip"` | ✅ | ✅ green |
| 03-05-T1 | 03-05 | 4 | RT-01 | T-03-18 | real-file outputs only under tmp_path | real-file | `uv run pytest -q tests/test_splice_real.py -k round_trip` | ✅ | ✅ green |
| 03-03-T2 | 03-03 | 2 | RT-02 | T-03-08, T-03-09 | refusals: BSS, page tail past vsize (D-18), no object, cross-object, overlap incl. identical bytes, empty, non-physical page; length unchanged; non-page regions equal original | unit (synthetic) | `uv run pytest -q tests/test_splice.py -k "refuse or overlap or length or physical"` | ✅ | ✅ green |
| 03-03-T3 | 03-03 | 2 | RT-02 | T-03-10, T-03-11 | fixup fields keep link-time bytes; report carries addresses only | unit (synthetic) | `uv run pytest -q tests/test_splice.py -k mask` | ✅ | ✅ green |
| 03-05-T1 | 03-05 | 4 | RT-02 | T-03-19 | assertions on offsets/booleans only | real-file | `uv run pytest -q tests/test_splice_real.py -k straddl` | ✅ | ✅ green |
| 03-01-T1, 03-04-T1, 03-04-T2 | 03-01, 03-04 | 1, 3 | RT-03 | T-03-01, T-03-02, T-03-14 | `--out` under orig/ refused; target names that are not bare file names refused; `--exe` never forms a path; orig/ never written | unit (synthetic + `write_manifest`) | `uv run pytest -q tests/test_cli.py -k rebuild` | ✅ | ✅ green |
| 03-02-T1 | 03-02 | 1 | RT-03 | T-03-07 | fixed command string in `rule rebuild` | unit | `uv run pytest -q tests/test_configure.py -k verify` | ✅ | ✅ green |
| 03-05-T3 | 03-05 | 4 | RT-03 | T-03-20, T-03-21 | phase gate on the main checkout, host and container: no real-file skip, three OK rebuild lines, silent `cmp`, `ninja verify` exit 0; each step logged under build/gate/ with its exit status and reproduced in the SUMMARY | gate (real-file, host + container) | `test "$(tail -qn 1 build/gate/0[1-6]-*.log \| sort -u)" = "exit=0"` | ✅ (build/gate/, reproduced in 03-05-SUMMARY.md) | ✅ green |
| 03-03-T1, 03-03-T2 | 03-03 | 2 | RT-04 | T-03-11 | mismatch report names offset/region/VA/count, no bytes | unit (synthetic) | `uv run pytest -q tests/test_splice.py -k "mutation or edge or short_page"` | ✅ | ✅ green |
| 03-05-T1 | 03-05 | 4 | RT-04 | T-03-19 | real control reported by offset and VA only | real-file | `uv run pytest -q tests/test_splice_real.py -k control` | ✅ | ✅ green |
| 03-01-T2 | 03-01 | 1 | RT-05 | T-03-03 | `layout()` refuses non-zero non-resident/debug fields (D-19), a loader section that does not end at the fixup section, and non-physical pages | unit | `uv run pytest -q tests/test_splice.py -k "layout or tiling or region_at"` | ✅ | ✅ green |
| 03-05-T1, 03-05-T2 | 03-05 | 4 | RT-05 | T-03-17 | facts pinned only after the spike READMEs confirm them | real-file | `uv run pytest -q tests/test_splice_real.py -k "layout or facts"` | ✅ | ✅ green |
| 03-04-T3 | 03-04 | 3 | RT-05 | T-03-13 | trailer reported as offset, length, sha1 only; never bytes | unit | `uv run pytest -q tests/test_le.py tests/test_cli.py -k trailer` | ✅ | ✅ green |
| 03-05-T2 | 03-05 | 4 | RT-05 | T-03-16 | docs record trailer as offset, length, first 4 bytes, sha1 (D-12) | doc check | `uv run pytest -q tests/test_hygiene.py -k toolchain` | ✅ | ✅ green |
| 03-02-T2 | 03-02 | 1 | D-15 | T-03-06 | no manifest md5/sha1 (or 8-digit prefix) under tests/ except the manifest's own pin in tests/test_targets.py | hygiene | `uv run pytest -q tests/test_hygiene.py -k manifest_hashes` | ✅ | ✅ green |
| 03-06-T1 | 03-06 | gap | RT-03 | T-03-22, T-03-23 | --orig reaches check-orig/verify; unsafe --orig and \|/LF/CR names refused before any write; parse-le $in unquoted; names with spaces work (WR-05, WR-06) | unit + integration | `uv run pytest -q tests/test_configure.py -k "orig or represent or spaces"` | ✅ | ✅ green |
| 03-06-T2 | 03-06 | gap | RT-02 | T-03-24 | masked_fields counts distinct fixup fields (touching, three-patch, straddling, two-field, mixed) (WR-02) | unit | `uv run pytest -q tests/test_splice.py -k distinct_fields` | ✅ | ✅ green |
| 03-06-T3 | 03-06 | gap | RT-03 | T-03-25, T-03-26 | gate re-run on the main checkout incl. ninja verify through a non-default --orig; logs under build/gate/03-06/, reproduced in 03-06-SUMMARY.md | gate (real-file, host + container) | `test "$(tail -qn 1 build/gate/03-06/0[1-7]-*.log \| sort -u)" = "exit=0"` | ✅ | ✅ green |
| 03-07-T1 | 03-07 | gap | RT-03 | T-03-27, T-03-28 | non-UTF-8 and option-like (`-`) orig dirs / exe paths refused with ConfigureError; build.ninja never truncated (WR-07, IN-09) | unit + container | `uv run pytest -q tests/test_configure.py -k \"utf8 or option_like or truncat\"` (Linux-only case runs in the container) | ✅ | ✅ green |
| 03-07-T2 | 03-07 | gap | RT-03 | T-03-29, T-03-30 | `CHECK-ORIG {orig}`, no fixed orig/ comment, rebuild `--out build` = builddir, no stale phase wording (IN-10, IN-11, IN-08) | unit + integration | `uv run pytest -q tests/test_configure.py -k \"description_names or header_comments or rebuild_out or writes_into_builddir or stale_phase\"` | ✅ | ✅ green |
| 03-08-T1 | 03-08 | gap | RT-03 | T-03-31, T-03-32 | malformed manifests and non-bare / Windows-reserved target names raise ManifestError, host-independently (IN-06, IN-07) | unit + CLI | `uv run pytest -q tests/test_targets.py tests/test_cli.py -k \"malformed or non_bare\"` | ✅ | ✅ green |
| 03-08-T2 | 03-08 | gap | RT-04 | T-03-33, T-03-34 | within-object page labels and refusal reasons; REFUSED/MISSING name the real input and manifest; 8 JSON keys kept (IN-01, IN-02, IN-03, VN-01) | unit + CLI | `uv run pytest -q tests/test_splice.py tests/test_cli.py -k \"within_the_object or later_object or unwritable_reason_names or names_the_input or refused_names or missing_names or eight_keys\"` | ✅ | ✅ green |
| 03-09-T1 | 03-09 | gap | RT-05 | T-03-35, T-03-36 | real-file helpers derived from le.py's reader, not splice.py's arithmetic; FACTS unchanged (IN-05) | real-file | `REVERSEAPOC_ORIG=... uv run pytest -q -rs tests/test_splice_real.py` (21 passed, no skip) | ✅ | ✅ green |
| 03-09-T2 | 03-09 | gap | RT-05 | — | toolchain.md container orig/ row lists SMKP.EXE (IN-04) | doc check | `grep -qF 'SMKP.EXE from your install' docs/toolchain.md` | ✅ | ✅ green |
| 03-10-T1 | 03-10 | gap | RT-03 | T-03-37, T-03-38 | gate re-run after G-03-6 incl. ninja check-orig through a non-default --orig and ninja verify from a sub-directory build.ninja; logs under build/gate/03-10/, reproduced in 03-10-SUMMARY.md | gate (real-file, host + container) | `test \"$(tail -qn 1 build/gate/03-10/0[1-8]-*.log \| sort -u)\" = \"exit=0\"` | ✅ | ✅ green |

Real-file rows skip in a worktree without orig/; executors run them with `REVERSEAPOC_ORIG="$(git rev-parse --path-format=absolute --git-common-dir)/../orig"` prefixed (plan 03-01 adds the override to tests/conftest.py).

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/conftest.py`: `page_numbers=`, `trailer=`, `extra_header_fields=` and `objects=` options on `build_le_image`, `trailer_offset`/`fixup_start`/`fixup_end` on `SyntheticLE`, `SYNTHETIC_TRAILER`, the `REVERSEAPOC_ORIG` override of `ORIG_DIR` (plan 03-01 Task 2); the field cut by the short last page is built with `fixups=[b"", b"", fixup_record(7, LAST_PAGE_SIZE - 2, 1, 0x10)]` (plan 03-03 Task 3)
- [x] `tests/test_splice.py`: synthetic region map, splice, masking, refusals, reassembly, D-13 cases
- [x] `tests/test_splice_real.py`: per-file skip, round trip, control mutation, straddler sweep, measured facts (facts added after the spike verdict)
- [x] new tests in `tests/test_cli.py`, `tests/test_configure.py`, `tests/test_le.py`, `tests/test_hygiene.py`
- No framework install needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real rebuild into `build/` is byte-identical | RT-03 | Writes the repo's `build/` (tests use `tmp_path` only) | `uv run reverseapoc rebuild`, then `cmp build/UFO2P.EXE orig/UFO2P.EXE`, `cmp build/TACP.EXE orig/TACP.EXE`, `cmp build/SMKP.EXE orig/SMKP.EXE` (all silent), and `sha1sum orig/*.EXE build/*.EXE` |
| `ninja verify` edge runs the gate | RT-03 | ninja is only in the image | `docker compose run --rm build bash -lc "uv run python configure.py && ninja verify"` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-10-20 (all 15 rows green on the main checkout with orig/ present, no real-file skip; manual-only rows executed by the 03-05 phase gate)

## Validation Audit 2026-10-20

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

## Validation Audit 2026-10-20

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Rows added (03-06) | 3 |

## Validation Audit 2026-10-21

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Rows added (03-07..03-10) | 7 |
