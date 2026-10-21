---
phase: 04-compiler-identification
reviewed: 2026-10-21T21:59:01Z
depth: standard
files_reviewed: 47
files_reviewed_list:
  - .githooks/commit-msg
  - config/cflags.txt
  - config/tacp/runtime.csv
  - config/ufo2p/runtime.csv
  - config/watcom.toml
  - docs/learnings.md
  - docs/matching.md
  - docs/research/wpack-format.md
  - docs/toolchain.md
  - probe/README.md
  - probe/cg_basic.c
  - tests/conftest.py
  - tests/cpptree.py
  - tests/libtree.py
  - tests/omfimage.py
  - tests/test_cflags.py
  - tests/test_cli.py
  - tests/test_compiler.py
  - tests/test_compiler_real.py
  - tests/test_cppscan.py
  - tests/test_cppscan_real.py
  - tests/test_githooks.py
  - tests/test_hygiene.py
  - tests/test_libmatch.py
  - tests/test_libmatch_real.py
  - tests/test_omf.py
  - tests/test_omf_real.py
  - tests/test_probe.py
  - tests/test_probe_real.py
  - tests/test_splice.py
  - tests/test_targets.py
  - tests/test_watcom.py
  - tests/test_wpack.py
  - tests/test_wpack_real.py
  - tests/watcomtree.py
  - tests/wpackimage.py
  - tools/reverseapoc/cflags.py
  - tools/reverseapoc/cli.py
  - tools/reverseapoc/compiler.py
  - tools/reverseapoc/cppscan.py
  - tools/reverseapoc/libmatch.py
  - tools/reverseapoc/omf.py
  - tools/reverseapoc/probe.py
  - tools/reverseapoc/splice.py
  - tools/reverseapoc/targets.py
  - tools/reverseapoc/watcom.py
  - tools/reverseapoc/wpack.py
findings:
  critical: 0
  warning: 5
  info: 7
  total: 12
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-10-21T21:59:01Z
**Depth:** standard
**Files Reviewed:** 47
**Status:** issues_found

## Summary

This is a phase-wide review of everything that changed between 2aeeb11 and HEAD. It concentrates on
the places where modules meet, which the per-plan reviews could not see: cflags and compiler,
omf with libmatch, probe and cppscan, watcom with wpack, the shared `splice._write_atomic`, and the
error mapping in `cli.main`. No BLOCKER was found. The hash gate, the path and argv checks, the
environment scrub, the wpack containment (`_inside`, `_check_in_tree`) and the atomic writes all
hold up across the module boundaries.

The five warnings are robustness gaps where modules meet:
- the CLI still prints raw tracebacks for some bad inputs (reproduced);
- one output path does not have the orig/ guard;
- a gate refusal becomes a silent "skipped" in `probe calibrate`;
- `libmatch --write` can commit a runtime map built from a partial sweep, and nothing downstream
  can tell;
- stale test gating keeps 10.5 out of the tests of the wrapper's invariants.

No game or compiler bytes were printed or written during the review. The one check on a real
object listed OMF record kinds only.

## Warnings

### WR-01: Bad input files and `-o .` still crash with a traceback instead of `reverseapoc <verb>: error:`

**File:** `tools/reverseapoc/cflags.py:135`, `tools/reverseapoc/libmatch.py:833`, `tools/reverseapoc/compiler.py:571`, `tools/reverseapoc/cli.py:430-443`
**Issue:** `cli._ERRORS` lists the typed error classes plus `OSError`. Three paths raise something
else, which escapes `main()` as a traceback. All three were reproduced:
- `load_cflags` calls `path.read_text(encoding="utf-8")`. A cflags file that is not UTF-8 raises
  `UnicodeDecodeError` (`reverseapoc cc ... --cflags <bad>`).
- `read_runtime_csv` calls `read_text(encoding="utf-8")` in the same way, which hits
  `probe scan --runtime <bad>`, `cppscan --runtime <bad>` and the default config/<exe>/runtime.csv.
- `compile_rule` computes `obj.with_suffix(".err")` before `_check_outputs` runs, so `cc SRC -o .`
  raises a plain `ValueError: WindowsPath('.') has an empty name`. This is the deferred 04-01
  minor. It is a confirmed crash, and the fix belongs with the other two.

`watcom.load_watcom_manifest` already wraps `UnicodeDecodeError` in `ManifestError`. The other
readers should follow the same pattern; project rule: one typed error class per module, mapped
in `cli.main`.
**Fix:**
```python
# cflags.load_cflags
try:
    text = path.read_text(encoding="utf-8")
except UnicodeDecodeError as exc:
    raise CflagsError(f"{path}: not UTF-8 ({exc})") from exc
return parse_cflags(text, versions=versions, where=str(path))

# libmatch.read_runtime_csv
try:
    text = Path(path).read_text(encoding="utf-8")
except UnicodeDecodeError as exc:
    raise LibMatchError(f"{path}: not UTF-8 ({exc})") from exc

# compiler.compile_rule: check the object name before deriving the error file
src, obj = Path(src), Path(obj)
if obj.suffix != OBJ_SUFFIX:
    raise CompilerError(f"{obj} must end in {OBJ_SUFFIX}; the compile deletes and rewrites it")
err = obj.with_suffix(".err")
```
Add one CLI test for each that asserts exit 1 and an `error:` line on stderr.

### WR-02: `probe calibrate --output` can overwrite files in orig/; `libmatch` protects only the `--orig` it was given

**File:** `tools/reverseapoc/cli.py:280`, `tools/reverseapoc/cli.py:131`
**Issue:** The docstring of `refuse_output` says it refuses "an output path inside orig/ or the
Watcom tree". Its callers pass different protected sets:
- `_probe_calibrate` calls `refuse_output(args.output, args.watcom_dir)`. orig/ is not protected,
  so `probe calibrate --output orig/UFO2P.EXE` replaces a game file through `_write_atomic` once
  the compiles finish.
- `_cmd_libmatch` protects `args.orig`. With `--orig /elsewhere --output orig/TACP.EXE`, the real
  orig/ is not protected either.

CLAUDE.md makes "never modify orig/" a hard rule, and the container's read-only mount does not
apply on the host.
**Fix:** Always protect the default trees as well as any override:
```python
# cli._probe_calibrate
refuse_output(args.output, DEFAULT_ORIG, args.watcom_dir, DEFAULT_INSTALL)
# cli._cmd_libmatch
refuse_output(output, args.orig, DEFAULT_ORIG, args.watcom_dir, DEFAULT_INSTALL)
```

### WR-03: `probe calibrate` turns a refusal by the D-13 hash gate into a "skipped" version, exits 0 and writes the calibration

**File:** `tools/reverseapoc/probe.py:778-783`, `tools/reverseapoc/cli.py:279-289`
**Issue:** `calibrate` catches every `CompilerError` from `check_gate` and records the version as
skipped. That includes a mismatching or known-bad compiler binary, a missing BINW compiler and a
missing wibo. `_probe_calibrate` then prints, writes calibration.json and returns 0, even when
every version was refused and `cells` is empty. A later `probe scan --calibration` reports
"consistent: 0 of 0 calibration cells", or a consistent set that leaves out the refused version.
The "calibration skipped:" line is the only sign that anything went wrong. Everywhere else a gate
refusal is fatal: `cc` exits 1.
**Fix:** In `_probe_calibrate`, refuse to write when anything was skipped unless the user asked
for a subset (`--versions`), or at least when no cell was produced:
```python
if not calibration.cells:
    raise ProbeError("no Watcom version passed the gate: " +
                     "; ".join(f"{v}: {r}" for v, r in calibration.skipped))
if calibration.skipped:
    print(calibration.format(), file=sys.stderr)
    return 1  # or: write, but exit 1 so a script or the gate notices
```

### WR-04: `libmatch --write` commits a runtime map built from a partial sweep, and downstream cannot tell

**File:** `tools/reverseapoc/cli.py:133-148`, `tools/reverseapoc/libmatch.py:334-351`, `tools/reverseapoc/cppscan.py:368-378`
**Issue:**
- `load_libraries` records a requested version with no LIB386 directory as `Skipped` and carries
  on. `_cmd_libmatch` refuses only when no library at all was loaded. If 11.0, say, is not
  installed, `libmatch UFO2P --write` silently overwrites the committed
  config/ufo2p/runtime.csv with rows whose `versions` lack 11.0.
- runtime.csv does not record which versions were swept or skipped.
- `cppscan.cpp_only_gap` checks only the versions the rows name. A map from a partial sweep
  (`--versions 10.5`, or a broken install) can therefore still give the full
  `C (wcc386): ...` verdict, although the sweep never held the other versions' C++ libraries.

The drift test in test_libmatch_real catches this only when orig/ and all three trees are present.
**Fix:** Make `--write` (the committed D-06 artifact) refuse any skip of the form `no LIB386
directory`:
```python
missing = [s.version for s in skipped if s.reason == f"no {LIB_DIR} directory"]
if args.write and missing:
    raise LibMatchError(f"--write needs every swept version; not installed: {', '.join(missing)}")
```
Also record the swept versions in the generated-by comment, for example
`# generated by: ... --write; versions 10.5;10.6;11.0`, and have `cpp_only_gap` check the
recorded set instead of the versions in the rows.

### WR-05: Stale test gating keeps 10.5 out of the wrapper invariant tests, and the 10.5 calibration test fails instead of skipping

**File:** `tests/test_compiler_real.py:34`, `tests/test_probe_real.py:88`, `tests/test_probe_real.py:209-216`
**Issue:**
- `RUNNABLE = ("10.6", "11.0")  # 10.5 joins once plans 04-06 and 04-11 fix its BINW compiler`
  and `CALIBRATED = ("10.6", "11.0")  # 10.5 joins once plan 04-11 reinstalls ...` were never
  updated. 04-06 and 04-11 are done, and 10.5 now compiles (`test_compile_real` runs it;
  build/probe/10.5 exists). As a result:
  - The tests of the wrapper's invariants never run for 10.5: environment injection, the
    `-bt=dos` target, error cleanup and stable normalized hashes.
  - The calibration-matrix rows never run for 10.5.
  - 10.5 runs a different path (the NT stub loading the decoded BINW LX compiler), and the docs
    lean on "10.5 and 10.6 byte-identical".
- `test_calibration_with_10_5` gates only on `_require_compiler("10.5")`, then calibrates every
  `SWEPT_VERSIONS` entry and asserts `cal.skipped == []`. With 11.0 missing it fails instead of
  skipping.
**Fix:** Set `RUNNABLE = VERSIONS` and `CALIBRATED = SWEPT_VERSIONS`, or drop the constants, and
remove the stale comments. In `test_calibration_with_10_5`, call `_require_compiler(v, root_dir)`
for every version in `SWEPT_VERSIONS` before `calibrate`.

## Info

### IN-01: The docs say `-zld` suppresses the file-dependency record, but the wrapper's own objects carry COMENT 0xE9

**File:** `docs/toolchain.md:290`, `tools/reverseapoc/compiler.py:179`
**Issue:** toolchain.md reads "always `-zq -zld -bt=dos` (quiet, no file-dependency record,
...)". The same document and learnings.md say the objects carry COMENT class 0xE9 dependency
records. build/logs/cc.log shows `-zld` on the probe compiles, and listing the record kinds of
build/probe/10.5/*/cg_basic.obj (kinds only, no bytes) shows a `COMENT/0xe9` in each. Either
`-zld` does not do what the docs say in these versions, or it only suppresses header
dependencies. The normalized hash hides the difference, so nothing breaks today.
**Fix:** Correct the `-zld` description in toolchain.md, or test a compile with a header and
record what `-zld` actually removes.

### IN-02: cflags accepts `wpp386`, but the compiler wrapper always runs WCC386.EXE

**File:** `tools/reverseapoc/cflags.py:23`, `tools/reverseapoc/compiler.py:184`, `tools/reverseapoc/compiler.py:199-203`
**Issue:**
- `COMPILERS = ("wcc386", "wpp386")`, so a `wpp386@10.6` rule parses.
- `gate_paths` refuses it: "no pinned binaries for wpp386 in config/watcom.toml". That message
  sends the user to the manifest.
- `COMPILER_EXE` and `build_argv` hard-code `BINNT/WCC386.EXE`. If someone later adds wpp386
  paths to `gate_paths`, C++ sources would compile with the C compiler.
**Fix:** Either refuse `wpp386` in cflags until the wrapper supports it, or derive the executable
from `rule.compiler` (`f"BINNT/{rule.compiler.upper()}.EXE"`) together with its gate paths.

### IN-03: Flags are checked against a deny list, while guest paths use an allow list

**File:** `tools/reverseapoc/cflags.py:65-85`
**Issue:** `_check_guest` allows only `[A-Za-z0-9._/-]`. `_check_flag` refuses only `-`, `/`, `\`
and whitespace, and the wrapper-owned prefixes. A `"` in a flag, for example `-dA="x`, reaches
Watcom's own command-line quoting via `list2cmdline`. It could then merge later argv entries
(`-i=`, the source, `-fo=`) into one option, which is exactly what "one flag is one option" is
meant to prevent. This is not observed in practice, because cflags.txt is a tracked file.
**Fix:** Allow only a fixed character set in flags, for example `re.fullmatch(r"-[A-Za-z0-9_=.+]+", flag)`.

### IN-04: The private `splice._write_atomic` is imported by three other modules

**File:** `tools/reverseapoc/compiler.py:175`, `tools/reverseapoc/libmatch.py:43`, `tools/reverseapoc/cli.py:35`
**Issue:** `_write_atomic` is now the shared atomic writer for the gate stamps, runtime.csv and
calibration.json. Importing an underscore name across modules hides that contract. A
refactor of splice could change it without anyone seeing the three callers.
**Fix:** Rename it to `write_atomic` (or move it to a small `fsutil` module) and export it.

### IN-05: The OMF reader decides inconsistently when a Base Frame follows

**File:** `tools/reverseapoc/omf.py:560-563`, `tools/reverseapoc/omf.py:679-686`
**Issue:** `_pubdef` reads the u16 base frame whenever the segment index is 0, even when there is a
group index. `_comdat`'s explicit public base reads it only when both group and segment are 0.
COMDAT's public base has the same layout as PUBDEF's, so one of the two parses the frame wrongly.
The Watcom libraries never use absolute publics or COMDATs, so real data is unaffected.
**Fix:** Pick the single TIS rule for both and add a synthetic test for the `group != 0, seg == 0`
case.

### IN-06: `cppscan._check_table` refuses an empty table at the very end of an object and mislabels `end < start`

**File:** `tools/reverseapoc/cppscan.py:273-281`
**Issue:**
- `le.obj_of_va(start)` uses the half-open `contains`. A legitimate empty XI or YI table
  (start == end) placed at `obj.end` is therefore reported as "not inside the data object".
- `end < start` is reported as "not a multiple of 6 bytes". This is the deferred 04-09 M5.
**Fix:** Look the object up by `start - 1` when `start == end`, or accept `start == obj.end`.
Give `end < start` its own message.

### IN-07: Dead code: `Candidate` and `_Hit.candidate()`

**File:** `tools/reverseapoc/libmatch.py:102-112`, `tools/reverseapoc/libmatch.py:426-429`
**Issue:** Nothing in tools/ or tests/ references them (grep). This is the deferred 04-05 M1.
**Fix:** Delete both.

## Triage of the deferred per-plan minors

Verdict key: **fix** means fix before the phase closes. **folded** means it is covered by a
finding above. **defer** means it can stay deferred. **resolved** means it is already fixed in
HEAD.

| Plan | Item | Verdict | Reason |
|---|---|---|---|
| 04-01 | M-1 stamp ignores known_bad/size/MD5 | defer | A manifest SHA-1 change invalidates the stamp. Only a known_bad flip on an unchanged SHA-1 slips through, which is cheap to close later by storing the whole key-file record in the stamp. |
| 04-01 | M-2 test_cc_json never proves stderr | defer | A gap in the test, not in behaviour. `_cmd_cc` routes the output correctly. |
| 04-01 | M-3 swallowed stamp OSError untested | defer | Only the cache path is affected. |
| 04-01 | M-4 SUMMARY test counts | defer | Planning artifact. |
| 04-01 | M-5 two-space separator inside the banner | defer | No code parses cc.log by field yet. Revisit if a tool ever does. |
| 04-01 | `-o .` raises ValueError | **fix** (folded into WR-01) | Reproduced as a traceback. |
| 04-01 | `out.resolve()==source`, `"xb"` vs `"wb"` not pinned | defer | Behaviour is correct, only unpinned. |
| 04-01 | killed mid-write leaves a stray .tmp | defer | Hidden dot-file in build/, harmless. |
| 04-01 | SUMMARY states the old `-i` rule | defer | Planning artifact. |
| 04-02 | M1 test_omf_real tolerates GRAPH.LIB failures | defer | Real-data coverage. Tighten when GRAPH.LIB is next touched. |
| 04-02 | M2 unframeable module stops the walk, untested | defer | Documented, and recorded as a failure, never silent. |
| 04-02 | M3 omfimage docstring 0xA5 / GARBAGE unused | defer | Test-helper wording. |
| 04-02 | M4 untested branches | defer | Not reached by Watcom libraries. IN-05 adds one more such branch. |
| 04-02 | M5 SUMMARY lines | defer | Planning artifact. |
| 04-02 | M6 16 MiB buffer per SEGDEF can raise MemoryError | defer | Inputs are libraries from hash-verified ISOs. Add a total-size cap if untrusted OMF is ever read. |
| 04-03 | M1 qsort tie order for n>=16 pinned only by the ISO test | defer | The ISO-gated test is the real oracle. A synthetic n>=16 tie fixture would be nice to have. |
| 04-03 | M2-M5 (version bytes, unused offsets, error text, initial window) | defer | Cosmetic, or covered by the CRC check before decoding. |
| 04-03 | M6 SUMMARY claims CID-01 complete | defer | Planning artifact. |
| 04-04 | M1, M2, M4-M6, M8, M9 | defer | Test hygiene and wording. |
| 04-04 | M3 `_require_compiler` turns a gate failure into a skip | defer | Session gate G10 fails on any non-10.5 real skip. See WR-05 for the related stale gating. |
| 04-04 | M7 `rmtree(ignore_errors)` + `mkdir` FileExistsError on Windows | defer | Possible flake in real tests only. Use `mkdir(exist_ok=True)` if it is ever seen. |
| 04-05 | M1 Candidate dead code | defer (IN-07) | Delete when convenient. |
| 04-05 | M2 rule (a) ignores the shared `publics` argument | defer | The signature is shared by both rules on purpose. |
| 04-05 | M3 negative tests, M4 displacement term untested | defer | Test gaps. |
| 04-05 | M5 hex case inconsistent | defer | Cosmetic. |
| 04-05 | M6 publics union across alternatives | defer | The rows cover the same range and bytes, so `CHK_PUBLIC in r.publics` (probe) still points at the right code. |
| 04-05 | M7 LPUBDEF statics under publics | defer | Only widens rule (b)'s evidence set. |
| 04-05 | read_runtime_csv accepts missing cells and drops extra ones | defer | cppscan fails loudly later, and the drift test compares against a fresh run. |
| 04-05 | partial-overlap message, per-rule resolved counts include dropped ranges | defer | Report wording only. |
| 04-06 | M1 OSError reading a part not wrapped | defer | It still reaches `main` as an error line, but it aborts the remaining versions of `install-watcom` and leaves `.partial`. Wrap it when the install loop is next touched. |
| 04-06 | M2 decoded file mtime, M3 corrupt-part cause | defer | Cosmetic, or a test gap. |
| 04-07 | M1-M4 | defer | Test strength and speed, and the SWEPT_VERSIONS label. WR-04 covers the partial-sweep risk behind M4. |
| 04-08 | M2 object_code ignores `unmaskable`, skips COMDAT code while chk_sites counts COMDAT | defer | The probe has no COMDAT and no LIDATA code. State it in probe/README. |
| 04-08 | M3 switch compares cover eax/al only | resolved | `_shapes_line` now states the limit. |
| 04-08 | M4 bare opcode lengths in `_jump_at` | resolved | Now `_REL8_SIZE` and `_REL32_SIZE`. |
| 04-08 | SUMMARY frontmatter stale, README nits | defer | Planning and docs wording. |
| 04-08 | `_movsd_runs` filters only `offset < len` | defer | Negative offsets are unreachable: scan_exe filters to `[base, end)`, and OMF offsets are >= 0. |
| 04-09 | M1, M3, M4, M6, M7 | defer | Test gaps and wording. M3's OMF displacement is 0 at the XIB/XIE/YIB/YIE sites in real data. |
| 04-09 | M5 end<start reported as "not a multiple of 6" | defer (IN-06) | Message only. |
| 04-09 | `_read_problem` OMFError untested, partial verdict prefix, `_init_segment` does no byte compare | defer | Consumers match `C (wcc386): ` with the colon. A wrong segment fails loudly in `_bound_addresses`. |
| 04-10 | consistent: header names its filter | resolved | The header now says "decisive idiom families ... only". |
| 04-10 | "flat 32-bit (-mf)" stronger than the data | defer | Wording. The LE big-flag count is reported next to it. |
| 04-10 | NOEMU387 count can never be non-zero | defer | State it in the fpu line or toolchain.md, since the evidence cannot show NOEMU387. |
| 04-10 | chk_calls not mask-aware, bare `+1` (probe.py:914) | defer | The `+1` is the call opcode byte. Name it (`_CALL_OPCODE_SIZE`) under the named-offsets rule when convenient. |
| 04-10 | sizes probe, by-value and shared-rep copies, UFO2P -4r on two sites | defer | Evidence limits are documented. Phase 5 matches decide. |
| 04-11 | "-s for most code" has no committed count | defer | Recorded in learnings.md as a throwaway count. Phase 5 per-function matches supersede it. |
| 04-11 | STACK.md says LE (kickoff research) | defer | History, left as written. |
| 04-11 | config/watcom.toml:37 and :106 BINNT notes say "the real LE compiler" | **owner decision** | The manifest is protected. Only the owner may edit it. learnings.md already flags the notes as stale. Not a code defect. |
| 04-12 | VALIDATION row citations, SUMMARY self-check scope | defer | Planning artifacts. |

---

_Reviewed: 2026-10-21T21:59:01Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
