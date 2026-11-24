---
title: The drive hook refuses read-only commands that name the checkout
created: 2026-11-23
area: hooks
files: the reverseapoc PreToolUse hook (.claude/hooks), its tests
source: clone work during drives, 2026-11-20 to 2026-11-23
---

# Reads refused during a drive

**Why.** While a drive holds build/driver/drive.lock, the reverseapoc hook refused commands that
only read the checkout: `cp` and `tar` from it into a clone, `find ... -exec grep`, `git pull`
from it, `date`, and any command with `$(...)`, `;` or a `for` loop. `cat <checkout>/x > clone/x`
and `git --no-optional-locks clone` were allowed. Each refusal cost a workaround (a scratchpad
Python copy script, split commands), and the `$(...)` refusal broke a CI watch.

**Do.** Read the hook and list what it parses. Allow the read-only forms (copy from the checkout
into a path outside it, `git --no-optional-locks fetch/pull` into a clone, find/grep reads,
command substitution of read-only commands) and keep refusing anything that writes under the
checkout. Test first with the refused commands above as cases.

**Done when.** The commands above run during a drive when their writes land outside the checkout,
writes under the checkout are still refused, and tests pin both.

## Result (2026-11-23)

Done in `tools/reverseapoc/hooks.py`, test first (26 new allowed cases failed before the change). What changed:

- **cp and Copy-Item:** a source may lie under the checkout; only what the copy writes is judged. GNU cp writes every
  `-t`/`--target-directory` value, else its last operand, and passes only with the value-free letters `rRpvfnuLT` and
  a few long flags (`_cp_targets`). `-l` and `-s` (links back into the checkout) and backups keep the old rule.
  Copy-Item writes its `-Destination`, by name or position, with only `-Path`, `-LiteralPath`, `-Recurse`, `-Force`
  and `-Container` beside it (`_copy_item_targets`). Anything else falls back to the old rule (no operand inside).
- **tar** (`_tar_read`): dash bundles of one mode (`c`, `t` or `x`), `v z j J`, `-f`, `-C` and `--exclude=`. No
  archive under the checkout in any mode; an extract needs every `-C` (chained, each relative to the last) outside,
  and the cwd outside unless a `-C` comes before the first member. Long options and old-style `tar cf` stay refused.
- **git fetch/pull** (`_git_fetch_in`): run in a repository outside the checkout (cwd or `-C`), with value-free listed
  options only (`--ff-only`, `--prune`, `-q`, ...), and no `NAME=value` before git (GIT_DIR could point inside).
  `--upload-pack` and any other option stay refused; so does a fetch or pull whose cwd is the checkout.
- **find** (`_drive_find_offender`, the drive guard's own; the worktree rule keeps `_find_offender`): `-exec` and
  `-execdir` pass when their program is in `_DRIVE_READS`. `-delete`, `-ok`, `-fprint*`, a writer or a shell stay
  refused. Bash's `\;` reaches the splitter as a separator, so the words after it are judged as a command of their
  own: `find . -exec grep x {} \; -delete` is refused, and so is a second `-exec` after a `\;` (over-refusal; use `+`).
- **date** (`_date_offender`): prints; `-s`, `--set` (any bundle or abbreviation) and a bare operand (sets the clock)
  are refused.
- **PowerShell literal assignment** (`_POWERSHELL_LITERAL`): `$x = 'lit'`, `$x='lit'`, `$x = 5` and `$x = "text"` with
  no `$` or backtick in it are data. A later `$x` stays unplaceable, so `Get-ChildItem $x` reads and `Set-Content $x`
  stays refused.
- **Substitutions:** no change was needed once `date` became a read. A substitution's commands are already judged as
  runs of their own, and the `$(...)` word stays unplaceable on purpose: `rm $(echo <checkout>/x)` must stay refused,
  and a substitution of a read (`$(cat list)`) can print a checkout path. So `echo $(date)` and
  `test "$(git -C <checkout> --no-optional-locks rev-parse HEAD)" = x` pass, while a non-read inside, or a non-read
  outer command next to any `$(...)`, is refused as before.
- **`;` stays as it is:** after `cd <clone>; <cmd>` the cd may have failed, so `<cmd>` may run in the checkout: a read
  passes there anyway, anything else is refused. Use `&&`.

Tests (tests/test_hooks.py): ALLOWED_BASH +23 (cp, tar, fetch/pull, find -exec, date, substitutions, `cd x; cat f`,
the `for` loop), ALLOWED_POWERSHELL +6 (Copy-Item, literal assignments), REFUSED_BASH +36 (copies, extracts and
archives into the checkout, `-l`/`-s`, fetch/pull from the checkout or with `--upload-pack` or GIT_DIR, find
`-exec rm`/`-delete`/`-ok`, `$(uv run ...)`, `date -s`), REFUSED_POWERSHELL +6, and
`test_drive_guard_keeps_a_cd_before_a_semicolon_unknown`. `cp tools/x.py /tmp/x.py` moved out of REFUSED_BASH: a
copy out of the checkout is what this todo allows (`cp tools/x.py {scratch}/x.py` is in ALLOWED_BASH). The lists now
take `{repo}` and `{scratch}` through `_placed`.

Still open (not built): a recursive copy keeps symlinks as links (`-r` without `-L`), so an absolute link inside the
checkout would point back into it from the clone; the hook cannot see that from the command text.
