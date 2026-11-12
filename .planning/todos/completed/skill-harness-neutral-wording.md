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

2026-11-12, closed by quick-batch item 261112-fdv (writing-skills, RED first): RED `c6415f3f`, GREEN `d405f128`.
Reworded L18, L32, L34, L126 and L145, which named Claude Code tools, and L14's /goal. Kept L15, L28 and L58 (hook
facts that bind every harness) and L209 and L215 (the /goal as the Claude mechanism it is). Evidence: the spike 012
Codex and agy transcripts, the 2026-11-11 canaries, LEARNINGS.md. The session.py note's matching wording is handed
to the coordinator, to apply after 261112-fdt merges.
