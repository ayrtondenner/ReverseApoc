---
spike: 013
idea: night-economics
name: copilot-cli
type: standard
validates: "Given the owner's GitHub Copilot CLI 1.0.111 on Copilot Pro (1,500 AI credits a month), when one headless `copilot -p --output-format json` session is captured doing allowed and forbidden steps in a scratch workspace, then we know its event stream, its permission rules and their denial forms, how credits map to a session, and what config it reads, enough to build a fail-closed drive harness whose canary proves the rest"
verdict: PARTIAL
related: [012]
tags: [copilot, harness, permissions, ai-credits, config-isolation, canary, owner-ruling-2026-11-13]
---

# Spike 013: GitHub Copilot CLI as a drive harness

## What This Validates

Whether GitHub Copilot CLI can run `reverseapoc drive` sessions beside Claude Code, Codex CLI
and Antigravity, spending the owner's Copilot Pro AI credits (1,500 a month, reset 2026-11-30)
on Claude Haiku 5.5 first. Owner ruling 2026-11-13: the owner installed the CLI and asked for
it; CLAUDE.md and `.claude/rules/workflow.md` now name it in the scoped runtime exception (drive
sessions only, launched and audited by the driver, config only under gitignored build/).

## Verdict

**PARTIAL.** The coordinator's live capture and the CLI's offline help and package answer the
stream, permission, billing and config questions, and the harness is built test-first on those
answers (`copilotjson.py`, `session.build_copilot_argv`, the driver's `copilot` branches, three
`[arms."copilot-..."]` entries, a Copilot canary). It stays partial until the owner's canary
runs: the open items at the end are what only a live session can prove, and every one of them
fails closed until it does.

## Evidence

The coordinator ran one session, read-only captures under the coordinator's scratchpad
(`captures/copilot/`: `stream1.jsonl` with 234 JSONL events, `usage1.json`, an empty
`stderr1.txt` and the workspace `ws1/`). Nothing here was run against GitHub; the worker read
only `copilot --version`, `copilot --help`, `copilot help <topic>` and the CLI's installed
package (`%LOCALAPPDATA%\copilot\pkg\win32-x64\1.0.111\`, its `schemas/session-events.schema.json`).

### The CLI and the headless argv

- `copilot --version`: `GitHub Copilot CLI 1.0.111.` at
  `C:\Users\Ayrton\AppData\Local\GitHubCopilotCLI\copilot.exe`, on the user PATH.
- The captured argv, cwd = the workspace, exit 0:
  `copilot -p <prompt> --model claude-haiku-5.5 --output-format json --no-auto-update
  --no-custom-instructions --disable-builtin-mcps --no-ask-user --disallow-temp-dir --add-dir <ws>
  --allow-tool "write(<ws>/x.txt)" --allow-tool "write(<ws>/y.txt)" --allow-tool "shell(git
  --version)" --deny-tool "read(<ws>/secret.txt)" --max-ai-credits 30 --usage-output-file <file>
  --stream on`.
- The driver's argv (`session.build_copilot_argv`): `-p <prompt>` first (the rule flags are
  variadic), `--model`, `--output-format json --stream on`, `--no-auto-update`,
  `--no-custom-instructions`, `--disable-builtin-mcps`, `--no-ask-user`, `--disallow-temp-dir`,
  `--available-tools view create edit powershell read_powershell` (the model sees no other
  tool: no web_fetch, no subagent, no skill, no sql), `--allow-tool shell(uv:*)`, one
  `--allow-tool write(<path>)` per session file (view unit, notes.md, plan.json,
  check-note.json, giveup.json), `--deny-tool read(<repo>/orig/**)` and `write(...)` for orig/
  and third_party/, `--deny-tool url`, `--deny-tool memory`, `--max-ai-credits <arm cap>` and
  `--usage-output-file build/driver/<run>/copilot/<exe>__<function>__attempt-<n>.usage.json`.
  No `--add-dir`: the cwd is the attempt dir, the only directory it may touch. Never
  `--allow-all*`, `--yolo`, `--autopilot` or `--trust-folder`.

### The event stream

- One JSON object per line; **the first line starts with a UTF-8 BOM** (streamjson.parse_line
  now takes it off, else session.start would be a malformed line). Envelope: `{"type", "data",
  "id", "timestamp", "parentId"}`, plus `ephemeral` and, per the CLI's schema, `agentId` on a
  subagent's events. The last line is `{"type": "result", "exitCode": 0, "usage":
  {"premiumRequests", "totalApiDurationMs", "sessionDurationMs", "codeChanges":
  {"filesModified": [...]}}}`.
- Types seen: session.start (data.copilotVersion, selectedModel, sessionLimits.maxAiCredits,
  context.cwd), session.mcp_servers_loaded, session.tools_updated, instruction.update (one,
  authority `runtime`), user.message, assistant.turn_start/turn_end, model.call_start /
  call_finished / call_final_result, assistant.message(_start/_delta), assistant.reasoning
  (_delta), assistant.tool_call_delta, tool.execution_start, tool.execution_complete,
  tool.shell_output, tool.execution_partial_result, session.info, session.background_tasks_changed,
  session.usage_checkpoint (totalNanoAiu), assistant.idle, result. No event carries token
  counts; the schema lists about 200 more types (hook.*, skill.*, subagent.*, permission.*,
  session.error, auto_mode_switch.*...).
- tool.execution_start: `toolCallId`, `toolName`, `arguments` (view `{path}`, edit `{path,
  old_str, new_str}`, create `{path, file_text}`, powershell `{command, description}` plus
  `shellToolInfo.hasWriteFileRedirection`), `model`, `turnId`. Paths are absolute with Windows
  backslashes. tool.execution_complete: `success`, `result.content`, `fileEdits: [{path, kind:
  edit|create}]`, `shellExecution.exitCode`, or `error: {code, message}`.

### Permissions and their denial forms

- `copilot help permissions`: `--allow-tool`/`--deny-tool` take `shell(cmd:*)`, `write(glob)`,
  `read(glob)`, `url(...)`, `memory`; deny wins over every allow; in a -p run a request no rule
  allows is denied; file access is limited to the cwd, `--add-dir` and the temp dir
  (`--disallow-temp-dir` drops it); **a path rule does not apply to shell commands**; and
  "commands it recognizes as read-only run without asking".
- Shell rules name a command plus at most its first subcommand ("shell(gh pr create)" does not
  cover "gh pr create --fill"), so **no rule can name the wrapper's exact forms**
  (`shell(uv run --frozen reverseapoc attempt:*)` matches nothing by that rule). The driver
  passes `shell(uv:*)`, the rule that surely matches them; the post-session command audit
  (`codex_command_strays`: exact wrapper forms only, no orig/ or third_party/ part) is the
  guard. The gap: `uv run python -c ...` or a read-only command such as `Get-Content` could read
  orig/ before the audit stops the night, as with Codex (docs/model-routing.md "What the audit
  cannot do").
- The two denial forms (both `success: false`, `error.code: "denied"`):
  `Permission to run this tool was denied due to the following rules: `read(<path>)`` (a deny
  rule; paths with forward slashes) and `Permission denied because no interactive user response
  was available. Retry in an interactive session so the user can approve it, or try an
  alternative that does not require this permission.` (no allow rule). copilotjson counts a call
  as not run only for a known call in its known shape ending in exactly one of these.
- `--sandbox` (MXC ProcessContainer/BaseContainer on Windows) exists but its support on this
  Windows 10 19045 is unverified; the driver does not pass it. A later canary may prove it.

### AI credits

- `copilot help billing`: each model call costs its tokens (input, cache read, cache write,
  output) at the model's per-token rate; `--max-ai-credits` (minimum 30) is a soft per-session
  cap (`copilot help limits`: one response may pass it; at 10% left the next call is final).
- usage1.json: `totalNanoAiu` 436608000 (1e9 nano AIU = 1 credit: 0.437 credits for 3 model
  calls), `tokenDetails` input 8, cache_read 50,478, cache_write 26,644, output 1,060,
  `modelMetrics` keyed by model id, `aiCreditsStatus` `complete`. At Haiku 5.5's <=100K rate
  (10 / 1 / 12.5 / 50 credits per 1M) those tokens cost exactly 0.436608 credits, so the arm's
  price table (the same rates in USD) reproduces GitHub's figure (tests/test_copilot.py).
- The default context tier caps a session at 100K tokens (telemetry `context_token_limit:
  100000`), so the >100K tier never applies; `--context long_context` is never passed.
- The driver records `credits` (totalNanoAiu / 1e9) in each Copilot attempt record, `cost_usd`
  0 (subscription billing), the tokens from the usage file.

### Config isolation

- Copilot reads a project's `CLAUDE.md`, `.claude/rules/`, `.claude/skills/`, `.claude/agents/`,
  `.claude/commands/` and hooks from `.claude/settings.json`, and user hooks and plugins from
  `$COPILOT_HOME` (`copilot help config`). The capture's tool results carried a user-level
  postToolUse hook's text (`[cost: 1% used · $0.30 left]`); its source was not found offline
  (no `~/.copilot/settings.json`, no `~/.copilot/hooks/`, no installed plugin; a
  `plugin-data/_direct/` entry exists).
- The login: `~/.copilot/config.json` holds no account (keys: firstLaunchAt,
  reasoningSummariesCleanupDone, trustedFolders `C:\Windows\System32` only); the Windows
  credential store holds `gh:github.com:<user>` entries, so the sign-in is likely the keyring's,
  not the home dir's. Nothing was copied.
- Mitigations built: `--no-custom-instructions`; a per-session `COPILOT_HOME`
  (`build/driver/<run>/copilot/<exe>__<function>__attempt-<n>.home/`) holding the driver's
  `settings.json` `{"disableAllHooks": true, "autoUpdate": false}` (audited unchanged after the
  session); `COPILOT_AUTO_UPDATE=false` and `COPILOT_PLUGIN_DIR_ONLY=true`;
  `--disable-builtin-mcps`; `--available-tools`; the cwd is the attempt dir, which is under the
  checkout but not a trusted folder (a -p run in an untrusted folder skips repository hooks);
  every session (any harness) loses every inherited `COPILOT_*` variable (COPILOT_ALLOW_ALL,
  COPILOT_PROVIDER_*, COPILOT_HOME...) and `GH_TOKEN`/`GITHUB_TOKEN`. `--secret-env-vars` is not
  passed: the vendors' keys never reach the process at all. The session state Copilot keeps
  (`session-state/<id>/events.jsonl`, the pack included) lands in the per-session home under
  gitignored build/, not in the owner's `~/.copilot`.
- The audit fails closed on hooks: any `hook.*` event, and any tool result carrying hook
  guidance text, is a stray.

## Open items the canary must prove

1. **The login survives the per-session COPILOT_HOME.** If it does not, every session ends on an
   authentication `session.error` (STOP). Then the owner chooses: sign in once with
   `COPILOT_HOME` set to a fixed driver home under build/, or drop the per-session home
   (losing `disableAllHooks`); copying `~/.copilot/config.json` or a token is not acceptable
   without the owner.
2. **No hook text, no repo instructions.** The canary FAILs on any hook event or hook text. The
   stream names no loaded instruction file, so "no CLAUDE.md reached the session" rests on
   `--no-custom-instructions`; check the canary session's
   `session-state/<id>/events.jsonl` under its home once.
3. **The allow rule `shell(uv:*)` lets the wrapper run** (else the canary's wrapper steps are
   denied: try `shell(uv run)`).
4. **The long-command shapes.** `attempt check` outlives the shell tool's 30 s sync wait.
   copilotjson accepts powershell's `mode` (sync|async) and `initial_wait` (the CLI's bundled
   tool table names them) and read_powershell `{shellId, delay}` (shellId from the capture's
   shell results); neither was captured in a call. Any other key is an unknown step.
5. **Each probe is refused**: a view under orig/, a `..` view, a create one directory above the
   workspace, `Get-Content` of an orig/ path (read-only commands may run unasked: a FAIL here
   means the shell reaches orig/ before the audit) and `Invoke-WebRequest`. A path outside the
   cwd is expected to be refused with the "no interactive user response" text; another text
   counts as run (fail closed).
6. **The usage file is written** and names the session's credits (the canary records them);
   re-measure the per-session cost (placeholder: about 3 to 5 credits per Haiku session).
7. **The model stays put.** Every model call, message and tool call must name the requested
   model (an automatic switch is an init stop). Record whether any `session.skills_loaded`
   or other unlisted event appears: each is an unknown step until named.

Run: `uv run reverseapoc drive --canary --night-model copilot-haiku-5-5 --allow-egress
copilot-haiku-5-5 --run canary-copilot-haiku` through the clean-environment launcher.
