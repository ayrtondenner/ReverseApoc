---
phase: 06-reporting-and-agent-pilot
plan: 12
subsystem: guardrails
tags: [hooks, claude-code, pretooluse, d-12, configure, python]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-03: configure.normalize_source/_NOT_CODE/_blank/_logical_lines (continuation, trigraph, CRLF handling; a lone CR raises _UnreadableSource); 06-07: the only authorized watcom.toml edit is done; 06-09: one project-header set"
provides:
  - "tools/reverseapoc/hooks.py: Decision, decide, main, asm_problem, matching_write_allowed, bash_allowed, attempt_form_matches, ATTEMPT_PREFIX, ATTEMPT_FORMS, ATTEMPT_NAME, ATTEMPT_NAME_SLOT"
  - ".claude/settings.json: the always-on PreToolUse handler (every session in the repo)"
  - "config/driver/claude-settings.json: matching-session settings (matching handler, always handler copy, plugins off)"
affects: [06-15 attempt wrapper (reuses attempt_form_matches/ATTEMPT_FORMS), 06-23 driver audit (reuses matching_write_allowed), 06-25 canary, every later executor (Write/Edit under build/ is denied)]

actuals:
  tokens: 13978  # chars/4 over git diff 325c606..1c1a616 (55,911 chars), SUMMARY excluded
  tasks: 3
  commits: 6  # git rev-list --count 325c606..1c1a616, before this SUMMARY commit
plan_head_before: 325c6066b67916ec70c794d79ebfabfcea2178c1
plan_head_after: 1c1a61697e3a8a33d4c0eb6a4d2b58bf03d3ef01

tech-stack:
  added: []
  patterns:
    - "Pure decide(payload, *, layer, env, tracked) plus a thin main that exits only 0 or 2 (fail closed)"
    - "Every path is judged in all its forms (lexical and host-real); a rule that denies any form denies the call, an allowlist must allow every form"
    - "C text in src/ and include/ is read only through configure's scanner (cfg._NOT_CODE.sub(cfg._blank, text) + cfg._logical_lines), loaded lazily through check._configure"

key-files:
  created:
    - tools/reverseapoc/hooks.py
    - tests/test_hooks.py
    - config/driver/claude-settings.json
  modified:
    - .claude/settings.json

key-decisions:
  - "decide returns Decision(deny=False) for no opinion; main prints nothing then, so no layer ever emits an allow"
  - "The always layer scans every logical line of the blanked, spliced text, directives and #if 0 branches included (configure.code_text's _live_code would refuse include guards and drop directives, so it is not used)"
  - "Matching-layer Bash: the command must consist only of [A-Za-z0-9_ -] (the wrapper forms' own characters), a strict superset of the D-44 metacharacter refusal, then shlex.split must equal ATTEMPT_PREFIX + one ATTEMPT_FORMS entry"
  - "attempt_form_matches takes the arguments after ATTEMPT_PREFIX, so the 06-15 wrapper can pass its own argv"
  - "The always handler carries no timeout or onFailure key and is copied byte-identical into the driver file; the matching handler has timeout 120 and onFailure block"

patterns-established:
  - "From this plan's merge on, write under build/ only by shell redirection or by the program's own writes (rulings R-B); the Write/Edit tools are denied there"

requirements-completed: [AGT-05]

coverage:
  - id: D1
    description: "Always-on hook denies Write/Edit/MultiEdit/NotebookEdit under orig/, asm/, build/, of config/targets.toml, config/watcom.toml and any *.sha1, in Windows, POSIX, .., upper-case, trailing-dot, ::$DATA and worktree forms; near misses and tools/, tests/, configure.py, docs/, .planning/ stay editable"
    requirement: "AGT-05"
    verification:
      - kind: unit
        ref: "tests/test_hooks.py#test_always_denies_a_write_under_orig, test_always_denies_protected_files, test_always_allows_near_miss_paths, test_always_allows_a_tools_edit, test_always_ignores_paths_outside_the_repo, test_worktree_root_is_found"
        status: pass
    human_judgment: false
  - id: D2
    description: "The single REVERSEAPOC_ATTEMPT_NOTES exemption: only under build/driver/ and named notes.md (D-46)"
    requirement: "AGT-05"
    verification:
      - kind: unit
        ref: "tests/test_hooks.py#test_always_allows_the_attempt_notes, test_always_resolves_relative_notes_against_the_payload_cwd, test_matching_allows_the_attempt_notes"
        status: pass
    human_judgment: false
  - id: D3
    description: "Inline asm (_asm, __asm, _Pragma, code-emitting #pragma aux) in src/ and include/ is denied on the post-edit text read through configure's scanner, including the 06-03 splice/trigraph/CRLF probes; a lone CR is refused; asm words in comments and strings, calling-convention pragmas and the committed headers and units pass"
    requirement: "AGT-05"
    verification:
      - kind: unit
        ref: "tests/test_hooks.py#test_always_denies_inline_asm_in_src, test_always_denies_lone_cr_naming_the_reason, test_always_denies_an_edit_that_completes_asm, test_always_allows_asm_words_in_comments_and_strings, test_always_allows_the_committed_headers_and_units"
        status: pass
    human_judgment: false
  - id: D4
    description: "Matching layer denies by default: claimed unit, new untracked include/*.h and notes only; no #pragma aux at all; reads in the repo and never .env*; Bash only as an exact wrapper form; every other tool denied; no claim denies writes and Bash"
    requirement: "AGT-05"
    verification:
      - kind: unit
        ref: "tests/test_hooks.py#test_matching_allows_only_the_claimed_unit, test_matching_include_rules, test_matching_denies_every_pragma_aux, test_attempt_forms_are_the_shared_constants, test_matching_bash_allows_exact_wrapper_forms, test_matching_bash_denies_everything_else, test_matching_reads_stay_in_the_repo, test_matching_denies_other_tools, test_matching_without_a_claim_denies_writes_and_bash, test_matching_write_allowed_is_the_one_allowlist, test_main_tracks_headers_with_git"
        status: pass
    human_judgment: false
  - id: D5
    description: "Real entry point end to end in a subprocess, both layers: deny JSON with exit 0, nothing with exit 0, exit 2 on malformed payloads"
    requirement: "AGT-05"
    verification:
      - kind: integration
        ref: "tests/test_hooks.py#test_entry_point_end_to_end, test_matching_entry_point_end_to_end"
        status: pass
    human_judgment: false
  - id: D6
    description: "Settings files: .claude/settings.json keeps its plugins and marketplaces and gains one always handler; config/driver/claude-settings.json has the matching handler, the identical always handler, all plugins off, autoMemoryEnabled false, disableClaudeAiConnectors true, no mcpServers/disableAllHooks"
    requirement: "AGT-05"
    verification:
      - kind: unit
        ref: "tests/test_hooks.py#test_project_settings_wire_the_always_layer, test_driver_settings_shape"
        status: pass
      - kind: other
        ref: "the plan's Task 3 python -c settings assertion"
        status: pass
    human_judgment: false
  - id: D7
    description: "Whether Claude Code really runs both handlers in a --settings matching session and honours the denials (research A1; MultiEdit/NotebookEdit field names, A5)"
    requirement: "AGT-05"
    verification: []
    human_judgment: true
    rationale: "Needs a real claude session; the owner's 06-25 canary proves it. Executors may not run claude -p."

duration: 21min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 12: Guardrail hooks Summary

**A stdlib `reverseapoc.hooks` module with a pure `decide` and a fail-closed entry point: an always-on layer in `.claude/settings.json` that keeps every session off orig/, asm/, build/, the hash manifests and inline asm in src/ and include/ (read through configure's D-12 scanner), and a deny-by-default matching layer in `config/driver/claude-settings.json` that lets a session edit only its claimed unit, read only the repo and run only the exact attempt-wrapper argv forms.**

Execution context nonce: 1fa04791bdedc648

## Performance

- **Duration:** about 21 min
- **Started:** 2026-10-25T04:07Z (approximate; the base commit is 04:06:43Z)
- **Completed:** 2026-10-25T04:28Z
- **Tasks:** 3 (each a RED test commit, then a GREEN commit)
- **Files:** 4 (3 created, 1 modified)

## Accomplishments

- `decide(payload, *, layer, env, tracked) -> Decision` and `main(argv)`, run as `uv run --frozen python -I -m reverseapoc.hooks pre-tool-use --layer always|matching`. A deny prints the `hookSpecificOutput` JSON and exits 0. No opinion prints nothing and exits 0. Any exception, an unreadable payload, an argparse error and even `SystemExit` exit 2 with the reason on stderr. `main` never returns another code.
- Path handling, in `canonical` and `candidates`:
  - Windows and POSIX forms, `..`, and casefold comparison.
  - NTFS forms: `\\?\` and `\\.\` prefixes, a trailing dot or space, `name::$DATA` streams.
  - The host realpath (symlinks, 8.3 names) is judged as well.
  - The checkout is the nearest ancestor holding `.git`, a directory or a worktree file. A path under `.claude/worktrees/<name>/` is also judged relative to that worktree, even when its `.git` is missing.
- Always layer (D-16, D-46):
  - Denies orig/, asm/, build/, config/targets.toml, config/watcom.toml and `*.sha1`.
  - Exempts only the `REVERSEAPOC_ATTEMPT_NOTES` path, and only when it lies under build/driver/ and is named notes.md.
  - For src/ and include/, it builds the post-edit text (Write content; Edit and MultiEdit applied to the current file, CRLF tolerated) and scans it with `cfg._NOT_CODE.sub(cfg._blank, ...)` plus `cfg._logical_lines`, so phases 1-2 and continuation splices apply.
  - Denied tokens: `\b_{1,2}asm\b`, `\b_Pragma\b`, and `#pragma aux` with `=` in the body.
  - configure is loaded lazily through `check._configure()`, so other edits never import it.
- Matching layer (D-17, D-18, D-44, D-45, DI-07):
  - Deny by default. The always rules run first.
  - Writes go only through `matching_write_allowed`, and no `#pragma aux` of any kind is allowed.
  - Read, Glob and Grep must stay inside the session's checkout, with no `~`, no `..` or absolute patterns and no `.env*`.
  - Bash is checked by `bash_allowed`.
  - Every other tool is denied. With no valid `REVERSEAPOC_CLAIM`, every write and every Bash call is denied.
  - `main`'s `tracked` asks `git ls-files -z --full-name -- :(top,icase)<dir>` and compares casefolded. A git failure blocks.
- Settings:
  - `.claude/settings.json` gains one PreToolUse handler and no `onFailure` key.
  - `config/driver/claude-settings.json` holds the always handler (byte-identical, Pitfall 3) and the matching handler (matcher `*`, timeout 120, `onFailure: block`). It sets all 7 plugins to false, `autoMemoryEnabled: false` and `disableClaudeAiConnectors: true`, with no `mcpServers` and no `disableAllHooks`.

## Task Commits

1. **Task 1 (tracer): orig/ write denied end to end.** RED `1c63e94`, GREEN `566dc0f`. Tracer gate: interactive, end-of-phase, automated verify only. I re-ran `uv run pytest -q tests/test_hooks.py` (4 passed) and expanded.
2. **Task 2: the full always-on layer.** RED `b28c4d8`, GREEN `148abec`.
3. **Task 3: the matching layer and the driver settings file.** RED `a53ebcc`, GREEN `1c1a616`.

The plan is `type: execute`, so the plan-level TDD gate does not apply. Every tdd task still has its RED test commit before its GREEN commit.

## RED evidence (semantic assessment)

- Task 1: collection failed with `ImportError: cannot import name 'hooks' from 'reverseapoc'`. The module did not exist yet, so all four tests failed for the planned reason, not for a fixture or syntax fault.
- Task 2: 45 targets failed, all on assertions. Each protected file, the notes exemption, every asm probe, the lone CR, the notebook case and the worktree build/ case returned no denial. orig/ (built in Task 1) and the allow cases passed, as expected.
- Task 3: 66 failed. 61 were `HookError: unknown layer 'matching'`, 2 were `AttributeError` for `ATTEMPT_PREFIX` and `matching_write_allowed`, 1 was the `_git_tracked` placeholder, 1 was the end-to-end run (exit 2 on the unknown layer), and 1 was `FileNotFoundError` for the driver settings file. All of them are the planned features missing.

## Verification

- `uv run pytest -q tests/test_hooks.py`: 137 passed.
- `uv run pytest -q tests/test_hooks.py -k always`: 69 passed, 2 deselected (Task 2 verify; exit 0).
- `uv run pytest -q`: 1735 passed, 217 skipped. The skips are real-file and platform skips that already existed; test_hooks.py skips nothing.
- `uv run ruff check .`: all checks passed. `ruff format --check` is clean on both new Python files.
- The plan's Task 3 settings assertion (`python -c "import json; ..."`) exits 0.
- The real command `uv run --frozen python -I -m reverseapoc.hooks pre-tool-use --layer always`, fed a src/ Write holding `_asm`, printed the deny JSON with exit 0 in about 0.36 s, configure load included.
- Acceptance greps: `def decide(`, `def main(`, `def matching_write_allowed(`, the literal `ATTEMPT_PREFIX = ("uv", "run", "--frozen", "reverseapoc", "attempt")` and `cfg._NOT_CODE` are in hooks.py. The driver file holds `"onFailure": "block"` and `"--layer matching"`. `.claude/settings.json` holds `"pre-tool-use --layer always"`.

## Files Created/Modified

- `tools/reverseapoc/hooks.py` (new, GPL-3.0-or-later SPDX header): both layers, the shared allowlist and the wrapper-form constants, and the entry point.
- `tests/test_hooks.py` (new): decision tests with synthetic payloads in a scratch checkout, two subprocess end-to-end runs (one per layer) and the shapes of both settings files.
- `.claude/settings.json`: the `hooks.PreToolUse` always handler. The existing keys are unchanged.
- `config/driver/claude-settings.json` (new): the matching-session settings.

## Decisions Made

See key-decisions in the frontmatter.

## Deviations from Plan

- **Orchestrator ruling (## 06-12, notes on what 06-03 built): C text is read only through configure's scanner.** hooks.py calls `cfg._NOT_CODE.sub(cfg._blank, text)`, which runs `normalize_source` first, then `cfg._logical_lines`. It never runs a regex on raw tool-input text. `configure.code_text` itself is not used: its `_live_code` refuses every conditional other than `#if 0` (so every include guard, as in common.h) and blanks directive lines, where `#pragma aux` lives. A lone CR raises `_UnreadableSource`, which hooks.py turns into a deny naming the line (`test_always_denies_lone_cr_naming_the_reason`, and the `lone-cr` case for both layers). The 06-03 probes that hide `_asm` behind a backslash-blank splice, a backslash-CRLF splice and a `??/` trigraph (INLINE_ASM_PROBES in tests/test_configure.py, copied as `CONTINUATION_ASM_PROBES`) are all denied, in src/ and in include/, through Write, Edit and MultiEdit.
- **Orchestrator ruling F16: inline-asm token matching.** The tokens are matched case-sensitively on the blanked, spliced code (`\b_{1,2}asm\b`, `\b_Pragma\b`, `#pragma aux` with `=` in the body). Only paths are casefolded. Tests:
  - the scaffolded unit is allowed by both layers;
  - an Edit of include/common.h that keeps its `#define INCLUDE_ASM(name) extern int INCLUDE_ASM_##name` is allowed by the always layer, and so are whole-file Writes of the committed common.h, watcom_compat.h and both matched units;
  - the near-miss paths `asm.md`, `buildx/x`, `orig_notes.md` and `tools/reverseapoc/asm.py` (and a few more) are allowed.
- **Orchestrator ruling F27: ATTEMPT_FORMS shape.**
  - `ATTEMPT_FORMS` is the tuple of argv tuples after `ATTEMPT_PREFIX`: `("check",)`, `("check", "--sweep")`, `("asm",)`, `("asm", "<NAME>")`, `("context",)`. `"<NAME>"` is the constant `ATTEMPT_NAME_SLOT`.
  - `ATTEMPT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")` is matched with fullmatch.
  - `attempt_form_matches(argv)` takes the arguments after the prefix and requires equal length and equal tokens, with `<NAME>` matched by ATTEMPT_NAME. 06-15's wrapper and test_skill should reuse it with their own argv.
- **Orchestrator ruling F32 (record only).** The always layer fails open if `uv` is missing or `reverseapoc.hooks` cannot be imported: the command then exits 1, which Claude Code treats as non-blocking. D-15 locks the command. The matching handler has `onFailure: block`. Inside the module, every failure exits 2.
- **Rulings R-A and R-B.** test_hooks.py has no skip; a test that needs a platform's path form picks it by `sys.platform` inside one test. **From this plan's merge on, the Write and Edit tools are denied under build/ for every Claude session in this repo (the orchestrator's included). Later executors write evidence under build/ by shell redirection or by the program's own writes.**

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] NTFS path aliases**
- **Found during:** Task 1
- **Issue:** On NTFS, `orig.\x`, `config\targets.toml::$DATA` and `\\?\C:\...` open the protected files, while a plain normpath and casefold would not see them.
- **Fix:** In Windows form, `canonical` strips device prefixes, stream suffixes and trailing dots and spaces. The host realpath is judged too (8.3 names, symlinks).
- **Files modified:** tools/reverseapoc/hooks.py
- **Verification:** `_forms` in test_hooks.py adds the trailing-dot and `::$DATA` forms on Windows.
- **Committed in:** `566dc0f`

**2. [Rule 2 - Missing critical] A worktree whose `.git` is missing**
- **Found during:** Task 2
- **Issue:** Nearest-`.git` detection alone judges a `.claude/worktrees/<name>/orig/x` path as `.claude/...` once that worktree's `.git` file is gone.
- **Fix:** `_repo_forms` also yields the path relative to the worktree directory.
- **Files modified:** tools/reverseapoc/hooks.py
- **Verification:** `test_worktree_root_is_found` (the `agent-gone` case).
- **Committed in:** `148abec`

**3. [Rule 2 - Missing critical] Reads and patterns that escape the repo**
- **Found during:** Task 3
- **Issue:** A Read of a literal `~/...` path would resolve inside the repo as a relative path. A Glob pattern can be absolute or climb with `..`. A Grep `glob` can name `.env`.
- **Fix:** The matching layer denies a raw path starting with `~`, absolute or `..` patterns, and patterns naming `.env*`.
- **Files modified:** tools/reverseapoc/hooks.py
- **Verification:** `test_matching_reads_stay_in_the_repo`
- **Committed in:** `1c1a616`

**4. [Rule 2 - Missing critical] Case-insensitive "tracked" check**
- **Found during:** Task 3
- **Issue:** On NTFS, `include/COMMON.H` or a differently-cased tracked header would pass a case-sensitive `git ls-files --error-unmatch`.
- **Fix:** `main`'s `tracked` lists the directory with `git ls-files -z --full-name -- :(top,icase)<dir>` and compares casefolded. The reserved header names are compared casefolded too.
- **Files modified:** tools/reverseapoc/hooks.py
- **Verification:** `test_main_tracks_headers_with_git`, `test_matching_include_rules`
- **Committed in:** `1c1a616`

---

**Total deviations:** 3 rulings applied as plan text (06-03 notes, F16, F27), 1 recorded (F32), R-A and R-B honoured, and 4 auto-fixes (Rule 2). **Impact:** all are hardening inside the planned files. There is no new surface, configure.py and check.py are untouched, and `files_modified` is exactly the plan's four files.

## Known limitations (not stubs)

- Research A1: whether hooks in a `--settings` file merge with or replace project hooks is unknown. The driver file carries the always handler and the matching layer re-applies the always rules, so the matching layer does not depend on merging. Plan 06-25's canary (run by the owner) proves the denials.
- A5: the MultiEdit (`edits[]`) and NotebookEdit (`notebook_path`, `new_source`) field names are assumed. An unknown shape is a HookError (exit 2) in both layers, and NotebookEdit is denied in src/, in include/ and in every matching session.
- A6: the token set is `_asm`, `__asm`, `_Pragma` and `#pragma aux ... =`. Asm assembled by token pasting (`_as ## m`) is not detected; it still cannot pass `check` unless it really matches. `_asm` inside `#if 0` is denied (conservative).
- An Edit whose `old_string` cannot be placed on the current file (the tool will fail) is judged on the current file and each `new_string` alone. Out of context this can over-deny, never under-deny.
- Grep without a `path` searches from the session cwd. ripgrep skips hidden and gitignored files such as `.env` by default; an explicit `.env` path or glob is denied.

## Issues Encountered

- The harness refuses Bash commands whose text contains "git" in complex forms (the main-checkout path contains "Gitprojects"). I ran those steps with plain commands or the Edit tool instead.
- After Task 1's GREEN commit the always hook was live for this worktree session too. My own edits to tools/ and tests/ went through, which is evidence that the layer does not block normal work.

## Next Phase Readiness

- 06-15: import `ATTEMPT_PREFIX`, `ATTEMPT_FORMS`, `ATTEMPT_NAME_SLOT` and `attempt_form_matches` from `reverseapoc.hooks`. The skill quotes `uv run --frozen reverseapoc attempt asm <NAME>` literally.
- 06-23: the post-attempt audit calls `hooks.matching_write_allowed(rel, claim=..., notes=<repo-relative notes path>, tracked=...)` on each `git status --porcelain` path.
- 06-25: the canary should show a denied `ls`, a denied write outside the claim and an allowed wrapper call.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/hooks.py, tests/test_hooks.py, config/driver/claude-settings.json, .claude/settings.json
- FOUND commits (ancestors of HEAD): 1c63e94, 566dc0f, b28c4d8, 148abec, a53ebcc, 1c1a616

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
