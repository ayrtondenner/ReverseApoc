---
phase: "04"
slug: "compiler-identification"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-10-21"
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 04-RESEARCH.md "Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥ 9.1 (dev group), ruff ≥ 0.17 |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["."]`) |
| **Quick run command** | `uv run pytest -q tests/test_<module>.py` |
| **Full suite command** | `uv run pytest -q && uv run ruff check .` on the host, then `docker compose run --rm test` (from `docker/`) |
| **Estimated runtime** | ~10 s for the host suite without real-file sweeps; the full LIB386 sweep across 3 versions is ~20 s more |

Skip conditions (extend `tests/conftest.py`):
- `ORIG_DIR` / `REVERSEAPOC_ORIG` (existing) for anything that reads the EXEs.
- **New:** `WATCOM_DIR` from `REVERSEAPOC_WATCOM_DIR`, defaulting to `third_party/watcom`. It covers the installed trees, which matters because worktrees have no `third_party/`. Tests skip per version when `WATCOM_DIR/<ver>` is missing.
- `REVERSEAPOC_WATCOM_MEDIA` (existing) for ISO-based wpack tests.
- Compile tests skip unless they run on win32 (native) or `wibo` is on PATH (container). 10.5 compile tests also skip until the 10.5 `BINW` key file checks `ok`.
- Any real-file test that skips on the owner's machine counts as a failure at the phase gate (Phase 3 D-20).

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q tests/test_<touched>.py && uv run ruff check .`
- **After every plan wave:** Run `uv run pytest -q && uv run ruff check .` on the host, then `docker compose run --rm test`
- **Before `/gsd-verify-work`:** The full suite must be green on the host and in the container, the real-file tests must have run (not skipped), and the D-03 log must be present.
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Requirement-level map from research. The planner binds task IDs; execution fills Status.

| Req | Behavior | Test Type | Automated Command | File Exists | Status |
|-----|----------|-----------|-------------------|-------------|--------|
| CID-01 | 10.6/11.0 (and 10.5 after D-01) compile a probe under wibo/native; banner contains `Version <ver>`; hashes logged | real-file integration | `uv run pytest -q tests/test_compiler_real.py` (container for wibo) | ✅ | ✅ green (04-12/01, 04-12/06, 04-12/08 under wibo) |
| CID-01 | wpack decodes PCK00017 to the manifest-pinned size/SHA-1; packed-stream CRC checked; corrupt/truncated input raises `WpackError` | unit + real-file | `uv run pytest -q tests/test_wpack.py tests/test_wpack_real.py` | ✅ | ✅ green (04-12/01, 04-12/06) |
| CID-01 | `install-watcom 10.5` runs the decoder inside `.partial`; `check-watcom` reports OK, not KNOWN BAD | unit | `uv run pytest -q tests/test_watcom.py -k wpack` | ✅ (extended) | ✅ green (04-12/01, 04-12/06) |
| CID-02 | cflags parsing: `*` first, last match wins, unmatched refused, comments, bad `compiler@version`, wrapper-owned flags forbidden | unit | `uv run pytest -q tests/test_cflags.py` | ✅ | ✅ green (04-12/01, 04-12/06) |
| CID-02 | Two sources get the version/flags their rules assign (injected runner) | unit | `uv run pytest -q tests/test_compiler.py -k two_sources` | ✅ | ✅ green (04-12/01, 04-12/06) |
| CID-02 | Path allowlist, backslash rewrite, own `H/` only, env scrub, `-bt=dos -zld -fr=`, hash gate refuses mismatch/known_bad, banner cached | unit | `uv run pytest -q tests/test_compiler.py` | ✅ | ✅ green (04-12/01, 04-12/06) |
| CID-02 | Real two-file compile with differing rules gives the expected codegen difference | real-file | `uv run pytest -q tests/test_compiler_real.py -k cflags` | ✅ | ✅ green (04-12/01, 04-12/06, 04-12/08 under wibo) |
| CID-04 | OMF reader: synthetic LIB, Easy OMF, THREAD fixups, LIDATA nesting cap, COMDAT32, non-OMF skip | unit | `uv run pytest -q tests/test_omf.py` | ✅ | ✅ green (04-12/01, 04-12/06) |
| CID-04 | Real LIB facts (module counts per version; EMU387 parses as Easy OMF) | real-file | `uv run pytest -q tests/test_omf_real.py` | ✅ | ✅ green (04-12/01, 04-12/06) |
| CID-04 | libmatch on a synthetic LE with a planted module: masked match, fixup mismatch rejects, short/unmaskable recorded, ambiguity rules | unit | `uv run pytest -q tests/test_libmatch.py` | ✅ | ✅ green (04-12/01, 04-12/06) |
| CID-04 | `config/<exe>/runtime.csv` re-derived equals committed; `_cstart_` at the entry VA; ≥1 version-discriminating range | real-file | `uv run pytest -q tests/test_libmatch_real.py` | ✅ | ✅ green (04-12/01, 04-12/06, 04-12/07) |
| CID-03 | Idiom counters on synthetic byte strings respect the library mask | unit | `uv run pytest -q tests/test_probe.py` | ✅ | ✅ green (04-12/01, 04-12/06) |
| CID-03 | Probe per version reproduces the calibration table; non-library counts per EXE recorded | real-file | `uv run pytest -q tests/test_probe_real.py` | ✅ | ✅ green (04-12/01, 04-12/06, 04-12/08 under wibo) |
| CID-05 | toolchain.md Compiler section has no "To be confirmed in Phase 4" and has per-EXE flag columns | doc lint | `uv run pytest -q tests/test_hygiene.py -k toolchain` | ✅ (extended) | ✅ green (04-12/01, 04-12/06) |
| CID-06 | XI/YI reader on a synthetic LE; priority classification; per-EXE report | unit + real-file | `uv run pytest -q tests/test_cppscan.py tests/test_cppscan_real.py` | ✅ | ✅ green (04-12/01, 04-12/06) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/conftest.py`: `WATCOM_DIR` + `REVERSEAPOC_WATCOM_DIR`, plus `requires_version(ver)` and `requires_runner()` skip helpers
- [x] `tests/omfimage.py`: synthetic OMF record/LIB builder (own literals, per coding-style)
- [x] `tests/wpackimage.py`: synthetic wpack archive builder, including a tiny Shannon-coded case with deterministic qsort tie order
- [x] The test files named in the map above
- [x] No framework install needed

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Status |
|----------|-------------|------------|-------------------|--------|
| Normalized object hash (THEADR and COMENT 0xE9 dropped) is equal for native and wibo compiles, per version | D-03 / CID-01 | Needs both the Windows host and the container | Compile the probe with `uv run reverseapoc cc` on the host and in `docker compose run`, compare normalized hashes, and log to `build/gate/04-native-vs-wibo.txt` | ✅ green (build/gate/04-native-vs-wibo.txt) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

## Validation Audit 2026-10-21

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
