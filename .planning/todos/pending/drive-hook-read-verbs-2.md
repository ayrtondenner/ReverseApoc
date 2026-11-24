---
title: More read-only commands the drive guard still refuses
created: 2026-11-24
area: hooks
files: tools/reverseapoc/hooks.py (_DRIVE_READS, the PowerShell method rule, _separated), tests/test_hooks.py
source: session of 2026-11-23/24, during runs 20261124-codex and 20261124-codex2
---

# Follow-up to drive-hook-read-only-verbs

**Why.** With the first batch in place (completed/drive-hook-read-only-verbs.md), these reads were
still refused while a drive held the lock, each costing a workaround:
- `sort`, `uniq` and `timeout` (not in `_DRIVE_READS`), in pipes such as `grep ... | sort | uniq -c`;
- PowerShell method calls on read results: `$_.CommandLine.Substring(0, 140)` and
  `@(Get-CimInstance ...).Count` (the `.x(` rule refuses any method call);
- a heredoc or `cat > file` that writes into the scratchpad after `cd <scratchpad dir> &&`;
- `$?` in `echo "exit=$?"` after a `;`.

**Do.** Test first, one case per command above as it was refused. Allow `sort`, `uniq` (with no
output file), `timeout <n> <read command>`, read-only method calls on read values (`.Substring`,
`.Count`, `.Length`, `.ToString`, `-replace`), and a redirect or heredoc whose target is outside
the checkout. Keep every write under the checkout refused, as well as `sort -o <checkout path>`
and `timeout <n> <non-read>`.

**Done when.** The commands above pass during a drive when nothing lands under the checkout, the
write forms are still refused, and tests pin both.
