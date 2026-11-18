---
title: Order picks by similarity to matched functions, cross-EXE included
created: 2026-11-18
area: picking
files: tools/reverseapoc/picker.py, tools/reverseapoc/contextpack.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-tooling-reproducibility.md #4; docs/research/notes-ideas-agentic-projects.md #2; docs/workflow.md (Select))
---

# Order picks by similarity to matched functions, cross-EXE included

**Why.** workflow.md says to switch to similarity-first picking once enough functions are matched (Lewis found it beat difficulty-first in the long tail), but `picker.py` orders by score only, and the pack's look-alikes come from the same EXE only.

**Do.** Add a similarity score (from the existing retrieval/BSim notes) to the tier queue as an ordering option, and draw pack look-alikes from both EXEs.

**Done when.** `drive --dry-run` shows the similarity order; a held comparison against score order is recorded in docs/model-comparison.md.

**Effort / value.** M / high. Evidence and sources: docs/research/notes-ideas-tooling-reproducibility.md #4; docs/research/notes-ideas-agentic-projects.md #2; docs/workflow.md (Select).
