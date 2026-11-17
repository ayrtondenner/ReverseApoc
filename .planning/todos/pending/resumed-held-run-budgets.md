---
title: A resumed held run gets fresh --arm-budget amounts
created: 2026-11-17
source: run 20261116-fable-ab, launched five times
---

# Budgets restart from zero on each launch of the same --run

A held run resumes when the same `--hold --run` drive is launched again, but each launch sizes
its `--arm-budget` amounts afresh. Run 20261116-fable-ab was launched five times; each time the
coordinator subtracted the earlier spend by hand (Copilot credits from the usage files, Terra
sessions from the records) to avoid overspending.

**Do (test first):** when a drive resumes a run, size each arm's budget against what that arm's
records under the same run already spent (sessions, `credits`, `cost_usd`, as the budget's
unit needs), and say so in the dry run and the start-of-run budget lines. A fresh `--run`
behaves as today.

**Done when:** resuming a held run whose arm already spent half its budget launches only the
other half, and the budget line names the earlier spend.
