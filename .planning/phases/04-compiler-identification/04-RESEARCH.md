# Phase 4: Compiler identification - Research

**Researched:** 2026-10-21
**Domain:** Watcom C 10.x/11.0 toolchain under wibo, OMF/LIB parsing, masked library matching over an LE code object, codegen fingerprinting, wpack decompression
**Confidence:** HIGH for the spike, wpack, OMF and library-match facts (measured this session on the real files, counts only). MEDIUM for the flag and version conclusions about game code (scan evidence; Phase 5 matches settle them).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### 10.5's damaged compiler
- **D-01:** Write our own stdlib wpack decoder in `tools/reverseapoc/`, called by `install-watcom 10.5`, so every contributor gets the same real `BINW/WCC386.EXE` (567,558 bytes) from `DISKIMGS/DISK02/PCK00017.1` + `DISKIMGS/DISK03/PCK00017.2`. Pin the decoded file's size and hashes in `config/watcom.toml`; this replaces the KNOWN BAD entry for the CD stub. **Time box: about one day.** If the decoder isn't working by then, defer 10.5 ("run only if the 10.6 result is ambiguous"), record the deferral in toolchain.md and the VERIFICATION, and reword CID-01 for 10.5 accordingly.
- **D-02:** The probe and library sweep cover exactly 10.5, 10.6 and 11.0. 11.0a/11.0b (already in `watcom.toml`) come in only if 11.0 turns out to be a candidate. No 10.5a.
- **D-03:** Once per version, the probe is compiled natively on the Windows host (BINNT binaries) and under wibo in the container, and the object hashes must be identical. This check is manual and logged (e.g. under `build/gate/04-*`), not CI. A difference means a wibo bug, not codegen.

#### Library match and runtime map
- **D-04:** Lift KKND-Decomp's `tools/lib_match.py` (CC0, 115 lines; masked-byte matching of OMF library modules), keeping a derivation header as `le.py` does. Add a new stdlib OMF reader, `tools/reverseapoc/omf.py`, covering the LIB dictionary/pages, THEADR, LNAMES, SEGDEF, GRPDEF as needed, PUBDEF, LEDATA, LIDATA and FIXUPP: enough to get each module's code bytes and fixup positions to mask. Phase 5's `omf2elf.py` grows from this module. — **Reversibility:** costly — Phase 5's omf2elf builds on its API.
- **D-05:** Scan every 32-bit library in each version's `LIB386` tree (CLIB3R, CLIB3S, MATH3R, MATH3S, MATH387R/S, EMU387 and whatever else is there), not only CLIB3R/MATH3R. Which of 3R vs 3S and 387 vs emulator matches is flag evidence for D-08.
- **D-06:** The result is committed as `config/<exe>/runtime.csv`: address range, module, library, the set of matching versions, and public names. It holds addresses and Watcom symbol names only, never bytes. A real-file test re-derives it and fails on drift (skipped without `orig/` and `third_party/watcom/`, like other real-file tests). The probe idiom counts exclude these ranges, and Phase 5 seeds `functions.csv` and the Ghidra cross-check from it. — **Reversibility:** costly — Phase 5 consumes the file format.
- **D-07:** Versions are recorded per module. A module whose bytes are identical across all swept versions is "uninformative". toolchain.md names the linked-library version from the modules that discriminate, and reports it separately from the game-code compiler version (the probe, D-10). A mix (e.g. most modules 10.6, a few from another version, as in Theme Hospital) is reported as a mix, not voted away.

#### Flags and evidence bar
- **D-08:** Phase 4 proves the flags a whole-binary scan of non-library code can show, with evidence for each flag: calling convention (`-3r`/`-3s`, consistent with D-05), stack checks (`-s`, i.e. absence of `__CHK` calls), FPU mode (`-fpi` vs `-fpi87`), CPU scheduling hints (`-4`/`-5`) and memory model. `-o*` and `-zp` go into toolchain.md as "candidate, evidence pending", each with what would prove it, and Phase 5's first matches confirm them. CID-05 is met for the observable flags.
- **D-09:** Evidence is gathered separately for each EXE (UFO2P `ufo24`, TACP `tac4`): library map, probe counts, flag scans and C/C++ scan. toolchain.md gets one column per EXE. "Both EXEs use the same flags" is a finding, never an assumption.
- **D-10:** Each probe idiom is counted in non-library code of both code objects: byte compare as `setcc al; and eax,0FFh` vs a branch, counted-loop bound in `ebx` vs `ecx`, switch compare order, and the others the probe sources cover. A version counts as identified when the counts favour one family and nothing contradicts it. Ties are stated as ties, e.g. "10.6 (10.5 byte-identical on the probe)", and no time is spent separating versions that emit the same code. Exact-sequence matching of the probe's compiled bytes is not required.

#### Compiler wrapper
- **D-11:** The entry point is `uv run reverseapoc cc SRC -o OBJ`, a new CLI verb following the existing `_cmd_<verb>` pattern, with the code in `tools/reverseapoc/compiler.py`. It runs the compiler under wibo in the container, or natively on the Windows host. — **Reversibility:** costly — Phase 5's configure.py/ninja rules and Phase 6's guardrail hooks call it by name.
- **D-12:** `config/cflags.txt` holds one rule per line, `<glob>  <compiler>@<version>  <flags...>` (e.g. `*  wcc386@10.6  -5r -s ...`), with `#` comments. A `*` default comes first, the last matching rule wins, and the wrapper refuses a source that no rule matches. This mirrors docs/matching.md's "Module / file glob → Compiler@version → Flags" table. — **Reversibility:** costly — every unit's build reads it.
- **D-13:** Before compiling, the wrapper checks the size and SHA-1 of the compiler binaries against `config/watcom.toml` (`BINNT/WCC386.EXE`, plus `BINW/WCC386.EXE` for 10.x, plus `BINNT/WCCD386.DLL` for 11.0). It refuses on a mismatch or a KNOWN BAD file, and writes the tool's own banner (e.g. "Version 10.6") into the build log. Hashes are cached per run so the check stays cheap. It reuses `watcom.load_watcom_manifest` and its validators.
- **D-14:** Watcom reads `/` as an option switch and splits paths on spaces, so the wrapper rewrites paths to relative paths with backslashes (as decomp.me does) and refuses any path containing a space or starting with `-`, the same allowlist idea `configure.py` got in plans 03-06/03-07. Include paths resolve only to the selected version's own `H/` tree, never the host's or another version's.

### Claude's Discretion
- The probe sources are written in-house, a clean-room C89 set covering mosura's documented constructs (byte compare return, counted loop, switch order) plus constructs the flag scans need. mosura's licence is unverified, so its files are not copied.
- The C vs C++ scan method (CID-06): vtable-shaped pointer tables in obj2, `__wcpp_` routines via the runtime map, XI/YI static-init segments, mangled `W?` names. Output per EXE.
- Module layout under `tools/reverseapoc/` (e.g. `wpack.py`, `omf.py`, `libmatch.py`, `compiler.py`, `probe.py`), test layout, CLI verbs other than `cc`, and where the probe sources live.
- How the spike "wibo 1.2.0 runs wcc386.exe for each version in Docker" is run and recorded (`/gsd-spike`).

### Deferred Ideas (OUT OF SCOPE)
- 10.5a (c105_a.zip patch) and 11.0a/11.0b sweeps: only if the results call for them (D-02).
- 10.0a media: worth getting only if the runtime map points to older CRT modules mixed in.
- Confirming `-o*` and `-zp` by matching real functions: Phase 5 (D-08).
- Guardrail hooks that stop agents from editing the compiler wrapper or `cflags.txt` during matching sessions: Phase 6 (AGT-05).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CID-01 | The original compiler runs under wibo 1.2.0 in Docker for 10.5, 10.6, 11.0, read-only from `third_party/watcom/` | Spike run this session: 10.6 and 11.0 compile under wibo from the read-only tree; the 10.x BINNT loader opens `..\BINW\WCC386.EXE` itself (no PATH, no W32RUN); 10.5 fails with `Loader read error` on the CD stub and **works** once the prototype wpack decoder supplies the real binary (banner "Version 10.5"). See "Spike results". |
| CID-02 | Compiler wrapper keyed by `compiler@version` plus `config/cflags.txt` | Verified invocation, path rewriting, env scrubbing (`WCC386` env var injects options), `-bt=dos` (NT host defaults to `__NT__`), `-fr=` (stray `.err` files), `fnmatch.fnmatchcase` glob semantics. See "Pattern 4/5". |
| CID-03 | Probe compiled with each version locates its idioms in non-library code | Probe experiments: `setcc al; and eax,0FFh` is a -4/-5 idiom (both 10.6 and 11.0 at -4), the 11.0 branch form appears only at -5, `movzx` only at -3; loop rotation differs 10.6 vs 11.0; struct copy unrolled `movsd` (-5) vs `rep movsd` (-4). Baseline non-library counts given. See "Pattern 6". |
| CID-04 | Linked CLIB3R/MATH3R modules match byte for byte (masked) against one version's LIB386 | Prototype matcher run: UFO2P 110 / TACP 122 masked matches, 0 multi-hits, ~5.6% of obj1; version pattern contains 10 modules that match only 10.6 and none that excludes 10.6. See "Pattern 3" and "Prototype results". |
| CID-05 | Version and default flags in `docs/toolchain.md` with per-flag evidence, per EXE | Evidence sources per flag mapped in "Flag evidence matrix". |
| CID-06 | C vs C++ scan confirms `wcc386` vs `wpp386` | XI/YI tables located through the matched `inirt386` fixups: no program-priority (64) init or DTOR (40) entries in either EXE. Apparent `__wcpp_` matches are false positives (byte-identical to CLIB `noefgfmt`/`nomem`). See "Pattern 7" and Pitfall 4. |
</phase_requirements>

## Summary

The spike is done and it succeeded for all three versions. wibo 1.2.0 in the existing image runs 11.0's native `BINNT/WCC386.EXE` (+ `WCCD386.DLL`) and 10.6's 9,216-byte BINNT loader, which opens `Z:\work\watcom\10.6\BINW\WCC386.EXE` relative to its own module path (traced with `WIBO_DEBUG=1`), so no PATH or W32RUN setup is needed. 10.5 fails exactly as expected (`Loader read error`, rc 3) on the 65,536-byte CD stub. A throwaway stdlib Python wpack decoder (about 150 lines, 0.4 s) turned `PCK00017.1` + `PCK00017.2` into a 567,558-byte file whose embedded CRC checks out, and that file, dropped in as `BINW/WCC386.EXE` next to the 10.5 BINNT loader, prints "WATCOM C32 Optimizing Compiler Version 10.5" under wibo and natively, and compiles a probe whose normalized object equals 10.6's. D-01's one-day box is very likely to hold.

The native-vs-wibo cross-check (D-03) works, but **raw object hashes can never be equal across host and container**: the object's THEADR record and the COMENT class 0xE9 dependency records carry the compiler's absolute path to the source (`Z:\...` under wibo, `C:\...` natively) and header timestamps. After dropping those records the 10.6 and 11.0 objects are identical between native and wibo. The D-03 gate therefore compares a "normalized object hash" (all records except THEADR and COMENT 0xE9), and the wrapper always passes `-zld`, which removes the dependency records without changing code.

The masked library match (D-04/D-05) is cheap and decisive for the linked runtime. A prototype that slides every CODE segment of every OMF library in `LIB386` over obj1, masking library-side FIXUPP bytes and target-side LE fixup bytes, matched 110 code ranges in UFO2P and 122 in TACP (0 ambiguous placements, about 44 KB, 5.6% of obj1) in under a second per version, and 19 s for the whole tree of all three versions. Every matched range is consistent with 10.6. 10 modules match 10.6 only (`prtf`, `grownear`, `ftos`, `memalloc`, `initargv` and others), none matches 10.5-only or 11.0-only, and the library choice is CLIB3R + MATH387R + EMU387 (register calls, inline x87 with emulator). `_cstart_` lands exactly on the LE entry point (obj1:0xB0784), which corroborates the map. Game code (non-library) shows `setcc al; and eax,0FFh` 30x/58x and `setcc; movzx` 0x, unrolled `movsd` runs 75x/35x and no `mov ecx,small; rep movsd`, and only 40/32 `__CHK` calls: consistent with `-5r -s` for most modules, with a few modules built without `-s`.

**Primary recommendation:** Build four stdlib modules (`compiler.py` + `cflags`, `omf.py`, `libmatch.py`, `wpack.py`) plus `probe.py`/`cppscan.py`, in waves where the wpack decoder is a parallel, time-boxed side track. Use the verified invocation `wibo <tree>\BINNT\WCC386.EXE -zq -zld -fr=<err> -bt=dos <flags> -i=<tree>\H <src> -fo=<obj>` with a scrubbed environment, and compare host vs container with the normalized object hash.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| wpack decode of 10.5 `WCC386.EXE` | Host CLI (`install-watcom`, Python stdlib) | Filesystem (`third_party/watcom/10.5/BINW`) | Install writes into gitignored `third_party/`, which is read-only in the container; it must run on the host |
| Compiler hash gate + banner log | Python wrapper (`compiler.py`) | Config (`config/watcom.toml`) | Wrapper is the only caller of the compiler (D-13); manifest is the source of truth |
| Compile one source | Container (wibo) | Windows host (native BINNT) | D-11: same verb, two execution backends; D-03 cross-checks them |
| Per-file compiler/flags selection | Config (`config/cflags.txt`) | Python wrapper | Committed policy; the wrapper only reads it |
| OMF/LIB parsing | Python library (`omf.py`) | — | Pure function of bytes; reused by Phase 5 omf2elf |
| Runtime map | Python (`libmatch.py`) | Config (`config/<exe>/runtime.csv`) | Derived from `orig/` + `third_party/watcom/`, committed as addresses + names only |
| Probe compile + idiom counts | Container/host compile, then Python scan (`probe.py`) | `runtime.csv` (mask) | Counts must exclude library ranges (D-06, D-10) |
| C vs C++ scan | Python (`cppscan.py`) | `runtime.csv`, LE fixups | Uses the runtime map to find `inirt386` and the XI/YI tables |
| Evidence write-up | Docs (`docs/toolchain.md`, `docs/matching.md`, `docs/learnings.md`) | VERIFICATION.md | CID-05 is a documentation requirement |

## Project Constraints (from CLAUDE.md)

- Never commit game files, disassembly, build output: `orig/`, `asm/`, `build/`, `third_party/` are gitignored. Never modify `orig/`, the hash manifests under `config/`, or the build scripts **to make a check pass**. (Pinning the decoded 10.5 binary in `config/watcom.toml` is an owner-decided data correction, D-01, not a check workaround. Make it its own reviewed task.)
- The Watcom compiler and the game are user-supplied; never baked into the Docker image (the decoded 10.5 binary goes to `third_party/watcom/10.5/BINW/`, never into an image layer or the repo).
- A matched function is byte-identical; no inline asm (no impact on Phase 4 beyond probe sources being plain C89).
- Claude Code is the only agent runtime; plugins at project scope.
- Done gate (tooling): `uv run pytest -q && uv run ruff check .` green on host **and** `docker compose run --rm test` green in the container.
- `.claude/rules/tools.md`: Python 3.14 via uv; **test-driven** (failing pytest first); **no third-party dependency without a reason recorded in `docs/tools.md`**; tooling is GPLv3; keep CC0/GPLv3 derivation headers; tests never embed game bytes (and by extension compiler bytes); real-file tests skip unless the files exist; shallow nesting; **no bare binary-format offsets** (name each after its spec field, derive related values); refactors pinned by tests first.
- `docs/coding-style.md#python-tooling`: name offsets after the spec (cite the spec section), `next(..., None)` for first-match, add error context in one place, reuse existing dataclasses (`FileHashes`), test fixture builders keep their own literals.
- `.claude/rules/workflow.md`: GSD owns phases; superpowers owns TDD and verification-before-completion inside a phase.
- Never print or commit game or compiler bytes: outputs are offsets, counts, sizes, hashes, names and banners only.

## Spike results (run 2026-10-21, read-only, scratch output only)

All runs used `docker compose run --rm -T build bash -s` from `docker/` with the script on stdin, `/work/watcom/<ver>` (read-only) as the tree, and `/tmp` inside the container for sources and objects. [VERIFIED: commands run this session]

| Version | Under wibo 1.2.0 (container) | Native on Windows host (Git Bash, `MSYS_NO_PATHCONV=1`) | Banner (first line) |
|---|---|---|---|
| 10.5 (CD stub) | `Loader read error`, rc 3 | not tried (same stub) | none |
| 10.5 (prototype-decoded BINW in a scratch tree mounted at `/scratch`) | compiles, rc 0 | compiles, rc 0 | `WATCOM C32 Optimizing Compiler  Version 10.5` |
| 10.6 | compiles, rc 0, ~43 ms per compile | compiles, rc 0, ~49 ms | `WATCOM C32 Optimizing Compiler  Version 10.6` |
| 11.0 | compiles, rc 0, ~88 ms per compile | compiles, rc 0 | `Watcom C32 Optimizing Compiler  Version 11.0` |
| 11.0 `BINW/WCC386.EXE` run directly | `Failed to load PE image` (expected: LE, not PE) (Correction 2026-10-21: measured LX in 10.5, 10.6 and 11.0; see docs/learnings.md.) | — | — |

Facts established:
1. **10.x loader mechanics.** `WIBO_DEBUG=1` shows the 10.6 BINNT loader calling `GetModuleFileNameA` → `Z:\work\watcom\10.6\BINNT\WCC386.EXE`, then `CreateFileA(Z:\work\watcom\10.6\BINW\WCC386.EXE)`. It resolves the sibling `BINW` from its own path. PATH, `WATCOM`, DOS4GW and W32RUN are not needed. A tree only needs `BINNT/WCC386.EXE` + `BINW/WCC386.EXE` + `H/`. [VERIFIED: wibo debug trace]
2. **Paths.** wibo maps `Z:\` to `/` and resolves relative paths against the cwd. Both `Z:\abs\path` and repo-relative backslash paths (`third_party\watcom\10.6\H` with cwd `/work`) work. Forward slashes break the command line (`Error! E1073: Invalid option '/10.6'`). [VERIFIED]
3. **Headers.** Without `-i=` or `INCLUDE`, `#include <stdio.h>` fails (`E1055`). `-i=<tree>\H` works, `INCLUDE=<tree>\H` works, `WATCOM=<tree>` alone does **not**. The bind mount is case-insensitive (`stdio.h` resolves to `STDIO.H`). [VERIFIED]
4. **Banner capture.** `-zq` suppresses the banner. Running the compiler with **no arguments** prints the 3-line banner plus usage and exits non-zero (10.6 rc 1, 11.0 rc 8): a cheap, side-effect-free banner probe. [VERIFIED]
5. **Exit codes.** Success 0. Compile errors: 10.6 rc 1 or 2, 11.0 rc 8. A failed compile writes no object. [VERIFIED]
6. **Stray error file.** By default the compiler writes `<stem>.err` into the **cwd** on errors (it would land in the repo root). `-fr=<path>` redirects it; bare `-fr` suppresses it. [VERIFIED]
7. **Environment injection.** Setting `WCC386=-3r` in the environment changed codegen (`movzx` appeared) on both 10.6 and 11.0. The compiler reads its own name as an options variable. compose's `env_file: ../.env` could carry it into the container. [VERIFIED]
8. **Target default.** The NT-hosted compilers predefine `__NT__` by default. Only `-bt=dos` gives `__DOS__` (tested with `#if defined(...)` publics). The default target changes header paths and default libraries, so a DOS/4GW build needs `-bt=dos`. [VERIFIED]
9. **Object determinism and D-03.** Raw objects differ between host and container because THEADR holds the absolute source path (`Z:\tmp\s\src\t.c` even when the command line said `src\t.c`) and COMENT 0xE9 holds absolute header paths and DOS timestamps. SHA-1 over all records **except THEADR and COMENT class 0xE9** was identical native vs wibo for 10.6 and 11.0, with and without `-zld`. 10.5-decoded gave the same normalized hash as 10.6 on that probe. [VERIFIED]

Recorded spike commands (canonical form):
```bash
# container, from docker/ ; B is a literal backslash (the Bash tool and MSYS both eat "\\")
B=$'\x5c'; win() { local p="$1"; echo "${p//\//$B}"; }
cd /work
env -i PATH=/usr/local/bin:/usr/bin:/bin /usr/local/bin/wibo \
  third_party/watcom/10.6/BINNT/WCC386.EXE -zq -zld -bt=dos -s \
  "-i=$(win third_party/watcom/10.6/H)" "Z:$(win /tmp/s/src/t.c)" "-fo=Z:$(win /tmp/s/out/t.obj)"
# native host (Git Bash): MSYS_NO_PATHCONV=1 stops MSYS from rewriting "-i=..." arguments
MSYS_NO_PATHCONV=1 third_party/watcom/10.6/BINNT/WCC386.EXE -zq -zld -bt=dos "-i=$(cygpath -w third_party/watcom/10.6/H)" 'src\t.c' '-fo=out\t.obj'
```
Recommendation for the spike record: write `.planning/spikes/004-wibo-watcom/README.md` from this section (Given/When/Then: "wibo 1.2.0 runs wcc386 for 10.5/10.6/11.0" → VALIDATED, with 10.5 conditional on the decoder).

## Standard Stack

### Core (all already present: no new dependency)
| Component | Version | Purpose | Why |
|---|---|---|---|
| Python stdlib (`struct`, `zlib`, `hashlib`, `fnmatch`, `subprocess`, `csv`, `re`) | 3.14.5 (host and image) | All new modules | `.claude/rules/tools.md`: no third-party dep without a recorded reason [VERIFIED: `uv run python` 3.14.5] |
| wibo | 1.2.0 at `/usr/local/bin/wibo` | Runs BINNT compilers in the container | Verified this session (`wibo --version`) |
| Open Watcom v2 `wdis` | 2026-10-01-Build (in image) | Disassemble probe objects for humans/tests, never for matching | Already in image |
| `tools/reverseapoc/le.py` | in repo | obj1 bytes (`load_flat()`), target fixups (`fixups()`), objects | Existing |
| `tools/reverseapoc/watcom.py` | in repo | `load_watcom_manifest`, `check_version`, `KeyFile`, `install_version` | Existing; D-13 reuses it |
| `tools/reverseapoc/iso9660.py` | in repo | Read `DISKIMGS/...` from the 10.5 ISO or installed tree | Existing |

### Considered and rejected for Phase 4
| Instead of | Could use | Tradeoff |
|---|---|---|
| Stdlib byte-pattern idiom counters | `capstone` 5.0.9 (PyPI, `py3-none` wheels for win_amd64 and manylinux x86_64, so 3.14 is fine) [VERIFIED: PyPI JSON] | Phase 5 needs it anyway (ARCHITECTURE C12). Phase 4's idioms are short, fixed encodings, and the structural loop counter works on byte shapes (validated on probe objects), so adding a dependency now buys little. **Recommend: no capstone in Phase 4.** |
| Own wpack decoder | mosura `oracle/wpack/wunpack.py` | Licence unverified (`license: null` on GitHub) [VERIFIED: GitHub API] |
| KKND `omf.py` as-is | own `omf.py` | KKND's reader lacks Easy-OMF handling, COMDAT and LIB walking, and mis-offsets fixups that follow LIDATA. Lift ideas and its CC0 code with a derivation header, but rewrite to repo style (named offsets, typed errors). |

**Installation:** none.

## Package Legitimacy Audit

No external packages are installed in this phase. Everything is stdlib or already in the repo or image. If the planner nonetheless adds `capstone`, it must go through `docs/tools.md` and the legitimacy gate first (`gsd_run query package-legitimacy check --ecosystem pypi capstone`), which was not run here because the recommendation is not to add it.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---|---|---|---|---|---|---|
| *(none)* | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                       third_party/watcom-media/*.iso (host, gitignored)
                                   │ install-watcom 10.5
                                   ▼
 DISKIMGS/DISK02/PCK00017.1 ─┐   wpack.decode() ──► BINW/WCC386.EXE (10.5) ──► check-watcom (manifest pin)
 DISKIMGS/DISK03/PCK00017.2 ─┘   (CRC of packed stream, length = 567,558)

 config/cflags.txt ─► cflags.select(src) ─► (compiler, version, flags)
                                               │
 config/watcom.toml ─► hash gate (cached) ─────┤ refuse on mismatch / known_bad
                                               ▼
 src.c ─► compiler.build_argv() ─► [wibo | native] BINNT\WCC386.EXE ─► obj (OMF)   + banner ─► build log
                                               │
                    ┌──────────────────────────┴───────────────────────────┐
                    ▼                                                      ▼
   third_party/watcom/<v>/LIB386/**.LIB ─► omf.read_library() ─► modules (segments, data, fixups, publics)
                                                                       │
 orig/<EXE> ─► le.LE: obj1 bytes + LE fixup set ─────────────────────► libmatch.scan()  (anchor ─► find ─► masked verify)
                                                                       │
                                                                       ▼
                                                       config/<exe>/runtime.csv (ranges, module, libs, versions, publics)
                                                                       │
            ┌──────────────────────────────────────────────────────────┼─────────────────────────────┐
            ▼                                                          ▼                             ▼
  probe/*.c compiled per version ─► probe.calibrate()          probe.scan(non-lib obj1)        cppscan (XI/YI via inirt386,
  (which idioms each version/flag emits)                       idiom + flag counts              PLIB-only matches, vtable-shaped
            └─────────────────────────────► evidence tables ◄──────────────────────────────┘  runs, W? strings)
                                                     │
                                                     ▼
                         docs/toolchain.md (per-EXE columns), docs/matching.md, VERIFICATION.md
```

### Recommended Project Structure
```
tools/reverseapoc/
├── wpack.py        # D-01 decoder (header, Shannon-Fano table, LZSS), WpackError
├── omf.py          # D-04 OMF object + LIB reader, OMFError
├── libmatch.py     # D-04/D-05/D-06 masked slide, runtime.csv writer/reader (KKND CC0 derivation header)
├── cflags.py       # D-12 rule parser (or inside compiler.py)
├── compiler.py     # D-11/D-13/D-14 wrapper, CompilerError
├── probe.py        # D-08/D-10 idiom + flag counters over non-library obj1
└── cppscan.py      # CID-06 scan
probe/              # clean-room C89 probe sources (repo root; plain C, not under src/)
├── cg_basic.c      # byte compare, counted loop, switch, struct copy, div-by-const, float expr
└── README.md       # what each construct discriminates, which flags it was calibrated with
config/
├── cflags.txt      # D-12
├── UFO2P/runtime.csv
└── TACP/runtime.csv
tests/
├── omfimage.py     # synthetic OMF/LIB builder (own literals)
├── wpackimage.py   # synthetic wpack builder (NO_SHANNON path + tiny Shannon table)
├── test_wpack.py, test_wpack_real.py
├── test_omf.py, test_omf_real.py
├── test_libmatch.py, test_libmatch_real.py (drift test for runtime.csv)
├── test_cflags.py, test_compiler.py, test_compiler_real.py
├── test_probe.py, test_cppscan.py, test_toolchain_real.py
```
Note: `config/targets.toml` names the targets `name = "UFO2P.EXE"` / `name = "TACP.EXE"` (lines 12, 22) [VERIFIED: config/targets.toml:12,22]. Decide whether `config/<exe>/` is `config/UFO2P.EXE/` or the stem `config/UFO2P/` (recommend the stem, derived from `name` in one helper) and reuse it for Phase 5's `functions.csv`.

### Pattern 1: wpack decoder (D-01)

**Format** (from Open Watcom v2 `bld/wpack/h/wpack.h` and `c/decode.c`, commit 4c245dd, 2026-08-31) [CITED: github.com/open-watcom/open-watcom-v2/tree/master/bld/wpack]:
- Archive = header, compressed file streams, then the file-info table. Multi-disk parts are a **plain concatenation**: `PCK00017.1` (109,568 B) + `PCK00017.2` (247,871 B) = 357,439 B = `info_offset` (357,412) + `info_len` (27). [VERIFIED: prototype]
- Header actually present on the 10.5 disc (12 bytes, **not** OW v2's 16-byte struct with `internal`): `u16 signature = 0x2403` (bytes `03 24`), `u8 major = 1`, `u8 minor = 1`, `u16 num_files`, `u16 info_len`, `u32 info_offset`. The first file's `disk_addr` is 12, which proves the 12-byte header for this media. [VERIFIED: prototype, header ints only]
- `file_info` (packed): `u32 length` (uncompressed), `u32 disk_addr`, `u32 stamp` (DOS date/time), `u32 crc`, `u8 namelen` (bit 0x80 = NO_SHANNON_CODE), `char name[namelen & 0x7F]` → `wcc386.exe`, length 567,558.
- **CRC** = standard CRC-32 of the *compressed* bytes `[disk_addr, next_file_or_info_offset)`. `zlib.crc32(data[12:357412]) == crc` was True. This gives an integrity check before decoding. [VERIFIED]
- Decoding: LZSS (window 4096, lookahead 60, threshold 2, window pre-filled with spaces, start `r = 4096-60`) with literal/length symbols (314 = 256-2+60) coded by a static canonical Shannon-Fano code. The code-length table is run-length packed (first byte = entries-1; entry bit 0x80 = skip `(e&0x7F)+1` symbols, else `(e>>4)+1` symbols of length `(e&0xF)+1`). Match positions use the LZHUF-style `d_code`/`d_len` tables (6 high bits table-coded, 6 low bits raw). `NO_SHANNON` streams use a 1-bit flag + 8-bit literal or 6-bit length + position.
- **Tie order matters:** `AssignCodes` sorts the symbol indices by code length with `wpack_qsort`, a fixed copy of Watcom's CLIB qsort (shell sort for n < 16, Bentley-McIlroy 3-way partition with median-of-3/pseudo-median-of-9 above). Python's stable `sorted` produced garbage (no `MZ`). A port of `wpack_qsort` produced a valid `MZ` file. [VERIFIED: prototype both ways]

**Prototype result** (scratch, never written to the repo) [VERIFIED this session]: size 567,558; sha1 `a479921bf3bfc6a092710ab291d00752a09d782b`; md5 `17751042fa2927337ba69bc0bfb16684`; crc32 `0xDAA1AD2A`; runs as 10.5 (banner above). mosura independently documents the same route (`cat` both parts, unpack, drop in as the BINNT loader's sibling) and the size 567,558 [CITED: github.com/jdmichaud/mosura docs/watcom-codegen-fingerprint.md "10.5: measured, not inferred"].

**Feasibility:** well under one day. The risky part (qsort tie order) is already solved, and the prototype is about 150 lines including the qsort port.

**Install integration:** `install_version` extracts into `.<ver>.partial` and then replaces. Decode inside the partial tree **before** the final replace, so `check_version` sees the decoded file. Extend the manifest schema minimally: a key-file entry gains an optional `wpack = ["DISKIMGS/DISK02/PCK00017.1", "DISKIMGS/DISK03/PCK00017.2"]` (parts in order) plus `wpack_member = "wcc386.exe"`. The entry's size/md5/sha1/crc32 become the decoded values, and `known_bad` is removed. Bound the output by both the archive's `length` and the manifest `size` (refuse if they disagree) so a corrupt header cannot allocate unbounded memory.

**Licence note:** OW's `bld/wpack` is under the Sybase Open Watcom Public License 1.0, which the FSF considers GPL-incompatible. `tools/` is GPLv3. Write `wpack.py` as an independent implementation from a format description (put the description in `docs/learnings.md` or a short `docs/research/wpack-format.md`), cite OW as the format reference, and do not copy code or comments. The `d_code`/`d_len` tables are the classic LZHUF (Okumura/Yoshizaki, 1988) tables. [ASSUMED: legal reading; owner to confirm, A1]

### Pattern 2: OMF/LIB reader (D-04)

Records that occur in the 32-bit libraries (counts from the 10.6 tree; record counts only) [VERIFIED: scratch parser]:

| Library (10.6) | Modules | Records present |
|---|---:|---|
| `DOS/CLIB3R.LIB` | 549 | THEADR, COMENT, LNAMES, SEGDEF32, GRPDEF, EXTDEF, LEXTDEF, PUBDEF (0x90) 75, PUBDEF32 508, LPUBDEF/LPUBDEF32, LEDATA (0xA0) 92, LEDATA32 745, LIDATA32 4, FIXUPP32 592, MODEND |
| `MATH3R.LIB` | 107 | same set, no LIDATA |
| `MATH387R.LIB` | 90 | same set |
| `DOS/EMU387.LIB` | 2 | 16-bit-numbered SEGDEF/PUBDEF/LEDATA/FIXUPP + LIDATA32, COMENT 0xAA (Easy OMF) |
| `PLIB3R.LIB` (C++) | 336 | adds **COMDAT32 476**, COMENT 0xA8/0xA9 (weak/lazy externs) |

Library sizes: 10.5 CLIB3R 544 modules, 11.0 CLIB3R 970 modules. Library page size 16 except 11.0 `DOS/EMU387.LIB` (512). [VERIFIED]

Required behaviour:
- **LIB walk:** header record 0xF0: `page = reclen + 3`, `u32 dict_offset`, `u16 dict_blocks`, `u8 flags`. Modules start on page boundaries and end at MODEND (0x8A/0x8B). The library ends at 0xF1. The dictionary is **not needed** for matching (sequential walk). Read it only if a later phase wants symbol lookup.
- **Not every `.LIB` is OMF:** 41/51/68 libraries (10.5/10.6/11.0, all under `NT/`) are COFF `!<arch>` import or MS libraries. Detect by first byte 0xF0 and report "skipped: not OMF" instead of failing. [VERIFIED]
- **Easy OMF (Phar Lap):** a module with COMENT class 0xAA uses the *16-bit* record numbers (0x90, 0x98, 0xA0, 0x9C) with **32-bit fields** (the 10.6 `NOEMU387.LIB` SEGDEF bodies are 8 bytes: attribute, u32 length, three indices; no extra access byte was present there, but the reader should tolerate one trailing byte [ASSUMED from the Phar Lap format, unverified]). Without this, `EMU387.LIB`/`NOEMU387.LIB` PUBDEFs mis-parse (struct error). wcc386's own objects also carry COMENT 0xAA (class 0xAA "80386") while using 0x91/0xA1 records. Treat 0xAA as "16-bit-numbered records have 32-bit offsets". [VERIFIED: parse failure reproduced, then fixed]
- **FIXUPP:** THREAD subrecords (high bit 0; D bit 0x40 = frame thread, method in bits 2-4, thread number in bits 0-1; target threads always carry an index, frame threads only for methods F0-F2); FIXUP subrecords: `locat` (M bit 0x40: segment-relative; clear = self-relative), location type in bits 2-5 (32-bit offset = 9, 16:32 pointer = 11), data-record offset 10 bits; `fixdat` F/T/P bits. Fixup offsets are relative to the **preceding** LEDATA. **A FIXUPP after LIDATA addresses the iterated record, not the expanded bytes**, so mark such segments "unmaskable" and skip them in matching (only 4 LIDATA32 in CLIB3R; none in code observed). Record the target kind (segment, group, external index) because the CID-06 and call-graph checks need external names.
- **LIDATA expansion:** recursive blocks (32-bit: `u32 repeat`, `u16 block_count`, then a byte-length content or nested blocks). Cap recursion depth and expanded size (`segment length` from SEGDEF bounds it).
- **COMDAT32 (0xC3):** needed for the C++ libraries (`PLIB*`) where code lives in COMDATs. D-04 lists no COMDAT, but CID-06 and Phase 5 (`omf2elf`, SPL-07) need it. Recommend minimal COMDAT support (name, alignment, data with continuation flag) in `omf.py`, or document that PLIB COMDAT code is not scanned.
- **Known parse failure:** `DOS/GRAPH.LIB` (10.5 and 10.6) has one module the prototype could not parse. It is irrelevant to a game that does not use Watcom's graph library (no match expected), but the reader must report it, never silently drop it.
- Model COMENT class 0x9B ("3fOp" etc.: CPU, model, optimized, fp mode) and default-library COMENT class 0x9F (`clib3r`, `math387r`, `emu387`/`noemu387`) are cheap per-module metadata. Keep them in the module object.

### Pattern 3: Masked library match (D-04/D-05/D-06/D-07)

KKND reference: `tools/lib_match.py` at commit `a371547864bb0884f0fc9efe07b681cda5b9eeef` (2026-09-24), CC0, 115 lines [VERIFIED: GitHub API, file read]. Its algorithm: per library module, cut each public in a CODE segment (to the next public), strip trailing `00`/`90`, take the first **48** bytes, mask library fixups, and test only at **known function starts** from `functions.csv`, with at least 16 unmasked bytes. It depends on KKND `omf.py` (224 lines, CC0). **Limits for us:** we have no `functions.csv` in Phase 4, and a 48-byte prefix cannot discriminate versions (D-07 needs whole bodies). Lift the masking idea and the derivation header. Replace the search strategy.

Recommended algorithm (prototype-validated):
1. Target side: `code = load_flat()[obj1.base : obj1.base+obj1.vsize]` (unrelocated), `lefix = {src_va + k}` for every LE fixup byte.
2. For each OMF library (all of `LIB386/**`, OMF only), each module, each **CODE-class** segment with length > 0: build `mask` = library fixup byte offsets, and `absf` = offsets of segment-relative (M=1) fixups.
3. Skip segments with fewer than `MIN_UNMASKED` unmasked bytes (status `short`) or with LIDATA fixups (status `unmaskable`). Record them; do not drop them.
4. **Anchor:** the longest run of unmasked bytes. `bytes.find` all occurrences in `code`. Candidate base = hit − anchor offset.
5. **Verify** at each candidate: every unmasked byte equal, **no LE fixup inside an unmasked byte**, and **an LE fixup present at every absolute (M=1) library fixup site**. Self-relative (rel32 call/jmp) sites have no LE fixup because wlink resolved them: mask them and do not require one.
6. Collect `(va, length, module, library, version)`. Merge across libraries and versions by `(va, length)`.
7. **Disambiguate** identical bodies. In 10.6 CLIB3R, `noefgfmt` and `nomem` (and 4 C++ stubs) all match the same 18-byte range, and C++ `fatalerr` matches where CLIB's `__fatal_runtime_error_` lives. Rules, in order: (a) verify the module's DATA/CONST bytes at the LE fixup targets (the off32 site points into obj2; compare that module's data segment there); (b) call-graph consistency: each rel32 to an EXTDEF must land on a range whose module publishes that name; (c) prefer C runtime (`CLIB*`, `MATH*`, `EMU*`) over C++ (`PLIB*`, `PLBX*`, `CPLX*`) when still tied; (d) otherwise record `ambiguous` with all candidates.
8. Sort and refuse overlaps unless one range is contained in another identical-body set.

Measured (MIN_UNMASKED=24; root `LIB386/*.LIB` + `LIB386/DOS/*.LIB`, all three versions; counts only) [VERIFIED: prototype]:

| | UFO2P | TACP |
|---|---|---|
| Distinct matched code ranges | 110 | 122 |
| Bytes covered (% of obj1) | 43,619 (5.56%) | 45,745 (5.75%) |
| Ranges matching 10.5+10.6+11.0 (uninformative) | 50 | 55 |
| 10.5+10.6 only | 49 | 55 |
| 10.6 only | 10 | 10 |
| 10.6+11.0 only | 1 (`cprintf`) | 2 |
| 10.5-only / 11.0-only / any range excluding 10.6 | 0 | 0 |
| Multi-placement segments (same segment at 2+ addresses) | 0 | 0 |
| Library sets (top) | CLIB3R alone 80; CLIB3R+CLIB3S identical 14; MATH387R 11 (+2 shared with MATH387S); EMU387 1; MATH3R only via one range shared with all math/clib libs | same pattern |
| Runtime per version | ~0.3 s | ~0.3 s |
| Whole `LIB386/**` tree, 3 versions | 19 s, same 110 ranges; every range also matched by a `DOS/` library | — |

10.6-only modules (UFO2P): `sprintf`, `ftell`, `memalloc`, `prtf` (3,038 B), `initargv`, `grownear` (1,466 B), `chk8087`, `cinit`, `efgfmt`, `ftos` (951 B). Threshold sensitivity: MIN_UNMASKED 16/12/8 → 122/129/136 ranges, still 0 multi-placements, and the version pattern does not change (11/11/11 10.6-only). At 16 and below, C++ stub false positives appear (Pitfall 4). **Recommend MIN_UNMASKED = 16, plus the disambiguation rules.** [VERIFIED]

Corroboration: `_cstart_` (CLIB `cstrt386`) matched at 0xC0784 = obj1 base 0x10000 + entry 0xB0784 in UFO2P, and 0xC28B0 in TACP (entry 0xB28B0). [VERIFIED]

`runtime.csv` (D-06) recommended columns (addresses and names only):
```
# generated by: uv run reverseapoc libmatch UFO2P ; do not edit
start,end,segment,module,libraries,versions,publics,status
0x000C10B7,0x000C10FA,_TEXT,sprintf,DOS/CLIB3R.LIB,10.6,sprintf_,unique
```
`start` inclusive, `end` exclusive, both 8-digit hex. `libraries`/`versions`/`publics` are `;`-joined and sorted. `status` ∈ {`unique`, `ambiguous`}, with alternatives in a separate `alternatives` column if needed. Library paths are relative to `LIB386` with `/`. The drift test re-derives the file and compares it byte for byte (text).

### Pattern 4: `config/cflags.txt` (D-12)

```
# glob                compiler@version  flags...
*                     wcc386@10.6       -bt=dos -5r -s -fpi -zp? -o?   # final values per toolchain.md evidence
```
- Parse: strip `#` comments, split on whitespace; field 1 = glob, field 2 = `name@version` (validate `name ∈ {wcc386, wpp386}` and version ∈ manifest), rest = flags.
- Match with **`fnmatch.fnmatchcase(posix_relpath, glob)`**: `*` crosses `/` (so the `*` default matches `src/a/b.c`) and matching is case-sensitive. `PurePosixPath.full_match('*')` does **not** match nested paths (False on 3.14.5), so do not use it. [VERIFIED: uv run python]
- First rule must be `*`. The **last** matching rule wins (D-12, deliberately unlike Theme Hospital's first-match). No match → refuse.
- Validate flags: each starts with `-`, no `/`, no spaces, no wrapper-owned flags (`-zq`, `-zld`, `-fo`, `-fr`, `-i`), no `-d`/`-fi` that points outside the tree. This keeps per-file rules from overriding the wrapper's invariants.

### Pattern 5: Compiler wrapper (D-11/D-13/D-14)

decomp.me reference (`cromper/cromper/compilers.py`, commit `6056cf56`, 2026-10-14) [VERIFIED: GitHub API]:
```
WATCOM_ARGS = ' -zq -i="Z:${COMPILER_DIR}/h" -i="Z:${COMPILER_DIR}/h/nt" ${COMPILER_FLAGS} -fo"Z:${OUTPUT}" "Z:${INPUT}"'
WATCOM_CC = '${WIBO} "${COMPILER_DIR}/binnt/wcc386.exe" $(echo "' + WATCOM_ARGS + "\" | sed 's:/:\\\\:g')"
```
Differences for us: no `h/nt` (D-14: own `H` only; NT headers are wrong for DOS), add `-bt=dos`, `-zld`, `-fr=`, and use list-argv subprocess, never a shell.

Recommended argv (both backends, cwd = repo root):
```
[<runner>] third_party\watcom\<ver>\BINNT\WCC386.EXE -zq -zld -fr=<objdir>\<stem>.err <cflags...> -i=third_party\watcom\<ver>\H <src> -fo=<obj>
```
- `<runner>` = `/usr/local/bin/wibo` (Linux; error if missing) or nothing (win32 native). On Linux, the program path argument to wibo can stay POSIX (`third_party/watcom/10.6/BINNT/WCC386.EXE`). Only the **guest arguments** need backslashes.
- Paths: resolve, require inside the repo, make repo-relative, refuse a space, a leading `-`, a `..` segment, or characters outside `[A-Za-z0-9._/-]` (mirror `configure.py`'s `_SAFE_ORIG = re.compile(r"[A-Za-z0-9._/:-]+")` at configure.py:65, minus `:`), then convert `/` → `\`.
- **Environment:** start from an empty env (plus `PATH`, and `SYSTEMROOT`/`TEMP`/`TMP` on Windows). Never pass `INCLUDE`, `WATCOM`, `WCC386`, `WPP386`, `WCL386`. [VERIFIED: WCC386 changes codegen]
- **Hash gate:** files per version: `BINNT/WCC386.EXE` always, `BINW/WCC386.EXE` for 10.x, `BINNT/WCCD386.DLL` for 11.0 (the 11.0 tree also has `BINW/WCC386.EXE` pinned but the native driver does not load it). Use `watcom.check_version()` results filtered to those paths, and refuse `missing`, `mismatch` and `known-bad`. Cache: ninja runs the wrapper once per source in separate processes, so "per run" caching needs a stamp file, e.g. `build/gate/watcom-<ver>.json` holding `{path: [size, mtime_ns, sha1]}`. Recheck size+mtime on each call and rehash only on change.
- **Banner:** run the compiler once with no arguments (no side effects, rc ≠ 0 expected), take the first non-empty line, require `Version <ver>` in it, and cache it with the hash stamp. Log `banner + argv + rc` to `build/logs/cc.log` (or stderr).
- Exit: propagate non-zero, delete a partial object on failure, print the compiler's stdout.
- Output object determinism: same machine, same paths → identical object. Across machines → compare normalized hashes (see D-03 below).

### Pattern 6: Probe and flag scans (D-08/D-10, CID-03)

What the experiments showed (our own clean-room probe, compiled this session with 10.6 and 11.0; mnemonics only) [VERIFIED]:

| Construct | 10.6 `-3r` | 10.6 `-4r`/`-5r`/default | 11.0 `-4r` | 11.0 `-5r`/default |
|---|---|---|---|---|
| `return c == 5;` (unsigned char) | `cmp al,5; sete al; movzx eax,al` | `cmp al,5; sete al; and eax,0FFh` | `sete; and eax,0FFh` | `cmp al,5; jne; mov eax,1; ret; xor eax,eax` (branch) |
| `for (i=0;i<n;i++) s+=a[i];` | rotated: `jmp` to bottom test, `jl` back | rotated | top-tested: `cmp; jge` exit, `jmp` back | top-tested |
| small struct copy (5 dwords) | `rep movsd` | `-4r`: `mov ecx,5; rep movsd`; `-5r`: 5× `movsd` unrolled | same split | same split |
| switch {1,2,3,10} at `-ox` | `cmp 2; jb; jbe; cmp 3; jbe; cmp 10; je` | same | `cmp; jae; cmp; jne ...` | same as 11.0 `-4r` |
| `-fpi` vs `-fpi87` | identical code; only the default-library COMENT differs (`emu387` vs `noemu387`) | | | |
| `-fpc` | calls into the math library; default libs `clib3r`+`math3r`, model COMENT `3fOc` | | | |
| `-3s`/`-5s` | default libs `clib3s`, `math387s` | | | |

Consequences:
- mosura's table (10.6 bound in `ebx`, 11.0 in `ecx`) did **not** reproduce with our probe: we saw 10.6 holding `n` in `ecx` and 11.0 in `ebx`. Register choice is construct-specific. **Calibrate every idiom from our own probe objects per version and flag set; never hard-code mosura's register claims.** [VERIFIED for our probe; mosura's claim CITED, construct differs]
- `setcc al; and eax,0FFh` excludes `-3` (any version) and 11.0 at `-5`, but **not** 11.0 at `-4`. Loop rotation is the 10.x-vs-11.0 discriminator that survives `-4`/`-5`, but `-oneatx` changed loop shape for both versions (neither shape was found). Shape counts in game code (rotated 111 vs top-tested 80 in UFO2P, 99 vs 105 in TACP) are **not decisive** without matching the flag set (structural matcher validated on probes: 10.6 objects (2,0), 11.0 objects (0,2)).
- Game code baseline (non-library, prototype mask at MIN_UNMASKED=16) [VERIFIED counts]:

| Idiom (byte encoding) | UFO2P non-lib / lib | TACP non-lib / lib | Reading |
|---|---|---|---|
| `0F 9x C0 25 FF 00 00 00` setcc al; and eax,0FFh | 30 / 3 | 58 / 3 | -4 or -5; not -3; not 11.0 -5 |
| `0F 9x C0 0F B6 C0` setcc al; movzx | 0 / 1 | 0 / 1 | the single hit is library code |
| unrolled `A5 A5` (not after `F3`/`A5`) | 75 / 2 | 35 / 2 | -5 struct copy |
| `B9 <1..16> 00 00 00 F3 A5` (mov ecx,small; rep movsd) | 0 | 0 | no -4 struct copy |
| `E8` to `__CHK` (each preceded by `68` push imm32) | 40 | 32 | `-s` default; a few modules without `-s`, clustered in two 64 KiB blocks (0x10000 and 0xB0000) |

Flag evidence matrix (what proves what; scan-provable vs Phase 5):

| Flag | Evidence source | Phase 4 status (from prototype) |
|---|---|---|
| `-3r` vs `-3s` (calling convention) | Library matched is CLIB3R/MATH387R (register naming `name_`); a stack-convention build would link CLIB3S. 14 CLIB3S matches are byte-identical asm modules shared with 3R | **Scan-provable:** register (`r`) |
| `-3`/`-4`/`-5` | `and`-form vs `movzx` (excludes -3); unrolled `movsd` vs `mov ecx,n; rep movsd` (-5 vs -4) | **Scan-provable** after probe calibration: -5 likely |
| `-s` | Count `push imm32; call __CHK` in non-library code, with `__CHK` located from the runtime map (`stk386`) | **Scan-provable:** `-s` for most modules; the exceptions are a per-glob cflags rule once Phase 5 maps the modules |
| `-fpi` vs `-fpi87` vs `-fpc` | MATH387R (14) vs MATH3R (1 shared) → inline x87, not `-fpc`; the EMU387 module is linked → objects requested `emu387` (`-fpi`); `-fpi87` objects request `noemu387` | **Scan-provable:** `-fpi`, with the caveat that one `-fpi` object anywhere pulls the emulator in (A3) |
| `-fp3`/`-fp5` | FP instruction scheduling (`fxch` placement) | Candidate, evidence pending (probe can add an FP expression) |
| `-mf` (flat) | LE flat layout, two objects, DGROUP via off32; `-mf` is wcc386's 386 default | Scan-consistent; record as default |
| `-bt=dos` | DOS CLIB linked; DOS/4GW binary | Required by the wrapper (NT host default is `__NT__`) |
| `-o*` | Loop/switch shapes, inlining, `-oneatx` vs `-ox` differences | Candidate, evidence pending → Phase 5 matches (D-08) |
| `-zp*` | Struct layouts (field offsets in matched code) | Candidate, evidence pending → Phase 5 |
| `-zm` | Function-per-segment padding between functions | Candidate, evidence pending → Phase 5 |

### Pattern 7: C vs C++ scan (CID-06)

Signals and what the prototype found [VERIFIED counts]:
1. **XI/YI init tables (strongest).** CLIB modules declare `XIB/XI/XIE/YIB/YI/YIE` DATA segments, with XI entries **6 bytes** each (SEGDEF length 6 in 15 CLIB3R modules). Find them through the matched `inirt386` module (`__InitRtns`): its absolute fixups target `XIB`, `XIE`, `YIB`, `YIE`, and the LE fixups at those sites give the table addresses in obj2. Read entries with `load_flat(relocate=True)` (unrelocated bytes do not hold the target address). Classify by priority: Watcom `INIT_PRIORITY_THREAD=1, FPU=2, RUNTIME=10, LIBRARY=32, PROGRAM=64`, `DTOR_PRIORITY=40` [CITED: open-watcom-v2 bld/watcom/h/rtprior.h; ASSUMED unchanged since 10.6, A4]. C++ static constructors use PROGRAM (64) and module destructors 40.
   - UFO2P XI at 0x13E11C..0x13E158 (10 entries: 7× prio 32, 1× each 1/2/3); YI 0x13E158..0x13E164 (2 entries: prio 1, 32). TACP XI 0x2B63D6..0x2B6412, the same priority profile. **No prio-64 or prio-40 entries in either EXE** → no C++ static init or module destructors. One prio-1 entry per table points to unmatched code just after the runtime (thread init, probably an unmatched short CLIB module).
2. **`__wcpp_` routines via the runtime map:** at MIN_UNMASKED ≤ 16 the PLIB modules `undefmbr`/`undefed`/`fatalerr` "match". These are false positives: the 18-byte range is also matched by CLIB `noefgfmt` (`_no_support_loaded_`) and `nomem` (`_Not_Enough_Memory_`), and the stub-referencing pointers in obj2 are CLIB's. Only ranges matched **exclusively** by C++ libraries that also pass the disambiguation rules count as C++ evidence. After that, none remain.
3. **Mangled `W?` strings / `__wcpp_` strings:** a string scan of obj2 (the existing toolchain.md says none; re-run as part of the scan).
4. **Vtable-shaped runs** (≥2 consecutive off32 fixups in obj2 whose targets are obj1 function starts outside the library): weak, because C function-pointer tables look identical. Report them as candidates only and never use them as the deciding signal.

Expected CID-06 verdict format (per EXE): "C (`wcc386`): no XI program-priority or YI destructor entries, no C++-only runtime module, no `W?` strings; N vtable-shaped candidate tables (C dispatch tables indistinguishable)". If any signal fires, name the modules that need `wpp386`.

### Anti-Patterns to Avoid
- **Whole-file object hash for D-03:** never equal across host and container (absolute paths). Use the normalized hash.
- **48-byte prefix matching for version evidence:** prefixes are shared across versions. Use whole segments.
- **Counting idioms over the whole file:** D-06/D-10 require the runtime mask.
- **Trusting single short matches as C++ evidence:** see Pitfall 4.
- **Shelling out with a string command:** list argv only; the cflags file is input data.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| CRC-32 for wpack | Table-driven CRC | `zlib.crc32` | Same polynomial (reflected 0xEDB88320; residue 0xDEBB20E3); verified equal on the 10.5 archive |
| File hashing / manifest validation | New hash code | `targets.hash_file`, `hash_bytes`, `FileHashes`, `watcom.check_version` | Existing, tested, D-13 says reuse |
| Reading the LE | New parser | `le.LE` (`objects`, `fixups()`, `load_flat(relocate=)`) | Phase 3 verified 87/87 |
| ISO reads for DISKIMGS | 7-Zip/subprocess | `iso9660.extract_all` (already done by install) | Stdlib, guarded |
| Glob matching | Hand regex | `fnmatch.fnmatchcase` | Semantics verified |
| Running Win32 compiler on Linux | Wine/dosemu | wibo 1.2.0 (in image) | Verified for all versions |
| Disassembly for humans | Own disassembler | `wdis` (OW v2, in image) on probe objects | Already installed |
| The Bentley-McIlroy qsort tie order | "Any sort" | A faithful port of Watcom's `qsort` (shell sort <16, BM partition) | A stable sort produced a wrong decode |

**Key insight:** in this domain the dangerous parts are *quiet* differences: environment-injected options, NT-default target macros, absolute paths in objects, equal-length identical library stubs. Each needs an explicit test rather than more code.

## Runtime State Inventory

Not a rename/refactor phase. One runtime-state item matters: after `install-watcom 10.5` gains the decoder, **existing installs** still hold the 65,536-byte stub. `check-watcom 10.5` will then report MISMATCH (not KNOWN BAD) for anyone who installed before. The plan needs a user-facing step: `uv run reverseapoc install-watcom 10.5 --force` (data migration of the local tree), documented in toolchain.md. Nothing else (no services, OS registrations, secrets or build artifacts carry Phase 4 state).

## Common Pitfalls

### Pitfall 1: Environment variables silently change codegen
**What goes wrong:** `WCC386=<opts>` (and `INCLUDE`) in the environment are honoured by the compiler; compose loads `../.env` into the container.
**How to avoid:** Wrapper builds the child env from scratch; a test asserts that `WCC386`, `WPP386`, `INCLUDE`, `WATCOM` set in the parent env are absent in the child env (inject a fake runner).
**Warning signs:** Host and container objects differ; `movzx` appears where `and` was expected.

### Pitfall 2: NT-hosted compiler targets NT by default
**What goes wrong:** Without `-bt=dos`, `__NT__` is defined and headers take NT branches (errno/threading macros), so codegen around library calls can differ from the 1997 DOS build.
**How to avoid:** `-bt=dos` in the `*` rule of cflags.txt (or wrapper-enforced). A test compiles a `#if defined(__DOS__)` probe and checks the public symbol.

### Pitfall 3: "Object hashes identical" is impossible across host/container
**What goes wrong:** THEADR and COMENT 0xE9 embed absolute paths and timestamps (the compiler expands relative paths with `GetFullPathNameA`).
**How to avoid:** Always pass `-zld`. Define `normalized_object_sha1(obj)` = SHA-1 over records excluding THEADR (0x80) and COMENT class 0xE9. D-03 logs both raw and normalized hashes and gates on normalized.

### Pitfall 4: Identical library bodies masquerade as C++ runtime or the wrong module
**What goes wrong:** 18-byte CLIB stubs (`noefgfmt`, `nomem`) equal the C++ `__wcpp_2_undefined_member_function__`/`__wcpp_2_undefed_cdtor__` stubs after masking. C++ `fatalerr` equals the head of CLIB's `__fatal_runtime_error_`. A naive scan "finds" the C++ runtime in both EXEs.
**How to avoid:** Disambiguation rules (data-segment check, call-graph consistency, C-before-C++ preference, `ambiguous` status). CID-06 counts only exclusive, consistent C++ matches.

### Pitfall 5: Easy OMF and non-OMF libraries
**What goes wrong:** `EMU387.LIB`/`NOEMU387.LIB` use 16-bit record numbers with 32-bit fields (COMENT 0xAA); `NT/*.LIB` include COFF `!<arch>` archives. A strict parser crashes mid-sweep.
**How to avoid:** Easy-OMF flag per module; first-byte check per library; report skipped and failed modules in the sweep summary.

### Pitfall 6: Stray `.err` files in the repo
**What goes wrong:** On a compile error the compiler writes `<stem>.err` into the cwd (repo root).
**How to avoid:** Always pass `-fr=<objdir>\<stem>.err` (or bare `-fr`). Make sure the hygiene test still passes after a failing compile test.

### Pitfall 7: MSYS and the Bash tool eat backslashes
**What goes wrong:** In Git Bash, `"\\"` collapsed and MSYS rewrote `-i=` arguments during this research. Hand-typed spike commands silently compile the wrong path.
**How to avoid:** Path conversion happens in Python (`PureWindowsPath`-style join, never via the shell). On the host run the wrapper from `uv run` (no MSYS conversion of Python's `subprocess` argv). For manual spikes use `MSYS_NO_PATHCONV=1` and `$'\x5c'`.

### Pitfall 8: wpack tie order and header size
**What goes wrong:** A stable sort, or OW v2's 16-byte header (with `internal`), decodes garbage. The 10.5 archive has a 12-byte header (`disk_addr = 12`).
**How to avoid:** Port Watcom's qsort exactly. Read the header size from the first file's `disk_addr` sanity (must equal 12 for this media; reject otherwise). Verify the compressed-stream CRC before decoding and size + SHA-1 after.

### Pitfall 9: mosura's fingerprint table taken as ground truth
**What goes wrong:** Register-bound claims are construct- and flag-specific (our probe showed the opposite register use); `setcc/and` alone does not exclude 11.0 at `-4`.
**How to avoid:** Calibrate idioms from our probe compiled with each version **and** each candidate flag set (`-4r`/`-5r`, `-ox`/`-oneatx`/`-os`). Report ties.

### Pitfall 10: Short-threshold and LIDATA-fixup segments disappear silently
**What goes wrong:** Unmatched runtime bytes leak into "game code" counts (e.g. the prio-1 init routine, short stubs), inflating idiom counts.
**How to avoid:** Record `short`/`unmaskable` segments. Report the coverage of the runtime region (`_cstart_`-adjacent area). Treat counts as lower-confidence near runtime boundaries.

## Code Examples

### Normalized object hash (D-03)
```python
# Source: this research's spike; OMF record layout per the TIS OMF 1.1 spec (type u8, length u16, body, checksum)
import hashlib, struct
_REC_TYPE = 0
_REC_LEN = 1
_REC_BODY = 3
_THEADR = 0x80
_COMENT = 0x88
_COMENT_CLASS = _REC_BODY + 1      # COMENT body: comment type byte, then class byte
_CLASS_DEPENDENCY = 0xE9
_MODEND = (0x8A, 0x8B)

def normalized_object_sha1(data: bytes) -> str:
    h, pos = hashlib.sha1(), 0
    while pos < len(data):
        kind = data[pos + _REC_TYPE]
        length = struct.unpack_from("<H", data, pos + _REC_LEN)[0]
        rec = data[pos:pos + _REC_BODY + length]
        if not (kind == _THEADR or (kind == _COMENT and rec[_COMENT_CLASS] == _CLASS_DEPENDENCY)):
            h.update(rec)
        pos += _REC_BODY + length
        if kind in _MODEND:
            break
    return h.hexdigest()
```

### Masked verify at a candidate (Pattern 3, step 5)
```python
def verify_at(code: bytes, base: int, va: int, seg: bytes, mask: frozenset[int],
              absolute: frozenset[int], target_fixups: set[int]) -> bool:
    if base < 0 or base + len(seg) > len(code):
        return False
    for k, byte in enumerate(seg):
        if k in mask:
            continue
        if code[base + k] != byte or (va + k) in target_fixups:
            return False
    return all((va + off) in target_fixups for off in absolute)
```

### Wrapper argv (Pattern 5)
```python
def build_argv(version: str, flags: list[str], src_rel: str, obj_rel: str, err_rel: str,
               *, native: bool) -> list[str]:
    tree = f"third_party/watcom/{version}"
    win = lambda p: p.replace("/", "\\")
    compiler = f"{tree}/BINNT/WCC386.EXE"
    argv = [] if native else ["/usr/local/bin/wibo"]
    argv += [win(compiler) if native else compiler,
             "-zq", "-zld", f"-fr={win(err_rel)}", *flags,
             f"-i={win(tree + '/H')}", win(src_rel), f"-fo={win(obj_rel)}"]
    return argv
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| Run 10.x under DOSBox/dosemu (mosura, Daggerfall) | wibo 1.2.0 runs the BINNT loader, which hosts the LE compiler (Correction 2026-10-21: measured LX in 10.5, 10.6 and 11.0; see docs/learnings.md.) | decomp.me cromper; verified here | Fast (~40-90 ms per compile), no emulator in image |
| KKND `lib_match.py`: prefix at known function starts | Anchor-and-verify slide over the whole code object, whole segments, both-side masks | This research | No function list needed (Phase 4 precedes the split) |
| Version from banner | Library-module version sets + calibrated probe idioms | mosura, Theme Hospital | Banner cannot separate 10.5/10.6/11.0 |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | Writing `wpack.py` from a format description (not copying OWPL code) keeps `tools/` GPLv3-clean; LZHUF tables are freely reusable | Pattern 1 | Licence conflict in `tools/`. RESOLVED by D-15 (owner, 2026-10-21): independent implementation from `docs/research/wpack-format.md`, OWPL `bld/wpack` cited as format reference only, LZHUF tables reused (plan 04-03) |
| A2 | The 10.5 archive's 12-byte header layout (vs OW v2's 16-byte) applies to all 10.5 PCK archives we touch | Pattern 1 / Pitfall 8 | Only PCK00017 is needed; low risk |
| A3 | EMU387 being linked implies game objects were compiled with `-fpi` (not `-fpi87`); wlink may link the emulator if *any* object requests it | Flag matrix | `-fpi87` for some modules would go unnoticed; Phase 5 matches confirm (code is identical either way, only the default-lib COMENT differs) |
| A4 | Watcom 10.6 used the same init priority constants as OW v2's `rtprior.h` (32 library / 64 program / 40 dtor) | Pattern 7 | The observed library entries all have 32, which supports it; if wrong, re-derive from 10.6 CLIB XI entries per module |
| A5 | wcc386 10.6's default CPU target is `-5r` (the default-flag probe matched `-5r` output on the tested constructs) | Pattern 6 | Only matters if cflags omit `-5r`; recommend always writing it explicitly |
| A6 | The ~40/32 `__CHK` call sites belong to game or third-party modules compiled without `-s`, not to unmatched Watcom runtime | Flag matrix | Their location (0x10000 and 0xB0000 blocks, below `_cstart_`) suggests non-runtime; Phase 5 split confirms |
| A7 | Byte-pattern idiom hits inside code are real instructions (not jump-table data in code) | Pattern 6 | Small count noise; acceptable for "counts favour" (D-10) |

## Open Questions (RESOLVED)

All five were settled before planning (owner decisions D-15/D-16 and the Claude's-discretion items in
04-CONTEXT.md, 2026-10-21) or are answered by execution; none blocks planning.

1. **Where do the 10.5 decoder's expected hashes come from in tests?** RESOLVED
   - What we know: the prototype gives size 567,558, sha1 `a479921b…`, md5 `17751042…`, crc32 `0xDAA1AD2A`.
   - Recommendation: the executor re-derives them with the production decoder, verifies the banner, and only then edits `config/watcom.toml` (one reviewed commit). Tests read them through `load_watcom_manifest()` (Phase 3 D-15/D-21 pattern).
   - **RESOLVED:** recommendation adopted (D-01, D-15). Plan 04-03 writes the decoder from `docs/research/wpack-format.md`; plan 04-06 Task 2 re-derives size and hashes from a real end-to-end `install-watcom 10.5`, checks the banner, pins them in `config/watcom.toml`, and `tests/test_wpack_real.py` reads the pin through `load_watcom_manifest()`, never a copied literal.
2. **Does D-05's "every 32-bit library" include the NT/OS2/WIN/NETWARE subtrees?** RESOLVED
   - What we know: whole-tree sweep costs 19 s for 3 versions and adds no new ranges; every range is also matched by a `DOS/` library.
   - Recommendation: sweep the whole tree (literal reading of D-05), skip non-OMF libraries with a reported reason, and in `runtime.csv` list all matching libraries but order `DOS/` and root first.
   - **RESOLVED:** recommendation adopted as a Claude's-discretion item in 04-CONTEXT.md (whole `LIB386` tree, each non-OMF library skipped with its reason reported). Plan 04-02 Task 3 (`test_lib386_sweep`: every library parsed or reported not OMF, non-OMF only under `NT/`); plan 04-05 (skip records `not OMF`, `runtime.csv` libraries with `DOS/` and root first); D-16 puts the file at `config/ufo2p/runtime.csv` and `config/tacp/runtime.csv` (plan 04-07).
3. **COMDAT support in `omf.py` now or in Phase 5?** RESOLVED
   - Recommendation: now, minimal (COMDAT32 data + name), because the PLIB C++ libraries keep code in COMDATs and CID-06 should scan them; Phase 5 needs it anyway (SPL-07).
   - **RESOLVED:** now, adopted as a Claude's-discretion item in 04-CONTEXT.md (`omf.py` supports COMDAT and Easy OMF now). Plan 04-02 Task 2 (Easy OMF, COMENT 0xAA) and Task 3 (COMDAT32 blocks with their fixups).
4. **Which modules lack `-s`?** RESOLVED
   - What we know: 40 (UFO2P) / 32 (TACP) `__CHK` calls in two address clusters.
   - Recommendation: report the ranges in toolchain.md; per-glob rules come when Phase 5 maps them to translation units.
   - **RESOLVED:** answered by execution in plans 04-10/04-11 per D-08/D-09; not a planning blocker. Plan 04-10 Task 2 counts the `__CHK` call sites per EXE grouped by 64 KiB block (`-s` evidence); plan 04-11 Task 2 records them in toolchain.md's Flags table. Per-glob `cflags.txt` rules for those modules wait for Phase 5's split (A6).
5. **Are UFO2P and TACP flags identical?** RESOLVED
   - Recommendation: report per EXE (D-09). The prototype numbers have the same signs for both, but TACP's setcc/movsd counts differ in magnitude.
   - **RESOLVED:** answered by execution in plans 04-10/04-11 per D-08/D-09; not a planning blocker. Plan 04-10 prints the evidence per flag and per EXE; plan 04-11 Task 2 gives toolchain.md one column per EXE, and "both EXEs use the same flags" is recorded only as a finding.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| Docker Desktop + `reverseapoc-build:local` image | wibo compiles, container test gate | ✓ | Docker 29.6.2; image present | — |
| wibo | CID-01 | ✓ (container) | 1.2.0 | Native Windows host run |
| `third_party/watcom/{10.5,10.6,11.0}` trees | everything | ✓ (10.5 BINW is the stub until D-01) | — | — |
| `third_party/watcom-media/*.iso` | wpack via install-watcom | ✓ | 5 ISOs | Installed `DISKIMGS/` tree |
| `orig/UFO2P.EXE`, `orig/TACP.EXE` | libmatch, probe scans | ✓ | — | — |
| Python | all tooling | ✓ | 3.14.5 (host via uv, image) | — |
| `wdis` | probe inspection | ✓ (container only) | OW v2 2026-10-01 | — |
| capstone | not needed | — | — | — |
| `gh` CLI | research only | ✓ | — | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none. 10.5 depends on D-01 (time-boxed; deferral path defined).

## Validation Architecture

### Test Framework
| Property | Value |
|---|---|
| Framework | pytest ≥ 9.1 (dev group), ruff ≥ 0.17 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["."]`) |
| Quick run command | `uv run pytest -q tests/test_<module>.py` |
| Full suite command | `uv run pytest -q && uv run ruff check .` (host) and `docker compose run --rm test` (from repo root; container) |

Skip conditions (extend `tests/conftest.py`):
- `ORIG_DIR` / `REVERSEAPOC_ORIG` (existing) for anything reading the EXEs.
- **New:** `WATCOM_DIR = Path(os.environ.get("REVERSEAPOC_WATCOM_DIR") or REPO_ROOT / "third_party" / "watcom")` for installed trees (worktrees have no `third_party/`). Skip per version if `WATCOM_DIR/<ver>` is missing.
- `REVERSEAPOC_WATCOM_MEDIA` (existing) for ISO-based wpack tests.
- Compile tests: skip unless (`sys.platform == "win32"`) or `shutil.which("wibo")` (container). 10.5 compile tests also skip while the 10.5 BINW key file is not `ok`.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| CID-01 | 10.6/11.0 (and 10.5 after D-01) compile a probe under wibo/native; banner contains `Version <ver>`; hashes logged | real-file integration | `uv run pytest -q tests/test_compiler_real.py` (in container for wibo) | ❌ Wave 0 |
| CID-01 | wpack decodes PCK00017 to the manifest-pinned size/SHA-1; packed-stream CRC checked; corrupt/truncated input raises `WpackError` | unit (synthetic) + real-file | `uv run pytest -q tests/test_wpack.py tests/test_wpack_real.py` | ❌ Wave 0 |
| CID-01 | install-watcom 10.5 runs the decoder inside `.partial`; check-watcom reports OK, not KNOWN BAD | unit (fake ISO via `tests/isoimage.py` + synthetic wpack) | `uv run pytest -q tests/test_watcom.py -k wpack` | ❌ extend existing |
| CID-02 | cflags parsing: `*` first, last match wins, refuse unmatched, comments, bad `compiler@version`, forbidden wrapper-owned flags | unit | `uv run pytest -q tests/test_cflags.py` | ❌ Wave 0 |
| CID-02 | Two sources get the version/flags their rules assign (argv inspected through an injected runner) | unit | `uv run pytest -q tests/test_compiler.py -k two_sources` | ❌ Wave 0 |
| CID-02 | Path allowlist (space, leading `-`, `..`, outside repo), backslash rewrite, include only own `H`, env scrub (`WCC386`/`INCLUDE` absent), `-bt=dos`/`-zld`/`-fr=` present, hash gate refuses mismatch and known_bad, banner cached | unit | `uv run pytest -q tests/test_compiler.py` | ❌ Wave 0 |
| CID-02 | Real two-file compile with differing rules gives objects whose model COMENT/codegen differ as expected (e.g. `-3r` vs `-5r` byte-compare idiom) | real-file | `uv run pytest -q tests/test_compiler_real.py -k cflags` | ❌ Wave 0 |
| CID-04 | OMF reader: synthetic LIB (header, pages, 0xF1), records incl. Easy OMF, THREAD fixups, LIDATA nesting cap, COMDAT32, non-OMF skip | unit | `uv run pytest -q tests/test_omf.py` | ❌ Wave 0 |
| CID-04 | Real LIB facts: 10.6 `DOS/CLIB3R.LIB` = 549 modules, 10.5 = 544, 11.0 = 970; EMU387 parses with Easy OMF | real-file | `uv run pytest -q tests/test_omf_real.py` | ❌ Wave 0 |
| CID-04 | libmatch on a synthetic LE (conftest `build_le_image`) with a planted synthetic module: masked match found, target-fixup-in-unmasked rejects, missing abs fixup rejects, short/unmaskable recorded, ambiguity rules | unit | `uv run pytest -q tests/test_libmatch.py` | ❌ Wave 0 |
| CID-04 | `config/<exe>/runtime.csv` re-derived equals committed (drift); `_cstart_` at entry VA; ≥1 range whose versions exclude all but one version (D-07 informative) | real-file | `uv run pytest -q tests/test_libmatch_real.py` | ❌ Wave 0 |
| CID-03 | Idiom counters on synthetic byte strings (setcc/and, setcc/movzx, unrolled movsd, rep movsd, __CHK calls, loop shapes) respect the library mask | unit | `uv run pytest -q tests/test_probe.py` | ❌ Wave 0 |
| CID-03 | Probe compiled per version: calibration table (which idiom each version × flag set emits) is reproduced; non-lib counts per EXE recorded | real-file | `uv run pytest -q tests/test_probe_real.py` | ❌ Wave 0 |
| CID-05 | toolchain.md has no "To be confirmed in Phase 4" line in the Compiler section and has per-EXE columns for each observable flag | doc lint (unit) | `uv run pytest -q tests/test_hygiene.py -k toolchain` | ❌ extend existing |
| CID-06 | XI/YI table reader on a synthetic LE; priority classification; PLIB-only/consistency rule; per-EXE report | unit + real-file | `uv run pytest -q tests/test_cppscan.py tests/test_cppscan_real.py` | ❌ Wave 0 |
| D-03 | Normalized object hash equal native vs wibo per version | manual, logged under `build/gate/04-native-vs-wibo.txt` | `uv run reverseapoc cc probe/cg_basic.c -o build/gate/...` on host and in container, then `uv run reverseapoc objhash ...` | manual-only (host + container) |

### Sampling Rate
- **Per task commit:** `uv run pytest -q tests/test_<touched>.py && uv run ruff check .`
- **Per wave merge:** `uv run pytest -q && uv run ruff check .` on the host, then `docker compose run --rm test`
- **Phase gate:** full suite green on host and in container; real-file tests ran (not skipped) on the owner's machine; D-03 log present.

### Wave 0 Gaps
- [ ] `tests/conftest.py`: `WATCOM_DIR` + `REVERSEAPOC_WATCOM_DIR`, `requires_version(ver)` and `requires_runner()` skip helpers
- [ ] `tests/omfimage.py`: synthetic OMF record/LIB builder (own literals, per coding-style)
- [ ] `tests/wpackimage.py`: synthetic NO_SHANNON archive builder (+ a tiny Shannon-coded case whose table has < 16 entries per length, so qsort ties take the shell-sort path and order is deterministic)
- [ ] test files listed in the map above
- [ ] No framework install needed

## Security Domain

`security_enforcement: true`, ASVS level 1.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | Bounds-checked binary parsers (`OMFError`, `WpackError` on any out-of-range length); LIDATA recursion depth and expanded-size caps; wpack output bounded by header length **and** manifest size; cflags line validation; path allowlist (D-14) |
| V6 Cryptography | no (integrity hashes only) | `hashlib.sha1`/`md5`, `zlib.crc32` for identification, not security |
| V10 Malicious Code / V12 Files | yes | wpack ignores archive-embedded names and writes only the manifest path; wrapper writes only `-fo`/`-fr` targets under `build/`; no `shell=True` |
| V14 Configuration | yes | Scrubbed child environment (no `WCC386`/`INCLUDE` injection); read-only compiler mount respected; no compiler bytes in logs |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Option injection through env vars (`WCC386`) or crafted flags in cflags | Tampering | Empty env + flag allowlist; tests |
| Path injection via `/`-prefixed or spaced paths (Watcom option parsing) | Tampering | D-14 allowlist + backslash rewrite |
| Decompression bomb / malformed archive | DoS | Size caps, CRC pre-check, typed errors |
| Malformed OMF causing unbounded recursion or huge allocations | DoS | Depth cap, SEGDEF-length bounds |
| Proprietary bytes leaking into logs/CSV/tests | Information disclosure | Outputs are addresses/names/hashes only; tests assert CSV columns have no hex byte dumps |

## Recommended Plan Decomposition

The 10.5 decoder runs as its own track so it never blocks 10.6/11.0 (D-01 time box).

- **Wave 0 (scaffolding):** conftest overrides and skip helpers; synthetic builders (`omfimage.py`, `wpackimage.py`); spike record `.planning/spikes/004-wibo-watcom/` from this research.
- **Wave 1 (parallel):**
  - 1A `cflags.py` + `compiler.py` + `cc` verb + hash gate + banner + env scrub (CID-01 for 10.6/11.0, CID-02).
  - 1B `omf.py` (LIB walk, records, Easy OMF, COMDAT32 minimal, normalized object hash helper).
  - 1C `wpack.py` + install-watcom 10.5 hook + manifest pin (time-boxed one day; on miss: deferral note in toolchain.md, VERIFICATION, CID-01 reworded).
- **Wave 2:** `libmatch.py` + `libmatch` verb + `config/UFO2P|TACP/runtime.csv` + drift test (CID-04). Depends on 1B.
- **Wave 3 (parallel):**
  - 3A probe sources (`probe/*.c`, C89) + `probe.py` calibration (per version × candidate flag set) + non-lib idiom and flag scans per EXE (CID-03, D-08, D-10). Depends on 1A + 2.
  - 3B `cppscan.py` (XI/YI via `inirt386`, exclusive C++ matches, `W?` strings, vtable candidates) per EXE (CID-06). Depends on 2.
- **Wave 4:** D-03 native vs wibo log per version (manual, `build/gate/04-*`); `config/cflags.txt` `*` rule with evidence-backed flags; `docs/toolchain.md` (per-EXE columns, per-flag evidence, library version vs game-code version reported separately, "10.6 (10.5 byte-identical on the probe)" wording if so), `docs/matching.md` table + Known idioms, `docs/learnings.md` (wpack, env injection, `-bt=dos`, normalized hash) (CID-05). 10.5 joins Waves 3/4 whenever 1C lands.

## Sources

### Primary (HIGH confidence)
- Commands run this session in `reverseapoc-build:local` (wibo 1.2.0) and natively: spike table, env/target/`.err` behaviour, normalized-hash equality, timings
- Scratch prototypes (wpack decoder, OMF/LIB parser, library matcher, XI/YI reader, idiom counters) run read-only against `orig/` and `third_party/watcom/`; counts, addresses, names and hashes only
- Repo files read this session: `config/watcom.toml` (10.5 BINW entry lines 36-42: `size = 65536`, `known_bad = true`), `docker/compose.yaml` (lines 17, 20: `- ../third_party/watcom:/work/watcom:ro`, `- ../third_party:/work/third_party:ro`; line 24 `env_file:`), `tools/reverseapoc/watcom.py`, `le.py`, `cli.py` (line 190: `except (IngestError, LEError, ManifestError, ISOError, WatcomError, OSError) as exc:`), `tests/conftest.py` (line 21 `REVERSEAPOC_ORIG`), `configure.py` (line 65 `_SAFE_ORIG = re.compile(r"[A-Za-z0-9._/:-]+")`)
- Open Watcom v2 `bld/wpack/{h/wpack.h,c/decode.c,c/common.c,c/wpackio.c,c/wqsort.c}` at commit 4c245dddbf4d23262c51ba2b4b809c1b34a9fa86 (format reference only)
- Open Watcom v2 `bld/watcom/h/rtprior.h` (init priorities)
- KKND-Decomp `tools/lib_match.py`, `tools/omf.py` at a371547864bb0884f0fc9efe07b681cda5b9eeef (CC0)
- decomp.me `cromper/cromper/compilers.py` at 6056cf56b3bf4f1cfcf2496fe97f83cc09b08010

### Secondary (MEDIUM confidence)
- mosura `docs/watcom-codegen-fingerprint.md` (no licence; facts cited, nothing copied): 10.5 = 10.6 on its probe, 10.5 unpack route, construct table
- PyPI JSON for capstone 5.0.9 wheel tags

### Tertiary (LOW confidence)
- Licence-compatibility reading of OWPL vs GPLv3 (A1, resolved by D-15)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (no new dependencies; all tools verified present)
- Spike / wrapper behaviour: HIGH (executed)
- wpack: HIGH (prototype decoded and ran the compiler)
- OMF + library match: HIGH for facts and counts; MEDIUM for the threshold/disambiguation policy (validated on two EXEs only)
- Flags for game code: MEDIUM (scan evidence; `-o*`/`-zp`/`-zm` deferred by D-08)
- C vs C++: MEDIUM-HIGH (XI/YI evidence strong; vtable signal weak by nature)

**Research date:** 2026-10-21
**Valid until:** 2026-11-20 (stable domain; re-check wibo/decomp.me pins if the image changes)
