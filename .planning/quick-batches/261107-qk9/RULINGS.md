# Batch 261107-qk9: coordinator rulings and project rules

Every planner and executor of this batch reads this file before anything else.

## Order (coordinator ruling)
- 261107-qka (measurement harness) comes first: every other item is measured with it.
- 261107-qkb, 261107-qkc, 261107-qkd and 261107-qke all touch tools/reverseapoc/lift.py, so they run one after another in that order to avoid merge conflicts: qkb depends on qka, qkc on qkb, qkd on qkc, qke on qkd. Declare exactly that in depends_on.

## Measurement (coordinator ruling)
- The curve gate needs orig/ (the game EXEs, gitignored) and the docker container. Worktrees have neither. Executors build and test only, with fixtures and no game bytes; they never run the curve gate. The coordinator runs it on the main checkout after each merge and records the exact and near counts per size bucket.
- Phase 7.1 is closed. Never edit any file under .planning/phases/07.1-matching-tooling/, and never write its 07.1-CURVE.md.

## Project rules (CLAUDE.md, .claude/rules/tools.md, owner)
- Python 3.14 via uv. Test-driven: write the failing pytest first, watch it fail for the right reason, then the code. `uv run pytest -q` and `uv run ruff check .` must pass.
- YAGNI per .claude/rules/tools.md: build only what the item asks for; no options or layers nobody asked for. Shallow nesting; named binary-format offsets; tests never embed game bytes; real-file tests skip without orig/.
- No change to check, gate, cflags handling, the build scripts or config/ hash manifests; never touch orig/. A lifted row is a draft, never a match: nothing lands, no status.csv or src/ change.
- Dispatched agents never push, never use the network, stay on Opus 5.5 (no fast mode), never dispatch subagents, and never install the unlazy Stop hook.
- NEVER type a bare `python`, `python3`, `python -` or an empty heredoc: they hang this shell forever. Always run a script file: `uv run python <path>`.
- build/ takes writes by shell redirection only (a hook refuses Write/Edit under build/).

Nonce: echo `9202d094a600` in your return and in your PLAN/SUMMARY frontmatter as `bundle_nonce`.
