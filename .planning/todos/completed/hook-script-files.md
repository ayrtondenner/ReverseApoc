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

## Result (2026-11-24)

Owner ruling (2026-11-24): **refuse except repo helpers** (option 1). While a drive holds the lock, refuse
`powershell`/`powershell.exe`/`pwsh` with `-File` or `-Command`/`-c` from any cwd, and the same through `cmd /c`.
Allow `uv run reverseapoc drive-stop ...` and `uv run reverseapoc drive-status ...` (todo drive-stop-helpers-in-repo
builds them: `reverseapoc drive-stop RUN [--wait-minutes N]`, `reverseapoc drive-status RUN [--log PATH]`).
`uv run --no-project python -I <script outside the checkout>` stays allowed, as today (the paper lint uses it).

Done in `tools/reverseapoc/hooks.py`, test first (66 refused and 6 helper cases failed before the change):

- `_drive_segment` raises `_ScriptRun` for any simple command whose program is `powershell` or `pwsh` (any path,
  `.exe` or not), or a launcher (`Start-Process`, `saps`, `start`, `timeout`, `env`, `xargs`, `nohup`, `exec`,
  `nice`) with such a word after it. It runs in the segment walk like the image guard, so `cmd /c`, `bash -c`,
  `eval`, `$(...)` and pipes are covered, from every cwd; `_drive_command` turns it into its own denial, which
  names the two helpers. Beyond the ruling's `-File`/`-Command`, a positional script, stdin
  (`cat x.ps1 | powershell`) and `-EncodedCommand` are refused too: each runs a script the hook cannot read.
- `_drive_helper` (through `_uv_read`) passes exactly `uv run reverseapoc drive-stop RUN [--wait-minutes N]` and
  `uv run reverseapoc drive-status RUN [--log PATH]`: no uv option, RUN a plain name, N digits, at most the one
  option. Any `NAME=value` before `uv` now makes a uv call a non-read (it could steer the environment uv writes).
- `powershell -NoProfile -Command "Get-Content tools\x.py"` moved from the listed reads to the refused runs.

Tests (tests/test_hooks.py): `SCRIPT_RUNS` (21, Bash and PowerShell, the commands of the 2026-11-23/24 session
among them) refused from a clone and from the checkout (42) and allowed with a stale drive and with none (42);
`DRIVE_HELPERS` (7, the paper-lint shape included) allowed from both cwds (14);
`test_drive_guard_keeps_other_helper_shapes_refused` (11). docs/workflow.md, "From a Claude Code session" step 3,
says so.

Left open (not in the ruling, unchanged): a script run without PowerShell still passes from a clone when nothing
in its command line names the checkout: a `.ps1` run directly by the PowerShell tool (`& <scratch>\x.ps1`),
`bash x.sh`, `cmd /c x.bat`, `python x.py`.
