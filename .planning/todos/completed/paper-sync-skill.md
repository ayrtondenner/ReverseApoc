---
title: A project skill that adds a session's run results to the Overleaf paper
created: 2026-11-23
area: paper
files: .claude/skills/paper-sync/ (SKILL.md, sanity.py, scan.py), tests/test_skill_paper_sync.py, docs/tools.md
source: sessions of 2026-11-20 to 2026-11-23 (six paper passes briefed by hand)
---

# paper-sync: the paper pass as a skill

Every paper pass of 2026-11-20..23 was briefed by hand. `.claude/skills/paper-sync/SKILL.md` now
holds the procedure, as an ordered recipe:

1. backup zip, never overwriting an earlier one;
2. a mirror built from that backup;
3. a facts file whose rows are marked T/S/derived;
4. a read-only re-check of the T rows against the records;
5. additive edits with `% FACT` lines (results in 08, tooling in 06 or 04, caveats in 10);
6. lint with the bundled `sanity.py`/`scan.py`, compared against the backup;
7. additive `plan_sync`, then `sync_directory`;
8. one compile judged by `summary.builtCleanly`.

`/ars-revision` and `/ars-citation-check` are named as optional follow-ups only.

The two lint scripts are the scratchpad scripts of the 2026-11-20 passes. They gained a module
docstring, ruff fixes, and lost a one-off citation-pair check. The skill copies them into the
scratchpad, because during a drive the hook runs a script only from outside the checkout.

## Written with writing-skills (2026-11-23)

The test was a dry-run scenario ("plan the paper pass, call no Overleaf tool"), run by Sonnet
agents on a clone at 9233222b.

- **RED, no skill, 3 prompts** (plain, hurried owner, tooling-heavy). All three found the backup,
  the additive sync and `builtCleanly`, partly because two of them read this todo. None built the
  mirror from the backup: they edited section text fetched one by one, and one offered per-file
  `write_file`. One passed `overwrite: true` on the backup. None used `% FACT` lines, linted
  before the sync, or had a section map. Only one marked figures T/S.
- **GREEN, with the skill, the hurried and tooling prompts.** Both picked paper-sync from its
  description among the project skills and followed all eight steps: backup without overwrite,
  mirror from the zip, facts file with kinds, owner figures marked S, lint against the backup,
  additive sync, one compile.
- **REFACTOR.** The tooling prompt said "a drive is running", and the agent refused the whole
  pass. The precondition now names the run being added: it must have its STOPPED record and its
  records committed. A different running drive does not block the pass. Re-run with a finished run
  plus a running one: it proceeded with the finished run only.

## Tests

tests/test_skill_paper_sync.py:
- `test_the_frontmatter_names_the_skill_by_when_to_use_it`
- `test_the_lint_scripts_it_runs_ship_with_it`
- `test_the_steps_run_in_the_safe_order`
- `test_a_pass_compiles_once_and_judges_by_built_cleanly`
- `test_docs_tools_lists_the_skill` (written failing first)

docs/tools.md lists the skill in the tools table and in "Skill installation decisions" item 4.
