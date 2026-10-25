# Phase 6 deferred-item ledger (DI-01..DI-37)

One row per item from the `<deferred_inventory>` of 06-CONTEXT.md (rulings D-38..D-43). The phase gate (plan 06-27)
walks this table row by row.

Status values:

- `closed`: closed by the commit(s) in the Commit(s) column. Each hash comes from the closing plan's SUMMARY and
  resolves with `git cat-file -e`.
- `ruled (D-xx)`: settled by the named owner ruling in 06-CONTEXT.md. No code change is owed in Phase 6.
- `pending 06-27`: closes only after the owner's pilot run (plan 06-27).
- `planned 06-NN`: the closing plan has not been executed or merged at the time of writing.

Built at base `5d391a9` (after wave 6: plans 06-01..06-16 merged). Wave 7 (06-17..06-22) was running in parallel, so
its rows say `planned`. Where a closing plan had fix rounds, the Commit(s) column lists the task commits and the
fix-round commits that touched the item; the full list is in that plan's SUMMARY.

## A. Phase 6 targets and driver blockers

| ID | Item | Closed by | Commit(s) | Status |
|----|------|-----------|-----------|--------|
| DI-01 | Backlog 999.3: `asm` writes a name SymbolTable.ambiguous lists (`_Alphabet`) as `<kind>_<start>.s`, one listing per functions.csv row | 06-06 Task 1 | a56080d, 6d535c1 | closed |
| DI-02 | 05 IN-02: `check` refused every jump-table function; a leading table's data-in-code row is now paired with its span | 06-10 Task 1; container proof in 06-16 (build/gate/06-seed/03-real.log, check_tables_real with objdiff, recorded in its SUMMARY) | 930a173, a314bb9; 0f30b1b | closed |
| DI-03 | `static` functions could not pass `check`; row-named statics and their callers now pass (no code change needed, pinned by tests) | 06-10 Task 2; container proof in 06-16 (same log) | 55edbe4, 2efa21c; 0f30b1b | closed |
| DI-04 | 05 minors 12a-c (oracle): duplicate/overlapping own publics refused (12a); target at a public's end and wrong target inside the function pinned (12b, 12c) | 06-03 | 5eab11a, 426e8ff | closed |
| DI-05 | 05 minor 15: backslash continuation fail-open in the D-12 parser | 06-03 | dee1491, a71dd7a | closed |
| DI-06 | WR-01 hardening: (a) `cc` provenance stamp and ninja land's stale-object refusal; (b) `check --src/--config OTHER` compiles under build/check-custom; (c) build.ninja rules carry a non-default `--config` tree | (a) 06-09 Tasks 2-3; (b) 06-09 Task 1; (c) 06-03 | (a) 8fcd36d, 3c56067, f8c8e48, 3533764; (b) 52e83b1, 47546f1; (c) 19a4f5b, de94a5b | closed |
| DI-07 | AGT-05 hooks also guard the cc wrapper and config/cflags.txt (matching layer denies every write but the claimed unit) | 06-12 Task 3 | a53ebcc, 1c1a616 | closed |
| DI-08 | README.md progress placeholder "coming in Phase 6" | 06-22 | none yet | planned 06-22 |
| DI-09 (spike) | Phase 5 deferral: the decomp.wtf INCLUDE_ASM spike (spike 006, verdict INVALIDATED; own agent layer per D-03/D-04) | 06-01 | f0f79ea, b3b4636 | closed |
| DI-09 (GhidraMCP) | Phase 5 deferral: GhidraMCP in the context pack | D-41 (DI-21 part: GhidraMCP becomes "Later (Phase 7 or later)"; the tools.md row edit is 06-20's) | none (ruling) | ruled (D-41) |
| DI-09 (sweeps) | Phase 5 deferral: `-zp`/`-zm`/`-fp` and 11.0a/b flag sweeps | D-41: they run only if a pilot miss needs them; recorded in PROJECT.md Key Decisions by 06-21 | none (ruling) | ruled (D-41) |
| DI-09 (GUI guide) | Phase 5 deferral: optional Ghidra GUI guide | D-41: no Ghidra GUI guide in Phase 6; recorded in PROJECT.md Key Decisions by 06-21 | none (ruling) | ruled (D-41) |
| DI-10 | Phase 6 builder decisions (scorer, hooks, progress file names, Nigel vs Python driver) | D-05..D-29 (decided in discuss-phase); PROJECT.md "Left to the builder" lines struck through by 06-21 | none (ruling) | ruled (D-05..D-29) |

## B. Small cleanups

| ID | Item | Closed by | Commit(s) | Status |
|----|------|-----------|-----------|--------|
| DI-11 | Backlog 999.1: docs/toolchain.md cc.log bullet says `--log` names a file, quotes both platforms' messages, device branch covers directories | 06-07 Task 1 | b328679 | closed |
| DI-12 | 04 IN-08: `--log <existing dir>` compiled, then failed and left the object; now refused before the compile | 06-07 Task 1 | 711b829, b328679 | closed |
| DI-13 | 04 IN-09: an unwritable log directory failed a good compile; `<log>.lock` is now probed before the compile | 06-07 Task 1 | 711b829, b328679 | closed |
| DI-14 | 04 IN-10: `_reap` kills only the Python `cc` (docstring says so); `cc_root` fails on a leftover directory | 06-07 Task 2 | 1b34ae3 | closed |
| DI-15 | 04 IN-11: the `/dev/null` sidecar test hid its regression when run as root; it now fails instead of skipping | 06-07 Task 2 | 1b34ae3 | closed |
| DI-16 | 04 IN-12: the IN-03 wording did not reach the `_append_log` docstring | 06-07 Task 2 | d24e14d | closed |
| DI-17 | 04 IN-13: a CLI test's `assert not obj.exists()` could not fail; it now writes the object first and checks it survives | 06-07 Task 2 | 1b34ae3 | closed |
| DI-18 | 04 IN-04: private `splice._write_atomic` imported by 7 modules; now public `fileio.write_atomic` (D-41) | 06-02 Tasks 1-2 | 1681fdc, cfb84d4, f90097f, 732a537 | closed |
| DI-19 row 1 (spike) | "objdiff checks only one relocation per instruction" over-generalized: spike 005 README:175 | 06-05 Task 2 | 191d094 | closed |
| DI-19 row 1 (toolchain) | the same over-generalization: the docs/toolchain.md part | 06-20 | none yet | planned 06-20 |
| DI-19 row 2 | spike 005 `Pair.module/segment: object`, `build_name_map` unannotated | 06-05 Task 2 | 191d094 | closed |
| DI-19 row 3 | symbols.csv data rows validated in production (range check) | 06-02 Task 3 | 863114d, bc84d08 | closed |
| DI-19 row 4 | `PROJECT_INCLUDE` unused; `MARKER_PREFIX` used as a substring | 06-07 Task 2 | 1b34ae3, d24e14d | closed |
| DI-19 row 5 | test_le duplicated MZ constants and a bare `0x40`; test_hygiene `partition("==")` | 06-05 Task 2 | 9d817e4, 02031f8, d7e4601 | closed |
| DI-19 rows 7a-d | `address_of` accepts a renamed placeholder (7a); data rows not range-checked (7b); `SYMBOL_KIND_FUNC` literal (7c); O(n^2) `any()` scans (7d) | 06-02 Task 3 | 863114d, bc84d08 | closed |
| DI-19 row 8 | ExportDrafts `Long.parseLong` aborts the batch; `toAddr(long)` default space only | 06-04 Task 2 and fix round 1 | dbc3d42, 8078685, 783ed9a | closed |
| DI-19 rows 9a-d | `LE_PAGE_SIZE` hard-coded (9a); `--top` check duplicated (9b); `_substitute` rewrites a scale (9c); `_has_chk` mnemonic-only (9d) | 06-06 Task 2 | 940b974, ec55400 | closed |
| DI-19 rows 10a-d | frame method not checked (10a, 06-03); `RelocResult` not tied to its row or bytes (10b, 06-08); bare LE kind numbers in tests (10c, 06-03); byte-dump regex lowercase-only (10d, 06-03) | 06-03; 06-08 Task 1 | 5eab11a, 426e8ff; 80c5789, 884e810 | closed |
| DI-19 row 11 | ret, table, then non-start code absorbed into the function (owner option (a), functions.csv regenerated) | 06-04 Task 1 and fix round 1 | 5cf5392, f4e63a4, 47b633d, a2678ad, 446a7e9 | closed |
| DI-19 rows 13a-b | Dockerfile "does not contain" list split (13a, 06-05); `lint.py` silently skips an explicit non-.c file (13b, 06-04) | 06-05 Task 2; 06-04 Task 2 | d8be60c; dbc3d42, 8078685 | closed |
| DI-19 row 14 | docs/tools.md GhidraMCP verdict "Use" but status "Later" | 06-20 | none yet | planned 06-20 |
| DI-19 rows 16a-b | a test copies cli's version-selection logic (16a); `test_units_tile_the_code` skips without orig/ (16b) | 06-04 Task 3 and fix rounds 1-2 | f0dc6bf, 84033a0, 7a640d8, ed30004, 474a60a | closed |
| DI-19 rows 17a-c | marked row with a non-code public counted as a stub (17a); non-strict UTF-8 read (17b); stray DATA public message (17c) | 06-09 Task 3 | f8c8e48, 3533764 | closed |
| DI-19 rows 18a-c | raw-field reasoning stated per kind (18a, 06-08); per-function `raw_fields` in the check JSON (18b, 06-09); end-to-end raw-field test (18c, 06-08) | 06-08 Task 2 and fix round 1; 06-09 Task 3 | c6f004e, b10cdbc, fda9fc3, 8293123; f8c8e48, 3533764 | closed |
| DI-19 row 19a | docs/toolchain.md "-s: consistent" should read tied / not separated | 06-20 | none yet | planned 06-20 |
| DI-19 row 19b | u_00054f20.c `void` choice gets a source comment (comment-only, token-identical) | 06-05 Task 1 | 43daac3 | closed |
| DI-20 | Stale doc text: matching.md:57,63; learnings.md:86; toolchain.md:374 and :166 | 06-20 | none yet | planned 06-20 |
| DI-21 | Owner-left doc items: tools.md:53 ast-grep, design spec :76, README :62/:139, tools.md:16 GhidraMCP (D-41) | 06-20 (docs) and 06-22 (README) | none yet | planned 06-20, 06-22 |
| DI-22 | Phase 1 carry-overs: toolchain.md:13 SMKP entry point obj1:0x6CB0; .dockerignore `*.IMG`, `*.CUE`, `*.mdf` | 06-20 | none yet | planned 06-20 |
| DI-23 | 04 security observations T-04-15/16 (10.5 real proofs), T-04-17 (failing assert printed bytes), T-04-36 (unlogged scratch checks) | 06-07 Tasks 2-3 and fix round 1; 04-SECURITY.md closure recorded by 06-21 Task 2 | 1b34ae3, e23cbcc, fdf0e0a | closed |
| DI-24 | Uncovered code: TACP ~0x29D4D..0x31040 and the UFO2P 3-byte tail at 0x000CFADA have no functions.csv rows | D-40 (counts as unmatched now; rows added when matching reaches it); D-50 (shown as an "uncovered" segment, implemented by 06-18) | none (ruling) | ruled (D-40, D-50) |
| DI-25 (wording) | Compiler candidates unseparated: fix the stale toolchain.md wording | 06-20 | none yet | planned 06-20 |
| DI-25 (evidence) | Compiler candidates unseparated: log the evidence from each pilot match | 06-27 (after the owner's pilot run) | none yet | pending 06-27 |

## C. Paperwork

| ID | Item | Closed by | Commit(s) | Status |
|----|------|-----------|-----------|--------|
| DI-26 | T-04-13: owner signed A1 off in 04-UAT.md, but 04-SECURITY.md still said pending | 06-21 Task 2 | none yet | planned 06-21 |
| DI-27 | 04-VALIDATION.md sign-off boxes unticked and "Approval: pending" against a validated frontmatter | 06-21 Task 2 | none yet | planned 06-21 |
| DI-28 | 05-VERIFICATION.md body said "Status: human_needed", frontmatter passed | 06-21 Task 2 | none yet | planned 06-21 |
| DI-29 | Spike 005 VALIDATED verdict needs the owner's recorded sign-off (owner line at the pilot checkpoint, D-41) | 06-26 (owner line) and 06-27 | none yet | pending 06-27 |
| DI-30 | STATE.md Phase 5 blocker repeats its RESOLVED text; Deferred Items table said none | 06-21 Task 3 | none yet | planned 06-21 |
| DI-31 | Backlog 999.2: Phase 7 SC4 (DEC-04) reworded so readlint also rejects `func_XXXXXXXX` / `D_XXXXXXXX` in a matched unit (readlint itself stays Phase 7) | 06-21 Task 3 | none yet | planned 06-21 |

## D. Owner-only

| ID | Item | Closed by | Commit(s) | Status |
|----|------|-----------|-----------|--------|
| DI-32 | Primary build: installed build vs CD v1.00; OpenApoc offsets re-located before reuse | D-42 (installed build primary, CD v1.00 cross-reference only, offsets re-located by signature in Phase 7, twin matching after Phase 7); recorded in PROJECT.md Key Decisions by 06-21 Task 3 | none (ruling) | ruled (D-42) |
| DI-33 | config/watcom.toml notes on lines 37 and 106 said "LE"; now "LX" (D-43, D-47, owner-authorized one-time edit) | 06-07 Task 3 | 28342e1 | closed |

## E. Listing work (owner, 2026-10-24)

| ID | Item | Closed by | Commit(s) | Status |
|----|------|-----------|-----------|--------|
| DI-34 (feed) | decomphub.progress.json (progress-v1) written by progress.py (D-29) | 06-18 | none yet | planned 06-18 |
| DI-34 (verification) | DecompHub maintainer verification file (D-31) | 06-22 | none yet | planned 06-22 |
| DI-34 (CI POST) | CI POST to the DecompHub refresh endpoint behind a repo variable (D-30) | 06-24 | none yet | planned 06-24 |
| DI-35 | Awesome-list PR drafts, files only; the owner opens or approves each (D-33) | 06-19 | none yet | planned 06-19 |
| DI-36 | decomp.me msdos preset request draft; the owner files it by hand (D-33) | 06-19 | none yet | planned 06-19 |
| DI-37 (links, notes) | .recomp.json links and notes (D-32) | 06-22 | none yet | planned 06-22 |
| DI-37 (status) | .recomp.json status after the pilot (D-32) | 06-27 | none yet | pending 06-27 |
