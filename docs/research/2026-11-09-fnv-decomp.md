# Fallout: New Vegas decomp (fnv_decomp): what it can teach ReverseApoc

Research date: 2026-11-09. Sources: the author's video, the GitHub repo, the project site and the agent brief of its
Fallout 3 successor, read through Tavily, read-only `gh api` calls and Playwright (for the JS-rendered site). The
video was also downloaded (yt-dlp), sampled with ffmpeg (one frame every 6 s over 3:57 to 6:48) and transcribed
locally with faster-whisper `medium.en`. Nothing from it is committed; frames and transcript stayed in the session
scratchpad.

- Video: [Fallout: New Vegas Is Now Fully Decompiled (Here's How I Did It)](https://www.youtube.com/watch?v=Ff8su9nY4os),
  Momus Digital, posted 2026-11-04, about 10 minutes.
- Repo: <https://github.com/momusdigital/fnv_decomp>
- Site (closed to contributions, final report): <https://fnvdecomp.com/>, method page <https://fnvdecomp.com/how.html>,
  terms <https://fnvdecomp.com/legal.html>
- Agent brief of the Fallout 3 successor, the same system still live: <https://f3decomp.com/agents.md>

## Takeaway

One author matched all 70,611 in-scope functions (11,537,067 bytes) of `FalloutNV.exe` 1.4.0.525 byte for byte in
about three and a half weeks, with about 50 volunteers pointing their own AI agents at a claim server. The repo holds
no Claude Code setup at all: the orchestration was the web service, and the repo is the source published at 100% plus
a CI gate. Most of what is worth copying is in the server's agent contract (claims, context packs, give-up records,
mandatory work notes, strikes) and in the measured lessons on the method page, not in the repo.

Their proof is weaker than ours. Each COFF object is compared function by function, with relocations, against the
user's own PE; the EXE is never relinked. Critics on Reddit point this out. ReverseApoc's gate splices each match into a
copy of the retail EXE and checks the whole file's SHA-1.

## Cited findings

### Toolchain and proof

- Compilers chosen per unit in `build/units.json`: VC++ 2008 SP1 15.00.30729.01 (almost every unit), 2008 RTM
  15.00.21022.08 and VC++ 2005 SP1 14.00.50727.762, run under Wine on Linux. Some units exist as `*_ob1_variant.cpp`
  copies because the game mixed optimisation settings. (repo README)
- `build/units.json` lists, per unit, the source, compiler, flags and functions (address, decorated symbol, size,
  fold aliases), so symbols are bound by the manifest, not a linker map. (repo)
- Own Python tools, no objdiff and no Ghidra or IDA scripts in the repo: `tools/msvc.py` (compiler wrapper),
  `tools/compare.py` (COFF vs PE, relocation targets resolved), `tools/function_spans.py` ("entry to next entry ...
  minus trailing 0xCC/0x90 padding; includes switch tables and inline data"), `tools/build_and_match.py` (full run
  against the user's EXE, SHA-256 fingerprinted, exit 3 on a mismatch, no game bytes printed),
  `tools/compare_builds.py` (base vs head for PRs), `tools/verified_eh.json` (owner allowlist for exception code). (repo)
- Exception-handling funclets placed elsewhere by the linker are found through the handler address the function pushes
  and compared as part of their parent. (repo)
- In the video (about 2:12) the footage shows the game running the decomp's code, so matched functions are also
  loaded into the real executable.

### CI without the game

- `.github/workflows/match.yml` runs on `pull_request_target`, always with main's tools, and fetches the PR as data.
  It builds the affected units at base and at head under Wine and requires identical output; main is already proven
  against the EXE, so no game copy is needed in CI. Renames and comments pass; a comment-only change skips the build.
- Compilers are downloaded from Microsoft with SHA-256 checks; the unpacked folders are digest-pinned
  (`MSVC_SP1_DIGEST`, ...). A PR touching anything outside `src/`, `include/`, `units.json` and `*.md` needs a
  maintainer. Two approvals, and the last push must be approved by someone else. After every merge, main is also built
  against the real EXE on the owner's machine. (repo)

### The agent contract (f3decomp.com/agents.md, same system as fnvdecomp.com)

- Agents connect through a GitHub device-code flow, get an API key and an MCP server
  (`claude mcp add --transport http f3decomp https://f3decomp.com/mcp`) and a local checker kit (`f3check`).
- One function per claim, 2-hour lease. A claim returns a context pack (the unit's source with every other function body
  removed, plus headers) and `best_attempts` from earlier agents.
- Give-ups are structured: a category (`register_allocation`, `stack_layout`, `eh`, ...) plus `tried`,
  `still_differs`, `suspected_cause` and `best_code`. The next agent starts from them, and a host-side permuter keeps
  working on close attempts.
- Work notes are mandatory: a plan before coding (`FRAME/SLOT/CALL/REGION R1 0x00-0x2b ...`, with REGIONs covering
  the whole function) and per check `--change/--why/--expect/--observed`. The checker refuses a check without them.
- For functions of 1 KB or more the checker prints which 0x100-byte regions are already exact.
- Code rules: no inline assembly, no naked functions, no raw byte emission, no hard-coded absolute addresses, no filler
  arrays, unknown fields named `unkXX` at their offsets. Two x87 idioms are allowed only through helper functions
  (`f3_SinCos`, `f3_FloatToInt`).
- Shared knowledge files: `compiler_tips.md` ("How the back end decides", from tracing the compiler) and
  `large_functions.md`.
- Every submission is re-verified on the server overnight. A failed one is a strike; three in seven days pause
  submissions. Trust tiers New (up to 511 B), Regular, Trusted, Power, Swarm (150 open claims) unlock by verified
  match rate.
- Every claim and submit records model, harness and token usage; the site publishes a by-model leaderboard and a cost
  and token ledger.

### Measured lessons (fnvdecomp.com/how.html)

- About 3 tries in 100 match: 42 fail to build, 55 build with different bytes (96,537 tries over 1.5 days).
- Gaps in shared class declarations caused about 34% of build failures; fixing one unblocks many functions. Agents
  pasting their own copy of a class declaration caused about 28%, so a checker auto-repairs that before compiling.
- Near misses are not nearly done: an instruction-reordering tool fixed 0 of 40 functions that were one or two
  instructions off.
- Thinking effort: Claude matched 12 of 20 big functions at its lowest setting and 17 of 20 at its highest, with less
  code per unit of effort at the top. They ran it at a middle setting.
- Bytes are the honest measure: the function count flattered them because about 22,000 small generated functions went
  first, and near the end two thirds of the remaining code sat in large functions.
- Routing by size: scripts for about 22,000 boilerplate functions, a fine-tuned local Qwen 27B under 256 B, cheap
  models on a $10/month plan for mid sizes, Claude, Codex and Gemini from 512 B up. Fine-tuning on proven matches took
  the local model from 8 to 37 matches out of the same 300 unseen functions.
- Function comments were drafted by Qwen 27B and reviewed by Codex and Claude Sonnet, labelled as possibly wrong. Names
  carry provenance markers: `// src: EXE|HAVOK_LIB|GAMEBRYO_LIB|CRT_LIB|COMMUNITY|XBOX_PDB|...|GUESS 0xADDR
  (confidence: high|medium|low)`. (repo README)

### What the video adds (frames and transcript)

- The first attempt was a $200/month Codex plan told to "research this ... and do the same for Fallout: New Vegas"
  and build a Linux port. After 2 to 3 days it had 3,245 JSON files, 1,198 Python files, 1,072 text files and about 775
  C/C++ files, "mostly verification receipts", stalled. A $20 Claude plan audited it and found about 3 KB of 11.54 MB
  proven. That audit led to the claim-server design.
- Bytes matched by model, from the frame at 6:15: GPT-6 / Codex 36.4%, Claude Opus 5.5 22.7%, 20+ other models 21.9%,
  scripts 5%, the fine-tuned Qwen 27B 3.4% (the bars sum to about 89%; the rest is not shown).
- Leaderboard frames: top contributors have almost no failed submissions (connorx2000 6,909 matches from 7,377
  submissions; h-x3n 4,692 from 4,692), so agents submitted only after the local checker passed.
- About 100 people came by; about half got through setup into the Discord. 40 to 50 worked at once.
- The author had no decomp background; the expertise was in the design (split into functions, the original compiler as
  judge, a claim server).
- He expects subscriptions to get dearer ("API pricing is subsidized") and plans to lean on fine-tuned local models.
- Critics call the output unreadable and "missing things other decomps have"; r/fnv removed his posts as "AI content".

### Timeline and cost

| Date (2026) | Milestone |
|---|---|
| 09.10 | First 10,011 functions |
| 11.10 | Codex "worker army" adds 14,809 functions in one day |
| 17.10 | Fine-tuned Qwen deployed |
| 20.10 | Public site opens to the community |
| 24.10 | Community takes over all matching |
| 31.10 | 100% matched |
| 01.11 | Integration into the source tree complete |
| 02.11 | Source published (repo created 31.10, first commit 02.11, single squashed import) |

Source: <https://fnvdecomp.com/> milestone log; repo history via `gh api`. The failed Codex run came before 09.10; its
length is only "two or three days".

- People: one lead (47,632 functions credited, many generated by scripts) and about 50 contributors; `CREDITS.md`
  names 45 plus 8 anonymous.
- Tokens: 38.1 billion processed, 519 million generated, 95% cached re-reads; Claude alone ran about 1,550 sessions.
- Money (self-reported, "compiled by hand"): $0 in metered API fees, $263.70 of Google Cloud trial credit, four flat
  subscriptions, three local machines (an RTX 5090 tower, two DGX Sparks, a Mac mini). A TikTok caption by the author
  says "$8.5-9k actually", probably hardware; not verified.

### Community context

- About 15 October 2026 decomp.dev took down its public index and leaderboard, blaming AI "slop" and AI forks racing
  human-led projects ([Broken Joysticks](https://www.brokenjoysticks.net/2026/10/19/decomp-dev-pulls-the-plug-on-its-public-index-as-ai-slop-breaks-the-community)).
- Reddit is split: [r/falloutnewvegas](https://www.reddit.com/r/falloutnewvegas/comments/1xqepsf/so_fnv_has_been_decompiled)
  sceptical, [r/FalloutMods](https://www.reddit.com/r/FalloutMods/comments/1xpxr5b/) enthusiastic,
  [r/decomps](https://www.reddit.com/r/decomps/comments/1xm007y/fallout_new_vegas_decomp_is_now_available) on the
  missing relink.
- Downstream users within days: a New Vegas co-op mod (nine bugs fixed with it), nv-rs (a Rust engine rewrite), a
  second co-op mod and a Tale of Two Wastelands mod.

## Inferences for ReverseApoc

Ideas we could take, each now a backlog item in `.planning/ROADMAP.md` (999.5 to 999.11):

1. Structured give-up records (category, tried, still differs, suspected cause, best code) in place of free-form
   PARTIAL notes, fed to the next attempt and to the difficult list.
2. Plan before code and per-check change/why/expect/observed notes, enforced by the attempt check.
3. A region board for large functions: which 0x100-byte regions are exact and which saved draft is closest for each.
   Fits the 256 B+ work queued from Phase 7.1.
4. Treat missing struct fields as a first-class blocker: count build failures by cause, and fix the shared header that
   unblocks the most functions. Quick task 261107-qkd already closed their 28% case (a draft redeclaring what its
   header declares).
5. Measure thinking effort and model by function size, with a per-function token ledger by model, effort and harness.
   Also serves the night usage calibration and the paper idea.
6. Name provenance markers (`// src: TAG 0xADDR (confidence)`) for the readability work.
7. Base-vs-head CI: once main is proven, a PR only has to compile identically to main. Our Watcom compiler is
   user-supplied, so this needs a self-hosted runner.

Decisions this supports: never trusting an agent's own match claim (the 3 KB Codex audit), skipping decomp-permuter
(0 of 40 near misses fixed), byte-based progress (our recomp.fyi matched code percent), and keeping readability separate
from matching (the main criticism).

Not a timeline for us: their speed came from a crowd of 50, their own GPUs, a well-known compiler and per-function
proof without a relink. By our night calibration (about 95 sessions per 10% of the weekly limit), their 1,550 Claude
sessions would be about 1.6 weeks of one person's quota.

## Gaps

- Which decompiler they used is never stated; the `FUN_00xxxxxx` placeholders suggest Ghidra.
- No functions-per-day figure; the site's chart data did not extract.
- The start date of the failed Codex run and the true hardware spend are not verified.
- The "by model" bars in the video sum to about 89%; the remainder is not explained.
