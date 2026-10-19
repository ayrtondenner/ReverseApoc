---
phase: 02-container-and-target-ingest
verified: 2026-10-19T23:18:52Z
status: human_needed
score: 5/7 must-haves verified
covered_files:
  - ".dockerignore"
  - ".github/workflows/ci.yml"
  - ".gitignore"
  - ".planning/phases/02-container-and-target-ingest/02-01-PLAN.md"
  - ".planning/phases/02-container-and-target-ingest/02-01-SUMMARY.md"
  - ".planning/phases/02-container-and-target-ingest/02-02-PLAN.md"
  - ".planning/phases/02-container-and-target-ingest/02-02-SUMMARY.md"
  - ".python-version"
  - "compose.yaml"
  - "config/targets.toml"
  - "configure.py"
  - "docker/Dockerfile"
  - "docker/README.md"
  - "docker/compose.yaml"
  - "docs/coding-style.md"
  - "docs/learnings.md"
  - "pyproject.toml"
  - "tests/conftest.py"
  - "tests/test_cli.py"
  - "tests/test_configure.py"
  - "tests/test_hygiene.py"
  - "tests/test_ingest.py"
  - "tests/test_le.py"
  - "tests/test_le_real.py"
  - "tests/test_targets.py"
  - "tools/reverseapoc/__init__.py"
  - "tools/reverseapoc/cli.py"
  - "tools/reverseapoc/ingest.py"
  - "tools/reverseapoc/le.py"
  - "tools/reverseapoc/targets.py"
  - "uv.lock"
covered_digest: "v3:sha256:f7731230d81955e6813f2f823828ea4c392f1a7ecd6e84dd0aee92935885e7bf"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 7/7
  reason: "Report went stale: 02-01-PLAN.md and 02-01-SUMMARY.md were reworded, and commit 5422eba changed covered file tests/test_hygiene.py (new test_no_doc_mentions_a_phase_zero)"
  gaps_closed: []
  gaps_remaining: []
  regressions:
    - "Working tree went red after the full host run: .planning/phases/01-hygiene-and-safety/01-VERIFICATION.md (rewritten 23:18:44Z by a concurrent Phase 1 verification) has 2 lines (49, 129) that fail test_no_doc_mentions_a_phase_zero. tests/test_hygiene.py now gives 1 failed, 13 passed, 3 skipped (truth 4)."
    - "Committed HEAD (5422eba) fails its own new test_no_doc_mentions_a_phase_zero: 10 hits in tracked .planning files whose fixes exist only as uncommitted working-tree edits. Host and container runs on the working tree are green. Pushing HEAD as committed would turn CI red (truth 5)."
human_verification:
  - test: "Commit the uncommitted edits to .planning/PROJECT.md, .planning/REQUIREMENTS.md, .planning/ROADMAP.md, .planning/STATE.md and .planning/research/SUMMARY.md (plus the phase directories) before or together with pushing 5422eba, then push and run `gh run list --limit 1`"
    expected: "The CI run for the pushed HEAD is `completed success`; `git grep -nIiE '\\bphases? 0\\b' HEAD -- '*.md'` over docs/, .planning/, README.md and CLAUDE.md returns 0 lines"
    why_human: "Which tree gets committed and pushed is the owner's decision. The verifier may not commit. At HEAD as committed the test is red (run on a `git archive HEAD` extract: 1 failed)"
  - test: "Reword .planning/phases/01-hygiene-and-safety/01-VERIFICATION.md lines 49 and 129 (written by a concurrent Phase 1 verification at 23:18:44Z, after this report's full host run) so they no longer name a zero-numbered phase, then run `uv run pytest -q` and `docker compose run --rm test`"
    expected: "Host `89 passed, 3 skipped`, container `92 passed`, both exit 0"
    why_human: "The file belongs to the Phase 1 verification and this verifier may write only 02-VERIFICATION.md. It may still be in the middle of being written"
---

# Phase 2: Container and target ingest Verification Report

**Phase Goal:** A contributor with their own game files can build the container, ingest and verify both executables against the hash manifest, and reproduce their scanned LE layout, with tests and ruff green on the host, in the container and in CI.
**Verified:** 2026-10-19T23:18:52Z
**Status:** human_needed
**Re-verification:** Yes. The previous report (passed, 7/7) went stale because 02-01-PLAN.md and 02-01-SUMMARY.md were reworded and commit 5422eba changed `tests/test_hygiene.py`. Every gate was run again.

Every result below comes from a command run during this re-verification. None of it is copied from SUMMARY.md, 02-UAT.md or the previous report.

## What changed since the previous report

- `5422eba`: rewords `docs/workflow.md`, `docs/research/2026-10-19-kickoff-research-report.md` and `docs/research/notes-skills-plugins-frameworks.md`, and adds `test_no_doc_mentions_a_phase_zero` to `tests/test_hygiene.py` (+13 lines). The test scans every `*.md` under `docs/` and `.planning/`, plus `README.md` and `CLAUDE.md`, for a zero-numbered phase.
- 02-01-PLAN.md and 02-01-SUMMARY.md (untracked) were reworded. Their frontmatter still declares the same 5 truths, artifacts, key links and `requirements: [ING-01..ING-05]`.
- `git diff --stat b3fc0d8 HEAD -- tools/ docker/ config/ .github/ .dockerignore .gitignore compose.yaml pyproject.toml uv.lock configure.py tests/` lists only `tests/test_hygiene.py | 13 +`. No code, image, compose, manifest or CI file changed.
- The image `reverseapoc-build:local` is still id db2c6eb44211, built from the unchanged Dockerfile.

## New finding: committed HEAD fails its own new test

The new test passes on the working tree but fails on the tree that is actually committed:

- Working tree, tracked and untracked: `grep` finds 0 matches for the test's regex. Host and container runs are green (below).
- `git grep` on `HEAD` finds 10 matches, all in tracked `.planning/` files: `PROJECT.md:17,44,78`, `REQUIREMENTS.md:10`, `ROADMAP.md:4,37,57`, `STATE.md:33,63`, `research/SUMMARY.md:8`. The edits that remove them are in the working tree but uncommitted (`git status`: ` M` on those five files). The parent tree `5422eba^` had 12.
- Running the named test on a `git archive HEAD` extract in the scratchpad (repo venv, no repo writes): `FAILED tests/test_hygiene.py::test_no_doc_mentions_a_phase_zero`, `1 failed, 1 passed`.

CI checks out the committed tree. If 5422eba is pushed without those five `.planning` edits, CI goes red, which breaks truth 5. Nothing has been pushed yet: local main is 11 commits ahead of origin (`e50784f`). The fix is already in the working tree. It only needs to be committed with or before the push, and committing is the owner's call. So truth 5 is UNCERTAIN, the gap goes to human verification, and it is not filed as a code gap.

## Goal Achievement

### Observable Truths

Truths 1-5 are the roadmap success criteria (the 02-01 must_haves restate them one to one). Truths 6-7 are the 02-02 gap-closure must_haves.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `docker compose build` succeeds; image has Python 3.14 + uv, ninja, objdiff-cli, wibo 1.2.0, OW v2 tools; `orig/` and `third_party/watcom/` read-only at run time and absent from every layer (ING-01) | VERIFIED | Image db2c6eb44211 (Dockerfile unchanged). In the container: `Python 3.14.5`, `uv 0.12.23`, ninja `1.11.1`, `objdiff-cli 3.8.2`, `wibo 1.2.0 (Linux x86_64)`, `wdis`/`wlink`/`wlib` at `/usr/local/bin`, `wcc386 not on PATH`, `uid=1000(dev)`. `/proc/self/mountinfo`: `/work rw`, `/work/orig ro`, `/work/watcom ro`, `/work/third_party ro`. Image run without mounts: `/work` has 0 entries, 0 UFO2P/TACP/SMKP files, 0 `*.iso/*.cue/*.img/*.bin` outside system dirs. `docker history`: the only `COPY` layers copy from build stages (`/opt/watcom-v2`, objdiff-cli, wibo, uv). |
| 2 | `reverseapoc ingest` copies EXEs into `orig/`; `check-orig` exits 0 against `config/targets.toml` (size, CRC32, md5, sha1); a test shows non-zero for a wrong or altered file (ING-02) | VERIFIED | `check-orig`: `OK UFO2P.EXE 1705790`, `OK TACP.EXE 3161594`, `OK SMKP.EXE 271436`, `3 ok, 0 mismatched, 0 missing`, `CHECK_EXIT=0`. The negative-path tests and ingest tests in tests/test_targets.py, tests/test_cli.py and tests/test_ingest.py are unchanged and green in both runs. Ingest was not run against the real game folder, because that would rewrite `orig/`. |
| 3 | `parse-le` on both EXEs reports MZ stub 0x352A4, LE header 0x37F34, two objects at their scanned bases, internal fixups only (ING-03) | VERIFIED | UFO2P: `stub size 0x000352a4`, `LE header 0x00037f34`, objects `0x00010000` (R-X) / `0x000d0000` (RW-), `fixups 28197 (sel16 10, ptr16:32 4, off32 28183)`, `UFO_EXIT=0`. TACP: `stub size 0x000352a4`, `LE header 0x00037f34`, objects `0x00010000` / `0x000e0000`, `fixups 24438 (sel16 10, ptr16:32 4, off32 24424)`, `TACP_EXIT=0`. `le.py` unchanged. |
| 4 | `pytest -q` and `ruff check .` pass on host; `docker compose run --rm test` passes; real-file tests skip unless `orig/` exists (ING-04) | UNCERTAIN | **Was green, now red because of another phase's file.** At 23:13Z, host: `89 passed, 3 skipped in 0.69s`, `PYTEST_EXIT=0` (one more than before: the new docs test). The 3 skips are the container-only W_OK cases. `All checks passed!`, `RUFF_EXIT=0`. Container: `Checked 7 packages`, `92 passed in 1.42s`, `DOCKER_TEST_EXIT=0`. The real-file skipif in tests/test_le_real.py is unchanged. Then, at 23:18:44Z, a concurrent Phase 1 verification rewrote `.planning/phases/01-hygiene-and-safety/01-VERIFICATION.md`. Re-running `uv run pytest -q tests/test_hygiene.py` now gives `1 failed, 13 passed, 3 skipped`: `test_no_doc_mentions_a_phase_zero` flags that file at lines 49 and 129. The Phase 2 code and test work as intended; the test caught a real violation. The fix is in a file this verifier may not write. Sent to human verification. |
| 5 | CI workflow runs tests and ruff on push and passes with no game file (ING-05) | UNCERTAIN | `.github/workflows/ci.yml` unchanged (`on: push`, ruff, pytest). `gh run list --limit 5`: 5/5 `completed success` on main push (latest 39327812497, 2026-10-19T21:28:50Z). HEAD is unpushed (11 ahead), and **HEAD as committed fails `test_no_doc_mentions_a_phase_zero`** (see above). CI will be green only if the five uncommitted `.planning` edits land with the push. Sent to human verification. |
| 6 | Inside the container `/work/orig`, `/work/watcom`, `/work/third_party` and `/work/third_party/watcom` are all non-writable (02-02) | VERIFIED | Fresh `test -w` (no writes): `/work/orig read-only`, `/work/watcom read-only`, `/work/third_party read-only`, `/work/third_party/watcom read-only`; `/work` WRITABLE as intended. The container run had 0 skipped, so the 3 `os.access(W_OK)` cases ran and passed. |
| 7 | Every compose mount of `orig/` or `third_party/` is `:ro` and each sits on its own in-repo path (02-02) | VERIFIED | `docker/compose.yaml` unchanged. The compose-parse tests pass on the host, and mountinfo above shows the ro overlays in effect. |

**Score:** 5/7 truths verified (0 present, behavior-unverified; 2 uncertain, sent to human verification)

### Owner-supplied Watcom media (third_party/watcom-media/)

Still 5 entries, gitignored (`git check-ignore` matches), and `git ls-files third_party orig` returns 0. The image without mounts has 0 disc images. No file contents were read.

### Advisory (New Scope, Unevidenced)

None. The committed-HEAD failure above has deterministic evidence (a named test run red on a HEAD extract) and touches a file modified since the prior `verified:` timestamp. That is why it is reported as a regression with a human-verification item and not as an advisory.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker/Dockerfile` | Pinned toolchain image, no game files | VERIFIED | Unchanged. Tools present, nothing baked in |
| `docker/compose.yaml` | build/test services, ro mounts on own paths | VERIFIED | Unchanged. ro overlays in effect |
| `config/targets.toml` | Manifest for the 3 targets | VERIFIED | `check-orig` 3 ok |
| `tools/reverseapoc/{le,targets,ingest,cli}.py` | Parser, manifest check, ingest, CLI | VERIFIED | Unchanged. Fresh CLI runs above |
| `tests/test_le.py`, `tests/test_le_real.py` | Synthetic and real-file LE tests | VERIFIED | Green on host and in container |
| `tests/test_hygiene.py` | Compose-parse, in-container writability, docs tests | VERIFIED (working tree) | 96 lines. Both docs tests pass on the working tree (`2 passed`). The new test fails on committed HEAD, see truth 5 |
| `.github/workflows/ci.yml` | Tests and ruff on push | VERIFIED | Unchanged. Last 5 runs green |
| `docker/README.md`, `.dockerignore`, `.gitignore` | Mount docs and exclusions | VERIFIED | Unchanged |

`verify.artifacts` and `verify.key-links` were not used. Both plans list artifacts and key_links as plain strings, which the tool cannot evaluate, so they were checked by hand.

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cli.py parse-le` | `le.LE.summary()` -> `format_summary` | `_cmd_parse_le` | WIRED | Fresh parse-le output on both EXEs |
| `cli.py check-orig` | `targets.check_orig(orig, config/targets.toml)` | `_cmd_check_orig` | WIRED | Fresh check-orig output, exit 0 |
| `docker/compose.yaml` test service | `uv sync --locked && uv run pytest -q` | `command:` | WIRED | `Checked 7 packages` then `92 passed` |
| `docker/compose.yaml` x-common.volumes | `../third_party:/work/third_party:ro` | YAML anchor | WIRED | `/work/third_party ro` in mountinfo |
| `test_protected_paths_are_not_writable_in_the_container` | `docker compose run --rm test` | in-container pytest | WIRED | 0 skipped in the container run |
| `compose.yaml` (root) | `docker/compose.yaml` | `include:` | WIRED | All compose commands ran from the repo root |

### Data-Flow Trace (Level 4)

Not applicable. The phase renders no dynamic data.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Host tests | `uv run pytest -q` | `89 passed, 3 skipped`, exit 0 | PASS |
| Lint | `uv run ruff check .` | `All checks passed!`, exit 0 | PASS |
| Container tests | `docker compose run --rm test` | `92 passed in 1.42s`, exit 0 | PASS |
| Protected paths ro | `docker compose run --rm --entrypoint bash test -c 'test -w ...'` (no writes) | 4/4 `read-only`, `/work` writable | PASS |
| Tool versions | same container | Python 3.14.5, uv 0.12.23, ninja 1.11.1, objdiff-cli 3.8.2, wibo 1.2.0, OW wdis/wlink/wlib | PASS |
| Nothing baked into the image | `docker run` without mounts; `docker history` | `/work` empty, 0 game files, 0 disc images, COPY only from stages | PASS |
| Manifest check | `uv run reverseapoc check-orig` | `3 ok, 0 mismatched, 0 missing`, exit 0 | PASS |
| LE layout UFO2P / TACP | `uv run reverseapoc parse-le orig/{UFO2P,TACP}.EXE` | stub 0x352a4, LE 0x37f34, objs 0x10000/0xd0000 and 0x10000/0xe0000, exit 0 | PASS |
| Docs tests, working tree | `uv run pytest -q` on the two docs tests in tests/test_hygiene.py | `2 passed` (before 23:18:44Z) | PASS |
| Hygiene tests after report write | `uv run pytest -q tests/test_hygiene.py` | `1 failed, 13 passed, 3 skipped`: phase-zero hits in 01-VERIFICATION.md:49,129 | FAIL (other phase's file) |
| New docs test, committed HEAD | `git archive HEAD` extract, repo venv `pytest` on the same test | `1 failed, 1 passed` (10 hits in tracked `.planning` files) | FAIL (committed tree only) |
| CI | `gh run list --limit 5` | 5x `completed success`; HEAD unpushed | PASS (history) |

### Probe Execution

No `scripts/*/tests/probe-*.sh` exist and neither plan declares a probe. Not applicable.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ING-01 | 02-01, 02-02 | Docker image with the pinned tools; `orig/` and `third_party/watcom/` read-only, never baked in | SATISFIED | Truths 1, 6, 7 |
| ING-02 | 02-01 | ingest + check-orig against size/CRC32/md5/sha1 | SATISFIED | Truth 2 |
| ING-03 | 02-01 | parse-le reproduces the scanned layout | SATISFIED | Truth 3 |
| ING-04 | 02-01 | pytest/ruff on host and in container; real-file skip | NEEDS HUMAN | Truth 4: green at the full run; red now because of the Phase 1 report |
| ING-05 | 02-01 | CI without game files | NEEDS HUMAN | Truth 5: green so far, but committed HEAD would go red if pushed alone |

All 5 IDs from the plan frontmatter are in REQUIREMENTS.md (lines 19-23, all `[x]`) and mapped to Phase 2 (lines 116-120). No other ID maps to Phase 2, so none are orphaned.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_hygiene.py` | 68, 73 | `TBD` in the rule's comment and regex | Info | Describes the rule. Not a debt marker |
| `docs/coding-style.md` | 34-36 | `XXXXXXXX` | Info | Naming placeholders (`func_XXXXXXXX`), not debt markers |
| `tests/test_hygiene.py` | parametrize of the W_OK test | Covers `/work/orig`, `/work/third_party`, `/work/watcom`, not `/work/third_party/watcom` itself | Info | Covered by the parent ro overlay. The fresh `test -w` confirms it read-only |
| `.planning/phases/01-hygiene-and-safety/01-VERIFICATION.md` | 49, 129 | Names a zero-numbered phase | Warning | Fails `test_no_doc_mentions_a_phase_zero` on the working tree. Not a Phase 2 file |
| commit `5422eba` | - | Test added in a commit whose tracked `.planning` files still fail it | Warning | CI goes red on push unless the pending `.planning` edits are committed too |

### Human Verification Required

### 1. CI stays green once HEAD is pushed

**Test:** Commit the pending edits to `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` and `.planning/research/SUMMARY.md` (plus the phase directories) before or together with the push. Then push and run `gh run list --limit 1`.
**Expected:** The run for the pushed HEAD is `completed success`, and `git grep` for the test's regex over the committed docs, `.planning`, README.md and CLAUDE.md returns 0 lines.
**Why human:** Only the owner decides what gets committed and pushed, and the verifier does not commit. Today the committed HEAD fails the test.

### 2. Host and container tests green again after the Phase 1 report

**Test:** Reword lines 49 and 129 of `.planning/phases/01-hygiene-and-safety/01-VERIFICATION.md` so they do not name a zero-numbered phase. Then run `uv run pytest -q` and `docker compose run --rm test`.
**Expected:** Host `89 passed, 3 skipped`, container `92 passed`, both exit 0.
**Why human:** A concurrent Phase 1 verification wrote that file at 23:18:44Z, after this report's full host run. This verifier may write only 02-VERIFICATION.md, and the Phase 1 report may still be in the middle of being written.

### Gaps Summary

No code gaps. Truths 1-3, 6 and 7 hold on fresh runs. The image, compose file, manifest, CLI and parser are unchanged, and host (89 passed, 3 skipped), container (92 passed) and ruff were green on the working tree at the full run. check-orig and parse-le give the scanned results for both EXEs, and the protected paths are read-only in the container.

One thing went wrong in the commit itself. Commit 5422eba added `test_no_doc_mentions_a_phase_zero`, but the tracked `.planning` files it scans were not fixed in that commit. Their fixes are still uncommitted in the working tree. So the committed HEAD fails the new test (confirmed on a `git archive HEAD` extract), and CI on that commit would fail. Separately, a concurrent Phase 1 verification rewrote `01-VERIFICATION.md` with two lines the same test rejects, so the working tree is red now too (`tests/test_hygiene.py`: 1 failed). The status is human_needed and not passed. The owner has to reword those two Phase 1 lines and commit the five `.planning` edits with the push. Then host, container and CI need to be confirmed green.

---

_Verified: 2026-10-19T23:18:52Z_
_Verifier: Claude (gsd-verifier)_
