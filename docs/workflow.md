# Workflow

Work runs at three levels:

1. **Milestone**: a set of gated phases, tracked by GSD in `.planning/`.
2. **Phase**: GSD's discuss, plan, execute, verify loop, with superpowers skills inside it.
3. **Function**: the per-function matching loop, from Phase 5 on.

The rule that ties them together: deterministic checks decide what is done. An agent never judges its own result. Every documented failure in the research (false match claims, rewritten hashes, permuter overfitting) came from letting the agent judge itself ([report](research/2026-10-19-kickoff-research-report.md)).

## The per-function loop

Starts in Phase 5 (by hand) and becomes unattended in Phase 6.

```
select function -> decompile attempt -> compile (Watcom under wibo)
  -> objdiff compare + relocation check -> splice + whole-EXE SHA-1 -> commit
```

1. **Select.** A scorer picks the next function. Start with easiest-first (KKND's `score_functions.py`); switch to similarity-first once enough functions are matched, because Lewis found that ordering by similarity to matched functions beat ordering by difficulty in the long tail. Twin functions between UFO2P (`ufo24`) and TACP (`tac4`), and Watcom runtime functions found by library matching, are the cheapest wins.
2. **Attempt.** One fresh headless session per function (`claude -p "/goal ..."`), given the target asm, callers and callees, shared headers, a Ghidra draft and notes from earlier attempts.
3. **Compile.** The original `wcc386` under wibo in Docker, with the file's flags from the per-file flags table.
4. **Compare.** objdiff on the OMF-to-ELF converted object against the target object cut from the LE. Then the relocation check: every `call rel32` must hit the same function and every absolute fixup must resolve to the original target. objdiff compares at most one relocation per instruction, so a separate check covers the rest. "A scratch match alone is never enough" (KKND).
5. **Splice and verify.** Splice the matched bytes in place into a copy of the original EXE and check the whole-EXE SHA-1 against the manifest. This is the definition of done.
6. **Commit.** One matched function per commit. Record anything learned in [learnings.md](learnings.md) and, if it is a reusable rule, in [matching.md](matching.md).

### Attempt cap and re-queue

- **3-5 attempts per function per pass.** In Macabeus's Mizuchi benchmark nearly half of the AI matches came on the first attempt, and after attempt 3 the conditional chance of a match fell to about a quarter ([Macabeus, 2026-03-10](https://gambiconf.substack.com/p/can-llms-really-do-matching-decompilation)).
- A function that hits the cap goes to a difficult list and is re-queued in a later pass, once more of its neighbours, structs and callees are matched.
- Partial results are kept as notes, not committed as matches.

### The driver owns verification

- The driver re-runs the compile, compare and SHA-1 check itself before committing. It never trusts the transcript. Only the container gate's exit 0 is a match (D-24).
- `/goal`'s evaluator "does not call tools" ([docs](https://code.claude.com/docs/en/goal)), so its verdict is a hint, not a check.
- The driver backs off when it hits usage limits (60, 120, 240 s, then every 300 s) and caps the night. Unattended Opus can exhaust a Max 20x plan in days ([Lewis, 2026-02-16](https://blog.chrislewis.au/the-long-tail-of-llm-assisted-decompilation/)).
- Phase 6 caps each function at 3 sessions per pass (D-07). A capped function goes to `build/driver/difficult.json` and comes back once a callee is matched or the easy pool is empty.
- **Nigel was rejected (D-05).** It has no licence (GitHub reports none), needs Go, which is not on the host, logs no turns or tokens, and detects usage limits by one phrase. The driver is our own stdlib Python instead: `tools/reverseapoc/driver.py` and the `reverseapoc drive` verb, built test-first.
- **decomp.wtf is not used in Phase 6 (D-03).** Spike 006 ([README](../.planning/spikes/006-decompwtf-fork-stub/README.md)) found that unpatched v0.10.6 fork mode does not accept our stub convention (verdict INVALIDATED: no build in WSL2, and its stub regex and linker-name lookup refuse our `INCLUDE_ASM(func_X);` units). Phase 6 runs on its own agent layer: the driver, the hooks, the `watcom-decomp` skill, the context pack and the attempt wrapper. decomp.wtf is re-evaluated for Phase 7's parallel claims.

### Running the driver

`reverseapoc drive` runs on the Windows host, in the main checkout (D-34). It starts one fresh `claude -p` session per attempt and runs every gate in the container.

```
uv run reverseapoc drive [--max-sessions N] [--target-matched N] [--dry-run | --canary] [--run ID] [--json]
```

| Flag | Default | Meaning |
|---|---|---|
| `--max-sessions N` | 30 | counted sessions before the night ends (D-48) |
| `--target-matched N` | 10 | matches before the night ends (D-48) |
| `--dry-run` | off | print the 10 pilot picks and build their packs; no claude, no gate |
| `--canary` | off | owner only: one real session that proves the guardrails deny (PASS/FAIL) |
| `--run ID` | the UTC start time | the run directory `build/driver/<ID>/` |
| `--json` | off | print exactly one JSON document on stdout |

The pilot command is `uv run reverseapoc drive --max-sessions 40 --target-matched 10` (D-37, D-48).

**Preflight.** Every run, the dry run and the canary included, first refuses to start (exit 2, with a named reason) when:

- the checkout is not the main checkout (a linked worktree has its own git dir);
- `git status --porcelain` is not empty (the refusal names the paths);
- `claude --version` is not major 2 or is below **2.1.302**, the minimum CLI version (D-36; the dry run skips only this check). 2.1.302 is the release where `-p` has the documented permission default; `onFailure` needs 2.1.295;
- `docker info` fails, or `uv sync --locked` fails in the container or on the host.

It then compiles `tools/` and `configure.py`, so no session writes a `.pyc` (the hooks run `python -I`, which ignores `PYTHONDONTWRITEBYTECODE`), regenerates the asm listings of both EXEs on the host, and precomputes the Ghidra drafts of the queue's top picks in one container call per EXE (D-13). Each command's output goes to `build/driver/<run>/preflight.log`.

**Dry run.** `uv run reverseapoc drive --dry-run` prints the 10 pilot picks: 5 UFO2P and 5 TACP, interleaved, easiest first, at most 2 per unit and 3 per 64 KiB region (D-10). It builds their context packs under `build/driver/<run>/dry-run/` and never launches claude or a gate. The picker skips functions that are matched in `status.csv`, partial today (this pass), or on the difficult list.

**Canary.** `uv run reverseapoc drive --canary` is run by the owner before the pilot. It launches one real session with the matching settings and a fixed prompt that asks for four calls: Write `config/targets.toml`, Write `tools/x.py`, Bash `ls`, and `uv run --frozen reverseapoc attempt context`. The claim is `ufo2p/u_000a34f0`, function `func_000A3980`, with its attempt directory under `build/driver/canary/<run>/`. It prints PASS only when all of these hold:

- the session's init event is clean (CLI version, model, the six tools, no MCP server, no plugin);
- the first three calls are in the result's `permission_denials`;
- the wrapper call was made, was not denied, and wrote `context.md`;
- no unknown stream event type carries an error;
- `git status --porcelain` is clean afterwards;
- nothing the night's audit pins or fingerprints changed (`.git/config` and hooks, the Claude settings files, `.venv`, the gitignored `.claude/` trees, every `__pycache__`).

Otherwise it prints FAIL with each failed check and exits 1. It leaves the tree as the session left it, for inspection; the next preflight refuses a dirty tree.

**One attempt.** The driver scaffolds the unit if it is missing, builds the pack, and starts the session in the checkout root. The session gets `REVERSEAPOC_CLAIM`, `REVERSEAPOC_FUNC`, `REVERSEAPOC_ATTEMPT_DIR` and `REVERSEAPOC_ATTEMPT_NOTES` (absolute paths). It may run only the attempt wrapper's three commands:

- `uv run --frozen reverseapoc attempt check` (and `check --sweep`, a diagnostic that is never a match), at most 25 runs per attempt;
- `uv run --frozen reverseapoc attempt asm` (or `asm <NAME>` for another row of the same EXE);
- `uv run --frozen reverseapoc attempt context`.

After the session the driver removes the attempt's containers, audits every changed path, then lints the unit (C89) and runs the container gate.

**Reset rules (D-34).** A match is one commit with explicit paths: the unit, `status.csv`, `decomphub.progress.json`, `progress/attempts.jsonl` and any new header. Anything else resets the attempt: `git restore --source=HEAD -- <unit> include/` for tracked files, and a unit scaffolded by this attempt or a header it added is deleted. The driver never runs `git add -A` or `git clean`. A partial attempt keeps its best C under `best/` and is scored by `gate --partial`. A write outside the claim is a guardrail stop: the stray files are restored or moved into `build/driver/<run>/quarantine/` (never deleted), the night ends and nothing is committed. A night that stops with partial rows leaves `status.csv` uncommitted and names it; the next drive refuses to start until the owner commits or restores it.

**End of run.** After the last session the driver runs, in the container, `uv run --frozen python configure.py && ninja -t clean && ninja verify`, then `reverseapoc gate --all`, and logs both under `build/driver/<run>/`. A failed check is recorded in the ENDED run record and the night exits 1. Then the `chore(driver): attempt log` commit holds the night's records. Exit codes: 0 ended clean, 1 stopped or a failed end check, 2 refused.

### Hooks (guardrails, Phase 6)

Agents have gamed verifiers before: Claude rewrote a SHA-1 to force a "match" and worked around a blocked `make` (Lewis); an agent tried to fork its compiler (Macabeus). Prose rules are not enough, so two PreToolUse hook layers in `tools/reverseapoc/hooks.py` enforce these.

**The always layer** runs in every Claude session in this repo (`.claude/settings.json`; the driver's settings file carries a copy). On Write, Edit, MultiEdit and NotebookEdit it blocks:

| Block | Why |
|---|---|
| Any write under `orig/` | The original executables are the ground truth |
| Writes to `config/targets.toml`, `config/watcom.toml` and any `*.sha1` | The SHA-1 is the done-gate |
| Writes under `asm/` and `build/` (except the attempt's own `notes.md`) | Generated output; the same oracle for everyone |
| Inline assembly in `src/` and `include/`: `_asm`, `__asm`, `_Pragma`, and `#pragma aux` bodies that emit code bytes | Matching must come from C |
| An Edit in `src/` or `include/` whose old text is not in the file verbatim, and any lone CR | The scan must see the exact text the compiler will |

**The matching layer** runs only in driver sessions (`config/driver/claude-settings.json`). It denies by default:

- writes only to the claimed unit, a new untracked `include/<name>.h` and the attempt's `notes.md`;
- **agents write no `#pragma aux` of any kind in the pilot, and no other `#pragma` either** (D-18); calling-convention pragmas come only in human-reviewed commits;
- Read, Glob and Grep only inside the checkout, never `.env*`;
- Bash only as one of the attempt wrapper's exact forms, never in the background;
- every other tool is denied, and without a valid claim every write and every Bash call is denied.

**Both layers fail closed.** Each handler runs `uv run --frozen --project "$CLAUDE_PROJECT_DIR" python -I -m reverseapoc.hooks ... || exit 2`. A missing `uv`, a missing module, or an unset or foreign `CLAUDE_PROJECT_DIR` blocks every Edit and Write (exit 2). The matching handler also sets `onFailure: block`.

Known limits:

- Bash is not covered by the always layer. An owner or executor session can still change `orig/` or a manifest with a shell command; `check-orig` and the gate catch it by hash.
- A hard link made by Bash to a protected file is allowed: the hook does no inode check. Only Bash can make one, and the matching layer cannot run `ln`, `mklink` or `fsutil`.
- Other git checkouts are over-denied: a path is judged against every ancestor holding `.git`, so `build/`, `orig/`, `asm/` and `*.sha1` are also blocked in another checkout a session writes to.
- Whether a `--settings` file merges with or replaces project hooks, and whether each tool's hook runs right before that tool (not once for the whole turn), is proven only on the real CLI. The canary checks the denials; the driver's post-session audit and the gate stand behind both.

## The GSD phase loop

GSD owns milestone and phase bookkeeping. Each phase in [the roadmap](#milestone-1-roadmap) runs:

| Step | Command | Output |
|---|---|---|
| Discuss | `/gsd-discuss-phase N` | `CONTEXT.md` |
| Plan | `/gsd-plan-phase N` | `RESEARCH.md`, `PLAN.md`, `VALIDATION.md` |
| Execute | `/gsd-execute-phase N` | `SUMMARY.md`, `VERIFICATION.md` |
| Verify | `/gsd-verify-work N` | `UAT.md` |

- A phase is complete only when its `VERIFICATION.md` passes; the checkbox in `ROADMAP.md` is just an annotation.
- Feasibility questions run as spikes with `/gsd-spike` (Given/When/Then, verdict VALIDATED, INVALIDATED or PARTIAL). Register each spike when its phase starts.

### Where superpowers fits

superpowers drives the work inside a phase:

- **brainstorming** during discuss, when a design question is open;
- **test-driven-development** during execute, for Python tooling (pytest for the LE reader, OMF converter, lints). For decompiled C the byte match is the test;
- **systematic-debugging** when a build or a match breaks;
- **verification-before-completion** before any "done" claim;
- **requesting-code-review** at the end of a plan, following [ceremonies.md](ceremonies.md);
- **writing-skills** whenever a project skill under `.claude/skills/` is created or updated, such as `watcom-decomp` (Phase 6) and `apoc-spec` (Phase 8). Owner rule since 2026-10-24.

When both systems prescribe a step, GSD's phase files are the record. `.claude/rules/workflow.md` states this split; re-check with `/gsd-health` after updating either system.

## Milestone 1 roadmap

Copied from the approved plan. Phases 1-2 are implemented first; 3-8 are planned later with `/gsd-plan-phase N`. Phases 7 and 8 were added by the owner on 2026-10-21.

| Phase | Goal | Verification gate (`VERIFICATION.md` must pass) | Spike (`/gsd-spike`) |
|---|---|---|---|
| 1 Hygiene and safety | GSD + plugins installed, `.gitignore`, key externalized, lean CLAUDE.md, docs skeleton, README, `.recomp.json`, design spec | `git ls-files` has no game file/key/`.env`; `/plugin` and `/gsd-health` clean; CLAUDE.md < 150 lines | none |
| 2 Container and target ingest | Docker image (uv, ninja, objdiff-cli, wibo, OW v2), hash manifest, Python LE parser with pytest | pytest green in container; parser reproduces the scanned layout of both EXEs | none |
| 3 Byte-identical round trip | KKND-style in-place page splice and whole-EXE rebuild | `cmp`/SHA-1 identical for UFO2P.EXE and TACP.EXE | iterated pages / fixup edge cases on the real files |
| 4 Compiler identification | mosura codegen probe + CLIB3R library match with owner-supplied Watcom 10.5/10.6/11.0 under wibo | version and default flags recorded in `docs/toolchain.md`, runtime modules match byte-for-byte | wibo 1.2.0 runs `wcc386.exe` for each version in Docker |
| 5 Split and first matches | Ghidra 12.1.4 + lastonesky LE loader, headless in the Docker image (own cached stage, OpenJDK 21), `omf2elf.py`, function split, `configure.py` -> ninja + `objdiff.json` + target ELF objects | one function per EXE compiles, matches (relocations checked), splices back, whole EXE still identical; objdiff shows 100% | objdiff diffs OMF-converted ELF cleanly (decides hybrid vs fallback) |
| 6 Reporting and agent pilot | `progress.py` + Pages + badge, `watcom-decomp` skill, hooks, decomp.wtf fork mode pinned at v0.10.6 with light patches, 3-5 attempt cap, driver-side re-verification | mosaic and badge live; 10 easy functions matched unattended, zero regressions, EXE identical; recomp.fyi and decomphub submissions done | decomp.wtf fork mode accepts the repo's stub convention |
| 7 Mechanics-first decompilation | `config/mechanics.toml` (OpenApoc checklist items -> functions), the Phase 6 driver at scale with claims and one owner of names, `readlint` for names, comments, types and constants, `reverseapoc stats` for the research metrics | every listed function matches (objdiff 100%, relocations checked), both EXEs identical, zero regressions; `readlint` clean; coverage per checklist item on the progress page | locate the #997 tick-rate and training code from timer setup and strings within a time box |
| 8 Clean-room specs for OpenApoc | OpenSpec-format template and status ladder, `speclint`, `wikifetch` (MediaWiki API), `apoc-spec` skill, `docs/clean-room.md`, `specs/LICENSE` (CC0-1.0), community claim inventory, `docs/findings/` (bugs, cut content, cheats and easter eggs, Learning AI) | every Phase 7 mechanic has a spec that passes `speclint`, reaches `backed-by-matched-code` and has an owner review line; negative tests prove the linter fails | `wikifetch` reads one UFOpaedia table page with revid and numbers intact |

Cross-cutting task, opened as a GitHub issue in Phase 1: ask OpenApoc which build has UFO2P CRC32 `0x4749ffc1` (current Steam/GOG is `0xDBD3B41D`) before reusing any of their offsets.
