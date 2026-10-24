---
status: complete
phase: 05-split-and-first-matches
source: [05-VERIFICATION.md]
started: 2026-10-24T07:40:00Z
updated: 2026-10-24T20:02:00.152Z
---

## Current Test

[testing complete]

## Tests

### 1. D-16 owner read of the two first matches
expected: Open src/ufo2p/u_000a34f0.c and src/tacp/u_00054f20.c next to `docker compose run --rm -T build bash -lc "uv sync --locked && uv run reverseapoc check ufo2p/u_000a34f0 --json"` (and tacp/u_00054f20). The C says what the function does in C89 with no inline asm or code-emitting pragma; the check JSON says ok, objdiff 100.0, reloc ok, bytes ok, both splices ok.
result: pass
note: Both checks re-run in the container on 2026-10-24 exit 0 with ok true. The matched functions are func_000A3980 (13 bytes) and func_00055080 (11 bytes): objdiff 100.0, reloc ok, 0 differing bytes, and both splices SHA-1 identical. The other functions in each unit are stubs. The placeholder names func_/D_ follow docs/coding-style.md ("a placeholder is better than a guess"). Naming is Phase 7 work; see Deferred Follow-Ups.

### 2. Accept the Docker image size and capstone 5.0.9
expected: The owner accepts the image with the Ghidra + JDK + clang layer (898,389,257 bytes after the D-20 strip) and capstone 5.0.9 as the first runtime dependency, or asks for a change.
result: pass
note: 898,389,257 bytes is the whole reverseapoc-build:local image (docker image inspect), up from 300,640,359 before 05-12. capstone is not in the image; `uv sync --locked` installs it into the reverseapoc_uv-venv volume (/opt/venv), pinned by hash in uv.lock.

### 3. Review the 7 hand verdicts in boundaries.csv
expected: Each hand verdict and its reason is right: config/ufo2p/boundaries.csv (1 ghidra, 1 capstone) and config/tacp/boundaries.csv (4 ghidra, 1 capstone), read against the gitignored listings (`uv run reverseapoc asm <EXE> --only <addr>`).
result: pass
note: The 7 rows are the only disagreements with no LE evidence that the runtime rule does not settle (evidence column empty). 2 capstone (shared exit blocks 0x0007BDB7 / 0x00028CA7) and 5 ghidra (reached through a stub or thunk, or called from code the capstone descent did not reach).

### 4. Decide on the superseded 05-08 truth (raw fields instead of refusal)
expected: The owner accepts that build_target leaves a branch or off32 field whose destination is in no functions.csv row (or outside the code object) raw and lists it in raw_fields (since e5120a9, plan 05-18), instead of refusing the unit as 05-08 planned, and an `overrides:` entry is added to 05-VERIFICATION.md; or asks for the refusal back. The relocation check still fails such references (relocs rules 4/5), so no false match is possible on them.
result: pass
note: Owner accepted the deviation; the overrides entry is in 05-VERIFICATION.md frontmatter (accepted 2026-10-24T19:56:37Z). At HEAD all 841 units cut with raw fields none. Milestone 1 converts only the functions in config/mechanics.toml (Phase 7); the others stay stubs.

### 5. Decide on the asm listing name collision (`_Alphabet`)
expected: The owner accepts as a known limitation that `uv run reverseapoc asm UFO2P.EXE` writes 1891 files for 1892 rows because two runtime rows share the ambiguous name `_Alphabet` (UFO2P rt_itoa 0x000C06FA and rt_ltoa 0x000C92CD; TACP 0x000C2826 / 0x000CD0AF) and the second overwrites asm/<exe>/_Alphabet.s; or asks for a fix (fall back to `<kind>_<start>.s` for a name SymbolTable.ambiguous lists).
result: pass
note: Accepted as a known limitation for Phase 5. The fix is deferred to Phase 6, where agents start relying on asm/; see Deferred Follow-Ups.

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Deferred Follow-Ups

- test: 1
  idea: "Phase 7's success criterion 4 says readlint must fail on FUN_, sub_ and DAT_ names. Those are Ghidra's placeholder forms. Our placeholders are func_ and D_, so a readlint built to that wording would let these two functions through unnamed. Phase 7 hasn't been planned, so this is cheap to fix now. Test 1 passes and the readlint problem is logged in the UAT under Deferred Follow-Ups for Phase 7: readlint must also reject func_XXXXXXXX / D_XXXXXXXX placeholders, not only FUN_/sub_/DAT_."
  target_phase: 7
  deferred_at: 2026-10-24
- test: 5
  idea: "Can we pass and defer the fix to Phase 6? So Phase 6 will fix it plus do the work where agents will rely on asm/ heavily. Fix: `asm` writes a name that SymbolTable.ambiguous lists (_Alphabet: UFO2P 0x000C06FA / 0x000C92CD, TACP 0x000C2826 / 0x000CD0AF) as `<kind>_<start>.s`, so no listing overwrites another (one file per functions.csv row), with a test."
  target_phase: 6
  deferred_at: 2026-10-24

## Gaps
