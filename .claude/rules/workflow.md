# Workflow ownership (GSD vs superpowers)

- GSD owns milestone and phase bookkeeping and the discuss -> plan -> execute -> verify loop
  (`/gsd-discuss-phase N`, `/gsd-plan-phase N`, `/gsd-execute-phase N`, `/gsd-verify-work N`,
  `/gsd-spike` for feasibility experiments). The files under `.planning/` are the record.
- superpowers owns the work inside a phase: brainstorming before new design, test-driven
  development for Python tooling, verification-before-completion before any "done" claim.
- When both prescribe a step, follow GSD's phase files for sequencing and superpowers for how
  the step is carried out. Re-run `/gsd-health` after updating either plugin.
- Create or update a project skill (`.claude/skills/<name>/`) only through superpowers'
  `writing-skills` skill. This covers `watcom-decomp` (Phase 6) and `apoc-spec` (Phase 8).
  A third-party skill kept as installed (such as `unlazy`) is updated from its upstream
  instead, with the new source and hash recorded in `docs/tools.md`.
- Claude Code is the only agent runtime in this repo, with one scoped exception: Codex CLI
  (the owner's ChatGPT Plus, D-13), Antigravity CLI (the owner's Google AI Plus, D-21) and
  GitHub Copilot CLI (the owner's Copilot Pro, owner ruling 2026-11-13, spike 013) may run
  `reverseapoc drive` sessions (spike 012 and later multi-arm nights), launched and audited
  by the driver under its guard set; their per-session config is generated under gitignored
  build/. Do not generate or commit files for other runtimes (no `.codex/`, no `.gemini/` or
  other Antigravity config, no `.github/copilot/`, `.copilot/` or other Copilot config, no
  AGENTS.md); anything else stays Claude Code only.
