# Repository infrastructure, Docker and coding standards for a Watcom/DOS matching decomp (ReverseApoc)

NOTE: written to the plan-mode file because plan mode forbade writing to the requested scratchpad path
(`...\scratchpad\research_notes\ReverseApoc kickoff research\repo_infra_docker_standards.md`). Copy this file there verbatim.
Research date: 2026-10-19. All web claims were fetched/searched on that date. Local repo facts were read read-only.

## 1. Build system: Makefile vs CMake vs ninja-via-Python vs wmake

### Takeaway
The closest, most recent Watcom/DOS matching decomps (Theme Hospital, KKND, Daggerfall) do NOT use Make or CMake: they use a Python driver (`configure.py` generating `build.ninja`, or a `tools/build_*.py` "gate" script) plus objdiff. Given the team is already on Python + uv, a Python-generated ninja build (or plain Python build script) is the best fit; Make is acceptable only as a thin Docker-facing wrapper; CMake adds little because Watcom is not a first-class CMake compiler for DOS/LE output.

### Cited Findings
- Theme Hospital decomp (Watcom 10.6, DOS 1997): `python3 configure.py` writes `build.ninja` and `objdiff.json`; targets `ninja`, `ninja build/report.json` (objdiff report), `ninja link`; Make/CMake not mentioned. Repo has `config/` (functions, symbols, relocs, cflags tables), `docs/` (MATCHING.md, BUGS.md), `include/`, `nix/`, `src/`, `tools/` (~30 Python scripts), gitignored `orig/` and `build/`. — [theme-hospital-decomp](https://github.com/matteo-pacini/theme-hospital-decomp); tree via GitHub API (`gh api repos/matteo-pacini/theme-hospital-decomp/git/trees/HEAD?recursive=1`)
- Theme Hospital per-file compiler flags live in `config/cflags.txt`: "first matching glob decides how a source file is compiled: glob, compiler (optionally @version), flags". Flags `-s -ot -d2 -zm` etc.; different Watcom versions selectable per file (10.6 default, 10.0a for some runtime modules). — [config/cflags.txt](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/config/cflags.txt) (fetched via GitHub API)
- KKND-Decomp (Watcom 10.x, DOS/4GW LE, 1997): no ninja/Make; "`python tools/build_kknd.py` is the gate": compiles `src/**/*.c`, verifies each C function against the original (bytes + relocation targets), splices, rewrites the LE, checks SHA-1; success = `build/DOS/KKND.EXE: OK`. Flags pinned in `configs/DOS/cflags.txt` (`-s -of+ -5r -omilert -zm -zp1`), per-file override with first-line `/* cflags: ... */`. Uses a PATCHED Open Watcom `wcc386` (`doc/compiler_patch.md`, `tools/owpatch/kknd-wcc386.patch`). Has `.github/workflows/progress.yml` and a `CLAUDE.md`. — [KKND-Decomp](https://github.com/Wyrelade/KKND-Decomp) (CLAUDE.md read via GitHub API)
- Daggerfall decomp (Watcom C32 10.0a, CauseWay extender): no Make/CMake; Python tools plus `tools/build-and-verify.sh`; README badges updated by every successful build; the real compiler is run under DOSBox-X via `tools/wcc10.py` ("one DOSBox-X run compiles all of src/ in under a minute"). — [daggerfall-decomp](https://github.com/brotchie/daggerfall-decomp)
- Syndicate Wars port (swars) is a source port (disassemble + replace DOS code with SDL), not a matching decomp; its companion repo uses autoconf. Build instructions for the main repo were not confirmed. — [swfans/swars](https://github.com/swfans/swars), [VOGONS account](https://www.vogons.org/viewtopic.php?p=1331177)
- Plain-Watcom open-source DOS projects (unzip, libxmp, zlib, jpeg) ship `wmake` makefiles (`makefile.wat`, `Makefile.dos`) calling `wcc386`; these are for building, not matching. — [libxmp Makefile.dos](https://fossies.org/linux/libxmp/Makefile.dos), [UnZip makefile.wat](https://pubs.usgs.gov/ds/2007/245/SOFTWARE/Zip_UnZip_Compression/unzip552_source/msdos/makefile.wat)
- rebrew (a compiler-in-the-loop decomp workbench, Python 3.13+, uv) uses `rebrew-project.toml`, runs toolchains in Docker images, and uses `make test` only for its own tests. — [maci0/rebrew](https://github.com/maci0/rebrew)
- objdiff supports x86 and uses an `objdiff.json` of units (`target_path` = expected object, `base_path` = ours); it powers decomp.dev progress reports. — [encounter/objdiff](https://github.com/encounter/objdiff)
- Not found: any Watcom-based decomp using CMake. TR1X/fallout1-ce/sm64 were not checked for build system here; TR1X and fallout1-ce are not Watcom matching projects (fallout1-ce is a CMake source port; unverified in this session).

### Inferences
- The matching problem is "compile one translation unit with exactly these flags and compare .obj/function bytes", with a per-file flags table. That fits a Python script reading `config/cflags.txt` better than Make pattern rules or CMake targets.
- Recommended: `configure.py` -> `build.ninja` + `objdiff.json` (ninja inside Docker), with `uv run` Python tools; a tiny `Makefile` (or `just`/script) is optional sugar for `docker compose run` commands. Because no make/cmake/ninja is installed on the host, everything build-related must run in the container anyway.

### Gaps
- Could not verify build systems of Magic Carpet / swars main repo / fallout1-ce / TR1X (not Watcom matching projects, low relevance).
- No survey of recomp.fyi or decomp.me DOS entries beyond the GitHub search results (searches returned Theme Hospital, Daggerfall, KKND, rebrew, decomp.wtf).

## 2. Running Watcom: Docker, Linux-native Open Watcom, original compilers, silent install vs user-provided

### Takeaway
Open Watcom v2 has official Linux (x86/x64) binaries and can be silently installed in Docker, but it is NOT the compiler the 1997 game was built with; matching decomps use the ORIGINAL Watcom 10.x (sometimes 11) run via wibo (Win32-on-Linux), DOSBox-X, or Wine. The original compiler, the game files and any CD media must be user-provided (or fetched by the user's own action); never baked into a published image.

### Cited Findings
- Open Watcom v2 "Current-build" release (2026-10-19) has assets `open-watcom-2_0-c-linux-x64`, `open-watcom-2_0-c-linux-x86`, `-c-dos.exe`, `-c-win-x64.exe`, and `ow-snapshot.tar.xz`, plus dated monthly builds (latest 2026-10-01); all marked pre-release. — [open-watcom-v2 releases](https://github.com/open-watcom/open-watcom-v2/releases); asset list via `gh api repos/open-watcom/open-watcom-v2/releases/tags/Current-build`
- Open Watcom license is the Sybase Open Watcom Public License v1.0; internal R&D/personal use granted; redistribution allowed with source-availability notices and license copy. — [license.txt](https://github.com/open-watcom/open-watcom-v2/blob/master/license.txt)
- Existing community Docker images for Open Watcom v2: `mcejp/open-watcom-v2` (~128 MB, ~5 yrs old), `mmastrac/openwatcom` (Alpine, 2021), `lapinlabs/watcom` (7 yrs), `ykode/openwatcom` (3 yrs), `dockerhy/watcom-docker` (3 yrs). None official; all stale. — [Docker Hub search results](https://hub.docker.com/r/mcejp/open-watcom-v2), [tags](https://hub.docker.com/r/mmastrac/openwatcom/tags)
- Open Watcom 2.0 Linux install puts tools under `/usr/bin/watcom` with `binl` / `binl64` directories (forum report). — [TinkerDifferent](https://tinkerdifferent.com/threads/installing-open-watcom-2-x-in-linux.5082)
- wibo: "minimal wrapper that runs simple command-line 32-bit Windows binaries on Linux and macOS ... developed to run Windows compilers faster than Wine"; MIT license; Linux x86 static + experimental x86_64 builds; repo ships Dockerfiles. — [decompals/wibo](https://github.com/decompals/wibo)
- Theme Hospital uses wibo 1.2.0 to run the Win32 Watcom C/C++ 10.6 `wpp386` on Linux; DOSBox variants are used only to play the rebuilt game. Compiler and runtime CD images are downloaded from WinWorld (~600 MB) at first `nix develop` (not supplied by the repo); the game comes from the user's GOG installer checked by SHA-256 and unpacked with innoextract into gitignored `orig/`. Reproducibility via Nix flake, not Docker. — [theme-hospital-decomp README](https://github.com/matteo-pacini/theme-hospital-decomp); [AGENTS.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/AGENTS.md)
- Daggerfall decomp: repo contains no game files and no compiler; user supplies Watcom 10.0a binaries copied from their own media to `third_party/watcom10/` (never committed), compiler run under DOSBox-X; tools check executables' SHA-1. — [daggerfall-decomp README](https://github.com/brotchie/daggerfall-decomp)
- KKND: uses a patched Open Watcom `wcc386` (resolved from `$WATCOM`, `tools/watcom/`, a local patched dir, else stock OW 1.9); notes that `wcc386` splits paths on spaces and treats `/` as an option switch, so tools compile from `build/tmp` with relative paths. Banner "1988-1994" = Watcom 10.0/10.0a class. — [KKND CLAUDE.md](https://github.com/Wyrelade/KKND-Decomp)
- Theme Hospital's MATCHING.md: 10.5/10.5a/10.6 generate identical code for what was tested; 10.0a ruled out for game code but needed for some runtime modules; 11.0 "worse throughout" (matched 2 of 10 demo functions) — i.e. exact compiler version matters. — [docs/MATCHING.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/docs/MATCHING.md)
- rebrew: Docker images contain "Wine, DOSBox, and native compiler runtimes"; prebuilt profiles pulled with `rebrew toolchain pull`, or build "an authorized image" yourself. — [rebrew](https://github.com/maci0/rebrew)
- decomp.wtf: installs checksum-verified compilers; proprietary ones install only after the user accepts terms. — [decomp.wtf](https://github.com/i12bp8/decomp.wtf) (repo reported archived)

### Inferences
- Silently installable in Docker (public, redistributable): Python 3.15 + uv, ninja, clang-format/clang-tidy/clangd, objdiff-cli (Rust release binary), wibo, Open Watcom v2 Linux (as fallback/`wdis`/`wlink`/`wlib`/tools and for non-matching experiments), DOSBox-X (for smoke tests), innoextract, nasm, rizin/ghidra optional.
- Must be user-provided or user-initiated: the original Watcom C/C++ 10.x/11 compiler + its libs/headers (proprietary Sybase/Powersoft; abandonware downloads are a legal grey zone, so keep as an opt-in script like Theme Hospital's WinWorld fetch, never a Dockerfile layer pushed to a registry), the game files (Steam/GOG paths already in `.env`), and any original EXE/CD data. Docker image should be built locally so no proprietary bytes are redistributed.
- Pragmatic design: Docker image = toolchain without Watcom; a `scripts/fetch-toolchain` step (or bind-mounted `third_party/watcom/`) supplies the compiler at runtime; compiler runs via wibo in-container (fast), DOSBox-X headless as fallback.
- Which exact Watcom version built UFO2P.EXE/TACP.EXE is unknown here and must be determined from the binaries (runtime banner/CRT code); not researched in this scope.

### Gaps
- Whether wibo successfully runs every Watcom 10.x/11 driver binary (WCC386.EXE is DOS-extended/Win32 variants) was only evidenced by Theme Hospital for Watcom 10.6 Win32 tools; not tested.
- Legal status of WinWorld/archive.org Watcom downloads was not researched; treat as user responsibility.
- No Docker image with original Watcom exists publicly that I could find (searches found only Open Watcom v2 images).

## 3. Rust for tooling?

### Takeaway
No for the project's own tooling; use Python + uv. Consume Rust tools as prebuilt binaries (objdiff, objdiff-cli). Only reconsider Rust if a Python tool becomes a measurable bottleneck (e.g. brute-force variant search) after profiling.

### Cited Findings
- objdiff is written in Rust (Apache-2.0/MIT) and ships GUI + CLI binaries, x86 supported. — [encounter/objdiff](https://github.com/encounter/objdiff)
- Every Watcom DOS matching decomp found (Theme Hospital, KKND, Daggerfall) writes its splitter/builder/matcher tools in Python; rebrew requires Python 3.13+/uv. — repos linked above.
- Theme Hospital's `tools/` has ~30 Python scripts (split, omf2elf, lefile, lewrite, variants, progress). — [tree](https://github.com/matteo-pacini/theme-hospital-decomp)

### Inferences
- Rust would add a second toolchain in Docker, slow iteration, and reduce contributor/AI-agent velocity; Python's LE/OMF parsers and capstone/pefile-style libs are enough. The heavy lifting (disassembly diff) is already in Rust via objdiff. Verdict: No.

### Gaps
- No benchmark data comparing Python vs Rust splitters for LE binaries.

## 4. ANSI C vs C++, dialect limits, mid-block declarations

### Takeaway
Write in C89/ANSI C with Watcom extensions unless the original module was C++ (Theme Hospital is C++ compiled with `wpp386`; KKND/Daggerfall are C with `wcc386`). Which one applies to Apocalypse should be decided per binary from the compiled code (C++ name mangling, vtables, RTTI/`$Wvf` COMDATs vs C-style `name_` symbols). Mid-block declarations are a C99 extension: enforce with `-Wdeclaration-after-statement` in a clang syntax-check and/or an ast-grep rule.

### Cited Findings
- Compiler difference: Theme Hospital notes "The game is C++: `wcc386` (C) generates different code for the same source." — [MATCHING.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/docs/MATCHING.md)
- Watcom C calling convention is register-based (eax, edx, ebx, ecx, then stack); C symbols get trailing `_` (functions) and leading `_` (data); structs packed (`-zp1`) and enums smallest-signed-type. — [MATCHING.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/docs/MATCHING.md), [KKND CLAUDE.md](https://github.com/Wyrelade/KKND-Decomp)
- Open Watcom v2's C99 wiki marks "mixed declarations and code" as supported but "C99 compatibility is an undocumented feature since the implementation is not complete"; use `-zastd=c99` to turn on implemented C99 extensions; default dialect not stated. This is Open Watcom v2, not the original 10.x/11 compilers. — [C99-Compliance wiki](https://github.com/open-watcom/open-watcom-v2/wiki/C99-Compliance)
- Clang diagnostic `-Wdeclaration-after-statement`: "mixing declarations and code is a C99 extension" / "incompatible with standards before C99". — [Clang diagnostics reference](https://clang.llvm.org/docs/DiagnosticsReference.html)
- KKND CLAUDE.md enforces readability rules even in a matching project: no pointer arithmetic with manual offsets; define structs (`ArrayElement`, size comments), self-review checklist, commit per matched function. — [KKND CLAUDE.md](https://github.com/Wyrelade/KKND-Decomp)
- Daggerfall `docs/natural_c.md` is dedicated to "making the lifted C read like real C (structuring, typed globals, local names, declarations) and the Watcom 10.0a control-flow rules". — [daggerfall-decomp README](https://github.com/brotchie/daggerfall-decomp)
- Theme Hospital rule: "Never reorder declarations: order decides stack slots and the layout of statics"; enumerators only replace literals, fields keep integer types. — [AGENTS.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/AGENTS.md)

### Inferences
- Pre-standard C++ in Watcom 10/11 has templates and exceptions only partially/very differently from modern C++; no STL as we know it; avoid claiming more without testing (not verified by a source I fetched).
- Mid-block declaration problem: AI assistants emit C99 style (`for (int i...)`, declarations after statements); Watcom 10/11 C front end rejects these, and moving declarations also changes stack-slot allocation, so declaration order is itself a matching variable. CI check suggestions: (1) `clang -fsyntax-only -std=gnu89 -Wdeclaration-after-statement -Werror=declaration-after-statement -Wno-...` over `compile_commands.json`; (2) an ast-grep rule on C for declarations following non-declaration statements in a compound_statement; (3) a tiny Python lint in `tools/`. No dedicated clang-tidy check for this was found (not verified exhaustively).
- Readability under constraints: use typedef'd structs/enums/named constants, descriptive locals (renaming locals is free in matching), comments for the compiler-driven oddities; keep macros/pragma aux in headers.

### Gaps
- Exact Watcom 10/11 C++ feature support (templates, exceptions, RTTI) was not sourced.
- Whether UFO2P/TACP are C or C++ (and compiler version) is unresolved here.

## 5. .clang-format / .clang-tidy / clangd with Watcom code

### Takeaway
clang-format works on Watcom-dialect source except it rewrites `#pragma aux` contents; Theme Hospital's solution is a wrapper script that masks every pragma (including continuation lines) before formatting. clangd/clang-tidy can index via a generated `compile_commands.json` plus a compat header, with remaining Watcom-only constructs reported as errors; keep tidy minimal.

### Cited Findings
- Theme Hospital `.clang-format`: `BasedOnStyle: LLVM`, `IndentWidth: 4`, `ColumnLimit: 120`, `BreakBeforeBraces: Linux`, `IndentExternBlock: NoIndent`, `SortIncludes: Never` (include order can matter), `IndentPPDirectives: None`, no short functions/ifs/loops/blocks on one line, `PointerAlignment: Right`, `SpaceAfterCStyleCast: false`, `ReflowComments: false`; comment: "Formatting must never change the build." — [.clang-format](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/.clang-format) (via GitHub API)
- Its `tools/format.py`: "clang-format rewrites the inside of pragmas (Watcom's `#pragma aux f parm [eax]` becomes `parm[eax]`), so each pragma, with its continuation lines, is swapped for a placeholder before formatting and put back afterwards"; supports `--check`; reads files as latin-1. — [tools/format.py](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/tools/format.py)
- Same repo: `compile_commands.json` (gitignored, generated) lets clangd/clang-tidy parse sources, "with some Watcom-only constructs still reported as errors"; `tools/clangd/compat.h` exists; `.nvim.lua` disables format-on-save. — README and tree above
- sm64 `.clang-format`: IndentWidth 4, ColumnLimit 104, PointerAlignment Right, `SortIncludes: false`, `SpaceAfterCStyleCast: true`, `BreakBeforeBraces: Attach`, `IndentCaseLabels: true`. — [n64decomp/sm64](https://github.com/n64decomp/sm64/blob/master/.clang-format) (via GitHub API)
- TR1X (LostArtefacts/TRX) `.clang-format`: Webkit base, ColumnLimit 80, `InsertBraces: true`, `SortIncludes: false`, `IndentPPDirectives: BeforeHash`. — [LostArtefacts/TRX](https://github.com/LostArtefacts/TRX/blob/develop/.clang-format) (via GitHub API; branch unverified)
- fallout1-ce `.clang-format`: only `BasedOnStyle: WebKit` and `AllowShortIfStatementsOnASingleLine: WithoutElse`. — [alexbatalov/fallout1-ce](https://github.com/alexbatalov/fallout1-ce) (via GitHub API)
- clang-format offers `// clang-format off/on` regions to protect code from reformatting. — [Linux kernel clang-format doc](https://www.kernel.org/doc/Documentation/process/clang-format.rst)
- The claude-plugins-official `clangd-lsp` plugin is already enabled in this repo's `.claude/settings.json`. — local file read.
- I found no public bug report specifically about clang-format and `__far`/`__interrupt`/`#pragma aux` (search came back empty).

### Inferences
- Recommended base: LLVM-derived (as in Theme Hospital), 4-space indent, Linux or Allman braces per team taste, `SortIncludes: Never`, `ReflowComments: false`, `ColumnLimit` 100-120, plus a `format.py`-style pragma mask and a CI `--check` that also rebuilds and verifies byte equality (formatting must be build-neutral, e.g. declaration order and line-based `__LINE__`/assert macros).
- Mask or `// clang-format off` also for `__asm` blocks and Watcom `#pragma aux` continuations.
- `.clang-tidy`: keep tiny, advisory-only (bugprone-*, readability-braces-around-statements, readability-identifier-naming for your naming scheme, misc-*), NOT performance/modernize-* (they suggest C++11 changes that would break matching). Use `-Wdeclaration-after-statement` as the real dialect gate rather than tidy.
- compile_commands.json: generate from `build.ninja`/cflags table with `-std=gnu89`, `-m32`, and `-D__WATCOMC__`, `-D__386__`, `-D__FLAT__`, and a compat header defining `__far`, `__near`, `__interrupt`, `__cdecl`, `__watcall` as empty macros.

### Gaps
- Exact sample .clang-tidy files from decomp projects were not found; recommendation above is judgement.
- TR1X/sm64/fallout configs are for non-Watcom-matching projects (sm64 matches GCC/IDO; TR1X is a port).

## 6. Testing strategy

### Takeaway
The byte-match verification IS the test suite for decompiled code; write unit tests (pytest) for tooling (LE parser, OMF reader, flag resolver, format masker, lints). TDD is meaningful for tooling and for lint/CI scripts, not for match-first function decomp. A DOSBox-X smoke test of a rebuilt binary is optional and later.

### Cited Findings
- Theme Hospital verification chain: `ninja build/report.json` (every function matched), `python3 tools/lewrite.py --strict` rebuilds `HOSPITAL.EXE`, `cmp build/hospital.exe orig/HOSPITAL.EXE`; per-file `tools/check.py`; objdiff per-function diff; the wlink build of changed code is checked by playing in DOSBox-X. Agents are told "Work is done when everything still matches and the EXE is byte-identical". — [README](https://github.com/matteo-pacini/theme-hospital-decomp), [AGENTS.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/AGENTS.md)
- KKND: "NEVER declare success on `match.py` alone ... ALWAYS run `python tools/build_kknd.py` ... SUCCESS CRITERIA: `build/DOS/KKND.EXE: OK`"; "On struct changes: rebuild; every function using that struct must still match." — [KKND CLAUDE.md](https://github.com/Wyrelade/KKND-Decomp)
- Daggerfall: every successful `tools/build-and-verify.sh` updates progress badges; the headless game is driven by tools (`fallplay.py`), with 8,204 recorded calls used to check readable-C versions of the engine. — [daggerfall-decomp README](https://github.com/brotchie/daggerfall-decomp)
- rebrew's own suite: `make test` / `make test-one T=<file>` / `make all` (gates), requiring nasm and bun. — [rebrew](https://github.com/maci0/rebrew)

### Inferences
- Layers: (a) unit tests (pytest) for `tools/`; (b) per-function match check (compile + compare bytes + relocs) = integration; (c) whole-EXE SHA-1/`cmp` of the rebuild against `orig/` = the E2E "golden" test (only runnable where the user has game files, so CI on public GitHub can only run (a) and lints; byte-match CI needs self-hosted runner or is run locally/in the dev container); (d) DOSBox-X smoke test only for non-matching/ported code.
- Honest answer on TDD: match-first for functions (the compiler is the oracle, the test already exists: target bytes). TDD yes for tooling, parsers, linters, format masker. For readable-refactors, a "does it still match" gate substitutes for unit tests; behaviour-affecting changes (e.g. `types` results from variants.py "can change behaviour", per Theme Hospital AGENTS.md) need human review.

### Gaps
- No data on CI practices for DOS decomps with proprietary inputs beyond progress workflow in KKND (`.github/workflows/progress.yml` content not read).

## 7. CLAUDE.md best practices and a lean layout

### Takeaway
Keep CLAUDE.md short (target < 200 lines), put detail in docs/*.md linked from it (use `@path` imports only for what must always load, since imports do not reduce context cost), use path-scoped `.claude/rules/` for file-type-specific rules, never put secrets in it, and audit for stale/duplicated/emphatic lines.

### Cited Findings
- Anthropic article: no required format; start with project summary and a directory map; add common commands, coding standards, test instructions, environment setup; "keep it concise ... every line costs attention"; move detailed material into separate markdown files referenced from CLAUDE.md; start simple, expand on real friction; include architectural context, custom tools with examples, default workflows, project-specific warnings; avoid secrets (API keys, credentials, connection strings), generic guidance, speculative content, and writing a comprehensive file all at once; commit it and maintain it. — [Using CLAUDE.md files](https://claude.com/resources/articles/using-claude-md-files)
- Claude Code memory docs: target "under 200 lines per CLAUDE.md file"; "imports help you organize a long file but don't reduce its context cost, because imported files also load at launch"; path-scoped `.claude/rules/*.md` load only when working with matching files; subdirectory CLAUDE.md files load on demand; `@path/to/import` syntax (skipped inside code spans/fences); `CLAUDE.local.md` for personal preferences, add to `.gitignore`; managed-policy CLAUDE.md for org-wide rules; `claudeMdExcludes` setting; first 200 lines/25KB of auto memory load; CLAUDE.md is context, not enforced config: use hooks for enforcement; "If two instructions contradict each other, Claude may pick one arbitrarily"; AGENTS.md is read only if no CLAUDE.md/CLAUDE.local.md exists (can import it from CLAUDE.md). — [Memory docs](https://code.claude.com/docs/en/memory)
- Anthropic prompt-audit guidance: goal is to find instructions that no longer fit, not to shorten; keep context only the author knows and the reasons behind constraints; delete restated defaults; remove/soften CRITICAL/MUST/NEVER emphasis (reserve for one or two real constraints, with the reason); describe outcomes not scripts; verify paths/commands against the repo; resolve conflicts between instruction files; avoid history narratives (dates, PR numbers, "no longer"); keep each fact in one place; anti-patterns: pressure language, stale facts, recency traps, anchoring prohibition lists, strategy coaching, volatile version pins. — [prompt-audit.md](https://github.com/anthropics/skills/blob/main/skills/claude-api/shared/prompt-audit.md)
- Decomp precedents: Theme Hospital's `AGENTS.md` (~60 lines) = Git rules, toolchain commands, "Matching a function" steps, Rules, Done criteria, and points to README and `docs/MATCHING.md`; KKND's CLAUDE.md = overview, structure, tools list, compiler facts, code-quality standards, task recipe, verification, commits, with separate `DECOMPILATION_LEARNINGS.md`, `CODEGEN_MODEL.md`, `NAMING.md`, `PLAN.md`, `PROGRESS.md`. — repos above.

### Inferences
Suggested layout (root CLAUDE.md ~80-120 lines):
- CLAUDE.md: one-paragraph project goal; hard constraints (never commit game files/binaries/keys; byte-match is the definition of done; ANSI C89 declarations at block top; do not reorder declarations); the 5-8 commands (docker run wrappers); "Done" gate; pointers: `docs/build.md`, `docs/decomp-workflow.md`, `docs/coding-style.md`, `docs/matching-tips.md`, `docs/tools.md`, `docs/ceremonies.md` (commit/PR/progress/release rituals), optionally `docs/legal-and-assets.md`.
- Use `.claude/rules/` with `paths:` globs for `src/**/*.c` (style/dialect rules) and `tools/**/*.py` (python rules) so they load only when relevant; keep a `docs/matching-tips.md` journal like KKND's learnings file that agents append to (searchable by a `learn.py`-style tool rather than loaded).
- Enforce with hooks/CI where possible (declaration-after-statement lint, secret scan, forbidden extension check) instead of prose.
- Daggerfall/KKND show commit conventions worth copying: one matched function per commit, learnings recorded with the match.

### Gaps
- Docs page sections on "large teams" cover managed CLAUDE.md, `claudeMd`, `claudeMdExcludes` only; mostly irrelevant for a single-owner repo.

## 8. Coding standards to distill into docs/coding-style.md

### Takeaway
Use the Imperial (Indian Hill-derived) C standard + the SEI CERT categories INT/ARR/STR/MEM/EXP as a base for new/non-matching code (tools, tests, harness) but let "match the original" override style in decompiled functions; Google C++ guide and micro-os-plus conventions are C++-oriented and mostly help only for naming/scoping ideas.

### Cited Findings
- Imperial College "Recommended C Style and Coding Standards": 79-col lines, K&R braces, always brace `if/else/do-while`, return type on its own line with name in column 1, `*` attached to variable, explicit comparisons, module prefix for globals, no leading/trailing underscores for user names, ALL CAPS macros/constants, avoid magic numbers, parenthesize macro params / `do{}while(0)`, explicit initialization, avoid embedded assignments, comment fall-through, no assumptions about type sizes/byte order/char signedness, sized typedefs, pragmas are machine dependencies (wrap in `#ifdef`), run lint routinely. Also 8.3-style filenames suggestion (`base <= 8` chars, suffix `<= 3`). — [Recommended C Style and Coding Standards](https://www.doc.ic.ac.uk/lab/cplus/cstyle.html)
- Google C++ Style Guide (C++20): header `#define` guards of form `<PROJECT>_<PATH>_<FILE>_H_`, self-contained headers, include order groups, "place a function's variables in the narrowest scope possible, and initialize variables in the declaration" (conflicts with C89 declarations at block top), `static` for internal linkage; namespaces/classes/exceptions/RTTI/etc. are C++-only. — [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html)
- micro-os-plus naming: lowercase snake_case, `_t` suffix on scalar typedefs, struct tags `_s` + typedef `_t`, private members trailing `_`, boolean functions `is/has/...`, units in names (`delay_milliseconds`), avoid macros except config; config macro prefix `MICRO_OS_PLUS_`. — [micro-os-plus naming](https://micro-os-plus.github.io/develop/naming-conventions/)
- C++ Best Practices (cpp-best-practices) chapters: Preface, Use the Tools Available, Style, Considering Safety, Maintainability, Portability, Threadability, Performance, Correctness, Enable Scripting, Further Reading, Final Thoughts. (Chapter list only; contents not read.) — [cppbestpractices TOC](https://github.com/cpp-best-practices/cppbestpractices/blob/master/00-Table_of_Contents.md)
- SEI CERT C sections: PRE Preprocessor, DCL Declarations and Initialization, EXP Expressions, INT Integers, FLP Floating Point, ARR Arrays, STR Characters and Strings, MEM Memory Management, FIO Input Output, ENV Environment, SIG Signals, ERR Error Handling, API Application Programming Interfaces, CON Concurrency, MSC Miscellaneous, POS POSIX, WIN Microsoft Windows (each has a Rules and a Recommendations part). — [SEI CERT C Coding Standard](https://cmu-sei.github.io/secure-coding-standards/sei-cert-c-coding-standard/)
- OpenSSF compiler hardening guide baseline: `-O2 -Wall -Wformat -Wformat=2 -Wconversion -Wimplicit-fallthrough -Werror=format-security`, `-D_FORTIFY_SOURCE=3`, `-fstack-protector-strong`, `-fstack-clash-protection`, linker `-z relro -z now -z noexecstack`, `-fPIE -pie`, `-fcf-protection=full` on x86_64, `-Werror` for development only; for C code that rejects obsolete constructs `-Werror=implicit -Werror=incompatible-pointer-types -Werror=int-conversion`; "for existing codebases, enable flags gradually". — [OpenSSF compiler hardening guide](https://best.openssf.org/Compiler-Hardening-Guides/Compiler-Options-Hardening-Guide-for-C-and-C++.html)

### Inferences
- Relevance of CERT rule families to legacy game code: INT (signed overflow, conversions, shifts), ARR (bounds, VLAs), STR (null termination, buffer sizes), MEM (alloc/free pairing, uninitialized memory), EXP (evaluation order, side effects, sequence points) are the high-yield ones; FIO/ENV/SIG/CON/POS/WIN largely irrelevant to DOS code.
- Conflicts with "match the original 1997 code": narrowest-scope declarations and initialize-at-declaration (Google) vs C89 block-top declarations and declaration order affecting stack slots; `-Wconversion`/explicit casts and fixed-width types can change integer promotion/codegen; `const`/`static` additions and header reordering can change symbol mangling/layout in C++; bounds checks and "fixing" original bugs change code (Theme Hospital keeps original bugs and lists them in docs/BUGS.md); replacing magic numbers by enums is fine only where it keeps types (Theme Hospital: enumerators replace literals only). Hardening flags (OpenSSF) apply only to the host-side tools/tests built with gcc/clang, not to Watcom matching builds.
- Naming: for decompiled symbols prefer address-based placeholders (`func_00012080`, `D_000B98D8`) until real names are known, then module-prefixed lowercase names (Imperial/micro-os-plus style) with `_t` typedefs; keep original names recovered from `__FILE__`/debug strings.

### Gaps
- "oodlescoop C best practices" could not be located (guessed URL oodlescoop.com/blog/c-best-practices returned 404; search found nothing under that name); no content to report.
- Google guide, cpp-best-practices and SEI CERT item-level contents were not read in full (by design for CERT).

## 9. Python tooling: 3.15 status, uv layout, Dockerfile

### Takeaway
As of 2026-10-19 Python 3.15.0 is released (2026-10-09 per python.org), uv is already at 0.13.x (not 0.12) and installs 3.15 by default; pin `uv` via the container image tag and Python via `.python-version`/`requires-python`. Check each dependency for 3.15 wheels; most pure-Python tool dependencies (pytest, capstone, lief-like parsers need checking) are fine, but heavy native libs may lag.

### Cited Findings
- python.org downloads page lists Python 3.15.0 as the latest release, dated 2026-10-09; the 3.15 series is in "bugfix" status. — [python.org downloads](https://www.python.org/downloads/)
- PEP 790 schedule (as fetched; labelled "Actual"): 3.15.0rc1 2026-08-04, rc2 2026-09-01, rc3 2026-10-02, final 2026-10-09; page last modified 2026-10-19. Betas: b1 2026-05-07, b2 2026-06-02, b3 2026-06-23, b4 2026-07-18. — [PEP 790](https://peps.python.org/pep-0790/), [3.15.0b1](https://www.python.org/downloads/release/python-3150b1/)
- Headline 3.15 changes (press, check docs): explicit lazy imports (PEP 810), UTF-8 default encoding (PEP 686), JIT speedups (~7-8% geomean on x86-64 Linux per one report), stable ABI for free-threaded builds, `frozendict`, sentinel type, unpacking in comprehensions, Tachyon sampling profiler. — [AlternativeTo](https://alternativeto.net/news/2026/10/python-3-15-is-here-with-faster-jit-compiler-explicit-lazy-imports-and-utf-8-by-default/), [What's new in 3.15](https://docs.python.org/fa/3.15/whatsnew/3.15.html)
- UTF-8-by-default matters for a project reading latin-1/CP437 DOS files: always pass explicit `encoding=` (Theme Hospital's format.py reads sources as latin-1). — [format.py](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/tools/format.py)
- uv: latest release 0.13.1 (2026-10-14); 0.13.0 made CPython 3.15 the default stable version for `uv python install`; 0.13.1 added CPython 3.16.0a1. The 0.12 line ran 0.12.0 (2026-07-28, breaking-changes release; `uv init` now declares a build system and packages by default) through at least 0.12.10 (2026-09-04). — [uv releases](https://github.com/astral-sh/uv/releases), [search results](https://newreleases.io/project/github/astral-sh/uv/release/0.12.2)
- Library lag (single third-party source, Kanaries guide tested 2026-10-11): numpy 2.5.4, scipy, scikit-learn, matplotlib, pandas, pyarrow had 3.15 wheels; polars/duckdb needed source builds on free-threaded/3.15; torch and tensorflow had no 3.15 wheels. Pydantic 2.14 beta was first with initial 3.15 support. An August 2026 PR said numpy/scipy lacked wheels then. — [Kanaries](https://docs.kanaries.net/de/topics/Python/python-3-15-upgrade-lazy-imports), [pydantic changelog](https://pydantic.dev/docs/validation/dev/get-started/changelog/), [GitHub PR #2011](https://github.com/munich-quantum-toolkit/core/pull/2011)
- uv Docker guidance: copy pinned binary `COPY --from=ghcr.io/astral-sh/uv:<version> /uv /uvx /bin/` (pin version or SHA256 digest); `UV_COMPILE_BYTECODE=1`; `UV_LINK_MODE=copy` with cache mounts `--mount=type=cache,target=/root/.cache/uv`; `uv python install <ver>`; `uv sync --locked`; cached dependency layer with `uv sync --frozen --no-install-project` + bind-mounted `uv.lock`; add `.venv` to `.dockerignore`. Example uses `debian:trixie-slim` and `uv:0.13.1`. — [uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/)

### Inferences
- The owner's "uv 0.12" request is already one minor behind; recommend pinning `ghcr.io/astral-sh/uv:0.13.x` (or 0.12.10 if 0.12 is a hard requirement; note 0.12 predates managed-3.15 default but `uv python install 3.15` still works if 0.12.x includes it, not verified).
- Layout: `pyproject.toml` (`requires-python = ">=3.15"`, `[dependency-groups] dev = [pytest, ruff, ...]`, `[project.scripts]` or `tools/` package), committed `uv.lock`, `.python-version` = `3.15`, run everything with `uv run ...`; run `uv sync --locked` in Docker. Pure-Python deps (pytest, ruff, capstone, pefile-like) are low risk; verify each has 3.15 wheels before locking; if one lags, pin Python 3.14 for tools (the host has 3.14) with a one-line change.
- Dockerfile skeleton (Linux, WSL2-friendly): `FROM ubuntu:24.04` or `debian:trixie-slim`; install `ninja-build clang-format clang-tidy clangd git ca-certificates` via apt; COPY uv from pinned image; `uv python install 3.15`; dependency layer; copy repo; download Rust prebuilt `objdiff-cli` and wibo (pinned versions + SHA256) in separate layers; no Watcom, no game files; bind-mount `./orig` and `./third_party/watcom` at runtime.

### Gaps
- Python 3.15 library compatibility for the exact deps (capstone, lief, pytest, ruff) was not verified; only one third-party blog on numpy-stack wheels.
- Python.org page content is from a summarizing fetch; "bugfix" status inferred from the page table.
- The `uv` version actually installable via `ghcr.io/astral-sh/uv:0.12.x` tags was not checked.

## 10. .gitignore, secrets and safety

### Takeaway
Right now the repo has NO .gitignore and untracked `.mcp.json` containing a live Tavily key (`tvly-...`), `.env` (game paths), `.env.example`, `.claude/`, `.agents/`, `.vscode/`, `skills-lock.json`. Nothing but README.md is tracked yet, so the key has never been committed; add `.gitignore` before the first `git add`, rotate the key anyway (it appeared in tool output/transcripts), and replace it by `${TAVILY_API_KEY}` expansion.

### Cited Findings
- Local repo state (read-only): `git ls-files` = only `README.md`; only commit is `d636597 Initial commit`; no `.gitignore`; `.env` and `.env.example` are both 142 bytes with identical keys `APOC_STEAM_FOLDER` and `APOC_GOG_FOLDER` (Windows paths with `%ProgramFiles%`); `.mcp.json` runs `npx -y tavily-mcp@latest` with a literal `TAVILY_API_KEY` in its `env` block; `docs/` is empty; `.claude/settings.json` enables plugins (clangd-lsp, superpowers, security-guidance, code-review, code-simplifier, claude-md-management); `.vscode/settings.json` has `python.terminal.useEnvFile: true`; `skills-lock.json` references `Leonxlnx/unlazy`. — local file reads on 2026-10-19.
- Claude Code `.mcp.json` supports `${VAR}` and `${VAR:-default}` expansion in `command`, `args`, `env`, `url`, `headers`. An unset variable with no default leaves `${VAR}` unexpanded and shows a warning in `claude mcp list` and `/mcp`. Expansion exists "so teams can share a config while each machine supplies its own paths and secrets". Project scope (`.mcp.json`) is meant to be committed; use local scope (stored in `~/.claude.json`) for servers with credentials. In `claude -p`/SDK/cloud sessions project-scoped servers load without prompting. — [Claude Code MCP docs](https://code.claude.com/docs/en/mcp)
- Anthropic's CLAUDE.md article: never include API keys/credentials in CLAUDE.md. — [article](https://claude.com/resources/articles/using-claude-md-files)
- Decomp precedents for ignoring game data: KKND `.gitignore` = `dumps/ asm/ build/ expected/ tools/watcom/ *.obj *.exe *.EXE __pycache__/ .venv*/ ... objdiff.json *.err`; Theme Hospital = `/orig/ /build/ /spike/ /result* __pycache__/ *.pyc /.ninja_* /build.ninja /objdiff.json *.err /compile_commands.json /.cache/`; Daggerfall: no files or compiler committed, SHA-1 checks of inputs. — repos above.
- Theme Hospital AGENTS.md: "Never commit game files. `orig/` and `build/` are gitignored; keep it so." Project states it contains no game assets or original binaries and asks contributors not to submit game files. — [AGENTS.md](https://github.com/matteo-pacini/theme-hospital-decomp/blob/master/AGENTS.md), [README](https://github.com/matteo-pacini/theme-hospital-decomp)

### Inferences
- Recommended `.gitignore` (deny-by-pattern for assets): `/orig/ /build/ /third_party/ /dumps/ .env .env.* !.env.example .mcp.json CLAUDE.local.md .claude/settings.local.json .venv/ __pycache__/ *.pyc /compile_commands.json /objdiff.json /build.ninja .ninja_* *.exe *.EXE *.com *.COM *.dat *.DAT *.lbx *.pck *.tab *.pal *.vid *.cd *.iso *.bin *.cue *.img *.obj *.lib *.map *.err` plus game-specific extensions to be confirmed from the actual game folder; also add `*.gog`, `*.mpq`-style archives only if present. Note `*.exe`/`*.obj` rules also block legitimate tool binaries, so allow-list exceptions (`!tools/**/*.exe` if ever needed).
- CI/pre-commit safety checks: (1) script that fails if any tracked file matches forbidden extensions or exceeds N KB, or has a SHA-1/SHA-256 matching a known game file hash list (hashes of originals are safe to commit); (2) secret scan (gitleaks or `detect-secrets`) in pre-commit and CI; (3) `git ls-files` allowlist test in pytest. Also protect `.env` via `python.terminal.useEnvFile` already set.
- MCP key handling: rotate the Tavily key now (it is plaintext in a file and appeared in this session's tool output), put `TAVILY_API_KEY` in the user environment or `.env` (gitignored) and change `.mcp.json` env to `"TAVILY_API_KEY": "${TAVILY_API_KEY}"`, commit `.mcp.json` only after that (or keep `.mcp.json` ignored and commit `.mcp.json.example`). Alternative: add the server at local/user scope via `claude mcp add` so no file in the repo holds it. Note the Tavily server timed out in this session, unrelated to the key.
- Because `.env` currently equals `.env.example` byte-for-byte (same size), `.env.example` can be committed as the template; ensure no real path leakage of the Windows username into committed files.
- Docker: mount game folders read-only (`-v "$APOC_GOG_FOLDER":/orig:ro`), add a `.dockerignore` mirroring `.gitignore` so the build context never contains game assets, and never `COPY` the game or Watcom into an image layer that could be pushed.

### Gaps
- Did not verify whether Tavily's MCP server supports env var-only configuration without an `env` block (it reads `TAVILY_API_KEY` from process env as documented in its README; not fetched).
- Did not check whether the leaked key has been used or is still valid.
- Exact file extensions of X-COM Apocalypse assets are not researched here; derive from the actual install folders.
