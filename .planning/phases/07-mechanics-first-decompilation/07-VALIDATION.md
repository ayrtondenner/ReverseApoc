---
phase: "7"
slug: "mechanics-first-decompilation"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-26"
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `07-RESEARCH.md` § Validation Architecture. Task IDs are filled in once the plans exist; until then the map is keyed by requirement.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + ruff (`pyproject.toml`; ruff `line-length = 100`, `target-version = py314`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths `tests`, pythonpath `.`); fixtures in `tests/conftest.py`; stand-in claude `tests/fakeclaude.py` |
| **Quick run command** | `uv run pytest -q tests/test_<module>.py -x && uv run ruff check .` |
| **Full suite command** | `uv run pytest -q && uv run ruff check .` on the host, then `docker compose run --rm test` in the container. Never run both at the same time: they share build/test-cc and build/test-cclog. |
| **Estimated runtime** | quick < 30 s; full host suite ~5 min; container suite ~11 min |

---

## Sampling Rate

- **After every task commit:** the quick command for the touched module(s) plus `uv run ruff check .`
- **After every plan wave:** the full host suite, then the container suite (not concurrently)
- **Before `/gsd-verify-work`:** both full suites green; `uv run reverseapoc readlint src/` exit 0; `gate --all` exit 0; `ninja verify`; rebuild + `cmp` silent for both EXEs; `uv run reverseapoc stats` shows at least 10 unattended matches; every tier signed in `config/mechanics.toml`
- **Max feedback latency:** 30 seconds for the quick command

---

## Per-Task Verification Map

Keyed by requirement until the planner assigns task IDs (`07-NN-MM`).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 1-2 | DEC-01 | — | typed call edges; jump tables give no edges; runtime rows stop the walk; closure with hubs (D-22), entries always members (D-31), asm role (D-23) | unit (synthetic LE) | `uv run pytest -q tests/test_callgraph.py tests/test_mechanics.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1-2 | DEC-01 | T-07 tamper | mechanics.toml strict parse; a signed tier's `members_sha256` change fails; no game bytes in committed files | unit + CI schema | `uv run pytest -q tests/test_mechanics.py tests/test_drift.py` | ❌ W0 / extend | ⬜ pending |
| TBD | TBD | 2 | DEC-01 | — | members file and asm list regenerate byte-identical from orig/ | real-file (skips without orig/) | `uv run pytest -q tests/test_mechanics_real.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | DEC-01 | — | spike 007 checkers pass and can fail (planted EXPECTED) | spike scripts (host) | `uv run python .planning/spikes/007-locate-997-training/<script>.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | DEC-02 | T-07 tamper | two workers never hold one unit; B's broken view never reaches A's gate; gates never overlap; no `os.kill` probing | integration (fake claude, fake gate) | `uv run pytest -q tests/test_driver_workers.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | DEC-02 | — | tier picker: callees first, hubs/asm never block, claimed unit skipped | unit | `uv run pytest -q tests/test_driver_pick.py` | extend | ⬜ pending |
| TBD | TBD | 2-4 | DEC-02 | T-07 tamper | D-29 prerequisites; rename end to end in one commit; collision refused | unit + integration | `uv run pytest -q tests/test_symbols.py tests/test_configure.py tests/test_check.py tests/test_drift.py tests/test_rename.py` | extend / ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | DEC-03 | T-07 tamper | D-27: unit rule chosen by logical path; `gate EXE/UNIT --cflags` refused with no row | unit | `uv run pytest -q tests/test_compiler.py tests/test_check.py tests/test_gate.py` | extend | ⬜ pending |
| TBD | TBD | 2-3 | DEC-03 | T-07 tamper | flags propose/regate/approve: hit C from `checks/NNNN.c`, regate never writes cflags.txt or src/, approve refusals, siblings listed (D-32) | unit (fake compile/objdiff) | `uv run pytest -q tests/test_flags.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | DEC-03 | — | second-stage sweep only for misses at or above 90%, at most 24 cells | unit | `uv run pytest -q tests/test_check.py -k sweep2` | extend | ⬜ pending |
| TBD | TBD | 3 | DEC-04 | — | readlint RL01-RL06 negative cases, exempt contexts, allowlist (D-30), waivers counted, scoped modes | unit | `uv run pytest -q tests/test_readlint.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | DEC-05 | — | `mechanics` key in progress.json; member vs full-closure figures; asm group outside the percentage; deterministic; 999.4 markup | unit (CI) | `uv run pytest -q tests/test_progress.py tests/test_progress_page.py tests/test_workflows.py` | extend | ⬜ pending |
| TBD | TBD | 3 | DEC-06 | — | one LIMIT pauses all workers; night cap 60 across workers; `totals` records validate; target-matched off by default | integration (fake claude) | `uv run pytest -q tests/test_driver_workers.py tests/test_cli.py` | ❌ W0 / extend | ⬜ pending |
| TBD | TBD | 2 | DEC-07 | — | malformed attempts.jsonl line exits 2 naming the line; trailer-less match is `human-written`; v1 and v2 lines together | unit (synthetic git) + CI on committed log | `uv run pytest -q tests/test_stats.py tests/test_attempts_schema.py` | ❌ W0 / extend | ⬜ pending |
| TBD | TBD | 3 | AGT-11 | — | two capped Opus passes → Fable argv with USD 12.50; init accepts the requested model | unit | `uv run pytest -q tests/test_session.py tests/test_streamjson.py tests/test_driver.py -k escalat` | extend | ⬜ pending |
| TBD | TBD | 1-4 | hooks | T-07 tamper | always layer protects cflags.txt and the proposal queue; view unit writable, scanned for inline asm/pragma | unit | `uv run pytest -q tests/test_hooks.py` | extend | ⬜ pending |
| TBD | TBD | 4 | skills | — | watcom-decomp and the readability skill name only existing paths and verbs | unit | `uv run pytest -q tests/test_skill.py` | extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_callgraph.py`, `tests/test_mechanics.py`, `tests/test_mechanics_real.py` — DEC-01
- [ ] `tests/test_readlint.py` — DEC-04
- [ ] `tests/test_stats.py` — DEC-07
- [ ] `tests/test_flags.py` — D-12..D-16, D-28, D-32
- [ ] `tests/test_driver_workers.py` — DEC-02, DEC-06 concurrency
- [ ] `tests/test_rename.py` — D-19, D-29
- [ ] `tests/fakeclaude.py` extensions (unit written from env, sleep, model echo)
- [ ] spike 007 scripts and README
- [ ] Framework install: none (pytest and ruff present)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tier sign-offs (Tier 1 with the hub rule, then Tiers 2-4) | DEC-01 | Owner judgement (D-04, D-22) | Owner reviews the drafted tier and records the sign-off in `config/mechanics.toml` |
| asm list sign-off | DEC-01 / DEC-03 | Owner judgement (D-23) | Owner reviews the detector's list and evidence |
| Flag approvals (D-13 batch, later batches, an optional default flip) | DEC-03 | cflags.txt is owner-only (D-12, D-14, D-33) | Owner runs `flags approve` after the re-gates pass |
| Fable canary | AGT-11 | Real `claude -p` session (D-11, D-25) | Owner runs one Fable session; the init event's model ID is recorded |
| Matching and readability nights until Tier 1's must-match set is matched and named | DEC-03, DEC-04, AGT-11 | Owner-started runs (D-11) | Owner runs `reverseapoc drive`; each match commit is re-gated |
| #997 spike result reported to the owner | DEC-01 | Owner decides any OpenApoc comment | Report answer, addresses, evidence, matched status |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
