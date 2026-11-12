# Model comparison

This page compares models and providers on our matching task: write Watcom C 10.6 that compiles
to the original bytes of one function. It is a living document. Each comparison gets its own
dated section, and the numbers in a section never change after it is written; a later run gets a
new section. How the harnesses work is in [model-routing.md](model-routing.md); this page holds
only what they measured.

## How to read it

- **One attempt per arm.** Every arm ran each pick once, under `--hold`, so a function is one
  try per model, not a match rate. Spike 012 had 20 picks: 7 under 64 B, 7 at 64-255 B and 6 at
  256 B and up. A gap of one function between two arms is within noise.
- **Held, landed and exact.** A held exact result is a session whose plain `attempt check`
  exited 0 in a hold run (`HOLD_EXACT`). Nothing lands during a hold run. `drive --land-held`
  then lands each function once, from the arm with the lowest API-equivalent cost, through the
  normal gate. A held result can still fail the gate (Haiku's `func_0005DB80` below). "Landed"
  here counts the functions an arm is credited with in the landing commits: the landing arm and
  every other arm that held the function exact. "Exact" in the `stats` columns is held exact or
  matched.
- **List price, not what was paid.** "API-equivalent $" is the arm's tokens at its public list
  price per million tokens (`config/driver/backends.toml` `prices`; the Claude arms use
  streamjson's table). Those prices are estimates read from public lists and marked "confirm
  at setup" in backends.toml. "Real paid $" is 0 on a subscription (the Claude Code login,
  ChatGPT Plus, Google AI Plus) and the API-equivalent on a metered arm (OpenRouter). For
  OpenRouter even that overstates the bill: the credits API showed less (see Quota).
- **The Codex double count.** `codexjson.usage` records Codex's `input_tokens`, which already
  include the cached tokens, as input, and `cached_input_tokens` again as cache read. So
  `stats` prices the Codex arms' cached tokens twice, and counts them twice in "per million
  tokens". The Codex rows show the `stats` figure and a recomputed one with the cached part
  counted once. The fault is still in the code (`tools/reverseapoc/codexjson.py`, `usage`).
- **Quota-cut arms.** Some arms ran fewer picks: Gemini 3.8 Flash ran 1 session, GPT-6 Luna 8,
  the other three Codex arms the 14 picks under 256 B only, and Muse Spark Open 11 before it was
  dropped. The two Claude 4.6 arms through agy and GPT-OSS 120B never passed a canary and ran
  nothing. Compare those arms per bucket, not by their totals.
- **Turns and wall time.** Turns are not comparable across harnesses: Codex reports one turn
  per session, and agy reported 1 for its one session. Wall time sums each session's own
  duration; arms ran in parallel, at 2 workers per Claude Code arm and 1 per Codex or agy arm.
  Two Qwen sessions were killed by the wall clock, so their time is the recorded seconds.
- **Per try.** The build failure, mismatch and match rates count the plain checks saved under
  `build/driver/<run>/.../checks.jsonl` (exit 2, 1 and 0). An arm with few checks (Muse's 8,
  Qwen's 7) has rates that say little.
- **Ratios.** "Exact per API $", "per wall hour" and "per million tokens" divide the exact
  functions by the API-equivalent dollars, the wall hours and all four token classes summed.
  A ratio of 0.00 with nothing exact is shown as a dash in the bucket tables.

Marks on figures: **(L)** a list-price estimate, **(S)** an owner screenshot reading,
**(R)** our recomputation from the `stats` token counts, **(D)** derived from the landing
commits' Co-Authored-By lines. Unmarked figures are read directly from the sources the section
names.

## Spike 012: model routing (2026-11-10 to 2026-11-11)

Sources: `reverseapoc stats --run 'spike012-*'` saved before the landing as
`build/gate/spike012/stats-final.txt` and `.json` (the "comparison per arm" block), the spike's
[README](../.planning/spikes/012-model-routing/README.md), and the orchestrator's facts brief of
2026-11-11 for quota readings and canary history. The landed credit (D) comes from the six
match commits the README names.

### The arms

| Arm | Model | Harness | Provider and billing | CLI |
|---|---|---|---|---|
| `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5` | Claude Haiku, Sonnet, Opus 5.5 | Claude Code | Anthropic, the owner's Claude subscription | Claude Code |
| `gpt-6-luna`, `gpt-6.1-sol`, `gpt-6.1-terra`, `gpt-6-astra` | GPT-6 Luna, GPT-6.1 Sol, GPT-6.1 Terra, GPT-6 Astra | Codex CLI, driver-side wrapper broker | OpenAI, the owner's ChatGPT Plus | codex 0.167.0 |
| `gemini-flash` | Gemini 3.8 Flash (medium) | Antigravity CLI (agy) | Google, the owner's Google AI Plus, "Gemini models" weekly group | agy 1.5.5, then 1.5.6 |
| `agy-sonnet-4-6`, `agy-opus-4-6` | Claude Sonnet 4.6, Opus 4.6 (Thinking) | agy | Google AI Plus, "Claude and GPT models" weekly group | agy 1.5.6 |
| `gpt-oss` | GPT-OSS 120B (medium) | agy | Google AI Plus, "Claude and GPT models" group | agy 1.5.5, 1.5.6 |
| `deepseek-flash`, `glm-5.3`, `glm-4.7-flash`, `qwen-hosted`, `muse-spark-open` | DeepSeek V4.1-Flash, GLM-5.3, GLM-4.7-Flash, Qwen3.6-35B-A3B, Muse Spark Open | Claude Code against OpenRouter's Anthropic-compatible endpoint | OpenRouter, metered (`OPENROUTER_API_KEY`, the owner's USD 100 credit) | Claude Code |

`gpt-oss-20b` (OpenRouter) and `qwen-local` were wired but never run in a drive.

### The drives

Every drive was `--hold --run spike012`, so each one resumed the last
([model-routing.md](model-routing.md#several-arms-in-one-drive)). The Claude Code arms ran the
frozen 20 picks at 2 workers each; the Codex and agy arms ran the 7 small picks
(`spike012-picks-small.txt`) and then the 7 medium ones (`-medium.txt`) at 1 worker each.

1. 2026-11-10, 8 arms (the three Claude arms and five OpenRouter arms): guardrail stop after 35
   sessions on Muse Spark's hook-denied write.
2. Resume 1, 8 arms: stopped by Ctrl+C on the owner's ruling after about 2 h, because
   recovered OpenRouter 429s were set aside as usage limits (11 sessions discarded, 7 with an
   exit-0 check); fixed in 3b2e42e9.
3. Resume 2, 7 arms (Muse out): stopped on a GLM-5.3 output overrun past 32,000 tokens; fixed in
   11ea0a4f, with a 64,000 output cap for metered arms.
4. Resume 3, the 4 OpenRouter arms left: ENDED clean; GLM-4.7-Flash's arm stopped on its last
   pick.
5. Round 5, Codex and agy: stopped on Codex `error` items (the dotted-key trust that Codex
   ignored for the `gpt-6.1-*` run dirs); fixed in cc0b7bad.
6. Small picks, 4 Codex arms and Gemini: stopped after 16 sessions on Gemini reading its own
   agy output files; allowed in 226fb7d5 (owner ruling).
7. Round 6, drive 1 (Codex, small picks): ENDED clean, 13 sessions. Drive 2 (Codex, medium
   picks): stopped on Luna's `uv run --frozen reverseapoc context`; resumed without Luna as
   drive 2b (Sol, Terra, Astra): ENDED clean, 18 sessions.
8. `drive --land-held 'spike012-*'`: 6 landed, 1 refused, end checks passed.

### Totals per arm

| Arm | Picks | Sessions | Held exact | Landed (D) | Landed bytes (D) | Turns | Wall min | API-equiv $ (L) | Real paid $ | Checks | Match per check | Exact per API $ | Per wall h | Per Mtok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Haiku 5.5 | 20 | 20 | 5 | 4 | 362 | 603 | 143.1 | 0.78 | 0 | 86 | 5.8% | 6.45 | 2.10 | 0.23 |
| Sonnet 5.5 | 20 | 20 | 5 | 5 | 425 | 501 | 128.1 | 9.51 | 0 | 68 | 7.4% | 0.53 | 2.34 | 0.33 |
| Opus 5.5 | 20 | 20 | 4 | 4 | 362 | 554 | 143.7 | 17.45 | 0 | 62 | 6.5% | 0.23 | 1.67 | 0.27 |
| GPT-6 Luna | 8 | 8 | 1 | 1 | 48 | 8 | 29.8 | 0.51 stats, 0.09 (R) | 0 | 19 | 5.3% | 1.98 stats, 11.10 (R) | 2.01 | 0.12 stats, 0.22 (R) |
| GPT-6.1 Sol | 14 | 14 | 4 | 4 | 362 | 14 | 42.7 | 15.10 stats, 1.96 (R) | 0 | 29 | 13.8% | 0.26 stats, 2.04 (R) | 5.62 | 0.29 stats, 0.57 (R) |
| GPT-6.1 Terra | 14 | 15 | 4 | 4 | 362 | 15 | 46.8 | 12.24 stats, 1.14 (R) | 0 | 35 | 11.4% | 0.33 stats, 3.51 (R) | 5.13 | 0.18 stats, 0.35 (R) |
| GPT-6 Astra | 14 | 14 | 4 | 4 | 362 | 14 | 46.1 | 75.51 stats, 11.75 (R) | 0 | 29 | 13.8% | 0.05 stats, 0.34 (R) | 5.20 | 0.30 stats, 0.59 (R) |
| Gemini 3.8 Flash | 1 | 1 | 0 | 0 | 0 | 1 | 11.2 | 0.74 | 0 | 3 | 33.3% | 0.00 | 0.00 | 0.00 |
| DeepSeek V4.1-Flash | 20 | 20 | 4 | 4 | 362 | 615 | 230.5 | 11.70 | 11.70 (L) | 42 | 9.5% | 0.34 | 1.04 | 0.11 |
| GLM-5.3 | 20 | 20 | 4 | 4 | 218 | 639 | 280.6 | 4.27 | 4.27 (L) | 53 | 7.5% | 0.94 | 0.86 | 0.11 |
| GLM-4.7-Flash | 20 | 20 | 1 | 1 | 48 | 757 | 203.2 | 1.24 | 1.24 (L) | 36 | 2.8% | 0.81 | 0.30 | 0.05 |
| Qwen3.6-35B-A3B | 20 | 21 | 0 | 0 | 0 | 725 | 221.6 | 4.88 | 4.88 (L) | 7 | 0.0% | 0.00 | 0.00 | 0.00 |
| Muse Spark Open | 11 | 11 | 2 | 2 | 106 | 470 | 70.7 | 48.44 | 48.44 (L) | 8 | 25.0% | 0.04 | 1.70 | 0.05 |

"Picks" is the distinct functions attempted; "Sessions" counts the attempt records (Terra and
Qwen redid one pick each). Gemini's one session logged a matching check (1 of 3), but it was the
session the small-picks drive stopped on, for reading its own agy output files, so it holds no
exact result. The run's totals over all arms: 204 sessions, 4,916 turns, $89.52 recorded cost
(the `per model` lines: the CLI's own figure on the Claude arms, 0 on Codex and agy, the
list-price estimate on OpenRouter).

### Tokens per arm

| Arm | Input | Output | Cache read | Cache creation | Total |
|---|---|---|---|---|---|
| Haiku 5.5 | 946 | 479,317 | 19,742,945 | 1,689,413 | 21.91 M |
| Sonnet 5.5 | 822 | 206,012 | 13,774,312 | 1,172,542 | 15.15 M |
| Opus 5.5 | 794 | 247,341 | 13,110,748 | 1,234,603 | 14.59 M |
| GPT-6 Luna | 4,404,199 | 46,840 | 4,152,960 | 0 | 8.60 M stats, 4.45 M (R) |
| GPT-6.1 Sol | 7,043,397 | 36,012 | 6,571,904 | 0 | 13.65 M stats, 7.08 M (R) |
| GPT-6.1 Terra | 11,470,226 | 43,419 | 11,102,336 | 0 | 22.62 M stats, 11.51 M (R) |
| GPT-6 Astra | 6,720,506 | 38,575 | 6,376,064 | 0 | 13.14 M stats, 6.76 M (R) |
| Gemini 3.8 Flash | 203,643 | 96,056 | 3,089,912 | 0 | 3.39 M |
| DeepSeek V4.1-Flash | 2,907,359 | 1,386,300 | 30,563,952 | 0 | 34.86 M |
| GLM-5.3 | 4,880,679 | 1,247,243 | 31,115,412 | 0 | 37.24 M |
| GLM-4.7-Flash | 18,777,052 | 221,914 | 65,543 | 0 | 19.06 M |
| Qwen3.6-35B-A3B | 11,764,278 | 1,132,413 | 26,807,584 | 0 | 39.70 M |
| Muse Spark Open | 3,099,023 | 226,544 | 34,883,232 | 0 | 38.21 M |

A Codex "Input" includes its "Cache read"; the recomputed total (R) is input plus output. Only
the Claude arms report cache creation; the Codex, agy and OpenRouter streams give none. On the
Claude login nearly all input arrives as cache reads, so "Input" there is tiny.

### Under 64 B (7 picks)

| Arm | Picks | Sessions | Held | Landed (D) | Turns | Wall min | Input | Output | Cache read | Cache creation | API-equiv $ (L) | Checks | Build fail | Mismatch | Match | Exact per API $ | Per wall h | Per Mtok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Haiku 5.5 | 7 | 7 | 3 | 3, 154 B | 156 | 37.4 | 244 | 94,603 | 3,787,031 | 434,891 | 0.17 | 19 | 0.0% | 84.2% | 15.8% | 17.42 | 4.81 | 0.69 |
| Sonnet 5.5 | 7 | 7 | 4 | 4, 217 B | 112 | 30.6 | 186 | 34,079 | 2,250,167 | 252,819 | 1.80 | 14 | 0.0% | 71.4% | 28.6% | 2.22 | 7.83 | 1.58 |
| Opus 5.5 | 7 | 7 | 3 | 3, 154 B | 111 | 31.5 | 186 | 35,802 | 2,242,802 | 257,687 | 3.23 | 12 | 0.0% | 75.0% | 25.0% | 0.93 | 5.71 | 1.18 |
| GPT-6 Luna | 7 | 7 | 1 | 1, 48 B | 7 | 25.0 | 3,526,216 | 38,779 | 3,315,200 | 0 | 0.41 stats, 0.07 (R) | 16 | 0.0% | 93.8% | 6.2% | 2.47 stats, 13.58 (R) | 2.40 | 0.15 stats, 0.28 (R) |
| GPT-6.1 Sol | 7 | 7 | 3 | 3, 154 B | 7 | 19.3 | 3,414,179 | 14,099 | 3,185,920 | 0 | 7.29 stats, 0.92 (R) | 10 | 0.0% | 70.0% | 30.0% | 0.41 stats, 3.27 (R) | 9.33 | 0.45 stats, 0.88 (R) |
| GPT-6.1 Terra | 7 | 7 | 3 | 3, 154 B | 7 | 18.5 | 4,851,410 | 15,280 | 4,694,656 | 0 | 5.16 stats, 0.47 (R) | 11 | 0.0% | 72.7% | 27.3% | 0.58 stats, 6.41 (R) | 9.72 | 0.31 stats, 0.62 (R) |
| GPT-6 Astra | 7 | 7 | 3 | 3, 154 B | 7 | 19.9 | 3,302,399 | 15,726 | 3,142,016 | 0 | 36.95 stats, 5.53 (R) | 10 | 0.0% | 70.0% | 30.0% | 0.08 stats, 0.54 (R) | 9.03 | 0.46 stats, 0.90 (R) |
| Gemini 3.8 Flash | 1 | 1 | 0 | 0 | 1 | 11.2 | 203,643 | 96,056 | 3,089,912 | 0 | 0.74 | 3 | 0.0% | 66.7% | 33.3% | - | - | - |
| DeepSeek V4.1-Flash | 7 | 7 | 3 | 3, 154 B | 171 | 56.9 | 783,026 | 322,902 | 7,398,536 | 0 | 2.84 | 12 | 0.0% | 75.0% | 25.0% | 1.06 | 3.17 | 0.35 |
| GLM-5.3 | 7 | 7 | 3 | 3, 154 B | 163 | 65.8 | 1,151,024 | 268,424 | 6,739,714 | 0 | 0.93 | 16 | 6.2% | 75.0% | 18.8% | 3.23 | 2.74 | 0.37 |
| GLM-4.7-Flash | 7 | 7 | 1 | 1, 48 B | 231 | 50.3 | 6,570,415 | 60,053 | 0 | 0 | 0.42 | 5 | 40.0% | 40.0% | 20.0% | 2.35 | 1.19 | 0.15 |
| Qwen3.6-35B-A3B | 7 | 8 | 0 | 0 | 269 | 68.3 | 4,497,300 | 303,106 | 9,928,000 | 0 | 1.72 | 2 | 0.0% | 100.0% | 0.0% | - | - | - |
| Muse Spark Open | 4 | 4 | 2 | 2, 106 B | 183 | 29.1 | 1,060,378 | 63,212 | 9,479,216 | 0 | 13.44 | 6 | 0.0% | 66.7% | 33.3% | 0.15 | 4.12 | 0.19 |

Real paid in this bucket: 0 on the subscription arms; DeepSeek $2.84, GLM-5.3 $0.93,
GLM-4.7-Flash $0.42, Qwen $1.72 and Muse $13.44 (L).

### 64 to 255 B (7 picks)

| Arm | Picks | Sessions | Held | Landed (D) | Turns | Wall min | Input | Output | Cache read | Cache creation | API-equiv $ (L) | Checks | Build fail | Mismatch | Match | Exact per API $ | Per wall h | Per Mtok |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Haiku 5.5 | 7 | 7 | 2 | 1, 208 B | 243 | 55.1 | 412 | 190,882 | 9,004,095 | 647,016 | 0.31 | 35 | 2.9% | 91.4% | 5.7% | 6.35 | 2.18 | 0.20 |
| Sonnet 5.5 | 7 | 7 | 1 | 1, 208 B | 197 | 52.8 | 342 | 95,993 | 6,237,609 | 510,211 | 4.25 | 28 | 0.0% | 96.4% | 3.6% | 0.24 | 1.14 | 0.15 |
| Opus 5.5 | 7 | 7 | 1 | 1, 208 B | 211 | 51.6 | 312 | 91,557 | 5,180,706 | 481,189 | 6.72 | 26 | 3.8% | 92.3% | 3.8% | 0.15 | 1.16 | 0.17 |
| GPT-6 Luna | 1 | 1 | 0 | 0 | 1 | 4.8 | 877,983 | 8,061 | 837,760 | 0 | 0.10 stats, 0.02 (R) | 3 | 0.0% | 100.0% | 0.0% | - | - | - |
| GPT-6.1 Sol | 7 | 7 | 1 | 1, 208 B | 7 | 23.4 | 3,629,218 | 21,913 | 3,385,984 | 0 | 7.82 stats, 1.04 (R) | 19 | 0.0% | 94.7% | 5.3% | 0.13 stats, 0.96 (R) | 2.57 | 0.14 stats, 0.27 (R) |
| GPT-6.1 Terra | 7 | 8 | 1 | 1, 208 B | 8 | 28.2 | 6,618,816 | 28,139 | 6,407,680 | 0 | 7.08 stats, 0.67 (R) | 24 | 0.0% | 95.8% | 4.2% | 0.14 stats, 1.49 (R) | 2.13 | 0.08 stats, 0.15 (R) |
| GPT-6 Astra | 7 | 7 | 1 | 1, 208 B | 7 | 26.2 | 3,418,107 | 22,849 | 3,234,048 | 0 | 38.56 stats, 6.22 (R) | 19 | 0.0% | 94.7% | 5.3% | 0.03 stats, 0.16 (R) | 2.29 | 0.15 stats, 0.29 (R) |
| DeepSeek V4.1-Flash | 7 | 7 | 1 | 1, 208 B | 229 | 79.2 | 1,037,383 | 457,059 | 10,814,714 | 0 | 4.10 | 18 | 0.0% | 94.4% | 5.6% | 0.24 | 0.76 | 0.08 |
| GLM-5.3 | 7 | 7 | 1 | 1, 64 B | 227 | 102.9 | 2,171,181 | 442,653 | 9,400,410 | 0 | 1.43 | 15 | 0.0% | 93.3% | 6.7% | 0.70 | 0.58 | 0.08 |
| GLM-4.7-Flash | 7 | 7 | 0 | 0 | 283 | 101.5 | 6,559,942 | 97,967 | 12,695 | 0 | 0.44 | 29 | 13.8% | 86.2% | 0.0% | - | - | - |
| Qwen3.6-35B-A3B | 7 | 7 | 0 | 0 | 267 | 88.8 | 3,717,111 | 463,580 | 9,878,976 | 0 | 1.78 | 5 | 20.0% | 80.0% | 0.0% | - | - | - |
| Muse Spark Open | 5 | 5 | 0 | 0 | 205 | 30.5 | 1,711,419 | 119,119 | 19,354,096 | 0 | 26.84 | 1 | 0.0% | 100.0% | 0.0% | - | - | - |

Gemini ran nothing here. Haiku's second hold is the 176 B `ufo2p func_0005DB80` that the gate
refused. GLM-5.3's is the 64 B `tacp func_00039E40`, which no other arm held; every other hold in
this bucket is the 208 B `tacp func_00022140`. Real paid: DeepSeek $4.10, GLM-5.3 $1.43,
GLM-4.7-Flash $0.44, Qwen $1.78, Muse $26.84 (L).

### 256 B and up (6 picks)

| Arm | Picks | Sessions | Held | Turns | Wall min | Input | Output | Cache read | Cache creation | API-equiv $ (L) | Checks | Build fail | Mismatch | Match |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Haiku 5.5 | 6 | 6 | 0 | 204 | 50.6 | 290 | 193,832 | 6,951,819 | 607,506 | 0.29 | 32 | 0.0% | 100.0% | 0.0% |
| Sonnet 5.5 | 6 | 6 | 0 | 192 | 44.7 | 294 | 75,940 | 5,286,536 | 409,512 | 3.46 | 26 | 0.0% | 100.0% | 0.0% |
| Opus 5.5 | 6 | 6 | 0 | 232 | 60.6 | 296 | 119,982 | 5,687,240 | 495,727 | 7.50 | 24 | 4.2% | 95.8% | 0.0% |
| DeepSeek V4.1-Flash | 6 | 6 | 0 | 215 | 94.4 | 1,086,950 | 606,339 | 12,350,702 | 0 | 4.76 | 12 | 0.0% | 100.0% | 0.0% |
| GLM-5.3 | 6 | 6 | 0 | 249 | 111.9 | 1,558,474 | 536,166 | 14,975,288 | 0 | 1.91 | 22 | 4.5% | 95.5% | 0.0% |
| GLM-4.7-Flash | 6 | 6 | 0 | 243 | 51.4 | 5,646,695 | 63,894 | 52,848 | 0 | 0.37 | 2 | 100.0% | 0.0% | 0.0% |
| Qwen3.6-35B-A3B | 6 | 6 | 0 | 189 | 64.4 | 3,549,867 | 365,727 | 7,000,608 | 0 | 1.38 | none saved | - | - | - |
| Muse Spark Open | 2 | 2 | 0 | 82 | 11.1 | 327,226 | 44,213 | 6,049,920 | 0 | 8.16 | 1 | 0.0% | 100.0% | 0.0% |

No arm held anything here, so every ratio is 0. The Codex and agy arms did not run this bucket
(quota). Real paid: DeepSeek $4.76, GLM-5.3 $1.91, GLM-4.7-Flash $0.37, Qwen $1.38, Muse $8.16
(L).

### What landed

`drive --land-held 'spike012-*'` landed 6 of the 7 distinct functions held exact, 489 bytes:

| Function | Bytes | Arms that held it | Landed from |
|---|---|---|---|
| `tacp func_00022140` | 208 | Haiku, Sonnet, Opus, DeepSeek, Sol, Terra, Astra | Haiku, dcd0844b |
| `tacp func_00039E40` | 64 | GLM-5.3 | GLM-5.3, 965d7cd6 |
| `tacp func_0009D110` | 45 | 9: Haiku, Opus, Sonnet, DeepSeek, GLM-5.3, Astra, Sol, Terra, Muse (D) | Haiku, 077e7885 |
| `tacp func_000A66A0` | 48 | 10: Haiku, Opus, Sonnet, DeepSeek, GLM-4.7-Flash, GLM-5.3, Astra, Luna, Sol, Terra (D) | Haiku, f6f3dd3d |
| `ufo2p func_00038510` | 61 | 9: Haiku, Opus, Sonnet, DeepSeek, GLM-5.3, Astra, Sol, Terra, Muse (D) | Haiku, 9dc95c98 |
| `ufo2p func_00038550` | 63 | Sonnet | Sonnet, 1aa59849 |
| `ufo2p func_0005DB80` | 176 | Haiku | refused by the gate: Haiku's C turned the matched `func_0005E550` of its unit back into `INCLUDE_ASM` |

Combined progress went from 0.5465% to 0.5808% (UFO2P 0.5789% to 0.5964%, +124 B; TACP 0.5145%
to 0.5654%, +365 B). The landing's end checks (`ninja verify`, `gate --all`) passed.

### Quota and spend

| Provider | What was read | Readings |
|---|---|---|
| Claude subscription | the weekly usage bar | None taken during the spike. An earlier calibration: 57 Opus sessions moved the weekly bar 6% (2026-11-07) (S) |
| ChatGPT Plus (Codex) | Codex Stats Monitor, 5-hour window and week, percent used (S) | 1% / 0% before round 5; 28% / 5% after round 5's canaries and probes (about 12 Codex sessions); 36% / 6% after 4 more canaries (about 2% of the 5-hour window per canary); 0% / 13% after the window reset and the small-picks drive (about 13 sessions, about 0.5% of the week each); 53% / 21% during the medium-picks drive; 100% (reset in 2 h 23 min) / 29% at 21:49 on 2026-11-11, after medium-picks drive 2b ended at 20:21 |
| Google AI Plus (agy) | `/usage` in an interactive agy, percent left per weekly group (S) | "Gemini models": 62.43% before Gemini's one drive session, 40.03% after it (one session, about 11 min, 100 steps, about 22% of the week). "Claude and GPT models": 98.79% before the two agy Claude 4.6 canaries, 36.04% after (two canaries of 8 short sessions each, about 63%). Both refresh weekly |
| OpenRouter | total usage from `GET /api/v1/credits`, of the owner's $100 | $12.23 before the 2026-11-10 resume; $39.58 two hours into the resumed 8-arm drive; $42.46 after the output-cap stop; $53.10 at the end |

- The medium-picks run on Codex (18 sessions of Sol, Terra and Astra, plus the 4 of the drive
  that stopped on Luna) took the 5-hour window from about 53% to 100% and the week from 21% to
  29% (S). From the 13% after the small picks to 29% is about 16 points of the week for those
  22 sessions, about 0.7% each (R).
- `agy -p /usage` printed nothing machine-readable, so the agy canary only estimated the quota:
  81,564 tokens per allowed canary session.
- OpenRouter charged $53.10 for the whole spike (canaries, the sessions the 429 fault set aside,
  every arm), against $70.53 at list price for the metered arms' drive sessions alone. The list
  prices overstate the bill; cache discounts were partly applied.

### Canaries and each model's harness failures

Each arm must pass its own canary on the installed CLI before a night (Codex and agy); the
Claude Code arms were canaried too.

| Arm | Canary history | Characteristic failure | Outcome |
|---|---|---|---|
| Haiku, Sonnet, Opus 5.5 | passed every time | none in the harness; Haiku's 176 B hold rewrote a shared struct and broke a matched function of its unit (refused by the gate) | ran 20 picks each |
| DeepSeek V4.1-Flash | refused or declined the forbidden probes once, then passed | refuses a canary's probes | ran 20 |
| GLM-5.3 | refused or declined the probes once, then passed | a reply ran past Claude Code's 32,000 output tokens and stopped resume 2 (fixed: the overrun is an attempt, and metered arms get a 64,000 cap) | ran 20 |
| GLM-4.7-Flash | passed every time | the most build failures per check (22.2%); arm-stopped on its last pick for a write to `temp_check_runner.py` at the repo top, which the hook denied | ran 20 |
| Qwen3.6-35B-A3B | failed twice, passed on retry | made two tool calls, then invented a table of verdicts | ran 20, held nothing |
| Muse Spark Open | passed once, then failed 3 times | sends file content as a JSON object, so plan.json is never written and `attempt check` exits 2; its hook-denied write stopped the first 8-arm drive after 35 sessions | dropped after 11 picks |
| GPT-6 Luna | failed until the broker; failed once more (ended its turn while `attempt check` still ran); passed after the wait instruction | ran `uv run --frozen reverseapoc context`, not a wrapper form, which stopped medium-picks drive 2 by design | left the 64-255 B picks after 1 |
| GPT-6.1 Sol, GPT-6.1 Terra | failed until the broker; failed once more on the unwaited check; passed after the wait instruction | Codex ignored their dotted-key project trust (their run dirs hold a dot), and the audit stopped the round 5 drive on the `error` items (fixed with an inline table) | ran 14 each |
| GPT-6 Astra | failed until the broker, then passed first time; passed again after the wait instruction | waited on its check where the others did not | ran 14 |
| Gemini 3.8 Flash | passed after the `manage_task` fix and the in-workspace unsandboxed probe | read its own agy output files under `.system_generated/`, which stopped the small-picks drive (now allowed by owner ruling) | 1 session, then quota |
| GPT-OSS 120B (agy) | failed 4 times | rewrote `..` paths, miscounted `..` levels, prefixed commands with `cd` | dropped |
| Claude Sonnet 4.6, Opus 4.6 (agy) | failed once each | waited with agy's unknown `schedule` timer; refused the `..` probe reads themselves | fixed (the timer is known, the probe wording neutral), deferred for quota |

### By provider and harness

| Provider and harness | Billing | Arms run | Sessions | Held exact (distinct functions) | API-equiv $ (L) | Real paid $ | Binding limit |
|---|---|---|---|---|---|---|---|
| Anthropic, Claude Code | subscription | Haiku, Sonnet, Opus 5.5 | 60 | 14 (6) | 27.74 | 0 | the weekly bar; not read during the spike |
| OpenAI, Codex CLI | ChatGPT Plus | Luna, Sol, Terra, Astra | 51 | 13 (4) | 103.36 stats, 14.94 (R) | 0 | the 5-hour window, then the week: no 256 B picks |
| Google, agy | Google AI Plus | Gemini 3.8 Flash | 1 | 0 (0) | 0.74 | 0 | the weekly group: one session took about 22% (S) |
| OpenRouter, Claude Code | metered | DeepSeek, GLM-5.3, GLM-4.7-Flash, Qwen, Muse | 92 | 11 (5) | 70.53 | 53.10 for the whole spike, from the credits API | the $100 credit; not reached |

Held exact counts a function once per arm. The distinct functions are the union over the
provider's arms (D).

### Routing conclusion

1. **Under 64 B the cheapest arms match what the strongest do.** Haiku held 3 of 7 for $0.17
   (L) in this bucket; Opus held the same 3 for $3.23 (L). GLM-5.3, DeepSeek, Sol, Terra and
   Astra held the same 3. Sonnet alone held a fourth.
2. **64-255 B is where arms separate, thinly.** One function each for seven arms (the same
   208 B one), one only GLM-5.3 found (64 B), and one only Haiku found (176 B), which failed
   the gate.
3. **Nothing at 256 B and up** held on any arm that ran it.
4. **Quota binds before dollars.** One Gemini session took about 22% of its weekly group, the
   agy Claude canaries 63% of theirs, and the Codex medium picks filled a 5-hour window (S).
5. So route by size, cheapest first, and escalate on failure: backlog 999.12 in
   `.planning/ROADMAP.md`, a size-routed cascade calibrated from these per-bucket figures, to be
   revisited after a few real nights because this run had 20 picks and one attempt per arm.

## Adding the next comparison

1. Freeze a pick list once (`reverseapoc drive --dry-run --stratify A,B,C --write-picks
   build/driver/<id>-picks.txt`), or reuse `build/driver/spike012-picks.txt` to compare with
   spike 012 directly.
2. Run each arm's canary on the installed CLI, then one `--hold --run <id>` drive with an
   `--arm` per arm (see [model-routing.md](model-routing.md#several-arms-in-one-drive)).
3. Before landing, save `reverseapoc stats --run '<id>-*'` as text and with `--json` under
   `build/gate/<id>/`; after `drive --land-held '<id>-*'`, run it again for the matched credit.
4. Read the quota meters before and after (the Claude weekly bar, Codex's two windows, agy's
   `/usage` groups, OpenRouter's credits) and write them down with the time.
5. Add a new dated section above "Adding the next comparison" with the same tables, mark every
   list-price, screenshot, recomputed and derived figure, and keep the older sections as they
   are. If a measurement fault is fixed in between (such as the Codex double count), say which
   figures it changes.
