---
phase: 03-byte-identical-round-trip
reviewed: 2026-10-20T23:11:55Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - configure.py
  - docs/learnings.md
  - tests/test_configure.py
  - tests/test_splice.py
  - tools/reverseapoc/splice.py
findings:
  critical: 0
  warning: 4
  info: 11
  total: 15
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-10-20T23:11:55Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Narrative Findings (AI reviewer)

## Summary

This is an incremental re-review after gap-closure plan 03-06. It covers commits `21d372a`,
`918b4f9`, `9f880bb` and `ee1dcaa` on top of `90d441e`, the commit the previous review was
written against. The changes are `configure.py` (`--orig` now reaches the check-orig and verify
rules, plus the `ConfigureError` refusals), `splice.py` (a count of distinct masked fields), the
new tests in `test_configure.py` and `test_splice.py`, and a `docs/learnings.md` entry.

`uv run pytest -q tests/test_configure.py tests/test_splice.py` gives 111 passed and 2 skipped
(the POSIX-only real-name tests). `uv run ruff check .` is clean.

WR-02, WR-05 and WR-06 are fixed; the evidence is below. The `docs/learnings.md` claim that ninja
shell-quotes `$in` (and `$out`) matches ninja's `EdgeEnv::MakePathList`, so leaving `parse-le $in`
unquoted is correct.

I found one new warning and three new info items. All are in `configure.py`:

- WR-07: a file name that cannot be encoded as UTF-8 still produces a traceback and leaves an
  empty `build.ninja`. This is the outcome the new refusal path was meant to rule out.
- IN-09: the `--orig` allowlist accepts a leading `-`. argparse then reads that path as an
  option.
- IN-10: the rule descriptions and header comments still say `orig/`.
- IN-11: `--output` does not reach the rebuild output directory.

Neither WR-07 nor IN-09 can occur in the default layout. No finding quotes game bytes.

## Resolved since the previous review

### WR-02: The `masked_fields` count is per (patch, field), not per field, so the report over-counts

Fixed.

- `tools/reverseapoc/splice.py:635` now counts `len({m.fixup for m in result.masked})`.
- The dedup key is sound. `Fixup` is `@dataclass(frozen=True, order=True)`
  (`tools/reverseapoc/le.py:145`), and `LE._parse_fixups` keeps one `Fixup` per `src_va` and
  refuses conflicting duplicates (`le.py:360-362`). Distinct `Fixup` values are therefore
  distinct fields.
- `SpliceResult.masked` stays one entry per (patch, field), and the comment at `splice.py:406`
  documents this.
- The `RebuildResult.masked_fields` comment (`splice.py:504`) now says "distinct".
- The fix is pinned by `tests/test_splice.py::test_mask_count_counts_distinct_fields`, with
  five cases: touching, three-patches, straddling, two-fields and mixed. It checks both the
  per-patch entry count and the distinct-field count in `masked_fields`, the text line and
  `to_json()`.

### WR-05: `configure.py --orig` reaches only `parse-le`; the new `verify` edge and `check-orig` still use the default `orig/`

Fixed.

- `HEADER` is now a template: `configure.py:36` and `configure.py:46` carry `--orig {orig}`.
- `render(exes, *, orig)` fills it after `_check_orig_dir` (`configure.py:97-103`).
- `main()` passes `_relative(args.orig, base)`, the same base the parse_le edges use
  (`configure.py:133-136`).
- The fix is pinned by `tests/test_configure.py`:
  - `test_render_passes_orig_to_check_orig_and_rebuild`
  - `test_main_passes_orig_to_check_orig_and_rebuild`, with the same-dir and sub-dir cases
    checked against the parse_le edge's directory
  - `test_generated_commands_read_the_orig_dir`, which runs the generated commands end to end
    through the CLI and gets REFUSED and MISMATCH from `elsewhere`
  - `test_render_has_verify_edge`, which expects `--orig orig` in the default layout

### WR-06: `parse_le` passes `$in` to the shell unquoted (this predates Phase 3)

Fixed, and the premise is corrected.

- ninja shell-escapes `$in` and `$out` itself: `GetShellEscapedString` on POSIX and
  `GetWin32EscapedString` on Windows. An exe name with a space or shell metacharacters therefore
  reaches `parse-le` as one argument. Quoting `$in` in the rule would have broken this. The
  unquoted rule is pinned at `tests/test_configure.py:120`.
- The real gaps were `|`, LF and CR in a ninja build path, which ninja 1.11 cannot escape, and
  the literal `--orig` text that WR-05 adds, which ninja does not quote. These are now refused:
  - `ninja_path` raises `ConfigureError` for `|`, LF and CR (`configure.py:60`, `:68-76`).
  - `_check_orig_dir` allows only `[A-Za-z0-9._/:-]+` (`configure.py:65`, `:79-86`).
  - `main()` prints `configure.py: error:` and returns 1 before it writes anything
    (`configure.py:135-139`).
- The refusals are pinned by:
  - `test_render_refuses_names_ninja_cannot_represent`
  - `test_main_refuses_names_ninja_cannot_represent`
  - `test_main_refuses_real_names_ninja_cannot_represent` (POSIX only)
  - `test_render_refuses_an_unsafe_orig_dir` (nine unsafe dirs)
  - `test_main_refuses_an_unsafe_orig_dir` (a byte-for-byte sentinel)
  - `test_main_keeps_names_with_spaces`
- The leading-dash gap left in the allowlist is a separate, lower-severity item (IN-09).

## Warnings

### WR-07: A file name that cannot be encoded as UTF-8 truncates `build.ninja` and escapes as a traceback

**File:** `configure.py:134-140`

**Issue:** The 03-06 refusal path promises an error line, exit 1, and an existing `build.ninja`
left alone. That holds only for `ConfigureError`. `find_executables` accepts any `*.exe` name.
`ninja_path` checks only `|`, LF and CR. A name that Python holds with surrogate code points (a
non-UTF-8 byte name on Linux, decoded with surrogateescape, or an unpaired UTF-16 surrogate on
Windows) passes `render()`. It then fails inside
`args.output.write_text(text, encoding="utf-8", ...)`.

`Path.write_text` opens the file in `"w"` mode, which truncates it, before encoding. The result
is an uncaught `UnicodeEncodeError` traceback and an empty `build.ninja`. I reproduced this on
Windows. `find_executables` was monkeypatched to return `[o / "A\udcffB.EXE"]`, and an existing
`build.ninja` held a sentinel line. The call raised `UnicodeEncodeError`, and the file afterwards
read `''`.

The input is unusual, and `build.ninja` can be regenerated. Still, this is a hole in the contract
the 03-06 tests just pinned (`test_main_refuses_an_unsafe_orig_dir` asserts the sentinel
survives).

**Fix:** Encode before opening the output, and refuse non-encodable paths the same way as the
others. For example, in `ninja_path`:
```python
try:
    path.encode("utf-8")
except UnicodeEncodeError:
    raise ConfigureError(f"{path!r} is not valid UTF-8; rename the file") from None
```
Then make the write all-or-nothing in `main()`:
```python
data = text.encode("utf-8")  # fails before the output is touched
tmp = args.output.with_name(args.output.name + ".tmp")
tmp.write_bytes(data)
os.replace(tmp, args.output)
```
Add a test that monkeypatches `find_executables` to return a surrogate-bearing name, as
`test_main_refuses_names_ninja_cannot_represent` does. It should assert exit 1, an
`error:` line, and an untouched sentinel.

## Info

### IN-09: The `--orig` allowlist accepts a leading `-`, which argparse reads as an option

**File:** `configure.py:65`, `configure.py:79-86`

**Issue:** `_SAFE_ORIG` lets a path start with `-`. For an orig directory named `-h` next to
`build.ninja`, `configure.py` exits 0 and writes `command = uv run reverseapoc check-orig --orig -h`
(and the same for rebuild). Running that command fails with `argument --orig: expected one
argument`. I reproduced both steps. The parse_le edge has the same problem, because its `$in`
becomes `-h/UFO2P.EXE`. ninja's quoting does not help, since the shell sees a correctly quoted
argument that starts with `-`.

This is the "broken build.ninja instead of an error" outcome that WR-06's fix set out to remove.
It is not an injection, and only a directory whose name starts with `-` triggers it.

**Fix:** In `_check_orig_dir`, also refuse a path whose first character is `-`, and add `"-h"` to
`UNSAFE_ORIG_DIRS`. Alternatively, write `--orig=PATH`, which argparse never reads as an option
(this still leaves the parse_le positional).

### IN-10: Rule descriptions and header comments still say `orig/` after `--orig` points elsewhere

**File:** `configure.py:25`, `configure.py:37`

**Issue:** After `python configure.py --orig ../elsewhere`, ninja's status line still prints
`CHECK-ORIG orig/`, and the header comment says `ninja check-orig   verify orig/ against ...`.
The command is correct, but the label names the wrong directory. The 03-06 plan kept these on
purpose (it put the wording out of scope), so this is a follow-up, not a regression.

**Fix:** Fill the description from the same template: `description = CHECK-ORIG {orig}`. Leave the
header comment generic ("the orig directory").

### IN-11: `--output` does not reach the rebuild output directory, so `verify` writes `<repo>/build` whatever `builddir` says

**File:** `configure.py:33`, `configure.py:45-48`

**Issue:** This is the WR-05 pattern applied to `--out`. The rebuild rule runs
`reverseapoc rebuild --orig {orig}` without `--out`, so the CLI writes to `DEFAULT_OUT` (the
absolute `<repo>/build`). The generated file says `builddir = build`, relative to `build.ninja`.
With `--output cfg/build.ninja`, a case `test_main_passes_orig_to_check_orig_and_rebuild` now
exercises, ninja's `$builddir` is `cfg/build`, but `ninja verify` writes `<repo>/build/<NAME>`.
Nothing breaks today, because the `$builddir/always/...` outputs are phony and never written.
The header still promises "rebuild every target into build/".

**Fix:** Emit `--out build` (relative to the build.ninja directory, the same directory as
`builddir`) in the rebuild rule, or document that verify always writes `<repo>/build`.

## Carried forward (not re-reviewed)

These findings keep their IDs, titles and severities, and they count in the totals above. 03-06
did not change the code they cite, apart from line shifts in `splice.py` from the comment added
at `:406`. Current line numbers are given where they moved. Dispositions are recorded in
`03-REVIEW-DISPOSITION.md`: WR-01 and WR-03 are deferred to Phase 5, and WR-04 to Phase 6.

### WR-01: Objects that share logical pages are accepted, and a patch into the second owner is silently dropped

**File:** `tools/reverseapoc/splice.py:147-162`, `tools/reverseapoc/splice.py:245-264` (root
cause in `tools/reverseapoc/le.py:268-284`). Unchanged. See the previous review: refuse shared
logical pages and overlapping object VA ranges in `layout()`.

### WR-03: The output write is checked by path only, not by file identity, and is not atomic; the input is read twice

**File:** `tools/reverseapoc/splice.py:581-583`, `tools/reverseapoc/splice.py:620-634` (previously
`:580-582`, `:621-633`). Unchanged. The fix is a samefile guard, a write to a temporary file
followed by `os.replace`, and a single read of the input.

### WR-04: With `--json`, an error in any target produces no JSON and discards the results already computed

**File:** `tools/reverseapoc/cli.py:52-58`, `tools/reverseapoc/cli.py:179-185`,
`tools/reverseapoc/splice.py:672` (previously `:671`). Unchanged. The fix is a per-target
`"error"` status, so `--json` always prints a list.

### IN-01: The mismatch label "page N of object M" uses the global logical page number

**File:** `tools/reverseapoc/splice.py:116-123`. Unchanged.

### IN-02: `_unwritable_reason` gives misleading reasons on unusual layouts

**File:** `tools/reverseapoc/splice.py:309-320`. Unchanged.

### IN-03: `layout()` says zero-length regions are left out, but zero-length page regions are kept

**File:** `tools/reverseapoc/splice.py:166`, `tools/reverseapoc/splice.py:184-185`. Unchanged.

### IN-04: `docs/toolchain.md` still says the container's `orig/` holds only UFO2P.EXE and TACP.EXE

**File:** `docs/toolchain.md:136`. Not in this review's file scope; carried as is.

### IN-05: The real-file test helpers copy the implementation's arithmetic instead of checking it independently

**File:** `tests/test_splice_real.py:56`, `tests/test_splice_real.py:132-137`. Not in this
review's file scope; carried as is.

### IN-06: A malformed TOML manifest crashes `rebuild` with a traceback

**File:** `tools/reverseapoc/cli.py:183`. Not in this review's file scope; carried as is.

### IN-07: `_check_bare_name` raises `SpliceError` for a manifest problem and accepts Windows device names

**File:** `tools/reverseapoc/splice.py:575-578` (previously `:574-577`). Unchanged.

### IN-08: `configure.py` still calls itself a "Phase 2 skeleton"

**File:** `configure.py:4`, `configure.py:24` (previously `:4`, `:21`). Re-checked, because 03-06
turned `HEADER` into a template. Both lines still say "Phase 2 skeleton". The plan put that
wording out of scope on purpose, so the finding stands unchanged.

---

_Reviewed: 2026-10-20T23:11:55Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
