---
phase: 01-hygiene-and-safety
plan: 01
subsystem: infra
tags: [hygiene, gitignore, plugins, gsd, docs]
retroactive: true

requires: []
provides:
  - "Repository hygiene rules (game bytes, build output, secrets never tracked)"
  - "Seven plugins at project scope; GSD 1.18.0 project-local for Claude Code"
  - "Lean CLAUDE.md, .claude/rules/, docs skeleton, README, .recomp.json, design spec"
affects: [container-and-target-ingest, byte-identical-round-trip]

tech-stack:
  added: [GSD 1.18.0 (project-local), superpowers, code-review, code-simplifier, claude-md-management, security-guidance, clangd-lsp, i-have-adhd]
  patterns: ["Bring your own game and compiler files; never commit them", "Deterministic checks decide done"]

key-files:
  created: [.gitignore, .dockerignore, CLAUDE.md, .claude/rules/workflow.md, .claude/rules/tools.md, .claude/rules/src.md, docs/workflow.md, docs/toolchain.md, docs/tools.md, docs/legal.md, docs/matching.md, docs/learnings.md, docs/coding-style.md, docs/ceremonies.md, docs/superpowers/specs/2026-10-19-reverseapoc-design.md, README.md, .recomp.json, tools/LICENSE]
  modified: []

key-decisions:
  - "tools/ is GPLv3 so Theme Hospital modules can be reused"
  - "Claude Code is the only agent runtime; plugins installed at project scope"

requirements-completed: [HYG-01, HYG-02, HYG-03, HYG-04]

coverage:
  - id: D1
    description: "git ls-files contains no game file, disassembly, build output, compiler binary, .env or API key"
    requirement: HYG-01
    verification:
      - kind: other
        ref: "node <scratchpad>/hygiene.mjs (scan of 94 tracked files with positive controls) -> 'HYGIENE OK', exit 0, run 2026-10-19"
        status: pass
    human_judgment: false
  - id: D2
    description: "All seven enabled plugins installed at project scope for this repo"
    requirement: HYG-02
    verification:
      - kind: other
        ref: "claude plugin list --json filtered by projectPath -> '7/7 enabled plugins installed at project scope for this repo', run 2026-10-19"
        status: pass
    human_judgment: false
  - id: D3
    description: "GSD installed project-local and /gsd-health healthy (no W028 shadowing)"
    requirement: HYG-02
    verification:
      - kind: other
        ref: "node .claude/gsd-core/bin/gsd-tools.cjs query validate.health -> status healthy, 0 errors, 0 warnings, run 2026-10-19"
        status: pass
    human_judgment: false
  - id: D4
    description: "CLAUDE.md under 150 lines with hard rules, commands, done gate"
    requirement: HYG-03
    verification:
      - kind: other
        ref: "wc -l CLAUDE.md -> 46"
        status: pass
    human_judgment: false
  - id: D5
    description: "Docs skeleton, README, .recomp.json and design spec exist and are coherent"
    requirement: HYG-04
    verification:
      - kind: other
        ref: "ls docs/*.md README.md .recomp.json docs/superpowers/specs/2026-10-19-reverseapoc-design.md"
        status: pass
    human_judgment: true
    rationale: "Whether the docs say the right things is an owner judgement; existence is automated"

duration: n/a (retroactive)
completed: 2026-10-19
status: complete
---

# Phase 1: Hygiene and safety Summary

**Repository made safe to publish and to run agents in before any tooling: no game bytes or secrets tracked, plugins and GSD at project scope, 46-line CLAUDE.md, docs skeleton and approved design spec.**

## Retroactive note

Built before GSD had project state: commit `d7d4d65` (repository hygiene, research, docs and
workflow setup, 70 files) and follow-ups
`f767758` (Tavily key in the user environment, not `.env`) and `e50784f` (bot-based discord plugin
dropped). This SUMMARY was written on 2026-10-19 when GSD was bootstrapped; the evidence below is
fresh command output from that day, not a recollection.

## Accomplishments

- `.gitignore`/`.dockerignore` exclude `orig/`, `third_party/`, `asm/`, `build/`, `.env*`, executables, disc images; GSD's generated files under `.claude/` are ignored, `.planning/` is not.
- Seven plugins enabled and installed at project scope; GSD 1.18.0 project-local, Claude Code only.
- `CLAUDE.md` (46 lines) plus `.claude/rules/{src,tools,workflow}.md`.
- Docs skeleton, README, `.recomp.json`, design spec, research notes, `tools/LICENSE` (GPLv3).

## Evidence (2026-10-19)

- Hygiene scan: `tracked files: 94 controls: ok` / `HYGIENE OK: no game file, .env or key in git ls-files`.
- Plugins: `7/7 enabled plugins installed at project scope for this repo` (superpowers 7.0.0 is also installed at user scope; harmless duplicate).
- `validate.health`: `"status": "healthy"`, no errors, no warnings.
- `wc -l CLAUDE.md`: 46.

## Deviations

- The roadmap's original gate text says `/plugin` clean; it is checked with `claude plugin list --json` scoped to this repo.

## Next Phase Readiness

Phase 2 (container and target ingest) builds on these rules.
