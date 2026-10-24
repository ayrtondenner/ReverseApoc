---
gsd_state_version: "1.0"
milestone: v1.0
milestone_name: Milestone 1
current_phase: 05
current_phase_name: Split and first matches
status: executing
stopped_at: Completed 05-12-PLAN.md
last_updated: "2026-10-24T02:09:30.263Z"
last_activity: 2026-10-23
last_activity_desc: Phase 05 execution started
state_head: 17017869190cd63520272c5a0e89138797da66c1
progress:
  total_phases: 8
  completed_phases: 4
  total_plans: 47
  completed_plans: 39
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-23)

**Core value:** Every match is proven by a deterministic oracle (rebuilt EXE SHA-1 identical to the original, objdiff 100% for the function), never by an agent's own judgement.
**Current focus:** Phase 05 — Split and first matches

## Current Position

Phase: 05 (Split and first matches) — EXECUTING
Plan: 13 of 20
Status: Ready to execute
Last activity: 2026-10-23 — Phase 05 execution started

Progress: [█████░░░░░] 50%

Next steps:
1. Phases 1-4 complete (Phase 4: VERIFICATION.md passed 26/26, UAT passed by the owner on 2026-10-23).
2. Phase 5: `/gsd-discuss-phase 5`, then `/gsd-plan-phase 5`, then `/gsd-execute-phase 5` and `/gsd-verify-work 5`.

## Performance Metrics

**Velocity:**
- Total plans completed: 27
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 2 | - | - |
| 2 | 2 | - | - |
| 3 | 10 | - | - |
| 04 | 13 | - | - |

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

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Phase structure fixed by the owner in `docs/workflow.md`; Milestone 1 phases are numbered 1-8 (Phases 7 and 8 added by the owner on 2026-10-21)
- [Roadmap]: A phase is complete only when its `VERIFICATION.md` passes; ROADMAP checkboxes are annotations
- [Phase 3]: In-place page splice for the MVP; full LE rewrite deferred (reopen trigger: a matched function changes size). Proven: three EXEs rebuild SHA-1 identical (Phase 3 gate)
- [Phase 5]: Hybrid pipeline (own oracle + decomp.wtf fork mode) vs fallback is decided by the objdiff-on-converted-ELF spike
- [Phase 04]: Game code: Watcom C 10.6 (10.5 byte-identical on the probe, 11.0 tied at -4r, candidate pending Phase 5 matches); linked runtime 10.6, no mix
- [Phase 04]: config/cflags.txt default is * wcc386@10.6 -4r -s -fpi (the flags the scans support); -s kept because only 40/32 functions call __CHK, which get per-glob rules in Phase 5
- [Phase 04]: Phase 4 gate green on host (974 passed, 6 platform-only skips) and container (980 passed, 0 skipped), ruff clean; rebuild SHA-1 identical; check-watcom OK; compiler/probe real tests pass under wibo
- [Phase 04]: cc.log appends are serialised by a stdlib OS lock on the sidecar <log>.lock (fcntl.flock / non-blocking msvcrt.locking retrying only on EACCES), released after the log closes; host and container on one log at once is unsupported (G-04-2)
- [Phase 04]: UAT 2026-10-23: owner re-tested G-04-2 (320 parallel compiles per environment, no lost line) and accepted the shipped `--log` behaviour; a docs note on a nameless or folder `--log` is backlog 999.1; review IN-08..IN-13 (info) left open in 04-REVIEW-DISPOSITION.md
- [Phase 05]: Spike 005 VALIDATED (D-02, D-19): objdiff-cli 3.8.2 scores the converted cmain386 OMF object at 100.0 for __CMain in both EXEs with only an address-to-name map; hybrid pipeline stays
- [Phase 05]: objdiff misses a wrong 2nd relocation of one instruction (100.0, spike 005 P3): the SPL-09 relocation check is the match gate; code sections are named _TEXT on both sides (a .text target is unpaired)
- [Phase 05]: 05-12: Ghidra 12.1.4 + LxLoader v12.1.4-1 (SHA-256 pinned), OpenJDK 21 and clang 18 are in the image; D-20 strip of docs/ and top-level Extensions/ kept (image 898,389,257 bytes)
- [Phase 05]: 05-12: Ghidra makes one one-address function in each EXE's data object (UFO2P 0x0013BD40, TACP 0x002B405C); reconcile (05-16) drops entries outside the code object

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 4]: RESOLVED 2026-10-19: Watcom 10.5, 10.6 and 11.0 media are supplied in gitignored `third_party/watcom-media/` (archive.org items Watcom_C_10.5/10.6/11.0; ISO SHA-1s 0722e749…, 211f4e7a…, 1708a29f…, re-checked in this session). Extracted trees go to `third_party/watcom/<ver>/`. RESOLVED 2026-10-21 (04-03/04-06/04-11): install-watcom 10.5 decodes the real BINW/WCC386.EXE from DISKIMGS PCK00017.1/.2 and config/watcom.toml pins it; the main checkout was migrated with --force
- [Phase 4]: For 10.5/10.6, `BINNT\WCC386.EXE` is a 9,216-byte Win32 loader for the LX compiler `BINW\WCC386.EXE`, so the layout needs `binw/` as well as `binnt/`; 11.0's BINNT is native (WCC386.EXE + WCCD386.DLL) (reported by session reverseapoc-f2 on 2026-10-19; CONFIRMED 2026-10-21 by spike 004: the loader opens ..\BINW\WCC386.EXE itself)
- [Phase 5]: RESOLVED 2026-10-24 (05-12): clang 18 (`clang-18=1:18.1.3-1ubuntu1`, `clang=1:18.0-59~exp2`) is in the Docker image and `reverseapoc lint` runs there; capstone 5.0.9 py3-none wheels verified in 05-03
- [Phase 6]: Repo visibility must be settled before Pages and listings (Pages on a private repo needs a paid plan)
- [Cross-cutting]: OpenApoc offsets describe the CD v1.00 build (UFO2P CRC32 `0x4749ffc1`); re-locate before reuse
- [Cross-cutting]: RESOLVED 2026-10-21: docs/toolchain.md and docs/learnings.md now say the installed UFO2P.EXE/TACP.EXE are the disc's `UFO2P4.EXE`/`TACP4.EXE` build (spike 003), not a store patch

### Roadmap Evolution

- Phase 7 added: Mechanics-first decompilation (owner decision 2026-10-21; DEC-01..06)
- Phase 8 added: Clean-room specs for OpenApoc (owner decision 2026-10-21; SPEC-01..09, CC0-1.0, OpenSpec format)

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-24T02:09:29.696Z
Stopped at: Completed 05-12-PLAN.md
Resume file: None
