<!-- Literature-mining report of 2026-11-18 (three research agents); source of the todos filed that day. Quotes and numbers from papers came through web summaries: re-read the source before citing. -->

# Ideas from LLM-decompilation and AI reverse-engineering research for ReverseApoc

Written 2026-11-18. Read-only research: nothing in the repo was changed.

**How this was built.** First I read what ReverseApoc already has:
- CLAUDE.md, docs/tools.md, docs/matching.md, docs/learnings.md and docs/model-comparison.md ("The difficulty curve");
- the two research notes and the spike manifest;
- every todo title and first paragraph;
- the code an idea touches: `contextpack.py`, `attempt.py`, `picker.py`, `search.py`, `classify.py`, `causes.py`, `stats.py`, `readlint.py`, `lift.py` and the `watcom-decomp` skill.

Then I read the papers on arXiv HTML, USENIX and NDSS. Decomperson, the NDSS 2026 study and the USENIX 2024 taxonomy were read as full text through `pdftotext`. Section numbers are the papers' own. WebFetch gives a model's summary of a page, so a quoted number is that summary's reading of the paper. Check it against the paper before citing it in the paper.

**The bottleneck these ideas aim at.** From docs/model-comparison.md:
- Match rates fall about 3x per size bucket.
- On 2026-11-14 the rates were 5% under 64 B, 3% at 64-255 B, 0.4% at 256-1023 B, and nothing at 1 KB or more has ever matched.
- Mismatches are 97.6% of tries. Build failures are 0.3% (docs/learnings.md, 2026-11-09).
- The leading mismatch class is length differences: 328 of the 2026-11-09 sample.

Ideas that help the 256 B+ rows, or that use the deterministic oracle better, rank highest.

Ideas are ordered by value, then effort.

---

## 1. Structure-first matching for 256 B and up: a control-flow section in the pack and a structural score in every check

**Sources**
- HELIOS, arXiv:2601.14598, https://arxiv.org/html/2601.14598, §III-C "Hierarchical Abstraction and Prompt Format", §V-A RQ1, §V-D RQ4 (prompt ablation), §VI-B.
- SK2Decompile (ICLR 2026), https://arxiv.org/html/2509.22114, §3.2-3.4, §4.2 "Ablations" (Table 4).
- Echo, arXiv:2609.18706, https://arxiv.org/html/2609.18706, §6.3 (CFG graph-edit similarity, Eq. 4), §7.3.
- Decomperson (USENIX Sec 2022), https://www.usenix.org/system/files/sec22-burk.pdf, §6 "RQ2: How do Humans Decompile?".

**What they do**
- HELIOS gives the model four prompt blocks before the raw Ghidra C:
  - FUNCTION_CONTEXT: the signature, block and loop counts;
  - CFG_OVERVIEW: each block's successors and roles, such as loop header or branch target;
  - BLOCK_DETAILS: per-block P-Code, keyed by block id;
  - the raw Ghidra C itself.

  A system rule says branches in the output must match the CFG.
- SK2Decompile first recovers a structure-only IR, with identifiers as placeholders, then names it.
- Echo scores candidates by assembly edit distance and also reports CFG similarity.
- Decomperson's humans first got the program's outline and signatures to compile. Then they worked one function at a time with small, single-hypothesis edits.

**What ReverseApoc would implement**
1. A new optional pack section, "Control flow", in `tools/reverseapoc/contextpack.py`, placed after "Target listing". It is built from `lift.py`'s existing `blocks()` and contains:
   - one line per basic block: offset range, size, successors (fall-through, taken), and whether it is a loop header or the target of a back edge;
   - the layout order Watcom emitted;
   - the loop count and branch count.

   It is offsets and counts only, so it is no more game-derived than the listing. It stays under build/driver/.
2. In `attempt.py`'s check summary (and `checks/NNNN.json`), a structural line for every plain check: `structure: blocks ours 14 / original 17, branches 9/11, calls 4/4, length 412/436, first block that differs @0x120`. It is computed in the container from both decoded objects, the way `classify.classify_pair` reads them.
3. A rule in the `watcom-decomp` skill, through `writing-skills`, for functions of 256 B or more: make the structural line equal (block count, branch count, length) before working on registers. The `plan.json` regions already give the grid.

**Why it would help**
- HELIOS §V-A: object compilability rose from 45.0% to 85.2% with the structure blocks (Gemini 2.0 Flash), and to 94.9% with compiler feedback. Functional correctness rose from 38.1% to 49.2%. For GPT-4.1 Mini it did not rise (58.0% to 50.3%), so the gain depends on the model and must be measured here.
- SK2Decompile §4.2: structure-only output (62.56) already beats end-to-end decompilation (58.37), and the two-phase pipeline reaches 63.75.
- ReverseApoc's own mismatch data says the agents most often get the shape wrong: length differs leads with 328, then "ours longer than the row" with 60. A structural line names that failure directly. Today the agent sees only the 8 rows around the first differing byte.

**Existing-feature check**
- What exists:
  - the target listing with converter notes;
  - the Ghidra draft;
  - `plan.json` regions (byte ranges plus intent);
  - the region board for 256 B+ (which 0x100 region is exact in which check);
  - `lift.py`'s block builder, used only by the converter.
- The gap:
  - no block, successor or loop view reaches the agent;
  - no check reports structure: the region board is byte-addressed, so one inserted block shifts every later region to "differs".

**Effort:** M. **Value:** high.

---

## 2. A full mismatch report and the mismatch class in `attempt check`

**Sources**
- Echo, §5.2 "Neural Refinement" (the model gets the current C plus a difflib assembly diff), §5.3 (the reasoning model gets the code, the mismatch and the full target assembly, for 5 rounds), Appendix C (seven mismatch patterns: register allocation, stack frame, loop control, data type, global object size, data flow, external or indirect call).
- SymDec, arXiv:2611.18892, https://arxiv.org/html/2611.18892v1, §3.4 "Feedback for Code Repair".
- "Recompilation Is Not Enough", arXiv:2609.07201, https://arxiv.org/html/2609.07201v1, §3.
- Decaf, arXiv:2605.11501, https://arxiv.org/html/2605.11501, §III-C (its reranker reads a disassembly diff).

**What they do**
- Echo feeds back a diff of the whole function, not the first difference.
- SymDec returns a structured report: the input, both outputs, the differing values, whether the difference is in the return value or in memory, and the scope.
- The Coreutils repair paper sends a compact summary of failures rather than full logs. It runs deterministic fixes first, then the LLM on what is left.

**What ReverseApoc would implement**
- In `attempt.py` and the check JSON, add `mismatches[]`: every run of differing instructions, not only the first. Each run carries its offset range, its row count, and the mnemonic shapes ours/original. Cap it at about 6 runs and 40 rows so the summary stays compact.
- Add `class`, taken from `classify.classify_pair`: tail, slot, size, register, branch or mixed. It already exists for batch records but is never shown in a session.
- Add one route hint per class. For example, "register: try assignment or use order (skill §C89)" and "branch: block order; see the structural line (idea 1)".
- The summary prints the class and the first two runs. The JSON holds them all. Nothing new is committed: checks/ lives under build/.

**Why it would help**
- Echo §7.4: its refinement stages, which use the diff, add exact matches on top of sampling, and each stage alone does less than both together. Echo matched 35.5% of 62 Mirai functions against 8.1% for GPT-5.6 (§7.6).
- SymDec §5.3: structured counterexample feedback raised the single-step pass rate from 90.1% to 93.3%, against 90.7% with plain fuzzing feedback.
- Decomperson §6: each submission averaged 47 changed characters and +1.5% diff score, and edits were "almost as likely to cause the diff score go down as to go up". Reversers test one hypothesis per submission, so they need to see what each edit moved. In a 400 B function the first difference hides every later one.

**Existing-feature check**
- What exists:
  - the 8-row window around the first difference (`bytes.first_va`);
  - `reloc.problems`;
  - the region board (256 B+ only);
  - `classify.py` (batch only);
  - `causes` (after the night).
- The gap: the skill says "The window is all you see of your own object ... write it in notes.md as a tooling request". No session sees later differences or the class.

**Effort:** M. **Value:** high.

---

## 3. Funnel diagnostics for attempts (stages, exit reasons, checks to match), plus a free refusal of a repeated C

**Sources**
- Reveree, arXiv:2609.01185, https://arxiv.org/html/2609.01185:
  - §4.3 "The Eight-Stage RE Schema";
  - §4.4 "Two-Channel Stage Detection" (deterministic rules for action stages, an LLM judge only for comprehension);
  - §4.5 (stage coverage, progress depth, "stall funnel");
  - §5.3.1 "Failure Modes": 852 failures were 50% budget exhaustion, 25% giving up, 19% round cap, 4% tool errors and 2% killed. Codex gives up in 98% of its failures, Sonnet exhausts its budget in 95%, and a bigger budget rescued only 10-15%.
- NDSS 2026 human-LLM teaming (Basque et al.), https://www.ndss-symposium.org/wp-content/uploads/2026-f380-paper.pdf, Finding 16: top performers used 1.71 LLM queries per function, bottom performers 3.43. Finding 18: the benefit comes on the first visit.
- Decomperson §6 (Table 3): 82% of edits touch one function.
- Macabeus's benchmark, already in `notes-automation-loops.md` Q6: about half the matches come on the first attempt, and 49 submissions were duplicates.

**What they do**
- They turn each trajectory into deterministic milestones and exit reasons, then find where failing runs fall away from solving ones.
- They show that larger budgets mostly buy nothing.

**What ReverseApoc would implement**
1. `reverseapoc causes --funnel RUN...`, or a `stats --run` table. It reads the saved `checks.jsonl`, `checks/NNNN.json`, `NNNN.note.json`, `plan.json` and `giveup.json`, and reports per arm and size bucket:
   - Stages:
     - S1: plan accepted;
     - S2: first check compiled (exit not 2);
     - S3: objdiff at least 80;
     - S4: at least 95, or one region exact;
     - S5: sweep ran;
     - S6: exit 0.
   - Exit reasons: check budget used, three shapes, time or turn cap, sweep hit, flags (no -s), tool error, guardrail.
   - The check index of the best and of the matching check.
   - The number of regressions (a check below the attempt's best so far).
   - The number of repeated C hashes.
2. In `attempt.py`, refuse with exit 2, counting nothing, a plain check whose `checks/NNNN.c` sha256 equals an earlier plain check of the same attempt and flags. A test runs first, as usual.
3. Read the funnel before setting the 25-check and 30-minute budgets, and the number of re-passes per function, per size bucket. That ties into `quota.toml` and the drive-budget skill.

**Why it would help**
- Quota, not money, binds the drives (learnings 2026-11-11). If most matches land by check 8, as Reveree's 10-15% rescue rate and Macabeus's first-attempt share suggest, a smaller check budget for the 64-255 B rows buys more sessions per week.
- The funnel also shows whether 256 B+ attempts stall at S3 (shape) or at S4 (registers). That decides between ideas 1 and 2, as the learnings entry "Measure where the bottleneck is before ordering plans" (2026-11-06) asks.

**Existing-feature check**
- What exists:
  - `causes`: per-try build-failure, mismatch and match counts, plus mismatch keys;
  - `stats --run`: per-arm sessions, turns, tokens and per-try rates;
  - `giveup.json` categories;
  - the check notes' change, why, expect and observed.
- The gap:
  - no per-attempt progression (stage reached, best-check index, regressions);
  - no exit-reason breakdown;
  - no duplicate-C detection (attempt.py has none);
  - nothing ties the budgets to measured checks-to-match.

**Effort:** S-M. **Value:** high.

---

## 4. Measure the look-alike retrieval, then widen it across EXEs and to near-miss C

**Sources**
- FidelityGPT (NDSS 2026), arXiv:2510.19615, https://arxiv.org/html/2510.19615v1:
  - §III-C (dynamic semantic-intensity line selection);
  - §IV-A (RAG over 241 labelled distorted lines, k = 1);
  - §IV-F RQ3 (ablation): its selection reached 0.91 accuracy against 0.81 for random lines, at 4.51 s and about 1,502 tokens, against 7.94 s for all lines.
- Idioms, arXiv:2502.04536, https://arxiv.org/html/2502.04536, §II-A and §IV-D "The Role of Neighboring Context": call-graph neighbours in BFS order raised user-defined-type accuracy from 9.2% to 15.1% (CodeGemma-7b), with about one point of change in correctness.
- CLAP, arXiv:2402.16928 (assembly embeddings, GCC and Clang corpora).
- Nova (ICLR 2025), arXiv:2311.13721: +6.17% Recall@1 for binary similarity.
- ReverseApoc's own `docs/research/notes-vector-retrieval-bsim.md` §1: "No published experiment isolates the match-rate gain from retrieved similar examples".

**What they do**
- They retrieve the context most like the target and prove its effect with an ablation against random or full context.

**What ReverseApoc would implement**
1. An A/B on frozen picks first. `drive --hold` with one pack variant per arm, through a driver flag such as `--pack-variant no-lookalikes`, or a `contextpack` switch the hold run records in its run marker. Compare k = 3 (today) with k = 0 and with 3 random matched functions, on the same 64-255 B picks.
2. If retrieval helps:
   - Let `_lookalike_inputs` also rank the other EXE's matched rows. UFO2P and TACP come from one codebase. Watch the variety rule and the flag cells.
   - Rank partial rows of at least 95% from the earlier best C as a second, labelled kind of look-alike ("near-miss C, not proven").
   - Normalise operands before the difflib ratio (registers, immediates, displacements), as Mizuchi does.
3. Use the look-alike ratio as a picker key, as Lewis did (rows with a strong matched look-alike first). See `notes-automation-loops.md` Q5.

**Why it would help**
- FidelityGPT's 10-point gain is for picking which context to show, not for showing more. The pack has a 24 KB cap (D-14), so sections compete.
- Idioms shows that call-graph neighbours help most with types, which the pack already lists (callers and callees with prototypes). The look-alike section is the unmeasured one.
- The match rate per pick is now 2-5%, so a held A/B needs about 100-150 picks per variant to see a change of a few points. Size it from the funnel (idea 3).

**Existing-feature check**
- What exists: "Look-alikes" in the pack (difflib over mnemonic sequences, floor 0.6, top 3, matched rows of the same EXE only, `LOOKALIKE_FLOOR` noted as "tuned from attempts.jsonl later").
- The gap:
  - the section was never ablated;
  - it never looks at the other EXE or at near-miss C;
  - the picker does not use similarity.

**Effort:** M. **Value:** high, if the A/B shows an effect.

---

## 5. Cross-EXE twin transplant: a deterministic pass before any agent

**Sources**
- CLAP (arXiv:2402.16928) and Nova (§ binary code similarity) treat function similarity across binaries as a solved retrieval task for GCC and Clang code.
- coddog and Lewis, in ReverseApoc's `notes-vector-retrieval-bsim.md` §5: "a function matched in one exe can seed the other (copy C, expect same build flags)".
- The paper side: FidelityGPT's retrieval of a known-good pattern (§IV-A) is the learned version of this idea.

**What they do**
- They find the same function in another binary and reuse what is known about it.

**What ReverseApoc would implement**
1. A batch verb, for example `reverseapoc twins`, over `tools/reverseapoc/batch.py`:
   - for every matched row in one EXE, find rows in the other EXE with the same length and an equal sequence of masked instructions (relocated fields and fixup targets masked);
   - copy the matched definition into the twin's unit with the twin's placeholders (callees and `D_` mapped through the fixups' targets);
   - compile under the twin unit's rule;
   - judge it with `batch.judge`.
2. An exact result becomes a candidate for the normal gate, never a match by itself.
3. Near twins (a ratio of at least 0.9) go to the front of the queue with the twin's C as "Earlier best C".
4. Measure first: count the twins (exact masked and at least 0.9). That is one script run, effort S.

**Why it would help**
- It costs no model tokens. Spike 010 measured about 0.1 s per compiled variant.
- `docs/tools.md` already says the opcode-distance idea "powers UFO2P-to-TACP twin matching", but nothing implements it.

**Existing-feature check**
- What exists: the batch harness, look-alikes within one EXE, and `libmatch` (runtime library rows only).
- The gap: no cross-EXE pairing of game code anywhere in `tools/`. A grep for twin, cross-EXE and "both EXEs" finds only gate and header code.

**Effort:** S to measure, M to build. **Value:** high if the twin count is large; drop it if not.

---

## 6. Per-function differential emulation for clean-room spec claims (a new rung on the SPEC-01 ladder)

**Sources**
- "When LLM Decompilers Recompile More and Preserve Less", arXiv:2609.05370, https://arxiv.org/html/2609.05370v1:
  - §4.1 "Oracle Design": a driver per function, AFL++ on the reference, comparing return value, written bytes and writable globals (.data/.bss), with ASan and four reruns;
  - §5.2: 4.9% of candidates that pass every shipped test still diverge, and LLM4Decompile raises the build rate from 75% to 90% while the matched rate falls from 74% to 62%;
  - §5.3: functions with introduced symbols diverge more often (53% against 20%).
- SymDec, §3.2-3.3 and §4.4: angr symbolic exploration, a solver-found counterexample replayed concretely on both binaries; 4.5% hidden differences against 2.4% found by fuzzing (§5.3); line coverage 96.2% symbolic against 94.8% fuzzing (§5.2); §6.1 limits on globals and environment.
- Decomperson §7: per-function diff score tracked hidden unit tests at Pearson r = 0.75 and 0.64.

**What they do**
- They check behaviour against the original binary, not against shipped tests, with generated inputs, replay confirmation and structured counterexamples.

**What ReverseApoc would implement**
- A Phase 8 verb, `reverseapoc spec-probe SPEC`, under Milestone 1 rules.
- How it works:
  - It loads the cited function's bytes from `le.load_flat` in memory, never written out. It runs them in Unicorn, x86-32 flat, with `__watcall` arguments in eax, edx, ebx and ecx, the stack set up, and modelled `D_` globals mapped from the data object.
  - It compares the result with an executable form of the spec's scenarios: each `#### Scenario:` WHEN/THEN gets a machine-readable inputs and expected-outputs block, plus random and boundary inputs inside the spec's stated domain.
  - It reports agreement counts, and counterexamples as register and global values only.
- A passing probe adds a status `emulator-verified` between `backed-by-matched-code` and `dosbox-verified`. `speclint` checks that the claim names the probe run.
- A second use: run the same probe between a near-miss's best C (compiled by Watcom, run in Unicorn) and the original. A partial row whose behaviour agrees then supports a spec as "behaviour-checked, not byte-matched". Decomperson's r = 0.64-0.75 says a high diff score usually means equal behaviour, but not always.
- Unicorn is a new dependency: give it a `docs/tools.md` row and a reason.

**Why it would help**
- Today the ladder jumps from matched code, where the spec author reads the C, straight to a DOSBox whole-game test that does not exist yet (SEED-261025-hft, Milestone 2).
- Liu et al. and SymDec show that reading code, or running a few tests, misses 4.5-4.9% of behaviour differences. An LLM spec author reading matched C is exposed to the same "introduced symbol" error (§5.3) when it paraphrases into formulas.
- The emulator gives the owner's spec review (SPEC-09) a mechanical check.

**Existing-feature check**
- What exists:
  - the ladder `drafted -> cited -> backed-by-matched-code -> dosbox-verified -> reviewed-by-openapoc` (REQUIREMENTS SPEC-01);
  - `speclint` (planned);
  - the DOSBox harness seed for M2;
  - Unicorn mentioned only as NHL95PC's compiler-internals trick (spike 010).
- The gap: no per-function behavioural check of a spec in M1, and nothing that checks a spec's numbers against the binary.

**Effort:** L. **Value:** high for Phase 8.

---

## 7. Struct shapes inferred across functions, shared by packs and readability headers

**Sources**
- Dramko et al., "A Taxonomy of C Decompiler Fidelity Issues" (USENIX Sec 2024), https://www.usenix.org/system/files/usenixsecurity24-dramko.pdf:
  - §4 has 15 top-level codes, 52 in all;
  - §5.1.2 "Deterministic given types": C0.b, C1, C3, C8, C11, C13 and C14 become fixable once types are known. It also says "Accesses of different parts of a composite type are, in general, spread out throughout multiple functions ... it might be necessary to examine all functions in which a given composite data type is used", and names this a "major opportunity".
- Idioms §II-A: code and type definitions are predicted jointly; neighbours raise UDT accuracy from 9.2% to 15.1% (§IV-D).
- ReCopilot, arXiv:2505.16366, https://arxiv.org/html/2505.16366, §3.4.2 "Data Flow Analysis": aliases are traced across functions; the ablation (Table 7) shows struct recovery rising from 9.77 to 14.47.
- Liu et al. §5.3: types and fields introduced without evidence drive divergence.

**What they do**
- They recover composite types from accesses across many functions, with evidence, rather than guessing them inside one function.

**What ReverseApoc would implement**
1. A deterministic verb, for example `reverseapoc fields EXE`. For each `D_` base and each pointer argument traced through the call graph (`callgraph.py` plus the converter's symbolic `r_`/`s_` state), it gathers every `[base + disp]` access over all rows, matched or not:
   - the width;
   - signedness (movsx or movzx);
   - stride (indexed);
   - the functions touching each offset.

   It writes candidate `struct unk_XXXX` layouts with per-field evidence under build/.
2. The pack gains a "Struct shapes" section for the target's `D_` externs and pointer arguments. Where a matched unit already declares the shape, it says which unit.
3. The readability skill's header proposals start from these shapes, so a shared header carries field evidence (`Evidence: table:` lines) rather than one unit's guess. Every proposal is still proved by the bytes and the gate.

**Why it would help**
- Today each matching agent declares its own `struct unk_XXXX` in its unit, and only `include/common.h` is shared.
- model-comparison.md records Haiku's held match that "rewrote a shared struct and broke a matched function of its unit". A cross-function layout gives every agent the same offsets.
- The readability pass is the "skin" stage that SK2Decompile and Idioms show depends on good types.

**Existing-feature check**
- What exists:
  - the "D_ externs" section (names only);
  - the skill's extern-type table, one access at a time;
  - `causes`'s shared-header-gap ranking;
  - readlint RL04 (placeholder field names) and RL05 (pointer arithmetic casts).
- The gap: no aggregation of field accesses across functions, no shared struct headers yet, and nothing that hands a struct shape to the pack.

**Effort:** L. **Value:** high.

---

## 8. Semantics-preserving control-flow and expression mutations as a `search` axis

**Sources**
- Echo:
  - §5.1 "Rule-Based Refinement": greedy, kept only if the distance falls;
  - Appendix B mutation rules:
    - branch: invert, merge or split conditions, restructure a terminal guard, hoist a common suffix, if to ternary;
    - loop: while to for, guarded do-while, invert the loop guard;
    - expression: De Morgan, swap comparison operands, swap commutative operands, toggle signedness.
- Decaf §III-C: reranking candidates by byte distance, with relocations as wildcards, took single-sample accuracy from 59.1% to 83.9% at N = 32 (Table IV).

**What they do**
- They search a small set of rewrites, each of which keeps the program's meaning, with the compiler as the judge.

**What ReverseApoc would implement**
- Add a `branch` axis and an `expr` axis to `tools/reverseapoc/search.py` AXES, after `type` and before `statement`. Use only rewrites with the same meaning in C89, and keep `search`'s rule that only an exact variant stands for anything that could change behaviour.
- Route rows that `classify` marks `branch` or `mixed` to it.
- Measure it on the near-miss rows of at least 90% with the Phase 7.1 curve gate (`measure_curve.py`) before any wider use.

**Why it would help**
- The 2026-11-06 learnings entry says class `slot` held none of the 841 not-matched rows, so the existing declaration and slot axes cannot reach most near misses. Branch and register classes are where they sit.
- Echo's mutators target exactly block order and loop shape, which Watcom's optimiser fixes and an agent rarely guesses within three shapes.
- Caveat: the FNV note in tools.md (an instruction-reorder tool fixed 0 of 40 near misses) and Lewis's permuter "doom loops" argue for a small, closed rule set measured by the curve gate, not a random permuter.

**Existing-feature check**
- What exists:
  - `search` axes: type, statement, scope, declaration;
  - spike 010's variants (23 of 200 with the converter, 3 of them from the variant search);
  - decomp-permuter skipped.
- The gap: no axis rewrites conditions, loops or expressions.

**Effort:** M. **Value:** medium. Measure on the near-miss lane before building more.

---

## 9. A whole-program signature table before per-function matching (Decomperson's "stub phase")

**Sources**
- Decomperson §6: reversers first "stub out the program, making sure that functions had enough code to successfully compile, and that the functions had the correct type signatures". Signature edits came early and naming late. Only 37% of first submissions compiled.
- HELIOS §III-C: FUNCTION_CONTEXT carries the signature.
- ReCopilot §3.4.1 "Call Chain Analysis": BFS callers and callees, the top 10 by an informativeness score.
- The taxonomy, §5.1.3: its four return cases (void or non-void, return value used or not), as an incorrect-return-behaviour issue. ReverseApoc faces the same `void` or `int` question.

**What they do**
- They fix every function's interface first, so per-function work starts from consistent prototypes.

**What ReverseApoc would implement**
1. A deterministic pass, for example `reverseapoc signatures EXE`, over `callgraph.py` and `lift.py`'s symbolic state:
   - argument count = the registers in `__watcall` order (eax, edx, ebx, ecx) that the callee reads before writing, combined with what every caller sets before the call;
   - stack arguments from `ret n` or caller cleanup;
   - return = `int` if any caller reads eax after the call, else `void`.
2. It writes a generated table of counts and kinds, with no bytes, under build/ or `config/<exe>/`.
3. The pack's Callers and Callees list an inferred prototype, marked "inferred", for unmatched neighbours. Today a prototype appears only for a matched one. The target also gets its own inferred prototype.
4. Check whether it is worth building by counting `giveup.json` category `call_convention` and the `causes` reloc keys that involve calls.

**Why it would help**
- Every session today re-derives each callee's argument count from the listing (skill §"Calling convention").
- Two agents can disagree, and the "void or int" rule defers to callers no session reads.
- One table removes that per-session work and makes the units agree.

**Existing-feature check**
- What exists:
  - the converter's `eax=<expr> edx=<expr>` hints on calls (per call site, "a hint, not proof");
  - matched callers' and callees' prototypes in the pack;
  - the skill's rules.
- The gap: no cross-function, whole-EXE signature inference, and no prototype for unmatched neighbours.

**Effort:** M. **Value:** medium. Measure the give-up category first.

---

## 10. Leakage and memorization controls for the paper and the held comparisons

**Sources**
- Asjad, "A Memorization Floor for LLM Refinement of Decompiled Code", arXiv:2609.17236, https://arxiv.org/html/2609.17236:
  - §3.2: the same function refined three times, intact, alpha-renamed (one consistent bijection) and scrambled (per occurrence), with a manipulation check (Table 2);
  - §7: five recommendations: a floor run against a second vendor's model, a manipulation check shipped with every ablation, arm-matched chance baselines, applicability checks registered in advance, and LLM-in-the-loop results re-run under a registration committed before the re-run.
- Reveree §5.4.1-5.4.2: Opus 4.7 reproduced 7.4% of picoCTF flags exactly from descriptions alone. Surface mutations dropped NYU-CTF solve rates by 7.7-30 points.
- Riddell et al., arXiv:2403.04811 (surface and semantic overlap with pretraining data).
- HELIOS §VI-B (cannot rule out HumanEval/MBPP contamination).
- The Spence et al. contamination-free RE benchmark (arXiv:2608.11469) is in the bib but was not read for this note.

**What they do**
- They separate what a model reads from the input from what it remembers, and pre-register the comparison.

**What ReverseApoc would implement**
1. A contamination ledger in `stats --run` and the paper's method:
   - each arm in `config/driver/backends.toml` records the model's knowledge cutoff;
   - each held pick records the first date any C for it (matched or best) was pushed to the public GitHub repo;
   - `stats` reports exact rates for picks never published before the arm's cutoff separately from the rest.

   The game's source is not public, which is a strong argument, but ReverseApoc's own matched C is public from 2026-10 on. Models trained later may have read it.
2. A recall probe in each canary or held run: one session per arm asked for a function's C with no listing. The expected result is no match. It is cheap evidence for the paper, in the spirit of Reveree §5.4.
3. For readability names, a naming-floor ablation on a seeded sample: rerun one readability unit with alpha-renamed callee and global placeholders and with strings scrambled. Names that survive scrambling came from the model's prior (OpenApoc's vocabulary is allowed by D-21, but OpenApoc code is not), not from the cited evidence. Report it beside the readability numbers.
4. Pre-register each held comparison: commit the pick list and the hypothesis before the run. `--write-picks` already freezes the list; add the hypothesis line in the run marker.

**Why it would help**
- These are the controls a reviewer of the planned arXiv paper will ask for.
- The memorization-floor paper shows that an ablation without a manipulation check can "not ablate" (§5.4). ReverseApoc's hold runs already isolate arms from each other, since `attempt.earlier_notes` drops hold-run notes and records. So the remaining exposure is training data, not the harness.

**Existing-feature check**
- What exists:
  - frozen pick lists (`--hold --picks`, `--write-picks --stratify`);
  - hold-run isolation of notes, give-ups and best C;
  - the stated rule never to compare career rates.
- The gap: no cutoff or publication dates, no recall probe, no naming-floor ablation, no pre-registered hypothesis.

**Effort:** S (1, 2 and 4); S-M (3). **Value:** medium for the project, high for the paper.

---

## Considered and dropped (no gap, or the evidence does not fit)

- **Compile-error feedback loops (DecLLM, ISSTA 2025, §4.2: 15 rounds, 37% to 75% recompilation; Wong et al. arXiv:2310.06530).** Build failures are 0.3% of ReverseApoc's tries (learnings 2026-11-09), and the C89 lint runs before commit. Nothing to gain.
- **Bottom-up naming order for readability (NDSS 2026 §VII-E, participant E22, "inside out").** `picker.readability_queue` is already bottom-up over callee SCCs.
- **Isolating one arm's work from another in held comparisons.** This already exists: `attempt.earlier_notes` leaves out hold-run notes and records.
- **Readability defects from the taxonomy (C1 non-idiomatic dereference, C6 literals).** readlint RL05 (pointer-arithmetic casts) and RL06 (magic literals) already cover them, and the bytes gate them.
- **Readability metric gating against Goodhart (Archibald and Thijssen, arXiv:2606.06838, §3.2 and §4.2: a 0.85 CFG gate, agents "minimize changes").** ReverseApoc's gate is byte identity, which is stronger. An owner-rated sample would be the only addition, which is low value now.
- **Best-of-N sampling with oracle selection (Decaf §III-B/C, Echo §4.1).** Multi-arm `--hold` with `--land-held` already samples several models on the same pick and keeps the cheapest exact one. Lewis found `--repeat 3` paid only in the extreme tail.
- **Fine-tuned decompiler models and assembly embeddings (SLaDe CGO 2024, Nova ICLR 2025, LLM4Decompile, ReCopilot, CLAP).**
  - They are trained on GCC or Clang x86-64 and ARM code, with no Watcom, `__watcall` or DOS/4GW LE.
  - ReverseApoc has about 200 matched functions, far from the thousands of pairs a fine-tune needs (`notes-automation-loops.md` Q8).
  - Re-evaluate only CLAP-style embeddings, and only if idea 4's A/B shows retrieval matters.
- **Benchmarks (DecompileBench, Findings of ACL 2025; ExeBench, MAPS 2022).** Both measure re-executability or readability on GCC and Clang code. Their evaluation-design lessons are already in ReverseApoc:
  - DecompileBench: readability and correctness diverge (LLMs scored 52.2% lower on functional correctness);
  - ExeBench: executable subsets are simpler than real code, and Decaf found its cached outputs wrong.

  ReverseApoc's held, size-stratified pick lists measured by bytes are stricter. For the paper, cite them as contrast only.
