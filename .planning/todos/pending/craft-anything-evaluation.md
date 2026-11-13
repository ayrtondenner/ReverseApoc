---
title: Evaluate craft-anything for ReverseApoc
created: 2026-11-13
source: owner, during run 20261113-cascade3
---

# Can storytold/craft-anything help?

https://github.com/storytold/craft-anything (MIT or Apache-2.0; early alpha, ~31k stars, read
2026-11-13 from its README). A Rust engine whose loop is study the original -> a coding agent
(Claude Code first) builds a new version -> check -> review. It ships its own decoders,
disassembler and pseudo-C decompiler (~320 tools), uses Ghidra in Deep mode, and has hex views,
call graphs and function lists. Its checks compare behaviour and appearance (screenshots, self
tests), not bytes; its default clean-room mode refuses to read the original's code. Nothing on
the page mentions DOS, Watcom, the LE format or byte-identical output.

Questions to answer (a short spike, read-only, nothing vendored):
- **Matching decomp (Phase 7):** does its decompiler or disassembler handle 32-bit DOS/4GW LE
  code, and would its pseudo-C beat our Ghidra drafts as a starting point for `attempt`
  sessions? Byte matching stays our oracle either way (CLAUDE.md).
- **Clean-room specs (Phase 8):** its study -> rebuild loop and clean-room mode are closer to
  OpenApoc's goal than to ours; could it help write or check the OpenSpec mechanic specs?
- **Tooling ideas to borrow:** call graphs and function lists for the progress page or the
  region board; its agent harness's check loop.
- **Constraints:** licence fit with tools/ (GPLv3; MIT/Apache is compatible inbound), the
  Claude-Code-only runtime rule (it drives Claude Code, so fine if used as a tool), egress (what
  it sends where), and that no game bytes or disassembly get committed.
Outcome: a docs/tools.md entry with a Use / Skip / Later verdict and the reason.
