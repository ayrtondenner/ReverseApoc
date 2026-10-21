---
phase: 04-compiler-identification
fixed_at: 2026-10-21T22:32:28Z
review_path: .planning/phases/04-compiler-identification/04-REVIEW.md
iteration: 1
findings_in_scope: 12
fixed: 11
skipped: 1
status: partial
---

# Phase 4: Code Review Fix Report

**Fixed at:** 2026-10-21T22:32:28Z
**Source review:** .planning/phases/04-compiler-identification/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 12 (fix_scope: all)
- Fixed: 11
- Skipped: 1 (IN-04, as the orchestrator allowed)

Every fix was written test-first: the new test was seen failing before the change, except for the
IN-05 PUBDEF pin (PUBDEF already followed the spec) and the IN-07 deletion of dead code. Each fix
is one `fix(04): ...` commit with its tests.

## Verification

- **Where it ran:** the fixes were made and committed in an isolated worktree
  (`.claude/worktrees/rf-04-*`, branch `gsd-reviewfix/04-97`). The real-file tests there used
  `REVERSEAPOC_ORIG`, `REVERSEAPOC_WATCOM_DIR` and `REVERSEAPOC_WATCOM_MEDIA`, pointed at the main
  checkout. After `main` was fast-forwarded, the gate ran again **in the main checkout**, with its
  default `orig/` and `third_party/`. That run can be reproduced from the tree as it is now.
- **Main checkout, final:** `uv run pytest -q`: 1027 passed, 6 skipped. All 6 skips depend on the
  platform: 2 for Windows file names, 1 for non-UTF-8 byte names, 3 that run only inside the
  container. No real-file test skips. `uv run ruff check .`: all checks passed.
- **Baseline before the fixes** (worktree, media env unset): 965 passed and 15 skipped. 9 of those
  skips were watcom-media skips, caused only by the unset media variable.
- **Unchanged:** `config/ufo2p/runtime.csv` and `config/tacp/runtime.csv` are byte-identical.
  `libmatch UFO2P --write` and `libmatch TACP --write`, run against the real trees, reproduced them
  exactly (`cmp` against HEAD), and the drift test passes. `config/watcom.toml`,
  `config/targets.toml`, `orig/` and `third_party/` were not touched; `check-watcom` reports
  10 ok. `.planning/config.json` and `.planning/milestone.lock` were not staged.

## Fixed Issues

### WR-01: Bad input files and `-o .` still crash with a traceback

**Files modified:** `tools/reverseapoc/cflags.py`, `tools/reverseapoc/libmatch.py`, `tools/reverseapoc/compiler.py`, `tests/test_cli.py`
**Commit:** 949d646
**Applied fix:**
- `load_cflags` now wraps `UnicodeDecodeError` in `CflagsError`, and `read_runtime_csv` wraps it in
  `LibMatchError`.
- `compile_rule` checks the `.obj` suffix (new `_check_object_name`) after the guest-path checks
  and before it derives the `.err` name. The order of the existing path refusals is unchanged.
- Four CLI tests assert exit 1 and an `error:` line: `cc --cflags`, `cppscan --runtime`,
  `probe scan --runtime` and `cc -o .`.

### WR-02: Outputs could land in orig/ or the Watcom tree

**Files modified:** `tools/reverseapoc/cli.py`, `tests/test_cli.py`
**Commit:** 08fd818
**Applied fix:** `_probe_calibrate` and `_cmd_libmatch` now always pass `DEFAULT_ORIG` and
`DEFAULT_INSTALL` to `refuse_output`, as well as any `--orig` or `--watcom-dir` override.
Parametrized tests monkeypatch the defaults to a temporary tree, so the real orig/ is never at
risk.

### WR-03: `probe calibrate` turned a hash-gate refusal into "skipped" and exited 0

**Files modified:** `tools/reverseapoc/cli.py`, `tests/test_cli.py`, `probe/README.md`
**Commit:** 353e363
**Applied fix:** If any version was skipped (or no cell was produced), the verb prints the table,
raises `ProbeError` naming each refused version with its reason, and writes no calibration.json.
`probe.calibrate()` itself still returns the skips. The README says how to calibrate a subset
(`--versions`).

### WR-04: `libmatch --write` could commit a runtime map from a partial sweep

**Files modified:** `tools/reverseapoc/cli.py`, `tests/test_cli.py`, `docs/toolchain.md`
**Commit:** 9db7bfd
**Applied fix:**
- `--write` now refuses with a `LibMatchError` (`_refuse_partial_sweep`) unless every
  `SWEPT_VERSIONS` entry and every `--versions` entry loads at least one OMF library.
- The refusal covers a missing LIB386 directory, a LIB386 directory with no OMF library, and a
  `--versions` subset.
- `--output` still accepts a partial sweep, and a test pins that.
- The runtime.csv format did not change (D-06), as the orchestrator asked.

### WR-05: Stale gating kept 10.5 out of the wrapper and calibration tests

**Files modified:** `tests/test_compiler_real.py`, `tests/test_probe_real.py`, `docs/learnings.md`
**Commit:** 71cf495
**Applied fix:**
- `RUNNABLE` is gone (the tests use `VERSIONS`), and `CALIBRATED = SWEPT_VERSIONS`.
- The calibration fixture now calibrates only the versions that can run here. A missing version
  skips only its own rows: `_Calibrated.cell` skips with that version's reason.
- Every 10.6 calibration row is also generated for 10.5.
- `MEASURED_CONSISTENT` gains the same eight 10.5 cells, which gives the 18 of 30 cited in
  docs/toolchain.md.
- `test_calibration_with_10_5` now calls `_require_compiler` for every version it sweeps.
- Proof: with a tree that held only 10.5 (a scratch junction, since removed), that test skipped
  instead of failing, the 10.5 rows passed, and the 10.6 and 11.0 rows skipped. The old code failed.
- **New finding:** 10.5 writes no `-fr=` error file at all (10.6 and 11.0 do). The error message
  still reaches the captured output, and no stray file appears anywhere. The cleanup test now
  records this per version, and docs/learnings.md has an entry for it.

### IN-01: The docs claim about `-zld` was wrong

**Files modified:** `docs/toolchain.md`, `docs/learnings.md`
**Commit:** 4778a10
**Applied fix:**
- **Measurement:** I counted COMENT classes (counts and lengths only, no bytes) in objects from a
  plain source and a header-including source, compiled with and without `-zld` on 10.5, 10.6
  and 11.0.
- **Without `-zld`:** each object has one COMENT 0xE9 per file (the source, then each header),
  plus one empty 0xE9.
- **With `-zld`:** only the empty 0xE9 end-of-list marker remains.
- toolchain.md now describes this, and learnings.md records the measurement. The wrapper was
  right, so no code changed.

### IN-02: cflags accepted `wpp386`, but the wrapper always runs WCC386.EXE

**Files modified:** `tools/reverseapoc/cflags.py`, `tests/test_cflags.py`, `config/cflags.txt`
**Commit:** ca4893a
**Applied fix:** `COMPILERS = ("wcc386",)` plus `UNSUPPORTED_COMPILERS = ("wpp386",)`. A `wpp386`
rule is now refused at the rule, with the line number and "not supported by the wrapper yet".
The comment in cflags.txt changed to match; the committed rule did not change.

### IN-03: Flags were checked against a deny list

**Files modified:** `tools/reverseapoc/cflags.py`, `tests/test_cflags.py`, `config/cflags.txt`
**Commit:** 15ce10f
**Applied fix:** After the checks that have their own messages, a flag must fullmatch
`_SAFE_FLAG = -[A-Za-z0-9_=.+]+`. Quotes and shell characters are now refused, and a
parametrized test covers them. The committed rule (`-4r -s -fpi`) and the "prefix only"
test flags still pass.

### IN-05: The OMF reader disagreed on when a Base Frame follows

**Files modified:** `tools/reverseapoc/omf.py`, `tests/omfimage.py`, `tests/test_omf.py`
**Commit:** 50e2915
**Applied fix:**
- **The rule:** TIS OMF 1.1 places PUBDEF's Base Frame after a Base Segment index of 0, whatever
  the Base Group index. It gives COMDAT's explicit public base the same layout. So `_pubdef` was
  right and `_comdat` was wrong: it read the frame only when the group index was 0 as well.
- **Reader:** `_comdat` now reads the frame whenever the segment index is 0.
- **Test helpers:** `comdat32` encodes the spec rule, and `pubdef32` can now emit a frame. Before,
  both helpers mirrored the reader rather than the spec.
- **Tests:** two synthetic tests pin the group != 0, segment == 0 case for PUBDEF and for COMDAT.
  The COMDAT one failed before the fix.
- **Real data:** `tests/test_omf_real.py` and `tests/test_libmatch_real.py` pass unchanged.
- **Caveat:** no local copy of the TIS specification exists in the repo, and no web tool was
  available. The rule comes from the spec text as I remember it, not from reading a copy here.
  It is marked for human verification below.

### IN-06: `_check_table` refused an empty table at the very end of an object

**Files modified:** `tools/reverseapoc/cppscan.py`, `tests/test_cppscan.py`
**Commit:** 6fd647a
**Applied fix:** `end < start` now has its own message ("ends before it starts"). An empty table
(start == end) that `obj_of_va` misses, because the lookup is half-open, falls back to the object
that ends exactly at `start`. Both cases have tests, and `tests/test_cppscan_real.py` still passes.

### IN-07: Dead code: `Candidate` and `_Hit.candidate()`

**Files modified:** `tools/reverseapoc/libmatch.py`
**Commit:** a122147
**Applied fix:** Grep found no reference in tools/, tests/ or the docs, so I deleted both. This
was trivially safe, so I fixed it even though the orchestrator allowed a skip.

## Needs human verification

- **IN-05 (OMF logic):** confirm against a copy of the TIS OMF 1.1 specification that COMDAT's
  explicit public base carries a Base Frame whenever its Base Segment index is 0. Watcom's
  libraries never use this case, so real data cannot tell the two rules apart.
- **WR-03 (behaviour choice):** `probe calibrate` now refuses to write when any version is
  refused, not only when every version is refused. Partial calibrations need `--versions`.

## Skipped Issues

### IN-04: The private `splice._write_atomic` is imported by three other modules

**File:** `tools/reverseapoc/compiler.py:175`, `tools/reverseapoc/libmatch.py:43`, `tools/reverseapoc/cli.py:35`
**Reason:** Skipped by orchestrator ruling. Renaming or moving the shared atomic writer is a
refactor of a helper used by four modules. It is better done on its own, with behaviour-pinning
tests.
**Original issue:** `_write_atomic` is now the shared atomic writer for the gate stamps,
runtime.csv and calibration.json, but it is imported across modules under an underscore name.

---

_Fixed: 2026-10-21T22:32:28Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
