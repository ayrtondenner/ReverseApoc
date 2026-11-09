# API Coverage — Phase 07.2 harness surfaces

> Full coverage by default. Opt-outs are explicit, reasoned decisions. The phase calls no provider API from Python:
> the driver launches Claude Code, Codex CLI and Antigravity CLI sessions and reads their streams, and the CI workflow
> uses GitHub Actions. Each surface below is the part those plans (07.2-08, 12, 13, 15) drive.

## Anthropic-compatible endpoints through Claude Code (07.2-12; DeepSeek, z.ai, OpenRouter, local llama.cpp)

| capability | decision | reason |
|---|---|---|
| endpoint: ANTHROPIC_BASE_URL per arm | INTEGRATE | |
| endpoint: ANTHROPIC_AUTH_TOKEN from the arm's named key variable | INTEGRATE | |
| endpoint: ANTHROPIC_API_KEY blanked for hosted arms | INTEGRATE | |
| endpoint: CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC | INTEGRATE | |
| endpoint: ANTHROPIC_DEFAULT_OPUS/SONNET/HAIKU_MODEL pins | INTEGRATE | |
| endpoint: init model check against the arm's accepted ids | INTEGRATE | |
| endpoint: token usage from the stream | INTEGRATE | |
| endpoint: llama-server `/v1/messages` on loopback | INTEGRATE | |
| endpoint: OpenRouter as the Gemini fallback arm | INTEGRATE | |
| endpoint: the CLI's total_cost_usd for non-Anthropic models | OPT-OUT | not trusted for unknown model ids (RESEARCH A3); cost is estimated from backends.toml prices |
| endpoint: apiKeyHelper and other credential helpers | OPT-OUT | explicitly out of scope: keys come only from named user environment variables (D-12) |
| endpoint: provider routing preferences (OpenRouter) | OPT-OUT | not needed yet: spike 012 uses the default route; revisit if an arm's canary shows provider drift |
| endpoint: provider thinking-budget or effort parameters | OPT-OUT | explicitly out of scope: effort stays as nights use it today, no flag (D-17) |
| endpoint: prompt-caching controls | OPT-OUT | not needed: Claude Code manages caching; cache tokens are recorded as reported |
| endpoint: a paid Gemini Pro arm via OpenRouter | OPT-OUT | deferred by the owner (D-25) |

## Codex CLI `codex exec` (07.2-13)

| capability | decision | reason |
|---|---|---|
| codex: `exec --json` event stream | INTEGRATE | |
| codex: `--model` | INTEGRATE | |
| codex: `--sandbox workspace-write` and `--cd` the attempt dir | INTEGRATE | |
| codex: -c approval_policy, network_access and project trust overrides | INTEGRATE | |
| codex: `--ephemeral`, `--skip-git-repo-check`, `--ignore-user-config` | INTEGRATE | |
| codex: `.rules` prefix_rule per session under build/ | INTEGRATE | |
| codex: events turn.completed, command_execution, file_change, turn.failed, error | INTEGRATE | |
| codex: `--version` for the canary-pass record | INTEGRATE | |
| codex: `--output-schema`, `-o/--output-last-message` | OPT-OUT | not needed: the event stream carries everything the record and audit read |
| codex: `--profile` and user config layers | OPT-OUT | explicitly out of scope: config is per-session flags and build/ files, never the owner's config (D-13) |
| codex: `resume` of an earlier thread | OPT-OUT | explicitly out of scope: every session starts fresh, as Claude sessions do |
| codex: `--add-dir` extra writable roots | OPT-OUT | explicitly out of scope: the attempt dir is the only writable root (D-13) |
| codex: `model_reasoning_effort` | OPT-OUT | explicitly out of scope: no effort flag (D-17) |
| codex: MCP tool calls and web search items | OPT-OUT | explicitly out of scope: no MCP servers (D-44) and network off |
| codex: agent_message, reasoning and todo_list items | OPT-OUT | not needed: kept raw in the transcript, not parsed |
| codex: `codex execpolicy check` offline rule test | OPT-OUT | not needed yet: the Codex canary proves the rules load on the real CLI |

## Antigravity CLI `agy` headless (07.2-15)

| capability | decision | reason |
|---|---|---|
| agy: `-p` headless prompt (last flag) | INTEGRATE | |
| agy: `--output-format stream-json` | INTEGRATE | |
| agy: `--model` | INTEGRATE | |
| agy: `--sandbox`, `--add-dir` the attempt dir | INTEGRATE | |
| agy: `--settings` per-session permissions | INTEGRATE | |
| agy: `--disable-slash-commands`, `--print-timeout` | INTEGRATE | |
| agy: events init, step_update, result (usage, num_turns, denied_actions) | INTEGRATE | |
| agy: `/usage` for the quota canary | INTEGRATE | |
| agy: `--effort` | OPT-OUT | explicitly out of scope: no effort flag (D-17) |
| agy: `--mode accept-edits/auto/plan` | OPT-OUT | not needed: headless soft-deny under the session settings is the permission model (D-24) |
| agy: `--dangerously-skip-permissions` | OPT-OUT | explicitly out of scope: forbidden, pinned by a test |
| agy: `--log-file` | OPT-OUT | not needed: the stream is captured as the transcript |
| agy: `agy models` | OPT-OUT | not needed in code: the owner records the slug at setup |
| agy: subagent steps | OPT-OUT | explicitly out of scope: sessions dispatch no subagents |
| agy: user-global settings.json rules | OPT-OUT | explicitly out of scope unless the canary shows per-session settings cannot restrict tools; then an owner step, documented and removable (D-24) |

## GitHub Actions for match.yml (07.2-08)

| capability | decision | reason |
|---|---|---|
| actions: `pull_request_target` with `types: [labeled]` | INTEGRATE | |
| actions: `workflow_dispatch` with a PR number input | INTEGRATE | |
| actions: repository variable gate `MATCH_CHECK_ENABLED` | INTEGRATE | |
| actions: self-hosted runner | INTEGRATE | |
| actions: `actions/checkout` with `persist-credentials: false` | INTEGRATE | |
| actions: `permissions: contents: read` | INTEGRATE | |
| actions: repository secrets | OPT-OUT | explicitly out of scope: the job uses no secret by design (D-06, D-07) |
| actions: PR comments, check-run annotations, write scopes | OPT-OUT | not needed yet: the job's pass or fail is the result; write scopes would widen the token |
| actions: automatic runs on every push | OPT-OUT | explicitly out of scope: a maintainer label gates every run (D-06) |
