# Tools and skills

Every tool, skill and framework considered at kickoff, with the verdict from the 2026-10-19 research ([report](research/2026-10-19-kickoff-research-report.md), [notes](research/)). Where the owner later decided differently, the row says so.

- **Verdict:** Use, Later or Skip, with the decomp-specific reason.
- **Install method:** plugin at project scope, pipx, Docker (in the build image), WSL2 (manual install in the Ubuntu distro), n/a (nothing to install, or a pattern we reimplement).
- **Status:** installed, the phase that brings it in, Later, or skipped.

## Use / Skip / Later

| Candidate | Verdict | Reason | Install method | Status |
|---|---|---|---|---|
| [decomp.wtf](https://github.com/i12bp8/decomp.wtf) | **Use in fork mode** (owner decision 2026-10-19; the report said Skip, reference only) | Archived 2026-10-15, no LE/x86 from-scratch path. Fork mode accepts a repo that builds with `configure.py` + ninja and emits `objdiff.json`, judges with objdiff and allows `#pragma`; we take its claims, MCP tools, guardrails and dashboard. Spike 006 (2026-10-24): INVALIDATED, because there is no build in WSL2: unpatched fork mode stops at its own setup and finds no `objdiff.json`, and ninja, wibo and objdiff-cli are missing. The code evidence also shows that its stub regex misses our bare `INCLUDE_ASM(func_X);` and that it looks functions up as `func_X_`. A submission is therefore refused, or inserted with the stub kept, which the D-12 check refuses. Those are D-02's PARTIAL patches, not yet sized ([spike 006](../.planning/spikes/006-decompwtf-fork-stub/README.md)). Phase 6 uses the own agent layer (D-03); decomp.wtf is re-evaluated for Phase 7 claims | WSL2, `uv sync` in its own venv (Python 3.12+), pinned v0.10.6, run as a subprocess | Phase 6: not used (spike 006); re-evaluated in Phase 7 |
| [REA](https://github.com/morluto/rea) ([guides](https://rea.tools/guides/native/)) | **Later** (optional) | Ghidra-backed MCP for "what does this logic do" questions; no matching loop; depends on Ghidra's LE loader | WSL2 (Node MCP server, Ghidra backend) | Later |
| [Ghidra 12.1.4](https://github.com/NationalSecurityAgency/ghidra) + [ghidra-lx-loader](https://github.com/lastonesky/ghidra-lx-loader/releases/tag/v12.1.4-1) | **Use** | lastonesky v12.1.4-1 fork (12.1 loader API, `__watcall`), loads both bound EXEs; upstream v12.0.1 targets 12.0; retrokit is not used (D-03) | Docker (own cached stage in `docker/Dockerfile`, OpenJDK 21 from apt) | installed (Phase 5) |
| [GhidraMCP](https://github.com/LaurieWired/GhidraMCP) vs alternatives | **Later (Phase 7 or later)** (D-41; the kickoff verdict was Use GhidraMCP 2.0 headless) | Supports 12.1.4 and PyGhidra headless (Python <= 3.13); bethington/ghidra-mcp later for a team server. Deferred in Phase 5; Phase 6 has no MCP server (D-44), so agents use the attempt wrapper instead | `uvx --python 3.13` | Later (Phase 7 or later) |
| [IDA Free](https://hex-rays.com/ida-free) | **Skip** | PE/ELF/Mach-O only, cloud decompiler, no IDAPython, unsupported by ida-pro-mcp | n/a | skipped |
| [objdiff](https://github.com/encounter/objdiff) (+ CLI report) | **Use**, behind an OMF-to-ELF shim | x86 supported, but OMF issue #97 open since 2024-08-19; proven via a converter in Theme Hospital | Docker (pinned `objdiff-cli` release binary) | Phase 2 (binary), Phase 5 (diffs) |
| [capstone](https://github.com/capstone-engine/capstone) 5.0.9 | **Use** (first runtime dependency, D-09) | x86-32 decoding for function discovery, asm listings, the easiest-first scorer and PC32 synthesis for target objects; its py3-none wheels (win_amd64, manylinux x86_64) load the C library through ctypes, so Python 3.14 needs no cp314 wheel; check the pin with importlib.metadata.version("capstone"), because capstone.__version__ reports 5.0.7 for 5.0.9 | uv: `[project].dependencies`, `capstone==5.0.9` | Phase 5 |
| [asm-differ](https://github.com/simonlindholm/asm-differ) | **Skip** (fallback only) | x86 "to a limited extent"; needs an OMF-capable objdump | n/a | skipped |
| [m2c](https://github.com/matt-kempster/m2c) | **Skip** | No x86 | n/a | skipped |
| [decomp-permuter](https://github.com/simonlindholm/decomp-permuter) | **Skip** | No x86; Lewis removed it for overfitting and "doom loops" | n/a | skipped |
| [Kappa](https://github.com/macabeus/kappa) | **Skip** (port two ideas) | Copilot-based, last commit 2026-02-20; reimplement LiftVariableDeclarations and AddOffsetComments with `-zp`-aware alignment | n/a (ideas reimplemented in `tools/`) | skipped (ideas: Phase 5-6) |
| [coddog](https://github.com/ethteck/coddog) | **Later** (reimplement the idea now) | x86 unverified; opcode Levenshtein is easy in Python and powers UFO2P-to-TACP twin matching | n/a (Python reimplementation) | Later (after Phase 5) |
| [mizuchi](https://github.com/macabeus/mizuchi) | **Later** (reference design) | Targets gba/n64/ps1; its m2c and permuter stages are dead on x86; benchmark and report design is worth copying | n/a | Later |
| [decomp_settings](https://github.com/ethteck/decomp_settings) | **Later** | Only if coddog, frogress or decomp.me presets are adopted | n/a | Later |
| [Nigel](https://github.com/cdlewis/nigel) | **Skip** (D-05, Phase 6; the kickoff verdict was Use, evaluate first) | Its contract maps onto build/verify/commit/reset, but it has no licence (GitHub `license: null`), needs Go (not on the host), logs no turns or tokens, and detects usage limits by one phrase. Phase 6 builds our own stdlib driver instead (a `reverseapoc drive` verb, D-05) | n/a | skipped (own stdlib driver, Phase 6) |
| [Ralph Loop](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/ralph-loop) | **Later** (prototype only) | Same-session context growth, single promise string, Windows bash path issue | plugin at project scope | Later |
| [/goal](https://code.claude.com/docs/en/goal) | **Use**, one `claude -p` per function | Independent judge per function; the driver re-verifies because the evaluator cannot run tools | n/a (built into Claude Code) | Phase 6 |
| [autoresearch](https://github.com/karpathy/autoresearch) | **Use the pattern only** | `program.md` + fixed harness + one metric + keep/discard; no GPU | n/a | Phase 6 (pattern) |
| [Bilevel Autoresearch](https://github.com/EdwardOptimization/Bilevel-Autoresearch) ([paper](https://arxiv.org/html/2603.23420v2)) | **Skip** | Noisy n=3 result, no cost data, harness-rewrite risk; use a human-approved retrospective instead | n/a | skipped |
| [GSD](https://github.com/open-gsd/gsd-core) | **Use** (owner decision 2026-10-19; the report said Later) | Milestone/phase state, verification gates and `/gsd-spike`; overlap with superpowers is handled by `.claude/rules/workflow.md` | project-local, Claude runtime only (`npx @opengsd/gsd-core@1.18.0 --claude --local`) | installed, project scope |
| [OpenSpec](https://github.com/Fission-AI/openspec) | **Skip the tool, use its spec format** (owner decision 2026-10-21) | Change-proposal model adds per-function overhead; the binary is the spec. Its `spec.md` shape (`### Requirement:` with SHALL/MUST, `#### Scenario:` with WHEN/THEN) is reused for the Phase 8 specs and checked by our own `speclint` | n/a | format: Phase 8 |
| [SpecKit](https://github.com/github/spec-kit) | **Skip** | A constitution-specify-plan-tasks pipeline for new software; nearly every stage overlaps GSD, and a third workflow system would give competing instructions | n/a | skipped |
| [superpowers](https://github.com/obra/superpowers) | **Use** | Brainstorm, plan, TDD, verification-before-completion inside a phase; `writing-skills` for every project skill we create or update | plugin at project scope | installed, project scope |
| [thermo-nuclear review](https://github.com/cursor/plugins/blob/main/cursor-team-kit/skills/thermo-nuclear-code-quality-review/SKILL.md) | **Skip** | No licence, TypeScript-flavoured, restructuring breaks matches | n/a (not plugin-installable) | skipped |
| [Ponytail](https://github.com/dietrichgebert/ponytail) | **Skip** | "Write less code" does not apply when the binary dictates shape | n/a | skipped |
| [pstack](https://github.com/backnotprop/pstack) | **Skip** | Third workflow system, Grok delegation by default, Cursor-only parts | n/a | skipped |
| [i-have-adhd](https://github.com/ayghri/i-have-adhd) | **Optional**, kept by the owner | Shapes chat output only; we apply its spirit to comments by convention | plugin at project scope (marketplace `ayghri/i-have-adhd`) | installed, project scope |
| [discord](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/discord) (official plugin) | **Skip** (installed 2026-10-19, removed the same day) | A bot bridge that needs a bot invited to the server, which the OpenApoc server does not allow; it failed to connect without a token and Bun | plugin at project scope | uninstalled |
| [discord-user-mcp](https://github.com/Jeluva/discord-user-mcp) (Jeluva fork) | **Use, per developer only** | Read-only, GET-only MCP over your own Discord session (11 tools: list guilds, read, search, pins, threads). Automating a user account is against Discord's ToS, so each developer decides for themselves. Built into gitignored `third_party/discord-user-mcp/`, registered with `claude mcp add --scope local` (your `~/.claude.json`, never the repo), token read from a file outside the repo via `DISCORD_TOKEN_FILE`. Note: the local-scope project key is case-sensitive; register it from the same working-directory casing your editor uses | local-scope MCP, not committed | owner's machine only |
| [Tavily MCP](https://github.com/tavily-ai/tavily-mcp) | **Use** for search and finding pages | Free tier is 1,000 credits a month; extract keeps wiki tables but leaks link titles into cells, and a `query` argument reranks and silently drops chunks, so never pass `query` when the whole page is needed and never cite from an extract (tested 2026-10-21) | project `.mcp.json` (`npx -y tavily-mcp@latest`, `${TAVILY_API_KEY}`) | installed, project scope |
| MediaWiki API (`reverseapoc wikifetch`) | **Use** for cited wiki content | `api.php?action=parse&prop=wikitext\|revid` answers on UFOpaedia (MediaWiki 1.43.6), StrategyWiki and Wikibooks with tables intact and a revision id to cite; stdlib only; descriptive User-Agent and at least 10 s between requests per host. The DOSBox wiki returns 403 to scripts, so it is read by hand | n/a (stdlib module in `tools/`) | Phase 8 |
| [Firecrawl MCP](https://github.com/firecrawl/firecrawl-mcp-server) | **Skip** | Its strength is crawling, which the MediaWiki API makes unnecessary; it needs a second API key, and UFOpaedia's robots.txt blocks AI crawlers anyway | n/a | skipped |
| [Context7](https://github.com/upstash/context7) | **Skip** for wiki reading | Indexes library docs from public GitHub repos only; it cannot read UFOpaedia, Wikibooks or StrategyWiki | n/a | skipped |
| [cpp-pro](https://github.com/sickn33/agentic-awesome-skills/blob/main/skills/cpp-pro/SKILL.md) | **Skip** | C++11-23 advice is wrong for Watcom C89 | n/a | skipped |
| [Mindrally cpp](https://github.com/Mindrally/skills/blob/main/cpp/SKILL.md) | **Skip** | Recommends replacing C arrays and `NULL` | n/a | skipped |
| [Qt agent-skills](https://github.com/TheQtCompanyRnD/agent-skills) | **Skip** | Qt-specific; nothing in this toolchain is Qt | n/a | skipped |
| clangd-lsp | **Later** for real use (after Phase 5); plugin installed now by owner decision | Needs `clangd` on PATH (the container has it) plus a generated `compile_commands.json` and a Watcom compat header | plugin at project scope | installed, project scope (useful after Phase 5) |
| [frontend-design](https://github.com/anthropics/claude-plugins-official) | **Use** (owner decision 2026-10-26) | Design guidance for the progress page (`progress.html`, `progress.svg` labels) | plugin at project scope (marketplace `anthropic-plugin-directory`) | installed, project scope; switched off in driver sessions (`config/driver/claude-settings.json`) |
| [clang-format](https://clang.llvm.org/docs/ClangFormat.html) | **Use**, with pragma masking | Build-neutral only with `SortIncludes: Never` and a pragma mask | Docker | Phase 2 (image), Phase 5 (use) |
| [clang](https://clang.llvm.org/) 18 | **Use** | C89 lint gate (D-14): `clang -fsyntax-only -std=gnu89 -Werror=declaration-after-statement` with `include/watcom_compat.h`, run as `uv run reverseapoc lint` | Docker (apt pin `clang-18=1:18.1.3-1ubuntu1`) | installed (Phase 5) |
| clang-tidy | **Skip** | `modernize-*` checks fight byte matching; use clang `-Werror=declaration-after-statement` instead | n/a | skipped |
| [ast-grep](https://ast-grep.github.io/) | **Later** (D-41; the kickoff verdict was Use) | Structural search and rewrite across C; Macabeus chose it over clangd for unopened files. No Phase 5 or Phase 6 work needed it, so it is not installed | Docker or pipx, decided when it is adopted | Later |
| [file-search-skill](https://github.com/netresearch/file-search-skill) | **Skip** | Redundant with the built-in ripgrep-based Grep | n/a | skipped |
| [Understand-Anything](https://github.com/Egonex-AI/Understand-Anything) | **Later** | Token-heavy first run; useful once subsystems are named | plugin at project scope | Later (after Milestone 1) |
| [Groma](https://github.com/MrLesk/groma.md) | **Later** | Offline C4 Markdown in git suits OpenApoc handoff docs; C support "Experimental" | npm global CLI | Later (after Milestone 1) |
| [BSim](https://ghidra.re/ghidra_docs/GhidraClass/BSim/README.html) | **Skip** | No turnkey headless search; hashed features do not fit cosine retrieval | n/a | skipped |
| [jina](https://huggingface.co/jinaai/jina-embeddings-v2-base-code) vs [Voyage](https://blog.voyageai.com/2026/08/13/voyage-code-4/) embeddings | **Later: jina v2 base code** | Local, Apache-2.0, proven in Mizuchi; Voyage code-4 optional; both untested on x86 asm | Python dependency (CPU) | Later |
| SQLite vs [pgvector](https://github.com/pgvector/pgvector) vs [RxDB](https://rxdb.info/) | **Later: SQLite + numpy** | 20k vectors is a millisecond brute-force scan; pgvector needs a server; RxDB is JavaScript | n/a (stdlib + numpy) | Later |
| Rust | **Skip** for own tools | Consume objdiff-cli binaries; all comparable tooling is Python | n/a | skipped |
| CMake vs Make vs ninja | **ninja via `configure.py`** | Per-file flags fit Python generation; Make optional sugar; CMake skipped | Docker | Phase 2 (skeleton), Phase 5 (compile) |
| TDD | **Use for tooling** | pytest for LE/OMF/format/lint code; for decompiled C the byte match is the test | n/a (superpowers skill + pytest) | Phase 2 onward |
| [recomp.fyi](https://recomp.fyi/) | **Use** | `.recomp.json` listing plus a `<VERSION>_report` artifact: one combined `X-COM_Apocalypse_DOS_report` with categories `ufo2p` and `tacp` (D-28), so its several-versions rule does not apply. Risk (D-49): objdiff's `Report::split()` treats dot-free category ids as versions, and recomp.fyi might copy that and split our report in two; its ingestion is private, so this cannot be tested | n/a (file at repo root) | Phase 1 (file), Phase 6 (report) |
| [decomp.dev](https://decomp.dev/) | **Skip** | Closed to new projects, October 2026 | n/a | skipped |
| [frogress](https://github.com/decompals/frogress) | **Skip** | Admin-issued key, extra service | n/a | skipped |
| [AnyPS5 progress.py](https://github.com/boykopovar/AnyPS5/blob/main/tools/progress.py) pattern | **Use the pattern** | Keep the treemap, badge and Pages design; rewrite the input; do not copy GPL-2.0 code | n/a (own `progress.py`) | Phase 6 |
| [decomp.me](https://decomp.me/) (added) | **Use**, sparingly | `wcc10.5`/`10.6`/`11.0` available; mind the community's stance on AI submissions | n/a (web) | Phase 4-5 |
| [wibo](https://github.com/decompals/wibo), [Open Watcom v2](https://github.com/open-watcom/open-watcom-v2), Docker (added) | **Use** | wibo runs the BINNT compiler; OW v2 for `wdis`/`wlink`/`wlib` only; Docker for every build step | Docker | Phase 2 |

## Claude Code ceremonies and plugins

Not rows in the report's table, but evaluated in the research notes. How they are used is in [ceremonies.md](ceremonies.md).

| Item | Verdict | Reason | Install method | Status |
|---|---|---|---|---|
| `/code-review` (built-in) | **Use** | Works on local diffs; tooling, plus comments and docs on matched C | n/a (built in) | available |
| code-review plugin (`/code-review:code-review`) | **Later** | PR-only via `gh`; useful once work flows through PRs | plugin at project scope | installed, project scope |
| `/simplify` (built-in) and code-simplifier agent | **Use on tooling only** | Simplifying a matched function breaks the match | n/a (built in) / plugin at project scope | available / installed, project scope |
| `/security-review` (built-in) | **Occasional** | Little attack surface in an offline 1997 game; useful for Docker and CI | n/a (built in) | available |
| security-guidance plugin | Research said **skip/disable**; installed by owner decision | Web-vulnerability focus is noise for decomp; LLM review on every Stop costs tokens | plugin at project scope | installed, project scope |
| `/verify` (built-in) | **Use, with a recipe** | Record a recipe so "verify" means build and byte compare | n/a (built in) | Phase 2 (recipe) |
| claude-md-management | **Use** | Keeps CLAUDE.md accurate; run at the end of each phase | plugin at project scope | installed, project scope |
| [retrokit](https://github.com/nemo22/retrokit) | **Skip** (not used, D-03; was the alternative LE loader and export) | Own LE loader, Watcom cspecs, library signatures, MCP; validated only on synthetic programs. The lastonesky loader loads both EXEs, so Phase 5 did not need it | n/a | skipped |
| [unlazy](https://github.com/Leonxlnx/unlazy) | Not evaluated by the research | Completion-discipline skill already present in the repo | project skill under `.claude/skills/` | installed, project scope |

## Other candidates from the kickoff and notes

| Item | Verdict | Note |
|---|---|---|
| [vscode-clangd](https://github.com/clangd/vscode-clangd) | Use, after Phase 5 | Same shim requirements as clangd-lsp |
| [objdiff VS Code extension](https://marketplace.visualstudio.com/items?itemName=decomp-dev.objdiff) | Later | WIP, few installs; use the CLI or GUI first |
| [Clang-Format VS Code extension](https://marketplace.visualstudio.com/items?itemName=xaver.clang-format) | Not evaluated | Not evaluated; format-on-save must stay off for C because formatting has to be proven build-neutral |
| [deep-codebase-search](https://mcpmarket.com/tools/skills/deep-codebase-search), [intelligent-file-search](https://mcpmarket.com/tools/skills/intelligent-file-search) | Not evaluated | Not fetched during research; likely redundant with built-in search, like file-search-skill |
| [Ketbome/decomp-skills](https://github.com/Ketbome/decomp-skills), [game-decomp-compendium](https://github.com/madpai/game-decomp-compendium) | Later (reference) | MIPS/MSVC-centred; no Watcom or DOS coverage |
| [reccmp](https://github.com/isledecomp/reccmp) | Later (reference) | MSVC-only matcher; its annotation convention is worth studying |
| ghidra-headless (trailofbits), ghidra (mitsuhiko) skills | Later | Useful for function discovery drafts if Ghidra automation needs a skill |
| [mosura](https://github.com/jdmichaud/mosura) | Use (probe) | Watcom version detection and codegen fingerprint for Phase 4 |
| [KKND-Decomp](https://github.com/Wyrelade/KKND-Decomp), [Theme Hospital decomp](https://github.com/matteo-pacini/theme-hospital-decomp) | Use (source of copied tools) | See the README's "Projects we build on" |

## Skill installation decisions

The repo targets Claude Code only for now (owner decision).

1. **unlazy** lives only under `.claude/skills/unlazy/`. Source: GitHub `Leonxlnx/unlazy`; `SKILL.md` sha256 `a1bf30a55d48d779db99b45d5b89004dd5eab0a0a4fe2b952188aae45c9d486b`. The duplicate `.agents/` tree written by the `npx skills` CLI was deleted, and `.agents/` is gitignored.
2. **`skills-lock.json` was removed.** It exists only to let `npx skills` re-sync, which would recreate `.agents/`. The source and hash above are the record instead.
3. **GSD is installed project-local for the Claude runtime only** (`npx @opengsd/gsd-core@1.18.0 --claude --local`). Files for other runtimes (`GEMINI.md`, `AGENTS.md`, `.cursor/`, `.codex/` and similar) are removed and gitignored. The installer (run 2026-10-19, v1.18.0, full profile) left no other-runtime files. It writes about 830 managed files (`.claude/gsd-core/`, `gsd-*` commands and agents, `hooks/`, `scripts/`, roughly 16 MB) and puts its hooks in `.claude/settings.local.json`, which is per-machine. Those managed paths are gitignored rather than committed: each contributor runs the same installer once, then `/gsd-health`. Project records under `.planning/` are committed.
4. **Skills we write go through superpowers' `writing-skills`** (owner, 2026-10-24). Every project skill created or updated under `.claude/skills/` (`watcom-decomp` in Phase 6, `apoc-spec` in Phase 8) is written with that skill. A third-party skill kept as installed, such as unlazy, is updated from its upstream instead, and its new source and hash go in item 1. The rule lives in `.claude/rules/workflow.md`.
