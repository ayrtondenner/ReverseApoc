---
phase: "6"
slug: "reporting-and-agent-pilot"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
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

Task IDs (`06-NN-MM`, plan and task number) were filled in at planning time. Gate plan 06-27 set each status on 2026-10-26 against its evidence logs. The logs are in `build/gate/06-evidence/` (gitignored), and the Status cell names the ones that prove the row:

- `30-host.log`: the host suite and ruff.
- `31-container.log`: the container suite and ruff.
- `11-regate-1..3.log`: the container `gate --all` on each pilot match commit.
- `12-final-ninja.log` and `13-final-gate.log`: the final tree, from clean.
- `14-drift.log`: the drift and attempt-log schema tests.
- `20-sweep-*.json`: the per-match sweeps.
- `33-live.log`: the live Pages check, written by the orchestrator under ruling F37.

| Req / item | Task IDs | Behaviour | Test Type | Automated Command | Where | File Exists | Status |
|---|---|---|---|---|---|---|---|
| RPT-01 | 06-11-01, 06-11-02, 06-11-03 | status.csv schema (sorted, LF, `0x%08X`); `gate` writes only on exit 0 | unit (fake check) | `uv run pytest -q tests/test_status.py tests/test_gate.py -x` | host + container | ✅ | ✅ green: 30-host.log, 31-container.log; 13-final-gate.log (gate --all exit 0 on the final tree) |
| RPT-01 / D-22 | 06-16-01, 06-18-03 | drift: matched rows == `source_marks.defined`; sha matches; the DecompHub file == derived | CI unit (committed files) | `uv run pytest -q tests/test_drift.py -x` | host, container, CI | ✅ | ✅ green: 14-drift.log (42 passed with test_attempts_schema.py, exit=0), 30-host.log, 31-container.log |
| AGT-06 | 06-11-02, 06-16-02, 06-27-01 | gate cross-check refuses a matched function reverted to INCLUDE_ASM | unit (fake landed set) + real | `uv run pytest -q tests/test_gate.py -k crosscheck`; `tests/test_gate_real.py` | host; container + real files | ✅ | ✅ green: 11-regate-1..3.log (gate --all exit=0 after each of c83cf4e, d288ad6, 955931f, both SHA-1s identical), 12-final-ninja.log and 13-final-gate.log (exit=0 from clean), 31-container.log (test_gate_real.py unskipped) |
| RPT-02 / D-50 | 06-18-01, 06-24-01 | progress.json numbers incl. the "uncovered" segment; squarified layout tiles its rect with no overlap, deterministic; shield schema keys | unit | `uv run pytest -q tests/test_progress.py -x` | host, CI | ✅ | ✅ green: 30-host.log, 31-container.log; 33-live.log (progress.json, progress.svg and the three shield files answer 200) |
| RPT-04 | 06-18-02, 06-24-02 | report.json uses report.proto field names only, version 2, u64 as strings, percent == progress.json combined | unit | `uv run pytest -q tests/test_report_shape.py -x` | host, CI | ✅ | ✅ green: 30-host.log, 31-container.log; 33-live.log (artifact `X-COM_Apocalypse_DOS_report` for f4056f1, not expired) |
| RPT-03 / D-30 | 06-24-02, 06-24-03, 06-27-03 | pages.yml: permissions, concurrency, schedule, pinned majors, artifact name, `-I` run, variable-gated DecompHub POST | text test | `uv run pytest -q tests/test_workflows.py -x` | host, CI | ✅ | ✅ green: 30-host.log, 31-container.log; 33-live.log (latest pages.yml run on main at f4056f1: success; `/` and `/index.html` 200; `/progress.html` 404 as expected after f4056f1) |
| RPT-05 | 06-18-02, 06-19-01, 06-19-02, 06-22-01, 06-22-02 | .recomp.json keys ⊆ the pinned schema properties; status in the enum; https links; the DecompHub feed follows progress-v1 rules | unit | `uv run pytest -q tests/test_listings.py -x`; the feed: `uv run pytest -q tests/test_progress.py -k decomphub -x` (ruling F31) | host, CI | ✅ | ✅ green: 30-host.log, 31-container.log; `.recomp.json` status `in-progress` (06-27-02); 33-live.log (raw decomphub.progress.json 200). The third-party submissions are owner-only (Manual-Only below) |
| AGT-05 / D-44..D-46 | 06-12-01, 06-12-02, 06-12-03 | decide(): Windows/POSIX/`..`/case/worktree paths; protected files; asm/pragma after comment blanking and continuation; the matching allowlist; Bash allowed only for exact attempt-wrapper argv with no shell metacharacters; the notes.md env exemption; other tools denied; exceptions → exit 2 | unit + 1 subprocess e2e | `uv run pytest -q tests/test_hooks.py -x` | host, container | ✅ | ✅ green: 30-host.log, 31-container.log; no `"reason": *"guardrail"` record in progress/attempts.jsonl after the 40-session pilot (06-27-01) |
| D-44 | 06-15-01, 06-15-02 | the attempt wrapper takes its target only from the driver's environment; `check` goes through `docker compose run`; `--sweep` allowed; `--cflags`/`--watcom-dir`/other units refused | unit (fake runner) | `uv run pytest -q tests/test_attempt_wrapper.py -x` | host, container | ✅ | ✅ green: 30-host.log, 31-container.log |
| AGT-08 | 06-13-01, 06-13-02, 06-13-03 | pack sections, look-alike ranking, ≤ 24 KB, truncation order, no write outside build/driver | unit (synthetic LE) | `uv run pytest -q tests/test_contextpack.py -x` | host, container | ✅ | ✅ green: 30-host.log, 31-container.log |
| AGT-07 / D-10 | 06-14-01, 06-14-02, 06-25-01 | status-aware skip; 5+5 interleave; ≤2 per unit, ≤3 per 64 KiB | unit | `uv run pytest -q tests/test_driver_pick.py -x` | host, container | ✅ | ✅ green: 30-host.log, 31-container.log |
| AGT-01..04 / D-48 | 06-17-01, 06-17-02, 06-17-03, 06-23-01, 06-23-02, 06-25-02, 06-25-03 | fake-claude scenarios: match → commit with trailers; partial/gave-up → reset; max_turns; rate_limit backoff (fake clock); auth/billing STOP; overloaded ×3; stray write → reset + stop; timeout kill; malformed lines; init assertions; version refusal; caps (3 per function, `--max-sessions`, `--target-matched`) | integration (fake claude, fake gate, tmp git repo) | `uv run pytest -q tests/test_driver.py -x` | host, container | ✅ | ✅ green: 30-host.log, 31-container.log; the pilot itself (10-commits.txt: 3 commits with the `Matched-By: reverseapoc drive` trailer, each re-gated in 11-regate-*.log) |
| AGT-03 / D-23 | 06-23-03 | attempts.jsonl schema: required keys/types/enums, no extra keys, no long hex blobs | unit | `uv run pytest -q tests/test_attempts_schema.py -x` | host, CI | ✅ | ✅ green: 14-drift.log (the committed 42-record log of run 20261026-005209 passes), 30-host.log, 31-container.log |
| AGT-09 | 06-15-03 | every path, verb and command named in SKILL.md exists; ≤ 300 lines | unit | `uv run pytest -q tests/test_skill.py -x` | host, CI | ✅ | ✅ green: 30-host.log, 31-container.log |
| AGT-10 | 06-01-01, 06-01-02 | spike 006 scripts: ALL PASS plus a planted-fail run | spike | `uv run python .planning/spikes/006-*/stub_regex.py <src>` | host / WSL2 | ✅ | ✅ green: 06-01-SUMMARY.md (stub_regex.py and linker_name.py ALL PASS, exit 0; `--plant` 1 FAILED, exit 1; outputs under build/spike006/). Verdict INVALIDATED, so the requirement's "own agent layer" branch applies (D-03) |
| AGT-11 / D-37 | 06-26-02, 06-27-01 | one owner-started run reaches 10 MATCHED, ≥ 3 per EXE, with the D-24 gate after every commit | owner run + re-gate | 06-27 Task 1 verify (count checks against the actual count, owner ruling 2026-10-26) | owner; container | ✅ | ⚠️ partial, owner-accepted 2026-10-26 (3/10), carried to Phase 7: run 20261026-005209, 3 MATCHED (2 UFO2P + 1 TACP) in 40 sessions (about USD 14 per match); every other D-37 condition held (10-commits.txt, 11-regate-1..3.log, 12-final-ninja.log, 13-final-gate.log, 14-drift.log, no guardrail record) |
| DI-01..06, 11-19, 22 | 06-02..06-10 (all tasks), 06-16-02 (container) | per the DI table in RESEARCH.md | unit / real | per-file pytest | host; container + real files for DI-02, DI-03, DI-19b | ✅ | ✅ green: 30-host.log, 31-container.log; build/gate/06-seed/03-real.log (DI-02, DI-03); every DI row closed or ruled in 06-DEFERRED-LEDGER.md (06-27-02) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky / partial (owner-ruled)*

---

## Wave 0 Requirements

- [x] `tests/fakeclaude.py` + `tests/fixtures/stream/*.jsonl` (synthetic events only; no game bytes)
- [x] `tests/test_status.py`, `tests/test_gate.py`, `tests/test_gate_real.py`, `tests/test_drift.py`, `tests/test_progress.py`, `tests/test_report_shape.py`, `tests/test_workflows.py`, `tests/test_listings.py`, `tests/test_hooks.py`, `tests/test_attempt_wrapper.py`, `tests/test_contextpack.py`, `tests/test_driver_pick.py`, `tests/test_driver.py`, `tests/test_attempts_schema.py`, `tests/test_skill.py`, `tests/test_fileio.py` (all present and run in 30-host.log and 31-container.log)
- `tests/conftest.py` helpers (a `requires_orig()` helper and a tmp git repo fixture): not needed, recorded by gate plan 06-27 (ruling F31). The driver tests build their own tmp git repo, and the real tests use the existing skip helpers.
- No framework install needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pilot run: 10 MATCHED commits, the gate after each, end-of-run `ninja verify` + `gate --all` (owner-run at 06-26-02; re-gated by 06-27-01) | AGT-11 | The owner starts it; it runs `claude -p` on the owner's subscription | At the pilot checkpoint: upgrade and pin the CLI, then `drive --max-sessions 40 --target-matched 10`. Evidence logs go under build/gate/06-evidence/; the phase gate then checks the attempt log and the commits. |
| Pages source set to "GitHub Actions" and the live URLs serving progress.json / progress.svg / progress-shield.json / decomphub.progress.json | RPT-03 | Repo settings are owner-only; the deploy needs a push to main | The owner sets Settings > Pages > Source once; after the deploy, curl each URL. |
| Awesome-list PRs and the decomp.me preset issue | RPT-05 | Third-party submissions, sent by the owner (decomp.me bans automation) | The owner opens each drafted PR or issue from `docs/listings.md`. |
| `<VERSION>_report` artifact present on a main run; DecompHub refresh POST accepted | RPT-04, D-30 | Needs a real Actions run on main | `gh run list` / `gh api` the artifact; check the POST step's log. |

Results, recorded by gate plan 06-27 (2026-10-26):

- **Pilot (AGT-11):** partial, owner-accepted 2026-10-26 (3/10), carried to Phase 7.
  - The owner ran run 20261026-005209 at 06-26-02: 3 MATCHED (ufo2p func_0008A0E0, tacp func_0006EE30, ufo2p func_0008A100) at the 40-session ceiling.
  - 06-27-01 re-gated every match commit in the container (11-regate-1..3.log, each exit=0), then ran the final tree from clean (12-final-ninja.log and 13-final-gate.log, exit=0).
- **Pages:** the owner set the source (06-26-02). 33-live.log (orchestrator, F37, main at f4056f1):
  - the latest pages.yml run is a success;
  - `/`, `/index.html`, progress.json, progress-shield.json, both per-EXE shields, progress.svg and the raw decomphub.progress.json answer 200;
  - `/progress.html` is 404, as expected: the owner's f4056f1 publishes the page only as index.html.
- **Report artifact:** `X-COM_Apocalypse_DOS_report` exists for f4056f1 and has not expired (33-live.log).
- **DecompHub POST:** not exercised live. The optional `DECOMPHUB_REFRESH` variable was not set, or not reported (06-26). The gating is covered by tests/test_workflows.py.
- **Awesome-list PRs, decomp.me issue and DecompHub claim:** owner-only. They were not reported at 06-26 and stay with the owner.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (the conftest helpers were not needed, ruling F31, see Wave 0)
- [x] No watch-mode flags
- [x] Feedback latency < 30s for the per-task quick runs (for example, 14-drift.log: 42 tests in 10 s). The full suites run once per wave: host 9 min 39 s, container 11 min 14 s.
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-10-26, gate plan 06-27.
- Host suite: 2780 passed, 35 skipped (platform skips only, F2 audit), ruff clean (30-host.log).
- Container suite: 2813 passed, 2 skipped (`Windows-only: msvcrt lock path` only), ruff clean (31-container.log).
- Hygiene: 32-hygiene.log.
- AGT-11 is partial, owner-accepted 2026-10-26 (3/10), carried to Phase 7.
