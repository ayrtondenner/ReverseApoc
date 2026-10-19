# Workflow ownership (GSD vs superpowers)

- GSD owns milestone and phase bookkeeping and the discuss -> plan -> execute -> verify loop
  (`/gsd-discuss-phase N`, `/gsd-plan-phase N`, `/gsd-execute-phase N`, `/gsd-verify-work N`,
  `/gsd-spike` for feasibility experiments). The files under `.planning/` are the record.
- superpowers owns the work inside a phase: brainstorming before new design, test-driven
  development for Python tooling, verification-before-completion before any "done" claim.
- When both prescribe a step, follow GSD's phase files for sequencing and superpowers for how
  the step is carried out. Re-run `/gsd-health` after updating either plugin.
- Claude Code is the only agent runtime in this repo. Do not generate files for other runtimes.
