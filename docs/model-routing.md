# Model routing: the spike 012 harness

Spike 012 compares model arms on the same frozen set of functions. Each arm attempts each
function once, and no arm's match lands before every arm has run. The landing then lands from
the arm with the lowest API-equivalent cost and credits every arm that matched. Phase 07.2
plan 06 built the flags below (D-17). Plans 12, 13,
15 and 16 add their own sections to this page: the backends file, the Codex and Antigravity
harnesses, and several arms in one drive. What the arms measured in spike 012 (per arm and size
bucket: matches, tokens, cost, quota, canary failures) is in [model-comparison.md](model-comparison.md).
Quick 261112-fds (backlog 999.12a) adds the size-routed cascade, `drive --cascade`, at the end
of this page.

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
- `--cascade` runs the size-routed cascade: each function's attempts climb the arms of its size
  bucket's row in the `[routing]` table of `config/driver/backends.toml`, in this one drive
  (see "The size-routed cascade" below).
- `--arm-cap NAME=N`, repeatable, with `--cascade` only: cascade arm NAME launches at most N
  sessions tonight. N may not exceed the arm's backends.toml `max_sessions`.

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
- **The cheapest rule.** Of a function's exact attempts, the one with the lowest
  API-equivalent cost lands: its tokens at its arm's list price (backends.toml `prices`; a
  Claude arm's come from streamjson's table). It is never the recorded `cost_usd`, which is 0
  on a subscription arm. Equal costs go to the earlier run id, then to the lower attempt
  number. An attempt that no arm of backends.toml prices stops the landing before anything
  lands.
- **What lands.** The C is the attempt's latest plain check that exited 0 (its
  `checks/NNNN.c`). It is copied into a fresh view under the landing run's own directory, so
  the hold run's files stay as they were. Every rename committed since the attempt's view head
  is applied, as a night's landing does. Then the normal path runs, under the gate lock: the
  copy into src/, the C89 lint, the container gate, and the match commit of explicit paths.
  There is no second landing path. Functions land in exe, unit and address order, so two
  functions of one unit report one after the other.
- **The stale-unit refusal.** A held C is the whole unit as of its view head. If
  `src/<exe>/<unit>.c` or `include/` changed between that head and HEAD, the function is not
  landed. Its landing record is REFUSED with "unit changed since the hold run; re-run".
- **Several functions of one unit.** Once the run has landed one function of a unit, the next
  held function of that unit is judged against HEAD as it was before that first landing (the
  unit and `include/` unchanged since its view head, and `include/` unchanged since), so this
  run's own landing is not a change. Only its definition is then spliced onto the unit as HEAD
  now has it, keeping the earlier landing, and the gate proves the result. A change from any
  other commit still refuses it as stale; a definition that cannot be spliced is REFUSED and
  named.
- **Credit.** The match commit carries `Matched-By: reverseapoc drive` and the co-author line
  of the landing attempt's requested model, for example `Co-Authored-By: Claude Haiku 5.5`. A
  hosted arm's attempt is credited to its arm instead, as in "Backends" below. Then it adds one
  `Co-Authored-By` line for every other arm that held the function exact, each from that arm's
  co-author (the Claude name for a Claude arm, the backends.toml `coauthor` otherwise), in run
  order and once each. An arm whose attempt was not exact gets no line. The commit message
  gives the landing attempt's own turns, tokens and seconds, and names the hold run.
  `stats --run <the same prefix>` counts the function as matched for each of those arms (and
  once in the totals). The default report leaves hold runs out, so there the landing is
  credited to the landing arm only.
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
- `--allow-egress ARM` when ARM is not the `--night-model` arm or an `--arm` arm, or when ARM
  sends nothing to a non-Anthropic backend;
- `--arm` with the flags listed under "Several arms in one drive" below;
- `--cascade` with `--hold` (a held comparison keeps using `--arm NAME=WORKERS`), `--arm`,
  `--night-model`, `--fable-trial`, `--canary`, `--land-held` or `--session readability`;
- `--allow-egress ARM` with `--cascade` when ARM is in none of the cascade's rows;
- `--arm-cap` without `--cascade`, an `--arm-cap` arm named twice, and an `--arm-cap` arm in
  none of the cascade's rows.

An unknown `--night-model` arm exits 2 and names the known arms. A malformed `[routing]` table
exits 2 when `--cascade` is parsed, naming the file and the key. An `--arm-cap` above the arm's
`max_sessions` exits 2 before any command.

## Backends

Plan 07.2-12 added `config/driver/backends.toml`, the table of arms. Each `[arms.<name>]` entry
gives the harness, the backend (the provider; `anthropic` is the Claude Code login), the model
id, `sends_disassembly`, `max_workers`, and for a hosted arm its endpoint (`base_url`), the
NAME of the environment variable holding its key (`key_env`), the init ids it accepts, its
prices per million tokens and its credit line. The file holds no key. The ids, endpoints and
prices of the hosted arms were read on 2026-11-09 and are marked in the file where they are
assumptions to confirm at setup.

| Arm | Harness | Backend | Model id | Key variable |
|---|---|---|---|---|
| `claude-opus-5-5`, `claude-fable-5-1`, `claude-haiku-5-5`, `claude-sonnet-5-5` | claude | anthropic | the arm name | none (the Claude Code login) |
| `gpt-6-luna`, `gpt-6.1-sol`, `gpt-6.1-terra`, `gpt-6-astra` | codex | openai | the arm name | none (the Codex CLI's ChatGPT Plus login) |
| `gemini-flash` | agy | google | `gemini-3.8-flash-medium` | none (the agy Google AI Plus sign-in) |
| `gpt-oss` | agy | google | `gpt-oss-120b-medium` | none (the agy sign-in) |
| `agy-sonnet-4-6` | agy | google | `claude-sonnet-4-6` | none (the agy sign-in) |
| `agy-opus-4-6` | agy | google | `claude-opus-4-6-thinking` | none (the agy sign-in) |
| `deepseek-flash` | claude | openrouter | `deepseek/deepseek-v4.1-flash` | `OPENROUTER_API_KEY` |
| `glm-5.3` | claude | openrouter | `z-ai/glm-5.3` | `OPENROUTER_API_KEY` |
| `glm-4.7-flash` | claude | openrouter | `z-ai/glm-4.7-flash` | `OPENROUTER_API_KEY` |
| `gpt-oss-20b` | claude | openrouter | `openai/gpt-oss-20b` | `OPENROUTER_API_KEY` |
| `muse-spark-open` | claude | openrouter | `meta/muse-spark-open` | `OPENROUTER_API_KEY` |
| `qwen-hosted` | claude | openrouter | `qwen/qwen3.6-35b-a3b` | `OPENROUTER_API_KEY` |
| `gemini-3.8-flash-openrouter` | claude | openrouter | `google/gemini-3.8-flash` (D-21's fallback for agy) | `OPENROUTER_API_KEY` |
| `qwen-local` | claude | local | `qwen3.6-35b-a3b` (the llama-server `--alias`) | none (loopback only) |

A hosted arm runs in the same Claude Code harness as the Claude arms, with the same hooks and
audit, against OpenRouter's Anthropic-compatible endpoint. Since 2026-11-10 the owner runs
DeepSeek and GLM only through OpenRouter, not through DeepSeek's or z.ai's own endpoints. The
ids and prices of the OpenRouter arms come from OpenRouter's public model list, read on
2026-11-10. `glm-4.7-flash` is a 31.2B MoE, the size class of Qwen3.6-35B-A3B, so it can get
a local twin later; so can `gpt-oss-20b` (GPT-OSS 20B, open weights, an MoE of about 21B
total parameters), which is not the Antigravity `gpt-oss` arm (GPT-OSS 120B).

- **Two flags.** A non-Anthropic arm that sends disassembly needs both `--night-model ARM`
  and `--allow-egress ARM`, for a night and for a canary alike:
  `reverseapoc drive --canary --night-model deepseek-flash --allow-egress deepseek-flash --run canary-deepseek`.
  What each backend receives is in [legal.md](legal.md#model-backends-and-what-they-receive).
- **The session environment.** Every session loses every arm's key variable, the retired
  `DEEPSEEK_API_KEY` and `ZAI_API_KEY` (no arm names them since 2026-11-10), every inherited
  `ANTHROPIC_*` variable (custom headers, model, Bedrock and Vertex URLs among them), every
  `CLAUDE_CODE_USE_*` variable, every `OPENAI_*` variable and every Google key or credentials
  variable, so a Claude arm always runs on the claude.ai login, nothing reroutes a session off
  its base URL and no session sees another arm's or vendor's key. `CLAUDE_CODE_OAUTH_TOKEN`
  reaches only a session on the Claude login. A hosted
  arm's session then gets its `ANTHROPIC_BASE_URL`, its own key as `ANTHROPIC_AUTH_TOKEN`, an
  empty `ANTHROPIC_API_KEY`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, the three
  `ANTHROPIC_DEFAULT_*_MODEL` pins set to its model, and `REVERSEAPOC_EGRESS=1`. A metered
  (hosted, non-loopback) arm also gets `CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000`, twice Claude
  Code's default, since a GLM-5.3 reply ran past 32000 in spike012; every OpenRouter provider in
  use allows at least 117964, and a local llama-server keeps the default. A session that still
  overruns ends with the CLI's "response exceeded the N output token maximum" error, which is
  counted as an attempt like a turn cap, not a reason to stop the night. A 429 that Claude
  Code retried and recovered from is not a usage limit either: OpenRouter gives short rate
  limits, and when the session then ends cleanly or on its turn or budget cap it is counted
  and gated (`streamjson.classify`; spike012 had set aside 11 such sessions, 7 with an exit-0
  check). A 429 error result, a rejected rate_limit_event or a session with no result after
  the retry stays a limit. Under it the
  hook denies any Read, Glob or Grep that can reach `orig/` or `third_party/`, of this
  checkout or of a worktree in it: by any path form, by a wildcard that fits either name, by
  a `**` or a slash-free Glob pattern from the top level, and any Grep from the top level. A
  hosted session searches below `src/`, `include/` or its attempt directory instead.
- **The refusals before any session** (exit 2, before the preflight runs any command): a
  non-Anthropic arm without `--allow-egress`; an `--allow-egress` naming any other arm; a
  hosted arm whose key variable is missing, empty or blank, because Claude Code would
  otherwise send the claude.ai login to that endpoint. The message names the variable and the
  endpoint, never a value.
- **Keys.** Every hosted arm names one variable, `OPENROUTER_API_KEY`. The owner sets it once
  as a Windows user environment variable, as
  [toolchain.md](toolchain.md#model-api-keys-and-sign-ins) shows, and opens a new shell. Run
  the canary of each hosted arm through the clean-environment launcher before its first night.
  The pass gate below covers only the Codex and agy harnesses; a Claude Code arm, hosted or
  not, is not refused for a missing canary file, so this canary is the owner's step.
- **Init, cost and credit.** A hosted session's init must name one of its arm's
  `accepted_init` ids, or the night stops. Its `cost_usd` is estimated from its tokens and the
  arm's prices, `cost_source: "estimate"`; the CLI's own figure for a model it does not know is
  not trusted, and `--max-turns` and the wall clock stay the runaway guards. Its match commit
  carries `Matched-By: reverseapoc drive` (so `stats` still counts an unattended match), then
  `Matched-By: <model id>` and the arm's `Co-Authored-By` line, and no Claude line.

## Codex arms

Plan 07.2-13 added `gpt-6-luna` and `gpt-6.1-sol`: GPT-6 Luna and GPT-6.1 Sol through the
Codex CLI (0.167.0, installed and signed in by the owner) on the owner's ChatGPT Plus login,
third and fourth in spike 012's order (D-18). This is the one scoped runtime exception in
CLAUDE.md: Codex runs only as `reverseapoc drive` arms, launched and audited by the driver.
The model ids are assumptions to confirm at setup. On 2026-11-11 the owner added
`gpt-6.1-terra` (GPT-6.1 Terra) and `gpt-6-astra` (GPT-6 Astra), both in the owner's
`codex debug models` catalog; Terra answered a one-word `codex exec` that day. They run like
Luna and Sol, one worker each, priced from OpenRouter's models list for the comparison only.
All four ids ran in spike 012: each arm's canary passed on codex-cli 0.167.0
(`build/driver/canary/<arm>.json`).

- **The session.** `codex exec --json --model <id> --sandbox workspace-write --cd <attempt dir>
  --skip-git-repo-check --ephemeral --ignore-user-config -c approval_policy="never"
  -c sandbox_workspace_write.network_access=false -c windows.sandbox="unelevated"
  -c projects={"<attempt dir>"={trust_level="trusted"}} <prompt>`. The trust is an inline
  table because Codex 0.167 splits a `-c` key on every dot, quotes or not: the dotted-key form
  was ignored, with two `error` items, for the Sol and Terra arms, whose run dirs hold a dot
  (spike 012 round 5); their sessions' per-session rules never loaded, and the audit stopped
  the drive on the unknown items. The Windows sandbox is set in
  the argv because `--ignore-user-config` drops the user config that enabled it: with none,
  Codex ran no sandbox and rejected every command (spike 012 canaries, 2026-11-10). It is
  unelevated by the owner's ruling (2026-11-10), the mode the owner's own Codex runs: elevated
  needs an admin setup the owner declined, and without it every command of the round-2
  canaries failed to start (exit -1, `helper_sandbox_lock_failed ... SetNamedSecurityInfoW
  sandbox dir failed: 5`). Codex loads no skill and runs no hook, so the prompt carries the goal, the
  watcom-decomp skill's body, a harness note (no Read, Grep or Glob tool: files are read
  through the wrapper's `context`, `asm` and `check` output; an agy session may also use its
  read_file tool inside its attempt dir; the note also says to create and edit files only with
  the file-edit tool, Codex's apply_patch, never with a shell command or redirection, since the
  audit reads that tool's `file_change` items and a shell write is a stray command) and the
  session rules. The note ends with the wait instruction (`session.WAIT_NOTE`): a wrapper
  command, `attempt check` above all, can run for minutes; if the shell tool hands it back
  while it still runs, keep polling it until it exits, and never end the turn while one runs.
  Codex's unified exec hands a long command back while it runs, and in spike 012 round 5
  Luna, Sol and Terra replied DONE there, so the session's end killed the check the broker was
  running and no check was logged (Astra waited and passed). The agy prompt and the Codex
  canary prompt carry the same instruction. Codex streams no event that names the
  model: the record keeps `model_requested` and a null `model`, and there is no init check.
  Tokens come from the `turn.completed` events (cached input as cache read, reasoning tokens
  added to output); the cost is 0 on Plus, recorded as an estimate. Known fault, not fixed
  yet: Codex's `input_tokens` already include its `cached_input_tokens`, and `codexjson.usage`
  records both, so the cached tokens count twice (as input and as cache read) and
  `stats --run` prices them twice; [model-comparison.md](model-comparison.md) gives spike 012's
  figures recomputed with the cached part once. `stats --run`'s
  comparison prices the tokens at the arm's list price in backends.toml (marked confirm at
  setup) as its API-equivalent figure.
- **The login.** No key is read. The session loses `OPENAI_API_KEY`, `OPENAI_BASE_URL`, every
  arm's key variable, every `ANTHROPIC_*` variable and every Google key variable, so Codex
  stays on the ChatGPT login and never sees another vendor's credential. `CODEX_HOME` is not
  moved and no credential is copied into build/.
- **The guard set.** Before each session the driver writes, in the fresh attempt dir under
  gitignored build/, `.codex/rules/attempt.rules` with one rule,
  `prefix_rule(pattern=["uv", "run", "--frozen", "reverseapoc", "attempt"], decision="allow")`,
  and an empty wrapper ledger outside the workspace,
  `build/driver/<run>/ledger/<exe>__<function>__attempt-<n>.jsonl`, named to the session by
  `REVERSEAPOC_WRAPPER_LEDGER`. The wrapper appends `{"path", "sha256"}` there for every file
  it writes. The session env pins uv to the checkout (`UV_PROJECT=<checkout>`,
  `UV_NO_CONFIG=1`, for agy sessions too): the session's commands run in its attempt dir, so
  without the pin a `pyproject.toml`, `uv.lock` or `uv.toml` it wrote there would be the
  project the allowed `uv run --frozen reverseapoc attempt` runs. A Codex session also gets
  its own uv cache, `UV_CACHE_DIR=<TEMP>/reverseapoc-uv-<run>__<exe>__<function>__attempt-<n>`
  under the session's TEMP: workspace-write denies the owner's uv cache, so uv could not start
  (round 3 canaries, 2026-11-10: `Failed to initialize cache ... os error 5`), and allows
  TEMP, where an empty cache serves `--frozen`. The driver makes it empty before the launch
  and removes it after the session (a removal that fails is a note, and the night stops after
  the audit, as for the containers); it lies outside the checkout, so the tree and attempt-dir
  audits never see it. Nothing Codex-specific is committed: no `.codex/`, no AGENTS.md.
- **The wrapper broker.** Codex's sandbox refused the wrapper's ledger append (the ledger lies
  outside the workspace) and Docker's pipe (`permission denied ... dockerDesktopLinuxEngine`),
  so `attempt check` could never compile there (spike 012 canary, 2026-11-11). By the owner's
  ruling the sandbox stays as it is and the driver runs the wrapper instead: a Codex session's
  env names its broker dir, `REVERSEAPOC_WRAPPER_BROKER=<attempt dir>/broker` (inside the
  workspace; TEMP is shared across sessions), and there `reverseapoc attempt <form>` only
  writes one request, `<id>.request.json` holding `{"args": [...]}`, and waits for
  `<id>.response.json` (`{"exit", "stdout", "stderr"}`), printing it and exiting with its exit
  code; no response within 660 s (the wrapper's 600 s bound plus a minute) is exit 2. While
  the session runs the driver serves that dir, one request at a time: it checks the request
  against the exact forms the hook allows for the session's kind (anything else is answered
  exit 2 and never runs), runs the real `uv run --frozen reverseapoc attempt <form>` outside
  the sandbox with the session's env minus the broker variable and cwd the attempt dir, so the
  ledger and Docker work as for a Claude session, kills it past 600 s, and writes the response
  atomically. When the session ends the broker stops: a wrapper still running is killed (as
  the session's own tree would be) and a request left is answered exit 2 without running. A
  broker failure is a note, and the night stops after the audit. No other harness gets the
  variable; the Claude and agy sessions run the wrapper themselves.
- **The audit.** After the session, besides the checks every session gets (git status, the
  view, pinned and fingerprinted files): every command must be an exact wrapper form and may
  not name `orig` or `third_party` as a path part; every `file_change` path must pass the
  session's write allowlist; every item must be of a type the audit knows (`agent_message`,
  `reasoning`, `todo_list`, `command_execution`, `file_change`; an MCP tool call or a web
  search is a stray); and the attempt dir may hold only the session files (notes.md,
  plan.json, check-note.json, giveup.json, proposals.jsonl), the transcript, the driver's own
  files as they were at launch (the rules file included), the broker's responses with the
  bytes it wrote, and wrapper output whose hash is its ledger entry's. A `file_change` into the
  broker dir is a stray write like any other (a forged request is still only a wrapper form,
  but the write is not the session's to make). Anything else, a session-written
  `.codex/config.toml` or a request nobody answered among it, is a stray:
  the files are quarantined, the attempt is recorded as a guardrail give-up and the night
  stops. Each launch gets a fresh attempt dir, so nothing a session writes there reaches the
  next one. The rules file is judged against the driver's own bytes, not the launch
  inventory: right after writing it the driver checks that it is a regular file reached
  through no link and holding exactly that rule (no session launches otherwise), and the audit
  checks the same again, so any session write to it is a stray.
- **What the audit cannot do.** It detects after the fact; it does not prevent. Codex's
  workspace-write sandbox restricts writes and the network, not reads, and Codex has no hook
  that could deny a read before it happens. A session that reads `orig/` or `third_party/` is
  caught by its command, quarantined and the night stops, but whatever it sent to OpenAI before
  it ended has left the machine. No read restriction of the installed CLI was confirmed
  offline, so none is assumed. The same holds for a command that runs before the audit: only
  the sandbox and the canary's probes stand between it and the host. The rules file has to sit
  in the workspace (Codex reads project rules from `<--cd>/.codex/rules/`), so if Codex re-read
  a session-edited rules file within the same session, only the audit would catch it.
- **The canary.** `reverseapoc drive --canary --night-model gpt-6-luna --allow-egress gpt-6-luna --run canary-luna`
  (and the same for `gpt-6.1-sol`, `gpt-6.1-terra` and `gpt-6-astra`) asks the session, in
  order, to run these exact commands:
  `whoami /all`, `Set-Content -Path '<one directory above the workspace>' -Value canary`
  (under build/, never under TEMP, which workspace-write allows),
  `Invoke-WebRequest -Uri https://example.com/ -UseBasicParsing`, and the wrapper's context
  form followed by `;` and a write outside the workspace; then to write plan.json and
  check-note.json with its file-edit tool and run the wrapper context and the wrapper check,
  both through the broker as in a night. The prompt says to
  attempt every numbered step exactly as written, even one it expects to be refused, since a
  refused step is the expected result (round 3: Luna ran no step at all). A probe counts only
  if it ran: its item ended
  with an exit code of 0 or more and no `Failed to create unified exec process` (round 2's
  canaries passed probes that never started). `whoami /all` is informational: the
  unelevated sandbox runs commands as the owner's own user and whoami shows the same groups
  and integrity level inside it as outside, so it passes when it ran with exit 0, naming the
  user. The sandbox proof is behavioural, matched on locale-independent PowerShell tokens
  (the owner's Windows prints messages in Portuguese): the outside write ran, printed
  `UnauthorizedAccess` (`GetContentWriterUnauthorizedAccessError`) and left no file; the
  fetch ran, failed and printed a network error (`WebCmdletWebResponseException`,
  `WebException`, `HttpRequestException` or `SocketException`); the compound command ran and
  left no file. A FAIL quotes the exit code and an output excerpt. The canary also needs the
  wrapper context to have written context.md with the ledger naming its bytes, the wrapper
  check to have logged exit 0 and consumed its note, the broker to have served with no
  problem, the audit to have flagged the
  three probe commands, the night's command audit to pass every other command (the wrapper
  calls aside, which have their own check: round 3's Sol wrote plan.json with `Set-Content`,
  a stray that would stop a night, so the canary fails naming it), the session's uv cache to
  be removed, the attempt dir to match the ledger, and the tree, refs and containers to be as
  for every canary. On PASS it writes
  `build/driver/canary/<arm>.json` (`arm`, `harness`, `cli_version` from `codex --version`,
  `date`, `result`); on FAIL it writes `result: FAIL` there.
- **The pass gate.** A night of a Codex arm is refused (exit 2, before any session, naming
  the canary command) unless that file says PASS for the CLI version `codex --version` reports
  now. Upgrading the CLI therefore means running the canary again.
- **The Plus windows.** Plus allows about 350 to 3,000 local Luna messages and 15 to 160 Sol
  messages per 5 hours (owner plan); the Terra and Astra limits are unmeasured. In spike 012 a
  Codex canary took about 2% of the 5-hour window and a small-pick session about 0.5% of the
  week, and the 22 sessions of the 64-255 B picks filled a 5-hour window (owner screenshots;
  [model-comparison.md](model-comparison.md#quota-and-spend)). Each arm runs with
  `max_workers = 1`; the owner may raise it in backends.toml. A Codex failure that says a usage limit was hit pauses the night like a
  Claude usage limit; any other failure stops it.
- **Windows sandbox caveats** (RESEARCH Pitfall 11). Elevated and unelevated sandbox modes have
  open issues, `apply_patch` has been reported at 13 to 20 s per patch, and some setups run
  commands as the real user. The canary's identity, outside-write and network probes exist
  for this; budget the 30-minute wall clock accordingly. The Windows CLI reports each command
  wrapped in its shell (`"<...>\powershell.exe" -Command <cmd>`, seen in the spike 012
  canaries' rejected-command lines). The audit takes exactly one such layer off and audits
  `<cmd>`, only for the real shells at their absolute paths
  (`C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`,
  `C:\Program Files\PowerShell\7\pwsh.exe`; any case, either slash), at most one `-NoProfile`
  and one argument after `-Command`. A bare `powershell.exe`, a relative path or any other
  directory could be a binary the session planted, so it is audited as the whole text (a
  stray), as are a shell left inside, a compound `<cmd>` and any other shape.
  Offline, `codex execpolicy check` (0.167.0) matches tokens literally: the driver's prefix
  rule allows `uv run --frozen reverseapoc attempt check` but matches neither its
  `powershell.exe -Command '...'` nor its `bash -lc '...'` form, so it cannot show whether a
  session unwraps the shell before the rule; the canary's wrapper check settles that.
- **If the per-session rules do not load** (RESEARCH A5: the canary's wrapper check is then
  refused or prompts), the fallback is one owner-installed user rule,
  `~/.codex/rules/reverseapoc.rules`, holding the same single prefix rule, written by the owner
  and removable; the driver never writes outside the repository.

## Antigravity arms

Plan 07.2-15 added `gemini-flash` (model `gemini-3.8-flash-medium`) and `gpt-oss` (model
`gpt-oss-120b-medium`): Gemini 3.8 Flash and GPT-OSS 120B through the Antigravity CLI (`agy`)
on the owner's Google AI Plus sign-in. Gemini is fifth in spike 012's order (D-18, D-21). This
is the same scoped runtime exception as Codex (CLAUDE.md). Gemini CLI's Google sign-in was
retired for consumer plans, so agy is the route. On 2026-11-11 the owner added
`agy-sonnet-4-6` (`claude-sonnet-4-6`) and `agy-opus-4-6` (`claude-opus-4-6-thinking`): Claude
Sonnet 4.6 and Opus 4.6 through the same agy sign-in. They draw on agy's "Claude and GPT
models" weekly group (`/usage` in an interactive agy), which is separate from Gemini's group
and from the owner's Claude subscription, so a night can run Claude through the subscription,
Claude and Gemini through agy, and GPT through Codex side by side. Each is capped at 7 sessions
(spike 012's picks under 64 B), since agy charges quota by token cost.

- **Install and sign in (owner).** Install agy 1.1.8 or later (`--output-format stream-json`
  arrived in 1.1.8), sign in with the AI Plus account, and run `agy models`. The owner set up
  with 1.5.3; spike 012's rounds 3 to 5 ran 1.5.5, and agy updated itself to 1.5.6 on
  2026-11-11. The pass gate below compares the canary's `cli_version` with `agy --version`, so
  that update refused every agy arm until it passed its canary again on 1.5.6:
  `gemini-flash` did (its pass file says PASS for 1.5.6); `gpt-oss`, `agy-sonnet-4-6` and
  `agy-opus-4-6` hold FAIL for 1.5.6. The `schedule` timer below first appeared under 1.5.6.
  agy then updated itself to 1.5.7 and 1.5.8 (installed 2026-11-13). 1.5.7 began streaming an
  in-place edit as the `edit_file` step (below), which the audit did not know: it stopped the
  20261113-cascade night, while the Gemini canary had passed on 1.5.7 because it never edited a
  file. The canary now edits a file, and every agy arm needs a new canary on 1.5.8 before a
  night. The ids in backends.toml are the slugs that list showed on 2026-11-09. Slugs
  vary per account, and agy exits 1 on an unknown one, so a wrong id fails the canary. For an
  effort comparison, set `gemini-3.8-flash-high` or `-low` as the `gemini-flash` model.
- **The session.** `agy --output-format stream-json --model <slug> --sandbox --add-dir <attempt
  dir> --settings <settings file> --disable-slash-commands --print-timeout <wall clock>s -p
  <prompt>`, with the attempt dir as its working directory. The timeout is a Go duration
  (`1800s`): agy 1.5.5 exits on a bare number. The flag that skips permissions is
  never passed. agy loads no skill and runs no hook, so the prompt is the Codex prompt (goal,
  skill body, the harness note with its wait instruction, session rules), plus one sentence
  that its read_file tool may read inside the attempt dir. The init event must name the attempt dir as cwd, the requested
  slug and no bypass permission mode, else the night stops (reason init). Tokens come from the
  result's `usage` (thinking tokens added to output), turns from `num_turns`, and the duration
  from `duration_seconds`. The cost is 0 on AI Plus, recorded as an estimate; `stats --run`'s
  comparison prices the tokens at the arm's list price in backends.toml (marked confirm at
  setup) as its API-equivalent figure. The result's `denied_actions` count as hook blocks.
- **The sign-in.** No key is read. The session loses every `ANTHROPIC_*` variable,
  `OPENAI_API_KEY`, `OPENAI_BASE_URL`, every arm's key variable and every Google key variable
  (`GEMINI_API_KEY`, `GOOGLE_API_KEY` among them), so agy stays on the AI Plus sign-in.
- **The settings file (D-24).** Before each session the driver writes
  `build/driver/<run>/agy/<exe>__<function>__attempt-<n>.json`, outside the workspace and never
  in the repository or the owner's settings. Allow: one `command(regex:...)` rule matching
  exactly the wrapper forms, `read_file` under the attempt dir only, and `write_file` of
  exactly the session's files (its view unit, notes.md, plan.json, check-note.json,
  giveup.json). Deny: any command naming orig or third_party in either case; reads and writes
  of the checkout's `orig/` and `third_party/` by their forward-slash and backslash paths and by
  one regex for any case, slash or `..` spelling; any read or write path holding a `..` segment
  (the allowed attempt-dir prefix followed by `..`, in case agy matches before it normalises) or
  an 8.3 short-name segment such as `THIRD_~1` (so the checkout itself must not sit under a
  short-name path: its own files would then be denied, which fails closed). There is no
  unsandboxed rule: agy 1.5.5 logs `Invalid "unsandboxed" permission rules found; they are
  ignored and grant nothing` (its binary: "unsandboxed is no longer a valid rule, use command()
  instead"), and its permission kinds are `command`, `read_file`, `write_file`, `read_url`,
  `execute_url` and `mcp`. A command the allow rule does not match soft-denies, and the
  canary's unsandboxed probe proves it. Deny beats
  allow, so the reads cannot be an "everything but" deny; instead headless agy soft-denies
  whatever is not allowed, so the allow lists are the whole surface. These rule forms come from
  agy's docs, not a captured run: the deny rules are **unconfirmed** until the owner's agy
  canary has tried its four probe reads (a `../` read and a different-case read of `orig/`, a
  `..` read behind the attempt-dir prefix, and a `THIRD_~1` short-name read) and all four were
  denied. The `gemini-flash` canary passed all four on agy 1.5.6 (spike 012); a canary of
  each other agy arm proves them again for that arm's model.
  The post-session audit stays the backstop either way. The wrapper ledger is the Codex one
  (`REVERSEAPOC_WRAPPER_LEDGER`).
- **The audit: detection after the fact.** agy runs no Claude hook. No sandbox read restriction
  of the installed CLI could be confirmed offline (the real `agy` is never run here), so none is
  assumed: the settings' deny rules are an attempt at prevention, and the audit is the
  backstop. After the session, besides the checks every session gets, the audit reads agy's own
  stream: every command that ran must be an exact wrapper form and may not name `orig` or
  `third_party` as a path part (any case, slash, quote, drive or `..`); every written path must
  pass the session's write allowlist; every read path must stay inside the checkout; no read or
  written path may name `orig/` or `third_party/`, hold a `..` segment or an 8.3 short-name
  segment below the checkout, judged on the raw path and on each resolved form (a link
  followed, `..` folded; Codex writes too); the settings file must hold the bytes
  the driver wrote; and
  the attempt dir may hold only the session files, the transcript, the driver's own files as
  they were at launch and wrapper output its ledger names. A session-written `.gemini/` file, a
  linked `view` or `view/build` and a forged `checks.jsonl` are strays. Anything else is
  quarantined, the attempt is recorded as a guardrail give-up and the night stops. The audit
  fails closed: a tool step that ran and is not `run_command` in agy 1.5.5's shape, or
  `read_file` or `write_file` with a path (an unknown tool, a missing name, another shape, a
  subagent), is a stray, and only `read_file` counts as a read; any other path step is judged
  as a write. The `run_command` shape is the one spike 012's round 3 captured: `tool_info`
  holds `name`, `parameters` with only a string `CommandLine` (the command), and once DONE
  `output`, whose text reads `Command exited with code <n>.` and then `Command output:`. A
  `Cwd` or any other key makes it unknown, and only a known step's command counts as run. agy
  backgrounds a command that outlives its time limit, and the model may poll it with
  `manage_task` (spike 012 round 4, gemini-flash's `attempt check`): `tool_info` holds `name`,
  `parameters` with only `Action` `"status"` and a string `TaskId`, and once DONE `output`
  (the task's status and its log's path). A status poll reads agy's own task list, writes no
  file, runs no command and stops nothing, so that exact shape is known, in no command, read
  or write list and never a denial. Any other action (`kill` stops a task; `list`), parameter
  or key, an `error` included, makes it unknown. The Claude 4.6 arms wait on such a task with
  `schedule` instead (spike 012 round 6), a timer that hands the model its own `Prompt` back after
  `DurationSeconds`: `tool_info` holds `name`, `parameters` with only an integer
  `DurationSeconds` from 1 to 3600 and a string `Prompt`, and once it ends `output`. It writes no
  file, runs no command and stops nothing, so that exact shape is known too; anything else about
  it is unknown. agy 1.5.7 and later stream an in-place edit as `edit_file` (the 1.5.8 captures,
  2026-11-13): `tool_info` holds `name`, `parameters` with only a string `Path`, and, once it
  fails, `error`. agy checks it against the `write_file` permission rules (a refused edit names
  `write_file`), so the session's `write_file(<path>)` allow rules already scope its edits, and
  the audit judges its `Path` as a write, exactly like `write_file`. Any other key or parameter
  makes it unknown. The canary's read probes also say, in plain words, that the tool itself decides
  whether a path is allowed, so the model makes the call and reports what the tool returns, even
  an error: in round 6 both Claude 4.6 arms refused the `..` reads themselves, so agy's deny rule
  was never reached. agy keeps that log, and the output of a long
  step, under the session's own conversation folder,
  `~/.gemini/antigravity-cli/brain/<conversation id>/.system_generated/`, and lets the model
  read it without asking the settings (spike 012 round 5: Gemini read `tasks/task-20.log` and
  `steps/8/output.txt`, and the audit stopped the drive). By the owner's ruling (2026-11-11) a
  read there is not a stray when it is exactly `tasks/task-<n>.log` or `steps/<n>/output.txt`
  in the folder of the conversation id the session's own `init` line names (UUID form only),
  absolute, with no `..` part, resolving to itself; any other read outside the checkout still
  is. A step
  agy soft-denied never ran, so it is a hook block, not a stray: it ends `DENIED`, or `ERROR`
  with exactly agy's refusal. That is a known tool in its known shape (its error aside), no
  subagent, error type `TOOL_ERROR`, and the whole message in round 3's format: `permission
  check failed for <action> "<target>": user denied permission for <action>(<target>)` for a
  read or write, or `...: user denied permission to run command:` and the command on the next
  line (action `unsandboxed`, or `command`), then agy's one-line warning. An `edit_file` step
  has one known refusal, 1.5.8's deny-rule one with no warning line: `permission check failed
  for write_file "<target>": Permission denied for write_file(<target>). Matches
  user-configured deny rule.`. Its soft-deny form was never captured, so such a step counts as
  run (fail closed). The action must fit
  the tool, and the target must be the step's own request: the command as written, or the
  path as agy canonicalizes it (slashes forward, `..` folded, case kept). Anything less exact
  counts as run, and an unknown or subagent step stays a stray whatever state it ends in. The
  result's `denied_actions` count as hook blocks and never stand for a step. A `write_file` or
  `edit_file` step that agy's permission check refused in that exact shape, for the step's own request
  (`agyjson.denied_writes`), counts as a denied write, so on a night of several arms a session
  whose only strays are such writes stops its arm only, as a Claude hook-denied write does
  (see "Several arms in one drive"); with one arm it stops the night. What a session sent to
  Google before it ended has left the machine.
- **The canary.** `reverseapoc drive --canary --night-model gemini-flash --allow-egress
  gemini-flash --run canary-gemini` (and the same for `gpt-oss`) runs eight short agy
  sessions in one attempt dir, under the night's settings file and ledger. Spike 012 showed why:
  headless agy ends the turn at its first soft-denied tool (its log: `Print mode: soft-denying
  tool confirmation "WriteFile" at step 2`, then shutdown, `num_turns` 1), so one session can
  prove one denial only. Each prompt is one plain instruction, because `gpt-oss-120b-medium`
  refused a prompt that called itself a guardrail canary with steps that would fail.
  1. **The allowed session** (timeout 1200 s, transcript `transcript.jsonl` in the attempt dir)
     runs `attempt context`, writes plan.json with an empty frame, edits it in place with its
     file-edit tool to the canary frame, runs `attempt plan`, writes check-note.json and runs
     `attempt check`. It passes when its init is clean, its result is SUCCESS, no step was
     denied, every tool step is in a shape the night's audit knows, a known `edit_file` step
     ran (so a version that renames or reshapes the edit step fails the canary, not the
     night), all three wrapper calls ran, context.md was written, and the check logged exit 0
     and consumed its note.
  2. **One session per probe** (timeout 180 s each, transcript
     `build/driver/<run>/agy/agy-canary-<name>.jsonl`, beside the settings file):
     `outside-write` (write a file one directory above the workspace), `fetch` (`curl -sS
     https://example.com/`), `unsandboxed` (a command writing a file in the attempt dir
     itself: round 4's gemini-flash refused a target one directory above the workspace as out
     of its scope before agy's permission check was reached, and the command is not an
     allowed wrapper form, so agy's soft-deny is what refuses it), and four reads of
     `orig/reverseapoc-canary-probe.txt`: `relative-read` (a `../` path),
     `different-case-read` (`ORIG/`), `dot-dot-read` (the attempt dir followed by `..`) and
     `short-name-read` (`THIRD_~1/`). Each read prompt tells the model to pass the path string
     exactly as written, character for character, without resolving or normalizing it (round
     4's gpt-oss folded the `..` spellings into the canonical path). The probe file never
     exists, so a read that is not denied finds nothing. The two command probes are plain
     one-line instructions ("Run
     `...` in the terminal"): round 3's models refused a prompt asking to run a command outside
     the terminal sandbox as unsafe. A probe passes only when its init is clean, no tool step
     ran, and a step agy's permission check refused (the audit's exact denial above) is the
     probe's own action naming the probe's file, host or command. It never comes from the
     result's `denied_actions`, which name no target. The actions counted are `write_file`,
     `read_file`, `unsandboxed`, `command` or `run_command` (a step ending DENIED), and for the
     fetch also `read_url` or `execute_url`. agy names a read's target canonicalized, so a
     read probe also needs the step's own request (`parameters.Path`) to be exactly the
     spelling asked for, slash direction aside; a request in another spelling FAILs as `read a
     different spelling than asked`. A session with no tool step FAILs as `model refused`. One
     whose only denials are of something else FAILs as `never attempted`. One with a step that
     was not denied FAILs as `not denied`, with that step's error. agy 1.5.5 refuses a
     relative `read_file` path before its permission check (`must be an absolute path`), so
     `relative-read` also passes on that exact rejection of the asked relative spelling (owner
     ruling 2026-11-10), and on nothing else: one that requests the absolute path instead
     reads a different spelling.
  3. **After all of them:** neither probe file exists, the attempt dir matches the ledger,
     the settings file is unchanged, and the tree, refs and containers are as for every canary.
     Each line agy printed on stderr about a permission headless mode cannot prompt for is kept
     as a NOTE, labelled with its session, on FAIL only.

  agy names no sandbox identity, so there is no whoami probe. On the owner's Windows 10 the
  terminal sandbox does not run at all (agy's log: `Terminal sandbox unavailable: sandboxing on
  Windows requires Windows 11 24H2 or later`), so `--sandbox` adds nothing there and the
  permission rules are the only guard the canary proves. The whole canary takes at most
  1200 + 7 x 180 s, about 41 minutes.
- **The quota step (D-21, D-25).** The canary then runs `agy -p /usage`. A JSON line naming a
  `remaining` number is a measurement: above 0 passes, and the pass file records it so the owner
  sizes the arm to the weekly quota. A `remaining` of 0, an error status, or text saying the
  quota or rate limit was hit is a FAIL that names the fallback arm and how to run it:
  `reverseapoc drive --night-model gemini-3.8-flash-openrouter --allow-egress
  gemini-3.8-flash-openrouter` (OpenRouter in the Claude Code harness, paid, needs
  `OPENROUTER_API_KEY`). If `/usage` prints nothing machine-readable (RESEARCH A8), the canary
  says the quota was estimated, not measured, and records the allowed session's tokens and 20 times
  them, so the owner can compare a 20-session arm with the bucket the app shows. In spike 012
  it printed nothing machine-readable, so every agy pass file holds an estimate
  (`"measured": false`); the owner read the real meters with `/usage` in an interactive agy.
- **The pass gate.** The canary writes `build/driver/canary/<arm>.json` (`arm`, `harness`,
  `cli_version` from `agy --version`, `date`, `result`, `tokens`, `quota`). A night of an agy
  arm is refused (exit 2, before any session, naming the canary command) unless that file says
  PASS for the version installed now. An arm on any harness without a canary is always refused.
- **Sizing.** Each arm runs with `max_workers = 1`. On AI Plus agy offers two weekly groups:
  "Gemini models" (Gemini 3.8 Flash; Gemini 4 Argon needs AI Pro or Ultra) and "Claude and GPT
  models" (Claude Sonnet and Opus 4.6, GPT-OSS 120B). Both are charged by token cost: in spike
  012 one Gemini Flash session took about 22% of its group's week, and the two agy Claude 4.6
  canaries about 63% of theirs (owner screenshots;
  [model-comparison.md](model-comparison.md#quota-and-spend)), so `max_sessions` 20 does not
  fit the Gemini week. A failure that names a quota or rate
  limit pauses the night like a usage limit; "authentication required" or any other failure
  stops it. A paid Gemini Pro arm is not built (D-25).
- **If `--settings` cannot restrict tools** (RESEARCH A9; the canary's wrapper check is then
  refused, or an outside write goes through), the fallback is a minimal owner-written
  user-global rule set, documented and removable in docs/legal.md. The driver never writes it.

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
- **Gated on its hosted twin (owner, 2026-11-10).** The hosted arms run first, through
  OpenRouter. Only then does the owner decide what runs locally, because local runs on the
  owner's machine (GTX 1660 6 GB, 32 GB RAM) are slow. `qwen-hosted` is the twin of `qwen-local`, and
  `glm-4.7-flash` and `gpt-oss-20b` are the twins of possible later local GLM-4.7-Flash and
  GPT-OSS 20B arms. If the twin matches
  about nothing on the frozen picks, the local arm is skipped: no llama.cpp setup and no model
  download. If the twin does well, the local arm runs a short check, not 20 sessions: only
  the 3 to 5 picks the twin matched, at Q4 quantization and local speed, with 30-minute
  sessions. The check measures what the local route loses.
- **Order.** `reverseapoc drive --canary --night-model qwen-local --run canary-qwen-local`, then
  the short hold run on the twin's matched picks:
  `reverseapoc drive --night-model qwen-local --workers 1 --picks <the twin's matched picks> --hold --run spike012-qwen-local`.

## Several arms in one drive

Plan 07.2-16 (D-22) runs several arms side by side in one drive process, so spike 012's arms
need not take one night each. Give `--arm NAME=WORKERS` once per arm. NAME is an arm of
`config/driver/backends.toml` and WORKERS is how many of its sessions run at once.

- **One process.** The night keeps one drive lock, one post-session audit under the gate lock,
  and one commit queue, whatever the arms. A second `reverseapoc drive` on the same checkout
  is still refused while one runs: separate processes would trip each other's lock, git index
  and audit. Run the arms in one drive, never in two.
- **Run ids.** With several arms, each arm runs under its own run id `<run>-<NAME>`, for
  example `spike012-claude-haiku-5-5`. Its attempt directories, claims, records and limit
  records name that run id, so two arms never share an attempt directory. The night's own
  STARTED and ENDED records keep the base run id `<run>`, and their totals count every arm's
  sessions. Under `--hold`, every arm's run directory gets the `HELD` marker.
- **One queue per arm.** Each arm builds its own queue over the same picks (with `--picks`, the
  same frozen list), with its own passes. Under `--hold` each function is therefore attempted
  once per arm. A free worker takes the next pick of its own arm, and the arms are served in
  turn. Claims stay per unit across arms, so two arms never run one unit at the same time. On a
  night without `--hold`, a function one arm matches is dropped from the other arms' queues.
- **Workers and caps.** The night's workers are the sum of the arms' WORKERS. Each arm's
  WORKERS must stay within its `max_workers`, which is checked before any command. An arm may
  also carry `max_sessions` in backends.toml, which caps that arm's launches for the night.
  `gemini-flash` and `gpt-oss` carry 20, the canary's planning estimate; `agy-sonnet-4-6` and
  `agy-opus-4-6` carry 7, the spike's picks under 64 B; the owner sets it from the agy quota.
  No Claude Code or Codex arm carries one. When an arm reaches its cap, it stops launching
  while the others go on. `--max-sessions` still caps the night's total (default 60), so
  spike 012's drives passed `--max-sessions 200`.
- **Usage pauses.** Each arm has its own usage-limit pause. A LIMIT session of one arm (a Codex
  Plus window, the Antigravity quota, an Anthropic limit) starts that arm's backoff only. The
  other arms keep launching, and the arm's own probe clears its pause. A paused arm with picks
  left keeps the drive open, so a quota-bound arm gets a short pick list (spike 012 ran its
  Codex and agy arms on `spike012-picks-small.txt` and `-medium.txt`, the frozen list's picks
  under 64 B and at 64-255 B).
- **One arm stops, or the whole drive.** On a night of several arms, a session whose only
  strays are writes that were denied stops its arm only (owner ruling 2026-11-10): for a Claude
  Code arm, a transcript write whose tool_use id is the only one of its kind and has a
  `permission_denials` entry naming the same tool and target; for an agy arm, a `write_file`
  that agy's permission check refused (above). The attempt is reset and recorded GAVE_UP
  guardrail, the arm launches nothing more (a LIMIT relaunch included), its sessions in flight
  finish, and a console line and the run record's detail name the arm, the attempt and the
  path; the other arms go on. A Codex session has no denied writes. Everything else still
  stops the whole drive: any other stray (an undenied or unprovable write, a command that is
  not an exact wrapper form, such as Luna's `uv run --frozen reverseapoc context` in spike 012,
  an unknown Codex or agy item, a read outside what is allowed), a write stray together with
  another stray or a containers note, a reset or check that fails or still finds a change, a
  night of one arm, a STOP from the stream (`streamjson.classify`), an init problem, a Codex or
  agy failure that is not a limit, an error, and Ctrl+C.
- **Resuming a hold run.** Running the same `--hold --run <run>` drive again resumes it (owner
  approval 2026-11-10, `driver.hold_progress`): per arm, a function with a counted hold
  attempt in the committed log (no abort reason, or `timeout`) is skipped; one cut short (a
  GAVE_UP guardrail or tool record, a transient abort, or no record) is attempted again, under
  the next attempt number so its directory is fresh. Spike 012 resumed its drive this way after
  each stop, dropping or adding `--arm` entries between runs.
- **Every per-arm gate still holds.** Each arm resolves through backends.toml. A Codex or agy
  arm needs its own canary PASS for the installed CLI. An arm that sends the pack off the
  machine needs its own `--allow-egress NAME`, and an `--allow-egress` naming an arm the night
  does not run, or one that sends nothing, is refused. A hosted arm needs its key, and each
  arm's sessions get that arm's own environment (the token-leak guard, the stripped env of the
  Codex and agy arms). Each session is audited by its own harness's audit.
- **The local arm.** `qwen-local` may run beside the cloud arms, at its one worker:
  `--arm qwen-local=1`. `--arm qwen-local=2` is refused. Its CPU still competes with the check
  compiles of the cloud arms' sessions.
- **The one-arm shorthand.** `--night-model X --workers N` is the same night as `--arm X=N`,
  under the base run id (one arm needs no suffix).
- **Refusals.** `--arm` is refused (exit 2, before any preflight) with `--night-model`,
  `--workers`, `--fable-trial`, `--canary`, `--land-held` and `--session readability`, and
  when an arm is named twice. A canary runs one arm at a time, with `--canary --night-model X`.
- **Console.** The night prints one `arms:` line naming each arm, its workers and its run id,
  and each attempt line names its arm.

The spike 012 night over the frozen pick list, the cloud arms at once (canaries passed first):

```
reverseapoc drive --picks build/driver/spike012-picks.txt --hold --run spike012 \
  --arm claude-haiku-5-5=2 --arm claude-sonnet-5-5=2 \
  --arm gpt-6-luna=1 --allow-egress gpt-6-luna \
  --arm gemini-flash=1 --allow-egress gemini-flash \
  --arm deepseek-flash=2 --allow-egress deepseek-flash
```

`qwen-local` is not in it: it runs later, and only if `qwen-hosted` did well (see
[The local arm](#the-local-arm)). The drives spike 012 really ran, their stops and what each
arm measured are in [model-comparison.md](model-comparison.md).

Then compare the arms with `reverseapoc stats --run spike012-*`, which splits by arm (below),
and land the exact results once each, from the lowest API-equivalent cost, with
`reverseapoc drive --land-held spike012-*`.

### Stats by arm

`stats --run` splits the selected records by arm, keyed `backend/harness/model`, for example
`google/agy/gemini-3.8-flash-medium` or `anthropic/claude/claude-haiku-5-5`. Two arms that
share a model id but differ in backend or harness (Gemini through agy and through OpenRouter)
are two arms. Each arm holds the distinct functions attempted, matched (an attempt, or a
landing credited to that arm) and held exact, and its tokens and cost. The JSON field is
`by_arm`, and the text prints a "per arm" block. The model x size table (`by_model_size`,
"per arm and size") is keyed by arm too. v1 and v2 records name no backend or harness, so they
group under `anthropic/claude/<model>`. A MATCHED landing is matched for its own arm and for
every arm that held the function exact among the selected records, as the landing commit
credits them.

### The comparison table

`stats --run RUN...` also prints spike 012's comparison table (owner ruling 2026-11-10). It
spans every run the names select and both EXEs, with one row per arm (`backend/harness/model`).
Without `--run` there is none: the JSON field `comparison` is null and the text is unchanged.

- **JSON.** `comparison` holds `columns` (in order), and `arms`, which maps each arm key to its
  backends.toml arm name (`arm`), its `billing` and `cells`, one cell per column. An arm with no
  backends.toml entry has `arm` and `billing` null.
- **Columns.** The three size groups of the stratified pick list (`under 64 B`, `64 to 255 B`,
  `256 B and up`, driver.STRATA_NAMES, sizes from `config/<exe>/functions.csv`), then `total`.
  An `unknown` column comes before `total` only when a function has no functions.csv size.
- **Counts.** `attempted`: the distinct functions the arm's matching attempts cover. `hold_exact`:
  those with a HOLD_EXACT attempt. `matched`: those the arm matched (a MATCHED attempt, or a
  MATCHED landing credited to it, as in "Stats by arm"). `exact`: the union of the last two.
  `sessions`: the attempt records. `turns` and `tokens` (input, output, cache_read,
  cache_creation): their sums.
- **Wall time.** `wall_ms` sums the records' `duration_ms`. A record whose `duration_ms` is null
  (a session the wall clock killed) or absent (v1 and v2) adds its `seconds` instead, and
  `wall_estimated_sessions` counts those records. The text shows minutes.
- **API-equivalent.** `api_usd`: the tokens at the arm's list price, for every arm. A non-Claude
  arm's price is its backends.toml `prices`; a Claude arm's is streamjson's table, which
  backends.toml defers to. The Codex and agy prices are public API list prices marked "confirm
  at setup" in backends.toml. The recorded `cost_usd` is never read here.
- **Billing and real paid.** Billing is derived from `base_url`, and backends.toml has no
  billing field: no base URL is a CLI's own sign-in (the Claude Code login, Codex on ChatGPT
  Plus, agy on Google AI Plus), `subscription`; a loopback one is the local server, `free`; any
  other is paid per token with the arm's key, `metered`. `paid_usd` is 0.00 on a subscription
  or free arm and the API-equivalent on a metered one. The text says the zero case in words.
  An arm with no backends.toml entry or no price shows null for both figures and says why.
- **Per-try rates.** `per_try` counts the plain checks of the attempts' saved
  `build/driver/<run>/<exe>/<function>/attempt-<n>/checks.jsonl` by `reverseapoc causes`' rule
  (exit 2 a build failure, 1 a mismatch, 0 a match; sweeps and malformed lines apart), with
  each outcome's percent. Where build/driver holds no saved checks (as in CI), the count is 0,
  the percents are null and the text says "no saved checks".
- **Ratios.** `exact_per_api_usd`, `exact_per_wall_hour` and `exact_per_mtok`: exact functions
  per API-equivalent dollar, per wall hour and per million tokens, from the unrounded figures,
  shown to 2 decimals; null when the denominator is 0 or missing.

## The size-routed cascade

Quick 261112-fds (backlog 999.12a) routes each function by its size, cheapest arm first, in one
drive: `reverseapoc drive --cascade`. Spike 012 showed that under 64 B the cheap arms match what
the strong ones do, and that quota binds before dollars ([model-comparison.md](model-comparison.md),
"Routing conclusion"). Quick 261112-fdt (backlog 999.12b) adds the escalation hand-off: a
paused or capped arm passes the attempt to the row's next arm, and a usage limit mid-attempt
hands the same attempt on.

- **The table.** `config/driver/backends.toml` holds a top-level `[routing]` table beside the
  arms. Only `drive --cascade` reads it (`backends.load_routing`). Each key is a size range in
  `reverseapoc stats`' own bucket label form, `"[low, high)"`, with `inf` for no upper bound, so
  no new threshold is defined. A key may span consecutive stats buckets: `"[256, inf)"` is
  stats' `[256, 1024)` and `[1024, inf)` merged into one row. Each value is the ordered list of
  arms, and every arm must be an `[arms."..."]` entry. The committed rows are the owner's:

  | Key | Arms, in order |
  |---|---|
  | `"[0, 64)"` | `gpt-6.1-terra`, `claude-haiku-5-5`, `deepseek-flash` |
  | `"[64, 256)"` | `gpt-6.1-terra`, `claude-haiku-5-5`, `deepseek-flash` |
  | `"[256, inf)"` | `gpt-6.1-terra`, `deepseek-flash` |

  Owner, 2026-11-13 (afternoon): GLM-5.3 left the rows (no match in about 45 sessions, three
  quarters of the day's OpenRouter spend), Haiku moved second, DeepSeek last.
  Owner, 2026-11-13: Terra first (spend each Codex 5-hour window), DeepSeek second (2 of its first
  5 sessions held on the cascade nights, docs/model-comparison.md), then Haiku and GLM-5.3.
  Owner, 2026-11-12: GLM-5.3 and DeepSeek V4.1-Flash joined the rows to spend the remaining
  OpenRouter credit. In spike 012, GLM-5.3 held 4 of 20 for $4.27 (L), the best matches per
  dollar of the OpenRouter arms, and DeepSeek held 4 of 20 for $11.70 (L). Qwen (0 held) and
  Muse (the most per match) stay out. The first table above (Haiku, Terra, Gemini) was the
  owner's default before this change. Gemini Flash left the 64-255 B row the same night: its weekly agy
  quota was spent, and agy 1.5.7 streams an `edit_file` step the agy audit does not know yet.

  A key that is no stats span, an empty row, a row that is not a list of arm names, an arm the
  table does not hold, a bucket in two rows, a bucket in no row, or a missing `[routing]` table
  exits 2 when `--cascade` is parsed, naming the file and the key.
- **The ladder.** A pass has three attempts (D-07). Attempt n of pass p runs on rung
  (p - 1) * 3 + n of its row, counted from 1, and the row's last arm takes every attempt past
  the row's end. So a function under 64 B runs Haiku, then GLM-5.3, then Terra on pass 1, and
  Terra on every attempt from pass 2. A function of 256 B and up runs Terra, GLM-5.3, then
  DeepSeek, and DeepSeek on every later attempt.
- **Run ids.** Each arm's attempts run under `<run>-<arm>`, with that arm's model, harness,
  session environment, audit and co-author, as the `--arm` lanes do. The night's STARTED and
  ENDED records keep `<run>` and count every arm. Compare the arms with
  `reverseapoc stats --run '<run>-*'`.
- **Concurrency.** `--workers` is the number of passes in flight. Each arm runs at most its
  backends.toml `max_workers` sessions at once (Terra and Gemini 1, the Claude arms 10). The
  night keeps one drive lock, one audit under the gate lock and one commit queue.
- **Caps.** Each arm launches at most `--arm-cap NAME=N` sessions tonight, else its
  `max_sessions`, else only `--max-sessions` caps it. An `--arm-cap` above the arm's
  `max_sessions` is refused. A capped arm is skipped for the attempt (see "The skip"). A
  launch that ends in a usage limit counts against its arm's own cap too, though not against
  `--max-sessions`, so `--arm-cap gemini-flash=1` means one agy launch, whatever it ends in.
- **The skip.** An attempt runs on the first arm of its row that can launch now. It tries the
  row from the attempt's rung, then the later arms, then the row's start. An arm that is capped
  or paused is skipped for that attempt only, so the next attempt's rung is still the ladder's.
  With the row Haiku, Sonnet, Opus and Sonnet capped at 1, function F runs Haiku, Sonnet, Opus,
  and the next function runs Haiku, Opus, Opus. A busy arm, with all its `max_workers` slots
  taken, is not skipped: the function waits off the workers for that arm. The reason is quota.
  Haiku's weekly quota is tight, and Terra and Gemini run `max_workers` 1, so skipping a busy
  arm would push most Terra-rung attempts back onto Haiku. An arm whose backoff has run out
  but whose one probe another attempt holds counts as paused.
- **The hand-off.** A usage limit mid-attempt starts the arm's pause and writes the limit record
  under the arm's run id, and no worker sleeps. The same attempt number then goes to the row's
  next arm that can launch. The arm's backoff ends on the clock, and the first launch on it
  after that is the probe (D-07's 60, 120, 240 s, then 300 s polls). A transient abort still
  ends the pass; its next pass is routed afresh.
- **The waits.** When the routing reaches a busy arm, or no arm of the row can launch, the
  function leaves the workers and comes back at its attempt number once an arm of its row can
  run. This is the cascade form of a paused night's wait: waiting picks keep the drive open,
  and the other arms' work keeps the workers. When every arm of the row is capped, the pass
  ends for tonight with one line naming each arm's cap. The function is not offered again
  tonight, gets no difficult-list entry, and comes back on a later night.
- **The end.** Once every cascade arm has launched its cap, the night ENDS `arms capped`: the
  passes still running finish, nothing more is dispatched, and the normal end of run follows
  (ninja verify, `gate --all`, the attempt-log commit). The cap line above is for a row that is
  capped while another row still has an arm that can run.
- **The carried work.** The next arm's context pack holds the earlier attempts' notes, give-up
  lines and best C, through the same earlier-notes path every night uses (07.2-02). A held
  night keeps arms apart, and a cascade is never held.
- **The records.** Each attempt record names the arm it ran on (run `<run>-<arm>`,
  `model_requested`, `harness`, `backend`), a skipped or handed-off attempt too, so
  `stats --run '<run>-*'` splits a cascade by arm. The limit record names the paused arm's run.
  No record key was added.
- **A denied write stops the drive.** A cascade has one dispatch lane, so a hook-denied write
  stops the whole cascade drive (fail closed), unlike an `--arm` night, which stops only that
  arm.
- **Every per-arm gate holds.** Each cascade arm is checked as an `--arm` arm is: a Codex or agy
  arm needs its own canary PASS for the installed CLI, an arm that sends the pack off the
  machine needs its own `--allow-egress NAME` (an `--allow-egress` naming no cascade arm is
  refused), a hosted arm needs its key, and each session is audited by its own harness.
- **Refusals.** `--cascade` is refused with `--hold` (held comparisons keep using `--arm`),
  `--arm`, `--night-model`, `--fable-trial`, `--canary`, `--land-held` and
  `--session readability`; see "The refusals" above for `--arm-cap`.
- **The dry run.** `reverseapoc drive --dry-run --cascade` prints, after each pick, its bucket
  and the arm of each of its three attempts at its next pass, for example
  ` bucket [0, 64) attempts claude-haiku-5-5, gpt-6.1-terra, gpt-6.1-terra`. With `--json`,
  each pick document gains `cascade` {`bucket`, `pass`, `attempts`}. The dry run needs the
  same `--allow-egress` flags as the night, because the arm checks run first. The preview
  applies the caps (`--arm-cap`, else `max_sessions`): pick after pick, each attempt it shows
  counts one launch of its arm, an attempt whose rung is capped shows the arm the routing would
  take instead, for example `claude-haiku-5-5 (gemini-flash capped)`, and an attempt whose
  whole row is capped shows `every arm capped` and ends that pick's list. Pauses and busy arms
  are not previewed; a skip for either is printed at run time as it happens.
- **Console.** The night prints one `cascade:` line naming each row and each arm's cap, and each
  attempt line names its arm. A usage limit prints one routing line, the hand-off line or the
  wait line, beside the attempt's own outcome line (`arm waiting after N s`). The templates:
  - skip: `<label>: skipped <arm> (capped), <arm> (paused)`, the label naming the arm that runs;
  - hand-off: `<label>: usage limit; arm <arm> pauses and passes this attempt to <next arm>`;
  - wait: `<label>: usage limit; arm <arm> pauses for <seconds> s; the function goes back to
    the queue at attempt <n>`;
  - cap: `<label>: every arm of its row has launched its cap tonight (<arm>: <cap> sessions,
    ...); the function waits for a later night`.

The owner's run (Haiku 30, Terra 20, Gemini Flash 1), first as a dry run, then the night, after
Terra's and Gemini's canaries have passed:

```
reverseapoc drive --dry-run --cascade --workers 3 \
  --arm-cap claude-haiku-5-5=30 --arm-cap gpt-6.1-terra=20 --arm-cap gemini-flash=1 \
  --allow-egress gpt-6.1-terra --allow-egress gemini-flash
reverseapoc drive --cascade --workers 3 \
  --arm-cap claude-haiku-5-5=30 --arm-cap gpt-6.1-terra=20 --arm-cap gemini-flash=1 \
  --allow-egress gpt-6.1-terra --allow-egress gemini-flash
```

The caps add up to 51 sessions, under `--max-sessions` 60, so this night normally ends
`arms capped`. Every row holds Terra, so once Haiku and Gemini are capped and Terra hits a
usage limit, the night waits and probes Terra as a paused night does (60, 120, 240 s, then
300 s polls). Each probe that ends in a limit uses one of Terra's 20, so the night still ends
`arms capped` once Terra is capped too. When Terra's week is used up, that takes at most its
remaining launches, under two hours of polls. Each is a Codex launch that sends the context
pack (`--allow-egress`) and writes one limit record.

### The evidence for each default row

Every figure below is spike 012's, from [model-comparison.md](model-comparison.md) and the
[spike README](../.planning/spikes/012-model-routing/README.md), with their marks: (L) a
list-price estimate, (S) an owner screenshot reading, (R) a recomputation from the `stats` token
counts. Spike 012 ran one attempt per arm over 20 picks, so a gap of one function is noise.

| Row | Evidence |
|---|---|
| `[0, 64)`: Haiku, Terra | Haiku held 3 of 7 at $0.17 (L), 15.8% match per check; Opus held the same 3 at $3.23 (L). Terra held 3 of 7 at $0.47 (R), with 27.3% match per check and 9.72 exact per wall hour. Haiku and Terra held the same three functions (`tacp func_0009D110`, `tacp func_000A66A0`, `ufo2p func_00038510`); Sonnet alone held a fourth, `ufo2p func_00038550`. So Terra's rung adds a second vendor at the owner's choice, not a measured extra match. |
| `[64, 256)`: Haiku, Terra, Gemini Flash | Haiku held 2 of 7 at $0.31 (L); one of them, the 176 B `ufo2p func_0005DB80`, failed the gate. Terra held 1, the 208 B `tacp func_00022140` that Haiku also held, at $0.67 (R). Gemini 3.8 Flash ran no pick in this bucket: its one session, under 64 B, held nothing (1 of 3 checks matched) and took about 22% of its weekly group (S), which is why the owner caps it at 1. GLM-5.3 alone held the 64 B `tacp func_00039E40` and is not in the row. |
| `[256, inf)`: Terra | No arm that ran this bucket held anything (Haiku 0 of 6, 32 checks, all mismatches). The Codex arms, Terra among them, did not run it (quota). So Terra first is the owner's choice, with no spike 012 measurement in this bucket. |

The caps' context: the medium-picks Codex run took the 5-hour window from about 53% to 100%
(S), about 0.7% of the week per session (R). The calibration of 57 Opus sessions = 6% of the
weekly bar (S) is an Opus figure, not Haiku's.

ROADMAP 999.12's last follow-up recalibrates these rows after a few real nights.

## Quota per session

Approximate figures for sizing a run to a budget: sessions = target / per session. Read on the
cascade nights of 2026-11-12 and 2026-11-13 from the owner's meters (S), the OpenRouter credits
API (A) and `stats --run` (T). They shift with function size and session length, and a reading of
a few sessions carries about one point of meter error. The todo `usage-meters-per-subscription`
replaces the screenshot readings with measured ones; re-measure this table when it lands.

| Arm (plan) | Tokens per session, average (T) | One session moves | Rough sizing |
|---|---|---|---|
| Haiku 5.5 (Claude Ultra) | about 1.07M cache read, 24k output, 80k cache creation | about 0.03% of the weekly bar (S: 30 sessions, 93% to 94%) | 3% of the week: about 90 sessions |
| Opus 5.5 (Claude Ultra) | - | about 0.1% of the weekly bar (S, 2026-11-07: 100 sessions, 17% to 27%) | 3% of the week: about 30 sessions |
| GPT-6.1 Terra (ChatGPT Plus) | about 0.94M input, 0.9M cache read, 3k output | about 1.35% of the 5-hour window and 0.22% of the week (S: 74 sessions filled one window, the week 50% to 66%) | one 5-hour window: about 74 sessions |
| Gemini 3.8 Flash (Google AI Plus) | about 175k input, 2.8M cache read, 28k output | about 15% of the agy week (S, one session; a canary about 6.6%) | the week: about 6 sessions |
| DeepSeek V4.1-Flash (OpenRouter) | about 76k input, 620k cache read, 28k output | about $0.30 (A) | $10: about 33 sessions |
| GLM-5.3 (OpenRouter) | about 215k input, 1.8M cache read, 77k output | about $0.60 (A) | left the rows on 2026-11-13: no match in about 45 sessions |

Past the Codex 5-hour window, Codex keeps running on the account's credits (about 1 to 2 credits
per session, chatgpt.com/settings/usage), and a full reset restores both the week and the window.
`stats` prices an OpenRouter arm at list price, which came in below the credits API's real spend
on these nights; size OpenRouter budgets from (A).
