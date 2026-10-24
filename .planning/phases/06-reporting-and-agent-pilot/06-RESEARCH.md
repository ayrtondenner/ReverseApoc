# Phase 6: Reporting and agent pilot - Research

**Researched:** 2026-10-24
**Domain:** stdlib Python tooling (status table, gate, progress/report generators, hooks, stdio MCP server, headless `claude -p` driver), GitHub Actions/Pages, external listing feeds
**Confidence:** HIGH for in-repo code facts and external schemas fetched this session; MEDIUM for Claude Code behaviours that the docs leave unstated (hook merge from `--settings`, `enabledPlugins` merge), which the plans must probe at the pilot checkpoint

## Summary

The scouting brief (`.superpowers/sdd/let-s-work-on-phase-effervescent-nebula/discuss-brief.md`, gitignored) already holds the decomp.wtf, Nigel, CLI-version, scorer and table-size facts; this file does not redo them. It adds what the planner needs to write tasks: the exact external contracts (MCP stdio, Claude Code hooks, stream-json, objdiff report, DecompHub, recomp.fyi, shields, Pages actions), a code-level plan for every deferred item, and the places where a locked decision needs one more flag or a reconciliation.

Five findings change what the plans must contain:
1. **MCP servers cannot live in a settings file.** No `mcpServers` key exists in Claude Code settings; servers come from `.mcp.json`, `~/.claude.json` or `--mcp-config`. So D-06 must add `--mcp-config <per-attempt json> --strict-mcp-config`. Without `--strict-mcp-config`, a `-p` session in this repo connects the project's Tavily server and the owner's user/local `discord-user` server, without asking.
2. **`--allowedTools` does not remove Bash.** It only pre-approves tools. `dontAsk` still runs the read-only command set without approval. "No shell at all" (D-04/D-17) therefore needs `--tools "Read,Edit,Write,Glob,Grep"` as well, plus a deny-by-default matching hook.
3. **The D-16 always-on layer blocks `build/`, and D-17 allows `build/driver/.../notes.md`.** Hook `deny` beats `allow` across hooks, so the always-on rule would deny the notes file. The always-on decision must exempt exactly the attempt's notes path, named by an env var the driver sets.
4. **`config/watcom.toml` says "the real LE compiler" on line 37 (10.5) and again on line 106 (10.6).** D-43 authorizes only line 37.
5. **objdiff's own `Report.split()` treats each dot-free category id as a separate version.** D-28's categories `ufo2p`/`tacp` are exactly that shape, so if recomp.fyi calls `split()`, its several-versions rule comes back. The planner records this as a risk; the locked decision stands.

**Primary recommendation:** Build every new piece as a pure, injectable Python core (decision function, JSON-RPC dispatcher, stream-json classifier, progress derivation, status read/write) with a thin I/O shell, tested on the host against synthetic inputs and a fake `claude`. Reserve container plus real-file tests for `gate`, DI-02/DI-03 and the pilot, which run in the main checkout.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Matching verdict (`check`, `gate`) | Container (objdiff-cli, wibo, Watcom) | — | objdiff-cli exists only in the container [VERIFIED: tools/reverseapoc/check.py:87,518-526] |
| status.csv + decomphub.progress.json write | Container (`gate`) | — | D-21: the only writer is `gate`, which needs `check` |
| Drift test (status ↔ src ↔ outputs) | CI / host pytest (no game files) | — | D-22; uses committed CSVs, `source_marks` and progress.py only |
| progress.json / svg / shield / report.json | GitHub Actions (Pages job) | host pytest | D-27/D-28; derived from committed CSVs, stdlib |
| Driver loop, scorer, context pack, commit | Windows host Python | Container via `docker compose run` | claude.exe is host-only (`C:\Users\Ayrton\.local\bin\claude.exe`, 2.1.240) [VERIFIED: `where claude`] |
| Guardrail hooks | Host (claude spawns them, Git Bash) | — | hooks run where claude runs [CITED: code.claude.com/docs/en/hooks] |
| MCP server (`check`/`asm`/`context`) | Host process spawned by claude | Container for `check` only | Recommended (Claude's discretion): a host server shells out to `docker compose run --rm -T build` per check, so no container outlives a killed session |
| Spike 006 | WSL2 (`ubuntu-recovered`) | — | D-01 |

## Package Legitimacy Audit

No new Python or npm package is installed by this phase: D-04 makes the MCP server stdlib-only, and progress/hooks/driver are stdlib. External tooling used:

| Package / action | Registry | Source | Verdict | Disposition |
|---|---|---|---|---|
| `decompnet` 0.10.6 (decomp.wtf) | GitHub tarball, not PyPI | github.com/i12bp8/decomp.wtf, tag v0.10.6 (archived, MIT) [VERIFIED: gh api] | n/a (pinned tarball, WSL2 spike only) | Approved for spike only; never imported or vendored (docs/legal.md:26) |
| actions/checkout v7.0.1, upload-pages-artifact v5.0.0, deploy-pages v5.0.1, upload-artifact v7.0.2, configure-pages v6.0.0 (optional), astral-sh/setup-uv v10.3.2 (repo pins v10.3.0) | GitHub Actions | gh api releases/latest, 2026-10-24 [VERIFIED] | OK (first-party / already used) | Approved |

**Packages removed due to [SLOP]:** none. **Flagged [SUS]:** none.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
**The authoritative verbatim text is `06-CONTEXT.md` `<decisions>` (L43-295) and `<deferred_inventory>` (L298-338). The planner MUST read it.** It is not repeated here, to keep this file under the orchestrator's length budget. Index:
- D-01..D-04: spike 006 (code evidence plus a half-day WSL2 smoke run); the verdict scale; no patched decomp.wtf; fallback = driver + hooks + skill + context pack + stdlib stdio MCP server (`check`, `asm`, `context`), no shell, no claims.
- D-05..D-08: own stdlib `driver.py` plus the `drive` verb; the exact `claude -p` argv; 3 sessions, 40 turns and 30 minutes per attempt, plus the "25 check runs" goal clause; backoff by error class; night cap 30 sessions or 10 MATCHED; `--max-budget-usd 5`.
- D-09, D-10: `score.assess` plus status awareness; the pilot takes 5 + 5, interleaved; at most 2 per unit, at most 3 per 64 KiB region.
- D-13, D-14: context-pack contents, look-alikes by opcode similarity, 24 KB cap, truncation order, `build/driver/<run>/<exe>/<func>/`.
- D-15..D-17: hooks in `tools/reverseapoc/hooks.py`; two layers; the matching-session allowlist (deny by default; no Bash; `git status --porcelain` audit).
- D-18, D-19: no `#pragma aux` of any kind from agents; the `watcom-decomp` SKILL.md (≤300 lines, 9 sections, written with `superpowers:writing-skills`, plus a path-existence pytest).
- D-20..D-23: sparse `config/<exe>/status.csv` (`start,name,unit,status,best_percent,attempts,source_sha256,date`); `gate` is the only writer; the drift test; committed `progress/attempts.jsonl`.
- D-24, D-25: per-commit gate plus a cross-check; an end-of-run clean `ninja verify` and `gate --all`; the commit format and trailers.
- D-26..D-33: what is measured; the Pages workflow; one combined artifact `X-COM_Apocalypse_DOS_report`; the `decomphub.progress.json` tracks; the CI POST behind a repo variable; the verification file; `.recomp.json`; the listing drafts in `docs/listings.md`.
- D-34..D-37: host main checkout and reset rules; model `claude-opus-5-5`; CLI upgrade and pin; the done criterion; the 40-session ceiling.
- D-38..D-43: wave order; DI-02/DI-03 now; DI-24 ruling; small rulings; DI-32 ruling; the one-line DI-33 edit under conditions.

### Claude's Discretion (verbatim)
- The internal module layout of the driver, MCP server and progress.py within `tools/reverseapoc/`; verb names other than `drive` and `gate`; the treemap layout algorithm (squarified or slice-and-dice, stdlib); the exact /goal prompt wording; the look-alike similarity metric.
- How the stand-in `claude` (a fake CLI emitting recorded stream-json) is built for the driver tests.
- Whether the MCP server runs inside the container (via `docker compose run -i`) or on the host shelling out to the container, provided `check` itself always runs in the container.

### Deferred Ideas (OUT OF SCOPE, verbatim)
- SQLite claims with a TTL for parallel agents (Phase 7, DEC-06), and re-evaluating decomp.wtf for that role (D-03).
- Scorer tuning: pure leaf functions, new features, dropping `WEIGHT_NO_FRAME` (Phase 7) (D-09).
- GhidraMCP as a live agent tool (Later) (D-14).
- A dedicated second clone for parallel runs (Phase 7) (D-34).
- Twin matching of CD v1.00 (after Phase 7) (D-42).
- Reddit, GBAtemp and decompals posts (later, at the owner's call).
- readlint itself, with the 999.2 rule (Phase 7, DEC-04).
</user_constraints>

### Research findings that touch locked decisions (owner confirmation needed)

> **Settled by the owner on 2026-10-24**: see `06-CONTEXT.md` D-44..D-50. In particular, **no MCP server is built** (D-44). The agent calls `check`/`asm`/`context` through a Bash-allowlisted attempt wrapper, so the "MCP stdio server" section and the MCP code example below are superseded.

| # | Decision | Finding | Recommended handling |
|---|---|---|---|
| R1 | D-06 ("the driver settings file adds ... the MCP server") | Settings files have no `mcpServers` key; the settings index lists none. Servers come from `.mcp.json`, `~/.claude.json` or `--mcp-config` [CITED: code.claude.com/docs/en/settings, /settings-reference, /mcp] | Add `--mcp-config build/driver/<run>/<exe>/<func>/mcp.json --strict-mcp-config` to the argv. The settings file keeps the hooks and the plugin overrides. |
| R2 | D-04/D-17 ("no shell at all") | `--allowedTools` pre-approves; to restrict the available tools use `--tools`. dontAsk still runs "the read-only command set" [CITED: cli-reference `--tools`; headless "dontAsk"] | Add `--tools "Read,Edit,Write,Glob,Grep"`. MCP tools are unaffected by `--tools` [CITED]. The matching hook also denies every other tool name. |
| R3 | D-16 always-on blocks `build/` vs D-17 allows `build/driver/.../notes.md` | Across hooks "precedence is deny > defer > ask > allow" [CITED: hooks] | The always-on decision exempts only the exact path in env `REVERSEAPOC_ATTEMPT_NOTES`, set by the driver and only under `build/driver/`. Alternative: an MCP `notes` tool. |
| R4 | D-43 (only `config/watcom.toml:37`) | Line 106 (10.6 entry) holds the same stale note `"Win32 loader stub; runs BINW/WCC386.EXE (the real LE compiler)"` [VERIFIED: grep config/watcom.toml lines 37,106]; docs/learnings.md:58 calls both stale | Ask the owner to extend the one-time authorization to line 106 too, or leave line 106 and record why |
| R5 | D-08 night cap 30 vs D-37 pilot ceiling 40 | One run cannot reach 40 sessions if it stops at 30 | Make both CLI options (`--max-sessions`, `--target-matched`) with default 30/10; the pilot runs `--max-sessions 40 --target-matched 10` |
| R6 | D-28 categories `ufo2p`, `tacp` | objdiff `Report::split()`: "Split the report into multiple reports based on progress categories ... a hack for projects that generate all versions in a single report"; a category id without `.` becomes its own report [VERIFIED: objdiff-core/src/bindings/report.rs via gh api] | Keep D-28. Record the risk in docs; recomp.fyi's ingestion code is private, so this cannot be tested. |
| R7 | D-26/D-40 (uncovered bytes count as unmatched) | The committed CSVs leave 25,691 (UFO2P) / 35,241 (TACP) bytes inside unit spans uncovered by any row, in 515 / 506 gaps. Most are inter-function alignment filler, so 100% becomes unreachable. The UFO2P 3-byte tail past 0x000CFADA lies outside every units.csv span and is invisible to CI [VERIFIED: computed from config/*/units.csv, functions.csv] | Show "uncovered" as its own counted segment in progress.json, and tell the owner the figure includes filler. The tail cannot be counted in CI without a committed extent. |

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RPT-01 | Committed per-function status table, written only by the local gate | §Gate and status table; §Drift test; `source_marks` reuse [VERIFIED: check.py:357-369] |
| RPT-02 | stdlib progress.py → progress.json, treemap svg, shields JSON | §progress.py; shields schema [CITED: shields.io/badges/endpoint-badge]; squarified treemap pattern |
| RPT-03 | Pages workflow publishes on push to main | §Pages workflow (actions pins verified) |
| RPT-04 | objdiff-shaped report.json as `<VERSION>_report` artifact | §report.json (report.proto fields, snake_case, REPORT_VERSION 2) |
| RPT-05 | .recomp.json updated, DecompHub submission | §.recomp.json (schema v1 props, status enum); §DecompHub (schema, refresh endpoint verbatim) |
| AGT-01 | Fresh `claude -p "/goal ..."` per function; driver re-verifies; one function per commit or reset | §Driver process model; §Commit composition |
| AGT-02 | 3-5 attempts per pass; difficult list; re-queue | §Driver state machine |
| AGT-03 | Tri-state outcome with turns, tokens, time, verifier output | §stream-json schema; §attempts.jsonl |
| AGT-04 | Back off on usage limits and auth/credit errors; night cap | §Error classification |
| AGT-05 | pytest-tested guardrail hooks | §Hooks contract; §Hook decision function |
| AGT-06 | Zero-regression gate after every commit | §Gate cross-check (landed set == matched set) |
| AGT-07 | Easiest-first scorer run by the driver | §Scorer wrapper |
| AGT-08 | Context pack | §Context pack (look-alikes, truncation) |
| AGT-09 | watcom-decomp skill | §Skill (sections, path pytest) |
| AGT-10 | decomp.wtf fork mode if the spike passes, else own layer | §Spike 006 procedure |
| AGT-11 | Pilot of 10 easy functions | §Pilot checkpoint preflight |
</phase_requirements>

## Project Constraints (from CLAUDE.md and .claude/rules)

- Never commit `orig/`, `asm/`, `build/`, `third_party/`. Never modify `orig/`, `config/` hash manifests or build scripts to make a check pass. No secrets in tracked files. [CLAUDE.md]
- A matched function stays byte-identical. No restructuring, no inline asm or pragma to force a match. [CLAUDE.md, .claude/rules/src.md:7-15]
- Claude Code is the only agent runtime; skills are installed as plugins at project scope; nothing for other runtimes. [CLAUDE.md, .claude/rules/workflow.md]
- Python 3.14 via uv; TDD (failing test first); `uv run pytest -q && uv run ruff check .` green on the host **and** in the container; no third-party dependency without a docs/tools.md reason; GPLv3 headers kept; tests never embed game bytes; real-file tests skip without `orig/`; shallow nesting; named binary offsets; refactors pinned by tests first. [.claude/rules/tools.md]
- GSD owns sequencing, superpowers owns in-phase craft (TDD, verification-before-completion). [.claude/rules/workflow.md]
- Commit types: only the 10 Conventional Commits types (GSD hook). Never run the host and container suites at the same time (shared `build/test-cc`). [06-CONTEXT code_context]
- Done gate for decompiled code: the rebuilt EXE is SHA-1 identical and objdiff shows 100% for the function. [CLAUDE.md]

## External Contracts (verified this session)

### Claude Code CLI facts the driver hard-codes

| Fact | Value | Source |
|---|---|---|
| `--settings` | file path or inline JSON; "override the same keys in your settings.json files"; precedence: managed > command line > local > project > user | [CITED: cli-reference; settings "Settings precedence"] |
| `--setting-sources` | comma list of `user`, `project`, `local` | [CITED: cli-reference] |
| `--mcp-config <configs...>` | JSON files or strings; with `-p`, waits for pending servers up to `MCP_TIMEOUT` (30 s default, v2.1.221+) | [CITED: cli-reference] |
| `--strict-mcp-config` | "Only use MCP servers from `--mcp-config`, ignoring all other MCP configurations" | [CITED: cli-reference] |
| `-p` and project content | "Without `--bare`, a `-p` session runs the hooks in a project's `.claude/settings.json` and connects the servers in its `.mcp.json` ... no workspace trust dialog and no per-server approval prompt" | [CITED: headless] |
| `--tools` | "Restrict which built-in tools Claude can use ... doesn't affect MCP tools" | [CITED: cli-reference] |
| `--max-turns` | "Exits with an error when the limit is reached" (print mode only) | [CITED: cli-reference] |
| `--max-budget-usd` | client-side estimate, print mode only; "Spend can pass the cap" | [CITED: cli-reference] |
| Variadic flags | `--tools`, `--allowedTools`, `--mcp-config` are `<...>` variadic on 2.1.240 | [VERIFIED: `claude --help` on host] |
| `/goal` in `-p` | "runs the loop to completion in a single invocation"; the evaluator is the small fast model and "does not call tools"; `/goal` is unavailable when `disableAllHooks` is true | [CITED: code.claude.com/docs/en/goal] |
| Exit on SIGTERM | exit 143; turn left unfinished | [CITED: headless] |

**Recommended argv** (D-06 plus R1/R2). The prompt goes immediately after `-p`, so the variadic flags cannot swallow it:
```
claude -p "/goal <condition>" --output-format stream-json --verbose
  --max-turns 40 --model claude-opus-5-5 --permission-mode dontAsk
  --tools "Read,Edit,Write,Glob,Grep"
  --allowedTools "Read,Edit,Write,Glob,Grep,mcp__reverseapoc__*"
  --setting-sources project --settings config/driver/claude-settings.json
  --mcp-config build/driver/<run>/<exe>/<func>/mcp.json --strict-mcp-config
  --append-system-prompt-file .claude/skills/watcom-decomp/SKILL.md
  --max-budget-usd 5
```
Whether the allow-rule form `mcp__reverseapoc__*` matches on 2.1.240 is not stated in the fetched text [ASSUMED]. The safe form lists each tool: `mcp__reverseapoc__check,mcp__reverseapoc__asm,mcp__reverseapoc__context`.

**`config/driver/claude-settings.json` keys** (all are valid settings keys [CITED: settings-reference index]): `hooks` (matching layer **plus a copy of the always-on handler**, see Pitfall 3), `enabledPlugins` (each of the 7 project plugins set `false`), `autoMemoryEnabled: false`, `disableClaudeAiConnectors: true` (belt and braces next to `--strict-mcp-config`), `cleanupPeriodDays` optional. Do **not** set `disableAllHooks`, which would also disable `/goal` [CITED: goal].

### stream-json events the driver parses (`--output-format stream-json --verbose`)

| Event | Fields used | Source |
|---|---|---|
| `{"type":"system","subtype":"init"}` | `claude_code_version`, `model`, `tools[]`, `mcp_servers[{name,status}]`, `plugins[{name,path}]`, `plugin_errors`, `mcp_server_errors`, `permissionMode`, `session_id` | [CITED: agent-sdk/typescript SDKSystemMessage; headless] |
| `{"type":"system","subtype":"api_retry"}` | `attempt`, `max_retries`, `retry_delay_ms`, `error_status`, `error` ∈ `authentication_failed`, `oauth_org_not_allowed`, `account_on_hold`, `billing_error`, `rate_limit`, `overloaded`, `invalid_request`, `model_not_found`, `server_error`, `max_output_tokens`, `cloud_credential_error`, `unknown` | [CITED: headless "Handle API retries"] |
| `{"type":"rate_limit_event"}` | `rate_limit_info.status` ∈ `allowed`, `allowed_warning`, `rejected`; `resetsAt?`, `utilization?`, `errorCode?: "credits_required"` | [CITED: agent-sdk SDKRateLimitEvent] |
| `assistant` / `user` | `message.content[]` `tool_use` blocks (`name`, `input.file_path`), for the independent transcript audit | [CITED: headless] |
| `{"type":"result"}` | `subtype` ∈ `success`, `error_max_turns`, `error_during_execution`, `error_max_budget_usd`, `error_max_structured_output_retries`; `is_error`, `api_error_status`, `num_turns`, `duration_ms`, `duration_api_ms`, `total_cost_usd`, `usage`, `modelUsage{model:{inputTokens,outputTokens,cacheReadInputTokens,cacheCreationInputTokens,costUSD,...}}`, `permission_denials[]`, `errors[]` (error arms), `terminal_reason` ∈ `completed`, `max_turns`, `budget_exhausted`, `api_error`, `model_error`, `prompt_too_long`, `hook_stopped`, ... ; `result` (success arm) | [CITED: agent-sdk SDKResultMessage, TerminalReason] |

"Prefer `modelUsage` for token/cost accounting"; `usage` covers the main loop only [CITED]. Tokens logged = sum over `modelUsage` of input + output + cacheRead + cacheCreation, each kept separately.

### Error classification (D-08) as a pure function `classify(events, exit_code) -> Disposition`

| Signal | Disposition |
|---|---|
| `api_retry.error == "rate_limit"`, `rate_limit_event.status == "rejected"` without `errorCode`, `api_error_status == 429`, or result/`errors` text matching `hit your .*limit` (case-insensitive) | `LIMIT`: back off 60/120/240 s, then poll every 300 s; not an attempt |
| `api_retry.error` ∈ {`authentication_failed`, `oauth_org_not_allowed`, `account_on_hold`, `billing_error`}, `errorCode == "credits_required"`, or text `Credit balance is too low` / `Not logged in` | `STOP`: write a STOPPED record and end the run |
| `api_retry.error` ∈ {`overloaded`, `server_error`} and no result, or exit ≠ 0 with no result event | `TRANSIENT`: up to 3 retries, then abort; not counted |
| result `success` / `error_max_turns` / `error_max_budget_usd` / `error_during_execution` with tool activity | `ATTEMPT_DONE`: counted; the outcome comes from the driver's own gate, never from the result |
| init check fails (version, model, `reverseapoc` server not `connected`, Bash in `tools`, non-empty `plugins`) | `STOP` (fail closed) |

The extra `api_retry` values (`oauth_org_not_allowed`, `account_on_hold`) and `rate_limit_event` go beyond D-08's list but are the same classes, so this widens nothing.

### Hooks contract (D-15/D-16)

- **stdin JSON** for PreToolUse: `session_id`, `transcript_path`, `cwd`, `permission_mode` (`default`, `plan`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`), `hook_event_name`, `tool_name`, `tool_input`, `tool_use_id`. Write: `file_path`, `content`. Edit: `file_path`, `old_string`, `new_string`, `replace_all`. "`tool_input.file_path` is always absolute" and "On Windows, the path arrives with backslash separators, even when your hook runs under Git Bash" [CITED: hooks]. The fetched text did not show the MultiEdit/NotebookEdit schemas; handle `edits[]` and `notebook_path`/`new_source` defensively and deny any tool whose payload the function does not understand [ASSUMED field names].
- **Output:** exit 0 with stdout `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"..."}}`; or exit 2, where stderr is the reason and "Exit 2 blocks even if the JSON says allow". **Any other exit code is non-blocking: the tool proceeds** (fail open). A timeout does not block unless `"onFailure": "block"` (v2.1.295+) [CITED: hooks].
- **Precedence:** "Deny and ask rules are still evaluated regardless of what the hook returns"; across hooks "deny > defer > ask > allow" [CITED: hooks].
- **Matcher:** letters, digits, `_ - , |` and spaces mean an exact list (`Edit|Write|MultiEdit|NotebookEdit`); anything else is an unanchored JS regex; `*` matches all, MCP tools included [CITED: hooks].
- **Handler fields:** `type: "command"`, `command`, `args` (exec form, no shell; on Windows needs a real `.exe`), `timeout` (default 600 s), `shell` (`bash` default = Git Bash). `CLAUDE_PROJECT_DIR` is exported to hooks and stdio MCP servers [CITED: hooks].
- **Merge:** hooks from user, project and local "are added together"; identical handlers run once. **Whether hooks in a `--settings` file merge or override project hooks is not stated** [ASSUMED: they merge]. Mitigation in Pitfall 3.

### MCP stdio server (D-04), legacy era 2025-11-25

- Framing: "Messages are delimited by newlines, and MUST NOT contain embedded newlines"; stderr is free for logs; "The server MUST NOT write anything to its stdout that is not a valid MCP message"; the client shuts down by closing stdin [CITED: modelcontextprotocol.io/specification/2025-11-25/basic/transports].
- The current spec (2026-07-28) is "modern" and stateless (`server/discover`, `_meta` per request). A dual-era client "probe[s] with `server/discover` and fall[s] back on any error that is not a recognized modern error" [CITED: /specification/latest/basic/versioning]. **So a legacy-only server that answers unknown methods with JSON-RPC `-32601` works with both kinds of client.** Which era Claude Code 2.1.x speaks is [ASSUMED]; the pilot preflight checks `mcp_servers[].status == "connected"`.
- Methods: `initialize` returns `{protocolVersion, capabilities:{tools:{listChanged:false}}, serverInfo:{name,version}, instructions?}` and "If the server supports the requested protocol version, it MUST respond with the same version. Otherwise ... the latest version supported by the server" [CITED: 2025-11-25 lifecycle]. `notifications/initialized` (no reply), `ping` → `{}`, `tools/list` → `{tools:[{name,description,inputSchema}]}`, `tools/call` → `{content:[{type:"text",text}], isError}`. Unknown tool → JSON-RPC error `-32602`; a tool failure → `isError: true` [CITED: /server/tools]. Notifications (no `id`) never get a response.
- Supported versions: `["2025-11-25","2025-06-18","2025-03-26","2024-11-05"]` [ASSUMED list beyond 2025-11-25; harmless, since the server echoes the request when the version is in the list, else answers `2025-11-25`].
- Claude Code limits: output warning above 10,000 tokens, default cap `MAX_MCP_OUTPUT_TOKENS` 25,000, text results over 50,000 chars saved to a file, stdio idle timeout 30 min, a per-server `timeout` (ms) in the server entry [CITED: code.claude.com/docs/en/mcp]. A 24 KB pack stays under all of them.
- Config entry (no `type` means stdio [CITED: mcp]): `{"mcpServers":{"reverseapoc":{"command":"uv","args":["run","--project","<repo>","--no-sync","python","-I","-m","reverseapoc.mcp","--attempt-dir","<dir>"],"timeout":900000}}}`.
- Windows: use `sys.stdin.buffer`/`sys.stdout.buffer` and write `json.dumps(obj, separators=(",",":")).encode() + b"\n"`, then flush. Text-mode stdout on Windows writes `\r\n`, and the default stdin encoding is not UTF-8 [ASSUMED standard CPython behaviour].

### objdiff report shape (RPT-04, D-28)

`report.proto` (package `objdiff.report`, proto3) [VERIFIED: raw.githubusercontent encounter/objdiff objdiff-core/protos/report.proto]:
- `Report{measures:1 Measures, units:2 repeated ReportUnit, version:3 uint32, categories:4 repeated ReportCategory}`
- `Measures{fuzzy_match_percent:1 float, total_code:2 u64, matched_code:3 u64, matched_code_percent:4 float, total_data:5 u64, matched_data:6 u64, matched_data_percent:7 float, total_functions:8 u32, matched_functions:9 u32, matched_functions_percent:10 float, complete_code:11 u64, complete_code_percent:12 float, complete_data:13 u64, complete_data_percent:14 float, total_units:15 u32, complete_units:16 u32}`
- `ReportCategory{id:1, name:2, measures:3}`; `ReportUnit{name:1, measures:2, sections:3 repeated ReportItem, functions:4 repeated ReportItem, metadata:5 ReportUnitMetadata}`; `ReportUnitMetadata{complete:1 bool, module_name:2, module_id:3, source_path:4, progress_categories:5 repeated string, auto_generated:6 bool}`; `ReportItem{name:1, size:2 u64, fuzzy_match_percent:3 float, metadata:4, address:5 u64}`; `ReportItemMetadata{demangled_name:1, virtual_address:2 u64}`.
- JSON uses proto field names (`pbjson_build ... .preserve_proto_field_names()`) [VERIFIED: objdiff-core/build.rs]. `REPORT_VERSION = 2` [VERIFIED: objdiff-core/src/bindings/report.rs:18]. pbjson writes u64 fields as JSON strings (proto3 JSON mapping) [ASSUMED]. Emit u64 as decimal strings and u32/float as numbers, the way objdiff-cli does, because both forms parse.
- Percent rules to mirror (`calc_matched_percent`): a zero total gives 100.0; category measures are sums; `fuzzy_match_percent` is weighted by `total_code` [VERIFIED: report.rs].
- Recommended unit list: one ReportUnit per units.csv unit that holds game/thunk rows (`name: "ufo2p/u_000a34f0"`, `progress_categories: ["ufo2p"]`, `source_path: "src/ufo2p/u_000a34f0.c"` when present), plus one synthetic `<exe>/uncovered` unit (R7). Runtime rows are left out of the totals (D-26). Then the report's combined `matched_code_percent` equals progress.json's combined figure, and a test asserts it.

### recomp.fyi (RPT-04/05, D-28/D-32)

- "Upload build/report.json as a GitHub Actions artifact named VERSION_report ... from a workflow that runs on your default branch ... the board reads the report every day"; status shows "In progress until it reaches 100%, then Complete once the report also matches all the data, unless you have set a status yourself"; several versions: "a figure appears only if one of them is the release your row works from ... or if they agree within half a point" [VERIFIED: curl recomp.fyi/add].
- Schema v1: `additionalProperties: false`; properties `$schema, game, wikidata, system, type, original, project, status, targets, toolchain, approach, maintainers, links, help, tags, notes`; `status` enum `exploring, in-progress, playable, released, complete, paused, unknown`; `links[].url` and `maintainers[].link` pattern `^https://` [VERIFIED: curl recomp.fyi/schema/v1.json]. A CI test cannot fetch the schema (no network in tests), so pin these property names and the enum as constants with a `# from recomp.fyi/schema/v1.json, 2026-10-24` comment and check `.recomp.json` against them.
- Current `.recomp.json` has `status: "exploring"` and notes naming retrokit and decomp.wtf fork mode [VERIFIED: read .recomp.json]. D-32 changes these.

### DecompHub progress-v1 (D-29/D-30)

- Schema [VERIFIED: decomphub.com/schemas/progress-v1.json via WebFetch]: top level `additionalProperties:false`, required `format` (const `decomphub.progress/v1`), `repository` (≤2048), `tracks` (1-20); optional `revision` (40-64 lowercase hex) and `reportedAt`. A track has required `id` (`^[a-z0-9][a-z0-9._-]{0,63}$`-shaped [CITED summary]), `label` (1-120), `scope` (1-300), `measurement`; optional `measuredAt`. A measurement is `null`, `{kind:"percent", value 0-100, valueMax?, approximate?}` or `{kind:"ratio", completed ≥0 int, total >0 int, unit 1-40, approximate?}`. Semantics: unique ids, completed ≤ total, "no overall percentage is inferred".
- Refresh step, verbatim from the page [VERIFIED: curl decomphub.com/progress]:
```yaml
- name: Notify DecompHub
  env:
    PROJECT_REPOSITORY: https://github.com/${{ github.repository }}
    PROJECT_REVISION: ${{ github.sha }}
  run: |
    jq -n --arg repository "$PROJECT_REPOSITORY" --arg revision "$PROJECT_REVISION" \
      '{repository: $repository, revision: $revision}' |
      curl --fail --silent --show-error --max-time 20 \
        -H "Content-Type: application/json" --data-binary @- \
        https://app.decomphub.com/api/progress/refresh
```
  Gate it with `if: github.event_name == 'push' && vars.DECOMPHUB_REFRESH == 'true'` (D-30: behind a repo variable the owner sets). README link: `[Progress data](decomphub.progress.json)`.
- The page does not describe a maintainer verification process; D-31's file follows TheGh0stShip's precedent (brief), and the owner files the claim.

### shields endpoint (D-26)

Required `schemaVersion` (number 1), `label` (here `"decompiled"`), `message` (non-empty); optional `color` (default `lightgrey`), `labelColor`, `isError`, `namedLogo`, `logoSvg`, `logoColor`, `logoSize`, `style`. `cacheSeconds` is a query parameter, not a schema field [CITED: shields.io/badges/endpoint-badge]. The README already uses `https://img.shields.io/endpoint?url=https://ayrtondenner.github.io/ReverseApoc/progress-shield.json` [VERIFIED: README.md:10].

### GitHub Pages workflow (D-27)

```yaml
name: Pages
on:
  push:
    branches: [main]
    paths: ["config/*/status.csv", "config/*/functions.csv", "config/*/units.csv",
            "tools/progress.py", "decomphub.progress.json", ".github/workflows/pages.yml"]
  schedule:
    - cron: "17 4 * * 1"          # weekly; also refreshes the 90-day report artifact
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: false
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10.3.0     # same pin as ci.yml
        with: { version: "0.12.23" }
      - run: uv sync --locked
      - run: uv run python -I tools/progress.py --out _site --report build/report.json
      - uses: actions/upload-artifact@v7
        with: { name: X-COM_Apocalypse_DOS_report, path: build/report.json, retention-days: 90, if-no-files-found: error }
      - uses: actions/upload-pages-artifact@v5
        with: { path: _site }
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: { name: github-pages, url: "${{ steps.deployment.outputs.page_url }}" }
    steps:
      - id: deployment
        uses: actions/deploy-pages@v5
  # notify-decomphub job: the D-30 step above, needs: deploy
```
Facts: `upload-pages-artifact` inputs `name` (default `github-pages`), `path`, `retention-days` (default 1); it tars and excludes dotfiles unless `include-hidden-files`. `upload-artifact@v7` inputs `name`, `path`, `if-no-files-found`, `retention-days`, `archive` (default `true`, zipped). Both have the major tags `v5`/`v7` [VERIFIED: gh api action.yml and git refs].
**Python:** ubuntu-latest's system Python is not 3.14, so D-27's bare `python -I tools/progress.py` must run under uv (above) or setup-python [ASSUMED runner image version]. `-I` implies `-P`: the script's directory is not on `sys.path`, so progress.py must not import siblings (see Pattern 4).
Scheduled workflows are disabled after 60 days without repository activity [ASSUMED GitHub policy], so the weekly run only lives while the repo is active.

## Architecture Patterns

### System flow

```
                    ┌──────────── Windows host (main checkout) ─────────────────────────────┐
 owner: reverseapoc drive ──► driver.py
   │  preflight: claude --version, docker up, uv sync, asm listings, drafts batch (container)
   │  scorer (host, orig/) ──► pick next (status-aware, variety) ──► difficult list
   │  context pack (host) ──► build/driver/<run>/<exe>/<func>/{context.md,mcp.json,notes.md}
   │  scaffold unit file if missing (units --write-src, committed CSVs)
   │  spawn claude -p "/goal…" ──► stream-json ──► classifier ──► LIMIT/STOP/TRANSIENT
   │        │ hooks (always + matching) on every tool call (Git Bash → uv → hooks.py)
   │        └► MCP server (host python) ── check ──► docker compose run --rm -T build … check --json
   │  post: transcript audit + git status --porcelain allowlist ─► stray? reset + STOP night
   │  gate (container) ─► check_unit + cross-check + status.csv + decomphub.progress.json
   │       exit 0 ─► git commit (explicit paths, trailers) ; else ─► reset ; attempts.jsonl
   │  end of run: ninja -t clean && ninja verify ; gate --all ; chore(driver) commit
                    └───────────────────────────────────────────────────────────────────────┘
 push to main ─► CI (pytest: drift test, hooks, driver w/ fake claude) ─► Pages job:
   progress.py(status.csv + functions.csv + units.csv) ─► _site/{progress.json,svg,shield} + build/report.json
   ─► deploy-pages ; artifact X-COM_Apocalypse_DOS_report ; optional DecompHub POST
```

### Recommended layout (Claude's discretion)
```
tools/progress.py                 # stdlib only, imports no reverseapoc (runs under -I in Pages)
tools/reverseapoc/status.py       # status.csv read/write/validate (schema of D-20)
tools/reverseapoc/gate.py         # gate EXE/UNIT, --partial, --all; cross-check
tools/reverseapoc/hooks.py        # decide(payload, layer, ctx) -> Decision ; main()
tools/reverseapoc/mcp.py          # JSON-RPC dispatcher + tools check/asm/context
tools/reverseapoc/contextpack.py  # pack builder, look-alikes, truncation
tools/reverseapoc/driver.py       # loop, scorer wrapper, classifier, attempts log, commit
tools/reverseapoc/streamjson.py   # parse + classify events (pure)
tools/reverseapoc/fileio.py       # write_atomic (DI-18)
config/driver/claude-settings.json
config/<exe>/status.csv           # gate-written
progress/attempts.jsonl           # driver-written, committed
decomphub.progress.json           # gate-written, committed
.claude/skills/watcom-decomp/SKILL.md
tests/fakeclaude.py + tests/fixtures/stream/*.jsonl  # synthetic, no game bytes
```

### Pattern 1: pure core, thin shell (every new module)
`hooks.decide(payload: dict, *, layer: str, repo: Path, tracked: Callable[[str], bool], notes: str | None) -> Decision`; `mcp.handle(message: dict, tools: Tools) -> dict | None`; `streamjson.classify(events, exit_code) -> Disposition`; `progress.derive(status, functions, units) -> Progress`. The shells read stdin/argv/env and write stdout. Tests feed dicts; one subprocess end-to-end test per shell.

### Pattern 2: hook decision function (D-16/D-17)
1. Normalize the path: `p = PureWindowsPath(raw) if "\\" in raw or ":" in raw[:3] else PurePosixPath(raw)`, then resolve `..` (use `os.path.normpath`, and `os.path.realpath` when the file exists) and casefold the result for comparison on Windows (NTFS is case-insensitive). Find the repo root as the nearest ancestor holding `.git` (a directory or a worktree file), not `CLAUDE_PROJECT_DIR`, which "stays fixed when Claude enters a worktree" [CITED: hooks].
2. **Always layer** (matcher `Edit|Write|MultiEdit|NotebookEdit`): deny when the repo-relative path starts with `orig/`, `asm/` or `build/` (except the exact `REVERSEAPOC_ATTEMPT_NOTES`), equals `config/targets.toml` or `config/watcom.toml`, or ends with `.sha1`. For `src/**` and `include/**`, build the post-edit text (Write: `content`; Edit: the current file with `old_string`→`new_string` applied once, or all with `replace_all`), splice `\`-newline continuations, blank comments and literals with configure's `_NOT_CODE`/`_blank`, then deny on `\b_{1,2}asm\b`, `_Pragma`, or a `#pragma aux` whose body holds `=` (code-emitting) [ASSUMED token set; Watcom keyword list not verified].
3. **Matching layer** (matcher `*`): allow `Read`/`Glob`/`Grep` only for paths inside the repo (deny `~/.claude*` credentials and other outside reads); allow `mcp__reverseapoc__{check,asm,context}`; allow Edit/Write only to `src/<exe>/<claimed unit>.c`, to `include/*.h` not tracked at HEAD and not `common.h`/`watcom_compat.h`, and to the notes path; deny any `#pragma aux`; deny every other tool (Bash, PowerShell, Agent, WebFetch, TodoWrite, ...), plus status.csv, attempts.jsonl and decomphub.progress.json.
4. Any exception inside `main()` → exit 2 with the reason on stderr (fail closed). The matching settings also set `"onFailure": "block"`; leave it out of `.claude/settings.json`, because an older CLI may drop a handler with an unknown key [ASSUMED].
5. Read the claimed unit from env `REVERSEAPOC_CLAIM=<exe>/<unit>` set by the driver; with no claim, the matching layer denies all writes.

### Pattern 3: gate and status table (D-20..D-24)
```python
# gate.py (container). check_unit signature: check.py:845-860 [VERIFIED]
result = check_unit(exe, unit, orig_dir=..., manifest=..., config_root=..., src_root=..., build_dir=...)
if result.exit_code != EXIT_OK: return EXIT_MISMATCH          # writes nothing
landed = {s.exe: set(s.result.landed) for s in result.splices}   # LandResult.landed: row starts [VERIFIED: land.py:90]
new = status_rows_for(result.functions, unit, src_sha256(lf_normalised(src)), attempts, today)
expected = matched_starts(read_status(all exes)) | {f.va for f in result.functions}
if any(landed[name] != expected[name] for name in landed): return EXIT_MISMATCH   # D-24 cross-check
write_status(merge(existing, new)); write_decomphub(progress.derive(...))      # write_atomic
```
- `gate --partial` recomputes `best_percent` by running `check --src build/driver/.../best` (safe only after DI-06(b), which routes a non-default `--src` to `check-custom`). Its row's `source_sha256` names that saved file, and the drift test skips the sha for partial rows.
- `gate --all`: `check_source` for each unit with a matched row (objdiff + relocations), then **one** `land_all`. Calling `check_unit` per unit would recompile every unit for each one, O(n²).
- Seeding: the two Phase 5 matches (UFO2P func_000A3980 in u_000a34f0, TACP func_00055080 in u_00054f20) get their rows by running `gate` in the container in the main checkout. That makes RPT-01's plan a main-checkout plan.
- CSV style: a first-line comment like the other generated CSVs (`# written by: uv run reverseapoc gate EXE/UNIT; do not edit`), `0x%08X` starts (functions.py's IN-05 rule), and LF line endings (`.gitattributes` `* text=auto eol=lf` [VERIFIED]).

### Pattern 4: progress.py under `python -I`
progress.py parses the three CSVs with `csv` itself. A test checks that its parser agrees with `reverseapoc.functions.read_functions_csv`/`read_units_csv` on the committed files. `gate` and the tests load it by path with `importlib.util.spec_from_file_location`, the way `check._configure()` loads configure.py [VERIFIED: check.py:329-347]. Outputs: `progress.json` (per EXE and combined: total/matched/partial/uncovered bytes, function counts, library bytes as their own group, generated-from commit if given), `progress.svg`, `progress-shield.json`, `report.json`, and `decomphub.progress.json` (written by gate, re-derived by the drift test).

### Pattern 5: squarified treemap (stdlib)
Bruls/Huizing/van Wijk: sort values descending; grow a row while the worst aspect ratio improves; lay the row along the shorter side; recurse into the remainder. Nest EXE → unit → function (each level's rect fed to the next). About 3,600 cells × ~110 bytes comes to about 400 KB of SVG. Keep `<title>` tooltips on unit groups and matched cells only, round coordinates to 0.1, and use fixed colours for matched / partial / unmatched / library / uncovered. Determinism (stable sort by size, then start) is required by the drift test and by Pages diffs.

### Pattern 6: context pack (D-13/D-14)
- Target listing `asm/<exe>/<file_name>.s` (after DI-01, one per row).
- Unit file text.
- Callees from `asm.walk` + `asm.branch_target` over the row; callers from a reverse index built once per run over all game rows (host, capstone; seconds).
- Each caller/callee carries its status (status.csv) and, when matched, its C prototype taken from the definition head (configure `_DEFINITION` match + brace scan on comment-blanked text, sliced from the original text).
- `D_` externs from the off32 fixups inside the row (`symbols.c_name(va, data=True)`).
- `include/common.h`.
- The Ghidra draft `asm/<exe>/ghidra/func_X.c`.
- matching.md L55-68.
- Earlier notes.md and attempts.jsonl rows for this function.
- Look-alikes: `difflib.SequenceMatcher(None, mnemonics(target), mnemonics(m)).ratio()` against every matched row, top 3 above a floor (e.g. 0.6), each with its C [ASSUMED metric; discretion].
- **Truncation:** required sections are never cut. Optional sections are dropped or shortened in the order look-alikes → callers → draft until the pack is ≤ 24,576 bytes (UTF-8); record `pack_bytes` and `truncated[]` in attempts.jsonl.

### Pattern 7: driver state machine (AGT-01/02/04)
```
for fn in queue (scorer ∖ status ∖ capped-this-pass, variety rule, interleave EXEs):
  for attempt in 1..3:
     session = run_claude(fn)        # wall clock 1800 s; kill tree on timeout (Windows: taskkill /T /F /PID)
     d = classify(session)
     LIMIT → backoff/poll, retry same attempt (not counted)   TRANSIENT → ≤3 retries
     STOP  → write STOPPED, end run
     audit(transcript tool_use paths) and git status --porcelain=v1 --untracked-files=all ⊆ allowlist, else reset + STOP night
     gate (container) exit 0 → commit MATCHED, break
     else reset(unit, include/), outcome PARTIAL (best % > 0 from MCP check log) or GAVE_UP
  capped → difficult list (re-queue when pool empty or a callee matched)
  stop when matched ≥ target or sessions ≥ max
end: ninja -t clean && ninja verify ; gate --all ; commit attempts.jsonl (chore(driver))
```
- Reset (D-34): `git restore --source=HEAD -- <unit> include/` when the unit file is tracked; delete it when it was scaffolded this attempt; `git clean -f -- include/` for new headers. Never `git add -A`.
- Every subprocess is an argv list (`claude.exe` is a real exe, so no shell is needed [VERIFIED: where claude]).
- Inject `claude_cmd`, `gate_runner`, `clock`, `sleep` and `git` for tests.

### Commit composition (D-25)
`git commit -F <msgfile> -- <unit.c> config/<exe>/status.csv decomphub.progress.json progress/attempts.jsonl [new include/*.h]`. Subject `feat(ufo2p): match func_0008A0E0 in u_0008a0b0 (C89)`. The body has attempt n/3, model (from init), turns, tokens, seconds, objdiff 100%, relocation ok, and both SHA-1s from the gate JSON. The trailers are set in the message: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Matched-By: reverseapoc drive`. `.githooks/commit-msg` skips a message that already has a Co-Authored-By trailer [VERIFIED: .githooks/commit-msg].

### Anti-patterns to avoid
- Trusting the result event or `/goal`'s verdict for MATCHED. Only the driver's own gate counts.
- `check_unit` per unit inside `gate --all` (recompiles everything n times).
- Writing hooks with a shell pipeline. Exit codes other than 0/2 fail open.
- Letting the MCP `check` tool take a free unit argument. Bind it to the claimed unit given on the server's argv; `asm` takes only a row name of the same EXE that the SymbolTable resolves.
- Running the docker-based MCP server with a TTY (`docker compose run` without `-T` against `tty: true` services corrupts JSON-RPC framing [ASSUMED]; `docker/compose.yaml` sets `tty: true` [VERIFIED]).

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| Unit-file parsing (marks, definitions, conditionals) | a second regex parser in hooks/drift/pack | `check.source_marks` → `configure._live_code`, `_NOT_CODE`, `_blank`, `_MARKER`, `_DEFINITION` [VERIFIED: check.py:357-369, configure.py:153-169] | configure and check must agree (D-12) |
| Matching verdict | anything new | `check.check_unit` / `check_source` / `land_all` | the oracle is fixed (CLAUDE.md) |
| Atomic writes | open/replace code | `fileio.write_atomic` (DI-18) | 7 modules already share it |
| Disassembly / features | a new decoder | `asm.walk`, `x86.decode`, `score.assess` [VERIFIED: score.py:287-302] | scorer and listings see the same instructions |
| Names | string formatting | `SymbolTable.linker_name`/`c_name`/`address_of` [VERIFIED: symbols.py] | Pitfall 3 of Phase 5 (one naming function) |
| Sequence similarity | Levenshtein code | `difflib.SequenceMatcher` | stdlib |
| JSON Schema validation | a validator | pinned property sets + enum constants in tests | no jsonschema dependency (rules/tools.md) |

## DI code-level plan (what changes, where, how it is proven)

| DI | Change | Files | Proof (host H / container C / real R) |
|---|---|---|---|
| 01 | `file_name`: also use `<kind>_<start>.s` when `name in symbols.ambiguous` (today only unsafe names; `_Alphabet` is a runtime row at two addresses per EXE) [VERIFIED: asm.py:244-249; functions.csv dup check found only `_Alphabet` in both EXEs, no case-only collisions] | asm.py | H: synthetic table with a duplicate runtime name → two distinct files; plus a test that file names are unique case-insensitively (the asm/ bind mount is NTFS) |
| 02 | Pair a data-in-code row with its `_TEXT` span. wcc386 puts the table at `_TEXT+0` before the public and emits `jmp cs:[eax*4+_TEXT+0]` [CITED: 05-REVIEW IN-02]. Map `[0, first public)` to the unit's D_ row that ends ≤ the function's row start (account for filler; e.g. UFO2P D_000108EC ends 0x00010934, the function starts 0x00010940), as an `OwnPublic` entry; relocation-check the table itself (its entries are own-segment fixups into the function); keep refusing anything else. **77 of 80 UFO2P data-in-code rows are game tables, most mid-unit**, so a non-leading table (between two publics) inflates the previous public's omf2elf size and still fails closed; D-39 covers the leading case only [VERIFIED: functions.csv scan] | check.py (`own_publics`, account), relocs.py (no widening; `test_own_segment_layout_coincidence_is_not_trusted` must stay) | C+R: the IN-02 6-case switch probe with real wcc386 10.6 passes; a wrong case target fails; H: relocpair synthetic table |
| 03 | A static named with its row's name (`static int func_X(void)`) is an LPUBDEF `func_X_`, and its callers use an EXTDEF `func_X_` [CITED: learnings.md:16]. `defined_functions` already pairs by name (`module.publics` includes locals) [VERIFIED: check.py:257-275,406-416]. Risk: omf2elf emits a LOCAL defined and a GLOBAL undefined symbol of one name; elf.py refuses "ambiguous" symbols [VERIFIED: elf.py:211]. **Probe first**, then resolve a self-EXTDEF to the local public in omf2elf/relocs | omf2elf.py, relocs.py or check.py | C+R: real wcc386 static helper + caller passes `check`; `helper` (no row name) still fails with the IN-01 message |
| 04 | 12a refuse duplicate/overlapping `own_publics` in `_check_own_publics`; 12b test a target at a public's end (refused); 12c test a wrong target inside the function (fails "resolves to ... lands on") [CITED: 05-REVIEW L300-313] | relocs.py, tests/test_relocs.py | H (relocpair) |
| 05 | Splice backslash-newline before blanking (C translation phase 2 precedes comment removal). To keep line numbers, drop each `\`+newline and add the newlines back at the end of the logical line. Fixes `//...\` and `#define ...\` hiding a marker or definition | configure.py (`_live_code` caller / `check_unit_source`, `source_marks`) | H: the three continuation texts from the 05 review probe |
| 06a | Provenance stamp `<obj>.prov.json` written by `cc` (compiler spec, flags, sha256 of src text, sha256 of cflags.txt and watcom.toml); `land_all(compile_fn=None)` refuses an object whose stamp is missing or stale | compiler.py, check.py `_land_exe`, configure.py (stamp as implicit output) | H fake compiler; C: ninja keeps working |
| 06b | `object_root` also routes a non-default `src_root` (and config_root) to `check-custom` [VERIFIED: check.py:207-215 checks only cflags/manifest/watcom_dir] | check.py | H: `check --src OTHER` leaves `build/<exe>/obj` untouched |
| 06c | build.ninja `target`/`land`/`asm`/`check-orig`/`rebuild` rules carry `--config {config}` and `--manifest {config}/targets.toml` when non-default (today only `collect_units` reads `config/targets.toml`) [VERIFIED: configure.py HEADER rules L72-113, collect_units L182-193 region] | configure.py | H: test_configure with a tmp config |
| 11 | toolchain.md cc.log bullet (both platforms' messages, device branch covers directories) and `_check_log_name` refusing an existing directory before the compile [CITED: 04-REVIEW IN-08 fix] | compiler.py:309-313, docs/toolchain.md | H |
| 12-17 | IN-08 (above); IN-09 pre-compile open of `<log>.lock` with "a+b"; IN-10 `_reap` docstring plus `cc_root` failing when rmtree leaves the dir; IN-11 `/dev/null.lock` test fails instead of skipping; IN-12 docstring "the Windows host and a container"; IN-13 create the object first and assert it survives [CITED: 04-REVIEW.md L71-200] | compiler.py, tests/test_compiler_real.py, test_cc_log.py, test_cli.py | H (IN-11 also C, as user dev) |
| 18 | `fileio.write_atomic`; `splice._write_atomic = write_atomic` alias for one release; update the importers asm, check, cli, compiler, functions, land, libmatch, omf2elf, and tests/test_compiler.py monkeypatches `compiler._write_atomic` [VERIFIED: grep] | new fileio.py + 8 modules | H: existing suite; one test that the alias is the same object |
| 19 | The rest of the 05 minors: wording/test-style items (05-REVIEW rows 1-5, 7a-d, 8, 9a-d, 10a-d, 11, 13a-b, 14, 16a-b, 17a-c, 18a-c, 19a-b). 19b adds a comment to matched `src/tacp/u_00054f20.c`, an allowed edit (comments only), and the gate must re-run it, because `source_sha256` changes (D-22) | various | H; the 19b re-gate is C+R |
| 20-23 | doc lines verified: matching.md:57,63 "Nothing recorded yet"; learnings.md:86; toolchain.md:374 "candidate pending Phase 5 matches", :166 "`-s`: consistent"; tools.md:53 ast-grep **Use**, :16 GhidraMCP; design spec :76; README :62 (retrokit), :139; toolchain.md:13 SMKP entry obj1:0x6CB0; `.dockerignore` lacks `**/*.IMG`, `**/*.CUE`, `**/*.mdf`, `**/*.MDF` (has lowercase `img`, `cue`) [VERIFIED: read each line] | docs, .dockerignore, test_hygiene parametrization | H (hygiene test extended) |
| 26-31 | paperwork: 04-SECURITY T-04-13 sign-off; 04-VALIDATION L102 "**Approval:** pending" [VERIFIED]; 05-VERIFICATION L45 `**Status:** human_needed` vs frontmatter `status: passed` [VERIFIED]; spike 005 owner line; STATE.md duplicated RESOLVED text (L113 region) and the "(none)" deferred table [VERIFIED]; ROADMAP Phase 7 SC4 reword (999.2) | .planning/* | review only |
| 33 | `config/watcom.toml:37` LE→LX. No test or gate hashes the file's bytes: `test_compiler_real.py:84-88` reads key-file sha1s; `compiler._stamp_files` stats compiler binaries; configure lists it only as an implicit ninja input, so an edit triggers a recompile and nothing more [VERIFIED: grep]. Do it before the hooks land and before 06a (whose stamp may hash the file) | config/watcom.toml | H: `load_watcom_manifest` parses; R4 for line 106 |

## Runtime State Inventory (new runtime state this phase creates)

| Category | Items | Action |
|---|---|---|
| Stored data | `config/<exe>/status.csv`, `decomphub.progress.json`, `progress/attempts.jsonl` (committed); `build/driver/<run>/...` (transcripts, packs, mcp.json, notes, check logs; gitignored) | gate/driver write; the drift test guards the first two |
| Live service config | GitHub Pages source = "GitHub Actions" (owner, once; `has_pages:false` per brief); repo variable `DECOMPHUB_REFRESH`; the DecompHub entry (pending review) | owner checkpoint tasks |
| OS-registered state | none (no scheduled tasks; the owner starts the driver by hand) | none, verified by D-34/D-37 |
| Secrets/env vars | none new. The driver sets `REVERSEAPOC_CLAIM`, `REVERSEAPOC_ATTEMPT_NOTES` per session; Tavily stays out via `--strict-mcp-config` | none |
| Build artifacts | Docker image unchanged; the named `uv-venv` volume needs `uv sync --locked` before `--no-sync` runs; build.ninja changes with DI-06c | driver preflight runs `docker compose run --rm build uv sync --locked` |

## Common Pitfalls

1. **Fail-open hooks.** Exit codes other than 0/2 let the tool run, and so does a timeout without `onFailure: block` [CITED]. Catch everything and exit 2. In the driver, also audit every `tool_use` path in the transcript and `git status`, independently of the hooks.
2. **Session pollution.** Without `--strict-mcp-config`, Tavily (`.mcp.json`) and the owner's user/local servers connect, and with them claude.ai connectors. Without `--setting-sources project`, the GSD hooks in `.claude/settings.local.json` run. Without the `enabledPlugins:false` overrides, the security-guidance Stop review runs. **Assert all of it from the `system/init` event** (`tools`, `mcp_servers`, `plugins`) and STOP on any surprise.
3. **`--settings` hooks may override instead of merge** [ASSUMED unknown]. Put the always-on handler in the driver settings file too; "Identical handlers defined in more than one settings file run once" [CITED], so it does not run twice. Prove it at the checkpoint with a canary `claude -p` that tries to Write `config/targets.toml` and `tools/x.py`, and expect both denials in `permission_denials`.
4. **The always-on hook breaks GSD executors writing evidence under `build/` with the Write tool.** Phase 5 plans wrote evidence by shell redirection (`> build/gate/...`) [VERIFIED: 05-*-PLAN.md]; Phase 6 plans after the hook plan must do the same. D-43's watcom.toml edit must come before the hook plan.
5. **Wrong MCP framing on Windows.** CRLF from text-mode stdout, a non-UTF-8 default stdin encoding, a stray `print()`. Use binary buffers. Also, `uv run` prints to stderr only.
6. **`--max-turns 40` binds before "25 check runs".** One check cycle is about 3-4 agentic turns (read, edit, check). Expect `error_max_turns` and map it to a counted attempt. Its outcome is PARTIAL or GAVE_UP from the MCP check log, never "error".
7. **Kill the process tree.** A 30-minute timeout must end claude.exe, the MCP server and any `docker compose run` child (`taskkill /T /F /PID`), and the driver should `docker ps --filter label=...` / `--name` to remove any check container left behind.
8. **Non-deterministic generated files.** decomphub.progress.json and the SVG must be byte-stable (sorted rows, fixed float formatting, LF, trailing newline). Otherwise the drift test flaps between the container (gate) and CI.
9. **`source_sha256` and comment passes.** Any edit of matched C, even DI-19b's comment, changes the sha, so the drift test fails until `gate` re-runs. This is intended (D-22), and the plan must schedule the re-gate.
10. **Scaffolded unit files.** An attempt on a unit without C creates an untracked `src/<exe>/<unit>.c`. Delete it on failure, or every later `gate`/`ninja verify` compiles it (harmless stubs, but noise and drift).
11. **`claude` major upgrades.** `--bare` "will become the default for `-p` in a future release" [CITED]; under bare mode subscription login is never read. The driver refuses a CLI version outside the tested set, and the init `apiKeySource` should be the subscription source [ASSUMED value name].
12. **Pages Python.** Do not rely on the runner's system python for 3.14 syntax (Pattern 4, Pages section).

## Spike 006 procedure (D-01..D-03, CONVENTIONS.md)

- Directory `.planning/spikes/006-decompwtf-fork-stub/` with `README.md` frontmatter (`spike: 006`, `idea: reporting-and-agent-pilot` (new MANIFEST.md idea entry), `name`, `type: standard`, `validates: "..."`, `verdict:`, `related: [005]`, `tags: [decomp.wtf, fork-mode, d-01]`) and one stdlib script per question, run with `uv run python .planning/spikes/006-.../<script>.py`, printing `PASS/FAIL <file> <claim> <detail>` and `ALL PASS`/`N FAILED`, exit 1 on any FAIL [VERIFIED: CONVENTIONS.md].
- `stub_regex.py <path-to-decompwtf-src>`: reads `forks/csource.py` **as text**, extracts `_stub`'s pattern with `ast` (no import, so nothing is vendored or executed), and claims it does not match `INCLUDE_ASM(func_000A34F0);` and does match `INCLUDE_ASM("x", func_000A34F0);`. A planted wrong expectation proves the checker can fail.
- `linker_name.py`: `forkengine._names` reads objdiff symbol `func_000A3980_`, and `csource.find` looks for `func_000A3980(` → mismatch claim (text/ast evidence).
- Smoke run (WSL2, half a day, the owner's distro `ubuntu-recovered`): install uv in WSL2 first (it has none [CITED brief]); `uv tool install "decompnet @ https://github.com/i12bp8/decomp.wtf/archive/refs/tags/v0.10.6.tar.gz"` (requires-python ≥3.12; it pulls `mcp`, `splat64`, `ninja` and others [VERIFIED: gh api pyproject.toml@v0.10.6]). Keep the downloaded source in its own empty directory and treat it as untrusted. Open a clone in fork mode, submit func_000A3980's C via `compile_and_diff`, and record the failure verbatim in the README. Do not build the WSL2 toolchain.
- Verdict per D-02; expected INVALIDATED or PARTIAL → D-03 own layer. Update `.recomp.json` notes (D-32) and docs/tools.md:13 accordingly. `tests/test_hygiene.py:136` bans the phrase "Ghidra and decomp.wtf run in WSL2" in live docs.

## Pilot checkpoint preflight (AGT-11, Wave 4, blocking-human)
1. The owner upgrades the CLI (`claude install stable` or `latest`); the driver's tested-version constant is updated, with min ≥ 2.1.302 recommended (the documented `-p` default; `onFailure` needs 2.1.295; `--strict-mcp-config` approval-skip needs 2.1.246; the MCP wait needs 2.1.221) [CITED].
2. The owner sets Pages source = GitHub Actions and optionally `DECOMPHUB_REFRESH`.
3. A canary session (Pitfall 3) shows hook denials, MCP `connected`, no Bash, no plugins.
4. `reverseapoc drive --dry-run` prints the 10 picks (variety rule) and builds packs, with no claude.
5. The owner starts `reverseapoc drive --max-sessions 40 --target-matched 10`; the phase gate then runs D-24's end-of-run checks and both suites.

## Code Examples

```python
# MCP dispatcher core (stdlib). Spec: 2025-11-25 lifecycle/tools [CITED]
SUPPORTED = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
def handle(msg: dict, tools: "Tools") -> dict | None:
    if "id" not in msg:                       # notification (e.g. notifications/initialized)
        return None
    method, rid = msg.get("method"), msg["id"]
    if method == "initialize":
        asked = (msg.get("params") or {}).get("protocolVersion")
        return _ok(rid, {"protocolVersion": asked if asked in SUPPORTED else SUPPORTED[0],
                         "capabilities": {"tools": {"listChanged": False}},
                         "serverInfo": {"name": "reverseapoc", "version": __version__}})
    if method == "ping":
        return _ok(rid, {})
    if method == "tools/list":
        return _ok(rid, {"tools": tools.describe()})
    if method == "tools/call":
        p = msg.get("params") or {}
        if p.get("name") not in tools.names:
            return _err(rid, -32602, f"Unknown tool: {p.get('name')}")
        text, failed = tools.call(p["name"], p.get("arguments") or {})
        return _ok(rid, {"content": [{"type": "text", "text": text}], "isError": failed})
    return _err(rid, -32601, f"Method not found: {method}")   # also server/discover -> legacy fallback
```

```json
// decomphub.progress.json (shape per progress-v1; values illustrative)
{"format":"decomphub.progress/v1","repository":"https://github.com/ayrtondenner/ReverseApoc",
 "tracks":[
  {"id":"ufo2p-code","label":"UFO2P.EXE matched code","scope":"Game and thunk bytes of UFO2P.EXE (installed build), byte-identical under check; runtime library excluded","measurement":{"kind":"percent","value":0.0018}},
  {"id":"ufo2p-functions","label":"UFO2P.EXE matched functions","scope":"Game and thunk functions of config/ufo2p/functions.csv","measurement":{"kind":"ratio","completed":1,"total":1553,"unit":"functions"}}]}
```
The 1553 is illustrative: 1549 game + 4 thunk rows [CITED brief table sizes]. The `total` must be derived, never hard-coded.

## State of the Art

| Old | Current | When | Impact |
|---|---|---|---|
| MCP `initialize` handshake (legacy, ≤2025-11-25) | stateless per-request `_meta`, `server/discover` (2026-07-28) | 2026-07 | the legacy server stays valid through dual-era clients; re-check when Claude Code drops legacy support |
| `-p` default permission mode inherited | Manual mode when nothing sets one (v2.1.302) | 2.1.302 | pass `--permission-mode dontAsk` explicitly (D-06 does) |
| hooks fail open on timeout | `onFailure: "block"` | 2.1.295 | use it in the driver settings |
| objdiff report v0/v1 | `REPORT_VERSION = 2` (`total_units`/`complete_units`) | objdiff-core | write `version: 2` |

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | Hooks in a `--settings` file merge with project hooks | Hooks contract | the always-on layer is absent in matching sessions; mitigated by duplicating the handler (Pitfall 3) |
| A2 | `enabledPlugins` from `--settings` merges per plugin key (false disables) | CLI facts | plugins load anyway; caught by the init assertion |
| A3 | The allow rule `mcp__reverseapoc__*` matches on the pinned CLI | Recommended argv | MCP calls denied under dontAsk; list the tools explicitly |
| A4 | Claude Code's MCP client falls back to `initialize` against a legacy server | MCP | server not connected; caught by the init check |
| A5 | MultiEdit/NotebookEdit payload fields (`edits[]`, `notebook_path`) | Hook decision | unknown shapes are denied by default in matching mode; always-on may miss one (low: no matching-relevant use) |
| A6 | Watcom inline-asm token set `_asm`/`__asm`/`_Pragma` | Hook decision | a missed spelling slips through the hook but still cannot pass `check` unless it really matches; reviewers see it |
| A7 | pbjson writes u64 as strings | report.json | recomp.fyi may expect numbers; both parse in objdiff |
| A8 | ubuntu-latest Python ≠ 3.14; schedules disabled after 60 days idle | Pages | progress.py fails to run / weekly refresh stops |
| A9 | `docker compose run` without `-T` against `tty: true` breaks stdio framing | Anti-patterns | moot if the host-side server is chosen |
| A10 | Look-alike metric (SequenceMatcher on mnemonics, floor 0.6) | Context pack | weaker look-alikes; tunable |
| A11 | `apiKeySource` value for subscription login | Pitfall 11 | log it rather than assert it until observed |

## Open Questions (owner)

1. **R4**: extend D-43 to `config/watcom.toml:106`? Recommendation: yes, in the same recorded edit.
2. **R7**: the uncovered bytes include alignment filler, so 100% can never be reached. Keep D-40 as is (recommended for honesty, with an "uncovered" legend), or count only gaps ≥ 16 bytes? The UFO2P 3-byte tail outside units.csv cannot be measured in CI.
3. **R5**: confirm that `--max-sessions 40` overrides the night cap of 30 for the pilot run.
4. **R3**: notes through an env-exempted Write (recommended) or through an MCP `notes` tool?
5. Should the DecompHub notify job also run on the weekly schedule? Recommendation: push only (the worker already polls hourly).

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|---|---|---|---|---|
| claude CLI | driver, pilot | ✓ host only | 2.1.240 (upgrade at checkpoint, D-36) | fake claude for all tests |
| Docker Desktop / compose | check, gate, drafts | ✓ | Docker 29.6.2 | none (blocking for gate/pilot) |
| uv | everything | ✓ | 0.12.23 | — |
| git | driver commit/reset | ✓ | 2.54.0.windows.1 | — |
| node | not needed (claude is a native exe) | ✓ | v24.16.0 | — |
| WSL2 `ubuntu-recovered` | spike 006 | ✓ (no uv, ninja, wibo, objdiff, claude [CITED brief]) | — | spike records "no build in WSL2" (an INVALIDATED criterion) |
| objdiff-cli, wibo, clang, Ghidra | gate, real tests, drafts | container only | per image | — |
| gh CLI | read-only checks | ✓ | — | — |

## Validation Architecture

### Test Framework
| Property | Value |
|---|---|
| Framework | pytest ≥9.1 + ruff ≥0.17 (`pyproject.toml`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths tests, pythonpath .) |
| Quick run | `uv run pytest -q tests/test_<module>.py -x` |
| Full suite | `uv run pytest -q && uv run ruff check .` (host), then `docker compose run --rm test` (container), never at the same time |

### Requirement → test map
| Req / item | Behaviour | Type | Command | Where | Files exist? |
|---|---|---|---|---|---|
| RPT-01 | status.csv schema, sorted, LF, `0x%08X`; gate writes only on exit 0 | unit (fake check) | `pytest tests/test_status.py tests/test_gate.py -x` | H+C | ❌ W0 |
| RPT-01 / D-22 | drift: matched rows == `source_marks.defined`; sha matches; decomphub file == derive | CI unit (committed files) | `pytest tests/test_drift.py -x` | H, C, CI | ❌ W0 |
| AGT-06 | gate cross-check refuses when a matched function is reverted to INCLUDE_ASM | unit (fake landed set) + real | `pytest tests/test_gate.py -k crosscheck`; `pytest tests/test_gate_real.py` | H; C+R | ❌ W0 |
| RPT-02 | progress.json numbers; squarified layout tiles its rect, no overlap, deterministic; shield schema keys | unit | `pytest tests/test_progress.py -x` | H, CI | ❌ W0 |
| RPT-04 | report.json uses report.proto field names only, version 2, u64 as strings, percent == progress.json combined | unit | `pytest tests/test_report_shape.py -x` | H, CI | ❌ W0 |
| RPT-03 | pages.yml has the permissions, concurrency, schedule, pinned majors, artifact name, `-I` run, variable-gated POST | text test | `pytest tests/test_workflows.py -x` | H, CI | ❌ W0 |
| RPT-05 | .recomp.json keys ⊆ pinned schema props; status in enum; https links; decomphub feed matches progress-v1 rules | unit | `pytest tests/test_listings.py -x` | H, CI | ❌ W0 |
| AGT-05 | decide(): Windows/POSIX/`..`/case/worktree paths; protected files; asm/pragma after comment blanking and continuation; matching allowlist; Bash/other tools denied; exceptions → exit 2 | unit + 1 subprocess e2e | `pytest tests/test_hooks.py -x` | H, C | ❌ W0 |
| D-04 | MCP initialize/version echo, ping, tools/list, tools/call, unknown tool −32602, unknown method −32601, notifications silent, binary LF framing; check bound to the claimed unit | unit + subprocess e2e (fake check runner) | `pytest tests/test_mcp.py -x` | H, C | ❌ W0 |
| AGT-08 | pack sections, look-alike ranking, ≤24 KB, truncation order, no write outside build/driver | unit (synthetic LE via conftest `build_le_image`) | `pytest tests/test_contextpack.py -x` | H, C | ❌ W0 |
| AGT-07 / D-10 | status-aware skip; 5+5 interleave; ≤2 per unit, ≤3 per 64 KiB | unit (synthetic candidates) | `pytest tests/test_driver_pick.py -x` | H, C | ❌ W0 |
| AGT-01..04 | fake-claude scenarios: match → commit with trailers; partial/gave-up → reset; max_turns; rate_limit backoff (fake clock); auth/billing STOP; overloaded ×3; stray write → reset + stop; timeout kill; malformed lines; init assertion failures; version refusal; caps (3/function, sessions, target) | integration (fake claude, fake gate, tmp git repo) | `pytest tests/test_driver.py -x` | H, C | ❌ W0 |
| AGT-03 / D-23 | attempts.jsonl schema: required keys/types/enums, no extra keys, no long hex blobs | unit | `pytest tests/test_attempts_schema.py -x` | H, CI | ❌ W0 |
| AGT-09 | every path, verb and MCP tool named in SKILL.md exists; ≤300 lines | unit | `pytest tests/test_skill.py -x` | H, CI | ❌ W0 |
| AGT-10 | spike scripts: ALL PASS plus a planted-fail run | spike | `uv run python .planning/spikes/006-*/stub_regex.py <src>` | H/WSL2 | ❌ |
| AGT-11 | pilot: 10 MATCHED commits, gate after each, end-of-run `ninja verify` + `gate --all` | manual-only (owner-started; costs subscription usage) | evidence logs under build/gate/06-evidence/ | host+C+R | — |
| DI-01..06,11-19,22 | see the DI table | unit / real | per-file pytest | H; C+R for 02/03/19b | partly |

### Sampling rate
- **Per task commit:** the touched test files, `-x` (under 30 s).
- **Per wave merge:** full host suite + ruff; then the container suite (sequential). Waves with container plans (02/03 probes, gate seeding, drafts) also run `test_*_real.py` in the main checkout with REVERSEAPOC_ORIG/WATCOM_DIR.
- **Phase gate:** host + container suites green; skip audit (only platform/real-file skips); `ninja -t clean && ninja verify`; `gate --all`; drift test green on the final tree.

### Wave 0 gaps
- [ ] `tests/fakeclaude.py` + `tests/fixtures/stream/*.jsonl` (synthetic events only; no game bytes)
- [ ] `tests/test_status.py`, `test_gate.py`, `test_gate_real.py`, `test_drift.py`, `test_progress.py`, `test_report_shape.py`, `test_workflows.py`, `test_listings.py`, `test_hooks.py`, `test_mcp.py`, `test_contextpack.py`, `test_driver_pick.py`, `test_driver.py`, `test_attempts_schema.py`, `test_skill.py`, `test_fileio.py`
- [ ] conftest: a `requires_orig()` helper (EXE present under ORIG_DIR); a tmp git repo fixture for driver tests
- No framework install needed.

## Security Domain

| ASVS category | Applies | Control |
|---|---|---|
| V2/V3 Authentication/Session | no (subscription login stays in the CLI) | `--bare` refused; no API key handling |
| V4 Access control | yes | the hook allowlist (deny by default), `--tools`, `--strict-mcp-config`, MCP tools bound to the claimed unit, the driver's post-attempt audit |
| V5 Input validation | yes | the MCP args schema (row-name regex `func_[0-9A-F]{8}` or a SymbolTable name), hook payload validation (deny on unknown shape), stream-json lines parsed defensively, status.csv parser strict |
| V6 Cryptography | minimal | sha256/sha1 via hashlib only |
| V12/V14 Files/Config | yes | write_atomic; paths normalized (`..`, case, worktree); no secrets in settings; the CI POST behind a variable with `--max-time 20` |

| Threat | STRIDE | Mitigation |
|---|---|---|
| Agent edits the oracle/manifests/status to fake a match | Tampering | two hook layers, the post-attempt audit, the gate re-run in the container, the drift test in CI |
| Agent reads credentials (`~/.claude/.credentials.json`) and writes them into committed C | Info disclosure | matching layer denies reads outside the repo; the driver commits only the allowlisted paths; human review of the matched C |
| Prompt injection via game strings/drafts in the pack | Tampering | the agent has no shell or network; all writes are allowlisted; the verdict comes from the build |
| Runaway spend | DoS | `--max-budget-usd 5`, `--max-turns 40`, 30-minute wall clock, session/target caps, STOP on billing |
| Hook crash → fail open | Elevation | catch-all → exit 2; `onFailure: block`; independent audit |
| Supply chain (decomp.wtf) | Tampering | WSL2-only spike, pinned tag tarball, untrusted-dir handling, never imported |

## Sources

### Primary (HIGH)
- In-repo files read this session: tools/reverseapoc/check.py (full), relocs.py (full), symbols.py, asm.py (L1-60, 225-283), score.py (L1-60, 220-362), compiler.py (L290-320, 460-593), cli.py (L913-1003, 1060-1180), configure.py (L1-340, render), land.py (L53-96), include/common.h, include/watcom_compat.h, config/watcom.toml (L30-45, 106), .claude/settings.json, .mcp.json, .recomp.json, README.md L1-20, .githooks/commit-msg, docker/compose.yaml, .github/workflows/ci.yml, .gitattributes, .gitignore, .dockerignore, tests/conftest.py, .planning/spikes/CONVENTIONS.md, 05-REVIEW.md L180-313, 05-REVIEW-FIX.md, 04-REVIEW.md L67-200
- objdiff report.proto, build.rs, bindings/report.rs (raw GitHub / gh api)
- decomphub.com/schemas/progress-v1.json; decomphub.com/progress (curl, verbatim snippet)
- recomp.fyi/schema/v1.json and /add (curl)
- gh api: GitHub Actions releases and action.yml inputs; decomp.wtf v0.10.6 pyproject.toml

### Secondary (MEDIUM, official docs via WebFetch)
- code.claude.com/docs/en/hooks, /mcp, /headless, /cli-reference, /settings, /settings-reference, /goal, /agent-sdk/typescript (curl: SDKResultMessage, SDKSystemMessage, SDKRateLimitEvent, ModelUsage)
- modelcontextprotocol.io/specification 2025-11-25 transports and lifecycle; latest versioning and tools
- shields.io/badges/endpoint-badge

### Tertiary (LOW)
- Assumptions A1-A11 above.

## Metadata
**Confidence breakdown:** standard stack HIGH (no new deps); external contracts HIGH (fetched); Claude Code merge semantics MEDIUM (docs silent, so probed at the checkpoint); DI-02/DI-03 implementation MEDIUM (needs the real-compiler probe first).
**Research date:** 2026-10-24. **Valid until:** about 2026-11-07 for the Claude Code CLI facts (fast-moving); 30 days for the rest.
