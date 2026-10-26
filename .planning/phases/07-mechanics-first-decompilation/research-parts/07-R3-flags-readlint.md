# Phase 7 research, slice 3 of 3: compiler-flag proposals, readlint, progress coverage page

**Researched:** 2026-10-26
**Scope:** D-12..D-16, D-20, D-21; DEC-04 (all of it); DEC-05 (the page); backlog 999.2 and 999.4; the flag-rule machinery DEC-03 and AGT-11 rely on.
**Method:** I read the code (file:line below) and ran three throwaway scripts over `progress/attempts.jsonl` and the gitignored pilot attempt directories. The scripts printed names, paths, percentages and hashes only. Nothing was compiled and no container was started.
**Confidence:** HIGH on how the code behaves today (read this session). MEDIUM on the designs I propose. LOW where a line is tagged `[ASSUMED]`.

No #997 tick-rate or training-rule evidence came up in this slice.

---

## Summary

1. **The re-gate can run without touching `config/cflags.txt`, but one bug has to be fixed first.**
   - `check` and `gate` both take `--cflags FILE`. A check run with a non-default cflags file compiles every unit of both EXEs into `build/check-custom/`, lands them all and compares both SHA-1s. [VERIFIED: tools/reverseapoc/check.py:229-240, 1118-1155; cli.py:949, 1095]
   - So a whole-unit re-gate is: build a temporary cflags file (the committed rules plus the one proposed rule), run `check_unit` with it, then run gate's cross-check.
   - The bug: the compiler picks a source's rule from the source's path relative to the repository root (`compiler.source_rule` → `_root_relative`; `check._compile` passes no root). [VERIFIED: compiler.py:273-283, 662-673; check.py:255-261] A unit file kept anywhere other than `src/<exe>/<unit>.c` (a saved attempt, or a copy of `src/`) only ever matches the `*` rule.
   - This already affects `gate --partial --src build/driver/.../best/<unit>.c`. Once per-unit rules exist, those partial scores would be measured under the wrong flags.
2. **`gate EXE/UNIT --cflags OTHER` writes `matched` rows under flags that are not committed.** `gate_units` refuses a non-default `--src` (`_committed_src`) but passes `--cflags` straight to `check`. [VERIFIED: gate.py:141-146, 242-247, 548-559, 470-480] This is a hole in D-12's "nothing lands without owner-approved flags". Close it before the proposal tool exists.
3. **The pilot sweep-hit list re-derived from `attempts.jsonl` is exactly the 6 functions D-13 names.**
   - func_0008A100 is the only hit that later matched.
   - None of the 6 units holds a matched function today.
   - Two facts change D-13's plan:
     - In 5 of the 6 cases, the driver's saved "best" C (`best/<unit>.c`) is **not** the C that hit. The driver saves the best *plain* check and never a sweep's C. [VERIFIED: driver.py:662-686]
     - Every C file that hit also defines a **second function** (the next row of the unit). That function scored 1-69% under the default rule, and the sweep never measured it under the hit flags. A whole-unit check of the file as it stands would therefore fail unless that second function also matches.
4. **A single sweep hit is weak evidence.**
   - All 6 hits are 32-48-byte functions.
   - func_0008A100 had 12 cells at 100% with one C file, then matched under the default with a different C file. That matched C does **not** match at `-4r -ot` or `-4r -oneatx` (75.0%, docs/toolchain.md:205).
   - `-4r -oneatx` reproduces all 6 pilot hits; `-ot` reproduces only 3 of them.
5. **readlint** can be a stdlib tokenizer layered on configure.py's translation-phase normaliser and `#if 0` rules.
   - It must find definitions by *any* identifier. The existing D-12 parser (`_DEFINITION`, `source_marks`) only sees `func_XXXXXXXX` names. [VERIFIED: configure.py:238-242, 404-413]
   - Every matched unit in `src/` fails today: placeholder names, header comments missing or without the checkable fields, and the bare literal `3` in u_00089980.
   - The readability pass leaves units unnamed between a match and their naming, so `readlint src/` cannot be a gate on every commit during Phase 7. It needs a tier/unit selector and a report-only mode.
6. **Progress page.**
   - The per-item coverage goes in a separate `mechanics` derivation, so gate's feed derivation never depends on `mechanics.toml`. It reads the file with `tomllib`, which is in the stdlib from 3.11, so the Pages runner's `python3 -I` can run it.
   - 999.4 can be fixed in CSS/HTML only, with no script:
     - the mosaic scrolls sideways in a focusable region;
     - an HTML legend sits above the mosaic;
     - a `<details>` list of matched and partial functions replaces the `title`-only tooltips;
     - a 2 px minimum width on a non-zero bar.
   - Several page tests assert exact strings and must change with it.

---

## Q1. Flag-proposal queue and whole-unit re-gate

### What the code does today

| Piece | Behaviour | Evidence |
|---|---|---|
| Rule format | `<glob>  <compiler>@<version>  <flags...>`. The first rule must be `*`; the **last** matching rule wins; globs use fnmatchcase on the repo-relative POSIX path (`*` crosses `/`). Each flag must match `-[A-Za-z0-9_=.+]+`, hold no second `-`, and not be wrapper-owned (`-zq -zld -bt -fo -fr -fi -fh -ad -i`, in any case). | config/cflags.txt:4-21; cflags.py:28-36, 66-90, 152-163 |
| cc wrapper | `compile_source(src, obj, cflags=..., root=REPO_ROOT)` picks the rule by `src`'s path relative to `root` and writes a provenance stamp holding `cflags_sha256`. | compiler.py:608-643, 662-673, 686-689 |
| ninja | `rule cc: uv run reverseapoc cc $in -o $out`. `config/cflags.txt` is an implicit input (`CC_CONFIG`), so any edit rebuilds every object. A per-unit rule needs no configure.py change: it reaches the build through the same file. | configure.py:89-90, 134 |
| `check` | `check EXE/UNIT [--cflags F]`. With a non-default F, outputs go to `build/check-custom/` (WR-01) and `land_all` compiles **every** unit of both EXEs with the same options before comparing both SHA-1s. | check.py:27-40, 229-240, 1118-1155, 1060-1090 |
| Exit codes | 0 only when every function the unit defines scores objdiff 100.0, passes the relocation check and the byte compare, and both splices are SHA-1 identical with nothing refused. | check.py:22-25 |
| Sweep (D-17) | 3 versions × `-4r`/`-5r` × {none, `-ox`, `-os`, `-ot`, `-oneatx`} × `-s -fpi`: 30 cells, or 60 when `-s` is toggled for a `__CHK` caller. Each cell compiles with a temporary one-rule `*` cflags file under `build/sweep/<exe>/<unit>/` and **measures only the swept function**. It never lands and refuses to write over `DEFAULT_CFLAGS` (T-05-38). | check.py:1160-1176, 1275-1306, 1317-1357 |
| Sweep hit | A cell with `objdiff_percent == 100.0`, `reloc_ok is True`, `differing == 0` and a spec other than the unit's own rule. The **first** such cell (in cell order) becomes `sweep_hit`. | attempt.py:315-317, 327-339, 342-345 |
| Driver | Logs only the first `sweep_hit` string per attempt, plus `needs`. `best_source` is the best **plain** check. | driver.py:625-638, 662-686 |
| `gate` | `gate_units` refuses a non-default `--src`, but `--cflags`, `--watcom-manifest` and `--watcom-dir` reach `check` unchanged, and **matched rows are written**. `gate --all` accepts them too and writes nothing. | gate.py:141-151, 242-247, 548-600, 685-726 |
| Hooks | The always layer protects `config/targets.toml`, `config/watcom.toml` and `*.sha1`, but **not** `config/cflags.txt`. A matching session is blocked from cflags.txt only because the matching layer denies everything except its unit, a new `include/*.h` and its notes. | hooks.py:67-75, 15-24 |
| Attempt wrapper | No agent argument chooses flags. `ATTEMPT_FORMS` are `check`, `check --sweep`, `asm`, `asm <NAME>` and `context`, and a test refuses `--cflags`. | attempt.py:1-18; hooks.py:105-111; tests/test_attempt_wrapper.py:505 |

**Can a unit be evaluated under proposed flags without editing cflags.txt?** Yes: run `check EXE/UNIT --cflags build/flags/<id>/cflags.txt`. [VERIFIED: check.py:1118-1155] Two conditions apply:

- **(a)** The candidate C must sit at its real path `src/<exe>/<unit>.c`. A per-unit glob only matches there (Summary point 1), and other units' per-unit rules only match their real paths too. If the candidate lived in a copy of `src/` under `build/`, `land_all` would compile every ruled unit with `*`, and the SHA-1s would fail for reasons unrelated to the proposal. [VERIFIED: compiler.py:273-283, check.py:255-261, 1032-1040]
- **(b)** `check` alone does not run gate's cross-check (D-24). That check catches a matched row that is no longer landed.

### Recommendation: fix how rules are selected first (one small plan, TDD)

**Pick the rule by the unit's logical path, not its physical path.**
- Add a keyword `rule_path: str | None` to `compile_source`/`source_rule`, defaulting to today's behaviour.
- `check._compile` passes `f"src/{stem}/{unit}.c"` whenever it compiles a unit file. The include root stays `REPO_ROOT`.
- This fixes `gate --partial` and lets the re-gate use a copy of `src/` under `build/flags/<id>/src/` without writing into the shared checkout's `src/`. That matters with D-06's N concurrent sessions.
- Tests:
  - a saved attempt under `build/driver/...` compiles with its unit's rule, not `*`;
  - the provenance stamp for ninja's objects is unchanged.
- Alternative if the planner wants no compiler change: the re-gate writes the candidate into `src/` under the unit claim (slice 2) and the gate lock, and restores the original afterwards. I do not recommend it: it is more moving parts in a shared checkout.

**Close the gate hole.**
- `gate EXE/UNIT` in write mode refuses a non-default `--cflags`, `--watcom-manifest` or `--watcom-dir` with a CheckError, the same way `_committed_src` refuses `--src`.
- `gate --all` keeps accepting them: it writes nothing, and D-14 needs it as the dry-run proof (Q4).
- Negative test: `gate ufo2p/u_x --cflags tmp.txt` exits 2 and writes no row.

### Recommendation: the queue file `config/cflags-proposals.toml`

Committed, with no game bytes: names, addresses, flag strings, repo-relative paths under `build/`, SHA-256 hex, percentages and dates. Read with `tomllib`; written by a small deterministic writer (a fixed key order; string values emitted with `json.dumps`, which is valid TOML for ASCII), and round-trip tested. TOML matches `config/mechanics.toml`. [ASSUMED: slice 1 picks TOML; the file name is fixed by CONTEXT]

```toml
# config/cflags-proposals.toml: proposed per-unit cflags rules (D-12). Written only by
# `reverseapoc flags`; config/cflags.txt changes only through `reverseapoc flags approve`.
version = 1

[[proposal]]
id = "F-0001"                        # sequential, never reused
exe = "ufo2p"
unit = "u_00060c50"
glob = "src/ufo2p/u_00060c50.c"      # always the exact unit path, never a wildcard
rule = "wcc386@10.6 -4r -ot -s -fpi" # what goes after the glob in cflags.txt
base = "wcc386@10.6 -4r -s -fpi"     # the unit's rule when proposed
functions = ["func_00061F30"]        # functions that match only under `rule`
keeps = []                           # matched functions of the unit the re-gate re-proved
alternatives = ["wcc386@10.6 -4r -oneatx -s -fpi"]  # other cells at 100% for every function
source = "sweep"                     # sweep | sweep2 | owner
candidate = "build/flags/F-0001/u_00060c50.c"        # gitignored copy of the hitting C
candidate_sha256 = "<64 hex, LF-normalised>"
evidence = ["build/driver/20261026-005209/ufo2p/func_00061F30/attempt-3/checks/0025.json"]
status = "proposed"                  # proposed | regated | failed | approved | landed | rejected | superseded
regate_exit = -1                     # -1 not run; else check's exit code
regate_cflags_sha256 = ""            # sha of the committed cflags.txt the re-gate was built on
regate_log = ""                      # build/flags/F-0001/regate.json
approved_by = ""
approved_date = ""
landed_commit = ""
```

- **One open proposal per unit.** A second hit in the same unit is merged into that proposal:
  - `rule` becomes a flag set in the **intersection** of every function's 100% cells;
  - ties go to the fewest flags, then the lowest cell number;
  - when the intersection is empty, the status is `failed` with a reason.
- **Read every cell, not just the first hit.** The intersection needs each function's full list of 100% cells, and the attempt's `checks/NNNN.json` holds them (`cells[*]`). The `sweep_hit` string in attempts.jsonl holds only the first hit.
- **Who writes the file.** The proposal-maker (the driver after a session, or the `flags propose` verb) writes the queue. Agents never do: the matching layer already denies it by default.

### Recommendation: the verbs (`reverseapoc flags ...`, one module `tools/reverseapoc/flags.py`)

| Verb | Runs where | What it does |
|---|---|---|
| `flags propose --from-attempts [RUN]` | host | Scans attempt dirs for sweep lines that have a hit. Copies the hitting snapshot `checks/NNNN.c` (not `best/`) to `build/flags/<id>/`, records its sha, and adds or merges a proposal. Idempotent; reads `attempts.jsonl` for the D-16 list. |
| `flags regate ID [ID...]` | container (needs objdiff-cli) | 1. Writes `build/flags/<id>/cflags.txt`: the committed text plus one `glob  rule  # F-0001 (proposed)` line, validated with `parse_cflags` and refused if it resolves to `DEFAULT_CFLAGS` (reuse the T-05-38 guard).<br>2. Builds `build/flags/<id>/src/` as a copy of `src/` with the candidate in place of the unit.<br>3. Runs `check_unit(..., src_root=<copy>, cflags=<tmp>)`, which needs the rule-path fix.<br>4. Runs `cross_check(splices, matched_from_status_csv, defined={new functions})`, exactly as `gate_units` does.<br>5. If the check fails only because a co-defined function is not at 100%, retries with that function turned back into `INCLUDE_ASM(func_X);` (the reduced variant) and records which variant passed.<br>6. Writes `regate_exit`, `regate_cflags_sha256` and the log path. Writes nothing in `src/` or `config/cflags.txt`. |
| `flags approve ID [ID...] --by NAME` | container, **owner-run** at a blocking-human checkpoint | For each ID in order:<br>- refuses unless `status = "regated"` and `regate_exit = 0`, the candidate's sha is unchanged, and `regate_cflags_sha256` equals today's cflags.txt sha (otherwise re-run regate);<br>- refuses if `REVERSEAPOC_CLAIM` is set (inside a matching session) or if two IDs share a unit;<br>- appends the rule to cflags.txt (`write_atomic`) with a trailing `# F-0001 approved NAME DATE`;<br>- copies the candidate into `src/<exe>/<unit>.c` under the unit claim and the gate lock (slice 2);<br>- runs `gate_units([(exe, unit)])` with the committed cflags;<br>- on failure, restores cflags.txt and the unit file and marks `failed`;<br>- on success, marks `approved` and prints the commit message to use.<br>One commit per proposal: rule + C + status.csv + feed + queue row, with a trailer such as `Flags-Approved-By: NAME (F-0001, DATE)` next to `Matched-By:`. stats classifies it (slice 2). |
| `flags list [--json]` | host | Shows the queue for review: function, unit, rule, alternatives, evidence and re-gate status. |

- **Why per-unit approvals compose in a batch.** Each rule names one exact unit path, and a batch never touches the same unit twice. A proposal whose re-gate ran on an older cflags.txt is therefore still sound after earlier approvals in the batch. The `regate_cflags_sha256` check still forces a re-run when the committed file changed in between; the approve step's `gate` proves it again anyway.
- **What the re-gate proves.** Every function the unit defines matches under the proposed rule, and the unit's already-matched functions are among them, because `check_unit` checks every defined function. Every other unit is compiled with its unchanged committed rule, and both EXEs land SHA-1 identical. The cross-check adds that no matched row was dropped. That is all of D-12's re-gate.
- **Hooks.**
  - Add `config/cflags.txt` to the always layer's `_PROTECTED_FILES`. D-12 says "the hooks keep blocking it", but today only matching sessions are blocked; a GSD executor's Edit/Write is not.
  - The approve verb writes from Python, so hooks never see it. Its guard is the owner checkpoint plus the `REVERSEAPOC_CLAIM` refusal.
  - Readability sessions (slice 2) must not get cflags.txt or the queue in their allowlist.

---

## Q2. The pilot sweep hits (D-13, D-16)

Re-derived by `pilot_hits.py`, `hit_marks.py` and `neighbor.py` in the scratchpad (`C:\Users\Ayrton\AppData\Local\Temp\claude\c--Users-Ayrton-Documents-Gitprojects-ReverseApoc\17a94130-d386-485e-bd6f-517f62527b62\scratchpad\`). [VERIFIED: progress/attempts.jsonl, 40 attempt lines, 15 functions]

- **Matched:** ufo2p func_0008A0E0, func_0008A100; tacp func_0006EE30.
- **Any sweep hit:** 7 functions. The 6 that never matched are the D-13 list; func_0008A100 hit and later matched.

For every row below I opened the hit's `checks/NNNN.json` and confirmed each listed cell is `status = measured`, `objdiff_percent = 100.0`, `reloc_ok = true`, `differing = 0`.

| EXE | Function (row bytes) | Unit (game rows) | Hitting C, all under `build/driver/20261026-005209/<exe>/<func>/` | Cells at 100% | Matched fns in unit (status.csv) | Other partial rows in unit |
|---|---|---|---|---|---|---|
| ufo2p | func_00026FD0 (32) | u_00026dd0 (8) | `attempt-3/checks/0005.c` (`best/` differs) | 5, 15, 25 (`-4r -oneatx`, all 3 versions) | none | none |
| ufo2p | func_0004DFD0 (32) | u_0004dfd0 (3) | `attempt-3/checks/0002.c` (the same as `best/u_0004dfd0.c`) | 4, 5, 14, 15, 24, 25 (`-ot` and `-oneatx`) | none | func_0004DFF0 (33.19) |
| ufo2p | func_00061F30 (32) | u_00060c50 (16) | 6 snapshots: `attempt-1/checks/0009.c`, `0019.c`; `attempt-2/checks/0002.c`, `0019.c`; `attempt-3/checks/0010.c`, `0025.c` (all differ from `best/`) | 4, 5, 14, 15, 24, 25 | none | func_00061F50 (46.45), func_00061FA0 (67.50) |
| ufo2p | func_0009C3A0 (32) | u_0009c1a0 (11 + 3 data-in-code) | `attempt-1/checks/0007.c`, `attempt-2/checks/0004.c` | 5, 15, 25 (`-oneatx` only) | none | none |
| tacp | func_000779C0 (32) | u_000778d0 (12) | `attempt-1/checks/0003.c`, `0008.c` | 4, 5, 14, 15, 24 (11.0 `-oneatx` not at 100) | none | none |
| tacp | func_0006FBD0 (48) | u_0006fbd0 (3) | `attempt-2/checks/0021.c`, `0025.c`; `attempt-3/checks/0008.c` | 5, 15, 25 (`-oneatx` only) | none | none |
| ufo2p (control) | func_0008A100 (27) | u_00089980 | `attempt-1/checks/0004.c` | 12 cells: `-ot` and `-oneatx` at **both** `-4r` and `-5r`, all versions | func_0008A0E0, func_0008A100 | none |

Findings that change how D-13 is carried out:

1. **Use the hitting snapshot, not `best/`.** `best/` is the best plain check (driver.py:662-686). It differs from the hitting C for 5 of the 6 functions; only func_0004DFD0 coincides.
2. **Every hitting file defines two functions: the target and the next row of its unit.** (`hit_marks.py`, via `check.source_marks`; names only below.)
   - The second functions: func_00026FF0, func_0004DFF0, func_00061F50, func_0009C3C0, func_000779E0, func_0006FC00.
   - The same C under the default rule scored between 1.03% and 68.95% for them, with reloc FAILED (`neighbor.py` matched same-hash plain checks).
   - Their score under the hit flags was never measured, because the sweep measures only the claimed function.
   - So `flags regate` must try the file as written first (the second function may match too, a bonus match), then the reduced variant.
   - The reduced variant may itself change the target's code if Watcom used the same-module definition. The check decides. [ASSUMED: Watcom's intra-module call knowledge can change caller codegen]
3. **None of the 6 units has a matched function,** so `keeps` is empty for all six. The new rule has nothing to keep matching today, but it **binds future matches in the unit**. u_00060c50 has two more partial functions (46.45%, 67.50%) that were scored under the default. After an `-ot` rule lands, they must match under `-ot` or the unit is mis-cut. Units are drafts (units.csv header "a draft (D-11), re-cut by hand when a unit is wrong").
4. **func_0008A100 shows a single hit decides little.**
   - One C file hit under 12 cells. A different C file then matched under the default, and *that* C misses at `-4r -ot`/`-oneatx` (75.0) but reaches 100 at `-5r` (docs/toolchain.md:205).
   - For 27-48-byte functions, several (C, flags) pairs give the same bytes.
   - Treat a hit as "this unit *can* match under F", not "the original used F".
   - Stronger evidence:
     - the same hit across independently written C (func_00061F30 hit in 6 snapshots across 3 sessions; func_00026FD0 in only 1, and a later snapshot of the same session did not hit);
     - larger functions with branches or loops;
     - agreement across units in different regions.
   - This matters for D-14 more than for D-12: a per-unit rule is reversible, but a default flip is not.
5. **objdiff 100% alone is not a hit.** func_0009C3A0 `attempt-1/checks/0006.json` has 6 cells at objdiff 100.0 with `reloc_ok = false`, `differing = 1`. The wrapper's predicate rightly ignores them. (This is spike 005's blind spot again.)
6. The domain note in CONTEXT says "6 matched at phase start". status.csv holds **5** matched rows (ufo2p 0x0008A0E0, 0x0008A100, 0x000A3980; tacp 0x00055080, 0x0006EE30), and docs/toolchain.md:214 says "All five". This is a minor wording fix.

---

## Q3. Second-stage sweep (D-15)

- **Accepted flag syntax:** every candidate in D-15 passes `_SAFE_FLAG` and none is wrapper-owned. `-od`, `-of+`, `-or`, `-oi`, `-om`, `-ol`, `-on`, `-op`, `-omiler`, `-zp1/2/4/8`, `-zm`, `-fp3` and `-fp5` all match `-[A-Za-z0-9_=.+]+`, and `+` is allowed. KKND's set is written as two flags, `-of+ -omiler`. [VERIFIED: cflags.py:32-36, 66-90]
- **Candidate list:** docs/toolchain.md:228-242.
  - `-od` disables all optimisation. [CITED: wcc386 usage text, https://mikrocontroller.net/topic/491868]
  - What the default optimisation is when no `-o` is given is unverified. [ASSUMED]
- **Cost per cell, from the object mtimes:** 30 cells took 10-11 s in 12 of 13 sweep dirs and 25 s in one (`build/sweep/*/*/cell-NN.o`), so about 0.35-0.85 s per cell for compile + omf2elf + objdiff. Container start and EXE load are paid once per run. [VERIFIED: ls of build/sweep]

**Bounded design, ≤ 24 cells, about 10-20 s.** The version is fixed at 10.6, because stage 1 never separated versions in any pilot sweep. The CPU and stack flag are taken from stage 1's best cell. Stage 2 runs **only** when no stage-1 cell hits and the best cell reaches ≥ 90.0 with reloc ok (rank as `SweepCell.rank`).

| Group | Cells | Flags (CPU and `-s -fpi` from stage 1's best) |
|---|---|---|
| O1: replace the `-o` set | 9 | `-od`; `-of+`; `-or`; `-oi`; `-om`; `-ol`; `-on`; `-op`; `-of+ -omiler` |
| O2: add one letter to the best stage-1 `-o` set | ≤ 8 | best set + each of the 8 letters, skipping letters the set already holds |
| Z: packing | 4 | best + `-zp1` / `-zp2` / `-zp4` / `-zp8` |
| M: segment per function | 1 | best + `-zm` |
| F: FP scheduling | 2 | best + `-fp3` / `-fp5` |

Implementation:
- `check.sweep2_cells(best: SweepCell)` beside `sweep_cells`; same `_measure` and same temporary-rule guard.
- The `SweepReport` JSON gains `stage2: {...}` with its own cells.
- The wrapper's `_sweep_line` looks for a hit in stage 1 first, then stage 2.
- No new `ATTEMPT_FORMS` entry: stage 2 runs inside the same `attempt check --sweep`. That keeps D-15's "the wrapper still never lets an agent choose flags" true, and keeps the agent's command surface fixed.
- **Before including `-zm`, spike it:** each function lands in its own code segment, and `account_unit`/`defined_functions` may assume one code segment. [ASSUMED] One synthetic test in `test_check.py` with an `-zm` object settles it. If it breaks, leave `-zm` out of stage 2 and record why in toolchain.md.
- Hits feed the same queue (`source = "sweep2"`).

---

## Q4. Flipping the `*` default (D-14)

- **What is matched today, by unit:**
  - ufo2p `u_00089980` (func_0008A0E0, func_0008A100) and `u_000a34f0` (func_000A3980);
  - tacp `u_00054f20` (func_00055080) and `u_0006ee30` (func_0006EE30).
  - [VERIFIED: config/ufo2p/status.csv, config/tacp/status.csv]
- **Mechanics, all in one commit by an owner-run verb** (for example `flags default --rule "<spec flags>" --by NAME`):
  1. List every unit with `matched` rows in status.csv at that moment.
  2. Write the candidate file `build/flags/default-<date>/cflags.txt`: the new `*` line first, then the existing per-unit rules, then one pin per matched unit that has no rule yet, `src/<exe>/<unit>.c  <old * spec and flags>  # pinned by D-14`. The last matching rule wins, so the pins override the new `*`.
  3. Run `gate --all --cflags <candidate>` in the container. It re-proves every matched function and both SHA-1s and writes nothing; it already accepts `--cflags` (gate.py:685-726).
  4. Also run `gate --all` with the new `*` and **no** pins. This dry run is evidence only: it tells the owner which pins are actually needed. Evidence from the pilot: func_0008A100's matched C misses at `-4r -ot`/`-oneatx`, so `u_00089980` needs its pin under either candidate.
  5. Write cflags.txt, update the hygiene-checked docs in the same commit, and run `gate --all` again with the committed file.
- **What `gate --all` proves:**
  - each matched row is still defined in C and scores 100.0 with reloc ok and identical bytes;
  - its `source_sha256` still matches the unit file (M9);
  - the landed set equals the matched set (D-24 cross-check);
  - both EXEs are SHA-1 identical.
  - [VERIFIED: gate.py:22-27 docstring, 645-726]
  - status.csv has **no flags column**, so a flip rewrites no rows. The history of which rule matched a function lives only in git and the docs.
- **Other effects:**
  - Every object's provenance stamp changes (`cflags_sha256`), so ninja recompiles everything.
  - The CI hygiene test asserts docs/toolchain.md quotes the `*` rule whole and that docs/matching.md has a matching `*` row per EXE (tests/test_hygiene.py:221-229).
  - `_DRIFTED_RULES` lists `*  wcc386@10.6  -4r -s -oneatx` as a drifted rule (tests/test_hygiene.py:236-246). It is not the same text as an `-oneatx` default with `-fpi`, but review the list in the flip commit and add the superseded default to it.
- **Evidence for the owner's D-14 ruling as of today:** 6 never-matched functions (4 UFO2P, 2 TACP, different regions) hit under `-4r -oneatx -s -fpi` with their own C. None is re-gated yet, all are 32-48 bytes, and one matched function (func_0008A100) disagrees at `-4r`. Not decisive (Q2 point 4). Propose the flip only after per-unit re-gates land and at least 3 non-trivial functions (with branches or loops) agree.

---

## Q5. readlint (DEC-04, D-20, D-21, backlog 999.2)

### Precedent

- **Verbs** register through `_add_<verb>_command(sub)` called from the parser builder (cli.py:1389-1408); errors are listed in `_ERRORS` (cli.py:1412+).
- **The `lint` verb** (cli.py:867-880, lint.py) is the shape to copy: `paths` (default `src`), `--json`, exit 0/1, and a tool error with its own message.
- readlint is stdlib and needs no container, so CI runs it on the host.

### Scanner design (`tools/reverseapoc/readlint.py`, stdlib)

1. **Reading the source.**
   - Read strict UTF-8 bytes (`check.read_source`), then `configure.normalize_source` (trigraphs, CRLF, splices; refuses a lone CR) through `check._configure()`, as `source_marks` does.
   - Run `configure.code_text(text)` once only so it raises `_ConditionalError` for anything but `#if 0`, which readlint maps to exit 2. readlint uses its own dead-region tracking with configure's `_directive_step`, so both read `#if 0` the same way. [VERIFIED: configure.py:180-260, 316-433]
2. **Tokenizer** with 1-based line numbers. Each kind comes from one compiled regex in this order:
   - `COMMENT` (`/* ... */`; `//` is refused or flagged, since C89 has no `//`);
   - `STRING` (with escapes); `CHAR` (`'...'`);
   - `DIRECTIVE` (a logical line starting with `#`);
   - `NUMBER` (`0[xX][0-9A-Fa-f]+[uUlL]*`, `[0-9]+[uUlL]*`, floats);
   - `IDENT` (`[A-Za-z_][A-Za-z0-9_]*`);
   - `PUNCT`, longest first (`<<=`, `>>=`, `->`, `++`, `<<`, `>>`, `&&`...).
   - Tokens in a dead `#if 0` branch are dropped. Comments are kept for the header and waiver rules.
3. **Structure, a pass at brace depth.**
   - **Definition:** at depth 0, `IDENT ( ... ) {` with balanced parentheses. **Any identifier**, so renamed functions are found. configure's `_DEFINITION` only knows `func_XXXXXXXX`.
   - **Stub:** `INCLUDE_ASM ( func_XXXXXXXX ) ;` (configure's `_MARKER`). Stub tokens are exempt from every rule.
   - **Declaration start:** the token after the previous depth-0 `;` or `}`, a directive, or the start of the file. The **header comment** is the last COMMENT token between that boundary and the declaration's first token.
   - **Struct/union bodies:** `struct|union [IDENT] { ... }` at any depth; field declarators are the IDENT before `;`, `,`, `[` or `:`.
   - **Enum bodies:** `enum [IDENT] { ... }`. A literal after `=` there is a naming and is exempt.
4. **Scope.**
   - `readlint PATHS...` collects `.c` files (lint.py's `collect_sources` precedent).
   - `<exe>/<unit>` comes from `src/<exe>/<unit>.c`. A **matched unit** is one with ≥ 1 `matched` row in `config/<exe>/status.csv` whose `unit` column is that unit. Other files are reported as `skipped`.
   - Inside a matched unit, every C definition is checked. A defined function in a matched unit is matched by construction: check refuses an unmatched one, and test_drift pins the rest.
   - Headers: also scan project headers the unit includes, bare names under `include/` excluding `common.h` and `watcom_compat.h`, for the struct-field and placeholder rules. D-19's shared struct headers are where fields get named.
5. **Selectors** (see "touches locked decisions" below):
   - `--units EXE/UNIT,...`
   - `--tier N` (reads `config/mechanics.toml` members, mapping functions to units through functions.csv)
   - `--report`: exit 0 and print the counts, for nightly or `stats` use. The default is strict.
6. **Output.**
   - `path:line: RLnn message`, then a summary: files checked/skipped, violations per rule, **waiver count** per file.
   - `--json` gives the same data. Exit 0 clean, 1 violations, 2 tool error.

### Rules (each with negative tests)

| ID | Rule | Precise test |
|---|---|---|
| RL01 | Placeholder name | An IDENT token outside stubs, comments and strings fully matching `FUN_[0-9A-Fa-f]+`, `sub_[0-9A-Fa-f]+`, `DAT_[0-9A-Fa-f]+`, `func_[0-9A-F]{8}`, `D_[0-9A-F]{8}`. Also `LAB_`, `PTR_`, `UNK_` + hex. [ASSUMED: "or similar" extends to these] Applies to definitions, declarations and references alike, which is 999.2's point. |
| RL02 | Header comment missing | A definition whose preceding comment (as defined above) does not exist. |
| RL03 | Header comment malformed | The header must contain all of:<br>(a) a first text line `<name>: <purpose>`, where `<name>` equals the defined identifier and the purpose is ≥ 3 words;<br>(b) a line `Address: <EXE> 0x%08X`, where `<EXE>` is `UFO2P.EXE` or `TACP.EXE` for the unit's EXE and the address is the start of the functions.csv row the name maps to (through symbols.csv for a renamed function, or parsed from a placeholder);<br>(c) ≥ 1 line `Evidence: <kind>: <text>`, kind in {`string`, `table`, `call`, `vocab`}. `vocab` means an OpenApoc domain term (D-21); text is non-empty. Cite strings and tables by address (`string 0x0012EFAC`), so the comment holds no game text. |
| RL04 | Unnamed struct field | A field declarator matching `(?i)^(unk|unknown|field_?(0x)?[0-9a-f]*|pad|padding|gap|filler|undefined)\w*$` inside a struct/union body. |
| RL05 | Raw offset access | A cast to a pointer type `( <type tokens> * )` whose operand is a parenthesised additive expression containing an integer literal other than 0, e.g. `*(T *)(p + 0x10)`, `(T *)((char *)p + 16)`, `*(T *)(p - 4)`. |
| RL06 | Magic integer literal | A NUMBER token (integer) in live code, outside `#define` bodies (directives are not scanned for this rule), enum initialisers and stubs, is allowed only if:<br>(1) its value is 0 or 1, so `-1` is allowed too (unary minus on 1);<br>(2) **bitwise context** (an operand of `&` `\|` `^` `~` `&=` `\|=` `^=`) and the value is 2^k, 2^k−1, or the 32-bit complement of 2^k−1;<br>(3) **shift count** (the right operand of `<<` `>>` `<<=` `>>=`) with 0 < v < 32, or the left operand of a shift being 2^k;<br>(4) **sizeof-like** value 2, 4 or 8 as an operand of binary `*` `/` `+` `-` (or the compound forms) or inside `[ ]`;<br>(5) a **waiver**: a `/* ... */` comment with non-empty text on the same physical line, counted and reported.<br>Case labels, call arguments, array dimensions, return values and comparisons get no special case. Character literals are not integers (exempt). Floating literals: see Open questions. |

How "sizeof-like" and "mask/shift" are pinned:
- **By context, not by value.** A bare 2^k anywhere would let `func_00089980(4, -1)` pass. With the context rule, the `4` there fails.
- **Contiguous-run masks are deliberately not allowed in general.** `60 = 0b111100` would slip through, and tick-rate-like constants are exactly what Phase 8 needs named.

### How today's matched C fares (all fail)

| File | RL01 placeholders (outside stubs) | RL02/RL03 | RL06 | Other |
|---|---|---|---|---|
| src/ufo2p/u_000a34f0.c | func_000A3990 (prototype, call), D_0012EFAC (extern, use), func_000A3980 (definition) | Header present (`func_000A3980: calls ...`) but no `Address:`/`Evidence:` → RL03 | none | none |
| src/tacp/u_00054f20.c | func_00011500, D_0028DF70, func_00055080 | Header present, no Address/Evidence → RL03 | none | none |
| src/tacp/u_0006ee30.c | func_00071BD0, D_002E4370, func_0006EE30 | No comment before the definition → RL02 | none | `free` is a runtime name, fine |
| src/ufo2p/u_00089980.c | func_00089980, func_0008A100, func_0008A0E0, D_001A714C (block-scope extern ×1, file-scope ×1, uses) | Both definitions have a one-line `/* void: ... */` comment → RL03 ×2 | `3` (call argument) fails; `4` (call argument) fails under the context rule; `-1` and `0` pass | Definitions are not in address order (0x8A100 first): fine, check accepts it |

There are no structs or raw offsets in `src/` or `include/` today, so RL04 and RL05 are exercised only by synthetic tests.

### Pitfalls for the readability pass that readlint provokes

- **Replacing a literal can change its type, and with it the bytes.**
  - `sizeof(T)` is unsigned. `x * sizeof(long)` changes signed/unsigned arithmetic and can change `imul`/`shl`/comparisons.
  - An enum constant is `int`, while `0xFFFFFFFF` is `unsigned int`.
  - Safe replacement: a `#define` whose body keeps the literal's exact spelling and suffix. The gate re-check catches any slip, but the readability prompt should say so up front.
- **Renaming changes linker names** (D-19, slice 2). readlint must not rely on configure's placeholder-only `_DEFINITION`, and neither can test_drift, `gate._reverted` or `source_marks` once names change.

---

## Q6. Progress coverage view and 999.4

### Today

- progress.py is stdlib-only, Python 3.12 syntax (a test parses it with `feature_version=(3, 12)`, test_progress.py:106), and run as `python3 -I tools/progress.py --out _site --report build/report.json --commit SHA` by pages.yml.
- Outputs are deterministic: JSON indent 2, sorted inputs, `_write_atomic`.
- `gate` loads it by path to rewrite `decomphub.progress.json` (gate.py:393-454).
- [VERIFIED: tools/progress.py:1-41, 390-408, 1144-1191; .github/workflows/pages.yml]

### Recommendation: coverage per item

- **Separate derivation.** `derive_mechanics(config_dir, progress) -> Mechanics | None` reads `config_dir/mechanics.toml` with `tomllib`. A missing file gives `None` and the page leaves the section out, so the synthetic CI configs keep working.
  - It stays separate from `derive()`: gate's feed derivation must never fail because of mechanics.toml.
  - A malformed file is a `ProgressError` (exit 2) in the Pages job and in a drift test, never in gate.
- **Per item:** members are (exe, address) pairs. Each must be a game or thunk row of functions.csv, otherwise `ProgressError`; runtime and data-in-code rows are excluded by D-02.
  - Counts: functions matched / partial / unmatched (from status.csv, through the existing `Function` objects).
  - Bytes: total and matched, and `percent = percent(matched_bytes, total_bytes)`.
  - A function reached from several items counts in each. A per-tier row uses the **union** of members.
- **progress.json:** add `"mechanics": {"items": [...], "tiers": [...]}` (or `null`).
  - Order: tier, then issue number, then item number; all lists sorted.
  - Bump `PROGRESS_VERSION` to 2 or keep it at 1? Keep 1. No current test pins the top-level key set (test_progress.py:165-174 pins the `functions` objects only), and adding a key is backward compatible. [VERIFIED: grep of test_progress.py]
  - Item fields: `id`, `issue`, `title`, `tier`, `signed_off`, `functions{total,matched,partial,unmatched}`, `bytes{total,matched,partial}`, `percent`. Sign-off `who`/`date` come from mechanics.toml (committed), so the output stays deterministic.
- **index.html:** a `<h2>Mechanics coverage</h2>` section after the EXE sections, as a `<ul class="items">`, not a table, so it wraps at 390 px with no horizontal scroll. Each `<li>` holds:
  - the item text ("#997 tick rate");
  - the tier and its sign-off state;
  - the text figures first ("12 of 40 functions matched, 3 partial; 18.2% of their code bytes");
  - a three-segment `aria-hidden` bar (matched / partial / unmatched shares by function count), each non-zero segment at least 2 px wide.
  - Issue numbers appear as **text, not links**: `_check_static` restricts hrefs to `progress.json`, README, the workflow and the commit (test_progress_page.py:144-146). That also keeps OpenApoc out of the page's links.
- **pages.yml:** add `"config/mechanics.toml"` to `on.push.paths`, and update `test_workflows.py`'s `PATHS`.
- **The DecompHub feed:** leave it unchanged (no mechanics tracks). That keeps gate's feed and the D-22 drift test independent of mechanics.toml.

### Recommendation: the 999.4 fixes (06-UI-REVIEW.md:27-31)

1. **Tooltips** (fix #1). Per EXE, after the strip: `<details><summary>Matched and partial functions (N)</summary><ul><li>{_function_title(f)}</li>...</ul></details>`, sorted by address. The same text serves the mosaic's `<title>`s. No script, keyboard and touch work natively, and the output stays deterministic. Keep the `title` attributes as a mouse bonus.
2. **Mosaic on a phone** (fix #2).
   - Change `.mosaic{margin-top:.75rem}` to `.mosaic{margin-top:.75rem;overflow-x:auto}`.
   - Inside the existing `@media (max-width: 40rem)` block add `.mosaic svg{min-width:48rem}`.
   - Wrap the mosaic as `<div class="mosaic" tabindex="0" role="region" aria-label="Decompilation mosaic, scrolls sideways">`, so a keyboard user can scroll it (WCAG: a scrollable region must be focusable).
   - Add an HTML legend above it (`<ul class="legend">` from `LEGEND_LABELS` and `TREEMAP_COLORS`, like `STRIP_KEY`). Keep the SVG's own legend, because progress.svg is also published on its own.
   - Tests to update: test_progress_page.py:153 asserts `.mosaic svg{display:block;width:100%;height:auto}` (keep that rule), and test_page_embeds_the_mosaic asserts `'<div class="mosaic">\n{svg}</div>\n'` (update it).
3. **Percent bar** (fix #3). For a non-zero percent emit `<span class="nz" style="width:X%">`, plus CSS `.bar .nz{min-width:2px}`. Optionally light the track to the uncovered grey (06-UI-REVIEW.md:51). test_page_shape asserts the exact bar markup and needs updating. Keep `_figures` text unchanged unless the owner wants counts first, because that string is pinned in test_page_shape and test_listings.
4. **Determinism:** all new markup comes from sorted committed data, uses no clock, and stays within the page tells (no "—", "·", gradient, transition, script or code/pre tags: test_progress_page.py TELLS and FORBIDDEN_TAGS).

---

## Q7. Drift and schema tests to extend

| Test file | New case |
|---|---|
| tests/test_drift.py | (a) `config/cflags-proposals.toml` parses. Every non-`*` rule in cflags.txt is the `glob`/`rule` of exactly one proposal with status `approved` or `landed` (or carries a `# pinned by D-14` comment). Every `landed` proposal's rule is in cflags.txt. No two open proposals share a unit. Its values carry no game bytes: an allowlist of fields; hex only as 64-char sha256; paths only under `build/`.<br>(b) `config/mechanics.toml` members are game/thunk rows of functions.csv; `derive_mechanics` succeeds on the committed config. This overlaps slice 1's schema test, so coordinate.<br>(c) `test_matched_rows_equal_defined_functions` must find **renamed** definitions. Today it uses `source_marks`, which is placeholder-only (test_drift.py:21-23, 52-60). Slice 2 owns the rename, but the shared "definitions in a unit" finder is a common dependency with readlint. |
| tests/test_hygiene.py | Every non-`*` cflags rule has a docs/matching.md "Compiler and flags per module" row (extend `_matching_rule_rows` beyond `*`). The `*`-rule doc check keeps working after a D-14 flip. |
| tests/test_workflows.py | `PATHS` includes `config/mechanics.toml`. |
| tests/test_progress.py / test_progress_page.py | The `mechanics` key (shape, order, union per tier, refusal of a non-game member, absence → `null` and no section). Two renders give the same bytes. The 999.4 markup. The hrefs set is unchanged. |
| tests/test_gate.py | `gate` write mode refuses a non-default `--cflags`/`--watcom-*`; `gate --all --cflags` still runs. |
| tests/test_compiler.py / test_check.py | Rule selection by logical unit path (the fix in Q1); `gate --partial` compiles under the unit's rule. |
| tests/test_hooks.py | The always layer denies an Edit/Write of `config/cflags.txt`. |
| tests/test_readlint.py (new) | Rules RL01-RL06, the waiver count, the selectors, and exit codes. See Validation ideas. |

---

## Research findings that touch locked decisions

The owner rules on each of these; I have not changed any decision.

1. **D-13 "re-runs the saved best C".**
   - The saved best C is the best plain check, not the C that hit, for 5 of 6 functions.
   - Every hitting file also defines a second function that has not been measured under the hit flags.
   - Recommend reading D-13 as "re-runs the C that produced the 100% cell (`checks/NNNN.c` of the sweep line), as written, else with the extra function reverted to `INCLUDE_ASM`".
   - If the owner reads "best C" literally, the expected result is 1 of 6 (func_0004DFD0) with the file as written, at most.
2. **D-12 "the hooks keep blocking" cflags.txt.**
   - True only for matching sessions, through default-deny. A GSD executor's Edit of cflags.txt is not blocked.
   - Recommend adding it to the always layer.
   - Separately, `gate --cflags` can write matched rows under uncommitted flags. That has to be closed for D-12's approval step to mean anything.
3. **D-12 "a real source had one flag set, so a rule is per unit".**
   - Sound only while the unit cut is right. Units are drafts.
   - A per-unit rule binds every later match in the unit, and partial percents of sibling functions become stale under the new rule.
   - Recommend that a proposal shows the unit's other partial rows, and that the owner's approval covers them knowingly. When a sibling later needs other flags, the cue is a unit re-cut, not a second rule.
4. **D-14 evidence.**
   - The six pilot hits "agree" on `-4r -oneatx` across both EXEs, which on paper meets Phase 5 D-18's "3 agreeing functions from different regions".
   - But they are 32-48-byte functions, none is re-gated, and func_0008A100's matched C disagrees at `-4r`.
   - Recommend that the owner treats tiny-function hits as not counting toward the default (only toward per-unit rules), or requires a minimum size or a branch/loop.
5. **D-20 "readlint ... `uv run reverseapoc readlint src/` exits 0 at the phase gate for every matched unit".**
   - During the phase, every new match lands unnamed (D-17), so `readlint src/` fails between a match and its readability pass. It cannot run as a CI gate on every commit.
   - Recommend: strict at the phase gate and per tier (`--tier 1`); `--report` mode in nightly runs or stats.
   - The 4 matched units of today and any pilot-hit units that land are outside Tier 1. They need readability sessions too before the gate.
6. **D-20 placeholder rule versus references.**
   - A matched function outside Tier 1 may call or read a function or global that nobody has named yet (its callee is unmatched).
   - Strictly, RL01 fails it. D-20's "small allowlist" is the release valve.
   - Recommend a committed `config/readlint-allow.csv` (`exe,name,reason`) holding only **references** (never definitions), counted and reported like waivers. Tier 1 needs none, because its callees are all in Tier 1 by D-02.
7. **D-20 waiver form `/* reason */`.**
   - Any same-line comment counts, so an ordinary trailing comment would also act as a waiver.
   - Option A (literal reading): any non-empty same-line block comment.
   - Option B: a tag such as `/* lit: reason */` for an exact count.
   - I recommend B; the owner's wording allows either.
8. **ROADMAP SC5 "every target reads matched".** It conflicts with D-05. That rewording plan (D-05) should also define what the coverage view shows for items in tiers that are located but unmatched.

---

## Risks and open questions

- **Floating literals** (D-20 says integer literals only). Report float literals under RL06 too, or leave them out? Physics and timer code may hold float constants (#997). I recommend reporting them in `--report` mode only until the owner rules.
- **`-zm` support in check** is unverified. [ASSUMED] Spike it before adding it to stage 2.
- **Multiple 100% flag sets for one unit** (u_0004dfd0, u_00060c50 and u_000778d0 hit under both `-ot` and `-oneatx`). The intersection-plus-fewest-flags tie-break is my proposal; the owner may prefer to group units by a common rule.
- **Batch approval while the driver runs.** approve takes the unit claim and the gate lock (slice 2). If those are not in place when the flags plan lands, approve must refuse while a `drive` process is alive (PID check), or run only with the driver stopped.
- **Re-gate cost.** One whole-unit check compiles every unit of both EXEs: one `land_all`. That is fine for a handful of proposals per batch, but it is not free per sweep.
- **Rule-path fix and provenance.** `check_provenance` (ninja's land step) selects the rule with `_compile_root(src_root)`. The logical-path change must keep both sides consistent; test that a ninja object built with a per-unit rule still passes `check_provenance`.
- **Readability edits and `-zp`.** RL04 renames fields in shared headers. Renames are safe, but any layout change is not; the gate catches it. The readlint docs must not suggest adding padding fields with other names.

---

## Interfaces other slices depend on (or I depend on)

| Interface | Owner | Contract I assume or offer |
|---|---|---|
| `config/mechanics.toml` | slice 1 | I need: items with `id`, `issue`, `title`, `tier`; members as (exe, start address), or names resolvable through functions.csv/symbols.csv; the sign-off per tier (`by`, `date`). progress.py and `readlint --tier` read it with `tomllib` under Python 3.12. |
| Unit claims + gate lock | slice 2 | `flags approve` (and any regate that writes `src/`) takes the same claim and lock the driver uses. |
| Naming state / rename | slice 2 | A shared "functions a unit defines" finder that accepts symbols.csv names. readlint (RL03 Address check), test_drift, `gate._reverted` and configure's D-12 check all need it once functions are renamed. INCLUDE_ASM markers keep `func_` names (configure.py:239), so renaming an **unmatched** function would break its stub. |
| `stats` classification | slice 2 | Flag-approved matches carry `Matched-By: reverseapoc drive` plus `Flags-Approved-By: NAME (F-nnnn, date)`. D-13 says they count as `human-hints` or `unattended` per stats' rules. |
| attempts.jsonl `check` record | slice 2 (schema) | Optional new fields `sweep_source` (the hitting `checks/NNNN.c`, relative to the attempt dir) and `sweep_cells_100` (a list of flag specs), so `flags propose` need not re-read the attempt dirs. The current reader relies only on `sweep_hit`. |
| Second-stage sweep JSON | this slice → driver | `SweepReport.to_json()["stage2"]` with the same cell shape; the wrapper's `sweep_hit` covers both stages. |
| Readability session allowlist | slice 2 | Must exclude `config/cflags.txt` and `config/cflags-proposals.toml`; may include `config/readlint-allow.csv` only through the driver. |

---

## Validation ideas (all runnable without game files unless marked)

**readlint, one negative test per rule plus one positive test.** Synthetic `.c` text in `tmp_path`, plus a synthetic status.csv marking the unit matched:
- RL01: one file per pattern (`FUN_1234`, `sub_1234`, `DAT_1234`, `func_0001ABCD`, `D_0001ABCD`), as a definition, a prototype, an extern and a use. The same names inside an `INCLUDE_ASM(...)` stub, a comment, a string and a dead `#if 0` branch must **not** fail.
- RL02: a definition with no comment; a comment separated from the definition by another declaration also fails.
- RL03: the name line naming another identifier; `Address:` with the wrong EXE or address; an Evidence kind outside the set; empty evidence text.
- RL04: `struct S { int unk_4; int field_0x8; char pad[2]; int ok; };` gives 3 failures; a field `padding_end` fails; `paddle` passes.
- RL05: `*(int *)(p + 0x10)`, `(short *)((char *)p + 16)` and `*(int *)(p - 4)` fail; `*(int *)p` and `(T *)q` pass.
- RL06: `x = 36;` fails; `case 36:` fails; `f(4)` fails; `a[i * 4]` passes; `x & 0xFF` passes; `x & 0xF0` fails; `x << 3` passes; `x * 3` fails; `-1` passes; `#define TICKS 36` passes, and its use `x = TICKS;` passes; `enum { TICKS = 36 };` passes; `x = 36; /* lit: ticks per second, see header */` passes and counts 1 waiver.
- An unmatched unit (no matched row) is skipped. A file with `#ifdef` exits 2. A file with a lone CR exits 2.
- Committed tree: `readlint --report src/` exits 0 and lists the 4 current files as failing, which pins today's state; strict `readlint src/` exits 1 until the readability pass.

**Flag proposals.** Use the existing fake compile and fake objdiff runners (test_check.py patterns):
- `flags propose` over a synthetic attempt dir picks `checks/NNNN.c` of the hitting sweep line, not `best/`. It merges two hits in one unit by intersection, and marks an empty intersection `failed`.
- `flags regate` never writes `config/cflags.txt` (assert its mtime and hash are unchanged) and never writes `src/`. Its temporary cflags file is committed text plus one line, and passes `parse_cflags`. It refuses to resolve to `DEFAULT_CFLAGS`. It records exit 1 when a matched function of the unit drops below 100 under the proposed rule (fake objdiff), and exit 1 when the cross-check drops a matched row.
- `flags approve` refuses `status != regated`, a changed candidate sha, a stale `regate_cflags_sha256`, a set `REVERSEAPOC_CLAIM`, and two IDs on one unit. On a gate failure it restores cflags.txt and the unit file byte for byte.
- `gate EXE/UNIT --cflags tmp` exits 2 and writes nothing.
- Container-only (owner checkpoint): `flags regate` on the 6 pilot proposals with the real compiler; `gate --all` after each approval commit.

**Progress determinism.**
- Two `render_html` calls over the same config plus mechanics.toml give equal bytes.
- No mechanics.toml means no section and an unchanged page for the synthetic config.
- A member that is a runtime row gives `ProgressError` → exit 2.
- A function shared by two items counts in both items and once in the tier union.
- `_check_static` still passes, so no new hrefs.
- The 999.4 strings are present: `overflow-x:auto`, `min-width:48rem` inside the 40rem query, the `tabindex="0"` region, the `<details>` list with one `<li>` per matched or partial function, and `.bar .nz{min-width:2px}`.
- The pages.yml path filter includes mechanics.toml.

---

## Sources

### Primary (read this session)
- tools/reverseapoc/check.py (L1-40, 200-261, 480-537, 895-1155, 1158-1357)
- tools/reverseapoc/cflags.py (all)
- tools/reverseapoc/compiler.py (L273-283, 608-673)
- tools/reverseapoc/gate.py (L1-151, 221-390, 456-480, 545-726)
- tools/reverseapoc/attempt.py (L1-120, 306-400)
- tools/reverseapoc/driver.py (L625-686)
- tools/reverseapoc/hooks.py (L1-147)
- tools/reverseapoc/cli.py (L880-1140, 1374-1420)
- tools/reverseapoc/lint.py (L1-60)
- configure.py (L60-140, 180-440)
- tools/progress.py (L1-440, 700-1195)
- .github/workflows/pages.yml
- tests/test_drift.py, tests/test_hygiene.py (L195-300), tests/test_progress_page.py (L1-200, 400-420), tests/test_progress.py (grep), tests/test_workflows.py (L80-110)
- config/cflags.txt, config/*/status.csv, functions.csv rows of the hit functions, include/common.h, src/*/*.c
- docs/toolchain.md (L184-242), docs/matching.md (L7-14), 06-UI-REVIEW.md (L27-51), ROADMAP 999.2/999.4, REQUIREMENTS DEC-01..07, 07-CONTEXT.md
- progress/attempts.jsonl and build/driver/20261026-005209/** (via the scratchpad scripts; names, paths, percents and hashes only)

### Secondary
- [mikrocontroller.net wcc386 usage listing](https://mikrocontroller.net/topic/491868): `-od` disables all optimisations (MEDIUM; the default with no `-o` is unverified)
- [Open Watcom v2 wiki, tools usage](https://github.com/open-watcom/open-watcom-v2/wiki/OW-tools-usage-Overview) (searched, no default-optimisation statement)
- [nginx auto/cc/owc](https://nginx.googlesource.com/nginx/+/nginx/auto/cc/owc): third-party use of `-ot` as "maximize speed" (LOW)

## Assumptions log

| # | Claim | Risk if wrong |
|---|---|---|
| A1 | Slice 1 picks TOML for mechanics.toml with (exe, address) members | The progress and readlint readers need a different parser and mapping |
| A2 | Watcom's knowledge of a same-module callee can change the caller's code, so the reduced variant may lose the hit | The reduced variant may pass more often than feared (harmless) |
| A3 | `-zm` objects may break `account_unit`/`defined_functions` | Stage 2 includes or drops one cell |
| A4 | Ghidra prefixes `LAB_`/`PTR_`/`UNK_` belong under "or similar" | RL01 is slightly broader than the owner meant |
| A5 | The wcc386 default `-o` set with no `-o` flag is unknown | Only affects how stage-1/2 results are explained, not the tools |
