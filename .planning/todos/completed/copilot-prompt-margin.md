---
title: The Copilot prompt has 38 characters left under the Windows command line
created: 2026-11-20
area: context-pack
files: .claude/skills/watcom-decomp/SKILL.md, tools/reverseapoc/session.py, tests/test_session.py
source: quick 261119-bhp (three-shapes rule edit)
---

# The next skill edit will not fit

**Why.** After the 2026-11-19 three-shapes edit, `test_each_signed_in_prompt_fits_the_windows_command_line`
passes with 38 characters to spare for the Copilot prompt (Codex 382, agy 259) under 32,767 - 2,500. The
first wording was 28 characters over. Any further skill text outside a `<!-- claude-only -->` block will
fail that test.

**Do.** Find room before the next skill change: move Claude-only text into claude-only blocks, trim
duplicated wording, or pass the skill to Copilot another way (a file the session reads) if the CLI
allows it. Keep the retrieval behaviour the RED/GREEN records pin (.planning/quick-batches/261119-bhi).

**Done when.** The Copilot prompt has at least 1,000 characters of margin and the skill tests pass.

## Resolution (2026-11-20)

Margins under 32,767 - 2,500 for the watcom-decomp prompts (longest goal, list2cmdline-quoted):

| Prompt | Before | After |
|---|---|---|
| Copilot | 38 | 1,093 |
| Codex | 382 | 857 |
| agy | 259 | 734 |

watcom-readability prompts are unchanged except Copilot (7,741 to 8,321, from the goal change).

- `tools/reverseapoc/session.py`: goal_prompt's stop clause is now the constant `_STOP_CLAUSE` (goal_prompt's output is
  byte-identical). `copilot_prompt` replaces it with `_SKILL_STOP_CLAUSE` ('Or stop as "When to give up" below says;
  no other stop meets this goal.'), since the Copilot prompt already carries the skill's full stop list. This saves
  580 characters. Claude's /goal and the Codex and agy prompts keep the list.
- `.claude/skills/watcom-decomp/SKILL.md` (through superpowers:writing-skills): two `<!-- claude-only -->` blocks.
  One holds the first two Pragmas bullets, which repeat the "Never" list's pragma ban ("A register difference is a
  C-shape or flags question; record it in notes.md." stays shared). The other holds the "When the /goal blocks a
  stop" paragraph, because only Claude sessions have a /goal. Claude's text is unchanged apart from the marker lines.
- Option (a) was not taken: the Copilot CLI 1.0.111 `--help` documents no prompt-from-file for `-p` (`--attachment`
  is for images and native documents), and a "read this file first" prompt would need driver changes plus a paid
  canary to prove.
- Tests: `test_the_copilot_prompt_leaves_room_for_the_next_skill_edit` (RED: margin 38; GREEN: 1,093) and
  `test_the_copilot_prompt_lists_each_stop_rule_once` (RED: each rule appeared twice; GREEN) in tests/test_session.py.
- Retrieval (fresh Sonnet agents, the 261119-bhi questions a-f plus pragma, stopping and blocked-stop questions):
  the baseline Copilot prompt, the new Copilot prompt and the edited SKILL.md (Claude view) gave the same answers
  to a-h. The new Copilot prompt still quotes the Never list's pragma ban and "A register difference ... record it
  in notes.md". On i) the Copilot view no longer sees the /goal paragraph and answers "keep working unless a stop
  rule holds", which is right for a harness without a /goal.
