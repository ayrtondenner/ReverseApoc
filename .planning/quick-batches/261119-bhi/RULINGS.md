# Rulings (batch 261119-bhi, owner 2026-11-19; binding)

- Three-shapes rule: at 256 B and up a new shape counts only when the attempt check's `shape:` line
  (blocks, branches) changes, with at most 6 shapes. The 15-check budget stays. Under 256 B the rule is
  unchanged. Any skill edit goes through superpowers:writing-skills (RED/GREEN retrieval test by a fresh agent).
- Hand-off board: retire a function when it has had at least 24 attempts AND its best percent did not rise over
  its last 9 attempts (3 passes). Return it automatically when tooling aimed at its failure class lands, or when
  the owner writes a hint for it in config/hints/<exe>.toml. The owner sees the dry-run list before the first --write
  (the coordinator does the first --write, never the executor).
- Held comparisons: Holm correction across arm pairs; a dropped or quota-cut arm enters a pair only on picks both
  arms finished; exact McNemar stays.
- Suspected bad splits: functions.csv is generated; fixes go through a supported generator input. Never touch a
  matched row. Until a fix lands, its rows sit on config/handoff.csv with reason "suspected bad split" and
  return_rule "boundary fixed".
- agy: a denied network step stops only that arm, like a denied write.
- Tool class: `Matched-By: reverseapoc twins` and `Matched-By: reverseapoc lift` landings are "tool", not human-written.
- Pragma/asm: refuse `#pragma`, `_asm`, `__asm`, `_Pragma` in landed C for every harness; include/watcom_compat.h's
  clang pragma stays allowed.
