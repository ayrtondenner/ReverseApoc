# Phase 5: Split and first matches - Research

**Researched:** 2026-10-23
**Domain:** Watcom 10.x OMF -> ELF32 bridge, LE target-object cutting, objdiff 3.8.2, Ghidra 12.1.4 headless in Docker, capstone discovery, relocation-checked splice
**Confidence:** HIGH for the mechanics probed in this session (objdiff, Ghidra, Watcom OMF shape, clang, capstone); MEDIUM for estimates (candidate counts, discovery disagreements); LOW only where tagged `[ASSUMED]`

All game-file observations below are offsets, lengths, counts, booleans, addresses and SHA-1s. No instruction bytes or disassembly of the game appear here. Byte strings shown in examples are made up for synthetic fixtures.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Spike, Ghidra and fallback
- **D-01:** The objdiff spike runs first, in wave 1, before any Ghidra or splitter work. It is time-boxed to about one day and registered with `/gsd-spike` as Given/When/Then. The method:
  1. Take a Phase 4 runtime function, i.e. a CLIB3R row of `config/<exe>/runtime.csv`. Its flags and bytes are already known, so it makes a known-good pair.
  2. Compile it with `reverseapoc cc`.
  3. Convert the object with a minimal `omf2elf`.
  4. Cut the target ELF from `le.py` bytes.
  5. Run objdiff-cli 3.8.2 on the pair.
- **D-02:** The verdict is INVALIDATED only if objdiff cannot load our ELF, or cannot show 100% on a byte-identical pair with its relocations mapped. If it works only with workarounds, the verdict is PARTIAL: the hybrid pipeline stays and the workarounds are recorded. Whatever the verdict, the KKND-style relocation check (SPL-09) is built.
- **D-03:** Ghidra 12.1.4 with the lastonesky ghidra-lx-loader v12.1.4-1, one loader per install. Pins:
  - Ghidra: `ghidra_12.1.4_PUBLIC_20260921.zip`, 569,649,598 bytes, SHA-256 `ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db`, which matches the release notes.
  - Loader: `ghidra_12.1.4_PUBLIC_20261010_ghidra-lx-loader.zip`, 331,500 bytes, SHA-256 `0a9c65cee8c090ec4b7f72b595eb829267f80ae8f36a2a44d4ef1ef5af41be45`, the GitHub asset digest.

  Ghidra 12.2 is rejected because the loader ships no 12.2 build and Ghidra refuses an extension built for another version. retrokit is not used. The lastonesky README calls UFO2P "DOS/16 LE and unbound", while our scan finds a bound DOS/4GW Pro file; this conflict gets checked when the loader first loads the real EXEs.
- **D-04:** Ghidra goes into the main Docker image (`docker/Dockerfile`), in one cached layer of about +800 MB. The layer holds:
  - `openjdk-21-jdk-headless` from apt, with the version pinned
  - Ghidra 12.1.4, unpacked under e.g. `/opt/ghidra`
  - the lastonesky extension, installed into it

  Both zips are downloaded at image build and checked against the D-03 SHA-256s, the same way the Dockerfile already pins objdiff-cli and wibo.

  This replaces "Ghidra in WSL2" from the design spec (owner, 2026-10-23). It is allowed because CLAUDE.md's user-supplied rule covers only the Watcom compiler and the game. Ghidra is Apache-2.0 and OpenJDK is GPLv2 with the Classpath Exception.

  Ghidra is a Java program, so headless use needs a JDK too. A Linux container cannot use the owner's Windows JDK (`C:\Program Files\Java\jdk-21.0.12.1`). That JDK stays optional, for running the Ghidra GUI natively on the host, which is not part of the pipeline. — **Reversibility:** reversible — moving Ghidra to a separate compose service later is a Dockerfile/compose change.
- **D-05:** The headless export is a CLI verb that runs in the container, e.g. `docker compose run --rm build uv run reverseapoc ghidra-export ufo2p`.
  - It drives `analyzeHeadless` with a committed Ghidra script that writes raw boundaries and names.
  - An adapter turns that output into input for `config/<exe>/functions.csv`.
  - `orig/` stays mounted read-only.
  - Tests that need the real Ghidra skip without it, through a `requires_ghidra()` helper next to `requires_runner()`.
  - The adapter is tested against synthetic export fixtures.

  No developer installs Ghidra or a JDK by hand, and there are no fetch/install/check-ghidra verbs.
- **D-06:** The first Ghidra task adds the Dockerfile layer. It proves `docker compose build` and has the container run a smoke test: `analyzeHeadless` loading a synthetic LE, or at least reporting its version. `tests/test_hygiene.py` is extended so it requires the pinned hashes in the Dockerfile and shows that no game or Watcom path is baked into the image. The owner's Downloads copies of the Ghidra zips are not used by the build.

#### Function list reconciliation
- **D-07:** Neither tool wins a boundary disagreement by default; evidence from the LE decides.
  - A start is real if it is a `call rel32` target, an absolute fixup target into code, an entry point, or a `runtime.csv` start.
  - An end is the next start or the start of padding.
  - Ghidra supplies boundaries, names and drafts, and capstone recursive descent over `le.py` bytes (`load_flat(relocate=False)`) supplies a second boundary list. Both feed the rule.
  - Target bytes always come from `le.py`, never from Ghidra (PITFALLS P4).
- **D-08:** A committed `config/<exe>/boundaries.csv` lists every Ghidra/capstone disagreement with a verdict: `rule`, `ghidra`, `capstone` or `data-in-code`, plus a reason. A test fails if any disagreement has no verdict. The file holds addresses only, never bytes. This is how the gate reads "every boundary disagreement reconciled" (SPL-02).
- **D-09:** `capstone==5.0.9` becomes the first runtime dependency, in `[project].dependencies` and `uv.lock`. Its reason goes into `docs/tools.md` first. Its py3-none wheels for win_amd64 and manylinux x86_64 load the library through ctypes, so Python 3.14 is fine. This resolves the STATE.md blocker "capstone cp314 wheels are unverified".
- **D-10:** `config/<exe>/functions.csv` has the columns `start,end,name,kind,unit,evidence`.
  - `kind` is one of `game`, `runtime`, `thunk`, `data-in-code`.
  - `evidence` is one of `call`, `fixup`, `entry`, `runtime`, `ghidra`, `capstone`.
  - Names are `func_XXXXXXXX`, or the Watcom public name for runtime rows.
  - There is no match-status column: the Phase 6 gate-written status table owns status, so the two never drift.

  The file is committed and holds addresses and names only. It is seeded from `runtime.csv` (04 D-06). — **Reversibility:** costly — Phase 6 progress, the scorer and the driver read this schema.

#### Units and stub convention
- **D-11:** `config/<exe>/units.csv` is an evidence-based draft for the whole EXE, and every function is in exactly one unit. Cuts come from:
  - `runtime.csv` boundaries
  - `__CHK` clusters (the 0x10000 and 0xB0000 blocks)
  - source-file and assert strings
  - data-order breaks
  - alignment gaps

  Units are drafts and may be re-cut later. Only the units that hold the first matches must be right in Phase 5.
- **D-12:** The stub for an unmatched function is a KKND-style `INCLUDE_ASM(func_XXXXXXXX);` marker in `src/<exe>/<unit>.c`. It expands to an extern declaration and emits no bytes, and the in-place splice keeps the original bytes. configure.py fails if any function listed in `units.csv` for a unit is neither defined in C nor marked. Whether decomp.wtf fork mode accepts this marker is the Phase 6 spike. — **Reversibility:** costly — every unit file carries the marker.
- **D-13:** Each unit gets one target ELF32 object, written directly by Python with no `as` step (ARCHITECTURE C11) and cut from `le.py` bytes. It holds:
  - one symbol per function
  - `R_386_32` and `R_386_PC32` relocations rebuilt from the LE fixups
  - synthesised `R_386_PC32` relocations for calls that leave the function (P8)

  Our side of each pair comes from `omf2elf`, and `objdiff.json` pairs the two. `objdiff.json` and `compile_commands.json` are generated and added to `.gitignore`.
- **D-14:** The compat header for the clang lint gate is `include/watcom_compat.h`, active only under clang.
  - It makes `__far`, `__near`, `__interrupt`, `__cdecl` and `__watcall` empty and turns `#pragma aux` into a no-op.
  - The lint command adds `-D__386__ -D__FLAT__` and `__WATCOMC__=1060` (10.6). That value changes only if matches settle on 10.5 (1050) or 11.0 (1100).
  - clang 18 is pinned into the Docker image, which resolves the STATE.md blocker "`clang` is missing from the Docker image".

#### First matches and compiler sweep
- **D-15:** Each EXE gets its own first function, picked by the PITFALLS P16 filter. The function must be game code outside `runtime.csv` with:
  - no jump table
  - no string or local-data reference
  - no straddling fixup (UFO2P has 14, TACP 11)
  - at least one `call rel32` and one absolute fixup

  A small scorer ranks the survivors easiest-first. A UFO2P/TACP twin is not required.
- **D-16:** The executor (Claude) drafts the C from the Ghidra decompile and `asm/`, then iterates against `check`. Only `check`'s output counts as a match: objdiff 100%, a passing relocation check, and both EXEs SHA-1 identical after the splice. The owner reviews the C at UAT. This is a rehearsal of the Phase 6 loop.
- **D-17:** The C structure and types are checked first. If a candidate still misses under the `* wcc386@10.6 -4r -s -fpi` default, a fixed, logged matrix is swept:
  - version: {10.6, 10.5, 11.0}
  - CPU: {`-4r`, `-5r`}
  - optimisation: {none, `-ox`, `-os`, `-ot`, `-oneatx`}
  - `-s` toggled where `__CHK` applies

  Each cell's result goes under `build/logs/`. If no cell reaches 100%, the next-ranked candidate is tried, up to 3 candidates per EXE. After that the run stops and reports at a checkpoint.
- **D-18:** A match that needs flags other than the default gets a per-glob rule in `config/cflags.txt`. The `*` default changes only when at least 3 functions from different regions of both EXEs agree (P18, no overfitting). Ties stay ties. `docs/toolchain.md` records each match's evidence cell, and that is how Phase 5 confirms or narrows the Phase 4 candidates (10.6 vs 10.5/11.0, `-4` vs `-5`, `-o*`). — **Reversibility:** costly — the default flags every later unit.

### Claude's Discretion
- `reverseapoc check <unit>`: its human output, its `--json` shape and its exit codes. It must print objdiff %, the relocation check and the splice SHA-1 (SPL-11), and serve the Phase 6 driver.
- omf2elf internals. It grows from `tools/reverseapoc/omf.py` (04 D-04). Only the 16-bit COMDAT (0xC2) and NBKPAT are still missing there.
- Scorer details and the exact Ghidra script language: Java, or Python through PyGhidra/Jython, whichever 12.1.4 headless supports cleanly.
- The straddling-fixup test (P3) and the negative tests: a wrong call or fixup target must fail the relocation check even where objdiff reports 100% (SPL-13).
- Execution topology, following the Phase 4 pattern:
  - tooling plans run in parallel worktree waves
  - the spike, first-match and gate plans run on the main checkout, using the recipe in auto-memory `gsd-main-checkout-plans`
  - the host suite and a container suite never run at the same time
- Which planning-adjacent docs still say "WSL2" for Ghidra and get corrected in a docs task:
  - `docs/workflow.md:91`
  - `docs/toolchain.md:229`
  - the design spec lines 49 and 88
  - `.planning/research/*`, left as historical research

### Deferred Ideas (OUT OF SCOPE)
- Whether decomp.wtf fork mode accepts the `INCLUDE_ASM` marker: the Phase 6 spike.
- Sweeping `-zp1/2/4/8`, `-zm` and `-fp3`/`-fp5`: only if the D-17 matrix finds no match.
- 11.0a/11.0b: only if matches favour 11.0 (04 D-02).
- Installed vs CD v1.00 primary build: revisit after Phase 5 (PROJECT.md Key Decisions).
- GhidraMCP / retrokit MCP for interactive agent queries: Phase 6 (agent context pack) or later.
- A host-native Ghidra GUI setup guide using the owner's Windows JDK: optional docs, not pipeline.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SPL-01 | Ghidra 12.1.4 (headless, JDK 21) with one LE loader in the Docker image exports a function list to `config/<exe>/functions.csv` | Verified in a throwaway container: apt pin `openjdk-21-jdk-headless=21.0.12.1+1-1~24.04.4`, extension installed by unzipping into `Ghidra/Extensions/`, `-loader LeLoader` loads both bound EXEs, Java GhidraScript export, ~1 min/EXE. See "Pattern 2" and "Ghidra headless facts" |
| SPL-02 | Independent capstone pass cross-checks the Ghidra list; disagreements reconciled | capstone 5.0.9 verified on Python 3.14; KKND `find_functions.py` shape; disagreement estimate (~500 / ~360 naive starts); the D-07 evidence rule and `boundaries.csv` test. "Pattern 3" |
| SPL-03 | Functions grouped into units under `config/<exe>/` | `units.csv` draft rules; Watcom emits functions out of source order and with fall-through (probe), so units are address ranges, not source orders. "Pattern 4" |
| SPL-04 | Stub convention keeps original bytes for unmatched functions | Verified: `INCLUDE_ASM(name)` -> `extern int INCLUDE_ASM_##name` emits no EXTDEF and no bytes under wcc386 10.6. "Pattern 4" |
| SPL-05 | Per-function disassembly generated into gitignored `asm/` | KKND `split.py` shape (CC0); operands must be resolved through `le.fixups()` because raw off32 fields hold object-relative offsets. "Pattern 9" |
| SPL-06 | `configure.py` writes `build.ninja`, `objdiff.json`, `compile_commands.json` | objdiff 3.x `config.schema.json` read at tag v3.8.2; TH `configure.py` layout; edge list in "Pattern 10" |
| SPL-07 | `omf2elf.py` converts Watcom OMF to ELF32 with pytest | Watcom 10.6 OMF shape probed (Easy OMF, loc 9, frame F1, targets T4/T6, addend in the field); TH conversion rules; objdiff accepted a converted 10.6 object at 100%. "Pattern 6" |
| SPL-08 | Target ELF objects cut from the LE with relocations rebuilt from LE fixups | Field rewrite rule (raw fields hold `target_off`), synthesized PC32, naming rules; verified objdiff pairing needs equal symbol name and section name `_TEXT`. "Pattern 5" |
| SPL-09 | Relocation check beyond objdiff | KKND `build_kknd.py` rules on the OMF side plus a reverse coverage check; objdiff verified blind to the second relocation of an instruction. "Pattern 7" |
| SPL-10 | Splice keeps original link-time value at each fixup site after its target is checked | `splice()` masks LE fixup fields only; our call rel32 fields are not LE fixups (UFO2P/TACP have 0 rel32 fixups), so the land step must fill both-side relocation fields from the original. "Pattern 8" |
| SPL-11 | Single-unit `check` tool prints objdiff %, reloc check, splice SHA-1 | `objdiff-cli diff -1 T -2 B -o - SYMBOL` JSON (`left.symbols[].match_percent`) and `report generate` JSON verified; proposed JSON shape and exit codes. "Pattern 11" |
| SPL-12 | C89 lint gate with Watcom compat header | Verified with `clang-18=1:18.1.3-1ubuntu1`: a compat header + `--target=i386-unknown-none -ffreestanding -nostdinc` passes Watcom constructs and fails a mixed declaration. "Pattern 12" |
| SPL-13 | One function per EXE matches, splices back, both EXEs SHA-1 identical, objdiff 100% | P16 funnel estimate (~565 UFO2P / ~683 TACP survivors, ~61 / ~74 at <=64 bytes); D-17 matrix is 30 cells; negative tests designed. "Pattern 13" |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Never commit game files, disassembly or build output: `orig/`, `asm/`, `build/`, `third_party/` stay gitignored. Ghidra decompiles and `asm/` listings are disassembly-class output: gitignored only.
- Never modify `orig/`, the hash manifests under `config/` (`targets.toml`, `watcom.toml`), or the build scripts to make a check pass.
- No secrets in tracked files or `.env`.
- Watcom and the game are user-supplied, never baked into the Docker image. Ghidra and OpenJDK are allowed in the image (D-04).
- A matched function is byte-identical and stays that way; no restructuring, no inline assembly or code-emitting `#pragma aux` to force a match (`.claude/rules/src.md`).
- Claude Code is the only agent runtime; plugins at project scope.
- Done gate (tooling): `uv run pytest -q && uv run ruff check .` green on the host and in `docker compose run --rm test`. Decompiled code: rebuilt EXE SHA-1 identical and objdiff 100% for the function.
- Python tooling (`.claude/rules/tools.md`): Python 3.14 via uv; TDD (failing pytest first); no third-party dependency without a reason in `docs/tools.md` first; `tools/` is GPLv3 and keeps derivation headers of KKND (CC0) and Theme Hospital (GPLv3) code; tests never embed game bytes, real-file tests skip without `orig/`; shallow nesting; no bare binary-format offsets (name each after its spec field); refactors pinned by tests first.
- C rules (`.claude/rules/src.md`): C89 for Watcom 10.x, `/* */` comments only, declarations at block start, lint gate `clang -fsyntax-only -std=gnu89 -Werror=declaration-after-statement` with the compat header; clang-format only with pragma masking.
- Workflow: GSD owns phases and sequencing; superpowers owns TDD and verification-before-completion inside a phase.

## Summary

Every mechanical question the spike and the tooling depend on was probed this session against the real tools, and none of them blocks the hybrid pipeline. objdiff-cli 3.8.2 loads hand-written ELF32 `ET_REL` objects with `.rel_TEXT` (implicit addends) and reports 100% for an identical pair. It reports less than 100% for a wrong call target or a wrong addend, but **still 100% when only the second relocation of an instruction is wrong** (`mov dword [A], offset B`). That is the SPL-13 negative test, already reproduced. A real Watcom 10.6 object converted with the Theme Hospital addend rule (`stored + displacement - 4` for self-relative fixups), using our `omf.py` model, paired at 100% against a target ELF with one `_TEXT` section per function. `[VERIFIED: objdiff-cli 3.8.2 in reverseapoc-build:local, synthetic objects]`

The D-01 spike has a literal known-good pair. Watcom's own `SRC/STARTUP/386/CMAIN386.C`, from the owner's 10.6 tree, compiled with `uv run reverseapoc cc` under the **default rule** `wcc386@10.6 -4r -s -fpi`, gives a 79-byte `__CMain` with 0 differing unmasked bytes against the `cmain386` runtime row in **both** UFO2P (0x000C5C9C) and TACP (0x000C7915). Its 4 self-relative call fixups and 5 absolute fixups exercise both relocation kinds. The 10.5 tree's copy also matches; 11.0's own copy differs. The catch: its relocation targets carry real linker names (`main_`, `exit_`, `stackavail_`, `____Argv`, `__ASTACKSIZ`, ...), not `func_`/`D_` placeholders. For objdiff to pair those relocations under `name_address`, the target writer needs an address-to-name map for them. That is the one workaround the spike will record. `[VERIFIED: compiled and compared this session]`

Ghidra 12.1.4 with the lastonesky loader runs headless in Ubuntu 24.04 as a non-root user with a read-only install. It imports both **bound** EXEs through the loader's BW-header walk; the README's "DOS/16 LE" is its name for this binding, so the D-03 conflict is resolved. It places `.object1` at 0x10000 and `.object2` at 0xD0000 / 0xE0000 with the le.py sizes. Its bytes equal le.py's at every non-relocation offset. It finds 1408 / 1498 functions in about one minute per EXE. Jython is only an uninstalled extension in 12.1.4, and PyGhidra's bundled JPype wheels stop at cp313, so **use a Java GhidraScript**. The image grows by about **1.17 GB** (882 MB Ghidra + 286 MB JDK), not the ~800 MB D-04 estimated. `[VERIFIED: throwaway container runs this session]`

**Primary recommendation:** run the spike on the `cmain386` pair with a minimal `omf2elf` (built on `omf.py`) and a minimal target writer (fields rewritten to addends, PC32 synthesized for calls, a spike-local address-to-name map). Build the OMF-side relocation check (KKND rules plus reverse coverage) as the authoritative gate. Fix two latent gaps before the first game match: the `cc` wrapper's single `-i=` (project headers), and the land step (fill our call fields from the original before `splice()`).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Ghidra 12.1.4 + JDK + LE loader | Docker image (`docker/Dockerfile`) | — | D-04; no host install; SHA-256-pinned downloads like objdiff/OW |
| Headless export (`ghidra-export`) | Python CLI verb (container) | Committed Java GhidraScript under `tools/` | CLI owns orchestration, paths, tmp project; script only dumps entries/bodies/names |
| Discovery (capstone) + reconcile | Python CLI (`tools/reverseapoc/`) | Committed config (`functions.csv`, `boundaries.csv`) | LE-derived evidence decides (D-07); committed output holds addresses/names only |
| Units + stubs | Committed config (`units.csv`) + `src/<exe>/*.c` | `configure.py` (validation) | Units are address ranges; configure refuses unmarked functions (D-12) |
| Compile | `reverseapoc cc` (existing) under wibo / native | `config/cflags.txt` | Unchanged wrapper, plus a project include dir |
| OMF -> ELF (base) | Python (`omf2elf`) | `omf.py` (reader) | Reader exists; writer is new |
| Target ELF (cut from LE) | Python (`target` writer) | `le.py` (only byte/fixup source) | P4: never Ghidra bytes |
| objdiff | objdiff-cli 3.8.2 (container only) | `objdiff.json` (generated, gitignored) | A viewer/score; not the gate (P7) |
| Relocation check | Python (OMF + LE, no ELF, no objdiff) | — | Independent oracle (SPL-09) |
| Land + splice + SHA-1 | Python (`splice.py` existing + new patch builder) | `config/targets.toml` | Existing splice masks LE fields only |
| Lint gate | clang 18 (container) | `include/watcom_compat.h` | Host has no clang |
| asm listings, Ghidra drafts | gitignored `asm/` | — | Disassembly-class output never committed |

## Standard Stack

### Core

| Tool / library | Version | Purpose | Why standard |
|---|---|---|---|
| objdiff-cli | v3.8.2 (already pinned, `ARG OBJDIFF_VERSION=v3.8.2`, Dockerfile:31) | Per-function diff and report | `[VERIFIED: objdiff-cli --version in reverseapoc-build:local]` Reads ELF and COFF only, so OMF must be converted |
| Ghidra | 12.1.4 PUBLIC 20260921 | Function list, names, drafts | `[VERIFIED: zip SHA-256 ddac49f9... recomputed this session]` |
| lastonesky ghidra-lx-loader | v12.1.4-1 (`extension.properties`: `name=LxLoader`, `version=12.1.4`) | LE loader + `watcom` cspec (`__watcall`: EAX, EDX, EBX, ECX) | `[VERIFIED: zip SHA-256 0a9c65ce... recomputed; ldefs id "watcom:LE:32:default"]` |
| OpenJDK 21 (headless JDK) | `openjdk-21-jdk-headless=21.0.12.1+1-1~24.04.4` | Runs Ghidra and compiles GhidraScripts | `[VERIFIED: apt-cache policy in ubuntu:24.04@sha256:68ee2200...]` Ghidra launches in `jdk` mode (`analyzeHeadless` -> `launch.sh ... jdk`) |
| clang 18 | `clang-18=1:18.1.3-1ubuntu1` (the `clang=1:18.0-59~exp2` metapackage depends on it) | Lint gate | `[VERIFIED: apt-cache policy; clang-18 --version "Ubuntu clang version 18.1.3 (1ubuntu1)"]` |
| capstone (PyPI) | 5.0.9, py3-none wheels | x86-32 decoding for discovery, asm, scorer, PC32 synthesis | `[VERIFIED: uv run --python 3.14 --with capstone==5.0.9; dist 5.0.9, cs_version (5, 0, 1280)]` `[WARNING: flagged as suspicious — verify before using.]` (see audit) |

### Supporting

| Library | Version | Purpose | When to use |
|---|---|---|---|
| ninja-build | 1.11.1-2 (image) | Build graph | All compile/convert/cut/lint edges |
| `reverseapoc cc` | in repo | Watcom compile under wibo | ninja `cc` rule |
| Python stdlib `struct`/`hashlib`/`json`/`csv` | 3.14 | ELF writer, CSVs, JSON | Everything else (stdlib-first) |

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|---|---|---|
| Java GhidraScript | PyGhidra | Needs pyghidra + JPype; the bundled `jpype1-1.5.2` wheels are cp39-cp313 only, and the project is on 3.14 `[VERIFIED: zip listing Ghidra/Features/PyGhidra/pypkg/dist]` |
| Java GhidraScript | Jython | Not installed by default in 12.1.4: it ships only as `Extensions/Ghidra/ghidra_12.1.4_PUBLIC_20260921_Jython.zip` `[VERIFIED: zip listing]` |
| `-loader LeLoader` | auto loader choice | Several loaders (MZ) accept the file; naming the loader avoids ambiguity. The class simple name worked `[VERIFIED: "Using Loader: Linear Executable (LE-Style DOS)"]` |
| RELA | REL | objdiff reads implicit addends for `R_386_32`/`R_386_PC32` (x86.rs `relocation_override`); TH and our probes use REL `[VERIFIED: objdiff v3.8.2 source + probe]` |

**Installation (Dockerfile additions, sketch):**
```dockerfile
# fetch stage: add unzip to its apt list, then
ARG GHIDRA_ZIP=ghidra_12.1.4_PUBLIC_20260921.zip
ARG GHIDRA_SHA256=ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db
ARG LXLOADER_ZIP=ghidra_12.1.4_PUBLIC_20261010_ghidra-lx-loader.zip
ARG LXLOADER_SHA256=0a9c65cee8c090ec4b7f72b595eb829267f80ae8f36a2a44d4ef1ef5af41be45
RUN curl -fsSL -o ghidra.zip "https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/${GHIDRA_ZIP}" \
 && echo "${GHIDRA_SHA256}  ghidra.zip" | sha256sum -c - \
 && unzip -q ghidra.zip -d /opt && mv /opt/ghidra_12.1.4_PUBLIC /opt/ghidra && rm ghidra.zip \
 && curl -fsSL -o lx.zip "https://github.com/lastonesky/ghidra-lx-loader/releases/download/v12.1.4-1/${LXLOADER_ZIP}" \
 && echo "${LXLOADER_SHA256}  lx.zip" | sha256sum -c - \
 && unzip -q lx.zip -d /opt/ghidra/Ghidra/Extensions && rm lx.zip
# final stage apt list: openjdk-21-jdk-headless=21.0.12.1+1-1~24.04.4  clang-18=1:18.1.3-1ubuntu1  (clang=1:18.0-59~exp2 for a plain `clang`)
# then: COPY --from=fetch /opt/ghidra /opt/ghidra   ENV GHIDRA_INSTALL_DIR=/opt/ghidra
```
```bash
uv add "capstone==5.0.9"   # after the docs/tools.md entry (D-09)
```

**Version verification done this session:** `npm`-style checks do not apply. PyPI `capstone` 5.0.9 was uploaded on 2026-05-28 with 11 wheels including `py3-none-win_amd64` and `py3-none-manylinux_2_17_x86_64`; the first release was 2.0 on 2014-01-21. The apt candidates were read in a fresh pinned `ubuntu:24.04` container. `[VERIFIED: pypi.org JSON API, apt-cache policy]`

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| capstone 5.0.9 | PyPI | 12+ years (2.0 on 2014-01-21; 37 releases) | not exposed by PyPI (the seam's only reason: `unknown-downloads`) | github.com/capstone-engine/capstone (9,128 stars; LICENSE.TXT + LICENSE_BSD_3_CLAUSE.txt; tag 5.0.9 exists) | [SUS] | Flagged: the planner adds a `checkpoint:human-verify` before `uv add`. Recommendation: approve. The flag comes from missing download data, not from any risk signal, and the package is a locked decision (D-09) |
| Ghidra 12.1.4 zip | GitHub release (NSA) | release 2026-09-21 | n/a | github.com/NationalSecurityAgency/ghidra | n/a (not a registry package) | SHA-256 pinned (D-03), re-verified this session |
| ghidra-lx-loader v12.1.4-1 | GitHub release | release 2026-10-10 | n/a | github.com/lastonesky/ghidra-lx-loader (fork of yetmorecode, Apache-2.0) | n/a | SHA-256 pinned (D-03), re-verified; it is third-party Java that runs inside the container. Mitigation: pinned hash, `orig/` read-only |
| openjdk-21-jdk-headless, clang-18 | Ubuntu noble archive | distro | n/a | Ubuntu | n/a | Version-pinned apt, like the existing Dockerfile packages |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** capstone (reason `unknown-downloads` only); the planner inserts `checkpoint:human-verify` before the `uv add`.

Note: `capstone.__version__` reports `5.0.7` for the 5.0.9 distribution. Check the pin with `importlib.metadata.version("capstone")`, never with `capstone.__version__`. `[VERIFIED: printed both this session]`

## Architecture Patterns

### System Architecture Diagram

```
orig/UFO2P.EXE, TACP.EXE (ro)                    third_party/watcom/<ver> (ro)
        |                                                   |
        v                                                   |
   le.py: load_flat(relocate=False), fixups()  <-- the only byte/fixup source (P4)
        |            |                  \
        |            |                   \--> Ghidra headless (container): LeLoader import
        |            |                         -> Java export: entries, bodies, names (build/ghidra/)
        |            v                                   |
        |     capstone recursive descent            ghidra adapter
        |            \______________________________/
        |                        v
        |        reconcile (D-07 evidence rule) --> config/<exe>/functions.csv, boundaries.csv
        |                        v
        |                 units draft --> config/<exe>/units.csv --> src/<exe>/<unit>.c (INCLUDE_ASM + C)
        |                                                                  |
        |                                configure.py --> build.ninja, objdiff.json, compile_commands.json
        |                                                                  |
        |                                         ninja: cc (wcc386 under wibo) --> build/<exe>/obj/<unit>.obj (OMF)
        |                                                                  |
        +--> target writer --> build/<exe>/target/<unit>.o      omf2elf --> build/<exe>/base/<unit>.o
        |                                   \______________________________/
        |                                                  v
        |                                    objdiff-cli diff/report  (score, view)
        |
        +--> relocation check (our OMF + LE; no ELF, no objdiff)  <-- authoritative
                                 | pass
                                 v
               patch builder (our bytes, original bytes at both-side reloc fields)
                                 v
               splice(le, {va: bytes}) --> build/<EXE> --> SHA-1 == config/targets.toml ?
                                 v
                  check prints: objdiff %, reloc verdict, splice SHA-1 (both EXEs in the gate)
```

### Recommended Project Structure

```
config/<exe>/functions.csv      # start,end,name,kind,unit,evidence (committed, addresses/names)
config/<exe>/boundaries.csv     # every Ghidra/capstone disagreement + verdict + reason
config/<exe>/units.csv          # unit ranges; every function in exactly one unit
include/common.h                # INCLUDE_ASM, s8/u8/... typedefs (C89)
include/watcom_compat.h         # clang-only shim (D-14)
src/ufo2p/<unit>.c, src/tacp/<unit>.c
tools/reverseapoc/
  elf.py          # ELF32 ET_REL writer (+ a tiny reader for tests)
  omf2elf.py      # Module -> ELF (base objects)
  target.py       # LE -> per-unit target ELF
  symbols.py      # ONE naming function: linker names <-> addresses (P8)
  discover.py     # capstone recursive descent (KKND find_functions shape)
  ghidra.py       # analyzeHeadless driver + adapter
  ghidra_scripts/ExportFunctions.java
  functions.py    # functions.csv / boundaries.csv / units.csv model + reconcile
  asm.py          # per-function listings into asm/
  relocs.py       # relocation check (OMF + LE)
  land.py         # patch builder for splice()
  check.py        # `reverseapoc check`
  lint.py         # clang gate
build/<exe>/{obj,base,target}/<unit>.{obj,o}; build/ghidra/<exe>/; build/logs/
asm/<exe>/func_XXXXXXXX.s (gitignored); asm/<exe>/ghidra/func_XXXXXXXX.c (gitignored drafts)
```

### Pattern 1: The objdiff spike on the `cmain386` pair (D-01/D-02)

**What:** the spike uses a runtime function whose C source is Watcom's own and which compiles byte-identical under the default rule.

Measured this session (counts only). The comparison masks our OMF fixup bytes and the LE fixup bytes:

| | UFO2P | TACP |
|---|---|---|
| runtime.csv row | `cmain386`, 0x000C5C9C..0x000C5CEB, `__CMain`, `DOS/CLIB3R.LIB`, versions `10.5;10.6`, unique | `cmain386` at 0x000C7915, same profile |
| Compile | `uv run reverseapoc cc third_party/watcom/10.6/SRC/STARTUP/386/CMAIN386.C -o build/.../cmain.obj` under the default `*  wcc386@10.6  -4r -s -fpi` (cflags.txt:37) | same object |
| Result | `_TEXT` 79 bytes = row length, 0 unmasked differing bytes; 4 self-relative + 5 segment-relative OMF fixups; 5 LE fixups in range | 79 = 79, 0 differing |
| Other flag sets | `-4r -s -ox` and `-5r -s -ox` also 0; every `-3r` set gives 77 bytes | — |
| Other versions | 10.5's own `CMAIN386.C`: 0 differing; 11.0's own: 93 bytes, 15 differing | — |

`[VERIFIED: compiled natively on the Windows host with reverseapoc cc this session; Watcom 10.6 banner "WATCOM C32 Optimizing Compiler Version 10.6"]`

Relocation targets of `__CMain`: OMF externs `__ASTACKSIZ`, `stackavail_`, `__ASTACKPTR`, `__CommonInit_`, `____Argv`, `____Argc`, `main_`, `exit_`. The LE side resolves them as follows (UFO2P):
- calls to 0xC9357, which is not a runtime.csv start (`stackavail_` sits inside a module);
- 0xC9360, the `__CommonInit_` row start;
- 0x10010, game code: `main_`;
- 0xC01E1, the `exit` module start + 1: `exit_`;
- data targets 0x13BBA4, 0x13BBA8, 0x249968, 0x24996C.

**Spike Given/When/Then (proposed, matching `.planning/spikes/CONVENTIONS.md`):**
- *Given* the `cmain386` rows of both EXEs, `SRC/STARTUP/386/CMAIN386.C` from the owner's 10.6 tree (read-only, never copied into the repo), objdiff-cli 3.8.2 in `reverseapoc-build`, a minimal `omf2elf` and a minimal target writer;
- *When* the object is compiled with `reverseapoc cc`, converted, and diffed against the target cut from `le.py` bytes (relocations rebuilt from LE fixups, PC32 synthesized for the 4 calls, an address-to-name map for the 8 linker names);
- *Then* objdiff loads both objects and reports `match_percent` 100.0 for `__CMain` under the default `functionRelocDiffs=name_address`. A planted wrong call target (or wrong 2nd relocation) is recorded (<100 / still 100). The KKND-style relocation check passes on the good pair and fails on both plants.
- Verdict rules per D-02. A name map that the target writer needs for non-placeholder names is a recorded workaround, so expect **PARTIAL or VALIDATED** depending on how the owner reads "relocations mapped" (Open Question 1).
- Output only `PASS/FAIL` lines with names, addresses, counts and SHA-1s.

### Pattern 2: Ghidra headless export (SPL-01, D-04..D-06)

Facts verified in throwaway `ubuntu:24.04@sha256:68ee2200...` containers this session:
- Extension install is non-interactive: unzip the loader zip into `<GhidraInstallDir>/Ghidra/Extensions/`, which gives `Ghidra/Extensions/ghidra-lx-loader/`. It is picked up at the next start. `[CITED: docs/GettingStarted.md in the 12.1.4 zip, "install ... directly into the Ghidra installation directory ... if a Ghidra installation is only ever used headlessly"]` `[VERIFIED: import used the loader]`
- Command that worked:
  `mkdir -p /tmp/proj && /opt/ghidra/support/analyzeHeadless /tmp/proj p_UFO2P -import /orig/UFO2P.EXE -loader LeLoader -postScript ExportFunctions.java <out> -scriptPath <dir> -deleteProject -max-cpu 4`
  - The project location must exist first: without it the run fails with `Directory not found: /tmp/proj` (exit 1).
  - `-loader` takes the class simple name (`LeLoader`); full package paths are no longer recognized. `[CITED: support/analyzeHeadlessREADME.md]`
  - Language and compiler were chosen automatically: `watcom:LE:32:default:watcom`. Pass `-processor watcom:LE:32:default -cspec watcom` explicitly so a loader update cannot change them.
- Results:

  | | UFO2P | TACP |
  |---|---|---|
  | Full analysis (root, `-max-cpu 4`) | 59 s | 56 s |
  | `-noanalysis` import as non-root user with a read-only install | 11 s | 11 s |
  | Functions | 1408 (25 with more than one body range) | 1498 (19) |
  | `.object1` | 0x00010000..0x000CFADC, size 785,117 | size 795,983 |
  | `.object2` | 0x000D0000, size 1,580,576 | 0x000E0000, size 2,486,448 |
  | `.image` overlay (whole file) | SHA-1 = `config/targets.toml` SHA-1 | same |

- The D-03 conflict is resolved. The loader's `checkFormat` uses `e_lfanew` only when the first MZ has `e_lfarlc == 0x40`; otherwise it walks "DOS/16 BW" headers from `(e_cp-1)*512 + e_cblp`. In both real EXEs `e_lfarlc != 0x40` and a `BW` header sits at 0xF474, so "DOS/16 LE" is the loader's name for BW-chain binding, which DOS/4GW Pro uses. `[VERIFIED: LeLoader.java source in the release zip + header booleans of the real files]`
- P4 cross-check: zero every relocation site from Ghidra's relocation table in both Ghidra's blocks and le.py's `load_flat(relocate=False)`, and the SHA-1s are equal for both objects of both EXEs. So Ghidra's bytes equal file bytes except at fixups. `[VERIFIED]`
- Ghidra's relocation table lists each page-straddling off32 field **twice**: type 7 count 28,197 = 28,183 + 14 (UFO2P) and 24,435 = 24,424 + 11 (TACP). Types 2 (sel16) x10 and 6 (ptr16:32) x4 in each. Never take fixups from Ghidra (P3). `[VERIFIED]`
- Script language: **Java GhidraScript** (compiled on the fly by the JDK). Jython is an uninstalled extension zip; PyGhidra needs JPype wheels the zip ships only up to cp313. `[VERIFIED]`
- `analyzeHeadless` has no `-version` flag; it prints usage. For the D-06 smoke test read `Ghidra/application.properties` (`application.version=12.1.4`) or check a synthetic-LE import. `[VERIFIED]`
- User settings go to `~/.config/ghidra/ghidra_12.1.4_PUBLIC`; the install can stay root-owned and read-only. `[VERIFIED: non-root run]`
- Heap: `analyzeHeadless` defaults `MAXMEM_DEFAULT=2G`, overridable by `GHIDRA_HEADLESS_MAXMEM`; 2G sufficed. `[VERIFIED: support/analyzeHeadless]`
- Sizes: the install unzipped is 882 MB, the JDK (`/usr/lib/jvm`) 286 MB. Largest Ghidra parts: `Features/FunctionID` 195 MB, `Features/Base` 176 MB, `docs` 104 MB, `Extensions` 100 MB, `Debug` 79 MB. `[VERIFIED]`

**Export format (recommendation):** one TSV/CSV per EXE in gitignored `build/ghidra/<exe>/functions.raw.csv` with `entry,body_min,body_max,addresses,ranges,thunk,calling_convention,name`. The adapter uses **only `entry`** as a start candidate and computes ends by the D-07 rule, because Ghidra bodies are address sets (multi-range for 25 / 19 functions), not contiguous ranges. Names other than `FUN_*` (e.g. `_entry`) are hints. Draft decompiles, if exported, go to `asm/<exe>/ghidra/` (gitignored).

**Synthetic-LE smoke test pitfall:** `tests/conftest.py` builds the bound variant with a 0xCC-filled outer MZ (`e_lfarlc` = 0xCCCC, no BW chain), and the unbound variant's MZ has `e_lfarlc` = 0x9090. The loader rejects both. A Ghidra-loadable fixture needs `e_lfarlc = 0x40` with `e_lfanew` -> LE, or a real BW chain. `[VERIFIED by reading conftest.py and LeLoader.java; not run against Ghidra]`

### Pattern 3: Discovery and reconciliation (SPL-02, D-07, D-08)

- Raw bytes: in both EXEs every off32 field in the file holds the **object-relative offset** (`target_off`), never the linear address: 28,183 / 28,183 in UFO2P, 24,424 / 24,424 in TACP. Decoding `load_flat(relocate=False)` therefore yields object offsets in `disp`/`imm` operands. Every operand that overlaps a fixup field must be resolved through `le.fixups()` (`target_va`), e.g. a jump table's address. `[VERIFIED]`
- Fixup source/target objects (UFO2P / TACP): obj1->obj2 25,368 / 21,962; obj1->obj1 1,998 / 1,885 (function pointers, jump tables); obj2->obj2 690 / 482; obj2->obj1 127 / 95 (function-pointer tables in data). No rel32 fixups at all, so every `call rel32` inside obj1 is resolved at link time and has **no LE fixup**. `[VERIFIED]`
- Naive estimate (a throwaway KKND-shaped recursive descent without gap fill, against the Ghidra export; counts are MEDIUM):

  | | UFO2P | TACP |
  |---|---|---|
  | capstone starts | 1,880 | 1,837 |
  | Ghidra starts | 1,407 | 1,497 |
  | both | 1,392 | 1,479 |
  | capstone-only | 488 | 358 |
  | Ghidra-only | 15 | 18 |
  | decoded bytes | 693,162 / 785,117 | 688,933 / 795,983 |
  | jump-table bytes found | 4,588 | 4,220 |
  | distinct `call rel32` targets | 1,430 (Ghidra has 1,384) | 1,506 (Ghidra has 1,471) |
  | runtime.csv starts found by capstone / Ghidra | 101 / 74 of 121 | 105 / 84 of 132 |

  Expect hundreds of `boundaries.csv` rows unless the reconcile rule auto-classifies the common cases. Most capstone-only starts come from treating every code-pointing instruction fixup as a function start. Ghidra misses about 40 call targets per EXE. Plan the reconcile step to emit `rule` verdicts automatically wherever the D-07 evidence decides, so a human reason is needed only for the rest.
- `runtime.csv` has **no per-public offsets**: `exit_` is module start + 1, and `stackavail_` is not a module start. Seeding `functions.csv` from runtime rows (04 D-06) therefore needs the PUBDEF offsets of each matched module (from the LIB386 module via `libmatch`/`omf.py`), or a call target will look like an unknown start. `[VERIFIED: cmain386 call targets]`
- Padding/filler between functions: TH treats `nop`, `mov eax,eax` (both encodings) and `lea eax,[eax+0]` as filler after a terminal instruction; KKND adds zero bytes. In our 10.6 probe, functions sat back to back and 2 bytes of padding aligned a jump table to 4. `[CITED: TH tools/omf2elf.py PADDING, tools/x86scan.py; VERIFIED: probe object]`
- **Leading jump tables:** Watcom places a switch table *before* the function entry in the same segment. The probe's `jmp [reg*4+table]` fixup is segment-relative to `_TEXT`, and the table precedes the entry. The bytes between the previous function's last instruction and the next entry may therefore be the *next* function's table: classify them as `data-in-code` rows, never as the previous function's tail (TH `leading_table`, KKND "the checked region starts at the previous public"). `[VERIFIED: probe; CITED: TH/KKND]`

### Pattern 4: Units and the INCLUDE_ASM stub (SPL-03, SPL-04, D-11, D-12)

- `#define INCLUDE_ASM(name) extern int INCLUDE_ASM_##name` (KKND's macro has a dir argument; D-12 uses one argument). Under wcc386 10.6 a file of such lines plus one real function produced externs `('_D_000D1234',)` only and `_TEXT` 6 bytes: **no EXTDEF and no bytes for the markers**. `[VERIFIED: probe compile]`
- Watcom emits functions out of source order and lets a function fall through into the next. In a non-`-zm` probe, a static helper landed at offset 0, a 5-byte function fell through into the function after it, and the publics came in the order helper, 3rd, 2nd, 4th, 5th. Units are therefore **address ranges**; the order of functions inside `src/<exe>/<unit>.c` does not have to follow addresses, and a function that falls through has no `ret`. `[VERIFIED: probe]`
- Watcom gives every call a self-relative fixup, even to a `static` function in the same segment (LPUBDEF + LEXTDEF `helper_`). Intra-unit calls are therefore visible as relocations on our side. `[VERIFIED]`
- With `-zm`, each function becomes its own SEGDEF named `_TEXT`, in reverse source order, with the switch table at the start of the function's own segment. `[VERIFIED]`
- configure.py "neither defined nor marked" check: a regex over `src/` for `INCLUDE_ASM(func_X);` and for function definitions, like KKND's `build_kknd.py` detection. The `check` tool later confirms definitions from the compiled publics.
- **Compiler include path gap:** the wrapper passes one `-i=` with the version's `H` dir only (`build_argv`, compiler.py:332-341; `include = guest_path(watcom_dir / rule.version / "H", root, inside=False)`, compiler.py:525), and `-i` is wrapper-owned (cflags cannot add it). `#include "common.h"` from `src/ufo2p/x.c` would not find `include/`. Watcom 10.6 accepts a `;`-separated list: `-i=build\...\inc;third_party\watcom\10.6\H` found both a project header and `<stddef.h>` (rc 0). Extend the wrapper to `-i=include;<tree>\H`, with a test that no Open Watcom path leaks in (P6). `[VERIFIED: native 10.6 compile this session]`

### Pattern 5: Target ELF writer (SPL-08, D-13)

Rules (TH `split.py` semantics, emitted directly as ELF):
1. ELF32 LSB, `ET_REL`, `EM_386`; sections `null, _TEXT..., .rel_TEXT..., .symtab, .strtab, .shstrtab`; `sh_link` of each `.rel` = symtab index, `sh_info` = the section it relocates; symtab `sh_info` = first non-local index. This exact shape loaded in objdiff 3.8.2. `[VERIFIED: probe]`
2. **Section name `_TEXT`**, the same name omf2elf gives Watcom's code segments. objdiff pairs a symbol only if the name, section kind and section base name all match (`find_symbol` in diff/mod.rs). A probe with `.text` on one side was left unpaired (no `match_percent`). `[VERIFIED]`
3. **One `_TEXT` section per function** (TH's `-zm` mirror). A two-section target (two functions) paired at 100% with a one-section base. `[VERIFIED: probe]`
4. Symbols: per function a GLOBAL `STT_FUNC` with explicit `st_size` = `end - start` from functions.csv (padding excluded). Referenced externals are GLOBAL `STT_NOTYPE` with `shndx` 0.
5. Bytes: `load_flat(relocate=False)[start:end]` (P4). **Every relocated field is rewritten to its REL addend**, because the file holds `target_off` there and objdiff reads the addend from the field.
6. Every LE fixup with `src_va` in range becomes `R_386_32`:
   - target in obj1 at a function start: that function's symbol, addend 0;
   - target inside a function: the containing function's symbol + delta (TH `code_ref`);
   - target in obj2: `_D_<target>` (or a mapped name), addend 0.
   - Use `le.fixups()` once: a straddler is one field, one relocation (P3).
7. Synthesize `R_386_PC32` (addend -4, written into the field) for every decoded `call rel32` and for `jmp`/`jcc rel32` leaving the function, against the destination's symbol. Skip LE fixup sites while decoding: a fixup at an instruction start is data (TH `x86scan`; objdiff does the same, x86.rs "If the instruction starts at a relocation, it's inline data").
8. Names come from **one** function in `symbols.py`, which the reloc check, the asm writer and the scorer share. Linker names follow Watcom's register convention: function `func_XXXXXXXX` -> `func_XXXXXXXX_`, data `D_XXXXXXXX` -> `_D_XXXXXXXX`, verified from the probe externs `('func_00012345_', 'helper_', '_D_000D1234', '_D_000D2000')`. Runtime rows use their Watcom public verbatim (e.g. `strncpy_`). Non-placeholder names (`main_`, `____Argv`) need an address-to-name map (Open Question 1).
9. objdiff relocation equality for an *undefined* symbol is name + addend only (`reloc_eq` -> `(None, None) => symbol_name_addend_matches`). So C that writes `D_000D2000[2]` (symbol `_D_000D2000`, addend 8) will **not** objdiff-match a target that names `_D_000D2008` + 0, though the bytes and the reloc check agree. First matches should declare one extern per referenced address. `[VERIFIED: objdiff v3.8.2 code.rs + probe stored addend 8]`

### Pattern 6: omf2elf (SPL-07)

Watcom 10.6 object shape, from probes of our own synthetic C under the default rule:
- Records: `THEADR, COMENT x4, LNAMES, SEGDEF32 x5, GRPDEF x2, LPUBDEF32, EXTDEF, LEXTDEF, LEDATA32, FIXUPP32, PUBDEF32, ..., MODEND`. `model 3fOp`, default libraries `('math387r', 'emu387')`, **Easy OMF** (COMENT 0xAA) set.
- Segments: `_TEXT CODE`, `CONST DATA`, `CONST2 DATA`, `_DATA DATA`, `_BSS BSS`.
- Every fixup is location 9 (offset32) with frame method 1 (group FLAT). Externals use target method 6, segments method 4; there is no displacement (0 in every case), and the addend lives in the field bytes (e.g. `stored 8` for `D_000D2000[2]`).
- Self-relative fields store 0; ELF PC32 addend = `stored + disp - 4` = -4 (TH rule, which paired at 100%).
- String literals give a segment-relative fixup to `CONST`; switch tables a segment-relative fixup to own `_TEXT`.
- No COMDAT appeared in C objects, with or without `-zm`.

`[VERIFIED: omf.read_object on probe objects]`

Conversion rules (TH `omf2elf.convert`/`write_elf`, GPLv3, on top of our `omf.Module`, which already applies BAKPAT, expands LIDATA and tracks FIXUPP threads and CEXTDEF):
- one ELF section per SEGDEF and per COMDAT; debug classes dropped;
- `R_386_PC32` if `segment_relative` is false, else `R_386_32`, rewriting the field to `stored + displacement - (4 if self-relative else 0)`;
- extern target -> undefined symbol named as in OMF; segment target -> that section's `STT_SECTION` symbol;
- publics in code -> `STT_FUNC`, sized to the next public in the same section, with trailing Watcom filler trimmed after a terminal instruction (TH `sized`); `LPUBDEF` -> LOCAL;
- COMDAT with a selection criterion -> WEAK.
- Still missing in `omf.py` (CONTEXT): 16-bit COMDAT 0xC2 (TH handles both via `kind = rtype & ~1`) and applying NBKPAT. TH also maps location 5 to 32-bit under Easy OMF ("the assembler's objects"). wcc386 emitted location 9 in every probe, so this matters only if a library module is ever converted. `[CITED: TH tools/omf2elf.py at 7993814a]`
- Refuse (clear error) what Phase 5 does not need: iterated COMDAT, fixups to LIDATA (`unmaskable`), frame-number targets, pointer/selector locations.

### Pattern 7: Relocation check (SPL-09), OMF + LE only

Inputs: our `omf.Module`, the function's public and segment range `[off, off+size)`, its row `[start, end)`, `le.fixups()`, and `load_flat(relocate=False)`. All checks are in flat VA space:
1. **Length:** `size == end - start` (KKND "equal length").
2. **Fields:** `ours` = VAs covered by our OMF fixups (mapped `start + (fx.offset - off)`); `theirs` = VAs of LE fixup fields in range.
3. **Bytes:** every byte outside `ours U theirs` is equal.
4. **Each of our fixups resolves to the original target** (KKND `build_kknd.py`):
   - self-relative -> want = `addr(symbol) + stored + displacement`; have = `F + 4 + int32(original[F:F+4])`; require no LE fixup at `F`;
   - segment-relative to extern -> an LE fixup at `F` with `kind == SRC_OFF32` and `target_va == addr(symbol) + stored + displacement`;
   - segment-relative to own `_TEXT` -> `start - off + stored` (jump table/case label);
   - to `CONST`/`_DATA`/`_BSS` -> FAIL "local segment reference, move data to an extern D_ symbol".
5. **Reverse coverage** (TH `elfrelocs` compares both lists): every LE fixup field in range must be one of ours, or our code has a constant where the original had a relocated address. The raw field holds `target_off`, so a literal equal to it would otherwise pass the byte compare.
6. `addr(name)` comes from `symbols.py`: parse `func_XXXXXXXX_` / `_D_XXXXXXXX`, look up runtime publics in functions.csv, and FAIL "unknown symbol" for anything else.

Straddlers: a single `Fixup` per field from `le.fixups()`, checked by VA. Splice masks both halves (`MaskedField.straddles_page`). The P3 test is a synthetic LE whose function contains a straddling off32 field: the check passes, and the splice masks 4 bytes across the page boundary.

### Pattern 8: Land + splice (SPL-10)

`splice(le, patches)` writes patch bytes except at **LE fixup fields**, which keep their original values (`MaskedField`, splice.py:446-465; `splice`, splice.py:527-554). Our self-relative call fields are **not** LE fixups (0 rel32 fixups in both EXEs), so splicing our raw object bytes would write our placeholder displacement (0 / -4) and break the SHA-1. The patch builder therefore copies our function bytes and overwrites every field in `ours U theirs` with the original bytes, only **after** check 4 passed: KKND's "our bytes everywhere except under a relocation on either side". Then `splice(le, {start: patch})` and compare the SHA-1 with `load_manifest()`. The gate splices all matched functions of both EXEs (zero regressions, P11).

### Pattern 9: asm listings (SPL-05)

KKND `split.py` shape (CC0): one Intel-syntax listing per function with symbolic operands, via the same `symbols.py`. Fixup operands are resolved through `le.fixups()`, not decoded immediates (raw fields hold object offsets). Output goes to `asm/<exe>/func_XXXXXXXX.s`, gitignored. A reading aid only; never assembled. Tests check names and structure on a synthetic LE, never real output.

### Pattern 10: configure.py edges (SPL-06)

Keep the existing `check_orig`, `parse_le`, `rebuild` rules (configure.py:35-48) and add:
- `rule configure` (`generator = 1`), regenerating when `config/<exe>/*.csv` or the `src/` file list changes;
- `rule cc`: `uv run reverseapoc cc $in -o $out` -> `build/<exe>/obj/<unit>.obj`, implicit deps `config/cflags.txt`, `config/watcom.toml`, `include/*.h`;
- `rule omf2elf` -> `build/<exe>/base/<unit>.o`;
- `rule target` -> `build/<exe>/target/<unit>.o`, implicit deps `orig/<EXE>`, `functions.csv`, `units.csv`;
- `rule lint` (stamp);
- `rule asm` (stamp; writes `asm/`);
- `verify` extended to land every matched function before the SHA-1;
- optional `report`: `objdiff-cli report generate -o build/report.json`.

Do not quote `$in`/`$out` (learnings 2026-10-20), and route every path through `ninja_path()`. Restrict unit names to `[a-z0-9_]`, so they never need ninja or Watcom escaping (`_SAFE_PATH = [A-Za-z0-9._/-]`).

`objdiff.json` (schema `https://raw.githubusercontent.com/encounter/objdiff/main/config.schema.json`, read at tag v3.8.2):
```json
{"$schema": "https://raw.githubusercontent.com/encounter/objdiff/main/config.schema.json",
 "min_version": "3.8.2", "custom_make": "ninja", "build_target": false, "build_base": true,
 "watch_patterns": ["*.c", "*.h"],
 "progress_categories": [{"id": "ufo2p", "name": "UFO2P.EXE"}, {"id": "tacp", "name": "TACP.EXE"}],
 "units": [{"name": "ufo2p/<unit>", "target_path": "build/ufo2p/target/<unit>.o",
            "base_path": "build/ufo2p/base/<unit>.o",
            "metadata": {"source_path": "src/ufo2p/<unit>.c", "progress_categories": ["ufo2p"]}}]}
```
`base_path` may be omitted for a unit with no C yet ("Omit if there is no source object yet"). `symbol_mappings` (target name -> base name) and per-unit `options` exist if needed. `[VERIFIED: config.schema.json v3.8.2]`

`compile_commands.json` (clang JSON compilation database): `[{"directory": "<abs repo root>", "file": "<abs src>", "arguments": ["clang", "-std=gnu89", "--target=i386-unknown-none", "-ffreestanding", "-nostdinc", "-funsigned-char", "-D__386__", "-D__FLAT__", "-D__WATCOMC__=1060", "-Iinclude", "-include", "include/watcom_compat.h", "-c", "src/ufo2p/<unit>.c"]}]`. It is written per environment and gitignored (paths differ between host and container). `[CITED: TH configure.py compile_commands(); ASSUMED: field set per the clang JSONCompilationDatabase spec]`

### Pattern 11: `reverseapoc check <exe>/<unit>` (SPL-11)

Flow: compile -> omf2elf -> target -> objdiff per defined function -> reloc check -> land + splice -> SHA-1.

Two objdiff modes, both verified on synthetic objects:
- per symbol: `objdiff-cli diff -1 <target.o> -2 <base.o> -o - <symbol>` prints JSON with top-level `left`/`right`, each with `sections` and `symbols`. A symbol's `match_percent` is a float and `size` a string. A target-only symbol has no `match_percent`.
- per project: `objdiff-cli report generate -p <dir> -o report.json -f json` prints `units[].functions[]` with `name`, `size`, `fuzzy_match_percent` (absent when 0 or unpaired; default it to 0.0) and `address`, plus `measures`.

objdiff-cli, ninja and clang exist **only in the container** (host check this session: none on PATH), so `check` runs via `docker compose run --rm build uv run reverseapoc check ufo2p/<unit>`. On the host it should fail early with a clear message.

Proposed `--json`:
```json
{"exe":"ufo2p","unit":"<unit>","compiler":"wcc386@10.6","flags":["-4r","-s","-fpi"],
 "functions":[{"name":"func_000XXXXX","va":"0x000XXXXX","size":N,"objdiff_percent":100.0,
   "reloc":{"ok":true,"problems":[]},"bytes":{"ok":true,"differing":0,"first_va":null}}],
 "splice":{"sha1":"...","expected":"...","ok":true},"ok":true}
```
Exit codes: 0 every defined function matched and SHA-1 ok; 1 any mismatch; 2 tool or usage error (compile failure, objdiff missing, unknown unit).

### Pattern 12: Lint gate (SPL-12, D-14)

Verified with clang 18.1.3. A draft `include/watcom_compat.h` (guarded by `#ifdef __clang__`; `#pragma clang diagnostic ignored "-Wunknown-pragmas"`; empty `__far __near __huge __interrupt __loadds __saveregs __export __pascal __fortran __syscall __watcall __cdecl _far _near _cdecl`) plus
`clang-18 -fsyntax-only -std=gnu89 -Werror=declaration-after-statement --target=i386-unknown-none -ffreestanding -nostdinc -funsigned-char -D__386__ -D__FLAT__ -D__WATCOMC__=1060 -Iinclude -include include/watcom_compat.h <file>`
**passed** a file with `int __watcall f(int);`, `#pragma aux f parm [eax] value [eax] modify [ecx edx];`, `void __far __interrupt g(void);`, `INCLUDE_ASM(...)` and `#if __WATCOMC__ != 1060 #error`. It **failed** a mixed declaration with `error: mixing declarations and code is a C99 extension [-Werror,-Wdeclaration-after-statement]` (rc 1).
- `#pragma aux` cannot be redefined as a macro; making it a no-op means suppressing the unknown-pragma warning, as above.
- Do not guard the header on `!defined(__WATCOMC__)`, because the lint command defines `__WATCOMC__`.
- `-nostdinc` keeps the gate independent of Watcom's `H` dir (user-supplied, absent in CI). First-match units should therefore include only project headers. `-funsigned-char` matches Watcom's unsigned `char` default (toolchain.md "Char signedness").
- `--target=i386-unknown-none` gives 32-bit `long`/pointers.
`[VERIFIED: container run]`

### Pattern 13: First-match selection and sweep (SPL-13, D-15..D-18)

P16 funnel over the union of starts. A throwaway estimate in which "no jump table" means no fixup into obj1 inside the function and a "string" is a data target of at least 3 printable bytes then NUL; MEDIUM:

| Step | UFO2P | TACP |
|---|---|---|
| total | 1,895 | 1,855 |
| game (outside runtime.csv) | 1,522 | 1,501 |
| no code fixup | 1,266 | 1,274 |
| no straddler | 1,258 | 1,269 |
| >= 1 call rel32 | 756 | 842 |
| >= 1 off32 to obj2 | 696 | 784 |
| no string target | **565** | **683** |
| survivors <= 64 bytes; median span | 61; 320 | 74; 276 |

Add two filters the funnel lacks:
- every call target is a functions.csv start whose linker name `symbols.py` can produce (no `main_`-style or mid-module runtime target);
- every data target is referenced at an exact address (one `D_` extern each).

Prefer candidates without a `__CHK` prologue, so the default `-s` applies. The scorer: KKND `score_functions.py` weights (size + 12 per call + penalties for `cs:` tables, FPU, `D_` references, `ret N`, no `push ebp` frame).

The D-17 matrix is 3 versions x 2 CPU x 5 optimisation = **30 cells** (60 with the `-s` toggle). At ~43-88 ms per compile under wibo (spike 004) plus `uv run` start-up, a candidate sweep takes well under a few minutes. Log one line per cell under `build/logs/`.

### Anti-Patterns to Avoid

- **Bytes from Ghidra or `relocate=True`:** P4; Ghidra matches the file only off fixups.
- **objdiff 100% as the match:** verified blind to the 2nd relocation of an instruction.
- **Splicing raw object bytes:** our call fields are not LE fixups.
- **Re-reading per-page fixups or Ghidra's relocation table:** straddlers appear twice there.
- **A second naming function:** objdiff pairs by exact name; one `symbols.py`.
- **Trusting `capstone.__version__`:** it reports 5.0.7 for 5.0.9.
- **Committing Ghidra drafts or asm:** gitignored `asm/` only.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| OMF parsing | a new reader | `tools/reverseapoc/omf.py` (+0xC2, NBKPAT) | Already handles threads, LIDATA, BAKPAT, CEXTDEF, COMDAT32, Easy OMF |
| LE bytes and fixups | Ghidra export, per-page parsing | `le.py` `load_flat(relocate=False)`, `fixups()` | Single deduplicated source (P3/P4) |
| Splice/SHA-1 | a new writer | `splice.py` `splice`, `rebuild_target` | Proven round trip, masking, refusals |
| x86 decoding | an opcode table | capstone 5.0.9 (`detail=True`, `imm_offset`/`disp_offset`) | Locked D-09; verified operand access |
| LE loading in Ghidra | another loader | lastonesky v12.1.4-1 only | One loader per install |
| objdiff JSON | text scraping | `--format json` / `report generate -f json` | Stable fields verified |
| Compiler invocation | ad-hoc wibo calls | `reverseapoc cc` | Hash gate, env scrub, path rules |
| Field-addend semantics | guessing | TH omf2elf rule `stored + disp - 4` | Verified at 100% on a real Watcom object |

**Key insight:** every hard part (OMF, LE, splice, compiler invocation) already exists and is tested. Phase 5 is glue plus two new writers (ELF base, ELF target) and one new oracle (reloc check). The risk is in naming and field semantics, which this research pinned down empirically.

## Reuse and lift plan (licenses, derivation headers)

| Source | File | What it does | Lift into | License / header |
|---|---|---|---|---|
| TH (`matteo-pacini/theme-hospital-decomp` @ `7993814a4f562a1898b20621dbfa60644f9697d7`) | `tools/omf2elf.py` (589 lines) | OMF -> ELF32 (convert/write_elf, filler trimming, COMDAT weak) | `omf2elf.py` + `elf.py` (on `omf.Module`) | GPLv3-or-later; header `# Derived from Theme Hospital decomp tools/omf2elf.py (GPLv3), https://github.com/matteo-pacini/theme-hospital-decomp` |
| TH | `tools/split.py` (295) | target objects: one `_TEXT` per function, R_386_32 from fixups, PC32 for leaving branches, leading tables | `target.py` (emit ELF directly, no `as`) | GPLv3; same header form |
| TH | `tools/x86scan.py` (129) | fixup sites as data, filler detection, `trimmed_end`, `leading_table` | `discover.py` helpers | GPLv3 |
| TH | `tools/elfrelocs.py` + `verify.py` (93 + 38) | per-function relocation lists from ELF; flags 100% with differing relocations | optional ELF-side cross-check in `check` | GPLv3 |
| TH | `tools/check.py` (94) | one-unit build in a temp dir, objdiff JSON per function | `check.py` | GPLv3 |
| TH | `configure.py` (177) | build.ninja + objdiff.json + compile_commands.json, CLANG_FLAGS | extend our `configure.py` | GPLv3 |
| TH | `tools/clangd/compat.h` (27) | empty Watcom keywords for clang | `include/watcom_compat.h` (ours adds `__watcall`, `__cdecl`, the pragma suppression; drop TH's `#pragma pack(1)`, since our `-zp` is unknown) | GPLv3 |
| KKND (`Wyrelade/KKND-Decomp` @ `4dfd5b100755421bac28ab9dab452b1db7a9c81f`, CC0) | `tools/find_functions.py` (193) | capstone recursive descent: seeds, switch tables via fixups, gap prologues, padding trim | `discover.py` | CC0; header `# Derived from KKND-Decomp tools/find_functions.py (CC0 1.0), https://github.com/Wyrelade/KKND-Decomp` (as `le.py` does) |
| KKND | `tools/build_kknd.py` (203) | reloc-target verification, local-segment refusal, leading-table handling, keep-original splice | `relocs.py` + `land.py` | CC0 |
| KKND | `tools/gen_units.py` (85) | units from `__FILE__` strings, `--write-src` INCLUDE_ASM scaffolding | `functions.py` units draft | CC0 |
| KKND | `tools/score_functions.py` (71) | easiest-first score | scorer (Phase 5 minimal) | CC0 |
| KKND | `tools/land.py` (42) | replace INCLUDE_ASM with matched C | optional helper | CC0 |
| KKND | `tools/split.py` (129) | per-function Intel listings with symbols | `asm.py` | CC0 |
| KKND | `tools/lib_match.py` | masked library matching | already lifted as `libmatch.py` | — |

`docs/research/notes-own-pipeline-reuse-inventory.md` agrees: TH `omf2elf`/`elfrelocs`/`verify`/`x86scan` "nearly as-is"; KKND discovery/scaffold "adapt"; KKND `omf.py` lacks COMDAT/writer (ours supersedes it). One correction to that note: it suggested `ghidra2functions` over retrokit; D-03 dropped retrokit, so the adapter reads our own Java export instead.

## Runtime State Inventory

Not a rename/refactor phase. The only "rename" is the docs correction of "Ghidra in WSL2" to "Ghidra in the Docker image" (`docs/workflow.md:91`, `docs/toolchain.md:229`, design spec lines 49/88). No stored data, live service config, OS registration, secrets or build artifact carries that string. Verified by reading CONTEXT and the cited lines' context; the old WSL2 plan was never installed.

## Common Pitfalls

### Pitfall 1: Raw off32 fields hold object offsets
**What goes wrong:** decoding `relocate=False` bytes gives wrong addresses for every absolute operand, e.g. jump tables.
**Why:** wlink stored `target_off` in every field (100% of 52,607 fields across both EXEs).
**How to avoid:** resolve operands through `le.fixups()`; the target writer rewrites every field to its addend.
**Warning signs:** jump-table walks that read garbage; asm listings with tiny absolute addresses.

### Pitfall 2: Splicing call fields from our object
**What goes wrong:** the SHA-1 fails although the reloc check passed.
**Why:** `splice()` masks LE fixups only, and call rel32 fields have none.
**How to avoid:** the patch builder copies the original bytes at `ours U theirs` fields after the target check.
**Warning signs:** the SHA-1 mismatch's first differing offset is one of our call fields.

### Pitfall 3: Names that differ by convention
**What goes wrong:** objdiff leaves functions unpaired or shows relocation diffs.
**Why:** `func_X` vs `func_X_`, `D_X` vs `_D_X`, `.text` vs `_TEXT`, `_D_base+8` vs `_D_addr`.
**How to avoid:** one `symbols.py`; section name `_TEXT`; one extern per referenced address in first matches.
**Warning signs:** no `match_percent` for a defined function.

### Pitfall 4: objdiff 100% with a wrong 2nd relocation
**What goes wrong:** a false match.
**How to avoid:** the reloc check is the gate; keep the negative test that plants exactly this (verified 100%).

### Pitfall 5: Ghidra smoke test with the existing synthetic LE
**What goes wrong:** the D-06 smoke import fails, which looks like a Docker problem.
**Why:** the loader needs `e_lfarlc == 0x40` or a BW chain.
**How to avoid:** a Ghidra-compatible fixture variant, or a version check through `application.properties`.

### Pitfall 6: `analyzeHeadless` without an existing project dir, or with `-version`
**What goes wrong:** exit 1 with `Directory not found`; `-version` just prints usage.
**How to avoid:** `mkdir -p` a temp project dir; `-deleteProject`.

### Pitfall 7: Image size surprise
**What goes wrong:** +1.17 GB, not +800 MB. Docker Desktop disk and build time grow; the Ghidra zip download is ~570 MB.
**How to avoid:** a separate cached fetch stage for Ghidra so objdiff/OW changes do not refetch it. Optional slimming (delete `docs/`, `Extensions/`) only with a smoke test `[ASSUMED safe]`.

### Pitfall 8: runtime publics are not module starts
**What goes wrong:** call targets such as `exit_` (module + 1) look like unknown starts and fail the reloc check's name lookup.
**How to avoid:** seed functions.csv with per-public offsets from the LIB386 modules.

### Pitfall 9: The wrapper cannot see `include/`
**What goes wrong:** the first `#include "common.h"` fails to compile.
**How to avoid:** extend `-i` to `include;<H>` (verified syntax); keep the "no OW path" test.

### Pitfall 10: Leading jump tables and fall-through
**What goes wrong:** boundary errors break the equal-length rule.
**How to avoid:** classify tables as `data-in-code`; first matches exclude tables (D-15); fall-through functions have no `ret`, so do not require one.

### Pitfall 11: Host vs container tools
**What goes wrong:** `check`/`lint`/`ninja` "work" only half on the host.
**How to avoid:** container-first verbs that fail early on the host with a message; never run host and container suites at once (CONTEXT).

## Code Examples

### Verified objdiff probe shape (synthetic bytes)
```python
# Source: this session's probe (scratchpad mkelf.py); bytes are made up.
# mov eax,[abs32]; call rel32; mov dword [abs32], imm32; ret
CODE = bytes.fromhex("a100000000" "e800000000" "c70500000000" "00000000" "c3")
GOOD = [(1, R_386_32, "_D_000D0000", 0), (6, R_386_PC32, "func_00012345_", -4),
        (12, R_386_32, "_D_000D0010", 0), (16, R_386_32, "_D_000D0020", 0)]
# objdiff-cli diff -1 target.o -2 base.o -o - func_00010000_  ->
#   identical: 100.0 | wrong call symbol: 98.75 | wrong addend at 12: 98.75
#   wrong symbol only at 16 (2nd reloc of one instruction): 100.0   <- needs the reloc check
#   section named .text on one side: unpaired (no match_percent)
```

### omf2elf addend rule
```python
# Source: TH tools/omf2elf.py convert() (GPLv3), applied to omf.OMFFixup
stored = struct.unpack_from("<i", data, fx.offset)[0]
relative = not fx.segment_relative
struct.pack_into("<i", data, fx.offset, stored + fx.displacement - (4 if relative else 0))
rtype = R_386_PC32 if relative else R_386_32
```

### Relocation check core (sketch)
```python
# Source: KKND tools/build_kknd.py rules (CC0), adapted to omf.Module + le.Fixup
for fx in segment.fixups:
    if not off <= fx.offset < off + size:
        continue
    field = start + fx.offset - off
    stored = struct.unpack_from("<i", segment.data, fx.offset)[0]
    want = symbols.address_of(fx.target_name, functions) + stored + fx.displacement
    if not fx.segment_relative:
        have = field + 4 + struct.unpack_from("<i", original, field)[0]
        ok = have == want and field not in le_fixups_by_va
    else:
        lf = le_fixups_by_va.get(field)
        ok = lf is not None and lf.kind == SRC_OFF32 and lf.target_va == want
# plus: every LE fixup in [start, end) is one of ours (reverse coverage)
```

### Ghidra export script skeleton (Java)
```java
// Source: this session's ProbeExport.java (ran under 12.1.4); prints/writes addresses and names only
public class ExportFunctions extends GhidraScript {
  @Override protected void run() throws Exception {
    try (PrintWriter w = new PrintWriter(new File(getScriptArgs()[0]))) {
      for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
        int ranges = 0; for (AddressRange r : f.getBody()) ranges++;
        w.println(f.getEntryPoint() + "," + f.getBody().getMinAddress() + "," + f.getBody().getMaxAddress()
          + "," + f.getBody().getNumAddresses() + "," + ranges + "," + f.isThunk() + ","
          + f.getCallingConventionName() + "," + f.getName());
      }
    }
  }
}
```

## State of the Art

| Old approach | Current approach | When changed | Impact |
|---|---|---|---|
| Ghidra in WSL2 (design spec) | Ghidra + JDK in the Docker image | owner, 2026-10-23 (D-04) | No host install; image +1.17 GB |
| Jython GhidraScripts | Java scripts or PyGhidra; Jython is an optional extension | Ghidra 12.x (zip ships `..._Jython.zip`) | Use Java |
| yetmorecode loader 12.0.1 | lastonesky v12.1.4-1 | Ghidra 12.1 Loader API change | Pinned |
| TH `split.py` -> GNU `as` | Python emits ELF directly | D-13 | No binutils step |

**Deprecated/outdated:** `docs/toolchain.md` "Ghidra ... Neither has been tested on UFO2P or TACP. Decided in Phase 5" is now answered (lastonesky loads both); STACK.md "Keep it in WSL2" is superseded by D-04.

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | `compile_commands.json` field set (`directory`, `file`, `arguments`) is what clangd 18 reads | Pattern 10 | clangd ignores the file; editor-only impact |
| A2 | Deleting `docs/` and `Extensions/` from the Ghidra install is safe | Pitfall 7 | Ghidra fails at start; keep it optional and smoke-tested |
| A3 | `uv run` start-up is small relative to compile time per ninja edge | Pattern 13 | Slower builds; could switch edges to `python -m` inside the venv |
| A4 | Multiple same-named `_TEXT` sections on the target side keep pairing for many functions (verified for 2) | Pattern 5 | Pairing gaps in larger units; fall back to one section per unit |
| A5 | The KKND score weights transfer to Watcom 10.6 game code | Pattern 13 | A poorer first pick; the 3-candidate cap bounds it |
| A6 | The GitHub `ubuntu-latest` CI runner has a clang that can run the lint test | Validation | The lint test skips in CI; the container still gates it |

## Open Questions

1. **Does a target-side address-to-name map count as "relocations mapped" (D-02)?**
   - What we know: `__CMain`'s relocations name `main_`, `exit_`, `stackavail_`, `__CommonInit_` and four runtime data symbols. objdiff pairs undefined-symbol relocations by exact name + addend.
   - What's unclear: whether the owner reads a spike-local name map as a workaround (PARTIAL) or as normal mapping (VALIDATED).
   - Recommendation: record it as the one workaround in the spike README. Make the general mechanism an optional `config/<exe>/symbols.csv` (address,name,kind; addresses and names only), needed by first game matches only if they call non-placeholder targets, which the filter avoids.
2. **Is reading `SRC/STARTUP/386/CMAIN386.C` from the user's tree acceptable for the spike?** It is never copied into the repo; the spike script points `reverseapoc cc` at `third_party/watcom/10.6/...` (inside the repo root, gitignored, read-only mount in the container). Recommendation: yes; it literally satisfies D-01 step 2.
3. **Image size +1.17 GB vs D-04's ~800 MB.** Recommendation: accept, with a separate cached stage; flag to the owner at the first Ghidra task's checkpoint.
4. **Per-public offsets for runtime rows:** regenerate from LIB386 at functions.csv seeding (needs the Watcom trees, like `libmatch --write`), or extend runtime.csv? Recommendation: derive in the functions.csv generator with a drift test; leave the committed runtime.csv untouched (it is generated, "do not edit").
5. **Jump-table functions later:** own-segment relocations on a non-`-zm` base vs per-function target sections will not objdiff-pair until omf2elf splits `_TEXT` by public. Out of Phase 5 (D-15 excludes tables); note it for Phase 6/7.
6. **`ninja verify` landing:** extend `rebuild` to splice matched functions from built objects (zero-regression gate), or keep landing inside `check` only? Recommendation: both call one `land.py`; `ninja verify` lands all matched functions of both EXEs.

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|---|---|---|---|---|
| Docker Desktop | everything container | yes | server 29.6.2 | — |
| `reverseapoc-build:local` image | tests, ninja, objdiff | yes (built 2026-10-19, 1.13 GB) | lacks clang, JDK, Ghidra, capstone | rebuild after the Dockerfile tasks |
| objdiff-cli | spike, check | container only | 3.8.2 | none on host |
| ninja | build | container only | 1.11.1 | none on host |
| clang | lint | none yet | 18.1.3 to add | — |
| Ghidra zip (owner Downloads) | not used by the build | yes | 12.1.4, SHA-256 OK | the Dockerfile downloads its own |
| Network to GitHub releases | image build | yes (gh API, release download worked) | — | — |
| Watcom trees | cc, spike | yes: 10.5, 10.6, 11.0, 11.0a, 11.0b | — | — |
| `orig/` | real-file tests, spike | yes: UFO2P, TACP, SMKP | — | real-file tests skip |
| Python / uv (host) | tooling | yes | 3.14.5 / uv 0.12.23 | — |
| Windows JDK | not used | yes | 21.0.12.1 | — |

**Missing dependencies with no fallback:** none (clang, JDK, Ghidra and capstone are added by planned tasks).
**Missing with fallback:** objdiff, ninja and clang on the host: run in the container.

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | pytest >= 9.1 (`[dependency-groups].dev`), ruff >= 0.17 |
| Config | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["."]`) |
| Quick run | `uv run pytest -q -x tests/test_<module>.py` |
| Full suite | `uv run pytest -q && uv run ruff check .` (host), `docker compose run --rm test` (container) |

### Phase Requirements -> Test Map

| Req ID | Behavior | Type | Automated command | File exists? |
|---|---|---|---|---|
| SPL-01 | Ghidra layer pinned; export adapter; real export loads both EXEs at the right bases | hygiene + unit + real (`requires_ghidra`) | `uv run pytest -q tests/test_hygiene.py tests/test_ghidra.py tests/test_ghidra_real.py` | ❌ Wave 0 (`test_ghidra*.py`); hygiene ✅ extend |
| SPL-02 | capstone descent on a synthetic LE; reconcile rule; every disagreement has a verdict; real drift test | unit + real | `uv run pytest -q tests/test_discover.py tests/test_functions.py tests/test_functions_real.py` | ❌ |
| SPL-03 | every function in exactly one unit; ranges tile | unit + real | `uv run pytest -q tests/test_units.py` | ❌ |
| SPL-04 | INCLUDE_ASM emits nothing (real compile); configure refuses an unmarked function | real (`requires_version("10.6")`, `requires_runner`) + unit | `uv run pytest -q tests/test_stub_real.py tests/test_configure.py` | ❌ / ✅ extend |
| SPL-05 | listings symbolic, only under `asm/`; nothing committed | unit + hygiene | `uv run pytest -q tests/test_asm.py tests/test_hygiene.py` | ❌ |
| SPL-06 | build.ninja edges, objdiff.json schema keys, compile_commands.json, gitignore entries | unit | `uv run pytest -q tests/test_configure.py` | ✅ extend |
| SPL-07 | synthetic OMF (omfimage: threads, LIDATA, BAKPAT, CEXTDEF, COMDAT32/0xC2) -> ELF sections/symbols/relocs/addends; real probe compile converts | unit + real | `uv run pytest -q tests/test_elf.py tests/test_omf2elf.py tests/test_omf2elf_real.py` | ❌ |
| SPL-08 | synthetic LE -> target: fields rewritten, R_386_32 per fixup, PC32 for leaving calls, a straddler once, inline data skipped | unit | `uv run pytest -q tests/test_target.py` | ❌ |
| SPL-09 | pass on a good pair; FAIL on wrong call, wrong 2nd fixup, missing fixup, local-segment ref, length; straddler passes | unit | `uv run pytest -q tests/test_relocs.py` | ❌ |
| SPL-10 | patch builder keeps original bytes at both-side fields; splice SHA-1 equal; a mutated non-reloc byte fails | unit + real | `uv run pytest -q tests/test_land.py tests/test_splice_real.py` | ❌ / ✅ extend |
| SPL-11 | check JSON shape and exit codes with fake runners; objdiff JSON parsing (absent percent = 0) | unit | `uv run pytest -q tests/test_check.py` | ❌ |
| SPL-12 | lint passes good C and fails mixed declarations; the compat header is inert for Watcom | real (`requires_clang`) | `uv run pytest -q tests/test_lint.py` | ❌ |
| SPL-13 | the two first matches: objdiff 100, reloc pass, both EXE SHA-1s; objdiff-blind negative (2nd reloc) passes objdiff and fails reloc | container real | `docker compose run --rm build bash -lc "python configure.py && ninja && ninja verify && uv run reverseapoc check ufo2p/<u> && uv run reverseapoc check tacp/<u>"` + `tests/test_check_real.py`, `tests/test_objdiff_real.py` (`requires_objdiff`) | ❌ |

### Sampling Rate
- **Per task commit:** the quick run for the touched module, plus `uv run ruff check .`.
- **Per wave merge:** the full host suite, then the container suite (never concurrently).
- **Phase gate:** full suites green on host and container with real-file tests unskipped; `ninja verify` SHA-1 identical for both EXEs; the spike README verdict recorded.

### Wave 0 Gaps
- [ ] `tests/conftest.py`: `requires_ghidra()`, `requires_objdiff()`, `requires_clang()`, `requires_capstone()` next to `requires_runner()`; a Ghidra-loadable synthetic LE variant (`e_lfarlc = 0x40`)
- [ ] `tests/elfread.py`: a test-only ELF32 reader (sections, symbols, relocs, implicit addends)
- [ ] `tests/omfimage.py`: add `comdat16` (0xC2) and NBKPAT builders
- [ ] Synthetic Ghidra export fixture (CSV text, made-up addresses)
- [ ] capstone in `uv.lock` before discovery tests (after the docs/tools.md entry and the human-verify checkpoint)

## Security Domain

`security_enforcement` is enabled (ASVS level 1). This is offline tooling, not a web app.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard control |
|---|---|---|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | partial | read-only mounts for `orig/`, `third_party/` (compose + `test_hygiene`); refuse writes into `orig/` (splice `_refuse_inside_orig`) |
| V5 Input Validation | yes | bounds-checked parsers (`omf.OMFError`, `le.LEError`); the ELF writer validates inputs; CSV schema validation with clear errors; `ninja_path` and `_SAFE_PATH` for paths in commands |
| V6 Cryptography | yes (integrity only) | SHA-256 pins for downloads (`sha256sum -c`), SHA-1 manifests for game/compiler; never hand-rolled |
| V10 Malicious code | yes | third-party Java (loader) and JVM run in the container only, pinned by hash; the Ghidra project lives in `/tmp` and is deleted |
| V14 Configuration | yes | apt version pins; no Watcom/game in image layers (hygiene test); generated files gitignored |

### Known Threat Patterns

| Pattern | STRIDE | Mitigation |
|---|---|---|
| Tampered Ghidra/loader download | Tampering | SHA-256 pin, build fails on mismatch |
| Game bytes leaking via asm, decompiles, logs or test fixtures | Information disclosure | gitignored `asm/`, `build/`; tests use synthetic bytes; outputs print counts/addresses/SHA-1s |
| Path or command injection via unit/file names in build.ninja | Tampering | unit names `[a-z0-9_]`; `ninja_path`; refuse option-like paths |
| Malformed OMF/ELF/LE crashing or overreading | DoS | bounded cursors, named offsets, explicit errors |
| A false "match" (objdiff blind spot) | Spoofing (of the oracle) | reloc check + splice SHA-1 are the gate; negative tests |

## Sources

### Primary (HIGH confidence, verified with tools this session)
- objdiff v3.8.2 source at tag `v3.8.2`: `config.schema.json`, `objdiff-core/config-schema.json` (`functionRelocDiffs` choices `none|name_address|data_value|all`, default `name_address`), `objdiff-core/src/diff/code.rs` (`reloc_eq`, match percent), `diff/mod.rs` (`find_symbol`, `symbol_name_matches`), `arch/x86.rs` (implicit addends, inline data), `obj/read.rs`, `protos/diff.proto`, `protos/report.proto`, `objdiff-cli/src/cmd/diff.rs`
- objdiff-cli 3.8.2 runs on synthetic ELF pairs in `reverseapoc-build:local`
- Ghidra 12.1.4 zip (SHA-256 verified): `docs/GettingStarted.md`, `support/analyzeHeadlessREADME.md`, `support/analyzeHeadless`, `Ghidra/application.properties`; headless runs on both EXEs
- lastonesky ghidra-lx-loader v12.1.4-1 zip (SHA-256 verified): `extension.properties`, `data/languages/x86-watcom.ldefs`, `watcom.cspec`, `LeLoader.java`, `LinearLoader.java`, `Options.java`, `Dos16Header.java`
- Watcom 10.6/10.5/11.0 compiles via `reverseapoc cc` (probe C; `SRC/STARTUP/386/CMAIN386.C`)
- `apt-cache policy` in `ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac`; clang-18 runs
- PyPI JSON for capstone; `uv run --python 3.14 --with capstone==5.0.9`
- In-repo: `le.py`, `splice.py`, `omf.py`, `compiler.py:44-55, 322-341, 525`, `config/cflags.txt:37`, `config/ufo2p/runtime.csv:1-2`, `configure.py:20-51`, `docker/Dockerfile:28-97`, `tests/conftest.py`, `tests/omfimage.py`

### Secondary (MEDIUM)
- Theme Hospital decomp @ `7993814a4f562a1898b20621dbfa60644f9697d7`: `tools/omf2elf.py`, `split.py`, `x86scan.py`, `elfrelocs.py`, `verify.py`, `check.py`, `configure.py`, `tools/clangd/compat.h`, `config/cflags.txt` (read via `gh api`)
- KKND-Decomp @ `4dfd5b100755421bac28ab9dab452b1db7a9c81f` (CC0): `tools/find_functions.py`, `build_kknd.py`, `gen_units.py`, `score_functions.py`, `land.py`, `split.py`, `include/common.h`
- Throwaway estimators (discovery agreement, P16 funnel): counts only, heuristic definitions stated

### Tertiary (LOW)
- None used as the basis of a recommendation without a tag.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (pins read from registries/archives and run)
- Architecture: HIGH for objdiff/OMF/Ghidra mechanics (probed); MEDIUM for unit drafting and scorer weights
- Pitfalls: HIGH (most reproduced this session)
- Estimates: MEDIUM (throwaway heuristics)

**Research date:** 2026-10-23
**Valid until:** about 2026-11-22 for the pins (apt security updates can bump `openjdk-21-jdk-headless` or `clang-18`; refresh with `apt-cache policy` as the Dockerfile comment says)
