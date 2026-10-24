# Phase 6: Reporting and agent pilot - Context

**Gathered:** 2026-10-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Progress is published from gate-written data, and an unattended per-function driver matches easy functions under guardrails. The build decides every match, never the agent. The phase covers both UFO2P.EXE (`ufo24`) and TACP.EXE (`tac4`).

- **Reporting (RPT-01..05):**
  - a committed per-function status table that only the local gate writes;
  - stdlib `progress.py` writing progress.json, the treemap progress.svg, a shields endpoint JSON, an objdiff-shaped report.json and the DecompHub feed;
  - a GitHub Pages deploy;
  - the `<VERSION>_report` artifact for recomp.fyi;
  - `.recomp.json` and the listings.
- **Agent pilot (AGT-01..11):**
  - the decomp.wtf stub-convention spike;
  - our own Python driver, which runs one fresh `claude -p "/goal ..."` session per function;
  - guardrail hooks, the `watcom-decomp` skill, the context pack and an attempt wrapper for direct `check`/`asm`/`context` calls (D-44);
  - the easiest-first scorer and the zero-regression gate;
  - an owner-started pilot that matches 10 easy functions.
- **Every open deferred item from Phases 1-5** (DI-01..DI-37 below). The owner put all of them in scope on 2026-10-24.

Not in this phase:
- mechanics-driven matching at scale, claims for parallel agents, and readlint (Phase 7);
- clean-room specs (Phase 8);
- SMKP.EXE matching (deferred).

Requirements: RPT-01..05 and AGT-01..11 (`.planning/REQUIREMENTS.md`). Roadmap spike: decomp.wtf fork mode accepts the repo's stub convention.

Facts fixed before the discussion (owner, 2026-10-24):
- **Repo:** public. GitHub topics `matching-decompilation` and `game-preservation` added (12 topics in total).
- **DecompHub:** the entry was submitted by the owner and is pending review. Its fields are in auto-memory `decomphub-listing-entry`.
- **Listings in scope:** recomp.fyi (automatic, through `.recomp.json` and the report artifact); the DecompHub progress feed and verification file; drafted PRs to yibie/awesome-rea, SubmitGame/awesome-decomp-games and CharlotteCross1998/awesome-game-decompilations; a drafted decomp.me msdos preset request, which the owner files by hand because decomp.me bans LLM and automated access.
- **Listings ruled out:** Rebuild Atlas, PCGamingWiki, MobyGames, Wikidata, and the OpenApoc channels (Milestone 1 has no OpenApoc contact). Reddit, GBAtemp and decompals come later, at the owner's call.
- **Third-party submissions:** Claude drafts each one; the owner sends it or approves that one submission.
- **Pilot:** the owner starts the real pilot run. Execution builds the driver, tests it against a stand-in `claude`, and stops at a blocking-human checkpoint.
- **unlazy:** no Stop hook; the gates ledger is kept.

</domain>

<decisions>
## Implementation Decisions

### Spike AGT-10 (decomp.wtf v0.10.6 fork mode)
- **D-01:** The spike is the code evidence plus a half-day smoke run.
  - **Code evidence:**
    - The stub regex in `forks/csource.py` (`_stub`) needs `"`, `/`, `,` or a space before the name, so `INCLUDE_ASM(func_X);` does not match it.
    - Fork mode looks functions up by objdiff's linker name `func_X_` (`forkengine._names` L1484-1497).
    - Fork mode would add a second definition next to the marker, which `configure.py:304` refuses.
    - Its build runs `python configure.py` and `ninja` in WSL2, where uv, ninja, wibo, objdiff-cli and claude are all missing.
    - `_CHEAT` (`app/forkengine.py:37`) is applied only to what the agent submits, so existing `INCLUDE_ASM` lines are not refused.
  - **Smoke run:**
    - Install pinned v0.10.6 in WSL2 with `uv tool install "decompnet @ https://github.com/i12bp8/decomp.wtf/archive/refs/tags/v0.10.6.tar.gz"`. MIT; the tag is commit `eba4693c`.
    - Open a clone in fork mode and submit func_000A3980's known C through `compile_and_diff`, recording the real failure mode.
    - Do not build the full WSL2 toolchain.
  - The spike is recorded as `.planning/spikes/006-*` under the spike CONVENTIONS.
- **D-02:** The verdict follows Phase 5's D-02.
  - VALIDATED: unpatched v0.10.6 puts a definition in place of our marker, scores it through our ninja and objdiff, and `check` still exits 0.
  - PARTIAL: the same, but only after at most about 50 lines of patches (stub regex, `name_` to `name` lookup) plus a build wrapper.
  - INVALIDATED: anything deeper, or no build in WSL2.
- **D-03:** No patched decomp.wtf in Phase 6. PARTIAL is treated like INVALIDATED for the pilot. decomp.wtf is re-evaluated for Phase 7's parallel claims (DEC-02/DEC-06). `docs/legal.md:26` ("never imported or vendored") stands.
- **D-04:** The fallback "minimal own agent layer" has these parts:
  - the driver (D-05);
  - the hooks (D-15..D-17);
  - the `watcom-decomp` skill (D-19);
  - the context pack (D-13, D-14);
  - **direct CLI calls** for `check`, `asm` and `context`, through a Bash allowlist (D-44).

  **Revised by the owner on 2026-10-24, after research.** The discussion had picked a stdlib stdio MCP server so that agents would get no shell at all. The owner reversed that before any plan was written: there is **no MCP server**. Agents get Bash, and the hooks plus `--allowedTools` restrict it to those wrapper commands only. There are no claims and no SQLite. — **Reversibility:** costly — the wrapper command names are referenced by the skill, the hooks allowlist and the tests.

### Driver AGT-01/02/03/04
- **D-05:** Our own stdlib Python driver, `tools/reverseapoc/driver.py`, plus a `reverseapoc drive` verb, built test-first. It owns the outcome log, backoff, gate calls and the commit. Nigel is rejected: it has no licence (GitHub `license: null`), needs Go (not on the host), logs no turns or tokens, and detects limits by one phrase.
- **D-06:** Each session is launched as:
  ```
  claude -p "/goal ..." --output-format stream-json --verbose --max-turns 40
    --model claude-opus-5-5 --permission-mode dontAsk
    --tools "Read,Edit,Write,Glob,Grep,Bash"
    --allowedTools "Read,Edit,Write,Glob,Grep,Bash(<attempt wrapper> *)"
    --strict-mcp-config
    --setting-sources project --settings config/driver/claude-settings.json
    --append-system-prompt-file .claude/skills/watcom-decomp/SKILL.md
    --max-budget-usd 5
  ```
  This is the command as revised after research (D-44, D-45).
  - The driver settings file adds the matching-session hooks (D-16) and turns off plugins such as security-guidance, whose Stop review costs tokens.
  - `--setting-sources project` keeps the per-machine GSD hooks in `.claude/settings.local.json` out.
  - `--bare` is not used: it needs `ANTHROPIC_API_KEY`, and the owner uses a subscription.
- **D-07:** One attempt is one fresh session. The caps:
  - at most **3 sessions per function per pass**;
  - `--max-turns 40`;
  - a 30-minute wall clock;
  - a /goal clause: "or stop after 25 check runs".

  A capped function goes to a difficult list. It is re-queued later, once the easy pool is exhausted or one of its callees gets matched.
- **D-08:** The driver backs off by error class, read from stream-json `system/api_retry.error`, the final `result` event and the result text.
  - `rate_limit` or "hit your ... limit": back off 1, 2 and 4 minutes, then poll every 5 minutes. This is not counted as an attempt.
  - `authentication_failed`, `billing_error`, "Credit balance is too low" or "Not logged in": stop the run and write a STOPPED record.
  - `overloaded` or `server_error`: 3 retries, then the attempt is aborted (not counted).
  - The owner's plan is **Max 20x**, so the night cap is **30 sessions or 10 MATCHED, whichever comes first**, with `--max-budget-usd 5` per session as a runaway guard.

### Scorer AGT-07
- **D-09:** Reuse `score.assess` (the P16 filter) as it is, plus status awareness: skip functions that are matched, capped, or partial in this pass. About 1308 candidates remain. Admitting pure leaf functions, adding features (no jump table, no static, no x87, size ≤ 64) and dropping the constant `WEIGHT_NO_FRAME` are recorded as Phase 7 tuning.
- **D-10:** The pilot picks 5 UFO2P + 5 TACP, interleaved, easiest-first within each EXE. Variety rule: at most 2 per unit and at most 3 per 64 KiB region. This keeps the pilot off UFO2P's eight look-alike 27-byte functions at 0x0008A0E0..0x0008A1C0 and gives DI-25 evidence from different regions.

- **D-11, D-12:** not used. The numbering is kept stable so references don't shift.

### Context pack AGT-08
- **D-13:** The pack is written by a `context` CLI command. The driver runs it before each attempt, and the agent may re-run it through the attempt wrapper (D-44). It holds:
  - the target asm listing (`asm/<exe>/<name>.s`);
  - the unit file;
  - caller and callee signatures with their match status;
  - the `D_` externs the function touches;
  - `include/common.h`;
  - the Ghidra draft (`asm/<exe>/ghidra/func_X.c`);
  - the matching.md idioms;
  - PARTIAL notes from earlier attempts;
  - **up to 3 matched look-alike functions**, chosen by opcode-sequence similarity (the coddog idea), with their C.

  Ghidra drafts are precomputed in one container batch for the scorer's top N (`ghidra-export --drafts`).
- **D-14:**
  - The pack is capped at **24 KB**, truncated in a fixed order: look-alikes, then callers, then the draft.
  - It is written to gitignored `build/driver/<run>/<exe>/<func>/`, because listings and drafts are game-derived (`docs/legal.md` "Generated files stay local"). It is never committed.
  - GhidraMCP stays out ("Later").

### Guardrail hooks AGT-05 (+ DI-07)
- **D-15:** The hooks are stdlib Python in `tools/reverseapoc/hooks.py`: a pure decision function plus a thin entry, run as `uv run --frozen python -I -m reverseapoc.hooks pre-tool-use`.
  - They are linted by ruff.
  - pytest feeds hook JSON payloads covering Windows and POSIX paths, `..`, and letter case, and asserts deny or allow. One subprocess end-to-end run is included.
  - They do not live in `.claude/hooks/`, which is gitignored, GSD-managed and excluded from ruff.
- **D-16:** The hooks come in two layers.
  - **Always on, in `.claude/settings.json`:** block edits under `orig/`, `config/targets.toml`, `config/watcom.toml`, any `*.sha1`, `asm/` and `build/`, and block `_asm`, `__asm` and code-emitting `#pragma aux` in `src/` and `include/`.
  - **Matching sessions only, in `config/driver/claude-settings.json`, passed with `--settings`:** the D-17 allowlist. A by-hand matching session passes the same file.
- **D-17:** The matching-session allowlist denies by default.
  - Writes are allowed only to:
    - the claimed unit's `src/<exe>/<unit>.c`;
    - new headers under `include/` (never `common.h` or `watcom_compat.h`, where `INCLUDE_ASM` could be redefined);
    - the attempt's `build/driver/.../notes.md`.
  - Bash runs only the attempt wrapper's `check`, `asm` and `context` subcommands (D-44). Every other Bash command is denied, including any with shell chaining, pipes, redirection, substitution or a second command. Their other tools are Read, Edit, Write, Glob and Grep.
  - The wrapper's `check` may run `check --sweep` as a diagnostic. A sweep hit is recorded as PARTIAL "needs flags X" for the owner to decide (D-18 of Phase 5: cflags.txt is owner-only).
  - The block covers cflags.txt, the cc wrapper, configure.py, tools/, the manifests, status.csv, `.claude/`, `.github/` and `tests/` (DI-07).
  - After each attempt the driver checks `git status --porcelain` against the allowlist. Any stray path resets the attempt and stops the night.

### watcom-decomp skill AGT-09
- **D-18:** Pragma policy: agents may write **no `#pragma aux` of any kind** during the pilot, and the hook blocks it. Calling-convention pragmas come only in human-reviewed commits. Reconcile `.claude/rules/src.md:15` and `docs/coding-style.md:22` to say this. Default `__watcall` needs no pragma.
- **D-19:** `.claude/skills/watcom-decomp/SKILL.md`, at most 300 lines. **Author it with the `superpowers:writing-skills` skill (owner).** Its sections:
  1. `__watcall` registers (eax, edx, ebx, ecx) and the `name_` / `_name` linker names.
  2. Flags: the `*` default, no `-s` for `__CHK` functions, and that cflags.txt is owner-only.
  3. C89 rules and the lint.
  4. The pragma policy (D-18).
  5. Relocation rules (docs/matching.md L59-68).
  6. Strings move to extern `D_` symbols; no statics or jump tables until DI-02/DI-03 widen the pool.
  7. `INCLUDE_ASM`: replace the marker; extern names.
  8. The attempt wrapper's `check`/`asm`/`context` commands (D-44), check's JSON, and its exit codes 0/1/2.
  9. When to give up.

  It links to docs for depth, and a pytest checks that every path, verb and command it names exists.

### Status table RPT-01 and attempt log AGT-03
- **D-20:** The status table is a sparse `config/<exe>/status.csv`, with rows only for matched or partial functions; a missing row means unmatched.
  - Columns: `start,name,unit,status,best_percent,attempts,source_sha256,date`.
  - There is no commit column, because a commit cannot contain its own hash.
  - It sits next to functions.csv, which Phase 5 D-10 kept free of status.

  — **Reversibility:** costly — the drift test, progress.py, report.json, the DecompHub feed and the gate all read this schema.
- **D-21:** The only writer is a new `reverseapoc gate EXE/UNIT` verb, run in the container.
  - It runs `check`. On exit 0 it writes matched rows for every function the unit defines, and rewrites `decomphub.progress.json`.
  - `--partial` writes partial rows.
  - The driver calls it, and humans call it after a by-hand match.
- **D-22:** A CI drift test catches hand edits without game files:
  1. matched rows equal exactly the functions defined in C in `src/` (the existing `source_marks` parser);
  2. each matched unit's LF-normalised `source_sha256` equals the file, so any edit to matched C, even a rename or comment pass, must be re-gated;
  3. the progress, report and DecompHub outputs equal what `progress.py` derives;
  4. the hooks also block agent edits of status.csv.
- **D-23:** The outcome log is a committed `progress/attempts.jsonl` with no game bytes.
  - Fields: function, attempt n, outcome MATCHED/PARTIAL/GAVE_UP, abort reason, turns, tokens, cost estimate, seconds, model, CLI version, and a check summary. It has a schema test.
  - Transcripts, packs and full check output stay in gitignored `build/driver/`.
  - Failed attempts are committed with the next match, or in one `chore(driver): attempt log` commit at the end of the night.
  - It is public evidence of AI use (`docs/legal.md` "AI use").

### Zero-regression gate AGT-06 and commits
- **D-24:** Before each commit the driver runs `gate` for the unit in the container. That covers:
  - objdiff and the relocation check for the unit;
  - landing every compiled unit of both EXEs;
  - both SHA-1s;
  - no refusals;
  - a **new cross-check that the landed set equals status.csv's matched set**, which catches a match reverted to `INCLUDE_ASM` that the whole-EXE SHA-1 cannot see.

  At the end of each run: `python configure.py && ninja verify` from clean, plus `gate --all` (objdiff for every matched unit). No git hook, and no CI part (CI has no game files).
- **D-25:** Commit format for a match: `feat(<exe>): match func_0008A0E0 in u_0008a0b0 (C89)`.
  - The body carries attempt n/3, model, turns, tokens, seconds, objdiff 100%, relocation ok, and both SHA-1s.
  - Trailers: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, set explicitly because `.githooks/commit-msg` adds it only when `CLAUDECODE` is set; and `Matched-By: reverseapoc drive`.

### Progress, Pages, report and DecompHub RPT-02/03/04/05
- **D-26:** What is measured:
  - The main figure is matched bytes of game and thunk functions over all game and thunk bytes, per EXE and combined.
  - The runtime library is its own group, "library, not decompiled", outside the percentage.
  - Data-in-code is excluded. Bytes outside any functions.csv row count as unmatched code (DI-24).
  - Treemap: EXE, then unit, one cell per function sized by bytes, coloured matched / partial / unmatched / library.
  - Shield: the combined percentage, labelled "decompiled".
  - File names already published in README.md:8-14 are kept: `progress.json`, `progress.svg`, `progress-shield.json` under `https://ayrtondenner.github.io/ReverseApoc/`.
- **D-27:** Pages is deployed by `.github/workflows/pages.yml`.
  - It runs on push to `main` (with a paths filter) plus a weekly `schedule`.
  - Steps: checkout@v7, `python -I tools/progress.py` (stdlib), upload-pages-artifact@v5, deploy-pages@v5.
  - The owner sets Settings > Pages > Source to "GitHub Actions" once; Pages is not enabled yet.
  - The weekly run also refreshes the report artifact before its 90-day expiry.
- **D-28:** `progress.py` builds report.json in CI from status.csv and functions.csv, in objdiff's report shape (`measures`, `units`, `categories` ufo2p/tacp).
  - It is uploaded as **one combined artifact, `X-COM_Apocalypse_DOS_report`**, so recomp.fyi's several-versions rule never applies.
  - Every `measures` field is filled, because recomp.fyi's ingestion is private. The shape is tested against objdiff's `report.proto` field names.

  — **Reversibility:** costly — recomp.fyi reads the artifact by name daily.
- **D-29:** `decomphub.progress.json` (progress-v1) is committed at the repo root.
  - `gate` rewrites it.
  - It has no `revision` field, since a file cannot hold its own commit hash.
  - Tracks: `ufo2p-code` and `tacp-code` (percent of bytes), and `ufo2p-functions` and `tacp-functions` (ratio).
  - README links it.
- **D-30:** **Plus a CI POST** to `https://app.decomphub.com/api/progress/refresh` (or the documented endpoint) with `{repository, github.sha}` on push to main, behind a repo variable. The owner approved this outward-facing call on 2026-10-24.
- **D-31:** A DecompHub maintainer verification file (two-sentence ownership statement, like TheGh0stShip's `docs/DECOMPHUB_VERIFICATION.md`) is added. The owner files the maintainer claim.
- **D-32:** `.recomp.json` update (DI-37):
  - `status` moves to in-progress once the pilot lands;
  - `links` gets the Pages progress page;
  - `notes` drop "retrokit", and drop "decomp.wtf fork mode" if the spike does not validate;
  - "ai-assisted" stays in the tags.

  It must validate against `https://recomp.fyi/schema/v1.json`.
- **D-33:** Listing drafts (DI-35, DI-36):
  - **Awesome-lists:** a PR text per list, in each list's own format:
    - awesome-rea: `categories/game-decompilation.md`, naming its acceptance test, byte comparison;
    - awesome-decomp-games: `data/additions.json`, with platform DOS and type decomp;
    - awesome-game-decompilations: the PC section, marked AI.
  - **decomp.me:** a preset issue (platform `msdos`, compiler `wcc10.6`, flags `-4r -s -fpi`).
  - All drafts go in a committed `docs/listings.md`. The owner opens or files each one.

### Pilot AGT-11
- **D-34:** The driver runs on the Windows host in the main checkout.
  - Every check and gate goes through `docker compose run --rm build ...`, and Docker Desktop must be up.
  - The owner does not work in the checkout during a run.
  - Reset after a failure: `git restore --source=HEAD -- <claimed unit> include/`, plus deleting any untracked file in the allowlist.
  - A per-attempt worktree is not used: compose mounts `orig/` and `third_party/` relative to the checkout.
- **D-35:** The model is pinned to **Opus, latest: `claude-opus-5-5` (Opus 5.5)**, for every attempt. Its full ID is logged with `--max-turns 40` and `--max-budget-usd 5` per session.
- **D-36:** **Upgrade and pin the Claude CLI** before the pilot.
  - The host has 2.1.240 today, which predates `--permission-prompts` (2.1.259) and the documented `-p` permission default (2.1.302).
  - The owner runs the upgrade at the pilot checkpoint.
  - Every attempt logs `claude --version`, and the docs state the minimum version.
  - The driver refuses an untested major version, because `--bare` may become the `-p` default and would drop subscription login.
- **D-37:** Done criterion: one owner-started run reaches 10 MATCHED, with:
  - each match its own commit;
  - the D-24 gate passing after every commit for both EXEs;
  - at least 3 functions from each EXE;
  - no guardrail breaches;
  - a complete attempt log.

  The driver may back off and resume on its own. **Ceiling: 40 sessions**, after which the pilot stops and reports PARTIAL at the checkpoint instead of grinding.

### Deferred inventory (DI-01..DI-37; all in scope, owner 2026-10-24)
- **D-38:** Plan grouping and wave order. The planner may split or merge plans for file overlap, but keeps this order.

  | Wave | Plans |
  |---|---|
  | 1 | spike 006 (D-01..D-03); `asm` ambiguous-name fix (DI-01); oracle hardening (DI-04, DI-05, DI-06); cc and log cleanup (DI-11..DI-18); the Phase 5 minors (DI-19) |
  | 2 | jump tables and statics (DI-02, DI-03); status table, `gate` and cross-check (RPT-01, AGT-06); hooks (AGT-05, DI-07); skill, context pack and the attempt wrapper (AGT-08, AGT-09, D-04, D-44); scorer (AGT-07) |
  | 3 | driver plus stand-in tests (AGT-01..04); progress.py, Pages, report, DecompHub feed and README (RPT-02..05, DI-08, DI-34, DI-37); listing drafts (DI-35, DI-36); docs and paperwork (DI-20..DI-23, DI-25..DI-31, DI-33) |
  | 4 (main checkout) | the pilot checkpoint (blocking-human: CLI upgrade, Pages source, owner starts the run), then the phase gate |

  DI-01, DI-04, DI-06, DI-07 and status.csv are hard prerequisites of the driver.
- **D-39:** DI-02 and DI-03 are implemented now; both fail closed today.
  - DI-02: pair a leading jump table's data-in-code row with its segment span, using the 05-REVIEW IN-02 switch probe as the acceptance case.
  - DI-03: pair LPUBDEF statics with their rows by name, and resolve self-EXTDEF calls to the local public.
  - The pilot keeps P16's exclusions either way. Phase 7 admits these functions.
- **D-40:** DI-24: the uncovered code counts as unmatched in the progress figures now. Rows are added when matching reaches that code. This ruling is recorded.
- **D-41:** Small rulings:
  - **DI-18:** `splice._write_atomic` becomes public `write_atomic` in a new `tools/reverseapoc/fileio.py`, re-exported from splice for one release.
  - **DI-21:**
    - ast-grep becomes "Later";
    - the GhidraMCP row becomes "Later (Phase 7 or later)";
    - design spec L76 and README L62/L139 are annotated, not rewritten;
    - `.recomp.json` notes drop "retrokit" (D-32).
  - **DI-09:**
    - no Ghidra GUI guide in Phase 6;
    - the `-zp`/`-zm`/`-fp` and 11.0a/b sweeps run only if a pilot miss needs them.
  - **DI-26, DI-27, DI-29:**
    - Claude records the owner's existing sign-offs (04-UAT A1, 05 UAT) with dates and links;
    - the owner confirms spike 005 VALIDATED with one line at the pilot checkpoint.
- **D-42:** DI-32: the installed build (`UFO2P4.EXE`/`TACP4.EXE`) stays primary. CD v1.00 is for cross-reference only. OpenApoc offsets are re-located by signature when Phase 7 needs them. Twin matching of CD v1.00 is revisited after Phase 7. This ruling is recorded in PROJECT.md Key Decisions.
- **D-43:** DI-33: **the owner allows Claude one recorded edit** of the `config/watcom.toml` notes on **lines 37 and 106**. Both say "the real LE compiler" and should say LX. Line 106 was added after research found the same stale note there (D-47). The conditions:
  - the edit changes only those two comment words or lines;
  - it is made before the always-on hooks land;
  - the commit message quotes the owner's authorization of 2026-10-24;
  - the planner first confirms that no gate or test hashes the file's bytes (`tests/test_compiler_real.py:85` reads its keys, not its hash).

  CLAUDE.md's "never modify the hash manifests to make a check pass" is not engaged: this is a comment fix the owner authorized, not a change to make a check pass.

### Owner rulings after research (2026-10-24)

These settle the R1-R7 findings in `06-RESEARCH.md` ("Research findings that touch locked decisions"). Where this section disagrees with RESEARCH.md, this section wins. RESEARCH.md's "MCP stdio server" section and its MCP code example are **superseded**: no MCP server is built.

- **D-44:** **No MCP server** (owner reversal of the discussion's choice on question 1.4).
  - The agent runs `check`, `asm` and `context` as direct CLI calls through one host-side attempt wrapper. Example shape: `uv run reverseapoc attempt check|asm|context ...`; the planner chooses the final verb name.
  - The wrapper reaches the container for `check` through `docker compose run --rm build ...`. It reads the claimed EXE, unit and function from the driver's environment, never from agent arguments, so the agent cannot point it at another unit, `--cflags` or `--watcom-dir`. It may pass `--sweep`.
  - Bash is pre-approved only for that wrapper in `--allowedTools`. The matching-session hook denies every Bash command whose argv is not exactly a wrapper invocation, and every command that contains `;`, `&`, `|`, `<`, `>`, `` ` ``, `$(`, a newline or any other shell metacharacter.
  - `--strict-mcp-config` stays with no server listed, so `-p` sessions do not connect to `.mcp.json`'s Tavily or the owner's user-scope `discord-user` server (R1).
  - The stdio MCP server is recorded as a Deferred Idea, revisited if Bash allowlisting proves leaky.
- **D-45:** R2: the session gets `--tools "Read,Edit,Write,Glob,Grep,Bash"`, so no other built-in tool exists. `--allowedTools` restricts Bash to the wrapper (D-06). dontAsk mode may still run read-only shell commands by itself, so the hook's deny (D-44) is the binding rule.
- **D-46:** R3: the always-on hook exempts exactly one path from its `build/` block: the path in env `REVERSEAPOC_ATTEMPT_NOTES`, which the driver sets. It must resolve under `build/driver/` and end in `notes.md`. Nothing else under `build/` becomes writable.
- **D-47:** R4: the one-time `config/watcom.toml` edit covers line 106 as well as line 37 (D-43). Research confirmed that no test or gate hashes the file's bytes.
- **D-48:** R5: the driver takes `--max-sessions` (default 30, the night cap) and `--target-matched` (default 10). The pilot runs with `--max-sessions 40 --target-matched 10` (D-37 ceiling).
- **D-49:** R6: keep D-28's single combined report with categories `ufo2p`/`tacp`. Record in docs the risk that objdiff's `Report::split()` treats dot-free category ids as versions, which recomp.fyi might copy. recomp.fyi's ingestion is private and cannot be tested.
- **D-50:** R7: bytes inside unit spans that belong to no functions.csv row (25,691 in UFO2P and 35,241 in TACP, mostly alignment filler) appear as their own **"uncovered"** segment in progress.json, the treemap and the report.
  - They are counted in the denominator, and the page notes that most of them are filler (refines D-26/D-40).
  - The 3-byte UFO2P tail past 0x000CFADA lies outside every unit span. It is recorded as not counted.
  - Attributing the filler is left to a later phase.

### Claude's Discretion
- The internal module layout of the driver, the attempt wrapper and progress.py within `tools/reverseapoc/`; verb names other than `drive` and `gate`; the treemap layout algorithm (squarified or slice-and-dice, stdlib); the exact /goal prompt wording; the look-alike similarity metric.
- How the stand-in `claude` (a fake CLI emitting recorded stream-json) is built for the driver tests.
- The attempt wrapper's verb name and argument shape (D-44), provided `check` itself always runs in the container and the claimed target comes from the driver's environment.

</decisions>

<deferred_inventory>
## Deferred inventory carried into Phase 6

Every row ends Phase 6 closed by a commit, or carried forward under an owner ruling recorded in STATE.md. The source copy with full detail is `.superpowers/sdd/let-s-work-on-phase-effervescent-nebula/deferred-inventory.md` (gitignored, on the owner's machine).

| ID | Item | Source |
|---|---|---|
| DI-01 | 999.3: `asm` writes names SymbolTable.ambiguous lists (`_Alphabet`: UFO2P 0x000C06FA/0x000C92CD, TACP 0x000C2826/0x000CD0AF) as `<kind>_<start>.s`, so there is one listing per functions.csv row; with a test | ROADMAP.md 999.3; asm.py:245-248 |
| DI-02 | 05 IN-02: `check` refuses every jump-table function; pair the leading table row with its span | 05-REVIEW.md:202-216 |
| DI-03 | `static` functions cannot pass `check` | docs/learnings.md:16; 05-REVIEW.md:192 |
| DI-04 | 05 minors 12a-c: duplicate own publics; tests for a target at a public's end and a wrong target inside the function | 05-REVIEW.md:259-299 |
| DI-05 | 05 minor 15: backslash continuation fails open in the D-12 parser | 05-REVIEW.md:259-299 |
| DI-06 | WR-01 hardening: `land` provenance stamp and stale-object refusal; `check --src OTHER` writes ninja's object paths; `--config DIR` regeneration still uses the repo's targets.toml | 05-REVIEW-FIX.md:54-56 |
| DI-07 | Hooks also guard the cc wrapper and config/cflags.txt | 04-CONTEXT.md deferred |
| DI-08 | README.md progress placeholder "coming in Phase 6" | README.md:8-14 |
| DI-09 | Phase 5 context deferrals (spike; GhidraMCP; sweeps; GUI guide), ruled in D-41 | 05-CONTEXT.md:221-232 |
| DI-10 | Phase 6 builder decisions (scorer, hooks, progress names, driver), decided in D-05..D-29 | PROJECT.md:92,94 |
| DI-11 | 999.1: toolchain.md cc.log bullet: `--log` must name a file (`.`/`/` refused before compile; an existing folder compiles then fails: 'Is a directory' / 'Permission denied'); `_append_log` device branch covers directories | ROADMAP.md 999.1; 04-UAT.md:85-89 |
| DI-12..DI-17 | 04 IN-08..IN-13: `--log <dir>` leaves the object; unwritable log dir fails a good compile; `_reap` kills only the Python `cc` and `cc_root` fails on a leftover dir; root-run test hides its regression; `_append_log` docstring wording; a CLI `assert not obj.exists()` that cannot fail | 04-REVIEW-DISPOSITION.md:87-92 |
| DI-18 | 04 IN-04: `splice._write_atomic` imported by 7 modules (D-41) | 04-REVIEW-DISPOSITION.md:101 |
| DI-19 | Remaining 05 deferred minors (rows 1-5, 7a-d, 8, 9a-d, 10a-d, 11, 13a-b, 14, 16a-b, 17a-c, 18a-c, 19a-b) | 05-REVIEW.md:259-299 |
| DI-20 | Stale doc text: matching.md:57,63; learnings.md:86; toolchain.md:374 ("candidate pending Phase 5 matches") and :166 ("-s: consistent" → tied) | as listed |
| DI-21 | Owner-left doc items: tools.md:53 ast-grep; design spec :76; README :62/:139; tools.md:16 GhidraMCP (D-41) | 05-15-SUMMARY.md:168-173 |
| DI-22 | Phase 1 carry-overs: toolchain.md:13 SMKP entry point obj1:0x6CB0 unchecked; .dockerignore lacks `*.IMG`, `*.CUE`, `*.mdf` | 01-VERIFICATION.md:127-128 |
| DI-23 | 04 security observations: T-04-15/16 real proofs only for 10.6/11.0; T-04-17 a failing assert prints probe bytes; T-04-36 doc claims resting on scratch checks | 04-SECURITY.md:122 |
| DI-24 | Uncovered code (TACP ~0x29D4D..0x31040; UFO2P 3-byte tail 0x000CFADA) (D-40) | 05-VERIFICATION.md:92-93 |
| DI-25 | Compiler candidates unseparated: log evidence from each pilot match; fix stale wording | toolchain.md:150-166,374 |
| DI-26 | T-04-13 owner sign-off recorded in 04-UAT but 04-SECURITY still says pending | 04-SECURITY.md:57,109-111 |
| DI-27 | 04-VALIDATION sign-off boxes unticked / "Approval: pending" vs frontmatter | 04-VALIDATION.md:95-102 |
| DI-28 | 05-VERIFICATION body says human_needed, frontmatter passed | 05-VERIFICATION.md:45 |
| DI-29 | Spike 005 VALIDATED owner sign-off not recorded | 05-VALIDATION.md:82-84 |
| DI-30 | STATE.md:112 duplicate RESOLVED text; Deferred Items table says none | STATE.md |
| DI-31 | 999.2: reword Phase 7 SC4 (DEC-04) so readlint also rejects `func_XXXXXXXX`/`D_XXXXXXXX` in matched units (ROADMAP edit now; readlint stays Phase 7) | ROADMAP.md 999.2 |
| DI-32 | Primary build ruling (D-42) | PROJECT.md:84 |
| DI-33 | config/watcom.toml:37 "LE" → "LX" (D-43) | config/watcom.toml:37 |
| DI-34 | DecompHub feed, verification file, CI POST (D-29..D-31) | owner 2026-10-24 |
| DI-35 | Awesome-list PR drafts (D-33) | owner 2026-10-24 |
| DI-36 | decomp.me msdos preset draft (D-33) | owner 2026-10-24 |
| DI-37 | .recomp.json update (D-32) | owner 2026-10-24 |

</deferred_inventory>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and gates
- `.planning/ROADMAP.md` § Phase 6 (and § Backlog 999.1-999.3): goal, success criteria, spike
- `.planning/REQUIREMENTS.md`: RPT-01..05, AGT-01..11
- `docs/workflow.md`: the per-function loop (L11-53), the guardrail table (L41-53), the Phase 6 roadmap row (L92)
- `docs/ceremonies.md`: what review passes may touch (matched C: comments, names and whitespace only)
- `CLAUDE.md` and `.claude/rules/src.md`, `.claude/rules/tools.md`, `.claude/rules/workflow.md`: the hard rules

### Research and evidence behind these decisions
- `.superpowers/sdd/let-s-work-on-phase-effervescent-nebula/discuss-brief.md`: the scouting brief with every checked fact and source (gitignored, on the owner's machine)
- `docs/research/notes-decompwtf-rea-ghidra-ida.md`: decomp.wtf fork mode, `_CHEAT` (~L258), what the hybrid buys (L294-320)
- `docs/research/notes-progress-reporting-recompfyi.md`: recomp.fyi, objdiff report shape (L62), artifact naming (L106), self-hosted pipeline (L171)
- `docs/research/` automation-loop notes (Lewis, Macabeus): attempt caps, look-alikes, the opus-vs-sonnet evidence
- `docs/superpowers/specs/2026-10-19-reverseapoc-design.md` L65, L100-102: the agent layer and the open builder questions
- `docs/tools.md` rows: decomp.wtf L13, GhidraMCP L16, Nigel L27, /goal L29, recomp.fyi L63, AnyPS5 L66
- `docs/legal.md`: generated files stay local; AI use; never vendor decomp.wtf (L26); listings honest about AI (L55)

### Toolchain and matching rules
- `docs/matching.md` (relocation rules L59-68), `docs/coding-style.md` (pragma L22), `docs/toolchain.md`, `docs/learnings.md`
- `include/common.h` L19: the `INCLUDE_ASM` stub (D-12 of Phase 5)

### Prior phase decisions
- `.planning/phases/05-split-and-first-matches/05-CONTEXT.md`: D-02 (spike verdict scale), D-10 (no status in functions.csv), D-12 (stub), D-15 (P16 scorer), D-18 (cflags owner-only)
- `.planning/phases/05-split-and-first-matches/05-REVIEW.md` L186-299 and `05-REVIEW-FIX.md` L54-56: DI-02..DI-06, DI-19
- `.planning/phases/04-compiler-identification/04-REVIEW-DISPOSITION.md` L87-101: DI-12..DI-18

### External specs
- recomp.fyi spec and schema: `https://recomp.fyi/spec`, `https://recomp.fyi/schema/v1.json`, `https://recomp.fyi/add`
- DecompHub progress-v1: `https://decomphub.com/progress`, `https://decomphub.com/schemas/progress-v1.json`
- objdiff report shape: objdiff `report.proto` (encounter/objdiff)
- Claude Code headless and CLI reference (`--output-format stream-json`, `--max-turns`, `--setting-sources`, `--settings`, `--permission-mode dontAsk`, `api_retry` events), hooks reference (`permissionDecision`, merge across sources), `/goal`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tools/reverseapoc/cli.py`: `build_parser` L1074-1136 registers verbs through `_add_*_command(sub)`; `_ERRORS` L1139. New verbs (`gate`, `drive`, the attempt wrapper, `progress`) follow this pattern.
- `tools/reverseapoc/score.py`: `assess` L287, `ScoreReport` L334, weights L48-54, P16 filter L226-258. The driver's scorer wraps it with status awareness.
- `tools/reverseapoc/check.py`:
  - `check_unit` L845, `FunctionCheck` L544, `CheckResult.to_json` L660, `land_all` L789, `_land_exe`/`ExeLand.ok` L753-821;
  - `source_marks` L351-371 (D-22's drift test);
  - exit codes 0/1/2 (`EXIT_TOOL`=2, L83).

  `gate` wraps `check_unit`.
- `tools/reverseapoc/asm.py`: `write_listings` L265. The pack reads the listings; DI-01 is at L245-248.
- `tools/reverseapoc/ghidra.py`: `ghidra-export --drafts` (L31-38, L313-325) writes `asm/<exe>/ghidra/func_X.c`.
- `tools/reverseapoc/symbols.py`: Watcom linker names `func_XXXXXXXX_` (L9).
- `configure.py`:
  - the build.ninja rules (L72-113) and the `verify` phony (L484);
  - `objdiff.json` already carries `progress_categories` (ufo2p, tacp);
  - `check_unit_source` L315 refuses a function both defined and marked.
- `tests/conftest.py`: `ORIG_DIR` and skip helpers (`requires_objdiff`, `requires_runner`, `requires_clang`, `requires_ghidra`, ...).
- Phase 5 match commits 5ab2e79 and a463163 (`feat(05-18)`, `feat(05-19)`): the shape of a match.

### Established Patterns
- Stdlib-only Python, tested with pytest; real-file tests skip unless `orig/` exists. CI has no game files.
- Generated, game-derived output (asm/, build/) is gitignored and never committed. Committed data is free of bytes (CSV of addresses, names, statuses).
- Host and container suites never run at the same time (shared build/test-cc).
- GSD commit hook accepts only the 10 Conventional Commits types.
- `.githooks/commit-msg` adds Co-Authored-By only when `CLAUDECODE` is set.
- `tests/test_hygiene.py:136` bans the phrase "Ghidra and decomp.wtf run in WSL2" in live docs.

### Integration Points
- `.claude/settings.json` (today only `enabledPlugins`): gains the always-on hook block (D-16).
- `config/driver/claude-settings.json` (new): the matching-session hooks and the plugin overrides (no MCP server, D-44).
- `.github/workflows/ci.yml`: the drift test runs here. The new `.github/workflows/pages.yml` sits next to it.
- `docker/compose.yaml` (`build` service): every `check`/`gate` the driver runs.
- `README.md` Progress section, `.recomp.json`, the repo root `decomphub.progress.json`.

</code_context>

<specifics>
## Specific Ideas

- The README already publishes the Pages URLs for `progress-shield.json`, `progress.svg` and `progress.json`. Keep those names (D-26).
- recomp.fyi shows a percentage only from a default-branch artifact. One combined `X-COM_Apocalypse_DOS_report` avoids its several-versions rule (D-28).
- The score today ranks the two already-matched functions first, and UFO2P 0x0008A0E0..0x0008A1C0 holds eight identical-feature 27-byte functions (D-09, D-10).
- The owner wants the `watcom-decomp` skill written with `superpowers:writing-skills` (D-19).
- Model pinned to the latest Opus: `claude-opus-5-5` (D-35).

</specifics>

<deferred>
## Deferred Ideas

- SQLite claims with a TTL for parallel agents (Phase 7, DEC-06), and re-evaluating decomp.wtf for that role (D-03).
- A stdlib stdio MCP server exposing check/asm/context. It was chosen in the discussion, then dropped by the owner after research (D-44). Revisit it if Bash allowlisting proves leaky.
- Attributing the uncovered filler bytes (D-50), for example with a committed padding list.
- Scorer tuning: pure leaf functions, new features, dropping `WEIGHT_NO_FRAME` (Phase 7) (D-09).
- GhidraMCP as a live agent tool (Later) (D-14).
- A dedicated second clone for parallel runs (Phase 7) (D-34).
- Twin matching of CD v1.00 (after Phase 7) (D-42).
- Reddit, GBAtemp and decompals posts (later, at the owner's call).
- readlint itself, with the 999.2 rule (Phase 7, DEC-04).

</deferred>

---

*Phase: 06-reporting-and-agent-pilot*
*Context gathered: 2026-10-24*
