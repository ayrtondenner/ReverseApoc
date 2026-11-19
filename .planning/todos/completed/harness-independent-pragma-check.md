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

## Resolution (2026-11-19)

Quick task 261119-bhl (batch 261119-bhi). The check sits in `gate`, the landing path every
harness shares (driver `_judge`, twins, flags all run `reverseapoc gate EXE/UNIT`; `ninja
verify` runs no lint, so a lint rule would not have reached it).

- RED 9de887d3, GREEN b911c71e: `gate.unit_asm_problem` runs `hooks.asm_problem(text,
  any_pragma_aux=True, any_pragma=True)` (the matching layer's strict scan, no second copy)
  over each gated unit before check, in `gate EXE/UNIT` and in `gate --all`'s recheck of every
  matched unit; `gate.header_asm_problems` runs the always layer's lax scan over every
  `include/*.h`, so `watcom_compat.h`'s clang `#pragma` and `common.h`'s `##` pass. A refused
  file is exit 1 naming the file and the line; no check runs and nothing is written.
- `batch.refusal` dropped its `_BANNED` regex for the same strict scan (it now also refuses
  `_Pragma`, `%:pragma`, `__pragma`, `__emit` and `#`/`##` operators, ignores comments and
  literals, and names the line).
- Tests (tests/test_gate.py): `#pragma aux`, a plain `#pragma`, `_asm`, `__asm` and `_Pragma`
  each refused by gate; a Codex-arm landing (the unit carrying `#pragma aux`, gated through
  `driver.gate_argv`, which names no arm) refused through the CLI with exit 1; gate --all
  refuses a matched unit with a `#pragma` and a header with `__asm`; the committed headers pass
  both gates. tests/test_batch.py pins `_Pragma`, `%:pragma` and the line in the reason.
- One-off scan over the tree at fccbab48 (scratch script calling `gate.unit_asm_problem` and
  `gate.header_asm_problems`; `gate --all` needs orig/, which the worktree lacks): 179 units
  scanned under the strict rule (ufo2p 89, tacp 90), 0 problems; 2 headers (common.h,
  watcom_compat.h) under the lax rule, 0 problems. The two Codex Sol landings ea7d2a60 and
  4c4de2db are clean.
- Docs: docs/workflow.md (Hooks: "The gate's scan"; the hook-timing note), docs/toolchain.md
  (batch/judge refusal).
