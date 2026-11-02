---
phase: 07-mechanics-first-decompilation
plan: "48c"
type: execute
wave: 15
depends_on: ["07-48", "07-48b"]
files_modified: [tools/reverseapoc/flags.py, tools/reverseapoc/cli.py, tools/reverseapoc/batch.py, tests/test_flags.py, tests/test_batch.py, tests/test_cli_batch.py, docs/workflow.md, docs/toolchain.md, .planning/phases/07-mechanics-first-decompilation/07-48c-SUMMARY.md, build/gate/07-evidence/]
autonomous: false
gap_closure: true
requirements: [DEC-03]
user_setup: []

estimate:
  tokens: 160000
  raw_tokens: 160000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "`uv run reverseapoc flags propose --from-batch <results.jsonl> --cell \"<flags>\" --author \"<who>\"` (flags.propose_batch) turns the exact records of that cell in a `reverseapoc batch` results file into proposals in config/cflags-proposals.toml (D-12): one per (exe, unit), with `source = \"batch\"`, `author`, evidence = the results file (a repo-relative path under build/), rule = the unit's committed compiler spec plus the cell's flags, base = the unit's committed rule, the functions in start order, keeps, and siblings (D-32). The candidate is the whole unit with each row's C at its INCLUDE_ASM marker: the committed src/<exe>/<unit>.c, or `units.scaffold_unit` when there is none. It is written to build/flags/<id>/<unit>.c, with its LF sha256, as `_candidate` does"
    - "The negatives are refused or skipped with a reason, and nothing is written for a refusal: a record that is not exact (skipped); a record of the cell whose flags differ from the rule the proposal would write, or a cell with no record (refused); a results file or a record's source outside build/ (refused); an unknown author, i.e. anything other than `reverseapoc lift` or `claude subagent (spike 011)` (refused); a duplicate (exe, unit, rule) the queue already holds (skipped, the queue byte-identical). Also: a source whose LF sha256 differs from the record's (refused), a unit with an open proposal (skipped), a function status.csv has matched (skipped), and a cell equal to the unit's committed rule (skipped)"
    - "`reverseapoc batch` records gain `source` (the input C file, a repo-relative POSIX path inside the repo, absolute otherwise) and `source_sha256` (its LF sha256, empty when it could not be read as ASCII). A record names no C file today, and build/batch/run/ is overwritten by the next batch, so `--from-batch` could not find the C it judged"
    - "The queue schema grows one optional field, `author` (default \"\"), written only when set. All 44 committed entries of config/cflags-proposals.toml still parse, and `format_queue(read_queue(...))` reproduces the committed file byte for byte. `author` is set exactly when `source == \"batch\"`"
    - "`flags approve` of a batch proposal (synthetic tests only; executors never run approve) writes `Matched-By: <author>` in place of the co-authors it derives from attempts. The message holds no `Matched-By: reverseapoc drive` line and no attempt-derived Co-Authored-By line, so `stats` never counts it toward AGT-11's unattended figure, and the gate runs with `--attempts 0` (by hand). Sweep proposals land exactly as before"
    - "`flags regate` is unchanged (the regate section of flags.py is byte-identical): it already re-proves the whole unit under the proposed rule, which is the sibling control spike 011's control_cells.py did. config/cflags.txt and config/cflags-proposals.toml are unchanged by this plan"
    - "Done gate as in 07-48: the host suite and ruff, then the container suite (R-A skips only), the container gate --all with both SHA-1s OK diffed against this plan's pre-change run, `/code-review`, and docs/workflow.md and docs/toolchain.md naming `--from-batch` and the record keys"
  prohibitions:
    - statement: "MUST NOT run `flags approve` or `flags default` (owner only), and MUST NOT run `flags propose` or `flags regate` against the committed queue (that is Task 2b, run by the orchestrator after this plan)"
      status: resolved
      verification: judgment
    - statement: "MUST NOT edit config/cflags.txt, config/cflags-proposals.toml, orig/, the config/ hash manifests, configure.py, the build scripts, any src/ file, status.csv or decomphub.progress.json"
      status: resolved
      verification: test
    - statement: "MUST NOT change `flags regate` or the sweep-sourced propose and approve paths beyond what the batch source needs (the 44 committed entries keep their exact text)"
      status: resolved
      verification: test
    - statement: "MUST NOT rewrite the C a batch judged when splicing it (no declaration rewrite): a declaration clash surfaces in `flags regate` and fails closed"
      status: resolved
      verification: test
    - statement: "MUST NOT run `reverseapoc drive` or `claude -p`, MUST NOT push, and MUST NOT dispatch subagents (R-D); no game bytes in the queue, records, tests or evidence"
      status: resolved
      verification: judgment
  artifacts:
    - path: tools/reverseapoc/flags.py
      provides: "BATCH source, AUTHORS, Proposal.author (optional), propose_batch, the batch landing trailer"
      contains: "def propose_batch"
    - path: tools/reverseapoc/cli.py
      provides: "`flags propose --from-batch FILE --cell FLAGS --author WHO`, exclusive with --from-attempts; batch records with source keys"
      contains: "--from-batch"
    - path: tools/reverseapoc/batch.py
      provides: "with_source: a record's source path and LF sha256"
      contains: "def with_source"
    - path: tests/test_flags.py
      provides: "the batch-proposal negatives, the tracer, the queue compatibility pin and the batch approve trailer"
      contains: "test_propose_batch_adds_one_proposal_per_unit"
    - path: docs/workflow.md
      provides: "the --from-batch verb and the batch landing trailer under Flag rules"
      contains: "--from-batch"
  key_links:
    - from: tools/reverseapoc/cli.py
      to: tools/reverseapoc/batch.py
      via: "the batch verb adds `source` and `source_sha256` to every record through batch.with_source"
      pattern: "with_source"
    - from: tools/reverseapoc/flags.py
      to: tools/reverseapoc/batch.py
      via: "propose_batch builds the proposed rule with batch.cell_rule and checks each record's flags against it"
      pattern: "cell_rule"
    - from: tools/reverseapoc/flags.py
      to: tools/reverseapoc/units.py
      via: "a unit with no committed src file is scaffolded with units.scaffold_unit before the row's C replaces its marker"
      pattern: "scaffold_unit"
    - from: config/cflags-proposals.toml
      to: tools/reverseapoc/flags.py
      via: "read_queue accepts an entry without `author`; format_queue omits an empty author, so the committed queue round-trips byte for byte"
      pattern: "OPTIONAL_FIELDS"
---

<objective>
This is a gap closure. Spike 011 found 13 converter rows and 5 agent rows that are exact only under `-4r -oneatx -s
-fpi`: ufo2p 0x00034FE0, 0x000483A0 and 0x0005FBD0, and tacp 0x00095800 and 0x00098300. Each needs a per-unit cflags
rule through the owner's D-12 approval.

`flags propose` reads only driver attempts today. Its sources are sweep, sweep2 and owner; its evidence is a driver
attempt's checks/NNNN.json; and `flags approve` derives co-authors from those attempts. The owner chose a new plan,
07-48c, to add a batch input (AskUserQuestion, at the kickoff of this gap). The design's "Plan 07-48c" section:
- a batch-sourced proposal takes a `reverseapoc batch` results file and its cell;
- its `source` is "batch", its evidence is the batch record file under build/, and its candidate is the whole unit
  with the row's C spliced in, copied to build/flags/<id>/ as `_candidate` does now;
- it has an `author`, "reverseapoc lift" or "claude subagent (spike 011)";
- `flags approve` writes `Matched-By: <author>` for batch proposals, in place of the co-authors it derives from
  attempts;
- `regate` is unchanged;
- the negatives: a record that is not exact, a cell that differs from the proposed rule, an evidence path outside
  build/, an unknown author, and a duplicate (exe, unit, rule).

Decisions taken here, with their reasons:
- **Batch records name their C.** A record today holds exe, address, cell, flags, compiled, exact, exact_trim, score,
  len and key, but no file. The compiled cell sources under build/batch/run/<exe>/<addr>/ are overwritten by the next
  batch, and are numbered by --cell order, not by cell text. So `reverseapoc batch` adds `source` and `source_sha256`
  to each record (`batch.with_source`, applied in cli.py where the input path is known). `propose_batch` reads the
  file the record names, checks its LF sha256, and refuses an older record without these keys ("re-run reverseapoc
  batch").

  `batch.cell_record` keeps its signature and output, so its existing tests are unchanged. The keys are additive, and
  docs/toolchain.md lists them.
- **The splice is the row's C verbatim at its marker.** For each row, the candidate replaces `INCLUDE_ASM(<name>);`
  with the row's file text, as the spike's land_converter does, with no declaration rewrite. C89 allows identical
  redeclarations, and common.h is guarded. A conflicting declaration fails the compile inside `flags regate`, which
  records the proposal `failed` with the reason: fail-closed, and visible to Task 2b. The splice is skipped, with a
  reason, when:
  - the marker is missing, because the unit already defines the row;
  - the row's file defines another row's placeholder (contextpack.definitions), so only the row's own function is
    proposed.
- **One proposal per (exe, unit) per run.** The queue allows one open proposal per unit (`_check_queue`). So the
  exact records of one unit in one results file become one proposal that lists all its functions. Proposals are
  never merged across runs: a unit with an open proposal is skipped, and a duplicate (exe, unit, rule) the queue
  already holds, whatever its status except rejected or superseded, is skipped with its id. A re-run is idempotent.
- **`author` is optional in the file and closed in value.** A new entry carries it only when set, so the 44 committed
  entries keep their exact text. AUTHORS is the design's two names, and the CLI offers only those as choices.
- **A batch landing is not a driver match.** The C came from the converter or a spike subagent, so no attempt and no
  model co-authors it. Its trailer is `Matched-By: <author>`, and the gate records attempts 0, "by hand" in gate's
  own terms. `stats` classes such a commit `human-written` until the owner rules a converter class (spike 010
  ruling 4 allowed only that converter C may land).

Sequencing:
- 07-48c runs on the MAIN checkout on `gsd/07-48-filler-rule` (or its own branch from it), after 07-48b, and never at
  the same time as it. It depends on 07-48 by code: a filler row's batch record is exact, and its `flags regate`
  passes, only under 07-48's rule.
- It sits in wave 15, one after 07-48b, because both use the main checkout, its branch, build/test-cc and the
  container, and the host and container suites never run at once.
- The orchestrator fast-forwards main, pushes and watches CI; the executor never pushes.
- The auto-memory `gsd-main-checkout-plans` recipe applies (`[gsd:dispatch phase="07" plan="07-48c"]`). R-A, R-C and
  R-D apply.
- This plan unblocks Task 2b, which the orchestrator runs: re-judge the 18 rows under `-4r -oneatx -s -fpi` with
  `reverseapoc batch`, then `flags propose --from-batch` on the host, then `flags regate <ids>` in the container; the
  owner approves.

Output: the batch source in flags.py, the CLI verb, the record keys, the approve trailer, the tests, the docs, and
the SUMMARY.
</objective>

<execution_context>
@C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/.claude/gsd-core/workflows/execute-plan.md
@C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/phases/07-mechanics-first-decompilation/07-48-SUMMARY.md
@.planning/phases/07-mechanics-first-decompilation/07-17-PLAN.md
@.planning/phases/07-mechanics-first-decompilation/07-24-PLAN.md
@C:/Users/Ayrton/.claude/plans/pasted-content-id-769c-kickoff-gate-curious-gosling.md
@.superpowers/sdd/let-s-execute-gsd-execute-phase-7-sorted-harp/rulings.md

<interfaces>
As built on main at 8943cce. flags.py is not touched by 07-48 or 07-48b. batch.py and cli.py are, so find each
function there by name.

**flags.py**
- Module docstring L1-31 (the queue format). QUEUE L64; SOURCES L74-75 (sweep, sweep2, owner); FLAGS_DIR L80.
- `Proposal` L106-155: frozen, fields in file order, last `reverted`; `to_json` (asdict); `line()`.
- `FIELDS` L158 (every dataclass field today); `_LIST_FIELDS` L159; `_INT_FIELDS` L160.
- `_build_path` L172 (repo-relative POSIX under build/, no . or ..). `_field_problem` L178-208. `_check_queue`
  L211-230 (printable ASCII; one open proposal per (exe, unit)).
- `_proposal` L233-251 (requires `set(table) == set(FIELDS)`). `read_queue` L254. `_toml_value` L274. `format_queue`
  L284-291 (FIELDS order). `write_queue` L294.
- `_Context` L418-483: rules, status, `rows(exe)` (symbols-aware names), `base(exe, unit)`, `start`, `matched`,
  `keeps`, `siblings`.
- `ProposeReport` L547-563. `_next_id` L566. `_candidate` L571-581 (write_atomic, lf_sha256). `_new_proposal` L584.
- `_MARKER` L599 (the INCLUDE_ASM regex). `_spliced` L602. `propose(runs, *, repo, queue=None)` L659-694 (idempotent;
  skips matched; skips an approved unit; merges into an open one).
- The regate section runs from the `# ---- regate:` comment (L697) to `CFLAGS = Path(...)` (L1016), and stays
  byte-identical.
- approve:
  - `_hitting_attempts` L1066 (refuses non-driver evidence), `_attempt_models` L1092, `_coauthors` L1117;
  - `_Landing(proposal, source, coauthors, attempts)` L1148;
  - `_approvable` L1162-1188 (it computes attempts as the max hitting attempt, and the co-authors);
  - `_approve_message` L1304-1318 (trailers: co-authors, `driver.MATCHED_BY`, `Flags-Approved-By:`);
  - `_confirmation` L1321;
  - the gate call with `--attempts str(land.attempts)` L1379-1381.
- driver.MATCHED_BY = `Matched-By: reverseapoc drive` (driver.py L239). stats.py classes by it.
- status.lf_sha256(text). units.scaffold_unit(exe, unit_row, functions) L344. functions.read_units_csv.
  contextpack.definitions(text) L472. check.unit_rule_path.

**batch.py**: `cell_rule(base, flags_text)` (validated by cflags' parser; BatchError), `cell_record(...)` (the record
dict), `COMMITTED_CELL`, `read_ascii`, `refusal`, `parse_address`.

**cli.py**
- `_batch_file(args, rules, exe, start, path)` (refused records built here) and `_file_records(item, compiled)`.
  `_BatchFile` holds exe, start, cells, jobs and refused; add the path, or the computed source keys, to it.
  `_run_batch` writes the JSONL.
- `_flags_propose` L2058 (`flags.propose(args.from_attempts, repo=args.repo)`).
- `_add_flags_command` L2092: `--from-attempts` with nargs `*` and required=True L2105; `--json`; `--repo` added to
  every verb L2129-2131.
- `_cmd_flags` maps `_ERRORS` to exit 2.

**Tests**
- tests/test_flags.py:
  - `make_repo(tmp_path)` L79 (a synthetic repo: config/, cflags, status, functions.csv, units, src) and `queue_of`
    L120;
  - `_proposal(**changes)` L190;
  - `test_queue_round_trip` L206 asserts the keys of an entry equal `flags.FIELDS` and that FIELDS ends with reason,
    variant_sha256, reverted. Both stay true, because FIELDS stays the required keys;
  - the approve tests L948-1230 with fake git and runner (`test_approve_lands_one_commit` L948 is the model);
  - `test_cli_propose_and_list` L329.
- tests/test_batch.py L332-362 (cell_record tests, unchanged). tests/test_cli_batch.py: the `no_load` fixture L19
  (refuses loading and compiling), and the batch CLI refusal tests.

**Committed queue** (measured at 8943cce): 44 entries, all `source = "sweep"`, statuses failed and landed.
`format_queue(read_queue(path))` already equals the file byte for byte at HEAD, so the compatibility pin is a guard
that must stay green, not a RED test.

The container commands, the R-A regex and the host-suite background rule are as in 07-48's interfaces.
</interfaces>
</context>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: Tracer - a batch results file becomes one D-12 proposal per unit through `flags propose --from-batch`, negatives first</name>
  <reversibility rating="costly">the queue format is read by the driver, the approval tool and the docs (D-12); the field is optional and the committed entries keep their exact text</reversibility>
  <precondition>All of these hold:
- Main checkout. `git status --porcelain` is empty except ` M .planning/config.json`.
- The branch holds 07-48's SUMMARY commit, and 07-48b's if it has run: `L=$(git log --format=%s) && printf '%s\n' "$L" | grep -q '^docs(07-48): complete'`.
- The drive lock prints True (the design's preflight one-liner).
- `uv run reverseapoc check-orig` exits 0, and `docker image inspect reverseapoc-build:local` exits 0.
- No host suite, no container command and no `reverseapoc drive` is running.</precondition>
  <files>tools/reverseapoc/flags.py, tools/reverseapoc/cli.py, tools/reverseapoc/batch.py, tests/test_flags.py, tests/test_batch.py, tests/test_cli_batch.py</files>
  <read_first>
    - tools/reverseapoc/flags.py (L1-300: the docstring, Proposal, FIELDS, _field_problem, _check_queue, _proposal, read/format/write_queue; L418-700: _Context, _candidate, _new_proposal, _MARKER, _spliced, propose)
    - tools/reverseapoc/cli.py (`_batch_file`, `_file_records`, `_run_batch`; L2055-2135: the flags verbs)
    - tools/reverseapoc/batch.py (cell_rule, cell_record, read_ascii)
    - tools/reverseapoc/units.py (scaffold_unit) and tools/reverseapoc/contextpack.py (definitions)
    - tests/test_flags.py (L1-130 make_repo and helpers; L190-340 queue and propose tests)
    - tests/test_cli_batch.py (L1-60, the no_load fixture)
  </read_first>
  <behavior>
    Negatives first. Each fails on HEAD because `flags.propose_batch`, `batch.with_source` and the CLI option do not exist, reached as attributes or as CLI arguments inside the test bodies:
    - test_propose_batch_skips_a_record_that_is_not_exact: the cell's only record has exact false -> report.added empty, report.skipped names the exe and address with `not exact`, and the queue file is byte-identical (or still absent)
    - test_propose_batch_refuses_a_cell_whose_flags_differ: a record of the cell whose `flags` is not the cell rule's flags -> FlagsError naming the address, and nothing is written; a `--cell` with no record in the file -> FlagsError
    - test_propose_batch_refuses_paths_outside_build: a results file at the repo root, and one outside the repo -> FlagsError containing `build/`; a record whose `source` lies outside build/ -> FlagsError
    - test_propose_batch_refuses_an_unknown_author: author `someone` -> FlagsError naming both AUTHORS
    - test_propose_batch_skips_a_duplicate_exe_unit_rule: the queue already holds a landed proposal with the same exe, unit and rule -> skipped with `duplicate of F-0001`, queue byte-identical; and a unit with an open proposal under another rule -> skipped with `is open`
    - test_propose_batch_refuses_a_changed_source: the source file edited after the record -> FlagsError with `changed since the batch judged it`; and a record without `source` -> FlagsError with `re-run reverseapoc batch`
    - test_propose_batch_skips_matched_and_committed_rule: a function status.csv has matched, and a cell whose flags equal the unit's committed rule -> both skipped with their reasons
    - test_propose_batch_skips_a_file_defining_another_row: the row's file also defines the unit's next row's placeholder -> skipped with that name
    - test_queue_refuses_author_rules: a batch proposal without author, a sweep proposal with author, and an author outside AUTHORS -> FlagsError from write_queue
    - test_cli_propose_needs_exactly_one_source: `flags propose` with neither or both of --from-attempts and --from-batch -> exit 2; --from-batch without --cell or --author -> exit 2; --cell or --author with --from-attempts -> exit 2
    Positives:
    - test_propose_batch_adds_one_proposal_per_unit (TARGET, the tracer): in make_repo, a results file under build/batch/ with two exact records of one unit (one has a committed src file, one marker per row) and one of a unit with no src file, each naming a source under build/ with its LF sha256 -> two proposals, F-0001 and F-0002:
      - source `batch` and the author given;
      - evidence `(the results path,)`;
      - rule = the committed spec plus the cell's flags, and base = the unit's committed rule;
      - functions in start order; keeps; siblings as `_Context.siblings` gives;
      - status proposed, regate_exit -1;
      - the candidate at build/flags/<id>/<unit>.c: the unit text with each marker replaced by its row's file text (the scaffolded unit for the second), and candidate_sha256 its LF sha256;
      - config/cflags.txt unchanged
    - test_propose_batch_is_idempotent: a second run adds nothing, and the queue is byte-identical
    - test_queue_round_trips_a_batch_proposal: write_queue then read_queue returns it; its entry ends with `author = "reverseapoc lift"`; an entry without author has no author line; test_queue_round_trip passes unchanged
    - test_committed_queue_round_trips_byte_identical (a guard, green on HEAD too): read_queue of REPO_ROOT/config/cflags-proposals.toml has 44 entries, every author is "", and format_queue reproduces the file byte for byte
    - test_with_source_names_the_path_and_lf_sha256 (tests/test_batch.py): a file inside the repo gives a repo-relative POSIX path, one outside gives an absolute POSIX path, and CRLF text gives the same sha256 as its LF form; the other keys of the record are unchanged
    - test_batch_records_name_their_source (tests/test_cli_batch.py): `batch` over a `#pragma` source, so nothing compiles, with batch.load_exe_inputs monkeypatched to a stub ExeInputs holding that one row -> the refused record has `source` equal to the file's repo-relative path and `source_sha256` its LF sha256
    - test_cli_propose_from_batch: `main(["flags", "propose", "--from-batch", <path>, "--cell", "-4r -oneatx -s -fpi", "--author", "reverseapoc lift", "--repo", <repo>])` exits 0, prints `added F-0001`, and `--json` prints one document
  </behavior>
  <action>
**Baseline first, before any edit** (build/gate/07-evidence/, by shell redirection):
- `git rev-parse HEAD > 48c-head-before.txt`;
- `cp config/cflags-proposals.toml build/gate/07-evidence/48c-queue-before.toml`;
- `docker compose run --rm build bash -lc "uv sync --locked && uv run reverseapoc gate --all" >
  build/gate/07-evidence/48c-gate-all-before.log 2>&1; echo "exit=$?" >>
  build/gate/07-evidence/48c-gate-all-before.log`.

It must end `exit=0` with config/ and the feed unchanged; otherwise STOP. Then start 48c-notes.txt.

**RED.**
1. Write the tests of `<behavior>` in tests/test_flags.py, tests/test_batch.py and tests/test_cli_batch.py, negatives
   first.
   - Results files and C sources are made-up text in the synthetic repo; the records are JSON lines written by the
     test.
   - Every new name is reached as an attribute or a CLI argument inside a test body, so HEAD collects.
2. Run `uv run pytest -q tests/test_flags.py tests/test_batch.py tests/test_cli_batch.py
   --junitxml=build/gate/07-evidence/48c-red.xml -p no:cacheprovider`.
3. Record 48c-red-record.json, target `tests/test_flags.py::test_propose_batch_adds_one_proposal_per_unit`, and
   require RED_EVIDENCE_OK from `gsd_run check tdd-red-evidence`.
4. In 48c-notes.txt, note that test_committed_queue_round_trips_byte_identical passed on HEAD by design (a guard).
5. Commit `test(07-48c): failing tests for batch-sourced flag proposals, negatives first`.

**GREEN, tools/reverseapoc/batch.py.**
- Add `with_source(record: dict, path: Path, text: str | None) -> dict`. It returns the record plus `source` (a
  repo-relative POSIX path when `path` is inside REPO_ROOT, else absolute POSIX) and `source_sha256`
  (`status.lf_sha256(text)`, or "" when `text` is None).
- The module docstring says records name their source so `flags propose --from-batch` can find the C a record
  judged.

**GREEN, tools/reverseapoc/cli.py, the batch verb.**
- `_BatchFile` carries the source keys.
- `_batch_file` reads the text once. The text is None when it is not ASCII, and it is kept for a `#pragma` refusal.
- Both refused and judged records pass through `batch.with_source`. Nothing else in the verb changes.

**GREEN, tools/reverseapoc/flags.py.**
1. **Constants.** `BATCH = "batch"`, added to SOURCES. `AUTHORS = ("reverseapoc lift", "claude subagent (spike
   011)")`. `OPTIONAL_FIELDS = {"author": ""}`.
2. **Proposal.** The last field is `author: str = ""`. FIELDS becomes the required keys, every field not in
   OPTIONAL_FIELDS, so test_queue_round_trip holds.
3. **The reader and writer.**
   - `_proposal` accepts FIELDS plus any optional key present, with its type checked; an unknown or missing
     required key is refused as today.
   - `_check_queue` checks the optional keys for printable ASCII too.
   - `format_queue` writes FIELDS, then each optional key whose value differs from its default.
4. **`_field_problem`** gains `author`: `p.author in ("", *AUTHORS)`, and `(p.source == BATCH) == (p.author != "")`.
5. **`propose_batch(results: Path, cell: str, author: str, *, repo: Path, queue: Path | None = None) ->
   ProposeReport`**, in this order:
   - the author is in AUTHORS, else FlagsError;
   - the results file is inside `repo` and `_build_path` holds for its repo-relative POSIX path, else FlagsError
     naming build/;
   - read the JSONL. Records whose `cell` equals `cell` are the cell's records; none is a FlagsError;
   - for each record: exe in EXES, and an address that parses;
   - the proposed rule for its unit (from functions.csv via `_Context.rows`) is `batch.cell_rule(committed rule,
     cell)`, rendered `spec flags`. A BatchError becomes a FlagsError. A record whose `flags` differ from that rule's
     flags is a FlagsError naming the address;
   - a non-exact record is skipped;
   - a record without `source`/`source_sha256` is a FlagsError ("re-run reverseapoc batch");
   - the source must satisfy `_build_path`, and its LF sha256 must equal the record's, else FlagsError ("changed
     since the batch judged it");
   - group the remaining records by (exe, unit), in start order.

   Each group is then skipped, with a reason in `skipped`, when:
   - the rule equals the unit's base;
   - a function is matched in status.csv;
   - a queue entry has the same (exe, unit, rule) and a status other than rejected or superseded ("duplicate of
     F-NNNN");
   - another proposal is open or approved for the unit;
   - a row's marker is missing, or its file defines another of the unit's row placeholders.

   Otherwise:
   - build the candidate from the committed src/<exe>/<unit>.c, or `units.scaffold_unit` over config/<exe>/units.csv
     and functions.csv when there is none;
   - replace each row's marker with its file text (`_MARKER`);
   - write it to build/flags/<id>/<unit>.c with write_atomic;
   - add the Proposal of the truth above.

   Write the queue only when something was added.
   - Keep nesting shallow: a record reader, a group checker and a candidate builder as small helpers
     (.claude/rules/tools.md).
6. **The module docstring** gains: the batch source, author, the evidence (a results JSONL under build/) and the
   candidate built from the unit.

**GREEN, tools/reverseapoc/cli.py, the flags verb.**
- `flags propose` takes a required mutually exclusive group, `--from-attempts [RUN ...]` | `--from-batch FILE`, plus
  `--cell FLAGS` and `--author WHO` (choices AUTHORS).
- `_flags_propose` dispatches to `flags.propose` or `flags.propose_batch`. It refuses `--cell`/`--author` without
  `--from-batch`, and their absence with it, as a FlagsError (exit 2).
- The help text says the proposals still need `flags regate` and the owner's approval.

Run the three test files green, plus tests/test_cli_batch.py, ruff and `git diff --quiet -- config/`. Commit
`feat(07-48c): flags propose --from-batch (batch-sourced D-12 proposals with an author)`.
  </action>
  <verify>
    <automated>uv run pytest -q tests/test_flags.py tests/test_batch.py tests/test_cli_batch.py && uv run ruff check . && test "$(grep -c '^def propose_batch' tools/reverseapoc/flags.py)" -eq 1 && test "$(grep -c '^def with_source' tools/reverseapoc/batch.py)" -eq 1 && test "$(grep -c -- '--from-batch' tools/reverseapoc/cli.py)" -ge 1 && cmp config/cflags-proposals.toml build/gate/07-evidence/48c-queue-before.toml && git diff --quiet "$(cat build/gate/07-evidence/48c-head-before.txt)" HEAD -- config/ src/ decomphub.progress.json && grep -qx "exit=0" build/gate/07-evidence/48c-gate-all-before.log</automated>
    <fails_when>Non-zero exit in any of these cases: a flags, batch or CLI batch test fails; ruff fails; propose_batch, with_source or the --from-batch option is missing (all absent at 8943cce); the committed queue changed; config/, src/ or the feed changed; or the pre-change gate log did not exit 0</fails_when>
  </verify>
  <acceptance_criteria>
    - RED_EVIDENCE_OK for build/gate/07-evidence/48c-red-record.json, and 48c-notes.txt names how each negative failed on HEAD
    - `uv run python -c "from pathlib import Path; from reverseapoc import flags; p=Path('config/cflags-proposals.toml'); q=flags.read_queue(p); assert len(q)==44 and all(x.author=='' for x in q) and flags.format_queue(q)==p.read_bytes().decode('ascii')"` exits 0
    - `uv run python -c "from reverseapoc import flags; assert flags.AUTHORS == ('reverseapoc lift', 'claude subagent (spike 011)') and 'batch' in flags.SOURCES and 'author' not in flags.FIELDS"` exits 0
  </acceptance_criteria>
  <done>The orchestrator can turn a batch run's exact rows into reviewable per-unit rule proposals, with the C that was judged and who wrote it, without touching config/cflags.txt.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: `flags approve` writes `Matched-By: <author>` for a batch proposal, with no attempt co-authors and attempts 0 (synthetic tests only)</name>
  <precondition>Task 1 is committed; `git diff --quiet -- tools/ tests/` exits 0. The executor never runs `flags approve` for real: these are fake-git, fake-runner tests</precondition>
  <files>tools/reverseapoc/flags.py, tests/test_flags.py</files>
  <read_first>
    - tools/reverseapoc/flags.py (L1016-1190: constants, _hitting_attempts, _attempt_models, _coauthors, _Landing, _approvable; L1300-1330: _approve_message, _confirmation; L1347-1430: _Approver and its gate call)
    - tests/test_flags.py (L780-1000: _git, _attempt_record, test_approve_lands_one_commit and its fakes)
    - tools/reverseapoc/stats.py (L1-20: how a commit is classed by its Matched-By trailer)
  </read_first>
  <behavior>
    Negatives first:
    - test_approve_a_batch_proposal_has_no_driver_trailer: approving a regated batch proposal (fake git and runner) -> the commit message has no `Matched-By: reverseapoc drive` line and no `Co-Authored-By:` line, and no attempts.jsonl is read for it (an attempts log with no matching record does not refuse it)
    - test_approve_a_batch_proposal_gates_with_attempts_0: the runner's gate argv holds `--attempts 0`
    Positives:
    - test_approve_a_batch_proposal_writes_matched_by_author (TARGET): the message's trailer block is exactly `Matched-By: claude subagent (spike 011)` then `Flags-Approved-By: <by> (<id>, <date>)`; the commit is made; the proposal is landed
    - the existing approve tests (test_approve_lands_one_commit, test_approve_a_fable_candidate_names_fable, test_approve_a_mixed_candidate_gets_one_trailer_per_model_in_pass_order ...) pass unchanged: sweep proposals keep their co-authors and `Matched-By: reverseapoc drive`
    - test_list_shows_the_author: `Proposal.line()` of a batch proposal holds `author claude subagent (spike 011)`, and `_confirmation` names it
  </behavior>
  <action>
**RED.**
1. Write the tests above in tests/test_flags.py, modelled on test_approve_lands_one_commit's fakes. The batch
   proposal is written to the fake repo's queue as regated with exit 0 on today's cflags sha, with its candidate at
   its path.
2. Run `uv run pytest -q tests/test_flags.py --junitxml=build/gate/07-evidence/48c-red2.xml -p no:cacheprovider`.
3. Record 48c-red2-record.json (target `test_approve_a_batch_proposal_writes_matched_by_author`) and require
   RED_EVIDENCE_OK.
4. Commit `test(07-48c): failing tests for the batch landing trailer`.

**GREEN, tools/reverseapoc/flags.py.**
- Constants:
  - `MATCHED_BY_KEY`, derived from driver.MATCHED_BY's key (the text before its first colon, plus the colon), never
    a second literal;
  - `BY_HAND_ATTEMPTS = 0` (gate's `--attempts` count, 0 = by hand).
- `_approvable`: for `p.source == BATCH`, build `_Landing(p, _landing_source(repo, p), (), BY_HAND_ATTEMPTS)` without
  calling `_hitting_attempts` or `_coauthors`. Every other refusal stays in force, for both sources: regated with exit
  0, today's cflags sha, one per unit, the candidate's sha.
- `_approve_message`: for a batch proposal the trailer block is `f"{MATCHED_BY_KEY} {p.author}"` then the
  Flags-Approved-By line. The sweep block is unchanged.
- `Proposal.line()` adds `  author <author>` when set, and `_confirmation` names the author.
- The docstrings of approve and `_approve_message` say why: a batch C was written by the converter or a spike
  subagent, not by a driver attempt, so no attempt co-authors it. stats then classes the landing human-written, never
  unattended (AGT-11).

Run tests/test_flags.py and tests/test_stats.py green, then ruff. Commit `feat(07-48c): flags approve
writes Matched-By: <author> for batch proposals`.

**The regate section stays byte-identical.** Show it: `git show "$(cat
build/gate/07-evidence/48c-head-before.txt)":tools/reverseapoc/flags.py | sed -n '/^# ---- regate/,/^CFLAGS = /p' >
build/gate/07-evidence/48c-regate-before.txt`, the same `sed` on the working file into 48c-regate-after.txt, then
`cmp` the two.
  </action>
  <verify>
    <automated>uv run pytest -q tests/test_flags.py tests/test_batch.py tests/test_cli_batch.py && uv run ruff check . && git show "$(cat build/gate/07-evidence/48c-head-before.txt)":tools/reverseapoc/flags.py > build/gate/07-evidence/48c-flags-before.py && sed -n '/^# ---- regate/,/^CFLAGS = /p' build/gate/07-evidence/48c-flags-before.py > build/gate/07-evidence/48c-regate-before.txt && sed -n '/^# ---- regate/,/^CFLAGS = /p' tools/reverseapoc/flags.py > build/gate/07-evidence/48c-regate-after.txt && test -s build/gate/07-evidence/48c-regate-before.txt && cmp build/gate/07-evidence/48c-regate-before.txt build/gate/07-evidence/48c-regate-after.txt && test "$(grep -c 'BY_HAND_ATTEMPTS' tools/reverseapoc/flags.py)" -ge 2 && cmp config/cflags-proposals.toml build/gate/07-evidence/48c-queue-before.toml</automated>
    <fails_when>Non-zero exit in any of these cases: a flags or batch test fails (the existing sweep approve tests included); ruff fails; the regate section is empty or differs from HEAD's; BY_HAND_ATTEMPTS is not defined and used (absent at 8943cce); or the committed queue changed</fails_when>
  </verify>
  <acceptance_criteria>
    - RED_EVIDENCE_OK for build/gate/07-evidence/48c-red2-record.json
    - `grep -c '"Matched-By' tools/reverseapoc/flags.py` is 0 (the key is derived from driver.MATCHED_BY, not a second literal)
  </acceptance_criteria>
  <done>When the owner approves a batch proposal, its match commit says who wrote the C, and it can never pass as an unattended driver match.</done>
</task>

<task type="auto">
  <name>Task 3: Docs, both suites, the container gate --all diffed against the pre-change run, /code-review, then the SUMMARY</name>
  <precondition>Tasks 1-2 are committed; `git status --porcelain` is empty except ` M .planning/config.json`; `docker image inspect reverseapoc-build:local` exits 0; no host suite or container command is running</precondition>
  <files>docs/workflow.md, docs/toolchain.md, .planning/phases/07-mechanics-first-decompilation/07-48c-SUMMARY.md, build/gate/07-evidence/</files>
  <read_first>
    - build/gate/07-evidence/48c-notes.txt
    - docs/workflow.md (the "Flag rules (D-12, D-14)" section, around L288-306) and docs/toolchain.md ("Batch judge", around L410-421)
    - 07-48-PLAN.md Task 4 (the same done-gate steps)
  </read_first>
  <action>
**A fresh context may start here.** Read 48c-notes.txt first. The restart rule is as in 07-48 Task 4.

1. **Docs** (one commit, `docs(07-48c): flags propose --from-batch`):
   - **docs/workflow.md, "Flag rules".** The propose bullet names both inputs:
     - `--from-attempts <run> ...` as today;
     - `uv run reverseapoc flags propose --from-batch <results.jsonl> --cell "<flags>" --author "<who>"` (host): a
       `reverseapoc batch` results file under build/; one proposal per unit from the cell's exact records; the author
       is one of the two names; the candidate is the whole unit with each row's C at its marker; it still needs
       `flags regate` and the owner's approval.

     The approve bullet adds that a batch proposal's commit carries `Matched-By: <author>` in place of the attempt
     co-authors.
   - **docs/toolchain.md, "Batch judge".** The record key list gains `source` and `source_sha256`, with why: `flags
     propose --from-batch` reads the C a record judged and refuses one that changed since.
2. **The done gate**, as 07-48 Task 4 steps 2-6, with `48c-` names:
   - the host suite in the background, then the container suite;
   - then the container gate --all into 48c-gate-all-after.log, diffed with 48c-gate-all-before.log into
     48c-gate-all.diff, every line explained and the newly passing functions listed (none expected);
   - config/ and the feed unchanged, else STOP;
   - fix-forward with `fix(07-48c): ...` after a failing test.
3. **`/code-review`** on `git diff <48c-head-before>...HEAD`, at the default level, never max or ultra. Each finding
   is fixed (test first) or recorded with its reason. If this executor cannot run it, record "code review deferred
   to the orchestrator" with the command.
4. **The SUMMARY**, .planning/phases/07-mechanics-first-decompilation/07-48c-SUMMARY.md. It holds:
   - the verb as built and the record keys;
   - the queue compatibility evidence (44 entries, byte-identical round trip);
   - the RED assessments, the suites and gate results, the gate diff, and the Review section;
   - under Deviations: any fix-forward;
   - the Task 2b hand-off, below.

   Commit it alone: `docs(07-48c): complete the batch-sourced flag proposals plan`.
5. **The Task 2b hand-off**, written into the SUMMARY for the orchestrator. Nothing here is run by the executor:
   1. re-judge the 18 rows (the 13 converter rows from the inferred arm, and ufo2p 0x00034FE0, 0x000483A0,
      0x0005FBD0, tacp 0x00095800, 0x00098300, plus tacp 0x0001E860 if 07-48b placed it there) with `uv run
      reverseapoc batch <dir> --cell "-4r -oneatx -s -fpi" --out build/<...>.jsonl`, the converter rows and the
      agent rows as separate runs because each run takes one author;
   2. `uv run reverseapoc flags propose --from-batch <file> --cell "-4r -oneatx -s -fpi" --author "<who>"` on the
      host, then `docker compose run --rm build bash -lc "uv sync --locked && uv run reverseapoc flags regate <ids>"`;
   3. a proposal whose regate breaks a matched sibling is reported, not pushed;
   4. commit the queue entries following `git log -- config/cflags-proposals.toml`; never `flags approve`; the owner
      approves.
  </action>
  <verify>
    <automated>E=build/gate/07-evidence; grep -qx "exit=0" $E/48c-host.log && grep -qx "exit=0" $E/48c-ruff.log && grep -qx "exit=0" $E/48c-container.log && grep -qx "exit=0" $E/48c-gate-all-after.log && grep -q "^OK UFO2P.EXE sha1 " $E/48c-gate-all-after.log && grep -q "^OK TACP.EXE sha1 " $E/48c-gate-all-after.log && ! grep -q "MISMATCH" $E/48c-gate-all-after.log && ! grep "^SKIPPED" $E/48c-host.log | grep -vqE "GHIDRA_INSTALL_DIR|run in the container|only inside the container|POSIX-only|Windows file names cannot hold|non-UTF-8 byte names|symlink creation needs privileges on this host" && ! grep "^SKIPPED" $E/48c-container.log | grep -vq "Windows-only: msvcrt lock path" && test "$(grep -c -- '--from-batch' docs/workflow.md)" -ge 1 && test "$(grep -c 'source_sha256' docs/toolchain.md)" -ge 1 && test -f .planning/phases/07-mechanics-first-decompilation/07-48c-SUMMARY.md && cmp config/cflags-proposals.toml $E/48c-queue-before.toml && uv run reverseapoc check-orig && git diff --quiet "$(cat $E/48c-head-before.txt)" HEAD -- config/ src/ decomphub.progress.json configure.py && S=$(git status --porcelain) && test -z "$(printf '%s\n' "$S" | grep -v '^ M .planning/config.json$' | grep -v '^$')"</automated>
    <fails_when>Non-zero exit in any of these cases: a suite, ruff or the container gate failed; a SHA-1 line is missing or a MISMATCH appears; a skip reason outside R-A appears; the docs do not name `--from-batch` or `source_sha256` (both absent at 8943cce); the SUMMARY is missing; the committed queue, config/, src/, the feed or configure.py changed; `check-orig` fails; or the tree is dirty beyond R-C's flag</fails_when>
    <human-check>The orchestrator re-runs the reported checks (end-of-phase mode) before it fast-forwards main and starts Task 2b</human-check>
  </verify>
  <acceptance_criteria>
    - 48c-host.head and 48c-container.head equal the HEAD before the SUMMARY commit, or a later fix-forward commit
    - the SUMMARY holds the Task 2b hand-off with the exact commands, a Review section (or the deferral line), and names every line of 48c-gate-all.diff or says it is empty
  </acceptance_criteria>
  <done>The batch input to the D-12 queue is documented and green in both suites and the whole-EXE gate, and Task 2b can start.</done>
</task>

</tasks>

## Artifacts this phase produces

- `tools/reverseapoc/flags.py`: BATCH, AUTHORS, OPTIONAL_FIELDS, `Proposal.author`, the queue reader and writer for
  optional keys, `propose_batch` and its helpers, the batch landing trailer, MATCHED_BY_KEY and BY_HAND_ATTEMPTS.
- `tools/reverseapoc/cli.py`: `flags propose --from-batch/--cell/--author`, and the batch verb's source keys.
- `tools/reverseapoc/batch.py`: `with_source`.
- Tests: `tests/test_flags.py`, `tests/test_batch.py` and `tests/test_cli_batch.py`.
- Docs: `docs/workflow.md` and `docs/toolchain.md`.
- `.planning/phases/07-mechanics-first-decompilation/07-48c-SUMMARY.md`, with the Task 2b hand-off.
- Gitignored evidence in build/gate/07-evidence/:
  - the baselines: `48c-head-before.txt`, `48c-queue-before.toml`, `48c-gate-all-before.log`;
  - the RED records: `48c-red.xml`, `48c-red-record.json`, `48c-red2.xml`, `48c-red2-record.json`;
  - the regate proof: `48c-flags-before.py`, `48c-regate-before.txt`, `48c-regate-after.txt`;
  - the notes `48c-notes.txt`;
  - the done gate: `48c-host.head/.log`, `48c-ruff.log`, `48c-container.head/.log`, `48c-container-build.log`,
    `48c-gate-all-after.log`, `48c-gate-all.diff`.

## Sequencing and follow-ups (for the orchestrator)

- **Task 2b** (not a GSD plan) starts after this plan is on main, with the hand-off in the SUMMARY.
- **A declaration clash** between a row's C and its unit shows as a `failed` proposal at regate, with the compile
  error as its reason. Task 2b then edits the row's batch source so its declarations agree with the unit's, re-runs
  `reverseapoc batch`, and proposes again. That new run's evidence is a different results file, so it is not a
  duplicate once the failed proposal is rejected.
- **The stats classes are unchanged.** A batch landing classes `human-written` until the owner rules a converter
  class.

## Flagged assumptions

- **Each batch run has one author.** Converter rows and agent rows go in separate `reverseapoc batch` runs. A mixed
  file is proposed under one author only if the orchestrator says so, so Task 2b splits them.
- **Grouping by unit within a run.** If two of the 18 rows share a unit, they become one proposal. Rows of one unit
  from two different runs cannot both be open; the second is skipped until the first is landed, rejected or failed.

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| batch results and C under build/ -> the committed queue | gitignored evidence becomes a committed proposal |
| the queue -> config/cflags.txt | only the owner's `flags approve` crosses it (D-12) |
| proposal source -> commit trailers -> stats | who wrote the C decides the match class and AGT-11 |
| the committed queue's 44 entries -> the new reader | the schema change must not reinterpret history |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-07-148 | Elevation of privilege | a batch proposal changing config/cflags.txt or landing without the owner | high | mitigate | propose_batch writes only the queue and build/flags/ (a test asserts cflags.txt unchanged); approve keeps every gate (owner name, drive lock, claim env, regated exit 0 on today's cflags sha, lint, container gate) for both sources; executors never run approve |
| T-07-149 | Tampering | a results file or source outside build/, or a C file edited after the batch judged it | medium | mitigate | `_build_path` on the results path and on each record's source; the source's LF sha256 must equal the record's; each is a FlagsError with nothing written, under a negative test |
| T-07-150 | Repudiation | wrong attribution: an unknown author, or a converter or subagent match counted as an unattended driver match (AGT-11) | medium | mitigate | AUTHORS is closed (queue validation and CLI choices); a batch landing carries `Matched-By: <author>` only, with no driver Matched-By and no attempt co-authors (negative test); gate attempts 0 |
| T-07-151 | Tampering | the schema change reinterpreting or rewriting the 44 committed entries | medium | mitigate | `author` optional and omitted when empty; FIELDS stays the required keys; the committed queue round-trips byte for byte under a test, and `cmp` against the baseline copy |
| T-07-152 | Information disclosure | game bytes in the queue, records or tests | medium | mitigate | the queue stays printable ASCII names, flags, paths and SHA-256s; records add a path and a SHA-256 only; candidates live in gitignored build/flags/; tests use made-up C |
| T-07-SC | Tampering | package installs | low | accept | no package is installed |
</threat_model>

<verification>
- On a synthetic repo: `flags propose --from-batch` turns a cell's exact records into one proposal per unit, with the
  unit candidate, the author and the results file as evidence. Each of the design's negatives is refused or skipped
  for its reason, a re-run is idempotent, and config/cflags.txt is untouched.
- The committed queue's 44 entries parse and round-trip byte for byte. A batch proposal's synthetic approval commit
  carries `Matched-By: <author>` and nothing that `stats` would count as unattended. regate is byte-identical.
- Both suites and the container gate --all are green, and the committed queue, config/, src/ and the feed are
  unchanged.
</verification>

<success_criteria>
- The design's "Plan 07-48c" is implemented: a batch input to the D-12 queue (D-12, D-32), the author trailer at
  approval, regate unchanged, and the five negatives.
- Task 2b can propose the 18 `-oneatx` rows for the owner's approval, each re-proved over its whole unit by `flags
  regate` (DEC-03).
</success_criteria>

<output>
Create `.planning/phases/07-mechanics-first-decompilation/07-48c-SUMMARY.md` in Task 3, from
build/gate/07-evidence/48c-notes.txt and the evidence files, with the Task 2b hand-off.
</output>
