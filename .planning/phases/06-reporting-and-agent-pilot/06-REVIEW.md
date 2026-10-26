---
phase: 06-reporting-and-agent-pilot
reviewed: 2026-10-26T00:00:00Z
depth: standard
files_reviewed: 111
files_reviewed_list:
  - .claude/rules/src.md
  - .claude/settings.json
  - .claude/skills/watcom-decomp/SKILL.md
  - .dockerignore
  - .github/workflows/ci.yml
  - .github/workflows/pages.yml
  - .gitignore
  - .recomp.json
  - README.md
  - config/driver/claude-settings.json
  - config/tacp/functions.csv
  - config/tacp/status.csv
  - config/ufo2p/functions.csv
  - config/ufo2p/status.csv
  - config/watcom.toml
  - configure.py
  - decomphub.progress.json
  - docker/Dockerfile
  - docs/DECOMPHUB_VERIFICATION.md
  - docs/coding-style.md
  - docs/learnings.md
  - docs/legal.md
  - docs/listings.md
  - docs/matching.md
  - docs/superpowers/specs/2026-10-19-reverseapoc-design.md
  - docs/toolchain.md
  - docs/tools.md
  - docs/workflow.md
  - progress/attempts.jsonl
  - src/tacp/u_00054f20.c
  - src/tacp/u_0006ee30.c
  - src/ufo2p/u_00089980.c
  - tests/fakeclaude.py
  - tests/fixtures/stream/canary_fail.jsonl
  - tests/fixtures/stream/canary_pass.jsonl
  - tests/fixtures/stream/canary_unknown_error.jsonl
  - tests/fixtures/stream/canary_wrapper_denied.jsonl
  - tests/relocpair.py
  - tests/test_asm.py
  - tests/test_attempt_wrapper.py
  - tests/test_attempts_schema.py
  - tests/test_cc_log.py
  - tests/test_check.py
  - tests/test_check_tables_real.py
  - tests/test_cli.py
  - tests/test_compiler.py
  - tests/test_compiler_real.py
  - tests/test_configure.py
  - tests/test_contextpack.py
  - tests/test_discover.py
  - tests/test_drift.py
  - tests/test_drive.py
  - tests/test_drive_real.py
  - tests/test_driver.py
  - tests/test_driver_pick.py
  - tests/test_fileio.py
  - tests/test_functions.py
  - tests/test_functions_real.py
  - tests/test_gate.py
  - tests/test_gate_real.py
  - tests/test_ghidra.py
  - tests/test_hooks.py
  - tests/test_hygiene.py
  - tests/test_land.py
  - tests/test_le.py
  - tests/test_lint.py
  - tests/test_listings.py
  - tests/test_objdiff_real.py
  - tests/test_omf2elf.py
  - tests/test_progress.py
  - tests/test_relocs.py
  - tests/test_report_shape.py
  - tests/test_score.py
  - tests/test_session.py
  - tests/test_skill.py
  - tests/test_status.py
  - tests/test_streamjson.py
  - tests/test_stub_real.py
  - tests/test_symbols.py
  - tests/test_target.py
  - tests/test_treemap.py
  - tests/test_units.py
  - tests/test_workflows.py
  - tools/progress.py
  - tools/reverseapoc/asm.py
  - tools/reverseapoc/attempt.py
  - tools/reverseapoc/check.py
  - tools/reverseapoc/cli.py
  - tools/reverseapoc/compiler.py
  - tools/reverseapoc/contextpack.py
  - tools/reverseapoc/discover.py
  - tools/reverseapoc/driver.py
  - tools/reverseapoc/fileio.py
  - tools/reverseapoc/functions.py
  - tools/reverseapoc/gate.py
  - tools/reverseapoc/ghidra_scripts/ExportDrafts.java
  - tools/reverseapoc/hooks.py
  - tools/reverseapoc/land.py
  - tools/reverseapoc/libmatch.py
  - tools/reverseapoc/lint.py
  - tools/reverseapoc/omf2elf.py
  - tools/reverseapoc/picker.py
  - tools/reverseapoc/relocs.py
  - tools/reverseapoc/score.py
  - tools/reverseapoc/session.py
  - tools/reverseapoc/splice.py
  - tools/reverseapoc/status.py
  - tools/reverseapoc/streamjson.py
  - tools/reverseapoc/symbols.py
  - tools/reverseapoc/target.py
  - tools/reverseapoc/x86.py
findings:
  critical: 2
  warning: 4
  info: 4
  total: 10
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-10-26
**Depth:** standard
**Files Reviewed:** 111
**Status:** issues_found

## Summary

The scope was 111 files. I read these in full and traced their call chains: the driver loop and verb
(`driver.py`), the hooks, the session runner, the stream-json classifier, the attempt wrapper,
`contextpack.py`, `picker.py`, `gate.py`, `status.py`, the `drive`/`attempt` CLI paths, the parts
of `check.py` and `compiler.py` they call, both workflows, both settings files, and the
`configure.py` diff. I covered the rest less closely: the three `src/*.c` diffs, the
gate-written tables, the docs (grepped for numeric and behavioural claims) and the tests
(scanned for weak patterns, with spot reads).

The hardened parts hold up under tracing. Path normalisation, deny-by-default for tools, the
Bash allowlist, containment and quarantine, and fail-closed stream classification all do what
their docstrings claim. Two defects remain at the system level:

1. The driver treats any gate exit 0 as a match for the **claimed** function. It never checks
   that the gate wrote a matched row for that start. A unit that already holds a matched
   function therefore produces a false MATCHED commit for an unmatched sibling.
2. The no-pragma and no-inline-asm guardrail only scans the text of the unit and of new
   headers. An `#include` of the agent-writable `notes.md`, or of any other path, brings
   unscanned text into the wcc386 compile. I confirmed on the host that the hook gives a unit
   with such an include no opinion, and that the notes path is allowlisted.

The known item (ci.yml checkout without `persist-credentials: false`) is WR-01.

## Critical Issues

### CR-01: A gate pass is recorded and committed as a match for the claimed function even when that function was never matched

**File:** `tools/reverseapoc/driver.py:1543-1562`, `tools/reverseapoc/driver.py:1576-1584`, `tools/reverseapoc/driver.py:1564-1574`
**Issue:** `_judge` returns the gate run. `_counted` (and `_salvage` for a LIMIT session) calls
`_commit_match` whenever `gate.exit_code == EXIT_OK`. The only extra check is that SHA-1s are
present for both EXEs. But `gate EXE/UNIT` exits 0 when every function the unit *defines in
C* passes (`CheckResult.ok`, check.py:818-822). INCLUDE_ASM stubs are ignored
(`stubs: ... not checked`), and gate writes rows only for `result.functions`
(gate.py:522-526).

Units hold many functions. `src/ufo2p/u_00089980.c` already defines matched
`func_0008A0E0` and `func_0008A100` next to 13 INCLUDE_ASM stubs. Take a pick such as
`func_0008A120` in that unit. A session that leaves the claimed function as a stub (gives up,
times out, or matches a *different* sibling instead) still gets gate exit 0. The driver then
appends a MATCHED attempt record, commits `feat(ufo2p): match func_0008A120 in u_00089980`
with "objdiff 100%" / "relocation ok" in the message, and increments `self.matched` toward
`target_matched`. status.csv correctly has no row for `func_0008A120`. That breaks
D-24's "only the gate decides a match": the gate decided a different fact. The attempt wrapper
already guards against exactly this (`_verdict`/`claimed_row`, attempt.py:272-285, 566-577),
but the driver does not reuse the guard. No test in `tests/test_driver.py` covers a passing
gate that wrote no row for the claimed start.
**Fix:** Require the claimed start among the gate's written matched rows before treating exit 0
as a match. A pass without it should be logged as GAVE_UP/PARTIAL from the checks summary, with
the pre-gate tables restored (the gate rewrote source_sha256 and the feed):
```python
def _claimed_matched(gate: GateRun, claim: _Claim) -> bool:
    want = f"0x{claim.pick.start:08X}"
    written = gate.doc.get("written") if isinstance(gate.doc, Mapping) else None
    return isinstance(written, list) and any(
        isinstance(w, Mapping) and w.get("start") == want and w.get("status") == STATUS_MATCHED
        for w in written)

# in _counted / _salvage:
if gate is not None and gate.exit_code == EXIT_OK and _claimed_matched(gate, claim):
    ...commit...
elif gate is not None and gate.exit_code == EXIT_OK:
    notes = self._restore_pre_gate()   # undo the gate's re-hash/feed rewrite
    ...record PARTIAL/GAVE_UP with notes...
```
Add a driver test: a unit with one already-matched function, a fake gate that exits 0 with
`written` naming only that function, and an assertion that the pick is not MATCHED and nothing
is committed.

### CR-02: The no-`#pragma` / no-inline-asm guardrail is bypassed by `#include` of an agent-writable, unscanned file

**File:** `tools/reverseapoc/hooks.py:443-470`, `tools/reverseapoc/hooks.py:546-563`, `tools/reverseapoc/hooks.py:643-666`
**Issue:** `asm_problem` scans only the text being written to `src/` or `include/`. The
matching layer also lets the session write its attempt's `notes.md` under `build/driver/`
(`matching_write_allowed`, D-46), and that content is never scanned. Nothing refuses an
`#include` directive pointing outside `include/`: not the hook, not configure's D-12 check,
not the lint (clang ignores unknown pragmas), and not the driver audit. A session can write
`#pragma aux func_X = 0x.. 0xC3` (or `_asm`) into notes.md and put
`#include "../../build/driver/<run>/<exe>/<func>/attempt-<n>/notes.md"` in the unit. The
quoted-include search relative to the source file then hands wcc386 the pragma, which
violates the hard rule "no inline assembly to force a match" (CLAUDE.md, `.claude/rules/src.md`,
D-16/D-18). The gate runs in the same bind-mounted tree before the reset, so it would pass. The
end-of-run `ninja -t clean && ninja verify` does not delete notes.md either. The committed unit
would include a gitignored file and fail to build from a fresh clone. I confirmed the hook side
on the host: `asm_problem('#include "common.h"\n#include "../../build/driver/r/ufo2p/func_000A3980/attempt-1/notes.md"\n...', any_pragma_aux=True, any_pragma=True)`
returns `None`, and `matching_write_allowed` allows that notes path. I did not run the
wcc386 side, because a container compile is out of bounds for this review. The same gap
admits `#include` of any tracked or build/ file, an absolute `/work/...` path, or
`<../build/...>` through `-i=include`. docs/workflow.md and SKILL.md state that the hook
blocks every pragma, which this gap makes untrue.
**Fix:** Refuse every `#include` in `src/` and `include/` whose operand is not a bare header
name. Enforce it in the hook (matching and always layers) and in configure's D-12 check, so the
gate refuses too:
```python
_INCLUDE = re.compile(r'\s*(#|%:)\s*include\s*(["<])([^">]*)[">]')
_HEADER_NAME = re.compile(r"[A-Za-z0-9_]+\.h")

def _include_problem(logical: str) -> str | None:
    m = _INCLUDE.match(logical)
    if m is not None and not _HEADER_NAME.fullmatch(m.group(3)):
        return f"an #include of {m.group(3)!r} (only a bare include/<name>.h is allowed)"
    return None
```
Call it from `_inline_asm` for each logical line. Also scan notes.md writes with
`asm_problem` (or refuse `#` directives in it), as defence in depth.

## Warnings

### WR-01: ci.yml checkout keeps the job token in `.git/config` while repository and PR code runs (known item from 06-24)

**File:** `.github/workflows/ci.yml:14`
**Issue:** `actions/checkout@v7` runs without `persist-credentials: false`, so `GITHUB_TOKEN` stays
in `.git/config` for `uv sync --locked`, `ruff` and `pytest`. On `pull_request` that code is the
PR's own (tests, conftest, any build hook). The token is limited to `contents: read`, so the
blast radius is small, but it is avoidable exposure, and it is inconsistent with pages.yml,
which sets the option. `tests/test_workflows.py::test_every_checkout_drops_its_credentials`
only reads pages.yml, so nothing pins this.
**Fix:**
```yaml
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
```
and extend the workflow test to both files (iterate over `ci.yml` and `pages.yml`).

### WR-02: The always-layer hook has no timeout/onFailure, so a slow or hung hook does not fail closed

**File:** `.claude/settings.json:20-31`, `config/driver/claude-settings.json:18-27`
**Issue:** The matching handler sets `"timeout": 120, "onFailure": "block"`. The always handler,
which guards `orig/`, `asm/`, `build/`, the hash manifests and inline asm for every interactive
and GSD session, sets neither in either file. A hook that runs past Claude Code's default timeout
(uv start-up plus the lazy `configure.py` import for a src/include edit, under load) is treated
as a non-blocking error, so the edit goes through. hooks.py's docstring and docs/workflow.md:206
("Both layers fail closed") claim more than the configuration delivers. In a matching session the
matching handler repeats the always rules, so the gap is mainly in non-driver sessions.
**Fix:** Give the always handler the same `"timeout": 120, "onFailure": "block"` in both settings
files, and pin it in a test next to the existing settings tests.

### WR-03: `gate --partial` keeps an older partial row's date (and reports it as written), so a function attempted today stays eligible today

**File:** `tools/reverseapoc/gate.py:729-747`, `tools/reverseapoc/driver.py:1862-1871`
**Issue:** When an existing partial row has an equal or higher percent, `_merge_partial` keeps
that row with only its attempts updated (`dataclasses.replace(best, attempts=...)`), so its
`date` stays the old day. `excluded_keys` skips a partial row only when `row.date == today`
("every partial row of this pass"). A function that scored 80% yesterday and 70% today keeps
yesterday's date, and a second `drive` the same day picks it again, which contradicts D-09.
The unchanged row is also appended to `touched`, so the gate exits 0 and reports "wrote partial
..." for a row whose percent, sha and date did not change.
**Fix:** Stamp the kept row with today's date, at least when the attempt ran today, and only
report rows that changed:
```python
if old is not None:
    best = old if old.best_percent >= percent else row
    row = dataclasses.replace(best, attempts=max(old.attempts, attempts), date=day)
    if row == old:
        continue
```

### WR-04: A Bash-tool timeout kills the attempt wrapper mid-run and leaves `check.lock` behind, ending every later check of the attempt

**File:** `tools/reverseapoc/attempt.py:437-458`, `tools/reverseapoc/hooks.py:698-709`
**Issue:** The wrapper relies on the agent setting the Bash tool's `timeout` to 600000
(SKILL.md:100), because a run can last up to 580 s plus 15 s of removal. The Bash tool's
default is 120 s, and a sweep easily exceeds it. When the tool kills the wrapper, the
`finally` that unlinks `check.lock` never runs. By design (`_check_lock` docstring) a stale lock
is never cleared, so every later `attempt check` in that session is refused. The run's
container also keeps writing build/ until the driver removes it after the session. One omitted
parameter silently ends the attempt. The hook already inspects `tool_input` for
`run_in_background` but not for `timeout`.
**Fix:** In `_matching`'s Bash branch, deny an `attempt check` (plain or `--sweep`) whose
`tool_input.timeout` is missing or below 600000, with a reason that tells the agent to set it:
```python
if argv_is_check(command) and not (isinstance(t := tool_input.get("timeout"), int)
                                   and not isinstance(t, bool) and t >= 600_000):
    return _deny("run attempt check with the Bash tool's timeout set to 600000")
```

## Info

### IN-01: A sweep with no measured cell logs `best_percent` 0.0, not null

**File:** `tools/reverseapoc/attempt.py:334`
**Issue:** `_sweep_line` writes `0.0` when no cell was measured, while `reloc_ok`/`bytes_ok` are
`None` and the `CheckLogLine` docstring says the fields are null without a measurement. The driver
ignores sweep lines, so this is only a data-consistency wart in checks.jsonl.
**Fix:** `float(best["objdiff_percent"]) if best else None`.

### IN-02: A failed lint is recorded as PARTIAL even when no check scored above 0%

**File:** `tools/reverseapoc/driver.py:1585-1586`
**Issue:** `gate is None` (lint exit 1) sets `outcome, abort = PARTIAL, LINT` whatever
`summary.best_percent` is. README.md:88 defines PARTIAL as "scores above 0% in objdiff", so
attempts.jsonl can hold PARTIAL records with `best_percent: null`.
**Fix:** `outcome = PARTIAL if (summary.best_percent or 0.0) > 0.0 else GAVE_UP`, keeping
`abort = LINT` in both cases.

### IN-03: Tests that assert on docstring wording

**File:** `tests/test_gate.py:831-835`
**Issue:** `test_cmd_gate_docstring_names_the_half_write` passes or fails on the text of
`cli._cmd_gate.__doc__`, not on behaviour. The behaviour is already pinned by the test above it
(lines ~810-828). This test adds no protection and breaks on a rewording.
**Fix:** Drop it, or assert on the CLI's actual error output for the half-write case.

### IN-04: Workflow actions are pinned by tag, not by commit SHA

**File:** `.github/workflows/ci.yml:14,25`, `.github/workflows/pages.yml:39,48,56,71`
**Issue:** `actions/checkout@v7`, `astral-sh/setup-uv@v10.3.0`, `actions/upload-artifact@v7`,
`actions/upload-pages-artifact@v5` and `actions/deploy-pages@v5` all follow mutable tags. A
moved tag runs new code with the job's permissions (`pages: write` / `id-token: write` in deploy).
**Fix:** Pin each to a full commit SHA with the tag as a comment, and let Dependabot bump them.

---

_Reviewed: 2026-10-26_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
