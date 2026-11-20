---
title: One landing helper for flags approve and twins
created: 2026-11-18
area: twins
source: batch 2026-11-18 worker reports
---

# One landing helper for flags approve and twins

U13 (batch 2026-11-18): twins reuses flags._Approver's private helpers. Factor a shared landing helper (write unit, container lint, gate --attempts 0, status, one commit with a trailer, restore on failure).

## Resolution (2026-11-20)

`flags.land_unit` is the one landing step: snapshot the paths, write(), the container C89 `lint`
of the unit, the container `gate EXE/UNIT --attempts N --json`, passed() (the matched-row check),
one commit of every path that exists with the message file, and on `LandingFailed` or any other
error every path restored byte for byte and the staged index reset before it propagates.
`flags._Approver.land` (attempts from the hit, passed() also records the queue row landed) and
`twins._Lander.land` (attempts 0) call it; both keep their own failure handling (approve fails
the queue row; twins returns the reason). `LandingFailed` replaces flags' `_GateFailed` and
twins' `_Failed`; `approve_lint_argv` (one caller) is gone; `_refuse_dirty` and
`_hold_drive_lock` are now public (`refuse_dirty`, `hold_drive_lock`), so twins uses no private
flags helper any more. Behaviour is unchanged.

Characterization tests, green before and after the refactor (and each pair red under a
mutation of land_unit: no index reset, no passed() call):
tests/test_flags.py `test_approve_writes_the_commit_message_under_build_flags`,
`test_approve_fails_a_gate_that_leaves_no_matched_row`,
`test_approve_restores_then_raises_when_the_commit_fails`; tests/test_twins.py
`test_a_twin_lints_its_unit_before_the_gate_and_writes_its_message_under_build`,
`test_a_failing_lint_restores_every_file_and_skips_the_gate`,
`test_a_gate_without_a_matched_row_fails_and_restores`,
`test_a_failing_commit_restores_every_file_then_raises`. tests/test_flags.py and
tests/test_twins.py: 157 passed; ruff check clean.
