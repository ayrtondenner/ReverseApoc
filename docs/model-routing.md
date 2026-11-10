# Model routing: the spike 012 harness

Spike 012 compares model arms on the same frozen set of functions. Each arm attempts each
function once, and no arm's match lands before every arm has run. The landing then credits
the cheapest arm that matched. Phase 07.2 plan 06 built the flags below (D-17). Plans 12, 13,
15 and 16 add their own sections to this page: the backends file, the Codex and Antigravity
harnesses, and several arms in one drive.

## The flags

- `--night-model ARM` runs every matching session of the night on ARM instead of the pass's
  model. ARM is an arm of `config/driver/backends.toml` (see "Backends" below). The Claude
  arms are named by their model ids (`claude-haiku-5-5`, `claude-sonnet-5-5`,
  `claude-opus-5-5`, `claude-fable-5-1`), so a Claude id works as it did before plan 12. The
  budget is the per-session `--max-budget-usd`, as for Opus. Effort stays as nights use it
  today: there is no effort flag. With `--canary`, `--night-model X` makes the canary session
  run on arm X.
- `--allow-egress ARM` is the owner's opt-in for a non-Anthropic arm (D-11). See "Backends".
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
  of the attempt's requested model, for example `Co-Authored-By: Claude Haiku 5.5`. A hosted
  arm's attempt is credited to its arm instead, as in "Backends" below. The commit message
  gives that attempt's own turns, tokens and seconds, and names the hold run.
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
  `--canary` or `--fable-trial`;
- `--allow-egress ARM` when ARM is not the `--night-model` arm, or when ARM sends nothing to a
  non-Anthropic backend.

An unknown `--night-model` arm exits 2 and names the known arms.

## Backends

Plan 07.2-12 added `config/driver/backends.toml`, the table of arms. Each `[arms.<name>]` entry
gives the harness, the backend (the provider; `anthropic` is the Claude Code login), the model
id, `sends_disassembly`, `max_workers`, and for a hosted arm its endpoint (`base_url`), the
NAME of the environment variable holding its key (`key_env`), the init ids it accepts, its
prices per million tokens and its credit line. The file holds no key. The ids, endpoints and
prices of the hosted arms were read on 2026-11-09 and are marked in the file where they are
assumptions to confirm at setup.

| Arm | Backend | Model id | Key variable |
|---|---|---|---|
| `claude-opus-5-5`, `claude-fable-5-1`, `claude-haiku-5-5`, `claude-sonnet-5-5` | anthropic | the arm name | none (the Claude Code login) |
| `deepseek-flash` | deepseek | `deepseek-flash` | `DEEPSEEK_API_KEY` |
| `glm-5.3` | zai | `glm-5.3` | `ZAI_API_KEY` |
| `muse-spark-open` | openrouter | `meta/muse-spark-open` | `OPENROUTER_API_KEY` |
| `qwen-hosted` | openrouter | `qwen/qwen3.6-35b-a3b` (to confirm) | `OPENROUTER_API_KEY` |
| `qwen-local` | local | `qwen3.6-35b-a3b` (the llama-server `--alias`) | none (loopback only) |

A hosted arm runs in the same Claude Code harness as the Claude arms, with the same hooks and
audit, against its provider's Anthropic-compatible endpoint.

- **Two flags.** A non-Anthropic arm that sends disassembly needs both `--night-model ARM`
  and `--allow-egress ARM`, for a night and for a canary alike:
  `reverseapoc drive --canary --night-model deepseek-flash --allow-egress deepseek-flash --run canary-deepseek`.
  What each backend receives is in [legal.md](legal.md#model-backends-and-what-they-receive).
- **The session environment.** Every session loses every arm's key variable and any inherited
  `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_DEFAULT_*_MODEL`, so a Claude
  arm always runs on the claude.ai login and no session sees another arm's key. A hosted
  arm's session then gets its `ANTHROPIC_BASE_URL`, its own key as `ANTHROPIC_AUTH_TOKEN`, an
  empty `ANTHROPIC_API_KEY`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, the three
  `ANTHROPIC_DEFAULT_*_MODEL` pins set to its model, and `REVERSEAPOC_EGRESS=1`. Under it the
  hook denies any Read, Glob or Grep that can reach `orig/` or `third_party/`, of this
  checkout or of a worktree in it: by any path form, by a wildcard that fits either name, by
  a `**` or a slash-free Glob pattern from the top level, and any Grep from the top level. A
  hosted session searches below `src/`, `include/` or its attempt directory instead.
- **The refusals before any session** (exit 2, before the preflight runs any command): a
  non-Anthropic arm without `--allow-egress`; an `--allow-egress` naming any other arm; a
  hosted arm whose key variable is missing, empty or blank, because Claude Code would
  otherwise send the claude.ai login to that endpoint. The message names the variable and the
  endpoint, never a value.
- **Keys.** The owner sets the three variables once as Windows user environment variables,
  as [toolchain.md](toolchain.md#model-api-keys-and-sign-ins) shows, and opens a new shell.
  Run the canary of each hosted arm through the clean-environment launcher before its first
  night.
- **Init, cost and credit.** A hosted session's init must name one of its arm's
  `accepted_init` ids, or the night stops. Its `cost_usd` is estimated from its tokens and the
  arm's prices, `cost_source: "estimate"`; the CLI's own figure for a model it does not know is
  not trusted, and `--max-turns` and the wall clock stay the runaway guards. Its match commit
  carries `Matched-By: reverseapoc drive` (so `stats` still counts an unattended match), then
  `Matched-By: <model id>` and the arm's `Co-Authored-By` line, and no Claude line.

## The local arm

`qwen-local` runs Qwen3.6-35B-A3B on the owner's own llama.cpp server and is the last arm of
spike 012 (D-18): it may slip without blocking the cloud arms, and `qwen-hosted` runs the same
weights early through OpenRouter as a fast check.

- **The server.** llama-server lives under `C:\llm\`, outside the repository, with the GGUF
  the owner chose. Start it on loopback with tool calls enabled and the model name the arm
  expects, one slot, for example:
  `C:\llm\llama-server.exe -m <gguf> --host 127.0.0.1 --port 8080 --jinja --alias qwen3.6-35b-a3b -np 1`.
  `--jinja` is needed for tool calls; `--alias` is the id the session asks for and the init
  must echo. Without `--api-key` the server ignores the token.
- **The token.** The arm has no key variable. Its session gets `ANTHROPIC_AUTH_TOKEN=local`
  (`backends.LOOPBACK_TOKEN`), a fixed non-empty value, so Claude Code never falls back to the
  claude.ai login. A base URL that is not loopback always needs a key variable.
- **One worker.** The server has one slot, so `max_workers = 1` and `--workers 2` with
  `--night-model qwen-local` is refused. Its CPU also competes with the check compiles of the
  same night.
- **No egress flag.** `sends_disassembly = false`: nothing leaves the machine, so the arm takes
  no `--allow-egress` and one naming it is refused. Its cost is 0, recorded as an estimate.
- **Order.** `reverseapoc drive --canary --night-model qwen-local --run canary-qwen-local`, then
  the hold run: `reverseapoc drive --night-model qwen-local --workers 1 --picks build/driver/spike012-picks.txt --hold --run spike012-qwen-local`.
