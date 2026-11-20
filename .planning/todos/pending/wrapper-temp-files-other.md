---
title: Other wrapper temp files left by a killed check still stop a night
created: 2026-11-18
area: driver
source: batch 2026-11-18 worker reports
---

# Other wrapper temp files left by a killed check still stop a night

U1 (batch 2026-11-18) excused only `checks/.NNNN.json.<hex>.tmp`. Other files written by fileio.write_atomic, such as `.context.md.<hex>.tmp` and temp files under `view/build/attempt-cache/`, can be left by a killed check and still stop the night. Decide which are safe to quarantine, with the same ledger check.

## Partial resolution (2026-11-20)

The wrapper (`attempt.py`) calls `fileio.write_atomic` (temp name `.<name>.<16 hex>.tmp`,
fileio.py:40) in the attempt dir at four places:

| Target | Call site | Ledger entry before the write? |
|---|---|---|
| `checks/NNNN.json` | `_record`, attempt.py:1236 | yes: `checks/NNNN.c` (attempt.py:1188) |
| `checks/NNNN.diff.json` | `_save_diff`, attempt.py:1321, run at :1198 for a plain matching check only | yes: `checks/NNNN.c` |
| `context.md` | `cmd_context`, attempt.py:2263; `contextpack.write_pack`, contextpack.py:974 | no |
| `view/build/attempt-cache/<form>[.<NAME>].json` | `_cache_store`, attempt.py:2203 (asm and context) | no |

(`checks/NNNN.c` and `checks/NNNN.note.json` are O_EXCL creates and `checks.jsonl` an append:
no temp file.)

What the runs show (searched every `build/driver/` tree of the checkout on 2026-11-20, read
only): the only wrapper temp files ever left in an attempt dir are `checks/.NNNN.json.<hex>.tmp`
(20261116-fable-ab and 20261116-mixed4, both quarantined; 20261113-cascade2-claude-haiku and
spike012-claude-sonnet, Claude sessions, still in place). No `.context.md.*.tmp`, no
attempt-cache temp file and no diff temp file has been seen. The `view/build/check-custom/.../
*.prov.json.<hex>.tmp` files two fable-ab attempts hold are the container's, under view/build/,
which the audit does not inventory.

Done: `checks/.<NNNN>.diff.json.<16 hex>.tmp` joins the U1 rule. It is written in the same
in-flight window as the observed shape, so the same ledger check proves it the wrapper's:
`checks/NNNN.c` ledgered, no `checks/NNNN.json`, and (new, for both shapes) no ledger entry for
the temp file's own target. A diff leftover is excused only in a matching session
(`check_leftovers(..., diffs=claim.session != READABILITY)`): a readability or sweep check
saves no diff. Tests: `tests/test_codex.py::test_a_check_killed_saving_its_diff_leaves_a_leftover_and_nothing_else`,
`tests/test_copilot.py::test_a_check_killed_saving_its_diff_does_not_stop_the_night`.
docs/model-routing.md "Faults the drive rides out" says so.

## Open question for the owner: `.context.md.<hex>.tmp` and attempt-cache temp files

Neither write has a ledger entry before it, so the ledger cannot show it in flight, and a
session could plant a file of either shape. The attempt-cache name also carries the session's
own `attempt asm NAME` argument. Both still stop the night. Options:

1. **Keep them strays (current behaviour, fail closed).** Cost: a session killed inside
   `attempt context` or an `attempt asm`/`context` cache store stops the night. Never seen in
   any run so far. Recommended until one is seen.
2. **Ledger an intent before each such write.** The wrapper appends a line such as
   `{"path": "context.md", "writing": true}` before write_atomic (read_wrapper_ledger already
   ignores lines without a sha256, so older audits are unaffected), and the audit quarantines
   `.context.md.<16 hex>.tmp` or `view/build/attempt-cache/.<entry>.json.<16 hex>.tmp` only when
   the ledger's last line for that target is the intent. Same proof as U1; needs an attempt.py
   change and a ledger-format note in docs.
3. **Quarantine by shape alone.** Not recommended: it excuses a file any session can make
   without a stop.
4. **The wrapper removes its own stale temp files at the start of each context/asm run.** Does
   not cover the usual case (a session killed at its timeout mid-command), so not enough alone.
