---
title: Read the subscription and credit meters without the owner's screenshots
created: 2026-11-13
source: owner, during night 20261112-cascade
---

# Measure quota use per arm from the tools themselves

Tonight's quota figures (docs/model-routing.md "Quota per session") came from the owner's
screenshots of the Claude Code usage panel, the Codex stats extension, agy's `/usage` screen and
ChatGPT's usage page. Give the orchestrator (and a drive) a way to read them directly, so runs can
be sized to a budget (todo `budget-runs-and-contributors`) and the quota table re-measured.

Per source, find a non-interactive read:
- **OpenRouter:** done in practice: `GET https://openrouter.ai/api/v1/credits` with the key
  (total credits and usage). Wrap it as a verb.
- **Codex (ChatGPT Plus/Pro):** the 5-hour and weekly bars, plus credits and full resets
  (chatgpt.com/settings/usage). The Codex stats extension reads them, probably from the CLI's
  local session data or its rate-limit headers; find the same source.
- **agy (Google AI Plus):** quota shows only in the interactive `/usage` screen; spike 012 found
  `agy -p /usage` prints nothing machine-readable. Find another path or scrape it carefully.
- **Claude Code (Ultra):** the weekly and Fable bars live in the claude.ai account; no
  documented CLI read is known. Investigate before assuming none.
Record each read's source and date beside the numbers. Never print or commit a key or token.
