---
status: testing
phase: 01-hygiene-and-safety
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md]
started: 2026-10-19T23:08:35Z
updated: 2026-10-19T23:08:35Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 1
name: Docs skeleton, README, .recomp.json and design spec are coherent
expected: |
  Skim CLAUDE.md, README.md, docs/workflow.md (Milestone 1 roadmap, Phases 1-6), docs/toolchain.md,
  docs/tools.md, docs/legal.md and the design spec. They say what you decided: hard rules, bring-your-own
  files, GPLv3 tools/, Claude Code only, GSD for phases + superpowers inside them, the six phases with their
  gates. Nothing contradicts .planning/PROJECT.md, and every doc (research notes included) uses the
  phase numbers 1-6 with no reference to any earlier numbering. The 6 automated items below (no game files/keys tracked, 7/7 plugins at project scope,
  GSD healthy, CLAUDE.md 46 lines, .dockerignore patterns, no bare TBD) match what you expect.
awaiting: user response

## Tests

### 1. Docs skeleton, README, .recomp.json and design spec are coherent
expected: The docs state the owner's decisions consistently with PROJECT.md and Phases 1-6, with no earlier numbering anywhere; the automated items 2-7 are confirmed by the owner
result: [pending]

### 2. git ls-files contains no game file, disassembly, build output, compiler binary, .env or API key
expected: git ls-files contains no game file, disassembly, build output, compiler binary, .env or API key
result: pass
source: automated
coverage_id: D1

### 3. All seven enabled plugins installed at project scope for this repo
expected: All seven enabled plugins installed at project scope for this repo
result: pass
source: automated
coverage_id: D2

### 4. GSD installed project-local and /gsd-health healthy (no W028 shadowing)
expected: GSD installed project-local and /gsd-health healthy (no W028 shadowing)
result: pass
source: automated
coverage_id: D3

### 5. CLAUDE.md under 150 lines with hard rules, commands, done gate
expected: CLAUDE.md under 150 lines with hard rules, commands, done gate
result: pass
source: automated
coverage_id: D4

### 6. .dockerignore excludes **/*.exe, *.EXE, *.iso, *.ISO, *.bin, *.BIN
expected: .dockerignore excludes **/*.exe, *.EXE, *.iso, *.ISO, *.bin, *.BIN
result: pass
source: automated
coverage_id: D1

### 7. No bare TBD marker in live docs
expected: No bare TBD marker in live docs (stale ones replaced by known values, unknowns name their requirement/phase)
result: pass
source: automated
coverage_id: D2

## Summary

total: 7
passed: 6
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps

[none yet]
