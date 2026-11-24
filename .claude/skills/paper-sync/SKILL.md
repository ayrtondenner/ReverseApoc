---
name: paper-sync
description: Use when a ReverseApoc session, tooling batch, experiment or drive night has ended and its results, tooling changes or quota readings should go into the Overleaf arXiv paper (project 6afce29e14bd43436c220d22), or when someone asks to "update the paper", "add tonight's run to the paper" or "sync the paper".
---

# Paper sync

## Overview

One pass adds a session's facts to the Overleaf paper without losing anything already there.
Every number in the new text traces to a record, an owner reading or a stated derivation, and
the only writes to Overleaf are one additive `sync_directory` and one compile.

## Before you start

- Each run you add must have ended and its records must be committed. A run has ended when
  `progress/attempts.jsonl` holds its ENDED or STOPPED record, or when it was killed and no
  drive process is left for it. A killed run has no totals line, so its figures come from its
  own attempt records: count and sum them, and mark the result derived. A run that is still
  going (a STARTED record only, and its process alive) gets no figures yet, because its numbers
  still move. A different drive running now does not block the pass: everything below reads the
  checkout or writes under the scratchpad.
- Load the overleaf-web tools with ToolSearch, then call `auth_status`. If it fails or returns
  AUTH_EXPIRED, stop and tell the owner to run `npx overleaf-web-mcp login`. There is no other
  route to the project.
- Work in `<scratchpad>/paper/`, never under the checkout. Copy this skill's `sanity.py` and
  `scan.py` into `paper/scripts/`. During a drive, the hook runs a script only from outside the
  checkout.

## The pass, in order

1. **Backup.** `download_project_zip` to a new file `paper/overleaf-backup-<mmdd>.zip`. If the
   name is taken, pick a new one: never pass `overwrite: true` over an earlier backup.
2. **Mirror.** Unzip that backup into a new `paper/current-<mmdd>/`, then copy it to
   `paper/upload/`. Edit only `upload/`. The mirror comes from the backup you just took, not
   from an older local copy, because the owner may have edited the project since.
3. **Facts file.** Write `paper/facts-<mmdd>.md` before any prose. It has one table per run or
   tooling batch, with the columns `Item | Value | Kind | Source`. Kind is one of:
   - **T**: read from `progress/attempts.jsonl`, `config/*/status.csv`, a drive log or `stats`;
   - **S**: the owner's screenshot or reading (meter bars, reset times);
   - **derived**: computed from T/S rows, with the formula written out.
   Each source names the file and the record, line or command you read. A figure you cannot
   trace gets no row, so it stays out of the paper.
4. **Check.** Re-read every T row read-only against the records: session counts, matched,
   STOPPED reason, wall seconds, cost. Fix the facts file, not the record. Never estimate a limit
   time or a pause: quote the transcript's "try again at …" or leave it out.
5. **Edit `upload/`.**
   - Run results go in `sections/08-results.tex`. Tooling (driver, hooks, meters, quota) goes in
     `sections/06-agents-and-drive.tex`, or in `04-method.tex` when the method itself changed.
     Limits and caveats go in `10-threats.tex`.
   - Above each new paragraph, put a `% FACT: facts-<mmdd> §<n> "<row>" (<value>) (T|S|derived)`
     line for each number in it, in the style the files already use.
   - Additive only: add or extend paragraphs and table rows. Change an existing figure only where
     a newer record supersedes it, and keep the old one in its `% FACT` line.
   - Each tooling change says what changed, why, and the incident that caused it (run id and date).
   - Never name the owner's private project. Write no secrets and no e-mail addresses.
6. **Lint.** Run both scripts on the backup mirror and on `upload/`:
   `uv run --no-project python -I paper/scripts/sanity.py paper/upload`, and likewise `scan.py`
   (undefined refs or cites, duplicate labels). An issue that `upload/` has and `current-<mmdd>/`
   does not is a defect: fix it before you sync.
7. **Sync.** `plan_sync` from `paper/upload` to the project root. The plan must show changed or
   localOnly files only, and `remoteOnly` must hold nothing you mean to delete. Use additive
   mode, never mirror. Then `sync_directory` with that `planToken`. On REMOTE_DRIFT, start again
   at step 1.
8. **Compile once.** `compile_project`. It passes only when `summary.builtCleanly` is true;
   status "success" just means a PDF came out. If it is false, read `get_compile_log`, fix
   `upload/`, and go round steps 6-8 once more. Never compile in a loop.

## Done when

- `facts-<mmdd>.md` exists and every number in the new text has a `% FACT` line pointing to it.
- The backup zip exists and the sync plan deleted nothing.
- `summary.builtCleanly` is true.
- Your report names the sections touched, the backup path and any S or derived figure the owner
  should double-check.

## Follow-ups (optional, never part of this pass)

`/ars-revision` restructures prose and `/ars-citation-check` checks references. Run them only
when the owner asks, after a clean pass.

## Common mistakes

| Mistake | Instead |
|---|---|
| `write_file` per section | One `plan_sync` + `sync_directory` from the mirror |
| Mirror from last session's local copy | Mirror from the backup you just downloaded |
| Owner's recap numbers pasted in | Facts file rows re-read from records, owner figures marked S |
| "Limit hit around 21:40" | Quote "try again at …" from the transcript, or omit |
| Compile, tweak, compile | Lint first; at most one retry after reading the log |
