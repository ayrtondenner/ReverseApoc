---
phase: "6"
slug: "reporting-and-agent-pilot"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-24"
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `06-RESEARCH.md` § Validation Architecture. The D-04 row is changed by `06-CONTEXT.md` D-44: there is no MCP server, and an attempt wrapper replaces it.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥9.1 + ruff ≥0.17 (`pyproject.toml`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths `tests`, pythonpath `.`) |
| **Quick run command** | `uv run pytest -q tests/test_<module>.py -x` |
| **Full suite command** | `uv run pytest -q && uv run ruff check .` on the host, then `docker compose run --rm test` in the container. Never run both at the same time: they share build/test-cc and build/test-cclog. |
| **Estimated runtime** | quick < 30 s; full host suite ~5 min; container suite ~10 min |

---

## Sampling Rate

- **After every task commit:** run the touched test files with `-x` (under 30 s).
- **After every plan wave:** run the full host suite and ruff, then the container suite, one after the other. Waves with container plans (the DI-02/DI-03 probes, gate seeding, Ghidra drafts) also run `test_*_real.py` in the main checkout with `REVERSEAPOC_ORIG` / `REVERSEAPOC_WATCOM_DIR`.
- **Before `/gsd-verify-work`:** both suites green. The skip audit allows only platform skips and real-file skips. Also: `ninja -t clean && ninja verify`, `gate --all`, and the drift test green on the final tree.
- **Max feedback latency:** 30 seconds per task commit.

---

## Per-Task Verification Map

Task IDs (`06-NN-MM`, plan and task number) were filled in at planning time; statuses are set by gate plan 06-27 against its evidence logs.

| Req / item | Task IDs | Behaviour | Test Type | Automated Command | Where | File Exists | Status |
|---|---|---|---|---|---|---|---|
| RPT-01 | 06-11-01, 06-11-02, 06-11-03 | status.csv schema (sorted, LF, `0x%08X`); `gate` writes only on exit 0 | unit (fake check) | `uv run pytest -q tests/test_status.py tests/test_gate.py -x` | host + container | ❌ W0 | ⬜ pending |
| RPT-01 / D-22 | 06-16-01, 06-18-03 | drift: matched rows == `source_marks.defined`; sha matches; the DecompHub file == derived | CI unit (committed files) | `uv run pytest -q tests/test_drift.py -x` | host, container, CI | ❌ W0 | ⬜ pending |
| AGT-06 | 06-11-02, 06-16-02, 06-27-01 | gate cross-check refuses a matched function reverted to INCLUDE_ASM | unit (fake landed set) + real | `uv run pytest -q tests/test_gate.py -k crosscheck`; `tests/test_gate_real.py` | host; container + real files | ❌ W0 | ⬜ pending |
| RPT-02 / D-50 | 06-18-01, 06-24-01 | progress.json numbers incl. the "uncovered" segment; squarified layout tiles its rect with no overlap, deterministic; shield schema keys | unit | `uv run pytest -q tests/test_progress.py -x` | host, CI | ❌ W0 | ⬜ pending |
| RPT-04 | 06-18-02, 06-24-02 | report.json uses report.proto field names only, version 2, u64 as strings, percent == progress.json combined | unit | `uv run pytest -q tests/test_report_shape.py -x` | host, CI | ❌ W0 | ⬜ pending |
| RPT-03 / D-30 | 06-24-02, 06-24-03, 06-27-03 | pages.yml: permissions, concurrency, schedule, pinned majors, artifact name, `-I` run, variable-gated DecompHub POST | text test | `uv run pytest -q tests/test_workflows.py -x` | host, CI | ❌ W0 | ⬜ pending |
| RPT-05 | 06-18-02, 06-19-01, 06-19-02, 06-22-01, 06-22-02 | .recomp.json keys ⊆ the pinned schema properties; status in the enum; https links; the DecompHub feed follows progress-v1 rules | unit | `uv run pytest -q tests/test_listings.py -x` | host, CI | ❌ W0 | ⬜ pending |
| AGT-05 / D-44..D-46 | 06-12-01, 06-12-02, 06-12-03 | decide(): Windows/POSIX/`..`/case/worktree paths; protected files; asm/pragma after comment blanking and continuation; the matching allowlist; Bash allowed only for exact attempt-wrapper argv with no shell metacharacters; the notes.md env exemption; other tools denied; exceptions → exit 2 | unit + 1 subprocess e2e | `uv run pytest -q tests/test_hooks.py -x` | host, container | ❌ W0 | ⬜ pending |
| D-44 | 06-15-01, 06-15-02 | the attempt wrapper takes its target only from the driver's environment; `check` goes through `docker compose run`; `--sweep` allowed; `--cflags`/`--watcom-dir`/other units refused | unit (fake runner) | `uv run pytest -q tests/test_attempt_wrapper.py -x` | host, container | ❌ W0 | ⬜ pending |
| AGT-08 | 06-13-01, 06-13-02, 06-13-03 | pack sections, look-alike ranking, ≤ 24 KB, truncation order, no write outside build/driver | unit (synthetic LE) | `uv run pytest -q tests/test_contextpack.py -x` | host, container | ❌ W0 | ⬜ pending |
| AGT-07 / D-10 | 06-14-01, 06-14-02, 06-25-01 | status-aware skip; 5+5 interleave; ≤2 per unit, ≤3 per 64 KiB | unit | `uv run pytest -q tests/test_driver_pick.py -x` | host, container | ❌ W0 | ⬜ pending |
| AGT-01..04 / D-48 | 06-17-01, 06-17-02, 06-17-03, 06-23-01, 06-23-02, 06-25-02, 06-25-03 | fake-claude scenarios: match → commit with trailers; partial/gave-up → reset; max_turns; rate_limit backoff (fake clock); auth/billing STOP; overloaded ×3; stray write → reset + stop; timeout kill; malformed lines; init assertions; version refusal; caps (3 per function, `--max-sessions`, `--target-matched`) | integration (fake claude, fake gate, tmp git repo) | `uv run pytest -q tests/test_driver.py -x` | host, container | ❌ W0 | ⬜ pending |
| AGT-03 / D-23 | 06-23-03 | attempts.jsonl schema: required keys/types/enums, no extra keys, no long hex blobs | unit | `uv run pytest -q tests/test_attempts_schema.py -x` | host, CI | ❌ W0 | ⬜ pending |
| AGT-09 | 06-15-03 | every path, verb and command named in SKILL.md exists; ≤ 300 lines | unit | `uv run pytest -q tests/test_skill.py -x` | host, CI | ❌ W0 | ⬜ pending |
| AGT-10 | 06-01-01, 06-01-02 | spike 006 scripts: ALL PASS plus a planted-fail run | spike | `uv run python .planning/spikes/006-*/stub_regex.py <src>` | host / WSL2 | ❌ | ⬜ pending |
| DI-01..06, 11-19, 22 | 06-02..06-10 (all tasks), 06-16-02 (container) | per the DI table in RESEARCH.md | unit / real | per-file pytest | host; container + real files for DI-02, DI-03, DI-19b | partly | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/fakeclaude.py` + `tests/fixtures/stream/*.jsonl` (synthetic events only; no game bytes)
- [ ] `tests/test_status.py`, `tests/test_gate.py`, `tests/test_gate_real.py`, `tests/test_drift.py`, `tests/test_progress.py`, `tests/test_report_shape.py`, `tests/test_workflows.py`, `tests/test_listings.py`, `tests/test_hooks.py`, `tests/test_attempt_wrapper.py`, `tests/test_contextpack.py`, `tests/test_driver_pick.py`, `tests/test_driver.py`, `tests/test_attempts_schema.py`, `tests/test_skill.py`, `tests/test_fileio.py`
- [ ] `tests/conftest.py`: a `requires_orig()` helper (EXE present under ORIG_DIR); a tmp git repo fixture for driver tests
- No framework install needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pilot run: 10 MATCHED commits, the gate after each, end-of-run `ninja verify` + `gate --all` (owner-run at 06-26-02; re-gated by 06-27-01) | AGT-11 | The owner starts it; it runs `claude -p` on the owner's subscription | At the pilot checkpoint: upgrade and pin the CLI, then `drive --max-sessions 40 --target-matched 10`. Evidence logs go under build/gate/06-evidence/; the phase gate then checks the attempt log and the commits. |
| Pages source set to "GitHub Actions" and the live URLs serving progress.json / progress.svg / progress-shield.json / decomphub.progress.json | RPT-03 | Repo settings are owner-only; the deploy needs a push to main | The owner sets Settings > Pages > Source once; after the deploy, curl each URL. |
| Awesome-list PRs and the decomp.me preset issue | RPT-05 | Third-party submissions, sent by the owner (decomp.me bans automation) | The owner opens each drafted PR or issue from `docs/listings.md`. |
| `<VERSION>_report` artifact present on a main run; DecompHub refresh POST accepted | RPT-04, D-30 | Needs a real Actions run on main | `gh run list` / `gh api` the artifact; check the POST step's log. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
