---
title: A per-function hint file the owner writes, read into the context pack
created: 2026-11-18
source: literature mining of 2026-11-18 (docs/research/notes-ideas-agentic-projects.md #5)
---

# A per-function hint file the owner writes, read into the context pack

**Why.** The owner has no way to pass a hint (a type, a struct, a known flag) to the next session on a hard function except editing notes by hand.

**Do.** A committed hints file (config/hints/<exe>.toml, keyed by function) the pack includes verbatim.

**Done when.** A test shows a hint in the pack; the skill tells agents hints come from the owner.

**Effort / value.** S / med-high. Evidence and sources: docs/research/notes-ideas-agentic-projects.md #5.
