---
phase: "3"
slug: "byte-identical-round-trip"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-20"
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `03-RESEARCH.md` § Validation Architecture; task IDs are filled in once the plans exist.

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
| (planner) | — | — | RT-01 | — | N/A | unit (synthetic) | `uv run pytest -q tests/test_splice.py -k "assemble or permuted or tail or round_trip"` | ❌ W0 | ⬜ pending |
| (planner) | — | — | RT-01 | — | N/A | real-file | `uv run pytest -q tests/test_splice_real.py -k round_trip` | ❌ W0 | ⬜ pending |
| (planner) | — | — | RT-02 | T-3-tamper | refusals: BSS, page tail past vsize (D-18), no object, cross-object, overlap incl. identical bytes, empty, non-physical page; length unchanged; non-page regions equal original | unit (synthetic) | `uv run pytest -q tests/test_splice.py -k "refuse or overlap or length or physical"` | ❌ W0 | ⬜ pending |
| (planner) | — | — | RT-02 | — | N/A | unit (synthetic) | `uv run pytest -q tests/test_splice.py -k mask` | ❌ W0 | ⬜ pending |
| (planner) | — | — | RT-02 | — | N/A | real-file | `uv run pytest -q tests/test_splice_real.py -k straddl` | ❌ W0 | ⬜ pending |
| (planner) | — | — | RT-03 | T-3-path | `--out` under orig/ refused; target names that are not bare file names refused; orig/ never written | unit (synthetic + `write_manifest`) | `uv run pytest -q tests/test_cli.py -k rebuild` | ❌ (file exists, tests new) | ⬜ pending |
| (planner) | — | — | RT-03 | — | N/A | unit | `uv run pytest -q tests/test_configure.py -k verify` | ❌ (file exists, test new) | ⬜ pending |
| (planner) | — | — | RT-04 | — | N/A | unit (synthetic) | `uv run pytest -q tests/test_splice.py -k "mutation or edge or short_page"` | ❌ W0 | ⬜ pending |
| (planner) | — | — | RT-04 | — | N/A | real-file | `uv run pytest -q tests/test_splice_real.py -k control` | ❌ W0 | ⬜ pending |
| (planner) | — | — | RT-05 | T-3-input | `layout()` refuses non-zero non-resident/debug fields (D-19) and non-physical pages | unit | `uv run pytest -q tests/test_splice.py -k "layout or tiling or region_at"` | ❌ W0 | ⬜ pending |
| (planner) | — | — | RT-05 | — | N/A | real-file | `uv run pytest -q tests/test_splice_real.py -k "layout or facts"` | ❌ W0 | ⬜ pending |
| (planner) | — | — | RT-05 | T-3-leak | trailer reported as offset, length, sha1 only; never bytes | unit | `uv run pytest -q tests/test_le.py tests/test_cli.py -k trailer` | ❌ (files exist, tests new) | ⬜ pending |
| (planner) | — | — | RT-05 | — | N/A | doc check | `uv run pytest -q tests/test_hygiene.py -k toolchain` | ❌ | ⬜ pending |
| (planner) | — | — | D-15 | T-3-oracle | no manifest SHA-1 string appears under tests/ | hygiene | `uv run pytest -q tests/test_hygiene.py -k manifest_hashes` | ❌ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py`: `page_numbers=` and `trailer=` options on `build_le_image`, `trailer_offset` on `SyntheticLE`; a fixture variant with a fixup field cut by the short last page
- [ ] `tests/test_splice.py`: synthetic region map, splice, masking, refusals, reassembly, D-13 cases
- [ ] `tests/test_splice_real.py`: per-file skip, round trip, control mutation, straddler sweep, measured facts (facts added after the spike verdict)
- [ ] new tests in `tests/test_cli.py`, `tests/test_configure.py`, `tests/test_le.py`, `tests/test_hygiene.py`
- No framework install needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real rebuild into `build/` is byte-identical | RT-03 | Writes the repo's `build/` (tests use `tmp_path` only) | `uv run reverseapoc rebuild`, then `cmp build/UFO2P.EXE orig/UFO2P.EXE`, `cmp build/TACP.EXE orig/TACP.EXE`, `cmp build/SMKP.EXE orig/SMKP.EXE` (all silent), and `sha1sum orig/*.EXE build/*.EXE` |
| `ninja verify` edge runs the gate | RT-03 | ninja is only in the image | `docker compose run --rm build bash -lc "uv run python configure.py && ninja verify"` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
