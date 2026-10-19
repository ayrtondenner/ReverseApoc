# Stack Research

**Domain:** Byte-matching decompilation of a 1997 DOS/4GW Watcom 10.x LE game (X-COM: Apocalypse, UFO2P.EXE `ufo24` + TACP.EXE `tac4`)
**Researched:** 2026-10-19 (synthesised from local research only; no new web lookups)
**Scope:** Milestone 1 Phases 3-6 (round trip, compiler ID, split and first matches, reporting and agent pilot). Phases 1-2 (hygiene, Docker image, hash manifest, LE parser) already exist and are not re-researched.
**Confidence:** MEDIUM overall. Versions are pinned in the repo or recorded in `docs/toolchain.md` / `docs/research/` (HIGH for the fact of the pin). Fitness for UFO2P/TACP is mostly MEDIUM, because no borrowed tool has been run on our binaries yet.

> Numbering: research notes use the old phase numbers 0-5. Old N = new N+1. This file uses the new numbers only (3 = round trip, 4 = compiler ID, 5 = split and first matches, 6 = reporting and pilot).

Confidence tiers in this file, assigned by hand because web providers were out of scope:
- **HIGH**: pinned or present in the repo (Dockerfile, `pyproject.toml`, `uv.lock`, CI), or a fact measured by a local scan.
- **MEDIUM**: a single well-cited research note says so and a comparable project (Theme Hospital, KKND, decomp.me) uses it in production, but it is untested on UFO2P/TACP.
- **LOW**: an inference in the notes, or explicitly listed as a gap there.

## What already exists (baseline, do not rebuild)

| Component | Pinned version | Where | Confidence |
|---|---|---|---|
| Python | 3.14 (`.python-version`), 3.14.5 in image | `.python-version`, `docker/Dockerfile` | HIGH |
| uv | 0.12.23 (host, image, CI) | `docker/Dockerfile`, `.github/workflows/ci.yml` | HIGH |
| Base image | `ubuntu:24.04@sha256:68ee2200…` | `docker/Dockerfile` | HIGH |
| ninja | 1.11.1-2 (apt) | `docker/Dockerfile` | HIGH |
| binutils (GNU `as`, `objdump`) | 2.42-4ubuntu2.10 | `docker/Dockerfile` | HIGH |
| clang-format, clangd | 1:18.0-59~exp2 | `docker/Dockerfile` | HIGH |
| wibo | 1.2.0 (`COPY --from=ghcr.io/decompals/wibo:1.2.0`) | `docker/Dockerfile` | HIGH |
| objdiff-cli | v3.8.2, sha256-verified | `docker/Dockerfile` | HIGH |
| Open Watcom v2 | `2026-10-01-Build` snapshot, only `wdis`/`wlink`/`wlib` on PATH | `docker/Dockerfile` | HIGH |
| pytest / ruff | pytest 9.1.1 (lock), ruff >=0.17 | `pyproject.toml`, `uv.lock` | HIGH |
| Build backend | hatchling >=1.27 | `pyproject.toml` | HIGH |
| CI | `actions/checkout@v7`, `astral-sh/setup-uv@v10.3.0` | `.github/workflows/ci.yml` | HIGH |
| LE reader | `tools/reverseapoc/le.py`, derived from KKND `le.py` (CC0); raises `LEUnsupportedError` on iterated/zero pages and non-internal fixups | `tools/reverseapoc/le.py` | HIGH |
| `configure.py` | Phase 2 skeleton (only `check-orig` / `parse-le` edges) | repo root | HIGH |

The project has **zero runtime Python dependencies** today (`dependencies = []`). Keep it that way unless a phase records a reason in `docs/tools.md` (rule in `.claude/rules/tools.md`).

## Recommended Stack

### Core Technologies (the matching oracle)

| Technology | Version | Purpose | Why Recommended | Phase | Confidence |
|---|---|---|---|---|---|
| Original Watcom C `wcc386.exe` (Win32-hosted `BINNT\`), user-supplied | 10.6 primary, 10.5 equivalent; 11.0 only for the probe; `wpp386` kept per file | The only compiler that can produce the game's bytes | Banner `1988-1995` excludes only 10.0/10.0a. Local idiom counts (`setcc; and eax,0FFh` 33x UFO2P / 61x TACP vs `movzx` 1x each) point at classic 10.x/11.0 and away from Open Watcom. Theme Hospital (also 1997) matched with 10.6 and found 10.5/10.5a/10.6 identical; 11.0 matched 2 of 10. | 4 (prove), 5 (use) | MEDIUM (hypothesis until Phase 4 gate) |
| wibo | 1.2.0 (already in image) | Runs `BINNT\wcc386.exe` on Linux in Docker | Used by Theme Hospital and decomp.me's cromper for exactly this compiler family. nixpkgs' wibo 0.6.14 fails with "Unhandled function LocalAlloc". Whether every 10.x version runs under it is the Phase 4 spike. | 4 | MEDIUM |
| Python stdlib tooling in `tools/reverseapoc/` (GPLv3) | Python 3.14 | LE splice/verify, OMF-to-ELF, split, configure, progress, driver | Every comparable Watcom decomp (Theme Hospital, KKND, Daggerfall) writes its tools in Python, and the repo already does. | 3-6 | HIGH |
| In-place page splice (from KKND `build_kknd.py`, CC0) | n/a (adapted code) | Phase 3 round trip and the Phase 5+ "splice and verify" step | Starts from `bytearray(original)` and overwrites only page bytes, so unmatched bytes, headers, fixup tables and the 217,764-byte DOS/4GW Pro blob are identical by construction. About 1-3 days, against 10-20+ for Theme Hospital's full `lewrite.py` rewrite. | 3 | MEDIUM |
| `configure.py` -> `build.ninja` + `objdiff.json` + `compile_commands.json` (Theme Hospital pattern) | ninja 1.11.1 | Build graph with per-file `compiler@version` + flags from `config/cflags.txt` (first matching glob wins) | Fits per-file flags better than Make or CMake. It is also the exact interface decomp.wtf fork mode accepts ("builds with configure.py + ninja and produces objdiff.json"). | 5 (compile rules), 6 (fork mode) | HIGH (pattern), MEDIUM (fork-mode fit) |
| `omf2elf.py` from Theme Hospital (GPLv3, about 589 lines) | copied with its header | Converts Watcom OMF objects to ELF32 so objdiff can read them | objdiff cannot read OMF (issue #97 open since 2024-08-19; v3.8.2 still ELF/COFF only). This is the only complete Watcom OMF reader + ELF writer found: COMDAT, LIDATA, FIXUPP threads, BAKPAT. It is also the reason `tools/` is GPLv3. | 5 | MEDIUM |
| objdiff-cli | v3.8.2 pinned (Theme Hospital proved 3.8.1 through the same converter) | Per-function diff, `report generate` -> `report.json` | Supports x86. Its report shape is what recomp.fyi ingests and what decomp.wtf fork mode judges with. | 5, 6 | MEDIUM |
| Relocation check (Theme Hospital `elfrelocs.py` + `verify.py`, KKND build-gate rules) | copied/adapted | Every `call rel32` hits the same function, every absolute fixup resolves to the original LE target | objdiff compares at most one relocation per x86 instruction, so a 100% objdiff score is not enough on its own. | 5 | MEDIUM |
| Whole-EXE SHA-1 against `config/targets.toml` | stdlib `hashlib` | The done gate | Already the project's definition of done (CLAUDE.md). The driver re-runs it and never trusts a transcript. | 3-6 | HIGH |

### Analysis stack (WSL2 Ubuntu, outside the build image)

| Technology | Version | Purpose | Why Recommended | Phase | Confidence |
|---|---|---|---|---|---|
| Ghidra | 12.1.4 (2026-09-21) + JDK 21 | Function discovery, drafts, naming | Stock Ghidra has no LE loader and no `__watcall` (issues #532 and #156, open since 2019), so it needs one of the two loaders below. Keep it in WSL2: putting it in the compile image would bloat the image. | 5 | MEDIUM |
| lastonesky ghidra-lx-loader | v12.1.4-1 (2026-10-10) | LE loader + complete Watcom cspec (`__watcall`, `__cdecl`, `__stdcall`, …) | Only maintained loader for the Ghidra 12.1 loader API. Upstream yetmorecode v12.0.1 breaks on 12.1. "A wrong convention makes every recovered signature systematically wrong." | 5 | MEDIUM |
| *or* retrokit | v0.2.0 (2026-10-14), Apache-2.0, via pipx | Own LE loader, `watcom`/`watcomreg` cspec auto-detect, OW library signatures, `functions.csv`/`fixups.txt` export, stdio MCP | Ships the export that lastonesky lacks, and is aimed at exactly this class of game. Only 6 days old and validated only on synthetic programs. Its `size` is a Ghidra body count and needs a `ghidra2functions.py` adapter to become contiguous ranges. | 5 | LOW-MEDIUM |
| GhidraMCP (LaurieWired) | 2.0 (2026-10-10), headless PyGhidra | Claude Code access to Ghidra | Supports Ghidra 12.1.4 with no GUI. Headless needs Python 3.10-3.13, so run it with `uvx --python 3.13` while the project stays on 3.14. | 5 | MEDIUM |
| KKND `find_functions.py` (capstone recursive descent, CC0) | adapted | Ghidra-independent second function list | Diffing the Ghidra and capstone lists catches boundary errors before they break the splice size check. | 5 | MEDIUM |

**Pick exactly one loader per Ghidra install** (lastonesky or retrokit). The Phase 5 spike decides. Neither has been tested on UFO2P/TACP. The lx-loader README's claim that UFO2P is "DOS/16 LE and unbound" contradicts the local scan (bound DOS/4GW Pro), so treat it as untested.

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---|---|---|---|---|
| capstone | >=5.0 (KKND's only dependency; decomp.wtf pins >=5.0.9) | x86-32 disassembly for `find_functions.py`, `lib_match.py`, side-by-side diffs, scorer opcode features | Phase 5, when KKND discovery and diff tools are lifted. It is the first runtime dependency: record the reason in `docs/tools.md` and confirm cp314 wheels before locking. | MEDIUM (3.14 wheel availability not verified, LOW) |
| retrokit `formats.py` `_expand_iterated` (Apache-2.0) | graft the function, keep its notice | Iterated-page expansion | Only if the Phase 3 spike finds iterated/zero pages, which `le.py` currently rejects. Apache-2.0 into GPLv3 is allowed. | MEDIUM |
| KKND `lib_match.py` (CC0) + Theme Hospital `omf2elf.library_module` | adapted | Masked-byte match of linked runtime functions against `CLIB3R.LIB` / `MATH3R.LIB` from each Watcom version's `LIB386` | Phase 4 gate (NHL95PC-style library match). It also labels runtime functions for free later. | MEDIUM |
| Theme Hospital `cc.py`, `check.py`, `split.py`, `x86scan.py` (GPLv3) | adapted | wibo+wcc386 invocation with `/`->`\` and `Z:` paths; per-file check; per-unit GNU-`as` target objects with R_386_32 / R_386_PC32 from LE fixups; switch-table-aware scan | Phase 5. `split.py` needs the image's binutils `as`, which is already installed. | MEDIUM |
| KKND `gen_units.py`, `land.py`, `split.py`, `score_functions.py`, `auto_families.py`, `name_evidence.py`, `learn.py` (CC0) | adapted / as-is | `INCLUDE_ASM` scaffolding, landing matched C, easiest-first ranking, trivial-family auto-match, names from diagnostic strings, learnings search | Phase 5 (scaffold) and Phase 6 (scorer, pilot). The stub convention must also satisfy decomp.wtf fork mode, which expects GNU-asm `INCLUDE_ASM` (open item). | MEDIUM |
| mosura codegen probe (5 constructs: `cmpbyte`, counted loop, small switch, `x/7`, `x/10u`) | reference recipe | Separates 10.0a / 10.5=10.6 / 11.0 / OW2 | Phase 4 step 1. Search UFO2P's code object for the 10.x idioms (`sete; and eax,0FFh`, loop bound in `ebx`, ascending switch compares). | MEDIUM |
| clang (the compiler driver, not only clang-format) | 18 from Ubuntu 24.04, same series as the installed clang-format/clangd | `clang -fsyntax-only -std=gnu89 -Werror=declaration-after-statement` with a Watcom compat header | **Gap:** this is the lint gate in `.claude/rules/src.md` and `docs/coding-style.md`, but the image installs only `clang-format` and `clangd`. Add the `clang` apt package (pinned like the others) in Phase 5, before the first C file. | HIGH (gap is real), MEDIUM (exact package pin) |
| ast-grep | install method TBD in `docs/tools.md` (Docker or pipx) | Structural search; optional declaration-after-statement rule | Phase 5, optional. clang is the real dialect gate. | LOW (no pinned version recorded) |

### Phase 6 reporting and agent layer

| Technology | Version | Purpose | Why Recommended | Confidence |
|---|---|---|---|---|
| Own `tools/progress.py` (stdlib only) | n/a | Writes `progress.json`, a squarified-treemap `progress.svg` (one cell per function, sized by bytes, grouped by module) and shields `shield.json` (`schemaVersion: 1`) | decomp.dev closed to new projects (2026-10-15); frogress needs an admin-issued key. AnyPS5/sa3 prove the output design, but rewrite the input and do not copy AnyPS5's GPL-2.0 code. | MEDIUM |
| GitHub Actions Pages deploy | `actions/upload-pages-artifact@v5`, `actions/deploy-pages@v5`, `actions/checkout@v7` (already used); `actions/upload-artifact@v4` for the report | Publishes progress on push to `main`; uploads `report.json` as a `<VERSION>_report` artifact for recomp.fyi | AnyPS5 and bw1-decomp workflows. Pages on a private repo needs a paid plan. CI never has `orig/`, so progress must come from committed per-function status, not from a live build. | MEDIUM |
| shields.io endpoint badge | `https://img.shields.io/endpoint?url=<json>` | README badge | recomp.fyi renders no badge. Cache lag cannot go below shields' default. | MEDIUM |
| `.recomp.json` (already committed) + objdiff `report.json` | spec v1 | recomp.fyi listing and percentage | The board reads objdiff-shaped reports daily, so the OMF bridge also decides whether a percentage appears. | MEDIUM |
| Claude Code `claude -p "/goal …"`, one fresh session per function | built in | In-function persistence with an independent small-model judge | `/goal`'s evaluator "does not call tools", so the driver re-runs compile, compare and SHA-1 itself. It requires workspace trust and is unavailable with `disableAllHooks`/`allowManagedHooksOnly`. Use `--output-format stream-json --verbose` for logs. | MEDIUM |
| Driver: evaluate Nigel first, fallback about 200 lines of Python | Nigel: Go binary, no version recorded (needs a Go build step and owner approval) | Pick, attempt, verify, commit or reset; 3-5 attempts per pass, then re-queue; back off on usage limits | Nigel's `candidate_source`/`verify_command`/`success_command`/`reset_command`, `--shard`, `--time-limit` map almost 1:1 onto the loop. Lewis's results came from a dumb driver plus a good scorer, verifier and hooks. | MEDIUM (design), LOW (Nigel fit untested) |
| Claude Code hooks (`.claude/settings.json`, PreToolUse on Edit/Write/Bash) | built in | Block edits to `orig/`, `config/targets.toml` / `*.sha1`, build and verify scripts during matching, `_asm`/`__asm`/code-emitting `#pragma aux` in `src/`, builds outside the verify script, edits to `asm/`/`build/` | Prose rules fail: Lewis's agent rewrote a SHA-1 and worked around a blocked `make`. decomp.wtf fork mode does **not** ban `#pragma`, so our hook has to block code-emitting `#pragma aux` while allowing calling-convention pragmas. | MEDIUM |
| decomp.wtf fork mode | v0.10.6 (archived 2026-10-15), own venv in WSL2, Python 3.12+; its deps include capstone>=5.0.9, mcp>=2.3.0, pyelftools>=0.33 | Claims for parallel agents, MCP tools (`claim_function`, `compile_and_diff`, …), dashboard, undo when a match breaks, Ghidra drafts on ELF target objects | Owner decision (hybrid pipeline): it buys the agent layer for about 3-7 extra days instead of 12-24 to build one. Run it **as a subprocess, never imported**. Autopilot is unavailable on x86 because it needs m2c. Pin the version or fork at the last commit, because there is no upstream any more. | MEDIUM (LOW until the Phase 6 spike "fork mode accepts the stub convention") |
| Project `watcom-decomp` skill under `.claude/skills/` | n/a | Accumulates verified flags, idioms and pitfalls from `docs/matching.md` | No marketplace skill covers Watcom or DOS/4GW. The general C++ skills push C++11-23 idioms that break matching. | MEDIUM |

### Development Tools

| Tool | Purpose | Notes |
|---|---|---|
| decomp.me (`msdos` platform: `wcc10.0a`, `wcc10.5`, `wcc10.5a`, `wcc10.6`, `wcc11.0` + `wpp`) | Zero-setup flag hunting in Phase 4-5 | Use sparingly: the community is wary of AI submissions. Do not flood it with agent scratches. Whether `-zm`/`-d2` can be typed as custom flags is unverified. |
| Watcom BINNT binaries natively on the Windows host | Debugging a compile outside Docker | Same binaries wibo runs. The container stays the oracle. |
| OW v2 `wdis` / `wlib` / `wlink` | Disassemble OMF, list and extract `CLIB3R.LIB` modules, optional non-identical relink | Never `wcc386` from OW for matching. The Dockerfile already keeps it off PATH. |
| decompals binutils-omf (`omf-nm`, `omf-objdump`, GPL-2.0) | Inspecting OMF when debugging `omf2elf` | Optional, inspection only (cromper uses v0.4). Not required. |
| clang-format 18 + a pragma-masking `format.py` (Theme Hospital pattern) | Build-neutral formatting of C | `SortIncludes: Never`, `ReflowComments: false`, mask every `#pragma` and its continuation lines. Format-on-save stays off for C. Any format change must be re-verified by a rebuild. |
| clangd (already in image) + generated `compile_commands.json` + compat header | Editor navigation | The compat header defines `__far`, `__near`, `__interrupt`, `__cdecl`, `__watcall` empty for clang, plus `-D__386__ -D__FLAT__` and a `__WATCOMC__` value set from the Phase 4 result. Path decided in Phase 5. |

## Installation

```bash
# Phase 3: nothing new. Stdlib only (struct, hashlib), runs in the existing image.
docker compose build && docker compose run --rm test

# Phase 4: user-supplied compilers, never baked into an image layer
#   third_party/watcom/<version>/binnt/wcc386.exe, h/, lib386/ (CLIB3R.LIB, MATH3R.LIB)
#   mounted read-only at /work/watcom by docker/compose.yaml
# Invocation pattern (decomp.me cromper / Theme Hospital cc.py):
#   wibo /work/watcom/10.6/binnt/wcc386.exe -zq -i="Z:\work\watcom\10.6\h" <flags> -fo"Z:\..." "Z:\..."
#   (Watcom treats "/" as an option switch and splits on spaces: convert / to \, use relative build/tmp paths)

# Phase 5: Python dependency (record the reason in docs/tools.md first)
uv add "capstone>=5.0"
# Phase 5: Dockerfile addition, pinned like the other apt packages
#   clang=1:18.0-59~exp2   (lint gate: clang -fsyntax-only -std=gnu89 -Werror=declaration-after-statement)

# Phase 5: WSL2 Ubuntu (not Docker)
#   Ghidra 12.1.4 + JDK 21; install ONE of:
#     lastonesky ghidra-lx-loader v12.1.4-1 (File > Install Extensions)
#     pipx install retrokit  &&  retrokit install-loader
uvx --python 3.13 --from "ghidra-mcp[headless] @ git+https://github.com/LaurieWired/GhidraMCP" \
    ghidra-mcp --headless --binary /path/to/UFO2P.EXE --project ~/ghidra/reverseapoc

# Phase 6: WSL2, own venv, pinned and run only as a subprocess
#   git clone decomp.wtf at v0.10.6 under ~/src (Linux filesystem, not /mnt/c); uv sync
# Nigel: Go build step, owner approval required before installing
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|---|---|---|
| In-place page splice (KKND) | Theme Hospital `lewrite.py` full LE rewrite (433 lines, hardcoded `CODE_BASE`/`DATA_VSIZE`/`LINKED_AFTER`, module "MAIN", WSTUB 10.5 stub) | Only once shiftable or relinkable builds are wanted (a matched function changes size). Not in Milestone 1. |
| Theme Hospital `omf2elf.py` + objdiff | KKND-style compare: cut each function from its OMF object, mask relocations, check targets; no objdiff | If the Phase 5 spike shows objdiff cannot diff converted ELF cleanly. That also costs the recomp.fyi percentage and decomp.wtf fork mode (fallback = own pipeline + minimal agent layer). |
| Theme Hospital `omf2elf.py` (GPLv3) | Extend KKND `omf.py` (CC0, no COMDAT/CEXTDEF/BAKPAT, no writer) with an ELF writer | Only if tooling ever had to be permissive. It does not: `tools/` is GPLv3 by owner decision. Cost would be about 3-5 extra days. |
| lastonesky ghidra-lx-loader | retrokit (own loader + export + MCP) | If its export and library signatures save the adapter work and its loader handles the bound DOS/4GW Pro files. The Phase 5 spike decides; never install both in one Ghidra. |
| GhidraMCP 2.0 headless | retrokit's MCP; bethington/ghidra-mcp (200+ tools, Docker, Ghidra Server) | retrokit MCP if retrokit wins the loader spike. bethington once a shared team Ghidra server exists. |
| Nigel | About 200-line Python driver | If Nigel's Go build is not approved, or its "candidate disappears from source" success rule does not fit the INCLUDE_ASM convention. |
| decomp.wtf fork mode (owner decision) | Own minimal agent layer: MCP over the oracle, SQLite claims, guardrails, Claude Code only (about 5-9 days) | If fork mode rejects the stub convention or objdiff-on-converted-ELF fails (same spike outcome as above). |
| objdiff-cli v3.8.2 | v3.8.1 (the version Theme Hospital proved with `omf2elf`) | If 3.8.2 shows a regression on converted objects. Bumping is a Dockerfile ARG change. |
| Python 3.14 | Python 3.15.0 (released 2026-10-09) | After the milestone, once capstone and any other dependency has cp315 wheels. One-line change. GhidraMCP stays on 3.13 either way. |
| uv 0.12.23 | uv 0.13.1 (current) | Bump host, image and CI together in a tooling-only change, not in the middle of a matching phase. |
| Easiest-first scorer (KKND `score_functions.py`) | Similarity-first (opcode Levenshtein over Watcom-normalised asm, coddog idea reimplemented in Python; UFO2P<->TACP twins) | Switch once enough functions are matched. Lewis found similarity ordering beat difficulty ordering in the long tail. Build it after Phase 5. |

## What NOT to Use

| Avoid | Why | Use Instead |
|---|---|---|
| Open Watcom `wcc386` (1.9 / 2.0) for matching | It descends from 11.0c, threads jumps on conditions it can prove at loop entry and lays out loops differently. "No flag tested fixes this" (KKND). It emits `movzx` where the game has `and eax,0FFh`. | The original 10.x `wcc386` under wibo. OW v2 only for `wdis`/`wlink`/`wlib`. |
| KKND's patched OW `wcc386` (506-line patch) | A workaround for not having the real compiler; it adds an unverifiable variable to the oracle | The real 10.5/10.6 binaries (reference only if they somehow fail) |
| Watcom 10.0/10.0a as the default | Excluded by the `1988-1995` banner. Theme Hospital needed 10.0a only for some CRT modules. | 10.6 default; per-file `compiler@version` in `config/cflags.txt` if the library match shows mixing |
| Baking any Watcom 10.x/11.0 binary into an image layer, or a fetch step inside the Dockerfile | Proprietary, IP owner unverified; hard rule in CLAUDE.md | User-supplied `third_party/watcom/`, read-only mount; an opt-in user-run fetch script at most |
| nixpkgs wibo 0.6.14 (or any wibo before 1.2.0) | Cannot run Watcom ("Unhandled function LocalAlloc") | wibo 1.2.0 (already pinned) |
| Theme Hospital `lefile.py` | No bound-stub offset; raises on fixup source lists | The existing KKND-derived `tools/reverseapoc/le.py` |
| Theme Hospital `lewrite.py` / `relink.py` / `link.py` in Milestone 1 | Game-specific constants; 10-20+ days; not needed while matched functions keep their size | In-place splice |
| PyPI `omf` | It is the *Open Mining Format* library, unrelated. Other GitHub OMF parsers are unlicensed or AGPL. | Theme Hospital `omf2elf.py` |
| objconv (and forks) as the OMF bridge | Drops or rejects records Watcom emits (stated in `omf2elf.py`'s docstring) | `omf2elf.py` |
| Upstream yetmorecode ghidra-lx-loader v12.0.1 on Ghidra 12.1.x | Ghidra 12.1 changed the Loader API and the x86 compiler specs | lastonesky v12.1.4-1 |
| Two LE loaders in one Ghidra install | Conflicting loaders and cspecs | One loader per install |
| GhidraMCP headless under the project's Python 3.14 | PyGhidra headless needs 3.10-3.13 | `uvx --python 3.13` |
| Ghidra inside the build image | About 540 MB plus JDK, unrelated to the compile oracle | Ghidra in WSL2 |
| IDA Free | PE/ELF/Mach-O only, cloud decompiler, no IDAPython, unsupported by ida-pro-mcp; owner wants analysis local | Ghidra + LE loader |
| decomp.wtf from-scratch (ROM) mode | MIPS-hard-coded matcher (`R_MIPS_*`, 4-byte words), no LE/x86 splitter; adding "dos-watcom" costs about 16-27 days | Fork mode over our `configure.py` + `objdiff.json` repo |
| Importing decomp.wtf modules into `tools/` | Owner constraint: it stays a separate tool | Subprocess / MCP only |
| m2c, decomp-permuter, mizuchi's m2c/permuter stages | No x86. Lewis removed the permuter for overfitting and "doom loops". | Ghidra drafts; human-reviewed variants later |
| asm-differ | x86 only "to a limited extent"; needs an OMF-capable objdump | objdiff-cli |
| CMake, Make as the real build, wmake | Watcom is not a first-class CMake DOS/LE compiler; per-file flags fit Python generation | `configure.py` -> ninja (a thin Make wrapper is optional sugar only) |
| Rust for own tools | Second toolchain, slower iteration; every comparable project uses Python | Python; consume objdiff as a binary |
| clang-tidy `modernize-*` / `cppcoreguidelines-*`; cpp-pro, Mindrally cpp skills | Push C++11-23 rewrites that break matching or do not compile under `wcc386` | clang `-Werror=declaration-after-statement`; project `watcom-decomp` skill |
| `/simplify`, code-simplifier, Ponytail, thermo-nuclear on `src/` | Any change of shape changes codegen | Use on Python tooling only |
| Ralph Loop as the pilot driver | One growing session, single promise string, only `--max-iterations` as a cost control, Windows bash-path breakage | Driver + one `claude -p "/goal …"` per function |
| Bilevel Autoresearch | Noisy n=3 result, no cost data, outer loop rewrites the harness (reward hacking) | Human-approved retrospective that edits CLAUDE.md, learnings and the scorer, never the verifier |
| decomp.dev, frogress | Closed to new projects / admin-issued key | Self-hosted Pages progress + recomp.fyi |
| Copying AnyPS5 `progress.py` | GPL-2.0 code, scans its own C++ stubs | Own stdlib `progress.py` with the same output design |
| BSim, embeddings (jina / Voyage), sqlite-vec/pgvector in Milestone 1 | No turnkey headless search; a corpus of a few thousand functions does not need ML | Opcode Levenshtein + twins after Phase 5 |
| Theme Hospital `variants.py` (534-line source beam search) in the Milestone 1 pilot | High value later, but it is a permuter-style search with the overfitting risk Lewis documented, and it widens the pilot's scope | Defer to after Milestone 1; GPLv3-compatible when wanted |

## Stack Patterns by Variant

**If the Phase 3 spike finds iterated/zero pages or non-internal fixups in UFO2P/TACP:**
- Extend `le.py` with retrokit's `_expand_iterated` (Apache-2.0 notice kept) and add the record types to the reader.
- The splice still writes only physical page bytes back. Iterated pages must stay byte-identical, because they are never re-encoded.
- Because both borrowed readers raise `NotImplementedError` on these, and ours raises `LEUnsupportedError`.

**If Phase 4 shows modules compiled with different versions (Theme Hospital: 10.0a for some CRT):**
- Keep `compiler@version` per glob in `config/cflags.txt`, and record each row in `docs/matching.md` with evidence.
- Because the two module names (`ufo24`, `tac4`) suggest separate link scripts and possibly different flags per EXE.

**If Phase 4 proves 11.0 instead of 10.6:**
- Same stack. Only the default in `cflags.txt` and the compat header's `__WATCOMC__` change.
- Expect the 11.0 idioms: a branch instead of `setcc` for byte compares, loop bounds in `ecx`.

**If a module proves to be C++ (vtables in obj2, `__wcpp_` routines, XI/YI static-init segments):**
- Switch that glob to `wpp386`. `omf2elf.py` already handles COMDAT and weak symbols (Theme Hospital is C++).
- Because `wcc386` "generates different code for the same source".

**If the Phase 5 objdiff spike fails:**
- Use the KKND compare (cut from OMF, mask relocations, check targets) and an own minimal agent layer (MCP + SQLite claims + guardrails + Claude Code only).
- recomp.fyi then gets a hand-built objdiff-shaped `report.json` (KKND `make_report.py` does this), or shows no percentage.

## Version Compatibility

| Package A | Compatible With | Notes |
|---|---|---|
| Ghidra 12.1.4 | lastonesky ghidra-lx-loader v12.1.4-1 | Requires 12.1.x; 12.0.x is no longer supported |
| Ghidra 12.1.4 | GhidraMCP 2.0 | Headless PyGhidra: Python 3.10-3.13, `GHIDRA_INSTALL_DIR` set, extension installed |
| Ghidra 12.x + JDK 21+ | retrokit 0.2.0 | Python 3.10+; `retrokit install-loader` compiles against the local Ghidra; re-run after any Ghidra update |
| Ghidra 11.3+ | JDK 21 | PyGhidra since 11.3 |
| decomp.wtf 0.10.6 | Python 3.12+, Ghidra 12.1.4 (its own pin, optional, Java 21+) | Separate venv in WSL2; never shares the project's venv |
| wibo 1.2.0 | Watcom 10.6 `BINNT\wcc386.exe` / `wpp386.exe` | Proven by Theme Hospital and cromper. 10.5 and 11.0 under wibo: Phase 4 spike. The 10.5 CD's `BINW/WCC386.EXE` is a damaged 65,536-byte stub; the real binary must be unpacked from `DISKIMGS/DISK02+03/PCK00017.{1,2}` (mosura). |
| objdiff-cli 3.8.1 | Theme Hospital `omf2elf.py` output | Proven. 3.8.2 (our pin) has not been tried with converted objects. |
| Python 3.14 | capstone >=5.0 | cp314 wheels not verified in the research. Check before `uv lock`. |
| clang-format / clangd 18 | `clang` 18 | Add the driver from the same Ubuntu 24.04 series so the lint gate and clangd agree |
| Docker compose mount `../third_party/watcom:/work/watcom:ro` | repo bind mount `..:/work` | Side effect: Docker creates an empty `watcom/` directory in the checkout (present today, not gitignored). Add `/watcom/` to `.gitignore` so a compiler copied there by mistake can never be committed. |

## Phase-by-phase stack summary

| Phase | New stack | Reused | Spike |
|---|---|---|---|
| 3 Round trip | None beyond stdlib (`hashlib`, `struct`) | `le.py`, KKND in-place splice logic, `targets.toml` SHA-1 | Iterated/zero pages and fixup edge cases on the real files |
| 4 Compiler ID | User-supplied Watcom 10.5/10.6/11.0 (`BINNT`, `h/`, `LIB386`) | wibo 1.2.0, `wlib`/`wdis`, mosura probe recipe, KKND `lib_match.py`, `omf2elf.library_module`, decomp.me for quick checks | wibo 1.2.0 runs `wcc386.exe` for each version in Docker |
| 5 Split + first matches | Ghidra 12.1.4 + JDK 21 + one LE loader (WSL2), GhidraMCP 2.0 (py3.13), capstone, clang 18 driver, `omf2elf.py`/`elfrelocs.py`/`verify.py`/`split.py`/`cc.py`/`check.py`, KKND discovery/scaffold tools, full `configure.py` | objdiff-cli 3.8.2, binutils `as`, ninja, clang-format/clangd | objdiff diffs OMF-converted ELF cleanly (decides hybrid vs fallback) |
| 6 Reporting + pilot | `progress.py`, Pages workflow (`upload-pages-artifact@v5`, `deploy-pages@v5`), report artifact (`upload-artifact@v4`), hooks, `watcom-decomp` skill, driver (Nigel or Python), decomp.wtf 0.10.6 fork mode (WSL2) | objdiff `report generate`, `.recomp.json`, KKND `score_functions.py`/`auto_families.py`/`learn.py` | decomp.wtf fork mode accepts the repo's stub convention |

## Sources

All local; each cites its own upstream URLs and access dates (2026-10-19).

- `docs/research/2026-10-19-kickoff-research-report.md`: overall verdicts, use/skip/later table, risks (MEDIUM)
- `docs/research/notes-own-pipeline-reuse-inventory.md`: Theme Hospital / KKND / retrokit tool inventory, line counts, licences, splice-vs-rewrite effort, OMF reader survey (MEDIUM)
- `docs/research/notes-target-binary-and-toolchain.md`: local scan of the targets, banner and codegen evidence, mosura probe, decomp.me compiler IDs, objdiff OMF status (HIGH for local-scan facts, MEDIUM otherwise)
- `docs/research/notes-repo-infra-docker-standards.md`: ninja-via-Python precedent, wibo/Docker boundary, clang-format pragma masking, compat header, uv/Python pins (MEDIUM)
- `docs/research/notes-decompwtf-rea-ghidra-ida.md`: decomp.wtf internals and fork-mode fit, Ghidra 12.1.4 loader status, GhidraMCP 2.0, IDA Free limits (MEDIUM)
- `docs/research/notes-automation-loops.md`: `/goal`, Nigel contract, Ralph limits, Lewis's driver evidence (MEDIUM)
- `docs/research/notes-progress-reporting-recompfyi.md`: Pages workflow action versions, shields endpoint, recomp.fyi artifact convention, objdiff report proto (MEDIUM)
- `docs/research/notes-vector-retrieval-bsim.md`: why similarity retrieval stays non-ML in Milestone 1 (MEDIUM)
- `docs/toolchain.md`: version pins table, target facts, compiler hypothesis (HIGH for pins)
- `docs/tools.md`: Use/Skip/Later verdicts and owner overrides (decomp.wtf fork mode, GSD) (HIGH for decisions)
- `docs/workflow.md`: Phase 3-6 goals, gates and spikes; hook block list (HIGH for decisions)
- `docs/superpowers/specs/2026-10-19-reverseapoc-design.md`: Owner/Default decisions, constraints, items left to the builder (HIGH for decisions)
- Repo: `docker/Dockerfile`, `docker/compose.yaml`, `pyproject.toml`, `uv.lock`, `.python-version`, `.github/workflows/ci.yml`, `tools/reverseapoc/le.py`, `configure.py`, `config/targets.toml`, `.claude/rules/*.md` (HIGH)

---
*Stack research for: Watcom 10.x DOS/4GW LE byte-matching decompilation (ReverseApoc, Milestone 1 Phases 3-6)*
*Researched: 2026-10-19*
