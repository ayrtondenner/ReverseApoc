---
title: agy 1.5.13 reports a refused compound command as DONE with no output
created: 2026-11-19
area: driver
files: tools/reverseapoc/agyjson.py, tests/test_agy.py
source: run 20261119-quota3 (STOPPED guardrail after 1 session, agy-opus-4-6)
---

# A run_command step that may never have run

**What happened.** Opus 4.6 on agy 1.5.13 (tacp func_000A87C0 attempt 1) sent
`cd <attempt dir> && uv run --frozen reverseapoc attempt context 2>&1`; agy's permission check
refused it (state ERROR, "permission check failed for unsandboxed ... user denied permission").
Its next step, the same form with `attempt asm`, ended state DONE after 0.045 s with no `output`
key in tool_info. The audit counted it as a command that ran, not an exact wrapper form, and
stopped the whole drive. `uv run` cannot finish in 0.045 s, and no wrapper output appeared in the
attempt dir, so the step was most likely soft-denied and reported as DONE.

**Do.**
- Read agy 1.5.13's own log for that conversation (~/.gemini/antigravity-cli/log/) and find
  whether the step was denied; capture a minimal repro in a canary probe (a compound command).
- Only with that evidence: treat a run_command step that ends DONE with no `output` key as a
  denial (test first), else keep it a stray. Keep agy-opus-4-6 off nights until then.

**Done when.** The shape is proven one way or the other and the audit follows the proof.
