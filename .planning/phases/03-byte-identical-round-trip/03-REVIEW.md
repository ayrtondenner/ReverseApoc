---
phase: 03-byte-identical-round-trip
reviewed: 2026-10-20T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - configure.py
  - docs/toolchain.md
  - tests/conftest.py
  - tests/test_cli.py
  - tests/test_configure.py
  - tests/test_hygiene.py
  - tests/test_le.py
  - tests/test_splice.py
  - tests/test_splice_real.py
  - tools/reverseapoc/cli.py
  - tools/reverseapoc/le.py
  - tools/reverseapoc/splice.py
findings:
  critical: 0
  warning: 6
  info: 8
  total: 14
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-10-20
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Narrative Findings (AI reviewer)

## Summary

I reviewed the Phase 3 changes since `7618b93`: the new `splice.py` (region map, decompose and
reassemble, linear-address splice with fixup masking, rebuild gate), the `le.py` additions
(named header-table constants, `pages_end`, public `check_loadable`, trailer summary), the
`rebuild` CLI verb, the `verify` ninja edge, and the synthetic and real-file tests. I judged
findings against D-01..D-21. Masking under D-02, the D-18 vsize clip and the D-19 refusals are
treated as intended behaviour.

`uv run pytest -q` passed (324 passed, 3 container-only skips; the real-file tests ran against
`orig/`) and `uv run ruff check .` was clean. On the real targets the round trip, tiling and
masking are sound. I found no blocker. The main problems:

- Malformed-input gaps: an LE whose objects share logical pages makes a patch vanish silently.
  I confirmed this by running it.
- The masked-field count in the rebuild report and its JSON is inflated. Also confirmed by
  running it.
- The output write is checked by path only, not by file identity, and is not atomic.
- With `--json`, an error prints no JSON at all.
- `configure.py --orig` does not reach the new `verify` edge.
- `parse_le` passes `$in` to the shell unquoted (this predates Phase 3).

No finding quotes game bytes.

## Warnings

### WR-01: Objects that share logical pages are accepted, and a patch into the second owner is silently dropped

**File:** `tools/reverseapoc/splice.py:147-162`, `tools/reverseapoc/splice.py:245-264`
(the root cause is in `tools/reverseapoc/le.py:268-284`)

**Issue:** `_read_objects` checks each object's page range against the page map, but never checks
that two objects do not claim the same logical page, or that their VA ranges do not overlap.

- `decompose()` copies a shared page into the images of both objects.
- `_owner()` gives the page region to the first matching object only.
- `_pieces()` therefore reads the page back only from the first object's image.

A patch that `_runs()` resolves into the second object is written into an image that
`reassemble()` never reads. `splice()` returns the original bytes with `masked == ()`, so a
rebuild would report `ok`, which is a false pass for a patch that was asked for. I reproduced it
with `build_le_image(fixups=[b"", b"", b""], objects=[(0x2000, 0x10000, 0x2045, 1, 2),
(0x1200, 0x20000, 0x2043, 2, 2)])`: `splice(le, {0x20010: b"\x5a"}).data == img.data`.

The real targets have disjoint, identity-mapped objects, so today's gate is not affected.
`splice()` is the public primitive Phase 5 lands functions through, though, and it should fail
loudly, as D-03 does for other layouts it cannot handle.

**Fix:** In `layout()` (or `_check_mappable`), refuse any logical page owned by more than one
object, and any objects whose `[base, end)` ranges overlap:
```python
def _check_disjoint(le: LE) -> None:
    owners = Counter(p for o in le.objects for p in range(o.page_index, o.page_index + o.page_count))
    shared = sorted(p for p, n in owners.items() if n > 1)
    if shared:
        raise LEUnsupportedError(f"logical page {shared[0]} belongs to more than one object")
    by_base = sorted(le.objects, key=lambda o: o.base)
    for a, b in pairwise(by_base):
        if a.end > b.base:
            raise LEUnsupportedError(f"objects {a.index} and {b.index} overlap at {b.base:#x}")
```

### WR-02: The `masked_fields` count is per (patch, field), not per field, so the report over-counts

**File:** `tools/reverseapoc/splice.py:483-487`, `tools/reverseapoc/splice.py:503`,
`tools/reverseapoc/splice.py:634`

**Issue:** `_masked_fields` yields one `MaskedField` for each patch that touches a field. When two
touching patches split one fixup field, `result.masked` holds two entries for the same fixup. I
confirmed this: `{0x10010: 2 bytes, 0x10012: 2 bytes}` on the default fixture gives
`len(result.masked) == 2`, with both entries at `src_va 0x10010`.

`rebuild_target` reports `len(result.masked)` as `masked_fields`. Both the text line ("masked N
fixup fields") and the JSON field that the Phase 6 driver will read describe it as a count of
fields. The per-patch detail in `masked` is useful; the count is what is wrong.

**Fix:** Count distinct fixups:
```python
masked = len({m.fixup for m in result.masked})
```
Alternatively, rename the field to `masked_entries`. Then add a test with two touching patches
over one off32.

### WR-03: The output write is checked by path only, not by file identity, and is not atomic; the input is read twice

**File:** `tools/reverseapoc/splice.py:580-582`, `tools/reverseapoc/splice.py:621-633`

**Issue:** There are three separate problems here.

1. **Path check only.** `_refuse_inside_orig` resolves paths, so it catches a symlink from
   `build/` into `orig/`. It cannot catch a hardlink: if `build/<NAME>` is a hardlink to
   `orig/<NAME>`, `out_path.write_bytes()` truncates and rewrites the file in place. That
   rewrites the original executable. With an empty patch set the bytes come out the same; once
   Phase 5 passes patches they will not.
2. **Not atomic.** `write_bytes` writes in place. An interrupted rebuild leaves a truncated
   `build/<NAME>` that later tools might read.
3. **Input read twice.** `check_target()` hashes `orig/<NAME>`, then `LE(check.path)` reads it a
   second time. A file that changes between the two reads is parsed without being verified. The
   result is a `mismatch` with no first difference, because `_mismatch` compares against
   `le.data` rather than the bytes that were verified.

**Fix:**
- Read the file once and pass the same bytes to both the hash check and `LE(...)`.
- Refuse when the output and an orig file are the same file:
  `out_path.exists() and os.path.samefile(out_path, orig_dir / target.name)`.
- Write to a temporary file next to the output and swap it in, which also breaks any hardlink:
```python
tmp = out_path.with_name(out_path.name + ".tmp")
tmp.write_bytes(result.data)
os.replace(tmp, out_path)
```

### WR-04: With `--json`, an error in any target produces no JSON and discards the results already computed

**File:** `tools/reverseapoc/cli.py:52-58`, `tools/reverseapoc/cli.py:179-185`,
`tools/reverseapoc/splice.py:671`

**Issue:** `rebuild()` builds its results inside a list comprehension. An `LEError` or
`SpliceError` from one target (for example a D-19 refusal, a truncated file, or a bad target name
caught by `rebuild_target`) propagates out of `rebuild()`. `main()` then prints a single stderr
line and exits 1.

- Stdout is empty, even with `--json`, so the Phase 6 driver that D-08 says will consume the
  JSON gets invalid input and has to parse stderr instead.
- Targets already rebuilt (and written to `build/`) are not reported.

**Fix:** Catch `LEError` per target in `rebuild()` and record it as a status, for example
`"error"` with a message field, so the report always covers every selected target. Then
`--json` always prints a list. Keep exit code 1.

### WR-05: `configure.py --orig` reaches only `parse-le`; the new `verify` edge and `check-orig` still use the default `orig/`

**File:** `configure.py:32-45`, `configure.py:65-82`, `configure.py:92-99`

**Issue:** `main()` uses `--orig` only to find executables for `parse-le`. `render()` emits
`uv run reverseapoc rebuild` and `uv run reverseapoc check-orig` with no `--orig`. After
`python configure.py --orig /elsewhere`, `ninja parse-le` reads `/elsewhere`, while
`ninja verify` rebuilds and checks the repo's `orig/` (or reports every target MISSING). The
generated file is internally inconsistent. The `check-orig` half predates this phase; this phase
copied the pattern into the new `verify` edge.

**Fix:** Pass the orig directory into `render()` and emit it in both commands. Escape it with
`ninja_path`, and shell-quote it too (see WR-06):
```python
"rule rebuild\n  command = uv run reverseapoc rebuild --orig " + quoted_orig
```
Add a test asserting that `--orig` appears in the `rebuild` rule.

### WR-06: `parse_le` passes `$in` to the shell unquoted (this predates Phase 3)

**File:** `configure.py:37-40`, `configure.py:78`

**Issue:** `ninja_path` escapes paths for ninja's own syntax, but `$in` is expanded unquoted into
`command = uv run reverseapoc parse-le $in`. On POSIX (the container), ninja runs commands through
`/bin/sh -c`:

- A file in `orig/` whose name contains a space is split into two arguments.
- A name containing `;`, `&`, `$(...)` or a backtick runs as shell code.

`find_executables` accepts any `*.exe` name in `orig/`, so a stray or hostile file name there runs
arbitrary commands when `ninja parse-le` runs. The risk is local and the code predates this
phase, but the file is in scope, and WR-05's fix will add a second path to the same command
lines.

**Fix:** Quote the expansion in the rule (`command = uv run reverseapoc parse-le "$in"`). Better,
in `find_executables`, refuse names outside a conservative character set such as
`[A-Za-z0-9._-]`, and add a test with a name containing a space.

## Info

### IN-01: The mismatch label "page N of object M" uses the global logical page number

**File:** `tools/reverseapoc/splice.py:116-123`

**Issue:** `describe()` prints `page {page.logical} of object {obj.index}`. For object 2 of the
synthetic fixture, this gives "page 3 of object 2" for object 2's first page. That reads as "the
third page of object 2". The VA that follows disambiguates it, but this is the D-08 gate's
primary diagnostic.

**Fix:** Say "logical page 3 (page 1 of object 2)", or print the index within the object, and
update the matching assertions in `test_splice.py` and `test_splice_real.py`.

### IN-02: `_unwritable_reason` gives misleading reasons on unusual layouts

**File:** `tools/reverseapoc/splice.py:309-320`

**Issue:**
- An address on a whole page that lies past vsize (any page, not only the last) is reported as
  "past the end of object N ... in its last page".
- A gap left by a short page in the middle of an object (possible with a permuted page map) is
  reported as "in the BSS".

The refusals themselves are correct; only the reason text is wrong.

**Fix:** Name the page: compute `(addr - obj.base) // le.page_size`, and say "past the page data
of page K" when the address is below `obj.end`.

### IN-03: `layout()` says zero-length regions are left out, but zero-length page regions are kept

**File:** `tools/reverseapoc/splice.py:166`, `tools/reverseapoc/splice.py:184-185`

**Issue:** Only the fixed spans are filtered with `end > start`. A page region whose size is 0
(a header with `last_page_size == 0`) is appended anyway. Tiling still passes, so only the
docstring is wrong.

**Fix:** Filter page regions the same way, or reword the docstring.

### IN-04: `docs/toolchain.md` still says the container's `orig/` holds only UFO2P.EXE and TACP.EXE

**File:** `docs/toolchain.md:136`

**Issue:** Under D-07, `rebuild` (and `ninja verify`, which line 77 recommends running in the
container) also requires SMKP.EXE. With only the two EXEs listed in that row, `verify` reports
SMKP MISSING and exits 1.

**Fix:** List SMKP.EXE in the "Supplied by you" row.

### IN-05: The real-file test helpers copy the implementation's arithmetic instead of checking it independently

**File:** `tests/test_splice_real.py:56`, `tests/test_splice_real.py:132-137`

**Issue:** `_page_backed_end` and `MAX_FIELD` are line-for-line copies of `splice.py`, including
the `page_index + page_count - 2` index. A shared off-by-one would pass both. The `FACTS` table
from the spikes pins the outcomes, which limits the risk.

**Fix:** Derive the page-backed end from `LEPage.file_offset`, `size` and `le.pages_end`, or note
in the docstring that `FACTS` is the oracle.

### IN-06: A malformed TOML manifest crashes `rebuild` with a traceback

**File:** `tools/reverseapoc/cli.py:183`

**Issue:** `load_manifest` lets `tomllib.TOMLDecodeError` (a `ValueError`, not a
`ManifestError`) escape, and `main()`'s except tuple does not include it. The other verbs share
this pattern, but `rebuild` is the new path that the Phase 6 driver will call.

**Fix:** Wrap the TOML parse in `load_manifest` and raise
`ManifestError(f"{path}: {exc}") from exc`.

### IN-07: `_check_bare_name` raises `SpliceError` for a manifest problem and accepts Windows device names

**File:** `tools/reverseapoc/splice.py:574-577`

**Issue:**
- A bad `[[targets]] name` is a manifest error but surfaces as `SpliceError`.
- Names such as `CON` or `NUL`, or names ending in a dot, pass the check. On Windows,
  `build/NUL` is a device, not a file.

The manifest is trusted config, so this is hardening rather than a defect.

**Fix:** Raise `ManifestError`, and reject reserved device names and trailing dots or spaces.

### IN-08: `configure.py` still calls itself a "Phase 2 skeleton"

**File:** `configure.py:4`, `configure.py:21`

**Issue:** The module docstring and the generated header still say "Phase 2 skeleton", even
though the file now carries the Phase 3 `verify` edge.

**Fix:** Change it to "verification targets only (check-orig, parse-le, verify)", without a phase
label.

---

_Reviewed: 2026-10-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
