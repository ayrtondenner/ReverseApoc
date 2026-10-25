---
phase: 05-split-and-first-matches
verified: 2026-10-24T07:30:00Z
status: passed
score: 4/4 roadmap success criteria verified; 13/13 requirements satisfied; 2 plan-level truths need an owner decision
covered_files: [".gitignore",".planning/phases/05-split-and-first-matches/05-01-PLAN.md",".planning/phases/05-split-and-first-matches/05-01-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-02-PLAN.md",".planning/phases/05-split-and-first-matches/05-02-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-03-PLAN.md",".planning/phases/05-split-and-first-matches/05-03-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-04-PLAN.md",".planning/phases/05-split-and-first-matches/05-04-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-05-PLAN.md",".planning/phases/05-split-and-first-matches/05-05-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-06-PLAN.md",".planning/phases/05-split-and-first-matches/05-06-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-07-PLAN.md",".planning/phases/05-split-and-first-matches/05-07-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-08-PLAN.md",".planning/phases/05-split-and-first-matches/05-08-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-09-PLAN.md",".planning/phases/05-split-and-first-matches/05-09-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-10-PLAN.md",".planning/phases/05-split-and-first-matches/05-10-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-11-PLAN.md",".planning/phases/05-split-and-first-matches/05-11-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-12-PLAN.md",".planning/phases/05-split-and-first-matches/05-12-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-13-PLAN.md",".planning/phases/05-split-and-first-matches/05-13-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-14-PLAN.md",".planning/phases/05-split-and-first-matches/05-14-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-15-PLAN.md",".planning/phases/05-split-and-first-matches/05-15-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-16-PLAN.md",".planning/phases/05-split-and-first-matches/05-16-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-17-PLAN.md",".planning/phases/05-split-and-first-matches/05-17-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-18-PLAN.md",".planning/phases/05-split-and-first-matches/05-18-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-19-PLAN.md",".planning/phases/05-split-and-first-matches/05-19-SUMMARY.md",".planning/phases/05-split-and-first-matches/05-20-PLAN.md",".planning/phases/05-split-and-first-matches/05-20-SUMMARY.md","README.md","config/tacp/boundaries.csv","config/tacp/functions.csv","config/tacp/symbols.csv","config/tacp/units.csv","config/ufo2p/boundaries.csv","config/ufo2p/functions.csv","config/ufo2p/symbols.csv","config/ufo2p/units.csv","configure.py","docker/Dockerfile","docs/coding-style.md","docs/learnings.md","docs/matching.md","docs/superpowers/specs/2026-10-19-reverseapoc-design.md","docs/toolchain.md","docs/tools.md","docs/workflow.md","include/common.h","include/watcom_compat.h","pyproject.toml","src/tacp/u_00054f20.c","src/ufo2p/u_000a34f0.c","tests/conftest.py","tests/elfread.py","tests/omfimage.py","tests/relocpair.py","tests/test_asm.py","tests/test_check.py","tests/test_check_real.py","tests/test_compiler.py","tests/test_configure.py","tests/test_discover.py","tests/test_discover_real.py","tests/test_elf.py","tests/test_functions.py","tests/test_functions_lib_real.py","tests/test_functions_real.py","tests/test_ghidra.py","tests/test_ghidra_real.py","tests/test_hygiene.py","tests/test_land.py","tests/test_le.py","tests/test_lint.py","tests/test_objdiff_real.py","tests/test_omf.py","tests/test_omf2elf.py","tests/test_omf2elf_real.py","tests/test_relocs.py","tests/test_score.py","tests/test_stub_real.py","tests/test_symbols.py","tests/test_target.py","tests/test_units.py","tests/test_x86.py","tools/reverseapoc/asm.py","tools/reverseapoc/check.py","tools/reverseapoc/cli.py","tools/reverseapoc/compiler.py","tools/reverseapoc/discover.py","tools/reverseapoc/elf.py","tools/reverseapoc/functions.py","tools/reverseapoc/ghidra.py","tools/reverseapoc/ghidra_scripts/ExportDrafts.java","tools/reverseapoc/ghidra_scripts/ExportFunctions.java","tools/reverseapoc/land.py","tools/reverseapoc/lint.py","tools/reverseapoc/omf.py","tools/reverseapoc/omf2elf.py","tools/reverseapoc/relocs.py","tools/reverseapoc/score.py","tools/reverseapoc/symbols.py","tools/reverseapoc/target.py","tools/reverseapoc/units.py","tools/reverseapoc/x86.py","uv.lock"]
covered_digest: "v3:sha256:b15328d4e18b8c2597c4a071537614513d7bacd0e7b11ea7709edc636ba978f2"
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "build_target refuses a branch destination outside every functions.csv row"
    reason: "05-18 (e5120a9) keeps such fields raw and lists them in raw_fields so every unit stays cuttable (F11 principle, D-13); relocs.check_function still fails any reference into no row (rules 4/5), so nothing can pass on it"
    accepted_by: "ayrtondenner"
    accepted_at: "2026-10-24T19:56:37Z"
decision_coverage:
  honored: 20
  total: 20
  not_honored: []
deferred:
  - truth: "Jump-table functions can be checked and landed (IN-02: wcc386 puts the table before the public, outside every own public, so check refuses them)"
    addressed_in: "Phase 7"
    evidence: "Phase 7 goal: 'Every function behind the OpenApoc checklist items ... matched byte for byte ... by the Phase 6 driver at scale'; 05-REVIEW-DISPOSITION.md IN-02 deferred to Phase 6/7. Fails closed today (refused, never passed)."
human_verification:
  - test: "D-16 owner read: open src/ufo2p/u_000a34f0.c and src/tacp/u_00054f20.c next to `docker compose run --rm -T build bash -lc \"uv sync --locked && uv run reverseapoc check ufo2p/u_000a34f0 --json\"` (and tacp/u_00054f20)"
    expected: "The C says what the function does in C89 with no inline asm or code-emitting pragma, and the check JSON says ok, objdiff 100.0, reloc ok, bytes ok, both splices ok"
    why_human: "Readability and naming of matched C are an owner call; the oracle only decides the bytes"
  - test: "Accept the Docker image size (Ghidra + JDK + clang layer, 898,389,257 bytes after the D-20 strip) and capstone 5.0.9 as the first runtime dependency"
    expected: "Owner accepts both, or asks for a change"
    why_human: "Owner judgement (05-VALIDATION.md manual row, D-09)"
  - test: "Review the 7 hand verdicts in config/ufo2p/boundaries.csv (1 ghidra, 1 capstone) and config/tacp/boundaries.csv (4 ghidra, 1 capstone) against the gitignored listings"
    expected: "Each hand verdict and its reason is right"
    why_human: "Hand verdicts are a person's reading of listings; the tests only pin that they exist, carry a reason and survive regeneration"
  - test: "Decide on the superseded 05-08 truth: build_target was planned to REFUSE a branch destination outside every functions.csv row; since 05-18 (e5120a9) it leaves such fields raw and lists them in raw_fields (kinds `off32 to no row`, `branch to no row`, `branch outside the code object`)"
    expected: "Owner accepts the deviation (add an `overrides:` entry), or asks for the refusal back"
    why_human: "A plan truth was reversed by a later plan's recorded deviation, not by an orchestrator ruling; the orchestrator review approved it and the relocation check still fails such references (rules 4/5), but only the owner can accept a must-have change"
  - test: "Decide on the asm listing collision: `uv run reverseapoc asm UFO2P.EXE` reports 1892 listings but writes 1891 files, because two runtime rows are both named `_Alphabet` (rt_itoa 0x000C06FA and rt_ltoa 0x000C92CD; TACP likewise 0x000C2826 / 0x000CD0AF) and the second overwrites asm/<exe>/_Alphabet.s"
    expected: "Owner accepts it as a known limitation of the ambiguous runtime name, or asks for a fix (e.g. fall back to <kind>_<start>.s for a name SymbolTable.ambiguous lists)"
    why_human: "05-11 truth says one listing per functions.csv row; it holds for every game function but not for this one runtime data table; the impact is cosmetic for matching, so it is a judgment call"
---

# Phase 5: Split and first matches Verification Report

**Phase Goal:** The matching pipeline works end to end: functions are found and grouped into units, C compiles with the identified compiler, objdiff and an independent relocation check compare it to the target cut from the LE, and one hand-matched function per EXE splices back with both EXEs still SHA-1 identical.
**Verified:** 2026-10-24
**Status:** passed
**Owner sign-off:** the 2026-10-24 UAT passed 5/5 ([05-UAT.md](05-UAT.md), commit c988bed). The owner accepted the 05-08 deviation through the frontmatter `overrides:` entry (accepted_at 2026-10-24T19:56:37Z, commit 4491f04), and the frontmatter was set to `passed` in commit f96343f. Plan 06-21 updated this body line on 2026-10-25 to match (DI-28, D-41). The UAT settled the frontmatter's `human_verification` items, which were still open at verification time.
**Re-verification:** No, initial verification

## Evidence I produced myself (at HEAD 50bc3d0, after the review fix wave)

The gate logs under build/gate/05-evidence/ were written at 5403794, before the fix wave changed check.py, configure.py and functions.py, so I re-ran the decisive commands myself:

| Command (container unless marked) | Result |
|---|---|
| `uv run reverseapoc check ufo2p/u_000a34f0 --json` | exit 0; func_000A3980, 13 bytes, objdiff 100.0, reloc ok, bytes ok (0 differing); splice exactly UFO2P.EXE + TACP.EXE, both ok, SHA-1 e7488bf3... / 48ef0096... equal to config/targets.toml; 2 stubs; problems [] |
| `uv run reverseapoc check tacp/u_00054f20 --json` | exit 0; func_00055080, 11 bytes, objdiff 100.0, reloc ok, bytes ok; both splices ok with the manifest SHA-1s; 10 stubs |
| `uv run python configure.py && ninja && ninja lint && ninja verify` | exit 0; 841 units; REBUILD 3 EXEs == manifest; LAND UFO2P.EXE and TACP.EXE landed 1 each, SHA-1 == manifest (incremental: cc and lint stamps were up to date; the clean 846-edge build with CC and LINT edges is in build/gate/05-evidence/01-ninja.log) |
| `pytest tests/test_check_real.py tests/test_objdiff_real.py tests/test_functions_real.py tests/test_lint.py tests/test_omf2elf_real.py tests/test_stub_real.py tests/test_discover_real.py` | 46 passed, 0 skipped |
| host: `uv run reverseapoc asm UFO2P.EXE` | exit 0, "wrote 1892 listings"; 1891 files in asm/ufo2p (see `_Alphabet` warning) |
| host: `git ls-files` filter for asm/, build/, orig/, third_party/, objdiff.json, compile_commands.json, build.ninja, .o, .obj, CMAIN386 | nothing tracked |
| host: `uv run pytest -q -rs` + `uv run ruff check .` | 1605 passed, 26 skipped (platform reasons only), ruff clean |

## Goal Achievement

### Observable Truths (roadmap success criteria, the contract)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | functions.csv for both EXEs, from Ghidra 12.1.4 (headless, JDK 21, one LE loader in the image), cross-checked by capstone with every disagreement reconciled; functions grouped into units under config/<exe>/ (SPL-01..03) | ✓ VERIFIED | docker/Dockerfile has its own `AS ghidra` stage with both SHA-256 pins and `sha256sum -c`, OpenJDK 21 and clang 18 pins, LxLoader unpacked into Ghidra/Extensions. config/ufo2p/functions.csv 1892 rows, config/tacp/functions.csv 1874 rows, header `start,end,name,kind,unit,evidence`, generated-by line; every row has a unit. boundaries.csv: UFO2P 591 rows (589 rule, 1 ghidra, 1 capstone), TACP 497 (492 rule, 4 ghidra, 1 capstone), no empty verdict. units.csv 408 / 433 units (841 total). Drift test test_functions_real.py passed in the container at HEAD; test_ghidra_real.py passed in the container at the gate (09-rows.log SPL-01, 101 passed). |
| 2 | configure.py writes build.ninja, objdiff.json, compile_commands.json; ninja compiles units with the Phase 4 compiler under wibo; unmatched functions keep original bytes via the stub convention; per-function asm generated into gitignored asm/ by script; the C89 lint gate passes on src/ (SPL-04..06, SPL-12) | ✓ VERIFIED | configure.py rules cc, omf2elf, target, lint, asm, land, configure (generator = 1). Clean gate build: `CC src/ufo2p/u_000a34f0.c`, `CC src/tacp/u_00054f20.c`, 841 TARGET cuts, LINT both files ok. My HEAD run: exit 0. include/common.h defines `INCLUDE_ASM(name) extern int INCLUDE_ASM_##name`; check reports the marked rows as stubs, not landed, and both EXEs stay SHA-1 identical. `asm` verb wrote listings from orig/ into gitignored asm/ (warning: `_Alphabet` collision). lint.py LINT_FLAGS hold `-std=gnu89 -Werror=declaration-after-statement` and force-include include/watcom_compat.h; test_lint.py passed unskipped in the container. |
| 3 | omf2elf.py converts Watcom OMF (COMDAT, LIDATA, FIXUPP threads, BAKPAT, CEXTDEF) to ELF32 with pytest green; target ELFs cut from the LE carry relocations rebuilt from LE fixups (SPL-07, SPL-08) | ✓ VERIFIED | omf2elf.py handles COMDAT 0xC2/0xC3 (WEAK by selection), LIDATA, BAKPAT/NBKPAT, CEXTDEF, threads, with named refusals; tests test_comdat16_converts_to_a_weak_section, test_lidata_converts, test_bakpat_bytes_are_kept, test_cextdef_extern, test_fixup_through_thread_subrecords_converts_like_an_explicit_one, test_kitchen_sink_module; test_omf2elf_real passed in the container. target.py cuts from `load_flat(relocate=False)` with R_386_32 per off32 LE fixup and synthesized R_386_PC32; ninja cut all 841 units with "raw fields none; undecoded none". |
| 4 | For one function per EXE, `check` prints objdiff 100%, a passing relocation check and, after splicing with the original link-time value kept at each fixup site, both EXEs SHA-1 identical to config/targets.toml; a negative test with a wrong call or fixup target fails the relocation check where objdiff reports 100% (SPL-09..11, SPL-13) | ✓ VERIFIED | My container runs above (exit 0, both EXEs, manifest SHA-1s). FunctionCheck.ok requires objdiff == 100.0 AND reloc.ok AND bytes_ok; CheckResult.ok also requires every splice ok. land.build_patch keeps the original bytes under every field of either side and refuses an unchecked function. Negatives: tests/test_objdiff_real.py::test_second_relocation_blind_spot (real objdiff-cli scores the wrong 2nd relocation 100.0, relocs.check_function fails it naming the field VA), tests/test_check_real.py::test_cmain386_wrong_call_target_fails, tests/test_check.py::test_reloc_failure_beats_objdiff; all passed. |

**Score:** 4/4 roadmap truths verified (0 present, behavior-unverified).

### Plan-level must_haves (20 plans, judged against the rulings-amended text)

All plan truths were checked against the code, the committed config and the tests named in them. They hold, with these exceptions and notes:

| Plan | Truth | Status | Note |
|---|---|---|---|
| 05-08 | "build_target refuses (TargetError naming the VA) ... a branch destination outside every functions.csv row" | ? UNCERTAIN (owner decision) | Since e5120a9 (05-18), such fields stay raw and are listed in raw_fields. Recorded as a deviation in 05-18-SUMMARY, reviewed and approved by the orchestrator (progress.md line 118-119). The relocation check still fails such a reference (rules 4/5), so nothing can pass on it. Not a ruling, so it needs an owner override. The non-off32 part of the same truth was changed by ruling F11 and holds as amended. |
| 05-11 | "`asm EXE` writes one Intel-syntax listing per functions.csv row" | ⚠ WARNING (owner decision) | 1892 rows, 1891 files: both `_Alphabet` runtime rows map to asm/<exe>/_Alphabet.s (asm.file_name uses SymbolTable.c_name; the name is ambiguous by design, 05-04). Every game function gets its listing. |
| 05-20 | "container suite passes with zero skipped tests" | ✓ VERIFIED (as amended by F6) | 2 skips, both `Windows-only: msvcrt lock path`, the reason F6 allows. |
| 05-01 | spike 005 PASS lines and objdiff 100 for `__CMain` | ✓ VERIFIED | README `verdict: VALIDATED`, MANIFEST row; 05-spike.log; re-proved by production code in test_cmain386_pair_matches (container, both EXEs). |
| 05-18/05-19 | at most 3 candidates, `*` default unchanged, no per-glob rule | ✓ VERIFIED | config/cflags.txt has only `*  wcc386@10.6  -4r -s -fpi`; no `_asm` / `#pragma aux` under src/; both matches used the default rule. |

### Deferred / known limitations (not Phase 5 must_haves)

| # | Item | Disposition |
|---|---|---|
| 1 | IN-02: jump-table functions are refused by check | Deferred to Phase 7 (fails closed) |
| 2 | TACP code stretch around 0x00029D4D..0x00031040 has no functions.csv rows (largest gaps 0x0002EA1B..0x000308C0, 7845 bytes) but lies inside units | Not required by any must_have: every row is in one unit and the unmatched bytes stay original in the splice. Recorded in 05-16-SUMMARY; to be closed when matching reaches that code |
| 3 | UFO2P 3-byte tail at 0x000CFADA after the last row | Same as 2 |

### Required Artifacts

| Artifact | Status | Details |
|---|---|---|
| tools/reverseapoc/{elf,omf2elf,x86,discover,target,relocs,land,ghidra,asm,score,lint,units,check,functions,symbols}.py | ✓ VERIFIED | Present, substantive, wired through cli.py verbs and the ninja rules |
| tools/reverseapoc/ghidra_scripts/ExportFunctions.java, ExportDrafts.java | ✓ VERIFIED | `extends GhidraScript`, DecompInterface; used through -postScript |
| include/common.h, include/watcom_compat.h | ✓ VERIFIED | Content as the plans state |
| configure.py, .gitignore | ✓ VERIFIED | Generated files ignored and untracked |
| config/<exe>/{functions,boundaries,units,symbols}.csv | ✓ VERIFIED | Addresses, names, kinds, reasons only |
| src/ufo2p/u_000a34f0.c, src/tacp/u_00054f20.c | ✓ VERIFIED | One C89 function each plus INCLUDE_ASM markers |
| docker/Dockerfile | ✓ VERIFIED | Ghidra stage, pins, no ADD, COPY --from only |
| docs/toolchain.md `### Phase 5 match evidence` | ✓ VERIFIED | Both rows |
| .planning/spikes/005-objdiff-omf-elf/README.md | ✓ VERIFIED | verdict VALIDATED |
| 05-VALIDATION.md | ✓ VERIFIED | status validated, nyquist_compliant true, wave_0_complete true, every SPL row cites build/gate/05-evidence/ |

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| check.py | relocs.check_function | `_reloc` -> check_function with own_publics | WIRED |
| check.py | land.land | `_land_exe` -> land(expected_sha1=targets.toml) | WIRED |
| check.py | objdiff-cli | objdiff_argv / match_percent | WIRED (100.0 seen in real runs) |
| land.py | splice.splice | keep-original patches | WIRED |
| target.py | symbols / elf / x86 | linker_name, write_elf, decode | WIRED |
| configure.py | functions.py, lint.CLANGD_FLAGS | read_units_csv / read_functions_csv | WIRED |
| ninja `verify` | rebuild + land | phony over always/verify and always/land | WIRED (both ran at HEAD) |
| src/<exe>/<unit>.c | config/<exe>/units.csv | D-12 completeness check in configure and check's account_unit | WIRED |

### Data-Flow Trace (Level 4)

| Output | Source | Real data | Status |
|---|---|---|---|
| check JSON splice SHA-1 | land() over le.py image + compiled object, compared with config/targets.toml | yes (manifest SHA-1s reproduced) | ✓ FLOWING |
| check JSON objdiff_percent | objdiff-cli on build/<exe>/target/<unit>.o vs base/<unit>.o | yes | ✓ FLOWING |
| functions.csv | reconcile(Ghidra export, capstone discovery, runtime rows) | yes (drift test regenerates from inputs) | ✓ FLOWING |

### Requirements Coverage

| Requirement | Source plans | Status | Evidence |
|---|---|---|---|
| SPL-01 | 05-03, 05-04, 05-10, 05-12, 05-15, 05-16, 05-20 | ✓ SATISFIED | Truth 1 |
| SPL-02 | 05-03, 05-07, 05-13, 05-16, 05-20 | ✓ SATISFIED | Truth 1, no empty verdict |
| SPL-03 | 05-04, 05-13, 05-16, 05-20 | ✓ SATISFIED | units.csv, every row in one unit |
| SPL-04 | 05-05, 05-13, 05-14, 05-20 | ✓ SATISFIED | INCLUDE_ASM, stubs not landed, SHA-1 identical |
| SPL-05 | 05-11, 05-20 | ✓ SATISFIED (warning) | asm verb into gitignored asm/; `_Alphabet` collision |
| SPL-06 | 05-14, 05-18, 05-20 | ✓ SATISFIED | configure + ninja at HEAD |
| SPL-07 | 05-01, 05-02, 05-06, 05-20 | ✓ SATISFIED | Truth 3 |
| SPL-08 | 05-01, 05-08, 05-20 | ✓ SATISFIED | Truth 3, 841 cuts |
| SPL-09 | 05-09, 05-18, 05-20 | ✓ SATISFIED | relocs.py rules 1-5, negatives |
| SPL-10 | 05-09, 05-17, 05-18, 05-20 | ✓ SATISFIED | build_patch keep-original, landed SHA-1 |
| SPL-11 | 05-17, 05-20 | ✓ SATISFIED | check verb JSON, exit codes |
| SPL-12 | 05-12, 05-15, 05-20 | ✓ SATISFIED | lint gate in container |
| SPL-13 | 05-09, 05-18, 05-19, 05-20 | ✓ SATISFIED | Truth 4 |

No orphaned requirements: REQUIREMENTS.md maps exactly SPL-01..SPL-13 to Phase 5 and every one is claimed by at least one plan.

### Decision Coverage

All trackable CONTEXT.md decisions are honored by shipped artifacts (20/20).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| UFO2P match end to end | container `reverseapoc check ufo2p/u_000a34f0 --json` | exit 0, ok | ✓ PASS |
| TACP match end to end | container `reverseapoc check tacp/u_00054f20 --json` | exit 0, ok | ✓ PASS |
| ninja graph + verify | container `configure.py && ninja && ninja lint && ninja verify` | exit 0 | ✓ PASS |
| objdiff blind spot negative | container test_objdiff_real.py | passed | ✓ PASS |
| asm listings from orig/ | host `reverseapoc asm UFO2P.EXE` | 1892 reported, 1891 files | ⚠ WARNING |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes are declared or present. The spike driver result is in build/gate/05-evidence/05-spike.log (verdict VALIDATED, exit 0), and the production re-proof (test_cmain386_pair_matches) passed in my container run.

### Test Quality Audit

| Test file | Linked req | Skipped (container) | Circular | Assertion level | Verdict |
|---|---|---|---|---|---|
| tests/test_relocs.py | SPL-09 | 0 | no (synthetic pairs) | value | OK |
| tests/test_land.py | SPL-10 | 0 | no | value (SHA-1) | OK |
| tests/test_check.py | SPL-11 | 0 | no (fake runner) | behavioral (exit codes) | OK |
| tests/test_check_real.py | SPL-10, SPL-13 | 0 | no: oracle is config/targets.toml SHA-1 | behavioral | OK |
| tests/test_objdiff_real.py | SPL-13 | 0 | no: real objdiff-cli | value | OK |
| tests/test_functions_real.py | SPL-01..03 | 0 | consistency by design (regenerate == committed); correctness comes from the splice SHA-1 oracle | value | OK |

Disabled tests on requirements: 0. Circular patterns: 0. Insufficient assertions: 0.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| tools/reverseapoc/asm.py | 244-249, 265-283 | file_name collides for the two `_Alphabet` rows; the report counts writes, not files | ⚠ Warning | One runtime data-table listing lost per EXE; no effect on matching |
| tests/test_check_real.py | 147 | skips on the host when ninja is not on PATH (new WR-01 test; a reason F6's list does not name) | ℹ Info | Runs and passes in the container |

No TBD/FIXME/XXX debt markers in any file the phase changed.

### Host suite

Run once by the verifier at HEAD 50bc3d0: `uv run pytest -q -rs` 1605 passed, 26 skipped, exit 0; `uv run ruff check .` all checks passed. Every skip has a platform reason (objdiff-cli, Ghidra, clang, ninja not on the host PATH; only inside the container; POSIX-only; Windows file names; non-UTF-8 names). No test_*_real.py test skipped for a missing orig/ or Watcom tree (ruling F6).

### Gaps Summary

No roadmap success criterion failed. The pipeline runs end to end at HEAD in the container: 841 units cut, two units compiled with wcc386 10.6 under wibo, lint green, objdiff 100.0 plus a passing independent relocation check for func_000A3980 (UFO2P) and func_00055080 (TACP), and both EXEs landed SHA-1 identical to config/targets.toml. What remains is owner work: the D-16 read of the two C files, the image-size/capstone acceptance, the 7 hand verdicts, and two plan-level decisions (the 05-08 refusal that 05-18 turned into raw fields, and the `_Alphabet` listing collision).

If the owner accepts the 05-08 deviation, add to this frontmatter:

```yaml
overrides:
  - must_have: "build_target refuses a branch destination outside every functions.csv row"
    reason: "05-18 (e5120a9) keeps such fields raw and lists them in raw_fields so every unit stays cuttable (F11 principle, D-13); relocs.check_function still fails any reference into no row (rules 4/5), so nothing can pass on it"
    accepted_by: "<owner>"
    accepted_at: "<ISO timestamp>"
```

---

_Verified: 2026-10-24_
_Verifier: Claude (gsd-verifier)_
