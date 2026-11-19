---
title: Check landed C for #pragma and _asm on every harness, not only in the Claude Code hook
created: 2026-11-19
area: attempt-check
files: tools/reverseapoc/hooks.py, tools/reverseapoc/driver.py, tools/reverseapoc/gate.py, tools/reverseapoc/lint.py
source: coordinator, after the 2026-11-18/19 drives (Codex Sol landings ea7d2a60, 4c4de2db)
---

# The inline-asm and pragma ban holds only where the Claude Code hook runs

The ban on inline assembly and pragmas in matching C (CLAUDE.md "Hard rules": no inline
assembly to force a match) is enforced at write time by the Claude Code PreToolUse hook:
`hooks._matching_write`, tools/reverseapoc/hooks.py:2269-2272, calls `_source_problem` with
`asm_rule=_MATCHING_ASM_RULE, any_pragma_aux=True, any_pragma=True` for a write under `src/`,
`include/` or the view unit. Codex, agy and Copilot sessions never run that hook. Their only
guard is the driver's post-session audit (tools/reverseapoc/driver.py), which checks which
paths a session touched, not what the C says. So a Codex, agy or Copilot landing such as the
two Sol matches of run 20261118-flags gets no content check for `#pragma` or `_asm`.

Do, test first:
- put the check in the landing path every harness shares: `gate` before a unit lands, or a
  `lint` rule that `gate` and `ninja verify` run, reusing `hooks.asm_problem` (no second copy
  of the rule);
- refuse the landing, with the line, when the unit has a pragma or inline asm the rule bans;
- a test per harness shape: a driver landing from a Codex arm whose unit carries
  `#pragma aux` must be refused;
- run it once over every unit already under `src/` and record the result.
