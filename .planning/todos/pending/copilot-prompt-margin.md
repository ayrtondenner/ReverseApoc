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
