# Legal notes

This is a description of how the project handles copyrighted material, not legal advice.

## No game assets or code bytes in the repository

- No original executables, data files, CD images, extracted assets or disassembly are committed, now or later.
- Hashes (md5, SHA-1, CRC32) of the original files are committed. They identify the files without containing them.
- `.gitignore` and `.dockerignore` exclude `orig/`, `third_party/`, `asm/`, `build/`, `.env` and executable and image file types. Phase 1's gate checks that `git ls-files` contains no game file, no `.env` and no key.
- Never attach game files, executables or disassembly to issues or pull requests.

## You supply the game and the compiler

- **Game:** your own Steam or GOG copy. `uv run reverseapoc ingest` (Phase 2) copies the executables from the paths in your `.env` into the gitignored `orig/` and checks them against the hash manifest.
- **Compiler:** Watcom C/C++ 10.x and 11.0 are proprietary, and their current IP owner was not verified. The repository links to third-party archives and hosts no compiler bytes. `uv run reverseapoc fetch-watcom` is an opt-in convenience that you run on your own machine and at your own responsibility; nothing in the Dockerfile or CI runs it. The compiler lands in the gitignored `third_party/`, is mounted read-only into the container at run time, and is never baked into an image layer, so no image built from this repo carries it. Sources and commands: [Getting the Watcom compilers](toolchain.md#getting-the-watcom-compilers).
- Open Watcom v2 is redistributable under its own licence and is installed in the image, but only for auxiliary tools (`wdis`, `wlink`, `wlib`). It cannot produce matching code.

## Generated files stay local

`asm/` (disassembly) and `build/` (objects, rebuilt executables, reports) are regenerated on your machine from your own files and are gitignored. This follows KKND's `.gitignore` and Macabeus's script-generated Klonoa setup, and keeps the game's code bytes out of the repository.

## Licences in this repository

- **`tools/` is GPLv3** (version 3 or later). It includes modules copied from the [Theme Hospital decomp](https://github.com/matteo-pacini/theme-hospital-decomp) (`omf2elf.py` and related), whose tooling is GPLv3; their copyright headers are kept as-is. Code taken from [KKND-Decomp](https://github.com/Wyrelade/KKND-Decomp) (CC0) and [retrokit](https://github.com/nemo22/retrokit) (Apache-2.0) can be combined into a GPLv3 work; the reverse is not possible.
- **`tools/reverseapoc/search.py`** adapts the declaration pattern and the type-move loop of `tools/permute.py`, the search for the block holding every use from `tools/scope_decls.py` and the seeded declaration shuffles from `tools/permute_decls.py`, and **`tools/reverseapoc/classify.py`** adapts the register pattern of `tools/match/classify_diff.py`, all from [NHL95PC](https://github.com/abdulahmad/NHL95PC). That repository has no licence file, so nothing here is a licence claim for that code: each file's first lines name the origin, and they are used with attribution and the owner's permission (D-13).
- **Specs under `specs/` are CC0-1.0** (owner decision 2026-10-21). They are written in our own words from the matched code and from community sources, so OpenApoc (GPL-3.0) can use them, text included, without attribution. A spec can only be CC0 if we wrote it; see the source rules in [Specs and clean room](#specs-and-clean-room).
- **decomp.wtf** (MIT) was evaluated in spike 006 as a separate tool run as a subprocess in WSL2, and Phase 6 does not use it (D-03; it is re-evaluated for Phase 7). It is never imported or vendored, so its code does not mix with ours.
- **Decompiled C under `src/` and `include/`:** this code reproduces the logic of the copyrighted original game. It is written for interoperability and research, and published to help OpenApoc, a GPL reimplementation that requires the original game files, understand the original behaviour. As with Theme Hospital's decomp, the project claims no rights in it, and it ships with no assets. Rebuilding the game from it requires your own original executables.

## Specs and clean room

Phase 8 writes one behaviour spec per mechanic for OpenApoc. The decompiled C never leaves this repository; only the specs do. The roles, the review rule and the OpenApoc discussion behind them are in [clean-room.md](clean-room.md).

Community sources are read for facts, which are not copyrightable, and re-expressed in our own words:

- **UFOpaedia:** no open licence ("All of the texts on this website are copyrighted to their respective authors", `UFOpaedia:Copyrights`), and its robots.txt blocks AI crawlers. We fetch single pages for reference, throttled, with an honest User-Agent, never crawl it, cite by revision id and copy no prose or table layout.
- **StrategyWiki and Wikibooks:** CC BY-SA 4.0. Copying their wording or table layout would make a spec an adaptation under BY-SA, which conflicts with CC0, so we state the facts in our own structure and cite by revision id.
- **DOSBox wiki:** used for harness setup only, read by hand.
- **OpenApoc Discord:** read-only, paraphrased, linked by message URL; no bulk export is committed.

## AI use

AI tools, Claude Code in particular, are used openly for research, tooling and decompilation attempts. AI output is never trusted on its own: every match is accepted only after a deterministic byte comparison run by the build (objdiff, relocation checks, whole-EXE SHA-1), and the agent is blocked from editing the original files, hash manifests and build scripts.

From the Phase 6 driver (plan 06-23) on, the public record of every agent attempt is the committed `progress/attempts.jsonl` (D-23). It holds one line per attempt with the function, the attempt number, the outcome (matched, partial or gave up), the abort reason, turns, tokens, a cost estimate, the time taken, the model and CLI version, and a check summary. It holds no game bytes. Failed attempts are committed too, so the log shows what the agent could not do as well as what it matched. Transcripts and full check output stay in the gitignored `build/`.

## Model backends and what they receive

A matching session sends its model provider three things:

- the context pack: one function's disassembly listing, its Ghidra draft and our unit's C;
- the output of the attempt wrapper for the functions the session names (check results, byte and relocation differences);
- the repository files the session reads.

A session never sends a whole executable, and never anything under `orig/`. Every arm is listed in `config/driver/backends.toml`, and `sends_disassembly` there marks whether that arm's context packs leave the machine.

| Backend | Arms | What it receives |
|---|---|---|
| Anthropic | the Claude Code login: Opus, Fable, Haiku and Sonnet | the three items above, as since Phase 6 |
| OpenRouter | `deepseek-flash` (DeepSeek V4.1-Flash), `glm-5.3` (GLM-5.3), `glm-4.7-flash` (GLM-4.7-Flash), `gpt-oss-20b` (GPT-OSS 20B), `muse-spark-open` (Muse Spark Open), `qwen-hosted` (Qwen3.6-35B-A3B), and the Gemini fallback of D-21 if the Antigravity canary fails, all through OpenRouter's Anthropic-compatible endpoint. Since 2026-11-10 DeepSeek and GLM run only through OpenRouter, never through their own endpoints | the same three items; no read of `orig/` or `third_party/` |
| OpenAI | Codex CLI on the owner's ChatGPT Plus plan (plan 07.2-13): `gpt-6-luna`, `gpt-6.1-sol`, `gpt-6.1-terra`, `gpt-6-astra` | the same; Codex's sandbox restricts writes and the network, not reads, the driver runs the session's wrapper calls for it (the broker), and every command, write and stream item is audited after the session ends |
| Google | Antigravity CLI on the owner's Google AI Plus plan (plan 07.2-15): `gemini-flash`, `gpt-oss` and the Claude 4.6 arms `agy-sonnet-4-6` and `agy-opus-4-6`, whose packs go to Google, not to Anthropic | the same; agy's terminal sandbox does not run on the owner's Windows 10, so the driver's per-session permission rules and the post-session audit of every step are the guards |
| GitHub | GitHub Copilot CLI on the owner's Copilot Pro plan (spike 013, owner ruling 2026-11-13): `copilot-haiku-5-5`, `copilot-sonnet-5-5` and `copilot-gpt-6-luna`, whose packs go to GitHub and from there to the model's vendor (Anthropic or OpenAI) | the same; Copilot runs no sandbox here, so its per-session rules (the attempt dir as its only directory, reads and writes under `orig/` and `third_party/` denied, every URL denied, only the session's own files writable) and the post-session audit of every tool call are the guards; its shell rules cannot reach paths, so a shell read is detected only after the fact |
| local llama.cpp server | `qwen-local` (Qwen3.6-35B-A3B on the owner's machine) | nothing leaves the machine: the server listens on loopback only, and `sends_disassembly = false` |

The rules:

- **Opt-in.** The owner opted in on 2026-11-09 to send context packs to the non-Anthropic backends above for spike 012. A non-Anthropic arm whose `sends_disassembly` is true runs only when both `--night-model <arm>` and `--allow-egress <arm>` are given. An `--allow-egress` that names any other arm is refused, so a typo can never send packs to a new backend (D-11).
- **No game files or compiler.** A Claude Code session of a non-Anthropic arm runs with `REVERSEAPOC_EGRESS=1`. The matching hook then denies every Read, Glob and Grep that can reach `orig/` or `third_party/`, by any path form or wildcard, without relying on `.gitignore`. The Codex, Antigravity and Copilot sessions have no such hook (Copilot's file tools are denied those paths by its rules; its shell commands are not). Neither CLI's sandbox restricts reads on the owner's machine (Codex's limits writes and the network; agy's does not run on Windows 10), and agy's per-session rules deny reads of those paths. The driver's audit after the session treats any command or read naming `orig/` or `third_party/` as a stray, which detects such a read but cannot recall what was already sent (plans 07.2-13 and 07.2-15).
- **Keys.** A hosted arm's key comes only from the user environment variable that `backends.toml` names. Every hosted arm names `OPENROUTER_API_KEY` (see [Model API keys and sign-ins](toolchain.md#model-api-keys-and-sign-ins)). `DEEPSEEK_API_KEY` and `ZAI_API_KEY` are not used, and the driver strips both from every session. The driver copies it into that one session's environment and never logs, records or writes it. A missing or empty key stops the run before any session, because Claude Code would otherwise send the owner's claude.ai login to that endpoint (D-12, D-26). Codex, Antigravity and Copilot use their own sign-ins and need no key.
- **Antigravity permission rules (D-24).** Per session first: before each agy session the driver writes a settings file under gitignored `build/driver/<run>/agy/` and passes it with `--settings`. It is never saved in the repository or in the owner's agy settings. Only if the owner's agy canary shows that `--settings` cannot restrict tools may the owner add a minimal user-global rule set to `~/.gemini/antigravity-cli/settings.json`: allow only `command(regex:^uv run --frozen reverseapoc attempt ...$)` (the wrapper forms) and deny everything else. The driver never writes that file. If it is added, it is listed here with its date, and it is removed by deleting those rules from that file (or the file, if nothing else is in it). None is in use today.

## Why not IDA Free

IDA Free was rejected. Its decompiler runs in Hex-Rays' cloud, so function bytes would leave the machine, and the owner wants analysis to stay local. It also cannot load LE executables (its file formats are PE, ELF and Mach-O), has no IDAPython and is not supported by ida-pro-mcp. Ghidra with an LE loader runs fully locally.

## Community reception and our conduct

Parts of the decompilation community oppose AI-driven decompilation: decomp.wtf was archived and decomp.dev closed to new projects in October 2026, both citing AI-driven behaviour. Our conduct follows from that:

- State AI use openly (README and this file).
- Do not flood shared services such as decomp.me with agent-generated scratches; use them sparingly, by hand, for genuinely hard functions.
- Credit prior reverse engineering, especially OpenApoc's extractors and its contributors' Ghidra work, wherever it is reused.
- List the project in directories (recomp.fyi, decomphub.com) honestly as an AI-assisted decomp.
