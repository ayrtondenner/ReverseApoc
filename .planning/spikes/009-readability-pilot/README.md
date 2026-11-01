---
spike: 009
idea: night-economics
name: readability-pilot
type: standard
validates: "Given the units with matched functions, when a small `drive --session readability` night runs, then units land readlint-clean with bytes unchanged, renames go through proposals, and the cost per unit is known"
verdict: VALIDATED
related: [008]
tags: [readability, readlint, d-17, d-19, drive, renames]
---

# Spike 009: Readability pilot on matched units

## What This Validates
Given the units with matched functions, when a small readability night runs (plan 07-40's
pipeline, ahead of 07-40), then units land readlint-clean with the bytes unchanged, renames go
through proposals, and the cost per unit is known. Owner-authorized (2026-11-01).

## How to Run
```
uv run reverseapoc readlint --report src/ --json
uv run reverseapoc drive --session readability --dry-run
uv run reverseapoc drive --session readability --workers 3 --max-sessions 3   # slice
uv run reverseapoc drive --session readability --workers 3 --max-sessions 9
```

## Investigation Trail
- Preconditions (read-only investigation): the F5 allowlist is a process precondition, not a code
  check (readlint treats a header-only list as "allow nothing"). Without it 28 of 34 units
  referenced a placeholder that is not a matched definition, so strict readlint would have kept
  them from landing.
- Owner ruling 2026-11-01: allowlist first. config/readlint-allow.csv got 5 function references
  (2 closures, 2 hubs, 1 member) and 39 data globals (359011e). Strict readlint RL01 179 -> 53.
- Slice (run 20261101-164853): 3 sessions, 3 LANDED, 3 renames, ENDED cleanly with the end-of-run ninja verify
  and gate --all. Names were checked by hand before the rest: each header cites real call sites
  (for example a caller registering the function as a button callback).
- Rest (run 20261101-165343): 9 sessions, 9 LANDED, 17 renames (8 of them data globals the sessions could
  evidence, although allowlisted), ENDED cleanly.
- Independent checks: container `gate --all` exit 0 with both EXEs SHA-1 identical; mechanics.toml,
  the members file, the asm list and cflags.txt unchanged; Tier 1 matched still 45.

## Results
**VALIDATED.** The first readability nights ran end to end on Opus: 12 of 12 units LANDED, 20
renames APPLIED through their own gated commits (12 functions, 8 data globals), 0 REFUSED, 0
DEFERRED, no stop. Cost $4.48 in all (about $0.37 per unit, 12-17 turns, 2-4 minutes per
session). Strict readlint over src/ went 224 -> 185 violations (RL01 53 -> 40, RL02 26 -> 16,
RL03 75 -> 66).

Signal for the build: readability is cheap and safe at this size; the 15 units left in the queue
cost about $6. Allowlist rows whose global was renamed are now stale and are pruned in 07-40
Task 3. Some names are honest but thin when evidence is thin (`flag_e7304_set`,
`flags_set_d5058_and_pair`); they improve as neighbours get matched.
