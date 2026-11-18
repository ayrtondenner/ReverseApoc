---
title: Differential emulation for behaviour specs (Phase 8)
created: 2026-11-18
area: specs
source: literature mining of 2026-11-18 (docs/research/notes-ideas-tooling-reproducibility.md #10; docs/research/notes-ideas-llm-decomp-research.md #6)
---

# Differential emulation for behaviour specs (Phase 8)

**Why.** Byte-matching proves bytes, not behaviour; the clean-room spec phase needs runtime checks. Daggerfall's emulator, coverage and call tools and Liu et al./SymDec show the approach.

**Do.** A headless emulator harness (e.g. Unicorn) that calls an original function with spec scenarios and compares against the spec; an `emulator-verified` rung on the SPEC-01 ladder.

**Done when.** One spec verified by emulation end to end.

**Effort / value.** L / high (Phase 8). Evidence and sources: docs/research/notes-ideas-tooling-reproducibility.md #10; docs/research/notes-ideas-llm-decomp-research.md #6.
