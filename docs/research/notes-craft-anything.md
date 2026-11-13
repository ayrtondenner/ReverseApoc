# craft-anything: can it help ReverseApoc?

Read date: 2026-11-13. Source: the English README of
[storytold/craft-anything](https://github.com/storytold/craft-anything), one capture saved for this
evaluation. Nothing else was read: not the linked `docs/tools.md`, `docs/STATUS.md`,
`docs/tool-status.md`, `docs/claude-code.md` or `docs/ROADMAP.md`, not the licence files, not the
code. Nothing was cloned, installed or run. The todo's star count (about 31k) is not in the capture
and is not checked here.

Verdict: **Skip** for Milestone 1. Look again only if a release documents DOS/4GW LE or Watcom
input and a byte-level check.

## What it is

- A pure-Rust engine, "early alpha", MIT or Apache-2.0 at your option. The ArtCraft name and logos
  are trademarks outside that licence.
- Four steps: Study the original, Build a new project with a coding agent, Check the build against
  the original, Ready. Claude Code is the first builder; it runs the user's own `claude` program.
- 320 tools (300 in the engine), each a CLI subcommand and an MCP tool. "Its own decoders,
  disassembler and decompiler work without any outside program." Deep mode adds Ghidra "when it's
  installed". The Advanced workbench shows functions, strings, pseudo-C, disassembly, hex, call
  graphs and an evidence ledger.
- Two modes. Clean room (the default) reads nothing inside the original, only what a user can see
  (screenshots, visible text, layout, an app window). Deep reads code and files, "for your private
  use".
- Checks: websites at three screen widths, "a game's own self-test", "an app's runs". The status
  box lists "behaviour checks for apps and games" as "partly there", and game rebuilds target
  Unity, Unreal or Godot.

## (a) Matching decomp, Phase 7

- The README names no DOS, DOS/4GW, LE/LX, Watcom, `__watcall` or 16/32-bit x86 support. Its native
  coverage is "native programs", with no list of formats or architectures in the README. Whether
  its disassembler or decompiler loads UFO2P.EXE or TACP.EXE is not established.
- Its Ghidra use in Deep mode is not described: the README does not say which loader or cspec it
  passes. Our drafts already come from Ghidra 12.1.4 with the lastonesky LE loader and
  `__watcall` ([tools.md](../tools.md#use--skip--later)). If craft-anything calls Ghidra's default
  loaders, as decomp.wtf did ([notes](notes-decompwtf-rea-ghidra-ida.md)), it would not load our
  EXEs. This is a guess from a similar tool, not a fact about this one.
- Nothing shows its own pseudo-C is better than Ghidra's on any input, and the README gives no
  quality measure. A comparison would need it installed and pointed at our EXEs, which this
  read-only spike does not do.
- Its check compares behaviour and appearance, not bytes. That cannot replace our gate (spliced
  EXE SHA-1 plus objdiff 100%) and does not feed the attempt loop. At best it would be one more
  draft source, and that is unproven.

## (b) Clean-room specs, Phase 8

- Its clean-room mode is the opposite of our spec author's role. In
  [clean-room.md](../clean-room.md#roles) the spec author reads matched C, Ghidra and community
  sources; craft-anything's clean room refuses to read code at all and works from what is visible.
  The README itself says clean room "is a rule about what Craft Anything offers and refuses. It is
  not an operating-system sandbox".
- Its Study -> Build loop fits the OpenApoc implementer's side (build from evidence, check the
  result), not ours. That side is OpenApoc's choice and is out of Milestone 1 (no contact with
  OpenApoc about specs).
- It has no notion of OpenSpec requirements, scenarios or our status ladder, and `speclint` already
  checks the format. Nothing in the README suggests it can check a spec against matched code.

## (c) Ideas to borrow

- Call graphs and function lists: we already have both. `tools/reverseapoc/callgraph.py` builds
  direct, pointer and table edges for `mechanics`, the picker and the driver, and
  `config/<exe>/functions.csv` is the function list. A
  call-graph view on the progress page would come from those, not from craft-anything. The region
  board works inside one function (0x100-byte rows), so a call graph does not fit there.
- Its check loop ("what doesn't match yet", "how alike") is what objdiff's percentage, the check
  summary and the region board already give us, with bytes as the measure.
- One idea worth noting: results are "evidence records with their confidence, coverage and
  limitations", and big ones come back "as a summary first" and are paged. Phase 8 evidence entries
  could name coverage and limitations the same way. This is an idea for the `apoc-spec` work, not a
  dependency.

## (d) Constraints

- Licence: MIT or Apache-2.0 is compatible inbound with GPLv3 for `tools/`. Nothing is vendored, so
  this does not come up. The licence files were not read.
- Runtime rule: it launches the user's `claude` itself, outside `reverseapoc drive` and its guard
  set (hooks, audit, wrapper ledger). The drive exception in CLAUDE.md does not cover a second
  orchestrator. It also offers Codex, Copilot, Grok and other ACP agents as builders, which the rule
  forbids here.
- Egress: in Deep mode the builder "may use all of" the inspection output, so disassembly of the
  game would go to whatever agent or API is selected (Anthropic, OpenAI, OpenRouter, xAI, local, or
  fal.ai for pictures). The README does not say exactly what each backend is sent.
- Game bytes and disassembly: each project folder keeps `capture/`, `app/`, `checks/` and
  `investigation.cany/` (evidence) under `Documents/Craft Anything` by default, outside the repo. A
  project folder chosen inside the checkout would put disassembly where git could pick it up.
- Install: Rust 1.97 or newer to build, or a signed MSI or portable zip on Windows. Neither fits the
  Docker image, and "installing dependencies runs code" for each rebuilt project.

## Not established by the README

- Any DOS, LE, Watcom or 32-bit x86 support, or which architectures the decompiler covers.
- How its pseudo-C compares with Ghidra's, on any target.
- What Deep mode passes to Ghidra (loader, cspec, calling convention).
- What each AI backend receives.
- Whether any tool was tested on a real DOS game; the status box says some engine tools are
  "tested only against stand-ins".
