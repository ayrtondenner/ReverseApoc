---
phase: 03-byte-identical-round-trip
reviewed: 2026-10-21T02:50:18Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - configure.py
  - docs/toolchain.md
  - tests/test_cli.py
  - tests/test_configure.py
  - tests/test_splice.py
  - tests/test_splice_real.py
  - tests/test_targets.py
  - tools/reverseapoc/splice.py
  - tools/reverseapoc/targets.py
findings:
  critical: 0
  warning: 4
  info: 1
  total: 5
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-10-21T02:50:18Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Narrative Findings (AI reviewer)

## Summary

This is an incremental re-review after gap-closure plans 03-07, 03-08, 03-09 and 03-10. It
covers the commits from `46ac0a2` (the previous review) to `f93c4cb`. The source commits are
`231ee0d` and `bf341b5` (configure.py), `51a6efc` and `09781cf` (targets.py, splice.py),
`154a73c` (docs/toolchain.md) and `e3abcc6` (test_splice_real.py), plus their RED-test commits.
`tools/reverseapoc/cli.py` and `tools/reverseapoc/le.py` did not change. I read both to check
the call sites.

Checks run at HEAD:

- `uv run pytest -q tests/test_configure.py tests/test_splice.py tests/test_targets.py tests/test_cli.py tests/test_splice_real.py`:
  220 passed, 3 skipped. The skipped tests are the two POSIX-only `|`/LF name tests and the
  Linux-only non-UTF-8 name test. `orig/` is present, so the real-file tests ran.
- `uv run ruff check .`: clean.

WR-07, IN-01 to IN-11 and VN-01 are fixed. The evidence for each is below, and none of them
counts. WR-02, WR-05 and WR-06 stay fixed. 03-07 touched the configure.py code behind WR-05 and
WR-06, and I re-checked it.

I found one new warning and one new info item:

- WR-08 is in the new `_unwritable_reason` code. When an LE header declares
  `last_page_size > page_size`, a patch past vsize in that page raises an uncaught `TypeError`
  instead of a `SpliceError`. The same unchecked header field also makes the plain round trip
  produce wrong bytes when that page is not the last page of its object. That part predates
  this diff.
- IN-12: after VN-01, the REFUSED and MISSING lines name the real input file and manifest. The
  remedy hints still tell the user to run `check-orig` and `ingest` with no `--orig` or
  `--manifest`.

WR-01, WR-03 and WR-04 are carried forward and still count. Only their line numbers moved. No
finding quotes game bytes.

## Resolved since the previous review

### WR-02: The `masked_fields` count is per (patch, field), not per field, so the report over-counts

Fixed by 03-06, and still fixed. 03-07 to 03-09 did not change this code, apart from adding the
`common` dict:

- `tools/reverseapoc/splice.py:671` still counts `len({m.fixup for m in result.masked})`.
- `:672` passes that count through `common`.
- It is pinned by `tests/test_splice.py::test_mask_count_counts_distinct_fields`.

### WR-05: `configure.py --orig` reaches only `parse-le`; the new `verify` edge and `check-orig` still use the default `orig/`

Fixed by 03-06. I re-checked it because 03-07 edited `HEADER`:

- `configure.py:36` and `configure.py:46` still carry `--orig {orig}`. The rebuild command is
  now `rebuild --orig {orig} --out build`.
- It is pinned by `test_render_passes_orig_to_check_orig_and_rebuild`,
  `test_main_passes_orig_to_check_orig_and_rebuild` and
  `test_generated_commands_read_the_orig_dir`. The first two were updated for `--out build`.

### WR-06: `parse_le` passes `$in` to the shell unquoted (this predates Phase 3)

Fixed by 03-06. I re-checked it because 03-07 edited `ninja_path` and `_check_orig_dir`:

- `$in` is still unquoted (`configure.py:41`), by design.
- The `|`/LF/CR refusal (`:60`, `:70-75`) runs before the new UTF-8 check.
- The `_SAFE_ORIG` allowlist (`:65`, `:96-101`) is unchanged. `_check_orig_dir` now also
  calls `_refuse_option_like` (`:102`).

### WR-07: A file name that cannot be encoded as UTF-8 truncates `build.ninja` and escapes as a traceback

Fixed (03-07, `231ee0d`):

- `ninja_path` refuses a path that does not encode as UTF-8 with a `ConfigureError`
  (`configure.py:76-81`).
- `main()` encodes the whole text inside the `try`, and catches `ConfigureError` and
  `UnicodeEncodeError` (`:152-157`). It writes with `write_bytes` only after that (`:158`), so
  a refusal never opens `build.ninja`.
- Tests:
  - `test_render_refuses_names_that_are_not_utf8` covers a low and a high surrogate.
  - `test_main_refuses_names_that_are_not_utf8` monkeypatches `find_executables`, so it runs on
    Windows too. It checks exit 1, the `error:` line, `\udcff` in the message and the sentinel.
  - `test_main_refuses_real_names_that_are_not_utf8` uses a real byte name and runs on Linux
    only.
  - `test_main_never_truncates_on_an_encoding_failure` is the defence-in-depth path through
    the encode in `main()`.
- The fix uses encode-before-open, not a temporary file plus `os.replace`. This is enough for
  the contract the finding named (a refusal leaves `build.ninja` alone).

### IN-09: The `--orig` allowlist accepts a leading `-`, which argparse reads as an option

Fixed (03-07, `231ee0d`):

- `_refuse_option_like` (`configure.py:85-92`) is applied to the orig dir (`:102`) and to every
  exe path before `ninja_path` (`:129`).
- An exe path relative to the build.ninja directory starts with `-` only when the orig dir does,
  or when the orig dir is `.` and the name starts with `-`. Both cases are covered.
- Tests: `test_render_refuses_an_option_like_orig_dir` (`-h`, `--orig`, `-`),
  `test_render_refuses_an_option_like_exe_path`, `test_main_refuses_an_option_like_orig_dir`
  and `test_main_refuses_an_option_like_exe_name`. The `test_main_*` tests use a sentinel.

### IN-10: Rule descriptions and header comments still say `orig/` after `--orig` points elsewhere

Fixed (03-07, `bf341b5`):

- `description = CHECK-ORIG {orig}` (`configure.py:37`).
- The header comments say "the orig dir" (`:25-26`).
- Pinned by `test_render_check_orig_description_names_the_orig_dir` and
  `test_header_comments_name_no_fixed_orig_dir`.

### IN-11: `--output` does not reach the rebuild output directory, so `verify` writes `<repo>/build` whatever `builddir` says

Fixed (03-07, `bf341b5`):

- The rebuild rule passes `--out build` (`configure.py:46`). `build` is the same literal as
  `builddir = build` (`:33`), and the render docstring says so (`:116`).
- Pinned by:
  - `test_rebuild_out_is_the_builddir`, which checks that the two literals agree.
  - `test_generated_rebuild_writes_into_builddir`. It chdirs into `cfg/` and runs the generated
    command through the CLI. It asserts `cfg/build/IN11.EXE` and that nothing is written to the
    monkeypatched CLI default.

### IN-01: The mismatch label "page N of object M" uses the global logical page number

Fixed (03-08, `09781cf`):

- `_page_label` (`splice.py:101-108`) prints the page's position in its object. When the object
  does not start at logical page 1, it adds `(logical page L)`.
- `Region.describe` (`:127-135`) uses `_page_label`. It produces the agreed form
  "page K of object M (logical page L), VA ...", followed by "(physical page N)" when the page
  map is permuted.
- Tests:
  - `test_region_labels_count_pages_within_the_object`: identity and permuted maps.
  - `test_mismatch_label_in_a_later_object`: the text and the `--json` region.
  - `tests/test_splice_real.py::test_control_mutation_is_reported`, which now expects the
    page number within the object.
- Note, outside this review's file scope: `le.py:430` and `:434` (`check_loadable`) still print
  "object N: page {page.logical}". The label is ambiguous in the same way, but those lines are
  error messages, not the D-08 mismatch label.

### IN-02: `_unwritable_reason` gives misleading reasons on unusual layouts

Fixed (03-08, `09781cf`), with the exception recorded under WR-08:

- `_unwritable_reason` (`splice.py:333-354`) separates four cases:
  - no object
  - BSS past the page-backed end
  - a hole after a short page inside the object ("past the page data of page K ... (N bytes)")
  - page data past vsize, which names the page instead of "its last page"
- `test_unwritable_reason_names_the_page` covers the short-page hole, page 1 and page 2 past
  vsize, and a later object. Each case also asserts that the old wrong word ("BSS",
  "last page") is absent.
- The new `_page_slot` unpack at `:345` relies on an invariant the LE reader does not enforce.
  That is a new defect, so it is a new finding (WR-08), not a reopening of IN-02.

### IN-03: `layout()` says zero-length regions are left out, but zero-length page regions are kept

Fixed (03-08, `09781cf`). This was a docstring-only change. The `layout()` docstring
(`splice.py:178-180`) now says that zero-length fixed regions are dropped and every page keeps
its region. That matches `:198-199`.

### IN-04: `docs/toolchain.md` still says the container's `orig/` holds only UFO2P.EXE and TACP.EXE

Fixed (03-09, `154a73c`). `docs/toolchain.md:136` now lists UFO2P.EXE, TACP.EXE and SMKP.EXE,
which matches the three `[[targets]]` names in `config/targets.toml`.

### IN-05: The real-file test helpers copy the implementation's arithmetic instead of checking it independently

Fixed (03-09, `e3abcc6`):

- `tests/test_splice_real.py` no longer copies `MAX_FIELD` or the
  `page_index + page_count - 2` index.
- `_page_backed_end` (`:154-161`) takes the furthest page end over the object table's page
  range. `_page_at` and `_page_offset` (`:125-146`) go through `LE.page_va` and
  `LEPage.file_offset`. `_straddles` (`:172-176`) compares page identity, not page-index
  arithmetic. `_covered` is now a direct range test.
- The module docstring (`:10-12`) names `FACTS` as the oracle.
- One residual note, not a finding: `LE.page_va` (`le.py:330`) and `splice._page_regions`
  (`splice.py:173`) use the same `base + (logical - page_index) * page_size` formula, so a bug
  in that formula would be shared. `FACTS` still guards against it.

### IN-06: A malformed TOML manifest crashes `rebuild` with a traceback

Fixed (03-08, `51a6efc`):

- `load_manifest` wraps `TOMLDecodeError` and `UnicodeDecodeError` in a `ManifestError` that
  names the manifest (`targets.py:121-125`). It also refuses a `targets` value that is not an
  array of tables (`:129-130`).
- `cli.main` already catches `ManifestError` (`cli.py:183`).
- Pinned by `tests/test_targets.py::test_malformed_manifest_raises_manifest_error` (six shapes)
  and by `tests/test_cli.py::test_malformed_manifest_is_an_error_line`. The CLI test covers
  `check-orig`, `rebuild` and `rebuild --json`, and checks that no `build/` is created.

### IN-07: `_check_bare_name` raises `SpliceError` for a manifest problem and accepts Windows device names

Fixed (03-08, `51a6efc`):

- `targets.check_bare_name` (`targets.py:76-91`) raises `ManifestError`. It checks both
  `PurePosixPath` and `PureWindowsPath`, and uses `ntpath.isreserved`, which catches device
  names with or without an extension, trailing dots and spaces, and wildcard or control
  characters. Python is pinned to 3.14 (`pyproject.toml:6`), so `isreserved` (3.13+) is
  available.
- `load_manifest` applies it per entry (`:97-100`).
- `splice._check_bare_name` (`splice.py:612-614`) delegates to it for hand-built Targets.
- Pinned by `test_manifest_refuses_a_non_bare_target_name` (14 names) and
  `test_rebuild_target_refuses_a_non_bare_name`.

### IN-08: `configure.py` still calls itself a "Phase 2 skeleton"

Fixed (03-07, `bf341b5`). The module docstring (`configure.py:4-5`) and the header
(`configure.py:24`) now say "Verification targets only (check-orig, parse-le, verify)". Pinned by
`test_no_stale_phase_wording`.

### IN-13 (formerly VN-01): REFUSED and MISSING lines always name orig/<NAME> and config/targets.toml, whatever --orig and --manifest say

Fixed (03-08, `09781cf`):

- `RebuildResult.source` (`splice.py:539`) is set to `check.path` for every status
  (`:660`, `:662`, `:672`).
- `RebuildReport.manifest` (`:597`) is filled by `rebuild()` (`:710`) and passed to
  `format(width, manifest)` (`:605`).
- The MISSING and REFUSED lines (`:562-569`) name the real input file and manifest.
- The 8-key `--json` contract is unchanged: neither new field is in `to_json()`
  (`:581-590`).
- Pinned by:
  - `test_rebuild_result_names_the_input_path`
  - `tests/test_cli.py::test_rebuild_refused_names_the_input_and_manifest`
  - `test_rebuild_missing_names_the_input`
  - `test_rebuild_json_refused_keeps_the_eight_keys`
- The remedy hints on these lines are a separate, lower-severity item (IN-12).

## Warnings

### WR-08: `_unwritable_reason` raises `TypeError` when `last_page_size` exceeds `page_size`, and the same header makes the round trip produce wrong bytes

**File:** `tools/reverseapoc/splice.py:344-345` (new in 03-08), `tools/reverseapoc/splice.py:315-320`,
`tools/reverseapoc/splice.py:265-267`. The root cause is in `tools/reverseapoc/le.py:207`, `:294`.

**Issue:** The comment at `:344` says that a page of the object covers `addr` because
`base <= addr < _page_backed_end`. That holds only if every page holds at most `page_size` bytes.
The LE reader never checks this:

- `le.py:224` checks only that `page_size` is a power of two.
- `last_page_size` (`le.py:207`) becomes the size of the last physical page (`:294`) with no
  upper bound.
- `layout()` and `check_tiling()` accept such a file, because the last physical page's region
  simply runs up to `pages_end`.

When that page is the last page of its object, `_page_backed_end` (`:315-320`) returns an address
past `base + page_count * page_size`. A patch byte in that range that is also past vsize has the
following path:

1. `obj_of_va` misses it.
2. The fallback at `:339` finds the object.
3. `_page_slot` returns `None`.
4. `off, page = _page_slot(...)` raises
   `TypeError: cannot unpack non-iterable NoneType object`.

`TypeError` is not an `LEError`, so it bypasses `rebuild_target`'s re-raise (`:666-667`) and
`cli.main`'s except tuple. The `splice()` contract ("Raises SpliceError for ... any byte outside
page data clipped to its object's vsize") is broken.

I reproduced this with the test fixture. I used `build_le_image(fixups=[b"", b"", b""])`, set
the objects to `(0x2000, 0x10000, ..., 1, 2)` and `(0x1000, 0x20000, ..., 3, 1)`, set
`extra_header_fields={0x2C: 0x1400}`, and padded the file to the new size:

- `layout()` passes, and `splice(le, {})` round-trips.
- `splice(le, {0x20FFF: b"\x01"})` is accepted.
- `splice(le, {0x21000: ...})` and `splice(le, {0x21200: ...})` both raise `TypeError`.

The same header also breaks the plain round trip when the oversized page is not the last page of
its object. This part is in `decompose`, which is unchanged since the previous review.

- `image[off : off + page.size] = ...` (`:267`) writes past the page's slot, and the next page
  overwrites the overflow.
- `_pieces` (`:278`) then reads `page.size` bytes back from the slot.
- With `page_numbers=(3, 2, 1)` and `last_page_size = 0x1400`, `splice(le, {}).data` differs
  from the input in 1024 bytes, starting at the last page's region. `rebuild` would report this
  as MISMATCH, not as a refusal of a layout it cannot represent.

Only a malformed header triggers this, and the CLI passes no patches today. The real targets
are not affected (`FACTS`). Phase 5's patch driver will call `splice()` with patches, and its
callers will rely on catching `SpliceError`/`LEError` (the D-03/D-18 refusals).

**Fix:** Refuse the layout in one place, so that every caller (`layout`, `decompose`,
`_unwritable_reason`, `_masked_fields`) keeps its invariant. For example, in
`splice._check_mappable` (or in the `LE` constructor next to the `page_size` check):
```python
if le.last_page_size > le.page_size:
    raise LEUnsupportedError(
        f"last page size {le.last_page_size:#x} exceeds the page size {le.page_size:#x}"
    )
```
Then make the `_page_slot` result explicit, so that a future layout change fails as a
`SpliceError` and not as a `TypeError`:
```python
slot = _page_slot(le, obj, addr)
if slot is None:
    raise SpliceError(f"{addr:#x}: no page of object {obj.index} covers it")
off, page = slot
```
Add a test that builds the image above and asserts `LEUnsupportedError` from `layout()`. Also
add a `_refused` case if the guard goes into `_unwritable_reason` rather than into the layout
check.

## Info

### IN-12: REFUSED and MISSING hints tell the user to run `check-orig` and `ingest` without the `--orig` and `--manifest` that produced the line

**File:** `tools/reverseapoc/splice.py:564`, `tools/reverseapoc/splice.py:566-569`

**Issue:** After VN-01, `rebuild --orig elsewhere --manifest custom.toml` prints
`REFUSED   SYNTH.EXE  elsewhere/SYNTH.EXE does not match custom.toml; run uv run reverseapoc check-orig`.
Following that hint checks the default `orig/` against `config/targets.toml`. That run can
report OK and contradict the line the user just read. The MISSING hint `run uv run reverseapoc
ingest` has the same gap, because `ingest` also defaults to `orig/` and the default manifest.

03-08's plan kept both hints verbatim on purpose. This is therefore a follow-up to VN-01, not a
regression.

**Fix:** Either name the options when they differ from the defaults, or make the hint generic.
For example, the hint could say "run uv run reverseapoc check-orig with the same --orig and
--manifest". Keep the status words and the column layout.

## Carried forward (not re-reviewed)

These findings keep their IDs, titles and severities, and they count in the totals above.
03-07 to 03-10 did not change the code they cite. Only line numbers moved in `splice.py`. Current
line numbers are given, with the previous ones in parentheses. Dispositions are recorded in
`03-REVIEW-DISPOSITION.md`: WR-01 and WR-03 are deferred to Phase 5, and WR-04 to Phase 6.

### WR-01: Objects that share logical pages are accepted, and a patch into the second owner is silently dropped

**File:** `tools/reverseapoc/splice.py:159-174` (previously `:147-162`),
`tools/reverseapoc/splice.py:259-278` (previously `:245-264`). The root cause is in
`tools/reverseapoc/le.py:268-284`, which is unchanged.

The code is unchanged. The fix, as in the earlier reviews, is to refuse shared logical pages and
overlapping object VA ranges in `layout()`.

### WR-03: The output write is checked by path only, not by file identity, and is not atomic; the input is read twice

**File:** `tools/reverseapoc/splice.py:617-619` (previously `:581-583`),
`tools/reverseapoc/splice.py:655-670` (previously `:620-634`).

The code is unchanged. 03-08 added only the `source=` arguments and the `common` dict. The fix
is a samefile guard, a write to a temporary file followed by `os.replace`, and a single read of
the input.

### WR-04: With `--json`, an error in any target produces no JSON and discards the results already computed

**File:** `tools/reverseapoc/cli.py:52-58`, `tools/reverseapoc/cli.py:179-185`,
`tools/reverseapoc/splice.py:709` (previously `:672`).

The code is unchanged. `rebuild_target` can now also raise `ManifestError` for a hand-built
non-bare name (IN-07), which takes the same path. The fix is a per-target `"error"` status, so
`--json` always prints a list.

---

_Reviewed: 2026-10-21T02:50:18Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
