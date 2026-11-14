---
title: Codex attempt records carry no model
created: 2026-11-13
source: owner, counting the project's sessions (296 of 1,236 records had model null)
---

# Codex attempt records carry no model

`codex exec --json` streams no init event naming the model, so an attempt record's `model`
(the model the CLI reported) is null on every Codex session: 296 records on 2026-11-13 (Terra
245, the spike 012 GPT arms 51). `stats` already falls back to `model_requested`, but any other
reader of `model` sees a blank.

Do (test first): a Codex record's `model` is the `--model` the driver passed (`claim.model`;
the CLI runs exactly that model and exits on an unknown one). Committed records stay as they
are (D-23); readers keep falling back to `model_requested` for them.
