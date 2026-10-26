# Phase 7: Mechanics-first decompilation - Context

**Gathered:** 2026-10-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Find the functions behind the OpenApoc checklist items that touch the original game (#263, #264, #265, #997) and list them, in tiers, in `config/mechanics.toml` for the owner's sign-off. Then match Tier 1 completely with the Phase 6 driver at scale (parallel sessions, unit claims, one writer of the naming state, Opus-then-Fable escalation) and make it readable through a separate readability pass checked by `readlint`. The phase also ships the per-item coverage view on the progress page and `reverseapoc stats`. Both EXEs stay SHA-1 identical after every commit. The phase covers both UFO2P.EXE (`ufo24`) and TACP.EXE (`tac4`).

- **DEC-01:** `config/mechanics.toml`, located from UI strings, data-table xrefs and the call graph; signed off tier by tier.
- **DEC-02, DEC-06:** callees-first order inside a tier, unit claims for N concurrent sessions, the driver as the only writer of shared naming state, the Phase 6 caps and logging carried over (new values below), and nightly totals.
- **DEC-03 (reworded by owner ruling D-05):** every function in Tier 1's call trees matches; Tiers 2-4 are located and signed off.
- **DEC-04:** stdlib `readlint`, TDD, with backlog 999.2 (our own `func_`/`D_` placeholders).
- **DEC-05:** per-item coverage on the progress page.
- **DEC-07:** stdlib `stats` over the whole Phase 6-7 history.
- **AGT-11 carry-in:** the 10-match unattended target from the Phase 6 pilot (3/10 so far) is met during this phase.
- **Roadmap spike:** locate the #997 tick-rate and training code from the timer setup and strings within a time box (D-03).

Not in this phase:
- matching Tiers 2-4 to completion (Milestone 2, SEED-261025-3ga);
- clean-room specs, `speclint`, `wikifetch`, findings docs (Phase 8);
- SMKP.EXE, the CD v1.00 twin (D-42 of Phase 6);
- any contact with OpenApoc (Milestone 1 rule). A #997 finding goes to the owner only.

Pilot facts that shaped the discussion (`progress/attempts.jsonl`, run 20261026-005209):
- 3 MATCHED in 40 sessions (about USD 14 per match). 37 sessions ended PARTIAL, mostly at 60-87%.
- 15 distinct functions were tried; 12 never matched. For 6 of those 12, `--sweep` found a 100% cell (objdiff 100.0 and relocation check passing) under `-ot` or `-oneatx`: ufo2p func_00026FD0 (`-oneatx`), func_0004DFD0 (`-ot`), func_00061F30 (`-ot`), func_0009C3A0 (`-oneatx`); tacp func_000779C0 (`-ot`), func_0006FBD0 (`-oneatx`). func_0008A100 had an `-ot` hit too but later matched under the default. (The discussion said "7 of 9"; this recount from the log is the correct figure.) The planner re-derives this list from `attempts.jsonl` with a script (D-16).
- Game code: UFO2P 1,549 game + 4 thunk functions, TACP 1,519 game + 7 thunk functions (`config/<exe>/functions.csv`); 6 matched at phase start.

</domain>

<decisions>
## Implementation Decisions

### Target list scope (DEC-01, roadmap spike)
- **D-01:** **Items.** Every checklist item of #263, #264, #265 and #997 that touches the original game is in, including the borderline ones: dynamic music #264-21, name generator #265-13, vehicle lanes #264-19/20. OpenApoc-only tooling, modding, UI-chrome and project items are out: #263-19/20/23/24, #264-1, #264-22/23, #264-29..33, #265-14..18. Items already ticked in OpenApoc are in when the original's rule or numbers are still useful (for example #263-7 diplomacy, #263-5 economy). Claude proposes the exact in/out line per tier and the owner rules on it at that tier's sign-off.
- **D-02:** **Depth.** The **full transitive call tree** of each item's entry function or functions, shared plumbing included (drawing, sound, file I/O, memory). The runtime library rows (`kind = runtime`, already matched by libmatch) and data-in-code rows are excluded. A function reached from several items is listed once with every item that reaches it.
- **D-03:** **Spike, 1 day.** Work from the PIT / INT 8 timer setup, UI strings and data xrefs in the Ghidra output. VALIDATED: strings and xrefs locate the tick rate and the training rule, and that method locates the rest of the list. PARTIAL or INVALIDATED: add call-graph walking from OpenApoc data-table offsets, re-located by signature (Phase 6 D-42). The spike is recorded as `.planning/spikes/007-*` under the spike CONVENTIONS. **Any #997 finding is reported to the owner at once,** with the answer, the addresses and evidence, and whether matched code backs it yet. No agent posts to OpenApoc (auto-memory `notify-owner-997-tick-rate`; `docs/clean-room.md`).
- **D-04:** **Tiers, signed off one at a time** before the driver works on them:
  - Tier 1: #997 (tick rate) + #263-1 (agent training, incl. androids);
  - Tier 2: the rest of #263;
  - Tier 3: #264;
  - Tier 4: #265.

  Each sign-off is a blocking-human checkpoint. Claude drafts the tier (items, entry functions, call trees, the evidence for each entry), and the owner signs it. The sign-off is recorded in `config/mechanics.toml` (who, date) and in the plan's SUMMARY. — **Reversibility:** costly — progress.py's coverage view, the picker's tier order and Phase 8's speclint all read `config/mechanics.toml`.

### Scale, budget and parallelism (DEC-02, DEC-03, DEC-06, AGT-11)
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

### Compiler-flag rulings
- **D-12:** **Per-unit rules, owner-approved in batches.** A real source file had one flag set, so a rule is per unit. A sweep hit becomes a **proposed per-unit rule** in a review queue, a committed file without game bytes. A tool then re-gates the whole unit under the proposed flags: every already-matched function in the unit must still match, and both EXEs must stay SHA-1 identical. The evidence (log paths and the check JSON summary) is attached to the proposal. The owner approves proposals in batches, and only then is `config/cflags.txt` edited, in a commit that quotes the approval. Phase 5 D-18 stands: agents and the driver never edit cflags.txt, and the hooks keep blocking it. — **Reversibility:** costly — the queue format is read by the driver, the approval tool and the docs.
- **D-13:** **Pilot sweep hits first.** An early plan re-runs the saved best C of the 6 never-matched pilot functions with a 100% sweep cell (D-16 list). It turns real hits into proposals with whole-unit re-gates and lands what the owner approves, each as its own match commit through `gate`. The C is in gitignored `build/driver/20261026-005209/...`; if it is missing, those functions are re-queued instead. These matches count toward AGT-11, classed `human-hints` or `unattended` by the `stats` rules (the agent wrote the C, the owner approved the flags). They are also evidence for the real game default.
- **D-14:** **The `*` default** changes only by owner ruling on Phase 5 D-18 evidence (3 or more agreeing functions from different regions of both EXEs). Claude proposes the change with evidence. Units already matched under the old default get pinned per-unit rules in the same commit, so nothing regresses, and `gate --all` runs before that commit.
- **D-15:** **Second-stage sweep.** The 30-cell first stage stays. When no cell reaches 100% and the best cell is at or above 90%, a second stage tries the candidates in `docs/toolchain.md` "Fallbacks and candidates": single `-o` letters (`-od -of+ -or -oi -om -ol -on -op`, KKND's `-of+ -omiler`), `-zp1/2/4/8`, `-zm`, `-fp3/-fp5`. It is a diagnostic only and feeds the same proposal queue. The wrapper still never lets an agent choose flags for a real check.
- **D-16:** The pilot-hit list in `<domain>` comes from reading `progress/attempts.jsonl`. The planner re-derives it with a script, not by hand.

### Readability and naming (DEC-04)
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

### Claude's Discretion
- The `config/mechanics.toml` schema (items, tiers, entry functions, member functions, the sign-off record), the claims-file format and stale rule, the flag-proposal queue format, the naming-proposal format, module layout and verb names (the existing verbs `drive`, `gate`, `check`, `attempt` keep their names).
- How the call trees are computed (Ghidra export, capstone discovery's call edges, relocation targets) and how indirect calls and jump tables are handled.
- The per-item coverage view on the progress page (DEC-05): how progress.py reads mechanics.toml and shows each item's matched / partial / unmatched share. **Backlog 999.4** (phone mosaic: sideways scroll with a ~48rem minimum SVG width or an HTML legend; keyboard/touch tooltips instead of `title`-only; the percent bar that draws nothing at current values; 06-UI-REVIEW.md fixes #1-#3) is folded into the same progress.py work.
- `stats` internals beyond the roadmap text (DEC-07), plus the per-model split (D-09), the matching/readability split (D-18) and the per-attempt hook-block count from Phase 7 on.
- Scorer and picker tuning carried from Phase 6 D-09: callees first inside a tier, admitting jump-table and static functions now that DI-02/DI-03 landed, dropping or keeping `WEIGHT_NO_FRAME`.
- The readability `/goal` prompt wording, and whether the readability session text is a new project skill or a section of `watcom-decomp`. Either way it is written or updated with `superpowers:writing-skills` (`.claude/rules/workflow.md`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and gates
- `.planning/ROADMAP.md` § Phase 7 (goal, SC1-SC6, spike) and § Backlog 999.2 and 999.4
- `.planning/REQUIREMENTS.md`: DEC-01..DEC-07, AGT-11 (carry-in)
- `.planning/STATE.md`: Phase 06 decisions (pilot result, PARTIAL ruling) and next steps
- `docs/workflow.md`: the per-function loop, "The driver owns verification", "Running the driver", the Milestone 1 roadmap row for Phase 7
- `docs/ceremonies.md`: what review and readability passes may touch (matched C: comments, names and whitespace only)
- `CLAUDE.md`, `.claude/rules/src.md`, `.claude/rules/tools.md`, `.claude/rules/workflow.md`: the hard rules; project skills only through `superpowers:writing-skills`

### Prior decisions this phase builds on
- `.planning/phases/06-reporting-and-agent-pilot/06-CONTEXT.md`: D-05..D-10 (driver, session argv, caps, backoff, scorer), D-13/D-14 (context pack), D-15..D-18 (hooks, pragma policy), D-20..D-25 (status.csv, gate, drift test, attempts.jsonl, commits), D-34..D-37 (main checkout, model pin, CLI pin, pilot), D-42 (installed build primary, OpenApoc offsets re-located by signature), D-44..D-48 (attempt wrapper, no MCP server, notes path, driver flags), D-50 (uncovered bytes)
- `.planning/phases/06-reporting-and-agent-pilot/06-27-SUMMARY.md` and `06-VERIFICATION.md`: the pilot result and how it was re-gated
- `.planning/phases/06-reporting-and-agent-pilot/06-UI-REVIEW.md`: fixes #1-#3 behind backlog 999.4
- `.planning/phases/05-split-and-first-matches/05-CONTEXT.md`: D-12 (INCLUDE_ASM stub), D-15 (P16 scorer), D-18 (cflags.txt is owner-only; 3 agreeing functions before the default changes)
- `.planning/PROJECT.md` Key Decisions: the decomp.wtf row (closed by D-06), Phases 7-8 row

### Matching and toolchain
- `docs/matching.md`: relocation rules, jump tables and statics
- `docs/toolchain.md`: "Flags", "Fallbacks and candidates" (the second-stage sweep list, D-15), "Phase 6 match evidence" (what the pilot sweeps separated)
- `docs/learnings.md`: scorer notes (P16 exclusions lifted in Phase 7), build notes
- `config/cflags.txt`: the rule format and the `*` default
- `progress/attempts.jsonl`: pilot attempts, the source of the D-16 list

### OpenApoc and the mechanics list
- OpenApoc issues: https://github.com/OpenApoc/OpenApoc/issues/263, /264, /265, /997 (read 2026-10-26; checklists quoted in the discussion)
- `docs/research/notes-target-binary-and-toolchain.md` (~L255-300): OpenApoc PRs #1685/#1688 (andremmfaria, `FUN_` addresses on the CD build), extractor data-table offsets (`tools/extractors/common/ufo2p.h`, `tacp.h`), UFOpaedia pages, debug strings
- `.planning/seeds/SEED-261025-os5-m2-pilot-spec-997-dosbox-verified.md`: why #997 is the priority (36 vs 144 tps community claim, unverified)
- `.planning/seeds/SEED-261025-3ga-m2-full-byte-matching-decomp.md`: where Tiers 2-4 continue
- `docs/clean-room.md`: author/implementer split; no OpenApoc contact in Milestone 1
- `docs/legal.md`: generated files stay local; AI-use record

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tools/reverseapoc/driver.py` (2,614 lines): run loop, caps, backoff, `attempts.jsonl` schema (`_ATTEMPT_SCHEMA` ~L345 incl. `check.sweep_hit`/`needs`), `CheckSummary` L629, gate-before-commit, reset. The workers, claims, model escalation and naming-proposal writer extend it.
- `tools/reverseapoc/attempt.py`: the attempt wrapper (`check`/`asm`/`context`), `--sweep` and `sweep_hit` (L17, L245, L384). The second-stage sweep and the proposal queue start here.
- `tools/reverseapoc/picker.py`, `score.py`: status-aware easiest-first picker with the variety rule; the tier-scoped callees-first order replaces or wraps it.
- `tools/reverseapoc/session.py`, `streamjson.py`: session argv (model, budget, settings) and the stream-json classifier; per-model budget and model choice go here.
- `tools/reverseapoc/gate.py`: the only writer of `config/<exe>/status.csv` and `decomphub.progress.json`; `gate --all`, cross-check of the landed set.
- `tools/reverseapoc/hooks.py`: two-layer hooks; the per-session allowlist, the symbols.csv/shared-header block and the readability allowlist extend it.
- `tools/reverseapoc/contextpack.py`: the 24 KB pack; callers/callees with status; tier and item context can be added.
- `tools/reverseapoc/symbols.py`, `config/<exe>/symbols.csv`: names and linker names (`func_XXXXXXXX_`); the naming state of D-19.
- `tools/reverseapoc/check.py`: `check_unit`, `source_marks` (which functions a unit defines in C), the sweep matrix.
- `tools/reverseapoc/ghidra.py`, `discover.py`, `relocs.py`, `target.py`: Ghidra export and drafts, capstone discovery (call edges), LE fixups; inputs for the call trees and string/xref search.
- `tools/progress.py`: progress.json, progress.svg, progress.html, shields, report.json; the coverage view and 999.4 go here.
- `tools/reverseapoc/cli.py`: verbs registered through `_add_*_command(sub)`; new verbs (`readlint`, `stats`, `mechanics`, a flags-proposal verb) follow it.

### Established Patterns
- Stdlib-only Python, TDD with pytest; real-file tests skip unless `orig/` exists; CI has no game files; ruff clean.
- Game-derived output (asm/, build/, Ghidra drafts, packs, transcripts) is gitignored and never committed; committed data has addresses, names and statuses only.
- `write_atomic` (`tools/reverseapoc/fileio.py`) for every committed data file.
- Only the container `gate` decides a match; one match per commit with the D-25 message and `Matched-By` trailer.
- Host and container suites never run at the same time (shared build/test-cc).
- Main-checkout plans need the recipe in auto-memory `gsd-main-checkout-plans` (temporary `allow_default_branch_commits`, `--force-isolation none`).

### Integration Points
- `config/mechanics.toml` (new): read by the driver (tier order), progress.py (coverage), stats, and Phase 8 speclint.
- `config/driver/claude-settings.json` and the per-session settings: hooks per claimed unit.
- The flag-proposal queue file (new) and `config/cflags.txt` (owner-only edits).
- `.github/workflows/pages.yml`: publishes the coverage view; `.github/workflows/ci.yml`: drift and schema tests for the new files.
- REQUIREMENTS.md / ROADMAP.md rewording (D-05).

</code_context>

<specifics>
## Specific Ideas

- The owner's escalation idea, verbatim intent: start with Opus latest, and for functions that fail and get requeued, retry with Fable latest as the stronger model for problematic stuck functions (D-09; the owner then chose "after two capped Opus passes").
- #997 is the item that matters most to OpenApoc: it blocks fixes in #263 and #264. The community claim is 36 ticks per second in the original versus 144 assumed in parts of OpenApoc, still unverified. Tell the owner the moment the spike or any run finds it (D-03).
- The owner wants every original-game item listed, including borderline ones, at full call-tree depth (D-01, D-02), and accepted that only Tier 1 must be fully matched in this phase (D-05).

</specifics>

<deferred>
## Deferred Ideas

- Matching Tiers 2-4 to completion: Milestone 2 (SEED-261025-3ga).
- A second clone or a multi-clone SQLite claims store; decomp.wtf as a claims layer. Closed for Milestone 1 by D-06 (spike 006 stands).
- A human-hints escalation step for stuck functions. Offered; the owner chose unlimited driver passes (D-08). Revisit if Tier 1 stalls.
- GhidraMCP as a live agent tool: stays "Later".
- Twin matching of CD v1.00: after Phase 7 (Phase 6 D-42).
- Attributing the uncovered filler bytes (Phase 6 D-50).

</deferred>

---

*Phase: 07-mechanics-first-decompilation*
*Context gathered: 2026-10-26*
