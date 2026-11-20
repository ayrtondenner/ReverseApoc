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

## Resolution (2026-11-20)

Proven from agy's own records, read-only; no agy launch and no canary. The step never ran:
agy cancelled it when it soft-denied the other command of the same turn.

- agy's log, `~/.gemini/antigravity-cli/log/cli-20261119_213418.log` (conversation
  8916f959-e708-4997-9bff-2f95de221e25, language server 1.5.13):
  `21:34:30.752449 tool_confirmation_manager.go:222] Print mode: soft-denying tool confirmation
  "Bash" at step 2`, then `rpcs_backend.go:482] CancelCascadeInvocation requested:
  cascade_id="8916f959-..."` and `cascade_manager.go:2644] Cancel requested for cascade` in the
  same millisecond, then shutdown. There is no confirmation line for step 3.
- The model asked for both commands in one planner response (step 1 `tool_calls`, two
  run_command calls: "I'll start by gathering context and the assembly listing in parallel").
- agy's conversation store (`conversations/8916f959-....db`, table `steps`): step 2 status 7
  with the permission message in `error_details`; step 3 status 6, with no error and no output
  in its payload (only the CommandLine). Across all 243 local conversation DBs, the numbers map
  2 = RUNNING, 3 = DONE, 4 = INVALID, 7 = ERROR against the brain transcripts' names, so 6 fits
  the Cascade enum's CANCELED. agy's own `brain/<id>/.system_generated/logs/transcript_full.jsonl`
  leaves step 3 out entirely. The 6 = CANCELED name is inferred from the enum's layout; the binary
  was not decoded.
- Same shape, same store status, from an explicit soft-deny: canary 20261118-canary-gemini-flash,
  short-name read (conversation 8d0fbed8, `cli-20261118_171947.log`: `soft-denying tool
  confirmation "ReadFile" at step 2`). The stream shows DONE after 0.069 s with no output, and the
  store shows status 6.
- Every agy stream under build/driver: run_command DONE with output 224 (fastest 0.79 s, store
  status 3); DONE without output exactly 1, this step (0.045 s, store status 6). read_file DONE
  without output: 9 that ran (status 3), so the rule is for run_command only.
- This agrees with the attempt's records without proving anything by itself. The wrapper ledger
  is empty (0 bytes), and the attempt dir holds only the driver's files: context.md, view/ and
  view-head.txt from 21:33, before the 21:34:18 launch, and the saved transcript. A cache hit of
  `attempt asm` would also have left no ledger line.

What changed: `agyjson._denial` treats a run_command step in its known shape as a denial (action
`cancelled`) when it ends DONE, its tool_info holds only name and parameters (no output, no
error), and its duration_seconds is under `CANCELLED_MAX_S = 0.25`. Such a step drops out of
`commands()`, so the night audit no longer counts it as a stray. A step with no duration, a
duration at or over the bound, an output, an error, a subagent, or another tool still counts as
run (fail closed). In a canary, the allowed session reports it as a denied step, and no probe
counts it as its proof, because `cancelled` is no probe action.

Tests (tests/test_agy.py): `test_agyjson_a_cancelled_command_never_ran` (new) and
`test_agy_soft_denied_steps_are_not_strays` (adds the `cancelled_command` fixture, the quota3
session with made-up paths). RED: the unit test's `commands()` held the asm command, and the
night exited 1. GREEN: test_agy.py 77 passed, ruff clean. agy-opus-4-6 can return to nights. A
compound `cd ... &&` command is still soft-denied by the allow regex, so that session spends its
turn and does nothing useful, but it no longer stops the drive.
