---
title: Copilot calls with junk extra argument keys stop the night
created: 2026-11-14
source: night 20261114-nearmiss7 (stopped after 74 sessions, 5 matched)
---

# A create with `{path, file_text, file_path: "x"}`

Copilot Haiku sent `create` with an extra `file_path` key; the CLI ignored it and wrote the
session's own notes.md through `path` (an allowed write), but the audit failed closed on the
unknown shape and stopped the night.

Do (test first): read the CLI's bundled schemas (1.0.111 `cli-main.js`: view, create, edit,
powershell, read_powershell) and accept an extra key only if it is absent from that tool's own
schema (the CLI drops it), so a real key such as `requestSandboxBypass` stays unknown. Re-verify
against the shipped CLI version each update (the canary). Alternative or addition: a line in
`copilot_prompt` naming each tool's exact arguments.
