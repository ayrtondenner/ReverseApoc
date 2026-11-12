---
spike: "012"
spike_name: "model-routing"
project: "ReverseApoc"
generated: "2026-11-11"
scope: "spike 012 and the session that ran it, 2026-11-09 to 2026-11-11"
counts:
  decisions: 12
  lessons: 10
  patterns: 9
  surprises: 11
sources:
  - ".planning/spikes/012-model-routing/README.md"
  - ".planning/spikes/MANIFEST.md (row 012)"
  - ".planning/ROADMAP.md (Phase 999.12)"
  - "config/driver/backends.toml"
  - "docs/model-routing.md"
  - "git log --since=2026-11-09 (commit messages)"
  - ".planning/debug/recovered-429-counted-as-limit.md (gitignored)"
  - ".planning/debug/codex-agy-arms-round5.md (gitignored)"
  - ".planning/debug/codex-canary-wrapper-audit.md (gitignored)"
  - "build/gate/spike012/results.txt, stats-final.txt, drive-r5-refused.err.log (gitignored)"
  - "the orchestrator's facts brief of 2026-11-11 (session scratchpad, not in the repo)"
missing_artifacts:
  - "PLAN.md and SUMMARY.md (a spike has none; the README is the record)"
---

# Spike 012 Learnings: model routing

An adapted `/gsd-extract-learnings` over spike 012 and the multi-day session that ran it: multi-arm
hold drives over Claude Code (subscription and OpenRouter), Codex CLI (ChatGPT Plus) and agy
(Google AI Plus) arms, and the tool faults found and fixed on the way. The per-arm metrics live in
[docs/model-comparison.md](../../../docs/model-comparison.md); this file holds what we decided and
learned.

Citations: a commit hash; a file path; `results.txt Lnn` for `build/gate/spike012/results.txt`
(gitignored); `stats-final Lnn` for `build/gate/spike012/stats-final.txt` (gitignored, taken before
the landing, so it shows hold exact, not matched); `facts Lnn` for the orchestrator's facts brief.

## Decisions

### DeepSeek and GLM only through OpenRouter (owner, 2026-11-10)
No direct DeepSeek or z.ai arm. `deepseek-flash` and `glm-5.3` use OpenRouter's endpoint and
`OPENROUTER_API_KEY`; the retired `DEEPSEEK_API_KEY` and `ZAI_API_KEY` are stripped from every
session. `glm-4.7-flash` joined as a small model that could get a local twin.

**Rationale:** the commits record the effect rather than a reason: one metered provider and one key
(`OPENROUTER_API_KEY`) for every open-weight arm, and one OpenRouter row in legal.md.
**Source:** 0b69431b, 4915162d, 73c757cc; backends.toml (the comment above the OpenRouter arms)

---

### Local arms are gated on their hosted twins (owner, 2026-11-10)
The hosted twin runs first through OpenRouter. If it matches about nothing on the frozen picks, the
local arm is skipped (no llama.cpp setup, no download). If it does well, the local arm runs only a
short check on the 3 to 5 picks the twin matched.

**Rationale:** local runs on the owner's machine (GTX 1660 6 GB, 32 GB RAM) are slow. Applied:
`qwen-hosted` held 0 of 20 (stats-final L42), so by this rule `qwen-local` is skipped.
**Source:** 73c757cc; docs/model-routing.md "The local arm"

---

### A hook-denied write stops its arm only, and a hold run resumes (owner, 2026-11-10)
A session whose only strays are writes the hook denied, with nothing changed after its reset, stops
its own arm on a multi-arm night; the other arms go on. Running the same `--hold --run` drive again
skips the functions each arm already finished and retries the ones cut short. Extended to agy's
exact fail-closed write denials (d5bcccc2). Hardened after a security review: a write counts as
denied only on a unique tool_use id with the same tool and target, since hosted providers issue the
ids (92794e11).

**Rationale:** the first 8-arm drive stopped every arm after 35 sessions because Muse Spark tried a
write the hook denied (to `src/tacp/u_000a6100.c`), which changed nothing.
**Source:** 8da01b25, cdfdf6b5, d5bcccc2, 92794e11

---

### Strict canaries: each arm passes its own canary on the installed CLI (owner)
No arm borrows another arm's pass, and a model that rewrites a probe must pass the probe itself
(the strict ruling on gpt-oss in round 4). A night of a Codex or agy arm is refused unless that
arm's canary file says PASS for the CLI version installed now. Muse Spark was left out after three
failed canaries in a row; GPT-OSS 120B after failing on agy 1.5.6.

**Rationale:** the canary is the only proof that a harness's guard set works for that model and
that CLI version. It held: when agy updated itself to 1.5.6 mid-day, the drive refused gpt-oss
before any session.
**Source:** .planning/debug/codex-agy-arms-round5.md (Symptoms); docs/model-routing.md "The pass
gate"; drive-r5-refused.err.log L8; results.txt L57-71, L100-102

---

### Codex runs its Windows sandbox unelevated, then through a driver-side broker (owner, 2026-11-10 and 2026-11-11)
Unelevated is the mode the owner's own Codex uses. Unelevated, the sandbox refused the wrapper's
ledger append and Docker's named pipe, so no Codex session could ever run `attempt check`. The
owner kept the sandbox as it is: inside it the wrapper only queues a request, and the driver checks
the request against the exact wrapper forms and runs the real wrapper outside the sandbox.

**Rationale:** elevated needs an admin setup the owner declined, and with it every command of the
round-2 canaries failed to start (`helper_sandbox_lock_failed`, exit -1). The broker keeps the
sandbox's write and network limits and still lets the check compile.
**Source:** 4c6795a8, b9a7d74d, 689ff384; .planning/debug/codex-agy-arms-round5.md (Evidence)

---

### An agy session may read its own agy output files (owner, 2026-11-11)
Allowed: exactly `tasks/task-<n>.log` or `steps/<n>/output.txt` under
`~/.gemini/antigravity-cli/brain/<conversation id>/.system_generated/`, for the conversation id of
the session's own init line (UUID form), absolute, with no `..` part. Any other read outside the
checkout still stops the drive.

**Rationale:** agy keeps a backgrounded command's output there and lets the model read it without
asking the settings. The audit stopped the small-picks drive on these reads (11 strays on that
session; none after the fix).
**Source:** 226fb7d5, b6524d00

---

### Smaller harness rulings, each dated in its commit
- agy 1.5.5's exact relative-path rejection counts for the relative-read probe (959ff435,
  2026-11-10).
- The CLI's "response exceeded the 32000 output token maximum" with no API status is the model's
  own failure, counted as an attempt; metered arms get `CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000`
  (11ea0a4f, 2026-11-11).
- The 8-arm resume was stopped by Ctrl+C once recovered 429s were being set aside (c1590c99).

**Rationale:** each ruling names one exact shape, so everything else stays fail-closed.
**Source:** the commits named

---

### Luna left out of the 64-255 B picks (owner, 2026-11-11)
In drive 2, Luna ran `uv run --frozen reverseapoc context`, not a wrapper form (a usage error, exit
1, nothing changed). That stray stops the whole drive by design. The owner resumed without Luna;
Sol, Terra and Astra ended clean (18 sessions).

**Rationale:** one arm's stray should not keep the other arms from their picks. Luna has 8 picks, 1
of them at 64-255 B.
**Source:** 950e8d08; results.txt L117-120; facts L72-75

---

### Quota-bound arms run small picks first (owner, 2026-11-11)
The Codex arms ran the 7 picks under 64 B, then the 7 at 64-255 B, and never the 6 at 256 B and up.
The agy Claude 4.6 arms are capped at `max_sessions = 7`, the picks under 64 B.

**Rationale:** one Gemini Flash session took 22% of its weekly agy group; a paused arm with queued
picks keeps a drive open; and no arm matched anything at 256 B and up.
**Source:** README Findings; 32092cba; backends.toml (agy Claude arms comment); results.txt
L110-120

---

### Land from the lowest API-equivalent cost and credit every holder (2026-11-10)
`--land-held` ranks the exact attempts by their tokens at the arm's list price, never by the
recorded cost (0 on a subscription). Each match commit carries a Co-Authored-By line for every arm
that held the function exact.

**Rationale:** subscription arms record no cost, so the recorded figure cannot rank them; crediting
every holder keeps the comparison honest when seven arms hold one function.
**Source:** 8aa220f8; README (the table of landed functions)

---

### The agy Claude 4.6 arms wait for the weekly reset (2026-11-11)
Both failed their first canary (an unknown `schedule` timer; refusing the `..` reads on their own).
Both causes were fixed (efdb1b99, be869480), but the two canaries had taken about 63% of agy's
"Claude and GPT models" weekly group.

**Rationale:** a re-canary and 7 sessions each would not fit what was left of the week.
**Source:** facts L36-38, L56-57; README Follow-ups

---

### Backlog 999.12: a size-routed model cascade (owner, 2026-11-11)
Route each function to the cheapest arm likely to match it by size, and escalate to a stronger arm
only on a failed attempt. A paused arm passes the attempt to the next arm in its row.

**Rationale:** `attempt check` is an exact scorer, so escalating on failure has no false positives;
spike 012's per-bucket table calibrates the routing. Built after the spike closes.
**Source:** faaf6746; .planning/ROADMAP.md Phase 999.12

---

## Lessons

### Every harness hides its own long-command, config and permission behaviour
Each CLI had behaviour that neither its docs nor our offline reading predicted; each fault showed up
only in a real canary or drive. Codex 0.167.0: `--ignore-user-config` dropped the sandbox setting (e82dcb58); the sandbox
denied the owner's uv cache (a6cfd9e9), the ledger and Docker (b9a7d74d); unified exec hands a
long command back while it runs (390885e6); `-c` keys split on dots (cc0b7bad); each command comes
wrapped in the shell's absolute path (629b104b, 09621301); a rejected command shows only on
stderr (73627b4c). agy 1.5.5 and 1.5.6: an `{"event": kind}` envelope (d8db6e05); `--print-timeout`
needs a Go duration (1a3f45f3); the `unsandboxed` rule is ignored (69a654fa); headless mode ends the
turn at the first soft-denied tool (30102605); a soft-denied step ends ERROR, not DENIED
(cea8673f); `run_command` has its own shape (f66387e3); targets come back canonicalized
(f63f5850); `manage_task`, `schedule` and the own-output reads (cc87173b, efdb1b99, 226fb7d5).
Claude Code: a 32000 output-token ceiling (11ea0a4f), and our own hook's timeout rule looked like a
denied wrapper in the canary (cb3f8d46).

**Context:** what we do differently: treat a new CLI or a new CLI version as unknown, capture a
real stream before trusting a shape, teach the audit exact shapes only, and keep every unknown
fail-closed.
**Source:** the commits named; README Findings

---

### A held match can fail the gate
Haiku's `ufo2p func_0005DB80` was exact (objdiff 100%, relocations and bytes OK), but to get there
Haiku rewrote the unit's shared struct and turned the matched `func_0005E550` back into
`INCLUDE_ASM`. `attempt check` judges the claimed function and the splice, so it passed; the gate
re-checks every matched row of the unit and refused the landing. 6 of 7 held functions landed.

**Context:** a check must also flag a matched function of its unit that is no longer C (an open
follow-up).
**Source:** README Findings; gate-0005db80-partial.txt; facts L76-77

---

### Quotas bind before money
OpenRouter used $53.10 of the owner's $100 over the whole spike. The subscription quotas ran out
first: one Gemini Flash session took 22% of a week, two agy Claude canaries took 63% of another
group, a Codex canary took about 2% of the 5-hour window and a small-pick Codex session about 0.5%
of the week.

**Context:** size an arm's picks to its quota, small picks first; measure the quota with the
owner's screenshots, since `agy -p /usage` prints nothing machine-readable.
**Source:** facts L24-40; README Findings

---

### The fail-closed audits stopped the right things
Five stops: Muse's hook-denied write (8da01b25), the Codex `error` items when the trust setting
dropped (2bb2daf1), Gemini's reads of its own output files (b6524d00), Luna's non-wrapper command
(950e8d08), and GLM-4.7-Flash's hook-denied write to `temp_check_runner.py` at the repo top (an
arm stop, facts L66-67). Each was a real unknown. In the Codex case the sessions were running
without their per-session rules.

**Context:** each stop cost sessions and a resume, and each ended in a narrow, exact allowance or
an owner ruling, never in a wider rule. Keep failing closed.
**Source:** the commits named; results.txt

---

### Test what the drive really runs, not only the canary path
Sol and Terra passed their canaries (results.txt L91-93), whose run dirs are timestamps with no dot.
The drive's run dirs are `spike012-gpt-6.1-sol` and `spike012-gpt-6.1-terra`; Codex split the
trust key on that dot and dropped it, and the audit stopped the drive. Earlier, round-2 Codex
canaries passed probes that never started (b63167d2, 7e7f14e4), and the Codex canary never checked
that the audit passes its own wrapper calls (476ad5d1).

**Context:** a canary should use the drive's run-id shapes, prove each check both ways (a probe
flagged and a real wrapper call passed), and count a probe only if it ran. The canary now also runs
the night's command audit over every other command (a6cfd9e9).
**Source:** cc0b7bad, 2bb2daf1; .planning/debug/codex-agy-arms-round5.md (the canary's run dir
`build/driver/canary/20261111-005956/`); .planning/debug/codex-canary-wrapper-audit.md

---

### Rules written for one provider misfire on another
Phase 6's D-08 made any `api_retry` `rate_limit` a usage limit. OpenRouter's short 429s, which
Claude Code retried and recovered from, set aside 11 finished sessions (7 with an exit-0 check)
and redid their picks on OpenRouter credit. A GLM-5.3 reply that ran past 32000 output tokens
matched no known signal and stopped the whole drive.

**Context:** classify on how a session ended, not on an event in its middle; pin each new
provider's transcript shapes as fixtures before its first drive.
**Source:** 3b2e42e9, 11ea0a4f; .planning/debug/recovered-429-counted-as-limit.md

---

### Know each CLI's token semantics before pricing it
Codex's `input_tokens` already includes the cached tokens. `codexjson.usage` records it as input and
records `cached_input_tokens` again as cache read, so `stats` prices Codex cached tokens twice (Astra
shows $75.51 against about $11.75). The fault is not fixed yet. The OpenRouter arms price both cache
classes as input on purpose, so their list figure ($70.53) overstates what OpenRouter charged
($53.10).

**Context:** read one real usage event per CLI against its docs before trusting `stats`; fix
`codexjson.usage` test-first, then re-run `stats`.
**Source:** facts L24-27, L86-89; README Results; backends.toml (OpenRouter comment)

---

### Probe wording decides whether a model tries the probe
gpt-oss refused a prompt that called itself a guardrail canary (30102605). Round 3's models refused
to run a command "outside the terminal sandbox" as unsafe (592e2ddb). Gemini refused a target one
directory above its workspace on scope, and gpt-oss folded the `..` spellings (cc87173b). Claude
4.6 refused the `..` reads itself, so agy's deny rule was never reached (be869480).

**Context:** one plain instruction per probe, the exact string to pass character for character,
and a line saying the tool decides whether a path is allowed.
**Source:** the commits named

---

### Some models fail the harness itself
Muse Spark sent file content as a JSON object, so `plan.json` was never written; it failed 5 of its
7 canaries. Qwen made two tool calls and then invented a table of verdicts. DeepSeek and GLM-5.3
each declined the probes once, then passed on retry.

**Context:** retry a failed canary once; leave an arm out after repeated failures rather than
loosen the canary.
**Source:** README Findings; facts L46-50; results.txt L8-71

---

### Watch the right CI workflow
A push to main can start two workflows: CI (`ci.yml`, every push) and Pages (`pages.yml`, when
`config/*/status.csv` or another progress file changes, as every match commit does). "CI green" for
a fix means `ci.yml`'s run at that fix's commit, as the 429 fix recorded ("CI green at 3b2e42e9").

**Context:** when watching a run after a push, select it by workflow name and commit, not the
newest run.
**Source:** .github/workflows/ci.yml, pages.yml; .planning/debug/recovered-429-counted-as-limit.md
(Resolution)

---

## Patterns

### A canary per arm per CLI version
Each arm runs its own canary through the clean-environment launcher; the pass file records the
arm, harness, CLI version and result, and a night refuses an arm without a PASS for the installed
version. Retry once on a failure; re-canary after any CLI update or harness fix.

**When to use:** before any arm's first drive, after any CLI update (agy updates itself), and after
each harness fix.
**Source:** docs/model-routing.md "The pass gate"; drive-r5-refused.err.log L8; results.txt

---

### Hold, then land-held
`drive --hold` records exact results without landing them, so every arm attempts the same frozen
picks; `drive --land-held 'spike012-*'` then lands each function once, from the lowest
API-equivalent cost, through the gate, crediting every holder.

**When to use:** any comparison of arms or settings over one pick list.
**Source:** 722dc288, 19708dbf, 8aa220f8; results.txt L121

---

### Per-arm pauses, caps and stops
Each arm has its own usage-limit pause, its own `max_workers` and optional `max_sessions`, and a
hook-denied write stops only its arm. One drive process serves all arms.

**When to use:** mixing subscription arms with different quota windows in one drive.
**Source:** 1a0e55c5, 829b17d5, cdfdf6b5; docs/model-routing.md "Several arms in one drive"

---

### Resumable hold runs
Re-running the same `--hold --run` command skips each arm's finished functions and retries the ones
cut short in a fresh attempt dir. Spike 012's run resumed after a guardrail stop, a Ctrl+C, a
classifier stop, the Codex `error`-item stop, the agy read stop and Luna's stray, with the arm list
changed each time.

**When to use:** any long drive that a stop or a quota can cut.
**Source:** cdfdf6b5; results.txt L49-120

---

### Commit a stopped drive's records unedited
A guardrail stop or an interrupt does not commit the attempt ledger, so a `chore(drive)` commit
adds its records as they are, naming why the drive stopped.

**When to use:** after every drive that did not end clean.
**Source:** 8da01b25, c1590c99, 2bb2daf1, b6524d00, 950e8d08

---

### One fault, one fix loop
A debug file states the symptom and the evidence; a failing test comes first; then the fix, the
host and container suites, CI, a re-canary of the affected arms, and the resume. The mutation runs
in the codex-canary-wrapper-audit session showed each new test bites.

**When to use:** every tool fault a drive turns up.
**Source:** .planning/debug/recovered-429-counted-as-limit.md (Resolution);
.planning/debug/codex-canary-wrapper-audit.md; README Findings

---

### Positive and negative controls in a canary
A canary probe must be refused, and the canary's own legitimate wrapper calls must pass the same
audit a night runs; a probe counts only if it ran.

**When to use:** any guard that a canary is meant to prove.
**Source:** 476ad5d1, b63167d2, 7e7f14e4

---

### Work outside the checkout while a drive runs
A drive holds the checkout's drive lock, git index and audit, and a second drive on it is refused.
Fixes were built on separate branches and merged between drives (7fd19073, 5acf8f0a, cd1078cf,
df2a8a73, 689ff384). The last fixes were authored during drives 1, 2 and 2b (efdb1b99 at 19:16,
be869480 at 19:34, faaf6746 at 20:10) and committed to main at 20:22, right after drive 2b ended at
20:21.

**When to use:** any tooling work during a live drive.
**Source:** `git log --format='%ad %cd'` of those commits; results.txt L115-120; docs/model-routing.md
"One process"

---

### Evidence files under build/gate/<spike>/
`results.txt` gets one line per canary and drive (arm, result, exit code, minutes or time), plus
OpenRouter usage readings before and after drives; each fix round leaves `r*-host-pytest.txt` and
`r*-container-pytest.txt`; drive logs, stats, land and gate output sit beside them. The write-up
cites them; they stay gitignored.

**When to use:** every spike or drive whose numbers a write-up will quote.
**Source:** README Evidence; build/gate/spike012/

---

## Surprises

### Under 64 B the cheapest arms match what the strongest do
Haiku 5.5 held 3 of 7, the same as Opus 5.5, at $0.78 API-equivalent for its whole run against
$17.45. The per-arm figures are in docs/model-comparison.md.

**Impact:** the cascade backlog (999.12) and the small-picks-first ruling.
**Source:** README Results; stats-final L61-69

---

### Seven arms converged on one 208 B function, and nothing at 256 B and up matched
Haiku, Sonnet, Opus, DeepSeek, Sol, Terra and Astra all held `tacp func_00022140`; every 256 B+
attempt on every arm that ran them failed.

**Impact:** 64-255 B is where arms separate, thinly; 256 B+ needs something other than a bigger
model.
**Source:** README Results

---

### One agy session can take a fifth of a week
One Gemini Flash matching session (about 11 minutes, 100 steps) took about 22% of its weekly group;
two agy Claude canaries (8 short sessions each) took about 63% of theirs.

**Impact:** Gemini ran 1 session; the agy Claude arms never ran a drive.
**Source:** facts L33-38

---

### agy updated itself mid-day
agy went from 1.5.5 to 1.5.6 during the session, and the pass gate refused gpt-oss's drive until it
re-canaried on 1.5.6 (it then failed).

**Impact:** one refused drive start and a dropped arm; the version-bound pass gate earned its place.
**Source:** drive-r5-refused.err.log L8; results.txt L98-102; facts L18-20

---

### Codex splits a `-c` key on every dot, even inside quotes
`projects."<dir>".trust_level` was ignored for run dirs holding a dot; the inline-table form works.

**Impact:** the Sol and Terra sessions ran without their per-session rules until the audit stopped
the drive.
**Source:** cc0b7bad

---

### agy's terminal sandbox does not run on Windows 10
agy logs that sandboxing on Windows needs Windows 11 24H2 or later, so `--sandbox` adds nothing on
the owner's machine; its `unsandboxed` permission rule is ignored and grants nothing.

**Impact:** the permission rules and the post-session audit are the only guards on agy arms.
**Source:** docs/model-routing.md (Antigravity arms, the canary); 69a654fa

---

### Headless agy ends the turn at its first soft-denied tool
The old ten-step agy canary only ever saw its first probe.

**Impact:** the agy canary became eight one-probe sessions.
**Source:** 30102605

---

### `whoami` looks the same inside Codex's unelevated sandbox
It lists the same groups and no restricted-token SID, so it proves nothing about the sandbox.

**Impact:** the sandbox proof became behavioural (a refused outside write, a failed fetch).
**Source:** b63167d2, 7e7f14e4

---

### OpenRouter charged less than its list prices
$53.10 real for the whole spike (canaries and discarded sessions included) against $70.53 at list
price for the metered arms.

**Impact:** list-price figures for OpenRouter arms are an upper bound.
**Source:** facts L24-27; README Results

---

### Codex reports one turn per session
In `stats`, each Codex arm shows as many turns as sessions (Astra: 7 sessions, 7 turns under 64 B),
while Claude Code arms show 15 or more turns per session.

**Impact:** turn counts do not compare across harnesses; docs/model-comparison.md holds the
per-arm figures.
**Source:** stats-final L61, L81

---

### A log watcher held results.txt open
One canary round's lines could not be written while a watcher held the file, and were restored from
the launcher's output.

**Impact:** evidence writers must not share a file with a watcher that locks it.
**Source:** results.txt L63-68
