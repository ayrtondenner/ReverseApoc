# Executor brief (batch 261109-gzs)

Read this after the worktree branch check and before your plan.

## Your plan file
`.planning/quick/` is gitignored, so your worktree does not contain your plan. First action after the branch check:
copy it from the main checkout (read-only source) into the same relative path inside your worktree, then read it there.
A hook refuses commands that spell the main checkout's absolute path from a worktree, so use the relative form from
your worktree root (`.claude/worktrees/<name>/`):

    mkdir -p "<rel dir>" && cp "../../../<rel plan path>" "<rel plan path>"

Also read, read-only, from the main checkout the same way: `../../../.planning/quick-batches/261109-gzs/RULINGS.md`
(binding).

If your plan depends on a sibling item, the coordinator tells you its merged commit; run
`git merge --no-ff <commit>` in your worktree first.

## How to work
- Read `.claude/rules/tools.md` first. Test first: write the failing pytest, run it, see it fail for the right reason,
  then write the code. Commit each task atomically (code and tests only) on your worktree branch, with explicit paths.
- `uv run pytest -q` and `uv run ruff check .` green in your worktree before you report. Name any failure you saw,
  even one you did not cause.
- Watcom: your worktree has no third_party/. For tests that compile, set
  `REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom` (read only). Never read or copy orig/, never run docker, the
  curve gate or `reverseapoc drive`.
- Never write outside your worktree: the main checkout is read-only for you.
- NEVER type a bare `python`, `python3`, `python -` or an empty heredoc: they hang this shell forever. Run scripts as
  `uv run python <file>`.
- Never push, no network, no subagents, stay on Opus 5.5, never install the unlazy Stop hook.
- Write your SUMMARY at the plan's quick directory path inside your worktree, with `status: complete` and
  `bundle_nonce: c9b1f422d4ec` in its frontmatter; do not commit it, the PLAN or STATE.md (the coordinator handles
  docs).
- Return: status (DONE / DONE_WITH_CONCERNS / BLOCKED), your worktree path, branch, commit list, one-line test result,
  and concerns.
