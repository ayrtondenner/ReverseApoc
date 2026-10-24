---
phase: 05-split-and-first-matches
fixed_at: 2026-10-24T06:10:36Z
review_path: .planning/phases/05-split-and-first-matches/05-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 5
skipped: 1
status: partial
---

# Phase 5: Code Review Fix Report

**Fixed at:** 2026-10-24T06:10:36Z
**Source review:** .planning/phases/05-split-and-first-matches/05-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (WR-01, IN-01..IN-05)
- Fixed: 5 (WR-01, IN-01, IN-03, IN-04, IN-05)
- Skipped: 1 (IN-02, left open on purpose)

Each fix was written test-first. The new tests failed before the change and pass after it, and the
core WR-01 assertions also fail when `object_root` is reverted. There is one commit per finding, made
on `main` in the main checkout. No worktree was used.

## Fixed Issues

### WR-01: `check` overwrites ninja's unit objects with objects built under its own `--cflags`/`--watcom-dir`

**Files modified:** `tools/reverseapoc/check.py`, `tests/test_check.py`, `tests/test_check_real.py`
**Commit:** bcf46d7
**Applied fix:** A new `check.object_root(build_dir, options)` returns `build_dir` only when
`--cflags`, `--watcom-manifest` and `--watcom-dir` are all the committed defaults that ninja's `cc`
edge uses. Otherwise it returns `build_dir/check-custom`. `check_source` and the compiling path of
`land_all` write `obj`, `base` and `target` under that root. Ninja's own land step
(`compile_fn=None`) still reads `build/<exe>/obj`. `check-custom` does not match `[a-z0-9_]+`, so it
can never be an EXE stem or a `build.ninja` output path.

With default options, check keeps the old paths. The 05-14 `target`/`land` argv and the rest of the
`check` CLI are unchanged.

Tests:
- Fake compiler: after `check --cflags`, `--watcom-manifest` or `--watcom-dir`, ninja's object
  keeps its bytes and mtime, every compile lands under `check-custom`, and the `land` verb (ninja
  verify's step) lands the committed-flags object with the manifest SHA-1. A second test shows that
  default options keep `build/<exe>/obj`.
- Container (`test_ninja_keeps_committed_objects_after_a_custom_check`): configure + ninja build
  `u_000a34f0`, then `check` runs with an experimental cflags file (`-4r -fpi`). Ninja's object is
  unchanged and `ninja -n` reports no work. A further ninja run still yields the config/cflags.txt
  object, and the experiment's object really differs from it. With `object_root` reverted, this
  test fails on the unchanged-object assertion.

The review also suggested optional hardening: a provenance stamp, or refusing a stale object in
`land`. It was not added, because the required outcome (check's non-default objects never reach
ninja's paths) is met by the separation.

### IN-01: A `static` function always fails `check`, and the messages do not say why

**Files modified:** `tools/reverseapoc/check.py`, `tests/test_check.py`, `docs/learnings.md`
**Commit:** 1fecd6b
**Applied fix:** A public that names no row of the unit and comes from an LPUBDEF
(`Public.local`) now gets a specific reason. For code it reads: "public X is a static (LPUBDEF)
function, which check cannot pair with a row: give it its row's func_ name or keep the row
INCLUDE_ASM". Static data gets "make it non-static". The `land` verb refuses with the same reason.
docs/learnings.md records the limit. Tests cover check JSON, land output and static data.

### IN-03: `check` skips the D-12 source checks for a unit with no game or thunk rows

**Files modified:** `tools/reverseapoc/check.py`, `tests/test_check.py`, `tests/test_check_real.py`
**Commit:** 300ee86
**Applied fix:** `account_unit` now runs `source_marks` for every unit file, even when the unit has
no game or thunk row, so its problems (a refused conditional, a marker or definition naming another
unit's function) are mismatches, matching configure.py.

`account_unit` and `check_source` take `unit_file` (default True). Only the 05-18 runtime pair
passes `unit_file=False`: it reads Watcom's own CMAIN386.C in place, a file configure never reads.
`rt_cmain386` is itself a units.csv unit, so the exemption has to be explicit and cannot be
inferred from units.csv. The pair's test was updated to pass it.

Tests: a runtime-only unit whose file has `#ifdef` or a foreign marker fails `check` and `land`, a
clean file passes as the control, and `unit_file=False` keeps the exemption. The container real
tests (the CMAIN386 pair) still pass.

### IN-04: `configure.py --config DIR` swaps the CSVs but not the manifest

**Files modified:** `configure.py`, `tests/test_configure.py`
**Commit:** aaa08e6
**Applied fix:** `collect_units` reads `DIR/targets.toml`. A config dir without one is refused with
a ConfigureError naming the file, and nothing is written. The default `config/` resolves to the same
manifest as before. No refusal was weakened, and no hash manifest or build script was touched to
make a check pass.

Tests: a tmp config whose targets.toml names SYN.EXE gets SYN's unit edges and none of UFO2P's.
A config dir without targets.toml is refused. The tmp split tree used by the configure tests now
carries its own manifest.

### IN-05: The committed-CSV address parser accepts more than `0x%08X`

**Files modified:** `tools/reverseapoc/functions.py`, `tests/test_functions.py`
**Commit:** 2d74826
**Applied fix:** `_parse_address` requires `0x` followed by 8 upper-case hex digits, which is
exactly what the writers emit, before calling `int()`. Any other cell is refused as
`<file>: data row N: <column> '<cell>' is not a hex address written as 0x%08X ...`. All committed
CSVs (functions, units, symbols, boundaries, runtime) already comply: 10,820 cells were checked.

Tests: each reader's address column (functions start and end, units, symbols, boundaries) is tried
with `-0x10`, `0x1_0`, a leading space, a trailing space, `+0x...`, a short form, lower case, `0X`
and no prefix. The written form still reads.

## Skipped Issues

### IN-02: Every jump-table function is refused: wcc386 puts the table before the public

**File:** `tools/reverseapoc/relocs.py:213-218`
**Reason:** Left open on purpose, as instructed. The refusal fails closed by design: a jump-table
function is never reported as matched. Pairing a leading table's data-in-code row with its segment
span is deferred to Phase 6/7, with the review's probe as the acceptance case.
**Original issue:** wcc386 10.6 places a switch's table at `_TEXT+0`, before the function's
public. The relocation check therefore finds the table target in no own public and refuses the
function.

## Verification

Everything ran in the **main checkout** (`main`). No isolated worktree was used, so these results
can be reproduced from this tree.

- Host: `uv run pytest -q` gave `1605 passed, 26 skipped`. `uv run ruff check .` gave `All checks
  passed!`
- Container, run after the host suite had finished, never at the same time:
  - `docker compose run --rm -T build bash -lc "uv sync --locked && uv run python configure.py &&
    ninja && ninja lint && ninja verify"` exited 0. Rebuild: UFO2P, TACP and SMKP SHA-1 == manifest.
    Land: `OK UFO2P.EXE ... landed 1` and `OK TACP.EXE ... landed 1`.
  - `uv run reverseapoc check ufo2p/u_000a34f0 --json` exited 0 with `ok: true`.
  - `uv run reverseapoc check tacp/u_00054f20 --json` exited 0 with `ok: true`.
  - `uv run pytest -q tests/test_check_real.py` gave 4 passed, including the WR-01 configure + ninja
    test and the CMAIN386 pair.

---

_Fixed: 2026-10-24T06:10:36Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
