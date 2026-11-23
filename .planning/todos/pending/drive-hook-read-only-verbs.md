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
