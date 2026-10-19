# decomp.wtf, REA, Ghidra/GhidraMCP, IDA Free, Understand-Anything and Groma for the ReverseApoc (X-COM Apocalypse, DOS/4GW LE, Watcom) matching decompilation

All sources accessed 2026-10-19 unless stated. GitHub metrics come from the GitHub REST API (api.github.com/repos/...) on that date.

NOTE ON OUTPUT LOCATION: this session ran in plan mode (read-only), so these notes were written to the plan file instead of the requested scratchpad path. No repos were cloned. Code was read over raw.githubusercontent.com and the GitHub API, and nothing was executed.

## 1. decomp.wtf: what it is, platforms, LLM integration, matching, install, license, maturity, limitations, WSL2 install, Watcom/DOS extension needs

### Takeaway
decomp.wtf is a local Python app (MIT) with three parts: a ROM-splitting and compile-and-compare pipeline, an MCP-based agent harness (Claude Code, Codex, opencode, any OpenAI-compatible API), and a browser GUI. The author archived it on 2026-10-15, two days after creating the repo, so it is now unmaintained (last version 0.10.6). It has no support for x86 "from scratch" projects, and nothing about DOS, LE, OMF or Watcom. x86 only appears in fork mode (public PC decomps judged by objdiff), in an MSVC-focused agent guide, and as optional Ghidra drafts. For ReverseApoc it is a reference architecture and a source of reusable parts. It is not a turnkey tool.

### Cited Findings
**Status and maturity**
- The README now opens with "This project is discontinued... I've decided to stop working on decomp.wtf and archive it." The reason given is that "a lot of the decompilation community... is against AI decompiling like this." "I won't fix issues, review pull requests or make new releases anymore." "You can still install the last version (0.10.6)." — [decomp.wtf README](https://github.com/i12bp8/decomp.wtf)
- GitHub API: created 2026-10-13T08:19Z, last push 2026-10-15T20:39Z, archived=true, 506 stars, 241 forks, open_issues_count 0, license MIT. — [GitHub API repos/i12bp8/decomp.wtf](https://api.github.com/repos/i12bp8/decomp.wtf)
- About 96 commits on main. — [GitHub repo page](https://github.com/i12bp8/decomp.wtf)
- License: "MIT © 2026 Sam Wolfs". — [README](https://github.com/i12bp8/decomp.wtf)

**What it is (pipeline + agent harness + web app)**
- Workflow: "Open a ROM. splat and spimdisasm find every function and data symbol, and decomp.wtf recognises the compiler... Add agents. Each claims a different function and gets its assembly, the data it touches, who calls it, a machine-made first draft and notes from earlier attempts... Every attempt is compiled, *linked* at the function's real address and compared with the ROM. A miss returns an instruction diff." — [README "How it works"](https://github.com/i12bp8/decomp.wtf)
- Two modes: "Start from scratch" (N64, PS1/2, GC, Wii, GBA, DS) and "Continue a public decomp" (fork any of 245 decomp.dev projects, "for GameCube, Wii, PlayStation 1 and 2, N64, GBA, DS, Switch, PC, Xbox 360 and more"). — [README](https://github.com/i12bp8/decomp.wtf)
- Other features: a live view GUI, an "Autopilot" (matched-twin copies plus machine drafts run through the judge), a background "Permuter" for near misses at 95% or more, `find_similar` look-alikes, a shared header for structs and prototypes, a "Decompile together" multi-user room mode (`decomp host` / `decomp join`), and "Export project" to a rebuildable decomp tree. — [README Features](https://github.com/i12bp8/decomp.wtf)
- Repo layout: `src/decompnet/rom/` (ROM reading, splat splitting, matcher `match.py`), `app/` (engine, `tools.py` MCP tools and agent prompt, `agents.py`, `server.py`, `collab.py`, `guide/` agent know-how), `forks/` (decomp.dev catalog, objdiff, m2c and Ghidra drafts, dtk splits), `network.py` (claims/attempts/notes/shared header), `toolchains.py` + `toolchains.toml` (pinned compilers), `hostenv.py` / `wsl.py` (Linux / WSL / Docker host), `site/public/install.sh`, `install.ps1`, `linux-base.sh`, `Dockerfile`. — [README Repository layout](https://github.com/i12bp8/decomp.wtf); [src/decompnet listing](https://github.com/i12bp8/decomp.wtf/tree/main/src/decompnet)
- Top-level modules also include `elfobj.py`, `compiler.py`, `scoring.py`, `similarity.py`, `permuter.py`, `handwritten.py`, `policy.py`, `limits.py`. — [src/decompnet listing](https://github.com/i12bp8/decomp.wtf/tree/main/src/decompnet)

**Platforms, compilers and architectures**
- Platform table: GameCube/Wii (Recommended, CodeWarrior GC 1.0 to Wii 1.7), N64 (Recommended, KMC GCC 2.7.2 and IDO 5.3/7.1), PlayStation (Beta, GCC 2.7.2/2.8.1 PSY-Q era), PS2 (Beta, EE-GCC 2.96), GBA (Beta, agbcc), DS (Beta, CodeWarrior for DS). "3DS · PSP · Switch · PC · Xbox · Xbox 360" are marked "coming", with public-decomp (fork) support only. — [README Platforms](https://github.com/i12bp8/decomp.wtf)
- "Drafts: m2c for MIPS, PowerPC and ARM; optional Ghidra for x86, AArch64 and everything else." The agent toolkit includes "guides for MIPS, PowerPC, ARM, x86, AArch64, IDO, GCC, Metrowerks, agbcc, PSY-Q, C++ and objdiff." — [README Features](https://github.com/i12bp8/decomp.wtf)
- The x86 agent guide is titled "x86 and MSVC (PC, original Xbox)". It covers cdecl, stdcall, thiscall and fastcall, MSVC 4.x-7.1 idioms and reccmp annotations (`// FUNCTION: GAME 0x401000`). It does not mention Watcom or a register calling convention. — [app/guide/x86.md](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/app/guide/x86.md)
- The pinned toolchain registry (`toolchains.toml`) contains MIPS GCCs, IDO, EE-GCC, mwcc, mwccarm, agbcc, binutils, coddog, dtk-template, luvdis, maspsx, an i386 glibc runtime, and Ghidra. A grep of the file found no Watcom or MSVC compiler entry. — [toolchains.toml](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/toolchains.toml)
- The pinned Ghidra is "NationalSecurityAgency/ghidra 12.1.4", described as "Large (540 MB) and needs Java 21+; optional". — [toolchains.toml](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/toolchains.toml)
- `forks/ghidra.py` produces "Ghidra drafts: decompiled C for platforms m2c doesn't read (x86, AArch64, Xbox 360 PowerPC, SuperH...)". It runs `analyzeHeadless ... -import <obj> -postScript DecompWtfExport.java` once per object file and caches the result as JSON. It imports the unit's object with Ghidra's default loaders and passes no custom loader or cspec. — [forks/ghidra.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/forks/ghidra.py)

**How it drives LLMs**
- Agents table: "Claude Code: Runs headless against the app's local MCP server". Codex CLI works the same way, "with approvals limited to decomp.wtf's tools". Antigravity CLI and opencode (DeepSeek, Qwen, Kimi...) also work. "API key: A built-in agent loop for any OpenAI-compatible API: DeepSeek, OpenRouter, OpenAI, or... llama.cpp, Ollama or LM Studio." Any other MCP client can point at `decomp mcp`. — [README Agents](https://github.com/i12bp8/decomp.wtf)
- Claude Code plugin: `/plugin marketplace add i12bp8/decomp.wtf`, then `/plugin install decomp-wtf@decomp-wtf` (adds a "decompile" skill), or `claude mcp add decomp -- decomp mcp`. — [README](https://github.com/i12bp8/decomp.wtf)
- "Agents only get decomp.wtf's tools: no shell... in our tests a small function cost Claude Code about 8 cents... cheaper models often get stuck on them on register allocation." Local models need at least 16K context. — [README Agents](https://github.com/i12bp8/decomp.wtf)

**How matching is measured**
- From scratch: candidates are "linked at the real address, so calls, globals, strings and jump tables are verified too". Byte-for-byte; "Score 0, or it doesn't count." — [README](https://github.com/i12bp8/decomp.wtf)
- Forks and GC/Wii/DS: "judged by objdiff inside the project's own build". A file counts as "linked" when all functions and data match and the project's checksum passes. — [README](https://github.com/i12bp8/decomp.wtf)
- Guardrails: "agents write only C/C++ sources and headers, never targets, assembly or build scripts, and inline assembly is refused. A change that breaks any function that already matched is undone." — [README](https://github.com/i12bp8/decomp.wtf)

**Install requirements**
- "decomp.wtf runs on Linux, and on Windows (supported, still unstable)... on Windows it runs in its own small Linux (a WSL 2 distribution called `decomp-wtf`)... macOS isn't supported." — [README Install](https://github.com/i12bp8/decomp.wtf)
- Linux: `curl -fsSL https://decomp.wtf/install.sh | bash`. GitHub mirror: `curl -fsSL https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/site/public/install.sh | bash`. Windows: `irm https://decomp.wtf/install.ps1 | iex`, which builds the distro from Debian's official WSL image. Projects end up at `\\wsl.localhost\decomp-wtf\home\decomp\Decomp`. — [README Install](https://github.com/i12bp8/decomp.wtf)
- "One line sets up everything: uv, the app, the period compilers (pinned and checksum-verified) and the m2c draft decompiler." Python 3.12+ badge. Development: `uv sync`, `uv run decomp`, `uv run pytest`. — [README](https://github.com/i12bp8/decomp.wtf)
- Docker is used only for server deployment (`site/public/Dockerfile`, "Docker on a server"), not for the desktop install. The README does not mention a GPU or Node.js. — [README Repository layout](https://github.com/i12bp8/decomp.wtf)
- Toolchains are "mounted read-only into the compile sandbox". On Windows, Linux-only toolchains run inside WSL 2 (`wsl.py`). — [toolchains.toml header](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/toolchains.toml)

**Known limitations (from the README)**
- Beta platforms were "tested on homemade games, much less on real ones". N64 export is not shiftable yet. C++ only works on GC/Wii/DS. Inline asm is refused. Hard functions are slow or expensive. Many community decomps reject AI contributions. — [README](https://github.com/i12bp8/decomp.wtf)

**Directly relevant prior art (Watcom/DOS/4GW LE matching decomps and AI RE toolkits)**
- KKND-Decomp: a matching decompilation of KKND (DOS, 1997). "MZ stub + DOS/4GW Pro + Linear Executable (LE), 3 objects, 20,192 fixups". The compiler is "Watcom C/C++32 (1994 runtime, Watcom 10.x) — matched with Open Watcom `wcc386`", with flags `-s -of+ -5r -omiler -zm -zp1`. "the LE image is split per function and relinks byte-identical". `tools/build_kknd.py` "compiles src/**/*.c with wcc386, cuts every C function out of its OMF object, requires it to be byte-identical to the original (relocations masked but their targets checked), splices it into the LE image, rewrites the executable and checks the SHA-1." `tools/` has "LE/OMF readers, splitter, build + verify, matcher". Progress is 492/3713 functions (13.25%). CC0 license, 8 stars, created 2026-09-24. — [Wyrelade/KKND-Decomp](https://github.com/Wyrelade/KKND-Decomp); [GitHub API](https://api.github.com/repos/Wyrelade/KKND-Decomp)
- retrokit (nemo22): a "Headless-Ghidra toolkit for reverse engineering 32-bit DOS and Win32 games (1993-2010): own LE/LX loader, Watcom calling conventions, library signatures, MCP server". It handles DOS/4GW, DOS/32A, PMODE/W, CauseWay and DOS/4G bind. It ships `watcom` and `watcomreg` cspecs with auto-detection and Open Watcom CRT/math/C++ signatures, and runs `retrokit mcp GAME_analysis` (stdio, `claude mcp add retrokit -- retrokit mcp <path>`). It needs Ghidra 12.x, JDK 21+ and Python 3.10+. It is not a matching-decompilation tool. Apache-2.0, 31 stars, created 2026-10-13, and "largely written with Claude through Claude Code". — [nemo22/retrokit](https://github.com/nemo22/retrokit); [GitHub API](https://api.github.com/repos/nemo22/retrokit)
- rebrew (maci0): a "Compiler-in-the-loop decompilation workbench for binary-matching game reversing". It has a GA matcher, live Ghidra ops, objdiff hooks and "six packaged agent workflows". It needs "Python 3.13+ and Linux x86_64 with Docker for shipped compiler profiles. Wine, DOSBox, and native compiler runtimes live inside their images". The repo contains `docs/codegen/watcom/open-watcom.md`, `docs/OMF_NOTES.md` and `src/rebrew/formats/omf16.py`. Its sister repo recompile-toolchains has a `base-dosemu` image and MSC 5.1/6.0 MS-DOS images, but no Watcom image was visible. MIT, 10 stars, pushed 2026-10-19. — [maci0/rebrew](https://github.com/maci0/rebrew); [repo tree via GitHub API](https://api.github.com/repos/maci0/rebrew/git/trees/main?recursive=1); [recompile-toolchains tree](https://api.github.com/repos/maci0/recompile-toolchains/git/trees/main?recursive=1)
- wcdatool: "Watcom Disassembly Tool to aid disassembling DOS applications created with the Watcom Toolchain". — [fonic/wcdatool](https://github.com/fonic/wcdatool)

### Inferences
- **decomp.wtf cannot import UFO2P.EXE or TACP.EXE as is.** The from-scratch pipeline depends on splat/spimdisasm (MIPS), decomp-toolkit (PPC), ds-decomp and luvdis (ARM). There is no LE or x86 splitter, and "PC" is "coming".
- **The x86 path that exists is fork mode only.** It works on an already-set-up community project built with that project's own build and judged by objdiff.
- **Being archived lowers the risk of building on it but means no upstream help.** The MIT license allows forking. Pin v0.10.6 or fork at the last commit.
- **Suggested WSL2 install outline.** I have not run any of these steps.
  - **Option A (official):** run the Windows `install.ps1`. It creates its own WSL2 distro `decomp-wtf` (Debian) next to the existing Ubuntu.
  - **Option B (more controllable, uses the existing Ubuntu):**
    1. In the Ubuntu WSL2 shell, install `git` and `curl`, and install uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`). uv pulls Python 3.12+.
    2. Either run the Linux installer (`curl -fsSL https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/site/public/install.sh | bash`, after reading it first), or, for development, `git clone https://github.com/i12bp8/decomp.wtf` (or a personal fork) under `~/src` in the Linux filesystem, not `/mnt/c`, then run `uv sync` and `uv run decomp`.
    3. Optional Ghidra drafts: install JDK 21+ and run `decompnet toolchain install ghidra`, which pins Ghidra 12.1.4.
    4. Connect Claude Code: `claude mcp add decomp -- decomp mcp`.
    5. Smoke-test with the bundled Demo Quest 64 and `uv run pytest`.
  - Docker Desktop is not required. The repo `Dockerfile` is only useful if you want the server/room mode in a container.
- **What a Watcom/DOS/4GW target would need, by component (my mapping from the code layout):**
  1. **Importer/splitter (`rom/`):** an LE parser and function splitter. Options are to adapt KKND-Decomp's LE/OMF readers and splitter, retrokit's LE loader, or ghidra-lx-loader output. It must handle the DOS/4GW bound stub, object table, page map and fixups.
  2. **Toolchain (`toolchains.toml`):** add Open Watcom 1.9/2.0 `wcc386` (KKND shows it can match Watcom 10.x output) and possibly the original Watcom 10.x/11.0 under DOSBox/dosemu (the rebrew/recompile-toolchains pattern). Add flag discovery.
  3. **Object format (`elfobj.py`, `compiler.py`):** Watcom emits OMF, while the matcher appears ELF-centric (`elfobj.py`). Add an OMF reader, or convert OMF to ELF.
  4. **Matcher:** link at the real address, or splice the function into the LE image and compare with relocations masked and targets checked, as KKND does. Add whole-EXE SHA-1 verification.
  5. **Drafts (`forks/ghidra.py`):** install an LE loader extension and the Watcom cspec into the pinned Ghidra so drafts use watcall. Today it imports with default loaders.
  6. **Agent guide (`app/guide/`):** add a `watcom.md`. The existing x86.md is MSVC-only.
  7. **Export:** a `build.py` that rebuilds the LE via wlink or splice.
  8. **Platform registration:** add PC/DOS to the platform table and to UI detection.
- **Fallback option:** the closest working reference for a Watcom DOS/4GW byte-identical rebuild is KKND-Decomp (CC0). Combining its build/verify approach with retrokit (Ghidra LE + watcall + MCP) and decomp.wtf's agent harness ideas (claims, permuter, twins, shared header, guardrails) may beat forcing decomp.wtf itself.

### Gaps
- The real number of open issues before archiving is unknown. The API reports 0, likely because issues were closed or disabled at archive time.
- objdiff support for 32-bit OMF/Watcom objects was not verified. I found no source.
- Whether decomp.wtf's matcher (`rom/match.py`, `elfobj.py`) can be generalised to x86 without a rewrite was not verified at code level. Only file names and README were read.
- I could not verify the reported "Theme Hospital Watcom 10.6 matching decomp" in search. It may not exist.
- The exact Watcom version and flags used for X-COM Apocalypse were not researched here.

## 2. REA (Reverse Engineer Anything): what it is, MCP exposure of Ghidra/IDA, deep native analysis requirements, Ghidra-only use, Windows/WSL2, licensing/pricing

### Takeaway
REA is an MIT-licensed Node.js MCP server and CLI (`rea-agents`). It gives coding agents (Claude Code and others) one interface for native binaries, JS/Electron, .NET, Android, firmware, pcaps and websites. For native binaries it needs exactly one backend: Hopper, Ghidra 12.1.x (free; experimental on Windows), or IDA (Windows, with an existing MCP registration). Ghidra alone is enough, and running inside WSL2 Linux is the documented route. I found no paid tier. Its docs say nothing about LE/DOS formats or the Watcom convention.

### Cited Findings
- "One MCP for reverse engineering across binaries, applications, and runtime behavior." Native analysis "can use an existing Hopper, Ghidra, or IDA installation". "Analysis runs locally, and results include the evidence and limitations behind each conclusion." — [morluto/rea README](https://github.com/morluto/rea)
- "REA-authored code is licensed under MIT". Commercial tools (IDA Pro, Hopper, JEB) need the user's own licenses. — [morluto/rea README](https://github.com/morluto/rea)
- Native backends: Hopper (macOS or Linux), "Ghidra (macOS or Linux; experimental on Windows): free, but needs an existing Ghidra 12.1.x installation and a 64-bit JDK 21 or newer", "IDA (Windows): for an existing IDA setup with an MCP registration". — [rea.tools Native guide](https://rea.tools/guides/native/)
- CLI example: `npx -y rea-agents@latest function <path> <name> --provider ghidra --json`. "Each CLI invocation imports and analyzes the binary, then closes its session... Your agent's MCP queries reuse the imported binary while that session is open." — [rea.tools Native guide](https://rea.tools/guides/native/)
- Requirements: Node.js 22.19+, 24.11+ or 26+. Setup: `npx rea-agents@latest setup --client claude_code`, which "adds its MCP connection and an investigation skill, keeps a backup of existing configuration". Health check: `npx -y rea-agents@latest doctor --client claude_code --json`. — [rea.tools Get started](https://rea.tools/get-started/)
- WSL: "If your agent runs in WSL, install Node.js and REA inside that Linux environment and use Linux paths there." — [rea.tools Get started](https://rea.tools/get-started/)
- The guides index lists Set up REA, "Native binaries (Recover a sound-pan calculation)" starting from "a Windows game executable", JS & Electron, and Browser behavior. It mentions no pricing. — [rea.tools Guides](https://rea.tools/guides/)
- GitHub API: created 2026-04-14, pushed 2026-10-19T19:08Z, MIT, 334,851 stars, 84,612 forks, 1,249 open issues. The README cites a "300,000 GitHub stars" milestone. — [GitHub API repos/morluto/rea](https://api.github.com/repos/morluto/rea); [README](https://github.com/morluto/rea)

### Inferences
- **Ghidra-only use matches the owner's local-only legal preference.** Run Claude Code, Node and REA inside the Ubuntu WSL2 distro with Ghidra 12.1.x and JDK 21, which REA treats as Linux, not the "experimental" Windows mode.
- **REA should be used for exploratory "understand the logic" questions, not as the matching engine.** It has no compile-and-compare loop.
- **REA relies on Ghidra's loaders.** Ghidra has no built-in LE loader (see section 3), so REA can only analyze UFO2P/TACP if an LE loader extension (ghidra-lx-loader or retrokit's) is installed in that Ghidra, or if the LE is pre-converted. This is untested.
- **The star count is anomalous.** 334k stars for a 6-month-old repo is far above typical tools. Treat popularity metrics with caution, although the API reports it as stated.

### Gaps
- REA does not document which MCP tool names it exposes, or how it drives Ghidra internally (PyGhidra, headless, or a bridge).
- Whether REA's Ghidra provider honours installed extensions (LE loader) or lets you choose a loader/cspec is not documented.
- I found no statement on pricing or paid tiers. The absence of any mention suggests it is free, but this is unconfirmed.
- The page https://rea.tools/first-investigation/ was not fetched separately. Get started covers a "first investigation" using notes-example.zip.

## 3. Ghidra: LE / DOS/4GW loading, unbinding, watcall, GhidraMCP and alternatives, headless/Docker, ghidra.decomp.dev

### Takeaway
Stock Ghidra (latest 12.1.4, released 2026-09-21) has no LE/LX loader and no watcall convention. Both feature requests have been open since 2019. Third-party extensions fill the gap. lastonesky/ghidra-lx-loader v12.1.4-1 (2026-10-10) loads DOS/4GW LE on Ghidra 12.1.x and ships a Watcom cspec with `__watcall`. retrokit bundles its own LE loader, Watcom cspecs and an MCP server. LaurieWired's GhidraMCP 2.0 (2026-10-10) now supports Ghidra 12.1.4 and a GUI-less PyGhidra headless mode. bethington/ghidra-mcp is a heavier alternative with Docker and Ghidra-server support.

### Cited Findings
**LE loader status**
- The built-in loaders in `Ghidra/Features/Base/.../app/util/opinion` include MzLoader, NeLoader, PeLoader, OmfLoader, ElfLoader, MachoLoader, CoffLoader, ComLoader, etc. There is no LE/LX loader. — [GitHub API contents listing](https://api.github.com/repos/NationalSecurityAgency/ghidra/contents/Ghidra/Features/Base/src/main/java/ghidra/app/util/opinion)
- Issue #532 "DOS MZ "LE" loader support" has been open since 2019-04-29. — [ghidra#532](https://github.com/NationalSecurityAgency/ghidra/issues/532)
- Latest release is Ghidra_12.1.4_build, published 2026-09-21. — [GitHub API releases/latest](https://api.github.com/repos/NationalSecurityAgency/ghidra/releases/latest)
- yetmorecode/ghidra-lx-loader (the "Ultimate Ghidra loader for the LX/LE executable file format (OS/2, DOS4GW, VxD)") handles LX, LE (DOS/16, DOS/4), DOS32A unbound LE/LX and VxD. Tested DOS/4GW titles include F1 Manager Professional and Redguard. It has full page-map and fixup support, labels per fixup and page, base-address/selector override, and an option to map the MZ header to an overlay. Its latest release is v12.0.1 (2026-01-29), last push 2026-08-29, 85 stars, Apache-2.0. — [yetmorecode/ghidra-lx-loader](https://github.com/yetmorecode/ghidra-lx-loader); [GitHub API](https://api.github.com/repos/yetmorecode/ghidra-lx-loader)
- lastonesky/ghidra-lx-loader fork, v12.1.4 (2026-10-09): "Requires Ghidra 12.1.x. Ghidra 12.0.x is no longer supported because Ghidra 12.1 changed... the Loader API... the built-in x86 compiler specs". "Verified imports: DOS/4GW LE, OS/2 LX and Windows VxD samples." — [lastonesky release v12.1.4](https://github.com/lastonesky/ghidra-lx-loader/releases/tag/v12.1.4)
- lastonesky v12.1.4-1 (2026-10-10): "Watcom compiler spec completed: full data organization plus `__cdecl`, `__stdcall`, `__thiscall` and `__fastcall` in addition to `__watcall`". Code and data objects get correct permissions. Entry, import and name tables are parsed. "Picking the convention that actually produced the module is essential... a wrong convention makes every recovered signature systematically wrong." — [lastonesky release v12.1.4-1](https://github.com/lastonesky/ghidra-lx-loader/releases/tag/v12.1.4-1)
- Install: "File > Install Extensions... > +, select the zip and restart Ghidra." — [lastonesky release v12.1.4](https://github.com/lastonesky/ghidra-lx-loader/releases/tag/v12.1.4)
- retrokit: its own LE/LX loader is compiled with javac against the local Ghidra by `retrokit install-loader` (re-run after Ghidra updates). It has `watcom` and `watcomreg` cspecs with auto-detection (`--cspec` override), functions at fixup targets, in-function switch tables, and param counts from `ADD ESP,n`. It recommends against the deep-analysis analyzers (slow). — [nemo22/retrokit](https://github.com/nemo22/retrokit)

**watcall in stock Ghidra**
- Issue #156 "Open/Watcom C/C++" has been open since 2019-03-11. — [ghidra#156](https://github.com/NationalSecurityAgency/ghidra/issues/156)
- Ghidra's `GenericCallingConvention` enum lists cdecl, fastcall, stdcall, thiscall, vectorcall and unknown, with no watcall. — [Ghidra API docs](https://ghidra.re/ghidra_docs/api/ghidra/program/model/data/GenericCallingConvention.html)

**Unbinding the DOS/4GW stub**
- A VOGONS user reports using "SB /U" from DOS/32A's sb.exe to unbind the stub and extract the LE. The result was readable by IDA's file dumper. Other users report failures (a ".LC" output that would not run) and a manual approach that cuts the file at the LE header offset. PMODE/W tools can also bind and unbind. — [VOGONS thread](https://www.vogons.org/viewtopic.php?p=1377457); [VOGONS](https://www.vogons.org/viewtopic.php?p=1335143); [DOSBox wiki DOS32A](https://www.dosbox.com/wiki/TOOLS:DOS32A)
- The KKND matching decomp works directly on the bound "MZ stub + DOS/4GW Pro + LE" image without unbinding. It splices functions back into the LE image and checks the SHA-1. — [KKND-Decomp](https://github.com/Wyrelade/KKND-Decomp)

**GhidraMCP (LaurieWired) and alternatives**
- GhidraMCP README: "Install Ghidra 12.1.4", install the release zip via File > Install Extensions, enable GhidraMCPPlugin, then `claude mcp add ghidra -- uvx --from git+https://github.com/LaurieWired/GhidraMCP ghidra-mcp --ghidra-server http://127.0.0.1:8080/`. Headless mode: "ghidra-mcp can also import and analyze a binary itself using PyGhidra, with no Ghidra GUI running. This needs Python 3.10–3.13, the GhidraMCP extension installed... and GHIDRA_INSTALL_DIR set": `uvx --python 3.13 --from "ghidra-mcp[headless] @ git+https://github.com/LaurieWired/GhidraMCP" ghidra-mcp --headless --binary /path/to/target` (`--project DIR` to persist). — [GhidraMCP README](https://github.com/LaurieWired/GhidraMCP)
- GhidraMCP releases: 2.0 on 2026-10-10, 1.4 on 2025-06-23. Apache-2.0, 11,411 stars, 94 open issues. — [GitHub API releases](https://api.github.com/repos/LaurieWired/GhidraMCP/releases); [GitHub API repo](https://api.github.com/repos/LaurieWired/GhidraMCP)
- bethington/ghidra-mcp: "200+ MCP tools... GUI plugin + headless server, lazy tool loading, convention enforcement, batch operations, Ghidra Server integration, and Docker deployment." Apache-2.0, 5,789 stars, pushed 2026-10-16. — [GitHub API bethington/ghidra-mcp](https://api.github.com/repos/bethington/ghidra-mcp)
- PyGhidra (since Ghidra 11.3) "provides direct access to the Ghidra API within a native CPython 3 interpreter using JPype". Launch with `./support/pyghidra`. Ghidra 11.3+ needs JDK 21. — [Ghidra 11.3 What's New](https://ghidradocs.com/11.3_PUBLIC/docs/WhatsNew.html)
- decomp.wtf already drives headless Ghidra via `support/analyzeHeadless ... -postScript` with a Java export script. — [forks/ghidra.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/forks/ghidra.py)

**Shared Ghidra server**
- ghidra.decomp.dev is a "Ghidra Panel" login page under decomp.dev with "Continue with Discord", linking to github.com/encounter/ghidra-panel. It does not say which projects are hosted or the version. — [ghidra.decomp.dev](https://ghidra.decomp.dev)
- Decomp projects use shared Ghidra servers. LEGO Island (isledecomp) keeps a shared repository that needs permission to push. Twilight Princess adds users through a users.yaml PR. — [isle CONTRIBUTING](https://git.mattkc.com/isledecomp/isle/src/commit/3ba1d354e2fd665ac0a7f73420160548d5c8fe9a/CONTRIBUTING.md); [tp Contributing](https://git.new.deadbsd.org/falso/tp/raw/commit/7723ab15f7ab0ab4f974ae1e32260c28166364d6/docs/Contributing.md)

### Inferences
- **Recommended local stack:** Ghidra 12.1.4 + JDK 21 inside the WSL2 Ubuntu, the lastonesky ghidra-lx-loader v12.1.4-1 extension (LE + `__watcall` cspec), and GhidraMCP 2.0 in `--headless` PyGhidra mode for Claude Code. Alternatively retrokit, which has its own LE loader, Watcom cspec auto-detection and MCP in one package and is aimed at exactly this class of game.
- **Pick one loader.** Pinning matters because Ghidra 12.1 broke loader APIs. Do not mix loader extensions in the same Ghidra install.
- **Unbinding is probably unnecessary for Ghidra.** The LX loaders and KKND both handle bound MZ+LE files. Keep `sb /u` as a fallback for tools that need a bare LE.
- **ghidra.decomp.dev is decomp.dev's community server, gated by Discord.** It is unlikely to host ReverseApoc. A self-hosted Ghidra Server (in Docker or WSL2) is the equivalent for a team.
- **Headless Ghidra in Docker is feasible.** bethington/ghidra-mcp advertises Docker deployment, and analyzeHeadless or PyGhidra run on Linux. For a single developer, a WSL2 install without Docker is simpler.

### Gaps
- I did not find whether yetmorecode's upstream ghidra-lx-loader has merged lastonesky's Watcom cspec.
- None of the LX loaders were tested on UFO2P.EXE or TACP.EXE. Their DOS/4GW Professional variant and any compression or overlay quirks are unknown.
- I did not fetch a dedicated Docker image for headless Ghidra (for example a community `ghidra-headless` image).
- Pyghidra-mcp and Ghidrathon status were not individually researched.

## 4. IDA Free 9.x: cloud decompiler limitation, local disassembler, LE support, ida-pro-mcp applicability

### Takeaway
The claims are confirmed. IDA Free has a local x86/x64 disassembler but only a cloud decompiler, which needs an internet connection and does part of the work remotely. It is for non-commercial use only, and has no IDAPython or SDK. The pricing table lists only "3 file formats" (PE, ELF, Mach-O), so LE is very likely unsupported. ida-pro-mcp explicitly says "IDA Free is not supported". IDA Free is therefore not a viable automation backend for this project. Even as a last resort it is only a manual viewer.

### Cited Findings
- IDA Free: "x86/x86-64bit cloud-based decompiler". The disassembler supports x86/x86-64 and 32/64-bit apps. "No, IDA Free is dedicated to non-commercial use only." "No, you don't have access to IDA C++ SDK or IDAPython API with IDA Free." Results can be saved. — [hex-rays.com/ida-free](https://hex-rays.com/ida-free)
- Pricing comparison: IDA Free has "3 file formats" (PE, ELF, Mach-O) and a "Cloud Only" decompiler. IDA Home has "All file formats", is "Cloud Only", and starts "from $365 per year". IDA Pro Essential is "€1 099 per year" ("2, cloud"), Expert "€4 999 per year" ("2 to 6, local") and Ultimate "€8 599 per year" ("All, local"). — [hex-rays.com/pricing](https://hex-rays.com/pricing)
- Hex-Rays decompiler docs (9.x): cloud decompilers need an internet connection because part of the decompilation is performed remotely. — [Hex-Rays docs 9.3 decompiler overview](https://docs.hex-rays.com/ida-9.3/core/decompiler/overview) (found via search snippet; not fetched directly)
- The full IDA product lists "Linear Executable (LX), Linear Executable (LE)" among supported formats. — [Hex-Rays supported file formats 9.1](https://docs.hex-rays.com/9.1/user-guide/disassembler/supported-file-formats) (search snippet)
- An unofficial VOGONS reply about older versions says the free IDA "does not contain support for loading LE/LX executables". — [VOGONS](https://www.vogons.org/viewtopic.php?p=1377457) (search snippet)
- ida-pro-mcp prerequisites: "IDA Pro (8.3 or higher, 9 recommended), **IDA Free is not supported**". The recommended route is `idalib-mcp` headless, which needs idalib (an IDA Pro feature). MIT, 13,020 stars, pushed 2026-09-26. — [mrexodia/ida-pro-mcp README](https://github.com/mrexodia/ida-pro-mcp); [GitHub API](https://api.github.com/repos/mrexodia/ida-pro-mcp)
- REA's IDA provider is Windows-only and needs "an existing IDA setup with an MCP registration". — [rea.tools Native guide](https://rea.tools/guides/native/)

### Inferences
- IDA Free cannot load the LE executables (only PE/ELF/Mach-O are listed), its decompiler is cloud-only, and it cannot run MCP. It does not fit the project. Even an unbound LE would probably not load in Free.
- If IDA were ever needed, local decompilation of 32-bit x86 would require at least IDA Pro Expert (local decompilers). That conflicts with the budget and the local-only goal unless purchased.

### Gaps
- I found no official Hex-Rays statement specific to IDA Free 9.x and LE/LX. The conclusion rests on the "3 file formats" table plus an older forum post.
- The exact IDA Free version number on the download page was not captured.

## 5. Understand-Anything and Groma: what they do, install/invocation, suitability for (a) understanding decomp.wtf quickly and (b) ReverseApoc onboarding docs, licenses and cost

### Takeaway
Both are MIT-licensed and free. Understand-Anything is a Claude Code plugin (also available for Codex and others). It uses tree-sitter plus a multi-agent LLM pipeline to build a knowledge graph with a dashboard, guided tours, chat and an `/understand-onboard` onboarding guide. It is good for quickly learning decomp.wtf's roughly 40-module Python codebase, but costs LLM tokens. Groma (groma.md) is a deterministic, offline, no-AI CLI that scans code into a C4 architecture map stored as OKF Markdown in Git. Agents curate it through its CLI, and it is better suited to durable, reviewable onboarding docs for ReverseApoc. Python is "Available" and C/C++ are "Experimental" in Groma.

### Cited Findings
**Understand-Anything**
- "Understand Anything is a Claude Code Plugin that analyzes your project with a multi-agent pipeline, builds a knowledge graph of every file, function, class, and dependency, then gives you an interactive dashboard." — [README](https://github.com/Egonex-AI/Understand-Anything)
- Install: `/plugin marketplace add Egonex-AI/Understand-Anything`, then `/plugin install understand-anything`. Other platforms use `install.sh` or `install.ps1`, which clone to `~/.understand-anything/repo`. — [README](https://github.com/Egonex-AI/Understand-Anything)
- Commands: `/understand` (writes `.ua/knowledge-graph.json`; incremental later), `/understand-dashboard`, `/understand-chat`, `/understand-diff`, `/understand-explain <file>`, "`/understand-onboard` Generate an onboarding guide for new team members", `/understand-domain`, `/understand --auto-update` (post-commit hook), and `/understand src/frontend` to scope to a folder. — [README](https://github.com/Egonex-AI/Understand-Anything)
- "Heads up on token usage: The initial /understand analyzes your whole codebase and can consume a significant number of tokens on large projects. We recommend running it on a token plan / subscription, or using a local model." — [README](https://github.com/Egonex-AI/Understand-Anything)
- "Tree-sitter (deterministic)... LLM (semantic)" hybrid with 5 agents for `/understand`. A committed graph can be viewed without an LLM: `npx https://github.com/Egonex-AI/Understand-Anything/releases/latest/download/understand-anything-viewer.tgz /path/to/project` (Node >= 18). — [README](https://github.com/Egonex-AI/Understand-Anything)
- MIT, created 2026-03-15, pushed 2026-10-12, 86,996 stars, 330 open issues. — [GitHub API](https://api.github.com/repos/Egonex-AI/Understand-Anything)

**Groma (groma.md)**
- "groma.md scans your code into a first C4 architecture map. You can curate it into the architecture you would explain to a new teammate, either yourself or with your coding agent... Everything is plain Markdown in your repository." — [README](https://github.com/MrLesk/groma.md)
- "groma.md is free, MIT-licensed, and runs locally with no account or backend. Scans run offline... deterministic code analysis (fixed rules) and call no AI service... You can use groma.md entirely without AI." — [README](https://github.com/MrLesk/groma.md)
- Install: `npm i -g groma.md backlog.md` (Backlog.md optional), then `groma web`, which serves a map on localhost:4747. Agent use: `groma agent-instructions`, `groma view --plain`, `groma view <file>`. "Setup registers groma.md in your AGENTS.md or CLAUDE.md". `groma export ./site` publishes a static site. Architecture is stored in a `groma/` folder as an Open Knowledge Format 0.2 bundle. — [README](https://github.com/MrLesk/groma.md)
- Languages: Python, Go, Java, Rust, TS/JS and others are "Available". C, C++ and NASM x86-64 assembly are "Experimental". Other languages can be added as scanner plugins. — [README Languages](https://github.com/MrLesk/groma.md)
- MIT, created 2026-07-11, pushed 2026-10-19, 296 stars, 14 open issues. — [GitHub API](https://api.github.com/repos/MrLesk/groma.md)

### Inferences
- **(a) Understanding decomp.wtf in a Claude Code session:** Understand-Anything fits best (plugin install, `/understand`, then `/understand-chat "how does a match get judged?"`), with a one-off token cost. Running it scoped to `src/decompnet` limits cost. Groma also works on Python and costs no tokens, but its output is a C4 map, not explanations. For a 40-module codebase, reading the README layout table plus targeted file reads may be nearly as fast.
- **(b) ReverseApoc onboarding docs:** Groma's Git-versioned Markdown architecture, PR-reviewable and static-site exportable, suits long-lived developer docs. Its AGENTS.md/CLAUDE.md registration helps Claude Code sessions. Understand-Anything's `/understand-onboard` plus a committed `.ua/` graph (viewable without an LLM) gives a richer first-day tour, but its output is LLM-generated and needs review. Both handle C only experimentally (Groma) or via tree-sitter (UA), and neither understands decomp-specific concepts like matched or nonmatching asm.
- **Integration caveat:** both tools modify the target repo (`.ua/`, `groma/`, CLAUDE.md block), which should be planned for, since ReverseApoc keeps its own CLAUDE.md conventions.

### Gaps
- I did not verify which tree-sitter languages Understand-Anything supports (C/Python coverage) or real token costs for a codebase of decomp.wtf's size.
- Groma's Windows support is not stated (only "macOS requires Apple Silicon"). Running it inside WSL2 is presumably fine but unverified.
- Neither tool's behaviour on large generated assembly trees (asm/nonmatchings) was assessed.

## 6. Follow-up: effort comparison, forking decomp.wtf vs own pipeline (KKND + Theme Hospital + retrokit)

Method: I took the file list and byte sizes from `gh api repos/i12bp8/decomp.wtf/git/trees/main?recursive=1` and counted lines with `curl raw.githubusercontent.com/... | wc -l` for every source file, on 2026-10-19. I read key modules (rom/match.py, elfobj.py, scoring.py, compiler.py, rom/detect.py, app/engine.py, app/forkengine.py, forks/*.py, app/tools.py) over raw URLs. Nothing was cloned or executed. Effort figures are my estimates for one developer with Claude Code and are not sourced.

### Takeaway
decomp.wtf is about 21.7k lines of Python, plus 3.8k lines of plain JS/CSS/HTML GUI and 5.5k lines of tests (40 files). Roughly 60% of it does not depend on the platform: claims, MCP tools, agent runner, GUI, collab rooms, permuter, twins and scoring. Its from-scratch ("ROM") mode is hard-wired to MIPS. `rom/match.py` hard-codes R_MIPS_* relocations and 4-byte words, and `engine.py` switches between MIPS and GBA with `if platform == "gba"` branches. There is no platform registry. Adding "dos-watcom" there means a new x86 matcher, a new splitter and new export paths, about 16-27 dev-days, so it is not cheaper than the own pipeline. Its fork mode is a different story. It accepts any local git repo that "builds with configure.py + ninja and produces objdiff.json". It judges with objdiff-cli, which supports "x86, x86_64 (PC)", and it does not ban `#pragma`. So an own pipeline that also emits per-unit ELF target objects and an objdiff.json could get decomp.wtf's whole agent layer for about 3-7 extra days. That hybrid is the recommendation.

### Cited Findings
**Module inventory (line counts from raw files)**
- **Totals:** src/decompnet is about 26,640 lines including GUI static files (app.js 2,651, app.css 664, index.html 478), agent guides (*.md, 587), toolchains.toml (509) and DecompWtfExport.java (49). That leaves about 21.7k lines of Python. tests/ has 40 files and 5,550 lines. — [repo tree](https://github.com/i12bp8/decomp.wtf)
- **Platform-agnostic, reusable as-is (about 13.4k lines):**
  - claims/coordination `network.py` 779;
  - SQLite `store.py` 126;
  - MCP tools `app/tools.py` 394. Its tools are project_info, claim_function, get_function, compile_and_diff, release_function, get_context, edit_context, rename_symbol, split_function, read_data, list_functions, add_note, search_notes, find_similar, guide, read_file, search_code, edit_file, file_status, split_file and work;
  - agent runner `app/agents.py` 1,110, plus bridge 179, chat 251 and connect 105;
  - GUI/API server `app/server.py` 1,244 plus static GUI 3,793 (plain JS, no Node build);
  - collab rooms (`collab.py` 844, `forkroom.py` 197);
  - CLI (`app/cli.py` 478, `cli.py` 182, coordinator `server.py` 325, launcher 65);
  - twins 694;
  - source-level permuter (`permuter.py` 239 + `app/permute.py` 164);
  - `scoring.py` 287, which uses capstone and already maps ("x86", False) to CS_MODE_32;
  - compile orchestration `compiler.py` 167, with a `cmd` template using {src}, {obj} and {include}, bwrap/docker/WSL sandbox and resource caps;
  - other small modules: project 215, policy 50, seeds 126, similarity 72, textedit 66, jobs 80, limits 52, updates 261, service 135, registration 100, public 60, upstream 85, local 49;
  - generic guides 210 lines.
  — [app/tools.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/app/tools.py); [scoring.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/scoring.py); [compiler.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/compiler.py)
- **Fork mode (about 3.9k lines, objdiff-judged, mostly arch-agnostic):** `app/forkengine.py` 2,396, `forks/project.py` 550, objdiff 198, drafts 164, datadiff 186, literals 133, csource 105, policy 80, catalog 52. — [forks/project.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/forks/project.py)
- **Mixed:** `app/engine.py` 1,730 (ROM-mode engine; claims/attempt logic is generic, but import/target/evaluate/split/export dispatch is per platform); `elfobj.py` 287 (generic ELF function extraction; `MACHINES` already includes `EM_386 -> "x86"`; "Anything not listed masks the 4 bytes at r_offset, which is right for most absolute/PC32 relocs").
- **Platform-specific (about 6.2k lines):**
  - splitters and readers 1,887: split.py 438 (splat), n64 116, n64code 256, psx 139, ps2 36, gba 176, gba_candidates 140, luvdis_run 39, overlays 119, chd 260, detect 85, symbols 83;
  - matchers 661: match.py 415 (MIPS), match_arm.py 246;
  - export/rebuild 1,118: export 339, export_build 332, export_gba 147, export_gba_build 300;
  - dtk/DS scaffolding 1,887: scratch_dtk 740, scratch_dsd 281, dtksplits 268, ds_template 598;
  - handwritten.py 240 (mips/ppc);
  - per-platform guides 377;
  - Ghidra drafts 115 (ghidra.py 66 + Java 49);
  - host/toolchains 1,257 (toolchains.py 374, toolchains.toml 509, hostenv 188, wsl 186).
- **MIPS hard-coding in the from-scratch matcher:** `rom/match.py` defines `R_MIPS_32, R_MIPS_26, R_MIPS_HI16, R_MIPS_LO16, R_MIPS_GPREL16`. `_patch()` raises on any other type. It unpacks code as `len(code)//4` 32-bit words, and `canonical_target` returns `FunctionObj(..., "mips", ...)`. — [rom/match.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/rom/match.py)
- **GBA precedent for a second arch:** `match_arm.py` works "without relocations from a disassembler: for each relocation in the candidate, the original's bytes at the same place say what it refers to". `engine.py` special-cases it in `_target_obj`, `_evaluate`, `_import_gba`, `split_function` and `export_rom`. — [rom/match_arm.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/rom/match_arm.py); [app/engine.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/app/engine.py)
- **No platform registry:** there are only dicts: `PLATFORM_STATUS` and `PLATFORM_COMPILERS` in engine.py, `PLATFORMS` in rom/detect.py (n64, psx, ps2, gba), and `M2C` in forks/drafts.py. — [engine.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/app/engine.py); [rom/detect.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/rom/detect.py)
- **Fork-mode guardrails differ:** ROM-mode `compiler.check_source` forbids asm, INCLUDE_ASM, `.incbin`, section/naked attributes, `#pragma` and system includes. Fork mode's `_CHEAT` forbids asm, INCLUDE_ASM, GLOBAL_ASM, INCLUDE_RODATA, `.incbin` and asm includes, but not `#pragma`, so Watcom `#pragma aux` would pass. — [compiler.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/compiler.py); [forkengine.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/app/forkengine.py)
- **Fork mode accepts local repos:** `forkengine.py` line 411 accepts `_REPO.match(repo) or (local.is_dir() and (local / ".git").exists())`. `forks/project.py` covers "configure: other configure.py + ninja projects" and, once "its build has produced objdiff.json, decomp.wtf takes over". — [forkengine.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/app/forkengine.py); [forks/project.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/forks/project.py)
- **Fork-mode drafts:** m2c is tried first. Otherwise `ghidra.decompile_object(unit.target, ...)` runs when "unit.target exists and ghidra.available()", so Ghidra analyses the unit's ELF target object and needs no LE loader. Autopilot "needs m2c" and `drafts.M2C` has no x86 entry, so autopilot would be unavailable. — [forkengine.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/app/forkengine.py); [forks/drafts.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/forks/drafts.py)
- **objdiff supports x86:** the README lists "x86, x86_64 (PC)". Apache-2.0, pushed 2026-10-19. decomp.wtf's objdiff module calls itself "the community's diff engine, for every architecture it supports". — [objdiff README](https://github.com/encounter/objdiff); [forks/objdiff.py](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/src/decompnet/forks/objdiff.py)
- **Dependencies (pyproject):** requires-python >=3.12; capstone>=5.0.9, mcp>=2.3.0, pyelftools>=0.33, splat64[mips], spimdisasm, rabbitizer, httpx, uvicorn, ninja, truststore (win32), zstandard (linux); uv_build backend; pytest dev group. Node appears only in `site/package.json` (Cloudflare website), not in the app. — [pyproject.toml](https://raw.githubusercontent.com/i12bp8/decomp.wtf/main/pyproject.toml)
- **Tests:** 40 test files / 5,550 lines, including test_claims, test_network, test_agents, test_app_server, test_forks (474), test_fork_judge, test_rom, test_speed and test_wsl. They run with `uv run pytest`. — [repo tree](https://github.com/i12bp8/decomp.wtf)
- **Toolbelt:** wibo is already in decomp.wtf's pinned toolbelt ("decomp-toolkit, maspsx and wibo are in the pinned toolbelt"). — [README Built on](https://github.com/i12bp8/decomp.wtf)

### Inferences (effort estimates: one developer plus Claude Code, my judgement)
**A. Adding a "dos-watcom" platform to decomp.wtf's from-scratch mode**

| Extension point | Work | Reusable pieces | Days |
|---|---|---|---|
| Platform registration and dispatch | Add to `detect.PLATFORMS`/`Picked` (MZ+LE sniff), `PLATFORM_STATUS`/`PLATFORM_COMPILERS`, and generalise about 8 `platform == "gba"` branches in engine.py into a dispatch table | none | 1.5-2.5 |
| LE reader and splitter | x86 function records (bytes, asm text via capstone, refs from LE fixups) in the GBA style, not `split.RomFunction`, whose `AsmLine.word` is a 4-byte MIPS word | KKND le.py, find_functions.py; retrokit/Ghidra function list as a seed | 2-4 |
| Toolchain | toolchains.toml entry for Open Watcom wcc386 under wibo, or OW 2.0 Linux; wrapper `cmd` = wcc386, then OMF-to-ELF, writing func.o (fits `compiler.py`'s {src}/{obj} template unchanged); whitelist `#pragma aux` in `check_source` | Theme Hospital cc.py flags, wibo 1.2.0 | 1-2 |
| Object reader | OMF to ELF. `elfobj` and `scoring` already handle EM_386 and x86-32 and the default 4-byte mask fits R_386_32/PC32, so conversion is sufficient at this layer | omf2elf.py (GPLv3) as a subprocess | 0.5-1 (own permissive rewrite: 3-5) |
| Matcher | New `rom/match_x86.py` modelled on match_arm (246) plus match.py data placement: variable-length instructions, R_386_32 vs PC32, target relocs from LE fixups, Watcom inline switch tables in code, data checks | KKND build_kknd (mask relocs, check targets) | 3-5 |
| Export/splice | New `export_dos` | KKND in-place page splice + SHA-1 | 2-3 (not needed for pilot) |
| Ghidra drafts | ROM mode only uses m2c seeds; wire Ghidra or retrokit output into `seeds.py` | retrokit per-function C | 1-2 |
| Agent guide | `guide/watcom.md` (register convention, -5r/-s/-o flags, `#pragma aux`) | KKND COMPILER_ANALYSIS notes | 0.5 |
| GUI | platform names, status and map tweaks in app.js | | 0.5-1 |
| Learning curve, tests, WSL validation | in an unfamiliar 21.7k-line codebase | | 3-6 |
| **Total** | | | **about 16-27 d** (14-24 without export) |

- **Is OMF-to-ELF conversion enough?** At the object-reading and scoring layer, yes. For the from-scratch matcher, no: `rom/match.py` is MIPS-only and needs a new x86 linker-comparator. In fork mode it is enough, because objdiff does the comparison.

**B. Maintenance after a full fork**
- **Code owned:** about 21.7k Python, 3.8k GUI, 5.5k tests. Pruning the MIPS/PPC/ARM/DS platform code (about 6k) would leave about 15-16k Python plus GUI.
- **Main rot vectors:**
  - the external agent CLIs that `agents.py` (1,110 lines) shells out to, such as Claude Code and Codex flags;
  - the fast-moving `mcp>=2.3.0` SDK;
  - Ghidra 12.1.x API breaks (12.1 already broke LX loaders);
  - WSL host code.
- **No upstream:** the repo was created 2026-10-13 with about 96 commits, but v0.10.6 and 21.7k lines suggest earlier private development. Either way, there is no upstream to absorb fixes.

**C. Building decomp.wtf's agent layer from scratch in the own pipeline**
- MCP server with about 8-10 tools over the KKND oracle: 2-4 d.
- SQLite claims/leases with TTL for parallel agents: 1-2 d.
- Guardrails (source regex, MCP-only tool allowlist for headless Claude, revert on regression): 1-2 d.
- Web dashboard: 3-6 d (static HTML progress report instead: 0.5-1 d).
- Multi-agent runner (Claude Code + Codex + OpenAI-compatible loop): 2-5 d (Claude Code only via `claude -p` with an allowlist: 0.5-1 d).
- Twins, look-alikes and permuter: 3-5 d (optional).
- **Full parity: about 12-24 d. Minimum viable (MCP + claims + guardrails + Claude Code only + static report): about 5-9 d.**
- A 10-function unattended pilot does not strictly need the layer. Headless Claude Code with a CLAUDE.md and the KKND-style `match.py scratch.c` loop takes about 0.5-1 d, but has no claims and weaker guardrails.

**D. Hybrid (recommended)**
- The own pipeline is the oracle (KKND LE/splice/SHA-1, Theme Hospital configure.py/ninja/cc.py with wcc386 under wibo, omf2elf, retrokit discovery). It additionally emits:
  1. per-unit target ELF objects cut from the LE, with relocations from LE fixups (2-4 d, reusing omf2elf's ELF writer if GPLv3 is acceptable);
  2. `objdiff.json` (0.5 d).
- ReverseApoc, as a local git repo, is then opened in decomp.wtf fork mode, which provides:
  - the MCP tools (claim_function, compile_and_diff, read_file, search_code, edit_file, file_status);
  - claims and parallel agents;
  - the GUI;
  - one git commit per match;
  - undo when a match breaks;
  - Ghidra drafts on ELF targets.
- Small patches to a pinned decomp.wtf fork (1-3 d):
  - the `INCLUDE_ASM` stub convention for Watcom units;
  - an x86/Watcom guide;
  - "linked" logic that is dtk-specific and should be disabled;
  - autopilot unavailable.
- **Hybrid total:** own pipeline 13-24 d + 3-7 d, against own pipeline + agent layer 18-33 d (MVP) to 25-48 d (parity).

### Gaps
- I did not verify that objdiff-cli diffs ELF objects converted from Watcom OMF correctly (symbol sizes, section names, FLAT-group fixups).
- I did not verify how fork mode replaces stubs for a project whose asm stubs are not GNU-asm `INCLUDE_ASM` (KKND's gen_units style).
- I did not read KKND or Theme Hospital code myself. Their line counts come from the coordinator.
- These are estimates, not measurements. The biggest uncertainty is the x86 matcher (inline switch tables, data placement).
