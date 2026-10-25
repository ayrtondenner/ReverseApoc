---
id: SEED-261025-8ob
status: dormant
planted: 2026-10-25
planted_during: Milestone 1, Phase 6 (Reporting and agent pilot)
trigger_when: Milestone 2, when the full decomp ([[SEED-261025-3ga]]) reaches 100%
scope: medium
---

# SEED-261025-8ob: After 100%, sweep specs, findings and docs for updates

## Why This Matters

The owner asked for this on 2026-10-25. Some claims can only be closed with full coverage. Examples:
- an item has no effect anywhere (the Alien Detector, the Dimension Force Field);
- a research topic can never unlock (Live Overspawn);
- the "UFO CHEAT" / "TAC CHEAT" modes are beta-only (no plain "CHEAT" string was found in our EXEs on 2026-10-25).

Until then those entries read "not seen in the code matched so far".

## What to Sweep

- `specs/`: update every spec with what the full code shows. This includes the Learning AI spec ([[SEED-261025-o1r]]).
- `docs/findings/bugs.md`, `cut-content.md`, `cheats-and-easter-eggs.md` and `learning-ai.md` (Phase 8, SPEC-10):
  - close every "not seen in the code matched so far" note;
  - check every unreferenced string and table entry for cut content;
  - settle the cheat and debug-key questions.
- `specs/claims.md`: update the verdicts.
- Misc docs (`docs/learnings.md`, `docs/matching.md`, README): refresh where the full decomp changed what we know.

## When to Surface

**Trigger:** the full decomp reaches 100%.

## Scope Estimate

**Medium.** Mostly reading and writing, with some cross-reference queries.

## Breadcrumbs

- `.planning/REQUIREMENTS.md`: SPEC-07 and SPEC-10.
- UFOpaedia "Cut items and features (Apocalypse)" (rev 117358) and "Cut items and creatures (Apocalypse)" (rev 127437).
- TCRF https://tcrf.net/X-COM:_Apocalypse (not readable by the agent on 2026-10-25; read it by hand).
