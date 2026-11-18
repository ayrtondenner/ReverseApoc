---
title: An interrupted attempt check leaves checks/.000N.json.*.tmp and stops the night
created: 2026-11-17
area: driver
files: tools/reverseapoc/driver.py, tools/reverseapoc/attempt.py
source: run 20261116-fable-ab, 18:18 STOPPED guardrail (Copilot Sonnet, tacp func_000410C0)
---

# The wrapper's own temp file is a stray when its check is killed mid-write

The 18:18 stop of run 20261116-fable-ab named
`.../tacp/func_000410C0/attempt-1/checks/.0002.json.b6d3a4ff20e5fde3.tmp` as "a wrapper-owned
file the wrapper's ledger never saw" and quarantined it. The attempt wrapper writes a check's
record to a temp file and renames it into place; when the session (here Copilot, whose shell
tool can time out or be backgrounded) dies between the two, the temp file stays and the audit
stops the whole drive.

**Do (test first):** decide which side owns the cleanup. Either the wrapper removes a stale
`checks/.*.tmp` of its own form before each check and at its start, or the audit excuses
exactly that form (`checks/.<n>.json.<16 hex>.tmp`, inside the session's own attempt dir,
never linked) as the wrapper's own leftover, quarantined without stopping the night. Prefer
the narrower one.

**Done when:** a killed check's leftover temp file no longer stops a night, and any other file
in `checks/` still does.

## Resolution (2026-11-18)

Done in batch 2026-11-18 (U1): a `checks/.NNNN.json.<hex>.tmp` left by an in-flight check is quarantined without stopping the night; other files still stop it. Other wrapper temp files: new todo wrapper-temp-files-other.
