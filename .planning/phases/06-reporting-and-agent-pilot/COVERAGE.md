# API Coverage — Phase 6 external surfaces (Claude Code CLI headless, DecompHub, GitHub Pages/Actions, recomp.fyi)

> Full coverage by default. Opt-outs are explicit, reasoned decisions (CONTEXT.md D-06, D-08, D-27..D-33, D-44, D-45).

| capability | decision | reason |
|---|---|---|
| claude-cli:print-mode (`-p` with a `/goal` prompt) | INTEGRATE | |
| claude-cli:output-format-stream-json (`--output-format stream-json --verbose`) | INTEGRATE | |
| claude-cli:max-turns | INTEGRATE | |
| claude-cli:max-budget-usd | INTEGRATE | |
| claude-cli:model | INTEGRATE | |
| claude-cli:permission-mode-dontAsk | INTEGRATE | |
| claude-cli:tools (built-in tool restriction) | INTEGRATE | |
| claude-cli:allowedTools | INTEGRATE | |
| claude-cli:strict-mcp-config | INTEGRATE | |
| claude-cli:setting-sources | INTEGRATE | |
| claude-cli:settings-file | INTEGRATE | |
| claude-cli:append-system-prompt-file | INTEGRATE | |
| claude-cli:version (`claude --version`) | INTEGRATE | |
| claude-cli:stream-events (init, api_retry, rate_limit_event, tool_use, result) | INTEGRATE | |
| claude-cli:hooks-PreToolUse (permissionDecision deny, exit 2) | INTEGRATE | |
| claude-cli:mcp-config | OPT-OUT | explicitly out of scope: no MCP server in Phase 6 (D-44); --strict-mcp-config with no server keeps all servers out |
| claude-cli:bare-mode | OPT-OUT | not needed: --bare needs ANTHROPIC_API_KEY and the owner uses a subscription (D-06) |
| claude-cli:resume-continue-session | OPT-OUT | explicitly out of scope: one fresh session per attempt (D-07) |
| claude-cli:json-schema-structured-output | OPT-OUT | not needed: the driver's own gate decides the outcome, never the session's output |
| claude-cli:permission-prompts | OPT-OUT | not needed: dontAsk plus the deny-by-default matching hook bind every tool call (D-45) |
| claude-cli:other-hook-events (Stop, PostToolUse, SessionStart, ...) | OPT-OUT | not needed: PreToolUse guards every edit and command; the owner declined a Stop hook |
| claude-cli:interactive-and-ide-features | OPT-OUT | explicitly out of scope: unattended headless sessions only |
| decomphub:progress-v1-feed (decomphub.progress.json) | INTEGRATE | |
| decomphub:refresh-endpoint (POST /api/progress/refresh) | INTEGRATE | |
| decomphub:maintainer-verification | OPT-OUT | not needed as an API call: the owner files the claim citing docs/DECOMPHUB_VERIFICATION.md (D-31) |
| github-actions:checkout | INTEGRATE | |
| github-actions:upload-artifact (X-COM_Apocalypse_DOS_report) | INTEGRATE | |
| github-actions:upload-pages-artifact | INTEGRATE | |
| github-actions:deploy-pages | INTEGRATE | |
| github-actions:schedule-and-workflow-dispatch | INTEGRATE | |
| github-actions:configure-pages | OPT-OUT | not needed: the owner sets the Pages source once by hand (D-27) |
| github-api:read-only-checks (gh run list, gh api reads) | INTEGRATE | |
| github-api:write-actions (PRs, issues, settings, variables, pushes) | OPT-OUT | explicitly out of scope for automation: the owner performs every outward write (D-30, D-33) |
| recomp-fyi:recomp-json-listing | INTEGRATE | |
| recomp-fyi:report-artifact-ingestion | INTEGRATE | |
| recomp-fyi:submission-form | OPT-OUT | not needed: listing is automatic through .recomp.json and the artifact |
| decomp-me:any-access | OPT-OUT | explicitly out of scope: decomp.me bans LLM and automated access; the owner files the preset issue by hand (D-33) |
