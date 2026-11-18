---
title: Transfer matches between UFO2P and TACP twins without model tokens
created: 2026-11-18
area: twins
files: tools/reverseapoc/twins.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-tooling-reproducibility.md #5; docs/research/notes-ideas-llm-decomp-research.md #5; docs/workflow.md (Select, line 44))
---

# Transfer matches between UFO2P and TACP twins without model tokens

**Why.** docs/workflow.md calls UFO2P/TACP twin functions the cheapest wins, but nothing implements twin transfer: a match in one EXE is never tried in the other. Lewis's long-tail post and coddog support clone transfer.

**Do.** First count the twins (byte-identical or relocation-identical functions across the EXEs and within each). Then a deterministic `twins` step: copy a matched source to its twin's unit, run the normal gate, and land it with no agent session.

**Done when.** The count is recorded; a test proves a twin lands through the gate; a night reports twin landings separately from agent matches.

**Effort / value.** S-M / high. Evidence and sources: docs/research/notes-ideas-tooling-reproducibility.md #5; docs/research/notes-ideas-llm-decomp-research.md #5; docs/workflow.md (Select, line 44).

## Status (2026-11-18)

Status (batch 2026-11-18, U13, merge d8a4b11d): `reverseapoc twins` is built and a test lands a twin through the gate. Dry run: 84 unmatched rows with a matched twin, 72 candidates, 67 pass on the host. Left: the owner's go to land them.
