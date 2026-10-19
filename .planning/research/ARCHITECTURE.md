# Architecture Research

**Domain:** Byte-matching decompilation pipeline for a bound DOS/4GW LE executable built with Watcom C 10.x (X-COM: Apocalypse, UFO2P.EXE `ufo24` and TACP.EXE `tac4`)
**Researched:** 2026-10-19
**Confidence:** HIGH for the oracle (splice, compile, compare, SHA-1): it copies two working Watcom/LE pipelines (KKND-Decomp, Theme Hospital) that the local research inventoried file by file. MEDIUM for the OMF-to-ELF/objdiff seam and the decomp.wtf fork-mode seam: they are documented but untested on these binaries, and the Phase 5 and Phase 6 spikes exist to settle them.

**Sources:** local files only, as the brief requires. No web lookups were made. Phase numbers follow ROADMAP.md (1-6).

---

## Standard Architecture

Every comparable project has the same three layers. The research found no exception.

1. An **analysis layer** that turns the original binary into a function list, names and drafts. It is outside the build and never judges a match.
2. A **deterministic oracle** that compiles C with the original compiler, compares the result with the original bytes, and rebuilds the whole executable for a final hash check.
3. An **agent/driver layer** that picks a function, asks a model for C, and then runs the oracle again itself before committing. It is replaceable.

The arrows only point down into the oracle. The oracle never reads anything the agent layer writes except `src/` and `include/`. That one rule is what keeps the verifier trustworthy (`docs/research/2026-10-19-kickoff-research-report.md`, "Conclusion"; `docs/workflow.md`, "The driver owns verification").

KKND-Decomp is the closest structural match: bound DOS/4GW Pro LE, Watcom 10.x, in-place splice with a SHA-1 gate. Theme Hospital adds the parts KKND lacks: a configure.py/ninja build, the real Watcom 10.6 under wibo, OMF-to-ELF and objdiff. ReverseApoc's design is KKND's gate plus Theme Hospital's build and compare path (`docs/research/notes-own-pipeline-reuse-inventory.md` Q1, Q2, Q4).

### System Overview

```
 HOST (Windows 10)                 WSL2 Ubuntu                          GitHub
 ┌──────────────────────┐   ┌───────────────────────────────────┐   ┌──────────────────────┐
 │ Steam/GOG install    │   │ ANALYSIS LAYER (never judges)     │   │ Actions: ci.yml      │
 │  (read-only)         │   │  Ghidra 12.1.4 + LE loader        │   │  (lint, pytest,      │
 │        │ ingest      │   │   (lastonesky or retrokit)        │   │   no orig/, no wcc)  │
 │        v             │   │  GhidraMCP 2.0 headless (py3.13)  │   │ Actions: progress.yml│
 │ orig/  (gitignored)  │   │        │ functions/names/drafts   │   │  -> Pages: svg, json,│
 │ third_party/watcom/  │   │        v                          │   │     shield; report   │
 └────────┬─────────────┘   │  ghidra2functions adapter ──────┐ │   │     artifact         │
          │ ro bind mounts  │                                 │ │   └──────────▲───────────┘
          v                 │ AGENT LAYER (replaceable)       │ │              │ committed
 ┌─────────────────────────────────────────────────────────┐ │ │              │ metadata only
 │ DOCKER BUILD IMAGE: THE ORACLE                          │ │ │              │
 │                                                         │ │ │              │
 │  config/  targets.toml  cflags.txt  <exe>/functions.csv ◄─┼─┘              │
 │           <exe>/units.csv                               │ │                │
 │      │                                                  │ │                │
 │  configure.py ──writes──> build.ninja, objdiff.json,    │ │                │
 │      │                    compile_commands.json         │ │                │
 │      v                                                  │ │                │
 │  ┌────────────┐  ┌────────────┐  ┌──────────────────┐   │ │                │
 │  │ cc: wibo + │─>│ omf2elf    │─>│ objdiff-cli      │   │ │                │
 │  │ wcc386@ver │  │ (OMF->ELF) │  │ base vs target   │   │ │                │
 │  └─────▲──────┘  └────────────┘  └────────▲─────────┘   │ │                │
 │        │ src/ include/                     │            │ │                │
 │        │                     ┌─────────────┴──────┐     │ │                │
 │        │                     │ split: target ELF  │     │ │                │
 │        │                     │ per unit from LE   │     │ │                │
 │        │                     └─────────▲──────────┘     │ │                │
 │        │   ┌───────────────────────────┴───────────┐    │ │                │
 │        │   │ le.py (LE reader: pages, fixups)      │◄── orig/ (ro)         │
 │        │   └───────────────────────────┬───────────┘    │ │                │
 │        │                               v                │ │                │
 │        │   ┌───────────────────────────────────────┐    │ │                │
 │        │   │ gate: cut fn bytes, mask relocs,      │    │ │                │
 │        │   │ check reloc targets, splice in place, │    │ │                │
 │        │   │ whole-EXE SHA-1 vs targets.toml       │────┼─┼──> PASS / FAIL │
 │        │   └───────────────────────────────────────┘    │ │                │
 └────────┼────────────────────────────────────────────────┘ │                │
          │ edits src/ only                                  │                │
 ┌────────┴─────────────────────────────────────────────┐    │                │
 │ driver (Nigel or ~200-line Python): scorer -> claude │────┘                │
 │ -p "/goal ..." -> re-run gate -> commit | reset      │─────────────────────┘
 │ hooks: deny edits to orig/, manifests, oracle files  │  (commits src/ + status)
 │ decomp.wtf v0.10.6 fork mode (claims, MCP, GUI)      │
 └──────────────────────────────────────────────────────┘
```

This matches the design spec's diagram (`docs/superpowers/specs/2026-10-19-reverseapoc-design.md`, "Architecture overview"). The overview above adds the config tables, the split between the analysis and agent layers, and the CI boundary.

### Component Responsibilities

Status: **exists** = in the repo today, **P3 to P6** = the phase that builds it.

| # | Component | Owns | Implementation (and reuse source) | Status |
|---|---|---|---|---|
| C1 | Target manifest + ingest | Ground truth of what the originals are (size, CRC32, MD5, SHA-1) | `tools/reverseapoc/targets.py`, `ingest.py`, `config/targets.toml` | exists |
| C2 | LE reader | Header, object table, page map, fixups as `Fixup(src_va, kind, target_va, ...)`, `load_flat()` | `tools/reverseapoc/le.py` (from KKND le.py, CC0). Rejects iterated/zero pages and non-internal fixups | exists |
| C3 | Byte-region map | Proves every file byte belongs to exactly one region: bound extender, Watcom stub, LE header/loader section, fixup section, data pages. Maps linear address to file offset per page | New, small, inside `le.py` or a `layout.py` next to it | P3 |
| C4 | Splicer | Pure function: original bytes + `{va: bytes}` patches -> new file bytes. Refuses patches that fall outside page data (BSS), change length, or touch bytes outside the patched function's range | New, after KKND `build_kknd.py` (`out = bytearray(le.data)`, per-page overwrite) | P3 |
| C5 | Whole-EXE gate | Rebuilds `build/<exe>/<EXE>` from the splice and compares SHA-1 with C1. The project's definition of done | New, uses `targets.hash_file`. `reverseapoc rebuild` / `ninja verify` | P3 |
| C6 | Compiler wrapper (`cc`) | Runs `BINNT\wcc386.exe` (or `wpp386`) under wibo with per-file `compiler@version` and flags from `config/cflags.txt`. Handles path rewriting (`/` -> `\`, no spaces) | Adapt TH `cc.py` (GPLv3) plus the decomp.me cromper command line (MIT) | P4 |
| C7 | OMF reader | LNAMES/SEGDEF/GRPDEF/EXTDEF/PUBDEF/LEDATA/LIDATA/FIXUPP/COMDAT. Extracts modules from `.LIB` files | TH `omf2elf.py` reader half plus `library_module` (GPLv3) | P4 (needed for the library match, not only for objdiff) |
| C8 | Library matcher + codegen probe | Masked-byte matching of CLIB3R/MATH3R modules against obj1; compiles mosura probe constructs per version and searches the idioms | Adapt KKND `lib_match.py` (CC0). Probe sources are new | P4 |
| C9 | ELF32 writer | Writes `.text`/`.data` with FUNC symbols and `.rel` sections (R_386_32, R_386_PC32). Shared by C10 and C11 | TH `omf2elf.py` writer half | P5 |
| C10 | OMF-to-ELF (base objects) | Our compiled `.obj` -> `.o` that objdiff can read | TH `omf2elf.py` | P5 |
| C11 | Target splitter | One ELF target object per unit, cut from the LE: function bytes from pages, relocations from LE fixups | Adapt TH `split.py` (it emits GNU `as`). Recommended instead: emit ELF directly through C9 and skip `as` | P5 |
| C12 | Function table | `config/<exe>/functions.csv` (addr, size, name, unit, status). Ghidra/retrokit export -> contiguous, padding-trimmed ranges, cross-checked by capstone discovery | New `ghidra2functions` adapter plus KKND `find_functions.py` (needs `capstone`, recorded in `docs/tools.md`) | P5 |
| C13 | Relocation check | Every `call rel32` hits the same function; every absolute fixup resolves to the original LE fixup target. Covers what objdiff misses (at most one relocation per instruction) | TH `elfrelocs.py`/`verify.py` (GPLv3) plus KKND rules | P5 |
| C14 | Landing step | For each function marked in `src/`: cut its bytes from the compiled object, require identical non-relocated bytes and equal length, keep the original bytes at fixup fields, hand the patch to C4 | Adapt KKND `build_kknd.py` and `land.py` | P5 |
| C15 | Build generator | `configure.py` -> `build.ninja` (cc, omf2elf, split, objdiff, report, rebuild, verify edges), `objdiff.json`, `compile_commands.json` | Existing skeleton plus the TH `configure.py`/`project.py` pattern, slimmed down | exists (skeleton) -> P3, P5 |
| C16 | Progress reporter | `progress.json`, treemap `progress.svg`, shields `shield.json`, objdiff-shaped `report.json`, all from committed metadata | New stdlib script (the AnyPS5 output design, rewritten) | P6 |
| C17 | Scorer | Ranks unmatched functions: easiest first, later similarity first, twins and runtime functions first | KKND `score_functions.py`, plus an opcode-Levenshtein `similar.py` | P6 |
| C18 | Driver | Per function: candidate -> `claude -p "/goal ..."` -> re-run C15/C5 -> commit or reset. Attempt cap of 3 to 5, re-queue, usage-limit backoff | Nigel (evaluate first) or about 200 lines of Python | P6 |
| C19 | Guardrail hooks | PreToolUse denies edits to `orig/`, manifests, oracle files and generated dirs, and inline asm or code-emitting `#pragma aux` in `src/` | New Claude Code hooks in `.claude/settings.json` | P6 |
| C20 | decomp.wtf fork mode | Claims, MCP tools, GUI, undo on regression. Consumes the repo through `configure.py` + ninja + `objdiff.json` | decomp.wtf v0.10.6 (MIT, archived), run as a subprocess in WSL2 with light patches | P6 |
| C21 | `watcom-decomp` skill | Flags, idioms and C89 rules for agents | `.claude/skills/watcom-decomp/` | P6 |

## Recommended Project Structure

This extends the existing tree and keeps the single `reverseapoc` package (`pyproject.toml` already builds `tools/reverseapoc`). It does not move to the flat `tools/*.py` layout from the kickoff report.

```
ReverseApoc/
├── configure.py                  # C15: grows P3 (rebuild/verify edges) and P5 (compile/diff edges)
├── config/
│   ├── targets.toml              # C1 (exists; protected)
│   ├── cflags.txt                # P4: glob -> compiler@version flags (first match wins, TH style)
│   ├── ufo2p/ functions.csv units.csv symbols.csv   # P5: metadata only, no game bytes
│   └── tacp/  functions.csv units.csv symbols.csv
├── include/                      # P5: shared structs/prototypes; include/compat/ for clangd
├── src/
│   ├── common/                   # engine code matched in both EXEs (twins)
│   ├── ufo2p/                    # only C that matches; markers name the address
│   └── tacp/
├── probe/                        # P4: mosura codegen probe sources (our own C, no game bytes)
├── tools/reverseapoc/
│   ├── cli.py targets.py ingest.py le.py      # exist
│   ├── splice.py                 # P3: C3 region map + C4 splicer
│   ├── rebuild.py                # P3: C5 gate (rebuild + SHA-1)
│   ├── watcom.py                 # P4: C6 compiler wrapper (wibo, path rewriting, versions)
│   ├── omf.py                    # P4: C7 reader (TH-derived; keep the GPLv3 header)
│   ├── libmatch.py               # P4: C8
│   ├── elf.py                    # P5: C9 ELF32 writer
│   ├── omf2elf.py                # P5: C10
│   ├── split.py                  # P5: C11 target objects
│   ├── functions.py              # P5: C12 table model, Ghidra adapter, capstone cross-check
│   ├── relocs.py                 # P5: C13
│   ├── land.py                   # P5: C14 (calls splice.py + rebuild.py)
│   ├── progress.py score.py similar.py        # P6: C16, C17
│   └── driver/                   # P6: C18 (if Nigel loses)
├── tests/                        # pytest per module; real-file tests skip without orig/
├── .claude/
│   ├── settings.json             # P6: hook registration (C19)
│   ├── guard/                    # P6: hook scripts (NOT .claude/hooks/, see Integration Points)
│   ├── rules/ skills/watcom-decomp/
├── .github/workflows/ ci.yml (exists)  progress.yml (P6)
├── orig/ third_party/watcom/     # gitignored, ro mounts
└── build/                        # gitignored: <exe>/obj/*.obj, base/*.o, target/*.o, report.json, <EXE>
```

### Structure Rationale

- **One Python package, one CLI.** Every oracle step is reachable as `uv run reverseapoc <verb>`, and `build.ninja` only calls those verbs. Hooks, the driver and decomp.wtf then have a small, fixed set of commands to allow or protect. The tests, ruff and the existing `cli.py` pattern carry over unchanged.
- **`config/<exe>/` per target.** The two EXEs have separate module names, bases and probably link scripts (`docs/toolchain.md`, "Targets"). Every tool takes an `exe` key and never assumes one EXE. KKND's tools assume one EXE, which is why the reuse inventory marks them "adapt" (`notes-own-pipeline-reuse-inventory.md` Q8).
- **`src/common/` for twins.** The splice gate verifies per EXE, so one C function can land at different addresses in UFO2P and TACP. Use a reccmp-style marker that can repeat, `// FUNCTION: UFO2P 0x000xxxxx` and `// FUNCTION: TACP 0x000yyyyy` (the convention in decomp.wtf's x86 guide, `notes-decompwtf-rea-ghidra-ida.md` section 1; TH uses `// FUNCTION: 0xADDR`). This is a recommendation, not yet a project decision.
- **Metadata committed, bytes never.** `functions.csv` holds addresses, sizes, names and status. That is enough for CI to compute progress without `orig/` or the compiler (see Pattern 4). KKND commits the same kind of CSVs.

## Architectural Patterns

### Pattern 1: In-place page splice into a copy of the original (the oracle's core)

**What:** Start from `bytearray(original)`. For each matched function, overwrite only its bytes inside the page that holds them, then hash the whole file. Headers, page map, fixup tables and the DOS/4GW blob are never regenerated.
**When to use:** For all of Milestone 1. It stays valid while every matched function has exactly the original length and unmatched bytes stay original.
**Trade-offs:** Byte-identical by construction and about 1 to 3 days of work, against 10 to 20+ for TH's full `lewrite.py` (`notes-own-pipeline-reuse-inventory.md` Q4). It cannot produce shiftable or relinkable builds. Nobody needs those in Milestone 1.

**Example:**
```python
def splice(le: LE, patches: dict[int, bytes]) -> bytes:
    out = bytearray(le.data)
    for va, chunk in sorted(patches.items()):
        for off, piece in le.file_ranges(va, chunk):   # C3: splits across page boundaries
            out[off:off + len(piece)] = piece
    return bytes(out)                                   # caller hashes and compares (C5)
```

The Phase 3 round trip is `splice(le, {})` plus a stronger test. C3 must show that the file decomposes into its regions with no gaps or overlaps, and recomposing them must reproduce the SHA-1. That is the "round trip" that actually proves the layout model. An identity splice proves almost nothing on its own.

### Pattern 2: Masked compare, then splice original relocation bytes

**What:** Compiled code has placeholder values in relocated fields, while the LE pages hold link-time values. The gate compares every non-relocated byte, checks that each relocation's target matches the LE fixup target (C13), and then splices with the **original** bytes kept at fixup fields (KKND: "Relocated fields keep the original link-time value after the relocation target has been checked", `notes-own-pipeline-reuse-inventory.md` Q2).
**When to use:** For every landing (C14). The SHA-1 alone would pass a function whose call goes to the wrong target if the gate took bytes from the original at fixup sites without the target check. The two checks are both required.
**Trade-offs:** String literals and other local-segment data references are refused until data placement is modelled. Such data moves to `extern D_` symbols (KKND rule, `docs/matching.md` "Relocation rules").

### Pattern 3: One generated build graph, every consumer goes through it

**What:** `configure.py` writes `build.ninja`, `objdiff.json` and `compile_commands.json` from `config/`. Humans, the driver, decomp.wtf fork mode and CI all run the same ninja targets: `ninja verify`, `ninja report`, `ninja build/<exe>/base/<unit>.o`.
**When to use:** From Phase 3, when the `rebuild` and `verify` edges join the existing `check-orig`/`parse-le` edges.
**Trade-offs:** decomp.wtf fork mode accepts exactly this contract ("builds with configure.py + ninja and produces objdiff.json", `notes-decompwtf-rea-ghidra-ida.md` section 6), so the agent layer comes almost for free. The price: generated files (`objdiff.json`, `compile_commands.json`) must stay out of git. Today's `.gitignore` covers `build.ninja` but **not** those two files.

### Pattern 4: Progress from committed metadata, not from CI builds

**What:** CI has neither `orig/` nor the Watcom compiler (`ci.yml`: "orig/ is never present in CI"), so it cannot run the oracle. Progress is computed from `config/<exe>/functions.csv` (sizes) plus the function markers in `src/`. A function present in C counts as matched because the local gate refuses anything else. This is KKND's model (`notes-own-pipeline-reuse-inventory.md` Q2, `make_report.py`).
**When to use:** Phase 6, for `progress.py`, Pages and the recomp.fyi `report.json` artifact.
**Trade-offs:** The trust anchor moves from CI to the local gate plus hooks. A protected `status` column, which only the driver or gate writes, keeps that anchor honest. A hand-built objdiff-shaped report may or may not be accepted by recomp.fyi (`notes-progress-reporting-recompfyi.md`: "unverified").

### Pattern 5: Driver-owned verification with a per-function fresh session

**What:** The driver picks the candidate (the agent does not choose), runs one `claude -p "/goal ..."`, then re-runs the gate itself, commits on PASS and resets on FAIL. Attempt cap 3 to 5, with a difficult list for re-queue. `/goal`'s evaluator cannot call tools, so its verdict is only a hint (`docs/workflow.md`).
**When to use:** Phase 6 pilot. The Nigel contract maps one to one: `candidate_source` = `reverseapoc next --json`, `verify_command` = `ninja verify`, `success_command` = git commit, `reset_command` = git checkout (`notes-automation-loops.md`, Nigel inference).

## Data Flow

### Match Flow (one function, Phase 5 by hand, Phase 6 by the driver)

```
functions.csv ──> scorer (C17) ──> candidate F (exe, va, size, unit)
                                        │
          context: target asm, callers/callees, Ghidra draft, notes
                                        v
              agent edits src/<exe|common>/<unit>.c   (only writable surface)
                                        │
                                        v
  cflags.txt ──> cc: wibo wcc386@ver (C6) ──> build/<exe>/obj/<unit>.obj (OMF)
                                        │
                     ┌──────────────────┴───────────────────┐
                     v                                      v
          omf2elf (C10) -> base/<unit>.o          land (C14): cut F from OMF,
                     │                            mask relocs, check targets (C13)
  orig (ro) -> le.py -> split (C11) -> target/<unit>.o          │
                     v                                      v
          objdiff-cli: diff + report.json          splice (C4) -> build/<exe>/<EXE>
          (a view, plus progress)                           │
                                                            v
                                  SHA-1 == targets.toml ? (C5)  ── PASS -> driver commits
                                                                └─ FAIL -> driver resets, notes
```

Direction is strictly left to right and top to bottom. Nothing downstream writes upstream. `orig/` and `third_party/` are read-only mounts. `config/targets.toml` and the oracle code are protected by hooks from Phase 6 on.

### State and where it lives

```
config/targets.toml      (protected, human-edited, ground truth)
config/cflags.txt        (P4 finding; agents may propose, a human approves)
config/<exe>/*.csv       (function table; the status column is written only by gate/driver)
src/, include/           (agent-writable)
docs/learnings.md        (agent-appendable; promotion to matching.md is human-reviewed)
build/                   (disposable, regenerated; never trusted across runs)
git history              (one matched function per commit = the audit trail)
```

### Key Data Flows

1. **Ingest (exists):** game folder -> `ingest` -> `orig/` -> `check-orig` against `targets.toml`.
2. **Round trip (P3):** `orig/<EXE>` -> `le.py` + C3 region map -> splice with no patches -> `build/<exe>/<EXE>` -> SHA-1 equal. The same path later carries real patches, unchanged.
3. **Compiler ID (P4):** `probe/*.c` -> C6 at 10.5/10.6/11.0 -> C7 -> idiom search in obj1 bytes, and `LIB386/clib3r.lib` -> C7 `library_module` -> C8 masked match against obj1 -> results in `docs/toolchain.md`, `config/cflags.txt`, and runtime function names in `config/<exe>/symbols.csv`.
4. **Split (P5):** Ghidra/retrokit export (WSL2) -> C12 adapter + capstone cross-check -> `functions.csv` and `units.csv` -> C11 target objects -> `objdiff.json` -> objdiff.
5. **Progress (P6):** committed CSVs + `src/` markers -> `progress.py` (in CI) -> Pages (`progress.svg`, `progress.json`, `shield.json`) and a `<VERSION>_report` artifact for recomp.fyi.

## Build Order (dependencies between components)

The order is consistent with the fixed Milestone 1 phase order (`docs/workflow.md`, "Milestone 1 roadmap").

```
exists:  C1 manifest ── C2 le.py ── C15 configure.py skeleton ── Docker image (wibo, objdiff-cli, OW tools)
           │
P3:      C3 region map ─> C4 splicer ─> C5 rebuild + SHA-1 gate ─> ninja verify edge
           │                     (no compiler, no OMF needed: build first, test hardest)
P4:      C6 cc/wibo wrapper ─> C7 OMF reader ─> C8 lib match + probe ─> cflags.txt
           │                     (C7 is pulled in here: the library match needs OMF/.LIB parsing)
P5:      C12 function table ─┐
         C9 ELF writer ─> C10 omf2elf ─┐
         C9 ─> C11 target split ───────┼─> objdiff spike (hybrid vs fallback)
         C13 reloc check ─> C14 land ──┴─> uses C4/C5 from P3, C6/C7 from P4
         C15 grows: compile, convert, split, objdiff.json, report, land+verify edges
           │
P6:      C16 progress (needs C12 + markers)    C17 scorer (needs C12)
         C19 hooks (need the final oracle file list from P5)
         C18 driver (needs one-command `ninja verify` from P5 + C17 + C19)
         C20 decomp.wtf fork mode (needs objdiff.json + target objects from P5) ── spike: stub convention
         C21 watcom-decomp skill (needs P4 flags + P5 learnings)
```

Implications for the roadmap:

- **Phase 3 is self-contained and should stay compiler-free.** C3, C4 and C5 depend only on `le.py`. Their spike (iterated pages and fixup edge cases) is partly answered already: `le.py` raises on non-physical pages and non-internal fixups, and `tests/test_le_real.py` exercises `load_flat()` and `fixups()` on the real files. If those tests ran green with `orig/` present, both EXEs use only physical pages and internal fixups. Confirm this at the start of Phase 3 instead of re-researching it.
- **Phase 4 should take in the OMF reader (C7), not wait for Phase 5.** The library match parses `.LIB` and OMF modules. Bring TH's `omf2elf.py` in once in Phase 4, the reader half used there, and add the ELF writer half and tests in Phase 5. An early signal at no extra cost: run objdiff on one converted CLIB3R module in Phase 4. That previews the Phase 5 spike before the function split exists.
- **In Phase 5, run the objdiff spike first.** The gate does not depend on it: C13, C14 and C5 decide "done" whatever objdiff says, so the KKND-style fallback costs little. C11 and C20 do depend on the spike outcome.
- **In Phase 5, write the unit model (C12 plus `units.csv`) before C11 and C15's compile edges.** Both are keyed by unit, and boundary errors between Ghidra and capstone break the splice size check (`notes-own-pipeline-reuse-inventory.md` Q8, "Function discovery").
- **Phase 6 has an internal order:** C19 hooks before the first unattended C18 run. C16 progress is independent and can run in parallel. The C20 spike (stub convention) comes before choosing decomp.wtf over a Claude-Code-only minimal layer.

## Scaling Considerations

The scale here is matched functions and parallel agents, not users. Each EXE has roughly 0xC0000 bytes of code. Comparable projects have 2,938 (TH) and 3,713 (KKND) functions.

| Scale | Architecture adjustments |
|---|---|
| 1-10 functions (Phases 5-6) | Single checkout, single build dir, `ninja verify` rebuilds both EXEs. A full splice plus SHA-1 of 1.7 MB and 3.2 MB files is negligible next to a wibo compile |
| 100s of functions, 1 agent | `ninja` incremental per unit. Landing should skip units whose objects did not change. Keep `verify` whole-EXE: it is cheap and it is the definition of done |
| 1000s of functions, 3-4 parallel agents | One git worktree and build dir per agent (Lewis ran 3-4 worktrees with Nigel `--shard`). decomp.wtf claims stop collisions. Re-verify on `main` after each merge, because two individually verified splices can still interact through a shared unit |

### Scaling Priorities

1. **First bottleneck: file I/O on the Docker Desktop bind mount.** The repo is mounted from NTFS into the container (`docker/compose.yaml`: `..:/work`). Thousands of small `.obj`/`.o` writes under `build/` will be slow. Fix: put `build/` on a named volume, the way the venv already lives in `uv-venv`, or keep the working clone in the WSL2 filesystem. decomp.wtf's own docs say projects belong in the Linux filesystem, not `/mnt/c`.
2. **Second bottleneck: subscription usage limits, not compute.** Unattended Opus can exhaust a Max 20x plan in days (`docs/workflow.md`). The driver needs backoff, a nightly cap and cheapest-first ordering.

## Anti-Patterns

### Anti-Pattern 1: Letting the agent's verdict, objdiff's percentage or `/goal` count as "matched"

**What people do:** They treat a 100% objdiff score or a "MATCH" line in the transcript as done.
**Why it's wrong:** objdiff compares at most one relocation per x86 instruction. `/goal` cannot run tools. Agents have rewritten SHA-1s and claimed false matches (`docs/workflow.md`; kickoff report, "A thin per-function driver").
**Do this instead:** Done = C13 relocation check + C5 whole-EXE SHA-1, re-run by the driver.

### Anti-Pattern 2: Rewriting the LE (TH `lewrite.py` style) in Milestone 1

**What people do:** They regenerate headers, page map and fixup records for a "real" rebuild.
**Why it's wrong:** TH's writer hardcodes game-specific constants and needs a 457-line relinker. That is 10 to 20+ days for zero matching value.
**Do this instead:** In-place splice (Pattern 1). Revisit only if shiftable builds become a goal.

### Anti-Pattern 3: Requiring units to compile completely before anything is verified

**What people do:** They model each original source file as a unit that must compile and link whole, with asm stand-ins for every unmatched function.
**Why it's wrong:** The splice never needs unmatched functions compiled. Their original bytes are already in the copy. GNU-asm `INCLUDE_ASM` (the decomp.wtf convention) means nothing to `wcc386`.
**Do this instead:** Make `INCLUDE_ASM(name)` a no-op C declaration, as KKND does with `extern int INCLUDE_ASM_##name`, so a unit holds only matched C plus markers. The target object still contains every function, and objdiff reports the missing ones as unmatched, which is the right progress signal. Whether decomp.wtf fork mode tolerates this is the Phase 6 spike.

### Anti-Pattern 4: Running the oracle in CI, or skipping CI because it cannot run the oracle

**What people do:** They try to build in Actions, which would mean shipping the game or the compiler. Or they publish progress by hand.
**Why it's wrong:** The first breaks the "no game bytes" anti-goal. The second lets progress drift from reality.
**Do this instead:** Pattern 4. CI lints, tests and computes progress from committed metadata. The local gate plus hooks guard the metadata.

### Anti-Pattern 5: One-EXE assumptions in reused code

**What people do:** They copy KKND tools that hardcode a single EXE, `func_`/`D_` naming and paths.
**Why it's wrong:** Every later twin match and progress figure needs a per-EXE key.
**Do this instead:** Every CLI verb and ninja edge takes `<exe>`. `config/<exe>/` holds per-target tables. Twins share source in `src/common/`.

## Integration Points

### External Tools

| Tool | Integration pattern | Notes |
|---|---|---|
| Watcom 10.x `wcc386` (user-supplied) | Subprocess under wibo 1.2.0 in Docker, `/work/watcom:ro` | Paths must use `\` and contain no spaces. The BINNT binary also runs natively on Windows for debugging. Running every version under wibo is the Phase 4 spike |
| objdiff-cli v3.8.2 (pinned in the Dockerfile) | Subprocess on `objdiff.json` units (`target_path` = C11 output, `base_path` = C10 output) | Cannot read OMF (issue #97), hence C10. Symbol naming and section layout must suit both objdiff and decomp.wtf (left to Phase 5 by the design spec) |
| Ghidra 12.1.4 + LE loader + GhidraMCP 2.0 (WSL2) | Out-of-band export -> C12 adapter. Never called by the build | Python 3.13 for GhidraMCP headless. retrokit sizes are Ghidra body counts and need trimming into contiguous ranges. The lx-loader README calls UFO2P "unbound", which contradicts the local scan: check in Phase 5 |
| decomp.wtf v0.10.6 fork mode (WSL2) | Opens the repo as a local git repo and runs configure.py + ninja + objdiff itself | **Open seam:** its build runs in WSL2 or its own sandbox, not in our Docker image. Either wibo, objdiff-cli, ninja and uv get installed in WSL2 at the same pins, or our ninja rules wrap `docker compose run`. Decide in the Phase 6 spike. Fork mode does not ban `#pragma`, so our hooks must cover `#pragma aux` code bodies |
| Claude Code hooks | PreToolUse on Edit/Write/Bash, registered in `.claude/settings.json` | **Path trap:** `.gitignore` ignores `.claude/hooks/` (GSD's install dir), so project hook scripts must live elsewhere (for example `.claude/guard/` or `tools/reverseapoc/guard.py`) or they will never be committed |
| GitHub Pages / recomp.fyi | `progress.yml` on push to `main`: upload-pages-artifact + deploy-pages; `<VERSION>_report` artifact | Pages on a private repo needs a paid plan. Whether recomp.fyi accepts a hand-built report is unverified |

### Internal Boundaries

| Boundary | Communication | Notes |
|---|---|---|
| `le.py` <-> everything | Python API (`LE`, `Fixup`, `load_flat`, new `file_ranges`) | The only reader of `orig/` bytes. Never writes |
| splice/rebuild (C4/C5) <-> land (C14) | Python API: `{va: bytes}` patches in, PASS/FAIL + SHA-1 out | C4 is pure and policy-free. All match policy (masking, targets, data refs) sits in C13/C14 |
| ninja <-> tools | `uv run reverseapoc <verb>` command lines | Keeps the protected surface small: the verbs plus `configure.py` |
| driver / decomp.wtf <-> oracle | Shell: `ninja verify` exit code + `report.json` | The driver never imports oracle code; decomp.wtf stays a subprocess (MIT/GPLv3 boundary, `docs/superpowers/specs/2026-10-19-reverseapoc-design.md` "Constraints") |
| agents <-> repo | File edits limited to `src/`, `include/`, notes | Enforced by C19. The function-table status column is written only by C14 or the driver |
| WSL2 analysis <-> Docker oracle | Files: exported CSVs under `config/<exe>/` | One-way. Ghidra output is a hint that the C12 capstone cross-check validates |

## Sources

- `docs/superpowers/specs/2026-10-19-reverseapoc-design.md`: architecture overview diagram, decisions, "What is left to the builder"
- `docs/workflow.md`: per-function loop, driver ownership of verification, hooks table, Milestone 1 roadmap and spikes
- `docs/toolchain.md`: LE layout, Docker image contents, objdiff/OMF bridge, wibo path rules
- `docs/matching.md`: relocation rules inherited from KKND
- `docs/research/2026-10-19-kickoff-research-report.md`: pipeline shape, recommended repo layout, risks
- `docs/research/notes-own-pipeline-reuse-inventory.md`: TH/KKND/retrokit tool inventory (Q1-Q8), in-place vs full rebuild, effort estimates
- `docs/research/notes-decompwtf-rea-ghidra-ida.md`: decomp.wtf fork-mode contract and guardrail gaps (section 6), Ghidra loaders
- `docs/research/notes-automation-loops.md`: Nigel contract, `/goal` limits, driver composition
- `docs/research/notes-progress-reporting-recompfyi.md`: progress outputs, objdiff report shape, recomp.fyi ingestion
- `docs/research/notes-repo-infra-docker-standards.md`: configure.py/ninja precedent, cflags table, gitignore precedents
- Repo code: `tools/reverseapoc/{le,targets,ingest,cli}.py`, `configure.py`, `docker/Dockerfile`, `docker/compose.yaml`, `.github/workflows/ci.yml`, `.gitignore`, `tests/test_le_real.py`

---
*Architecture research for: byte-matching decompilation of Watcom 10.x DOS/4GW LE executables*
*Researched: 2026-10-19*
