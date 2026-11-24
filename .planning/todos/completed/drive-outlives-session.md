---
title: A drive launched from an agent session dies when that session ends
created: 2026-11-23
area: driver
files: tools/reverseapoc/driver.py, tools/reverseapoc/cli.py, docs/model-routing.md, docs/workflow.md, tests/test_drive.py, tests/test_driver_records.py
source: run 20261121-codex (killed ~05:10 on 2026-11-22 with its parent Claude Code session)
---

# The night dies with the session

**Why.** Run 20261121-codex was launched from a Claude Code session through a PowerShell
launcher (`Start-Process uv run reverseapoc drive ... -Wait`, memory drive-from-claude-session).
When that session ended at about 05:10 on 2026-11-22, the driver process was killed with it,
during a 5-hour pause. It wrote no STOPPED record, left build/driver/drive.lock behind, and its
records had to be committed by hand (2e809eea). A long Codex night needs to outlive the session
that starts it.

**Do.** Find the smallest launch that detaches the driver from its parent on Windows, keep the
env stripping and the console Ctrl-C stop working, check what a killed driver leaves, test first.

## Resolution (2026-11-23)

### The spike (scratch scripts in the session scratchpad, not in the repo)

- The session's process chain (pwsh, cmd.exe, claude.exe, the two Code.exe hosts) is in a job
  (`IsProcessInJob` true for each; explorer.exe is not). A drive under the old launcher is in
  it too: a stand-in shell running `Start-Process uv run ... sleeper.py -NoNewWindow -Wait` gave
  a sleeper python that `IsProcessInJob` reported in a job, sharing the shell's console.
- A child started with `CREATE_NEW_CONSOLE | CREATE_BREAKAWAY_FROM_JOB` and a hidden window
  (STARTUPINFO `SW_HIDE`), output redirected to a file: `CreateProcess` succeeded, so the job
  allows breakaway, and the sleeper's uv and python were in no job. Its parent was the spawning
  process, which had exited, so its parent chain leads nowhere.
- Tree-kill of both stand-in shells (`taskkill /T /F`, the session-end kill): the old
  launcher's sleeper died with its shell; the detached sleeper and its uv lived on.
- The unchanged ctrlc-drive.ps1 helper then found the detached sleeper by its command line
  (`... reverseapoc drive --run spike-det`), attached to its console and sent Ctrl-C: the
  sleeper wrote `KeyboardInterrupt caught` and exited, its uv with it. Both streams reached the
  log file.
- WMI `Win32_Process.Create` and schtasks were not needed.

### The change

- `reverseapoc drive --detach --log PATH ...` (cli `_detach_drive`): Windows only, the two
  flags together (each alone is refused, exit 2; off Windows exit 2). It re-spawns the same
  drive argv without `--detach`/`--log` as `uv run reverseapoc drive ...` in the repo root,
  adds `--run <UTC time>` when `--run` is absent so the Ctrl-C helper can find it, prints
  the pid, run id and log path, and exits 0. An abbreviated `--det`/`--lo` is refused rather
  than passed on.
- `driver.detached_env` builds the env as the launcher did: no `CLAUDE*` or `GIT_EDITOR`, PATH
  the User then Machine PATH without `\Microsoft\WindowsApps`, `OPENROUTER_API_KEY` from the
  User variables when set. `driver.saved_env` reads those from the registry, expanded.
- `driver.spawn_detached` is the seam: the spike's flags, stdin from NUL, stdout and stderr
  appended to the one log file.
- What a killed drive leaves: drive.lock is an OS byte lock (locks.py), so the kill frees it
  and the next drive starts. Its records stay uncommitted (the next drive refuses them as dirty
  outputs until they are committed by hand), stale claims are recovered as before, and now the
  next STARTED names the unended runs (below).
- docs/model-routing.md, new section "Launching a night from an agent session"; docs/workflow.md
  step 1 of "From a Claude Code session" points to it.

### Owner ruling (2026-11-23)

Question: "Should the next drive's STARTED record name earlier runs that have a STARTED but no
STOPPED?" Options: name them / docs only. Chosen: name them. `driver.unended_runs` reads
progress/attempts.jsonl for run records with a STARTED event and no later ENDED or STOPPED one
(run ids as the run records write them), and STARTED names them in its detail ("earlier runs
with no end record (killed): ...") and in a new `unended` field (a list of run ids, every new
STARTED record; an optional key, refused on any other event, so committed lines stay valid).
No record is written on their behalf. An ENDED run counts as ended too.

### Tests

- tests/test_drive.py: test_detach_respawns_the_drive_argv_in_the_repo,
  test_detach_names_the_run_id_when_none_is_given, test_detached_env_is_the_launchers,
  test_detach_and_log_need_each_other (2 cases), test_detach_is_refused_off_windows,
  test_spawn_detached_is_a_hidden_console_outside_the_job (Windows only),
  test_spawn_detached_smoke_writes_both_streams_to_the_log (Windows only, a real spawn).
- tests/test_driver_records.py: test_started_names_earlier_runs_that_never_ended,
  test_started_without_unended_runs_lists_none, test_only_a_started_record_names_unended_runs.

Not done here: a real night started with `--detach` from a session that then ends. The first
such night is the end-to-end proof.
