---
title: A project skill that adds a session's run results to the Overleaf paper
created: 2026-11-23
area: paper
files: .claude/skills/paper-sync/ (new), docs/tools.md
source: sessions of 2026-11-20 to 2026-11-23 (six paper passes briefed by hand)
---

# The paper pass is a fixed procedure

**Why.** Every paper update this session followed the same steps, briefed by hand each time: a
facts list with sources ((T) records, (S) owner screenshots, derived figures marked), a read-only
check of every number against progress/attempts.jsonl and the drive logs, a backup zip of the
Overleaf project, edits in a local copy of its files, an additive `plan_sync` then
`sync_directory`, one compile judged by `summary.builtCleanly`, and a facts-pack section. The
check caught real errors (a wrong re-sign status, an estimated limit time, an unnamed 5-hour
pause). No ARS skill reads run records or session content; academic-paper revision mode restructures
prose, so it is a follow-up pass, not this step.

**Do.** Write the skill through superpowers' writing-skills (.claude/rules/workflow.md), with a
retrieval test, and list it in docs/tools.md. Keep it to the procedure above; point to
`/ars-revision` and `/ars-citation-check` as optional follow-ups.

**Done when.** Invoking the skill after a session produces a verified, additive paper update that
compiles cleanly, and docs/tools.md lists it.
