---
title: Deny agy's search_web in the session settings, not only in the audit
created: 2026-11-18
area: driver
files: tools/reverseapoc/driver.py, config/driver/backends.toml
source: run 20261118-pro (STOPPED guardrail after 9 sessions)
---

# Deny agy's search_web in the session settings, not only in the audit

**What happened.** On run 20261118-pro, GPT-OSS 120B (agy 1.5.11, arm gpt-oss) ran agy's `search_web` tool at step 44 of tacp func_00087090 attempt 1, with the query "reverseapoc plan.json frame string". The step finished (DONE, 3.8 s): the web search ran. The agy audit then stopped the whole drive ("tool 'search_web' ... is not a tool step the agy audit knows"). Fail-closed worked, but only after the egress. The query held only the public project name.

**Why.** driver.agy_settings allows the wrapper command and file reads and writes inside the attempt dir, and denies command forms and paths. It names no deny rule for search_web or other network tools, and agy 1.5.11 lists search_web among its tools (the init event's tool list).

**Do.**
- Add explicit deny rules for every agy tool outside the session's needs: search_web, and read_url or browser tools if agy has them. Take them from the init event's tool list, and fail the canary if a new network tool appears.
- Add a canary probe that asks for a web search and requires it to be denied.
- Decide with the owner whether a denied network step stops only that arm, like a denied write.

**Done when.** A canary on agy 1.5.11 shows search_web denied, and a session that asks for it is refused without egress.

## Resolution (2026-11-19)

Quick task 261119-bhm (batch 261119-bhi), RED 2e44be29, GREEN and docs on branch qb-261119-bhm.

- **Mechanism (read-only, installed agy 1.5.12).** agy's permission grammar, read from its
  binary (the same string in the 1.5.9 binary beside it):
  `^(command|read_file|write_file|read_url|mcp|execute_url|download_url|unsandboxed)\s*\(.*\)$`.
  No kind names search_web, and no settings.json key that disables it was found: the CLI log
  parses only `permissions={Allow, Deny, Ask}` and `toolPermission`; the tool-enable switches
  in the binary (SearchWebToolConfig.enabled / force_disable, CASCADE_WEB_SEARCH_TOOL_DISABLED,
  the app's internet_access_policy) are internal protobuf fields; a custom agent's `tools:` list
  or a PreToolUse hook would need agy user or plugin config, which the driver never writes
  (D-24). The 20261118-pro step itself shows search_web asks no permission (DONE under
  request-review, where headless agy soft-denies anything needing a confirmation). So
  **search_web cannot be denied by the session settings on 1.5.12**; the audit is its guard.
- **Settings.** agy_settings now denies `read_url(*)`, `execute_url(*)`, `download_url(*)` and
  `mcp(*)` (read_url_content, the 23 browser tools, the MCP tools).
- **agyjson.** NETWORK_ACTIONS and NETWORK_TOOLS (explicit, from 1.5.11's init list, each with
  its denying kind or None); init_problems takes the settings' deny rules and refuses a
  network-looking init tool that is unknown or whose kind is not denied; network_steps names
  every network step that ran (search_web always); a network refusal in the deny-rule or
  soft-deny form is a denial, and denied_network lists them.
- **Driver.** A network step that ran stops the drive (guardrail). A denied network step with
  nothing else stray stops only its arm (owner ruling 2026-11-19), like a denied write.
- **Canary.** New `search-web` probe; passes only on a denied network-kind step with no step
  run. Expected to FAIL on 1.5.12 (a search_web step runs).
- **Owner ruling 2026-11-19, "Probe advisory, detect-only"** (quick batch 261119-adv): the
  search-web probe never fails the canary; a denied search is a PASS, anything else an
  ADVISORY (console line, `advisories` in the canary JSON and pass file) the verdict ignores,
  and a night's search_web step still stops the drive.
- **Pending: the live canary on agy 1.5.12** (the coordinator runs it; it also gives the 1.5.12
  init tool list and the first captured network refusal, if any).
