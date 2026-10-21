---
gsd_state_version: "1.0"
milestone: v1.0
milestone_name: Milestone 1
current_phase: 04
current_phase_name: Compiler identification
status: executing
stopped_at: Completed 04-11-PLAN.md
last_updated: "2026-10-21T20:48:46.238Z"
last_activity: 2026-10-21
last_activity_desc: Completed 04-11
state_head: e724a56501a8c34ba9fa10447da6b5083e9c42ed
progress:
  total_phases: 8
  completed_phases: 3
  total_plans: 26
  completed_plans: 25
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-21)

**Core value:** Every match is proven by a deterministic oracle (rebuilt EXE SHA-1 identical to the original, objdiff 100% for the function), never by an agent's own judgement.
**Current focus:** Phase 04 — Compiler identification

## Current Position

Phase: 04 (Compiler identification) — EXECUTING
Plan: 12 of 12 (04-11 complete; 04-12, the phase gate, is next)
Status: Ready to execute
Last activity: 2026-10-21 — Completed 04-11 (D-03 normalized equal for 10.5/10.6/11.0; toolchain.md records 10.6, -4r -s -fpi)

Progress: [█████░░░░░] 50%

Next steps:
1. Phases 1-3 complete (Phase 3: VERIFICATION.md passed 87/87, UAT passed by the owner on 2026-10-21).
2. Phase 4: `/gsd-discuss-phase 4`, then `/gsd-plan-phase 4`, then `/gsd-execute-phase 4` and `/gsd-verify-work 4`.

## Performance Metrics

**Velocity:**
- Total plans completed: 14
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 2 | - | - |
| 2 | 2 | - | - |
| 3 | 10 | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 04 P11 | 24min | 3 tasks | 8 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Phase structure fixed by the owner in `docs/workflow.md`; Milestone 1 phases are numbered 1-8 (Phases 7 and 8 added by the owner on 2026-10-21)
- [Roadmap]: A phase is complete only when its `VERIFICATION.md` passes; ROADMAP checkboxes are annotations
- [Phase 3]: In-place page splice for the MVP; full LE rewrite deferred (reopen trigger: a matched function changes size). Proven: three EXEs rebuild SHA-1 identical (Phase 3 gate)
- [Phase 5]: Hybrid pipeline (own oracle + decomp.wtf fork mode) vs fallback is decided by the objdiff-on-converted-ELF spike
- [Phase 4]: Watcom 10.6 (10.5 equivalent) is the hypothesis; Open Watcom only for `wdis`/`wlink`/`wlib`
- [Phase 04]: Game code: Watcom C 10.6 (10.5 byte-identical on the probe, 11.0 tied at -4r, candidate pending Phase 5 matches); linked runtime 10.6, no mix
- [Phase 04]: config/cflags.txt default is * wcc386@10.6 -4r -s -fpi (proven flags only); -s kept because only 40/32 functions call __CHK, which get per-glob rules in Phase 5

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 4]: RESOLVED 2026-10-19: Watcom 10.5, 10.6 and 11.0 media are supplied in gitignored `third_party/watcom-media/` (archive.org items Watcom_C_10.5/10.6/11.0; ISO SHA-1s 0722e749…, 211f4e7a…, 1708a29f…, re-checked in this session). Extracted trees go to `third_party/watcom/<ver>/`. RESOLVED 2026-10-21 (04-03/04-06/04-11): install-watcom 10.5 decodes the real BINW/WCC386.EXE from DISKIMGS PCK00017.1/.2 and config/watcom.toml pins it; the main checkout was migrated with --force
- [Phase 4]: For 10.5/10.6, `BINNT\WCC386.EXE` is a 9,216-byte Win32 loader for the LE compiler `BINW\WCC386.EXE`, so the layout needs `binw/` as well as `binnt/`; 11.0's BINNT is native (WCC386.EXE + WCCD386.DLL) (reported by session reverseapoc-f2 on 2026-10-19; CONFIRMED 2026-10-21 by spike 004: the loader opens ..\BINW\WCC386.EXE itself)
- [Phase 5]: `clang` (C89 lint gate) is missing from the Docker image; capstone cp314 wheels are unverified
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

Last session: 2026-10-21T20:48:45.834Z
Stopped at: Completed 04-11-PLAN.md
Resume file: None
