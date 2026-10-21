---
gsd_state_version: "1.0"
milestone: v1.0
milestone_name: Milestone 1
current_phase: 4
current_phase_name: Compiler identification
status: planning
stopped_at: Phase 3 complete, ready to plan Phase 4
last_updated: "2026-10-21T11:40:30.316Z"
last_activity: 2026-10-21
last_activity_desc: Phase 3 complete, transitioned to Phase 4
state_head: 3222aecb88ad555603a623ccf9e8b20a6d862579
progress:
  total_phases: 6
  completed_phases: 3
  total_plans: 14
  completed_plans: 14
  percent: 50
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-21)

**Core value:** Every match is proven by a deterministic oracle (rebuilt EXE SHA-1 identical to the original, objdiff 100% for the function), never by an agent's own judgement.
**Current focus:** Phase 4 — Compiler identification

## Current Position

Phase: 4 — Compiler identification
Plan: Not started
Status: Ready to plan
Last activity: 2026-10-21 — Phase 3 complete, transitioned to Phase 4

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

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Phase structure fixed by the owner in `docs/workflow.md`; Milestone 1 phases are numbered 1-6
- [Roadmap]: A phase is complete only when its `VERIFICATION.md` passes; ROADMAP checkboxes are annotations
- [Phase 3]: In-place page splice for the MVP; full LE rewrite deferred (reopen trigger: a matched function changes size). Proven: three EXEs rebuild SHA-1 identical (Phase 3 gate)
- [Phase 5]: Hybrid pipeline (own oracle + decomp.wtf fork mode) vs fallback is decided by the objdiff-on-converted-ELF spike
- [Phase 4]: Watcom 10.6 (10.5 equivalent) is the hypothesis; Open Watcom only for `wdis`/`wlink`/`wlib`

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 4]: RESOLVED 2026-10-19: Watcom 10.5, 10.6 and 11.0 media are supplied in gitignored `third_party/watcom-media/` (archive.org items Watcom_C_10.5/10.6/11.0; ISO SHA-1s 0722e749…, 211f4e7a…, 1708a29f…, re-checked in this session). Extracted trees go to `third_party/watcom/<ver>/`. Still open: the 10.5 `BINW/WCC386.EXE` is a damaged 64 KiB stub (the real one is in DISKIMGS PCK00017.1/.2); hash every compiler binary
- [Phase 4]: For 10.5/10.6, `BINNT\WCC386.EXE` is a 9,216-byte Win32 loader for the LE compiler `BINW\WCC386.EXE`, so the layout needs `binw/` as well as `binnt/`; 11.0's BINNT is native (WCC386.EXE + WCCD386.DLL) (reported by session reverseapoc-f2 on 2026-10-19, to confirm in Phase 4)
- [Phase 5]: `clang` (C89 lint gate) is missing from the Docker image; capstone cp314 wheels are unverified
- [Phase 6]: Repo visibility must be settled before Pages and listings (Pages on a private repo needs a paid plan)
- [Cross-cutting]: OpenApoc offsets describe the CD v1.00 build (UFO2P CRC32 `0x4749ffc1`); re-locate before reuse
- [Cross-cutting]: Spike 003 found the installed UFO2P.EXE/TACP.EXE are byte-identical to the CD's `XCOM3/UFOEXE/UFO2P4.EXE`/`XCOM3/TACEXE/TACP4.EXE`; docs/toolchain.md "OpenApoc CRC mismatch" still says the store installers applied a later build. Owner decision pending on correcting it
- [Phase 5]: Close Phase 3 review findings WR-01 (layout() must refuse shared logical pages and overlapping objects; today a patch into the second owner is silently dropped and rebuild reports OK) and WR-03 (samefile guard against a hardlink into orig/, atomic write, single read of the input) before splice() lands real patches (owner triage 2026-10-20; .planning/phases/03-byte-identical-round-trip/03-REVIEW.md)
- [Phase 6]: Close Phase 3 review finding WR-04 (rebuild --json must always print, with a per-target error status, so the driver never loses results) (owner triage 2026-10-20)
- [Phase 5]: Close Phase 3 review findings WR-08 (refuse last_page_size > page_size when the LE is read and handle the no-page case, so a malformed header can never make splice() raise a raw TypeError; a regression from plan 03-08) and IN-12 (carry --orig/--manifest into the REFUSED/MISSING check-orig and ingest hints) before Phase 5 patches flow through splice() (owner triage 2026-10-21)

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-10-21
Stopped at: Phase 3 complete, ready to plan Phase 4
Resume file: None
