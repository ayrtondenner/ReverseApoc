---
title: A drive launched from an agent session dies when that session ends
created: 2026-11-23
area: driver
files: tools/reverseapoc/driver.py, docs/model-routing.md
source: run 20261121-codex (killed ~05:10 on 2026-11-22 with its parent Claude Code session)
---

# The night dies with the session

**Why.** Run 20261121-codex was launched from a Claude Code session through a PowerShell
launcher (`Start-Process uv run reverseapoc drive ... -Wait`, memory drive-from-claude-session).
When that session ended at about 05:10 on 2026-11-22, the driver process was killed with it,
during a 5-hour pause. It wrote no STOPPED record, left build/driver/drive.lock behind, and its
records had to be committed by hand (2e809eea). A long Codex night needs to outlive the session
that starts it.

**Do.** Find the smallest launch that detaches the driver from its parent on Windows (a detached
process, a scheduled task, or `--detach` in the CLI) while keeping the env stripping
(CLAUDE*, GIT_EDITOR, WindowsApps on PATH) and the console Ctrl-C stop working. Check what a
killed driver leaves (stale lock, no end record) and whether the next drive's `recovered` handling
covers it; test first for any driver change.

**Done when.** A drive started from a session keeps running after the session exits, can still be
stopped with the documented Ctrl-C, and docs/model-routing.md says how to launch it.
