---
title: GitHub Copilot as a drive harness (Copilot CLI arms)
created: 2026-11-13
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
