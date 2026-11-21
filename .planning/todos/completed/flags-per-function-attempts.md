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

## Resolution (2026-11-21)

Owner ruling R1 (2026-11-21): each function newly matched by a flags landing gets the attempt
number of its own hitting attempt in status.csv. A function with no hitting attempt of its own
(its C rode along with a sibling's attempt, F-0035's func_00077F00) gets 0, like a hand-matched
row. When byte-identical C hit more than once for a function (R3), it gets the larger number.

- gate: `--attempts` is repeatable. `--attempts N` (at most once) is the count for every
  function the targets define, as before; `--attempts START=N` (START in hex, each start once)
  gives the function at START its own count (gate_units `attempts_by_start`). A START that no
  gated unit defines, or that two gated EXEs define, is a tool error (exit 2) and writes
  nothing. `--partial` takes only N, `--all` takes none. The existing callers (driver, twins,
  batch, the approve path for batch proposals) pass a single `--attempts N` and are unchanged.
- flags approve: `_own_attempts` maps each hitting attempt's function to its start and its own
  attempt number. The landing runs `gate EXE/UNIT --attempts 0 --attempts 0xSTART=N ... --json`.
- Tests: tests/test_gate.py (`test_per_start_attempts_*`, `test_gate_cli_per_start_attempts`,
  `test_gate_cli_refuses_bad_attempts`), tests/test_flags.py
  (`test_approve_gives_each_function_its_own_attempts`, `..._two_hit_functions_...`,
  `test_approve_credits_every_model_of_a_byte_identical_hit`).
- The status.csv rows the F-0035 / F-0077 landings already wrote are not touched here; that is
  .planning/todos/pending/flags-landing-records.md.
