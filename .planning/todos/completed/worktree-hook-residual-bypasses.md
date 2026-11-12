---
title: Worktree main-path hook, residual bypasses (security review round 3)
created: 2026-11-09
source: automated security review of quick task 261109-gzy (merged bf8a7f56), round 3
---

# Worktree main-path hook: residual bypasses

Quick task 261109-gzy added a PreToolUse rule that denies a worktree Bash or PowerShell command when the command, or a
script it names, spells the main checkout's absolute path. Two security rounds were fixed, and the second made the rule
fail closed (ruling 2).

The rule's raw-text layer denies any literal spelling of the main path in the command text and in every script it
reads. The rule is a guard against our own agents, not a sandbox (docs/workflow.md Known limits). The real containment
is the harness worktree plus the batch and driver audits.

Round 3 flagged three more ways to hide a script from detection, so its body is never read. They were accepted as
residual risk on 2026-11-09 and not fixed:

1. **Raw-text indirection match vs quoted words.** Indirection keywords are matched on the raw text, so a quoted or
   escaped keyword or verb can slip past. A fix would match on tokenized, unquoted words, or deny any script-naming
   command with a quote or backslash inside a bare word.
2. **Incomplete denylist.** `sl`, `chdir`, `-e`, `-ec`, `-enc`, `--eval` and working-directory flags (`--directory`,
   `--project`, `-C`, `-WorkingDirectory`) are not listed. The better form is an allowlist: a script-naming command
   must be a plain interpreter followed by a plain script path.
3. **PowerShell backtick escapes** can hide a script word from the suffix test. A fix would normalise backtick and
   backslash escapes before the test, or deny any PowerShell word containing a backtick.

**Why deferred:** each round finds more parser shapes. A path assembled at run time can never be caught by patterns.
The durable fix is OS-level: run worktree agents with no read access to the main checkout, as a sandboxed user or
container mount.

**What closes this:** either the allowlist form of item 2 plus normalisation (items 1 and 3), or an OS-level sandbox
for worktree agents, with tests.

## Result (quick 261112-fdw, 2026-11-12)

Closed by the allowlist form plus normalisation, in batch 261112-fdr, RED first each time:

- `f078276c` RED and `9b070683` GREEN: the worktree allowlist replaces the keyword denylist (item 2).
- `3168bdea` RED and `2d5f8322` GREEN: substitutions are judged, PowerShell escapes and quotes are decoded, and a
  .ps1 run ends the call (items 1 and 3).
- `5ea6d907` RED (review finding 1, test strings written by the owner) and `f2c4347e` GREEN: a script-naming call
  holding `$'` or a word-initial `#` outside quotes is refused, and so is a PowerShell call with a `$(` after a direct
  script run.

The rule is still a guard against our own agents, not a sandbox; docs/workflow.md Known limits lists what stays open.
