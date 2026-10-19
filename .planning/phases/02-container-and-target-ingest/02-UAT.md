---
status: complete
phase: 02-container-and-target-ingest
source: [02-01-SUMMARY.md, 02-02-SUMMARY.md]
started: 2026-10-19T22:42:37Z
updated: 2026-10-19T23:07:32.205Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Clean image build and container test run succeed from scratch (docker compose build --no-cache; docker compose run --rm test -> all passed); the auto-covered deliverables 2-8 are confirmed by the owner
result: pass
evidence: "Run by Claude at the owner's request on 2026-10-19 after removing reverseapoc-build:local and the reverseapoc_uv-cache/uv-venv volumes: build --no-cache exit 0 in 90s (objdiff-cli and ow-snapshot sha256 OK); docker compose run --rm test exit 0, 91 passed, 0 skipped. Owner reviewed the output and answered 'pass'."


### 2. Container builds and runs the test suite with read-only orig/ and third_party/watcom/ mounts
expected: Container builds and runs the test suite with read-only orig/ and third_party/watcom/ mounts
result: pass
source: automated
coverage_id: D1

### 3. check-orig verifies the user's executables against config/targets.toml
expected: check-orig verifies the user's executables against config/targets.toml
result: pass
source: automated
coverage_id: D2

### 4. parse-le reproduces the scanned layout of both EXEs
expected: parse-le reproduces the scanned layout of both EXEs
result: pass
source: automated
coverage_id: D3

### 5. pytest and ruff green on the host
expected: pytest and ruff green on the host
result: pass
source: automated
coverage_id: D4

### 6. CI runs tests and ruff on push without game files
expected: CI runs tests and ruff on push without game files
result: pass
source: automated
coverage_id: D5

### 7. compose mounts third_party read-only at its own in-repo path; every protected mount is :ro
expected: compose mounts third_party read-only at its own in-repo path; every protected mount is :ro
result: pass
source: automated
coverage_id: D1

### 8. Inside the container /work/orig, /work/watcom, /work/third_party(/watcom) are not writable
expected: Inside the container /work/orig, /work/watcom, /work/third_party(/watcom) are not writable
result: pass
source: automated
coverage_id: D2

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
