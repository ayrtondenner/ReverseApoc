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

## Result (2026-11-24)

Owner ruling (2026-11-24): allow `sort` and `uniq` (no `-o` and no output file under the checkout),
`timeout <n> <read command>`, and read-only PowerShell method calls or properties on read values (`.Substring(`,
`.Count`, `.Length`, `.ToString(`, `.Trim(`, `-replace`). Allow a heredoc, `cat > file` or redirect whose target is
outside the checkout after `cd <outside dir> &&`, and `$?` in an echo. Keep refused: `sort -o <checkout>`,
`timeout 5 rm ...`, method calls that write (`.Delete(`, `.WriteAllText(`, `[IO.File]::Write...`) and any write under
the checkout.

Done in `tools/reverseapoc/hooks.py`, test first (25 cases failed before the change):

- **sort** (`_sort_offender`): refused with `-o`, `-T` (temporary files) or `--compress-program`, in a bundle or any
  long abbreviation, even when the output lies outside: while the call touches the checkout, no `-o` at all.
- **uniq** (`_uniq_outputs`): reads when nothing after its input operand (its output file) may lie under the
  checkout; `-f`/`-s`/`-w` values are skipped and everything after `--` is an operand.
- **timeout** (`_untimed`): `timeout [-k D] [-s SIG] [--preserve-status] [--foreground] [-v] DURATION <cmd>` is judged
  as `<cmd>` (nested timeouts too), image and nested-shell checks included. Any other option, a missing duration,
  or a timed `cd` (it cannot move the shell) is a non-read.
- **PowerShell members** (`_pure_members`): `.Count`, `.Length`, and `.Substring(`, `.Trim(`, `.ToString(` whose
  arguments are numbers, `$values` or quoted text with no `/` or `\`, after a value, `)` or `]`, are taken out
  before the call is judged, and `@(` reads as `(`. Every other method call still meets the `.x(` rule, so
  `.Delete()`, `[IO.File]::WriteAllLines(...)` and `.ToString('<path>')` stay refused. `-replace` heading a
  segment (after a `(...)`) is a read; its operands are still judged.
- **`$?`** is a number, so `_guarded` no longer counts it as an unplaceable path.
- **Heredocs:** `cd <outside> && cat > f <<'EOF'`, `cat <<EOF > f` and `cat > f` already passed; the tests now pin
  them, beside `cat > notes.txt <<EOF` from the checkout (refused).

Holes found and closed on the way (probe and an independent review, each a failing test first):
- a value glued to its option was never judged: `cp -t<checkout>`, `mv -t<checkout>`, `tar -C<checkout>`,
  `sort -o<checkout>` and PowerShell `-Path:<checkout>` passed from a clone. `_glued` now adds such tails (when
  they hold a separator or an expansion) to the run's words and to the writer check.
- the body of a here-document with an unquoted delimiter is expanded by Bash, but the splitter dropped it:
  `cat > <scratch>/x <<EOF` with `$(rm -rf <checkout>/tools)` in the body passed. `_heredoc_substitutions` judges
  those substitutions.
- a writer or remover with no operand (`Get-ChildItem tools | Remove-Item`, `Remove-Item (Resolve-Path x)`, whose
  `(...)` the splitter cuts off) counted as a read; it is now refused when the call touches the checkout.
- PowerShell or docker behind another launcher (`nohup bash -c "pwsh ..."`, `env -S`, `time`, `command`, `winpty`,
  `find -exec`, `call`, `Start-Process cmd '/c pwsh ...'`; `nohup docker compose build`, `env docker build`) is
  refused like the direct forms.
- a word after `--` that starts with `-` was never an operand: `rm -rf -- -/../tools` from the checkout deleted
  `tools`. `_operands` now takes every word after `--`.

Tests (tests/test_hooks.py): `READS_2_ALLOWED` (26) allowed from the checkout; `READS_2_REFUSED` (40: 29 from the
checkout, 11 from a clone).

Left refused on purpose: `.Substring(0, [Math]::Min(...))` and any argument that is itself a call; `timeout -k2`
(glued value); `sort -o <outside>` while the call touches the checkout.

Still open, older than this change (independent review, 2026-11-24, not fixed here): a `<<` that is not a
heredoc (`cat <<<EOF`, `echo "<<EOF"`, `$((1<<EOF))`) makes `_HEREDOC` drop the following lines as a body, so a
command on them (`rm -rf tools`) is never judged. It needs a quote-aware heredoc reader shared with the worktree
layer, so it is left for its own todo.
