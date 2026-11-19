---
title: Held comparison of the Codex arms before upgrading to ChatGPT Pro
created: 2026-11-13
area: evaluation
files: docs/model-comparison.md
source: owner, during run 20261113-cascade3
---

# Do Codex's stronger models match enough to justify Pro?

The owner is weighing ChatGPT Pro ($100, "Pro 5x") over Plus ($20). Per third-party reports
(2026-11), Pro drops the 5-hour window and gives about 5x the weekly Codex budget; on Plus about
5 Terra sessions take 1% of the week, so Pro would be about 2,500 Terra sessions a week.

More sessions only pay if they match. GPT-6.1 Terra held 1 of about 90 sessions on the cascade
nights (mostly 64-255 B), while Haiku held 4 of 78 and DeepSeek 2 of 5
(docs/model-comparison.md "Cascade nights"). Spike 012 had Luna, Sol, Terra and Astra on the
picks under 256 B only, one attempt each.

Do: a `--hold` drive on one frozen pick list (spike 012's method), stratified by size and
including 256 B and up, with `--arm gpt-6.1-sol=N --arm gpt-6-astra=N --arm gpt-6.1-terra=N`
and a Claude control (Haiku), one attempt each; then `stats --run '<run>-*'` per arm and bucket,
and Plus quota per session per arm from the meters (or the usage-meter todo once built).
Decide on volume, not per-session quality (owner, 2026-11-13): on a flat-rate plan a session
costs nothing extra, so the question is matches per week for the extra $80/month. Measure:
- Terra's matches per session on fresh functions and on repeats (diminishing returns: at 25x
  the volume it keeps meeting functions it already failed);
- how many Codex sessions this machine sustains at once (Docker checks per session: try 5, 10,
  15 workers and watch throughput and errors);
- whether Sol or Astra turn the same Pro quota into more matches than Terra (a better use of the
  quota, not a gate).
Upgrade if expected matches per week at the volume the machine can run beat the alternatives
per dollar (for example the same $80 on OpenRouter DeepSeek). Volume Terra fits best on
functions the other arms already gave up on, or as its own lane, so it does not spend the
attempt-1 slots a stronger arm converts better. Record the verdict in docs/model-comparison.md.

## Result (2026-11-18): run 20261118-pro

A `--hold` drive on 6 frozen near-miss picks (`build/driver/20261118-pro-picks.txt`: 2 under 64 B, 2 at 64-255 B, 2 at 256-1023 B), one attempt per arm and function:

| Arm | Sessions | Held exact | API-equivalent | Per session |
|---|---|---|---|---|
| GPT-6.1 Sol | 6 | 0 | $10.52 | $1.75 |
| GPT-6 Astra | 6 | 0 | $57.46 | $9.58 |
| GPT-6.1 Terra | 6 | 0 | $7.41 | $1.24 |
| Haiku 5.5 (Claude control) | 5 | 0 | $0.19 | $0.04 |
| Gemini 3.8 Flash (agy) | 4 | 0 | $2.21 | $0.55 |
| GPT-OSS 120B (agy) | 4 | 0 | $0.11 | $0.03 |

No arm held an exact match, so there are 0 discordant pairs: a null that cannot separate the arms. Nothing shows Sol or Astra matching more than Terra, and they cost about 1.4x and 7.8x Terra's list price a session.

The run stopped once on a guardrail (GPT-OSS ran agy's `search_web`; the owner dropped GPT-OSS). The Codex 5-hour window ran out at 19:08, the Codex week at 22:19 (the owner used one limit reset), and Gemini ran out of agy's weekly quota; an owner-approved console Ctrl-C ended the run. The worker-count and repeat questions above were not measured. The 256 B night the same day gave the Plus quota figure: about 0.41% of the Codex week a Terra session at 256 B and up, against 0.25% on smaller rows.

## Resolution (2026-11-19)

The data gives no case for upgrading to ChatGPT Pro. Six picks are too few to settle it, but Sol and Astra cost much more per session than Terra and matched nothing, and Terra itself matched 0 of 14 at 256-1023 B the same day. More Terra volume pays only where Terra matches. Verdict recorded in docs/model-comparison.md, "The 256 B night and a held Codex-tier comparison (2026-11-18/19)". Reopen it only with a larger held list or a queue where Terra matches again.
