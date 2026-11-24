---
title: paper-sync's precondition shuts out a killed run
created: 2026-11-24
area: paper
files: .claude/skills/paper-sync/SKILL.md, tests/test_skill_paper_sync.py
source: first real paper-sync pass, 2026-11-24 (run 20261124-codex)
---

# "Its STOPPED record is in attempts.jsonl"

**Why.** The skill lets a run into the paper only once "its STOPPED record is in
`progress/attempts.jsonl`". Run 20261124-codex was hard-killed with the owner's approval and will
never have one, yet its process is gone and its records were committed by hand (8b338bfd). The
pass of 2026-11-24 included it on judgement and summed its attempt records with a scratch script,
because there was no STOPPED totals line. Run 20261121-codex (killed with its session) is in the
same position. A drive that ENDED is also left unnamed by the wording.

**Do.** Through superpowers' writing-skills (.claude/rules/workflow.md): a dry-run scenario with a
killed run whose records are committed, run against the current skill (RED: it should refuse or
hesitate), then reword the precondition so the run must have ended (an ENDED or STOPPED record, or
no drive process left for it and its records committed) and its records must be committed. Say
that a killed run's figures come from its attempt records, since there is no totals line. Re-run
the scenario (GREEN), and update tests/test_skill_paper_sync.py if a pinned phrase changes.

**Done when.** The skill takes a killed run with committed records, still refuses a run that is
going, and the RED/GREEN record is in the completed todo.
