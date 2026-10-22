---
status: diagnosed
phase: 04-compiler-identification
source: [04-VERIFICATION.md]
started: 2026-10-21T22:56:05Z
updated: 2026-10-22T20:24:52Z
---

## Current Test

[testing complete]

## Tests

### 1. Goal wording vs delivered result
expected: Owner accepts under D-08/D-10 (override or reworded goal) or reopens the phase (see 04-VERIFICATION.md "Verdict on the goal wording")
result: pass
note: "Accepted with override (04-VERIFICATION.md overrides). 10.6 preferred, 10.5 first fallback, 11.0 candidate; candidate flags listed for proof/permutation in docs/toolchain.md 'Fallbacks and candidates'."

### 2. Backstop truth (04-01): concurrent cc processes never read a half-written gate stamp
expected: Under concurrent compiles (Phase 5's first ninja -j) no compile fails or trusts a torn stamp; cc.log lines may interleave (unit tests prove the atomic swap and torn-stamp miss; no concurrent-process test exists — insufficient_spec)
result: issue
reported: "issue: the log loss."
severity: major
evidence: |
  1600 parallel `cc` compiles (container 10.5/10.6/11.0, Windows host 10.6; build/uat-conc*/): 1600/1600 ok,
  one real banner and one object per version, no torn/garbage/wrong-shape/wrong-root/forged stamp ever trusted,
  no leftover .tmp. Stamp property HELD. But cc.log LOSES lines (not just interleaves): bind mount 72/80 (6 bare
  "0" fragments), 495/608 (25 malformed), 75/96; container-local /tmp 80/80; Windows host 732/736.
  Pure-Python open("a")+write probe: bind mount ~20% kept, /tmp 3200/3200, Windows host 2989 and 1914 of 3200.

### 3. Judgment-tier prohibitions (31 across plans 04-01..04-12)
expected: Owner confirms the advisory LLM-judge verdicts in 04-VERIFICATION.md "Prohibitions" (all observed as held), in particular T-04-13/A1: no OWPL code or comments copied into tools/reverseapoc/wpack.py (also closes 04-SECURITY.md's one open item)
result: pass
note: "Owner reviewed all 12 grouped prohibition rows and signed off A1 (T-04-13): no OWPL code or comments in tools/reverseapoc/wpack.py. Re-run /gsd-secure-phase 4 to close T-04-13 in 04-SECURITY.md."

## Summary

total: 3
passed: 2
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-04-2
  truth: "Under concurrent compiles (ninja -j) no compile fails or trusts a torn stamp; cc.log keeps one intact line per compile (lines may interleave, never vanish or tear)"
  status: failed
  reason: "User reported: issue: the log loss. (1600-compile concurrency run: stamp held; cc.log lost/tore lines on the Docker Desktop 9p bind mount and on the Windows host, none on container-local Linux fs)"
  severity: major
  test: 2
  root_cause: "Stale-offset overwrite, not dropped writes: tools/reverseapoc/compiler.py _append_log (:405-408) does an unsynchronised open('a') + write and relies on O_APPEND being atomic between processes. Docker Desktop's 9p drvfs bind mount (cache=0x5 writeback; bytes reach the server at close) and the Windows host (UCRT _write = lseek(FILE_END) + WriteFile) both emulate append in two steps, so concurrent writers read the same EOF and overwrite each other. Container-local fs is correct (0/6400 lost). Default build/logs/cc.log sits on the bind mount."
  artifacts:
    - path: "tools/reverseapoc/compiler.py"
      issue: "_append_log has no cross-process synchronisation; assumes atomic O_APPEND"
    - path: "tests/"
      issue: "no concurrent-writer test; 04-VERIFICATION truth marked insufficient_spec"
  missing:
    - "Serialise read-EOF -> write -> CLOSE of the log across processes with a stdlib OS lock on a sidecar <log>.lock (POSIX fcntl.flock(LOCK_EX); win32 msvcrt.locking(LK_NBLCK) on byte 0 in a short sleep loop, catching only the contention errno; never LK_LOCK). The lock must be released only after the log fd is closed (unlock-before-close still lost 102-118/1600 on 9p)."
    - "Regression test (red first): 16 subprocess writers x 25 calls of the real compiler._append_log with a log under REPO_ROOT/build (bind mount in the container, NTFS on the host; tmp_path passes in the container today and proves nothing); expect exactly 400 intact lines with the exact tag set. Prototype: build/debug-cclog/test_cclog_concurrency.py (orchestrator re-ran 2026-10-22: today fails on host and container bind mount; lock_append candidate passes both)."
    - "Crash safety: a writer killed while holding the lock must not block later writers (OS locks free on process exit; measured 0.003-0.011 s)."
    - "Document that host and container writing the SAME log at once is unsupported (OS locks do not cross that boundary; measured host lost 222/1200)."
    - "Keep constraints: _log_line format and bytes-free content unchanged; --log and default build/logs/cc.log unchanged; stdlib only; lock sidecar sits next to whatever --log names. Optional: open the log with newline set to LF for uniform LF (host lines are CRLF today)."
  debug_session: ".planning/debug/cc-log-loses-lines-parallel.md"
