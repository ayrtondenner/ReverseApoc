---
status: testing
phase: 05-split-and-first-matches
source: [05-VERIFICATION.md]
started: 2026-10-24T07:40:00Z
updated: 2026-10-24T07:40:00Z
---

## Current Test

number: 1
name: D-16 owner read of the two first matches
expected: |
  src/ufo2p/u_000a34f0.c and src/tacp/u_00054f20.c say what each function does in plain C89 with no
  inline asm or code-emitting pragma, and `check ufo2p/u_000a34f0 --json` / `check tacp/u_00054f20 --json`
  (run in the container) say ok, objdiff 100.0, reloc ok, bytes ok, both splices ok.
awaiting: user response

## Tests

### 1. D-16 owner read of the two first matches
expected: Open src/ufo2p/u_000a34f0.c and src/tacp/u_00054f20.c next to `docker compose run --rm -T build bash -lc "uv sync --locked && uv run reverseapoc check ufo2p/u_000a34f0 --json"` (and tacp/u_00054f20). The C says what the function does in C89 with no inline asm or code-emitting pragma; the check JSON says ok, objdiff 100.0, reloc ok, bytes ok, both splices ok.
result: [pending]

### 2. Accept the Docker image size and capstone 5.0.9
expected: The owner accepts the image with the Ghidra + JDK + clang layer (898,389,257 bytes after the D-20 strip) and capstone 5.0.9 as the first runtime dependency, or asks for a change.
result: [pending]

### 3. Review the 7 hand verdicts in boundaries.csv
expected: Each hand verdict and its reason is right: config/ufo2p/boundaries.csv (1 ghidra, 1 capstone) and config/tacp/boundaries.csv (4 ghidra, 1 capstone), read against the gitignored listings (`uv run reverseapoc asm <EXE> --only <addr>`).
result: [pending]

### 4. Decide on the superseded 05-08 truth (raw fields instead of refusal)
expected: The owner accepts that build_target leaves a branch or off32 field whose destination is in no functions.csv row (or outside the code object) raw and lists it in raw_fields (since e5120a9, plan 05-18), instead of refusing the unit as 05-08 planned, and an `overrides:` entry is added to 05-VERIFICATION.md; or asks for the refusal back. The relocation check still fails such references (relocs rules 4/5), so no false match is possible on them.
result: [pending]

### 5. Decide on the asm listing name collision (`_Alphabet`)
expected: The owner accepts as a known limitation that `uv run reverseapoc asm UFO2P.EXE` writes 1891 files for 1892 rows because two runtime rows share the ambiguous name `_Alphabet` (UFO2P rt_itoa 0x000C06FA and rt_ltoa 0x000C92CD; TACP 0x000C2826 / 0x000CD0AF) and the second overwrites asm/<exe>/_Alphabet.s; or asks for a fix (fall back to `<kind>_<start>.s` for a name SymbolTable.ambiguous lists).
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
