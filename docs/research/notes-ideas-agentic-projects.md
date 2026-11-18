<!-- Literature-mining report of 2026-11-18 (three research agents); source of the todos filed that day. Quotes and numbers from papers came through web summaries: re-read the source before citing. -->

# Ideas from other agentic matching-decompilation projects (2026-11-18)

Thirteen ideas ReverseApoc does not have yet, ranked by value per effort. Each one was checked
against what already exists: CLAUDE.md, docs/tools.md, docs/learnings.md, docs/model-routing.md,
docs/model-comparison.md, the todos, the watcom-decomp skill, and the code it would touch
(`attempt.py`, `contextpack.py`, `picker.py`, `classify.py`, `search.py`, `driver.py`). Ideas
with no gap left were dropped; they are listed at the end.

**How the sources were read.** Pages came through WebFetch, which hands back a model's summary
of the page, not the page itself. Section names and quotes below are as that summary gave them.
Re-read the page itself before quoting any of them in the paper. Lewis's repository files were
read raw from GitHub. OpenReview blocked the fetch, so Oblokulov et al. rests on the ICML
abstract only.

**Our own numbers.** Read on 2026-11-18 from `progress/attempts.jsonl` (4,070 attempt records,
849 functions) and from the local `build/driver/*/*/*/attempt-*/checks.jsonl` and `notes.md`
(277 runs, 3,827 attempts with a plain check, 14,586 plain checks). The scripts are in
`scratchpad/ideas/` (`checkstats.py`, `tail.py`, `ledger.py`, `hard.py`), run with
`uv run --no-project python -I`. The build/ tree covers only the runs still on this machine.

| # | Idea | Value | Effort |
|---|---|---|---|
| 1 | `attempt diff`: the whole aligned diff of our object | high | M |
| 2 | Twin-first and similarity-first picking, with look-alikes from the other EXE | high | M |
| 3 | Retire long-tail functions from the agent queues, onto a hand-off board | high | S-M |
| 4 | Triage rows that branch into another row (suspected bad splits) | med-high | S-M |
| 5 | A per-function hint file that the owner writes, read into the pack | med-high | S |
| 6 | Pre-registered decision rules and paired statistics for held comparisons | med | S |
| 7 | Set the check budget from our own checks-to-match data | med | S |
| 8 | Show the failure class (`classify.py`) in `attempt check` output | med | S |
| 9 | Collect the agents' tooling requests across notes.md files | med | S |
| 10 | A/B test of carried context: earlier best C and give-ups against a fresh start | med | S-M |
| 11 | Reasoning effort as an arm setting, measured on held picks | med | M |
| 12 | Refuse a check whose C repeats an earlier check | low-med | S |
| 13 | Notify the owner when a drive stops or ends | low-med | S |

---

## 1. `attempt diff`: the whole aligned diff of our object

- **Sources.**
  - Echo, https://arxiv.org/html/2609.18706v1. §2.2, Algorithm 2 and §5.3: after the rounds of
    local-diff repair, reasoning-based refinement "receives the full target assembly, not only
    the local diff". The diff the neural stage reads (§5.2) is a GenDiff/difflib diff of the
    whole function.
  - Macabeus, https://gambiconf.substack.com/p/can-llms-really-do-matching-decompilation. In
    the failure modes and planned improvements: Claude claimed false matches because it "could
    not run objdiff itself", and the first future item is "add objdiff visibility to the MCP
    tool".
  - Wortley, https://freeqaz.com/blog/llm-assisted-decompilation, "Bet: structured tools, not
    vibes": agents "call typed tools: run a structured diff…".
- **What they do.** The agent sees its own compiled code against the target across the whole
  function, not only at the first difference.
- **What ReverseApoc would build.**
  - A new wrapper command, `uv run --frozen reverseapoc attempt diff [NNNN]` (the eighth, so
    the skill's "seven wrapper commands" line changes). It prints the aligned instruction diff
    of the latest check (or check NNNN) for the claimed function only, from the object `check`
    already compiled, with every differing row marked.
  - Cap the output at about 200 rows, keeping 3 rows of context around each difference block.
    It uses no check from the 25.
  - It is derived from the agent's own C plus the original's listing, which the agent already
    has. It goes to stdout only and is never written to a record.
  - The check JSON gains nothing. Add the command to the canary probes of every harness and to
    each harness's exact-form command audit.
- **Why it would help.**
  - In our own notes, 181 notes.md files ask for this, the most repeated tooling request:
    "a disassembly of our object", "a window that shows our rows past the first difference",
    "the window shows 8 rows, so the loop body cannot be compared".
  - Today each check shows one difference (`WINDOW_BEFORE = 3`, `WINDOW_AFTER = 4` in
    check.py), so a function with k separate differences needs at least k checks.
  - This matters most at 256 B and up (todo `first-matching-night-256b`). Echo §7.6 says a
    local mismatch "cascades" through register allocation in longer functions, which a window
    at the first difference cannot show.
- **Existing-feature check.** There is the 8-row window and, at 256 B and up, the region board
  (exact or closest per 0x100). The skill says "the window is all you see of your own object…
  write it in notes.md as a tooling request". Gap: no view of our object past the window.
- **Effort / value.** M / high.

## 2. Twin-first and similarity-first picking, with look-alikes from the other EXE

- **Sources.**
  - Lewis, "The Long Tail of LLM-Assisted Decompilation",
    https://blog.chrislewis.au/the-long-tail-of-llm-assisted-decompilation/, sections
    "Prioritising Similar Functions" and "Computing Function Similarity". Once "everything left
    was hard", he "adjusted the agent loop to prioritise functions with similar (matched)
    counterparts". coddog and his own n-gram score "select different most-similar candidates
    in 90.6% of cases", so he keeps both.
  - Repo github.com/cdlewis/snowboardkids2-decomp: `task-runner/decompile-coddog-similar/task.yaml`
    (candidates from `score_functions.py --by-coddog-similarity`, the prompt names "a fairly
    similar function", run with `--model opus --effort xhigh`) and
    `task-runner/decompile-unmatched/task.yaml` (`--by-similarity`).
  - Macabeus's benchmark, prompt section: "up to 5 examples from similar functions", using
    jina-embeddings-v2-base-code.
- **What they do.** The queue is ordered by how close each function's nearest matched
  neighbour is, and that neighbour is named in the prompt.
- **What ReverseApoc would build.**
  1. In `contextpack._lookalike_inputs`, also rank the matched rows of the other EXE (UFO2P for
     a TACP target, and the reverse), labelled `(tacp)` / `(ufo2p)` in the Look-alikes
     section. Today the ranking draws only from `rows` of the same EXE.
  2. A picker order `--order similarity`, for the tier queue and the near-miss lane, that ranks
     by the best look-alike ratio across both EXEs. It applies only above a floor (0.9 for
     twins), after the callee-first rule.
  3. `stats` would split matches by "had a look-alike of 0.9 or more", so the gain can be seen.
- **Why it would help.**
  - The two EXEs share engine code (docs/workflow.md "Select": "Twin functions between UFO2P
    (`ufo24`) and TACP (`tac4`)… are the cheapest wins"). A matched twin's C is close to a
    ready answer.
  - Our match rate fell with size (learnings 2026-11-14). That is the stall in which Lewis's
    change paid off.
- **Existing-feature check.** The pack holds up to 3 look-alikes from the same EXE (difflib
  ratio, floor 0.6). The picker is easiest-first or tier-ordered, with no similarity term.
  docs/workflow.md plans the switch ("switch to similarity-first once enough functions are
  matched") and docs/tools.md lists coddog as "Later". Gap: nothing in the picker, and nothing
  across EXEs.
- **Effort / value.** M / high.

## 3. Retire long-tail functions from the agent queues, onto a hand-off board

- **Sources.**
  - Wortley, https://freeqaz.com/blog/how-agent-swarms-decompile-games, failure modes: "Agents
    grind. They don't decide when to stop". In the human-in-the-loop part, the remaining tail
    "needs either serious distributed compute or a human".
  - Wortley, https://freeqaz.com/blog/llm-assisted-decompilation, "When the metric lies":
    strategies were "retired by their own pre-registered kill criteria".
  - Heumann, https://momo5502.com/posts/2026-10-09-game-decompilation, "Final State": they
    stopped byte matching the last functions because continuing "would consume more tokens".
  - Lewis, "Snowboard Kids 2 is 100% Decompiled",
    https://blog.chrislewis.au/snowboard-kids-2-is-100-decompiled/, "The journey": a
    "Leaderboard shared on discord for tracking work on the remaining… functions", and the
    community did "the final ten".
  - Oblokulov et al., ICML 2026 DL4C, https://icml.cc/virtual/2026/82758 (abstract): run
    history, progress dashboards and "community task brokers" for non-expert contributors.
- **What ReverseApoc would build.**
  - A retirement rule in the picker. A function leaves every agent queue once it has failed
    under K distinct models (K = 3 to start) and its best_percent has not risen over its last
    M sessions. The rule reads `progress/attempts.jsonl`, which is committed.
  - A committed `config/<exe>/retired.csv` (start, models tried, sessions, best_percent, last
    give-up category, class from idea 8) and a "long tail" table on the progress page.
  - Only the owner returns a row to the queues (`reverseapoc retire --return ADDR`), for
    example after a new tool, a hint (idea 5) or a model that has not been tried on it.
- **Why it would help.**
  - From our ledger: 180 unmatched functions were each tried by three or more distinct models.
    They took 1,963 sessions, 48% of all 4,070. 65 of them have a best of 90% or more, which is
    what a human or a targeted tool should look at.
  - The matching rate on a function's later attempts is low: 11.5% on attempt 1, 3.6% on
    attempt 2, 0.7% on attempt 3, 0.7% from attempt 8 on. The 7.2% at attempt 4 tracks new
    tools and models arriving, which is the re-entry trigger above.
- **Existing-feature check.** `build/driver/difficult.json` is a per-night cache for the Phase 6
  picker only. A capped near-miss row leaves the lane for one drive and comes back the next
  night. Gap: no rule across nights, no committed list and no board.
- **Effort / value.** S-M / high (it saves sessions every night).

## 4. Triage rows that branch into another row (suspected bad splits)

- **Sources.**
  - Wortley, https://freeqaz.com/blog/llm-assisted-decompilation, "Decompiling a binary with no
    names": a pool that "looked 'unmatchable' wasn't missing source"; the splitter had
    misattributed it. Reclassifying it gave "+1,176 strict matches in one day".
  - Macabeus, Klonoa post, https://gambiconf.substack.com/p/starting-a-decompilation-project,
    "Refining the assembly": functions with no return "almost always" come from a splitting
    bug, and data misclassified as code "inflates objdiff counts".
- **What ReverseApoc would build.** A `reverseapoc triage` report, also run by the picker as a
  flag (not a filter, at first). It lists every row that:
  - branches or jumps to `<other row>+N`, an interior label;
  - is entered by such a jump from another row;
  - has a fall-through with no `ret` or `jmp`;
  - has a second entry.

  The tier queue and the near-miss lane would show the flag in `--dry-run`. The owner then
  decides whether to merge or split the boundary in `functions.csv` (owner-only, as now).
- **Why it would help.** 23 of our notes.md files ask for exactly this: "a pool filter that
  drops rows whose jump targets are `func_X+offset` interior labels", and "the claim picker
  could flag rows that jump to `<other row>+N`… and rows that contain a second entry".
  Sessions on such rows cannot match, whatever the model.
- **Existing-feature check.** `score.py`'s P16 filter already demands that calls and jumps out
  go only to row starts, but the tier queue takes members "whatever score's P16 filter says of
  it", and the near-miss lane has no such check. The skill stops on a jump-table target outside
  the function. Gap: no boundary check for the tier and near-miss queues.
- **Effort / value.** S-M / med-high.

## 5. A per-function hint file that the owner writes, read into the pack

- **Sources.**
  - Heumann, https://momo5502.com/posts/2026-10-09-game-decompilation, "Working side by side":
    "you can steer the agents… when letting them work autonomously, steering is not possible".
  - Klonoa post, cheating attempts: Claude argued register order was "impossible" to
    reproduce, and this was "quickly dismissed by more experienced decompers".
  - Lewis, 100% post: the last ten functions came from community members who "answered my dumb
    questions… and decompiled functions themselves".
  - Lewis's `tools/claude` bootstraps an attempt from a decomp.me scratch ID: it fetches the
    scratch's `source_code` as the starting C.
- **What ReverseApoc would build.**
  - A committed `config/<exe>/hints.toml`, keyed by start address, owner-only (add it to the
    deny paths of every harness and to the audit). It holds plain text and, optionally, a
    starting C file under a committed `hints/` folder that holds no game bytes.
  - `contextpack` would add a "Hints from the owner" section after the listing, fenced like
    every other section, with no cap cut. The driver would record `hint: true` on the attempt,
    so `stats` can measure what hints buy.
- **Why it would help.** The long tail (idea 3) is where one expert sentence ("this is a
  `switch` with the default first", "the second argument is a `short`") turns a 90% row into a
  match. Today the only way in for that sentence is editing the skill or matching.md, which
  reaches every function.
- **Existing-feature check.** The pack holds the agents' own earlier notes, give-ups and best
  C; matching.md holds global idioms. Gap: no per-function human input.
- **Effort / value.** S / med-high.

## 6. Pre-registered decision rules and paired statistics for held comparisons

- **Sources.**
  - Wortley, https://freeqaz.com/blog/how-agent-swarms-decompile-games, "Model IQ was flat": a
    pre-registered gate that "a stronger model has to double the cheap one to count as a real
    lever". Cheap 13 of 30, Sonnet 5 13, Opus 4.8 15, all together 19.
  - Retrobench, https://retrobench.ai, scoring: "close averages are ties, not an ordering";
    under variance, run-to-run swings "can reach low double digits".
  - Macabeus's benchmark, results: 3 runs per dataset; "88% of the functions had identical
    outcomes across all runs".
- **What ReverseApoc would build.**
  - `reverseapoc stats --paired RUN_A RUN_B` on held runs over the same picks. It prints the
    discordant pairs (A exact and B not, and the reverse), an exact McNemar p-value and a
    Wilson interval per arm, with stdlib math only.
  - A "Decision rule" line that a comparison section in docs/model-comparison.md must carry
    before the run starts, for example "Pro is bought if Sol or Astra hold ≥2x Terra's rate on
    the frozen picks", written into the todo `codex-pro-held-comparison` first.
- **Why it would help.** "Fable 2 matches against Opus 1 on 132 held rows" (learnings
  2026-11-16) has a discordant count of 3 at most, so no conclusion follows. The routing rows
  in model-routing.md are set from 20-pick results that the doc itself calls noise. A written
  rule stops a decision being read off noise after the fact, and the paper needs the
  statistics.
- **Existing-feature check.** model-comparison.md "How to read it" says "a gap of one function
  between two arms is within noise", with no test, no interval and no rule stated in advance.
- **Effort / value.** S / med.

## 7. Set the check budget from our own checks-to-match data

- **Sources.**
  - Macabeus's benchmark, attempt distribution: "nearly half of the matches happened on the
    first attempt"; after the 3rd attempt the chance of a match "drops to roughly one-quarter".
  - Constraint-Guided Multi-Agent Decompilation, https://arxiv.org/html/2604.23940v2: §3.4,
    cases not converging within 5 iterations "rarely succeed with additional attempts"; §5.3,
    only 3-5 pp gained after the first 2 iterations.
  - Lewis, long-tail post, "What about Ralph Wiggum?", for the other side: there "the 85th
    percentile of successful attempts remains 28 attempts", and one function took 87.
- **What ReverseApoc would build.**
  - A `stats --checks` report: the check index at which each match came, and P(match | no
    match by check k), per size bucket and lane.
  - Then an owner ruling on D-07. Either lower `attempt.CHECK_BUDGET` and
    `session.MAX_CHECK_RUNS` (for example to 12), or keep 25 and add a plateau stop to the
    skill's "When to give up": "no new best_percent in the last 5 checks".
- **Why it would help.** From our build/driver logs (227 matched attempts):
  - 64% matched on the first plain check, p85 at check 3, p95 at check 6 and the latest at
    check 10;
  - of the 181 attempts that went past check 10, none matched;
  - a new best_percent after check 10 came in only 25 of 3,827 attempts;
  - the ledger puts sessions with 11-25 check runs at 8% of all tokens (mean 1.88M against
    1.39M for 1-3 runs), for 2 matches in 226 sessions.

  The saving is modest (about 8-11% of tokens), but it costs little. Lewis's opposite figure is
  for Opus on an N64 tail and does not hold here, so re-measure on the 256 B queue before
  changing the budget there.
- **Existing-feature check.** The budget is a fixed 25 (D-07), the give-up rule is "three
  different C shapes" and there is no checks-to-match report. Gap: no measurement and no
  adaptive stop.
- **Effort / value.** S / med.

## 8. Show the failure class (`classify.py`) in `attempt check` output

- **Sources.**
  - Wortley, https://freeqaz.com/blog/llm-assisted-decompilation, "Bet: structured tools, not
    vibes": a forked objdiff that "emits 21 pattern detectors, six fixability classes, and
    machine-readable root-cause diagnoses" for agents.
  - Echo, Appendix C: seven mismatch patterns (register allocation, stack frame, loop control,
    data type, global size, data flow, external symbol).
- **What ReverseApoc would build.** After the window in `attempt check`, print one line:
  `class: slot (the widest mask this row needs); see matching.md "<idiom>"`. It comes from
  `classify.classify_pair` on the object the check already holds, with a fixed map from class
  to matching.md heading. It lands in `checks/NNNN.json` as a label string, like `with_class`
  already does for batch records. A class decides nothing (the module's own docstring).
- **Why it would help.** The agent learns that the whole difference is a slot order or a
  register choice, which the skill's give-up rule already treats differently. Today it infers
  this from 8 rows. It also fills giveup.json's `category` from evidence rather than a guess.
- **Existing-feature check.** classify.py has `CLASSES` and `ROUTES`, but only the CLI's batch
  or search reports call it (cli.py:1193). Neither the check summary nor the pack names a
  class. Gap: the agent never sees it.
- **Effort / value.** S / med.

## 9. Collect the agents' tooling requests across notes.md files

- **Sources.**
  - Klonoa post, "Human supervision": "I still need to read the report to guide the
    improvements".
  - Wortley, failure and human-in-the-loop parts: agents "wrote up each dead end with evidence"
    and handed "the call back to me".
  - Wortley, "When the metric lies": "negative results are committed as first-class
    artifacts".
- **What ReverseApoc would build.** `reverseapoc requests [--run GLOB]` reads every
  `build/driver/**/notes.md` and prints its "Tooling request" lines, normalised (hex folded as
  in `causes`) and ranked by how many attempts and models raised each. The skill would add a
  fixed tag (`Tooling request:` at the start of a line). The coordinator reviews the top items
  after each night and turns them into todos.
- **Why it would help.** 350 notes.md files hold tooling requests. Ideas 1 and 4 came from
  reading them by hand here. Others repeat too: "let sweep stage 2 run when the only reloc
  problem…" (11), "measure only the code part of a row whose tail…" (12), and per-cell
  `first_va` in the sweep JSON. Nothing reads them now, because build/ is never committed and
  no tool parses them.
- **Existing-feature check.** `reverseapoc causes` ranks mismatch causes from the records, and
  the give-up categories are committed. Gap: no reader for the free-text requests.
- **Effort / value.** S / med.

## 10. A/B test of carried context: earlier best C and give-ups against a fresh start

- **Sources.**
  - Heumann, "Lessons": "Throw it away if it's bad"; salvaging "did in fact cost us more time
    than starting from scratch".
  - Heumann, "Why is that?": the workers' comments "effectively acted as unintentional prompt
    injection" on the reviewer.
  - Macabeus's benchmark, failure modes: 49 duplicate submissions that repeat attempt 1.
  - Klonoa post: an agent's "impossible" claim was wrong.
  - Lewis, long-tail post, "Permuters": Claude "optimised around permuter noise", a doom loop.
- **What ReverseApoc would build.**
  - A held drive on a frozen near-miss pick list (the todo `near-miss-write-picks` gives the
    list), split by pick into two packs: the normal one, and one with "Earlier best C" and
    "Earlier give-ups" left out (a `contextpack` switch used only by `--hold`).
  - Compare with idea 6's paired test.
  - Whatever the outcome, label each carried give-up line with its model and mark it
    "unverified claim" in the pack, so one weak model's "needs asm" does not steer the next.
- **Why it would help.** The near-miss lane is now the best yield (learnings 2026-11-14), and
  every session in it starts from an earlier best C. Whether that anchor helps or traps is
  untested. Matches after an earlier failure came mostly from a new model (41 against 24 from a
  model that had failed it before), which is consistent with either answer.
- **Existing-feature check.** The pack always carries best C, give-ups and notes (07.2-02), and
  fences free text as data. Gap: no measurement of the effect and no source label on the
  claims.
- **Effort / value.** S-M / med.

## 11. Reasoning effort as an arm setting, measured on held picks

- **Sources.**
  - Wortley, https://freeqaz.com/blog/how-agent-swarms-decompile-games, "What surprised me":
    the default 8,000-token output ceiling made reasoning models look bad. Raising it to 32k
    with a reasoning sub-cap and an answer floor fixed that. "Capping thinking effort took one
    model from 4/7 to 6/7 byte-exact", and a forced mid-thought wrap-up "turned already-correct
    answers into zeros".
  - Lewis repo, `task-runner/decompile-coddog-similar/task.yaml`: `--model opus --effort xhigh`.
  - Lewis, 100% post: on the last ten functions, "the most effective model appeared to be Codex
    5.5 xhigh".
- **What ReverseApoc would build.**
  - An optional `effort` key per arm in `config/driver/backends.toml`, passed as each CLI's own
    flag (Claude Code `--effort`, Codex `-c model_reasoning_effort=…`, Copilot's flag if it has
    one) and recorded in the attempt record's existing `effort` field.
  - Each effort is a separate arm with its own canary. Then a held run of one model at two
    efforts on the same near-miss picks.
- **Why it would help.** The effect is not monotonic (Wortley gained by capping, Lewis by
  raising), so it has to be measured. Effort may be a cheaper lever than a stronger model on a
  flat-rate plan.
- **Existing-feature check.** The record has an `effort` field, but "a night passes no effort
  (null: the CLI default, D-17)". Only agy's Gemini uses the model-id variants `-high`/`-low`
  (backends.toml comment). Gap: no effort axis for the Claude, Codex or Copilot arms.
- **Effort / value.** M / med.

## 12. Refuse a check whose C repeats an earlier check

- **Source.** Macabeus's benchmark, failure modes ("Duplicate submissions… it happened 49
  times") and planned improvements ("Duplicate-code detection: ask for slightly different code
  when a duplicate is detected").
- **What ReverseApoc would build.** In `attempt.py`, before compiling: if the view unit, with
  whitespace collapsed, equals the source of an earlier check in this attempt
  (`checks/NNNN.c`), refuse with exit 2 and use no check. Print "same C as check 0003 (objdiff
  87.5%): change the C first". Add a test first, and update the skill's exit-code text.
- **Why it would help.** In our logs, 664 of 14,586 plain checks (4.6%), in 157 attempts,
  re-ran C identical to an earlier check of the same attempt. Each one costs a container
  compile and a turn, and tells the agent nothing new.
- **Existing-feature check.** check-note.json asks what this run changes; the wrapper's hash
  ledger tracks file integrity, not repeats. Gap: no repeat refusal.
- **Effort / value.** S / low-med.

## 13. Notify the owner when a drive stops or ends

- **Sources.**
  - Lewis repo `tools/notify.sh`, called by `task-runner/decompile-unmatched/task.yaml`
    (`success_command: './tools/notify.sh "$TASK_NAME matched $CANDIDATE"'`).
  - Heumann, "Communication": "A GitHub webhook posts CI failures into the shared channel".
- **What ReverseApoc would build.** On every STOPPED or ENDED run record, the driver runs an
  optional owner command from an environment variable (for example a Windows toast through
  PowerShell, or an ntfy topic). The message holds only the run id, the reason and the session
  counts: no paths, no C and no listing. It is off by default and never fails the drive.
- **Why it would help.** Eleven drives stopped on 2026-11-14 and six on 2026-11-16 (learnings),
  each on a fail-closed audit stop that waits for the owner. A stop at 01:00 that is seen at
  08:00 loses a night of quota windows.
- **Existing-feature check.** The STOPPED record and the console line exist. The drive-budget
  skill and the meters read state when asked. Gap: no push.
- **Effort / value.** S / low-med.

---

## Considered and dropped (already covered, or not applicable)

- **Hash the checker against a secret in CI** (Heumann, "Cheating"). Covered: agents never
  commit; the wrapper ledger, the per-harness audits and SHA-1 `ninja verify` plus `gate --all`
  after each drive already guard the oracle. The protected paths are in CLAUDE.md.
- **SHA-1, make and no-verify hooks** (Lewis `.claude/hooks/block-*.sh`). Covered by the hooks,
  the wrapper-only command rules and the audit, which go further.
- **Hourly re-reading of the instructions, and earlier compaction (42% instead of 90%)**
  (Heumann, "The First Month"). Not applicable: ReverseApoc runs one fresh session per function
  (`claude -p` with /goal), so instructions cannot decay and context does not pile up.
- **A reviewer agent** (Heumann; Klonoa's adversarial subagents). Heumann himself dropped it
  once byte matching existed ("the reviewer agent is not needed anymore"); readability sessions
  and readlint cover quality.
- **A background permuter or Transmuter** (Mizuchi, Klonoa). docs/tools.md skips
  decomp-permuter on evidence (Lewis's doom loops; FNV fixed 0 of 40); `search.py` exists.
- **Echo's control-flow mutators** (branch inversion, De Morgan, while/for, §5.1). These could
  be a fifth `search.py` axis, but the FNV result and D-26 (a reordering stands only when
  exact) make the payoff doubtful. Revisit if idea 8 shows many `branch`-class near misses.
- **Separate stateless repair agents per failure level** (Constraint-Guided, §3.3). Compile
  errors are only 187 of 14,586 plain checks (1.3%), so a separate compile-repair stage would
  buy little.
- **Contamination variants** (Retrobench's non-canonical ATLAS). Apocalypse has no public
  source, so recall cannot help; that argument belongs in the paper, not the tooling.
- **Typed MCP tools over shell tools** (Wortley). The seven exact-form wrapper commands already
  play that role, with fail-closed audits across five harnesses.
- **A per-session tool-call cap and the TTFT, soft and hard timeouts** (Mizuchi). Covered by
  the 25 checks, 30 minutes, max_turns and the D-08 classifier.
- **A logistic-regression scorer retrained on outcomes** (Lewis, one-shot post, "The Scorer").
  Mostly subsumed: our difficulty curve shows size dominates, and idea 2's similarity order is
  the stronger change for the tail. It is worth one line in idea 7's report: fit
  P(match | bucket, arm) from the ledger.
