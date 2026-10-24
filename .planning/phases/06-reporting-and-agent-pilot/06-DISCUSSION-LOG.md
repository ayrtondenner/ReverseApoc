# Phase 6: Reporting and agent pilot - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-24
**Phase:** 06-reporting-and-agent-pilot
**Mode:** `--batch` (questions asked up to 4 at a time). A read-only scouting agent prepared each question's options, recommendation and evidence beforehand in `.superpowers/sdd/let-s-work-on-phase-effervescent-nebula/discuss-brief.md`.
**Areas discussed:** the owner picked all 12. Decomp.wtf spike; Driver and session launch; Scorer and pilot picks; Context pack; Hooks and pragma policy; Status table and attempt log; Zero-regression gate and commits; watcom-decomp skill; Progress, Pages and report; Pilot run settings; Deferred grouping and rulings; Owner-only items.

## Decided before the discussion (during session planning)

| Question | Options | Owner's choice |
|---|---|---|
| How does the discussion reach the owner? | Batched questions in the main session / recommended defaults reviewed after / `--power` HTML form | Batched questions |
| Which deferred items go into Phase 6? | Phase 6 targets and driver blockers / small cleanups / paperwork / 999.2 wording now (multi-select) | All four |
| Who starts the AGT-11 pilot? | The owner (execution stops at a checkpoint) / the executor, capped | The owner |
| Repo visibility | Decide in discussion / go public in Phase 6 / stay private | The owner made the repo **public** during planning |
| Other listings (multi-select) | AI-tolerant awesome-lists / DecompHub progress feed / GitHub topics / decomp.me msdos preset | All four |
| When is DecompHub submitted? | Now, before Phase 6 / after Pages is live | Now. Submitted by the owner, pending review |

Facts checked during the session (read-only):
- `gh repo view` reports visibility PUBLIC.
- decomp.dev disabled its index and new submissions on 2026-10-14.
- Rebuild Atlas (labs.parkrelics.com) is an unofficial copy of decomp.dev's old directory, with no way to submit and no DOS entries.
- decomp.me has a `msdos` platform with a `wcc10.6` compiler and no msdos presets yet. Its FAQ forbids LLM or automated access.
- DecompHub's progress-v1 schema and its refresh endpoint.
- The fork-mode mismatches in decomp.wtf v0.10.6: the stub regex, the linker-name lookup and the build environment.
- Nigel has no licence.
- The host Claude CLI is 2.1.240.

---

## 1. Decomp.wtf spike

| Question | Option | Selected |
|---|---|---|
| 1.1 How is the spike run? | Code evidence plus a half-day smoke run | ✓ |
| | Code evidence only | |
| | Full one-day spike with patches and a WSL2 toolchain | |
| 1.2 Verdict criteria | As Phase 5's D-02 (PARTIAL means at most ~50 lines of patches) | ✓ |
| | Any patch means INVALIDATED | |
| | Change our marker first | |
| 1.3 Patch decomp.wtf if PARTIAL? | No: our own layer for the pilot, re-evaluate in Phase 7 | ✓ |
| | Yes, with a pinned patch file | |
| 1.4 The fallback "minimal own agent layer" | Driver + hooks + Bash allowlist | |
| | **Plus a stdlib stdio MCP server, so agents get no shell** | ✓ (not the recommendation) |
| | Plus MCP + SQLite claims | |

## 2. Driver and session launch

| Question | Option | Selected |
|---|---|---|
| 2.1 Nigel or our own driver? | Our own stdlib Python driver | ✓ |
| | Nigel | |
| 2.2 Session launch | dontAsk + tool allowlist + `--setting-sources project` + a driver settings file | ✓ |
| | `--permission-mode auto` | |
| | `--bare` + an API key | |
| 2.3 Attempt caps | 3 sessions per function per pass | ✓ |
| | 4 | |
| | 5 | |
| 2.4 Plan tier for the night cap | **Max 20x** (30 sessions or 10 MATCHED) | ✓ |
| | Max 5x | |
| | Pro | |
| | API key billing | |

## 3. Scorer and pilot picks

| Question | Option | Selected |
|---|---|---|
| 3.1 What does "easy" mean? | P16 + skip matched, capped and partial-this-pass | ✓ |
| | Also admit pure leaf functions | |
| | New features + weights | |
| 3.2 The pilot's 10 | 5+5 with the variety rule (≤2 per unit, ≤3 per 64 KiB region) | ✓ |
| | 5+5 easiest-first | |
| | Global easiest-first | |

## 4. Context pack

| Question | Option | Selected |
|---|---|---|
| 4.1 Contents | Core items + up to 3 matched look-alikes | ✓ |
| | Core only | |
| | Core without the Ghidra draft | |
| 4.2 Size, location, GhidraMCP | 24 KB cap, gitignored build/driver/, no GhidraMCP | ✓ |
| | No cap | |
| | Add GhidraMCP | |

## 5. Hooks and pragma policy

| Question | Option | Selected |
|---|---|---|
| 6.1 Hook language and location | Stdlib Python in tools/reverseapoc/hooks.py | ✓ |
| | Node, like the GSD hooks | |
| | Python under .claude/hooks/ | |
| 6.2 When the hooks are active | Two layers: always-on + matching-session only | ✓ |
| | Everything always on | |
| | Driver sessions only | |
| 6.3 Matching-session rules | Deny-by-default allowlist, `--sweep` allowed as a diagnostic | ✓ |
| | Allowlist without sweep | |
| | Blocklist | |
| 5.1 Pragma policy | No `#pragma aux` of any kind in agent edits | ✓ |
| | Calling-convention pragmas allowed in include/ | |

## 6. watcom-decomp skill

| Question | Option | Selected |
|---|---|---|
| 5.2 Skill contents and upkeep | Short (≤300 lines) and checked by a test | ✓ |
| | Long, copying docs/ | |

**Owner's note:** "also invoke superpowers /writing-skills when writing the skill".

## 7. Status table and attempt log

| Question | Option | Selected |
|---|---|---|
| 7.1 Path and format | Sparse `config/<exe>/status.csv` | ✓ |
| | One full progress/status.csv | |
| 7.2/7.3 Writer and CI drift check | `gate` verb + drift test (rows vs src/, source hash, derived outputs) | ✓ |
| | The driver writes it directly | |
| | Format check only in CI | |
| 7.4 Outcome log | Committed `progress/attempts.jsonl`, no game bytes | ✓ |
| | All gitignored | |

## 8. Zero-regression gate and commits

| Question | Option | Selected |
|---|---|---|
| 9.1 What runs and where | `gate` before each commit, in the container, with the status.csv cross-check; `ninja verify` + `gate --all` at the end of each run | ✓ |
| | Also a pre-commit hook | |
| 9.2 Commit format | `feat(<exe>): match func_X in u_Y (C89)`, stats in the body, explicit trailers | ✓ |
| | `feat(06-NN): match ...` | |

## 9. Progress, Pages and report

| Question | Option | Selected |
|---|---|---|
| 8.1 What is measured | Bytes, with the runtime library shown apart | ✓ |
| | Function counts | |
| 8.2 Pages deploy | Actions deploy (push + weekly) | ✓ |
| | gh-pages branch | |
| 8.3 report.json source and artifact | One combined artifact `X-COM_Apocalypse_DOS_report`, built in CI | ✓ |
| | Two per-EXE artifacts | |
| | objdiff-cli, committed | |
| 8.4 DecompHub feed | Committed, no POST | |
| | **Committed + a CI POST to the refresh endpoint** (owner's OK for the outward-facing call) | ✓ (not the recommendation) |
| | Pages-hosted only | |

## 10. Pilot run settings

| Question | Option | Selected |
|---|---|---|
| 10.1 Where the driver runs | Windows host, main checkout, via docker compose | ✓ |
| | A dedicated second clone | |
| 10.2 Model | Opus pinned | ✓, with a change (below) |
| | Sonnet for attempts 1-2, Opus for the 3rd | |
| | Sonnet only | |
| 10.3 Claude CLI | Upgrade and pin before the pilot | ✓ |
| | Stay on 2.1.240 | |
| 10.4 Done criterion | 10 MATCHED in one run, ceiling of 40 sessions | ✓ |
| | 10 over several runs | |

**Owner's choice for 10.2 (free text):** "Opus latest (5.5 as of now) pinned", recorded as `claude-opus-5-5`.

## 11. Deferred grouping and rulings

| Question | Option | Selected |
|---|---|---|
| 11.1 Plan grouping | Accept the 16-plan, 4-wave map | ✓ |
| | Fewer, larger plans | |
| | Deferred items as their own first wave | |
| 11.2 DI-02/DI-03 | Implement jump tables and statics now | ✓ |
| | Document only, carry to Phase 7 | |
| 11.3 DI-24 | Count the uncovered code as unmatched now | ✓ |
| | Re-run discovery now | |
| 11.4 Small rulings (DI-18, DI-21, DI-09, DI-26/27/29) | Accept all | ✓ |
| | Accept with changes | |

## 12. Owner-only items

| Question | Option | Selected |
|---|---|---|
| 12.1 DI-32: primary build | The installed build, CD v1.00 for cross-reference | ✓ |
| | Switch to CD v1.00 | |
| | Add CD v1.00 as a second target | |
| 12.2 DI-33: config/watcom.toml:37 | The owner fixes it by hand | |
| | **Claude edits it once, recorded** | ✓ (not the recommendation) |

---

## Claude's Discretion

- The internal module layout of the driver, MCP server and progress.py.
- Verb names other than `drive` and `gate`.
- The treemap layout algorithm.
- The /goal prompt wording.
- The look-alike similarity metric.
- How the stand-in `claude` for the driver tests is built.
- Whether the MCP server runs in the container or on the host. Either way, `check` always runs in the container.

## Deferred Ideas

- SQLite claims for parallel agents, and re-evaluating decomp.wtf for that role (Phase 7).
- Scorer tuning (Phase 7).
- GhidraMCP (Later).
- A second clone for parallel runs (Phase 7).
- Twin matching of CD v1.00 (after Phase 7).
- Reddit, GBAtemp and decompals posts (later).
- readlint with the 999.2 rule (Phase 7).
