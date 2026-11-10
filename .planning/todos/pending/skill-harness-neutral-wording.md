---
created: 2026-11-10
source: 07.2-09 SUMMARY (concerns)
---

# watcom-decomp skill: harness-neutral wording for Codex and agy sessions

The watcom-decomp SKILL.md text is also the instruction text for Codex (07.2-13) and Antigravity (07.2-15) drive
sessions. 07.2-09's new text names no tool, but older lines still name Claude Code tools ("Look around with Read,
Grep and Glob", "the Bash tool's `timeout`"). A Codex or agy session has none of these by those names.

Do: reword those lines to name what to do (read a file, search, run the wrapper) rather than a Claude Code tool, or
have the session prompt add a short per-harness note. Through superpowers:writing-skills, RED first. Measure after
the first Codex and agy canaries show how those sessions read the skill; don't change it blind.

2026-11-10 (07.2 review WR-10): the prompt note is now there: session.py's `codex_prompt` and `agy_prompt` add a
"Harness note" (no Read, Grep or Glob; read through the wrapper's printing forms; agy may also read_file inside its
attempt dir), so the skill wording itself is still open but no longer the only text a Codex or agy session gets.
