---
title: GitHub Copilot as a drive harness (Copilot CLI arms)
created: 2026-11-13
area: harness-copilot
files: config/driver/backends.toml
source: owner, during night 20261113-cascade2
---

# GitHub Copilot as a drive harness

The owner has GitHub Copilot Pro with 1,500 AI credits a month (1 used, resets 2026-11-30) and no other
use for them. Add Copilot as a fourth signed-in harness beside Claude Code, Codex CLI and Antigravity,
so its models can run as cascade or `--arm` lanes.

Model lists (owner links): GitHub Docs "Supported AI models" and "AI model comparison"
(docs.github.com/en/copilot/reference/ai-models/supported-models and .../model-comparison).

Before building:
- **Runtime rule.** CLAUDE.md and `.claude/rules/workflow.md` allow other runtimes only for Codex CLI
  and Antigravity drive sessions. Copilot CLI needs the same scoped owner exception written there first.
- **Spike first** (as spike 012 did for Codex and agy): what Copilot CLI's headless mode streams
  (events, tool steps, model id), how it is sandboxed on Windows, how its permission rules can deny
  `orig/` and other paths, how premium-request credits map to sessions, and which models are worth an
  arm per spike 012's per-bucket figures.
- **Then build, test-first:** a `copilot` harness in `backends.py`/`session.py`, a stream adapter
  and audit that fail closed on unknown steps (the agy 1.5.7 `edit_file` stop shows why), a canary
  per arm and CLI version, and `[arms."copilot-..."]` entries in `config/driver/backends.toml`.

## Built (2026-11-13, worker branch; not yet canaried)

- Runtime exception in CLAUDE.md and `.claude/rules/workflow.md` (owner ruling 2026-11-13).
- Spike record: `.planning/spikes/013-copilot-cli/README.md` (PARTIAL), MANIFEST row.
- `backends.py`: harness `copilot`, optional `max_ai_credits` (>= 30, default 30, Copilot only);
  every session now loses every `COPILOT_*` variable and `GH_TOKEN`/`GITHUB_TOKEN`.
- `session.py`: `build_copilot_argv`, `copilot_prompt`, `COPILOT_SHELL_RULE =
  "shell(reverseapoc-attempt)"` (security review: the first build's `shell(uv:*)` pre-approved
  `uv run python -c`); the wrapper is the package's new `reverseapoc-attempt` console script
  (`cli.attempt_main`), first on the session's PATH.
- `copilotjson.py`: init check, usage/credits from `--usage-output-file`, tool calls by id,
  exact denials, commands/writes/reads, fail-closed `unknown_steps`, `hook_traces`, classify.
  `streamjson.parse_line` takes a leading BOM off (1.0.111's first line).
- `driver.py`: the copilot branches (env, per-session COPILOT_HOME with hooks off, guard launch,
  argv, cwd = attempt dir, audit, init stop, denied writes, record `credits` + validator, pass
  gate, one-session canary with eleven probes).
- Arms: `copilot-haiku-5-5`, `copilot-sonnet-5-5`, `copilot-gpt-6-luna` (backend github, 4
  workers, 30 credits, GitHub's credit rates as USD prices).
- Docs: model-routing.md "Copilot arms" and quota row, tools.md row, legal.md egress row,
  toolchain.md sign-in row.

## What the live canary must still prove (spike 013 "Open items")

1. The sign-in survives the per-session `COPILOT_HOME` (else an authentication STOP: the owner
   chooses a fixed driver home signed in once, never a copied token).
2. No hook text and no hook event; repo instructions absent (check the session's
   `session-state/<id>/events.jsonl` under its home once).
3. `shell(reverseapoc-attempt)` lets the wrapper run (fallback `shell(reverseapoc-attempt:*)`,
   never a uv rule), and the eleven probes, `uv run python -c` and the other uv, powershell and
   cmd commands among them, are each a denial in Copilot's stream.
4. The long-command shapes: powershell `mode`/`initial_wait` and `read_powershell
   {shellId, delay}` are accepted unconfirmed; any other key stops the night (fail closed).
5. Each probe refused with one of the two known texts (the shell read of orig/ especially).
6. The usage file written; re-measure the per-session credits (placeholder 3 to 5 per Haiku
   session).
7. No model switch and no unlisted event type (`session.skills_loaded` would be one).

## Status (2026-11-16)

- The live canary passed on 1.0.111 on its third run (2026-11-13). The arm ran 123 Haiku 5.5
  sessions on 2026-11-14 (runs `20261114-nearmiss` to `-opus-sonnet`) and matched 6.
- Item 6: measured 2.2 credits a session (273.6 over 123), within 10% of the account meter;
  quota.toml carries it.
- Item 4 and beyond: the nights showed shapes the capture had not. Each stopped a drive, and
  each is now known by its exact shape: `view_range`, edits missing `path` or `old_str` that the
  CLI refused or failed with ENOENT, `timeout`/`async`/named `shellId`, extra
  `description`/`file_path` keys, `%TEMP%` result spills, and `;`-chained wrapper calls
  (docs/learnings.md, 2026-11-16).
- Run `20261114-opus-sonnet` stopped on `view {path, forceReadLargeFiles}`. Done on 2026-11-16:
  the review read all five tools' keys from 1.0.111's package. The view schema is in
  `prebuilds/win32-x64/runtime.node`; `cli-main.js` has only a help table.
  - `forceReadLargeFiles` (boolean) is now known, test-first.
  - Kept unknown on purpose: view's flattened `view_range[0]`/`[1]`, and powershell's `detach`,
    a process that outlives the session.
  - `edit` stays `{path, old_str[, new_str]}`. The JSON schema requires only `path`, but the CLI
    refuses an edit without `old_str` at run time (nights -nearmiss3/-5).

  The Haiku arm's `max_workers` went from 4 to 10 for the owner's 5-hour spend of the month's
  credits.
