---
spike: 012
idea: night-economics
name: model-routing
type: comparison
validates: "Given one frozen list of 20 functions stratified by size (7 under 64 B, 7 at 64-255 B, 6 at 256 B and up), when every model arm runs them as a --hold drive (one attempt each, nothing lands until all arms finish) and --land-held lands each function once from the cheapest arm, then we know which model buys the most proven matched bytes per token and per dollar in each size bucket"
verdict: PARTIAL
related: [008, 010, 011]
tags: [model-routing, multi-arm, hold, land-held, codex, agy, openrouter, haiku, cost, quota, d-21, d-22]
---

# Spike 012: model routing

## What This Validates

Which models match Watcom C 10.6 functions, at what cost, by size: the Claude arms on the owner's
subscription (Haiku, Sonnet and Opus 5.5), GPT arms through the Codex CLI on ChatGPT Plus (GPT-6
Luna, GPT-6.1 Sol, GPT-6.1 Terra, GPT-6 Astra), Gemini 3.8 Flash and Claude 4.6 through the
Antigravity CLI (agy) on Google AI Plus, and open-weight models through OpenRouter (DeepSeek
V4.1-Flash, GLM-5.3, GLM-4.7-Flash, Qwen3.6-35B-A3B, Muse Spark Open). One frozen pick list
(`build/driver/spike012-picks.txt`, the 07.2 gate's stratified 20), one attempt per arm, held
until every arm finished, then landed once through the gate.

## Verdict

**PARTIAL.** The comparison is complete for 13 arms over the buckets each could afford, and 6 of
the 7 distinct functions any arm held exact landed through the gate (489 bytes; combined progress
0.5465% to 0.5808%). It is partial because quotas and canaries cut three arms short: Gemini Flash
ran 1 session (one session took 22% of its weekly agy quota), the two agy Claude 4.6 arms never
passed their canary before their weekly group ran low, and the Codex arms ran the 14 picks under
256 B only (ChatGPT Plus quota). GPT-OSS 120B never passed its canary.

The answer to the question:
1. **Under 64 B, the cheapest arms match what the strongest do.** Haiku 5.5 held 3 of 7, at
   $0.78 API-equivalent for its whole 20-pick run; Opus 5.5 also held 3, at $17.45.
2. **64-255 B is where arms separate, thinly.** Haiku held 2 (one, 176 B, only Haiku found, then
   failed the gate); Sonnet, Opus, DeepSeek, Sol, Terra and Astra held 1 each, the same 208 B
   `tacp func_00022140`, and GLM-5.3 held the 64 B `tacp func_00039E40` alone.
3. **Nothing at 256 B and up** matched on any arm that ran it.
4. So: route by size, cheapest first, escalate on failure (backlog 999.12).

## Results

Held exact per arm and bucket (`stats --run 'spike012-*'`, `build/gate/spike012/stats-final.txt`).
API-equivalent is tokens at each arm's public list price; real paid is 0 for subscription arms.
The Codex rows are recomputed here: `codexjson.usage` counts Codex's `input_tokens` (which
includes its cached tokens) as input and the cached tokens again as cache read, so `stats`
prices cached tokens twice for those arms (stats shows Astra $75.51, Sol $15.10, Terra $12.24,
Luna $0.51); the figures below price the cached part once.

| Arm | Picks | < 64 B | 64-255 B | 256 B+ | API-equiv $ | Real $ | Wall min | Match per check |
|---|---|---|---|---|---|---|---|---|
| Haiku 5.5 | 20 | 3 | 2 | 0 | 0.78 | 0 | 143 | 5.8% |
| Sonnet 5.5 | 20 | 4 | 1 | 0 | 9.51 | 0 | 128 | 7.4% |
| Opus 5.5 | 20 | 3 | 1 | 0 | 17.45 | 0 | 144 | 6.5% |
| GPT-6 Luna | 8 | 1 | 0 (1 run) | - | ~0.09 | 0 | 30 | 5.3% |
| GPT-6.1 Sol | 14 | 3 | 1 | - | ~1.96 | 0 | 43 | 13.8% |
| GPT-6.1 Terra | 14 | 3 | 1 | - | ~1.14 | 0 | 47 | 11.4% |
| GPT-6 Astra | 14 | 3 | 1 | - | ~11.75 | 0 | 46 | 13.8% |
| DeepSeek V4.1-Flash | 20 | 3 | 1 | 0 | 11.70 | 11.70* | 231 | 9.5% |
| GLM-5.3 | 20 | 3 | 1 | 0 | 4.27 | 4.27* | 281 | 7.5% |
| GLM-4.7-Flash | 20 | 1 | 0 | 0 | 1.24 | 1.24* | 203 | 2.8% |
| Qwen3.6-35B-A3B | 20 | 0 | 0 | 0 | 4.88 | 4.88* | 222 | 0% |
| Muse Spark Open | 11 | 2 | 0 | 0 | 48.44 | 48.44* | 71 | 25% of 8 |
| Gemini 3.8 Flash | 1 | 0 | - | - | 0.74 | 0 | 11 | (1 session) |

\* tokens at list price. OpenRouter's real total for the whole spike (canaries, the sessions the
429 bug discarded, every arm) was $53.10 of the owner's $100, against $70.53 listed for the
metered arms: the list price overstates what OpenRouter charged.

The 7 distinct functions held exact, all landed through `drive --land-held 'spike012-*'` except
the last (each match commit carries a Co-Authored-By line for every arm that held it):

| Function | Bytes | Arms that held it | Landed from |
|---|---|---|---|
| `tacp func_00022140` | 208 | 7 (Haiku, Sonnet, Opus, DeepSeek, Sol, Terra, Astra) | Haiku, dcd0844b |
| `tacp func_00039E40` | 64 | GLM-5.3 | GLM-5.3, 965d7cd6 |
| `tacp func_0009D110` | 45 | 9 | Haiku, 077e7885 |
| `tacp func_000A66A0` | 48 | 10 | Haiku, f6f3dd3d |
| `ufo2p func_00038510` | 61 | 9 | Haiku, 9dc95c98 |
| `ufo2p func_00038550` | 63 | Sonnet | Sonnet, 1aa59849 |
| `ufo2p func_0005DB80` | 176 | Haiku | refused by the gate (below) |

`gate --all` exits 0 with both SHA-1s identical after the landing (UFO2P 83 landed, TACP 62).

## Findings

- **A held match can still fail the gate.** Haiku's `func_0005DB80` is objdiff 100% with relocs
  and bytes OK (`gate --partial` agrees), but to get there it rewrote the unit's shared struct and
  turned the already-matched `func_0005E550` back into `INCLUDE_ASM`. `attempt check` judges the
  claimed function and the splice (bytes stay identical either way), so it passed; the gate
  re-checks every matched row of the unit and refused the regression. Follow-up: `attempt check`
  should flag a matched function of its unit that is no longer C.
- **Models fail the harness in their own ways**, which the canaries and the audit caught each
  time: Muse Spark sends file content as an object; Qwen invents a table of verdicts after two
  tool calls; GPT-OSS rewrites `..` paths and prefixes commands with `cd`; DeepSeek and GLM-5.3
  sometimes refuse a canary's probes; Luna ran `reverseapoc context` instead of the wrapper's
  `attempt context` (a stray, whole-drive stop by design; it then left the 64-255 B picks);
  Claude 4.6 through agy refuses `..` reads on its own.
- **Tool faults found and fixed during the spike** (each test-first, both suites and CI green):
  recovered OpenRouter 429s were set aside as usage limits (3b2e42e9); an output-token overrun
  stopped the drive (11ea0a4f, plus a 64000 cap for metered arms); the Codex sandbox refuses
  Docker and the wrapper ledger (a driver-side broker, 689ff384); Codex hands long commands back
  while they run (wait instruction, 390885e6); Codex splits `-c` keys on dots, dropping project
  trust for `gpt-6.1-*` runs (inline table, cc0b7bad); agy's `manage_task`, `schedule` and its
  own `.system_generated` output reads (cc87173b, efdb1b99, 226fb7d5).
- **Quotas are the binding constraint, not dollars.** One Gemini Flash session took 22% of its
  weekly agy group; two agy Claude 4.6 canaries took 63% of theirs; ChatGPT Plus ran about 0.5% of
  the week per small-pick session. Each arm pauses on its own (D-22), but a paused arm with queued
  picks keeps a drive open, so quota-bound arms get small pick lists.

## Follow-ups

- Backlog 999.12: a size-routed cascade (cheap arm first, escalate on failure), calibrated from
  the table above.
- Fix `codexjson.usage` to price Codex's cached tokens once (input minus cached as input), test
  first, then re-run `stats`.
- `attempt check` flags a unit regression (a matched function no longer C).
- After the agy weekly reset: Sonnet 4.6 then Opus 4.6 through agy (one canary each with the
  neutral probe wording), Gemini Flash re-canaried, on the 7 small picks.
- The Codex arms' 6 picks at 256 B and up, if Plus quota allows.

## Evidence

`build/gate/spike012/`: `results.txt` (every canary and drive line), `canary-*.log`,
`drive-run*.log`, `stats-final.txt`/`.json`, `gate-all-final.txt`, `land.log`/`land.err.log`,
`gate-0005db80-partial.txt`, `r*-host-pytest.txt` and `r*-container-pytest.txt`. Records:
`progress/attempts.jsonl` (`run` = `spike012-<arm>`). Debug sessions:
`.planning/debug/recovered-429-counted-as-limit.md`, `.planning/debug/codex-agy-arms-round5.md`.
