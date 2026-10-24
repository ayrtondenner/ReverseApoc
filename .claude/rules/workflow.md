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
- Claude Code is the only agent runtime in this repo. Do not generate files for other runtimes.
