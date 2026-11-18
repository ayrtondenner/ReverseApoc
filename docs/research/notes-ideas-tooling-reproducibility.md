<!-- Literature-mining report of 2026-11-18 (three research agents); source of the todos filed that day. Quotes and numbers from papers came through web summaries: re-read the source before citing. -->

# Tooling, reproducibility and evaluation ideas for ReverseApoc (2026-11-18)

Read-only research. Repo state read first: CLAUDE.md, docs/tools.md (all verdicts), docs/toolchain.md,
docs/ci.md, docs/workflow.md, docs/model-comparison.md, docs/model-routing.md (headings), the three
research notes, docs/learnings.md (top), every pending/completed todo, and the relevant code
(`contextpack.py`, `picker.py`, `search.py`, `classify.py`, `causes.py`, `stats.py`, `driver.py` record
schema, `progress/attempts.jsonl`, `.recomp.json`, `config/targets.toml`). Each idea below names
what already exists and the gap that is left. Ideas with no gap were dropped (list at the end).

Ordered by value, then effort.

---

## 1. Environment digest in every run record

- **Source(s):**
  - EdgeBench discussion #3, https://huggingface.co/datasets/ByteDance-Seed/EdgeBench/discussions/3, opening post (zhzopa, Jul 17). The reproducer proved their setup was "verified bit-for-bit official" by checking that the "work image digest matches Docker Hub, `internet: false`". The org's reply (Jul 23) confirmed that the published 15.2 "was indeed produced under exactly these conditions", which was "not our intended setup".
  - Debian `.buildinfo`, as Nesbitt describes it in "Reproducible Builds in Language Package Managers", https://nesbitt.io/2026/02/24/reproducible-builds-in-language-package-managers.html: "recording everything about the build environment ... exact versions of all build dependencies, architecture, and build flags".
  - SWE-bench harness reference, https://www.swebench.com/SWE-bench/reference/harness/: results are keyed by `run_id`, with per-instance logs under `logs/evaluation/<run_id>/`.
- **What they do:** pin and record the exact image, tool versions and inputs that produced each score, so a third party can tell whether its run matches the original.
- **What ReverseApoc would implement:** the `STARTED` run record (schema 3, `driver.py` `KIND_RUN`) gains an `env` object:
  - `HEAD` commit of the checkout;
  - Docker image ID of `reverseapoc-build:local`;
  - sha256 of `config/cflags.txt`, `config/watcom.toml`, `config/driver/backends.toml` (prices) and `quota.toml`;
  - sha256 of the `watcom-decomp` SKILL.md and of the context-pack template version;
  - each arm's CLI name and version (claude, codex, agy, copilot) plus its model id and effort;
  - the uv.lock hash and the host OS string.

  `validate_record` checks the shape, and `stats --run` prints the digest beside every table so a comparison can say "same environment" or name what changed.
- **Why:** EdgeBench's 0-vs-15.2 dispute was settled only because both sides could compare digests. ReverseApoc has already had silent environment shifts: agy auto-updating 1.5.7, then 1.5.8 to 1.5.9 mid-day (learnings 2026-11-13 and 2026-11-16); Copilot's audit shapes changing per CLI version; the Codex trust-key split (learnings 2026-11-11). The paper will compare nights run weeks apart.
- **Existing-feature check:** attempt records carry `model`, `cli_version`, `effort`, `harness` and `backend`. `cc` checks the compiler SHA-1 against watcom.toml. `view-head.txt` holds the view's commit, but under gitignored build/. A canary is required per agy version. **Gap:** the committed record names no tool commit, image, skill or prompt version, prices table or cflags hash. A record in `progress/attempts.jsonl` cannot say which driver code or skill text produced it.
- **Effort:** S. **Value:** high.

## 2. Nightly gold and null control on the real judge path

- **Source(s):**
  - EdgeBench #3, opening post: "Control AIs ('pure-sleep') survive the full 20 years in your judge image, so the engine is fine". That control is what separated a broken task from a broken judge.
  - SWE-bench harness reference (URL above): validate the harness by running `--predictions_path gold` on a few instances before trusting a run.
- **What they do:** before scoring agents, run a submission whose outcome is known (a gold patch, a do-nothing AI) through the exact scoring path.
- **What ReverseApoc would implement:** a preflight step `controls` that runs through the same container, wrapper and view-unit path a session uses, per EXE:
  - Gold: 2 already-matched functions (fixed list in `config/driver/controls.toml`, one small and one 256 B+) with their committed C copied into a throwaway attempt dir. `reverseapoc-attempt check` must exit 0.
  - Null: the same functions' `INCLUDE_ASM` stub, or a body of `return;`. The check must exit 1, not 0 and not 2.

  Any other result refuses the night (`reason: controls`). The results go into the `STARTED` record. This costs no model tokens and a few compiles.
- **Why:** the guardrail canaries prove that writes are denied. Nothing proves, per night, that the judge still says "exact" for a known match and "not exact" for a known miss after a Docker, wibo, image or tool change. The Docker removal fault and the interrupted-check temp-file stops (pending todos) show that the container path does break between nights.
- **Existing-feature check:** the preflight compiles tools/, regenerates asm and checks the CLI version and a clean tree (workflow.md "Preflight"). `ninja verify` and `gate --all` are run by hand after a night. The canaries test guardrails only. **Gap:** no known-good or known-bad submission goes through the attempt-check path before sessions start.
- **Effort:** S. **Value:** high.

## 3. A frozen benchmark set with repeats, held-out half and intervals

- **Source(s):**
  - Macabeus, "Can LLMs Really Do Matching Decompilation?", https://gambiconf.substack.com/p/can-llms-really-do-matching-decompilation, results section. Three runs per game (six in total); "53/60 (88%) identical outcomes across all 3 runs"; the always-failing 12 are reported apart from the rest.
  - VideoGameBench, arXiv:2505.18134, abstract: three of the ten games are kept secret "to encourage solutions that generalize to unseen environments".
  - BALROG, arXiv:2411.13543, abstract: a public leaderboard over fixed environments of graded difficulty.
- **What they do:** a fixed task list, several independent runs per model and a hidden subset. Run-to-run variance is then measured instead of assumed, and tuning cannot overfit the visible tasks.
- **What ReverseApoc would implement:**
  - `config/bench/v1.toml`: about 60 unmatched rows stratified by size bucket (<64, 64-255, 256-1023, 1K+) and by EXE, split into `dev` (may be used while tuning the skill, learnings or pack) and `heldout` (only run for a reported comparison).
  - `drive --bench v1 --repeats 3 --hold` runs each arm k times, each repeat a fresh session with no earlier-best C from the same bench run.
  - `stats --bench` reports, per arm and bucket: pass@1 (mean over repeats), pass@k, a Wilson 95% interval, per-function agreement across repeats, and a paired comparison between arms on the same rows (McNemar or a sign test).
  - Matched bench rows are never removed. The set is versioned, and v2 is a new file.
  - Contamination guard: the bench draws only rows unmatched at freeze time, and later matches land as usual, so a function's own C is never in a later pack.
- **Why:** model-comparison.md "How to read it" already says "a gap of one function between two arms is within noise", and the Fable A/B section says "three exact matches are too few to rank the models". Repeats and intervals turn that caveat into a number. The held-out half answers a reviewer's first question: were the skill and pack tuned on the rows used to compare?
- **Existing-feature check:** `--hold`, `--write-picks` (with `--stratify`), the frozen `spike012-picks.txt`, and the dated, immutable comparison sections. **Gap:** single attempts per arm, no repeats, no dev/held-out split, no intervals or paired tests in `stats`. Pick lists live under gitignored build/, so they are not a committed versioned set.
- **Effort:** M. **Value:** high (the paper's evaluation section depends on it).

## 4. Similarity-first ordering inside a tier

- **Source(s):**
  - Chris Lewis, "The Long Tail of LLM-Assisted Decompilation", https://blog.chrislewis.au/the-long-tail-of-llm-assisted-decompilation/ (2026-02-16), section on prioritisation, as summarised in docs/research/notes-blogs-and-reference-repos.md: ranking by difficulty "ran out of value; prioritising functions similar to already-matched ones worked much better". coddog "matched or beat his composite score".
  - coddog README, https://github.com/ethteck/coddog, `match`: "Find functions that are similar to a query function" (`-t 0.7`).
- **What they do:** order the queue by how close each unmatched function is to something already matched, so the agent always has a strong look-alike.
- **What ReverseApoc would implement:** a picker order `similar` (next to score's `(__CHK, score, start)`):
  - inside each tier queue, rank by the best `contextpack.lookalikes` ratio against the current matched set (difflib over mnemonics, the function already there), ties broken by score's rank;
  - recompute between passes, since every landing changes the matched set;
  - keep the D-10 variety rule unchanged;
  - evaluate on the bench (idea 3), `similar` against `score` on the same arm.
- **Why:** match rates fell from about 27% to 2% for Opus as the queue moved from small leaves to tier-1 functions (learnings 2026-11-14). Lewis's data says the long tail moves faster when each pick has a near neighbour already solved.
- **Existing-feature check:** look-alikes (up to 3 matched functions, floor 0.6) are already in every context pack. workflow.md step 1 says "switch to similarity-first once enough functions are matched", but `picker.py` orders by score only (no similarity term). **Gap:** the ordering itself is not built.
- **Effort:** S-M. **Value:** high.

## 5. Twin and clone transfer with no model tokens

- **Source(s):**
  - coddog README (URL above): `cluster`, "Find clusters of functions that are identical or near-identical in one binary ... useful for de-duplicating redundant code". `compare2`, "Find common functions between one binary and another". `submatch` finds shared instruction runs.
  - ReverseApoc's own workflow.md step 1: "Twin functions between UFO2P (`ufo24`) and TACP (`tac4`) ... are the cheapest wins". The picker docstring names UFO2P's "eight 27-byte functions at 0x0008A0E0..0x0008A1C0".
- **What they do:** find code compiled from the same source more than once and match all copies from one solution.
- **What ReverseApoc would implement:** `reverseapoc twins` (read-only over orig/ and config/):
  - Cluster game rows within and across UFO2P/TACP by (a) fixup-masked byte hash, which gives exact twins, and (b) opcode ratio of 0.9 or more, which gives near twins.
  - Write `build/twins/<exe>.csv`, addresses only.
  - After every landed match, a zero-token step copies the matched C into each exact twin's view, maps callee and `D_` names through `symbols.csv` and each EXE's address map, and judges it with `batch.judge`. An exact result goes to the normal gate as a match commit with `Matched-By: reverseapoc twins`.
  - Near twins go to the front of the queue (idea 4), with the twin's C as look-alike 1.
  - `stats` gets a `twins` class beside unattended, human-hints and human-written.
- **Why:** both EXEs share an engine (one compiler and flags, and both give the same answer for every flag: toolchain.md "Flags"). A twin transferred costs a compile instead of a session (about $0.59 for an Opus session, model-comparison.md).
- **Existing-feature check:** `libmatch.py` does this for the Watcom runtime only. Look-alikes cover matched functions inside one pack. **Gap:** no game-code twin detection, no automatic transfer, and no class for it.
- **Effort:** M. **Value:** high.

## 6. Function map between the installed build and the CD v1.00 build

- **Source(s):**
  - ReverseApoc docs/learnings.md (OpenApoc CRC entry) and docs/toolchain.md "OpenApoc CRC mismatch": "OpenApoc's offsets and `FUN_` addresses only apply to the CD build ... treat the build-to-build diff as free matching evidence later".
  - coddog `compare2` (URL above).
  - objdiff `config.schema.json`, https://raw.githubusercontent.com/encounter/objdiff/main/config.schema.json: `symbol_mappings`, "Manual symbol mappings from target to base".
  - splat, https://github.com/ethteck/splat: projects import names from a `symbol_addrs` file.
- **What they do:** map functions across two versions or two binaries, and import names from another analysis keyed by address.
- **What ReverseApoc would implement:** `reverseapoc crossmap`, which writes `config/<exe>/cd-map.csv` (installed start, CD start, method `hash|ratio|anchor`, ratio; addresses only, D-21):
  - Map by masked-byte hash first, then by opcode ratio anchored on call-graph neighbours.
  - Specs, the mechanics map and the progress tooltips show the CD address next to ours, so OpenApoc's Ghidra `FUN_` addresses resolve.
  - Optionally, matched C is also spliced into the CD build and checked against `[[cd_builds]]` sha1, as a second, independent proof per function.
- **Why:** OpenApoc is the project's only consumer, and its community addresses are CD-build addresses. Without a map, every spec and finding needs hand translation. A second binary that also rebuilds from the same C is extra evidence that the C is the source and not an overfit.
- **Existing-feature check:** `[[cd_builds]]` hashes are recorded in `config/targets.toml`, and the trailer spike compared files. **Gap:** no function-level map, no address import or export, and no second-build check.
- **Effort:** M. **Value:** high for OpenApoc, med for matching.

## 7. Errata ledger that `stats` applies

- **Source(s):**
  - EdgeBench #3, org replies of Jul 23 and Jul 28. The fault was confirmed, the images were fixed and the task JSONs updated ("delete your old task folder and run sforge fetch-tasks again"). Users were offered a choice: keep the blind-run scores "comparable to the current leaderboard" or wait for corrected re-runs.
- **What they do:** publish a confirmed measurement fault, say which scores it affects, and keep both the original and the corrected figures, labelled.
- **What ReverseApoc would implement:** `progress/errata.toml`, one `[[erratum]]` per fault:
  - `id` (E-001 ...), `found` date, `component` (e.g. `codexjson.usage`), `effect` ("cached tokens priced twice"), `runs` (glob of affected run ids), `fields` (e.g. `cost_usd`), `fixed_in` (commit, or null), and `correction` (a named rule `stats` knows, such as `codex_cached_once`).
  - `stats` prints raw and corrected columns plus the erratum ids that applied, and refuses an unknown rule.
  - model-comparison.md cites erratum ids instead of prose notes.
  - First entries: the Codex cached double count (still in code per model-comparison.md), the recovered-429 misclassification (11 sessions, learnings 2026-11-11), Codex records with null `model` (completed todo), and the progress co-author label (pending todo).
- **Why:** faults found so far are carried as prose in dated sections, with "(R)" recomputed figures done by hand. One file keeps the paper's tables consistent and auditable.
- **Existing-feature check:** dated, never-edited comparison sections, and the rule "if a measurement fault is fixed in between, say which figures it changes" (model-comparison.md "Adding the next comparison", step 5). **Gap:** no machine-readable fault list, and no corrected figures computed by `stats`.
- **Effort:** S-M. **Value:** med-high.

## 8. Attempt-to-match curves from our own records, to set caps per bucket

- **Source(s):**
  - Macabeus (URL above): nearly half the AI-phase matches came on the first attempt, and after the 3rd the conditional match probability was about 1/4. "Claude resubmitted identical code 49 times".
  - Lewis, "The Long Tail" (URL above): the retry cap was originally 30, the 85th percentile of successful attempts was 28, and one function needed 87.
- **What they do:** set the retry cap from the measured distribution of attempts-to-success.
- **What ReverseApoc would implement:** `stats --hazard`, over the committed attempt log (4,481 lines, schema v1 to v3):
  - per size bucket and arm, the conditional match probability at attempt n, pass p and check count c (from checks.jsonl where present), as a Kaplan-Meier style table;
  - the expected cost per match at each cap.

  `config/driver/caps.toml` would then hold per-bucket caps chosen from that table, with the table's date.
- **Why:** the cap of 3-5 and its justification in workflow.md "Attempt cap and re-queue" come from Macabeus's GBA/N64 data. ReverseApoc now has enough of its own records, on a different compiler, to measure the curve instead.
- **Existing-feature check:** the cap, the difficult list, re-queue by pass, and `causes` (per-try build/mismatch rates). **Gap:** no curve computed from our records, and the caps are not per bucket.
- **Effort:** S. **Value:** med.

## 9. Candidate archive per function (program database, MAP-Elites cells)

- **Source(s):**
  - AlphaEvolve, arXiv:2506.13131. §2.5: the evolutionary database balances "exploration and exploitation", "inspired by a combination of the MAP elites algorithm" and "island-based population models". §2.2: the prompt "comprises multiple previously discovered solutions sampled from the program database". §2.3: Flash for "a higher rate of candidate generation", Pro for "occasional, higher-quality suggestions". §2.4: evaluation cascade.
  - MicroRCT, arXiv:2105.04342, abstract: MAP-Elites used "to generate a diversity of park layouts".
  - Macabeus (URL above): 49 identical resubmissions.
  - FNV agent contract (docs/research/2026-11-09-fnv-decomp.md): a claim returns `best_attempts` from earlier agents.
- **What they do:** keep many diverse good candidates instead of one best. The next proposer gets several parents from different niches, and duplicates are never re-evaluated.
- **What ReverseApoc would implement:**
  - `build/driver/archive/<exe>/<start>.jsonl` (local, gitignored), one row per distinct candidate: normalized-source sha256, exact/score/stack_score, `classify.py` class (slot, register, branch, size, mixed, tail), arm family, run and attempt.
  - The archive keeps the best candidate per (class x arm family) cell.
  - The pack's "earlier best C" section shows the top 2 from different cells, labelled with their class.
  - `attempt check` looks up the source hash first. An identical source returns the cached verdict and a note "same as check N of run R" without compiling.
  - The cascade's cheap arm fills cells, and the strong arm gets the two best parents.
- **Why:** the near-miss lane holds about 100 KB of partial rows. One "earlier best C" collapses diversity: two near misses that fail for different reasons (slot vs register) carry complementary information. Resubmitting identical code wastes checks.
- **Existing-feature check:** earlier best C (one), structured give-ups with `best_code`, the near-miss lane ranked by bytes left, and the size-routed cascade. **Gap:** no multi-candidate archive, no diversity cells, no cross-session dedupe of sources.
- **Effort:** M. **Value:** med (strong outside evidence, but untested on Watcom; measure on the bench).

## 10. Headless emulator: runtime coverage, call harness, behaviour checks

- **Source(s):** brotchie/daggerfall-decomp README tool table, https://github.com/brotchie/daggerfall-decomp. It is a Watcom C 10 DOS game at 100% (2,297 of 2,297 functions):
  - `tools/fallemu.py`: "run `FALL.EXE` headless (Unicorn): DOS, DPMI, timer, keyboard and mouse, scripted scenarios";
  - `fallcov.py`: "which functions ran, per source unit";
  - `fallfuzz.py`: "coverage-guided random play";
  - `fallevidence.py`: "evidence for naming";
  - `fallcall.py`: "call any function in a live game from a safe point between frames: return value, functions run".
- **What they do:** run the user's own EXE headless, to get runtime evidence (coverage, call results) for naming and documentation.
- **What ReverseApoc would implement (staged):**
  1. A Unicorn LE loader with minimal DOS/DPMI/timer shims for TACP.EXE and UFO2P.EXE, running from the user's orig/ only, local, outputs addresses and counts only.
  2. `reverseapoc cover <scenario>`: functions run per scripted scenario (a tactical turn, a base screen). It feeds `mechanics.toml` evidence ("ran in scenario X") and the tier picker.
  3. `reverseapoc call EXE ADDR`: call one function on a snapshot state and record the return value, memory writes and callees. It gives naming evidence for readability sessions and Phase 8 scenarios.
  4. Optionally, differential calls of a near-miss C build against the original on fuzzed states, labelled `behaviour-equal (N states)`. This is never a match, only spec evidence, the analogue of differential CPU testing ("Testing CPU Emulators", ISSTA 2009).
- **Why:** Phase 8's specs need behaviour, OpenApoc needs mechanics, and the #997 tick-rate question is a runtime question. Static call graphs miss pointer-driven code. Daggerfall shows the approach working on the same compiler family.
- **Existing-feature check:** the static `callgraph.py` (direct, pointer, table and midrow edges), the mechanics map, Ghidra drafts. Nothing runs the game (no emulator, DOSBox or coverage tool in tools/ or the roadmap). **Gap:** all runtime evidence.
- **Effort:** L. **Value:** med-high (high for Phase 8, low for matching).

## 11. Cold-rebuild verification record, published

- **Source(s):**
  - isledecomp/isle README, https://github.com/isledecomp/isle, "Status" and the ReproBit section. ReproBit "builds everything from scratch and checks every byte against the retail files". Each verified push publishes a `report.html` and "its full `report.json` record", and "every run compares its reccmp scores and its ReproBit intervention cost with the `master` release and prints the deltas".
  - f15se2-re README, https://github.com/neuviemeporte/f15se2-re, "Verification": `make verify` with `mzdiff` is the contribution gate.
- **What they do:** a from-scratch rebuild in a clean environment produces a durable, public certificate per verified commit, with deltas against the last one.
- **What ReverseApoc would implement:** `reverseapoc gate --all --record` run from a fresh `git clone` in a fresh container. It writes `build/gate/verify-<sha>.json` with:
  - tool commit, image ID, watcom.toml/cflags/uv.lock hashes (idea 1's digest);
  - each output's SHA-1 equal to targets.toml, a yes/no per EXE;
  - matched counts and bytes, units compiled, duration, and deltas against the previous record.

  The owner appends a summary line (no game bytes) to `progress/verifications.jsonl`, and the Pages site shows "last cold-verified at <sha>, <date>".
- **Why:** today a reader of the progress page must trust that the owner ran `ninja verify` and `gate --all` after a night. A dated certificate per verified commit makes the SHA-1 claim checkable from the repo, the same claim recomp.fyi and DecompHub display.
- **Existing-feature check:** `ninja verify`, `gate --all` by hand after a drive, match.yml (base-vs-head, disabled, self-hosted). **Gap:** no from-clean-clone mode and no committed, dated verification record linked on the page.
- **Effort:** M. **Value:** med.

## 12. Public provenance split on the progress page

- **Source(s):**
  - Broken Joysticks, https://www.brokenjoysticks.net/2026/10/19/decomp-dev-pulls-the-plug-on-its-public-index-as-ai-slop-breaks-the-community. Encounter: "the community aspect of decompilation has been broken"; the tracker was flooded until human and machine output were hard to tell apart; objection to people who "just want to burn tokens to make number go up". The same admin rejects an AI ban.
  - 404 Media, https://www.404media.co/video-game-reverse-engineering-community-shuts-down-because-ai-has-made-it-too-easy/ (2026-10-15): it had become impossible to tell which projects are human-led and which are AI-made.
- **What they do:** (the gap the community names) mark which work is AI-made, so a human-led project and an AI one can be told apart.
- **What ReverseApoc would implement:**
  - `progress.json` and the page split matched bytes by `stats` class: unattended (by model family), human-hints, human-written, twins (idea 5), converter (`reverseapoc lift`/`search`).
  - The mosaic tooltip shows each function's class and model.
  - The README's "AI use" section links the split.
  - `.recomp.json` gets an `x-ai-assisted: true` key (`^x-` keys are allowed by the spec) or a tag, if recomp.fyi lists one.
- **Why:** ReverseApoc is openly AI-driven. Saying exactly how much, per function, from committed trailers, is the transparent answer to the criticism that closed decomp.dev's index, and it backs the paper's claims.
- **Existing-feature check:** `Matched-By`/`Match-Hints`/`Co-Authored-By` trailers; `stats` classes from git (unattended, human-hints, human-written, flags-approved); the README "AI use" paragraph; the timeline's per-day co-author label. **Gap:** `progress.py` and the page do not publish the class or model split per function or in the headline.
- **Effort:** S. **Value:** med.

---

## Considered and dropped (no gap, or does not apply)

- **decomp-permuter / an automatic host-side permuter on near misses:** `search.py` exists, guided by the slot model. Phase 7.1 measured 0 exact and 0 near on 445 rows at 256 B+, and FNV's reordering tool fixed 0 of 40. Already on the Skip line in tools.md.
- **splat-style automatic splitting:** `discover.py`, `splits.py`, `symbols.csv` and Ghidra reconciliation cover it. Symbol import is folded into idea 6.
- **m2c / asm-differ:** no x86; `lift.py` and objdiff with the relocation check cover the roles.
- **objdiff features not used:** `progress_categories` is used. `report changes` overlaps the progress timeline and daily log. `scratch` (decomp.me button) would push game bytes to a web service, already "sparingly". `symbol_mappings` is folded into idea 6.
- **reccmp-aggregate (best-of-N builds):** answers MSVC build entropy. Watcom here is deterministic (normalized SHA-1 equal native and under wibo, toolchain.md "wibo").
- **ReC98 "position independence" axis:** matters for a port. ReverseApoc is explicitly not a port, and the in-place splice is the design.
- **Static recompilation (N64Recomp, XenonRecomp, Zelda64Recomp, Jamulator):** these build runtimes, not matching source. Their verification is play-testing a port, which does not transfer. The one transferable piece (running the original headless for evidence) is idea 10. ido-static-recomp's compiler-in-container matches what wibo plus the D-03 native-vs-wibo check already prove.
- **Heumann's hashed verify script and Lewis's SHA-1 hook:** covered by the D-15 manifest-hash guard, hooks and the driver-owned verification.
- **SWE-agent ACI (lint on edit, terse tool output):** the attempt check lints, refuses `#pragma`/`_asm`, and prints bounded output.
- **Contributor onboarding:** the README has a "spend your own plans" path, the drive-budget skill and match.yml. No concrete gap found beyond idea 11.
- **trAIns (Rios & Chaimowicz 2009):** an AI built on an OpenTTD reimplementation. No harness or measurement lesson for drives; it belongs to the paper's future-work section.
