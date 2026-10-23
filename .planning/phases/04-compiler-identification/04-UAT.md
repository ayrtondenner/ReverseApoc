---
status: complete
phase: 04-compiler-identification
source: [04-VERIFICATION.md]
started: 2026-10-21T22:56:05Z
updated: 2026-10-23T19:14:30.860Z
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

### 4. UAT re-test of G-04-2 after plan 04-13 (also settles the 04-01 backstop truth)
expected: Many parallel `reverseapoc cc` compiles inside ONE environment (container bind mount, then separately the Windows host), each environment with its own --log: every compile exits 0; no torn stamp is trusted; cc.log holds exactly one intact line per compile (lines may interleave, none lost, none torn); the sidecar cc.log.lock exists and is empty
result: pass
note: "320 parallel compiles per environment (10 rounds x 32; round 1 no stamp, round 2 torn stamp planted), build/uat-retest/: container bind mount and Windows host each 320/320 exit 0 and ok, one banner (10.6), one normalized sha1, cc.log exactly 320 intact lines with every object once, cc.log.lock present and empty, no leftover .tmp, stamp valid JSON after the run. Before 04-13 the bind mount kept 72/80."

### 5. Truth 24 / P1 of 04-13: `--log` behaviour for a nameless path and a device
expected: Owner accepts the changed behaviour as now shipped after review fixes WR-01/WR-02: a --log without a file name is refused before the compile; a device log such as /dev/null is appended without the lock and gets no sidecar; docs/toolchain.md says the log's directory must be writable for <log>.lock. Rejecting turns this into a gap
result: pass
note: "Owner accepted (2026-10-23). Observed: `--log .` refused before the compile (exit 1, no object); `--log /dev/null` compiles, exit 0, no /dev/null.lock; an existing folder as --log compiles then fails with 'Is a directory' (exit 1, object kept), same as before 04-13. docs/toolchain.md:321 is accurate but does not spell out the nameless/folder cases: deferred as a doc follow-up."

### 6. Prohibitions of 04-13 without wired enforcement (P1 --log part, P2, P5, P6)
expected: Owner confirms the verifier's observations: pyproject `dependencies = []` and uv.lock unchanged since c2d4054~1; no 'debug-cclog' reference in the committed tests; config/, docker/, tests/test_compiler.py, tests/test_cli.py unchanged since c2d4054~1 (beyond the 04 review fixes); check-orig 3 OK; every gate step logged with exit=0
result: pass
note: "Re-checked 2026-10-23 at HEAD: dependencies = [], pyproject.toml and uv.lock unchanged since c2d4054~1; no debug-cclog reference in tests/; config/, docker/, tests/test_compiler.py unchanged, tests/test_cli.py +17 lines only from review fix WR-01 (37b104f); check-orig 3 ok; build/gate/04-13/01..05 all exit=0 (every exit=1 in 04-13-SUMMARY is a deliberate mutant)."

## Summary

total: 6
passed: 5
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-04-2
  truth: "Under concurrent compiles (ninja -j) no compile fails or trusts a torn stamp; cc.log keeps one intact line per compile (lines may interleave, never vanish or tear)"
  status: resolved
  resolved_by: 04-13-PLAN.md
  resolved_at: 2026-10-23
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

## Deferred Follow-Ups

- test: 5
  idea: "Update docs/toolchain.md (the cc.log bullet) to say --log must name a file: `--log .` or `--log /` is refused before the compile, and an existing folder compiles first and then fails with 'Is a directory'"
  deferred_at: 2026-10-23
