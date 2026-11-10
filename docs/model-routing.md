# Model routing: the spike 012 harness

Spike 012 compares model arms on the same frozen set of functions. Each arm attempts each
function once, and no arm's match lands before every arm has run. The landing then credits
the cheapest arm that matched. Phase 07.2 plan 06 built the flags below (D-17). Plans 12, 13,
15 and 16 add their own sections to this page: the backends file, the Codex and Antigravity
harnesses, and several arms in one drive.

## The flags

- `--night-model MODEL` runs every matching session of the night on MODEL instead of the
  pass's model. MODEL is one of the Claude ids in `session.MODEL_NAMES`
  (`claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`, `claude-fable-5-1`). Plan 12
  makes the name an arm of `config/driver/backends.toml`; the Claude arms keep their model
  ids as names, so the same command works before and after. The budget is the per-session
  `--max-budget-usd`, as for Opus. Effort stays as nights use it today: there is no effort
  flag. With `--canary`, `--night-model X` makes the canary session ask for X.
- `--picks FILE` restricts the night to the functions FILE lists, through the same subset
  path a Fable trial uses (`TierQueue.only` on a signed tier, the matching pool candidates
  without one). Each pick waits only on callees that are also picks. A pick that is not in
  the queue, or is already matched, is refused before anything starts, and the refusal names
  every such pick. The file has one function per line, `<exe> 0x<8 hex digits>` (for example
  `ufo2p 0x0008A0E0`). A `#` starts a comment and blank lines are ignored. A line that does not
  parse, or a pick listed twice, is refused with its line number.
- `--dry-run --stratify A,B,C --write-picks FILE` writes the pick list. It reads the signed
  tier queue's first 400 picks in queue order. It takes the first A rows under 64 B, the
  first B rows of 64 to 255 B, and the first C rows of 256 B and up. Only rows no pass ever
  finished are taken. A hold run finishes no pass, so its rows still count as unattempted. The
  three groups are the stats size buckets with the last two merged. Sizes come from
  `config/<exe>/functions.csv` (end minus start), the same numbers `stats` uses. The dry run
  then lists the chosen picks and builds their packs as any dry run does. A group that cannot
  be filled within those 400 picks makes the dry run exit 2. The refusal names the group and
  how many rows it found, and no file is written.
- `--hold` makes the night a hold run. Nothing lands: no lint, no gate, no `gate --partial`
  and no status.csv write. Each function is attempted once, although the passes would allow
  more. Every attempt record carries `hold_run: true`. An attempt whose plain check exited 0
  is recorded as `HOLD_EXACT`, never `MATCHED`. The others are `PARTIAL` or `GAVE_UP` by
  their best percent. The attempt-log commit still runs, so the hold run's records are
  committed.
- `--land-held RUN...` lands the hold runs' exact results later (see "Landing a hold run"
  below). A trailing `*` names a prefix, as in `stats --run`.

## The hold-run marker

A hold run writes `build/driver/<run>/HELD` when it starts. The context pack of every later
session leaves out three things: the notes under a run directory holding that file, the
attempt records with `hold_run: true`, and their give-ups and best C. So one arm's work never
reaches another arm's sessions. The pass index leaves hold-run records out too, so a hold run
never moves a function to its next pass. The default `reverseapoc stats` report leaves
hold-run attempts out of its counts, sums and splits. `stats --run spike012-*` reads them, with
`HOLD_EXACT` counted under "hold exact".

The dry run's `held:` line and its JSON `held` count are a different thing. They still mean
the signed asm hold: rows the signed asm list keeps out of the queue. Console text and records
say "hold run" for this harness, never "held".

## The spike 012 order of commands

1. Stratify once into a picks file, on the main checkout:
   `reverseapoc drive --dry-run --stratify 7,7,6 --write-picks build/driver/spike012-picks.txt`.
   That is 20 functions: 7 under 64 B, 7 of 64 to 255 B and 6 of 256 B and up. The six rows of
   256 B and up are the ones the 256 B todo (`.planning/todos/pending/first-matching-night-256b.md`)
   needs. Its queue reached the first 256 B row at pick 88 and the first 1 KB row at pick 289,
   so the 400-pick window covers both. If the queue cannot give six such rows, the dry run says
   so and exits 2.
2. Run one hold run per arm on that frozen list, each under its own run id:
   `reverseapoc drive --night-model claude-haiku-5-5 --picks build/driver/spike012-picks.txt --hold --run spike012-haiku`,
   then the same for the next arm (`--run spike012-sonnet`, and so on).
3. Compare the arms: `reverseapoc stats --run spike012-*`.
4. Land the results: `reverseapoc drive --land-held spike012-*`.

## Landing a hold run

`reverseapoc drive --land-held RUN...` runs on the main checkout with the drive lock and the
preflight a night uses, and it launches no session. It reads the committed attempt log and keeps
the `HOLD_EXACT` records of the hold runs the names select. A trailing `*` is a prefix, so
`spike012-*` takes every arm. A name that selects no hold run makes the drive exit 2 and name
it.

- **Once per function.** Each function lands at most once, and one that status.csv already
  matches is skipped. A second `--land-held` over the same runs therefore lands nothing new.
- **The cheapest rule.** Of a function's exact attempts, the one with the lowest `cost_usd`
  lands. Equal costs go to the earlier run id, then to the lower attempt number.
- **What lands.** The C is the attempt's latest plain check that exited 0 (its
  `checks/NNNN.c`). It is copied into a fresh view under the landing run's own directory, so
  the hold run's files stay as they were. Every rename committed since the attempt's view head
  is applied, as a night's landing does. Then the normal path runs, under the gate lock: the
  copy into src/, the C89 lint, the container gate, and the match commit of explicit paths.
  There is no second landing path. Functions land in exe, unit and address order, so two
  functions of one unit report one after the other.
- **The stale-unit refusal.** A held C is the whole unit as of its view head. If
  `src/<exe>/<unit>.c` or `include/` changed between that head and HEAD, the function is not
  landed. Its landing record is REFUSED with "unit changed since the hold run; re-run". This
  also covers a second function of a unit that an earlier landing of the same run just
  changed.
- **Credit.** The match commit carries `Matched-By: reverseapoc drive` and the co-author line
  of the attempt's requested model, for example `Co-Authored-By: Claude Haiku 5.5`. The commit
  message gives that attempt's own turns, tokens and seconds, and names the hold run.
- **Records.** Each function gets one `landing` record: MATCHED with its commit, or REFUSED
  with its reason (a lint failure or a gate refusal leaves the unit as HEAD has it). No second
  attempt record is written. A landing record has no tokens and no cost, so `stats` counts the
  cost once, in the held attempt. The end-of-run checks (`ninja verify`, `gate --all`) and the
  attempt-log commit follow, as after a night.

## The refusals

The drive refuses (exit 2), before any preflight, each of these combinations:

- `--night-model` with `--fable-trial`, `--session readability` or `--model`;
- `--hold` with `--session readability`, `--canary` or `--dry-run`;
- `--write-picks` without `--stratify`;
- `--stratify` without `--write-picks` or `--dry-run`;
- `--picks` with `--stratify`;
- `--land-held` with `--picks`, `--hold`, `--night-model`, `--stratify`, `--dry-run`,
  `--canary` or `--fable-trial`.

An unknown `--night-model` id exits 2 and names the known ids.
