# Feature Research

**Domain:** Byte-matching decompilation pipeline for a 1997 DOS/4GW Watcom 10.x LE game (X-COM: Apocalypse, UFO2P.EXE / TACP.EXE). Scope is the rest of Milestone 1: Phases 3-6.
**Researched:** 2026-10-19
**Confidence:** MEDIUM-HIGH. Every claim comes from the project's own research notes. Those notes cite primary sources (repos, blogs, docs) that were read on 2026-10-19, but none of the reference tooling has been run against UFO2P/TACP. Effort figures are the notes' estimates, not measurements.

**Source restriction:** this file uses local sources only: `docs/research/*`, `docs/workflow.md`, the design spec, `docs/toolchain.md` and the repo. No web lookups. Phase numbers match `docs/workflow.md` and ROADMAP.md (1-6).

**Users of this pipeline:** (1) the owner, working by hand from Phase 5 on; (2) the unattended per-function agent driver from Phase 6 on; (3) OpenApoc developers who read matched C; (4) outside observers who look at progress and directory listings. "Table stakes" means a pipeline that lacks the feature is not a credible matching decomp, or cannot pass its phase gate.

---

## Feature Landscape

### Table Stakes (Users Expect These)

The ID prefixes are for requirements mapping: **RT** round trip (Phase 3), **CID** compiler identification (Phase 4), **SPL** split and first matches (Phase 5), **RPT** reporting (Phase 6), **AGT** agent pilot (Phase 6).

#### Phase 3: Byte-identical round trip
Gate (`docs/workflow.md`): `cmp`/SHA-1 identical for UFO2P.EXE and TACP.EXE. Spike: iterated pages and fixup edge cases on the real files.

| ID | Feature | Why Expected | Complexity | Notes |
|----|---------|--------------|------------|-------|
| RT-01 | **Rebuild from decomposed parts, not from a file copy.** The writer reassembles each EXE from (a) the untouched prefix, meaning the 217,764-byte bound DOS/4GW Pro blob, the MZ stub, the LE header and the loader and fixup tables, and (b) per-object images re-paged through the LE page map. | A writer that only copies the input passes `cmp` without proving anything. Abahbob's "checksum-matching build of raw bytes first" rule exists to prove that the splice path is right before any C goes in. | LOW-MEDIUM | KKND `build_kknd.py` does `out = bytearray(le.data)` and then overwrites page bytes per object (notes-own-pipeline-reuse-inventory.md Q2/Q4). Make the Phase 3 test go through object images (VA to file offset through the page map) so that Phase 5 reuses the same path. About 1.5-3 days (reuse inventory Q8 row 1). |
| RT-02 | **In-place page splice API**, `splice(exe, va, bytes)`. It writes into a copy of the original and refuses any write outside page data (header, fixup tables and blob are read-only) and any write that would change the file length. | This is the Phase 5 and 6 done-gate primitive. It is byte-identical by construction for unmatched bytes. | LOW | It replaces a full LE rewrite in the MVP (spec decision "In-place page splice"). It only holds while a matched function is exactly the original size, so the splice must check that. |
| RT-03 | **Whole-EXE SHA-1 gate for both targets** against `config/targets.toml`, exposed as a CLI verb and a ninja target, and run inside the container. | This is the project's definition of done (CLAUDE.md "Done gate"). Theme Hospital ends with `cmp`, KKND with SHA-1. | LOW | The manifest already exists (Phase 2). The gate reads it and never writes it (hard rule). Two-EXE orchestration is new work: KKND handles one EXE (reuse inventory Q2). |
| RT-04 | **Negative tests: the oracle can say no.** A synthetic LE fixture (no game bytes) with a one-byte mutation must fail the gate, and the failure must name the object, page and offset that differ. | An oracle that cannot fail is not an oracle. The research's main lesson is that agents game verifiers that are weak or silent (Lewis, Macabeus). | LOW | pytest, TDD (`.claude/rules/tools.md`). Real-file tests stay skip-unless-`orig/` (existing pattern in `tests/test_le_real.py`). |
| RT-05 | **LE edge-case coverage on the real files** (the Phase 3 spike): iterated or zero pages, non-internal fixups, fixups that straddle a page boundary, the last partial page, and object vsize beyond the page data (BSS in obj2). | KKND's and Theme Hospital's readers both raise `NotImplementedError` on these (reuse inventory Q4/Q8 risks). | LOW (likely de-risked) | **Phase 2 already narrowed this.** `tools/reverseapoc/le.py` raises `LEUnsupportedError` on iterated, zero and invalid pages and on imported, entry, additive and chained fixups. `tests/test_le_real.py` loads both real EXEs flat and parses every fixup without raising. Inference (MEDIUM): neither EXE uses those features. The spike should confirm this explicitly and cover page-straddling fixups (le.py already detects conflicting duplicates) and BSS. |

#### Phase 4: Compiler identification
Gate: version and default flags recorded in `docs/toolchain.md`, with runtime modules matching byte for byte. Spike: wibo 1.2.0 runs `wcc386.exe` for each version in Docker.

| ID | Feature | Why Expected | Complexity | Notes |
|----|---------|--------------|------------|-------|
| CID-01 | **Run the original `BINNT\wcc386.exe` under wibo 1.2.0 in Docker**, separately for each owner-supplied version (10.5, 10.6, 11.0). The compiler is mounted read-only from `third_party/watcom/`. | Every Watcom matching decomp that matches uses the real period compiler. KKND had to patch Open Watcom because it did not (toolchain.md "Compiler"). | MEDIUM | Known traps: wibo older than 1.2.0 fails with "Unhandled function LocalAlloc". Watcom treats `/` as an option switch and splits paths on spaces, so decomp.me rewrites `/` to `\` and KKND uses relative `build/tmp` paths. On the 10.5 CD, `BINW/WCC386.EXE` is a damaged 64 KiB stub (notes-target-binary-and-toolchain.md). The BINNT binaries also run natively on Windows for debugging. |
| CID-02 | **A compiler wrapper keyed by `compiler@version`**, plus a per-file flags table (`config/cflags.txt`, glob to compiler@version plus flags). | Modules can mix versions: Theme Hospital used 10.0a for some CRT modules. UFO2P (`ufo24`) and TACP (`tac4`) may use different flags. | LOW-MEDIUM | Adapt Theme Hospital `cc.py` (131 lines, GPLv3, "nearly as-is") (reuse inventory Q1). Phase 5's `configure.py` consumes the table. |
| CID-03 | **mosura codegen probe.** Compile the 5-construct probe (byte compare, counted loop, small switch, `x/7`, `x/10u`) with each version and search for the resulting idioms in both code objects. | It is the only cheap way to tell 10.5/10.6 from 11.0. The `1988-1995` banner excludes only 10.0/10.0a. | MEDIUM | 10.5 and 10.6 give byte-identical probe output (156 bytes). 11.0 branches instead of `sete al; and eax,0FFh` and puts loop bounds in `ecx`, not `ebx`. Open Watcom emits `movzx`. Local whole-file counts (33/61 `and eax,0FFh` vs 1/1 `movzx`) already point to classic 10.x (toolchain.md). |
| CID-04 | **Library match of the linked runtime.** Masked-byte matching of CLIB3R/MATH3R modules from each version's `LIB386` against both code objects, NHL95PC/KKND style. | This is the second leg of the gate ("runtime modules match byte-for-byte"), and it is the strongest version evidence. | MEDIUM | Needs an OMF/.LIB reader: Theme Hospital `omf2elf.library_module` or KKND `omf.py` with `lib_match.py` (115 lines, CC0, "as-is"). It also labels runtime functions with real names and boundaries, which gives Phase 5's split and Phase 6's scorer their cheapest wins. Theme Hospital counted 79 Watcom runtime functions among its 2,938 (reuse inventory Q1). |
| CID-05 | **Default-flag discovery with per-flag evidence**, recorded in `docs/toolchain.md` and the `matching.md` table. | The gate needs "default flags recorded". Without flags, no Phase 5 match is possible. | MEDIUM-HIGH | Evidence patterns from KKND: no stack-check call in prologues means `-s`; 16-byte zero fill between functions means `-zm`; `and eax,0xff` rather than `movzx` means `-5r`. NHL95PC inferred `-5r` from instruction statistics. `-zp` packing affects every struct. Candidate grid from toolchain.md: `-5r`/`-4r`, `-s`, an `-o*` subset, `-zp1`/`-zp4`. |
| CID-06 | **C vs C++ confirmation scan**: vtables in obj2, `__wcpp_` routines in obj1, XI/YI static-init segments. | It decides between `wcc386` and `wpp386`, and the two generate different code for the same source (Theme Hospital). | LOW | The kickoff report places it in compiler identification. toolchain.md says "Phase 5". It is cheap, so run it with CID-03/04. |

#### Phase 5: Split and first matches
Gate: one function per EXE compiles, matches (relocations checked), splices back, whole EXE still identical, and objdiff shows 100%. Spike: objdiff diffs OMF-converted ELF cleanly, which decides hybrid vs fallback.

| ID | Feature | Why Expected | Complexity | Notes |
|----|---------|--------------|------------|-------|
| SPL-01 | **Function discovery** with Ghidra 12.1.4, one LE loader (lastonesky ghidra-lx-loader v12.1.4-1 or retrokit) and the Watcom cspec, in WSL2. Output: `config/<exe>/functions.csv`. | No symbols come for free: there is no debug info and the non-resident name table is empty. Every later step needs boundaries. | MEDIUM-HIGH | Use one loader per Ghidra install. Neither loader has been tested on these EXEs. "A wrong convention makes every recovered signature systematically wrong" (lastonesky). retrokit's size field is a Ghidra body count, so a `ghidra2functions` adapter (about 100-200 lines) is needed to get contiguous, padding-trimmed ranges (reuse inventory Q3/Q6). About 2.5-4 days. |
| SPL-02 | **Independent discovery cross-check**: KKND `find_functions.py`-style capstone recursive descent seeded from the entry point, data-to-code fixups and immediates, reading switch tables through fixups, scanning gaps and trimming padding. Diff its list against Ghidra's. | "A boundary error between Ghidra and capstone breaks the splice size check" (reuse inventory Q8 risks). In-place splicing depends on exact sizes. | MEDIUM | `find_functions.py` (193 lines, CC0, "nearly as-is"). Reconciling the two lists is budgeted time, not a one-off. |
| SPL-03 | **Unit split and per-EXE config**: `config/{ufo2p,tacp}/{functions,symbols,splits}.csv`, with functions grouped into translation units. Sources go in `src/ufo2p/`, `src/tacp/` and `src/common/`. | objdiff and decomp.wtf both work per unit. Splice ranges come from these files. | MEDIUM | KKND `gen_units.py` groups by `__FILE__` strings. This game embeds only `source\grafix.c` and `source/pixlpath.c` (toolchain.md), so unit boundaries need other heuristics (gaps, `-zm` alignment, call clustering). This is an open design point. |
| SPL-04 | **Stub convention for unmatched functions** (an `INCLUDE_ASM` equivalent). The build keeps original bytes for every function that is not yet in C. | Every matching decomp needs it, because the EXE must stay identical while 99% of it is still unmatched. | MEDIUM | KKND's `INCLUDE_ASM` expands to `extern int INCLUDE_ASM_##name`, and the splice keeps the original bytes. decomp.wtf fork mode expects GNU-asm `INCLUDE_ASM`, which is the Phase 6 spike (spec "Also open"). Choose a convention that works for both. |
| SPL-05 | **`asm/` generated from `orig/` by script** (per-function Intel-syntax `.s` with symbolic operands, as a reading aid), gitignored. | Humans and agents need the target listing, and committing disassembly is forbidden. | LOW | KKND `split.py` (129 lines, "as-is"): "the build does not assemble it". Same pattern as Macabeus's Klonoa setup (kickoff report, repository layout). |
| SPL-06 | **Compile path**: `configure.py` writes `build.ninja` (wcc386 under wibo per `cflags.txt`, then OMF output, then `omf2elf`), `objdiff.json` and `compile_commands.json`. | It is the standard shape of current matching decomps (Theme Hospital, bw1-decomp), and decomp.wtf fork mode requires `configure.py` + ninja + `objdiff.json`. | LOW-MEDIUM | `configure.py` already exists as a Phase 2 skeleton with verification targets only. Adapt Theme Hospital `configure.py` (177 lines) and a slimmed `project.py`. |
| SPL-07 | **OMF to ELF32 converter** (`omf2elf.py`, Theme Hospital, GPLv3), covering COMDAT, LIDATA, FIXUPP threads, BAKPAT and CEXTDEF, with pytest. | objdiff cannot read OMF: issue #97 has been open since 2024-08-19 and v3.8.2 reads ELF and COFF only. | LOW (copy) | About 1 day including tests (reuse inventory Q5). This is why `tools/` is GPLv3. A permissive rewrite would take 3-5 days and is not needed. |
| SPL-08 | **Target ELF objects cut from the LE**, with relocations rebuilt from LE fixups: absolute fixups become R_386_32, rel32 branches that leave the section become R_386_PC32, and inline Watcom switch tables in code are treated as data. | objdiff diffs a *base* object (ours) against a *target* object (the original), so the target must exist as ELF. | MEDIUM-HIGH | Adapt Theme Hospital `split.py` (295 lines) and `x86scan.py` (129 lines). About 2-4 days. The Phase 5 spike decides whether objdiff reads these cleanly (symbol sizes, section names, FLAT-group fixups). |
| SPL-09 | **Extra relocation check** beyond objdiff: every non-relocated byte identical, equal length, every `call rel32` hits the same function, every absolute fixup resolves to the original LE fixup target, and local-segment data references (string literals) are rejected and moved to an extern `D_` symbol. | "objdiff compares at most one relocation per x86 instruction", so a 100% score alone is not enough. "A scratch match alone is never enough" (KKND). | MEDIUM | Theme Hospital `elfrelocs.py`/`verify.py` (93/38 lines, as-is) plus KKND's `build_kknd.py` rules (`docs/matching.md` "Relocation rules"). |
| SPL-10 | **Fixup-site handling on splice**: write the original link-time value at each fixup site *after* its target has been checked, not the compiled object's placeholder. | Without it the spliced EXE differs at every relocated field, even for a perfect match. | LOW-MEDIUM | This is KKND's behaviour: "Relocated fields keep the original link-time value after the relocation *target* has been checked" (reuse inventory Q2). Builds on RT-02. |
| SPL-11 | **Single-unit check tool** (`check`): build one file's unit in a temp dir and print the match per function (objdiff % plus reloc check plus splice SHA-1). Safe to run next to ninja. | It is the human inner loop now and the agent's `verify_command` in Phase 6. | LOW-MEDIUM | Adapt Theme Hospital `check.py` (94 lines) or KKND `match.py` (190 lines). Keep the output terse and the error messages unambiguous: "ambiguous tool errors caused rabbit holes" (Lewis, notes-automation-loops.md Q5). |
| SPL-12 | **C89 lint gate**: `clang -fsyntax-only -std=gnu89 -Werror=declaration-after-statement` against a compat header (empty `__far`, `__near`, `__watcall` and so on, plus `-D__386__ -D__FLAT__` and a `__WATCOMC__` value), run from `compile_commands.json`. | Mid-block declarations are the most common LLM mistake on C89 targets (Macabeus, Lewis). | LOW | It is already a stated rule in `.claude/rules/src.md`. The compat header path and the `__WATCOMC__` value are decided in this phase (spec "Also open"). |
| SPL-13 | **First matches, one per EXE**, done by hand. Each is committed as one function per commit and recorded in `docs/matching.md` (flags, idioms, evidence). | This is the gate. It also proves that the whole chain (compile, convert, diff, reloc check, splice, SHA-1) works end to end on real code. | MEDIUM (unknown) | Pick tiny, leaf, runtime-adjacent or UFO2P/TACP twin functions first. Use `func_XXXXXXXX` naming (coding-style.md). |

#### Phase 6: Reporting and agent pilot
Gate: mosaic and badge live; 10 easy functions matched unattended with zero regressions and the EXE identical; recomp.fyi and decomphub submissions done. Spike: decomp.wtf fork mode accepts the repo's stub convention.

| ID | Feature | Why Expected | Complexity | Notes |
|----|---------|--------------|------------|-------|
| RPT-01 | **Committed per-function status source of truth** (module, function, address, size, status in matched / partial / unmatched), written only by the local gate. | **CI cannot run the oracle.** Game files and the compiler are never in git, images or CI, so progress must come from committed data that the local SHA-1 gate already proved. | LOW-MEDIUM | KKND's `make_report.py` counts a function "defined in C" as matched "because the build gate refuses anything else" (reuse inventory Q2). This is a design consequence of the hard rules that is easy to miss. |
| RPT-02 | **`progress.py` (stdlib only)** writes `progress.json` (totals, per-module counts, git SHA, timestamp), `progress.svg` (squarified treemap with one cell per function, grouped by module, sized by bytes, green/amber/gray) and a shields endpoint JSON. | decomp.dev closed to new projects on 2026-10-15 and recomp.fyi renders no badge, so progress has to be self-hosted (notes-progress-reporting-recompfyi.md §2/§5). | LOW-MEDIUM | Write it from scratch (about 100 lines for the treemap). AnyPS5's renderer is GPL-2.0 and its input stage does not apply here. Partial (amber) cells are shown but never counted in the percentage. |
| RPT-03 | **Pages workflow**: on push to `main`, with `paths` filters, a concurrency group and `pages: write, id-token: write`, run `upload-pages-artifact` then `deploy-pages`, and redeploy only when `progress.json` changed. | This is the pattern AnyPS5 and sa3 use. | LOW | Pages needs a **public** repo, or a paid plan for a private one (kickoff report). The README embeds the SVG and badge with a footnote that defines the metric (AnyPS5). |
| RPT-04 | **objdiff-shaped `report.json`** uploaded as a `<VERSION>_report` Actions artifact from the default branch, built from the committed status. | recomp.fyi reads decomp percentages daily from that artifact. Without it the row shows no percentage. | LOW-MEDIUM | Proto fields: `measures.{total_code, matched_code, matched_code_percent, total_functions, matched_functions}`, `units[].functions[].{name, size, fuzzy_match_percent}`. **Unverified:** whether recomp.fyi accepts a hand-built report, and how strictly it parses the artifact name (progress notes §3/§5). With two EXEs, a figure shows only if one matches `original` or the two agree within half a point. |
| RPT-05 | **Directory listings**: update `.recomp.json` (it exists; status is `exploring`, so move it to `in-progress` and add a Progress link) and submit to decomphub.com through its reviewed form once the repo is public. | Visibility in the directories that are still open (spec decision, [Owner]). | LOW | `.recomp.json` already uses "Watcom C/C++ 10.x" and "DOS/4GW", not "Open Watcom", as the kickoff report advised. It must stay under about 8 KB and must not mention where to get game files (progress notes §5). |
| AGT-01 | **Per-function driver**: the candidate source (scorer) yields F, the driver runs one fresh `claude -p "/goal …"` session on F, then the driver itself re-runs compile, objdiff, reloc check, splice and SHA-1, and then commits (one function per commit) or resets. | This is the design behind every documented AI decomp success (Lewis's one-shot loop and Nigel). `/goal`'s evaluator "does not call tools", so its verdict is only a hint. | MEDIUM | Evaluate Nigel first. Its `candidate_source`, `verify_command`, `success_command` and `reset_command` map almost 1:1 onto this loop, but it is a Go binary that needs a build step. The alternative is about 200 lines of Python (spec, notes-automation-loops.md Q5/Q9). |
| AGT-02 | **Attempt cap and re-queue**: 3-5 attempts per function per pass. A function that hits the cap goes to a difficult list and is re-queued once more of its neighbours, structs and callees match. Partial results are kept as notes, never committed as matches. | Mizuchi: nearly half of AI matches came on attempt 1, and after attempt 3 the conditional chance fell to about a quarter. Lewis's cap of 30 attempts was expensive in the tail. | LOW | KKND keeps `tools/difficult_functions` and Lewis a `difficult_functions` log. |
| AGT-03 | **Tri-state outcome record per attempt** (MATCHED / PARTIAL / GAVE_UP, plus turns, tokens, wall time and the verifier output) in a file the driver reads. | Ralph's single promise string cannot express the outcome, and the retrospective and any audit need the logs (automation notes Q3/Q9). | LOW | The driver trusts only its own re-verification for MATCHED. |
| AGT-04 | **Usage-limit and failure backoff**: detect non-zero exits and auth or credit errors (on which `/goal` clears), sleep and retry (Lewis checks every 5 minutes), cap functions per night, and give each call a timeout. | "An unattended Opus task could burn through the Claude 20x Max plan in a matter of days" (Lewis). | LOW-MEDIUM | Nigel has `timeout` and `--time-limit`. A Python driver needs its own. |
| AGT-05 | **Guardrail hooks** (Claude Code PreToolUse) that block: edits under `orig/`; edits to hash manifests (`config/targets.toml`, `*.sha1`); edits to build and verify scripts during a matching session; inline asm (`_asm`, `__asm`, code-emitting `#pragma aux` bodies) in `src/`; builds that bypass the verify script; edits to `asm/` and `build/`. | Agents have gamed verifiers: one rewrote a SHA-1, one worked around a blocked `make` by running its contents, one wrote a Python script to edit a forbidden file (Lewis), and one forked its compiler (Macabeus). Prose rules are not enough. | MEDIUM | The block table is in `docs/workflow.md` "Hooks". Hooks must also catch **indirect** writes (Bash, Python one-liners), not only Edit/Write. Calling-convention pragmas stay allowed. decomp.wtf fork mode's `_CHEAT` filter does not ban `#pragma`, so our hook is the only `#pragma aux` guard (decompwtf notes §6). |
| AGT-06 | **Zero-regression gate**: after every commit, all previously matched functions still match and both EXEs are still SHA-1 identical. A change that breaks an existing match is undone automatically. | This is in the Phase 6 gate wording. decomp.wtf: "A change that breaks any function that already matched is undone". | LOW-MEDIUM | It is cheap with in-place splicing: rebuild everything, then SHA-1. |
| AGT-07 | **Easiest-first scorer**: KKND `score_functions.py` (71 lines, as-is) or Lewis's first formula `instruction_count + 3×branch + 2×jump + 2×label`, with the driver, not the agent, picking the function. | Driver-chosen cheapest-first is token-efficient (Lewis). Easy functions build up callees, and 62.7% of calls flow from higher- to lower-complexity functions. | LOW | Library-matched runtime functions (CID-04) and trivial families come off the queue first. The scorer's design is left to this phase (spec "What is left to the builder"). |
| AGT-08 | **Per-function context pack**: target asm, callers and callees (with signatures), shared headers, a Ghidra draft, the relevant `matching.md` and `learnings.md` sections, and notes from earlier attempts. | It is the input contract of both Lewis's and Macabeus's loops. "Avoid unrequested context" (Lewis): give only what helps. | MEDIUM | The data comes from SPL-01/05 and GhidraMCP. decomp.wtf's `get_function` and `get_context` MCP tools already shape it in fork mode. |
| AGT-09 | **`watcom-decomp` project skill**: calling convention (`__watcall`, `name_` and `_name` symbols), recorded flags, C89 rules, `#pragma aux` policy, how to read objdiff output on OMF-converted objects, and the relocation rules. | No marketplace skill covers Watcom or DOS/4GW. The kickoff report ranks this skill, CLAUDE.md and the hooks above any plugin. | LOW-MEDIUM, and it grows | Seed it from `docs/matching.md` and `docs/coding-style.md`. decomp.wtf's x86 guide is MSVC-only, so a `watcom.md` guide is needed for fork mode too. |
| AGT-10 | **decomp.wtf v0.10.6 fork mode in WSL2**, pinned and run as a subprocess (MIT, never imported), with light patches: the stub convention, a Watcom guide, disabling the dtk-specific "linked" logic, and accepting that autopilot is unavailable (it needs m2c, which has no x86). | It is the owner's hybrid decision. It provides claims, MCP tools, a dashboard and undo on regression for about 3-7 extra days, against 12-24 days to build them (decompwtf notes §6). | MEDIUM | **Conditional:** only if the Phase 5 objdiff spike passes. Otherwise the fallback is the own pipeline plus a minimal agent layer (MCP, claims, guardrails, Claude Code only), about 5-9 days. It is archived with no upstream, so pin the commit. |

### Differentiators (Competitive Advantage)

These line up with the Core Value (a deterministic oracle proves every match) and with the project's purpose (documenting the engine for OpenApoc). None is needed to pass a Milestone 1 gate unless the "Phase" column says so.

| Feature | Value Proposition | Complexity | Phase | Notes |
|---------|-------------------|------------|-------|-------|
| **UFO2P to TACP twin matching**: exact buckets of normalized-asm hashes first, then opcode-sequence bounded Levenshtein, coddog-style, reimplemented in Python | "ReverseApoc has a structural advantage the N64 projects lacked: two executables built from one engine by one compiler" (kickoff report, Conclusion). A match in `ufo24` can seed its twin in `tac4`. The report calls this "the most valuable thing to build after Phase 4" | MEDIUM | 6 (scorer input); the asm-normalization data foundation in 5 | coddog's x86 support is unverified, so reimplement it. Normalization (strip addresses, relabel jumps, mask immediates) matters more than the algorithm (notes-vector-retrieval-bsim.md) |
| **Similarity-first scheduling**, switched on once enough functions match | Lewis: ordering by similarity to matched functions beat difficulty ordering in the long tail. Coddog and his composite score disagreed on the top candidate 90.6% of the time | MEDIUM | After the pilot (v1.x) | The pilot needs only easiest-first. Lay out the scorer interface so it can be swapped |
| **Library-match-first clearing of the Watcom runtime** | Clears a share of both code objects with real names before any agent writes C, and supplies ground-truth names for callers | LOW (on top of CID-04) | 4 to 6 | Theme Hospital had 79 runtime-library functions out of 2,938 |
| **Trivial-family auto-matcher** (return-constant functions, forwarders), keeping only verified results | Cheap and deterministic, so it saves agent tokens. Lewis's m2c pre-pass matched only 0.93% and was still "cheaper than spending agent tokens" | LOW | 6 | KKND `auto_families.py` (141 lines, CC0, as-is) |
| **Name evidence from diagnostic strings** (`Name(): ...` and source-file strings) | Real names, not `func_XXXXXXXX`, is what OpenApoc readers need | LOW | 5 to 6 | KKND `name_evidence.py` (68 lines) |
| **Mismatch diagnostics** that classify why a function differs (register allocation, branch layout, stack-slot order, relocation target) | "Defensive tooling with clear errors beat prompt engineering" (Lewis). Lewis later added mismatch classification in N64 Decomp Workbench | MEDIUM | 5 to 6 | It grows out of SPL-09/11 output |
| **Source-variant beam search** (Theme Hospital `variants.py`: operand swaps, declaration order, `op=`, types, if/else) scored by objdiff | "The strongest single accelerator" for near misses (reuse inventory Q7). It is deterministic, and its rewrites stay plausible C, unlike the permuter | MEDIUM | After the pilot | GPLv3, which is compatible. Treat it with the permuter's caution: use it only near 100% and never let it produce shapes a 1997 developer would not write |
| **Searchable learnings journal** (KKND `learn.py`) fed into the context pack | Lewis: the shared `DECOMPILATION_LEARNINGS.md` improved later attempts | LOW | 6 | `docs/learnings.md` and `docs/matching.md` already exist |
| **Human-approved retrospective outer loop** (nightly or every N functions, it proposes diffs to CLAUDE.md, learnings, scorer weights and tool error messages, and never to the verifier) | It captures the levers that worked for Lewis (scheduler switch, tool fixes, learnings) without the harness-rewrite risk of Bilevel | LOW | After the pilot | Needs logs from a few hundred attempts first (automation notes Q9 D') |
| **Comment pass for OpenApoc readers** (a game-terms summary per function, `BUG(original):` notes, `NOTE(match):` notes, struct offset and size comments that respect `-zp`) | It is the project's reason to exist ("the most trustworthy source" for logic, mechanics, bugs and AI) | LOW per function | 5 onward, as a separate batched loop | Edits limited to comments and names (ceremonies.md). "Split the goal": match first, quality second (Macabeus) |
| **CD v1.00 build as a second, cross-reference target** | OpenApoc's offsets and `FUN_` addresses describe the CD build. A build-to-build diff (same compiler, small source delta) is free matching evidence | LOW (the round trip is generic) to MEDIUM | 3 (round trip), later (matching) | Already recorded under `[[cd_builds]]`. The owner revisits which build is primary after Phase 5 |
| **Dual-loader and dual-discovery cross-check report** | Function boundaries are proven, not trusted, which matches the oracle-first ethos | LOW (on top of SPL-02) | 5 | |
| **Transparent AI-use record** (per-attempt logs, AI-use statement in `docs/legal.md`, never flooding decomp.me with agent scratches) | decomp.wtf was archived and decomp.dev closed, both citing AI-driven behaviour. Openness is the mitigation in the risk table | LOW | 6 | Attempt logs come from AGT-03 at no extra cost |
| **Parallel agents** (decomp.wtf claims, or Nigel `--shard` over git worktrees) | Throughput. Lewis ran 3-4 worktrees | MEDIUM | After the pilot | Worktrees drifted and syncing could take more than an hour (Lewis, 84-days post). The 10-function pilot does not need it |

### Anti-Features (Commonly Requested, Often Problematic)

This section includes the design spec's **anti-goals** (things the project must actively avoid) and **non-goals** (out of scope for Milestone 1), plus tool and pattern choices the research rejected.

#### From the design spec

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Playable port** (platform layer, SDL, "just fix this while we are here") [anti-goal, Owner] | People want to play the game | It is not the project. It competes with OpenApoc, which ReverseApoc serves | Document behaviour for OpenApoc. Mark original bugs `BUG(original):` and never fix them in matched code |
| **Modern C++ rewrite / modernizing matched C** [anti-goal, Default] | Readability, "best practice" | Any change of shape changes Watcom's codegen and breaks the match. cpp-pro and Mindrally-style skills push C++11-23 idioms | C89 for `wcc386`. Allowed edits to matched code are comments, names and build-proven-neutral formatting |
| **Committing game bytes** (EXEs, assets, disassembly, compiler binaries) in git, image layers or issues [anti-goal, Owner] | Convenience for contributors and CI | Legal exposure, and it breaks the bring-your-own-files model | `orig/` and `third_party/watcom/` are gitignored and mounted read-only. `asm/` is regenerated by script. CI works from committed status data only (RPT-01) |
| **Agents judging their own matches; agents editing `orig/`, manifests or build scripts** [anti-goal, Default] | Simpler loop, fewer moving parts | This caused every documented failure: false match claims, a rewritten SHA-1, a forked compiler | The driver re-verifies (AGT-01), hooks block the edits (AGT-05), and the zero-regression gate catches the rest (AGT-06) |
| **Win9x release, SMKP.EXE, XCOMAPOC.EXE, SETUP.EXE** [non-goals for Milestone 1] | Completeness | SMKP has a different DOS/4GW blob, XCOMAPOC is 16-bit, SETUP is Borland. Each one dilutes Milestone 1 | Only UFO2P.EXE and TACP.EXE (installed build). SMKP comes in a later milestone |
| **Competing with or replacing OpenApoc** [non-goal] | Visibility | Splits a small community | Serve OpenApoc: credit its RE and coordinate on the build question |
| **Claiming "first Watcom / X-COM decomp"** [non-goal] | Marketing | Not verifiable | Say "the closest found" |
| **IDA** [Owner/Default] | Familiar tool | IDA Free lists only PE, ELF and Mach-O, its decompiler is cloud-only, it has no IDAPython, and ida-pro-mcp does not support it | Ghidra 12.1.4 with an LE loader and GhidraMCP |

#### From the research (tools and patterns)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Full LE rewrite / relinkable or shiftable build** in Milestone 1 (Theme Hospital `lewrite.py` and `relink.py`; `wlink` `link.py`) | "Real" rebuild, mods | About 10-20+ days. Theme Hospital constants are hardcoded (`CODE_BASE`, `DATA_VSIZE`, linker filler table). It is not needed while matched sizes equal the originals | In-place splice (RT-02). Revisit only if a later milestone needs shiftable builds |
| **Unbinding DOS/4GW** (`sb /u`) or regenerating the extender or stub | "Clean" LE for tools | Extra failure modes (VOGONS reports broken output). KKND and both LX loaders handle the bound file | Treat the 217,764-byte blob and the headers as opaque, read-only bytes |
| **Matching with Open Watcom / patching OW `wcc386`** (the KKND route) | Freely redistributable compiler | "No flag tested fixes" its jump threading and loop layout. KKND's patch is 506 lines | Real Watcom 10.x under wibo. OW v2 only for `wdis`, `wlink` and `wlib` |
| **Baking the Watcom compiler into the Docker image** or auto-downloading it by default | One-command setup | Proprietary, with the IP owner unverified | User-supplied and read-only mounted. An opt-in fetch script at most |
| **Inline asm or asm stand-ins counted as matches** (Theme Hospital has 53 `*.standin.s` among its "100%") | Reaching 100% faster | It breaks the "matching must come from C" rule (CLAUDE.md), and the result documents nothing for OpenApoc | A function that cannot be matched in C stays an `INCLUDE_ASM`-style stub and counts as unmatched |
| **decomp-permuter / random source mutation** | Closes near misses | No x86 support. Lewis removed it for "odd code, overfitting and doom loops" | Deterministic `variants.py`-style search near 100% only (differentiator), or a human |
| **m2c drafts** | Standard in N64/GBA decomps | No x86 backend, which is also why decomp.wtf's autopilot is unavailable in fork mode | Ghidra drafts (decomp.wtf fork mode runs Ghidra on the ELF target object) |
| **Ralph Loop as the driver** | One-line setup | Context grows in one session, it has a single exact-match promise, its only cost control is iterations, and the bash hook breaks on Windows when WSL `bash` comes first on PATH | Fresh `claude -p "/goal …"` per function (AGT-01). Ralph only for a 5-10 function prototype |
| **Bilevel or autoresearch outer loop that rewrites the harness or search code** | "Self-improving" pipeline | A noisy n=3 result with no cost data, and it widens the reward-hacking surface (cf. the SHA-1 incident) | Human-approved retrospective that never touches the verifier (differentiator) |
| **Agent picks its own function** | Less driver code | Token-inefficient (Lewis). Agents choose what is fun, not what is cheap | Scorer-driven candidate source (AGT-07) |
| **Grinding 30+ attempts per function** | "It eventually matches" | The 85th percentile of successes was at attempt 28, and `--repeat 3` helped only the extreme tail at high token cost | A 3-5 cap with re-queue (AGT-02) |
| **Building decomp.wtf's from-scratch "dos-watcom" platform** | Full integration | About 16-27 days. Its ROM matcher hard-codes `R_MIPS_*` and 4-byte words, and there is no platform registry | Fork mode on our repo (AGT-10), or a minimal own agent layer as the fallback |
| **Building a full agent layer with GUI and dashboard in Milestone 1** | Parity with decomp.wtf | 12-24 days | Fork mode provides it, or use a static report plus a Claude-Code-only `claude -p` driver |
| **decomp.dev registration / frogress** | The community-standard progress hub | decomp.dev is closed to new projects. frogress needs an admin-issued key | Self-hosted Pages progress (RPT-02/03) |
| **Embeddings / vector DB retrieval** (jina, Voyage, pgvector, RxDB) in Milestone 1 | Mizuchi uses it | The corpus is a few thousand functions, and Lewis dropped embeddings for exact opcode similarity | Opcode Levenshtein and twin hashing first. SQLite plus numpy later if needed |
| **BSim** | Built into Ghidra | No turnkey headless whole-program search, and its hashed features do not fit cosine retrieval | Own similarity script |
| **Restructuring reviewers on matched C** (`/simplify`, code-simplifier, thermo-nuclear, Ponytail, clang-tidy modernize-*) | Code quality | Any shape change breaks the match | Use them on Python tooling only. On C, run only the comment pass (ceremonies.md) |
| **Data, rodata or string-literal placement matching** in Milestone 1 | "Complete" matching | Theme Hospital needed `config/sections.txt` and days of work | Reject local-segment references and move strings to an extern `D_` symbol (SPL-09) |
| **GPU fine-tuning of a decomp model** | Faster agents | There is no training data at zero matches, and no documented decomp loop needed it | Hosted models and CPU tools only |
| **Mass decomp.me scratch submission by agents** | Free compiler sandbox | Community stance against AI floods (decomp.wtf archive reason) | Use decomp.me sparingly for human flag-hunting in Phase 4 |

---

## Feature Dependencies

```
[Phase 2 done: LE parser, hash manifest, container]
    └──> RT-01 rebuild-from-parts ──> RT-02 splice API ──> RT-03 SHA-1 gate (both EXEs)
                                          │                    └──> RT-04 negative tests
                                          │
[owner-supplied Watcom 10.5/10.6/11.0]    │
    └──> CID-01 wibo runs wcc386 ──> CID-02 compiler@version wrapper + cflags table
              │                         ├──> CID-03 codegen probe ─┐
              │                         └──> CID-04 library match ─┼──> CID-05 default flags recorded
              │                                (needs OMF/.LIB reader: omf2elf or omf.py)
              │
              └──> SPL-06 configure.py/ninja compile path
                         └──> SPL-07 omf2elf ──┐
SPL-01 Ghidra discovery ──┐                    │
SPL-02 capstone discovery ┴─> SPL-03 units/config ──> SPL-04 stub convention
                                   └──> SPL-08 target ELF from LE ──┤
                                                                    ├──> objdiff 100% (SPIKE: hybrid vs fallback)
                                   SPL-09 reloc check ──────────────┤
                                   SPL-10 fixup-site splice (needs RT-02)
                                                                    └──> SPL-11 check tool ──> SPL-13 first matches
SPL-12 C89 lint ─────────────────────────────────────────────────────────────────────────────┘

SPL-13 + RT-03 ──> RPT-01 committed status ──> RPT-02 progress.py ──> RPT-03 Pages ──> badge/mosaic
                                         └──> RPT-04 report.json artifact ──> RPT-05 recomp.fyi %
SPL-11 (verify_command) + AGT-07 scorer + AGT-08 context pack + AGT-09 skill
    └──> AGT-01 driver ──requires──> AGT-05 hooks, AGT-06 zero-regression gate
             ├──> AGT-02 cap/re-queue, AGT-03 outcome log, AGT-04 backoff
             └──> 10 unattended matches (Phase 6 gate)
AGT-10 decomp.wtf fork mode ──requires──> objdiff spike PASSED (Phase 5) + SPL-04 stub convention accepted (Phase 6 spike)

CID-04 library match ──enhances──> AGT-07 scorer (cheapest wins) and SPL-01 (names, boundaries)
Twin matching ──enhances──> AGT-07 scorer (TACP seeded from UFO2P)
AGT-03 outcome logs ──enhances──> retrospective outer loop
Full LE rewrite ──conflicts──> in-place splice as the done-gate (two oracles that can disagree)
decomp.wtf fork mode ──conflicts──> KKND-style fallback compare (only one is the agent judge; the spike decides)
```

### Dependency Notes

- **Phase 3 is required by Phase 5's gate.** SPL-10 and the "splices back, whole EXE still identical" check reuse RT-02/03 directly. If RT-01 tests only a file copy, the splice path stays unproven until the first real match, which is the worst time to debug page mapping.
- **Phase 4 is required by Phase 5.** No match is possible without the version and the default flags (CID-05). CID-01's wibo spike also de-risks the Phase 5 compile path, because both use the same wrapper.
- **CID-04 needs an OMF reader before Phase 5.** The library match reads `.LIB` OMF modules, so the OMF reader (Theme Hospital `omf2elf.library_module` or KKND `omf.py`) arrives in Phase 4, not Phase 5. Plan for SPL-07 to be partly pulled forward.
- **Discovery is required by everything that follows.** In-place splicing needs exact sizes, so SPL-01 and SPL-02 must agree, or their disagreements must be resolved, before SPL-13.
- **The objdiff spike gates AGT-10.** If objdiff cannot diff the converted ELF cleanly, the hybrid path falls back to the KKND-style compare plus a minimal own agent layer, and RPT-04 (an objdiff-shaped report) has to be hand-built from our own compare results. recomp.fyi acceptance of a hand-built report is unverified either way.
- **RPT-01 is required by RPT-02 to RPT-04,** because CI cannot run the oracle. The status file is the only bridge between the local SHA-1 gate and public progress.
- **AGT-05 and AGT-06 are required by AGT-01.** An unattended driver without hooks and a regression gate repeats the documented failures, so the hooks are part of the pilot, not an add-on.
- **Twin matching enhances the scorer**, but only once SPL-01 and SPL-05 give normalized asm for both EXEs. Build the normalized-asm data in Phase 5 even if the scheduler uses it later.
- **The full LE rewrite conflicts with in-place splicing** in Milestone 1. Two writers would be two oracles that can disagree. Keep one.

---

## MVP Definition

### Launch With (Milestone 1, Phases 3-6 gates)

- [ ] RT-01 to RT-05: rebuild from parts, splice API, SHA-1 gate for both EXEs, negative tests, LE edge-case spike. *Without these, no later match can be trusted.*
- [ ] CID-01 to CID-06: wibo plus wcc386 per version, compiler@version wrapper, probe, library match, flags, C/C++ scan. *Without the compiler and flags there is nothing to match against.*
- [ ] SPL-01 to SPL-13: discovery and cross-check, units, stubs, generated asm, configure/ninja, omf2elf, target ELF, reloc check, fixup-site splice, check tool, C89 lint, and the first match per EXE. *This is the Phase 5 gate.*
- [ ] RPT-01 to RPT-05: committed status, progress.py, Pages, report artifact, listings. *This is the Phase 6 reporting gate.*
- [ ] AGT-01 to AGT-09: driver, cap, outcome log, backoff, hooks, zero-regression gate, easiest-first scorer, context pack, `watcom-decomp` skill. *This is the Phase 6 pilot gate (10 unattended matches).*
- [ ] AGT-10: decomp.wtf fork mode, **only if** the Phase 5 objdiff spike passes. Otherwise the minimal own agent layer replaces it.

### Add After Validation (v1.x, the next milestone)

- [ ] Similarity-first scheduling and UFO2P to TACP twin matching. Trigger: the easiest-first queue's hit rate drops, or about 50+ functions are matched to serve as references.
- [ ] Trivial-family auto-matcher and name-evidence extraction. Trigger: the pilot shows agent tokens going to trivial forwarders.
- [ ] Human-approved retrospective outer loop. Trigger: a few hundred logged attempts.
- [ ] Comment-pass loop on matched functions (batched per module, cheaper model). Trigger: the first module with 10+ matched functions.
- [ ] Parallel agents (claims or `--shard` worktrees). Trigger: the single-agent pilot runs clean for a week with zero regressions.
- [ ] `variants.py`-style beam search for 95%+ near misses. Trigger: the difficult list fills with near misses.
- [ ] Mismatch classification diagnostics.

### Future Consideration (v2+)

- [ ] Full LE rewrite or relinkable build. Defer until someone needs shiftable builds; it stays a documentation project.
- [ ] Data, rodata and string placement matching. Defer: it needs a sections model, which is days of work.
- [ ] CD v1.00 build as a full matching target. Defer until the owner revisits which build is primary after Phase 5.
- [ ] SMKP.EXE. Deferred by the spec (a different DOS/4GW blob).
- [ ] Embedding retrieval (jina v2 base code plus SQLite and numpy). Defer: opcode similarity first.
- [ ] Understand-Anything or Groma onboarding docs. Defer until subsystems are named.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| RT-01/02/03 rebuild-from-parts, splice, SHA-1 gate | HIGH | LOW | P1 |
| RT-04 negative tests | HIGH | LOW | P1 |
| RT-05 LE edge-case spike | MEDIUM (likely de-risked) | LOW | P1 |
| CID-01 wibo plus wcc386 per version | HIGH | MEDIUM | P1 |
| CID-03 probe + CID-04 library match | HIGH | MEDIUM | P1 |
| CID-05 default flags | HIGH | MEDIUM-HIGH | P1 |
| CID-06 C/C++ scan | MEDIUM | LOW | P1 |
| SPL-01/02 discovery and cross-check | HIGH | MEDIUM-HIGH | P1 |
| SPL-07 omf2elf | HIGH | LOW | P1 |
| SPL-08 target ELF from LE | HIGH | MEDIUM-HIGH | P1 |
| SPL-09/10 reloc check, fixup-site splice | HIGH | MEDIUM | P1 |
| SPL-11 check tool | HIGH | LOW-MEDIUM | P1 |
| SPL-12 C89 lint | MEDIUM | LOW | P1 |
| RPT-01/02/03 status, progress, Pages | MEDIUM | LOW-MEDIUM | P1 |
| RPT-04/05 report artifact, listings | MEDIUM | LOW | P1 |
| AGT-01 driver with re-verification | HIGH | MEDIUM | P1 |
| AGT-05/06 hooks, zero-regression gate | HIGH | MEDIUM | P1 |
| AGT-02/03/04 cap, logs, backoff | HIGH | LOW | P1 |
| AGT-07/08/09 scorer, context pack, skill | HIGH | LOW-MEDIUM | P1 |
| AGT-10 decomp.wtf fork mode | MEDIUM | MEDIUM | P1 if the spike passes, otherwise dropped |
| Twin matching / similarity scheduling | HIGH | MEDIUM | P2 |
| Library-first clearing, trivial families, name evidence | MEDIUM | LOW | P2 |
| Comment pass loop | HIGH (for OpenApoc) | LOW | P2 |
| Retrospective outer loop | MEDIUM | LOW | P2 |
| variants.py beam search | MEDIUM | MEDIUM | P3 |
| Parallel agents | MEDIUM | MEDIUM | P3 |
| Full LE rewrite / relink | LOW (for this project) | HIGH | P3 / anti-feature for Milestone 1 |

**Priority key:**
- P1: Must have for the Milestone 1 gates
- P2: Should have, add when possible (mostly the next milestone)
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | KKND-Decomp (CC0) | Theme Hospital decomp (GPLv3) | decomp.wtf v0.10.6 (MIT, archived) | Lewis / Nigel (N64) | ReverseApoc approach |
|---------|-------------------|-------------------------------|------------------------------------|---------------------|----------------------|
| Target | Bound DOS/4GW Pro LE, Watcom 10.0-class | Unbound LE (WSTUB), Watcom 10.6 C++ | MIPS/PPC/ARM from scratch; x86 only in fork mode | N64 MIPS, IDO/GCC | Bound DOS/4GW Pro LE, Watcom 10.6 hypothesis, C |
| Compiler | Patched Open Watcom 2.0 | Real 10.6 + 10.0a under wibo 1.2.0 (Nix) | Pinned period compilers, no Watcom | IDO / KMC GCC | Real 10.x under wibo 1.2.0 in Docker, user-supplied |
| Build | Single `build_kknd.py` gate | `configure.py`, ninja, `cflags.txt` | Own engine; fork mode uses the project's ninja | Makefile + `build-and-verify.sh` | Theme Hospital-style `configure.py` + ninja + `cflags.txt` |
| EXE output | In-place page splice + SHA-1 | Full `lewrite.py --strict` rewrite + `cmp` | Links at the real address (ROM mode) | Full ROM build + SHA-1 | In-place splice + SHA-1 (KKND); full rewrite deferred |
| Per-function diff | Custom: cut from OMF, mask relocs, check targets | objdiff via `omf2elf` + `elfrelocs` check | objdiff (fork) / own matcher (ROM) | asm-differ, objdiff | objdiff via `omf2elf`, plus a KKND-style reloc check; KKND compare is the fallback |
| Discovery | Capstone recursive descent | rizin + rel32 + prologues + demo debug info | splat/spimdisasm | splat | Ghidra + LE loader, cross-checked with capstone |
| Runtime library | `lib_match.py` masked bytes | Demo-identified, 79 functions | n/a | SDK source matching | Library match in Phase 4 (gate evidence and free names) |
| Agent layer | CLAUDE.md, learnings, give-up list, easiest-first scorer | AGENTS.md, `variants.py` | MCP tools, claims, GUI, undo on regression, Ghidra drafts | Scorer, fresh headless session per function, hooks, Nigel, worktrees | Driver + `claude -p "/goal"` + hooks; decomp.wtf fork mode if the spike passes |
| Guardrails | Build gate refuses non-matches | "Done" = report + strict + cmp | C-only sources, inline asm refused, revert on regression (`#pragma` not banned in fork mode) | Hooks block SHA-1 edits, test skipping, off-script builds, generated-file edits | Hooks on `orig/`, manifests, build scripts, inline asm, generated files; driver re-verifies |
| Progress | `make_report.py` to decomp.dev (now closed) | `ninja report` | Dashboard | decomp.dev | Self-hosted Pages treemap + badge + `report.json` artifact for recomp.fyi |
| Non-C matches | n/a | 53 asm stand-ins counted in 100% | Inline asm refused | n/a | Not allowed; stubs stay unmatched |

---

## Sources

All local and read on 2026-10-19. Research notes use the old phase numbers.

- `docs/research/2026-10-19-kickoff-research-report.md`: pipeline shape, the milestone table, the Use/Skip/Later verdicts, the risk table, and the twin-matching conclusion.
- `docs/research/notes-own-pipeline-reuse-inventory.md`: KKND, Theme Hospital and retrokit tool inventories with line counts and licences, in-place vs full rewrite, the OMF readers, discovery, and effort estimates (Q1-Q8).
- `docs/research/notes-automation-loops.md`: autoresearch, Bilevel, Ralph, `/goal`, Lewis/Nigel, Mizuchi attempt curves, and the driver recommendation matrix (Q1-Q9).
- `docs/research/notes-progress-reporting-recompfyi.md`: the AnyPS5 and sa3 Pages patterns, the decomp.dev closure, the objdiff report proto, the OMF gap, and the `.recomp.json` spec and artifact ingestion.
- `docs/research/notes-decompwtf-rea-ghidra-ida.md`: decomp.wtf architecture, fork mode vs from-scratch, the hybrid effort estimate, LE loaders, GhidraMCP, and IDA Free limits.
- `docs/research/notes-blogs-and-reference-repos.md`: Macabeus and Lewis series details, Abahbob's checksum-first rule, and README and reference repo conventions.
- `docs/research/notes-target-binary-and-toolchain.md`: the mosura probe, the NHL95PC/KKND/Theme Hospital version-pinning methods, and the flag-evidence patterns.
- `docs/research/notes-vector-retrieval-bsim.md`: opcode Levenshtein vs embeddings, and asm normalization for twin matching.
- `docs/workflow.md`: Milestone 1 roadmap (new numbering), gates, spikes, the per-function loop, the hook table, and the attempt cap.
- `docs/superpowers/specs/2026-10-19-reverseapoc-design.md`: goals, non-goals, anti-goals, decisions, and what is left to the builder.
- `docs/toolchain.md`, `docs/matching.md`, `docs/coding-style.md`, `docs/ceremonies.md`, `.claude/rules/src.md`: target facts, compiler evidence, relocation rules, C89 and naming rules, and review-pass limits.
- Repo: `tools/reverseapoc/le.py` (raises on iterated, zero and invalid pages and on non-internal fixups), `tests/test_le_real.py` (both EXEs load and parse their fixups), `configure.py` (Phase 2 skeleton), `.recomp.json` (current listing draft).

---
*Feature research for: Watcom 10.x / DOS/4GW LE byte-matching decompilation pipeline (ReverseApoc Milestone 1, Phases 3-6)*
*Researched: 2026-10-19*
