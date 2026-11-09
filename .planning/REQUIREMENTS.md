# Requirements: ReverseApoc

**Defined:** 2026-10-19
**Core Value:** Every match is proven by a deterministic oracle (rebuilt EXE SHA-1 identical to the original, objdiff 100% for the function), never by an agent's own judgement.

Sources: the verification gates in `docs/workflow.md` (Milestone 1 roadmap), the design spec, and `.planning/research/FEATURES.md` (RT/CID/SPL/RPT/AGT ids reused from there). "The owner" is the human maintainer; "a contributor" is anyone with their own game and compiler files.

## v1 Requirements (Milestone 1)

### Hygiene and safety (Phase 1, built before GSD was set up)

- [x] **HYG-01**: `git ls-files` contains no game file, disassembly, build output, compiler binary, `.env` or API key; `.gitignore`/`.dockerignore` exclude `orig/`, `third_party/`, `asm/`, `build/`, `.env` and executable/image types
- [x] **HYG-02**: All plugins enabled in `.claude/settings.json` are installed at project scope (`claude plugin list`) and GSD is installed project-local for Claude Code only, with `/gsd-health` clean
- [x] **HYG-03**: `CLAUDE.md` stays under 150 lines and states the hard rules, commands and done gate; per-path rules live in `.claude/rules/`
- [x] **HYG-04**: Docs skeleton exists (`docs/toolchain.md`, `coding-style.md`, `matching.md`, `learnings.md`, `tools.md`, `legal.md`, `workflow.md`, `ceremonies.md`), plus README, `.recomp.json` and the approved design spec

### Container and target ingest (Phase 2, built before GSD was set up)

- [x] **ING-01**: A contributor can build a Docker image with Python 3.14 + uv, ninja, objdiff-cli, wibo 1.2.0 and the Open Watcom v2 tools, with `orig/` and `third_party/watcom/` mounted read-only and never baked in
- [x] **ING-02**: A contributor can run `uv run reverseapoc ingest` to copy their EXEs into `orig/` and `uv run reverseapoc check-orig` to verify them against `config/targets.toml` (size, CRC32, md5, sha1)
- [x] **ING-03**: `uv run reverseapoc parse-le` reproduces the scanned layout of both EXEs (stub 0x352A4, LE header 0x37F34, two objects at their bases, all fixups internal)
- [x] **ING-04**: `uv run pytest -q` and `uv run ruff check .` pass on the host and `docker compose run --rm test` passes in the container; real-file tests skip unless `orig/` exists
- [x] **ING-05**: CI runs tests and ruff on push without any game file

### Byte-identical round trip (Phase 3)

- [x] **RT-01**: The rebuild reassembles each EXE from decomposed parts (untouched prefix regions plus per-object images re-paged through the LE page map), not from a file copy
- [x] **RT-02**: A splice API writes bytes at a linear address into a copy of the original and refuses writes outside page data and any change of file length; straddling fields are handled in flat address space
- [x] **RT-03**: A CLI verb rebuilds UFO2P.EXE, TACP.EXE and SMKP.EXE into `build/` and checks the whole-EXE SHA-1 against `config/targets.toml`; `cmp` against `orig/` is silent
- [x] **RT-04**: Negative tests prove the gate can fail: a one-byte mutation (mid-page, page edge, short last page, across a page boundary) changes the SHA-1 and the failure names the offset
- [x] **RT-05**: A byte-region map tiles every byte of each file (extender, MZ stub, LE header/loader section, fixup section, padding, pages, 27-byte trailer) and the LE edge cases on the real files are confirmed and documented (page types, straddling fixups, trailer)

### Compiler identification (Phase 4)

- [x] **CID-01**: The original Watcom compiler runs under wibo 1.2.0 in Docker for each owner-supplied version (10.5, 10.6, 11.0), mounted read-only from `third_party/watcom/` (11.0: native `BINNT\wcc386.exe`; 10.5/10.6: `BINNT\wcc386.exe` loads the LX `BINW\WCC386.EXE`, so `binw/` is required too)
- [x] **CID-02**: A compiler wrapper keyed by `compiler@version` plus a per-file flags table (`config/cflags.txt`) selects the compiler and flags per source file
- [x] **CID-03**: The mosura codegen probe compiled with each version locates its idioms in both code objects (non-library code)
- [x] **CID-04**: Linked CLIB3R/MATH3R runtime modules match byte for byte (masked) against one version's `LIB386`
- [x] **CID-05**: Compiler version and default flags are recorded in `docs/toolchain.md` with per-flag evidence, per EXE
- [x] **CID-06**: A C vs C++ scan (vtables, `__wcpp_` routines, XI/YI segments) confirms `wcc386` vs `wpp386`

### Split and first matches (Phase 5)

- [x] **SPL-01**: Ghidra 12.1.4 (headless, JDK 21) with one LE loader in the Docker image exports a function list to `config/<exe>/functions.csv`
- [x] **SPL-02**: An independent capstone discovery pass cross-checks the Ghidra function list and boundary disagreements are reconciled
- [x] **SPL-03**: Functions are grouped into translation units with per-EXE config under `config/<exe>/`
- [x] **SPL-04**: A stub convention keeps original bytes for every unmatched function
- [x] **SPL-05**: Per-function disassembly is generated from `orig/` into gitignored `asm/` by script
- [x] **SPL-06**: `configure.py` writes `build.ninja`, `objdiff.json` and `compile_commands.json` for the Watcom-under-wibo compile path
- [x] **SPL-07**: `omf2elf.py` converts Watcom OMF to ELF32 (COMDAT, LIDATA, FIXUPP threads, BAKPAT, CEXTDEF) with pytest
- [x] **SPL-08**: Target ELF objects are cut from the LE with relocations rebuilt from LE fixups
- [x] **SPL-09**: A relocation check beyond objdiff verifies every non-relocated byte, equal length, every `call rel32` target and every absolute fixup target
- [x] **SPL-10**: Splicing a matched function keeps the original link-time value at each fixup site after its target is checked
- [x] **SPL-11**: A single-unit `check` tool prints per-function match (objdiff %, reloc check, splice SHA-1)
- [x] **SPL-12**: A C89 lint gate (`clang -fsyntax-only -std=gnu89 -Werror=declaration-after-statement` with a Watcom compat header) runs on `src/`
- [x] **SPL-13**: One function per EXE compiles, matches with relocations checked, splices back, both EXEs stay SHA-1 identical and objdiff shows 100%

### Reporting (Phase 6)

- [x] **RPT-01**: A committed per-function status table is written only by the local gate
- [x] **RPT-02**: `progress.py` (stdlib) writes `progress.json`, a treemap `progress.svg` and a shields endpoint JSON
- [x] **RPT-03**: A GitHub Pages workflow publishes the mosaic, badge and raw JSON on push to `main`
- [x] **RPT-04**: An objdiff-shaped `report.json` is uploaded as a `<VERSION>_report` artifact for recomp.fyi
- [x] **RPT-05**: `.recomp.json` is updated and the decomphub.com submission is done once the repo is public

### Agent pilot (Phase 6)

- [x] **AGT-01**: A per-function driver runs one fresh `claude -p "/goal ..."` session per function, re-verifies compile/compare/splice/SHA-1 itself, and commits one function per commit or resets
- [x] **AGT-02**: Attempts are capped at 3-5 per function per pass; capped functions go to a difficult list and are re-queued later
- [x] **AGT-03**: Each attempt records a tri-state outcome (MATCHED / PARTIAL / GAVE_UP) with turns, tokens, time and verifier output
- [x] **AGT-04**: The driver backs off on usage limits and auth/credit errors and caps functions per night
- [x] **AGT-05**: Claude Code guardrail hooks block edits to `orig/`, hash manifests, build/verify scripts during matching sessions, inline asm and code-emitting `#pragma aux` in `src/`, and builds that bypass the verify script; hooks are tested with pytest
- [x] **AGT-06**: A zero-regression gate keeps every previously matched function matching and both EXEs SHA-1 identical after every commit
- [x] **AGT-07**: An easiest-first scorer, run by the driver, picks the next function
- [x] **AGT-08**: A per-function context pack (target asm, callers/callees, headers, Ghidra draft, notes) is supplied to each attempt
- [x] **AGT-09**: A `watcom-decomp` project skill documents calling convention, flags, C89 rules, pragma policy and relocation rules
- [x] **AGT-10**: decomp.wtf v0.10.6 fork mode runs pinned in WSL2 as a subprocess, if the Phase 6 stub-convention spike passes (otherwise a minimal own agent layer)
- [ ] **AGT-11**: The pilot matches 10 easy functions unattended with zero regressions and both EXEs identical

### Mechanics-first decompilation (Phase 7)

- [ ] **DEC-01**: `config/mechanics.toml` maps each OpenApoc checklist item the decomp can answer (#263, #264, #265, #997) to its EXE and the functions behind it, located from UI strings and data-table cross-references; the owner signs the list off
- [ ] **DEC-02**: The driver works through the list callees first, with claims so parallel agents never take the same function and a single owner of the shared naming state (symbols file)
- [ ] **DEC-03**: Every function in Tier 1's must-match set (Tier 1's entry functions plus their callees down to the signed hub rule, minus owner-signed asm rows) matches (objdiff 100%, relocation check passes), both EXEs stay SHA-1 identical with zero regressions, and Tiers 1-4 are located and signed off in `config/mechanics.toml`; Tiers 2-4 keep matching in Milestone 2 (owner ruling D-05, 2026-10-26, refined by D-22, D-23, D-31)
- [ ] **DEC-04**: A stdlib `reverseapoc readlint` (TDD) fails on placeholder names (`FUN_`, `sub_`, `DAT_`), functions without a header comment, and unnamed struct fields or magic constants in matched units; the tool decides readability, not the agent
- [ ] **DEC-05**: The progress page shows coverage per checklist item for both the must-match set and the full closure (D-22), asm rows as their own group (D-23), and for tiers that are located but not matched yet their located and signed-off state (owner ruling D-05, 2026-10-26)
- [ ] **DEC-06**: The Phase 6 usage caps and per-attempt logging carry over, and nightly totals (turns, tokens, time) are recorded
- [ ] **DEC-07**: A stdlib `reverseapoc stats` (TDD) reads `progress/attempts.jsonl` and the git commit trailers and reports match rate by function size, attempts per match, turns, tokens, cost and time per matched function, regressions the gate stopped, and guardrail-hook blocks; every match is classed `unattended`, `human-hints` or `human-written` (from the `Matched-By` trailer and owner notes in manual packs), and from Phase 7 on each attempt record carries its hook-block count. The numbers are kept for a later paper (owner, 2026-10-25)

### FNV-inspired matching pipeline (Phase 7.2)

- [ ] **PIPE-01**: Schema-3 attempt record (effort, harness, backend, duration_ms, cost_source, giveup, a held state and a landing record); Haiku and Sonnet ids in the three model tables; `stats --run` with a model x size-bucket table; every committed line still validates (07.2-CONTEXT D-16, D-26)
- [ ] **PIPE-02**: `attempt giveup` validates a session-written `giveup.json` (survey categories); the record carries the giveup; the context pack gains an "earlier give-ups" section and the earlier best C within the 24 KB cap (D-04, D-26)
- [ ] **PIPE-03**: `attempt plan` validates `plan.json` (FRAME/SLOT/CALL/REGION covering 0..size); `attempt check` refuses with exit 2, using no run, without a plan or a `check-note.json` (change/why/expect); the observed outcome is recorded by the tool (D-01..D-03, D-26)
- [ ] **PIPE-04**: A stdlib `reverseapoc causes` reports per-try build-fail/mismatch/match rates, Watcom error codes, mismatch classes and shared-header gaps ranked by functions blocked, over drive run dirs (999.8)
- [ ] **PIPE-05**: Region board: per-0x100 region difference counts in check JSON (addresses only), and at 256 B and up the board plus the closest saved draft per region (999.7)
- [ ] **PIPE-06**: `drive --night-model`, `--picks FILE`, `--dry-run --stratify A,B,C --write-picks FILE`, a hold mode that never lands, and `drive --land-held RUN...` landing each function once from the cheapest arm through the normal land and gate (D-17)
- [ ] **PIPE-07**: readlint RL07 requires `/* src: TAG 0xADDR (confidence: high|medium|low) */` on every identifier the readability pass renames from a placeholder, rejects a malformed marker, and a test proves the objects byte-identical; the watcom-readability skill learns the form (D-14, D-15)
- [ ] **PIPE-08**: Base-vs-head CI: `match.yml` (disabled by default, label-gated, pull_request_target with main's tools, PR as data, inside the Docker image, no orig/), a tested `reverseapoc compare-objects`, and `docs/ci.md`; the owner registers the runner (D-06..D-09, D-23)
- [ ] **PIPE-09**: The watcom-decomp skill teaches plan, notes, giveup and the region board, through superpowers:writing-skills, RED first (D-05)
- [ ] **PIPE-10**: Evidence docs 9a-9d (Codex audit, permuter 0 of 40, bytes-first confirmation, our per-try rates beside FNV's) and docs/tools.md rows for every new backend and CLI (D-19)
- [ ] **PIPE-11**: `config/driver/backends.toml`, per-arm session env, the token-leak guard, an explicit `--allow-egress` per hosted arm, the docs/legal.md backends section, and an endpoint preflight (D-10..D-12, D-26)
- [ ] **PIPE-12**: A Codex CLI harness adapter (GPT-6 Luna, GPT-6.1 Sol on the owner's ChatGPT Plus) with its own canary, audit of every command run, and the scoped runtime exception written into CLAUDE.md and .claude/rules/workflow.md (D-13, D-26)
- [ ] **PIPE-13**: Slot model and lifter follow-ups from the Phase 7.1 review, measured on the converter curve (folded todo)
- [ ] **PIPE-14**: An Antigravity CLI (agy) harness adapter for Gemini on the owner's Google AI Plus, with a quota canary, per-session settings first, and the OpenRouter fallback (D-21, D-24, D-25)
- [ ] **PIPE-15**: Multi-arm drive: `drive --arm <name>=<workers>` runs several arms in parallel in one process, each with its own run id, pick queue and usage pause (D-22, D-26)
- [ ] **PIPE-16**: Phase gate: host and container suites green, `gate --all` and `ninja verify` exit 0, `drive --canary` passes, matched bytes unchanged (D-20)

### Clean-room specs (Phase 8)

- [ ] **SPEC-01**: A spec template `specs/_template/spec.md` in OpenSpec format (`## Purpose`, `## Requirements`, `### Requirement:` with SHALL/MUST, `#### Scenario:` with WHEN/THEN) plus OpenApoc issue, constants and formulas, functions (EXE + address), evidence, sources and a status ladder `drafted -> cited -> backed-by-matched-code -> dosbox-verified -> reviewed-by-openapoc`
- [ ] **SPEC-02**: A stdlib `reverseapoc speclint` (TDD) enforces the OpenSpec validate rules in strict mode, that cited addresses exist in `config/<exe>/functions.csv`, that `backed-by-matched-code` matches the gate-written status table, that `dosbox-verified` names a test, that no fenced C or text copied from `src/` appears, and that every source has URL, access date and wiki revid
- [ ] **SPEC-03**: A stdlib `reverseapoc wikifetch` reads single pages through the MediaWiki API with a descriptive User-Agent, at least 10 s between requests per host, the revid recorded, and a gitignored cache; wiki text is never committed
- [ ] **SPEC-04**: An `apoc-spec` project skill in `.claude/skills/apoc-spec/` teaches an agent to fill the template from matched code and sources
- [ ] **SPEC-05**: `docs/clean-room.md` states the author/implementer split, the human review rule and the conduct towards OpenApoc, and links the OpenApoc Discord messages on clean-room practice
- [ ] **SPEC-06**: `specs/LICENSE` is CC0-1.0, named in `docs/legal.md` and `README.md`, with the rule that community facts are re-expressed in our own words and cited, never copied
- [ ] **SPEC-07**: `specs/claims.md` inventories mechanics claims from UFOpaedia, Wikibooks, StrategyWiki and the OpenApoc Discord, paraphrased and linked, each tied to a checklist item with a verdict (confirmed, refuted, refined) or "none found"
- [ ] **SPEC-08**: Every target in `config/mechanics.toml` has a spec that passes `speclint` and reaches at least `backed-by-matched-code`
- [ ] **SPEC-09**: The owner reviews every spec; a review line in the spec records who and when
- [ ] **SPEC-10**: `docs/findings/bugs.md`, `cut-content.md`, `cheats-and-easter-eggs.md` and `learning-ai.md` exist and hold what is known when Phase 8 runs: community reports (UFOpaedia through `wikifetch` with revid, OpenApoc Discord by message link, other sources by URL and access date), paraphrased under the SPEC-06 source rules, plus findings from Phase 7's matched code and `docs/learnings.md`. Each entry names the EXE (UFO2P or TACP), the build, the function address where known, and a status: `reported`, `confirmed` (the function is matched per the gate-written status table), `refuted`, or `not seen in the code matched so far`. An item that fits two files lives in one and is linked from the other. Each file states that later phases and milestones keep it current (owner, 2026-10-25)

## v2 Requirements

Deferred to a later milestone. Tracked but not in the current roadmap.

- **TWIN-01**: UFO2P <-> TACP twin matching (normalized-asm hashes, then opcode Levenshtein)
- **AUTO-01**: Trivial-family auto-matcher (return-constant, forwarders), verified before landing
- **NAME-01**: Function names from diagnostic strings
- **LE-01**: Full LE rewrite / relinkable build (reopen trigger: a matched function changes size)
- **DATA-01**: Data/rodata placement matching
- **CD-01**: CD v1.00 builds as a second matching target
- **SMKP-01**: SMKP.EXE (Smacker player)
- **SIM-01**: Embedding-based similarity retrieval, parallel agents, variant beam search

## Out of Scope

| Feature | Reason |
|---------|--------|
| A playable port / platform layer / SDL | Anti-goal [Owner]: ReverseApoc documents the engine for OpenApoc |
| Modern C++ rewrite or modernizing matched C | C89 for Watcom 10.x; modern idioms break matching |
| Committing game bytes, disassembly or compiler binaries | Anti-goal [Owner]; legal |
| Agents judging their own matches or editing `orig/`, manifests, build scripts | Anti-goal: the driver and the build decide |
| Inline asm or asm stand-ins counted as matches | Matching must come from C |
| Open Watcom `wcc386` for matching | Does not match classic 10.x codegen |
| Compiler or game baked into the Docker image | Bring your own files [Owner] |
| IDA | Cloud decompiler, no LE loader |
| Win9x release, XCOMAPOC.EXE, SETUP.EXE | Non-goals for Milestone 1 |
| decomp.wtf from-scratch mode, permuter, m2c | No LE/x86 path |
| Contacting OpenApoc about specs, or sending specs or PRs to OpenApoc | Owner decision 2026-10-21: not in Milestone 1; the specs stay in this repo until after the milestone |
| Clean-room implementation in OpenApoc | Done later by implementers who see only `specs/`, never `src/` |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| HYG-01 | Phase 1 | Complete |
| HYG-02 | Phase 1 | Complete |
| HYG-03 | Phase 1 | Complete |
| HYG-04 | Phase 1 | Complete |
| ING-01 | Phase 2 | Complete |
| ING-02 | Phase 2 | Complete |
| ING-03 | Phase 2 | Complete |
| ING-04 | Phase 2 | Complete |
| ING-05 | Phase 2 | Complete |
| RT-01 | Phase 3 | Complete |
| RT-02 | Phase 3 | Complete |
| RT-03 | Phase 3 | Complete |
| RT-04 | Phase 3 | Complete |
| RT-05 | Phase 3 | Complete |
| CID-01 | Phase 4 | Complete |
| CID-02 | Phase 4 | Complete |
| CID-03 | Phase 4 | Complete |
| CID-04 | Phase 4 | Complete |
| CID-05 | Phase 4 | Complete |
| CID-06 | Phase 4 | Complete |
| SPL-01 | Phase 5 | Complete |
| SPL-02 | Phase 5 | Complete |
| SPL-03 | Phase 5 | Complete |
| SPL-04 | Phase 5 | Complete |
| SPL-05 | Phase 5 | Complete |
| SPL-06 | Phase 5 | Complete |
| SPL-07 | Phase 5 | Complete |
| SPL-08 | Phase 5 | Complete |
| SPL-09 | Phase 5 | Complete |
| SPL-10 | Phase 5 | Complete |
| SPL-11 | Phase 5 | Complete |
| SPL-12 | Phase 5 | Complete |
| SPL-13 | Phase 5 | Complete |
| RPT-01 | Phase 6 | Complete |
| RPT-02 | Phase 6 | Complete |
| RPT-03 | Phase 6 | Complete |
| RPT-04 | Phase 6 | Complete |
| RPT-05 | Phase 6 | Complete |
| AGT-01 | Phase 6 | Complete |
| AGT-02 | Phase 6 | Complete |
| AGT-03 | Phase 6 | Complete |
| AGT-04 | Phase 6 | Complete |
| AGT-05 | Phase 6 | Complete |
| AGT-06 | Phase 6 | Complete |
| AGT-07 | Phase 6 | Complete |
| AGT-08 | Phase 6 | Complete |
| AGT-09 | Phase 6 | Complete |
| AGT-10 | Phase 6 | Complete |
| AGT-11 | Phase 6 | Partial (3/10, owner-accepted 2026-10-26; the 10-match target carries to Phase 7) |
| DEC-01 | Phase 7 | Pending |
| DEC-02 | Phase 7 | Pending |
| DEC-03 | Phase 7 | Pending |
| DEC-04 | Phase 7 | Pending |
| DEC-05 | Phase 7 | Pending |
| DEC-06 | Phase 7 | Pending |
| DEC-07 | Phase 7 | Pending |
| PIPE-01 | Phase 7.2 | Pending |
| PIPE-02 | Phase 7.2 | Pending |
| PIPE-03 | Phase 7.2 | Pending |
| PIPE-04 | Phase 7.2 | Pending |
| PIPE-05 | Phase 7.2 | Pending |
| PIPE-06 | Phase 7.2 | Pending |
| PIPE-07 | Phase 7.2 | Pending |
| PIPE-08 | Phase 7.2 | Pending |
| PIPE-09 | Phase 7.2 | Pending |
| PIPE-10 | Phase 7.2 | Pending |
| PIPE-11 | Phase 7.2 | Pending |
| PIPE-12 | Phase 7.2 | Pending |
| PIPE-13 | Phase 7.2 | Pending |
| PIPE-14 | Phase 7.2 | Pending |
| PIPE-15 | Phase 7.2 | Pending |
| PIPE-16 | Phase 7.2 | Pending |
| SPEC-01 | Phase 8 | Pending |
| SPEC-02 | Phase 8 | Pending |
| SPEC-03 | Phase 8 | Pending |
| SPEC-04 | Phase 8 | Pending |
| SPEC-05 | Phase 8 | Pending |
| SPEC-06 | Phase 8 | Pending |
| SPEC-07 | Phase 8 | Pending |
| SPEC-08 | Phase 8 | Pending |
| SPEC-09 | Phase 8 | Pending |
| SPEC-10 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 82 total
- Mapped to phases: 82
- Unmapped: 0 ✓

---
*Requirements defined: 2026-10-19*
*Last updated: 2026-11-09 after adding PIPE-01..PIPE-16 (Phase 7.2, FNV-inspired matching pipeline)*
