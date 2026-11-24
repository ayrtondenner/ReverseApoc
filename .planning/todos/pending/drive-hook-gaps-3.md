---
title: Drive guard gaps left after the 2026-11-24 hook batch
created: 2026-11-24
area: hooks
files: tools/reverseapoc/hooks.py, tests/test_hooks.py
source: unit C report (hook-script-files, drive-hook-read-verbs-2, image-guard-other-retags), 2026-11-24
---

# Four gaps the batch found and did not close

**Why.** Working on the three hook todos of 2026-11-24, the agent and an independent reviewer
found these, outside the rulings it had:
1. **High.** A `<<` that is not a heredoc (`<<<`, a quoted `"<<EOF"`, `$((1<<x))`) makes the
   heredoc stripper drop the lines after it, so they are never judged. It needs a quote-aware
   heredoc reader.
2. Script runs that are not PowerShell still pass from a clone: `bash x.sh`, `cmd /c x.bat`, a
   `.ps1` run directly, `python x.py` (the documented `uv run --no-project python -I <script
   outside>` excepted). The owner's rule for PowerShell (refuse except the drive helpers) may
   extend to these; that is the owner's call.
3. `docker rmi reverseapoc-build:local` (and `docker image rm`) passes during a drive.
4. Over-refusal: the launcher rule refuses `find`, `env` and the like whenever a word contains
   `pwsh` or `powershell`, e.g. `find . -exec grep powershell {} +`.

**Do.** Test first: fix 1 and 3, and narrow 4 to a launcher whose program word is PowerShell.
For 2, ask the owner whether the PowerShell rule extends to other interpreters' scripts, write the
question with options here, and implement the ruling.

**Done when.** A non-heredoc `<<` no longer hides commands, `docker rmi` of the shared image is
refused during a drive, `find ... grep powershell` passes, the owner's ruling on 2 is pinned, and
tests cover each.
