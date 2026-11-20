---
title: Refuse a night up front on a bad hint file or signature table
created: 2026-11-18
area: driver
source: batch 2026-11-18 worker reports
---

# Refuse a night up front on a bad hint file or signature table

U10 (batch 2026-11-18): a malformed config/hints/<exe>.toml or build/signatures/<exe>.json raises in attempt.make_pack at session launch, and the driver catches only PackOverCap, so one typo stops a night partway. Validate both in driver.load_world (contextpack.read_hints once per EXE; signatures.load note) and refuse the drive with a reason.

## Resolution (2026-11-20)

`driver.check_pack_inputs(data, roots)` reads config/hints/<exe>.toml (contextpack.read_hints over
the EXE's game and thunk row starts, as make_pack does) and build/signatures/<exe>.json
(signatures.load) once per EXE; `load_world` calls it right after exe_inputs. A malformed file
raises ContextPackError or SignatureError there, and `_load_worlds` (unchanged) turns it into
`refused (world): cannot load the EXEs: <Error>: <path>: ...`, exit 2, before any session. No
file, or a stale table (load's note), is no refusal; make_pack still reads both per session.

Tests (tests/test_driver_world.py): `test_pack_inputs_pass_with_no_files_or_good_ones`,
`test_a_bad_hint_file_refuses_the_drive_up_front`,
`test_a_malformed_signature_table_refuses_the_drive_up_front` (RED: no check_pack_inputs, and the
refusal named `AttributeError` from assess instead of the bad file; GREEN: 3 passed).
tests/test_drive_real.py::test_real_pools_have_units_and_callees passes over the real EXEs with
the committed config/hints/ files (62 s).
