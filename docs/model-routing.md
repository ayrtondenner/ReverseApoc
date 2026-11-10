# Model routing: the spike 012 harness

Spike 012 compares model arms on the same frozen set of functions. Each arm attempts each
function once, and no arm's match lands before every arm has run. The landing then lands from
the arm with the lowest API-equivalent cost and credits every arm that matched. Phase 07.2
plan 06 built the flags below (D-17). Plans 12, 13,
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
- `--arm` with the flags listed under "Several arms in one drive" below.

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
- **The session environment.** Every session loses every arm's key variable, every inherited
  `ANTHROPIC_*` variable (custom headers, model, Bedrock and Vertex URLs among them), every
  `CLAUDE_CODE_USE_*` variable, every `OPENAI_*` variable and every Google key or credentials
  variable, so a Claude arm always runs on the claude.ai login, nothing reroutes a session off
  its base URL and no session sees another arm's or vendor's key. `CLAUDE_CODE_OAUTH_TOKEN`
  reaches only a session on the Claude login. A hosted
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

## Codex arms

Plan 07.2-13 added `gpt-6-luna` and `gpt-6.1-sol`: GPT-6 Luna and GPT-6.1 Sol through the
Codex CLI (0.167.0, installed and signed in by the owner) on the owner's ChatGPT Plus login,
third and fourth in spike 012's order (D-18). This is the one scoped runtime exception in
CLAUDE.md: Codex runs only as `reverseapoc drive` arms, launched and audited by the driver.
The model ids are assumptions to confirm at setup.

- **The session.** `codex exec --json --model <id> --sandbox workspace-write --cd <attempt dir>
  --skip-git-repo-check --ephemeral --ignore-user-config -c approval_policy="never"
  -c sandbox_workspace_write.network_access=false -c projects."<attempt dir>".trust_level="trusted"
  <prompt>`. Codex loads no skill and runs no hook, so the prompt carries the goal, the
  watcom-decomp skill's body, a harness note (no Read, Grep or Glob tool: files are read
  through the wrapper's `context`, `asm` and `check` output; an agy session may also use its
  read_file tool inside its attempt dir) and the session rules. Codex streams no event that names the
  model: the record keeps `model_requested` and a null `model`, and there is no init check.
  Tokens come from the `turn.completed` events (cached input as cache read, reasoning tokens
  added to output); the cost is 0 on Plus, recorded as an estimate. `stats --run`'s
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
  project the allowed `uv run --frozen reverseapoc attempt` runs. Nothing Codex-specific is
  committed: no `.codex/`, no AGENTS.md.
- **The audit.** After the session, besides the checks every session gets (git status, the
  view, pinned and fingerprinted files): every command must be an exact wrapper form and may
  not name `orig` or `third_party` as a path part; every `file_change` path must pass the
  session's write allowlist; every item must be of a type the audit knows (`agent_message`,
  `reasoning`, `todo_list`, `command_execution`, `file_change`; an MCP tool call or a web
  search is a stray); and the attempt dir may hold only the session files (notes.md,
  plan.json, check-note.json, giveup.json, proposals.jsonl), the transcript, the driver's own
  files as they were at launch (the rules file included) and wrapper output whose hash is its
  ledger entry's. Anything else, a session-written `.codex/config.toml` among it, is a stray:
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
  (and the same for `gpt-6.1-sol`) asks the session, in order, to run `whoami`, write a file
  one directory above its workspace, fetch `https://example.com/`, run the wrapper's context
  form followed by `;` and a write outside the workspace, write plan.json and check-note.json,
  and run the wrapper check. It passes only when the identity is not the owner's `USERNAME`,
  neither outside file exists afterwards, the fetch failed, the wrapper check logged exit 0 and
  consumed its note, the audit flagged the three probe commands, the attempt dir matches the
  ledger, and the tree, refs and containers are as for every canary. On PASS it writes
  `build/driver/canary/<arm>.json` (`arm`, `harness`, `cli_version` from `codex --version`,
  `date`, `result`); on FAIL it writes `result: FAIL` there.
- **The pass gate.** A night of a Codex arm is refused (exit 2, before any session, naming
  the canary command) unless that file says PASS for the CLI version `codex --version` reports
  now. Upgrading the CLI therefore means running the canary again.
- **The Plus windows.** Plus allows about 350 to 3,000 local Luna messages and 15 to 160 Sol
  messages per 5 hours (owner plan). Each arm runs with `max_workers = 1`; the owner may raise
  it in backends.toml. A Codex failure that says a usage limit was hit pauses the night like a
  Claude usage limit; any other failure stops it.
- **Windows sandbox caveats** (RESEARCH Pitfall 11). Elevated and unelevated sandbox modes have
  open issues, `apply_patch` has been reported at 13 to 20 s per patch, and some setups run
  commands as the real user. The canary's identity, outside-write and network probes exist
  for this; budget the 30-minute wall clock accordingly. A Codex command may also be reported
  wrapped in its shell (`powershell.exe -Command ...`), which the audit treats as a non-wrapper
  form: the canary shows it, and it fails closed.
- **If the per-session rules do not load** (RESEARCH A5: the canary's wrapper check is then
  refused or prompts), the fallback is one owner-installed user rule,
  `~/.codex/rules/reverseapoc.rules`, holding the same single prefix rule, written by the owner
  and removable; the driver never writes outside the repository.

## Antigravity arms

Plan 07.2-15 added `gemini-flash` (model `gemini-3.8-flash-medium`) and `gpt-oss` (model
`gpt-oss-120b-medium`): Gemini 3.8 Flash and GPT-OSS 120B through the Antigravity CLI (`agy`)
on the owner's Google AI Plus sign-in. Gemini is fifth in spike 012's order (D-18, D-21). This
is the same scoped runtime exception as Codex (CLAUDE.md). Gemini CLI's Google sign-in was
retired for consumer plans, so agy is the route.

- **Install and sign in (owner).** Install agy 1.1.8 or later (`--output-format stream-json`
  arrived in 1.1.8; the owner has 1.5.3), sign in with the AI Plus account, and run
  `agy models`. The ids in backends.toml are the slugs that list showed on 2026-11-09. Slugs
  vary per account, and agy exits 1 on an unknown one, so a wrong id fails the canary. For an
  effort comparison, set `gemini-3.8-flash-high` or `-low` as the `gemini-flash` model.
- **The session.** `agy --output-format stream-json --model <slug> --sandbox --add-dir <attempt
  dir> --settings <settings file> --disable-slash-commands --print-timeout <wall clock>s -p
  <prompt>`, with the attempt dir as its working directory. The timeout is a Go duration
  (`1800s`): agy 1.5.5 exits on a bare number. The flag that skips permissions is
  never passed. agy loads no skill and runs no hook, so the prompt is the Codex prompt (goal,
  skill body, session rules). The init event must name the attempt dir as cwd, the requested
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
  short-name path: its own files would then be denied, which fails closed); and every
  unsandboxed command. Deny beats
  allow, so the reads cannot be an "everything but" deny; instead headless agy soft-denies
  whatever is not allowed, so the allow lists are the whole surface. These rule forms come from
  agy's docs, not a captured run: the deny rules are **unconfirmed** until the owner's agy
  canary has tried its four probe reads (a `../` read and a different-case read of `orig/`, a
  `..` read behind the attempt-dir prefix, and a `THIRD_~1` short-name read) and all four were
  denied.
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
  fails closed: a tool step that ran and is not `run_command` with a command, or `read_file` or
  `write_file` with a path (an unknown tool, a missing name, another shape, a subagent), is a
  stray, and only `read_file` counts as a read; any other path step is judged as a write. A
  step whose own last state is `DENIED` never ran, so it is a block, not a stray; the result's
  `denied_actions` count as hook blocks and never stand for a step. What a session sent to
  Google before it ended has left the machine.
- **The canary.** `reverseapoc drive --canary --night-model gemini-flash --allow-egress
  gemini-flash --run canary-gemini` (and the same for `gpt-oss`) asks the session, in order, to
  write a file one directory above its workspace, fetch `https://example.com/`, run an
  unsandboxed command that writes a file outside the workspace, read
  `orig/reverseapoc-canary-probe.txt` by a `../` path from the attempt dir, as an absolute
  `ORIG/` path and as the attempt dir's absolute path followed by `..` segments, read
  `THIRD_~1/reverseapoc-canary-probe.txt`, write plan.json and check-note.json, and run the
  wrapper check. The probe file never exists, so a read that is not denied finds nothing. agy
  names no sandbox identity, so there is no whoami probe. It passes only when the init is
  clean, the result is SUCCESS, neither outside file exists, the fetch was denied or failed,
  the unsandboxed command and all four probe reads are among the denied actions, the wrapper
  check logged exit 0 and
  consumed its note, the attempt dir matches the
  ledger, the settings file is unchanged, and the tree, refs and containers are as for every
  canary.
- **The quota step (D-21, D-25).** The canary then runs `agy -p /usage`. A JSON line naming a
  `remaining` number is a measurement: above 0 passes, and the pass file records it so the owner
  sizes the arm to the weekly quota. A `remaining` of 0, an error status, or text saying the
  quota or rate limit was hit is a FAIL that names the fallback arm and how to run it:
  `reverseapoc drive --night-model gemini-3.8-flash-openrouter --allow-egress
  gemini-3.8-flash-openrouter` (OpenRouter in the Claude Code harness, paid, needs
  `OPENROUTER_API_KEY`). If `/usage` prints nothing machine-readable (RESEARCH A8), the canary
  says the quota was estimated, not measured, and records the session's tokens and 20 times
  them, so the owner can compare a 20-session arm with the bucket the app shows.
- **The pass gate.** The canary writes `build/driver/canary/<arm>.json` (`arm`, `harness`,
  `cli_version` from `agy --version`, `date`, `result`, `tokens`, `quota`). A night of an agy
  arm is refused (exit 2, before any session, naming the canary command) unless that file says
  PASS for the version installed now. An arm on any harness without a canary is always refused.
- **Sizing.** Each arm runs with `max_workers = 1`. AI Plus gives Gemini 3.8 Flash only, on a
  weekly quota (Gemini 4 Argon needs AI Pro or Ultra). A failure that names a quota or rate
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
- **Order.** `reverseapoc drive --canary --night-model qwen-local --run canary-qwen-local`, then
  the hold run: `reverseapoc drive --night-model qwen-local --workers 1 --picks build/driver/spike012-picks.txt --hold --run spike012-qwen-local`.

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
  also carry `max_sessions` in backends.toml, which caps that arm's launches for the night. The
  Antigravity arms carry 20, the canary's planning estimate; the owner sets it from the quota
  the agy canary measures. When an arm reaches its cap, it stops launching while the others go
  on. `--max-sessions` still caps the night's total.
- **Usage pauses.** Each arm has its own usage-limit pause. A LIMIT session of one arm (a Codex
  Plus window, the Antigravity quota, an Anthropic limit) starts that arm's backoff only. The
  other arms keep launching, and the arm's own probe clears its pause.
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

The spike 012 night over the frozen pick list, every arm at once (canaries passed first):

```
reverseapoc drive --picks build/driver/spike012-picks.txt --hold --run spike012 \
  --arm claude-haiku-5-5=2 --arm claude-sonnet-5-5=2 \
  --arm gpt-6-luna=1 --allow-egress gpt-6-luna \
  --arm gemini-flash=1 --allow-egress gemini-flash \
  --arm deepseek-flash=2 --allow-egress deepseek-flash \
  --arm qwen-local=1
```

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
