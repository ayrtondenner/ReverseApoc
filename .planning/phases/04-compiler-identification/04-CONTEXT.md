# Phase 4: Compiler identification - Context

**Gathered:** 2026-10-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Know and prove the exact Watcom version and default flags that built UFO2P.EXE (`ufo24`) and
TACP.EXE (`tac4`). The original compilers (10.5, 10.6, 11.0) run under wibo 1.2.0 in Docker from
the read-only `third_party/watcom/<ver>/` trees. A `compiler@version` wrapper reads
`config/cflags.txt`. A masked library match places the CLIB/MATH runtime modules in each code
object. The codegen probe is counted in non-library code only. A C vs C++ scan runs, and the
results with per-flag evidence are recorded in `docs/toolchain.md`.

Not in this phase: function split, Ghidra, omf2elf, objdiff, matching game functions (all Phase 5).
SMKP.EXE stays out (SMKP-01, v2).

Requirements: CID-01..CID-06 (`.planning/REQUIREMENTS.md`).

</domain>

<decisions>
## Implementation Decisions

### 10.5's damaged compiler
- **D-01:** Write our own stdlib wpack decoder in `tools/reverseapoc/`, called by `install-watcom 10.5`, so every contributor gets the same real `BINW/WCC386.EXE` (567,558 bytes) from `DISKIMGS/DISK02/PCK00017.1` + `DISKIMGS/DISK03/PCK00017.2`. Pin the decoded file's size and hashes in `config/watcom.toml`; this replaces the KNOWN BAD entry for the CD stub. **Time box: about one day.** If the decoder isn't working by then, defer 10.5 ("run only if the 10.6 result is ambiguous"), record the deferral in toolchain.md and the VERIFICATION, and reword CID-01 for 10.5 accordingly.
- **D-02:** The probe and library sweep cover exactly 10.5, 10.6 and 11.0. 11.0a/11.0b (already in `watcom.toml`) come in only if 11.0 turns out to be a candidate. No 10.5a.
- **D-03:** Once per version, the probe is compiled natively on the Windows host (BINNT binaries) and under wibo in the container, and the object hashes must be identical. This check is manual and logged (e.g. under `build/gate/04-*`), not CI. A difference means a wibo bug, not codegen.

### Library match and runtime map
- **D-04:** Lift KKND-Decomp's `tools/lib_match.py` (CC0, 115 lines; masked-byte matching of OMF library modules), keeping a derivation header as `le.py` does. Add a new stdlib OMF reader, `tools/reverseapoc/omf.py`, covering the LIB dictionary/pages, THEADR, LNAMES, SEGDEF, GRPDEF as needed, PUBDEF, LEDATA, LIDATA and FIXUPP: enough to get each module's code bytes and fixup positions to mask. Phase 5's `omf2elf.py` grows from this module. — **Reversibility:** costly — Phase 5's omf2elf builds on its API.
- **D-05:** Scan every 32-bit library in each version's `LIB386` tree (CLIB3R, CLIB3S, MATH3R, MATH3S, MATH387R/S, EMU387 and whatever else is there), not only CLIB3R/MATH3R. Which of 3R vs 3S and 387 vs emulator matches is flag evidence for D-08.
- **D-06:** The result is committed as `config/<exe>/runtime.csv`: address range, module, library, the set of matching versions, and public names. It holds addresses and Watcom symbol names only, never bytes. A real-file test re-derives it and fails on drift (skipped without `orig/` and `third_party/watcom/`, like other real-file tests). The probe idiom counts exclude these ranges, and Phase 5 seeds `functions.csv` and the Ghidra cross-check from it. — **Reversibility:** costly — Phase 5 consumes the file format.
- **D-07:** Versions are recorded per module. A module whose bytes are identical across all swept versions is "uninformative". toolchain.md names the linked-library version from the modules that discriminate, and reports it separately from the game-code compiler version (the probe, D-10). A mix (e.g. most modules 10.6, a few from another version, as in Theme Hospital) is reported as a mix, not voted away.

### Flags and evidence bar
- **D-08:** Phase 4 proves the flags a whole-binary scan of non-library code can show, with evidence for each flag: calling convention (`-3r`/`-3s`, consistent with D-05), stack checks (`-s`, i.e. absence of `__CHK` calls), FPU mode (`-fpi` vs `-fpi87`), CPU scheduling hints (`-4`/`-5`) and memory model. `-o*` and `-zp` go into toolchain.md as "candidate, evidence pending", each with what would prove it, and Phase 5's first matches confirm them. CID-05 is met for the observable flags.
- **D-09:** Evidence is gathered separately for each EXE (UFO2P `ufo24`, TACP `tac4`): library map, probe counts, flag scans and C/C++ scan. toolchain.md gets one column per EXE. "Both EXEs use the same flags" is a finding, never an assumption.
- **D-10:** Each probe idiom is counted in non-library code of both code objects: byte compare as `setcc al; and eax,0FFh` vs a branch, counted-loop bound in `ebx` vs `ecx`, switch compare order, and the others the probe sources cover. A version counts as identified when the counts favour one family and nothing contradicts it. Ties are stated as ties, e.g. "10.6 (10.5 byte-identical on the probe)", and no time is spent separating versions that emit the same code. Exact-sequence matching of the probe's compiled bytes is not required.

### Compiler wrapper
- **D-11:** The entry point is `uv run reverseapoc cc SRC -o OBJ`, a new CLI verb following the existing `_cmd_<verb>` pattern, with the code in `tools/reverseapoc/compiler.py`. It runs the compiler under wibo in the container, or natively on the Windows host. — **Reversibility:** costly — Phase 5's configure.py/ninja rules and Phase 6's guardrail hooks call it by name.
- **D-12:** `config/cflags.txt` holds one rule per line, `<glob>  <compiler>@<version>  <flags...>` (e.g. `*  wcc386@10.6  -5r -s ...`), with `#` comments. A `*` default comes first, the last matching rule wins, and the wrapper refuses a source that no rule matches. This mirrors docs/matching.md's "Module / file glob → Compiler@version → Flags" table. — **Reversibility:** costly — every unit's build reads it.
- **D-13:** Before compiling, the wrapper checks the size and SHA-1 of the compiler binaries against `config/watcom.toml` (`BINNT/WCC386.EXE`, plus `BINW/WCC386.EXE` for 10.x, plus `BINNT/WCCD386.DLL` for 11.0). It refuses on a mismatch or a KNOWN BAD file, and writes the tool's own banner (e.g. "Version 10.6") into the build log. Hashes are cached per run so the check stays cheap. It reuses `watcom.load_watcom_manifest` and its validators.
- **D-14:** Watcom reads `/` as an option switch and splits paths on spaces, so the wrapper rewrites paths to relative paths with backslashes (as decomp.me does) and refuses any path containing a space or starting with `-`, the same allowlist idea `configure.py` got in plans 03-06/03-07. Include paths resolve only to the selected version's own `H/` tree, never the host's or another version's.

### Decided after research (owner, 2026-10-21)
- **D-15:** `wpack.py` is an independent implementation written from a format description. The description (header layout, LZHUF stage, concatenation of the .1/.2 parts, the qsort tie order) goes in `docs/research/wpack-format.md` first. Open Watcom's OWPL-licensed `bld/wpack` is cited only as the format reference; none of its code or comments is copied into GPLv3 `tools/`. The classic 1988 LZHUF `d_code`/`d_len` tables may be reused.
- **D-16:** Per-EXE config directories use the lowercase stem: `config/ufo2p/`, `config/tacp/` (so D-06's file is `config/ufo2p/runtime.csv`). The manifest name (`UFO2P.EXE`) stays the lookup key, and one helper maps the name to the directory. Phase 5's `functions.csv` follows the same rule. — **Reversibility:** costly — Phase 5 and 6 tools resolve paths through it.

### Claude's Discretion
- The probe sources are written in-house, a clean-room C89 set covering mosura's documented constructs (byte compare return, counted loop, switch order) plus constructs the flag scans need. mosura's licence is unverified, so its files are not copied.
- The C vs C++ scan method (CID-06): vtable-shaped pointer tables in obj2, `__wcpp_` routines via the runtime map, XI/YI static-init segments, mangled `W?` names. Output per EXE.
- Module layout under `tools/reverseapoc/` (e.g. `wpack.py`, `omf.py`, `libmatch.py`, `compiler.py`, `probe.py`), test layout, CLI verbs other than `cc`, and where the probe sources live.
- How the spike "wibo 1.2.0 runs wcc386.exe for each version in Docker" is run and recorded (`/gsd-spike`).
- Settled from research (04-RESEARCH.md):
  - D-05's sweep covers the whole `LIB386` tree, and each non-OMF library (COFF under `NT/`) is skipped with its reason reported.
  - `omf.py` supports COMDAT and Easy OMF (COMENT 0xAA) now.
  - The wrapper scrubs the environment (no inherited `WCC386`/`INCLUDE`/`WATCOM`), always passes `-bt=dos -zq -fr= -zld`, and captures the banner from a no-argument run.
  - D-03's cross-check compares objects with THEADR and COMENT 0xE9 records dropped (they carry absolute paths and timestamps).
  - The probe idioms are calibrated per version and flag set before game code is counted.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and gates
- `.planning/ROADMAP.md` (Phase 4 section): goal, success criteria, prerequisite, spike line.
- `.planning/REQUIREMENTS.md`: CID-01..CID-06.
- `docs/workflow.md` ("Milestone 1 roadmap" table, Phase 4 row; hooks table: compiler wrappers are guarded in Phase 6).
- `docs/superpowers/specs/2026-10-19-reverseapoc-design.md`: compiler hypothesis, bring-your-own-compiler rule.
- `CLAUDE.md` and `.claude/rules/`: hard rules (compiler never in an image; nothing proprietary committed).

### Compiler evidence and research
- `docs/toolchain.md`: "Compiler" (Evidence, Hypothesis, Flags, C not C++), "Getting the Watcom compilers" (ISOs, layout, what is on the discs: BINNT loader on 10.x, damaged 10.5 BINW), "wibo", "Version pins".
- `docs/matching.md`: "Compiler and flags per module" table that Phase 4 starts filling.
- `docs/learnings.md`: the BINNT stub and the 10.5 damaged compiler.
- `.planning/research/PITFALLS.md`: the compiler pitfalls (library match first, then probe in non-library code only; mixed versions; damaged 10.5 binary; native vs wibo cross-check; hash every compiler binary).
- `docs/research/notes-target-binary-and-toolchain.md`: banner dating, mosura codegen fingerprint, NHL95PC libmatch, decomp.me's wibo invocation (`-zq`, `-i=`, `/`→`\`).
- `docs/research/notes-own-pipeline-reuse-inventory.md`: KKND `tools/lib_match.py` (CC0) and decomp.me `compilers.py` command lines.
- `.planning/research/STACK.md`, `.planning/research/ARCHITECTURE.md`: where the compiler wrapper sits in the pipeline.

### Code and config to change or reuse
- `config/watcom.toml`: media and key-file hashes for 10.5/10.6/11.0/11.0a/11.0b (`known_bad`, `skip_dirs`).
- `tools/reverseapoc/watcom.py`: `load_watcom_manifest`, `KeyFile`, `WatcomMedia`, `check_version`, `install_version` (the wpack decoder hooks into install).
- `tools/reverseapoc/iso9660.py`: stdlib ISO reader used to read `DISKIMGS/` from the 10.5 ISO.
- `tools/reverseapoc/targets.py`: field validators and `hash_file`/`FileHashes` shared with watcom.py.
- `tools/reverseapoc/le.py`: `LE` objects, pages, `fixups()` (target-side masking for the library match), `load_flat`.
- `tools/reverseapoc/cli.py`: verb pattern and `main()` except tuple.
- `docker/Dockerfile`, `docker/compose.yaml`: wibo 1.2.0 at `/usr/local/bin/wibo`, `third_party/watcom` mounted read-only at `/work/watcom`, OW v2 `wdis`/`wlink`/`wlib` on PATH.
- `configure.py`: path allowlist pattern (03-06/03-07) for D-14.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `watcom.py` already parses and validates the media manifest, checks key files by size/MD5/SHA-1 (`check_version`), and installs ISOs into `third_party/watcom/<ver>/` with a retrying replace. The wrapper's hash gate (D-13) and the 10.5 decode step (D-01) build on these.
- `iso9660.py` reads files out of the ISO in memory with path-traversal and loop guards, so the PCK00017 parts can be read straight from the 10.5 ISO.
- `le.LE` gives objects (`base`, `vsize`), page mapping and de-duplicated internal fixups with `src_va`/`size`. That is enough to mask target-side fixup bytes when sliding library modules over obj1.
- `tests/conftest.py`: `ORIG_DIR`/`REVERSEAPOC_ORIG` override and the real-file skip pattern. `REVERSEAPOC_WATCOM_MEDIA` is already used by the watcom tests.

### Established Patterns
- Stdlib-only Python 3.14 tooling under `tools/reverseapoc/`, one module per concern, a typed error class per module mapped in `cli.main()`.
- Real-file tests are skipped unless the user-supplied files exist. Synthetic fixtures never embed proprietary bytes. Output prints offsets, counts, hashes and names, never game or compiler bytes.
- Expected hashes come from the TOML manifests through their loaders, never copied into tests (D-15/D-21 from Phase 3).
- Derived code keeps a derivation header (KKND CC0, as in `le.py`).

### Integration Points
- New CLI verbs: `cc` (D-11), plus whatever the library match/probe/scan need.
- `config/cflags.txt` and `config/<exe>/runtime.csv` are new committed config.
- `docs/toolchain.md` "Compiler" section and the `docs/matching.md` table receive the results (CID-05).
- Phase 5's `configure.py` ninja rules call `reverseapoc cc`; Phase 5's split consumes `runtime.csv`.

</code_context>

<specifics>
## Specific Ideas

- Local scan facts (2026-10-19), whole file, library included: `setcc al; and eax,0FFh` 33× in UFO2P and 61× in TACP; `setcc al; movzx eax,al` once each; the 10.0a "promote then cmp eax,imm" idiom 0×. Phase 4 must recount these in non-library code only.
- decomp.me's invocation is the reference: `wibo binnt/wcc386.exe -zq -i=<ver>/h ... -fo<obj> <src>` with `/` rewritten to `\`.
- Expected result per the research: "10.6 (10.5 byte-identical on the probe)". Theme Hospital saw 11.0 match only 2 of 10 functions.

</specifics>

<deferred>
## Deferred Ideas

- 10.5a (c105_a.zip patch) and 11.0a/11.0b sweeps: only if the results call for them (D-02).
- 10.0a media: worth getting only if the runtime map points to older CRT modules mixed in.
- Confirming `-o*` and `-zp` by matching real functions: Phase 5 (D-08).
- Guardrail hooks that stop agents from editing the compiler wrapper or `cflags.txt` during matching sessions: Phase 6 (AGT-05).

</deferred>

---

*Phase: 04-compiler-identification*
*Context gathered: 2026-10-21*
