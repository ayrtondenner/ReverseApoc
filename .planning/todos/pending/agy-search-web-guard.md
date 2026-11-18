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
