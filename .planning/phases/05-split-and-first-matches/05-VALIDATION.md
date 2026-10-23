---
phase: "5"
slug: "split-and-first-matches"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-23"
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `05-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 9.1 and ruff >= 0.17, from `[dependency-groups].dev` |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["."]`) |
| **Quick run command** | `uv run pytest -q -x tests/test_<module>.py && uv run ruff check .` |
| **Full suite command** | Host: `uv run pytest -q && uv run ruff check .`. Container: `docker compose run --rm test`. Never run the two at the same time. |
| **Estimated runtime** | Quick run about 10 s. Full host suite about 2–4 min with real-file tests. The container suite takes longer: it runs Ghidra export real tests, about 1 min per EXE. |

---

## Sampling Rate

- **After every task commit:** run the quick command for the touched module, plus `uv run ruff check .`.
- **After every plan wave:** run the full host suite, then the container suite, one after the other.
- **Before `/gsd-verify-work`:** both full suites must be green with no real-file skips, `ninja verify` must give SHA-1 identical output for both EXEs, and the spike verdict must be recorded.
- **Max feedback latency:** 240 seconds.

---

## Per-Task Verification Map

The planner and executor fill in task IDs. Each row maps one requirement to the automated command that proves it. Every plan task that implements a row must carry that row's command, or a narrower one, as its `<automated>` verify.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | SPL-01 | T-05-* | The Ghidra and JDK layer is SHA-256 pinned, and no game or Watcom path is baked into the image | hygiene + unit + real (`requires_ghidra`) | `uv run pytest -q tests/test_hygiene.py tests/test_ghidra.py tests/test_ghidra_real.py` | ❌ W0 (hygiene ✅ extend) | ⬜ pending |
| TBD | TBD | TBD | SPL-02 | — | N/A | unit + real | `uv run pytest -q tests/test_discover.py tests/test_functions.py tests/test_functions_real.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SPL-03 | — | N/A | unit + real | `uv run pytest -q tests/test_units.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SPL-04 | — | N/A | real (`requires_version("10.6")`, `requires_runner`) + unit | `uv run pytest -q tests/test_stub_real.py tests/test_configure.py` | ❌ W0 / ✅ extend | ⬜ pending |
| TBD | TBD | TBD | SPL-05 | T-05-* | Listings exist only under gitignored `asm/` and are never committed | unit + hygiene | `uv run pytest -q tests/test_asm.py tests/test_hygiene.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SPL-06 | — | N/A | unit | `uv run pytest -q tests/test_configure.py` | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | SPL-07 | — | N/A | unit + real | `uv run pytest -q tests/test_elf.py tests/test_omf2elf.py tests/test_omf2elf_real.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SPL-08 | — | N/A | unit | `uv run pytest -q tests/test_target.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SPL-09 | T-05-* | A wrong call or fixup target fails even where objdiff says 100% | unit | `uv run pytest -q tests/test_relocs.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SPL-10 | T-05-* | Original bytes are kept at relocated fields on both sides, and a mutated non-relocated byte fails | unit + real | `uv run pytest -q tests/test_land.py tests/test_splice_real.py` | ❌ W0 / ✅ extend | ⬜ pending |
| TBD | TBD | TBD | SPL-11 | — | N/A | unit | `uv run pytest -q tests/test_check.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SPL-12 | — | N/A | real (`requires_clang`) | `uv run pytest -q tests/test_lint.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SPL-13 | T-05-* | Both EXE SHA-1s match `config/targets.toml`, and the objdiff-blind negative fails the relocation check | container real | `docker compose run --rm build bash -lc "python configure.py && ninja && ninja verify && uv run reverseapoc check ufo2p/<u> && uv run reverseapoc check tacp/<u>"` + `uv run pytest -q tests/test_check_real.py tests/test_objdiff_real.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py`: add `requires_ghidra()`, `requires_objdiff()`, `requires_clang()` and `requires_capstone()` next to `requires_runner()`, plus a Ghidra-loadable synthetic LE variant (`e_lfarlc = 0x40`).
- [ ] `tests/elfread.py`: a test-only ELF32 reader for sections, symbols, relocations and implicit addends.
- [ ] `tests/omfimage.py`: add `comdat16` (0xC2) and NBKPAT builders.
- [ ] A synthetic Ghidra export fixture (CSV text with made-up addresses, no game bytes).
- [ ] Add capstone to `uv.lock` before the discovery tests. The `docs/tools.md` entry comes first, then the human-verify checkpoint (D-09).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The owner reviews the C of the first matches | SPL-13 (D-16) | The oracle decides the match; readability and naming are a human call | At `/gsd-verify-work 5`, read `src/ufo2p/<unit>.c` and `src/tacp/<unit>.c` next to `uv run reverseapoc check` output |
| Image size and the capstone dependency are accepted | SPL-01, D-09 | Owner judgement on +1.17 GB and on the first runtime dependency | Checkpoint before `uv add capstone==5.0.9` and at the first `docker compose build` that includes the Ghidra layer |
| Spike verdict (VALIDATED / PARTIAL / INVALIDATED) | Spike (D-01/D-02) | The verdict decides hybrid vs fallback; the owner signs it | Read `.planning/spikes/005-*/README.md` and its Given/When/Then results |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 240s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
