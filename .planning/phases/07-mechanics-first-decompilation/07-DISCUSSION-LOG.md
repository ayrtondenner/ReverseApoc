# Phase 7: Mechanics-first decompilation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-26
**Phase:** 07-mechanics-first-decompilation
**Mode:** default (one question per turn), run while plan mode was on. The decisions were held in the session plan file and written here after the owner approved it.
**Areas discussed:** the owner picked all four. Target list scope; Scale, budget and parallelism; Compiler-flag rulings; Readability and naming.

Facts gathered before the questions (read-only):
- OpenApoc #263, #264, #265 and #997 read through `gh issue view` (checklist text).
- `progress/attempts.jsonl` of pilot run 20261026-005209: 3 MATCHED in 40 sessions; sweep hits under `-ot`/`-oneatx`.
- `config/<exe>/functions.csv`: UFO2P 1,549 game + 4 thunk, TACP 1,519 game + 7 thunk functions.

**Correction:** the gray-area screen and the flags questions said "7 of the 9 functions that never matched" had a 100% sweep cell. A recount from the log gives 12 never-matched functions, 6 of them with a hit (plus func_0008A100, which had a hit and later matched under the default). CONTEXT.md carries the corrected figure. The owner's flag decisions do not depend on the exact count.

---

## Target list scope

| Question | Option | Selected |
|---|---|---|
| Which items are "answerable"? | Original-behaviour gaps (tooling/modding/UI chrome/OpenApoc-internal out) (recommended) | |
| | #997 and the open #263 items only | |
| | Everything that touches the original game, borderline items included | ✓ |
| How deep is "the functions behind an item"? | Call tree minus shared plumbing (recommended) | |
| | Full transitive call tree | ✓ |
| | Core function plus direct callees | |
| #997 spike time box | 1 day, decides the locate method (recommended) | ✓ |
| | Half a day | |
| | No time box, until found | |
| Ordering and sign-off | Tiers, #997 first, sign off per tier (recommended) | ✓ |
| | One full list, one sign-off | |
| | Ordered by OpenApoc impact | |

## Scale, budget and parallelism

Shown to the owner before the first question: about 3,080 game functions, 6 matched; at the pilot rate (~13 sessions, ~USD 14 per match) 2,000 functions would be ~26,000 sessions, ~USD 28k, ~870 nights at 30 sessions.

| Question | Option | Selected |
|---|---|---|
| What makes Phase 7 done? | Tier 1 matched, all tiers located; Tiers 2-4 continue in Milestone 2 (recommended) | ✓ |
| | Every listed function, as worded | |
| | A fixed budget, then stop | |
| Parallel agents and claims | One driver, N sessions, unit claims (recommended) | ✓ |
| | Several clones, shared SQLite claims store | |
| | Stay serial | |
| Concurrency and night cap | N=3, 60 sessions/night (recommended) | ✓ |
| | N=2, keep 30 sessions/night | |
| | N=4+, no night cap, budget only | |
| A Tier 1 function the driver cannot match | Escalate to a human-hints session (recommended) | |
| | Unlimited driver passes | ✓ |
| | Owner decides each one | |

**Owner's free-text addition (on "more questions or next area"):** keep starting attempts on Opus latest, but retry requeued functions with Fable latest as the stronger model for difficult, stuck functions.

| Question | Option | Selected |
|---|---|---|
| When does a function move from Opus to Fable? | After its first capped pass (recommended) | |
| | After two capped Opus passes | ✓ |
| | Alternate Opus and Fable passes | |
| Budget cap for Fable sessions | Separate, higher cap; the planner checks pricing and proposes the value (recommended) | ✓ |
| | Keep USD 5 for both | |

## Compiler-flag rulings

| Question | Option | Selected |
|---|---|---|
| How are flag rules decided? | Gate-proven per-unit proposals, owner batch-approves (recommended) | ✓ |
| | Driver lands gate-proven rules itself (revises Phase 5 D-18) | |
| | Keep per-hit owner review | |
| The pilot's sweep-hit functions | Early plan: re-prove and land them (recommended) | ✓ |
| | Let the driver redo them | |
| How the `*` default changes | Owner flips it on D-18 evidence, old matches pinned (recommended) | ✓ |
| | Never change the default | |
| Grow the sweep matrix? | Add a second-stage sweep for >= 90% misses (recommended) | ✓ |
| | Keep 30 cells | |

## Readability and naming

| Question | Option | Selected |
|---|---|---|
| When are names, comments, types and constants added? | Separate readability pass per tier (recommended) | ✓ |
| | Inside the matching attempt | |
| | Match first, name at the end | |
| Who writes the shared naming state? | Driver is the only writer; sessions write proposals (recommended) | ✓ |
| | Claimed sessions edit under a global naming lock | |
| readlint strictness | Strict with a small waiver allowlist (recommended) | ✓ |
| | Names and comments only | |
| | Strict, no waivers | |
| Name sources | Game evidence first, OpenApoc vocabulary allowed (recommended) | ✓ |
| | Game evidence only | |

---

## Claude's Discretion

- The mechanics.toml schema, the claims-file format, the flag-proposal and naming-proposal formats, module layout and new verb names.
- How the call trees are computed (Ghidra export, discovery call edges, relocation targets), including indirect calls.
- The per-item coverage view on the progress page, with backlog 999.4 folded into the same progress.py work.
- `stats` internals beyond the roadmap text (per-model and matching/readability splits, hook-block counts).
- Scorer and picker tuning (callees first inside a tier, jump-table and static functions admitted).
- The readability `/goal` prompt and whether its skill text is new or a `watcom-decomp` section (written with `superpowers:writing-skills` either way).

## Deferred Ideas

- Matching Tiers 2-4 to completion (Milestone 2, SEED-261025-3ga).
- A second clone or a multi-clone SQLite claims store; decomp.wtf (closed by spike 006).
- A human-hints escalation step for stuck functions (offered, not chosen).
- GhidraMCP; CD v1.00 twin matching; attributing the uncovered filler bytes.
