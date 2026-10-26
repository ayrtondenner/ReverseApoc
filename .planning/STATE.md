---
gsd_state_version: "1.0"
milestone: v1.0
milestone_name: Milestone 1
current_phase: 6
current_phase_name: Reporting and agent pilot
status: executing
stopped_at: Phase 6 context gathered
last_updated: "2026-10-25T00:48:59.175Z"
last_activity: 2026-10-24
last_activity_desc: Phase 6 execution started
state_head: 9f2d578a16a2f66e419dd46d6d7550164a9afcda
progress:
  total_phases: 8
  completed_phases: 5
  total_plans: 74
  completed_plans: 47
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-24)

**Core value:** Every match is proven by a deterministic oracle (rebuilt EXE SHA-1 identical to the original, objdiff 100% for the function), never by an agent's own judgement.
**Current focus:** Phase 6 — Reporting and agent pilot

## Current Position

Phase: 6 (Reporting and agent pilot) — EXECUTING
Plan: 1 of 27
Status: Executing Phase 6
Last activity: 2026-10-24 — Phase 6 execution started

Progress: [██████░░░░] 63%

Next steps:
1. Phases 1-5 complete (Phase 5: VERIFICATION.md passed with 1 owner override, UAT passed 5/5 by the owner on 2026-10-24).
2. Phase 6: `/gsd-discuss-phase 6`, then `/gsd-plan-phase 6`, then `/gsd-execute-phase 6` and `/gsd-verify-work 6`. Pick up backlog 999.3 (`asm` listing collision on `_Alphabet`) in Phase 6.

## Performance Metrics

**Velocity:**
- Total plans completed: 47
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 2 | - | - |
| 2 | 2 | - | - |
| 3 | 10 | - | - |
| 04 | 13 | - | - |
| 05 | 20 | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 04 P11 | 24min | 3 tasks | 8 files |
| Phase 04 P12 | 9min | 2 tasks | 2 files |
| Phase 04 P13 | 18min | 3 tasks | 5 files |
| Phase 05 P01 | 10min | 2 tasks | 4 files |
| Phase 05 P12 | 42min | 3 tasks | 7 files |
| Phase 05 P18 | 32min | 3 tasks | 7 files |
| Phase 05 P19 | 17min | 3 tasks | 4 files |
| Phase 05 P20 | 25min | 3 tasks | 2 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Phase structure fixed by the owner in `docs/workflow.md`; Milestone 1 phases are numbered 1-8 (Phases 7 and 8 added by the owner on 2026-10-21)
- [Roadmap]: A phase is complete only when its `VERIFICATION.md` passes; ROADMAP checkboxes are annotations
- [Phase 3]: In-place page splice for the MVP; full LE rewrite deferred (reopen trigger: a matched function changes size). Proven: three EXEs rebuild SHA-1 identical (Phase 3 gate)
- [Phase 04]: Game code: Watcom C 10.6 (10.5 byte-identical on the probe, 11.0 tied at -4r, candidate pending Phase 5 matches); linked runtime 10.6, no mix
- [Phase 04]: config/cflags.txt default is * wcc386@10.6 -4r -s -fpi (the flags the scans support); -s kept because only 40/32 functions call __CHK, which get per-glob rules in Phase 5
- [Phase 04]: Phase 4 gate green on host (974 passed, 6 platform-only skips) and container (980 passed, 0 skipped), ruff clean; rebuild SHA-1 identical; check-watcom OK; compiler/probe real tests pass under wibo
- [Phase 04]: cc.log appends are serialised by a stdlib OS lock on the sidecar <log>.lock (fcntl.flock / non-blocking msvcrt.locking retrying only on EACCES), released after the log closes; host and container on one log at once is unsupported (G-04-2)
- [Phase 04]: UAT 2026-10-23: owner re-tested G-04-2 (320 parallel compiles per environment, no lost line) and accepted the shipped `--log` behaviour; a docs note on a nameless or folder `--log` is backlog 999.1; review IN-08..IN-13 (info) left open in 04-REVIEW-DISPOSITION.md
- [Phase 05]: Spike 005 VALIDATED (D-02, D-19): objdiff-cli 3.8.2 scores the converted cmain386 OMF object at 100.0 for __CMain in both EXEs with only an address-to-name map; hybrid pipeline stays
- [Phase 05]: objdiff misses a wrong 2nd relocation of one instruction (100.0, spike 005 P3): the SPL-09 relocation check is the match gate; code sections are named _TEXT on both sides (a .text target is unpaired)
- [Phase 05]: 05-12: Ghidra 12.1.4 + LxLoader v12.1.4-1 (SHA-256 pinned), OpenJDK 21 and clang 18 are in the image; D-20 strip of docs/ and top-level Extensions/ kept (image 898,389,257 bytes)
- [Phase 05]: 05-12: Ghidra makes one one-address function in each EXE's data object (UFO2P 0x0013BD40, TACP 0x002B405C); reconcile (05-16) drops entries outside the code object
- [Phase 05]: 05-18: first UFO2P match func_000A3980 (u_000a34f0) under the default wcc386@10.6 -4r -s -fpi rule; no sweep, no cflags rule, * default unchanged (D-18)
- [Phase 05]: 05-18: target.py leaves references into no functions.csv row and branches out of the code object raw (named in raw_fields, F11 principle) so every real unit cuts and the default ninja graph builds
- [Phase 05]: 05-19: first TACP match func_00055080 (u_00054f20) under the default wcc386@10.6 -4r -s -fpi rule; no sweep, no cflags rule
- [Phase 05]: 05-19: two leaf-sized matches separate no Phase 4 candidate (10.5/10.6/11.0, -4/-5, -o* tied); * default and __WATCOMC__ 1060 stay (D-18, D-14)
- [Phase 05]: 05-20: Phase 5 gate green on main from a clean ninja graph (both units compiled by wcc386@10.6 under wibo, linted, landed SHA-1 identical); both first-match checks exit 0; host 1540p/25 platform skips, container 1563p/2 Windows-only skips, ruff clean; 05-VALIDATION.md signed off 13/13 with build/gate/05-evidence/ logs
- [Phase 05]: UAT 2026-10-24 (5/5 passed): the owner accepted the 05-18 raw-fields deviation from 05-08 (override in 05-VERIFICATION.md), the 898 MB image and capstone 5.0.9 (in the uv venv volume, not the image), and the 7 hand boundary verdicts. Follow-ups: backlog 999.3 (`asm` `_Alphabet` collision, Phase 6) and 999.2 (readlint must reject `func_`/`D_` placeholders, Phase 7)
- [Phase 06]: 06-27 pilot result (D-37): owner run 20261026-005209 reached 3 MATCHED in 40 sessions: ufo2p func_0008A0E0 (c83cf4e), tacp func_0006EE30 (d288ad6) and ufo2p func_0008A100 (955931f), so 2 UFO2P + 1 TACP, about USD 14 per match. The gate re-checked it independently: each match commit was re-gated in the container (gate --all exit 0, both SHA-1s identical), the final tree passed from clean (ninja verify and gate --all exit 0), the drift and schema tests passed, and no guardrail record was found. All three matches hold under the `*` default; the sweeps leave 10.5/10.6/11.0 and -4r/-5r tied (docs/toolchain.md Phase 6 match evidence)
- [Phase 06]: Owner ruling 2026-10-26: the PARTIAL pilot is accepted. AGT-11 = partial, owner-accepted 2026-10-26 (3/10), and the 10-match target carries to Phase 7. AGT-11 is not marked complete in REQUIREMENTS.md

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 4]: RESOLVED 2026-10-19: Watcom 10.5, 10.6 and 11.0 media are supplied in gitignored `third_party/watcom-media/` (archive.org items Watcom_C_10.5/10.6/11.0; ISO SHA-1s 0722e749…, 211f4e7a…, 1708a29f…, re-checked in this session). Extracted trees go to `third_party/watcom/<ver>/`. RESOLVED 2026-10-21 (04-03/04-06/04-11): install-watcom 10.5 decodes the real BINW/WCC386.EXE from DISKIMGS PCK00017.1/.2 and config/watcom.toml pins it; the main checkout was migrated with --force
- [Phase 4]: For 10.5/10.6, `BINNT\WCC386.EXE` is a 9,216-byte Win32 loader for the LX compiler `BINW\WCC386.EXE`, so the layout needs `binw/` as well as `binnt/`; 11.0's BINNT is native (WCC386.EXE + WCCD386.DLL) (reported by session reverseapoc-f2 on 2026-10-19; CONFIRMED 2026-10-21 by spike 004: the loader opens ..\BINW\WCC386.EXE itself)
- [Phase 5]: RESOLVED 2026-10-24: clang 18 (`clang-18=1:18.1.3-1ubuntu1`, `clang=1:18.0-59~exp2`) is in the Docker image and runs the `reverseapoc lint` gate (05-12); capstone 5.0.9 py3-none wheels work on Python 3.14 (05-03); both re-proven by gate plan 05-20 (container lint and test_lint.py unskipped)
- [Phase 6]: Repo visibility must be settled before Pages and listings (Pages on a private repo needs a paid plan)
- [Cross-cutting]: OpenApoc offsets describe the CD v1.00 build (UFO2P CRC32 `0x4749ffc1`); re-locate before reuse
- [Cross-cutting]: RESOLVED 2026-10-21: docs/toolchain.md and docs/learnings.md now say the installed UFO2P.EXE/TACP.EXE are the disc's `UFO2P4.EXE`/`TACP4.EXE` build (spike 003), not a store patch

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 261026-9uc | Progress badges and mosaic labels: README Progress section shows two per-EXE shields (UFO2P.EXE, TACP.EXE; tools/progress.py writes one shields.io endpoint JSON per EXE, combined progress-shield.json stays published) and progress.svg draws a label on each large unit (game unit = unit name, library unit = its largest runtime function name; no label on small squares; deterministic bytes; tooltips kept). Brief: .superpowers/sdd/let-s-work-on-phase-effervescent-nebula/progress-visuals-brief.md. TDD. | 2026-10-26 | 058389b | — | .planning/quick/261026-9uc-progress-badges-and-mosaic-labels-readme-progress-section-sh |
| 261026-9ue | Drive timestamps: prefix every `drive:` console line and each attempt's start and finish line printed by `reverseapoc drive` with local time [HH:MM:SS] through an injectable clock seam; exit codes and --json (exactly one document) unchanged. TDD. | 2026-10-26 | def199b | — | .planning/quick/261026-9ue-drive-timestamps-prefix-every-drive-console-line-and-each-at |
| 261026-9ud | Progress page: new progress.html written by tools/progress.py and published by .github/workflows/pages.yml, linked from the README; per-EXE percent bar plus a one-tick-per-function strip and the labelled mosaic inline, design plan in the brief (system font, existing palette, dark scheme, no JavaScript, deterministic). Depends on the badges-and-labels task (same file tools/progress.py). TDD. | 2026-10-26 | 7cee997 | — | .planning/quick/261026-9ud-progress-page-new-progress-html-written-by-tools-progress-py |

### Roadmap Evolution

- Phase 7 added: Mechanics-first decompilation (owner decision 2026-10-21; DEC-01..06)
- Phase 8 added: Clean-room specs for OpenApoc (owner decision 2026-10-21; SPEC-01..09, CC0-1.0, OpenSpec format)

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| Phase 6 carry-in | DI-01..DI-37, the items carried into Phase 6 from Phases 1-5 and the owner's 2026-10-24 additions; one row each, with the closing commit or ruling, in [06-DEFERRED-LEDGER.md](phases/06-reporting-and-agent-pilot/06-DEFERRED-LEDGER.md) | every row closed or ruled; checked by the 06-27 phase gate (03b63e2) | 2026-10-24 (Phase 6 discuss) | v1.0 |

## Session Continuity

Last session: 2026-10-24T22:21:38.486Z
Stopped at: Phase 6 context gathered
Resume file: .planning/phases/06-reporting-and-agent-pilot/06-CONTEXT.md
