# Phase 5: Split and first matches - Context

**Gathered:** 2026-10-23
**Status:** Ready for planning

<domain>
## Phase Boundary

The matching pipeline works end to end, for both UFO2P.EXE (`ufo24`) and TACP.EXE (`tac4`).

- Ghidra 12.1.4 with one LE loader, plus an independent capstone pass, find the functions. The functions are grouped into translation units under `config/<exe>/`.
- C compiles with the Phase 4 compiler under wibo, through `reverseapoc cc` called by ninja.
- objdiff and an independent relocation check compare our objects with target ELF objects cut from the LE.
- One hand-matched function per EXE splices back in place, and both EXEs stay SHA-1 identical to `config/targets.toml`.

Not in this phase:
- progress reporting, guardrail hooks, the per-function driver and decomp.wtf (Phase 6)
- mechanics-driven matching at scale (Phase 7)
- SMKP.EXE (deferred)

Requirements: SPL-01..SPL-13 (`.planning/REQUIREMENTS.md`). Roadmap spike: objdiff diffs OMF-converted ELF cleanly. The verdict decides between the hybrid pipeline and the fallback.

</domain>

<decisions>
## Implementation Decisions

### Spike, Ghidra and fallback
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

### Function list reconciliation
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

### Units and stub convention
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

### First matches and compiler sweep
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

### Decided after research (owner, 2026-10-23)
- **D-19:** An address→name map on the target side counts as normal relocation mapping, not a workaround. The spike verdict is VALIDATED if objdiff then shows 100% on the `__CMain` pair, compiled from the owner's read-only `third_party/watcom/10.6/SRC/STARTUP/386/CMAIN386.C`, which is never copied into the repo. The general mechanism is an optional committed `config/<exe>/symbols.csv` with columns `address,name,kind`, holding addresses and names only and no bytes. The spike README records how it works.
- **D-20:** The Ghidra + JDK layer measures about +1.17 GB (882 MB Ghidra + 286 MB JDK), not the ~800 MB in D-04, and this is accepted. It stays in the main image but is built as its own cached Dockerfile stage, so Python or tool edits don't rebuild it. Unused parts of the Ghidra install, such as `docs/`, are stripped only if the smoke test still passes afterwards.

### Claude's Discretion
- Runtime public offsets, needed for call targets such as `exit_` at module + 1, are derived from LIB386 when `functions.csv` is generated, with a drift test. The committed, generated `runtime.csv` stays unchanged (research Open Question 4).
- `check` and `ninja verify` share one land step. `ninja verify` lands every matched function of both EXEs, which is the zero-regression gate (research Open Question 6).
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and gates
- `.planning/ROADMAP.md` §"Phase 5: Split and first matches": goal, success criteria 1-4, and the spike
- `.planning/REQUIREMENTS.md`: SPL-01..SPL-13
- `docs/workflow.md`: the per-function loop, "the driver owns verification", and the Milestone 1 roadmap row for Phase 5
- `CLAUDE.md` and `.claude/rules/`: hard rules (no game bytes, never edit `orig/`, manifests or build scripts to pass a check, no inline asm)

### Design and what is left to the builder
- `docs/superpowers/specs/2026-10-19-reverseapoc-design.md`: the pipeline diagram and "What is left to the builder" (target ELF cutting, section and symbol naming, COMDAT, FLAT-group fixups, inline switch tables, the relocation check, the stub convention, the compat header and `__WATCOMC__`)
- `.planning/research/ARCHITECTURE.md`: C11 (ELF written directly), C12 (Ghidra adapter), Pattern 3 (generated files gitignored), and the Phase 5 build order
- `.planning/research/PITFALLS.md`: P3 (straddlers), P4 (Ghidra shows relocated bytes), P7 (definition of matched), P8 (target objects, `name_`/`_name`, body-count sizes, `-zm` fill, switch tables), P9 (spike sunk cost), P11 (regressions), P16 (first-function filter), P17 (`__watcall` cspec check), P18 (flag overfitting)
- `.planning/research/STACK.md`: tool pins, clang 18, capstone, and the reuse sources
- `docs/research/notes-own-pipeline-reuse-inventory.md`: what to lift from Theme Hospital (omf2elf, elfrelocs, verify, split, check, configure/project) and KKND-Decomp (find_functions, gen_units, score_functions, land, build_kknd, lib_match), with licenses
- `docs/research/notes-decompwtf-rea-ghidra-ida.md` §3: Ghidra LE loading, headless use, the lastonesky loader

### Toolchain and matching rules
- `docs/toolchain.md`: "Fallbacks and candidates", "Flags", "wibo", the LE layout and straddlers, and the tools-in-container table
- `docs/matching.md`, `docs/coding-style.md` (C89, `func_XXXXXXXX`/`D_XXXXXXXX`, `src/ufo2p|tacp|common/`, the lint command), `docs/learnings.md`, `docs/tools.md` (Use/Skip/Later verdicts; the capstone entry goes in first)
- `config/cflags.txt`, `config/targets.toml`, `config/watcom.toml`, `config/ufo2p/runtime.csv`, `config/tacp/runtime.csv`

### Prior phase decisions
- `.planning/phases/03-byte-identical-round-trip/03-CONTEXT.md`: the splice API and refusals (D-01..D-21), fixup masking, `ninja verify`
- `.planning/phases/04-compiler-identification/04-CONTEXT.md`: D-04 (omf2elf grows from omf.py), D-06 (runtime.csv seeds functions.csv), D-08 (`-o*`/`-zp` confirmed by Phase 5 matches), D-11/D-12 (ninja calls `reverseapoc cc`, the cflags table), D-16 (config_dir)
- `.planning/phases/04-compiler-identification/04-VERIFICATION.md`: the owner override that accepts 10.6 as a preference order

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tools/reverseapoc/le.py`:
  - `LE.fixups()` gives a sorted `Fixup(src_va, kind, target_va, target_obj, target_off, size)`.
  - Also `load_flat(relocate=False)`, `obj_of_va`, `page_va` and `entry_va`.
  - It is the only source of target bytes and of relocations.
- `tools/reverseapoc/splice.py`:
  - `splice(le, {va: bytes}) -> SpliceResult(data, regions, masked)` keeps the link-time value at each fixup field, and `MaskedField` carries `partial`, `clipped` and `straddles_page`.
  - It refuses BSS, overlaps and runs across objects.
  - `rebuild` and `rebuild_target` are here too.
- `tools/reverseapoc/omf.py`:
  - Already parses THEADR, LNAMES, SEGDEF, GRPDEF, EXTDEF/LEXTDEF, COMDEF, CEXTDEF, PUBDEF/LPUBDEF, LEDATA, LIDATA (expanded), FIXUPP with THREAD state, BAKPAT, COMDAT32 with continuations, COMENT (Easy OMF, 0xE9) and MODEND.
  - It provides `Segment.mask`, `Comdat.mask` and `normalized_object_sha1`.
  - It lacks the 16-bit COMDAT 0xC2 and does not apply NBKPAT.
- `tools/reverseapoc/compiler.py` + `cflags.py`: the `cc` wrapper (`compile_rule`, `compile_source`, `runner_prefix` for native or wibo, the hash gate) and the `config/cflags.txt` parser (`select_rule`, last match wins).
- `tools/reverseapoc/libmatch.py`: `read_runtime_csv`, `MatchRange`, the masked slide. `probe.chk_calls` gives the `__CHK` caller set.
- `tools/reverseapoc/targets.py`: `load_manifest`, `config_dir(name)`, the hashing helpers.
- `configure.py` (repo root): writes `build.ninja` only, with the rules `check_orig`, `parse_le` and `rebuild`, the phony `verify`, and `ninja_path` escaping. A comment says "compile rules arrive in Phase 5".
- `docker/Dockerfile`: Ubuntu 24.04, uv, wibo 1.2.0, objdiff-cli v3.8.2 and the Open Watcom v2 snapshot, all SHA-pinned. It also has ninja 1.11.1, binutils 2.42, clang-format 18 and clangd 18, but not clang itself, nor capstone, nor Ghidra.

### Established Patterns
- The CLI is `tools/reverseapoc/cli.py`: `build_parser()` with one `_cmd_*` per verb. Each new verb (`ghidra-export`, `discover`, `units`, `asm`, `omf2elf`, `check`, `lint`) follows it.
- Tests:
  - `tests/` is flat, with about 660 tests.
  - Real-file tests are `test_<module>_real.py`; they take `ORIG_DIR`, overridable with `REVERSEAPOC_ORIG`, and skip per target.
  - `requires_version(v)` and `requires_runner()` gate Watcom tests; `requires_ghidra()` joins them.
  - Synthetic LE and OMF fixtures (`conftest.py`, `omfimage.py`) mean no game bytes are committed.
- TDD for Python tooling (superpowers). Lifted code keeps a derivation header naming its source and license, as `le.py` does for KKND (CC0). Theme Hospital code is GPLv3, compatible with `tools/` GPLv3.
- Committed config files hold addresses, names and hashes only, and a real-file drift test re-derives them (the runtime.csv precedent).
- Done gate: `uv run pytest -q && uv run ruff check .` on the host and in `docker compose run --rm test`, with real-file tests unskipped. Rebuild must stay SHA-1 identical.

### Integration Points
- `configure.py` → `build.ninja`. New edges cover: compile (`uv run reverseapoc cc`), omf2elf, target-ELF cut, objdiff.json, compile_commands.json, lint, check, plus the existing `verify`.
- `splice()` takes matched function bytes from our object, and `check` runs the whole-EXE SHA-1 against `config/targets.toml`.
- `config/<exe>/functions.csv`, `units.csv` and `boundaries.csv` are new. `runtime.csv` seeds them.
- `src/<exe>/<unit>.c` and `include/watcom_compat.h` are new directories.
- The Docker image gets a Ghidra + JDK layer and clang 18. `pyproject.toml` gets capstone.

</code_context>

<specifics>
## Specific Ideas

- The owner wants other developers to need no manual Ghidra download. That is why Ghidra and its JDK are baked into the image (D-04), not installed on the host.
- The owner already installed JDK 21.0.12.1 on Windows and downloaded the Ghidra 12.1.4 and 12.2 zips to `C:\Users\Ayrton\Downloads\Compressed\`. They are useful for a host GUI and are not used by the pipeline.
- Ghidra itself needs a JDK: the GUI and headless both run on Java. A container needs its own Linux JDK.

</specifics>

<deferred>
## Deferred Ideas

- Whether decomp.wtf fork mode accepts the `INCLUDE_ASM` marker: the Phase 6 spike.
- Sweeping `-zp1/2/4/8`, `-zm` and `-fp3`/`-fp5`: only if the D-17 matrix finds no match.
- 11.0a/11.0b: only if matches favour 11.0 (04 D-02).
- Installed vs CD v1.00 primary build: revisit after Phase 5 (PROJECT.md Key Decisions).
- GhidraMCP / retrokit MCP for interactive agent queries: Phase 6 (agent context pack) or later.
- A host-native Ghidra GUI setup guide using the owner's Windows JDK: optional docs, not pipeline.

</deferred>

---

*Phase: 05-split-and-first-matches*
*Context gathered: 2026-10-23*
