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

## Written with writing-skills (2026-11-24)

Dry-run scenarios ("pick a skill from the descriptions, follow it on paper, call no Overleaf
tool"), run by fresh Sonnet agents on a clone at 3b036fcc.

- **Scenario 1:** add 20261124-codex (hard-killed at a 5-hour pause with the owner's OK, no
  STOPPED record, 21 sessions, 0 matched, records in 8b338bfd).
- **Scenario 2:** the same, plus "run 20261124-codex3 is running now".
- **RED, current skill.** Both picked paper-sync, and both hesitated on the killed run: "ask the
  owner first; as the skill is written, the answer is no". They cited "its STOPPED record is in
  `progress/attempts.jsonl`" and noted that the owner's OK is not a STOPPED record. Scenario 2
  left codex3 out correctly, citing "a run that is still going gets no figures yet".
- **GREEN, reworded precondition.** A run has ended on an ENDED or STOPPED record, or when it was
  killed and no drive process is left for it. A killed run's figures are counted and summed from
  its attempt records and marked derived, because it has no totals line. A run still going (a
  STARTED record only, and its process alive) gets no figures. Both agents now said YES to
  20261124-codex, without asking, and quoted the killed-run clause. Both would first confirm that
  no process is left, and would recount the owner's 21/0 from the records. Scenario 2 still said
  NO to codex3, citing the still-going sentence, and kept the pass going for codex.
- **REFACTOR.** No new loophole. One agent mixed the kinds up, labelling the session count "T"
  and then "derived" in the same row. The precondition already says "derived", so no change.

## Tests

`test_the_precondition_takes_ended_stopped_and_killed_runs` checks that "Before you start" names
ENDED, STOPPED, killed runs, attempt records and a run still going. No pinned phrase changed.
