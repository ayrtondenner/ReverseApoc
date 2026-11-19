# Executor brief (batch 261119-bhi)

Read this after the worktree branch check and before your plan.

## Your plan file
`.planning/quick/` is gitignored, so your worktree does not contain your plan. First action after the branch check:
copy it from the main checkout (read-only source) into the same relative path inside your worktree, then read it.
A hook refuses commands that spell the main checkout's absolute path from a worktree, so use the relative form from
your worktree root (`.claude/worktrees/<name>/`):

    mkdir -p .planning/quick && cp ../../../.planning/quick/<id>-PLAN.md .planning/quick/

Also read, read-only, `../../../.planning/quick-batches/261119-bhi/RULINGS.md` (binding).

## How to work
- Read `.claude/rules/tools.md` first (YAGNI, Python only). Test first (superpowers:test-driven-development): write the
  failing pytest, run it, see it fail for the right reason, then write the code. Commit each RED and each GREEN step
  atomically (explicit paths) on your worktree branch. Unexpected failure: superpowers:systematic-debugging.
- Run ONLY the test files you touch or that cover the code you touch (`uv run pytest -q tests/test_x.py ...`), plus
  `uv run ruff check .`. Eight executors run at once; the coordinator runs the full host suite (~30 min) after
  merging. Paste the final lines (superpowers:verification-before-completion). Name any failure you saw.
- Watcom: your worktree has no third_party/. For tests that compile, set
  `REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom` (read only). Never read or copy orig/ into the worktree,
  never run docker, `reverseapoc drive` or the curve gate. Tests that need orig/ may skip in a worktree; say so.
- Never write outside your worktree: the main checkout is read-only for you.
- NEVER type a bare `python`, `python3`, `python -` or an empty heredoc: they hang this shell forever. Run scripts
  as `uv run python <file>` or `uv run --no-project python -I <file>`.
- Never push, no network, no gh, no subagents (except where your plan says a fresh-agent retrieval test), never
  install the unlazy Stop hook. Never name the owner's private project anywhere.
- Docs: update docs/model-routing.md / docs/learnings.md / docs/tools.md only where your change alters what they say.
  Todo items: `git mv .planning/todos/pending/<todo>.md .planning/todos/completed/` and append a
  `## Resolution (2026-11-19)` note with commits and evidence, when your plan says so.
- Write your SUMMARY at `.planning/quick/<id>-SUMMARY.md` inside your worktree with `status: complete` in its
  frontmatter; do not commit it, the PLAN or STATE.md.
- Return: status (DONE / DONE_WITH_CONCERNS / BLOCKED), worktree path, branch, commit list (RED and GREEN marked),
  one-line test result, and concerns.
