---
title: Notify the owner when a drive stops or ends
created: 2026-11-18
area: driver
files: tools/reverseapoc/driver.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-agentic-projects.md #13)
---

# Notify the owner when a drive stops or ends

**Why.** A drive that stops on a guardrail at night waits until someone looks; several nights lost hours that way.

**Do.** A driver hook that runs a configured notifier command (no secrets in the repo) on STOPPED and ENDED records.

**Done when.** A test fires the notifier on a fake stop; docs name the setting.

**Effort / value.** S / low-med. Evidence and sources: docs/research/notes-ideas-agentic-projects.md #13.

## Resolution (2026-11-18)

Done in batch 2026-11-18 (U2): REVERSEAPOC_NOTIFY runs on STOPPED/ENDED; values cut to safe characters after a security review (d3d2b0bd).
