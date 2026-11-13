---
name: drive-budget
description: Use when someone in ReverseApoc asks to spend part of a plan, window or dollar amount on a matching night or drive ("5% of my Claude plan via Haiku", "my whole Codex 5-hour window", "$30 of OpenRouter", "100 Copilot credits"), or asks how many sessions or matches a budget buys.
---

# Budget-sized drives

## Overview

A plain budget request becomes one `reverseapoc drive` command with an `--arm-budget` per arm.
You show its dry run and launch nothing until the user says yes to that exact command.

## Map the request

| They say | Arm | Budget |
|---|---|---|
| p% of Claude (Ultra) via Haiku / Opus | `claude-haiku-5-5` / `claude-opus-5-5` | `p%week` |
| my Codex 5-hour window, p% of it | `gpt-6.1-terra` | `100%5h`, `p%5h` |
| p% of my Codex week | `gpt-6.1-terra` | `p%week` |
| p% of my Antigravity / Gemini week | `gemini-flash` | `p%week` |
| $N of OpenRouter | `deepseek-flash` | `$N` |
| N Copilot credits, $N of Copilot | `copilot-haiku-5-5` | `Ncredits`, `$N` |

The figures are in `config/driver/quota.toml`. An arm with no entry there cannot take a budget,
and an arm missing from `config/driver/backends.toml` cannot run: tell the user and leave it
out. "5%" with no window means the week; say so.

## Build the command

```
uv run reverseapoc drive --dry-run \
  --arm claude-haiku-5-5=10 --arm-budget claude-haiku-5-5=5%week \
  --arm gpt-6.1-terra=5 --arm-budget gpt-6.1-terra=100%5h \
  --arm deepseek-flash=12 --arm-budget 'deepseek-flash=$30' \
  --allow-egress gpt-6.1-terra --allow-egress deepseek-flash \
  --max-sessions 340
```

- One `--arm NAME=WORKERS` per arm, workers at most its backends.toml `max_workers`.
- Quote the whole `'NAME=$N'` argument, in bash and PowerShell alike.
- `--max-sessions` is at least the sum of the budgets' sessions, plus any arm with no budget
  (the dry run prints the sum when the default 60 is lower). Leaving 60 spends far less than
  asked.
- `--allow-egress ARM` for every arm that is not a Claude login arm. The dry run needs it too
  and sends nothing. Before any launch, ask in its own question: "Codex and OpenRouter get
  disassembly of the game. OK to send it?" A budget request is not that consent. Without a
  yes, drop those arms.
- A Codex or Antigravity arm needs `build/driver/canary/<arm>.json` from a passed canary. If
  it is missing, offer the canary command instead (`drive --canary --night-model ARM
  --allow-egress ARM`) and leave the arm out tonight.

## Run, show, ask

1. Run the dry run. Paste its `budget ...` lines as they are: budget, quota per session with
   source and date, sessions, expected matches.
2. Ask: "Launch this exact command without `--dry-run`?" Wait for yes, even after "go".
3. On yes, launch from the main checkout of a clean clone, and write nothing under the
   checkout while it runs.

## Common mistakes

| Mistake | Fix |
|---|---|
| Inferring the egress opt-in from the request | Ask it separately |
| `--max-sessions` left at 60 | At least the sum of the budgets' sessions |
| `deepseek-flash='$30'` or an unquoted `$30` | `'deepseek-flash=$30'` |
| Codex arm without a canary file | The driver refuses it; offer the canary |
| Launching on "go" before showing the dry run | Dry run, then ask |
| Promising the expected matches | They are rough rates from a few nights |
