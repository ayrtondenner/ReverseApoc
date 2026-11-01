---
spike: 009
idea: night-economics
name: readability-pilot
type: standard
validates: "Given the units with matched functions, when a small `drive --session readability` night runs, then units land readlint-clean with bytes unchanged, renames go through proposals, and the cost per unit is known"
verdict: PENDING
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
uv run reverseapoc drive --session readability --workers 4 --max-sessions <N>
```

## Investigation Trail
PENDING

## Results
PENDING
