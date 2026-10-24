---
phase: 05-split-and-first-matches
reviewed: 2026-10-24T05:46:13Z
depth: standard
files_reviewed: 74
files_reviewed_list:
  - config/tacp/boundaries.csv
  - config/tacp/functions.csv
  - config/tacp/symbols.csv
  - config/tacp/units.csv
  - config/ufo2p/boundaries.csv
  - config/ufo2p/functions.csv
  - config/ufo2p/symbols.csv
  - config/ufo2p/units.csv
  - configure.py
  - docker/Dockerfile
  - docs/coding-style.md
  - docs/learnings.md
  - docs/matching.md
  - docs/superpowers/specs/2026-10-19-reverseapoc-design.md
  - docs/toolchain.md
  - docs/tools.md
  - docs/workflow.md
  - include/common.h
  - include/watcom_compat.h
  - pyproject.toml
  - src/tacp/u_00054f20.c
  - src/ufo2p/u_000a34f0.c
  - tests/conftest.py
  - tests/elfread.py
  - tests/omfimage.py
  - tests/relocpair.py
  - tests/test_asm.py
  - tests/test_check.py
  - tests/test_check_real.py
  - tests/test_compiler.py
  - tests/test_configure.py
  - tests/test_discover.py
  - tests/test_discover_real.py
  - tests/test_elf.py
  - tests/test_functions.py
  - tests/test_functions_lib_real.py
  - tests/test_functions_real.py
  - tests/test_ghidra.py
  - tests/test_ghidra_real.py
  - tests/test_hygiene.py
  - tests/test_land.py
  - tests/test_le.py
  - tests/test_lint.py
  - tests/test_objdiff_real.py
  - tests/test_omf.py
  - tests/test_omf2elf.py
  - tests/test_omf2elf_real.py
  - tests/test_relocs.py
  - tests/test_score.py
  - tests/test_stub_real.py
  - tests/test_symbols.py
  - tests/test_target.py
  - tests/test_units.py
  - tests/test_x86.py
  - tools/reverseapoc/asm.py
  - tools/reverseapoc/check.py
  - tools/reverseapoc/cli.py
  - tools/reverseapoc/compiler.py
  - tools/reverseapoc/discover.py
  - tools/reverseapoc/elf.py
  - tools/reverseapoc/functions.py
  - tools/reverseapoc/ghidra.py
  - tools/reverseapoc/ghidra_scripts/ExportDrafts.java
  - tools/reverseapoc/ghidra_scripts/ExportFunctions.java
  - tools/reverseapoc/land.py
  - tools/reverseapoc/lint.py
  - tools/reverseapoc/omf.py
  - tools/reverseapoc/omf2elf.py
  - tools/reverseapoc/relocs.py
  - tools/reverseapoc/score.py
  - tools/reverseapoc/symbols.py
  - tools/reverseapoc/target.py
  - tools/reverseapoc/units.py
  - tools/reverseapoc/x86.py
findings:
  critical: 0
  warning: 1
  info: 5
  total: 6
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-10-24T05:46:13Z
**Depth:** standard
**Files Reviewed:** 74
**Status:** issues_found

## Summary

Scope: the phase's changes since 688168c. The match oracle (`relocs.py`, `check.py`, `land.py`)
and the D-12 parser in `configure.py` were read line by line. The other tools modules were read
in full. Tests, docs and the generated CSVs were spot-checked. The CSVs were loaded through
their own readers: headers are exact, the rows parse, `check_unit_assignment` reports no
problem, no unit is unassigned, and boundaries.csv has no missing verdict, for both EXEs.

The oracle was probed adversarially, not just read:

- **Probes on the synthetic pair** (`tests/relocpair.py`): a wrong own-segment target inside the
  checked function, duplicate own-public entries, and a target at an own public's end.
- **Real compiler** (wcc386 10.6 on the host, objects under the gitignored `build/`, removed
  afterwards): a unit with a `static` helper, and a unit with a `switch` jump table, to see the
  fixups Watcom really emits.
- **D-12 parser**: backslash line continuations.
- **Tests**: `tests/test_relocs.py`, `test_check.py`, `test_land.py`, `test_configure.py`,
  `test_symbols.py` and `test_omf2elf.py` pass (271 passed, 3 skipped).

**No path was found that makes a non-matching or unchecked function report as matched or land.**
Every edge case probed either fails the relocation check or is refused one layer up:

- the unit account in `check.account_unit` (exported XOR marked, no stray public);
- the length rule against the containing public;
- omf2elf's refusals.

One gate-integrity hole remains (WR-01): `check` writes the same object files ninja owns, so
`ninja verify` can land objects that were built with flags the committed `config/cflags.txt`
does not produce. The Info items record two oracle limitations, demonstrated with the real
compiler. They fail closed, but they will surprise the Phase 6 driver.

## Warnings

### WR-01: `check` overwrites ninja's unit objects with objects built under its own `--cflags`/`--watcom-dir`, and `land`/`ninja verify` reuse any object on disk without checking where it came from

**File:** `tools/reverseapoc/check.py:673-674`, `tools/reverseapoc/check.py:710-715`, `tools/reverseapoc/cli.py:902-906`, `configure.py:446-449`

**Issue:** `check_source` compiles to `UnitPaths.of(build_dir, ...).obj`, which is
`build/<exe>/obj/<unit>.obj`. That is the same path as configure's `cc` edge output. It uses
`CompileOptions(cflags, watcom_manifest, watcom_dir, log)` from the command line, and
`land_all(..., compile_fn=compile_fn, options=options)` then recompiles every other unit of
both EXEs into the same ninja-owned paths with the same options.

After `reverseapoc check ufo2p/u_x --cflags experiment.txt` (or `--watcom-dir` pointing at
another tree), every `build/<exe>/obj/*.obj` was produced by uncommitted flags. Its mtime is
newer than its recorded inputs (src, `config/cflags.txt`, `config/watcom.toml`, headers), and
the command line is unchanged. So ninja treats the `cc` edge as clean and never recompiles it.

`ninja verify` (`_cmd_land` -> `land_all` with `compile_fn=None`) then lands those objects:

```python
elif not obj.is_file():
    raise CheckError(...)
```

and reports the SHA-1 as matching. The same happens when `reverseapoc land` runs outside ninja
with an object older than an edited source. `account_unit` even reads the current source text
against the stale object's publics.

The landed bytes are still byte-identical, so no wrong byte ships. But the zero-regression gate
then certifies "matches under the committed flags" (D-18: a non-default cell must become a
per-glob rule first), and that claim is false until a clean rebuild. A fresh clone or CI would
fail where the local `ninja verify` passed.

**Fix:** Keep check's objects apart from ninja's whenever its options differ from the defaults,
and make the land step refuse an object it cannot trace to the committed flags. For example:

```python
# check.py
def _obj_root(build_dir: Path, options: CompileOptions) -> Path:
    custom = any(v is not None for v in (options.cflags, options.watcom_dir,
                                          options.watcom_manifest))
    return Path(build_dir) / ("check" if custom else "") # build/check/<exe>/obj/...
```

Also do one of these:

- Write a provenance stamp beside each object (compiler spec + flags +
  `hash(config/cflags.txt)`) from `compile_source`'s result, and have `_land_exe` refuse an
  object whose stamp does not match the committed cflags/watcom manifest.
- At minimum, have `_land_exe` with `compile_fn=None` refuse an object older than its source or
  `config/cflags.txt`.

`check` itself can keep landing with its options, but its output should then say that the
splice used non-default flags.

## Info

### IN-01: A `static` function always fails `check`, and the messages do not say why

**File:** `tools/reverseapoc/check.py:405-407`, `tools/reverseapoc/relocs.py:235-238`

**Issue:** The real wcc386 10.6 was run on a unit with `static int helper(int)` and a caller.
`helper_` comes out as an LPUBDEF (`Public.local=True`), and the call is a self-relative fixup
to an EXTDEF named `helper_`, not a segment fixup. So the caller fails with
`unknown symbol helper_`, and the unit fails with `public helper_ is not a function of the
unit`. This fails closed and is correct for now: statics have no row name. But Phase 6/7 will
hit it on the first unit with a static, and nothing in docs/matching.md or docs/learnings.md
says that statics are unsupported. Note also that Watcom emits even intra-unit calls to
`func_X_` as extern fixups, so the `own_publics` path is used only for segment fixups (jump
tables, label addresses).

**Fix:** Record it in docs/learnings.md. Make the stray-public message say "a static (LPUBDEF)
function: give it its row's func_ name or keep the row INCLUDE_ASM" when `Public.local` is
true.

### IN-02: Every jump-table function is refused: wcc386 puts the table before the public, outside every own public

**File:** `tools/reverseapoc/relocs.py:213-218`, `tools/reverseapoc/check.py:254-264`

**Issue:** The real wcc386 10.6 was run on a 6-case `switch`. It places the 24-byte table at
`_TEXT+0`, puts the public `func_..._` at `_TEXT+0x18`, and emits a
`jmp cs:[eax*4+_TEXT+0]` fixup. The relocation check computes t=0, which lies in no own public
(`own_publics` covers only [first public, ...)), so it refuses with "needs the unit's
public-to-row map". This fails closed and matches the deferral in 05-CONTEXT (jump-table
pairing waits for Phase 6/7). Note for that work: the fix has to map the data-in-code row of a
leading table (`_D_` row, `KIND_DATA_IN_CODE`) to its segment span. Widening own-public sizes
would be the wrong fix: it would bring back the layout assumption that
`test_own_segment_layout_coincidence_is_not_trusted` forbids.

**Fix:** None now. Carry this probe into the Phase 6/7 plan as the acceptance case.

### IN-03: `check` skips the D-12 source checks for a unit with no game or thunk rows

**File:** `tools/reverseapoc/check.py:393`

**Issue:** `marks = source_marks(text, rows) if required else SourceMarks(...)`. For a
runtime-only unit (the 05-18 cmain386 pair path), a refused conditional (`#ifdef`) or a marker
naming another unit's function is not reported by `check`. configure.py still refuses the file
(`check_unit_source` runs the conditional check unconditionally), so ninja catches it.

**Fix:** Always call `source_marks` and keep only its `problems` when `required` is empty.

### IN-04: `configure.py --config DIR` swaps the CSVs but not the manifest

**File:** `configure.py:622`

**Issue:** `collect_units` calls `load_manifest()` with no argument, so it reads
`config/targets.toml` of the repo even when `--config` points elsewhere. The regeneration
command passes `--config` back, so a non-default config dir silently mixes two trees.

**Fix:** `load_manifest(config / "targets.toml")` when that file exists, else the default.

### IN-05: The committed-CSV address parser accepts more than `0x%08X`

**File:** `tools/reverseapoc/functions.py:194-199`

**Issue:** `int(cell, 16)` accepts `-0x10`, `0x1_0` and surrounding whitespace, so a hand edit
of units.csv, symbols.csv or boundaries.csv with a negative or underscored address is read
silently. The writers always emit `0x%08X`. ghidra.py already validates with `_HEX_CELL`.

**Fix:** `if not re.fullmatch(r"0x[0-9A-F]{8}", cell): raise ValueError(...)` before `int()`.

## Deferred Minors Triage

Verified against the current tree. "Still present" means the reviewer's observation still holds.
Probes in the review session:

- **Synthetic pair (relocpair):** (a) duplicate own publics, (b) a target at an own public's
  end, (c) a wrong target inside the checked function.
- **Real compiler (wcc386 10.6):** a static helper, and a switch.
- **D-12 parser:** three backslash-continuation texts.

| # | Item | file:line (current) | Still present? | Verdict | Reason |
|---|------|---------------------|----------------|---------|--------|
| 1 | "objdiff checks only one relocation per instruction" over-generalized | `.planning/spikes/005-objdiff-omf-elf/README.md:175`; `docs/toolchain.md:340` | yes | STAY-DEFERRED | Wording only. The gate does not rely on it (relocs.py is independent of objdiff), and toolchain.md:340 already names the observed instruction shape. |
| 2 | spike `Pair.module/segment: object`, `build_name_map` unannotated | `.planning/spikes/005-objdiff-omf-elf/spike.py:141-142,190` | yes | STAY-DEFERRED | Spike-local, not production code. |
| 3 | symbols.csv needs independent validation in production | `tools/reverseapoc/symbols.py:203-217` | yes (func rows must start a row; data rows unchecked) | STAY-DEFERRED | A wrong symbols.csv address cannot pass. Rule 4 compares `address_of` with the LE fixup `target_va` (segment-relative) or the original rel32 destination (self-relative), so a bad entry fails the check. |
| 4 | `PROJECT_INCLUDE` unused; `MARKER_PREFIX` used as a substring | `tools/reverseapoc/compiler.py:58`; `tests/test_stub_real.py:27,95` | yes | STAY-DEFERRED | Dead constant and a test name; no behaviour. |
| 5 | test_le duplicates MZ constants, bare `0x40`; test_hygiene `partition("==")` | `tests/test_le.py:53-54,64`; `tests/test_hygiene.py:354` | yes | STAY-DEFERRED | Test style. The hygiene parse fails closed. |
| 6a | `omf2elf._relocation` can raise `struct.error` | `tools/reverseapoc/omf2elf.py:273-280,295-302` | no | STAY-DEFERRED (fixed) | `_refuse_field` checks field bounds and the int32 addend range before any `_relocation` runs. |
| 6b | `_publics` accepts a public past the segment end, silently omits debug-segment publics | `tools/reverseapoc/omf2elf.py:203-219` | no | STAY-DEFERRED (fixed) | Both are refused. A public exactly at the end gets size 0, and check turns that into a RelocError, i.e. a failed check. |
| 6c | `tests/elfread.py` wraps on a reloc against symbol 0 | `tests/elfread.py:125-126` | no | STAY-DEFERRED (fixed) | Index 0 now raises. |
| 7a | `address_of` accepts the placeholder of an address symbols.csv renames | `tools/reverseapoc/symbols.py:174-176` | yes | STAY-DEFERRED | It resolves to the same address, so the relocation target is right. objdiff then sees different names (<100%), so `check` fails anyway. |
| 7b | symbols.csv data rows not range-checked | `tools/reverseapoc/symbols.py:203-217` | yes | STAY-DEFERRED | Same reason as #3. |
| 7c | `SYMBOL_KIND_FUNC` duplicates a `SYMBOL_KINDS` literal | `tools/reverseapoc/symbols.py:42`; `tools/reverseapoc/functions.py:90` | yes | STAY-DEFERRED | Naming hygiene. |
| 7d | `any()` scans in `_unit_follows`/`_symbol_follows` are O(n^2) | `tools/reverseapoc/functions.py:426-430,515-519` | yes | STAY-DEFERRED | Performance, out of v1 scope (n is about 400). |
| 8 | ExportDrafts `Long.parseLong` aborts; `toAddr(long)` uses the default space only | `tools/reverseapoc/ghidra_scripts/ExportDrafts.java:55-56` | yes | STAY-DEFERRED | `ghidra.py:298-311` validates every address before the script runs, and drafts are reading aids that never count as a match. |
| 9a | `LE_PAGE_SIZE` hard-coded | `tools/reverseapoc/score.py:40` | yes | STAY-DEFERRED | Scorer only (candidate ranking). The oracle uses le.fixups(), which handles straddlers itself. |
| 9b | `--top` check duplicated | `tools/reverseapoc/cli.py:525-526`; `tools/reverseapoc/score.py:344-345` | yes | STAY-DEFERRED | Redundant, harmless. |
| 9c | `_substitute` can rewrite a displacement equal to the raw fixup value | `tools/reverseapoc/asm.py:155-162` | yes | STAY-DEFERRED | Listings are a reading aid, never assembled. |
| 9d | `_has_chk` only checks the mnemonic `push` | `tools/reverseapoc/score.py:143-147` | yes | STAY-DEFERRED | Ranking heuristic. The call target must also be __CHK. |
| 10a | Frame method not checked | `tools/reverseapoc/relocs.py:274-288` | yes | STAY-DEFERRED | The bytes and targets are still verified. The frame affects only a link-time field value, and land keeps the original there. Not a fail-open for matched bytes. |
| 10b | `RelocResult` not tied to its row or bytes | `tools/reverseapoc/land.py:53-59`; `tools/reverseapoc/check.py:720-724` | yes | STAY-DEFERRED | The only producer builds `LandedFunction(d.row, d.ours, reloc)` from the same `Defined`. A mismatched pairing needs a new caller. |
| 10c | Bare LE kind numbers in tests | `tests/relocpair.py:43` (`fixup_record(7, ...)`) | yes | STAY-DEFERRED | Test style. |
| 10d | Byte-dump regex lowercase-only | `tests/test_relocs.py:35` | yes | STAY-DEFERRED | Test hygiene. Problems never format bytes. |
| 11 | ret, table, then non-start code absorbed into the function | `tools/reverseapoc/discover.py:321-336` | yes | STAY-DEFERRED | Boundary quality only. A row that is too long fails the length rule; it never makes a mismatch pass. |
| 12a | **ORACLE:** overlapping/duplicate own publics not refused | `tools/reverseapoc/relocs.py:137-144,198-203` | yes | STAY-DEFERRED | See "Oracle items 12 and 15 in detail" below. |
| 12b | **ORACLE:** no test that a target at an own public's end is refused | `tools/reverseapoc/relocs.py:198-203,213-218` | yes (no test) | STAY-DEFERRED | See below. |
| 12c | **ORACLE:** no test that fails a mismatched target inside the checked function | `tools/reverseapoc/relocs.py:211-212` | yes (no test) | STAY-DEFERRED | See below. |
| 13a | Dockerfile CONTAIN paragraph splits the "does NOT contain" list | `docker/Dockerfile:13-21` | yes | STAY-DEFERRED | Comment layout. |
| 13b | `lint.py` silently skips an explicit non-.c file | `tools/reverseapoc/lint.py:90-91` | yes | STAY-DEFERRED | ninja passes only `src/<exe>/<unit>.c`, and the stray-source rule refuses others. |
| 14 | tools.md GhidraMCP verdict "Use" but status "Later" | `docs/tools.md:16` | yes | STAY-DEFERRED | Doc consistency, no runtime effect. |
| 15 | **FAIL-OPEN:** backslash continuation not spliced in the D-12 parser | `configure.py:156-158,266-288` (used by `tools/reverseapoc/check.py:333-345`) | yes | STAY-DEFERRED | See below. |
| 16a | A test copies cli's version-selection logic | `tests/test_functions_real.py:123` | yes | STAY-DEFERRED | Test duplication. |
| 16b | `test_units_tile_the_code` skips without orig/ | `tests/test_functions_real.py:196-210` | yes | STAY-DEFERRED | Needs the code object of the real LE. This review ran `check_unit_assignment` over the committed CSVs without orig/ and found no problem. |
| 17a | A marked row with a non-code public counts as a stub | `tools/reverseapoc/check.py:396-400` | yes | STAY-DEFERRED | A stub is never landed, so the SHA-1 is safe. |
| 17b | check passes as stub some files configure refuses | `tools/reverseapoc/check.py:653-655` (`errors="replace"`) | yes | STAY-DEFERRED | configure refuses them, so no build.ninja is generated and `ninja verify` cannot run. |
| 17c | Stray-public rule also flags DATA publics | `tools/reverseapoc/check.py:405-407` | yes | STAY-DEFERRED | Fails closed; message wording only (see IN-01 for the static case). |
| 18a | Wrong stated reason why raw-field functions cannot pass | `tools/reverseapoc/target.py:34-35`; `docs/learnings.md:23` | yes | STAY-DEFERRED | The real compiler confirms that wcc386 emits a fixup for every call, even to a static, so the stated reason holds for compiled C. The actual guarantee is rule 4 (the target must be a nameable start equal to the original) plus rule 5. Reword when the files are next touched. No fail-open shown. |
| 18b | check JSON `raw_fields` per unit, not per function | `tools/reverseapoc/check.py:601-605` | yes | STAY-DEFERRED | Reporting granularity. |
| 18c | No end-to-end test of a new raw-field kind reaching a failing check_function | tests (none) | yes | STAY-DEFERRED | Covered by the rule 4/5 unit tests. A gap in test depth, not in the oracle. |
| 19a | toolchain.md "-s: consistent" should read tied/not separated | `docs/toolchain.md:166` | yes | STAY-DEFERRED | Doc wording. |
| 19b | u_00054f20.c `void` choice deserves a source comment | `src/tacp/u_00054f20.c:25-29` | yes | STAY-DEFERRED | The reasoning is in docs/learnings.md:18. A comment is an allowed edit to matched code at any time. |

### Oracle items 12 and 15 in detail

**12a, duplicate own publics.** The probe confirmed that duplicate entries make resolution
order-dependent: the last entry wins. Either outcome passes only when the original lands on the
chosen row, otherwise it fails closed. The only caller, `check.own_publics`
(check.py:254-264), sizes each entry to the next distinct offset, so it cannot produce
overlaps. Duplicates would need two PUBDEFs at one offset, which compiled C does not emit. Even
then, each duplicate is itself checked against its own row before anything lands.

**12b, target at an own public's end.** The probe returns refused with "needs the unit's
public-to-row map". Inside check.py, `t == end` is the next public's offset. Only a fixup into
trailing filler would map past a row, and C cannot produce one.

**12c, wrong target inside the checked function.** The probe fails as it should:
`_TEXT+0x5 resolves to 0x00010005, the original lands on 0x00010006`. Adding the three
probes as tests would be cheap.

**15, D-12 backslash continuation.** The probe confirmed that a marker or definition on the
continuation line of `// ...\` or `#define ...\` counts as live. It cannot make an unchecked
function pass, because `check.account_unit` (check.py:396-404) compares the parse with the
compiled object's publics:

- A false marker only turns the row into a stub: never landed, original bytes kept, reported
  as STUB.
- A hidden definition is not compiled, so the object has no public for it, and the row becomes
  the mismatch "defined in C but not exported", which is refused.
- A false marker next to a real export becomes the mismatch "both".

**MUST-FIX-BEFORE-PHASE-DONE:** none. No deferred minor was shown to let a non-matching or
unchecked function pass `check` or land. The two flagged items (12a-c, 15) are fail-closed for
the reasons above.

---

_Reviewed: 2026-10-24T05:46:13Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
