---
phase: 01-hygiene-and-safety
verified: 2026-10-19T23:17:35Z
status: passed
score: 6/6 must-haves verified
covered_files: [".claude/rules/src.md", ".claude/rules/tools.md", ".claude/rules/workflow.md", ".claude/settings.json", ".dockerignore", ".env.example", ".gitignore", ".mcp.json", ".planning/phases/01-hygiene-and-safety/01-01-PLAN.md", ".planning/phases/01-hygiene-and-safety/01-01-SUMMARY.md", ".planning/phases/01-hygiene-and-safety/01-02-PLAN.md", ".planning/phases/01-hygiene-and-safety/01-02-SUMMARY.md", ".recomp.json", "CLAUDE.md", "README.md", "compose.yaml", "docker/Dockerfile", "docker/README.md", "docker/compose.yaml", "docs/ceremonies.md", "docs/coding-style.md", "docs/learnings.md", "docs/legal.md", "docs/matching.md", "docs/superpowers/specs/2026-10-19-reverseapoc-design.md", "docs/toolchain.md", "docs/tools.md", "docs/workflow.md", "tests/test_hygiene.py", "tools/LICENSE"]
covered_digest: "v3:sha256:d0c26253d611dd83a7b9c071e33bc794b56980a477dffff04b31675259c719a3"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 6/6
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 1: Hygiene and safety Verification Report

**Phase Goal:** The repository is safe to publish and to run agents in: no game file, disassembly, build output or secret is tracked, every enabled plugin and GSD are installed at project scope for Claude Code only, CLAUDE.md is lean and states the hard rules, and the docs skeleton exists.
**Verified:** 2026-10-19T23:17:35Z
**Status:** passed
**Re-verification:** Yes, round 3. This round refreshes a stale report after wording-only changes: commit `5422eba` (removes the renumbering note from `docs/workflow.md`, rewords two research notes, adds `test_no_doc_mentions_a_phase_zero`) and uncommitted `.planning/` edits, including `01-01-PLAN.md` and `01-01-SUMMARY.md`.

I ran every check below myself in this round. Nothing comes from either SUMMARY. I never read bytes from `orig/` or `third_party/`.

## Goal Achievement

### Observable Truths

The must-haves are the same as last round: the four ROADMAP success criteria, with SC1 split into its `.gitignore` half and its `.dockerignore` half, plus the two 01-02 truths. The 01-02 `.dockerignore` truth restates SC1b, so I merged it into SC1b. The 01-01 truths restate SC1-SC4.

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1a | `git ls-files` lists no game file, disassembly, build output, compiler binary, `.env` or API key; `.gitignore` excludes `orig/`, `third_party/`, `asm/`, `build/`, `.env` (SC1, HYG-01) | VERIFIED | `hygiene.mjs`: `tracked files: 104 controls: ok` / `HYGIENE OK: no game file, .env or key in git ls-files`, exit 0. The 104 tracked paths, grouped by top-level directory, include none of `orig/ asm/ build/ third_party/ watcom/`. A grep of `git ls-files` for `.exe/.iso/.bin/.img/.cue/.mdf/.dll/.lib/.obj/.o/.smk/.zip` or a tracked `.env` finds nothing (exit 1). `git diff --numstat <empty-tree> HEAD` lists 0 binary files. `git check-ignore -v` matches all 8 probes: `orig/` (.gitignore:2), `third_party/` (:3), `asm/` (:4), `build/` (:5), `.env` (:21), `sub/GAME.EXE` (:14), `disc.iso` (:16), `watcom/` (:6). |
| 1b | `.dockerignore` excludes the same paths and the executable/image types (SC1, HYG-01; 01-02 truth 1) | VERIFIED | I read `.dockerignore`. It has `.git/ orig/ third_party/ asm/ build/ .env .env.* !.env.example`, plus `**/*.exe **/*.EXE **/*.iso **/*.ISO **/*.bin **/*.BIN **/*.img **/*.cue`. It last changed in `fa9c1a0`. The parametrized cases in `tests/test_hygiene.py` pass as part of the full run. Root `compose.yaml` only `include:`s `docker/compose.yaml`. |
| 2  | Every plugin enabled in `.claude/settings.json` is installed at project scope; `/gsd-health` is clean for a project-local GSD install that targets Claude Code only (SC2, HYG-02) | VERIFIED | `plugins.mjs` lists 7 plugins, each `project ... enabled`, then `7/7 enabled plugins installed at project scope for this repo`, exit 0. `validate.health` gives `"status": "healthy"`, with errors, warnings and info all empty and `repairable_count: 0`, exit 0. Its only stderr line is the note about the global `~/.gsd/defaults.json`. None of `.agents .codex .cursor .windsurf .gemini AGENTS.md GEMINI.md` exists at the repo root. |
| 3  | `wc -l CLAUDE.md` < 150; it states the hard rules, commands and done gate; per-path rules are in `.claude/rules/` (SC3, HYG-03) | VERIFIED | `46 CLAUDE.md`. All three `## Hard rules / Commands / Done gate` headings are present (count 3). `.claude/rules/` holds `src.md`, `tools.md` and `workflow.md`. |
| 4  | The docs skeleton, README, `.recomp.json` and the approved design spec exist (SC4, HYG-04) | VERIFIED | All 8 docs exist: toolchain 174, coding-style 89, matching 48, learnings 25, tools 99, legal 43, workflow 94 (was 96 before `5422eba` removed the two-line note), ceremonies 60. README is 165 lines. `.recomp.json` (55 lines) parses as JSON. Line 4 of the spec reads `**Status:** approved plan for Milestone 1; Phases 1-2 detailed, Phases 3-6 planned later with GSD.` The roadmap table in `docs/workflow.md` (lines 83-85 on) is intact after the edit. |
| 5  | No live doc (outside docs/research/) carries a bare TBD marker; unknowns name the requirement or phase that settles them (01-02 truth 2; debt-marker gate) | VERIFIED | `git grep -n TBD -- docs README.md CLAUDE.md ':!docs/research'` prints nothing (exit 1). `uv run pytest -q tests/test_hygiene.py -k "tbd or phase_zero"` gives `2 passed, 15 deselected`, exit 0. Last round showed the TBD oracle has teeth: it fails on `d2bf040^`, which has 14 hits. A wider case-insensitive scan for `TBD/FIXME/XXX/to be determined/TODO/HACK` over the same scope finds only false positives (see Anti-Patterns). |

**Score:** 6/6 truths verified (0 present but behavior-unverified). None of the truths depends on runtime state. Each is a static property of the tracked tree, the config files or the docs, and each is backed by a command run this round. Truths 1b and 5 are also backed by passing pin tests.

### What the wording change touched

- `docs/workflow.md` (`5422eba`): only the two-line renumbering note above the roadmap table was removed. Nothing a truth depends on changed.
- `tests/test_hygiene.py` (`5422eba`): adds `test_no_doc_mentions_a_phase_zero`. It scans `docs/`, `.planning/`, `README.md` and `CLAUDE.md` for `\bphases? 0\b` or a `| 0. ` table row. It passes now. On `5422eba^`, a `git grep` with the same regex over the tracked tree finds 12 hits, so the test is not vacuous. No truth depends on it. It guards the owner's wording decision.
- `01-01-PLAN.md` / `01-01-SUMMARY.md` (uncommitted): the retroactive notes now cite commits `d7d4d65`…`e50784f` and no longer use the old phase number. The must-haves are unchanged (5 truths, 8 artifacts, 2 key links), so the scope I verify did not shrink.
- `.planning/ROADMAP.md` (uncommitted): the numbering banner and the old-label notes are gone. The Phase 1 goal and its four success criteria are unchanged.

### Deferred Items

None.

### Advisory (New Scope, Unevidenced)

None. I found no new-scope blocker this round.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.gitignore` | game/build/secret/GSD exclusions | VERIFIED | All 8 `check-ignore` probes hit |
| `.dockerignore` | same paths, plus exe/image types at any depth | VERIFIED | 8 `**/` patterns, the dirs and the `.env` rules |
| `tests/test_hygiene.py` | pins the `.dockerignore` patterns, the read-only mounts, the live-doc TBD scan and the phase-zero scan | VERIFIED | 97 lines, 17 cases. The default `uv run pytest -q` collects it. |
| `CLAUDE.md` | lean; hard rules, commands, done gate | VERIFIED | 46 lines |
| `.claude/settings.json` | 7 enabled plugins | VERIFIED | 7/7 at project scope |
| `.claude/rules/` | per-path rules | VERIFIED | src.md, tools.md, workflow.md |
| `docs/*.md` (8) + README + spec | docs skeleton | VERIFIED | All present, and the spec is approved |
| `.recomp.json` | recomp.fyi metadata | VERIFIED | Valid JSON |

As last round, the plans list artifacts and key links as bare strings, not `{path, ...}` objects, so `verify.artifacts` and `verify.key-links` cannot evaluate them. I checked both lists by hand.

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| tests/test_hygiene.py | .dockerignore | `_ignore_patterns(REPO_ROOT / ".dockerignore")` + exact-string assert per extension and protected dir | WIRED | Cases pass in the full run |
| tests/test_hygiene.py::test_live_docs_carry_no_bare_tbd_markers | docs/ (minus research/), README.md, CLAUDE.md | `_live_docs()` rglob + `\bTBD\b` per line | WIRED | Passes now. It would fail on `d2bf040^` (14 hits). |
| compose.yaml | docker/compose.yaml | `include:` | WIRED | So the mount pins cover the compose file used from the repo root |
| CLAUDE.md | docs/workflow.md, docs/toolchain.md, docs/tools.md | "Where to read more" (line 39 on) and the Workflow section | WIRED | The targets exist |
| .gitignore | orig/, third_party/, asm/, build/, .env, executables, disc images | ignore rules | WIRED | All 8 `check-ignore` probes |

### Data-Flow Trace (Level 4)

Not applicable, because this phase is configuration and documentation only.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Tracked tree is free of game bytes and keys | `node <scratchpad>/hygiene.mjs` | `tracked files: 104 controls: ok`, `HYGIENE OK`, exit 0 | PASS |
| Plugins at project scope | `node <scratchpad>/plugins.mjs` | `7/7 enabled plugins installed at project scope for this repo`, exit 0 | PASS |
| GSD healthy | `node .claude/gsd-core/bin/gsd-tools.cjs query validate.health` | `"status": "healthy"`, all lists empty, exit 0 | PASS |
| CLAUDE.md is lean | `wc -l CLAUDE.md` | `46` | PASS |
| No bare TBD in live docs | `git grep -n TBD -- docs README.md CLAUDE.md ':!docs/research'` | no output, exit 1 | PASS |
| TBD and phase-zero oracles | `uv run pytest -q tests/test_hygiene.py -k "tbd or phase_zero"` | `2 passed, 15 deselected`, exit 0 | PASS |
| Full suite and lint (run once) | `uv run pytest -q`; `uv run ruff check .` | `89 passed, 3 skipped`; `All checks passed!` (exit 0) | PASS |

The 3 skips are container-only cases (`test_protected_paths_are_not_writable_in_the_container`). I did not re-run the container suite. The pass count went from 88 to 89 because of the new phase-zero test.

### Probe Execution

No `scripts/*/tests/probe-*.sh` exists and none is declared, so this does not apply.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| HYG-01 | 01-01, 01-02 | git ls-files is clean; .gitignore/.dockerignore exclude the dirs, .env and exe/image types | SATISFIED | Truths 1a, 1b |
| HYG-02 | 01-01 | Plugins at project scope; GSD project-local, Claude Code only, health clean | SATISFIED | Truth 2 |
| HYG-03 | 01-01 | CLAUDE.md < 150 lines with hard rules, commands, done gate; `.claude/rules/` | SATISFIED | Truth 3 |
| HYG-04 | 01-01, 01-02 | Docs skeleton, README, .recomp.json, approved design spec | SATISFIED | Truths 4, 5 |

The plans declare all 4 IDs, and REQUIREMENTS.md maps each of them to Phase 1 (lines 112-115). REQUIREMENTS.md maps no other ID to Phase 1, so there are no orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| tests/test_hygiene.py | 68, 73 | `TBD` | Info (false positive) | This is the oracle's own comment and regex |
| docs/coding-style.md | 34-36 | `XXXXXXXX` | Info (false positive) | Naming templates |
| docs/toolchain.md | 55 | `FUN_000xxxxx`, `0x0016xxxx` | Info (false positive) | Ghidra address templates matched by the case-insensitive `XXX` scan |
| docs/superpowers/specs/...design.md | 105 | `Watcom` | Info (false positive) | Matched by the case-insensitive `TBD/...` scan |
| .planning/ROADMAP.md | Phase 1 block | `**Plans**: TBD` | Info | This is a GSD roadmap template field in `.planning/`, outside the live-doc scope of truth 5 |
| docs/toolchain.md | 13 | SMKP entry point `obj1:0x6CB0` | Info | Carried over. I could not check it without reading `orig/`. |
| .dockerignore | n/a | No `**/*.IMG`, `**/*.CUE`, `**/*.mdf`/`*.MDF` (`.gitignore` has them) | Info | Carried over. `docker/Dockerfile` copies nothing from the build context. |
| plugins.mjs output | n/a | `superpowers` is also installed at user scope (7.0.0) | Info | HYG-02 needs project scope, and that holds |
| git history | `d7d4d65` | Commit subject uses the pre-GSD label | Info | Commit messages are history. The phase-zero test scans working-tree docs only, and that is the right scope. |
| README.md | 14 | "Placeholder ... coming in Phase 6" | Info | RPT-02/03 |

There are no debt-marker blockers. I found no new-scope blocker, so the #3304 evidence gate has nothing to act on.

### Human Verification Required

None from this verifier. Every truth was checked by a command run this round, and no PLAN has a `<human-check>` block. Separately, `01-UAT.md` (`status: testing`) has owner test 1 pending: the docs are coherent with PROJECT.md and use Phases 1-6. That is the owner-judgement item from `01-01-SUMMARY.md` D5 (`human_judgment: true`). It goes beyond the existence criterion SC4, and the UAT session already tracks it.

### Gaps Summary

There are no gaps. The changes that made the report stale are wording only. The renumbering note left `docs/workflow.md`, and a new test pins its absence across `docs/`, `.planning/`, `README.md` and `CLAUDE.md`. That test passes now and would fail on the previous tree (12 hits). Every success criterion still holds on fresh evidence: 104 tracked files are clean, the 8 ignore probes hit, `.dockerignore` has all patterns, 7/7 plugins are installed at project scope, GSD is healthy, CLAUDE.md is 46 lines with all three required sections, the docs skeleton is complete, and no live doc has a bare TBD. Tests (89 passed, 3 container-only skips) and ruff are green. The phase goal is achieved.

---

_Verified: 2026-10-19T23:17:35Z_
_Verifier: Claude (gsd-verifier)_
