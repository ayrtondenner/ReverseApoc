---
id: SEED-261025-os5
status: dormant
planted: 2026-10-25
planted_during: Milestone 1, Phase 6 (Reporting and agent pilot)
trigger_when: planning Milestone 2 (owner priority, because it is the first deliverable OpenApoc can review)
scope: medium
---

# SEED-261025-os5: Pilot spec for OpenApoc #997 (tick rate and training) reaches `dosbox-verified` and is reviewed by OpenApoc

## Why This Matters

The owner marked this a priority on 2026-10-25 because it is the item that is for OpenApoc. #997 blocks fixes in OpenApoc #263 and #264. JonnyH calls #997 a meta issue: the accumulation of extracted values whose meaning nobody knows. A community claim (OpenApoc Discord, 2026-02) says the original ran at 36 ticks per second while parts of OpenApoc assume 144. That claim is still unverified.

## What Milestone 1 Already Covers

- **Phase 7:** a spike locates the #997 tick-rate and training code, and the mechanics list includes #997.
- **Phase 8:** the #997 spec reaches at least `backed-by-matched-code`.
- **Phase 8, SPEC-07:** the wiki claim inventory. This is the "wiki claim inventory" item from the original 7-12 proposal.

## What Is Left For Milestone 2

1. **`dosbox-verified`.** It needs the differential harness ([[SEED-261025-hft]]).
2. **OpenApoc review (`reviewed-by-openapoc`).** It needs contact with OpenApoc, which is out of scope in Milestone 1 (owner decision 2026-10-21). The contact opens with the owner's own posts when Milestone 1 ends.

There is no "agree terms with OpenApoc" step (owner, 2026-10-25). We write the specs in the format that makes sense to us, since both projects are open source. If OpenApoc raises concerns about the format, the owner says so and we update the specs then.

## When to Surface

**Trigger:** planning Milestone 2. This is Track B, step B2 of the layout in [[SEED-261025-l4y]]. It needs only the #997 functions matched in Phase 7 and the harness, not the full decomp ([[SEED-261025-3ga]]).

## Scope Estimate

**Medium.** One spec plus one harness, then a review round trip with OpenApoc maintainers.

## Breadcrumbs

- `.planning/ROADMAP.md`: the Phase 7 spike and Phase 8 SPEC-01 status ladder (`drafted -> cited -> backed-by-matched-code -> dosbox-verified -> reviewed-by-openapoc`).
- `docs/clean-room.md`: the author/implementer split and conduct towards OpenApoc.
- OpenApoc #997, and PR #1688 (tick-rate constants), open at the time of planting.
