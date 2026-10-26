# Phase 7 research, slice 2 of 3: the driver at scale, naming and metrics

**Researched:** 2026-10-26
**Scope:** DEC-02, DEC-06, DEC-07, AGT-11 (carry-in), DEC-03 matching mechanics; owner rulings D-06..D-11, D-17..D-19 (07-CONTEXT.md)
**Method:** read-only. Code read this session: `tools/reverseapoc/driver.py` (all 2,614 lines), `attempt.py`, `gate.py`, `check.py` (land/compile/account parts), `cli.py` (check/gate/drive verbs), `hooks.py`, `session.py`, `streamjson.py`, `picker.py`, `symbols.py`, `status.py`, `functions.py` (symbols.csv part), `compiler.py` (root, include, lock parts), `configure.py` (D-12 parser), `config/driver/claude-settings.json`, `tests/test_drift.py`, `tests/test_attempts_schema.py`, `tests/fakeclaude.py`. Data read: `progress/attempts.jsonl` (42 records), git trailers, the 40 pilot transcripts under the gitignored `build/driver/20261026-005209/` (counted only, nothing quoted). Scratch scripts: `C:\Users\Ayrton\AppData\Local\Temp\claude\c--Users-Ayrton-Documents-Gitprojects-ReverseApoc\17a94130-d386-485e-bd6f-517f62527b62\scratchpad\att.py`, `fit.py`, `tr.py`.
**Confidence:** HIGH for what the code does today (read line by line); MEDIUM for the proposed designs (not prototyped); LOW where marked [ASSUMED].

No #997 tick-rate or training-rule finding came up in this slice (it does not read game code).

## Summary

The Phase 6 driver is serial by construction, and three of its mechanisms break as soon as two sessions share the checkout. (1) Every `check` and every `gate` compiles and lands **every unit file present in `src/`** of both EXEs (`check.land_all`, check.py:1060-1090, called from `check_unit` check.py:1150 with only the checked unit marked `fresh`), and `gate` refuses any src tree but the committed one (`_committed_src`, gate.py:242-247). So worker A's attempt check and A's gate compile worker B's half-edited unit: a compile error makes A's check exit 2 (CheckError, check.py:255-261) and A's gate a tool failure that stops the night (`_tool_failure`, driver.py:1552); a compiling but wrong B lands wrong bytes and fails A's SHA-1. The attempt wrapper does **not** compile a copy: it runs `check <claim> --json` on the real `src/` with default roots (attempt.py:222-226), writing ninja's own object paths under `build/<exe>/obj/`. (2) The post-session audit diffs the whole tree's `git status` before and after one session (driver.py:1109-1116, 1266-1278), so another worker's landing (unit, status.csv, feed, attempts.jsonl, a moved HEAD) reads as a stray and stops the night. (3) The pre-gate restore puts `attempts.jsonl` back to its pre-gate bytes (driver.py:1569-1570, 1536-1550), which would erase records other workers appended meanwhile.

The recommended design keeps `gate` untouched and makes `src/` equal HEAD at all times except for the one unit being landed under the lock: **each session edits a private copy of its claimed unit inside a per-attempt view tree** under `build/driver/<run>/<exe>/<func>/attempt-<n>/view/` (HEAD's `src/`, `include/` and config CSVs, snapshotted at launch, plus the private unit), the wrapper checks that view with `check --src/--config/--build/--log` pointed into it, and the driver copies the private unit into `src/` only inside the serialised lint+gate+commit section. Reset becomes "abandon the view"; the stray check becomes "nothing git can see changed except driver-owned files, whose bytes the driver knows". This needs one real code fix: `check._compile` calls the compiler without a compile root (check.py:255-257), so a src tree under `build/` selects its cflags rule by the path `build/driver/.../src/<exe>/<unit>.c` and silently falls to the `*` default. That bug already affects `gate --partial` today and matters the moment D-12 adds per-unit rules.

Threads fit (all work is subprocess-bound; `session.run_session` already uses reader threads and `taskkill /T /F`), with one coordinator thread owning the picker, claims, records and the gate lock. Claims are one O_EXCL file per unit plus a process-lifetime OS lock on `build/driver/drive.lock` (the msvcrt/fcntl pattern compiler.py:43-47, 473-512 already uses), never PID probing: on Windows `os.kill(pid, 0)` terminates the process. Model escalation needs a per-function pass count (difficult.json stores none), a model-aware `--max-budget-usd`, a model-aware init check (`_check_init` passes no `expected_model`, driver.py:1508), and a per-model `Co-Authored-By` (hard-coded Opus, driver.py:97). Renames (D-19) are blocked today by three placeholder-only parsers (configure.py:238-242, check.source_marks, the D-22 drift test) and by `SymbolTable.c_name` returning the symbols.csv **linker** name verbatim (`main_`), which is the wrong C name. `stats` has almost all inputs already; it needs a v2 attempt record (pass, session kind, hook blocks, gate verdict) that the schema test can read side by side with the 42 v1 lines, and a commit-trailer rule for `human-hints`.

**Primary recommendation:** private per-attempt view trees + one in-process lock around every shared write (gate, gate --partial, records, git, claims, renames), threads under a coordinator, `GIT_OPTIONAL_LOCKS=0` everywhere, and a `--fable-budget-usd` default of **12.50** for the owner to confirm.

## Architectural Responsibility Map

| Capability | Primary tier | Secondary tier | Rationale |
|------------|-------------|----------------|-----------|
| Picking, claims, pass/model choice, caps, backoff | Driver coordinator thread (host) | `build/driver/claims/` files | One process (D-06); files only for crash recovery and a second-process guard |
| One session (claude -p, audit) | Driver worker thread (host) | claude subprocess tree | Subprocess-bound; threads are enough |
| Session's own checks | Attempt wrapper (host) -> container `check` on the view | per-attempt `build/` | Must never see other sessions' edits or write ninja's objects |
| Match / readability verdict | Container `gate` on real `src/` | driver lock | Unchanged trust anchor (D-24); serialised (D-06) |
| Naming state (symbols.csv, shared headers) | Driver rename step under the lock | sessions write proposals only | D-19 |
| Write guardrails | `hooks.py` (per-process env) | driver post-session audit | Two layers, as Phase 6 |
| Metrics | `attempts.jsonl` (driver) + git trailers | local transcripts (optional back-fill) | DEC-07 must run in CI without build/ |

## 1. Concurrency in the driver

### Findings (evidence)

**Run loop.** `run()` (driver.py:876-912): dirty-output refusal, STARTED record, `_loop()`, end-of-run checks (`ninja verify`, `gate --all`, driver.py:1929-1954), run record, chore commit of the log. `_loop()` (977-991) iterates `deps.queue(difficult)` and calls `_function(pick)` serially. `_function` (1004-1014) runs up to `attempts_per_function` (3) attempts; a capped function goes to `build/driver/difficult.json` with only its matched callees (`save_difficult`, 712-715) and **no pass count**.

**Attempt lifecycle** (`_attempt` 1055-1078, `_launch` 1203-1255): fresh attempt dir; scaffold the unit into `src/` if missing (`_ensure_unit`); build the pack; `before = _snapshot()` of the **whole tree** (`git status --porcelain=v1 --untracked-files=all -z`, plus pinned files and a fingerprint of `.venv`, ignored `.claude/` trees and every `__pycache__`, 1109-1138); run the session with the claim env (`_Claim.env`, 763-768: `REVERSEAPOC_CLAIM`, `REVERSEAPOC_FUNC`, `REVERSEAPOC_ATTEMPT_DIR`, `REVERSEAPOC_ATTEMPT_NOTES`); remove the attempt's containers; `_measure` diffs before/after; `_audit` raises a guardrail STOP on any changed path the allowlist refuses (1280-1304); classify (LIMIT backs off with `BACKOFF_S = (60, 120, 240)`, `POLL_S = 300`, `TRANSIENT_RETRIES = 3`, driver.py:100-102).

**Counted session** (`_counted` 1608-1626): C89 lint in the container, then `gate EXE/UNIT --attempts N --json` (gate_argv 1864-1866); a match is `claimed_matched` on the gate's `written` rows (472-482) plus both SHA-1s (1574-1577), then one commit of explicit paths `[unit, status.csv, decomphub.progress.json, progress/attempts.jsonl, *new headers]` (1660). Otherwise `_reset` and, for PARTIAL, `gate --partial --src <best C>` which **writes status.csv** partial rows (gate.py:760-816).

**Reset** (`_reset` 1514-1532): `git restore --source=HEAD -- <unit> include/` for tracked paths, delete a unit scaffolded this attempt and the session's new headers. Note it restores **all of `include/`**.

**What concurrency breaks, one by one:**

| Mechanism | Evidence | Breaks with N sessions in one checkout because |
|---|---|---|
| Session check | attempt.py:222-226 runs `check <claim> --json` with default roots; check.py:1150 `land_all(... fresh={(target.name, unit)})` compiles every other unit file | it compiles other workers' live units (compile error -> exit 2; wrong bytes -> splice fails), and writes ninja's `build/<exe>/obj/<unit>.*` concurrently with other containers (object_root is `build_dir` itself for default roots, check.py:229-240) |
| Gate | gate.py:242-247 `_committed_src`; gate.py:579 `check_unit` -> `land_all` over real `src/` | same as above, plus the cross-check names any compiled-but-ungated unit "landed but is neither matched nor defined by a gated unit" (gate.py:361-363) |
| Audit | driver.py:1266-1278 whole-tree diff | other workers' landings, their scaffolded units in `src/`, the log appends all read as strays -> guardrail STOP |
| Reset | driver.py:1522-1525 `git restore ... include/` | wipes another session's new header; a scaffolded unit another worker shares cannot exist (whole-unit claims) but `include/` is shared |
| Pre-gate restore | driver.py:1569-1570 snapshots `status.csv`, feed, **attempts.jsonl**; 1536-1550 restores them | drops other workers' records and any partial rows another worker's `gate --partial` wrote |
| `_commit_headers` | driver.py:1640-1654: any untracked `include/*.h` the session did not write -> `_tool_failure` | another live session's new header stops the night |
| Git index | every audit runs `git status` (refreshes the index and may take `index.lock`), commits run `git add`/`git commit` | a commit racing a status can fail on `index.lock`; a failed commit runs `_undo_match` and marks the night breached (1680-1707) |
| `self.live`, counters | `_Night` holds one `live` session and plain ints (868, 863-866) | single-session state |

The wrapper's `check.lock` (attempt.py:438-459) is per attempt dir, so it serialises only one session's own checks.

### Recommendation: private view trees (Design B)

1. **At launch** the driver materialises `build/driver/<run>/<exe>/<func>/attempt-<n>/view/` from HEAD (not the worktree): `src/` (every tracked unit file), `include/` (tracked headers), `config/` (targets.toml, cflags.txt, and the per-EXE functions/units/symbols/runtime CSVs). Use `git archive HEAD src include config | tar -x` or `git show HEAD:<path>` per file through the git lock. The claimed unit is `view/src/<exe>/<unit>.c`: HEAD's file, or the scaffold if the unit has no committed file. This is the **only** C file the session may write (hook allowlist, section 3).
2. **Session checks:** the wrapper (host side, before docker) runs `check <claim> --src <view>/src --config <view>/config --cflags <view>/config/cflags.txt --build <view>/build --log <view>/build/logs/cc.log --json`. All `check` flags exist (`_add_unit_roots` cli.py:929-935, check flags cli.py:946-950). Objects then go to `<view>/build/check-custom/...` (object_root, check.py:229-240): no collision with ninja's objects or another session. `cc.log` and the Watcom stamp cache are already parallel-safe (compiler.py:13-14, 163-166, 202-204).
3. **Required fix, compile root.** `_compile` calls `compile_fn(src, obj, cflags=..., manifest=..., watcom_dir=..., log=...)` with no `root` (check.py:255-257), so `compile_source` uses `REPO_ROOT` (compiler.py:564) and `source_rule` matches the cflags glob against the repo-relative path (compiler.py:662-673; cflags.txt: "<glob> matches the source's repository-relative path"). A view unit at `build/driver/.../view/src/ufo2p/u_x.c` matches only the `*` rule. Fix: pass `root=<src_root>.parent` whenever the src root is a `src/` directory outside the default (the view root then holds `include/`, which `_include_list` takes from the compile root, compiler.py:359-363, and the object must lie inside the root, compiler.py:571). `check_provenance` already computes a root for non-default trees (`_compile_root`, check.py:973-978) but disagrees with the compile today. The same bug makes `gate --partial` score best C under `*` (it compiles `best/<unit>.c` with `src_root=saved.parent`, gate.py:786); save best C as `best/src/<exe>/<unit>.c` in the view layout instead. Slice 3's whole-unit re-gate under proposed flags depends on this fix too.
4. **Landing under the lock** (unchanged gate): copy the private unit into `src/<exe>/<unit>.c` (src/ is otherwise HEAD), rewrite any names renamed since the view snapshot (section 6), lint `src/<exe>/<unit>.c`, run the container gate, commit on a match, else `git restore --source=HEAD -- src/<exe>/<unit>.c` (or delete if untracked). Because no session writes `src/`, the gate sees committed units plus the one being landed, exactly as D-06 requires.
5. **Reset** becomes: leave the view in place as evidence (gitignored), release the claim. `git restore` runs only on the lock holder's own unit, never `include/` wholesale.
6. **Stray check** becomes two invariants. (a) Git-visible paths: after each session, `git status` may differ from the driver's **expected-state ledger** only in nothing. The ledger is the set of paths the driver itself has dirtied this night (`progress/attempts.jsonl`, `config/<exe>/status.csv` from partial gates, the unit being landed while the lock is held) with the exact bytes the driver last wrote (it already keeps bytes for restore, driver.py:1569). Any other change, or a ledger file whose bytes differ from the driver's last write, is a breach. (b) Build-tree paths: hash every non-claimed file in the session's view at launch and again before landing; a change is a breach. Pinned files and the fingerprint stay as they are (they are global, so a breach there stops the whole night, which is today's behaviour too).
7. **Attribution.** Per-session transcript write paths (driver.py:1292-1295) attribute a stray to a session; an unattributed stray stops the night with every live session killed and contained (fail closed).
8. **Headers.** Matching sessions get no `include/` writes at all (section 3). New types live in the unit file; shared headers come only from driver-applied proposals (D-19). That removes header collisions, `_commit_headers`, the header part of `_reset` and the `include/` arm of the audit.

**Threads, not processes.** Worker threads each run one `_launch` (claude subprocess + audit); the coordinator thread owns picker, claims, records, the gate lock and git. Python threads over `subprocess` are the right fit on the Windows host: the waits are on child processes and pipes; `run_session` already pumps stdout on a daemon thread and kills trees with `taskkill.exe /T /F` (session.py:117-144, 160-190). Two Windows specifics: `KeyboardInterrupt` reaches only the main thread, so it must set a stop event and kill every registered live session pid (run_session needs a hook that reports `proc.pid` to a registry); and `kill_tree` cannot reach grandchildren once the root exits on Windows (session.py:269-272, a known limit) — containers are still removed by name prefix per attempt (driver.py:1257-1264).

**Fallback (Design F), if the owner rejects edits outside `src/`:** let sessions edit `src/` as today but give `gate` a HEAD-view mode. That touches the gate's trust rule (`_committed_src`) and every status.csv path, so it is the costlier change.

## 2. Claims

### Findings
- O_CREAT|O_EXCL is already the project's atomic-create primitive on NTFS: `_O_NEW` (driver.py:142-143), `_check_lock` and `_reserve` (attempt.py:446, 472). Create-exclusive is atomic on NTFS; `os.rename` onto an existing file raises on Windows and `os.replace` overwrites, so rename is the wrong primitive for "first one wins" [ASSUMED: Windows semantics from Python docs knowledge, consistent with the code's own choice].
- `compiler.py` holds an OS lock (`msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)` / `fcntl.flock`) that "the kernel frees when its holder exits" (compiler.py:43-47, 489-512).
- On Windows, `os.kill(pid, sig)` with a signal other than CTRL_C_EVENT/CTRL_BREAK_EVENT calls TerminateProcess, so a `os.kill(pid, 0)` liveness probe kills the process [ASSUMED: Python os.kill documentation; do not prototype it].
- Units hold several target functions (e.g. `u_00089980` holds both matched func_0008A0E0 and func_0008A100, status.csv).
- The picker is pure and status-aware: it skips `excluded` (matched, or partial dated today) and `difficult` keys, ranks `(chk, score, start)` easiest first, interleaves EXEs and applies the variety rule `MAX_PER_UNIT = 2`, `MAX_PER_REGION = 3`, `REGION_SIZE = 0x10000` (picker.py:37-41, 126-128, 200-224). Its pool is score's P16 survivors (`ExeWorld.pool`, driver.py:2602).

### Recommendation
- **drive.lock:** at start the driver opens `build/driver/drive.lock` and takes the non-blocking OS lock for its whole life, writing `{run, started}`. Failing to get it refuses the start ("another drive is running"). Getting it proves any earlier holder is dead.
- **Claim file:** `build/driver/claims/<exe>__<unit>.json`, created O_CREAT|O_EXCL|O_BINARY, content `{"run","worker","exe","unit","function","start","kind":"matching|readability|rename","pass","model","claimed_at"}` (UTC ISO). Released by unlink after the landing decision. A rename claims every affected unit (section 6).
- **Stale rule:** with drive.lock held, every claim whose `run` is not the current run is stale: record it in the STARTED run record (new `recovered` list), move it to `build/driver/<run>/stale-claims/`, and go on. Under Design B a stale claim leaves nothing in `src/` except when the crash hit inside a landing; then the existing dirty-tree preflight (`_clean_tree`, driver.py:2163-2169) refuses the start and names the paths, which is the right owner checkpoint.
- **Granularity:** whole unit (D-06). A worker's task is one (function, pass) and keeps the claim for that pass's up to 3 sessions; between passes the unit is free.
- **Picker interface:** replace the pool source for Phase 7 with the signed-off tier's member set from slice 1, ordered callees first: condense the call graph to SCCs (recursion), order SCCs leaves first, and inside one level keep score's `(chk, score, start)` rank as the tie-break. The coordinator asks for "the next eligible key whose unit is not claimed and whose callees in the tier are all matched or capped at least once"; a key whose unit is claimed is skipped, not dropped. The variety rule is a pilot device and should be off for tier work (owner call; it would block a tier's dense units).

## 3. Hooks per session

### Findings
- The hooks learn the claim only from the process environment: `CLAIM_ENV = "REVERSEAPOC_CLAIM"`, `NOTES_ENV = "REVERSEAPOC_ATTEMPT_NOTES"` (hooks.py:79, 93), read in `_claim` (545-547) and `_notes_paths` (370-376). Hook commands are children of each claude process, so each session's hooks inherit that session's env. `config/driver/claude-settings.json` is one static file naming no unit (lines 17-42). **Per-process env is already enough for N sessions; no per-session settings file is needed.**
- Matching allowlist: `matching_write_allowed` (hooks.py:576-593) allows `src/<exe>/<unit>.c`, a new untracked `include/<name>.h` other than `("common.h", "watcom_compat.h")` (hooks.py:99), and the notes file. The always layer protects `build/` except the notes file (`_protected`, hooks.py:352-362; `_is_notes` 348-349). The inline-asm/pragma scan runs only for paths under `_SCANNED_DIRS = ("src", "include")` (hooks.py:77, 517, 690).
- The audit reuses the same predicate (driver.py:1193-1201).
- Denials appear in the result event's `permission_denials` (the canary relies on it, driver.py:2367-2370). Pilot: 0-3 per session, 41 in 40 sessions, 37 Bash and 2 Grep (transcript count, scratch `tr.py`).

### Recommendation
- New env: `REVERSEAPOC_UNIT_FILE` (absolute path of the view unit), `REVERSEAPOC_PROPOSALS` (`<attempt dir>/proposals.jsonl`), `REVERSEAPOC_SESSION_KIND` (`matching` | `readability`). The wrapper validates them like `_notes` (attempt.py:191-200): each must sit exactly at its expected place under the attempt dir.
- Matching allowlist becomes: the env unit file, notes.md, proposals.jsonl. **Deny** `src/**`, `include/**` (D-19: shared headers are driver-only) and `config/<exe>/symbols.csv` (already denied by default-deny, but give a named reason).
- The always layer's `build/` exemption extends from notes to the three env paths, and the inline-asm/pragma/include scan must run on the env unit file even though it lives under `build/` (otherwise the scan silently stops applying — pitfall P3).
- Readability kind: same paths. The hook cannot judge "comments, names, whitespace only"; the gate (bytes) and readlint decide (D-17). Add one driver check after the session: the set of functions the unit defines in C and marks INCLUDE_ASM is unchanged (via the renamed-aware `source_marks`, section 6), so a readability session cannot turn a stub into a match attempt.
- Hook-block count per attempt: `len(result.permission_denials)` (zero hooks code). Optional precision: hooks.py appends one JSON line per deny to `<attempt dir>/hooks.jsonl` (path from `REVERSEAPOC_ATTEMPT_DIR`), which separates hook denials from CLI permission-mode denials.

## 4. Model escalation and budget

### Findings
- `session.MODEL = "claude-opus-5-5"`, `MAX_TURNS = 40`, `MAX_BUDGET_USD = 5`, `TIMEOUT_S = 30 * 60` are module constants baked into `build_argv(prompt, *, claude)` (session.py:35-39, 56-84). `Deps.argv` takes the prompt only (driver.py:208).
- `streamjson.EXPECTED_MODEL = "claude-opus-5-5"` (streamjson.py:63); `check_init(..., expected_model=EXPECTED_MODEL)` (332-358); the driver calls it without `expected_model` (driver.py:1508-1509) and the canary too (2423-2424). A Fable session would STOP the night with "model ... is not claude-opus-5-5 (D-35)".
- `TESTED_MAJOR = 2`, `MIN_CLI_VERSION = (2, 1, 302)` (driver.py:104-105); pilot CLI `2.1.308` on all 40 attempts.
- `COAUTHOR = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"` is fixed (driver.py:97); the commit body's `model` line comes from the init event (driver.py:445, 1666).
- Cost: `usage()` copies `total_cost_usd` and sums tokens over every model in `modelUsage` (streamjson.py:371-388).
- Pilot (40 sessions, all Opus): cost USD 0.12-1.78, sum 42.93, mean 1.07; MATCHED mean 0.42, PARTIAL mean 1.13; mean tokens per session: input 81, output 21,202, cache read 1,358,358, cache creation 99,935 (scratch `att.py`).
- Prices [CITED: claude-api skill model table, cached 2026-10-06]: Opus 5.5 input USD 4 / output 20 per MTok, cache reads 0.20; Fable 5.1 input 10 / output 50, cache reads 0.25. Cache writes: 1.25x input for the 5-minute TTL (skill README "~1.25x cost") = Opus 5.00, Fable 12.50.
- Cross-check: the pilot tokens at those Opus rates give USD 47.83 (1.25x writes) or 43.83 (1x writes) against the CLI's 42.93: the CLI's own estimate is in the same range but not exactly reproducible from the four token classes.
- The driver runs on the owner's subscription login (`--bare` is never passed, session.py:7-9), so `total_cost_usd` and `--max-budget-usd` act on the CLI's API-equivalent estimate; the binding constraint at night is the subscription usage limit, which Fable spends faster [ASSUMED].

### Recommendation
- `build_argv(prompt, *, claude, model, max_budget_usd, max_turns)`; `Deps.argv(prompt, model, budget)`; `goal_prompt(..., kind)` for the readability `/goal`.
- Escalation rule (D-09): capped passes = passes of this function that ended without a match. Passes 1-2 Opus; pass 3 and later Fable. Persist the pass number in the v2 attempt record (`pass`) and derive "capped Opus passes" from `attempts.jsonl` (committed, survives runs); difficult.json gains `passes` as a cache only. For the 12 pilot functions (v1 records, no `pass`), treat each run's attempts 1-3 as one pass: they each have one capped Opus pass.
- Init check: pass `expected_model=<the model this session asked for>`; the driver's preflight and canary accept both IDs (D-09/D-36). Whether the init event reports exactly `claude-fable-5-1` and whether CLI 2.1.308 accepts that model is **unverified**: one owner-run Fable canary (`drive --canary --model claude-fable-5-1`) settles both before the first real Fable session (D-11) [ASSUMED].
- `Co-Authored-By` from a model-to-name table; refuse an unknown model rather than mislabel the commit.
- **Fable per-session cap: propose `--fable-budget-usd 12.50`.** Arithmetic: the Opus cap (5.00) is 2.8x the pilot's largest session (1.78). Repricing every pilot session at Fable rates (10 / 50 / 0.25 / 12.50) gives mean 2.65, p90 3.56, max 4.73 (scratch `fit.py`; ratio Fable/Opus-actual 2.47). 12.50 = 5.00 x 2.5 keeps the same token headroom as Opus (2.6x the repriced maximum); it also leaves room for Fable's longer turns. Worst case for a whole night if every session were Fable and hit the cap: 60 x 12.50 = 750 (API-equivalent); at the repriced mean: 60 x 2.65 = 159. **The owner confirms the value at the D-10 checkpoint.**

## 5. Usage limits with 3 workers

### Findings
D-08 classes (streamjson.py:13-30): STOP (auth, billing, credits, unknown codes) ends the night; LIMIT backs off 60/120/240 s then polls every 300 s, not counted, and keeps the session's work (`_salvage`, driver.py:1595-1606); TRANSIENT retries 3 times then logs an `abort` record; ATTEMPT_DONE is counted. `limit_streak` is a single field (driver.py:866, 1080-1085). Nothing is recorded for a LIMIT wait.

### Recommendation
- One global pause gate (`threading.Event` plus `paused_until`). Any LIMIT sets it; no worker launches while it is set; sessions already running finish and are salvaged or judged as usual. When the backoff ends, exactly **one** worker probes (one launch); a probe that is not LIMIT clears the pause for all, another LIMIT advances the shared streak. STOP from any worker: set the stop event, kill all live session trees, contain and reset each (their sessions are not counted), STOPPED record.
- Night cap across workers: reserve a slot before each launch (`counted + reserved < max_sessions`, D-07's 60); release the reservation if the session ends uncounted. `--target-matched` (default still 10 in `DriveOptions`, driver.py:1773, and in the verb, cli.py:1294) would end a Phase 7 night after 10 matches: the planner should ask the owner whether Phase 7 keeps it, raises it or disables it (open question Q4).
- Records: every record carries `worker` (int); add a `limit` record kind (`{kind, run, worker, seconds, streak, date}`) so DEC-06's nightly totals can report usage-limit time.

## 6. Rename pipeline (D-19)

### Where names live (evidence)

| Carrier | Name written | Writer / reader | Evidence |
|---|---|---|---|
| `config/<exe>/symbols.csv` | **linker** names: `address,name,kind`; rows today `0x00010010,main_,func`, `0x000C9357,stackavail_,func`, `0x0013BBA4,__ASTACKSIZ,data` (ufo2p) | hand-edited today; read by check.load_exe, gate._owners, cli split | config/ufo2p/symbols.csv:1-5; functions.py:489-554 |
| `functions.csv` | placeholders forever (`func_XXXXXXXX`, `D_XXXXXXXX`), "generated by: uv run reverseapoc functions UFO2P.EXE --write; do not edit" | `functions --write` | functions.csv:1; functions.py:10-14 |
| `units.csv` | unit names only | units draft | — |
| `status.csv` `name` | "its symbols.csv name verbatim when the start has one, else its functions.csv name" | gate only (`_owners`, `merge_matched` renames a re-gated start) | status.py:8-10; gate.py:270-282, 482-492 |
| src/ C | `func_X` definitions, `void func_X(void);` prototypes, `extern ... D_X;` | sessions | src/ufo2p/u_000a34f0.c |
| `INCLUDE_ASM(func_X);` | placeholder; macro emits no bytes (`#define INCLUDE_ASM(name) extern int INCLUDE_ASM_##name`) | scaffold | include/common.h:19; units.py:329-355 |
| Linker / objdiff names | `SymbolTable.linker_name`: symbols.csv name verbatim, else `func_X_` / `_D_X` | target cut (target.py:180-184, 294), check pairing (check.py:298-299, 632) | symbols.py:139-152 |
| `objdiff.json` | units and paths only, no symbol names; ninja's target edge lists symbols.csv as an input | configure.py:720-734, 769-770 | — |
| progress outputs, feed | status.csv names | progress.py:238; gate.write_feed | — |

### Blockers found
1. **`c_name` is wrong for symbols.csv rows.** `c_name` returns `symbol.name` verbatim (symbols.py:154-159), i.e. `main_`. Under Watcom's register convention a C function `main` links as `main_` and data `x` as `_x` (symbols.py:6-11, `FUNCTION_LINK_SUFFIX = "_"`, `DATA_LINK_PREFIX = "_"`). The context pack, asm listings and score show this name to agents (contextpack.py:554, 613, 622, 659, 699; asm.py:129-135, 252, 282). No test pins `c_name` for a symbols.csv row (tests/test_symbols.py:40-56 cover placeholders and runtime names only), so the fix is free: func C name = linker name minus the trailing `_`, data C name = linker name minus the leading `_`; refuse a symbols.csv func row without the suffix.
2. **configure.py's D-12 check is placeholder-only.** `_PLACEHOLDER = r"func_[0-9A-F]{8}"`, `_MARKER`, `_DEFINITION` (configure.py:238-242), and `check_unit_source` requires each row by `row.name` (the functions.csv placeholder) to be defined or marked (472-495). A unit defining `GetVolume(...)` instead of `func_X(...)` makes configure raise "func_X is neither defined in C nor marked INCLUDE_ASM (D-12)" (424, 800-802), so `ninja verify` (end-of-run check 1) fails. Fix: `_exe_units` already reads symbols.csv as an input (769-770); pass per-row C names into `check_unit_source` and match definitions against them.
3. **check.source_marks and the D-22 drift test** use the same parser (check.py:508-523; tests/test_drift.py:55-73). After a rename, status.csv says `GetVolume_` and the drift test finds no placeholder definition: CI fails. gate.py already notes the gap (gate.py:289-291). The drift test must compare by start through the symbol table.
4. **`address_of` refuses the placeholder of a renamed address** (`_refuse_renamed`, symbols.py:199-203). So every unit whose C still writes `func_X` for a renamed callee fails its relocation check on the next gate. Renames must rewrite all users atomically, as D-19 says.

### Proposal format (machine-checked, `proposals.jsonl`, one JSON object per line)
```
{"op":"rename","exe":"ufo2p","kind":"func","address":"0x000A3980","name":"GetSoundVolume","evidence":"<one line>"}
{"op":"rename","exe":"ufo2p","kind":"data","address":"0x0012EFAC","name":"g_soundVolume","evidence":"<one line>"}
{"op":"header","path":"include/<name>.h","text":"<full new header text>","evidence":"<one line>"}
```
Names are C names; the driver derives the linker name. `header` carries whole-file text for one shared header (never `common.h` or `watcom_compat.h`, hooks.py:99), so struct fields, enums and `#define`s use one op whose effect the gate proves; a header-diff op is a later refinement. The ops, the field set and the evidence rule are referenced by the readability skill, the driver and the hooks (D-19's reversibility note), so they should be pinned by tests first.

### Apply step (driver, single writer, under the lock)
1. Validate: C identifier, not a C89 or Watcom keyword, not placeholder-shaped (symbols.py:245-247 already refuses), unique among symbols.csv names, runtime publics and file-scope names in committed `src/`; `header` text passes the always-layer scans and the include rule.
2. Affected units: every committed unit whose code or comments contain the old placeholder token, plus units that `#include` a changed header.
3. Claim all affected units (a multi-unit claim); wait while any is claimed by a session.
4. Write symbols.csv (`write_symbols_csv`, functions.py:512-514, atomic), rewrite the placeholder token to the C name in each affected unit (word-boundary replace of the exact `func_XXXXXXXX` / `D_XXXXXXXX` token), write the header.
5. One `gate u1 u2 ...` (all or nothing, gate.py:548-600). Pass: commit symbols.csv, units, headers, status.csv and the feed, subject `refactor(<exe>): rename func_X to Name`, trailer `Renamed-By: reverseapoc drive`. Fail: restore every path, log the proposal as refused.
6. Pending renames are also applied, by the same rewrite, to a session's private unit at landing time, so a session that started before a rename still lands.

### Tests and drift checks to add
symbols.c_name for func and data symbols.csv rows; configure D-12 with renamed rows; source_marks renamed-aware; drift test by start; a rename end-to-end test on a tmp repo (fake gate) proving symbols.csv, unit text, status.csv name and feed change in one commit.

## 7. stats (DEC-07)

### Data available today
- `attempts.jsonl` v1 schema: `_CLAIM_FIELDS` + `outcome` (`MATCHED`, `PARTIAL`, `GAVE_UP`), `abort_reason` (`None`, `lint`, `timeout`, `guardrail`, `tool`), `turns`, `tokens` {`input`,`output`,`cache_read`,`cache_creation`}, `cost_usd`, `seconds`, `model`, `cli_version`, `check` {`runs`,`best_percent`,`sweep_hit`,`needs`}, `pack_bytes`, `truncated`, `date`; `abort` and `run` kinds (driver.py:322-378). `validate_record` demands the exact key set (393-412) and `test_committed_log_follows_the_schema` validates every committed line (tests/test_attempts_schema.py:45-50).
- Log contents: 42 records, one run `20261026-005209`: 40 attempts (3 MATCHED, 37 PARTIAL; 3 with abort_reason `lint`), STARTED, ENDED `max sessions` 40/3.
- Function size: `functions.csv` start/end; matched set: status.csv (5 matched rows today: tacp 0x00055080 attempts 0, 0x0006EE30 attempts 1; ufo2p 0x0008A0E0 attempts 1, 0x0008A100 attempts 2, 0x000A3980 attempts 0).
- Trailers: the 3 pilot match commits (c83cf4e, d288ad6, 955931f) carry `Matched-By: reverseapoc drive` (driver.py:98); the Phase 5 hand matches (5ab2e79, a463163) and the status seed (fc7d1cd) carry none.
- Hook blocks: only in the gitignored transcripts (`permission_denials`, 41 in 40 sessions).

### Missing, and where it comes from
| Metric | Source to add |
|---|---|
| hook blocks per attempt | `hook_blocks` = len(result.permission_denials) in the v2 record (section 3) |
| regressions the gate stopped | `gate` object in the v2 record: `{"exit", "claimed_ok", "regressions", "problems"}` from the gate JSON (`checks[].functions` of previously matched starts that now fail, `problems`, splice ok) |
| per-model split | `model` exists; add `model_requested` and `budget_usd` |
| matching vs readability | `session` (`matching` / `readability`) in v2; readability outcomes need their own enum (proposal: `LANDED`, `PARTIAL`, `REFUSED`, `GAVE_UP`) |
| pass / escalation | `pass` |
| human-hints | trailer `Match-Hints: <reason>` on drive commits with owner input (D-13: owner-approved flags), since manual-pack notes live in gitignored `build/driver/manual/` and cannot be read in CI |

### Rules
- **Schema evolution:** v1 lines stay valid; v2 lines carry `"schema": 2` and validate against the v2 key set (`RECORD_FIELDS` keyed by kind and version). stats refuses (exit 2, naming the line number) any line that is not JSON, not an object, or fails its version's `validate_record` (ROADMAP Phase 7 SC6).
- **Match classing:** walk `git log --format=%H%x00%B -- config/ufo2p/status.csv config/tacp/status.csv`, diff each commit's tables with its parent, and take the starts that become `matched` in that commit; class by that commit's trailers: `Matched-By: reverseapoc drive` without `Match-Hints` -> `unattended`; with `Match-Hints` -> `human-hints`; no `Matched-By` -> `human-written`. Today: 3 unattended, 2 human-written. AGT-11 is the unattended count (3/10).
- **Turns caveat:** `num_turns` exceeded `--max-turns 40` in 30 of 40 pilot sessions (max 75) while only 14 ended `error_max_turns`: the CLI counts turns differently from the cap, so stats must not assume turns <= 40.

## 8. Nightly totals (DEC-06) and AGT-11

Today a run record holds `sessions`, `matched`, `checks_failed`, `uncommitted`, `detail` (driver.py:361-372); the only nightly totals are those two counts. Add to the v2 ENDED/STOPPED record a `totals` object: `workers`, counted `sessions` by outcome, `turns`, the four token classes, `cost_usd`, session `seconds` and night wall `seconds`, `hook_blocks`, `regressions_stopped`, `limit_waits` {count, seconds}, `aborts`, and the same per `model` and per `session` kind; plus `recovered` claims on STARTED. AGT-11 stays a stats figure derived from git (no counter in the driver to drift).

## Research findings that touch locked decisions

1. **D-06 "the only C file it may edit" is `src/<exe>/<unit>.c`.** Concurrent sessions editing `src/` directly cannot be gated correctly in one checkout (section 1). Proposal: the session edits a private copy in its attempt view under `build/`; the driver lands it into `src/` under the lock. The claim stays a whole unit. Alternative: Design F (gate gets a HEAD-view mode), costlier and it changes the gate's trust rule. **Owner rules.**
2. **D-19 "hooks block agent edits of shared headers" vs Phase 6's "a new include/*.h" allowance.** Recommend that matching sessions write no headers at all (types stay local to the unit; shared types arrive by `header` proposals). Removes collisions. **Owner rules.**
3. **D-07 `--max-turns 40` kept:** the cap did not bound `num_turns` (finding 7); informational.
4. **D-07 night cap vs `--target-matched 10`:** the Phase 6 default would end Phase 7 nights early (Q4).
5. **D-10 Fable cap:** proposed 12.50; owner confirms.
6. **D-09:** Fable acceptance by CLI 2.1.308 and the exact init `model` string are unverified; needs one owner-run canary on Fable before the first Fable pass.
7. **Variety rule (Phase 6 D-10)** would throttle tier work in dense units; recommend switching it off for tier queues. Owner call.

## Risks and open questions

- **R1 Check time grows with matched units.** Every check compiles every committed unit of both EXEs (check.py:1032-1040) and the wrapper's run limit is `CHECK_TIMEOUT = 580` s (attempt.py:49). Three concurrent checks plus a gate on Docker Desktop multiply that. Measure a check's wall time per committed unit early; if needed, add a content-addressed object cache keyed by the provenance stamp (source, flags, headers; compiler.py:739-770) so views reuse HEAD objects.
- **R2 Git index contention.** Set `GIT_OPTIONAL_LOCKS=0` in the driver's git env and in every session env (Claude Code runs git status at startup [ASSUMED]); route all driver git calls through one lock; retry `git add/commit` once on an `index.lock` error before `_undo_match`.
- **R3 Partial gates write status.csv** (gate.py:814): they must run under the same lock as the matching gate, and the pre-gate restore must cover only status.csv and the feed, never the log; the MATCHED record append and its commit happen inside the lock.
- **R4 Breach blast radius:** with N sessions, a pinned-file or fingerprint change cannot be attributed; the night stops for all. Acceptable, but it must kill and contain every live session, not only the one being judged.
- **R5 `_commit_log` at night end** commits the log and both status tables; with workers it must run after all workers have drained.
- **Q1** Does the owner accept private views (finding 1)?
- **Q2** Fable cap value (finding 5).
- **Q3** Does the readability kind commit when the gate passes but readlint still fails on the unit (improvement), or only on a readlint pass?
- **Q4** `--target-matched` for Phase 7: keep 10, raise, or off?
- **Q5** Should a rename wait for live claims (safe, can stall) or preempt by rewriting the private units of live sessions at landing (the proposal does the latter for landing only)?

## Interfaces other slices depend on

- **From slice 1 (needed here):** for each signed-off tier, the member keys `(exe, start)`, the intra-EXE call edges among them (direct calls; indirect/jump-table edges flagged), and a sign-off flag. API sketch: `mechanics.load(path) -> Mechanics` with `tiers_signed()`, `members(tier) -> frozenset[Key]`, `callees(key) -> frozenset[Key]`. The driver computes the SCC order itself.
- **For slice 3:** the compile-root fix (section 1 point 3) is a prerequisite for whole-unit re-gates under proposed per-unit flags and for `gate --partial` under a unit rule; the view layout (`view/src`, `view/config/cflags.txt`) is the natural place to try a proposed rule without touching `config/cflags.txt`. readlint is called by the driver after a readability session's gate on `src/<exe>/<unit>.c` and needs the renamed-aware name set (symbols.csv C names). The progress coverage page reads status.csv names, which become linker names after renames (strip the convention for display).
- **For Phase 8 / skills:** the proposal ops and the view-path wording go into `watcom-decomp` (which today says the claimed file is `src/<exe>/<unit>.c`, SKILL.md:3, 15, 85) and the readability skill, through `superpowers:writing-skills`.

## Validation ideas (no game files, stand-in claude)

- **Concurrency harness:** extend `tests/fakeclaude.py` with `--write-env-unit` (writes the file named by `REVERSEAPOC_UNIT_FILE`) and `--sleep`; run `drive` with `--workers 3` against the existing tmp-repo fixture (`tests/test_driver.py` `_make_repo`, `Night`) with a fake gate that asserts, at call time, that `src/` differs from HEAD in exactly the landing unit. Cases: two workers never hold the same unit (claim file O_EXCL); a broken private unit in worker B never reaches A's gate; gate calls never overlap (fake gate records enter/exit timestamps under a barrier).
- **Ledger and audit:** a fake session that edits a tracked file outside its view stops the night and is attributed; a fake session editing another session's view is caught by the view hash check; records appended by worker B during A's failed gate survive.
- **Limits:** one fake LIMIT session pauses launches on all workers; exactly one probe launches after the backoff; the night cap of 60 holds across workers with uncounted sessions released.
- **Claims recovery:** a leftover claim from another run with a free drive.lock is moved to stale-claims and recorded; a held drive.lock refuses a second drive.
- **Escalation:** synthetic attempts.jsonl with two capped Opus passes makes the next argv carry `--model claude-fable-5-1` and `--max-budget-usd 12.50`; init check accepts the requested model and rejects the other.
- **Rename:** symbols.c_name tests; configure D-12 with a renamed row; drift test by start; end-to-end rename on a tmp repo with a fake gate.
- **stats:** malformed line -> exit 2 with the line number; synthetic git history with a trailer-less match -> `human-written`; `Match-Hints` -> `human-hints`; v1 and v2 lines read together.
- **Compile root:** a tmp tree under `build/` with a per-unit cflags rule compiles under that rule (unit test with a fake compile_fn capturing `root`).

## Assumptions log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | NTFS O_EXCL create is atomic; rename-over is not a safe "first wins" | 2 | claim races; low (the code base already relies on O_EXCL) |
| A2 | `os.kill(pid, 0)` on Windows terminates the process | 2 | only matters if someone adds PID probing |
| A3 | CLI 2.1.308 accepts `claude-fable-5-1` and its init reports that exact ID | 4 | first Fable session STOPs the night; owner canary catches it |
| A4 | Fable spends subscription limits faster than Opus | 4, 5 | more LIMIT pauses on Fable passes |
| A5 | Claude Code runs `git status` at session start | R2 | index.lock races; mitigated by GIT_OPTIONAL_LOCKS anyway |
| A6 | Cache writes priced 1.25x input (5-minute TTL) | 4 | Fable cap arithmetic shifts by a few percent |

## Sources

- Code and data in this repository, read this session (file:line cited inline).
- claude-api skill (bundled 2.1.310), model table cached 2026-10-06: Opus 5.5 and Fable 5.1 prices and cache-read prices.
