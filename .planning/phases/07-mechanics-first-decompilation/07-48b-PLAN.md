---
phase: 07-mechanics-first-decompilation
plan: "48b"
type: execute
wave: 14
depends_on: ["07-48"]
files_modified: [tools/reverseapoc/relocs.py, tools/reverseapoc/check.py, tests/test_relocs.py, tests/test_check.py, tests/test_land.py, tests/test_filler_real.py, tests/fixtures/filler/tacp/f_0001e860.c, docs/matching.md, .planning/phases/07-mechanics-first-decompilation/07-48b-SUMMARY.md, build/gate/07-evidence/]
autonomous: false
gap_closure: true
requirements: [DEC-02, DEC-03]
user_setup: []

estimate:
  tokens: 110000
  raw_tokens: 110000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "The span of a leading jump table, [table row start, head.start), passes its length rule when ours is short of it only by original alignment filler before the head. 07-48's tail rule applies to [table start + our first-public offset, head.start) with conditions 1, 2, 3 and 5: 0 < gap shortfall <= 15; head.start % 16 == 0; no LE fixup field in the gap; the original gap decodes exactly to head.start and is all `x86.is_alignment_filler`. Condition 4 (ours ends in a terminal instruction) does not apply, because a table is data"
    - "Only `check._head_reloc`'s check of the table span passes `table=True` to `relocs.check_function`. Every function check keeps all five conditions: a data-only span checked without `table=True` is refused for its missing terminal instruction"
    - "The negatives fail for their own reasons: a gap that is not filler, a head start off 16-byte alignment, a gap of 16 bytes, and an LE fixup in the gap. Each asserts its reason text, so each was RED on 07-48's HEAD"
    - "The table is never landed: land splices the head's row only, so the table and its gap keep the original bytes. The synthetic land of a gap-less leading-table unit gives an image equal to the original"
    - "tacp func_0001E860 (row [0x0001E860, 0x0001E900), unit u_0001df90, a 32-byte leading jump table and 8 bytes of filler before the function) was re-judged under its committed rule and under `-4r -oneatx -s -fpi`, from both spike 011 agent files. The outcome is recorded: committed exact joins Task 2a; exact only under `-oneatx` joins Task 2b's list (a D-12 proposal through 07-48c); neither is held, with its first difference. Under the `-oneatx` cell the real table span has no problem"
    - "Done gate as in 07-48: the host suite and ruff, then the container suite (R-A skips only), then the container gate --all with both SHA-1s OK, diffed against this plan's pre-change run, then `/code-review`; docs/matching.md's jump-table rule says what the gap rule accepts"
  prohibitions:
    - statement: "MUST NOT skip condition 4 for anything but the table span of `_head_reloc`, and MUST NOT accept a gap outside conditions 1, 2, 3 and 5 (owner ruling: option A, nothing broader)"
      status: resolved
      verification: test
    - statement: "MUST NOT edit orig/, the config/ hash manifests, config/cflags.txt, config/cflags-proposals.toml, configure.py, the build scripts, any src/ file, status.csv or decomphub.progress.json"
      status: resolved
      verification: test
    - statement: "MUST NOT run `flags approve`, `reverseapoc drive` or `claude -p`, MUST NOT push, and MUST NOT dispatch subagents (R-D)"
      status: resolved
      verification: judgment
    - statement: "MUST NOT put game bytes or disassembly in a tracked file, a test or the evidence: synthetic encodings in tests, our own C as the only real fixture, and evidence holding VAs, counts, booleans and mnemonic shapes only"
      status: resolved
      verification: test
  artifacts:
    - path: tools/reverseapoc/relocs.py
      provides: "check_function(table=...) and _trailing_filler skipping condition 4 for a table span"
      contains: "table: bool = False"
    - path: tools/reverseapoc/check.py
      provides: "_head_reloc checks the span with table=True; _reloc passes the flag"
      contains: "table=True"
    - path: tests/test_check.py
      provides: "the gap-less leading-table pair, its negatives and the spy that only the span is a table"
      contains: "test_table_gap_accepts_original_filler_before_the_head"
    - path: tests/test_filler_real.py
      provides: "real-file judge of tacp func_0001E860 under both cells"
      contains: "f_0001e860"
    - path: tests/fixtures/filler/tacp/f_0001e860.c
      provides: "our C for tacp func_0001E860, byte-identical to the spike 011 agent file"
      contains: "func_0001E860"
    - path: docs/matching.md
      provides: "the jump-table rule with the 07-48b gap clause"
      contains: "07-48b"
  key_links:
    - from: tools/reverseapoc/check.py
      to: tools/reverseapoc/relocs.py
      via: "_head_reloc's span check calls check_function(..., table=True); every other caller keeps the default"
      pattern: "table=True"
    - from: tools/reverseapoc/relocs.py
      to: tools/reverseapoc/x86.py
      via: "the gap rule decodes the original gap with x86.decode and requires is_alignment_filler (07-48)"
      pattern: "is_alignment_filler"
---

<objective>
This is a gap closure, small, after 07-48. The design's "Plan 07-48b" section applies 07-48's tail rule to the filler
between a leading jump table and its function.

wcc386 10.6 puts a switch's jump table at `_TEXT+0`, before the function's public. `check` pairs that table with the
unit's data-in-code row right before the function's row (`leading_table`, DI-02). It then checks the span [table row
start, head.start) like a function: equal length, equal bytes, and each entry landing on the original's case label
(`_head_reloc`).

Spike 011's tacp func_0001E860 failed only there. Its original has a 32-byte table, then 8 bytes of filler, then the
function aligned to 16. Our object has the table and the function with no filler between them. The agent's code was
right in every instruction (score 98.08), and the span's length rule refused it.

The rule, as the design states it:
- conditions 1, 2, 3 and 5 of 07-48 apply to [table start + our first-public offset, head.start);
- condition 4 does not apply, because a table is data and has no terminal instruction;
- the table is never landed, so its filler stays original.

Decisions taken here, with their reasons:
- **The flag is explicit.** `relocs.check_function` gains the keyword `table: bool = False`, and only
  `check._head_reloc` passes `table=True`, for the span. The row's kind (data-in-code) is not used as the switch,
  because an explicit argument cannot be reached by accident through another caller. A spy test pins that function
  checks never get it.
- **The negatives are RED on 07-48's HEAD because they assert the reason text.** On that HEAD the span still refuses
  any gap shortfall: `_trailing_filler` applies condition 4, and a table has no terminal instruction. So a negative
  that only checked "refused" would pass and prove nothing.
- **The re-judge decides which follow-on 0x0001E860 joins.** The design says "If it is exact, it joins the Task 2a
  batch". Task 2a lands rows under their committed rule, and the agent wrote this C for the inferred `-oneatx` cell.
  So the plan judges both cells and both agent files, and names the follow-on from the result.

Sequencing:
- 07-48b runs on the MAIN checkout on branch `gsd/07-48-filler-rule`, after 07-48's commits, and never in a worktree.
  The orchestrator fast-forwards main, pushes and watches CI; the executor never pushes.
- The auto-memory `gsd-main-checkout-plans` recipe applies (`[gsd:dispatch phase="07" plan="07-48b"]`).
- R-A, R-C and R-D apply. Evidence goes under build/gate/07-evidence/ by shell redirection only.
- The host suite and the container suite never run at the same time.

Output: the table-span gap rule and its tests, the real-file fixture and test of tacp func_0001E860, the re-judge
record, the docs, and the SUMMARY.
</objective>

<execution_context>
@C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/.claude/gsd-core/workflows/execute-plan.md
@C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/phases/07-mechanics-first-decompilation/07-48-PLAN.md
@.planning/phases/07-mechanics-first-decompilation/07-48-SUMMARY.md
@.planning/spikes/011-flags-from-filler/README.md
@C:/Users/Ayrton/.claude/plans/pasted-content-id-769c-kickoff-gate-curious-gosling.md
@.superpowers/sdd/let-s-execute-gsd-execute-phase-7-sorted-harp/rulings.md

<interfaces>
As built after 07-48 (its SUMMARY names the final commits). The line numbers below are from feac4c9 and move with
07-48's edits, so find each by name.

**relocs.py (after 07-48)**
- `_trailing_filler(pair) -> int | str`: conditions 1-5 in order, and the REASON_* constants.
- `_length`, `check_function(segment, *, off, size, row, flat, fixups, symbols, own_publics=())`, and
  `_verdict(..., filler)`. `RelocResult.filler`.

**check.py**
- `LeadingTable` (span: the data-in-code row with its end moved to head.start; head; size: our first public's
  offset), `LeadingTable.public`.
- `leading_table` (~L385-410). `own_publics` (~L413).
- `_reloc(d, exe, publics)` (~L435-444): the one caller of check_function for Defined rows. `_with_table` (~L447).
- `_head_reloc(d, exe, seg_map, table)` (~L471-481): the head's own check with the table's entry added, failed too by
  `_reloc(span, exe, head)`, where `span = Defined(table.span, table.span.name, d.segment, 0, table.size)`.
- `with_relocs` (~L484-509) and `checked_functions` (~L512).

**tests/test_check.py, the leading-table fixtures (~L1337-1535)**
- TABLE_VA = CODE_BASE + 0x100; TABLE_ENTRIES 3; TABLE_SIZE 12; TABLE_FILLER (4 bytes: `mov eax, eax` twice, the same
  on both sides today).
- SWITCH_OFF = 16, so SWITCH_VA = CODE_BASE + 0x110, which is 16-aligned. SWITCH_BODY; JUMP_FIELD 9; CASES.
- TABLE_ROW (data-in-code) and SWITCH_ROW.
- Builders: `table_module(prefix, publics)` (our unit: the table, the filler, the function), `table_original(cases,
  prefix)`, `table_check(module_, orig, rows)` (a SimpleNamespace ExeInputs; returns {name: RelocResult}), and
  `_table_original_with(filler, *, extra_entry)` (~L1492).
- Tests: test_leading_table_pairs_with_its_data_row, test_leading_table_with_a_wrong_entry_fails,
  test_mid_unit_table_still_fails_closed, test_leading_table_used_by_another_function_is_refused,
  test_leading_table_entry_outside_the_head_fails, test_leading_table_span_compares_filler_and_length (equal lengths,
  so it stays green), test_no_leading_table_without_its_data_row.

**batch.py**
- `table_row(exe, row)`: the data-in-code row right before `row` in its unit.
- `judge`, which passes rows [table_row, row].
- `cells_for(base, cell_texts)`, `write_cell_jobs` (it appends the pad function under `-ot`/`-oneatx` when the row
  ends in filler), `compile_batch`, `committed_rule`, `load_exe_inputs`.

**The real row.** tacp func_0001E860, row [0x0001E860, 0x0001E900) (160 bytes), unit u_0001df90 [0x0001DF90,
0x0001EB30). It has a 32-byte leading table row right before it, with 8 bytes of filler between that row's end and
0x0001E860. There is no committed src/tacp/u_0001df90.c. The agent C (ours, gitignored) is
build/spike-011/agents/b064/f_0001e860.c (43 lines), with the variant f_0001e860_with_neighbour.c (74 lines), which
also defines the next function.

**Verbs:** `uv run reverseapoc judge EXE ADDR FILE [--cell FLAGS ...]` exits 0 when some cell is exact, 1 when none is,
and 2 for a tool error. It prints one line per cell: `exact=`, score, `len ours/row`, and the first differing
instruction as mnemonic shapes.

The container commands, the R-A regex and the host-suite background rule are as in 07-48's interfaces.
</interfaces>
</context>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: Tracer - a gap-less leading table passes before a 16-aligned head when the original gap is filler, negatives first</name>
  <reversibility rating="costly">it widens what the match gate accepts for a table span; conditions 1, 2, 3 and 5, the negatives and the whole-EXE SHA-1 bound it</reversibility>
  <precondition>All of these hold:
- Main checkout (git-dir equals git-common-dir). `git status --porcelain` is empty except ` M .planning/config.json`.
- The current branch is `gsd/07-48-filler-rule` and holds 07-48's SUMMARY commit: `git log --format=%s | grep -q '^docs(07-48): complete'`, with `git log` captured first, as in 07-48's acceptance criteria.
- `uv run python -c "from reverseapoc import relocs; assert hasattr(relocs, '_trailing_filler')"` exits 0.
- The drive lock prints True (the design's preflight one-liner, as in 07-48 Task 1).
- `uv run reverseapoc check-orig` exits 0, and `docker image inspect reverseapoc-build:local` exits 0.
- No host suite, no container command and no `reverseapoc drive` is running.</precondition>
  <files>tools/reverseapoc/relocs.py, tools/reverseapoc/check.py, tests/test_relocs.py, tests/test_check.py, tests/test_land.py</files>
  <read_first>
    - tools/reverseapoc/relocs.py (`_trailing_filler`, `_length`, `check_function`, the docstring's rules)
    - tools/reverseapoc/check.py (LeadingTable, leading_table, _reloc, _with_table, _head_reloc, with_relocs)
    - tests/test_check.py (L1330-1540: the leading-table fixtures and tests)
    - tests/test_land.py (how a synthetic LE is landed and compared with its original)
    - build/gate/07-evidence/48-notes.txt (07-48's reason strings and mutant list)
  </read_first>
  <behavior>
    Negatives first. Each asserts the reason text, so on 07-48's HEAD (where the span still needs a terminal instruction) it fails for the wrong reason:
    - test_table_gap_refuses_a_gap_that_is_not_filler: ours has no filler between the table and the switch, and the original gap is four int3 -> the head fails with a problem at TABLE_VA + TABLE_SIZE holding `is not alignment filler`
    - test_table_gap_refuses_an_unaligned_head: the layout shifted so that the head starts 4 bytes off 16 -> `16-byte boundary`
    - test_table_gap_refuses_a_gap_of_16: 16 filler bytes in the original gap, the head aligned, ours with none -> `more than 15 bytes`
    - test_table_gap_refuses_an_le_fixup_in_the_gap: the original with a 4th LE table entry where ours has nothing (`_table_original_with(bytes(4), extra_entry=True)` against the gap-less module) -> `LE fixup field lies in the original's tail`
    - test_check_function_without_table_keeps_condition_4 (tests/test_relocs.py): a data-only "public" (made-up non-code bytes) short of an aligned row by filler. `check_function(...)` with the default is refused with `terminal instruction`; the same call with `table=True` is ok with `filler` equal to the gap
    - test_only_the_table_span_is_checked_as_a_table: a spy around `relocs.check_function` (monkeypatched where check.py calls it), over test_table_gap_accepts_original_filler_before_the_head's pair and over the not-head unit (NOT_HEAD_ROWS) -> `table=True` only for calls whose row is the span; every function's call has `table` False
    Positives:
    - test_table_gap_accepts_original_filler_before_the_head (TARGET, the tracer): `table_module` with an empty gap (a new `filler=` keyword, default TABLE_FILLER, so the existing tests are unchanged) against `table_original()` (the original keeps the 4-byte gap before SWITCH_VA, which is 16-aligned) -> verdicts[SWITCH_ROW.name].ok, with its own `filler` 0 (the head itself is full length)
    - test_table_gap_lands_the_head_only: land that head's LandedFunction into the synthetic LE -> LandResult.ok, first_difference None; the table and gap bytes are untouched
    - test_leading_table_span_compares_filler_and_length and the other leading-table tests pass unchanged
  </behavior>
  <action>
**Baseline first, before any edit** (build/gate/07-evidence/, by shell redirection):
- `git rev-parse HEAD > 48b-head-before.txt`;
- `uv run reverseapoc mechanics status --tier 1 > 48b-tier1-before.txt`;
- `docker compose run --rm build bash -lc "uv sync --locked && uv run reverseapoc gate --all" >
  build/gate/07-evidence/48b-gate-all-before.log 2>&1; echo "exit=$?" >>
  build/gate/07-evidence/48b-gate-all-before.log`.

It must end `exit=0` with config/ and the feed unchanged; otherwise STOP. Then start 48b-notes.txt.

**RED.**
1. Write the tests of `<behavior>` in tests/test_check.py, tests/test_relocs.py and tests/test_land.py, negatives
   first.
   - `table_module` gains `filler: bytes = TABLE_FILLER`, and an empty value lays the switch right after the table.
   - The made-up layouts for the unaligned head and the 16-byte gap are separate builders beside
     `_table_original_with`, each instruction named in a comment.
   - New names are reached as attributes inside test bodies, so 07-48's HEAD still collects.
2. Run `uv run pytest -q tests/test_check.py tests/test_relocs.py tests/test_land.py
   --junitxml=build/gate/07-evidence/48b-red.xml -p no:cacheprovider`.
3. Record 48b-red-record.json as .claude/gsd-core/references/tdd.md describes, target
   `tests/test_check.py::test_table_gap_accepts_original_filler_before_the_head`. `gsd_run check tdd-red-evidence
   build/gate/07-evidence/48b-red-record.json --raw` must print RED_EVIDENCE_OK.
4. In 48b-notes.txt, note how each negative failed (07-48's terminal-instruction reason, not its own).
5. Commit `test(07-48b): failing tests for filler between a leading table and its head`.

**GREEN, tools/reverseapoc/relocs.py.**
- `check_function` gains the keyword `table: bool = False`, passed to `_trailing_filler(pair, *, table)`, which skips
  condition 4 when `table` is set. Conditions 1, 2, 3 and 5 and their order are unchanged.
- The docstrings say:
  - `table=True` is for the span of a leading jump table only (check.py `_head_reloc`, 07-48b);
  - a table is data, so it has no terminal instruction;
  - the table is never landed.

**GREEN, tools/reverseapoc/check.py.**
- `_reloc(d, exe, publics, *, table: bool = False)` passes the flag to check_function.
- `_head_reloc` calls `_reloc(span, exe, head, table=True)`. No other call changes.
- Docstrings of LeadingTable, leading_table and with_relocs: the span is checked like a function, except that ours
  may lack original alignment filler before a 16-aligned head, under 07-48's conditions 1, 2, 3 and 5.

Run the three test files green and ruff, then commit `feat(07-48b): accept original filler between a leading table
and its head`.

**Mutant proof** (on the committed tree, restored with `git checkout -- tools/` after each):
- `_head_reloc` passes `table=False`: the TARGET fails;
- `_trailing_filler` skips condition 4 always: test_check_function_without_table_keeps_condition_4 fails;
- `_reloc` defaults `table` to True: test_only_the_table_span_is_checked_as_a_table fails.

Record each in 48b-mutants.txt with `failed: yes`, and finish with `git diff --quiet -- tools/`.
  </action>
  <verify>
    <automated>uv run pytest -q tests/test_check.py tests/test_relocs.py tests/test_land.py tests/test_batch.py && uv run ruff check . && test "$(grep -c 'table=True' tools/reverseapoc/check.py)" -eq 1 && test "$(grep -c 'table: bool = False' tools/reverseapoc/relocs.py)" -ge 1 && grep -qx "exit=0" build/gate/07-evidence/48b-gate-all-before.log && test "$(grep -c 'failed: yes' build/gate/07-evidence/48b-mutants.txt)" -ge 3 && git diff --quiet "$(cat build/gate/07-evidence/48b-head-before.txt)" HEAD -- config/ src/ decomphub.progress.json tools/reverseapoc/land.py tools/reverseapoc/x86.py && git diff --quiet -- tools/</automated>
    <fails_when>Non-zero exit in any of these cases: a check, relocs, land or batch test fails; ruff fails; check.py has no `table=True` call, or more than one (0 on 07-48's HEAD); relocs has no `table` keyword; the pre-change gate log did not exit 0; fewer than 3 mutants were shown failing; config/, src/, the feed, land.py or x86.py changed; or a mutant edit was left in tools/</fails_when>
  </verify>
  <acceptance_criteria>
    - RED_EVIDENCE_OK for build/gate/07-evidence/48b-red-record.json, and 48b-notes.txt names each negative's RED failure
    - `L=$(git log --reverse --format=%s "$(cat build/gate/07-evidence/48b-head-before.txt)"..HEAD) && printf '%s\n' "$L" | head -1 | grep -q '^test(07-48b)'` exits 0
    - `grep -n "table=True" tools/reverseapoc/check.py` shows the one line inside `_head_reloc`
  </acceptance_criteria>
  <done>A unit whose leading table is followed by less filler in ours than in the original passes, when that gap is the original's alignment filler before a 16-aligned head; every other gap is refused with its reason.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Re-judge tacp func_0001E860 under both cells, the real fixture and test, and the matching.md rule</name>
  <precondition>Task 1 is committed; `test -s build/spike-011/agents/b064/f_0001e860.c && test -s build/spike-011/agents/b064/f_0001e860_with_neighbour.c` exits 0 (else STOP: the C is never re-derived); no host suite or container command is running</precondition>
  <files>tests/fixtures/filler/tacp/f_0001e860.c, tests/test_filler_real.py, docs/matching.md</files>
  <read_first>
    - build/gate/07-evidence/48b-notes.txt
    - tests/test_filler_real.py (07-48's tests and skip pattern)
    - tools/reverseapoc/batch.py (table_row, judge, cells_for, write_cell_jobs, compile_batch)
    - docs/matching.md (L84-90: the confirmed rules for jump tables and statics)
  </read_first>
  <behavior>
    - test_real_leading_table_gap_tacp_0001e860 (host and container; skips through `orig/<EXE> not present ...`, requires_capstone, requires_runner and requires_version):
      - compile the fixture under each cell of `batch.cells_for(committed rule, ["-4r -oneatx -s -fpi"])` with `batch.write_cell_jobs` (the pad comes from it) and compile_batch, into build/test-filler/table/;
      - for the `-4r -oneatx -s -fpi` object: with_relocs over the rows [batch.table_row(exe, row), row] gives a head verdict with no problem whose VA lies in [table row start, 0x0001E860);
      - for each cell that 48b-rejudge.txt found exact: `batch.judge(...).exact` is True. The test holds those cells as the constant EXACT_CELLS_0001E860, with a comment citing the re-judge.
  </behavior>
  <action>
1. **Re-judge, both agent files and both cells:**
   - `uv run reverseapoc judge tacp 0x0001E860 build/spike-011/agents/b064/f_0001e860.c --cell "-4r -oneatx -s -fpi"
     > build/gate/07-evidence/48b-rejudge.txt 2>&1; echo "exit=$?" >> build/gate/07-evidence/48b-rejudge.txt`;
   - the same for f_0001e860_with_neighbour.c into 48b-rejudge-neighbour.txt.

   Exit 0 or 1 is a result; exit 2 is a tool error and a STOP. The lines hold exact flags, scores, lengths and mnemonic
   shapes, never bytes.
2. **Record the outcome** in 48b-notes.txt as `0x0001E860 <file>: committed exact=<bool>; -oneatx exact=<bool>`, with
   the follow-on:
   - committed exact: it joins Task 2a, re-judged there first;
   - only `-oneatx` exact: it joins Task 2b's list, a D-12 proposal through 07-48c's `flags propose --from-batch`
     with the author `claude subagent (spike 011)`;
   - neither: it is held, with its first-difference key.
3. **The fixture:**
   - `cp build/spike-011/agents/b064/f_0001e860.c tests/fixtures/filler/tacp/f_0001e860.c`, then `cmp`, and check
     `batch.refusal(text)` is None and the file is ASCII. It is never edited; its provenance goes in the test
     docstring.
   - If only the neighbour variant is exact, copy that one instead as `f_0001e860.c` and say so in the docstring and
     the notes. tests/fixtures/filler/ stays a valid batch DIR.
4. **The real test** of `<behavior>`, in tests/test_filler_real.py.
   - Host run into 48b-real-host.log, then the container run `docker compose run --rm build bash -lc "uv sync --locked
     && uv run pytest -q -rs tests/test_filler_real.py" > build/gate/07-evidence/48b-real-container.log 2>&1; echo
     "exit=$?" >> build/gate/07-evidence/48b-real-container.log`.
   - If the `-oneatx` object's table span still has a problem: STOP with `## CHECKPOINT REACHED`, quoting the
     problem's reason. The rule does not do on real data what the spike showed, and nothing is widened to fit it.
5. **docs/matching.md.** The jump-table bullet's "checks the table and the filler up to the function like a function"
   gains the 07-48b clause:
   - when ours has less filler there than the original, the gap passes under 07-48's conditions 1, 2, 3 and 5 (at
     most 15 bytes, the head 16-aligned, no LE fixup in the gap, the original gap all alignment filler);
   - a table is data, so condition 4 does not apply, and the table is never landed.
6. **Commits:** `test(07-48b): real-file leading-table gap fixture for tacp func_0001E860`, then `docs(07-48b): the
   leading-table gap rule`.
  </action>
  <verify>
    <automated>E=build/gate/07-evidence; uv run pytest -q tests/test_filler_real.py && uv run ruff check . && grep -Eq "^exit=[01]$" $E/48b-rejudge.txt && grep -Eq "^exit=[01]$" $E/48b-rejudge-neighbour.txt && grep -q "^0x0001E860 " $E/48b-notes.txt && grep -qx "exit=0" $E/48b-real-container.log && test -s tests/fixtures/filler/tacp/f_0001e860.c && test "$(grep -c '07-48b' docs/matching.md)" -ge 1 && grep -q "EXACT_CELLS_0001E860" tests/test_filler_real.py</automated>
    <fails_when>Non-zero exit in any of these cases: a real test fails on the host; ruff fails; a re-judge hit a tool error (exit 2) or has no exit line; the outcome line is missing from the notes; the container run of the real tests did not exit 0; the fixture is missing; matching.md does not name 07-48b (absent before this plan); or the test does not pin the exact cells</fails_when>
  </verify>
  <acceptance_criteria>
    - `cmp tests/fixtures/filler/tacp/f_0001e860.c build/spike-011/agents/b064/f_0001e860.c` exits 0, or 48b-notes.txt and the test docstring say the neighbour variant was copied and `cmp` against that file exits 0
    - 48b-real-container.log shows tests/test_filler_real.py passed with no skip in the container
    - 48b-notes.txt names the follow-on (Task 2a, Task 2b or held) for 0x0001E860
  </acceptance_criteria>
  <done>The real row behind this plan is re-judged with the new rule, its table span passes on real data, and the orchestrator knows which follow-on it joins.</done>
</task>

<task type="auto">
  <name>Task 3: Both suites, the container gate --all diffed against the pre-change run, /code-review, then the SUMMARY</name>
  <precondition>Tasks 1-2 are committed on gsd/07-48-filler-rule; `git status --porcelain` is empty except ` M .planning/config.json`; `docker image inspect reverseapoc-build:local` exits 0; no host suite or container command is running</precondition>
  <files>.planning/phases/07-mechanics-first-decompilation/07-48b-SUMMARY.md, build/gate/07-evidence/</files>
  <read_first>
    - build/gate/07-evidence/48b-notes.txt, 48b-mutants.txt, 48b-rejudge.txt, 48b-rejudge-neighbour.txt
    - 07-48-PLAN.md Task 4 (the same done-gate steps, with 48- names)
    - docs/ceremonies.md ("When to run them")
  </read_first>
  <action>
**A fresh context may start here.** Read 48b-notes.txt first. The restart rule is as in 07-48 Task 4. Each step uses
07-48 Task 4's exact commands with `48b-` file names:
1. **Host suite in the background**, with 48b-host.head, 48b-host.log and 48b-ruff.log. Wait for it to finish.
2. **Then the container suite**, with 48b-container.head, 48b-container-build.log and 48b-container.log.
3. **Then the container gate.**
   - Run gate --all into 48b-gate-all-after.log.
   - Diff it with 48b-gate-all-before.log into 48b-gate-all.diff, explaining every differing line in 48b-notes.txt
     and listing the newly passing functions (none expected: no src/ change).
   - `git status --porcelain -- config/ decomphub.progress.json` must stay empty; otherwise STOP.
4. **Tier 1:** `uv run reverseapoc mechanics status --tier 1 > build/gate/07-evidence/48b-tier1-after.txt`.
5. **A failure** is fixed forward: a failing test, then a `fix(07-48b): ...` commit (no amend), the re-runs, and a
   Deviations entry.
6. **`/code-review`** on `git diff <48b-head-before>...HEAD`, at the default level, never max or ultra. Each finding
   is fixed (test first) or recorded with its reason. If this executor cannot run it, record "code review deferred to
   the orchestrator" with the command.
7. **The SUMMARY**, .planning/phases/07-mechanics-first-decompilation/07-48b-SUMMARY.md. It holds:
   - the rule as built and the RED assessment;
   - the mutant table;
   - the re-judge table (both files, both cells) and the follow-on for 0x0001E860;
   - the suites and gate results, the gate diff and the newly passing list;
   - the Review section and any Deviations.

   Commit it alone: `docs(07-48b): complete the leading-table gap plan`.
8. **Orchestrator steps, not run here:** fast-forward main, push, `gh run watch`. 0x0001E860 then joins Task 2a or
   Task 2b as recorded.
  </action>
  <verify>
    <automated>E=build/gate/07-evidence; grep -qx "exit=0" $E/48b-host.log && grep -qx "exit=0" $E/48b-ruff.log && grep -qx "exit=0" $E/48b-container.log && grep -qx "exit=0" $E/48b-gate-all-after.log && grep -q "^OK UFO2P.EXE sha1 " $E/48b-gate-all-after.log && grep -q "^OK TACP.EXE sha1 " $E/48b-gate-all-after.log && ! grep -q "MISMATCH" $E/48b-gate-all-after.log && ! grep "^SKIPPED" $E/48b-host.log | grep -vqE "GHIDRA_INSTALL_DIR|run in the container|only inside the container|POSIX-only|Windows file names cannot hold|non-UTF-8 byte names|symlink creation needs privileges on this host" && ! grep "^SKIPPED" $E/48b-container.log | grep -vq "Windows-only: msvcrt lock path" && test -f .planning/phases/07-mechanics-first-decompilation/07-48b-SUMMARY.md && uv run reverseapoc check-orig && git diff --quiet "$(cat $E/48b-head-before.txt)" HEAD -- config/ src/ decomphub.progress.json configure.py && S=$(git status --porcelain) && test -z "$(printf '%s\n' "$S" | grep -v '^ M .planning/config.json$' | grep -v '^$')"</automated>
    <fails_when>Non-zero exit in any of these cases: a suite, ruff or the container gate failed; a SHA-1 line is missing or a MISMATCH appears; a skip reason outside R-A appears; the SUMMARY is missing; `check-orig` fails; config/, src/, the feed or configure.py changed in this plan; or the tree is dirty beyond R-C's flag</fails_when>
    <human-check>The orchestrator re-runs the reported checks (end-of-phase mode) before it fast-forwards main</human-check>
  </verify>
  <acceptance_criteria>
    - 48b-host.head and 48b-container.head equal the HEAD before the SUMMARY commit, or a later fix-forward commit
    - the SUMMARY names every line of 48b-gate-all.diff, or says it is empty, and lists the newly passing functions (expected: none)
    - the SUMMARY has a Review section from `/code-review`, or the deferral line with the command
  </acceptance_criteria>
  <done>The gap rule is green in both suites and in the whole-EXE gate, and the orchestrator can push it.</done>
</task>

</tasks>

## Artifacts this phase produces

- `tools/reverseapoc/relocs.py`: the `table` keyword and condition 4 skipped for a table span.
- `tools/reverseapoc/check.py`: `_reloc(..., table=)` and `_head_reloc`'s `table=True`, with the docstrings.
- Tests: `tests/test_check.py` (gap-less table builders, negatives, spy), `tests/test_relocs.py` and
  `tests/test_land.py`.
- The real-file test in `tests/test_filler_real.py` and the fixture `tests/fixtures/filler/tacp/f_0001e860.c` (our
  C).
- `docs/matching.md` (the jump-table clause).
- `.planning/phases/07-mechanics-first-decompilation/07-48b-SUMMARY.md`.
- Gitignored evidence in build/gate/07-evidence/:
  - the baselines: `48b-head-before.txt`, `48b-tier1-before.txt`, `48b-gate-all-before.log`;
  - the RED and mutant records: `48b-red.xml`, `48b-red-record.json`, `48b-mutants.txt`, and the notes
    `48b-notes.txt`;
  - the re-judge: `48b-rejudge.txt`, `48b-rejudge-neighbour.txt`;
  - the real runs: `48b-real-host.log`, `48b-real-container.log`;
  - the done gate: `48b-host.head/.log`, `48b-ruff.log`, `48b-container.head/.log`, `48b-container-build.log`,
    `48b-gate-all-after.log`, `48b-gate-all.diff`, `48b-tier1-after.txt`.

## Sequencing and follow-ups (for the orchestrator)

- **Task 2a or Task 2b** takes tacp 0x0001E860 as 48b-notes.txt records.
- **07-48c** runs after this plan, on the same branch or its own, never at the same time.
- Mid-unit jump tables (a table between two publics) still fail closed. This plan changes only the leading table's
  gap.

## Flagged assumptions

- **The real table span passes under the `-oneatx` cell.** Spike 011 found every instruction right under the
  inferred cell. If the span still fails on real data, Task 2 STOPs rather than adjusting the rule.
- **The head itself may still differ under the committed rule.** The case-label offsets follow the code, so the
  committed cell may fail on code, not on the gap. The re-judge records it, and only an exact cell is pinned.

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| our compiled table and head -> the match gate | the table span's length rule is widened for one shape |
| check.py callers -> relocs.check_function | only one caller may relax condition 4 |
| orig/ bytes -> tests and evidence | only VAs, counts, booleans and mnemonic shapes may leave |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-07-144 | Tampering | the table span's gap rule: a gap of code, a misaligned head, more than 15 bytes or a fixup in the gap passes | high | mitigate | conditions 1, 2, 3 and 5 from 07-48 with a negative test each, asserting its reason; the table entries are still checked against the original LE fixups; container gate --all with both SHA-1s |
| T-07-145 | Elevation of privilege | `table=True` reaching a function check, which would skip the terminal-instruction condition | high | mitigate | the keyword defaults to False; the one `table=True` call sits in `_head_reloc` (a grep gate counts exactly one); a spy test and a mutant prove function checks never get it |
| T-07-146 | Information disclosure | game bytes in the fixture, tests or re-judge evidence | high | mitigate | the fixture is our C (cmp-checked copy); synthetic layouts are made up; the judge lines hold flags, scores, lengths and mnemonic shapes; the real test asserts on VAs and booleans |
| T-07-147 | Repudiation | the re-judge outcome misreported, so a row joins the wrong follow-on | medium | mitigate | both judge logs are kept with their exit lines; the notes and the SUMMARY quote them; the real test pins only the cells the logs show exact |
| T-07-SC | Tampering | package installs | low | accept | no package is installed |
</threat_model>

<verification>
- On synthetic units: a gap-less leading table passes before a 16-aligned head when the original gap is alignment
  filler. A gap that is not filler, an unaligned head, a 16-byte gap and a fixup in the gap are refused for their own
  reasons. Only the span is checked as a table, and the head lands with the table and gap kept original.
- On the real row: tacp func_0001E860's table span passes under the `-oneatx` cell, and its follow-on is recorded.
- Both suites and the container gate --all are green. config/, src/ and the feed are unchanged.
</verification>

<success_criteria>
- The design's "Plan 07-48b" is implemented: the same tail rule on the table span, conditions 1, 2, 3 and 5, with
  condition 4 not applied to data.
- tacp func_0001E860 is re-judged and placed in Task 2a, Task 2b or held, with evidence (DEC-03). Driver sessions'
  switch functions with a gap before them can pass `attempt check` (DEC-02).
</success_criteria>

<output>
Create `.planning/phases/07-mechanics-first-decompilation/07-48b-SUMMARY.md` in Task 3, from
build/gate/07-evidence/48b-notes.txt and the evidence files.
</output>
