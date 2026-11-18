---
title: Stray messages say "(codex audit)" for every harness
created: 2026-11-17
area: driver
files: tools/reverseapoc/driver.py
source: 2026-11-16 run records (Copilot and agy strays labelled codex)
---

# One shared label names the wrong audit

`driver._AUDIT_MARK = " (codex audit)"` marks every audit stray, so the run records of
2026-11-16 call Copilot's tool-shape strays "(codex audit)". It is cosmetic, but it misleads
whoever reads a STOPPED record.

**Do (test first):** name the harness that audited the session (claude hook, codex, agy,
copilot) in the mark, keeping its role as the marker that tells a reason from a file to
contain.

**Done when:** a Copilot stray's record says "(copilot audit)" and the containment logic still
skips marked reasons.
