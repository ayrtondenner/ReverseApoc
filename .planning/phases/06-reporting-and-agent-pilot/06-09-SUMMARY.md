---
phase: 06-reporting-and-agent-pilot
plan: 09
subsystem: oracle
tags: [check, compiler, configure, ninja, provenance, di-06, python]

requires:
  - phase: 06-reporting-and-agent-pilot
    provides: "06-02 fileio.write_atomic; 06-03 the DI-06c config wiring, normalize_source/code_text and DEFAULT_RENDER_GOLDEN; 06-08 build_patch binding each verdict to its row and bytes"
provides:
  - "CompileOptions.src_root/config_root; object_root sends a non-default --src or --config to build/check-custom (DI-06 part b, ruling F7)"
  - "`reverseapoc cc` writes <obj>.prov.json atomically (compiler, flags, source/cflags/watcom SHA-256, version), declared as an implicit output of every cc edge (DI-06 part a, writer)"
  - "check_provenance: ninja's land step refuses an object whose stamp is missing, unreadable, of another format or stale (DI-06 part a, reader)"
  - "05-REVIEW 17a (marked row with a data public is a mismatch), 17b (strict UTF-8, no newline translation), 17c (stray data public named as data), 18b (per-function raw_fields in the JSON)"
affects: [06-11 gate --partial (routes to check-custom through CompileOptions.src_root), 06-16 container re-proof of the stamp flow, driver plans (DI-06 is a D-38 prerequisite)]

actuals:
  tokens: 24847  # fix round 2: chars/4 over git diff 370e3e2..b49be21 (99,387 chars, SUMMARY included); round 1: 21418, first round: 12000
  tasks: 3
  commits: 15  # git rev-list --count 370e3e2..b49be21, the earlier SUMMARY commits included
plan_head_before: 370e3e2b30f632f72b5dd6935253fc0d2598c59e
plan_head_after: b49be21e337fb1b6657c510f418c919ace1820d1

tech-stack:
  added: []
  patterns:
    - "A provenance stamp next to each build output, compared field by field with what the tool would record today; a torn, missing or wrong-shaped stamp is never trusted"
    - "Committed-default roots are module constants read at call time, so a test stands its synthetic tree in for them with monkeypatch"

key-files:
  created: []
  modified:
    - tools/reverseapoc/check.py
    - tools/reverseapoc/compiler.py
    - configure.py
    - tests/test_check.py
    - tests/test_compiler.py
    - tests/test_configure.py
    - tools/reverseapoc/cli.py  # fix round 1, M8

key-decisions:
  - "The provenance stamp is no cache: if it cannot be written, the compile fails and the object is deleted (the gate stamp stays best effort)"
  - "A compile that ran and left no object removes the old stamp; a refusal before the compile runs leaves the old object and its stamp alone"
  - "The source hash is taken before the compile, so a source edited during it gives a stale stamp"
  - "check_provenance picks the cflags rule relative to REPO_ROOT when the src tree is inside the repository (where ninja's cc runs), else relative to the src tree's parent"
  - "land_all's own src_root/config_root win over the options' when non-default; a default one only fills an unset field, so 06-11's gate --partial src_root is kept"
  - "read_source decodes the bytes with no newline translation, as configure's _check_source does, so a lone CR becomes a D-12 source problem in check too"

patterns-established:
  - "put_object/put_stamp in tests/test_check.py: a synthetic ninja object always comes with the stamp ninja's cc edge would write"

requirements-completed: [AGT-06]

coverage:
  - id: D1
    description: "check --src OTHER / --config OTHER compile under build/check-custom; ninja's build/<exe>/obj keeps bytes and mtime; default roots keep today's paths (DI-06 part b)"
    requirement: "AGT-06"
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_check_with_other_src_keeps_ninja_objects, test_check_with_other_config_keeps_ninja_objects, test_default_roots_keep_ninja_paths, test_object_root_keys_on_the_src_and_config_roots, test_land_all_with_other_src_compiles_outside_ninja_paths"
        status: pass
    human_judgment: false
  - id: D2
    description: "cc writes <obj>.prov.json (format 2 since fix round 1: eight keys, include_sha256 and object_sha256 added), atomically; a failed or refused compile leaves none; build.ninja's cc edge declares it as an implicit output (DI-06 part a, writer)"
    requirement: "AGT-06"
    verification:
      - kind: unit
        ref: "tests/test_compiler.py#test_compile_writes_a_provenance_stamp, test_a_refused_compile_leaves_no_stamp, test_provenance_stamp_is_written_atomically, test_a_provenance_stamp_that_cannot_be_written_fails_the_compile; tests/test_configure.py#test_cc_edge_declares_the_stamp, test_default_config_render_is_unchanged"
        status: pass
      - kind: other
        ref: "uv run reverseapoc cc src/ufo2p/u_000a34f0.c -o build/06-09/ufo2p/obj/u_000a34f0.obj --watcom-dir <main>/third_party/watcom (real wcc386 10.6, stamp written)"
        status: pass
    human_judgment: false
  - id: D3
    description: "ninja's land step refuses a missing, unreadable, wrong-shaped, other-format or stale stamp (source, cflags, flags) with a CheckError naming the object and 'run ninja'; a fresh stamp and a CRLF checkout land (DI-06 part a, reader)"
    requirement: "AGT-06"
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_land_refuses_an_object_without_a_stamp, test_land_refuses_an_object_with_a_stale_source, test_land_refuses_an_object_with_stale_cflags, test_land_refuses_an_object_built_with_other_flags, test_land_refuses_an_unreadable_or_wrong_shaped_stamp (4), test_land_refuses_a_stamp_of_another_format, test_land_accepts_a_fresh_stamp, test_land_reads_a_crlf_checkout_as_the_same_source, test_land_verb_refuses_a_stale_object"
        status: pass
      - kind: other
        ref: "uv run reverseapoc land --orig <main>/orig --build build/06-09: both EXEs OK at the manifest SHA-1 with fresh stamps; with tacp's stamp removed it refuses naming the object"
        status: pass
    human_judgment: false
  - id: D4
    description: "05-REVIEW rows 17a, 17b, 17c and 18b closed in check.py"
    requirement: "AGT-06"
    verification:
      - kind: unit
        ref: "tests/test_check.py#test_marked_row_with_a_data_public_is_refused, test_land_refuses_a_marked_row_with_a_data_public, test_non_utf8_unit_file_is_refused, test_unit_file_with_a_lone_cr_is_a_source_problem, test_stray_data_public_message_says_data, test_check_json_lists_raw_fields_per_function"
        status: pass
      - kind: other
        ref: "grep -n 'errors=\"replace\"' tools/reverseapoc/check.py prints nothing"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-10-25
status: complete
---

# Phase 6 Plan 09: Provenance stamp, stale-object refusal and check --src/--config isolation Summary

**`reverseapoc cc` now writes `<obj>.prov.json` (compiler, flags, SHA-256 of the source, cflags table and Watcom manifest, format version) declared to ninja as an implicit output, and ninja's land step refuses any object whose stamp is missing, unreadable or stale; `check --src/--config OTHER` compiles under `build/check-custom/`; and check fails closed on the four 05-REVIEW minors (17a-c, 18b).**

Execution context nonce: 1e3c1d7fb3d2c278

## Performance

- **Duration:** 15 min
- **Started:** 2026-10-25T03:11:24Z
- **Completed:** 2026-10-25T03:26:30Z
- **Tasks:** 3 (each a RED test commit, then its GREEN commit)
- **Files modified:** 6

## Accomplishments

- DI-06 part b: `CompileOptions` gains `src_root` and `config_root` (ruling F7). `object_root` returns `build_dir/check-custom` unless every option, these two included, is the committed default (`check.DEFAULT_SRC`, `check.DEFAULT_CONFIG`, read at call time). `check_unit` passes its roots, and `land_all` folds its own roots into the options through `with_roots`.
- DI-06 part a, writer: `compile_source` hashes the source (CRLF read as LF), the cflags table and the Watcom manifest before the compile, then writes the stamp with `fileio.write_atomic` once the object exists. If the compile ran and left no object, the old stamp is removed. A stamp that cannot be written fails the compile and deletes the object. configure.py adds `| $builddir/<exe>/obj/<unit>.obj.prov.json` to every cc edge, so ninja rebuilds objects that have no stamp yet.
- DI-06 part a, reader: `check_provenance` runs in `_land_exe` only on the ninja branch (no `compile_fn`). It compares the stamp, field by field, with `compiler.provenance()` of today's files and the rule `source_rule` picks. A stale stamp gives `stale object <obj>: built from another <fields> than today's; run ninja (`ninja objects`) to rebuild it from <src>`. A missing or unreadable one gives `stale object <obj>: no provenance stamp: <stamp> is missing|unreadable or of the wrong shape; run ninja ...`. No flag or environment variable skips it. The check runs before the account and relocation checks, so 06-08's build_patch binding still runs unchanged on everything that passes.
- 17a: a row marked INCLUDE_ASM whose linker name the object exports from a non-code segment is a mismatch: `marked INCLUDE_ASM but exported as <linker> outside a code segment (data)`. It is no longer a stub.
- 17b: `read_source` decodes the file's bytes strictly as UTF-8, with no newline translation, the way configure's `_check_source` reads them. A non-UTF-8 file raises `CheckError("<path>: not UTF-8 (...)")` (configure's wording), and a lone CR now reaches the D-12 parser, which reports it as a source problem.
- 17c: a stray non-static public outside a code segment is reported as `public <name> is data, not a function of the unit`.
- 18b: each function's JSON has `raw_fields`, the unit's raw fields that fall inside its row. The unit-level `target.raw_fields` stays.

## Task Commits

1. **Task 1 (tracer): `check --src/--config OTHER` keeps ninja's objects (DI-06 part b).** RED `52e83b1` (test), GREEN `47546f1` (fix). Tracer gate: interactive mode, `end-of-phase`, automated-only verify. I re-ran `uv run pytest -q tests/test_check.py tests/test_land.py tests/test_cli.py tests/test_check_real.py` (184 passed, 4 skipped, the real-file skips), then expanded to Task 2.
2. **Task 2: cc writes a provenance stamp declared to ninja (DI-06 part a, writer).** RED `8fcd36d` (test), GREEN `3c56067` (feat)
3. **Task 3: ninja's land refuses stale objects; the check minors.** RED `f8c8e48` (test), GREEN `3533764` (fix)

**Plan metadata:** this SUMMARY commit (docs).

The plan is `type: execute`, not `type: tdd`. The GREEN commit types follow the plan's actions (fix, feat, fix). Every tdd="true" task has its RED test commit before its GREEN commit.

## RED evidence (semantic assessment)

pytest's console report is not one of the formats `check tdd-red-evidence` supports. I judged RED by reading each target assertion, as 06-03 and 06-08 did.

- Task 1 (`52e83b1`): 4 targets failed.
  - `test_check_with_other_src_keeps_ninja_objects` and `..._config_...` failed on `written.is_relative_to(build/check-custom)`: the compile went to `build/syn/obj/u_00010000.obj`.
  - `test_land_all_with_other_src_compiles_outside_ninja_paths` failed on the same assertion.
  - `test_object_root_keys_on_the_src_and_config_roots` failed with `TypeError: unexpected keyword argument 'src_root'`, because the field does not exist yet.
  - `test_default_roots_keep_ninja_paths` passed, as planned: it pins the default behaviour.
- Task 2 (`8fcd36d`): 6 targets failed, all on assertions.
  - The three stamp tests found no `a.obj.prov.json` (the atomic-write test saw only the gate stamp written).
  - `test_cc_edge_declares_the_stamp` got `build $builddir/ufo2p/obj/u_00010000.obj` where it expected the `| ...prov.json` implicit output.
  - The two updated edge-prefix tests failed the same way.
  - The golden test still passed: it is updated in GREEN.
- Task 3 (`f8c8e48`): 16 targets failed on their assertions. No collection or import faults.
  - 9 land refusals: `DID NOT RAISE CheckError`.
  - The land verb returned 0.
  - 17a: the row was in `stubs`, and the land verb returned 0.
  - 17b: `DID NOT RAISE` for the non-UTF-8 file, and the lone-CR result was `ok`.
  - 17c: the message lacked `data, `.
  - 18b: `KeyError: 'raw_fields'`.
  - `test_land_accepts_a_fresh_stamp`, `test_land_reads_a_crlf_checkout_as_the_same_source` and `test_check_compiles_past_a_stale_ninja_object` passed, as planned: they pin the accepting paths.

## Files Created/Modified

- `tools/reverseapoc/check.py`: `CompileOptions.src_root/config_root`, `DEFAULT_SRC`/`DEFAULT_CONFIG`, `object_root` on five options, `with_roots`, `check_provenance` (with `_compile_root`, `_stale`) on the ninja land branch, the 17a/17c reasons, the strict `read_source`, and `FunctionCheck.raw_fields` with `_raw_fields_json`. Module docstring updated.
- `tools/reverseapoc/compiler.py`: `source_rule` (factored out of `compile_source`), `PROV_SUFFIX`/`PROV_VERSION`/`PROV_KEYS`, `provenance_path`, `source_sha256`, `provenance`, `read_provenance`, `_drop_orphan_stamp`, `_write_provenance`. `compile_source` writes or removes the stamp. Module docstring updated.
- `configure.py`: imports `PROV_SUFFIX`. The cc edge gets the stamp as an implicit output.
- `tests/test_check.py`: the env fixture stands the synthetic tree in for the committed roots. New: `put_stamp`/`put_object(stamp=)`, the DI-06b tests, the stamp-refusal tests, and the 17a-c and 18b tests.
- `tests/test_compiler.py`: the stamp tests. The two gate-stamp tests now tell the gate cache apart from the provenance stamp.
- `tests/test_configure.py`: `_edge` accepts implicit outputs, `test_cc_edge_declares_the_stamp`, the two cc-edge prefix asserts, and the golden.

## The golden diff (ruling F4, consumer)

`DEFAULT_RENDER_GOLDEN` changed in exactly one line, the cc edge. In the Python literal the trailing `\` is a line continuation, so the rendered text is a single line:

```diff
-build $builddir/ufo2p/obj/u_00010000.obj: cc src/ufo2p/u_00010000.c
+build $builddir/ufo2p/obj/u_00010000.obj | $builddir/ufo2p/obj/u_00010000.obj.prov.json: cc \
+src/ufo2p/u_00010000.c
```

## Decisions Made

See key-decisions in the frontmatter. The stamp path is a `$builddir` path, built the same way as the object it sits next to (`_built`, the unit and EXE names already checked by `_check_name`). It is not passed through `ninja_path`, which would escape the `$` of `$builddir`. That is the plan's "ninja_path-escaped" applied as the object's own output path is.

## Deviations from Plan

- **Orchestrator ruling F4 (consumer): update the golden.** Task 2 updated 06-03's `test_default_config_render_is_unchanged` golden. The only diff is the cc edge's `| ...prov.json` implicit output, shown above.
- **Orchestrator ruling F7: where src_root lives.** `CompileOptions` gained `src_root: Path | None = None` and `config_root: Path | None = None`, after `log`, so the existing positional constructions keep working. `object_root` returns `build_dir/check-custom` when either is set and not the committed default. `check_unit` passes both. `land_all` threads its own through `with_roots`: a non-default land root always wins, and a default one only fills an unset field, so the src_root 06-11's `gate --partial` passes is kept. `check_source` takes the options its callers give it.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The test env's tmp src/config are not the committed defaults**
- **Found during:** Task 1
- **Issue:** every test_check.py test runs on a tmp tree, which under F7 would route to check-custom, so the tests that pin ninja's paths (`test_check_passes_a_matching_unit`, `test_check_with_default_options_keeps_ninja_paths`) would break.
- **Fix:** the `env` fixture monkeypatches `check.DEFAULT_SRC`/`check.DEFAULT_CONFIG` to the env tree, so that tree stands for the committed one. `object_root` reads the constants at call time. Tests that build their env with `make_env` directly still run on non-default roots and stay consistent: both compile and land go to check-custom.
- **Files modified:** tests/test_check.py, tools/reverseapoc/check.py
- **Commit:** `52e83b1`, `47546f1`

**2. [Rule 2 - Missing critical] A provenance stamp that cannot be written fails the compile**
- **Found during:** Task 2 (`test_a_stamp_that_cannot_be_written_never_fails_a_compile[write]` failed every write_atomic, the new stamp's included)
- **Issue:** the gate stamp is a best-effort cache. The provenance stamp is what the land step trusts, so silently missing it would report a successful compile whose declared ninja output does not exist.
- **Fix:** `_write_provenance` raises CompilerError and deletes the object. The gate-stamp test now fails only the gate cache path. New test: `test_a_provenance_stamp_that_cannot_be_written_fails_the_compile`. `test_stamp_written_atomically` now expects both writes, the gate stamp first.
- **Files modified:** tools/reverseapoc/compiler.py, tests/test_compiler.py
- **Commit:** `3c56067`

**3. [Rule 1 - Bug] `-o .` crashed computing the stamp path**
- **Found during:** Task 2 (`tests/test_cli.py::test_cc_object_without_a_name_is_an_error_line`)
- **Issue:** `Path('.').with_name(...)` raised ValueError before compile_rule's own refusal of a nameless object.
- **Fix:** the stamp path is computed only once compile_rule has run or refused. `_drop_orphan_stamp` skips a path with no name and only removes the stamp of an object that is gone, so a refusal before the compile keeps the old object's stamp.
- **Files modified:** tools/reverseapoc/compiler.py
- **Commit:** `3c56067`

**4. [Rule 2 - Missing critical] Unreadable sources raise CompilerError**
- **Found during:** Task 2
- **Issue:** the source is now hashed before compile_rule's path checks, so a missing source would surface as a bare OSError.
- **Fix:** `source_sha256` turns the read failure into `CompilerError("<src>: cannot read the source (...)")`. `check_provenance` converts any OSError/ValueError while computing today's stamp into a CheckError naming the object.
- **Commit:** `3c56067`, `3533764`

**5. [Rule 2 - Missing critical] 17b: no newline translation either**
- **Found during:** Task 3
- **Issue:** `read_text` translates a lone CR into a line break, which hides it from 06-03's `normalize_source` refusal. configure's `_check_source` reads bytes for that reason (06-03 fix round 3).
- **Fix:** `read_source` decodes the bytes. New test: `test_unit_file_with_a_lone_cr_is_a_source_problem`.
- **Commit:** `3533764`

**6. [Additional tests]** `test_object_root_keys_on_the_src_and_config_roots`, `test_land_all_with_other_src_compiles_outside_ninja_paths`, `test_land_refuses_an_object_built_with_other_flags`, `test_land_refuses_an_unreadable_or_wrong_shaped_stamp` (4 cases), `test_land_refuses_a_stamp_of_another_format`, `test_land_reads_a_crlf_checkout_as_the_same_source`, `test_land_verb_refuses_a_stale_object`, `test_check_compiles_past_a_stale_ninja_object`, `test_land_refuses_a_marked_row_with_a_data_public` and `test_a_refused_compile_leaves_no_stamp`, beyond the plan's list.

---

**Total deviations:** 2 orchestrator rulings applied (F4, F7). 5 auto-fixed (1 blocking, 3 missing critical, 1 bug), plus extra tests. **Impact:** no scope creep. Only the six planned files changed. config/, orig/, targets.toml, watcom.toml and the build scripts are untouched.

## Issues Encountered

- `check.DEFAULT_SRC`/`DEFAULT_CONFIG` repeat cli.py's `DEFAULT_SRC`/`DEFAULT_CONFIG` (same values). cli.py is outside this plan's files, and check.py cannot import cli.py without a cycle. A later plan could make cli.py import them from check.
- objdiff-cli and ninja are not on the host, so the container proof of the stamp flow (ninja rebuilding stamp-less objects, then `ninja verify`) is 06-16's. On the host I ran it by hand with the main checkout's real Watcom tree and orig/:
  - `uv run reverseapoc cc src/ufo2p/u_000a34f0.c -o build/06-09/ufo2p/obj/u_000a34f0.obj --watcom-dir <main>/third_party/watcom` and the same for `src/tacp/u_00054f20.c`: both `OK ... wcc386@10.6 ... Version 10.6`, each stamp with the six keys (`flags ["-4r","-s","-fpi"]`, `version 1`).
  - `uv run reverseapoc land --orig <main>/orig --build build/06-09 --out build/06-09/land`: `OK UFO2P.EXE sha1 e7488bf3... landed 1`, `OK TACP.EXE sha1 48ef0096... landed 1`, exit 0.
  - With tacp's stamp moved away: `reverseapoc land: error: stale object build\06-09\tacp\obj\u_00054f20.obj: no provenance stamp: ... is missing; run ninja (`ninja objects`) to rebuild it from ...`, exit 1.
  - `python configure.py --orig <main>/orig --output <scratch>/build.ninja` accepts all 841 committed units, and both cc edges carry the stamp.

## Verification

- `uv run pytest -q tests/test_check.py`: 77 passed.
- `uv run pytest -q tests/test_compiler.py tests/test_configure.py`: 205 passed, 3 skipped (pre-existing platform skips).
- `uv run pytest -q tests/test_check.py tests/test_land.py tests/test_cli.py`: 203 passed.
- `uv run pytest -q`: 1584 passed, 217 skipped (real-file and platform skips: this worktree has no orig/, third_party/, objdiff or ninja). `uv run ruff check .`: all checks passed.
- Acceptance: every named test exists. `grep -n 'errors="replace"' tools/reverseapoc/check.py` prints nothing.
- No CR in any changed file (`grep -c $'\r'` = 0 for all six).

## Next Phase Readiness

- 06-11 can route `gate --partial` to check-custom with `CompileOptions(src_root=<file's parent>)`. land_all keeps that root.
- 06-16: the first container `ninja verify` after this merge rebuilds both matched objects, because their implicit `.prov.json` outputs are missing. Then land checks the stamps.

## Fix round 1 (review-06-09.md, FIX_BASE a264884)

Orchestrator ruling: extend the stamp so that a stale or substituted object can never land through a direct `land`. The stamp format is now 2 (`PROV_VERSION = 2`) with eight keys. A format-1 stamp is refused as stale, and the message names its format.

| Item | What was done | Test commit | Fix commit |
|------|---------------|-------------|------------|
| I1 (Important) | New key `include_sha256`. It hashes every file under the compile root's `include/`, the `-i=` directory the compile reads first: per file, sorted by its POSIX path below include/, the line `<path>\0<SHA-256 of the content with CRLF as LF>\n`, then SHA-256 over all lines. The writer uses compile_source's root (REPO_ROOT by default). The reader uses `_compile_root(src_root)`. After a header edit, a direct `reverseapoc land` refuses with `the headers under <root>/include changed since it was built; run ninja ...`. | `620a584` | `162557e` |
| I2 (Important) | New key `object_sha256`: SHA-256 of the object's bytes, taken in `_write_provenance` once compile_rule has returned ok, so from the finished object. `check_provenance` hashes the object on disk and refuses on a difference: `the object is not the one its stamp was written for (its bytes changed)`. `compile_rule` now deletes the old stamp together with the old object, right before the run, so an interrupted compile (simulated with a runner that writes part of the object, then raises KeyboardInterrupt) leaves no stamp. A refusal before the run (path checks, gate) still leaves the old object and its stamp as a matching pair. Because the stamp is deleted before the compile, `_check_outputs` also refuses a stamp path that is the source. A stamp that cannot be written still fails the compile and deletes the object. `_drop_orphan_stamp` is gone: nothing needs it now. | `620a584` | `162557e` |
| M7 | New tests: `test_land_refuses_an_object_after_a_watcom_manifest_change` (names the manifest path) and `test_land_refuses_an_object_built_by_another_compiler` (10.6 -> 10.5, same flags; names "the compiler"). | `620a584` | (passed with `162557e`) |
| Old format | `test_land_refuses_an_old_format_stamp`: a six-key format-1 stamp gives `... is of stamp format 1, not format 2`. | `620a584` | `162557e` |
| M3 | 17a now names the public's place the way 17c does. It says `outside a code segment (data)` only when the public is outside every code segment. Inside one, the reason is `in a code segment, but not as a function check can pair with its row`. The not-marked `exported as ...` reason uses the same phrase. Test: `test_a_code_public_check_does_not_take_is_not_called_data`, with defined_functions monkeypatched to take nothing. An absolute public could not be used as a fixture, because omf2elf refuses it as a tool error. | `b3c2049` | `30aa93c` |
| M5 | Restored `KEPT = "int kept;\n"` at tests/test_compiler.py (stray whitespace edit). | `620a584` | n/a |
| M6 | The env fixture's monkeypatch no longer passes `raising=False`. | `620a584` | n/a |
| M8 | cli.py imports `DEFAULT_SRC` and `DEFAULT_CONFIG` from check.py (no import cycle: check.py does not import cli). Test: `test_cli_takes_its_default_roots_from_check`. **Deviation:** cli.py is outside the plan's `files_modified`; the coordinator asked for it. | `b3c2049` | `30aa93c` |
| Wording | The stale message now reads `<fields> changed since it was built`, because "built from another the headers ... than today's" did not parse. | n/a | `5294bdb` |
| put_stamp | tests/test_check.py's `put_stamp` computes the format-2 stamp from its definition (`headers_sha256`, `_text_sha256`). It does not call compiler.py, so the reader is checked against an independent writer. The compiler-side test pins the same `include_sha256` scheme (`_headers_sha256`). | `620a584` | n/a |

RED evidence:
- `620a584`: 21 failures in test_check.py and 3 in test_compiler.py, all on assertions. The stamp tests got 6 keys instead of 8. The interrupted compile kept its stamp. `test_the_stamp_may_not_be_the_source`: `DID NOT RAISE` (the stamp overwrote the source). The format-1 stamp was accepted. The header, object, manifest and compiler tests raised the wrong refusal (the format-1 reader read the format-2 stamp as the wrong shape, so their named words were missing). The accept and land tests failed because the format-1 reader refused the format-2 stamp `put_stamp` writes, which is the format change itself. `test_a_refusal_before_the_compile_keeps_the_old_object_and_stamp` passed: it pins behaviour that must stay.
- `b3c2049`: 2 failures on assertions: the reason ended `outside a code segment (data)`, and `cli.DEFAULT_SRC is not check.DEFAULT_SRC`.

Notes recorded, no change (coordinator ruling):
- **M1:** `land_all` without a compiler takes the cflags table and manifest it compares with from `options`. No CLI path passes them (`_cmd_land` passes no options), so the no-bypass prohibition holds; this is a latent API surface only.
- **M2:** `_compile_root`'s outside-the-repository branch (the src tree's parent) serves only the tmp-tree tests. ninja's cc and compile_source always use REPO_ROOT. That branch can only refuse or agree.
- **M4:** two contrived corners. A FIFO or device "source" now blocks while being hashed, before compile_rule's path checks. A source named `<obj>.prov.json` is now refused by `_check_outputs`, which also closes the second corner.

Host re-proof with real files (main checkout's Watcom 10.6 tree and orig/):
- `uv run reverseapoc cc src/ufo2p/u_000a34f0.c -o build/06-09/ufo2p/obj/u_000a34f0.obj --watcom-dir <main>/third_party/watcom` and the same for `src/tacp/u_00054f20.c`: both OK. Each stamp has 8 keys and `version 2`. For ufo2p: `include_sha256 e0219065...`, `object_sha256 bf841071...`.
- `uv run reverseapoc land --orig <main>/orig --build build/06-09 --out build/06-09/land`: `OK UFO2P.EXE sha1 e7488bf3... landed 1`, `OK TACP.EXE sha1 48ef0096... landed 1`, exit 0.
- Each refusal exited 1, naming the object and "run ninja":
  - TACP stamp removed: `no provenance stamp: ... is missing`.
  - A comment appended to include/common.h: `the headers under <worktree>/include changed since it was built`.
  - TACP's object copied over UFO2P's: `the object is not the one its stamp was written for (its bytes changed)`.
- Everything was restored (include/common.h from a copy; `git status` clean apart from the code under commit; the UFO2P object from its backup). The land then gave both EXEs OK at the manifest SHA-1 again, exit 0.
- `python configure.py --orig <main>/orig --output <scratch>/build.ninja` accepts all 841 units.

Verification: `uv run pytest -q` gives 1594 passed, 217 skipped. `uv run ruff check .`: all checks passed. No CR in any changed file.

## Fix round 2 (rereview-06-09-r1.md, FIX_BASE 0c336e6)

| Item | What was done | Test commit | Fix commit |
|------|---------------|-------------|------------|
| N1 (Minor; it failed closed but blocked every unit) | **Problem:** the stamp hashed every file under include/, recursively. The cc edge declares only the top-level `include/*.h`, so a README, an editor backup or `include/sub/x.h` would make every unit refuse with "run ninja", and `ninja objects` could never clear it. **Fix:** there is now ONE definition, `compiler.project_headers(root)`: every top-level `<root>/include/*.h` file, sorted by name. `include_sha256` hashes exactly that list, one line `<name>\0<SHA-256, CRLF as LF>\n` per header. configure.py's `Layout.for_base` takes the cc edge's implicit header inputs from the same function. The regeneration edge now also depends on the include/ directory (new `Layout.header_dirs`, the same mechanism as `src_dirs`), so adding or removing a header re-runs configure and then rebuilds. The cheap option was available, so I did not need the "re-run configure.py" message variant. The default render does not change: the golden uses `Layout()`, whose `header_dirs` is empty, so `DEFAULT_RENDER_GOLDEN` is untouched and there is no diff to show. **Tests:** `test_land_ignores_files_in_include_that_are_no_project_header` (README, `common.h~` and `sub/x.h` added after the stamp, and the unit still lands); `test_cc_edge_headers_are_the_stamped_headers` (configure's header inputs are whatever `project_headers` returns; the real repository's set is top-level `include/*.h`); `test_regeneration_edge_watches_the_include_dir`. The compiler-side stamp test now also writes a README, a backup and `sub/c.h`, and pins `include_sha256` over `common.h` and `b.h` only. The test helper `headers_sha256` follows the same definition. | `3b06a55` | `b49be21` |
| N3 | `_land_exe` reads the object's bytes once. `check_provenance(..., data=)` hashes them through `provenance(rule, src, obj_data, ...)`, and the new `parse_module(data, path)` parses the same buffer, so what is hashed is exactly what lands. `read_module(path)` is now `parse_module(path.read_bytes(), path)`. `compiler.object_sha256` takes bytes. Test: `test_land_reads_the_object_once` counts `Path.read_bytes` calls on the object. | `3b06a55` | `b49be21` |

RED evidence (`3b06a55`): 5 failures.
- The stamp test's `include_sha256` differed, because the old code hashed the README, the backup and `sub/c.h`.
- The include-files test refused with "the headers under ... changed since it was built".
- The read-once test counted 2 reads.
- The regeneration edge lacked the include/ path.
- `test_cc_edge_headers_are_the_stamped_headers` failed with `AttributeError: no attribute 'project_headers'`, because the shared function did not exist yet.

**N2, known limit for Phase 7 (note only, no code).** Some headers a compile can read are outside `project_headers` and are not stamped:
- a quoted `#include` resolved by Watcom's search order before `-i=`: the including file's directory (src/<exe>/), the cwd (the compile root), and `../` paths;
- headers reached through a symlinked directory or a subdirectory of include/;
- Watcom system headers other than `H/STDIO.H`, the only H file in config/watcom.toml.

ninja has the same blind spot: there is no depfile, because `-ad` is wrapper-owned. So this is not a regression, and both committed units include only "common.h". Phase 6 matching sessions may create headers only under include/ (D-17). Phase 7 should either probe Watcom's quoted-include search order and widen the header set (and ninja's inputs) to match, or refuse any `#include` that resolves outside the project headers.

Re-proof on the host (main checkout's Watcom 10.6 tree and orig/):
- Both units compiled again, and the stamps were rewritten.
- `uv run reverseapoc land --orig <main>/orig --build build/06-09 --out build/06-09/land`: `OK UFO2P.EXE sha1 e7488bf3... landed 1`, `OK TACP.EXE sha1 48ef0096... landed 1`, exit 0.
- With a probe `include/README.06-09-probe.md` added after the build, the land still passed: both OK, exit 0. The probe was then removed and `git status` was clean.
- `python configure.py --orig <main>/orig --output <scratch>/build.ninja` accepts all 841 units, and its regeneration edge lists the include/ directory.

Verification:
- `uv run pytest -q tests/test_configure.py tests/test_compiler.py tests/test_check.py tests/test_cli.py`: 395 passed, 3 skipped.
- `uv run pytest -q`: 1598 passed, 217 skipped.
- `uv run ruff check .`: all checks passed.
- No CR in any changed file.

## Self-Check: PASSED

- FOUND: tools/reverseapoc/check.py, tools/reverseapoc/compiler.py, configure.py, tests/test_check.py, tests/test_compiler.py, tests/test_configure.py
- FOUND commits (ancestors of HEAD): 52e83b1, 47546f1, 8fcd36d, 3c56067, f8c8e48, 3533764, a264884; fix round 1: 620a584, 162557e, b3c2049, 30aa93c, 5294bdb, 0c336e6; fix round 2: 3b06a55, b49be21
- FOUND: tools/reverseapoc/cli.py (fix round 1)

---
*Phase: 06-reporting-and-agent-pilot*
*Completed: 2026-10-25*
