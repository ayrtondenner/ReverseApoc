# Phase 7: Mechanics-first decompilation - Research

**Researched:** 2026-10-26 (synthesis of three parallel slices, same day)
**Domain:** locating game mechanics in two Watcom/LE executables; a concurrent matching driver; readability tooling; flag rules; metrics; progress page
**Confidence:** HIGH for what today's code does (read line by line, load-bearing lines re-checked in this pass) and for the call-graph measurements (scripts run on the real EXEs); MEDIUM for the proposed designs (not prototyped); LOW where tagged `[ASSUMED]`

**Appendices (keep, read for depth):**
- `research-parts/07-R1-locate.md`: slice 1, locating, call graph, spike 007, `mechanics.toml` schema, item-to-entry drafts
- `research-parts/07-R2-driver.md`: slice 2, driver concurrency, claims, hooks, model escalation, renames, stats
- `research-parts/07-R3-flags-readlint.md`: slice 3, flag proposals, pilot re-prove, second-stage sweep, readlint, progress coverage, 999.4

This file holds addresses, counts, names and short identifying strings only. It contains no disassembly, no decompiled C and no table contents.

<user_constraints>
## User Constraints (from CONTEXT.md)

Copied from `07-CONTEXT.md` `<decisions>` and `<deferred>`. Where "Owner rulings after research" (D-22..D-29) disagree with an earlier decision, D-22..D-29 win (CONTEXT says so).

### Locked Decisions

#### Target list scope (DEC-01, roadmap spike)
- **D-01:** **Items.** Every checklist item of #263, #264, #265 and #997 that touches the original game is in, including the borderline ones: dynamic music #264-21, name generator #265-13, vehicle lanes #264-19/20. OpenApoc-only tooling, modding, UI-chrome and project items are out: #263-19/20/23/24, #264-1, #264-22/23, #264-29..33, #265-14..18. Items already ticked in OpenApoc are in when the original's rule or numbers are still useful (for example #263-7 diplomacy, #263-5 economy). Claude proposes the exact in/out line per tier and the owner rules on it at that tier's sign-off.
- **D-02:** **Depth.** The **full transitive call tree** of each item's entry function or functions, shared plumbing included (drawing, sound, file I/O, memory). The runtime library rows (`kind = runtime`, already matched by libmatch) and data-in-code rows are excluded. A function reached from several items is listed once with every item that reaches it.
- **D-03:** **Spike, 1 day.** Work from the PIT / INT 8 timer setup, UI strings and data xrefs in the Ghidra output. VALIDATED: strings and xrefs locate the tick rate and the training rule, and that method locates the rest of the list. PARTIAL or INVALIDATED: add call-graph walking from OpenApoc data-table offsets, re-located by signature (Phase 6 D-42). The spike is recorded as `.planning/spikes/007-*` under the spike CONVENTIONS. **Any #997 finding is reported to the owner at once,** with the answer, the addresses and evidence, and whether matched code backs it yet. No agent posts to OpenApoc (auto-memory `notify-owner-997-tick-rate`; `docs/clean-room.md`).
- **D-04:** **Tiers, signed off one at a time** before the driver works on them:
  - Tier 1: #997 (tick rate) + #263-1 (agent training, incl. androids);
  - Tier 2: the rest of #263;
  - Tier 3: #264;
  - Tier 4: #265.

  Each sign-off is a blocking-human checkpoint. Claude drafts the tier (items, entry functions, call trees, the evidence for each entry), and the owner signs it. The sign-off is recorded in `config/mechanics.toml` (who, date) and in the plan's SUMMARY. — **Reversibility:** costly — progress.py's coverage view, the picker's tier order and Phase 8's speclint all read `config/mechanics.toml`.

#### Scale, budget and parallelism (DEC-02, DEC-03, DEC-06, AGT-11)
- **D-05:** **Done rule (owner ruling, 2026-10-26).** The owner was shown the scale: full call trees for every item reach most of about 3,080 game functions, which at the pilot rate is months of runs. Phase 7 is therefore done when:
  - every function in Tier 1's call trees matches (objdiff 100%, relocation check, both EXEs SHA-1 identical) with zero regressions;
  - every tier (1-4) is located and signed off in `config/mechanics.toml`;
  - `readlint`, `stats` and the per-item coverage view ship, and Tier 1 passes `readlint`;
  - AGT-11's 10 unattended matches are reached along the way.

  Tiers 2-4 keep matching in Milestone 2 (SEED-261025-3ga). A plan task rewords REQUIREMENTS.md DEC-03 and DEC-05 and ROADMAP Phase 7 SC3 and SC5 to say this, quoting this ruling. — **Reversibility:** costly — it changes the phase gate wording that VERIFICATION.md checks.
- **D-06:** **Parallel sessions in one checkout.** One `reverseapoc drive` process in the main checkout runs N concurrent sessions.
  - A session claims a **whole unit** (`src/<exe>/<unit>.c`, the only C file it may edit) through an atomic stdlib claims file. A crashed run's claims are recoverable (stale-claim rule; the planner chooses it, e.g. PID plus timestamp).
  - `gate` runs and commits are serialised behind one lock, because `gate` lands every unit of both EXEs and writes `build/`.
  - The D-17 allowlist of Phase 6 becomes per-session: each session's hook settings name its own claimed unit and notes path.
  - The driver is the only writer of shared naming state (D-19).
  - No second clone. decomp.wtf is **not** re-evaluated: spike 006 stands, which closes Phase 6 D-03's "re-evaluate for Phase 7". Record this in `docs/workflow.md` and the PROJECT.md Key Decisions row.
- **D-07:** **Caps.** `--workers 3` (default), night cap **60 sessions** (default `--max-sessions 60`; it was 30), `--max-budget-usd 5` per Opus session kept, `--max-turns 40` and the 30-minute wall clock kept. The usage-limit backoff of Phase 6 D-08 pauses **all** workers. Every value is a driver flag, so the owner can change it per run.
- **D-08:** **Stuck functions: unlimited driver passes, no human step.** A function capped in a pass (3 sessions) is re-queued for a later pass, with more matched callees in its context pack, until it matches. The night cap still bounds each run. Within a tier the order stays callees first (DEC-02).
- **D-09:** **Model escalation (owner idea).** Passes 1 and 2 of a function run on Opus latest (`claude-opus-5-5`). After two capped Opus passes, every later pass runs on Fable latest (`claude-fable-5-1`). The model is logged per attempt (the existing `model` field), and `stats` reports match rate, cost and sessions per model. This revises Phase 6 D-35 ("Opus for every attempt"). The driver's CLI-version and model checks (Phase 6 D-36) must accept both model IDs.
- **D-10:** **Fable budget.** A separate per-model session cap (for example `--fable-budget-usd`), so Fable sessions are not cut short by a cap sized for Opus. Research checks current pricing and the planner proposes the value; **the owner confirms it** at a checkpoint before the first Fable session. Opus keeps USD 5.
- **D-11:** **Matching runs are owner-started,** as in the Phase 6 pilot. Execution builds and tests the new driver features against the stand-in `claude`. The owner starts the real runs at blocking-human checkpoints and may run as many nights as Tier 1 needs. The executor never starts a real `claude -p` matching run on its own.

#### Compiler-flag rulings
- **D-12:** **Per-unit rules, owner-approved in batches.** A real source file had one flag set, so a rule is per unit. A sweep hit becomes a **proposed per-unit rule** in a review queue, a committed file without game bytes. A tool then re-gates the whole unit under the proposed flags: every already-matched function in the unit must still match, and both EXEs must stay SHA-1 identical. The evidence (log paths and the check JSON summary) is attached to the proposal. The owner approves proposals in batches, and only then is `config/cflags.txt` edited, in a commit that quotes the approval. Phase 5 D-18 stands: agents and the driver never edit cflags.txt, and the hooks keep blocking it. — **Reversibility:** costly — the queue format is read by the driver, the approval tool and the docs.
- **D-13:** **Pilot sweep hits first.** An early plan re-runs the saved best C of the 6 never-matched pilot functions with a 100% sweep cell (D-16 list). It turns real hits into proposals with whole-unit re-gates and lands what the owner approves, each as its own match commit through `gate`. The C is in gitignored `build/driver/20261026-005209/...`; if it is missing, those functions are re-queued instead. These matches count toward AGT-11, classed `human-hints` or `unattended` by the `stats` rules (the agent wrote the C, the owner approved the flags). They are also evidence for the real game default.
- **D-14:** **The `*` default** changes only by owner ruling on Phase 5 D-18 evidence (3 or more agreeing functions from different regions of both EXEs). Claude proposes the change with evidence. Units already matched under the old default get pinned per-unit rules in the same commit, so nothing regresses, and `gate --all` runs before that commit.
- **D-15:** **Second-stage sweep.** The 30-cell first stage stays. When no cell reaches 100% and the best cell is at or above 90%, a second stage tries the candidates in `docs/toolchain.md` "Fallbacks and candidates": single `-o` letters (`-od -of+ -or -oi -om -ol -on -op`, KKND's `-of+ -omiler`), `-zp1/2/4/8`, `-zm`, `-fp3/-fp5`. It is a diagnostic only and feeds the same proposal queue. The wrapper still never lets an agent choose flags for a real check.
- **D-16:** The pilot-hit list in `<domain>` comes from reading `progress/attempts.jsonl`. The planner re-derives it with a script, not by hand.

#### Readability and naming (DEC-04)
- **D-17:** **A separate readability pass per tier.** Matching sessions keep the placeholders (`func_X`, `D_X`) and only need byte identity. Once a tier's call tree, or a closed sub-tree of it, is matched, a **readability session type** names, comments and types it bottom-up, with the callers known. A readability session edits comments, names, types it introduces and whitespace only (`docs/ceremonies.md`, matched C). Each unit is re-gated, so `source_sha256` is refreshed (Phase 6 D-22), and committed one unit per commit. A readability commit that changes bytes is refused by the gate like any regression.
- **D-18:** Readability sessions run through the same driver: same caps, workers, logging and hooks, as a different session kind with its own `/goal` prompt and allowlist. `stats` keeps the two kinds apart.
- **D-19:** **The driver is the only writer of shared naming state.** That state is the names in `config/<exe>/symbols.csv` and the shared struct, enum and `#define` headers under `include/` (never `common.h` or `watcom_compat.h`).
  - Sessions write **proposals** to their notes in a fixed, machine-checked format: rename X to Y, add a struct field, add an enum or constant.
  - The driver serialises them. It checks for collisions (a name already used, a struct layout clash), applies them, rewrites every user of a renamed symbol in `src/`, re-gates the affected units and commits.
  - Hooks block agent edits of symbols.csv and of the shared headers.
  - Renaming a function changes its linker name, so the target cut and objdiff's name map must follow symbols.csv (the planner verifies the full path: symbols.csv to target ELF to objdiff to `gate`). — **Reversibility:** costly — the proposal format is referenced by the readability skill text, the driver and the hooks.
- **D-20:** **readlint, strict with a small allowlist** (stdlib, TDD). It runs on matched units only; `INCLUDE_ASM` stubs and unmatched functions are exempt. It fails on:
  - placeholder names: `FUN_`, `sub_`, `DAT_`, and our own `func_XXXXXXXX` / `D_XXXXXXXX` (backlog 999.2);
  - a function without a header comment. The comment states the purpose, the EXE address, and the evidence the name rests on;
  - struct fields named `unk*`, `field_0x*`, `pad*` (or similar), and raw offset access like `*(T *)(p + 0x10)`;
  - integer literals other than 0, 1, -1, mask or shift powers of two and sizeof-like values, unless named by `#define` or `enum`, or marked with a one-line `/* reason */` waiver. readlint counts and reports the waivers.

  Negative tests cover every rule. `uv run reverseapoc readlint src/` exits 0 at the phase gate for every matched unit. Tier 1 is fully named by then, and any other matched unit is either named or covered by the same rules.
- **D-21:** **Name sources.** Game evidence comes first: strings, data-table roles, call context. OpenApoc's domain vocabulary (Organisation, Agent, Vehicle, Building...) is allowed, so Phase 8 specs map onto OpenApoc. Nothing is copied from OpenApoc code or comments (GPL) or from wikis (Phase 8 source rules). The header comment names the evidence.

#### Owner rulings after research (2026-10-26)

Research (`07-RESEARCH.md`, parts under `research-parts/`) measured things that touch the decisions above. The owner ruled on them before planning. Where this section disagrees with an earlier decision, this section wins.

- **D-22: Tier 1 stops at hub functions (refines D-02, D-05).** Research measured Tier 1's full closure at about 895 UFO2P + 1,122 TACP functions (about 65% of game code), counting function-pointer edges. TACP has a 160-function cycle that almost every battle function reaches. Tier 1's "must match" set therefore stops at **hub functions**: shared functions reached from many items, such as `get_text` (UFO2P 0x63800, TACP 0x5B360), the BIOS-tick readers, drawing, and the TACP cycle. Hubs are listed in mechanics data as shared. The driver may match them when it reaches them, but they are not required for Tier 1 done. Claude proposes the hub rule (for example a caller-count or item-count threshold) with the numbers at the Tier 1 sign-off, and the owner signs it with the tier. D-02's full closure is still computed and recorded, so coverage can show both figures. — **Reversibility:** costly — the done rule, the coverage view and Phase 8 speclint read the member and hub split.
- **D-23: Hand-written assembly is classified and excluded.** About 213 UFO2P and 216 TACP game functions start off Watcom's 16-byte alignment. The ones inspected are assembler or library code: the VESA blitters in UFO2P `u_000161b4` and the sound library. They cannot match from C without inline asm, which the hard rules forbid. A detector (off-alignment start plus spot checks) marks them `asm` in a committed list with evidence; the owner signs the list off. They stay `INCLUDE_ASM`, leave the driver queue and the "must match" sets, and the progress page shows them as their own group, outside the percentage like the runtime library. The planner decides whether the list is a new file or a new `kind` value; changing `functions.csv` touches its generator and drift tests.
- **D-24: Private per-attempt views (revises D-06's mechanism).** `check` and `gate` compile and land every unit in `src/`, so concurrent sessions in one checkout would see each other's half-edited units. Each session therefore edits a private copy of its claimed unit in a per-attempt view under `build/driver/.../view/`: HEAD's `src/`, `include/` and config, snapshotted at launch. The attempt wrapper runs `check --src/--config/--build/--log` against the view. Under the gate lock, the driver copies the unit into `src/`, runs `gate` (unchanged) and commits. Reset abandons the view. The stray-path check becomes "nothing git can see changed except driver-owned files with bytes the driver wrote". Claims stay one atomic file per unit (D-06). Threads fit the Windows host. Do not probe PIDs with `os.kill(pid, 0)`, which terminates the process on Windows.
- **D-25: Fable cap USD 12.50 per session (settles D-10).** Prices: Opus 5.5 at $4 input / $20 output and Fable 5.1 at $10 / $50 per million tokens. The pilot's sessions repriced at Fable rates come to mean 2.65, p90 3.56, max 4.73. USD 12.50 keeps the Opus cap's headroom of about 2.6-2.8x the largest session. A Fable canary run by the owner (D-11) settles whether CLI 2.1.308 accepts `claude-fable-5-1` and what model ID its init event reports.
- **D-26: The #997 spike starts from the BIOS tick (refines D-03).** Research found the game paces on the BIOS tick: UFO2P `func_00011430` (28 callers) and TACP `func_00011500` / `func_000116B0` read it through INT 1Ah at 18.2065 Hz. The PIT and INT 8 code belongs to the sound library (UFO2P 0xC8E41.., used only by sound init, a 30 Hz event). The spike therefore starts from the BIOS-tick readers and their main-loop callers, and looks for the "36 units per game second" accumulator that OpenApoc PR #1688 describes. It keeps the 1-day box and the verdict scale. Training from battles goes through `scenario/unitr.dat` (TACP 0x156A0 writes it, UFO2P 0xB2A90 reads it). EXPERIEN.DAT, BRAIN.DAT and WEAPEXP.DAT are the Learning AI files and belong to #265 (Tier 4), not #263-1. The lead was reported to the owner on 2026-10-26; nothing is posted anywhere.
- **D-27: Fixes the research found, done before the features that need them.**
  - `check._compile` passes no compile root, so a source outside `src/<exe>/<unit>.c` (a view, a saved attempt) gets the `*` rule instead of its unit's rule. Choose the rule by the logical path `src/<exe>/<unit>.c`. D-24 and the D-12 re-gates depend on this, and it already affects `gate --partial` on saved attempts.
  - `gate EXE/UNIT --cflags OTHER` writes matched rows under uncommitted flags; refuse it. `gate --all --cflags`, which writes nothing, stays as the D-14 dry run.
  - The always-on hook layer does not protect `config/cflags.txt` (only matching sessions block it); add it to the always-on layer, with the owner's approve step exempted the way D-46 of Phase 6 exempts the notes path.
  - The pre-gate restore of `progress/attempts.jsonl`, `gate --partial` writing status.csv, and the reset of all of `include/` must become concurrency-safe (under the lock, or scoped to the session's own files). Use one git lock and `GIT_OPTIONAL_LOCKS=0`.
- **D-28: D-13 re-prove uses the C that hit.** The driver saved only the best plain check in `best/`, so for 5 of the 6 functions that file is not the C that reached 100%. The C that hit is the sweep line's `checks/NNNN.c` in the attempt directory. Every file that hit also defines the next function of its unit, which scored 1-69% under the default and was never measured under the hit flags. So the re-gate tries the file as written first, then with that neighbouring function turned back into `INCLUDE_ASM`. A single sweep hit on a 32-48-byte function is weak evidence for the `*` default (D-14): `-4r -oneatx` reproduces all 6, `-ot` only 3, and func_0008A100's matched C misses under both at `-4r`.
- **D-29: The renaming prerequisites (refines D-19).** Renames are blocked today in four places, and all four are fixed before the first readability pass:
  - `SymbolTable.c_name` returns the linker name;
  - configure.py's D-12 parser recognises only `func_` names;
  - `source_marks` and the D-22 drift test share that parser;
  - `address_of` refuses the old placeholder for a renamed address, so every user is rewritten in the same commit.

  One shared "functions a unit defines" finder that knows renamed functions serves configure, readlint, the drift test and `gate`.

### Claude's Discretion
- The `config/mechanics.toml` schema (items, tiers, entry functions, member functions, the sign-off record), the claims-file format and stale rule, the flag-proposal queue format, the naming-proposal format, module layout and verb names (the existing verbs `drive`, `gate`, `check`, `attempt` keep their names).
- How the call trees are computed (Ghidra export, capstone discovery's call edges, relocation targets) and how indirect calls and jump tables are handled.
- The per-item coverage view on the progress page (DEC-05): how progress.py reads mechanics.toml and shows each item's matched / partial / unmatched share. **Backlog 999.4** (phone mosaic: sideways scroll with a ~48rem minimum SVG width or an HTML legend; keyboard/touch tooltips instead of `title`-only; the percent bar that draws nothing at current values; 06-UI-REVIEW.md fixes #1-#3) is folded into the same progress.py work.
- `stats` internals beyond the roadmap text (DEC-07), plus the per-model split (D-09), the matching/readability split (D-18) and the per-attempt hook-block count from Phase 7 on.
- Scorer and picker tuning carried from Phase 6 D-09: callees first inside a tier, admitting jump-table and static functions now that DI-02/DI-03 landed, dropping or keeping `WEIGHT_NO_FRAME`.
- Defaults the research left open, which the planner settles and records: `--target-matched` stops being a night stop in Phase 7 (it defaults to off; the night cap governs, and AGT-11 is counted by `stats`); a readability session commits a unit only when that unit passes readlint; renames apply only to units no live claim holds, and a claimed unit picks them up when it lands; matching sessions add no shared headers (new shared types go through D-19 proposals); the variety rule is off inside a tier.
- readlint scoping: strict `readlint src/` is the phase-gate form. Scoped forms (`--units`, `--tier`, `--report`) serve the readability passes, and an allowlist file (for example `config/readlint-allow.csv`) covers references from named code to not-yet-named callees. A tagged waiver form gives an exact count.
- Whether `config/mechanics.toml` holds member lists, or a generated, drift-tested `config/mechanics-members.csv` holds them (research recommends the CSV; progress.py and speclint read it in CI).
- The readability `/goal` prompt wording, and whether the readability session text is a new project skill or a section of `watcom-decomp`. Either way it is written or updated with `superpowers:writing-skills` (`.claude/rules/workflow.md`).

### Deferred Ideas (OUT OF SCOPE)
- Matching Tiers 2-4 to completion: Milestone 2 (SEED-261025-3ga).
- A second clone or a multi-clone SQLite claims store; decomp.wtf as a claims layer. Closed for Milestone 1 by D-06 (spike 006 stands).
- A human-hints escalation step for stuck functions. Offered; the owner chose unlimited driver passes (D-08). Revisit if Tier 1 stalls.
- GhidraMCP as a live agent tool: stays "Later".
- Twin matching of CD v1.00: after Phase 7 (Phase 6 D-42).
- Attributing the uncovered filler bytes (Phase 6 D-50).
</user_constraints>

## Summary

**#997 lead (not backed by matched code).** None of the functions below is matched (`config/<exe>/status.csv`). The owner already has the lead (D-26). Nothing goes to OpenApoc from an agent.
- Game time runs on the BIOS tick, not the PIT. UFO2P `func_00011430` (28 direct callers) and TACP `func_00011500` (35 callers) / `func_000116B0` call the runtime `int386_` with interrupt `0x1A`, which is the 18.2065 Hz BIOS tick (1,193,182 / 65,536). No game code reads the tick word at `0x46C` directly. [VERIFIED: slice 1 capstone scan of both EXEs; R1 "#997 FINDING"]
- The only PIT programming and INT 8 installs sit in the sound library (UFO2P `0xC8E41..0xC90F3`, TACP `0xCC151..`). Its only caller is sound init (UFO2P `func_000B5950`, TACP `func_000AF770`), which registers one 30 Hz event. [VERIFIED: slice 1 scan; that the library is HMI SOS is ASSUMED]
- OpenApoc PR #1688 claims the main loop busy-waits on the BIOS clock (18.2065 Hz) and adds a speed value into an accumulator where 36 units make one game second, so "36 ticks per second" would be a fixed-point fraction, not a 36 Hz rate. Our scan confirms the first half only. The 36-unit accumulator and the speed table are **not found yet**. Spike 007 q2 looks for them. [CITED: https://github.com/OpenApoc/OpenApoc/pull/1688]
- Candidates for the spike: the cityscape loop `func_00022EF0` (it reaches a tick wait in `func_00026B80`), a possible speed table at `0x1303E0` used by `func_000ACDC0`, and the `Slow/Normal/Double/Quadruple speed` strings at UFO2P `0xF14BF..0xF14E4`, which are reached only through `get_text`. [VERIFIED for the addresses: slice 1; the meaning of each is ASSUMED until q2 runs]

**What the phase is, after the rulings.** Three kinds of work, in roughly this order:
1. **Locate.** A deterministic stdlib call graph (LE fixups + capstone, no Ghidra), spike 007, the asm list (D-23), and `config/mechanics.toml` plus a generated members file, signed off one tier at a time.
2. **Tooling.** Prerequisite fixes (D-27, D-29) come first. Then the concurrent driver (private views, claims, one gate lock, model escalation), flag proposals, readlint, stats and the coverage page.
3. **Owner-run nights.** These match Tier 1's must-match set (members down to the hubs, minus asm) and then make it readable. AGT-11 (10 unattended matches) is reached along the way.

Locating is cheap. The measured scale is what drove D-22: the full closure of draft Tier 1 is about 895 UFO2P + 1,122 TACP functions with pointer edges, and TACP has a 160-function strongly connected component under almost every battle function. [VERIFIED: R1 Q1]

**The tooling is serial today.** It breaks in several places once two sessions share a checkout:
- every `check` and `gate` lands every unit in `src/` of both EXEs;
- the post-session audit diffs the whole tree;
- the pre-gate restore rewrites `attempts.jsonl`;
- reset restores all of `include/`. [VERIFIED: R2 §1; driver.py:1514-1532, 1569-1570 re-read this pass]

D-24's private views plus one lock around every shared write fix all of them. One bug blocks both views and flag re-gates. Both slices found it independently: `check._compile` passes no root (check.py:255-261), so a unit compiled from anywhere but `src/<exe>/<unit>.c` gets the `*` rule (D-27). Renames are blocked in four places (D-29). readlint, stats and the coverage view are new stdlib modules with clear precedents (`lint`, `progress.py`, the attempts schema).

**Primary recommendation:**
- Plan the D-27 and D-29 fixes as the first TDD plans.
- Run spike 007 and the call-graph/mechanics/asm work in parallel with them.
- Then build the concurrent driver (views → claims/locks → workers → escalation), flags, readlint, stats and the page.
- Put every owner step at its own blocking checkpoint: the asm list, the Tier 1 sign-off with the hub rule, the flag batch, the Fable canary, matching nights, and the Tier 2-4 sign-offs.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEC-01 | `config/mechanics.toml` maps each answerable item to its EXE and functions, located from UI strings and data xrefs; owner signs off | §A (call graph, `get_text` route, hand-off files, VA identity of data tables, schema, members CSV, drift/schema tests); §B spike 007; §C asm list; §D hub rule; Tier 1-4 drafts in R1 Q4 |
| DEC-02 | Callees first, claims so parallel agents never take the same function, single owner of shared naming state | §E (views, claims, locks, workers, tier picker with SCC order); §G (rename apply step, proposals) |
| DEC-03 | Every function on the list matches, both EXEs identical, zero regressions (reworded by D-05/D-22/D-23: Tier 1 must-match set) | §E driver at scale; §F escalation; §H flag proposals + D-13 re-prove; plan-ordering matching checkpoints; rewording task |
| DEC-04 | stdlib `readlint` (TDD) fails on placeholders, missing header comments, unnamed fields, magic constants | §I readlint design RL01-RL06; §G readability sessions; D-29 finder |
| DEC-05 | Progress page shows coverage per checklist item (reworded by D-05) | §K `derive_mechanics`, item list, tier union, member vs full-closure figures, asm group; 999.4 fixes |
| DEC-06 | Phase 6 caps and per-attempt logging carry over; nightly totals recorded | §E caps (D-07), global pause, cap reservation; §J v2 `totals` in run records, `limit` records |
| DEC-07 | stdlib `stats` (TDD) over attempts.jsonl + git trailers; classes `unattended`/`human-hints`/`human-written`; hook-block count per attempt | §J v2 schema, trailer classing, refusals, per-model/kind/size splits |
| AGT-11 | 10 unattended matches with zero regressions (3/10 carried in) | §H D-13 re-prove (up to 6, classing open as R4); §F escalation; matching nights; counted by `stats` from git |
</phase_requirements>

## Project Constraints (from CLAUDE.md and rules)

- Never commit game files, disassembly or build output (`orig/`, `asm/`, `build/`, `third_party/`). Committed data carries addresses, names, statuses, flag strings, SHA-256 hex and short evidence text only. Never modify `orig/`, the hash manifests under `config/`, or the build scripts to make a check pass.
- A matched function stays byte-identical. No restructuring and no inline assembly to force a match (this is why D-23 excludes asm rows rather than matching them).
- Tooling is stdlib Python 3.14 (progress.py stays 3.12-syntax, stdlib, `python3 -I`), developed TDD, ruff clean. Real-file tests skip without `orig/`. CI has no game files. Committed data files are written with `write_atomic` (`tools/reverseapoc/fileio.py`).
- Done gate: tests and ruff green on the host and in the container (`docker compose run --rm test`). The rebuilt EXE must be SHA-1 identical and objdiff must report 100% per matched function. Only the container `gate` decides a match: one match per commit, with the `Matched-By` trailer.
- Claude Code is the only agent runtime. Project skills are created or updated only through `superpowers:writing-skills` (`.claude/rules/workflow.md`). GSD owns phase sequencing; superpowers owns TDD and verification inside a phase.
- Host and container suites never run at the same time (they share build/test-cc). Main-checkout plans need the auto-memory `gsd-main-checkout-plans` recipe.
- No OpenApoc contact in Milestone 1. A #997 finding goes to the owner only. Nothing is copied from OpenApoc code or comments (GPL): their offsets serve as locators in a local script and are never committed as a table.
- No secrets in tracked files.

## Architectural Responsibility Map

| Capability | Primary tier | Secondary tier | Rationale |
|---|---|---|---|
| Call graph and closures | `tools/reverseapoc/callgraph.py` (host/container, needs `orig/`) | committed `config/mechanics-members.csv` | LE bytes are game data; CI reads only the committed result |
| Item, tier and sign-off decisions | `config/mechanics.toml` (hand-edited) | owner checkpoints | Owner decisions must not be rewritten by a generator (stdlib has no TOML writer) |
| asm classification | detector (needs `orig/`) | committed asm list, owner-signed | Judgement plus evidence, like mechanics |
| Picking, claims, pass/model choice, caps, backoff | driver coordinator thread | `build/driver/claims/`, `drive.lock` | One process (D-06); files are for crash recovery |
| One session | driver worker thread + `claude -p` | per-attempt view under `build/driver/.../view/` | Subprocess-bound; the view isolates edits (D-24) |
| Session checks | attempt wrapper → container `check` on the view | per-view `build/` | Must never see other sessions' edits |
| Match / readability verdict | container `gate` on real `src/` under the lock | driver | Unchanged trust anchor |
| Naming state (symbols.csv, shared headers) | driver rename step under the lock | sessions write `proposals.jsonl` | D-19 |
| Write guardrails | `hooks.py` (per-process env) | driver post-session ledger audit | Two layers, as in Phase 6 |
| Flag rules | `flags` verbs (propose/regate host+container; approve owner-run) | `config/cflags-proposals.toml`, `config/cflags.txt` | D-12, D-18 of Phase 5 |
| Readability verdict | `readlint` (host, stdlib, CI) + `gate` (bytes) | driver after readability sessions | The tool decides, not the agent |
| Metrics | `attempts.jsonl` (driver) + git trailers → `stats` | | Must run in CI without `build/` |
| Coverage page | `tools/progress.py` (Pages runner, stdlib) | committed mechanics files | CI/Pages has no game files |

## Standard Stack

No new external packages are needed. Everything is stdlib Python 3.14 plus what is already pinned:
- `capstone` 5.0.9 [VERIFIED: R1 environment table];
- objdiff-cli 3.8.2, Watcom 10.6 under wibo, and clang 18 in the container (STATE.md Phase 5 entries).

| Need | Use | Not |
|---|---|---|
| TOML read | `tomllib` (stdlib, 3.11+) | a TOML library |
| TOML write (proposal queue) | a small fixed-key-order writer, with string values emitted by `json.dumps` (valid TOML for ASCII), round-trip tested [ASSUMED: ASCII-only values; enforce in the writer] | a dependency |
| Atomic create (claims) | `os.open(..., O_CREAT\|O_EXCL\|O_BINARY)` (`driver.py:142-143`, `attempt.py:446,472` precedent) | `os.rename` (raises on Windows when the target exists) / `os.replace` (overwrites) [ASSUMED: Python docs knowledge, consistent with the code base's choice] |
| Process-lifetime lock | `msvcrt.locking(LK_NBLCK)` / `fcntl.flock` (`compiler.py:43-47, 473-512` pattern) | `os.kill(pid, 0)` probing (terminates the process on Windows, D-24) |
| Concurrency | `threading` workers + one coordinator; `subprocess` | multiprocessing |
| Decoding | `reverseapoc.x86` (pinned capstone) | Ghidra edges (the export has none: R1 Q1) |

**Package Legitimacy Audit:** not applicable. The phase installs no external package. (capstone is already locked in `uv.lock` and was accepted at Phase 5 UAT.)

## Standard approach per area

### A. Locate, call graph and mechanics data (DEC-01)

Detail in R1 Q1-Q6.

- **New module `tools/reverseapoc/callgraph.py`** (TDD, synthetic LE fixtures). It reuses `contextpack.CallIndex` (direct calls and tail jumps; 5,288 UFO2P / 4,885 TACP edges) and adds typed edges:
  - `pointer`: an off32/ptr16:32 fixup from a game or thunk row to another row's start (343 / 336 distinct edges);
  - `table`: data pointer slots grouped into runs and wired from each code row that references the run (67 slots in 13 runs / 35 in 12);
  - `hand`: from `[[edge]]` entries in mechanics.toml, for indirect calls a reader proved. [VERIFIED: R1 Q1 measurements]
- **Rules for the walk:**
  - runtime rows are leaves and never members;
  - data-in-code rows are never members;
  - thunks are walked;
  - jump tables stay intra-function;
  - unresolvable `call [reg]` sites are counted per function and listed, never guessed.
- **Report, do not guess, mid-row references:** 243 UFO2P / 220 TACP code→mid-row fixups and 64 data→mid-row per EXE. Each is a missed function start or a table base. A plan task classifies them before Tier 1 members freeze (a missed start would change `functions.csv`, its generator and drift test). [VERIFIED: R1 Q1, R4]
- **Locating routes:**
  - File names and format strings have direct fixup refs (1,095 / 592 of 3,800 / 2,227 strings).
  - UI text has none. It goes through `get_text(section, index)`: UFO2P `func_00063800` (180 callers, section table `0xF3794`, 50 sections), TACP `func_0005B360` (88 callers, `0x292D18`). To locate a UI string, compute its (section, index), then find call sites whose last `mov eax/edx, imm` match.
  - Hand-off files between the EXEs are the best cross-EXE evidence. The key one: `scenario/unitr.dat`, written by TACP `0x156A0` and read by UFO2P `0xB2A90`.
  - [VERIFIED: R1 Q2]
- **OpenApoc data-table offsets map to the same linear address in the installed build:**
  - 380 of 386 UFO2P data pages are byte-identical;
  - all 35 UFO2P + 12 TACP tables are identical at the same VA;
  - code addresses differ, so they need masked signatures and a byte check. [VERIFIED: R1 Q3]
  - Commit only our own installed addresses ("re-located by VA identity"), never OpenApoc's offset list.
- **Data files (recommendation; the members-file choice is Claude's discretion):**
  - `config/mechanics.toml`, hand-edited:
    - `schema`;
    - `[[tier]]` with `id`, `title`, `signed_off_by`, `signed_off_date`, `members_sha256`, and **the signed hub rule** (D-22);
    - `[[item]]` with `id`, `issue`, `title`, `url`, `tier`, `scope = in|out|duplicate`, `duplicate_of`, `reason`, `exes`;
    - `[[entry]]` with `item`, `exe`, `address`, `evidence` kind, a short `detail`, `source`;
    - `[[edge]]` hand edges.
    - Full schema sketch in R1 Q5.
  - `config/mechanics-members.csv`, generated by `reverseapoc mechanics --write`, LF, sorted, "do not edit". Columns `exe,address,items,tiers,via,role`:
    - `via` = the weakest edge kind on the shortest path;
    - **`role` is new, required by D-22/D-23:**
      - `member`: in the must-match set;
      - `hub`: shared boundary, located, not required;
      - `closure`: reached only through a hub, so in D-02's full closure only;
      - `asm`: excluded by D-23, wherever it falls.
    - No names (renames change names); readers join on the address.
  - Tests:
    - drift test (real files, skips without `orig/`): regenerate and compare bytes;
    - schema test (CI): every member is a game/thunk row; every entry has `via = entry`; items exist and are `in`; `duplicate_of` targets an `in` item; a signed tier's `members_sha256` equals the hash of its current rows, otherwise the tier must be re-signed.
- **Item drafts per tier** are in R1 Q4 (Tier 1 table, Tier 2-4 in/out proposals with evidence kinds). With D-26 applied, Tier 1's draft entries are:
  - #997: the tick readers and their main-loop callers (but see R1 below on hub entries);
  - #263-1: TACP `0x156A0` and its accrual sites, UFO2P `0xB2A90` and the stat-update callee, plus the android branch near the `(Android training not possible)` `get_text` site and the `android` ref in `func_0009B840`.
  - EXPERIEN/BRAIN/WEAPEXP.DAT go to Tier 4 (#265-1..8).
  - #263-21 and #264-2 are `duplicate_of = "997"`.

### B. Spike 007 (roadmap spike, D-03 as refined by D-26)

Design in R1 Q2.

- Directory `.planning/spikes/007-locate-997-training/`, under the spike CONVENTIONS, 1-day box. Stdlib plus `reverseapoc.x86` (stated deviation in the README).
- Scripts print `PASS/FAIL <file> <claim> <detail>`, end with `ALL PASS` / `N FAILED`, and exit 1 on any FAIL. Each fact under test is cross-checked against a module other than the one that produced it.

| Script | Box | Claims |
|---|---|---|
| `q1_timebase.py` | 1 h | PIT/INT 8 sites only in the sound-library span; `int386(0x1A)` readers UFO2P `0x11430`, TACP `0x11500` + `0x116B0`; caller counts 28 / 35 / 10; no direct `0x46C` read |
| `q2_tickrule.py` | 2.5 h | **start here per D-26**: from the tick readers' main-loop callers, find the time-advance loop and speed table in each EXE. Separate claims: "accumulator modulus is 36" (PR #1688) and "one speed-table entry per speed label". A FAIL is a finding |
| `q3_training.py` | 2 h | `unitr.dat` writer/reader; UFO2P stat-update callee; android branch; TACP accrual sites |
| `q4_strings.py` | 1 h | `get_text` section table decode; arg recovery rate (measure, ≥80% target); entries found for 12 sampled Tier 2-4 items |
| `q5_tables.py` | 0.5 h | OpenApoc CD offsets (fetched to scratch, never committed) map to the same VA; byte identity |
| `q6_callgraph.py` | 0.5 h | Q1 reachability reproduced; direct edges equal `CallIndex` |

- **Prove the checker can fail:**
  - plant one wrong EXPECTED value per script;
  - zero the `0x1A` immediate in an in-memory copy (q1 must report the reader as missing);
  - flip one byte in a copied table (q5 must FAIL).
- **Verdicts:**
  - VALIDATED = q2 and q3 PASS, and q4 finds ≥10 of 12;
  - PARTIAL = one of q2/q3 PASSes, or q4 finds 6-9;
  - INVALIDATED = otherwise.
  - Expect PARTIAL to VALIDATED. [ASSUMED]
- **Game data never leaves the scripts.** Report addresses, counts, booleans and protocol constants only. Read `cd.iso` in memory (spike 003 pattern).
- **Any #997 result goes to the owner at once,** with the addresses and "matched code backs it: yes/no". This is a notify step, not a blocking gate.

### C. asm classification (D-23)

- **Detector inputs:**
  - an off-alignment start (not 16-byte aligned; about 213 UFO2P / 216 TACP game rows);
  - heuristics: stack-frame calling convention instead of Watcom register args, inline `nop` padding, `enter`/`pushal`/`iretd`, and membership in known library spans (UFO2P `u_000161b4` VESA blitters `0x161B4-0x18970`, the sound library `0xC8E41..` and its wrapper unit `u_000c1b4b`, the TACP equivalents);
  - spot checks recorded as evidence. [VERIFIED: counts and spans from R1 R2; that most such rows are asm is ASSUMED (R1 A5)]
- Pilot evidence: TACP `func_000C6287` in the sound-library unit capped at 61.87% after 3 sessions.
- **Output:** a committed list with `exe,address,evidence` and the owner's sign-off. The detector proposes; it never decides alone. Rows off alignment with no asm evidence go to the owner as "unclear" rather than in or out.
- **Format (planner decides per D-23). Recommendation: a separate file** (for example `config/asm-functions.csv`, or `config/<exe>/asm.csv`) with a drift test (real) and a schema test (CI: every row is a game row of functions.csv). Do not add a new `kind` to `functions.csv`. Reasons:
  - `functions.csv` is generated by `functions --write` from the LE, while the asm list is signed judgement (the same split as functions.csv/units.csv and mechanics.toml/members);
  - `KINDS = ("game", "runtime", "thunk", "data-in-code")` (functions.py:57, per R1) is read by contextpack, configure and progress, so a new kind ripples through all of them.
  - The cost of the separate file: progress.py, the picker and the mechanics generator read one more file.
- **Consumers:**
  - the picker skips asm rows;
  - the mechanics generator sets `role = asm`;
  - progress shows an "assembler" group outside the percentage, like runtime;
  - configure's D-12 check still requires an `INCLUDE_ASM` marker for them (unchanged);
  - readlint treats them like any stub.
- **Sequencing:** the asm list is signed **before** the Tier 1 sign-off, because asm rows leave the must-match set. Draft Tier 1 holds 74-132 such rows per EXE (R1 R2).

### D. Hub rule (D-22)

- **The tool computes candidate rules; Claude proposes one with numbers at the Tier 1 checkpoint; the owner signs it with the tier.** Candidate criteria, all measurable from `callgraph.py`:
  1. membership in an EXE's largest SCC: TACP 160 functions on all edges around `0xBCDC0..0xBF980`, UFO2P 32;
  2. direct caller count ≥ K. Examples: `get_text` 180 / 88, UFO2P `0x27020` 146, the blitter `0x16864` 105 (also asm), `0x5CD00` 101 (looks like `random(n)`, ASSUMED), TACP `0x1F080` 68, the tick readers 28 / 35;
  3. own closure > X% of the EXE (135 UFO2P / 217 TACP functions reach >30%);
  4. reached from ≥ M items (needs all four tiers located; for Tier 1 alone use 1-3). [VERIFIED: R1 Q1 counts]
- **The must-match set** is the closure from the tier's entries that stops at hubs (a hub is recorded with `role = hub` and not walked further), minus asm rows. The full D-02 closure is still computed and recorded (`role = closure` beyond hubs).
- **Present at the checkpoint:**
  - must-match counts per EXE for 2-3 values of K, with and without pointer edges;
  - the hub list with caller counts;
  - how many members each edge kind adds;
  - the asm rows removed.
  - The real numbers do not exist yet (only the unbounded closures were measured). See the open questions.
- **Picker consequence:** a hub callee never blocks a member's "callees first" readiness. The driver may still pick hubs once the tier's members are exhausted ("may match them when it reaches them").

### E. Driver concurrency with private views (D-24), claims, locks (DEC-02, DEC-06)

Detail in R2 §1-§3, §5.

- **View at launch:** `build/driver/<run>/<exe>/<func>/attempt-<n>/view/` holds HEAD's tracked `src/`, `include/` and the config files `check` reads (targets.toml, cflags.txt, the per-EXE functions/units/symbols/runtime CSVs), taken from HEAD through the git lock (`git archive` or `git show HEAD:<path>`), not from the worktree. The claimed unit is `view/src/<exe>/<unit>.c` (HEAD's file, or the scaffold). It is the only C file the session may write.
- **Session checks:**
  - The wrapper builds `check <claim> --src <view>/src --config <view>/config --cflags <view>/config/cflags.txt --build <view>/build --log <view>/build/logs/cc.log --json`. All these flags exist (cli.py:929-950 per R2).
  - Today the wrapper passes default roots (`container_check_argv`, attempt.py:222-226, re-read this pass).
  - The view lies inside the repo, so the container mount sees it. Objects go to `<view>/build/check-custom/` (`object_root`, check.py:229-240), never to ninja's paths.
- **Landing under the lock (gate unchanged):**
  1. copy the private unit into `src/<exe>/<unit>.c`;
  2. apply pending renames to it (§G);
  3. run the C89 lint;
  4. run the container `gate EXE/UNIT --attempts N --json`;
  5. on a match: append the MATCHED record and commit explicit paths;
  6. otherwise: `git restore --source=HEAD -- src/<exe>/<unit>.c` (or delete it if untracked), and run `gate --partial` (scoped restore: status.csv and feed only).
  - `src/` equals HEAD at all times except for the unit being landed.
- **Locks:**
  - one in-process **gate lock** around lint+gate+commit, `gate --partial`, record appends, renames and `flags approve`;
  - one **git lock** through which every driver git call goes;
  - `GIT_OPTIONAL_LOCKS=0` in the driver's git env and in every session env (D-27);
  - retry `git add/commit` once on `index.lock` before `_undo_match`.
- **Claims:**
  - `build/driver/drive.lock` is held with the non-blocking OS lock for the process's life. Failing to get it refuses the start; getting it proves any earlier holder is dead.
  - Claim file `build/driver/claims/<exe>__<unit>.json`, created O_EXCL, content `{run, worker, exe, unit, function, start, kind, pass, model, claimed_at}`.
  - **Stale rule:** with drive.lock held, every claim whose `run` differs from the current run is stale. Record it under `recovered` in the STARTED record and move it to `build/driver/<run>/stale-claims/`.
  - A crash inside a landing leaves `src/` dirty. The existing `_clean_tree` preflight then refuses the start and names the paths (an owner checkpoint).
  - A rename claims every affected unit.
- **Threads:**
  - Worker threads each run one session (claude subprocess plus audit). One coordinator owns the picker, claims, records, locks and git.
  - Windows specifics: `KeyboardInterrupt` reaches only the main thread, which must set a stop event and kill every registered live session pid (`run_session` needs a pid-registry hook); `kill_tree` cannot reach orphaned grandchildren (session.py:269-272), so containers are still removed by name prefix per attempt. [VERIFIED: R2 §1]
- **Audit (D-24 stray rule):**
  - (a) Git-visible paths may differ from HEAD only by the driver's expected-state ledger: the paths the driver dirtied this night (attempts.jsonl, status.csv partial rows, the unit being landed while locked), each with the exact bytes the driver last wrote.
  - (b) Every non-claimed file in a session's view is hashed at launch and again before landing.
  - Pinned files and the `.venv`/`.claude`/`__pycache__` fingerprint stay global.
  - An unattributed breach stops the night and kills and contains every live session (fail closed).
  - Matching sessions write no `include/` files (CONTEXT discretion default). That removes `_commit_headers` (driver.py:1640-1654), the header arm of `_reset` and the `include/` arm of the audit.
- **Hooks per session:**
  - The hooks already learn the claim from each claude process's env (`CLAIM_ENV`, `NOTES_ENV`), so per-process env meets D-06's per-session allowlist without per-session settings files. [VERIFIED: R2 §3; hooks.py:79-93 re-read]
  - Add `REVERSEAPOC_UNIT_FILE`, `REVERSEAPOC_PROPOSALS` and `REVERSEAPOC_SESSION_KIND`. The wrapper validates that each sits at its expected place under the attempt dir.
  - Matching allowlist: the env unit file, notes.md and proposals.jsonl. Deny `src/**`, `include/**`, `config/<exe>/symbols.csv` and `config/cflags*.{txt,toml}` with named reasons.
  - **Two required hook changes** (see Prerequisite fixes P6):
    - the always layer's `build/` exemption extends from notes to the three env paths;
    - the inline-asm/pragma scan (`_SCANNED_DIRS = ("src", "include")`) must also run on the env unit file under `build/`.
- **Usage limits with N workers:**
  - One global pause (`threading.Event` + `paused_until`). Any LIMIT sets it. Running sessions finish and are salvaged or judged as usual. After the backoff exactly one probe launches; a non-LIMIT probe clears the pause for all. STOP from any worker stops everything.
  - The night cap reserves a slot before each launch (`counted + reserved < max_sessions`) and releases it if the session ends uncounted.
  - Every record gets `worker`, plus a new `limit` record kind `{kind, run, worker, seconds, streak, date}`.
- **Caps (D-07):**
  - `--workers 3`;
  - `--max-sessions` default 30 → **60** (driver.py:1772, cli.py:1292);
  - `--max-budget-usd 5` for Opus;
  - `--max-turns 40`;
  - 30 min wall clock;
  - `--target-matched` default **off**: today `type=_positive, default=10` (cli.py:1294, driver.py:1773, re-read this pass), so "off" needs a new representation, for example `0` = off with a new validator, or omitting the flag.
  - The CLI's `num_turns` exceeded 40 in 30 of 40 pilot sessions (max 75) while only 14 ended `error_max_turns`. `stats` must not assume turns ≤ 40 (informational; D-07 keeps the cap). [VERIFIED: R2 §7]
- **Tier picker (DEC-02, discretion):**
  - The pool is the signed tier's must-match members (not score's P16 survivors).
  - Condense the member call graph to SCCs and order the levels leaves first, with the `(chk, score, start)` rank as tie-break.
  - "Next eligible" = unit not claimed, and every in-tier callee matched or capped at least once (hubs and asm rows never block).
  - The variety rule is off inside a tier.
  - Admit jump-table and static functions (DI-02/DI-03 landed).
  - A capped function goes back in the queue for a later pass (D-08).
- **Check time** grows with matched units, because every check compiles every committed unit of both EXEs and `CHECK_TIMEOUT = 580` s (attempt.py:49). Measure early; see Risk K2.

### F. Model escalation and budgets (D-09, D-25)

Detail in R2 §4.

- **Plumbing:**
  - `session.build_argv(prompt, *, claude, model, max_budget_usd, max_turns)`. Today these are module constants (session.py:35-39, re-read).
  - `Deps.argv(prompt, model, budget)`;
  - `goal_prompt(..., kind)`.
- **Pass counting:**
  - A pass is up to 3 sessions on one function. Passes 1-2 run on `claude-opus-5-5`; pass 3 and later on `claude-fable-5-1`.
  - Persist `pass` in the v2 attempt record and derive "capped Opus passes" from `attempts.jsonl` (committed, survives runs). `difficult.json` stores no pass count today (driver.py:712-715) and becomes a cache only.
  - The 12 never-matched pilot functions (v1 records) each count as one capped Opus pass, so their next pass is Opus pass 2.
- **Init check:**
  - Pass `expected_model=<requested model>` to `streamjson.check_init`. Today the driver (driver.py:1508-1509) and the canary (driver.py:2423-2424) pass none, so they default to `EXPECTED_MODEL = "claude-opus-5-5"` (streamjson.py:63), and a Fable session would STOP the night.
  - The preflight accepts both IDs.
- **Co-author line:** `COAUTHOR` is hard-coded to Opus (driver.py:97). Take it from a model→name table and refuse an unknown model rather than mislabel the commit.
- **Budgets (settled by D-25):**
  - `--max-budget-usd 5` for Opus and `--fable-budget-usd 12.50` for Fable, chosen by the requested model.
  - Prices: Opus 5.5 at $4 / $20 per MTok, Fable 5.1 at $10 / $50. [CITED: claude-api skill model table, per R2 §4; owner-confirmed in D-25]
  - Worst-case night if every session were Fable at the cap: 60 × 12.50 = USD 750 (API-equivalent). At the repriced mean: 60 × 2.65 ≈ 159.
- **Canary (owner-run, D-11/D-25):**
  - `drive --canary --model claude-fable-5-1` before the first Fable pass.
  - It confirms that CLI 2.1.308 accepts the ID and records the exact `model` string the init event reports.
  - It needs a `--model` option on the canary path. [ASSUMED: acceptance and init string unverified (R2 A3)]

### G. Readability sessions and rename prerequisites (D-17..D-19, D-29)

Detail in R2 §6, R3 Q5 pitfalls.

- **Prerequisites (D-29), the first plan of this area:**
  - one shared "functions a unit defines" finder that matches definitions and `INCLUDE_ASM(...)` markers by **any** identifier mapped to a row start through symbols.csv C names. It serves configure's D-12 check (configure.py:238-242 `_PLACEHOLDER/_MARKER/_DEFINITION`), `check.source_marks` (check.py:508-523), the D-22 drift test (tests/test_drift.py:55-73, which compares names; switch it to compare **by start**), `gate._reverted`, and readlint;
  - `SymbolTable.c_name` fix: a func C name is the linker name minus the trailing `_`, a data C name is the linker name minus the leading `_`; refuse a func row without the suffix (symbols.py:154-159 returns the symbols.csv name verbatim today, re-read);
  - renames rewrite every user atomically, because `_refuse_renamed` (symbols.py:199-203) rejects the old placeholder.
  - [VERIFIED: all four blockers re-read this pass]
- **Linker-name path (D-19 asks the planner to verify):**
  - symbols.csv → `SymbolTable.linker_name` (symbols.py:139-152);
  - → target cut (target.py:180-184, 294 per R2);
  - → check pairing (check.py:298-299, 632 per R2);
  - → objdiff, whose `objdiff.json` carries units and paths only, no symbol names (configure.py:720-734);
  - → ninja's target edge, which lists symbols.csv as an input (configure.py:769-770).
  - So once `c_name` and the finder are fixed, a rename flows through. Pin it with an end-to-end tmp-repo test (fake gate) that renames one function and checks symbols.csv, unit text, the status.csv name and the feed in one commit.
- **Proposal format** (`<attempt dir>/proposals.jsonl`, one object per line, pinned by tests first):
  - `{"op":"rename","exe","kind":"func|data","address","name","evidence"}` (C names; the driver derives linker names);
  - `{"op":"header","path":"include/<name>.h","text","evidence"}` (whole-file text for one shared header, never `common.h`/`watcom_compat.h`).
  - D-19's "add a struct field / enum / constant" are expressed through `header`. A diff op is a later refinement.
- **Apply step (driver, under the gate lock):**
  1. validate the name: a C identifier, not a keyword, not placeholder-shaped, unique among symbols.csv, runtime publics and file-scope names; header text passes the always-layer scans;
  2. find the affected units: placeholder token users plus includers of a changed header;
  3. apply only if none of them is claimed (CONTEXT default); a claimed unit picks the rename up at landing;
  4. write symbols.csv (`write_symbols_csv`, atomic), word-boundary-rewrite the exact token, write the header;
  5. run one `gate u1 u2 ...` (all or nothing);
  6. commit `refactor(<exe>): rename func_X to Name` with the trailer `Renamed-By: reverseapoc drive`, or restore everything and log the proposal as refused.
  - A rename commit spans several units. That is D-19's explicit path, distinct from D-17's "one unit per commit" for readability edits.
- **Readability session kind:**
  - same driver, caps and hooks, with `REVERSEAPOC_SESSION_KIND=readability`, its own `/goal` and allowlist (unit file, notes, proposals; never cflags or the proposal queue).
  - After the session the driver checks that the set of functions the unit defines in C and marks `INCLUDE_ASM` is unchanged (renamed-aware finder), so a readability session cannot turn a stub into a match attempt.
  - The unit is re-gated (refreshes `source_sha256`) and committed only when it passes `readlint --units` (CONTEXT default).
  - Readability outcomes get their own enum (proposal: `LANDED`, `PARTIAL`, `REFUSED`, `GAVE_UP`).
- **Skill text:** recommend a **new project skill** for readability sessions, written with `superpowers:writing-skills`, rather than a section in `watcom-decomp`. `tests/test_skill.py` pins `watcom-decomp` to nine named sections and ≤ 300 lines, and the skill rides in every matching session's prompt. `watcom-decomp` still needs updates (also through writing-skills): the claimed file is now the view unit, proposals replace header writes, and there are no new headers. Today the skill says `src/<exe>/<unit>.c` (SKILL.md:3, 15, 85 per R2).
- **Pitfall:** replacing a literal can change its type and the bytes (`sizeof` is unsigned, an enum is `int`, `0xFFFFFFFF` is unsigned). Use a `#define` that keeps the literal's exact spelling and suffix. The gate catches slips; the prompt should say so up front. [VERIFIED: R3 Q5 pitfalls; C semantics]

### H. Flag proposals, pilot re-prove, second-stage sweep, default flip (D-12..D-16, D-28)

Detail in R3 Q1-Q4.

- **Queue `config/cflags-proposals.toml`** (committed, no game bytes; read with `tomllib`; deterministic writer). Fields per proposal: `id` (F-nnnn), `exe`, `unit`, `glob` (always the exact unit path), `rule`, `base`, `functions`, `keeps`, `alternatives`, `source = sweep|sweep2|owner`, `candidate` + `candidate_sha256`, `evidence` paths under `build/`, `status = proposed|regated|failed|approved|landed|rejected|superseded`, `regate_exit`, `regate_cflags_sha256`, `regate_log`, `approved_by`, `approved_date`, `landed_commit`, plus **`siblings`**: the unit's other partial rows with their percents (see R2 below). Full sketch in R3 Q1.
  - One open proposal per unit.
  - A second hit merges by intersecting every function's 100% cells (fewest flags, then lowest cell number). An empty intersection is `failed`.
  - This needs every cell, so read `checks/NNNN.json` `cells[*]`, not just the first `sweep_hit`.
- **Verbs (`tools/reverseapoc/flags.py`):**
  - `flags propose --from-attempts [RUN]` (host). Copies the **hitting** `checks/NNNN.c` (D-28) to `build/flags/<id>/`. Idempotent. It also re-derives the D-16 list from attempts.jsonl.
  - `flags regate ID...` (container):
    1. writes a temporary cflags file: committed text plus one line, validated with `parse_cflags` and refused if it resolves to `DEFAULT_CFLAGS`;
    2. builds a copy of `src/` with the candidate in place;
    3. runs `check_unit` against it (**needs the D-27 rule fix**);
    4. runs gate's `cross_check`;
    5. if only a co-defined neighbour misses, retries with that neighbour back to `INCLUDE_ASM` (D-28) and records which variant passed;
    6. writes nothing in `src/` or `config/cflags.txt`.
  - `flags approve ID... --by NAME` (**owner-run, blocking checkpoint**):
    - refuses unless the status is `regated` with exit 0, the candidate sha is unchanged and `regate_cflags_sha256` equals today's;
    - refuses inside a session (`REVERSEAPOC_CLAIM` set) and refuses two IDs on one unit;
    - takes the unit claim and the gate lock, or refuses while `drive.lock` is held if those do not exist yet;
    - appends the rule with `# F-nnnn approved NAME DATE`, copies the C into `src/`, runs `gate_units`, restores on failure;
    - one commit per proposal (rule + C + status.csv + feed + queue row), trailers `Matched-By: reverseapoc drive` and `Flags-Approved-By: NAME (F-nnnn, DATE)`.
  - `flags list [--json]`.
  - `flags default --rule ... --by NAME` (D-14, owner-run):
    - pin every matched unit that has no rule to the old `*`;
    - run `gate --all --cflags <candidate>` (writes nothing) and an unpinned dry run (evidence of which pins are needed);
    - write cflags.txt and the hygiene-checked docs in one commit;
    - run `gate --all` again.
- **The R3 caveat that "the candidate must sit at its real path" is superseded:** with the D-27 logical-path rule, a copy of `src/` under `build/flags/<id>/src/` compiles every unit under its own rule. That avoids writing into the shared checkout while the driver runs.
- **D-13/D-16 data (re-derived from attempts.jsonl by a script):** 6 never-matched functions with a 100% cell:
  - ufo2p func_00026FD0 (u_00026dd0), func_0004DFD0 (u_0004dfd0), func_00061F30 (u_00060c50), func_0009C3A0 (u_0009c1a0);
  - tacp func_000779C0 (u_000778d0), func_0006FBD0 (u_0006fbd0).
  - Control: func_0008A100, which hit and then matched under the default with different C.
  - None of the 6 units holds a matched function today, so `keeps` is empty.
  - Hitting files and cells are listed in R3 Q2.
  - Each hitting file also defines the next row: func_00026FF0, func_0004DFF0, func_00061F50, func_0009C3C0, func_000779E0, func_0006FC00. Under the default these scored 1.03-68.95%; they were never measured under the hit flags.
  - u_00060c50 has two more partial siblings (46.45%, 67.50%) that a rule would bind.
  - [VERIFIED: R3 Q2, every listed cell confirmed `measured`, objdiff 100.0, `reloc_ok`, `differing = 0`]
  - The driver logs only the first `sweep_hit` and saves the best *plain* check (driver.py:662-670, re-read). For future runs, add `sweep_source` and `sweep_cells_100` to the v2 `check` record so `propose` does not depend on attempt dirs.
- **Second-stage sweep (D-15):**
  - ≤ 24 cells, about 10-20 s, version fixed at 10.6, CPU and stack flags from stage 1's best cell;
  - runs only when no stage-1 cell hits and the best cell is ≥ 90.0 with reloc ok;
  - groups: O1 replace `-o` (9), O2 best + one letter (≤ 8), `-zp1/2/4/8` (4), `-zm` (1), `-fp3/-fp5` (2);
  - implemented as `check.sweep2_cells(best)` beside `sweep_cells`, reported as `SweepReport.to_json()["stage2"]`, and run inside the same `attempt check --sweep` (no new `ATTEMPT_FORMS`). Hits go to the queue as `source = "sweep2"`.
  - **Spike `-zm` first** (one synthetic test in `test_check.py`): `account_unit`/`defined_functions` may assume one code segment. [ASSUMED] Drop the cell and record why if it breaks.
  - Every D-15 flag passes `_SAFE_FLAG` (cflags.py:32-36). [VERIFIED: R3 Q3]
- **D-14 evidence today:** 6 tiny functions agree on `-4r -oneatx -s -fpi`, none re-gated, and func_0008A100's matched C disagrees at `-4r`. D-28 calls this weak. Whether a size or branch threshold applies is R3 below.

### I. readlint (DEC-04, D-20, D-21)

Detail in R3 Q5.

- **Module and verb:** `tools/reverseapoc/readlint.py`, stdlib, host-only (no container), CI-runnable. Verb shape copied from `lint` (cli.py:867-880): `readlint [PATHS] [--units EXE/UNIT,...] [--tier N] [--report] [--json]`. Exit 0 clean, 1 violations, 2 tool error.
- **Reading:**
  - strict UTF-8 → `configure.normalize_source` → `configure.code_text` once, so anything but `#if 0` exits 2;
  - a tokenizer (comments, strings, chars, directives, numbers, identifiers, punctuators longest first) with 1-based lines;
  - dead `#if 0` tokens dropped, comments kept.
- **Structure:**
  - depth-0 definitions `IDENT ( ... ) {` by **any identifier** (the shared finder, §G);
  - `INCLUDE_ASM(name);` stubs exempt from every rule;
  - the header comment is the last comment between the previous depth-0 boundary and the declaration;
  - struct/union bodies at any depth;
  - enum initialisers exempt.
- **Scope:**
  - a matched unit is one with ≥ 1 `matched` row in status.csv;
  - others are reported `skipped`;
  - also scan project headers the unit includes (bare names under `include/`, excluding `common.h` and `watcom_compat.h`) for RL01/RL04.
- **Rules:**
  - **RL01** placeholder identifier outside stubs, comments and strings: `FUN_`, `sub_`, `DAT_` + hex, `func_[0-9A-F]{8}`, `D_[0-9A-F]{8}`. `LAB_/PTR_/UNK_` are proposed, see R5.
  - **RL02** missing header comment.
  - **RL03** malformed header. It must have a first line `<name>: <purpose ≥ 3 words>`, a line `Address: <UFO2P.EXE|TACP.EXE> 0x%08X` matching the row the name maps to, and ≥ 1 `Evidence: <string|table|call|vocab>: <text>` line, citing strings and tables by address so no game text enters the comment. This format is our proposal for D-20's "purpose, EXE address, evidence".
  - **RL04** struct field matching `(?i)^(unk|unknown|field_?(0x)?[0-9a-f]*|pad|padding|gap|filler|undefined)\w*$`.
  - **RL05** a cast to a pointer type over a parenthesised additive expression with a non-zero integer literal.
  - **RL06** magic integer. Allowed by context, not by value:
    - 0 / 1 / -1;
    - 2^k, 2^k−1 or their complement as a bitwise operand;
    - a shift count 0 < v < 32;
    - 2/4/8 as an operand of `* / + -` or inside `[]`;
    - `#define`/enum bodies;
    - a **tagged waiver** on the same line, for example `/* lit: reason */` (CONTEXT: "a tagged waiver form gives an exact count"), counted and reported.
- **Allowlist** `config/readlint-allow.csv` (`exe,name,reason`): **references only, never definitions**, counted and reported. D-22/D-23 make it necessary even for Tier 1; see R1 below.
- **Today's state:** all 4 matched files fail (placeholders; RL03 headers missing `Address`/`Evidence`; RL02 in `u_0006ee30.c`; the bare `3` and `4` call arguments in `u_00089980.c`). Pin this with a `--report` test. Strict `readlint src/` fails until the readability passes; that is expected, because strict form is the phase-gate check, not a per-commit CI gate (CONTEXT default).
- **No structs or raw offsets exist in `src/`/`include/` today,** so RL04/RL05 are exercised only by synthetic tests.

### J. stats and nightly totals (DEC-07, DEC-06)

Detail in R2 §7-§8.

- **attempts.jsonl v2:**
  - v1 lines stay valid; v2 lines carry `"schema": 2` and validate against `RECORD_FIELDS` keyed by (kind, version). `validate_record` demands an exact key set today (driver.py:393-400, re-read), and `test_committed_log_follows_the_schema` validates every committed line.
  - New attempt fields:
    - `pass`, `session` (`matching|readability`), `model_requested`, `budget_usd`, `worker`;
    - `hook_blocks` = `len(result.permission_denials)` (pilot: 41 in 40 sessions);
    - `gate` `{exit, claimed_ok, regressions, problems}`;
    - optional `sweep_source`, `sweep_cells_100`.
  - New kinds: `limit`; ENDED/STOPPED `totals`; STARTED `recovered`.
  - Optional precision: hooks append a JSON line per deny to `<attempt dir>/hooks.jsonl` to separate hook denials from CLI permission denials.
- **Nightly `totals`** (DEC-06): `workers`, counted sessions by outcome, turns, the four token classes, cost, session seconds and night wall seconds, hook blocks, regressions stopped, limit waits {count, seconds}, aborts, the same per model and per session kind. `_commit_log` runs after all workers drain (R2 R5).
- **Match classing (from git, so it runs in CI):**
  - walk `git log -- config/ufo2p/status.csv config/tacp/status.csv`, diff each commit against its parent, and take the starts that become `matched`;
  - class by trailers:
    - `Matched-By: reverseapoc drive` without hint trailers → `unattended`;
    - with `Match-Hints:` → `human-hints`;
    - no `Matched-By` → `human-written`;
    - `Flags-Approved-By:` → per the R4 ruling below.
  - Today: 3 unattended (c83cf4e, d288ad6, 955931f), 2 human-written (5ab2e79, a463163). AGT-11 is the unattended count. [VERIFIED: R2 §7 trailer read]
  - DEC-07's "owner notes in manual packs" cannot be read in CI (manual packs are gitignored). The `Match-Hints:` trailer is the committed carrier for them. Record this reading in the plan.
- **Output:** match rate by function-size bucket, attempts per match, turns, tokens, cost and time per matched function, regressions stopped, hook blocks, the three-way split, and the per-model (D-09), per-kind (D-18) and per-tier splits. Over the whole Phase 6-7 history (v1 records lack some fields; report them as "n/a for v1").
- **Refusals (ROADMAP SC6):** exit 2 naming the line number for non-JSON, non-object, or a line failing its version's schema. A missing trailer is not an error; it is classed `human-written`.

### K. Progress coverage and 999.4 (DEC-05)

Detail in R1 Q6, R3 Q6.

- **Separate derivation** `derive_mechanics(config_dir, progress) -> Mechanics | None` in `tools/progress.py`:
  - reads `mechanics.toml` (`tomllib`), the members CSV and the asm list;
  - a missing file means no section, so synthetic CI configs keep working;
  - a malformed file is a `ProgressError` (exit 2) in the Pages job, never in `gate`, whose feed derivation stays independent.
- **Per item:**
  - functions total/matched/partial/unmatched and bytes total/matched/partial, joined by `(exe, address)` with status.csv and functions.csv;
  - **two figures per D-22:** the must-match set (`role = member`) and the full closure (all roles except asm);
  - per tier, the **union** of members;
  - asm rows as their own group outside the percentage (D-23).
- **progress.json:** add `"mechanics": {...}|null` and keep `PROGRESS_VERSION` 1 (no test pins the top-level key set).
- **index.html:**
  - a `Mechanics coverage` `<ul class="items">` section, text figures first, a three-segment `aria-hidden` bar;
  - issue numbers as text, not links (`_check_static` restricts hrefs);
  - located-but-unmatched tiers show their located state and sign-off (D-05 rewording of SC5).
- **pages.yml:** add `config/mechanics.toml`, `config/mechanics-members.csv` and the asm list to `on.push.paths`, and update `test_workflows.py` `PATHS`.
- **999.4, CSS/HTML only, no script:**
  1. a `<details>` list of matched and partial functions per EXE (keyboard/touch), keeping the `title` attributes;
  2. `.mosaic{...;overflow-x:auto}`, plus `.mosaic svg{min-width:48rem}` inside the 40rem query, plus `<div class="mosaic" tabindex="0" role="region" aria-label=...>`, plus an HTML legend above it;
  3. a non-zero bar segment `<span class="nz" style="width:X%">` with `.bar .nz{min-width:2px}`.
  - Tests pinning exact markup change with it (test_progress_page.py `.mosaic svg` rule and `test_page_embeds_the_mosaic`, test_page_shape's bar markup).
  - Keep the page tells (no script, no gradient, deterministic bytes).

## Prerequisite fixes (the planner's early tasks)

Each item is TDD. "Both slices" means R2 and R3 found it independently.

| # | Fix | Evidence (file:line, re-checked this pass where marked ✓) | Blocks |
|---|---|---|---|
| P1 | **Rule by logical path (D-27).** `_compile` calls `compile_fn` with no `root` ✓check.py:255-261, so `compile_source` uses `REPO_ROOT` ✓compiler.py:564 and `source_rule` matches the glob against the physical repo-relative path ✓compiler.py:662-673. **Reconciled fix (both slices):** pick the rule from the logical `src/<exe>/<unit>.c` (R3's `rule_path` keyword on `compile_source`/`source_rule`, D-27). Take the **include list and object containment from the view root** (R2's root = src-root parent), because `_include_list` reads `<root>/include` ✓compiler.py:359-363 and D-24 snapshots `include/` into the view. `check_provenance`'s `_compile_root` ✓check.py:973-978 returns `REPO_ROOT` for any tree inside the repo, so it must select the rule the same way. Test that a ninja object built under a per-unit rule still passes provenance. `gate --partial` compiles `best/` with `src_root=saved.parent` ✓gate.py:786 and gets fixed by the same change | D-24 views, D-12 re-gates, `gate --partial` under unit rules |
| P2 | **Refuse `gate EXE/UNIT` with a non-default `--cflags`, `--watcom-manifest` or `--watcom-dir` (D-27).** `check_kwargs` passes them through ✓gate.py:141-151. `gate_units` guards only `--src` (`_committed_src`) ✓gate.py:242-247, 548-559. Keep `gate --all --cflags` (gate.py:685-726, writes nothing) as the D-14 dry run | D-12 approval meaning, D-14 |
| P3 | **Always-layer protection of `config/cflags.txt` (D-27).** `_PROTECTED_FILES` lists only targets.toml and watcom.toml ✓hooks.py:71-74. `flags approve` writes from Python, which the hooks never see. If an agent-tool exemption is ever needed, model it on the D-46 `NOTES_ENV` env exemption ✓hooks.py:80-83. Also deny `config/cflags-proposals.toml` to sessions | D-12 |
| P4 | **Concurrency-safe shared writes (D-27).** Pre-gate snapshot includes `attempts.jsonl` ✓driver.py:1569-1570 (restore at 1536-1550). `_reset` restores all of `include/` ✓driver.py:1514-1532. `gate --partial` writes status.csv (gate.py:760-816). `_commit_headers` stops the night on any foreign untracked header ✓driver.py:1640-1645. Whole-tree audit (driver.py:1109-1138, 1266-1278). Single-session `_Night.live` and counters (driver.py:863-868). Fix: everything under the gate lock or scoped to the session; restore only status.csv and the feed; one git lock; `GIT_OPTIONAL_LOCKS=0` | D-24 / workers |
| P5 | **Rename prerequisites (D-29).** `c_name` ✓symbols.py:154-159; placeholder-only `_PLACEHOLDER/_MARKER/_DEFINITION` ✓configure.py:238-242 and `check_unit_source` (configure.py:472-495); `source_marks` ✓check.py:508-523; drift test by name ✓tests/test_drift.py:55-73; `_refuse_renamed` ✓symbols.py:199-203; `gate._reverted`; gate.py:289-291 notes the gap. Fix: one shared renamed-aware finder used by all of them; drift test compares by start | first readability pass, readlint, renames |
| P6 | **Hooks for view paths (D-24).** The always layer protects `build/` except the notes file (`_PROTECTED_DIRS`, ✓hooks.py:67-70), and the inline-asm/pragma scan runs only under `_SCANNED_DIRS = ("src", "include")` (✓hooks.py, near L77). Without a fix, the view unit is either unwritable or **silently unscanned** (R2 pitfall). Exempt the env unit file and proposals path the way notes are exempt, and scan the env unit file | D-24 sessions |
| P7 | **Wrapper uses the view roots.** `container_check_argv` passes default roots ✓attempt.py:222-226. Add `--src/--config/--cflags/--build/--log` into the view; validate the new env paths like `_notes` (attempt.py:191-200) | D-24 sessions |
| P8 | **Model plumbing.** Constants baked into argv ✓session.py:35-39; `EXPECTED_MODEL` ✓streamjson.py:63; driver/canary `check_init` without `expected_model` ✓driver.py:1508-1509, ✓2423-2424; fixed Opus `COAUTHOR` ✓driver.py:97 | D-09 Fable passes |
| P9 | **Defaults.** `max_sessions` 30 → 60 and `target_matched` 10 → off ✓driver.py:1772-1773, ✓cli.py:1292-1295 (`type=_positive` cannot express off) | D-07, CONTEXT default |
| P10 | **Sweep evidence.** The driver keeps only the first `sweep_hit` and the best plain C ✓driver.py:662-670, driver.py:625-638, attempt.py:315-345. Add `sweep_source` / `sweep_cells_100` to the v2 record | future flag proposals (D-13 itself reads the attempt dirs) |

The "6 matched at phase start" wording is already corrected to 5 in CONTEXT `<domain>` (R3 Q2 point 6). Nothing left to fix.

## Research findings that touch locked decisions (not settled by D-22..D-29)

The owner rules on each before or during planning. Research does not change any decision.

**R1. Named Tier 1 code will reference functions that stay unmatched (D-20 × D-22/D-23).** Slice 3 concluded that "Tier 1 needs no readlint allowlist, because its callees are all in Tier 1 by D-02". D-22 removed that premise: Tier 1 members call hubs (`get_text`, the tick readers, drawing, the TACP cycle) and asm rows that are not required to match. Those keep their `func_X` placeholders, and strict RL01 then fails every Tier 1 unit that calls them. Options:
- (a) Readability passes also **name** the hubs and asm rows that Tier 1 references, by D-19 rename proposals on unmatched functions. After D-29 the finder accepts `INCLUDE_ASM(GetText);` (the macro emits no bytes, include/common.h:19 per R2). The names rest on call-context evidence.
- (b) Allowlist those references in `config/readlint-allow.csv`, counted and reported.
- (c) Mixed: name hubs with strong evidence (`get_text`, the tick readers), and allowlist the rest.
- Recommendation: (c).

**R2. A hub that is also an item's entry (D-22 × D-04/D-26).** D-22 lists "the BIOS-tick readers" as hubs. Slice 1's draft #997 entries are those same readers (UFO2P `0x11430`, TACP `0x11500`/`0x116B0`), and D-26 starts the spike from them. Options:
- (a) An item's entry functions are always members of that item's must-match set, and the hub rule applies only below entries.
- (b) The hub rule wins: #997's must-match set starts at the time-advance loop that calls the readers, and the readers are optional.
- Recommendation: (a). An entry is evidence the owner signed; making it optional would leave #997's own time base unmatched.

**R3. Per-unit rules bind sibling functions; unit cuts are drafts (D-12).** A rule approved for one function binds every later match in that unit. Partial percents of siblings scored under the default become stale (u_00060c50 has two siblings at 46.45% and 67.50%). Options:
- (a) The proposal lists the siblings (`siblings` field) and the approval covers them knowingly. If a sibling later needs other flags, the cue is a unit re-cut, not a second rule.
- (b) Before approval, re-score each sibling's best C under the proposed flags as a diagnostic, and block approval if any sibling drops.
- (c) Hold rules for units with partial siblings until those siblings are measured.
- Recommendation: (a), with (b)'s numbers attached as evidence when cheap.

**R4. How flag-approved matches are classed for AGT-11 (D-13 delegates this to "the stats rules").** It decides up to 6 (plus any bonus neighbours) of the 7 matches AGT-11 still needs. Options:
- (a) `unattended`: the agent wrote the C unattended, and the owner's approval is a project configuration decision, not a hint to the agent.
- (b) `human-hints`: the match needed an owner action.
- Recommendation: (a), with the `Flags-Approved-By` trailer kept so `stats` can also show the flag-approved subset separately. Because D-13 delegated this, it can be confirmed at plan review rather than at a separate checkpoint.

**R5. readlint edge rules (D-20 wording).**
- (i) D-20 says "integer literals". Report floating literals too (physics and timer constants matter to #997), only in `--report` mode, or not at all? Recommendation: `--report` only until ruled.
- (ii) Extend RL01 to Ghidra's `LAB_`, `PTR_`, `UNK_` + hex prefixes ("or similar" in D-20 is attached to struct fields). Recommendation: include them (low risk; none occur today).

**R6. Threshold for D-14 default-flip evidence.** D-28 calls a single hit on a 32-48-byte function weak evidence, but sets no bar. Options:
- (a) Tiny-function hits count toward per-unit rules only. A default flip needs ≥ 3 agreeing **re-gated** functions with a branch or loop, or ≥ N bytes (for example 64), from different regions of both EXEs.
- (b) Phase 5 D-18 literally: 3 agreeing functions from different regions. The 6 pilot hits would qualify once re-gated.
- (c) No default flip in Phase 7.
- Recommendation: (a).

## Recommended plan ordering / dependency graph

```
Wave 1 (parallel; no deps)
  W1a  paperwork: reword DEC-03/DEC-05 + ROADMAP SC3/SC5 per D-05 (+ D-22 hubs, D-23 asm);
       docs/workflow.md + PROJECT.md decomp.wtf row (D-06)
  W1b  spike 007 (host, orig/ + cd.iso; 1-day box)  --> NOTIFY owner of any #997 result at once
  W1c  P1 rule-by-logical-path, then P2 gate --cflags refusal  (check.py/compiler.py, gate.py)
  W1d  P3 hooks cflags + P6 hooks view paths  (hooks.py)
  W1e  callgraph.py + mechanics.py loader/schema + members generator (TDD, synthetic LE)
  W1f  progress.py 999.4 fixes (independent of mechanics data)

Wave 2
  W2a  P5 rename prerequisites: shared finder, c_name, configure, source_marks, drift by start
       (after W1c: both touch check.py)
  W2b  asm detector + committed asm list                      (after W1e)
  W2c  mid-row reference classification + Tier 1 draft with hub-rule numbers (after W1e, W1b)
  W2d  attempts.jsonl v2 schema (+ test_attempts_schema), then stats (git trailer classing)
  W2e  flags.py propose/regate/list + second-stage sweep + -zm spike  (after W1c P1/P2, W1d P3)

  CHECKPOINT owner: asm list sign-off (D-23)                  (after W2b)
  CHECKPOINT owner: Tier 1 sign-off incl. hub rule (D-04, D-22); rule R1/R2 here at the latest
                                                              (after asm sign-off, W2c, spike verdict)

Wave 3 (driver.py is one file: serialise these plans)
  W3a  views + wrapper roots (P7) + per-session hook env + ledger audit      (needs P1, P6)
  W3b  claims + drive.lock + gate/git locks + P4 + coordinator/worker threads + global pause
       + cap reservation + v2 records/totals (DEC-06)                       (after W3a, W2d)
  W3c  tier picker (SCC callees-first, hubs/asm never block), D-08 re-queue (after W3b, Tier 1 signed)
  W3d  model escalation + budgets + init/co-author (P8) + defaults (P9)    (after W3b)
  W3e  readlint (TDD, all rules + selectors + allowlist + waivers)         (after W2a; parallel with W3a-d)
  W3f  progress coverage view (derive_mechanics, both figures, asm group, pages.yml) (after W1e, W2b)
  W3g  flags approve/default (claim + lock, or refuse while drive.lock held) (after W2e, W3b)

  CHECKPOINT owner: D-13 batch. Executor runs `flags regate` on the 6 (container tooling, not claude -p);
                    owner runs `flags approve` (blocking)        (after W3g; may run before W3c)
  CHECKPOINT owner: first Tier 1 matching night(s) on Opus (D-11) (after W3c, W3d)
  CHECKPOINT owner: Fable canary (D-25), before the first Fable pass, i.e. after a function has 2 capped passes

Wave 4
  W4a  rename apply step + readability session kind + /goal + readability skill (writing-skills)
       + watcom-decomp update (writing-skills)                  (after W2a, W3b, W3e)
  CHECKPOINT owner: matching nights until Tier 1 must-match set is all matched (repeatable)
  CHECKPOINT owner: readability nights per closed sub-tree; renames applied by the driver
  CHECKPOINT owner: Tier 2, 3, 4 sign-offs (D-04), any time after W2c tooling; parallel with nights
  CHECKPOINT owner (optional): D-14 default flip, if R6's bar is met

Wave 5
  Phase gate (main checkout recipe): readlint src/ exit 0; gate --all; ninja verify; rebuild + cmp silent;
  stats shows >= 10 unattended; every tier signed; host + container suites; VALIDATION sign-off
```

- **Parallel safely:** W1a-W1f; W2b/W2c/W2d/W2e; W3e and W3f alongside the driver chain.
- **Never parallel:** plans editing `driver.py`, `check.py` or `hooks.py` at the same time. Host and container suites never run at once.
- **Owner-run steps (blocking-human):** asm list sign-off; each tier sign-off (with the hub rule for Tier 1); `flags approve` batches; the Fable canary; every real matching or readability night (D-11); an optional default flip. Spike 007's #997 report is a notify, not a gate.
- Matching nights can start before readlint and renames exist (D-17 keeps placeholders while matching). Readability nights need W4a.
- Main-checkout plans (gate, approvals) use the `gsd-main-checkout-plans` recipe.

## Risks

- **K1 Scale of Tier 1 even with hubs.** The bounded must-match counts are not measured yet. If the hub rule leaves several hundred functions, Tier 1 takes many nights at the pilot rate (3 matches / 40 sessions, about USD 14 per match). Mitigations: present the numbers at the sign-off; Fable escalation; D-13 flag rules; callees-first context. The deferred human-hints step is the fallback if Tier 1 stalls.
- **K2 Check time.** Every check compiles every committed unit of both EXEs, with a 580 s wrapper limit. With 3 sessions plus a gate on Docker Desktop, this grows as matches accumulate. Measure per committed unit early. A content-addressed object cache keyed by the provenance stamp (compiler.py:739-770 per R2) lets views reuse HEAD objects.
- **K3 Git index contention and blast radius.** Mitigated by one git lock, `GIT_OPTIONAL_LOCKS=0` and one retry. A pinned-file breach is unattributable and stops the night for all workers (acceptable; it must kill and contain every session).
- **K4 View include root.** Compiling with the view as compile root changes guest-path mapping under wibo in the container. P1 needs a real compile test of a view on host and in the container.
- **K5 Renames touch many units.** One rename of a widely called function re-gates every user in one all-or-nothing gate, and it waits for claims. This can stall behind live sessions. Batch renames between nights if needed.
- **K6 asm misclassification.** A C function wrongly marked asm leaves the must-match set silently; an asm row wrongly kept wastes sessions. The owner sign-off plus listed "unclear" rows mitigate this.
- **K7 Per-unit rules on draft units** bind later matches (R3). A wrong unit cut then needs a re-cut.
- **K8 Fable cost and limits.** Fable spends subscription limits faster [ASSUMED]. LIMIT pauses stop all workers. The canary may show that the CLI rejects the ID, which would block escalation until the CLI is upgraded.
- **K9 Spike may not find the 36-unit accumulator.** Then #997 stays "18.2 Hz BIOS tick, sub-step rule unknown". That is still a finding for the owner; verdict PARTIAL.
- **K10 Contamination.** OpenApoc offsets and headers stay in scratch and are never committed. Names follow D-21 (vocabulary only). Schema and drift tests allowlist committed fields so no game bytes enter (hex only as 64-char SHA-256).
- **K11 Readability byte changes.** Literal-type slips change codegen. The gate refuses them, at the cost of wasted sessions; the prompt should warn.

## Open questions

1. What do the must-match counts come to under candidate hub rules (K values, pointer edges on or off)? The tool answers this at W2c; the owner needs it at the Tier 1 sign-off.
2. Does q2 find the 36-unit accumulator, and does TACP's battle loop pace the same way at a different scale? (Spike 007.)
3. What is the `get_text` argument recovery rate (q4)? It decides how many Tier 2-4 entries can be found by string.
4. How many mid-row references are missed function starts? A missed start changes `functions.csv`, so classify before Tier 1 freezes.
5. Does `-zm` break `account_unit`/`defined_functions`? (Synthetic spike in W2e.)
6. Does CLI 2.1.308 accept `claude-fable-5-1`, and what does init report? (Owner canary.)
7. Which base do PR #1685's `FUN_` addresses use? Not needed for the data route. The owner decides whether it matters (R1 open question 3).
8. Do the D-13 re-proves pass as written (bonus neighbour matches) or only reduced? Only the container regate knows.

## Validation Architecture

### Test Framework
| Property | Value |
|---|---|
| Framework | pytest (stdlib tooling, TDD), ruff (`line-length = 100`, `target-version = py314`) [VERIFIED: pyproject.toml:28-37] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["."]`); fixtures in `tests/conftest.py` (`ORIG_DIR`, honouring `REVERSEAPOC_ORIG`; `requires_version`, `requires_runner`, `requires_capstone`) |
| Quick run command | `uv run pytest -q tests/test_<module>.py -x && uv run ruff check .` |
| Full suite command | `uv run pytest -q && uv run ruff check .` (host); `docker compose run --rm test` (container, compose.yaml); never both at once |
| Stand-in claude | `tests/fakeclaude.py` (extend with `--write-env-unit`, `--sleep`, LIMIT/STOP modes); tmp-repo fixtures in `tests/test_driver.py` (`_make_repo`, `Night`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test type | Automated command | File exists? |
|---|---|---|---|---|
| DEC-01 | typed edges (direct/tail/pointer/table/hand), jump tables give no edges, runtime rows stop the walk, mid-row refs reported | unit (synthetic LE) | `uv run pytest -q tests/test_callgraph.py` | ❌ Wave 0 |
| DEC-01 | closure: cycle, shared callee listed once with both items, `via` weakest kind, hub stop, `role` column, asm role | unit | `uv run pytest -q tests/test_mechanics.py` | ❌ Wave 0 |
| DEC-01 | mechanics.toml strict parse (unknown scope/key, non-game entry, `duplicate_of` an `out` item, bad address refused); signed tier `members_sha256` change fails | unit + CI schema | `uv run pytest -q tests/test_mechanics.py tests/test_drift.py` | ❌ / extend |
| DEC-01 | members file and asm list regenerate byte-identical; get_text 50 sections; tick readers are the only `int386(0x1A)` callers; reachability within ±1% | real-file (skips w/o orig/) | `uv run pytest -q tests/test_mechanics_real.py` | ❌ Wave 0 |
| DEC-01 | spike checker can fail (planted EXPECTED, in-memory mutant, table byte flip) | spike scripts | `uv run python .planning/spikes/007-locate-997-training/q1_timebase.py` (etc.) | ❌ Wave 0 |
| DEC-02 | two workers never hold one unit (O_EXCL); broken private unit in B never reaches A's gate; gate calls never overlap; src/ differs from HEAD only by the landing unit at gate time | integration (fake claude, fake gate) | `uv run pytest -q tests/test_driver_workers.py` | ❌ Wave 0 |
| DEC-02 | stale claim from another run moved + recorded; held drive.lock refuses a second drive; no `os.kill` in driver (grep test) | unit | same | ❌ |
| DEC-02 | ledger audit: tracked edit outside the view stops the night and is attributed; edit in another session's view caught by view hash; worker B's records survive A's failed gate | integration | same | ❌ |
| DEC-02 | tier picker: SCC order leaves first, hubs/asm never block, claimed unit skipped not dropped, variety rule off | unit | `uv run pytest -q tests/test_driver_pick.py` | extend |
| DEC-02 | rename end-to-end: symbols.csv, unit text, status.csv name, feed in one commit; collision refused; claimed unit deferred and rewritten at landing | integration (tmp repo, fake gate) | `uv run pytest -q tests/test_rename.py` | ❌ Wave 0 |
| DEC-02 | D-29: `c_name` for symbols.csv func/data rows; configure D-12 with renamed row; `source_marks` renamed-aware; drift test by start | unit | `uv run pytest -q tests/test_symbols.py tests/test_configure.py tests/test_check.py tests/test_drift.py` | extend |
| DEC-03 | P1: unit under `build/...` compiles with its unit rule (fake compile_fn captures rule/root); ninja provenance unchanged; `gate --partial` uses the unit rule | unit | `uv run pytest -q tests/test_compiler.py tests/test_check.py tests/test_gate.py` | extend |
| DEC-03 | P2: `gate ufo2p/u_x --cflags tmp.txt` exits 2, writes no row; `gate --all --cflags` still runs | unit | `uv run pytest -q tests/test_gate.py` | extend |
| DEC-03 | flags: propose picks `checks/NNNN.c` not `best/`; merge by intersection; empty → failed; regate never writes cflags.txt or src/ (hash + mtime), refuses DEFAULT_CFLAGS, exit 1 when a kept function drops or cross-check drops a row; reduced variant tried; approve refuses status≠regated, changed sha, stale cflags sha, `REVERSEAPOC_CLAIM` set, two IDs one unit; restores byte-for-byte on gate failure | unit (fake compile/objdiff) | `uv run pytest -q tests/test_flags.py` | ❌ Wave 0 |
| DEC-03 | D-16 re-derivation script reproduces the 6 functions from committed attempts.jsonl | unit (committed data, CI) | `uv run pytest -q tests/test_flags.py -k pilot` | ❌ |
| DEC-03 | second-stage sweep: runs only when no hit and best ≥ 90 with reloc ok; ≤ 24 cells; same temp-rule guard; `-zm` object accounting | unit | `uv run pytest -q tests/test_check.py -k sweep2` | extend |
| DEC-03 | real re-gates of the 6 pilot proposals; `gate --all` after each approval; final rebuild + cmp | container, owner checkpoint | `docker compose run --rm build ... flags regate ...` | manual-gated |
| DEC-04 | RL01 each pattern as definition/prototype/extern/use fails; same names in stub/comment/string/`#if 0` pass | unit | `uv run pytest -q tests/test_readlint.py` | ❌ Wave 0 |
| DEC-04 | RL02 missing / separated comment; RL03 wrong name line, wrong EXE/address, bad evidence kind, empty text; RL04 `unk_4`, `field_0x8`, `pad[2]`, `padding_end` fail, `paddle` passes; RL05 three forms fail, `*(int *)p` passes; RL06 table of R3 (`x = 36` fails, `a[i * 4]` passes, `x & 0xF0` fails, tagged waiver passes and counts 1) | unit | same | ❌ |
| DEC-04 | unmatched unit skipped; `#ifdef` → exit 2; lone CR → exit 2; allowlist covers references only (a definition on it still fails); waiver/allowlist counts reported; `--units/--tier/--report` | unit | same | ❌ |
| DEC-04 | committed tree: `readlint --report src/` exits 0 and lists today's 4 failing files; strict form exits 1 until readability | CI (committed data) | `uv run pytest -q tests/test_readlint.py -k committed` | ❌ |
| DEC-05 | `mechanics` key shape/order; tier union counts a shared function once; member vs full-closure figures; asm group outside percent; non-game member → exit 2; missing file → `null` and no section; two renders byte-identical; hrefs unchanged | unit (CI) | `uv run pytest -q tests/test_progress.py tests/test_progress_page.py` | extend |
| DEC-05 | 999.4 markup strings (`overflow-x:auto`, `min-width:48rem` in 40rem query, `tabindex="0"` region, `<details>` list, `.bar .nz{min-width:2px}`); pages.yml paths | unit (CI) | `uv run pytest -q tests/test_progress_page.py tests/test_workflows.py` | extend |
| DEC-06 | one LIMIT pauses all workers; exactly one probe after backoff; night cap 60 across workers with uncounted sessions released; STOP kills all live sessions; `totals` and `limit` records validate; defaults (`--max-sessions 60`, `--workers 3`, target-matched off) | integration (fake claude) | `uv run pytest -q tests/test_driver_workers.py tests/test_cli.py` | ❌ / extend |
| DEC-07 | malformed line (non-JSON, non-object, schema fail) → exit 2 naming the line; v1 and v2 lines read together; trailer-less match → `human-written`; `Match-Hints` → `human-hints`; `Flags-Approved-By` per R4; missing trailer is not an error; committed history gives 3 unattended / 2 human-written | unit (synthetic git repo) + CI on committed log | `uv run pytest -q tests/test_stats.py tests/test_attempts_schema.py` | ❌ / extend |
| DEC-07 | `hook_blocks` = len(permission_denials) recorded per attempt | unit | `uv run pytest -q tests/test_driver.py -k hook_blocks` | extend |
| AGT-11 | escalation: two capped Opus passes → next argv `--model claude-fable-5-1 --max-budget-usd 12.50`; init accepts requested model, rejects the other; unknown model refused for co-author | unit | `uv run pytest -q tests/test_session.py tests/test_streamjson.py tests/test_driver.py -k escalat` | extend |
| AGT-11 | ≥ 10 unattended matches | `stats` over git at phase gate | `uv run reverseapoc stats` | manual-gated (owner nights) |
| hooks | always layer denies Edit/Write of `config/cflags.txt` and `cflags-proposals.toml`; env unit file writable, other view files and `src/**`/`include/**`/symbols.csv denied for sessions; pragma/inline-asm scan fires on the env unit under `build/`; readability kind cannot write cflags or queue | unit | `uv run pytest -q tests/test_hooks.py` | extend |
| skills | watcom-decomp still ≤ 300 lines, nine sections, paths/verbs exist after the view/proposal update; readability skill paths and commands exist | unit | `uv run pytest -q tests/test_skill.py` | extend (+ new skill test) |

### Negative tests each new tool needs (summary)
- **readlint:** one failing case per rule RL01-RL06, plus exempt contexts (stubs, comments, strings, `#if 0`, enum/`#define`), tool errors (exit 2) and an allowlist definition misuse.
- **stats:** a malformed line (each of the three shapes) exits 2 with the line number; the missing-trailer case is classed `human-written`, not an error.
- **claims:** an O_EXCL race between two workers; a stale claim; a held drive.lock; no PID probing.
- **re-gate refusal:** `flags approve` refusals (five conditions); `flags regate` refusing `DEFAULT_CFLAGS`; regate leaves cflags.txt and `src/` untouched.
- **gate `--cflags` refusal:** write mode exits 2 with no row; `--all` allowed.
- **hooks:** cflags.txt in the always layer; view paths; the scan on the view unit; the readability allowlist.
- **audit:** stray tracked edit; foreign view edit; a ledger file with unexpected bytes.

### CI vs orig/
- **Runs in CI (no game files):** everything synthetic (callgraph on synthetic LE, mechanics schema on committed files, readlint, stats on synthetic git plus the committed log, flags with fake compile/objdiff, driver workers with fake claude and fake gate, hooks, progress, workflows, skill tests, the D-16 script on committed attempts.jsonl).
- **Skips without orig/ (host and container):** the members and asm-list drift tests, the callgraph regression pins (get_text sections, tick readers, reachability), and the spike scripts (host only; they also need `cd.iso`).
- **Needs the container toolchain (owner or executor, never CI):** real `flags regate`/`approve`, real `gate --all`, rebuild + cmp, a real compile of a view (K4).

### Sampling Rate
- **Per task commit:** the quick command for the touched module(s) plus `uv run ruff check .`.
- **Per wave merge:** the full host suite `uv run pytest -q && uv run ruff check .`, then the container suite `docker compose run --rm test` (not concurrently).
- **Phase gate:** both full suites green, `uv run reverseapoc readlint src/` exit 0, `gate --all` exit 0, `ninja verify`, rebuild + cmp silent for both EXEs, `uv run reverseapoc stats` showing ≥ 10 unattended, every tier signed in mechanics.toml; then `/gsd-verify-work 7`.

### Wave 0 Gaps
- [ ] `tests/test_callgraph.py`, `tests/test_mechanics.py`, `tests/test_mechanics_real.py`: DEC-01
- [ ] `tests/test_readlint.py`: DEC-04
- [ ] `tests/test_stats.py`: DEC-07
- [ ] `tests/test_flags.py`: D-12..D-16
- [ ] `tests/test_driver_workers.py`: DEC-02/DEC-06 concurrency (or a section in test_driver.py)
- [ ] `tests/test_rename.py`: D-19/D-29
- [ ] `tests/fakeclaude.py` extensions (`--write-env-unit`, `--sleep`, model echo)
- [ ] spike 007 scripts and README
- [ ] framework install: none (pytest and ruff present)

## Security Domain

`security_enforcement` is enabled (ASVS level 1).

| ASVS Category | Applies | Standard control |
|---|---|---|
| V2 Authentication | no | No auth surface. The driver uses the owner's CLI login; no secrets in tracked files |
| V3 Session Management | no | |
| V4 Access Control | yes (agent write scope) | Two-layer hooks (always + per-session env allowlist), driver ledger audit, owner-only cflags.txt and approvals, the driver as the only naming writer |
| V5 Input Validation | yes | Strict parsing of mechanics.toml, members CSV, asm list, cflags-proposals.toml, proposals.jsonl, attempts.jsonl v1/v2 (exact key sets, enums, address formats, C-identifier checks, header text scans); `_SAFE_FLAG` for flags |
| V6 Cryptography | no (integrity only) | SHA-256 for `members_sha256`, `candidate_sha256` and cflags shas via `hashlib`; no hand-rolled crypto |

| Threat | STRIDE | Mitigation |
|---|---|---|
| A session edits files outside its claimed unit (another session's view, src/, cflags, symbols.csv) | Tampering / Elevation | Per-session env allowlist, always-layer protection, view hash and ledger audit, fail-closed night stop |
| A session smuggles inline asm or pragmas through a view file under build/ | Tampering | Scan the env unit file (P6) |
| Matched rows written under unapproved flags | Tampering | P2 gate refusal; approve-only cflags writes; `regate_cflags_sha256` freshness |
| A hand-edited member list or tier changes after sign-off | Repudiation / Tampering | Drift test; `members_sha256` check fails the schema test |
| Game bytes or OpenApoc GPL text enter committed files | Information disclosure / legal | Field allowlists in schema tests, hex only as 64-char SHA-256, OpenApoc data kept in scratch, D-21 name rules |
| A rename collision or a malicious header proposal | Tampering | Validation (identifier, uniqueness, scans), all-or-nothing gate, restore on failure |
| A crash leaves claims or a dirty src/ | DoS | drive.lock + stale-claim recovery; `_clean_tree` preflight |
| PID probing kills processes on Windows | DoS | No `os.kill(pid, 0)`; OS lock instead (grep test) |

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|---|---|---|---|---|
| uv / Python | all tooling | ✓ | Python 3.14.5 | — |
| capstone | callgraph, spike, asm detector | ✓ | 5.0.9 (pin) | — |
| `orig/` UFO2P.EXE, TACP.EXE | generator, drift tests, spike, gate | ✓ (host) | manifest-checked | tests skip in CI |
| Steam `cd.iso` | spike q5 / OpenApoc offset re-location | ✓ | `C:\Program Files (x86)\Steam\steamapps\common\XCom Apocalypse\cd.iso` | skip q5; data route via code refs only |
| Docker + image (objdiff 3.8.2, wibo, Watcom 10.6, clang 18) | check, gate, regate, container suite | ✓ (Phase 5/6) | — | — |
| `gh` (read-only issue text) | item list | ✓ | 2.92.0 | — |
| Claude CLI | owner nights, canaries | ✓ (owner) | 2.1.308 on all pilot attempts | Fable acceptance unverified → canary |
| Ghidra 12.1.4 | optional single-function drafts | in image | — | not needed for edges |

[VERIFIED: R1 environment table, R2 §4]. Nothing missing blocks execution.

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | The sound timer is the HMI SOS library | Summary | Naming only; "not the game clock" rests on the xref scan |
| A2 | Cityscape loop candidate `func_00022EF0`, speed-table candidate `0x1303E0` | Summary, §B | Spike looks elsewhere among the 28 callers |
| A3 | `scenario/unitr.dat` carries the battle stat changes for #263-1 | §A | #263-1 entries move; q3 tests it |
| A4 | PR #1685 matrices carry over by VA identity | §A (Tier 2) | Re-locate by signature |
| A5 | Off-alignment rows are mostly asm/library code | §C | Fewer exclusions; owner list settles |
| A6 | Proposed in/out lines for UI-chrome items (R1 Q4) | §A | Owner rules per tier |
| A7 | NTFS O_EXCL create is atomic; rename-over is unsafe as "first wins" | Standard Stack, §E | Claim races (low; code base already relies on O_EXCL) |
| A8 | `os.kill(pid, 0)` terminates the process on Windows | §E | Only matters if someone adds probing (D-24 forbids it) |
| A9 | CLI 2.1.308 accepts `claude-fable-5-1` and init reports that ID | §F | First Fable session STOPs; canary catches it |
| A10 | Fable spends subscription limits faster than Opus | §F, K8 | More LIMIT pauses |
| A11 | Claude Code runs `git status` at session start | §E | index.lock races; mitigated by `GIT_OPTIONAL_LOCKS=0` anyway |
| A12 | Cache writes priced 1.25x input | §F | Fable arithmetic shifts a few percent (cap already settled by D-25) |
| A13 | Watcom's knowledge of a same-module callee can change caller codegen, so the reduced variant may lose the hit | §H | Reduced variant passes more often (harmless) |
| A14 | `-zm` objects may break `account_unit`/`defined_functions` | §H | Stage 2 includes or drops one cell |
| A15 | `LAB_/PTR_/UNK_` belong under RL01 | §I, R5 | RL01 slightly broader than meant |
| A16 | The wcc386 default optimisation with no `-o` flag is unknown | §H | Only affects explanations |
| A17 | ASCII-only TOML values let `json.dumps` serve as the string writer | Standard Stack | Writer must reject non-ASCII |
| A18 | Spike verdict PARTIAL to VALIDATED | §B | INVALIDATED adds the call-graph route (already built in §A) |

## Sources

### Primary (HIGH confidence)
- Repository code re-read in this pass (✓ in the Prerequisite fixes table): `tools/reverseapoc/check.py` (225-262, 505-525, 970-980, land_all 1060/1118/1152), `compiler.py` (270-285, 355-365, 560-575, 660-675), `gate.py` (141-151, 242-247, 548-560, 780-792), `hooks.py` (60-100), `symbols.py` (139-160, 195-205), `configure.py` (236-244), `driver.py` (95-106, 393-400, 662-670, 710-716, 1505-1532, 1565-1572, 1640-1645, 1770-1776, 2420-2425; 2,614 lines), `session.py` (33-40), `streamjson.py` (60-65), `cli.py` (1290-1296), `attempt.py` (218-228), `tests/test_drift.py` (50-75), `tests/test_skill.py` (header), `tests/conftest.py`, `pyproject.toml`, `.planning/config.json`, `.planning/ROADMAP.md` § Phase 7, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`
- The three slice files (appendices) and the measurements and code readings they cite
- Slice 1 scratch measurements on `orig/` and `cd.iso` (call graph, strings, timer, tables)

### Secondary (MEDIUM confidence)
- [OpenApoc PR #1688](https://github.com/OpenApoc/OpenApoc/pull/1688): the tick-rate claim (36 units per game second)
- [OpenApoc extractor headers](https://github.com/OpenApoc/OpenApoc/tree/master/tools/extractors/common): offsets as locators only
- [UFOpaedia: Apocalypse](https://www.ufopaedia.org/Apocalypse): EXPERIEN/BRAIN/WEAPEXP.DAT under "Learning AI"
- claude-api skill model table (cached 2026-10-06): Opus 5.5 and Fable 5.1 prices (owner-confirmed in D-25)
- OpenApoc issues [#263](https://github.com/OpenApoc/OpenApoc/issues/263), [#264](https://github.com/OpenApoc/OpenApoc/issues/264), [#265](https://github.com/OpenApoc/OpenApoc/issues/265), [#997](https://github.com/OpenApoc/OpenApoc/issues/997) (read-only)

### Tertiary (LOW confidence)
- [mikrocontroller.net wcc386 usage listing](https://mikrocontroller.net/topic/491868): `-od` disables optimisation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH. No new packages; all primitives already used in the code base.
- Architecture: MEDIUM. The designs are consistent with the code read line by line, but views, workers and renames are not prototyped.
- Pitfalls and prerequisite bugs: HIGH. Every load-bearing file:line was re-read in this pass.
- Locating measurements: HIGH. Item-to-entry mapping: MEDIUM (spike 007 confirms it).

**Research date:** 2026-10-26
**Valid until:** about 2026-11-25. Code facts are stable until the prerequisite plans change them; the OpenApoc PR state may change.
