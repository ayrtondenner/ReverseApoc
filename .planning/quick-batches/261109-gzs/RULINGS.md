# Batch 261109-gzs: coordinator rulings and project rules

Every planner and executor of this batch reads this file before anything else. Source: the owner-approved plan of
2026-11-09 (Stage 1) and the 2026-11-07 tooling survey of runs 20261107-170844 and 20261107-030004.

## Order (coordinator ruling)
- 261109-gzv, 261109-gzw and 261109-gzy share files (attempt.py, hooks.py), so they run in that order: gzw depends
  on gzv, gzy depends on gzw. Declare exactly that in depends_on.
- 261109-gzx depends on 261109-gzu: both may touch the session/driver stop and sweep-hit logic, and gzx's skill
  wording must describe the driver behaviour gzu builds.
- 261109-gzt (lift.py) and 261109-gzz (probe/README.md) are independent: depends_on [].
- Later phase work (Phase 07.2) builds on this batch; do not start any 07.2 item (give-up records, plan notes, region
  board, token ledger, model routing) here.

## Scope rulings
- gzt: the lifter only. The measurement (curve point 14) needs orig/ and docker, which worktrees lack: the executor
  builds and unit-tests only; the coordinator runs the curve gate on the main checkout after the merge and writes
  point 14 into .planning/converter-curve/CURVE.md. Never edit .planning/phases/07.1-matching-tooling/.
- gzu: "sweep hit" means a sweep cell that is exact for the claimed function (the existing `check.sweep_hit` /
  `sweep_cells_100` signal in the attempt record). Park = no new session on that function for the rest of the run;
  report it in the night's console line and the run's ENDED totals. Nothing lands from a sweep; flags stay owner-only.
- gzv: output shows mnemonics, operands and addresses of our object and the original around the first difference.
  Never raw game bytes in records, logs that get committed, or tests (tests use synthetic objects/fixtures).
- gzv (coordinator, after plan check): before extracting `_masked()` out of `compare_bytes`, temporarily break the
  mask, show a compare_bytes test fails, restore it, and record that in the SUMMARY (tools.md: a refactor is pinned
  by tests proven to fail on broken code).
- gzt (coordinator, after plan check): tests/test_lift_headers_real.py must run, not skip, in the worktree (Task 1
  and Task 2 alike); the coordinator re-runs the real tests on the main checkout before curve point 14.
- gzw: the cache key must include everything the output depends on (view unit sha, headers, flags rule, tool version)
  so a stale cache is impossible; prove it with a test that changes each input.
  Amendment (coordinator, after planning): the key holds exactly the inputs each output READS. If `cmd_asm` does not
  read the view unit, leave the view unit out of asm's key (a test shows an edit to the view unit still hits, and
  each input asm does read still misses). The examples above were a minimum list for outputs that read them, not a
  requirement to key on unread inputs. Brace globs: accepted in Glob/Grep only, as the plan decided; Bash unchanged.
- gzx: the skill change goes through superpowers:writing-skills with a RED baseline first (a subagent-free baseline is
  fine: show the current text fails the new pressure test, then edit). tests/test_skill.py (sections, 300-line cap,
  command forms, JSON fields) stays green.
- gzy: the hook must not lock out the sanctioned relative form `REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom`
  or any read-only use the coordinator rules allowed in batch qk9 (ruling 6). It must refuse a worktree command or a
  script file run by it that spells the main checkout's absolute path. Brainstorm the exact rule (what counts as
  "from a worktree", which tools, script detection) in the plan, and keep the hook fail-closed on parse errors.
- gzz: docs only.

## Project rules (CLAUDE.md, .claude/rules/tools.md, owner)
- Read `.claude/rules/tools.md` before editing Python (path rules load only after a Read of a matching file).
- Python 3.14 via uv. Test-driven: write the failing pytest first, watch it fail for the right reason, then the code.
  `uv run pytest -q` and `uv run ruff check .` must pass.
- YAGNI per .claude/rules/tools.md: build only what the item asks for. Shallow nesting; named binary-format offsets;
  tests never embed game bytes; real-file tests skip without orig/.
- No change to gate, cflags handling, the build scripts or config/ hash manifests; never touch orig/. Nothing lands:
  no status.csv or src/ change.
- Dispatched agents never push, never use the network, stay on Opus 5.5 (no fast mode), never dispatch subagents,
  and never install the unlazy Stop hook.
- NEVER type a bare `python`, `python3`, `python -` or an empty heredoc: they hang this shell forever. Always run a
  script file: `uv run python <path>`.
- build/ takes writes by shell redirection only (a hook refuses Write/Edit under build/).
- Never name the owner's private project in anything.

Nonce: echo `c9b1f422d4ec` in your return and in your PLAN/SUMMARY frontmatter as `bundle_nonce`.
