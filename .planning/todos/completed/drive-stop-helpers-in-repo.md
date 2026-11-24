---
title: The drive's stop and status helpers live only in a session scratchpad
created: 2026-11-24
area: driver
files: tools/reverseapoc/drivectl.py, tools/reverseapoc/cli.py, docs/model-routing.md, tests/test_drivectl.py, pyproject.toml
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

## Resolution (2026-11-24)

### The change

- New tools/reverseapoc/drivectl.py, wired in cli.py as two commands, Windows only (exit 2
  elsewhere), read-only on the checkout:
  - `reverseapoc drive-stop RUN [--wait-minutes N]` (default 15): the console Ctrl-C of
    ctrlc-drive.ps1, sent from a short-lived helper child (`python -I -c`: FreeConsole,
    AttachConsole(pid), SetConsoleCtrlHandler(NULL, TRUE), GenerateConsoleCtrlEvent(0, 0)), so
    the caller's console is never detached. The helper refuses when the caller is on the
    drive's console (GetConsoleProcessList), as a Ctrl-C there would hit the caller too. Then it
    polls every 10 s as wait-drive-exit.ps1 did and prints RUN's last kind=run record from
    progress/attempts.jsonl. Exit 0 exited, 1 still running after N minutes (or not sent), 2 no
    drive process for RUN.
  - `reverseapoc drive-status RUN [--log PATH]`: each drive process (pid, parent, name,
    `in_job` from OpenProcess(0x1000) + IsProcessInJob, as injob.ps1), and with --log the
    sessions so far (the `MATCHED/PARTIAL/GAVE_UP after` lines) and the last 5 lines. Exit 0
    running, 2 not.
- The run match: a uv, reverseapoc or python process whose command line has
  `reverseapoc(\.exe"?)?\s+drive` followed by a space or the end (so not `drive-stop` or
  `drive-status`) and `--run RUN` or `--run=RUN` with the exact id (`20261124-codex` does not
  match `20261124-codex2`). Shells that name the drive (powershell, pwsh, cmd, bash) are not the
  drive.
- The process listing is one seam (drivectl.Seams.processes: `powershell.exe -NoProfile
  Get-CimInstance Win32_Process | ConvertTo-Json`), as are the job check, the Ctrl-C send, the
  sleep and the clock.
- docs/model-routing.md, new subsection "Stopping and inspecting a detached night" under
  "Launching a night from an agent session". pyproject.toml registers the `slow` marker.
- Not here: the hook allowing both commands during a drive is unit C's change.

### Tests

- tests/test_drivectl.py (48 tests): the run match (other runs, a prefix id, drive-stop and
  drive-status themselves, land-held, shells), the Get-CimInstance JSON parse (one object, bad
  JSON), stop's Ctrl-C target (the Python, else any drive process), wait, timeout, failed
  send, the record (none, broken line), the helper argv, status' process lines, job states,
  session count and tail, the CLI argv, exit codes and the off-Windows refusal.
- test_e2e_stop_interrupts_a_detached_sleeper (Windows only, `slow`, about 10 s): a sleeper in
  its own hidden console, broken away from the job, with `reverseapoc drive --run e2e-<hex>` in
  its argv: drive-status lists it in no job, drive-stop interrupts it (marker written) and
  exits 0, then drive-status exits 2.

### By hand (PowerShell tool, the real CLI, 2026-11-24)

```
child 12332
pid 12332 parent 7088 uv.exe in_job=no
pid 30064 parent 12332 python.exe in_job=no
pid 36332 parent 30064 python.exe in_job=yes
exit 0
sent the console Ctrl-C to pid 30064 (e2e-8f32dd25); waiting up to 1 min for the driver to exit
drive e2e-8f32dd25 exited
no kind=run record for e2e-8f32dd25 in ...\u-d\progress\attempts.jsonl
exit 0
started
KeyboardInterrupt caught
no drive process for e2e-8f32dd25
exit 2
```

The innermost python (36332) is in a job because Python's venv launcher (30064) puts its own
child in a job; uv, the detached root, is in none. The same sleeper started with
`Start-Process -NoNewWindow` (the caller's console) was refused, exit 1, and not interrupted:
`the console Ctrl-C to pid 29896 (e2e-478a86a4) was not sent: pid 29896 shares this command's
console; press Ctrl-C in that console instead`.
