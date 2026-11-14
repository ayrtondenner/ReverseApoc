---
title: Budget-sized drives from a plain request, and a README path for outside contributors
created: 2026-11-13
source: owner, during run 20261113-cascade3
depends_on: the usage-meter todo (measured quota per arm) and docs/model-routing.md "Quota per session"
---

# "Use 5% of my Claude plan via Haiku, my whole Codex 5-hour window, and $30 of OpenRouter"

**Goal.** A contributor states budgets in plain terms and gets a correctly sized drive:
"run a decomp session using 5% of my Claude Code Ultra plan via Haiku, 100% of my Codex
5-hour limit on the $100 Pro plan, and $30 from OpenRouter".

**Build (after the usage-meter todo):**
- A budget form per arm, for example `--arm-budget claude-haiku-5-5=5%week`,
  `--arm-budget gpt-6.1-terra=100%5h`, `--arm-budget deepseek-flash=$30`. The driver turns each
  into a session cap from the measured quota per session for that plan (Ultra, Plus, Pro 5x...),
  re-reads the real meter during the night, and stops the arm when its budget is spent, not
  only at a fixed count. Plans are named in config, not hard-coded.
- A dry run that prints the budget, the sessions it buys and the expected matches from the
  measured rates, before any spend.
- A project skill (through superpowers:writing-skills) that turns the plain request into the
  drive command, shows it with the dry run, and asks before launching.

**README for outside contributors:**
- What they need: their own copy of the game (`reverseapoc ingest`, hashes checked), the
  user-supplied Watcom 10.x compiler, Docker, uv, and whichever subscriptions or keys they want
  to spend (Claude Code, Codex CLI, Antigravity, OpenRouter...). Nothing copyrighted is shipped.
- Setup, the canaries per arm, and an example budget request.
- Egress: hosted and non-Anthropic arms send disassembly off the machine (`--allow-egress`);
  say so plainly so each contributor opts in knowingly.
- How results come back: matches are gated commits on their clone, opened as pull requests;
  CI and the owner's re-gate prove every byte (CLAUDE.md: never by an agent's word). Credit via
  the commit trailers.
- Rules from CLAUDE.md that apply to them (no game files or build output in commits, the
  hard rules, the agent runtimes allowed).

## Result (2026-11-13, batch unit 6)

Built: `--arm-budget`, `config/driver/quota.toml`, the dry-run budget table, the meter seam
(`Deps.meter`, default no reading), the README contributor guide and the `drive-budget` skill.
Not wired: the meter seam to `reverseapoc meters`. On 2026-11-13 no meter moves during a night
(Claude's figure is the usage panel's cache, Codex's is the last interactive session, Copilot
drive sessions log under their own COPILOT_HOME), so the session cap is the budget's real bound;
wire it when a meter reads live (todo `budget-meter-wiring`).
