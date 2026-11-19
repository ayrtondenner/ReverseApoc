# RED retrieval test (fresh agent, current SKILL.md at fccbab48, 2026-11-19)

- a) Unclear: the skill does not define "shape". Line 137 (shape: line = length, blocks, branches) argues against
  counting a type-only change; line 212 ("Change the C shape behind that instruction, one change per check") argues
  for counting every change. No other stop rule holds.
- b) Yes ("three different C shapes leave objdiff below 100", line 221).
- c) Yes (the rule names no size).
- d) Yes ("all 15 check runs are used", line 222).
- e) The skill does not say.
- f) No number specific to 256 B and up: three for every size.

Verdict: RED as expected (a ambiguous, e and f undefined).
