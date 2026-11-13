---
title: Held comparison of the Codex arms before upgrading to ChatGPT Pro
created: 2026-11-13
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
