---
gsd_state_version: "1.0"
milestone: v1.0
milestone_name: Milestone 1
current_phase: 3
current_phase_name: Byte-identical round trip
status: planning
stopped_at: Phase 3 context gathered
last_updated: "2026-10-20T15:13:24.876Z"
last_activity: 2026-10-20
last_activity_desc: Phase 2 complete, transitioned to Phase 3
state_head: 95bb8065480921eed7619b552f86867ea2fab3ce
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 4
  completed_plans: 4
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-20)

**Core value:** Every match is proven by a deterministic oracle (rebuilt EXE SHA-1 identical to the original, objdiff 100% for the function), never by an agent's own judgement.
**Current focus:** Phase 3 - Byte-identical round trip

## Current Position

Phase: 3 of 6 (Byte-identical round trip)
Plan: Not started
Status: Ready to plan
Last activity: 2026-10-20 — Phase 2 complete, transitioned to Phase 3

Progress: [███░░░░░░░] 33%

Next steps:
1. Phases 1-2 complete (retroactive VERIFICATION.md passed, UAT passed by the owner on 2026-10-19/20).
2. Phase 3: `/gsd-discuss-phase 3`, then `/gsd-plan-phase 3`, then `/gsd-spike` (LE edge cases; 27-byte trailer), then `/gsd-execute-phase 3` and `/gsd-verify-work 3`.

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 2 | - | - |
| 2 | 2 | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Phase structure fixed by the owner in `docs/workflow.md`; Milestone 1 phases are numbered 1-6
- [Roadmap]: A phase is complete only when its `VERIFICATION.md` passes; ROADMAP checkboxes are annotations
- [Phase 3]: In-place page splice for the MVP; full LE rewrite deferred (reopen trigger: a matched function changes size)
- [Phase 5]: Hybrid pipeline (own oracle + decomp.wtf fork mode) vs fallback is decided by the objdiff-on-converted-ELF spike
- [Phase 4]: Watcom 10.6 (10.5 equivalent) is the hypothesis; Open Watcom only for `wdis`/`wlink`/`wlib`

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 3]: `docs/toolchain.md` still says "page data runs exactly to EOF"; both EXEs carry a 27-byte trailer after the last LE page and 14/11 page-straddling fixups
- [Phase 4]: RESOLVED 2026-10-19: Watcom 10.5, 10.6 and 11.0 media are supplied in gitignored `third_party/watcom-media/` (archive.org items Watcom_C_10.5/10.6/11.0; ISO SHA-1s 0722e749…, 211f4e7a…, 1708a29f…, re-checked in this session). Extracted trees go to `third_party/watcom/<ver>/`. Still open: the 10.5 `BINW/WCC386.EXE` is a damaged 64 KiB stub (the real one is in DISKIMGS PCK00017.1/.2); hash every compiler binary
- [Phase 4]: For 10.5/10.6, `BINNT\WCC386.EXE` is a 9,216-byte Win32 loader for the LE compiler `BINW\WCC386.EXE`, so the layout needs `binw/` as well as `binnt/`; 11.0's BINNT is native (WCC386.EXE + WCCD386.DLL) (reported by session reverseapoc-f2 on 2026-10-19, to confirm in Phase 4)
- [Phase 5]: `clang` (C89 lint gate) is missing from the Docker image; capstone cp314 wheels are unverified
- [Phase 6]: Repo visibility must be settled before Pages and listings (Pages on a private repo needs a paid plan)
- [Cross-cutting]: OpenApoc offsets describe the CD v1.00 build (UFO2P CRC32 `0x4749ffc1`); re-locate before reuse

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-20T15:13:24.463Z
Stopped at: Phase 3 context gathered
Resume file: .planning/phases/03-byte-identical-round-trip/03-CONTEXT.md
