---
title: Other wrapper temp files left by a killed check still stop a night
created: 2026-11-18
area: driver
source: batch 2026-11-18 worker reports
---

# Other wrapper temp files left by a killed check still stop a night

U1 (batch 2026-11-18) excused only `checks/.NNNN.json.<hex>.tmp`. Other files written by fileio.write_atomic, such as `.context.md.<hex>.tmp` and temp files under `view/build/attempt-cache/`, can be left by a killed check and still stop the night. Decide which are safe to quarantine, with the same ledger check.
