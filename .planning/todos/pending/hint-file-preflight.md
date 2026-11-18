---
title: Refuse a night up front on a bad hint file or signature table
created: 2026-11-18
area: driver
source: batch 2026-11-18 worker reports
---

# Refuse a night up front on a bad hint file or signature table

U10 (batch 2026-11-18): a malformed config/hints/<exe>.toml or build/signatures/<exe>.json raises in attempt.make_pack at session launch, and the driver catches only PackOverCap, so one typo stops a night partway. Validate both in driver.load_world (contextpack.read_hints once per EXE; signatures.load note) and refuse the drive with a reason.
