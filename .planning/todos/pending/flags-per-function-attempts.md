---
title: Give each function a flags landing matches its own status.csv attempts
created: 2026-11-20
area: flags
files: tools/reverseapoc/flags.py, tools/reverseapoc/gate.py, tools/reverseapoc/cli.py
source: review of a685ec0f / 33b91481, finding 4 (2026-11-20)
---

# One --attempts for every row a landing matches

`flags approve` runs `gate EXE/UNIT --attempts N` once, and gate stamps N on every newly matched
row (gate.py `_write_tables`). N is the max attempt number over the attempts whose C landed
(`_hitting_attempts`; until 2026-11-20 it was the max over all evidence). A unit landing that
matches several functions therefore gives each the same number, even a function with no attempt of
its own (F-0035's func_00077F00, whose C came with func_00077EC0's attempt).

The per-function fix is not small, so it was left out of the review fix:

- gate needs per-start attempts, either a new CLI form (`--attempts START=N ...`) or a second gate
  pass;
- flags needs the rule for a function with no own hit: 0, the attempt that carried its C, or
  something else. That is a ruling question;
- the existing gate callers (driver, twins, batch) and their tests need care.

# Done when

- Each function newly matched by a flags landing gets the attempt number of its own hitting
  attempt.
- A function whose C rode along with another function's attempt gets the number the owner rules.
- A test pins both cases.
