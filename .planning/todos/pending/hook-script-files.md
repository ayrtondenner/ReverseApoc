---
title: The drive guard passes any script run as `powershell.exe -File` from a clone
created: 2026-11-24
area: hooks
files: tools/reverseapoc/hooks.py (_drive_offender, _nested), tests/test_hooks.py
source: session of 2026-11-23/24 (Ctrl-C helper, wait-for-exit, job checks, the owner-approved taskkill)
---

# A hole in the write guard

**Why.** During a drive the hook refused `taskkill` and `Stop-Process` on the drive's processes,
but `cd <clone> && powershell.exe -NoProfile -ExecutionPolicy Bypass -File <scratchpad script>`
passed. The hook judges the command line, not the script's contents. That is how the console
Ctrl-C helper, the wait-for-exit loop, the job checks and the owner-approved `taskkill` of run
20261124-codex all ran. The same route could run a script that writes under the checkout, and the
hook would never see it. (`uv run --no-project python <script outside>` is allowed on purpose and
has the same property.)

**Do.** Decide with the owner which of these it should be:
1. refuse `-File`/`-Command` scripts during a drive unless they are the repo's own stop helpers
   (todo drive-stop-helpers-in-repo);
2. read the script and judge each command in it, as for an inline command;
3. keep the route open, but document it as the operator's escape hatch and list what may use it.
Test first with the commands of this session as cases.

**Done when.** The owner's choice is written here, the hook enforces it, and tests pin both the
refused and the allowed script forms.
