---
title: The drive's stop and status helpers live only in a session scratchpad
created: 2026-11-24
area: driver
files: tools/reverseapoc/cli.py, tools/reverseapoc/driver.py, docs/model-routing.md
source: sessions of 2026-11-12 to 2026-11-24 (ctrlc-drive.ps1, wait-drive-exit.ps1, injob.ps1, watch-night.ps1)
---

# Copied from session to session

**Why.** The only documented stop for a drive is a console Ctrl-C. It is sent by a PowerShell
script (FreeConsole, AttachConsole to the drive's Python, SetConsoleCtrlHandler(NULL, TRUE),
GenerateConsoleCtrlEvent) that lives in a scratchpad and is copied into each new session. The same
goes for the wait-for-exit loop (matching `reverseapoc(\.exe"?)?\s+drive` in command lines), the
IsProcessInJob check that proved `--detach` worked, and the night watch that looks for a dated
limit in transcripts. Each copy drifts (the watch broke on a renamed transcript directory), and
the hook has to let `powershell.exe -File` pass for them to run (todo hook-script-files).

**Do.** Test first: add `reverseapoc drive-stop RUN` (send the console Ctrl-C to that run's
drive, then wait for the driver to exit and print its STOPPED record) and `reverseapoc
drive-status RUN` (pid, whether it is in a job, the last log lines, sessions so far). Both must
work while a drive holds the lock, so the hook allows them by name. Document them in
docs/model-routing.md next to `--detach`. The week-limit watch belongs to todo
drive-stops-on-week-limit, not here.

**Done when.** A session can stop and inspect a drive with repo commands only, the hook allows
them during a drive, and tests pin the argv and the run match.
