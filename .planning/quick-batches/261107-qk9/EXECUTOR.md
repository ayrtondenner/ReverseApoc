# Executor brief (batch 261107-qk9 and quick task 261107-qzx)

Read this after the worktree branch check and before your plan.

## Your plan file
`.planning/quick/` is gitignored, so your worktree does not contain your plan. First action after the branch check: copy it from the main checkout (read-only source) into the same relative path inside your worktree, then read it there:

    mkdir -p "<rel dir>" && cp "C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/<rel plan path>" "<rel plan path>"

Also read, read-only, from the main checkout: `.planning/quick-batches/261107-qk9/RULINGS.md` (binding; for 261107-qzx the owner's OK to change tools/reverseapoc/check.py overrides its "no change to check" line, for check.py only).

## How to work
- Test first: write the failing pytest, run it, see it fail for the right reason, then write the code. Commit each task atomically (code and tests only) on your worktree branch.
- `uv run pytest -q` and `uv run ruff check .` green in your worktree before you report. Name any failure you saw, even one you did not cause.
- Watcom: your worktree has no third_party/. Point `REVERSEAPOC_WATCOM_DIR` at `C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/third_party/watcom` (read only) for tests that compile. Never read or copy orig/, never run docker, the curve gate or `reverseapoc drive`.
- Never write outside your worktree except nothing at all: the main checkout is read-only for you.
- NEVER type a bare `python`, `python3`, `python -` or an empty heredoc: they hang this shell forever. Run scripts as `uv run python <file>`.
- Never push, no network, no subagents, stay on Opus 5.5, never install the unlazy Stop hook.
- Write your SUMMARY at the plan's quick directory path inside your worktree, with `status: complete` and `bundle_nonce: 9202d094a600` in its frontmatter; do not commit it, the PLAN or STATE.md (the coordinator handles docs).
- Return: status (DONE / DONE_WITH_CONCERNS / BLOCKED), your worktree path, branch, commit list, one-line test result, and concerns.
