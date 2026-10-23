---
phase: 04-compiler-identification
plan: 13
subsystem: tooling
tags: [python, cc-log, concurrency, fcntl, msvcrt, file-lock, docker, 9p]
gap_closure: true
gap_ids: [G-04-2]

requires:
  - phase: 04-compiler-identification
    provides: "reverseapoc cc, compile_rule and _append_log writing build/logs/cc.log (04-01..04-12)"
provides:
  - "cc.log appends serialised across processes by an OS lock on the sidecar <log>.lock (fcntl.flock on POSIX, non-blocking msvcrt.locking spin on win32), held across open, write and close"
  - "tests/test_cc_log.py: concurrent-append regression test (repo-build, tmp-path), exact line plus empty sidecar, default lock path, killed holder, two Windows-only contention tests"
  - "tests/test_compiler_real.py::test_parallel_cc_keeps_one_log_line_per_compile: 16 parallel real cc runs share one --log"
  - "docs: toolchain.md cc.log lock bullet; learnings.md 2026-10-22 O_APPEND entry"
affects: [05-split-and-first-matches, ninja -j builds, cc.log provenance]

actuals:
  tokens: 3840
  tasks: 3
  commits: 3
plan_head_before: 9b4dca2a90df8e797a421558ac0c64e4eb8ce1e9
plan_head_after: 53a50217d1d237d3b708c24b11f9c062a2fd68ba

tech-stack:
  added: []
  patterns:
    - "Cross-process append: an OS lock on a never-deleted sidecar file, released only after the data file is closed"
    - "Concurrency regression tests write under REPO_ROOT/build so the container run exercises the 9p bind mount"

key-files:
  created:
    - tests/test_cc_log.py
  modified:
    - tools/reverseapoc/compiler.py
    - tests/test_compiler_real.py
    - docs/toolchain.md
    - docs/learnings.md

key-decisions:
  - "cc.log appends are serialised by a stdlib OS lock on <log>.lock (design A of the G-04-2 diagnosis), released after the log is closed; no third-party dependency"
  - "win32 spins on msvcrt LK_NBLCK with a 1 ms sleep and retries only on EACCES; every other OSError propagates"
  - "The host and a container appending to the same cc.log at once is declared unsupported (documented in toolchain.md), not made safe"

patterns-established:
  - "Lock sidecar: <log>.lock next to whatever --log names, opened a+b, never written, never deleted"

requirements-completed: [CID-01, CID-02]

coverage:
  - id: D1
    description: "Parallel cc processes leave exactly one intact cc.log line per call, on the Windows host and on the container bind mount"
    requirement: CID-01
    verification:
      - kind: integration
        ref: "tests/test_cc_log.py#test_concurrent_appends_keep_every_line[repo-build] (host 5/5 and container 5/5 in gate steps 2 and 5)"
        status: pass
      - kind: integration
        ref: "tests/test_compiler_real.py#test_parallel_cc_keeps_one_log_line_per_compile (host and container, gate steps 1-5)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The lock is an OS lock on the sidecar <log>.lock: a killed holder does not block later appends, the sidecar stays empty, only EACCES is retried on win32"
    requirement: CID-01
    verification:
      - kind: unit
        ref: "tests/test_cc_log.py#test_a_killed_lock_holder_does_not_block_later_appends"
        status: pass
      - kind: unit
        ref: "tests/test_cc_log.py#test_append_writes_the_log_line_and_an_empty_sidecar_lock"
        status: pass
      - kind: unit
        ref: "tests/test_cc_log.py#test_lock_retries_while_busy and #test_lock_does_not_swallow_other_errors (host)"
        status: pass
      - kind: other
        ref: "mutants M1-M5 (build/gate/04-13/mutants/*.log, reproduced below): every required mutant exits non-zero"
        status: pass
    human_judgment: false
  - id: D3
    description: "_log_line, DEFAULT_LOG, --log and the dependency list are unchanged"
    requirement: CID-02
    verification:
      - kind: other
        ref: "Task 1 invariant check (_log_line diff, git diff of tests/test_compiler.py tests/test_cli.py pyproject.toml uv.lock, DEFAULT_LOG grep): exit 0"
        status: pass
      - kind: unit
        ref: "tests/test_cc_log.py#test_default_log_and_its_lock"
        status: pass
    human_judgment: false
  - id: D4
    description: "docs/toolchain.md states the lock sidecar, the parallel-safety scope and the unsupported host-plus-container case; docs/learnings.md records why"
    verification:
      - kind: other
        ref: "grep cc.log.lock / 'same log at the same time is not supported' docs/toolchain.md; first dated learnings heading is the 2026-10-22 O_APPEND entry; uv run pytest -q tests/test_hygiene.py"
        status: pass
    human_judgment: true
    rationale: "Whether the prose reads clearly to the owner is a judgement no test makes"

duration: 18min
completed: 2026-10-22
status: complete
---

# Phase 4 Plan 13: cc.log append race (G-04-2) Summary

**Parallel `reverseapoc cc` runs now keep one intact cc.log line each: `_append_log` opens, writes and closes the log inside a stdlib OS lock on the sidecar `<log>.lock` (fcntl.flock LOCK_EX in Linux, a non-blocking msvcrt.locking spin that retries only on EACCES on Windows), proven red then green on the host and in the container, with five reverted mutants.**

## Performance

- **Duration:** about 18 min
- **Started:** 2026-10-23T01:12Z (orchestrator start 01:11:36Z; first RED log 01:15:38Z)
- **Completed:** 2026-10-23T01:30Z
- **Tasks:** 3 of 3
- **Files modified:** 5 (1 created, 4 modified); gate and mutant logs under gitignored build/gate/04-13/

## Accomplishments

- Gap G-04-2 closed: the hammer test (16 writer processes x 25 real `_append_log` calls under build/) and 16 parallel real `cc` compiles sharing one `--log` leave exactly one intact line per call on the Windows host (NTFS) and on the container's 9p bind mount.
- The lock is held from before the log is opened until after it is closed (the 9p bind mount sends the bytes at close), lives in a never-deleted sidecar next to whatever `--log` names, and is freed by the OS when a holder dies.
- Five mutants (no lock, release before close, swallow every OSError, wrong sidecar name, crash-surviving mkdir lock) each fail the tests where the plan said they must, and were reverted.
- The done gate is green: host suite 1035 passed / 6 platform skips + ruff clean; container 1039 passed / 2 Windows-only skips + ruff clean; the concurrency tests passed 5 runs in a row on each environment.

## Task Commits

1. **Task 1 RED: regression tests** - `c2d4054` (test) `test(04-13): concurrent cc.log appends lose no line (G-04-2, red)`
2. **Task 1 GREEN: the sidecar OS lock** - `97f75ac` (fix) `fix(04-13): serialise cc.log appends with an OS lock on <log>.lock (G-04-2)`
3. **Task 2: mutants (not committed) and docs** - `53a5021` (docs) `docs(04-13): cc.log lock and the O_APPEND learning (G-04-2)`
4. **Task 3: done gate** - no commit (logs are gitignored; reproduced below)

## Files Created/Modified

- `tests/test_cc_log.py` (new) - concurrent-append test (repo-build, tmp-path), exact line and empty sidecar, default lock path, killed holder, two Windows-only msvcrt tests
- `tests/test_compiler_real.py` - `test_parallel_cc_keeps_one_log_line_per_compile` plus the `subprocess` and `sys` imports; no existing line changed
- `tools/reverseapoc/compiler.py` - `LOCK_SUFFIX`, `_LOCK_RETRY_SECONDS`, `_lock_path`, platform `_acquire`/`_release` (and win32 `_try_lock`), `_log_lock`, `_append_log` inside the lock, module docstring sentence
- `docs/toolchain.md` - "wibo" section: cc.log lock bullet
- `docs/learnings.md` - 2026-10-22 entry "O_APPEND is not atomic on the bind mount or the Windows host"

## TDD: RED results (at c2d4054, before the fix)

Logs: build/gate/04-13/red/ (gitignored). Command per environment as in the plan:
host `uv run pytest -q -rs tests/test_cc_log.py tests/test_compiler_real.py::test_parallel_cc_keeps_one_log_line_per_compile`,
container the same inside `docker compose run --rm build bash -lc "uv sync --locked && ..."`.

| Run | Summary line | Failing tests and failure line |
|-----|--------------|-------------------------------|
| host 1 | `8 failed` (exit 1) | repo-build `torn line start: ''`; tmp-path `torn line start: ''`; sidecar `{'elsewhere', 'elsewhere/my.log'} == {..., 'elsewhere/my.log.lock'}` (no lock file); default-paths `AttributeError: ... no attribute '_lock_path'`; killed-holder `assert '' == 'held'`; retries-while-busy `assert 0 >= (3 + 1)`; no-swallow `Failed: DID NOT RAISE OSError`; real parallel cc `assert 15 == 16` |
| host 2 | `7 failed, 1 passed` (exit 1) | repo-build `torn line start: '0'`; tmp-path `torn line start: ''`; sidecar, default-paths, killed-holder, both Windows-only tests as in run 1; real parallel cc PASSED (16/16) |
| host 3 | `8 failed` (exit 1) | repo-build `torn line start: '0'`; tmp-path `torn line start: ''`; the other five as in run 1; real parallel cc `assert 15 == 16` |
| container 1 | `5 failed, 1 passed, 2 skipped` (exit 1) | repo-build `merged line: '... exit 02026-10-23T01:16:00+00:00 ...'`; sidecar (no lock file); default-paths (`_lock_path` missing); killed-holder `assert '' == 'held'`; real parallel cc `assert 13 == 16`. tmp-path PASSED; both Windows-only tests skipped |
| container 2 | `5 failed, 1 passed, 2 skipped` (exit 1) | repo-build `torn line start: '22026-10-23T01:16:06+00:00 ...'`; sidecar, default-paths, killed-holder as in run 1; real parallel cc `assert 12 == 16` (a bare `'0'` line among them). tmp-path PASSED; Windows-only skipped |
| container 3 | `5 failed, 1 passed, 2 skipped` (exit 1) | repo-build `merged line: '... exit 02026-10-23T01:16:11+00:00 ...'`; sidecar, default-paths, killed-holder as in run 1; real parallel cc `assert 10 == 16`. tmp-path PASSED; Windows-only skipped |

- repo-build failed in all six runs; tmp-path passed in all three container runs (overlay fs appends atomically), as the plan expected.
- Real parallel cc: host failed 2 of 3 (15/16 lines twice), container failed 3 of 3 (13, 12 and 10 of 16 lines).
- Machine RED check: a fourth host run, `uv run pytest -q tests/test_cc_log.py --junitxml=build/gate/04-13/red/host-junit.xml` (exit 1, 7 failed), fed to `gsd-tools check tdd-red-evidence` with target `test_concurrent_appends_keep_every_line[repo-build]`, returned `RED_EVIDENCE_OK` (`target_test_failed`, format junit, no report errors).
- Semantic assessment: every target test executed and failed on its planned assertion (lost or torn lines, missing sidecar, missing `_lock_path`, holder could not take the lock, msvcrt never called); no collection, import or fixture error.

## TDD: GREEN results (at 97f75ac)

- Host: `8 passed in 3.94s` (exit 0, no skip). Container: `6 passed, 2 skipped in 4.02s` (exit 0), both skips `Windows-only: msvcrt lock path`.
- Host `uv run pytest -q && uv run ruff check .`: `1035 passed, 6 skipped`, `All checks passed!` (exit 0).
- Tracer gate (re-run of the Task 1 verify at the committed fix): host `8 passed in 3.02s`, container `6 passed, 2 skipped in 4.07s`, both exit 0.
- Task 1 verify checks 3-6 (commit subjects, LK_NBLCK/LOCK_EX/`with _log_lock(log)` present and no LK_LOCK/LK_RLCK, `_log_line` and invariants unchanged, no prototype name in the tests): all exit 0.

## Mutants (Task 2)

Each mutant was applied alone to tools/reverseapoc/compiler.py, run, and reverted with `git checkout -- tools/reverseapoc/compiler.py`; afterwards `git diff --exit-code -- tools/reverseapoc/compiler.py` exited 0. None was committed.

| Mutant | Env | Result | Tests that failed |
|--------|-----|--------|-------------------|
| M1 no lock | host | `6 failed, 1 passed`, exit=1 | repo-build, tmp-path, sidecar, killed-holder (`the writer did not wait for the lock`), retries-while-busy, no-swallow |
| M1 no lock | container | `3 failed, 2 passed, 2 skipped`, exit=1 | repo-build (`merged line`), sidecar, killed-holder |
| M2 release before close | container | `1 failed, 4 passed, 2 skipped`, exit=1 | repo-build (`torn line start: ''`) |
| M2 release before close | host | `7 passed`, exit=0 | none (recorded; NTFS shares its cache, so the plan does not require a host failure) |
| M3 every OSError is contention | host | `1 failed, 6 passed`, exit=1 | test_lock_does_not_swallow_other_errors (`DID NOT RAISE OSError`) |
| M4 `log.with_suffix(LOCK_SUFFIX)` | host | `2 failed, 5 passed`, exit=1 | sidecar test, default-paths test (`.../build/logs/cc.lock`) |
| M5 mkdir lock on `<sidecar>.d` | host | `4 failed, 3 passed`, exit=1 | killed-holder (`subprocess.TimeoutExpired` after 10 s), sidecar test, retries-while-busy, no-swallow (msvcrt never called) |

## Decisions Made

- Followed design A of the diagnosis as planned: stdlib OS lock on `<log>.lock`, released after the log closes; the line is computed before the lock so the critical section is only open/write/close.
- The release helpers run in a `finally` only after `_acquire` returned, so a non-contention error from the first lock attempt propagates without an unlock call on an unheld lock.

## Deviations from Plan

None - plan executed exactly as written. Two execution details, neither changing scope:

- M5 catches `(FileExistsError, PermissionError)` in its mkdir spin, as the diagnosis's mkdir candidate does, so the mutant is a working lock on Windows (where a delete-pending directory raises PermissionError) whose only defect is that it survives a crash. It fails the killed-holder test by timing out, as the plan requires.
- One extra host RED run with `--junitxml` was made after the RED commit, only to feed the GSD RED-evidence classifier.

## TDD Gate Compliance

RED `c2d4054 test(04-13): ...` precedes GREEN `97f75ac fix(04-13): ...`. The GREEN commit uses the `fix` type the plan prescribes for this gap closure instead of `feat`; no REFACTOR commit was needed.

## Issues Encountered

- In the container, pytest prints the location of skipped tests with the host path (`C:\Users\...\tests\test_cc_log.py:191`). The skip reasons and counts are correct; the cause was not investigated (it does not affect any result, and it was already the case for the RED runs before any change to compiler.py).
- `uv run ruff format --check tools/reverseapoc/compiler.py` reports two lines that would be reformatted, both pre-existing and outside this plan's change; the gate runs `ruff check`, which is clean.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- G-04-2 is closed: Phase 5's `ninja -j` can run many `cc` at once inside one environment without losing cc.log lines. Host and container must not share one `--log` at the same time (documented).
- Phase 4 is ready for `/gsd-verify-work 4` to re-check UAT test 2.

## Phase gate output

The five gate steps ran once each, in order, from the main checkout at 53a5021, each in a subshell with stdout and stderr redirected into build/gate/04-13/0N-NAME.log and one appended `exit=STATUS` line (Docker steps redirected on the host side). The logs are reproduced verbatim below (CRLF normalised to LF).

### Step 1: 01-host-suite.log

Command: `uv run pytest -q -rs && uv run ruff check .`

````text
........................................................................ [  6%]
........................................................................ [ 13%]
........................................................................ [ 20%]
................................ss...............s...................... [ 27%]
........................................................................ [ 34%]
.......................sss.............................................. [ 41%]
........................................................................ [ 48%]
........................................................................ [ 55%]
........................................................................ [ 62%]
........................................................................ [ 69%]
........................................................................ [ 76%]
........................................................................ [ 82%]
........................................................................ [ 89%]
........................................................................ [ 96%]
.................................                                        [100%]
=========================== short test summary info ===========================
SKIPPED [2] tests\test_configure.py:199: Windows file names cannot hold | or LF
SKIPPED [1] tests\test_configure.py:273: needs a file system that stores non-UTF-8 byte names
SKIPPED [3] tests\test_hygiene.py:355: only inside the container
1035 passed, 6 skipped in 119.42s (0:01:59)
All checks passed!
exit=0
````

### Step 2: 02-host-cclog-x5.log

Command: `for i in 1 2 3 4 5; do uv run pytest -q -rs tests/test_cc_log.py tests/test_compiler_real.py::test_parallel_cc_keeps_one_log_line_per_compile || exit 1; done`

````text
........                                                                 [100%]
8 passed in 3.10s
........                                                                 [100%]
8 passed in 2.98s
........                                                                 [100%]
8 passed in 3.96s
........                                                                 [100%]
8 passed in 3.31s
........                                                                 [100%]
8 passed in 3.05s
exit=0
````

### Step 3: 03-container-test.log

Command: `docker compose run --rm test`

````text
 Container reverseapoc-test-run-054328d3a712 Creating 
 Container reverseapoc-test-run-054328d3a712 Created 
Resolved 8 packages in 2ms
Checked 7 packages in 3ms
.....ss................................................................. [  6%]
........................................................................ [ 13%]
........................................................................ [ 20%]
........................................................................ [ 27%]
........................................................................ [ 34%]
........................................................................ [ 41%]
........................................................................ [ 48%]
........................................................................ [ 55%]
........................................................................ [ 62%]
........................................................................ [ 69%]
........................................................................ [ 76%]
........................................................................ [ 82%]
........................................................................ [ 89%]
........................................................................ [ 96%]
.................................                                        [100%]
1039 passed, 2 skipped in 120.17s (0:02:00)
exit=0
````

### Step 4: 04-container-suite.log

Command: `docker compose run --rm build bash -lc "uv sync --locked && uv run pytest -q -rs && uv run ruff check ."`

````text
 Container reverseapoc-build-run-53fc89fa006b Creating 
 Container reverseapoc-build-run-53fc89fa006b Created 
Resolved 8 packages in 2ms
Checked 7 packages in 2ms
.....ss................................................................. [  6%]
........................................................................ [ 13%]
........................................................................ [ 20%]
........................................................................ [ 27%]
........................................................................ [ 34%]
........................................................................ [ 41%]
........................................................................ [ 48%]
........................................................................ [ 55%]
........................................................................ [ 62%]
........................................................................ [ 69%]
........................................................................ [ 76%]
........................................................................ [ 82%]
........................................................................ [ 89%]
........................................................................ [ 96%]
.................................                                        [100%]
=========================== short test summary info ============================
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:191: Windows-only: msvcrt lock path
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:212: Windows-only: msvcrt lock path
1039 passed, 2 skipped in 119.78s (0:01:59)
All checks passed!
exit=0
````

### Step 5: 05-container-cclog-x5.log

Command: `docker compose run --rm build bash -lc "uv sync --locked && for i in 1 2 3 4 5; do uv run pytest -q -rs tests/test_cc_log.py tests/test_compiler_real.py::test_parallel_cc_keeps_one_log_line_per_compile || exit 1; done"`

````text
 Container reverseapoc-build-run-ee0ee5d63de8 Creating 
 Container reverseapoc-build-run-ee0ee5d63de8 Created 
Resolved 8 packages in 2ms
Checked 7 packages in 3ms
.....ss.                                                                 [100%]
=========================== short test summary info ============================
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:191: Windows-only: msvcrt lock path
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:212: Windows-only: msvcrt lock path
6 passed, 2 skipped in 4.59s
.....ss.                                                                 [100%]
=========================== short test summary info ============================
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:191: Windows-only: msvcrt lock path
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:212: Windows-only: msvcrt lock path
6 passed, 2 skipped in 4.11s
.....ss.                                                                 [100%]
=========================== short test summary info ============================
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:191: Windows-only: msvcrt lock path
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:212: Windows-only: msvcrt lock path
6 passed, 2 skipped in 3.93s
.....ss.                                                                 [100%]
=========================== short test summary info ============================
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:191: Windows-only: msvcrt lock path
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:212: Windows-only: msvcrt lock path
6 passed, 2 skipped in 3.86s
.....ss.                                                                 [100%]
=========================== short test summary info ============================
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:191: Windows-only: msvcrt lock path
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:212: Windows-only: msvcrt lock path
6 passed, 2 skipped in 3.84s
exit=0
````

### Mutants

Each mutant was applied alone, run, and reverted with `git checkout -- tools/reverseapoc/compiler.py`.

#### M1, no lock (unsynchronised open-append), host: mutants/M1-host.log

Command: `uv run pytest -q -rs tests/test_cc_log.py`

````text
FFF.FFF                                                                  [100%]
================================== FAILURES ===================================
_____________ test_concurrent_appends_keep_every_line[repo-build] _____________

where = 'repo-build'
shared_dir = WindowsPath('C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/build/test-cclog/test_concurrent_appends_keep_every_line_repo-build_')
tmp_path = WindowsPath('C:/Users/Ayrton/AppData/Local/Temp/pytest-of-Ayrton/pytest-887/test_concurrent_appends_keep_e0')

    @pytest.mark.parametrize("where", ["repo-build", "tmp-path"])
    def test_concurrent_appends_keep_every_line(where, shared_dir, tmp_path):
        base = shared_dir if where == "repo-build" else tmp_path
        log = base / "logs" / "cc.log"
        writers = [_start_writer(log, w, LINES) for w in range(WRITERS)]
        assert [p.wait() for p in writers] == [0] * WRITERS
>       assert_every_line_intact(log.read_text(encoding="utf-8").splitlines())

tests\test_cc_log.py:131: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
tests\test_cc_log.py:100: in assert_every_line_intact
    _assert_line_intact(line)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

line = ''

    def _assert_line_intact(line: str) -> None:
>       assert LINE_START.fullmatch(line), f"torn line start: {line!r}"
E       AssertionError: torn line start: ''
E       assert None
E        +  where None = <built-in method fullmatch of re.Pattern object at 0x00000233C915F840>('')
E        +    where <built-in method fullmatch of re.Pattern object at 0x00000233C915F840> = re.compile('\\d{4}-\\d\\d-\\d\\dT\\d\\d:\\d\\d:\\d\\d\\+00:00  .*').fullmatch

tests\test_cc_log.py:92: AssertionError
______________ test_concurrent_appends_keep_every_line[tmp-path] ______________

where = 'tmp-path'
shared_dir = WindowsPath('C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/build/test-cclog/test_concurrent_appends_keep_every_line_tmp-path_')
tmp_path = WindowsPath('C:/Users/Ayrton/AppData/Local/Temp/pytest-of-Ayrton/pytest-887/test_concurrent_appends_keep_e1')

    @pytest.mark.parametrize("where", ["repo-build", "tmp-path"])
    def test_concurrent_appends_keep_every_line(where, shared_dir, tmp_path):
        base = shared_dir if where == "repo-build" else tmp_path
        log = base / "logs" / "cc.log"
        writers = [_start_writer(log, w, LINES) for w in range(WRITERS)]
        assert [p.wait() for p in writers] == [0] * WRITERS
>       assert_every_line_intact(log.read_text(encoding="utf-8").splitlines())

tests\test_cc_log.py:131: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
tests\test_cc_log.py:100: in assert_every_line_intact
    _assert_line_intact(line)
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

line = ''

    def _assert_line_intact(line: str) -> None:
>       assert LINE_START.fullmatch(line), f"torn line start: {line!r}"
E       AssertionError: torn line start: ''
E       assert None
E        +  where None = <built-in method fullmatch of re.Pattern object at 0x00000233C915F840>('')
E        +    where <built-in method fullmatch of re.Pattern object at 0x00000233C915F840> = re.compile('\\d{4}-\\d\\d-\\d\\dT\\d\\d:\\d\\d:\\d\\d\\+00:00  .*').fullmatch

tests\test_cc_log.py:92: AssertionError
__________ test_append_writes_the_log_line_and_an_empty_sidecar_lock __________

tmp_path = WindowsPath('C:/Users/Ayrton/AppData/Local/Temp/pytest-of-Ayrton/pytest-887/test_append_writes_the_log_lin0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x00000233C9320640>

    def test_append_writes_the_log_line_and_an_empty_sidecar_lock(tmp_path, monkeypatch):
        monkeypatch.setattr(compiler, "datetime", _FrozenDatetime)
        log = tmp_path / "elsewhere" / "my.log"
        result = _result("w0-0")
        compiler._append_log(log, result)
        compiler._append_log(log, result)
        assert log.read_text(encoding="utf-8") == compiler._log_line(result) * 2
        found = {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")}
>       assert found == {"elsewhere", "elsewhere/my.log", "elsewhere/my.log.lock"}
E       AssertionError: assert {'elsewhere',...where/my.log'} == {'elsewhere',.../my.log.lock'}
E         
E         Extra items in the right set:
E         'elsewhere/my.log.lock'
E         Use -v to get more diff

tests\test_cc_log.py:148: AssertionError
___________ test_a_killed_lock_holder_does_not_block_later_appends ____________

shared_dir = WindowsPath('C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/build/test-cclog/test_a_killed_lock_holder_does_not_block_later_appends')

    def test_a_killed_lock_holder_does_not_block_later_appends(shared_dir):
        log = shared_dir / "logs" / "cc.log"
        log.parent.mkdir(parents=True)
        procs: list[subprocess.Popen] = []
        try:
            holder = subprocess.Popen(
                [sys.executable, "-c", HOLDER, str(log)], stdout=subprocess.PIPE, text=True
            )
            procs.append(holder)
            assert holder.stdout.readline().strip() == "held"
            writer = _start_writer(log, 0, 1, stdout=subprocess.PIPE)
            procs.append(writer)
            assert writer.stdout.readline().strip() == "start"
            time.sleep(BLOCKED_CHECK_SECONDS)
>           assert writer.poll() is None, "the writer did not wait for the lock"
E           AssertionError: the writer did not wait for the lock
E           assert 0 is None
E            +  where 0 = poll()
E            +    where poll = <Popen: returncode: 0 args: ['C:\\Users\\Ayrton\\Documents\\Gitprojects\\Rev...>.poll

tests\test_cc_log.py:172: AssertionError
________________________ test_lock_retries_while_busy _________________________

tmp_path = WindowsPath('C:/Users/Ayrton/AppData/Local/Temp/pytest-of-Ayrton/pytest-887/test_lock_retries_while_busy0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x00000233C9321350>

    @windows_only
    def test_lock_retries_while_busy(tmp_path, monkeypatch):
        import msvcrt
    
        real = msvcrt.locking
        calls = []
    
        def locking(fd, mode, nbytes):
            if mode == msvcrt.LK_NBLCK:
                calls.append(mode)
                if len(calls) <= BUSY_CALLS:
                    raise OSError(errno.EACCES, "busy")
            return real(fd, mode, nbytes)
    
        monkeypatch.setattr(msvcrt, "locking", locking)
        log = tmp_path / "logs" / "cc.log"
        compiler._append_log(log, _result("w0-0"))
        assert len(_log_lines(log)) == 1
>       assert len(calls) >= BUSY_CALLS + 1
E       assert 0 >= (3 + 1)
E        +  where 0 = len([])

tests\test_cc_log.py:209: AssertionError
___________________ test_lock_does_not_swallow_other_errors ___________________

tmp_path = WindowsPath('C:/Users/Ayrton/AppData/Local/Temp/pytest-of-Ayrton/pytest-887/test_lock_does_not_swallow_oth0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x00000233C92C8DD0>

    @windows_only
    def test_lock_does_not_swallow_other_errors(tmp_path, monkeypatch):
        import msvcrt
    
        real = msvcrt.locking
        calls = []
    
        def locking(fd, mode, nbytes):
            if mode == msvcrt.LK_NBLCK:
                calls.append(mode)
                if len(calls) == 1:
                    raise OSError(errno.EBADF, "bad")
            return real(fd, mode, nbytes)
    
        monkeypatch.setattr(msvcrt, "locking", locking)
        log = tmp_path / "logs" / "cc.log"
>       with pytest.raises(OSError) as excinfo:
             ^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE OSError

tests\test_cc_log.py:228: Failed
6 failed, 1 passed in 2.23s
exit=1
````

#### M1, no lock (unsynchronised open-append), container: mutants/M1-container.log

Command: `docker compose run --rm build bash -lc "uv sync --locked && uv run pytest -q -rs tests/test_cc_log.py"`

````text
 Container reverseapoc-build-run-3373fb591405 Creating 
 Container reverseapoc-build-run-3373fb591405 Created 
Resolved 8 packages in 4ms
Checked 7 packages in 4ms
F.F.Fss                                                                  [100%]
=================================== FAILURES ===================================
_____________ test_concurrent_appends_keep_every_line[repo-build] ______________

where = 'repo-build'
shared_dir = PosixPath('/work/build/test-cclog/test_concurrent_appends_keep_every_line_repo-build_')
tmp_path = PosixPath('/tmp/pytest-of-dev/pytest-0/test_concurrent_appends_keep_e0')

>   ???

C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:131: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:100: in assert_every_line_intact
    ???
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

line = '2026-10-23T01:20:43+00:00  wcc386@10.6  Version 10.6  BINNT/WCC386.EXE=0000000000000000000000000000000000000000  wcc3...w8-xx0.obj  sha1 1111111111111111111111111111111111111111  normalized 2222222222222222222222222222222222222222  exit 0'

>   ???
E   AssertionError: merged line: '2026-10-23T01:20:43+00:00  wcc386@10.6  Version 10.6  BINNT/WCC386.EXE=0000000000000000000000000000000000000000  wcc386 -fo=o/w1-x0.obj  sha1 1111111111111111111111111111111111111111  normalized 2222222222222222222222222222222222222222  exit 0202026-10-23T01:20:43+00:00  wcc386@10.6  Version 10.6  BINNT/WCC386.EXE=0000000000000000000000000000000000000000  wcc386 -fo=o/w8-xx0.obj  sha1 1111111111111111111111111111111111111111  normalized 2222222222222222222222222222222222222222  exit 0'
E   assert 2 == 1
E    +  where 2 = <built-in method count of str object at 0x3f38fab0>('Version 10.6')
E    +    where <built-in method count of str object at 0x3f38fab0> = '2026-10-23T01:20:43+00:00  wcc386@10.6  Version 10.6  BINNT/WCC386.EXE=0000000000000000000000000000000000000000  wcc3...w8-xx0.obj  sha1 1111111111111111111111111111111111111111  normalized 2222222222222222222222222222222222222222  exit 0'.count

C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:94: AssertionError
__________ test_append_writes_the_log_line_and_an_empty_sidecar_lock ___________

tmp_path = PosixPath('/tmp/pytest-of-dev/pytest-0/test_append_writes_the_log_lin0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x70762cec9940>

>   ???
E   AssertionError: assert {'elsewhere',...where/my.log'} == {'elsewhere',.../my.log.lock'}
E     
E     Extra items in the right set:
E     'elsewhere/my.log.lock'
E     Use -v to get more diff

C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:148: AssertionError
____________ test_a_killed_lock_holder_does_not_block_later_appends ____________

shared_dir = PosixPath('/work/build/test-cclog/test_a_killed_lock_holder_does_not_block_later_appends')

>   ???
E   AssertionError: the writer did not wait for the lock
E   assert 0 is None
E    +  where 0 = poll()
E    +    where poll = <Popen: returncode: 0 args: ['/opt/venv/bin/python', '-c', '\nimport sys\nfr...>.poll

C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:172: AssertionError
=========================== short test summary info ============================
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:191: Windows-only: msvcrt lock path
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:212: Windows-only: msvcrt lock path
3 failed, 2 passed, 2 skipped in 2.57s

exit=1
````

#### M2, release before close, container: mutants/M2-container.log

Command: `docker compose run --rm build bash -lc "uv sync --locked && uv run pytest -q -rs tests/test_cc_log.py"`

````text
 Container reverseapoc-build-run-c80eddf42465 Creating 
 Container reverseapoc-build-run-c80eddf42465 Created 
Resolved 8 packages in 2ms
Checked 7 packages in 3ms
F....ss                                                                  [100%]
=================================== FAILURES ===================================
_____________ test_concurrent_appends_keep_every_line[repo-build] ______________

where = 'repo-build'
shared_dir = PosixPath('/work/build/test-cclog/test_concurrent_appends_keep_every_line_repo-build_')
tmp_path = PosixPath('/tmp/pytest-of-dev/pytest-0/test_concurrent_appends_keep_e0')

>   ???

C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:131: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:100: in assert_every_line_intact
    ???
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

line = ''

>   ???
E   AssertionError: torn line start: ''
E   assert None
E    +  where None = <built-in method fullmatch of re.Pattern object at 0x7ed23e12f440>('')
E    +    where <built-in method fullmatch of re.Pattern object at 0x7ed23e12f440> = re.compile('\\d{4}-\\d\\d-\\d\\dT\\d\\d:\\d\\d:\\d\\d\\+00:00  .*').fullmatch

C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:92: AssertionError
=========================== short test summary info ============================
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:191: Windows-only: msvcrt lock path
SKIPPED [1] C:\Users\Ayrton\Documents\Gitprojects\ReverseApoc\tests\test_cc_log.py:212: Windows-only: msvcrt lock path
1 failed, 4 passed, 2 skipped in 2.49s

exit=1
````

#### M2, release before close, host (recorded, not required to fail): mutants/M2-host.log

Command: `uv run pytest -q -rs tests/test_cc_log.py`

````text
.......                                                                  [100%]
7 passed in 2.80s
exit=0
````

#### M3, every OSError counts as contention, host: mutants/M3-host.log

Command: `uv run pytest -q -rs tests/test_cc_log.py`

````text
......F                                                                  [100%]
================================== FAILURES ===================================
___________________ test_lock_does_not_swallow_other_errors ___________________

tmp_path = WindowsPath('C:/Users/Ayrton/AppData/Local/Temp/pytest-of-Ayrton/pytest-889/test_lock_does_not_swallow_oth0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000023C4CD16210>

    @windows_only
    def test_lock_does_not_swallow_other_errors(tmp_path, monkeypatch):
        import msvcrt
    
        real = msvcrt.locking
        calls = []
    
        def locking(fd, mode, nbytes):
            if mode == msvcrt.LK_NBLCK:
                calls.append(mode)
                if len(calls) == 1:
                    raise OSError(errno.EBADF, "bad")
            return real(fd, mode, nbytes)
    
        monkeypatch.setattr(msvcrt, "locking", locking)
        log = tmp_path / "logs" / "cc.log"
>       with pytest.raises(OSError) as excinfo:
             ^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE OSError

tests\test_cc_log.py:228: Failed
1 failed, 6 passed in 2.36s
exit=1
````

#### M4, wrong sidecar name (log.with_suffix), host: mutants/M4-host.log

Command: `uv run pytest -q -rs tests/test_cc_log.py`

````text
..FF...                                                                  [100%]
================================== FAILURES ===================================
__________ test_append_writes_the_log_line_and_an_empty_sidecar_lock __________

tmp_path = WindowsPath('C:/Users/Ayrton/AppData/Local/Temp/pytest-of-Ayrton/pytest-890/test_append_writes_the_log_lin0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000014FBB471480>

    def test_append_writes_the_log_line_and_an_empty_sidecar_lock(tmp_path, monkeypatch):
        monkeypatch.setattr(compiler, "datetime", _FrozenDatetime)
        log = tmp_path / "elsewhere" / "my.log"
        result = _result("w0-0")
        compiler._append_log(log, result)
        compiler._append_log(log, result)
        assert log.read_text(encoding="utf-8") == compiler._log_line(result) * 2
        found = {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")}
>       assert found == {"elsewhere", "elsewhere/my.log", "elsewhere/my.log.lock"}
E       AssertionError: assert {'elsewhere',...where/my.log'} == {'elsewhere',.../my.log.lock'}
E         
E         Extra items in the left set:
E         'elsewhere/my.lock'
E         Extra items in the right set:
E         'elsewhere/my.log.lock'
E         Use -v to get more diff

tests\test_cc_log.py:148: AssertionError
________________________ test_default_log_and_its_lock ________________________

    def test_default_log_and_its_lock():
        assert REPO_ROOT / "build" / "logs" / "cc.log" == compiler.DEFAULT_LOG
        lock = compiler._lock_path(compiler.DEFAULT_LOG)
>       assert lock == REPO_ROOT / "build" / "logs" / "cc.log.lock"
E       AssertionError: assert WindowsPath('C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/build/logs/cc.lock') == (((WindowsPath('C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc') / 'build') / 'logs') / 'cc.log.lock')

tests\test_cc_log.py:155: AssertionError
2 failed, 5 passed in 2.35s
exit=1
````

#### M5, mkdir lock that survives a crash, host: mutants/M5-host.log

Command: `uv run pytest -q -rs tests/test_cc_log.py`

````text
..F.FFF                                                                  [100%]
================================== FAILURES ===================================
__________ test_append_writes_the_log_line_and_an_empty_sidecar_lock __________

tmp_path = WindowsPath('C:/Users/Ayrton/AppData/Local/Temp/pytest-of-Ayrton/pytest-891/test_append_writes_the_log_lin0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000001A667DC1480>

    def test_append_writes_the_log_line_and_an_empty_sidecar_lock(tmp_path, monkeypatch):
        monkeypatch.setattr(compiler, "datetime", _FrozenDatetime)
        log = tmp_path / "elsewhere" / "my.log"
        result = _result("w0-0")
        compiler._append_log(log, result)
        compiler._append_log(log, result)
        assert log.read_text(encoding="utf-8") == compiler._log_line(result) * 2
        found = {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")}
>       assert found == {"elsewhere", "elsewhere/my.log", "elsewhere/my.log.lock"}
E       AssertionError: assert {'elsewhere',...where/my.log'} == {'elsewhere',.../my.log.lock'}
E         
E         Extra items in the right set:
E         'elsewhere/my.log.lock'
E         Use -v to get more diff

tests\test_cc_log.py:148: AssertionError
___________ test_a_killed_lock_holder_does_not_block_later_appends ____________

shared_dir = WindowsPath('C:/Users/Ayrton/Documents/Gitprojects/ReverseApoc/build/test-cclog/test_a_killed_lock_holder_does_not_block_later_appends')

    def test_a_killed_lock_holder_does_not_block_later_appends(shared_dir):
        log = shared_dir / "logs" / "cc.log"
        log.parent.mkdir(parents=True)
        procs: list[subprocess.Popen] = []
        try:
            holder = subprocess.Popen(
                [sys.executable, "-c", HOLDER, str(log)], stdout=subprocess.PIPE, text=True
            )
            procs.append(holder)
            assert holder.stdout.readline().strip() == "held"
            writer = _start_writer(log, 0, 1, stdout=subprocess.PIPE)
            procs.append(writer)
            assert writer.stdout.readline().strip() == "start"
            time.sleep(BLOCKED_CHECK_SECONDS)
            assert writer.poll() is None, "the writer did not wait for the lock"
            assert _log_lines(log) == []
            holder.kill()
            holder.wait()
>           assert writer.wait(timeout=FREED_TIMEOUT_SECONDS) == 0
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests\test_cc_log.py:176: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
C:\Program Files\Python314\Lib\subprocess.py:1279: in wait
    return self._wait(timeout=timeout)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <Popen: returncode: 1 args: ['C:\\Users\\Ayrton\\Documents\\Gitprojects\\Rev...>
timeout = 10

    def _wait(self, timeout):
        """Internal implementation of wait() on Windows."""
        if timeout is None:
            timeout_millis = _winapi.INFINITE
        elif timeout <= 0:
            timeout_millis = 0
        else:
            timeout_millis = int(timeout * 1000)
        if self.returncode is None:
            # API note: Returns immediately if timeout_millis == 0.
            result = _winapi.WaitForSingleObject(self._handle,
                                                 timeout_millis)
            if result == _winapi.WAIT_TIMEOUT:
>               raise TimeoutExpired(self.args, timeout)
E               subprocess.TimeoutExpired: Command '['C:\\Users\\Ayrton\\Documents\\Gitprojects\\ReverseApoc\\.venv\\Scripts\\python.exe', '-c', '\nimport sys\nfrom pathlib import Path\nfrom reverseapoc import compiler\nfrom reverseapoc.cflags import Rule\nlog, w, count = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])\nrule = Rule("*", "wcc386", "10.6", ("-5r", "-s"), 1)\ngate = compiler.Gate("10.6", Path("w/10.6"), (("BINNT/WCC386.EXE", "0" * 40),), "Version 10.6")\nprint("start", flush=True)\nfor j in range(count):\n    tag = f"w{w}-{\'x\' * (w % 3)}{j}"\n    result = compiler.CompileResult(\n        Path("a.c"), Path(f"o/{tag}.obj"), rule, gate, ("wcc386", f"-fo=o/{tag}.obj"), 0, "",\n        "1" * 40, "2" * 40,\n    )\n    compiler._append_log(log, result)\n', 'C:\\Users\\Ayrton\\Documents\\Gitprojects\\ReverseApoc\\build\\test-cclog\\test_a_killed_lock_holder_does_not_block_later_appends\\logs\\cc.log', '0', '1']' timed out after 10 seconds

C:\Program Files\Python314\Lib\subprocess.py:1608: TimeoutExpired
________________________ test_lock_retries_while_busy _________________________

tmp_path = WindowsPath('C:/Users/Ayrton/AppData/Local/Temp/pytest-of-Ayrton/pytest-891/test_lock_retries_while_busy0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000001A667DC23F0>

    @windows_only
    def test_lock_retries_while_busy(tmp_path, monkeypatch):
        import msvcrt
    
        real = msvcrt.locking
        calls = []
    
        def locking(fd, mode, nbytes):
            if mode == msvcrt.LK_NBLCK:
                calls.append(mode)
                if len(calls) <= BUSY_CALLS:
                    raise OSError(errno.EACCES, "busy")
            return real(fd, mode, nbytes)
    
        monkeypatch.setattr(msvcrt, "locking", locking)
        log = tmp_path / "logs" / "cc.log"
        compiler._append_log(log, _result("w0-0"))
        assert len(_log_lines(log)) == 1
>       assert len(calls) >= BUSY_CALLS + 1
E       assert 0 >= (3 + 1)
E        +  where 0 = len([])

tests\test_cc_log.py:209: AssertionError
___________________ test_lock_does_not_swallow_other_errors ___________________

tmp_path = WindowsPath('C:/Users/Ayrton/AppData/Local/Temp/pytest-of-Ayrton/pytest-891/test_lock_does_not_swallow_oth0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000001A667D467B0>

    @windows_only
    def test_lock_does_not_swallow_other_errors(tmp_path, monkeypatch):
        import msvcrt
    
        real = msvcrt.locking
        calls = []
    
        def locking(fd, mode, nbytes):
            if mode == msvcrt.LK_NBLCK:
                calls.append(mode)
                if len(calls) == 1:
                    raise OSError(errno.EBADF, "bad")
            return real(fd, mode, nbytes)
    
        monkeypatch.setattr(msvcrt, "locking", locking)
        log = tmp_path / "logs" / "cc.log"
>       with pytest.raises(OSError) as excinfo:
             ^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE OSError

tests\test_cc_log.py:228: Failed
4 failed, 3 passed in 12.80s
exit=1
````

## Self-Check: PASSED

- FOUND: tests/test_cc_log.py, tests/test_compiler_real.py, tools/reverseapoc/compiler.py, docs/toolchain.md, docs/learnings.md
- FOUND (ancestors of HEAD): c2d4054, 97f75ac, 53a5021
- `git rev-list --count 9b4dca2..53a5021` = 3; `gsd-tools check evaluation-scope --plan 04-13 --commits-only` resolved the same 3 commits
- Task 1, Task 2 and Task 3 verify blocks: every check exited 0

---
*Phase: 04-compiler-identification*
*Completed: 2026-10-22*
