# Batch 261112-fdr: coordinator rulings and project rules

Every planner and executor of this batch reads this file before anything else. Source: the owner-approved plan of
2026-11-12 (backlog 999.12 plus the five pending todos, built before a Haiku + GPT-6.1 Terra + Gemini Flash
cascade drive that runs on the result).

## Order (coordinator ruling)
- 261112-fdt depends on 261112-fds (same files: driver.py, session.py, backends, cli). Declare exactly that.
- 261112-fdu, 261112-fdv, 261112-fdw and 261112-fdx are independent: depends_on [].
- 261112-fdv must not edit tools/reverseapoc/session.py or driver.py (fds/fdt own them). If the per-harness note in
  session.py's codex_prompt/agy_prompt needs a wording change to stay consistent, name it in the SUMMARY's concerns;
  the coordinator applies it after fdt merges.
- Only fds/fdt touch driver.py, session.py, backends.py, cli.py, contextpack.py and config/driver/backends.toml.

## Scope rulings
- fds (cascade core):
  - The size buckets are stats.py's: reuse `stats.SIZE_BUCKETS` / `stats.size_bucket` (do not define new
    thresholds). The routing table may merge 256-1023 and 1024+ into one "256 B and up" row; say how in the table.
  - Every arm named in the routing table must be an existing `[arms."..."]` entry; loading the table fails loudly
    on an unknown arm, an empty row or an unknown bucket.
  - One drive process: reuse the 07.2-16 multi-arm machinery (lanes, per-arm pause, per-harness audit, the canary
    PASS precondition per arm, one lock, one commit queue). No second process, no new audit path.
  - Every existing mode (`--night-model`, `--arm`, `--hold`, Fable trial, readability, plain Opus/Fable D-09
    nights) behaves byte-for-byte as before; prove it with the existing tests plus a test that a non-cascade
    night's model choice is unchanged.
  - `--cascade` with `--hold` is refused with a clear message (YAGNI; held comparisons keep using --arm).
  - A per-arm session cap is required for the owner's run (Haiku 30, Terra 20, Gemini Flash 1). Pick the CLI form
    in the plan.
  - `--dry-run` prints, per pick, its bucket and the arm of each attempt.
  - Default rows (owner): under 64 B claude-haiku-5-5 then gpt-6.1-terra; 64-255 B claude-haiku-5-5,
    gpt-6.1-terra, gemini-flash; 256 B and up gpt-6.1-terra first. Record each row's evidence in
    docs/model-routing.md from docs/model-comparison.md and .planning/spikes/012-model-routing/ (cite figures,
    do not invent any).
- fdt (escalation): the escalation order is the row's order; an arm that is paused or capped is skipped for that
  attempt (not the function held). When every arm of the row is paused or capped, the function waits exactly as a
  paused single-arm night does today. The earlier attempts' notes and best draft reach the next attempt through
  the existing contextpack give-up record path (07.2's 999.5), not a new channel.
- fdu (causes): the executor builds and unit-tests the fold with synthetic keys. The worktree has no build/driver
  runs; the coordinator re-runs `causes` on 20261107-030004 and 20261107-170844 on the main checkout after the
  merge and checks docs/learnings.md's 9d classes. Leave the todo move to the coordinator.
- fdv (skill): through superpowers:writing-skills, RED first (a subagent-free baseline is fine: show the current
  text fails the pressure scenario, then edit). Evidence may be read read-only from the main checkout's
  `../../../build/driver/` (spike 012 runs, canaries) and `.planning/spikes/012-model-routing/`. tests/test_skill.py
  (sections, 300-line cap, command forms, JSON fields) stays green.
- fdw (hook): keep the hook fail-closed on parse errors, keep allowing the sanctioned relative form
  `REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom` and the read-only relative reads of the main checkout this
  batch's executors rely on (`cp ../../../.planning/...`, `cat ../../../...`). Positive controls for those are
  required tests.
- fdx (slots): probe compiles in the worktree are fine (`REVERSEAPOC_WATCOM_DIR=../../../third_party/watcom`). The
  curve measurement (`.planning/converter-curve/measure_curve.py`, needs orig/ and docker) is run by the
  coordinator on the main checkout after the merge; the executor must not run it. Narrow `order_is_known` only on
  a line its probe measurements draw; otherwise end as a documented partial (update the todo text in the SUMMARY
  for the coordinator to apply).

## Project rules (CLAUDE.md, .claude/rules/tools.md, owner)
- Read `.claude/rules/tools.md` before editing Python (path rules load only after a Read of a matching file).
- Python 3.14 via uv. Test-driven: write the failing pytest first, watch it fail for the right reason, then the code.
  `uv run pytest -q` and `uv run ruff check .` must pass.
- YAGNI per .claude/rules/tools.md: build only what the item asks for. Shallow nesting; tests never embed game
  bytes; real-file tests skip without orig/.
- No change to gate, cflags handling, the build scripts or config/ hash manifests; never touch orig/. Nothing lands:
  no status.csv or src/ change.
- Never start a real `reverseapoc drive`, `claude`, `codex` or `agy` session, and no network.
- Dispatched agents never push, stay on Opus 5.5 (no fast mode), never dispatch subagents, and never install the
  unlazy Stop hook.
- NEVER type a bare `python`, `python3`, `python -` or an empty heredoc: they hang this shell forever. Always run a
  script file: `uv run python <path>`.
- build/ takes writes by shell redirection only (a hook refuses Write/Edit under build/).
- Never name the owner's private project in anything.

Nonce: echo `702d1138a9e2` in your return and in your PLAN/SUMMARY frontmatter as `bundle_nonce`.

## Amendments after plan check (coordinator, 2026-11-12)
- fds (plan-check iteration 2, binding on the executor): any cascade attempt that takes a paused arm's probe and ends
  without an `on_limit`/`on_clear` verdict (transient retry, claim failure, halt, uncounted end) must hand the probe
  back: a retry keeps the probe it already holds, and a probe slot released with no verdict resets `probe_taken`.
  Pin it with a test where the probe attempt aborts and the night still ends. Also assert in the two-arm test that the
  paused pick returns through `lane.deferred` on the pool path.
- fdx: element-type restriction is settled at the size level (owner ruling 2026-11-12); see the plan's note.
