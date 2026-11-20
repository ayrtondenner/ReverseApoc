---
title: Show the whole aligned diff and the failure class in attempt check
created: 2026-11-18
area: attempt-check
files: tools/reverseapoc/attempt.py, tools/reverseapoc/classify.py, tools/reverseapoc/hooks.py
source: literature mining of 2026-11-18 (docs/research/notes-ideas-agentic-projects.md #1, #8; docs/research/notes-ideas-llm-decomp-research.md #2)
---

# Show the whole aligned diff and the failure class in attempt check

**Why.** `attempt check` shows only a short window around the first differing instruction (attempt.py `_window_lines`), and the failure class `classify.py` computes never reaches the agent. Agents keep asking for more: 181 notes.md files request a fuller diff (agentic-projects #1). Echo and SymDec use the whole difference set as the repair signal.

**Do.** Add `attempt diff` (or a `--full` view of check): every differing run aligned ours/original, each with its mismatch class (length, register, order, relocation), plus the classify verdict in check's own output. Keep it bounded for context-pack size limits.

**Done when.** A test check on a two-run mismatch prints both runs and their classes; the skill names the command; a held A/B shows whether it raises the match rate at 64-255 B.

**Effort / value.** M / high. Evidence and sources: docs/research/notes-ideas-agentic-projects.md #1, #8; docs/research/notes-ideas-llm-decomp-research.md #2.

## Status (2026-11-18)

Status (batch 2026-11-18, U6, merge a326861d): `attempt diff`, the class line and the skill text (9443f1c7) are in. Left: the held A/B at 64-255 B.

## Owner question: how to run the held A/B (2026-11-20)

The first two Done-when items hold at 0b49ec48: `uv run pytest -q tests/test_classify.py
tests/test_attempt_wrapper.py -k "diff or class"` gives 92 passed, and SKILL.md names the command
(the wrapper table row, the class line, the window paragraph). The A/B is still open. It needs a
paid drive and choices only the owner can make.

**What the records show (T, read-only grep of build/driver transcripts, 2026-11-20).** The command
is used. About 90 of the 355 counted sessions in runs from 20261118 to 20261120 have an
`attempt diff of check NNNN` output in their transcript. Codex, Claude, Fable and Gemini arms all
show it. Every night since 2026-11-18 had the command, so no run so far serves as a control.
Sessions that call it are the ones whose checks failed, so comparing callers with non-callers
says nothing about the match rate.

**Why it needs a ruling.**
1. *The control arm.* The feature has landed and there is no off switch. Options:
   - (a) A driver switch for a hold run, such as `--pack-variant no-full-diff`, recorded in the
     run marker and the environment digest. The class line is left out of check, and
     `attempt diff` is refused or left out of the guard forms. The skill still names the command,
     so the control arm either sees a refused command or needs a second copy of the skill. That
     is a skill-text question for writing-skills and touches the Copilot prompt margin. The same
     switch would serve todo `held-context-ablations` (one factor per held run), so the two
     todos could share one mechanism.
   - (b) Run the control from a checkout before a326861d, as the three-shapes A/B did with
     4f52a58e. This costs no code, but everything landed since 2026-11-18 (pack sections U7 to
     U11, the six-shapes rule, splits batches 1 and 2) differs between the arms, so the result
     would not isolate the diff.
   - (c) No A/B. Close the todo on the usage figures above and record the feature as kept
     without measurement, as the pack's other parts were until `held-context-ablations`.
2. *Size and picks.* `config/benchmarks/held-v1.txt` holds only 20 picks of 64-255 B (from 245
   partial rows at e93afb69). The three-shapes A/B came out 0 to 0 on 20 picks. At a 2-5% match
   rate per pick, a few points of difference needs about 100-150 picks per variant
   (docs/research/notes-ideas-llm-decomp-research.md, #4 "Why it would help"). That means a new
   frozen set (a held-v2 of 64-255 B rows) or a near-miss `--write-picks` list, and an owner
   budget of about 200-300 sessions in all.
3. *Arm and budget.* From docs/model-routing.md "Quota per session": Terra holds about 74
   sessions per 5-hour window (3-4 windows for 2 x 120). Haiku 5.5 on the Claude plan runs about
   300 sessions per 3% of the week. Haiku on Copilot costs about 2.2 credits a session.

**Recommendation, for the owner to accept or change.** Option (a), built once together with
`held-context-ablations`, then 2 x 120 picks of 64-255 B on one cheap arm (Haiku 5.5 or Terra),
judged by the held-v1 decision rule (exact McNemar p < 0.05). Nothing is built until the owner
rules.
