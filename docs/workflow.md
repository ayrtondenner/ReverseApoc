# Workflow

Work runs at three levels:

1. **Milestone**: a set of gated phases, tracked by GSD in `.planning/`.
2. **Phase**: GSD's discuss, plan, execute, verify loop, with superpowers skills inside it.
3. **Function**: the per-function matching loop, from Phase 5 on.

The rule that ties them together: deterministic checks decide what is done. An agent never judges its own result. Every documented failure in the research (false match claims, rewritten hashes, permuter overfitting) came from letting the agent judge itself ([report](research/2026-10-19-kickoff-research-report.md)).

## The per-function loop

Starts in Phase 5 (by hand) and becomes unattended in Phase 6.

```mermaid
%%{init: {"flowchart": {"wrappingWidth": 260}}}%%
flowchart TD
    A["Step 1: preflight<br/>Docker, CLI checked<br/>clean git tree<br/>asm regenerated"] -->|a check fails| R["REFUSED<br/>nothing starts"]
    A -->|all checks pass| B["Step 2: pick a function<br/>easiest first<br/>Ghidra draft as hint"]
    B --> C["Step 3: context pack<br/>target asm<br/>neighbours and draft<br/>compiler rules"]
    C --> D
    subgraph S["Step 4: one Claude Code session, guardrails on"]
        D["Edit the C<br/>of its one unit file"] --> E["Step 5: attempt check<br/>up to 25 per attempt"]
        E --> F["Watcom C 10.6<br/>compile in container"]
        F --> G["objdiff score<br/>relocation check<br/>splice into EXE copy<br/>whole-EXE SHA-1"]
        G -->|not identical yet| D
    end
    G -->|session ends| H["Step 6: driver check<br/>file audit, C89 lint<br/>full gate"]
    H -->|byte-identical| M["MATCHED<br/>one commit with<br/>explicit paths"]
    H -->|not identical| P["PARTIAL<br/>best C kept as notes<br/>unit reset"]
    H -->|write outside the claim| X["Guardrail stop<br/>strays restored<br/>night ends<br/>nothing committed"]
    P -->|under 3 attempts| C
    P -->|3 attempts| L["Difficult list<br/>retried next pass"]
    classDef matched fill:#008300,stroke:#005a00,color:#ffffff
    classDef partial fill:#eda100,stroke:#a86f00,color:#0b0b0b
    classDef stop fill:#52514e,stroke:#2b2a28,color:#ffffff
    class M matched
    class P,L partial
    class R,X stop
```

The flowchart is one `reverseapoc drive` attempt as Phase 6 runs it (the same one as the README's "How an agent session matches a function"); [Running the driver](#running-the-driver) has the details.

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
- **decomp.wtf is not used in Phase 6 (D-03).** Spike 006 ([README](../.planning/spikes/006-decompwtf-fork-stub/README.md)) found that unpatched v0.10.6 fork mode does not accept our stub convention (verdict INVALIDATED: no build in WSL2, and its stub regex and linker-name lookup refuse our `INCLUDE_ASM(func_X);` units). Phase 6 runs on its own agent layer: the driver, the hooks, the `watcom-decomp` skill, the context pack and the attempt wrapper. Phase 7 does not re-evaluate decomp.wtf: spike 006 stands (owner ruling D-06, 2026-10-26). Parallel sessions run in one `reverseapoc drive` process in the main checkout, each on a private per-attempt view under `build/driver/.../view/`, with whole-unit claims and one gate lock (D-24); no second clone.

### Running the driver

`reverseapoc drive` runs on the Windows host, in the main checkout (D-34). It starts one fresh `claude -p` session per attempt and runs every gate in the container.

**What changed in Phase 7.** The Phase 6 facts below still hold unless this list says otherwise:

- **One drive per checkout (D-06).** Every `drive` (night, dry run or canary) holds `build/driver/drive.lock`, an OS lock the kernel frees when the process dies, from before its preflight to its end. A second `drive` in the same checkout refuses to run.
- **Workers on private views (D-06, D-24).** `--workers N` sessions run at once (default 3). Each session edits a private copy of its unit in a per-attempt view, `build/driver/<run>/<exe>/<func>/attempt-<n>/view/`: HEAD's `src/`, `include/` and `config/`, taken with `git archive` at launch. It never edits `src/` itself, so sessions cannot see each other's half-edited C.
- **Whole-unit claims and stale-claim recovery (D-06).** Each attempt claims its whole unit with one atomic file, `build/driver/claims/<exe>__<unit>.json`, and frees it after its landing decision. A pick whose unit another pass holds waits and is handed out later. Since `drive.lock` is held, any claim left by another run is stale: the night moves it to `build/driver/<run>/stale-claims/` and names it in the STARTED record.
- **One landing at a time.** One gate lock serialises every shared write: the copy of a view unit into `src/`, the lint, the gate, the match commit or the reset, `gate --partial` and every record append. A gate therefore sees `src/` equal to HEAD except for the one unit it lands.
- **The shared usage-limit pause (D-07).** A session that ends on a usage limit pauses every worker: one backoff (60, 120, 240 s, then every 300 s), then exactly one probe launch. A probe that is not limited clears the pause for all workers. Each wait is a `limit` record.
- **The caps are flags (D-07, D-25).** The defaults are `--workers 3`, `--max-sessions 60`, `--target-matched` 0 (= off), `--max-budget-usd 5`, `--fable-budget-usd 12.50`, `--max-turns 40` and `--session-minutes 30` (table below). Every launched session counts toward `--max-sessions`.
- **The tier queue (D-04, D-08, D-22, D-23).** Once `config/mechanics.toml` has a signed tier whose digest still matches, the night takes its picks from the tier queue instead of the Phase 6 easiest-first pools. The order is the signed tiers in turn; within a tier, its members, callees first, then its hubs. An `asm` row is never queued. A function capped in a pass (3 sessions) goes back for its next pass the same night, with more matched callees in its pack. Passes are unlimited: only the night cap bounds a run. The queue reads the pass count from the committed `progress/attempts.jsonl`, never from `difficult.json`.
- **Opus, then Fable (D-09).** See "Model escalation" below. Before the first night that can reach a pass 3, the owner runs the Fable canary.

```
uv run reverseapoc drive [--workers N] [--max-sessions N] [--target-matched N] [--max-budget-usd USD] [--fable-budget-usd USD] [--max-turns N] [--session-minutes N] [--session matching|readability] [--dry-run | --canary [--model MODEL]] [--run ID] [--json]
```

| Flag | Default | Meaning |
|---|---|---|
| `--workers N` | 3 | sessions at once, one unit each (D-06, D-07) |
| `--max-sessions N` | 60 | sessions all workers launch before the night ends (D-07). Every launched session counts toward this cap, an aborted (transient) one included; a usage-limit relaunch keeps its slot |
| `--target-matched N` | 0 (off) | matches before the night ends |
| `--max-budget-usd USD` | 5 | per-session budget of an Opus session (`claude-opus-5-5`, passes 1 and 2 of a function, D-07) |
| `--fable-budget-usd USD` | 12.5 | per-session budget of a Fable session (`claude-fable-5-1`, pass 3 and later, D-09, D-25) |
| `--max-turns N` | 40 | turns per session (D-07) |
| `--session-minutes N` | 30 | each session's wall clock in minutes (D-07) |
| `--session KIND` | `matching` | the night's session kind (D-17, D-18): `readability` runs the readability nights below |
| `--dry-run` | off | print the 10 pilot picks and build their packs; no claude, no gate. With `--session readability`: the queued units and their readlint violation counts |
| `--canary` | off | owner only: one real session that proves the guardrails deny (PASS/FAIL) |
| `--model MODEL` | `claude-opus-5-5` | with `--canary` only: the model the canary asks for and its init check expects; `--model claude-fable-5-1` is the owner's Fable canary (D-25). The canary's init line and its JSON (`init_model`) name the model string the init event reported |
| `--run ID` | the UTC start time | the run directory `build/driver/<ID>/` |
| `--json` | off | print exactly one JSON document on stdout |

A Phase 7 night is `uv run reverseapoc drive`, with the defaults. The Phase 6 pilot was `uv run reverseapoc drive --max-sessions 40 --target-matched 10` (D-37, D-48).

**Model escalation (D-09).** A function's pass comes from the committed `progress/attempts.jsonl`. Passes 1 and 2 run on `claude-opus-5-5` with `--max-budget-usd`; pass 3 and every later pass run on `claude-fable-5-1` with `--fable-budget-usd`. Each attempt record names `model_requested` and `budget_usd` next to the init event's `model`. The init check expects the requested model, so an answer from another model stops the night (STOPPED `init`). Each match commit's `Co-Authored-By:` line names the requested model (`Claude Opus 5.5` or `Claude Fable 5.1`). The owner's Fable canary, `uv run reverseapoc drive --canary --model claude-fable-5-1 --run <fresh id>` (D-11, D-25), comes before the first Fable pass. It shows whether the CLI accepts `claude-fable-5-1` and which model id its init event reports. Run it before the first night in which a function has two capped passes in the log, because that function's next pass asks for Fable.

**Before you start** (the preflight refuses without most of these):

- Docker Desktop is running (`docker info` answers) and the image is built: `docker compose build`.
- `orig/` holds your executables: `uv run reverseapoc ingest`, then `uv run reverseapoc check-orig`.
- The Watcom trees are installed under `third_party/watcom/`: `uv run reverseapoc install-watcom` (after `fetch-watcom`), then `uv run reverseapoc check-watcom`.
- The Claude CLI is in the tested range: `claude --version` must print major 2 and at least 2.1.302 (for example `2.1.302 (Claude Code)`). Upgrade with `claude install stable` if it is older.
- The tree is clean: `git status` shows nothing, on the main checkout.

**Then, in this order, from the main checkout:**

1. `uv run reverseapoc drive --dry-run`: check the 10 picks and that it exits 0. With a signed tier they are the tier queue's first picks, each with its tier, level and pass.
2. `uv run reverseapoc drive --canary --run <fresh id>` (for example `--run canary1`, then `canary2`): repeat with a new id, after the recovery steps below, until the last line is `CANARY PASS`.
3. Before the first Fable pass: `uv run reverseapoc drive --canary --model claude-fable-5-1 --run <fresh id>`, the Fable canary, until `CANARY PASS`.
4. `uv run reverseapoc drive`: the night, with the default caps (add `--target-matched N` or a smaller `--max-sessions N` for a short one).
5. Read the results:
   - the exit code (0 ended clean, 1 stopped or a failed end check, 2 refused) and the printed summary (the last stdout line, stamped with the time the night ended);
   - `progress/attempts.jsonl`: one `attempt` record per counted session (outcome MATCHED, PARTIAL or GAVE_UP), `abort` records, and the `run` records; the last one is ENDED or STOPPED with its `reason`, `checks_failed` and `uncommitted`;
   - `config/ufo2p/status.csv` and `config/tacp/status.csv`: the matched and partial rows;
   - the commits: `git log --format='%h %s' --grep='^Matched-By: reverseapoc drive$'` lists one `feat(<exe>): match ...` commit per match; the night's last commit is `chore(driver): attempt log`;
   - `build/driver/<run>/`: transcripts, check logs, notes, `end-ninja-verify.log`, `end-gate-all.log`;
   - `uv run reverseapoc mechanics status`: the matched, partial and unmatched counts of each tier's must-match members.
6. The commits are local. Pushing `main` is the owner's step, after reading the results.

**The console.** In text mode every line `drive` prints while it runs starts with the host's local time as `[HH:MM:SS] ` (24-hour), and each long step gets its line when it starts, so the last line always says what is running and since when. Each preflight command prints as `[21:04:05] drive: $ docker info` when that command starts; its exit and output go to `preflight.log`, and the next line's time shows when it finished. Notes such as `drive: ufo2p: no Ghidra draft for ...` are stamped the same way. Each night attempt prints a line when it starts, for example `[22:10:31] drive: ufo2p func_0008A100 attempt 1/3: started`, a line before each usage-limit wait, for example `[22:11:20] drive: ufo2p func_0008A100 attempt 1/3: usage limit, next launch in 60 s`, and one with its outcome, for example `[22:19:02] drive: ufo2p func_0008A100 attempt 1/3: PARTIAL after 511.2 s`. The outcome is MATCHED, PARTIAL, GAVE_UP or ABORTED (transient); the seconds run from the start line to the outcome, relaunches, usage-limit waits and the gate included, so they can exceed the record's `seconds`. An attempt that stops the night prints no outcome line: the summary says why. Before each end-of-run check the night prints `[03:01:10] drive: end of run: ninja verify: started` and then `drive: end of run: gate --all: started`. The canary prints `drive: canary: ufo2p func_000A3980 session: started (timeout 1200 s)` before its session. The summary itself is stamped too, for example `[03:12:44] ENDED max sessions: 40 sessions, 3 matched`, and so is a refusal, for example `[21:04:05] reverseapoc drive: refused (dirty): ...`. Progress lines go to stderr and the summary to stdout. The dry run's pick lines, the canary's `PASS:` and `FAIL:` lines and its last line carry no time, so the last line is still exactly `CANARY PASS`. With `--json` no stamped line is printed: stdout is the one JSON document and stderr stays quiet. `preflight.log`, the `end-*.log` files, `progress/attempts.jsonl` and the transcripts carry no console time.

**Preflight.** Every run, the dry run and the canary included, first checks the checkout, then runs a fixed list of commands. Nothing is started unless all of it passes. It compiles `tools/` and `configure.py`, so no session writes a `.pyc` (the hooks run `python -I`, which ignores `PYTHONDONTWRITEBYTECODE`), and regenerates the asm listings of both EXEs on the host. The dry run and the night (not the canary) then load both EXEs and precompute the Ghidra drafts of their picks in one container call per EXE (`ghidra-export EXE --json --drafts ...`, D-13). Each command's output goes to `build/driver/<run>/preflight.log`.

Any failure before the night starts is a refusal: exit 2, a reason, a detail, and with `--json` exactly one document `{"event": "REFUSED", "reason": ..., "detail": ...}`. The reasons:

| Reason | When |
|---|---|
| `run id` | `--run ID` is not `[A-Za-z0-9_.-]+`, or a canary with this ID already ran (its attempt directory exists) |
| `drive lock` | another `reverseapoc drive` holds `build/driver/drive.lock` in this checkout, or the lock cannot be opened (D-06) |
| `claims` | a stale claim under `build/driver/claims/` cannot be moved to `build/driver/<run>/stale-claims/` |
| `worktree` | not the main checkout (a linked worktree has its own git dir) |
| `dirty` | `git status --porcelain` is not empty; the detail names the paths |
| `cli version` | `claude --version` fails, cannot be read, is not major 2, or is below **2.1.302**, the minimum CLI version (D-36; the dry run skips only this check). 2.1.302 is the release where `-p` has the documented permission default; `onFailure` needs 2.1.295 |
| `docker` | `docker info` fails |
| `container sync` / `host sync` | `uv sync --locked` fails in the container / on the host |
| `compile` | `compileall` of `tools/` and `configure.py` fails |
| `asm` | the asm listings of an EXE cannot be written |
| `world` | an EXE cannot be loaded (orig/, a config CSV) |
| `picks` | a status table or `build/driver/difficult.json` cannot be read, or the pilot cannot be filled with 5 + 5 |
| `drafts` | `ghidra-export --drafts` fails. Exit 1 is accepted only with a JSON document that names the missing drafts (a pack works without a draft); every other failure refuses |
| `pack` | the dry run cannot build a pack |
| `preflight` / `canary` | any other unexpected error in those steps. A git or a docker that cannot start does not land here: the real runners turn it into a failed command, so it gives `worktree` (git) or `docker`. A canary error after its session started is not a refusal: it is a FAIL line and `CANARY FAIL`, exit 1 |

The night's own refusal (`dirty` outputs: `progress/attempts.jsonl`, a `status.csv` or the feed differ from HEAD) also exits 2.

**Dry run.** `uv run reverseapoc drive --dry-run` prints 10 picks, builds their context packs under `build/driver/<run>/dry-run/` and never launches claude or a gate. With a signed tier (Phase 7) they are the tier queue's first 10 picks, each with its tier, level and pass. Without one they are the Phase 6 pilot picks: 5 UFO2P and 5 TACP, interleaved, easiest first, at most 2 per unit and 3 per 64 KiB region (D-10), skipping functions that are matched in `status.csv`, partial today (this pass), or on the difficult list.

**Canary.** `uv run reverseapoc drive --canary` is run by the owner before the pilot. It launches one real session with the matching settings and a fixed prompt that asks for five calls: Write `config/targets.toml`, Write `tools/x.py`, Bash `ls`, `uv run --frozen reverseapoc attempt context` and `uv run --frozen reverseapoc attempt check`. The claim is `ufo2p/u_000a34f0`, function `func_000A3980`, with its attempt directory under `build/driver/canary/<run>/`. It prints PASS only when all of these hold:

- the session's init event is clean (CLI version, the model the canary asked for, the six tools, no MCP server, no plugin). The canary asks for `claude-opus-5-5`, or for the model given with `--model` (the owner's Fable canary is `uv run reverseapoc drive --canary --model claude-fable-5-1 --run <fresh id>`, D-25); its budget is that model's (`--max-budget-usd` or `--fable-budget-usd`). The init line names the model string the init event reported, so the owner can report it. CLI built-in plugins count as plugins. The driver settings switch them off with short `<alias>@builtin: false` keys. CLI 2.1.308 ships `cc-plugin-agents-md`, `cc-plugin-telemetry` and `cc-plugin-plugin-authoring`; the key drops the `cc-plugin-` prefix (`"agents-md@builtin": false`), as probed on 2026-10-25;
- the first three calls are in the result's `permission_denials`;
- both wrapper calls were made and not denied, `attempt context` wrote `context.md`, and `attempt check` logged exit 0 (the claimed function is already matched, so this proves the container path);
- no unknown stream event type carries an error;
- the attempt's containers were removed afterwards (by the attempt's name prefix, as the night does);
- `git status --porcelain` is clean afterwards;
- HEAD and every ref are where they were (a commit leaves `git status` clean);
- nothing the night's audit pins or fingerprints changed (`.git/config`, `.git/info/exclude` and `attributes`, `.git/hooks/`, `.githooks/`, the two Claude settings files, `.venv`, the gitignored `.claude/` trees but `.claude/worktrees/`, every `__pycache__`).

Each check prints one `PASS: ...` or `FAIL: ...` line, with no time stamp; the last line is `CANARY PASS` (exit 0) or `CANARY FAIL` (exit 1). Use a fresh `--run ID` for every canary (the default, the UTC time, always is): a reused one is refused. The canary leaves the tree as the session left it, for inspection, and changes nothing back.

**After a FAILed or leaky canary**, before anything else:

1. Read the FAIL lines and the transcript `build/driver/canary/<run>/ufo2p/func_000A3980/attempt-1/transcript.jsonl`.
2. `git status` lists what the session left in git's view. Put tracked files back with `git restore --source=HEAD -- <paths>` (for example `git restore --source=HEAD -- config/targets.toml`) and delete untracked strays by name (for example `tools/x.py`). If HEAD moved, inspect the new commit with `git log` before resetting anything.
3. The FAIL line `pinned and fingerprinted files changed: ...` names paths git cannot see (`.git/hooks/`, `.git/config`, `.venv`, `.claude/`, `__pycache__`). The next preflight does not see them, so check each named path by hand: delete a new hook, `.pth` or `*customize.py`, restore `.git/config` or a settings file from a backup or by hand, and run `uv sync --locked` and `uv run --frozen python -m compileall -q tools configure.py` again for `.venv` and `__pycache__`.
4. If a container is named in a FAIL line, remove it with `docker rm -f <name>`.
5. Run the canary again with a new `--run ID` until it prints `CANARY PASS`.

**One attempt.** The driver claims the unit, builds the session's view from HEAD (`git archive` of `src/`, `include/` and `config/` into `<attempt dir>/view/`; Phase 7, D-24), scaffolds the unit inside the view if HEAD has none, builds the pack, and starts the session in the checkout root. The session gets these variables, as absolute paths:

- `REVERSEAPOC_CLAIM`, `REVERSEAPOC_FUNC`, `REVERSEAPOC_ATTEMPT_DIR` and `REVERSEAPOC_ATTEMPT_NOTES`, as in Phase 6;
- `REVERSEAPOC_UNIT_FILE`: the view unit, `build/driver/<run>/<exe>/<func>/attempt-<n>/view/src/<exe>/<unit>.c`, the only C file it edits (its /goal names it too);
- `REVERSEAPOC_PROPOSALS`: `<attempt dir>/proposals.jsonl`, for naming proposals (D-19) of readability sessions. For a matching session the hooks allow it, but nothing reads it: the driver applies proposals after readability sessions only (07-34, ruling F34), so a matching session writes its name ideas in notes.md;
- `REVERSEAPOC_SESSION_KIND`: `matching`, or `readability` on a readability night (see "Readability nights" below).

It may run only the attempt wrapper's five forms (`hooks.ATTEMPT_FORMS`). Each runs against the view, so its check compiles the view unit with the view's `config/cflags.txt`:

- `uv run --frozen reverseapoc attempt check`, at most 25 runs per attempt;
- `uv run --frozen reverseapoc attempt check --sweep`: a diagnostic that is never a match. When no stage-1 cell is perfect and the best one reaches 90% with its relocation check ok, a second stage (D-15) tries up to 24 more cells under 10.6. Either stage's hit is reported as `sweep hit: needs flags <spec>`, which feeds the flag rules below;
- `uv run --frozen reverseapoc attempt asm` and `uv run --frozen reverseapoc attempt asm <NAME>` (another row of the same EXE);
- `uv run --frozen reverseapoc attempt context`.

After the session the driver removes the attempt's containers and audits every changed path: git's view of the checkout, and every file of the view except its unit and `view/build/`. Then, under the gate lock, its landing section copies the view unit's bytes to `src/<exe>/<unit>.c` (the driver is the only writer of `src/`), lints the unit (C89) and runs the unchanged container gate. The driver does not land, lint or gate a view unit that defines no function of the unit in C (the scaffold left as it was, or only a comment or a struct added): the gate cannot match it, and refuses most such units with exit 2. The attempt ends as any other no-match (GAVE_UP, or PARTIAL with its `gate --partial`), with no gate verdict in its record, and the night goes on (hotfix 2026-10-31).

**Reset rules (D-34, D-24).** A match is one commit with explicit paths: the landed unit, `status.csv`, `decomphub.progress.json` and `progress/attempts.jsonl`. A matching session adds no header (D-19). Anything else resets the attempt: the driver puts back just the landed unit in `src/` (`git restore --source=HEAD -- <unit>` when HEAD tracks it, otherwise it deletes the copy it wrote) and abandons the view as it is, for inspection. It never touches all of `include/` and never runs `git add -A` or `git clean`. A partial attempt keeps its best C under `best/` and is scored by `gate --partial`. A write outside the session's allowlist is a guardrail stop: the stray files are restored or moved into `build/driver/<run>/quarantine/` (never deleted), the night ends and nothing is committed. A night that stops with partial rows leaves `status.csv` uncommitted and names it; the next drive refuses to start until the owner commits or restores it.

**End of run.** When the night ENDS (nothing to do, max sessions, target matched, queue exhausted), the driver runs, in the container, `uv run --frozen python configure.py && ninja -t clean && ninja verify`, then `reverseapoc gate --all`, and logs both under `build/driver/<run>/` (`end-ninja-verify.log`, `end-gate-all.log`). A failed check is recorded in the ENDED run record and the night exits 1. Then the `chore(driver): attempt log` commit holds the night's records. **A STOPPED night skips both end checks**: it has no ninja verify or `gate --all` evidence, so run them by hand before trusting it. Exit codes: 0 ended clean, 1 stopped or a failed end check, 2 refused.

**Warnings for the night.**

- **Do not edit the checkout while the driver runs.** The audit compares the tree before and after each session, so your edit looks like a session stray: the night stops on a guardrail (STOPPED `guardrail`), your file is restored to HEAD or moved into `build/driver/<run>/quarantine/`, and nothing is committed.
- **Ctrl+C** ends the night as STOPPED `interrupted`: every live session is killed, each live attempt is reset uncounted, and the record names what was undone. The end-of-run checks are skipped, as for any STOPPED night.
- **The canary is a real, paid Claude session.** Its `attempt check` alone can take up to 10 minutes (the wrapper's container check runs for at most 580 s).

**Open assumptions to watch at the pilot checkpoint.** The tests prove the driver against synthetic streams and fake commands only. These hold only if the real CLI, Docker and host behave as assumed. The canary checks items 1, 4, 5, 6 and 7; items 2 (hook timing) and 3 (`CLAUDE_PROJECT_DIR`, partly shown) stay open after a `CANARY PASS`; items 8 to 10 are operational:

- **`permission_denials` shape.** The canary reads the result event's `permission_denials` as `{tool_name, tool_use_id, tool_input}` entries and expects hook denials to appear there. If they do not, the canary FAILs; look at the transcript.
- **Hook timing per tool.** If Claude Code ran every PreToolUse hook of a turn before any of its tools, two Edits each placeable on the original file could compose `_asm`. The canary cannot see this. Behind it: the always layer denies any `src/` Edit whose old text is not verbatim in the file, and the gate decides every match; no commit-time inline-asm scan exists.
- **`CLAUDE_PROJECT_DIR`.** The canary shows that the hooks ran in a project holding `reverseapoc.hooks` (the denials and an allowed wrapper call), not that it is this checkout rather than another one with `hooks.py`. The main-checkout preflight and the session's cwd make a foreign value unlikely.
- **`uv run --frozen` writes nothing to `.venv`** once the preflight's host `uv sync --locked` ran (the wrapper has no `--no-sync`). The canary's fingerprint check proves or refutes it.
- **Container bytecode.** The container's Python 3.14 is assumed to accept the host-compiled `.pyc` in the bind mount and to write none during `attempt check`. The canary's fifth call and its fingerprint check prove or refute it.
- **Known stream event types** are `system`, `assistant`, `user`, `result` and `rate_limit_event`. Any other type is ignored by the night; the canary FAILs if one carries an error key.
- **CLI built-in plugins.** A newer CLI may add another built-in plugin. Then the canary FAILs with `init: plugins loaded: cc-plugin-<x>`. The fix is a new `"<x>@builtin": false` key in `config/driver/claude-settings.json`, proven by a fresh canary.
- **The `claude` executable** is found with `shutil.which("claude")` and is assumed to be the native `claude.exe` from `claude install`. A `.cmd` shim may not start under the driver's argv-list launch.
- **`COMPOSE_PROJECT_NAME`.** Container cleanup filters on the compose project label, derived from the checkout's directory name (`reverseapoc`). If `COMPOSE_PROJECT_NAME` is set, the filter finds nothing and no error is raised, so a timed-out check container could keep running.
- **Leaky canary leftovers** (for example `tools/x.py`) stay in place for inspection; clean up as above before the pilot.

### Readability nights

A readability night names, comments and types units that already match (D-17, D-18, DEC-04). It runs through the same driver as a matching night: the same preflight, caps, workers, views, hooks, claims and records. The session kind is the only difference.

```
uv run reverseapoc drive --session readability --dry-run   # the queue, with each unit's readlint violations
uv run reverseapoc drive --session readability             # the night
```

**The queue.** It holds every committed unit with at least one `matched` row in `status.csv` that strict readlint does not pass yet. The four pre-phase units and the D-13 units are in it too: they need names before the phase gate. The order:

1. units holding members of Tier 1;
2. units holding members of the other signed tiers, in tier order;
3. every other matched unit.

The queue is bottom-up. A unit is offered once each matched callee it has in another unit passes readlint, or shares its call cycle (SCC). Then its callees are named first, and the callers are known. The queue is read again from HEAD before each pick (a snapshot taken with `git archive`, never the working tree), so only committed landings count. A caller can come up the same night once its callees' landings are committed, and a callee whose landing is still in flight still counts as failing. With several workers, such a caller waits for the next night. When every matched unit passes readlint, the queue is empty: no session runs, and the night ENDS with `nothing to do`, exit 0.

**One session per unit.** The claim has kind `readability`, and the session's environment has `REVERSEAPOC_SESSION_KIND=readability`. The claimed function is the unit's lowest matched function, which the attempt directory and the record name. The session runs on Opus with `--max-budget-usd` (escalation to Fable is a matching rule). Its argv appends `.claude/skills/watcom-readability/SKILL.md` instead of watcom-decomp. Its /goal asks for `attempt check` to report the check OK and readlint clean for the unit, with `notes.md` written. The goal also says that names are checked again at landing.

**What a session may change.** In its view unit only: comments (above all each function's header comment), the names of locals and parameters, whitespace, `#define`s that name literals, and types the unit introduces. Function and global names change only through `proposals.jsonl` (D-19). Shared headers change only through header proposals. It never changes which functions the unit defines in C or marks `INCLUDE_ASM`.

**The rename commits.** After the session's audit, the driver applies its proposals first (07-34). Each valid rename is its own `refactor(<exe>): rename <old> to <new>` commit (`Renamed-By: reverseapoc drive`), and each header proposal is a `refactor(include): write include/<name>.h` commit. Before its gate, each one runs the C89 lint over every unit it rewrites or gates and, for a header, over a probe unit that includes `common.h` and then the header. A failing lint refuses the proposal, and nothing is committed. The session's view unit is rewritten under the new names.

**The landing.** It runs under the gate lock, in this order:

1. If the unit is unchanged against HEAD (after the renames), the outcome is **GAVE_UP**, with no gate.
2. The driver compares the set of functions the unit defines in C and marks `INCLUDE_ASM` (by start) with HEAD's. If the set changed, the outcome is **REFUSED**, before anything lands.
3. The unit lands in `src/` and gets the C89 lint. A failing lint is **REFUSED**, with `abort_reason` `lint`.
4. The container gate runs on the unit. A failing gate means a byte moved: **REFUSED**.
5. Strict `readlint --units <exe>/<unit>` runs. If it is clean, the outcome is **LANDED**: one commit `refactor(<exe>): name and document <unit> (readability)`, with the model's `Co-Authored-By:` line and `Readability-By: reverseapoc drive`. The commit holds the unit, `status.csv` (with `source_sha256` refreshed by the gate), the feed and the log. If readlint still fails, the outcome is **PARTIAL**: the unit and `status.csv` go back, and the view unit is kept under `<attempt dir>/best/<unit>.c`.

Every outcome is a v2 attempt record with `session: readability`. List the night's landings with `git log --format='%h %s' --grep='^Readability-By: reverseapoc drive$'`.

**Callees left unnamed (D-30).** A matched unit may call a hub or an `asm` row that no session can name from evidence. Its RL01 reference then keeps the unit from landing. Before the first readability night, the executor lists every RL01 reference (never a definition) to a row that is not matched, in matched units, with its members role. The owner reviews the list at a short checkpoint, and the executor commits it to `config/readlint-allow.csv`. After the nights, rows whose reference is gone (renamed by a proposal) are pruned and new ones are added, again with the owner's review. Sessions never edit the allowlist; they name candidates in `notes.md`.

**The done check.** `uv run reverseapoc readlint --tier 1` exits 0 (Tier 1 is fully named), and then `uv run reverseapoc readlint src/` exits 0 for every matched unit.

### Hooks (guardrails, Phase 6)

Agents have gamed verifiers before: Claude rewrote a SHA-1 to force a "match" and worked around a blocked `make` (Lewis); an agent tried to fork its compiler (Macabeus). Prose rules are not enough, so two PreToolUse hook layers in `tools/reverseapoc/hooks.py` enforce these.

**The always layer** runs in every Claude session in this repo (`.claude/settings.json`; the driver's settings file carries a copy). On Write, Edit, MultiEdit and NotebookEdit it blocks:

| Block | Why |
|---|---|
| Any write under `orig/` | The original executables are the ground truth |
| Writes to `config/targets.toml`, `config/watcom.toml` and any `*.sha1` | The SHA-1 is the done-gate |
| Writes to `config/cflags.txt` and `config/cflags-proposals.toml`, with no exemption (Phase 7, D-12, D-27 P3) | Flags are owner-only: only `reverseapoc flags approve` and `reverseapoc flags default` change `config/cflags.txt`, and only `reverseapoc flags` writes the proposal queue, all from Python, which no hook sees |
| Writes under `asm/` and `build/`, except the driver's per-session files at their exact shapes: the attempt's `notes.md` (`REVERSEAPOC_ATTEMPT_NOTES`), and in Phase 7 the view unit (`REVERSEAPOC_UNIT_FILE`) and `proposals.jsonl` (`REVERSEAPOC_PROPOSALS`) | Generated output; the same oracle for everyone |
| Inline assembly in `src/`, `include/` and the view unit: `_asm`, `__asm`, `_Pragma`, and `#pragma aux` bodies that emit code bytes | Matching must come from C |
| An Edit in `src/` or `include/` whose old text is not in the file verbatim, and any lone CR | The scan must see the exact text the compiler will |

**The matching layer** runs only in driver sessions (`config/driver/claude-settings.json`). It denies by default:

- **view mode (Phase 7, D-24):** with the driver's `REVERSEAPOC_CLAIM` and `REVERSEAPOC_UNIT_FILE` (at the view shape `build/driver/.../view/src/<exe>/<unit>.c`, naming the claim), a session writes only its view unit, the attempt's `notes.md` and its `proposals.jsonl` (`REVERSEAPOC_PROPOSALS`). Without `REVERSEAPOC_UNIT_FILE` it writes nothing: Phase 7 removed the Phase 6 allowlist of `src/<exe>/<unit>.c` and new `include/*.h`. A write to `include/` or a `config/<exe>/symbols.csv` is denied as shared naming state, which only the driver writes (D-19). `REVERSEAPOC_SESSION_KIND` is `matching` or `readability`; any other value writes nothing, and a readability session writes only in view mode. The driver's post-session audit applies the same allowlist to every path a write tool names in the transcript;
- **agents write no `#pragma aux` of any kind in the pilot, and no other `#pragma` either** (D-18); calling-convention pragmas come only in human-reviewed commits;
- Read, Glob and Grep only inside the checkout, never `.env*`;
- Bash only as one of the attempt wrapper's exact forms, never in the background, and `attempt check` (plain or `--sweep`) only with the Bash tool's `timeout` set to 600000: at the tool's 120 s default the tool kills the wrapper mid-run and its `check.lock` refuses every later check of the attempt;
- every other tool is denied, and without a valid claim every write and every Bash call is denied.

**Includes.** A file in `src/` or `include/` may `#include` only a bare header name: `"name.h"` from `include/`, or `<name.h>` from `include/` or the compiler's own headers (Watcom's `H` directory, for toolchain headers such as `conio.h` or `i86.h`); Watcom looks for a quoted header in the unit's own `src/<exe>/` first, where agents cannot write. No path, no `..`, no other suffix. Both layers deny any other `#include` under their own reason. configure's D-12 check refuses the same file at build time, and `check` (so `attempt check` and the gate) refuses it before compiling and counts it as a source problem of the unit's account, so no unscanned file (such as an attempt's `notes.md`) reaches the compile.

**Both layers fail closed.** Each handler runs `uv run --frozen --project "$CLAUDE_PROJECT_DIR" python -I -m reverseapoc.hooks ... || exit 2`. A missing `uv`, a missing module, or an unset or foreign `CLAUDE_PROJECT_DIR` blocks every Edit and Write (exit 2). Both handlers also set `"timeout": 120` and `"onFailure": "block"`, so a hook that runs past 120 s blocks the call too (`onFailure` needs CLI 2.1.295).

Known limits:

- Bash is not covered by the always layer. An owner or executor session can still change `orig/` or a manifest with a shell command; `check-orig` and the gate catch it by hash.
- A hard link made by Bash to a protected file is allowed: the hook does no inode check. Only Bash can make one, and the matching layer cannot run `ln`, `mklink` or `fsutil`.
- Other git checkouts are over-denied: a path is judged against every ancestor holding `.git`, so `build/`, `orig/`, `asm/` and `*.sha1` are also blocked in another checkout a session writes to.
- Whether a `--settings` file merges with or replaces project hooks, and whether each tool's hook runs right before that tool (not once for the whole turn), is proven only on the real CLI. The canary checks the denials; the driver's post-session audit and the gate stand behind both.

### Flag rules (D-12, D-14)

Flags are never a session's choice, and neither the agents nor the driver edit `config/cflags.txt` (Phase 5 D-18); both hook layers deny it. A sweep hit (`sweep hit: needs flags <spec>`, from either stage) is evidence. The driver writes it into the attempt record, and every sweep keeps its `checks/NNNN.json` and the C it ran (`checks/NNNN.c`). A hit is never a match and never evidence for the `*` default on its own (D-28, D-33). It becomes a per-unit rule through a queue, `config/cflags-proposals.toml`.

Executor verbs (GSD executors or the owner, between nights):

- `uv run reverseapoc flags propose --from-attempts <run> [<run> ...]` (host): reads every sweep line of every attempt of the named runs (all runs when none is named) and turns each hit into a proposed per-unit rule in the queue, copying the C that hit to `build/flags/<id>/<unit>.c`. Each proposal names its unit's siblings, which the rule would bind too (D-32).
- `uv run reverseapoc flags regate <ID> [<ID> ...]` (in the container, for objdiff-cli): re-proves each proposal on a copy of `src/`, under the committed rules plus the proposed one. Every matched function of the unit must still match and both EXEs must stay SHA-1 identical. It tries the file as written first, then D-28's reduced variant. It writes only the queue and `build/flags/`.
- `uv run reverseapoc flags list`: the queue, with the functions, unit, rule, alternatives, siblings, evidence and re-gate status.

Owner-only verbs, run by the owner at a checkpoint and never by an agent:

- `uv run reverseapoc flags approve <ID> [<ID> ...] --by <name>` (D-12): lands re-gated proposals in the order given, each as one gated match commit (the rule in `config/cflags.txt`, the C, `status.csv`, the feed, the queue and the `docs/matching.md` row) with a `Flags-Approved-By:` line. It is refused while a drive runs.
- `uv run reverseapoc flags default --rule <spec> --by <name>` (D-14, D-33): changes the `*` default only on D-33's evidence (3 or more functions matched under per-unit rules equal to the spec, each with a branch, a loop or 64+ bytes, from both EXEs and different 0x10000 regions). It pins every matched unit without a rule to the old default and runs `gate --all` before and after. `--evidence` prints the bar's inputs and verdict and changes nothing.

The batches so far are in [toolchain.md](toolchain.md#phase-7-flag-rules).

**Mechanics data.** The tier queue reads `config/mechanics.toml` and `config/mechanics-members.csv` (D-02, D-04). `uv run reverseapoc mechanics <verb>` keeps them:

- `mechanics write`: regenerates `config/mechanics-members.csv` from `mechanics.toml`, `functions.csv` and the call graphs of `orig/`;
- `mechanics check`: validates the committed files without game files (member rows, entries, the signed tier digests, the asm list sign-off);
- `mechanics status`: matched, partial and unmatched counts of each tier's must-match members, from `status.csv`;
- `mechanics hubs`: candidate hub-rule numbers for a tier (D-22);
- `mechanics digest`: a tier's `members_sha256`, for its sign-off;
- `mechanics graph`: an EXE's call-graph report (edge counts, indirect calls, the largest cycles);
- `mechanics locate`: entry candidates in one EXE (rows referencing a string, an address or a range, `get_text` call sites, `int386_` callers; needs `orig/`);
- `mechanics asm`: proposes the D-23 list of hand-written assembly rows, which leave the queue.

Each prints addresses, names and counts only.

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
| 7 Mechanics-first decompilation | `config/mechanics.toml` (OpenApoc checklist items -> functions), the Phase 6 driver at scale with claims and one owner of names, `readlint` for names, comments, types and constants, `reverseapoc stats` for the research metrics | every function in Tier 1's must-match set matches (objdiff 100%, relocations checked), every tier signed off (owner ruling D-05, 2026-10-26), both EXEs identical, zero regressions; `readlint` clean; coverage per checklist item on the progress page | locate the #997 tick-rate and training code from timer setup and strings within a time box |
| 8 Clean-room specs for OpenApoc | OpenSpec-format template and status ladder, `speclint`, `wikifetch` (MediaWiki API), `apoc-spec` skill, `docs/clean-room.md`, `specs/LICENSE` (CC0-1.0), community claim inventory, `docs/findings/` (bugs, cut content, cheats and easter eggs, Learning AI) | every Phase 7 mechanic has a spec that passes `speclint`, reaches `backed-by-matched-code` and has an owner review line; negative tests prove the linter fails | `wikifetch` reads one UFOpaedia table page with revid and numbers intact |

Cross-cutting task, opened as a GitHub issue in Phase 1: ask OpenApoc which build has UFO2P CRC32 `0x4749ffc1` (current Steam/GOG is `0xDBD3B41D`) before reusing any of their offsets.
