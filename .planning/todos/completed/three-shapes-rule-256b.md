---
title: How the three-shapes stop rule counts shapes at 256 B and up
created: 2026-11-19
area: context-pack
files: .claude/skills/watcom-decomp/SKILL.md
source: run 20261118-256 (todo first-matching-night-256b)
---

# Every 256 B session stopped at 3 checks

The watcom-decomp skill ("When to give up") lets a session stop when "three different C shapes
leave objdiff below 100". On run 20261118-256 all 36 GPT-6.1 Terra sessions, on 14 functions of
256-1023 B, used exactly 3 of their 15 checks and named that rule: 108 checks, 0 exact, 6 rows
raised (tacp func_0001E660 86.67 to 93.89). The rule ended every session before the check
budget did, so the night measured the rule more than the model.

**Owner question.** Should the rule count shapes differently at 256 B and up, together with
structure-first work (todo structure-first-large-functions)? For example:
- count a shape only when the control flow or the order of the statements changes, not a type,
  a declaration or a local's order;
- or scale the count with size (three under 256 B, more above it);
- or, at 256 B and up, let a session go past three shapes while its best percent is still
  rising.

Any change to the skill goes through superpowers' writing-skills skill
(`.claude/rules/workflow.md`), with a pressure test on a 256 B row before and after. Measure it
with a rerun of the 256 B night's picks and compare checks per session and best percent.

## Resolution (2026-11-19)

- Owner decision 2026-11-19: at 256 B and up a check is a new shape only when its `shape:` line's
  blocks or branches change, at most six shapes; the 15-check budget stays; under 256 B unchanged.
- Skill change through writing-skills (quick 261119-bhp, f9d99d82 RED, e9c46cff GREEN, merged
  e4dbdcff after the old-rule run): SKILL.md "When to give up", the shape-line paragraph and mismatch
  step 4; `session.STOP_RULES` in sync. Fresh-agent retrieval test: RED and GREEN records in
  .planning/quick-batches/261119-bhi/SKILL-RED.md and SKILL-GREEN.md.
- Held A/B (runs 20261119-3s-old and 20261119-3s-new, 20 picks of 256-1023 B, Terra): 0 and 0
  exact, McNemar p = 1.0 (Holm 1.0); checks 2.9 -> 7.8 a session; best percent up on 12 picks, down
  on 4; input tokens x1.83. docs/model-comparison.md "The three-shapes rule at 256 B and up".
