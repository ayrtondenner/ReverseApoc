---
title: Refuse an attempt check whose C repeats an earlier one
created: 2026-11-18
source: literature mining of 2026-11-18 (docs/research/notes-ideas-agentic-projects.md #12; docs/research/notes-ideas-llm-decomp-research.md #3)
---

# Refuse an attempt check whose C repeats an earlier one

**Why.** About 4.6% of checks (664 of 14,586, measured 2026-11-18) re-submitted C already checked in the same attempt, spending check budget and wall time for no new information.

**Do.** Hash the normalized unit source per check; a repeat returns the earlier result at once and does not count against the budget (or is refused with a message).

**Done when.** A test submits the same C twice and gets the cached verdict; stats counts the repeats.

**Effort / value.** S / low-med. Evidence and sources: docs/research/notes-ideas-agentic-projects.md #12; docs/research/notes-ideas-llm-decomp-research.md #3.
