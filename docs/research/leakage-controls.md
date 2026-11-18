<!-- Leakage-controls report of 2026-11-18 (todo leakage-controls, source: notes-ideas-llm-decomp-research.md #10). Repo sources only: no network was used. Every date below carries its file:line or commit; re-check a vendor's training cutoff at its model card before citing it in the paper. -->

# Leakage controls: a contamination ledger and a recall probe

Written 2026-11-18 at main `e93afb69`. This is the evidence behind the paper's
threats-to-validity paragraph on training-data contamination. It has three parts: what each model
could have seen (the ledger), how to test for recall (the probe, designed here and not run), and
what the paper should say. The research note behind it is
[notes-ideas-llm-decomp-research.md](notes-ideas-llm-decomp-research.md) #10 (lines 389-425).

No game bytes, disassembly or matched C appear here. Addresses, sizes and counts only.

## The question

A reviewer will ask whether a model matched a function because it reasoned from the pack or because
it had already read the answer. Three bodies of text could hold the answer:

1. **The original source of X-COM: Apocalypse.** It has never been published
   (notes-ideas-llm-decomp-research.md:409).
2. **Public reverse-engineering material** on UFO2P.EXE and TACP.EXE: OpenApoc and the
   community tools.
3. **ReverseApoc's own matched C**, public on GitHub since the first match.

## 1. Contamination ledger

### 1.1 When our matched C became public

| Event | Date | Source |
|---|---|---|
| Repository's first commit | 2026-10-15 | commit `6b2dc31b` (git log, first commit) |
| First matched C, UFO2P.EXE | 2026-10-24 00:59 -0300 | commit `f73b50e3`, `src/ufo2p/u_000a34f0.c`, the first commit touching `src/` |
| First matched C, TACP.EXE | 2026-10-24 01:29 -0300 | commit `c0e4b933`, `src/tacp/u_00054f20.c` |
| Repository stated public | by 2026-10-24 | `.planning/phases/06-reporting-and-agent-pilot/06-19-PLAN.md:65` ("(public)"), first committed 2026-10-24 in `14a92277` |

Commit dates are when the C entered the repository. The first push could be later, never earlier,
so 2026-10-24 is the earliest date any matched C of ours could have been public.

The matched C grew quickly after that. Cumulative `match` commits touching `src/` (git log of
`src/`, subjects containing `): match `). One commit can carry several functions (a batch commit
such as "match 23 Tier 1 functions"), so these are a lower bound on functions;
`config/*/status.csv` lists 234 matched rows today against 199 such commits:

| By the end of | Match commits (functions: at least this many) |
|---|---|
| 2026-10-25 | 5 |
| 2026-10-31 | 29 |
| 2026-11-03 | 76 |
| 2026-11-07 | 110 |
| 2026-11-13 | 145 |
| 2026-11-17 | 199 |

A model whose training cutoff fell before 2026-10-24 cannot have read any of it. One whose cutoff
fell on 2026-11-07 could have read the C of at least 110 functions, and somewhat more counting
the batch commits.

### 1.2 What else is public

From the kickoff research of 2026-10-19:

- **OpenApoc** is a C++ reimplementation, GPL-3.0, written to behave like the original. It is not
  derived from the original's source and holds none of its C
  (notes-blogs-and-reference-repos.md:149).
- **OpenApoc's extractors** read data tables out of both executables at fixed byte offsets
  (`ufo2p.h`, `tacp.h`, and `tools/extractors/docs/`), so they carry table layouts, not code
  (notes-target-binary-and-toolchain.md:273-276).
- **OpenApoc PRs by andremmfaria** (#1679, #1681, #1685, #1688; 2026-09-10 to 2026-09-13) cite
  Ghidra `FUN_` addresses and describe the behaviour of some functions: PR #1685 alone touches
  "~90 sites in ~25 functions" (notes-target-binary-and-toolchain.md:257-271). Those addresses are in the **CD
  build**, not the installed build ReverseApoc matches (docs/toolchain.md:36;
  docs/learnings.md:252-253). They do not line up with our addresses without re-deriving them.
- **UFOpaedia and the StrategyCore-era tools** (Apoc'd, Apatcher and others) cover file formats,
  data and behaviour, not code (notes-target-binary-and-toolchain.md:257, 278-287).
- **No public Ghidra or IDA database** for either executable was found
  (notes-target-binary-and-toolchain.md:307).
- **No other matching decompilation** of a Watcom DOS game was found in the decomp lists, and
  none of X-COM: Apocalypse (notes-blogs-and-reference-repos.md:166).

The research did not read the OpenApoc wiki or Discord (notes-target-binary-and-toolchain.md:308).
They could hold more addresses or pseudo-C. A gap to close before the paper's final draft.

### 1.3 What a session sees by design

Contamination is training exposure. It must be kept apart from what the harness shows a session on
purpose:

- Each session's view holds HEAD's `src/`, `include/` and `config/` (docs/workflow.md:73). So every
  committed matched function is **in context** for every later session. That is by design, the
  same as a human decompiler reading the repo, and needs no control.
- The driver never serves a matched row: the tier queue's items must be "not matched"
  (tools/reverseapoc/picker.py:31), and the near-miss lane's guards say "never a matched row"
  (docs/model-routing.md:1202).
- Best partial C stays under the gitignored `build/driver/<run>/.../best/`. The committed records
  "hold no C" (docs/model-routing.md:1215-1217). So partial C was never public either. A
  near-miss row's pack does carry its earlier best C from there (docs/model-routing.md:1215-1216):
  that too is in context by design, not training exposure.
- Hold runs keep arms apart: `attempt.earlier_notes` drops hold-run notes, records and best C
  (notes-ideas-llm-decomp-research.md:416; docs/model-routing.md:57).
- The canary checks an already-matched function ("the claimed function is already matched",
  docs/workflow.md:169). It is the one place a session works on public C. Its exit 0 proves the
  container path and never counts as a match.

**Consequence.** Every counted match is of a function whose matched C had never been public before
the session that wrote it, and whose earlier partial C, if any, was never public either. Memorising our repo cannot hand a model a match
it then reports. At most it can teach house style that the session already reads in its view. So
the ledger matters for any evaluation that re-runs **already matched** rows (the recall probe,
canaries, a future benchmark built from our matches). For the counts reported so far it does not.

### 1.4 The ledger per model

"First repo record" is the earliest commit or doc in this repository that names the model as in
use, listed in a catalogue or priced. A model's training cutoff precedes its release, and its
release precedes the first time anyone could use it. So a first repo record on or before
2026-10-24 proves the cutoff precedes all of our matched C. A later first record proves nothing
either way. Cutoffs: the repository states none.

| Model | Arms (harness) | Ran sessions? | Training cutoff | First repo record | Could it have read our matched C? |
|---|---|---|---|---|---|
| Claude Opus 5.5 | `claude-opus-5-5` (Claude Code) | yes | not stated (see note a) | co-author on 2026-10-19, `00602f50` | **No**: in use before 2026-10-24 |
| Claude Fable 5.1 | `claude-fable-5-1` (Claude Code) | yes (2026-11-16 A/B) | not stated | co-author on 2026-10-19, `1543145b` | **No**: in use before 2026-10-24 |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` (Claude Code), `copilot-sonnet-5-5` (Copilot) | yes | not stated | `0a60c4ef`, 2026-11-09 | Not ruled out by repo sources |
| Claude Haiku 5.5 | `claude-haiku-5-5` (Claude Code), `copilot-haiku-5-5` (Copilot) | yes | not stated | `0a60c4ef`, 2026-11-09 | Not ruled out by repo sources |
| Claude Sonnet 4.6, Opus 4.6 | `agy-sonnet-4-6`, `agy-opus-4-6` (agy) | no: never passed a canary (docs/model-comparison.md:34) | not stated | priced from a list cached 2026-10-06 (config/driver/backends.toml:213); Sonnet 4.6 cited on 2026-10-19 (2026-10-19-kickoff-research-report.md:45) | **No** |
| GPT-6 Luna | `gpt-6-luna` (Codex), `copilot-gpt-6-luna` (Copilot) | yes | not stated | `0a60c4ef`, 2026-11-09 (backends.toml:63-64, "OpenAI's help page and CLI 0.159.1's catalogue") | Not ruled out by repo sources |
| GPT-6.1 Sol | `gpt-6.1-sol` (Codex) | yes | not stated | `0a60c4ef`, 2026-11-09 | Not ruled out by repo sources |
| GPT-6.1 Terra | `gpt-6.1-terra` (Codex) | yes | not stated | `72e7278b`, 2026-11-11 (backends.toml:104-106, `codex debug models`, codex-cli 0.167.0) | Not ruled out by repo sources |
| GPT-6 Astra | `gpt-6-astra` (Codex) | yes | not stated | `72e7278b`, 2026-11-11 (backends.toml:104-106) | Not ruled out by repo sources |
| Gemini 3.8 Flash | `gemini-flash` (agy), `gemini-3.8-flash-openrouter` (OpenRouter, the D-21 fallback) | yes: 1 session in spike 012, 1 on the cascade nights (docs/model-comparison.md:109, 307) | not stated | `63594cf6`, 2026-11-09 (backends.toml:152, "`agy models` listed on 2026-11-09") | Not ruled out by repo sources |
| GPT-OSS 120B | `gpt-oss` (agy) | no: never passed a canary (docs/model-comparison.md:34) | not stated | `e66b25f6`, 2026-11-09 | Moot: no session |
| GPT-OSS 20B | `gpt-oss-20b` (OpenRouter) | no: wired, never run (docs/model-comparison.md:71) | not stated | `2e5a14db`, 2026-11-10 | Moot: no session |
| DeepSeek V4.1-Flash | `deepseek-flash` (OpenRouter) | yes | not stated | `63594cf6`, 2026-11-09 (prices from OpenRouter's list read 2026-11-10, backends.toml:311-312) | Not ruled out by repo sources |
| GLM-5.3 | `glm-5.3` (OpenRouter) | yes | not stated | `63594cf6`, 2026-11-09 | Not ruled out by repo sources |
| GLM-4.7-Flash | `glm-4.7-flash` (OpenRouter) | yes | not stated | `63594cf6`, 2026-11-09 | Not ruled out by repo sources |
| Qwen3.6-35B-A3B | `qwen-hosted` (OpenRouter); `qwen-local` never run (docs/model-comparison.md:71) | yes (hosted) | not stated | `0a60c4ef`, 2026-11-09 | Not ruled out by repo sources |
| Muse Spark Open | `muse-spark-open` (OpenRouter) | yes, 11 sessions (docs/model-comparison.md:32-33) | not stated | released 2026-10-15 (backends.toml:397; .planning/phases/07.2-fnv-inspired-matching-pipeline/07.2-RESEARCH.md:839) | **No**: released before 2026-10-24 |

First-record commits are the earlier of `git log --reverse -S<model id>` and `-S<display name>`
(for example `GLM-4.7`, `Qwen3.6`, `GPT-6 Luna`). Co-author dates come from
the `Co-Authored-By` trailers in git log.

Note a: this session's Claude Code harness states a knowledge cutoff of June 2026 for Opus 5.5.
That is not a repo source. Confirm it at Anthropic's model card before citing it.

The arms with no repo bound were all first recorded 16 to 18 days after 2026-10-24 (2026-11-09 to
2026-11-11). Exposure would need a training cutoff inside that window, followed by release within
days. That is unlikely, but the repo cannot rule it out. The paper must take each vendor's stated cutoff from
its model card.

### 1.5 Conclusion

- **The original source.** No model could have memorised it: it has never been published, and no
  public decompilation or code-level RE of either executable exists in what the research found.
  Public material is behaviour, data-table offsets and a few CD-build addresses.
- **Our matched C, for the reported counts.** Memorisation cannot explain a reported match. A
  served row is never matched, and its C appears nowhere public until the session that matches it
  (1.3). Other functions' C is in context by design.
- **Our matched C, for the models.** Opus 5.5, Fable 5.1 and Muse Spark Open provably predate all
  of it (and so do the two Claude 4.6 models, which never ran a session). For the Sonnet and Haiku
  5.5, GPT-6.x, Gemini 3.8 Flash, DeepSeek, GLM and Qwen arms the repo gives no bound. This only
  matters for evaluations on already-matched rows. The recall probe (part 2) is the test.

### 1.6 What `stats` would record

The research note asks `stats --run` to split exact rates by "picks never published before the
arm's cutoff" (notes-ideas-llm-decomp-research.md:404-407). Section 1.3 shows the split is empty
for matching runs: every pick is unpublished at launch. A field like `knowledge_cutoff` in
`config/driver/backends.toml` therefore earns its place only when a run serves matched rows, which
today only the canary and the probe do. Leave it out until then (YAGNI). Keep this ledger as the
record instead.

## 2. Recall probe design

Not run here. This section is the pre-registration: the hypotheses, sample rule, seed and
thresholds are fixed before any answer is seen. Commit it before the run, as the research note's
item 4 asks (notes-ideas-llm-decomp-research.md:412).

### 2.1 What it tests

Can a model produce a matched function's C, or its committed name, without the pack, the
disassembly or the repo? The cue is only the function's address, size and executable, or its
repository path. Exact or near-exact recall of our C means the model read ReverseApoc. Recall of
a never-attempted function's original bytes would point at the original source, which would be a
much bigger finding.

### 2.2 Hypotheses (registered 2026-11-18)

- **H1.** No arm recalls any matched function of 64 B or more (objdiff 100%, or raw token
  similarity 0.90 or more against our committed C).
- **H2.** On each arm, the matched sample and the control sample do not differ in the count of
  answers scoring objdiff 90% or more (one-sided Fisher exact, p >= 0.05).
- **H3.** No arm gives the exact committed name of more than one function whose name is not a
  `func_` placeholder. (One hit is allowed: a short descriptive name such as a `sys_` helper's can
  be guessed from the vocabulary OpenApoc and the game share.)
- **H4 (manipulation check).** On each arm, at least two of the three positive controls (2.4)
  reach raw token similarity 0.70 or more. This shows the prompt can draw out recall at all. An
  arm that fails H4 could not have failed H1-H3, so its results there are reported as
  uninformative, not as a pass (the "does not ablate" failure, Asjad §5.4,
  notes-ideas-llm-decomp-research.md:416).

Expected result: H1-H4 hold. The models predating our C (1.4) are a natural negative control. If
they "recall" as often as the later arms, the later arms' recall is chance, not memory.

### 2.3 Sample

Population, read at a pinned commit `S` (record its SHA in the run marker):

- **Matched rows.** Rows of `config/ufo2p/status.csv` and `config/tacp/status.csv` with status
  `matched`. Drop any start listed in that EXE's `runtime.csv` (library rows, matched by
  `libmatch`, not by C). Size is `end - start` from `config/<exe>/functions.csv`.
- **Controls.** Rows of `functions.csv` with kind `game` (the kinds are `game`, `runtime`,
  `data-in-code` and `thunk`) that have **no** row in `status.csv`, whose `(exe, start)` appears
  in **no** `kind: attempt` record of `progress/attempts.jsonl`, and whose address appears in
  **no** `kind: rename` record there. A missing status row alone is not enough: today 95 GAVE_UP
  attempt records name functions with no status row, and 62 APPLIED rename records gave such
  functions public names. The rows left were never attempted or renamed, so no C for them exists
  anywhere, partial or matched, not even under `build/`. They give the arm's chance rate on the
  same cue.

Strata: the `stats` size buckets merged as the cascade does (config/driver/backends.toml:484-505):
`[0, 64)`, `[64, 256)`, `[256, inf)`.

Draw, deterministic:

1. Sort each stratum by `(exe, start)`, EXE order `ufo2p`, then `tacp`.
2. `rng = random.Random(20261118)`. That is the seed, today's date, in the same form as
   `search.py`'s `SEED = 20261103` (tools/reverseapoc/search.py:51).
3. Matched: for each stratum in the order above, `rng.sample(stratum, min(10, len(stratum)))`.
4. Controls: with the same `rng`, continuing, 10 per stratum the same way.
5. Name probe. A row's committed name is its function's identifier in its unit at `S`. Take the
   matched sample's rows whose committed name is not a `func_` placeholder, in draw order, and
   keep the first 10. If fewer than 10, top up with
   `rng.sample(rest, min(10 - len(chosen), len(rest)))`, where `rest` is every other named matched
   row not already chosen, sorted by `(exe, start)`. Today about 40 of the 234 matched rows carry
   such a name.
6. Write the list (EXE, start, size, stratum, set) next to the run marker before the first prompt.

At `e93afb69` the matched population is 234 rows: 132 under 64 B, 91 at 64-255 B, 11 at 256 B
and up (status.csv joined to functions.csv). So the sample is 30 matched rows, ten per stratum,
and the top stratum is nearly the whole bucket. `drive --stratify` does not fit: it takes the
first unattempted rows of the tier queue (tools/reverseapoc/cli.py:2136-2138), never matched ones.
Running the probe needs a small sampler. Write it then, with its test, under the YAGNI rule.

### 2.4 Prompts

Every prompt is one turn: no tools, no files, no repo, no pack, no earlier answer. Temperature at
the harness default, recorded. Output cap 4,000 tokens. Nothing sent is secret: addresses, sizes,
paths and committed names are all public in the repo, and no disassembly is sent.

**Template W (weak cue).** Used for matched rows and controls.

```
X-COM: Apocalypse (MicroProse/Mythos, 1997, DOS), executable {EXE} as shipped in the
Steam/GOG installed build, compiled with Watcom C 10.6 (-4r -s -fpi), DOS/4GW LE.
The function at linear address 0x{START:08X} is {SIZE} bytes long.
From memory only, write the C89 source of this function as it was originally written.
If you do not know it, answer exactly UNKNOWN. Otherwise output one C89 translation unit:
the declarations the function needs, then the function. Nothing else.
```

**Template S (strong cue).** Used for matched rows only.

```
The GitHub repository ayrtondenner/ReverseApoc is a matching decompilation of
X-COM: Apocalypse. Its file src/{exe}/{unit}.c contains the function {NAME}
(address 0x{START:08X} in {EXE}, {SIZE} bytes).
From memory only, reproduce that function exactly as it appears in the repository.
If you do not know it, answer exactly UNKNOWN. Otherwise output one C89 translation unit:
the declarations the function needs, then the function. Nothing else.
```

**Template N (name).** Used for the name-probe rows.

```
In the GitHub repository ayrtondenner/ReverseApoc (a matching decompilation of
X-COM: Apocalypse), src/{exe}/{unit}.c defines a function at address 0x{START:08X} in {EXE}.
In the executable, the function just before it is named {PREV_NAME} and the one just after it
is named {NEXT_NAME}.
From memory only, what is this function's name? Answer with the identifier only, or UNKNOWN.
```

The neighbours are the previous and next kind-`game` rows of `functions.csv` by address, whatever
their unit, so they exist even for a unit holding one function. Their names are their committed
names at `S`. A `func_` placeholder is given as it is: it carries no meaning. At the first or last
game function of an EXE the missing neighbour is given as `none`.

**Positive controls (H4).** Three functions from a widely mirrored public C codebase that
predates every arm's cutoff, asked for with Template S's wording (repository, path and name). The
coordinator picks the three before the run and records them with the sample. Not from ReverseApoc,
and not from Open Watcom's library (the sample already drops the runtime rows).

Prompts per arm: 30 (W, matched) + 30 (W, controls) + 30 (S) + up to 10 (N) + 3 (positive) = up
to 103.

### 2.5 Scoring

For each C answer:

- **Parse.** The scored function is the answer's last function definition (declarations come
  first). `UNKNOWN`, or no definition, is an abstention: score 0, counted on its own line. The
  abstention rate is itself a result.
- **objdiff %.** Matched rows and controls are compiled the same way, so the comparison in H2
  builds in no difference between them: each answer is compiled as its own translation unit,
  holding only the answer's text, with the rule `config/cflags.txt` gives that function's unit.
  It is scored against the original function the way `attempt check` does, relocations masked. A
  build failure scores 0 and is counted. The coordinator runs this; the model never sees the
  result.
- **Token similarity** (matched rows and positive controls only). Tokenize the answer and our
  committed function with `readlint.tokenize` (tools/reverseapoc/readlint.py:315), dropping comments
  and directives. Then:
  - **T_raw:** `difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()` over token texts;
  - **T_alpha:** the same after renaming identifiers in each function to `v1, v2, ...` in order of
    first appearance (one bijection per function). C keywords stay, and so do `func_` and `D_`
    placeholders, which the address alone gives away.

  Renaming can only make two functions more alike, so T_alpha is at least about T_raw. A high
  T_alpha with a much lower T_raw means the model got the structure but not our names. A high
  T_raw, close to T_alpha, means it also knew our local and parameter names. Those names exist
  only in our repo, so that is the strongest sign of having read it.
- **Name answers.** A hit is an exact, case-sensitive match of the committed name.

Thresholds, per answer:

| Verdict | Rule |
|---|---|
| recalled | objdiff 100%, or T_raw >= 0.90 |
| near | objdiff >= 90%, or T_alpha >= 0.70 |
| none | anything else |

Per arm, contamination is flagged if any one of these holds:

- (a) one or more recalled answers at 64 B and up (H1). An exact answer under 64 B does not flag on
  its own: a 10-byte setter can be guessed. It counts through (b).
- (b) Template W's matched sample has at least three more answers at objdiff 90% or more than the
  controls, with one-sided Fisher exact p < 0.05 (H2).
- (c) two or more exact name hits (H3).

With 30 against 30, the probe detects gross memorisation, not a few percent. Say so in the paper.

### 2.6 Cost per arm

Assumptions: about 103 prompts, about 500 input tokens each (template and cue) and about 1,500
output tokens on average (code plus any reasoning, capped at 4,000). So about 50k input and 150k
output tokens per arm, about 0.2M in all. In tokens that is a fifth of one average matching
session (a Haiku session is about 1.07M cache read, 80k cache creation and 24k output,
docs/model-routing.md:1123). In dollars it is not. A session is mostly cheap cache reads, while
the probe is mostly output, so a Haiku probe costs about twice a Haiku session's list price. Dollars are list price, from `config/driver/backends.toml` `prices` and, for
the Claude Code arms, `streamjson.py`'s table (tools/reverseapoc/streamjson.py:102-105).

| Arm | Input / output USD per MTok | List cost of one probe |
|---|---|---|
| Claude Opus 5.5 | 4.00 / 20.00 | $3.20 |
| Claude Fable 5.1 | 10.00 / 50.00 | $8.00 |
| Claude Sonnet 5.5 (Claude Code; Copilot 2.00 / 10.00) | 2.00 / 10.00 | $1.60 |
| Claude Haiku 5.5 (Claude Code; Copilot the same) | 0.10 / 0.50 | $0.08 (about 8 Copilot credits) |
| GPT-6 Luna (Codex; Copilot the same) | 0.10 / 0.50 | $0.08 |
| GPT-6.1 Sol | 2.00 / 10.00 | $1.60 |
| GPT-6.1 Terra | 1.00 / 5.00 | $0.80 |
| GPT-6 Astra | 10.00 / 50.00 | $8.00 |
| Gemini 3.8 Flash | 0.75 / 3.75 | $0.60 |
| DeepSeek V4.1-Flash | 0.30 / 1.20 | $0.20 |
| GLM-5.3 | 0.07 / 1.40 | $0.21 |
| GLM-4.7-Flash | 0.061 / 0.40 | $0.06 |
| Qwen3.6-35B-A3B (hosted) | 0.10 / 0.90 | $0.14 |
| Muse Spark Open | 1.25 / 4.25 | $0.70 |
| GPT-OSS 120B (agy) | 0.04 / 0.18 | $0.03 |

The 15 arms cost about $25 at list price. On the subscription arms the cost is quota. Scaling the
per-session readings (docs/model-routing.md:1121-1130) by 0.2M tokens: Terra about 0.03% of the
Codex week, Haiku a negligible share of the Claude week, and Gemini 3.8 Flash about 1% of the agy
week. These are rough: those readings were taken on input-heavy sessions, and the probe is
output-heavy.

### 2.7 Constraints on running it

- Codex, agy and Copilot may run only `reverseapoc drive` sessions (CLAUDE.md, "Hard rules"). So
  the probe on those arms needs a drive session kind (for example `--session recall`) with a tool
  set of none, launched and audited like any other. The OpenRouter and Claude Code arms run
  through the same harness, so build it once for all.
- Run it in a hold run, so no answer reaches `earlier_notes` or a later session.
- Score after all arms have answered, and publish the scores beside this pre-registration.

## 3. What the paper should say

### 3.1 Draft threats paragraph

> **Training-data contamination.** X-COM: Apocalypse's source code has never been published, and
> we found no public decompilation or code-level reverse engineering of either executable. The
> public material is OpenApoc, a C++ reimplementation; its extractors' data-table offsets; and
> Ghidra addresses and behaviour notes for some functions of a different (CD) build. No model
> could have memorised the original C. Our own matched C has been public on GitHub since
> 2026-10-24, but it cannot inflate our match counts. The driver never serves a matched function
> and never publishes an unmatched attempt's best C, so no function's C was public before the
> session that matched it. Earlier matches, and a near-miss row's earlier best C, do reach later
> sessions, in context and by design, as they would reach a human working from the repository. Two of the models, Claude Opus 5.5 and Fable 5.1, were in
> use on the project before the first match, and a third, Muse Spark Open, was released before
> it, so their training data cannot contain any of our C. For the other models we do not have a
> bound from first-hand evidence. A pre-registered recall probe asks each model for 30 matched
> functions from address-only and repository-path cues, against 30 never-attempted controls and
> three public positive controls, and scores the answers by objdiff and token overlap with our
> committed C ([result]). This control covers evaluations on already-matched functions. It does
> not bear on the match counts, which no form of memorisation can reach.

Replace "[result]" with the probe's outcome, and the vendor cutoffs with model-card citations,
before submission.

### 3.2 The ledger as a compact table

| Model | Sessions run | Earliest evidence of availability | Predates our first matched C (2026-10-24)? |
|---|---|---|---|
| Claude Opus 5.5 | yes | in use 2026-10-19 | yes |
| Claude Fable 5.1 | yes | in use 2026-10-19 | yes |
| Muse Spark Open | 11 | released 2026-10-15 | yes |
| Claude Sonnet 4.6, Opus 4.6 (agy) | none | priced 2026-10-06 | yes |
| Claude Sonnet 5.5, Haiku 5.5 | yes | 2026-11-09 | unknown |
| GPT-6 Luna, GPT-6.1 Sol | yes | 2026-11-09 | unknown |
| GPT-6.1 Terra, GPT-6 Astra | yes | 2026-11-11 | unknown |
| Gemini 3.8 Flash | 2 | 2026-11-09 | unknown |
| DeepSeek V4.1-Flash, GLM-5.3, GLM-4.7-Flash, Qwen3.6-35B-A3B | yes | 2026-11-09 | unknown |
| GPT-OSS 120B, GPT-OSS 20B | none | 2026-11-09, 2026-11-10 | moot |

Training cutoffs: none stated in project sources. Fill them in from the vendors' model cards.

## Also in the todo, not designed here

- **Naming-floor ablation** (notes-ideas-llm-decomp-research.md:411). Rerun one readability unit
  with callee and global placeholders alpha-renamed and strings scrambled. Names that survive came
  from the model's prior, not the cited evidence. It needs its own seeded unit sample and a
  manipulation check like H4. File it as its own unit of work; it is a readability control, not a
  matching one.
- **Pre-registration of held comparisons** (notes-ideas-llm-decomp-research.md:412).
  `--write-picks` already freezes the pick list. The run marker still needs a hypothesis line.
  Section 2.2 is the probe's.
