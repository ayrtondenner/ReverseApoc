---
phase: 02-container-and-target-ingest
verified: 2026-10-19T23:27:05Z
status: passed
score: 7/7 must-haves verified
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
  previous_status: human_needed
  previous_score: 5/7
  gaps_closed:
    - "Committed HEAD fails its own test_no_doc_mentions_a_phase_zero (truth 5): the .planning edits are committed in 5adc4c5; a git archive HEAD extract (no orig/) gives 77 passed, 15 skipped and ruff clean; git grep over HEAD *.md finds 0 hits for the test's regex"
    - "Working tree red because of 01-VERIFICATION.md lines 49/129 (truth 4): both lines reworded; host 89 passed, 3 skipped; container 92 passed"
  gaps_remaining: []
  regressions: []
---

# Phase 2: Container and target ingest Verification Report

**Phase Goal:** A contributor with their own game files can build the container, ingest and verify both executables against the hash manifest, and reproduce their scanned LE layout, with tests and ruff green on the host, in the container and in CI.
**Verified:** 2026-10-19T23:27:05Z
**Status:** passed
**Re-verification:** Yes. The previous report (human_needed, 5/7) listed two regressions, both in tracked or committed docs, not in code. Both were checked again from scratch, and every other gate was re-run.

Every result below comes from a command run during this re-verification. None of it is copied from SUMMARY.md, 02-UAT.md or the previous report.

## What changed since the previous report

- New commit `5adc4c5` ("Bootstrap GSD retroactively for Phases 1 and 2") adds or updates 20 files, all under `.planning/`. It includes the five `.planning` files the previous report flagged (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md, research/SUMMARY.md) and both phase directories.
- `git status --short` is empty. The working tree equals HEAD.
- `git diff --stat b3fc0d8 HEAD` over tools/, docker/, config/, .github/, tests/, compose.yaml, pyproject.toml, uv.lock, configure.py, .dockerignore and .gitignore lists only `tests/test_hygiene.py | 13 +`, the same as before. `git diff --stat HEAD~1 HEAD` over .github, tools, tests, docker and config is empty.
- The fingerprint over the covered files has not changed: `v3:sha256:f7731230...85e7bf`, the same digest as the previous report.
- The image `reverseapoc-build:local` is still id db2c6eb44211.

## Regression 1 re-checked: committed HEAD and its own new test

- `git archive HEAD` extracted into a new, empty scratch directory (`.../scratchpad/verify-head`). The extract has no `orig/`, so it matches CI's checkout. `tests/conftest.py` sets `REPO_ROOT = Path(__file__).resolve().parents[1]`, and pytest reported `rootdir:` as the extract, so the docs tests scanned the extracted tree and not the repo.
- `uv run --project <repo> --no-sync python -m pytest -q -p no:cacheprovider tests` in the extract gives `77 passed, 15 skipped in 1.18s`, exit 0. The 15 skips are the real-file tests, which skip without `orig/`, and the 3 container-only W_OK cases.
- The same test file run verbose with `-k "phase_zero or tbd or doc"` gives `10 passed`, and `test_no_doc_mentions_a_phase_zero` is one of them.
- `ruff check --no-cache .` in the extract: `All checks passed!`, exit 0.
- `git grep -nIiE '\bphases? 0\b' HEAD -- '*.md'` returns 0 lines, and `git grep -nIiE '^\| 0\. ' HEAD -- '*.md'` returns 0 lines. That covers both alternatives of the test's regex. In the previous report it was 10 lines.

**Refuted.** The committed tree passes its own test and ruff without game files.

## Regression 2 re-checked: 01-VERIFICATION.md lines 49 and 129

- Line 49 now reads "the numbering banner and the old-label notes are gone ...". Line 129 now reads "Commit subject uses the pre-GSD label ...". Neither line names a zero-numbered phase.
- A working-tree `grep` with the test's regex over `docs/`, `.planning/`, README.md and CLAUDE.md finds 0 matches.
- Host `uv run pytest -q`: `89 passed, 3 skipped in 0.67s`, exit 0. Container `docker compose run --rm test`: `92 passed in 6.00s`, exit 0.

**Refuted.** Host and container are green again.

## Goal Achievement

### Observable Truths

Truths 1-5 are the roadmap success criteria (the 02-01 must_haves restate them one to one). Truths 6-7 are the 02-02 gap-closure must_haves.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `docker compose build` succeeds; image has Python 3.14 + uv, ninja, objdiff-cli, wibo 1.2.0, OW v2 tools; `orig/` and `third_party/watcom/` read-only at run time and absent from every layer (ING-01) | VERIFIED | Image db2c6eb44211, built from an unchanged Dockerfile (no Dockerfile diff since b3fc0d8). Fresh `/proc/self/mountinfo` in the container: `/work rw`, `/work/orig ro`, `/work/third_party ro`, `/work/watcom ro`. The tool versions and the absence of baked-in files are not re-checked here, because the image id is the same one the previous report checked (Python 3.14.5, uv 0.12.23, ninja 1.11.1, objdiff-cli 3.8.2, wibo 1.2.0, OW wdis/wlink/wlib; `/work` empty without mounts, no game files or disc images). `git ls-files orig third_party` returns 0; `third_party/watcom-media` is gitignored. |
| 2 | `reverseapoc ingest` copies EXEs into `orig/`; `check-orig` exits 0 against `config/targets.toml` (size, CRC32, md5, sha1); a test shows non-zero for a wrong or altered file (ING-02) | VERIFIED | `check-orig`: `OK UFO2P.EXE 1705790`, `OK TACP.EXE 3161594`, `OK SMKP.EXE 271436`, `3 ok, 0 mismatched, 0 missing`, exit 0. The negative-path and ingest tests (tests/test_targets.py, tests/test_cli.py, tests/test_ingest.py) are unchanged and green on the host, in the container and in the HEAD extract. Ingest was not run against the game folder, because that would rewrite `orig/`. |
| 3 | `parse-le` on both EXEs reports MZ stub 0x352A4, LE header 0x37F34, two objects at their scanned bases, internal fixups only (ING-03) | VERIFIED | UFO2P: `stub size 0x000352a4`, `LE header 0x00037f34`, objects `0x00010000` R-X / `0x000d0000` RW-, `fixups 28197 (sel16 10, ptr16:32 4, off32 28183)`, exit 0. TACP: `stub size 0x000352a4`, `LE header 0x00037f34`, objects `0x00010000` R-X / `0x000e0000` RW-, `fixups 24438 (sel16 10, ptr16:32 4, off32 24424)`, exit 0. |
| 4 | `pytest -q` and `ruff check .` pass on host; `docker compose run --rm test` passes; real-file tests skip unless `orig/` exists (ING-04) | VERIFIED | Host: `89 passed, 3 skipped`, exit 0. The 3 skips are the container-only W_OK cases. Ruff: `All checks passed!`, exit 0. Container: `Checked 7 packages`, `92 passed in 6.00s`, exit 0, 0 skipped. Real-file skip: the HEAD extract has no `orig/` and gives 15 skipped (12 real-file and 3 container-only), against 3 on the host where `orig/` exists. |
| 5 | CI workflow runs tests and ruff on push and passes with no game file (ING-05) | VERIFIED | `.github/workflows/ci.yml`: `on: push`, `runs-on: ubuntu-latest`, `uv sync --locked`, `uv run ruff check .`, `uv run pytest -q`. `gh run list --limit 5`: 5/5 `completed success` on main push (latest 39327812497, 2026-10-19T21:28:50Z). HEAD (5adc4c5) is not pushed yet; it is 12 commits ahead of origin/main (e50784f). The committed tree was reproduced the way CI sees it (a `git archive HEAD` extract with no game files): `77 passed, 15 skipped`, ruff clean. The same tree passes on Linux in the container (92 passed), so the result does not depend on the OS. |
| 6 | Inside the container `/work/orig`, `/work/watcom`, `/work/third_party` and `/work/third_party/watcom` are all non-writable (02-02) | VERIFIED | Fresh `test -w` (no writes): `/work/orig read-only`, `/work/watcom read-only`, `/work/third_party read-only`, `/work/third_party/watcom read-only`; `/work WRITABLE` as intended. The container run had 0 skipped, so the 3 parametrized `os.access(W_OK)` cases ran and passed. |
| 7 | Every compose mount of `orig/` or `third_party/` is `:ro` and each sits on its own in-repo path (02-02) | VERIFIED | `docker/compose.yaml` unchanged since b3fc0d8. The compose-parse tests pass on the host and in the HEAD extract, and mountinfo shows the ro overlays in effect. |

**Score:** 7/7 truths verified (0 present, behavior-unverified)

### Advisory (New Scope, Unevidenced)

None.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker/Dockerfile` | Pinned toolchain image, no game files | VERIFIED | Unchanged. Same image id |
| `docker/compose.yaml` | build/test services, ro mounts on own paths | VERIFIED | Unchanged. ro overlays in effect |
| `config/targets.toml` | Manifest for the 3 targets | VERIFIED | `check-orig` 3 ok |
| `tools/reverseapoc/{le,targets,ingest,cli}.py` | Parser, manifest check, ingest, CLI | VERIFIED | Unchanged. Fresh CLI runs above |
| `tests/test_le.py`, `tests/test_le_real.py` | Synthetic and real-file LE tests | VERIFIED | Green on host and in container; real-file cases skip in the HEAD extract |
| `tests/test_hygiene.py` | Compose-parse, in-container writability, docs tests | VERIFIED | Green on the working tree, in the container and on committed HEAD |
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
| Committed tree, CI-like (no orig/) | `git archive HEAD` extract; repo venv `python -m pytest -q -p no:cacheprovider tests` | `77 passed, 15 skipped`, exit 0 | PASS |
| Committed tree, docs tests | same extract, `tests/test_hygiene.py -k "phase_zero or tbd or doc" -v` | `10 passed` | PASS |
| Committed tree, lint | same extract, `ruff check --no-cache .` | `All checks passed!`, exit 0 | PASS |
| Committed docs, test regex | `git grep` for both regex alternatives over `HEAD -- '*.md'` | 0 lines | PASS |
| Host tests | `uv run pytest -q` | `89 passed, 3 skipped`, exit 0 | PASS |
| Lint | `uv run ruff check .` | `All checks passed!`, exit 0 | PASS |
| Container tests | `docker compose run --rm test` | `92 passed in 6.00s`, exit 0 | PASS |
| Protected paths ro | `docker compose run --rm --entrypoint bash test -c 'test -w ...'` (no writes) | 4/4 `read-only`, `/work` writable; mountinfo ro on orig, watcom, third_party | PASS |
| Manifest check | `uv run reverseapoc check-orig` | `3 ok, 0 mismatched, 0 missing`, exit 0 | PASS |
| LE layout UFO2P / TACP | `uv run reverseapoc parse-le orig/{UFO2P,TACP}.EXE` | stub 0x352a4, LE 0x37f34, objs 0x10000/0xd0000 and 0x10000/0xe0000, exit 0 | PASS |
| CI | `gh run list --limit 5` | 5x `completed success`; HEAD unpushed (12 ahead) | PASS (history) |

### Probe Execution

No `scripts/*/tests/probe-*.sh` exist and neither plan declares a probe. Not applicable.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ING-01 | 02-01, 02-02 | Docker image with the pinned tools; `orig/` and `third_party/watcom/` read-only, never baked in | SATISFIED | Truths 1, 6, 7 |
| ING-02 | 02-01 | ingest + check-orig against size/CRC32/md5/sha1 | SATISFIED | Truth 2 |
| ING-03 | 02-01 | parse-le reproduces the scanned layout | SATISFIED | Truth 3 |
| ING-04 | 02-01 | pytest/ruff on host and in container; real-file skip | SATISFIED | Truth 4 |
| ING-05 | 02-01 | CI without game files | SATISFIED | Truth 5 |

All 5 IDs from the plan frontmatter are in REQUIREMENTS.md (lines 19-23, all `[x]`) and mapped to Phase 2 (lines 116-120). No other ID maps to Phase 2, so none are orphaned.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_hygiene.py` | 68, 73 | `TBD` in the rule's comment and regex | Info | Describes the rule. Not a debt marker |
| `docs/coding-style.md` | 34-36 | `XXXXXXXX` | Info | Naming placeholders (`func_XXXXXXXX`), not debt markers |
| `tests/test_hygiene.py` | parametrize of the W_OK test | Covers `/work/orig`, `/work/third_party`, `/work/watcom`, not `/work/third_party/watcom` itself | Info | Covered by the parent ro overlay. The fresh `test -w` confirms it read-only |
| commit `5adc4c5` message | - | Says the two VERIFICATION.md files were "both passed", but the committed 02-VERIFICATION.md is `human_needed`, 5/7 | Info | A commit message can't be changed without rewriting history. This report replaces the committed file |
| `.planning/phases/01-hygiene-and-safety/01-VERIFICATION.md` | 49 | Calls the ROADMAP.md edit "(uncommitted)", which 5adc4c5 has since committed | Info | A stale note in a Phase 1 file. It does not affect Phase 2 or any test |

### Human Verification Required

None. After the push, it is still worth checking that the first CI run of `5adc4c5` is green with `gh run list --limit 1`. This is not a gate: the committed tree was already reproduced without game files and passed.

### Gaps Summary

No gaps. Both regressions in the previous report are refuted on fresh evidence. Commit 5adc4c5 contains the `.planning` edits, and a `git archive HEAD` extract with no `orig/` passes the whole suite (77 passed, 15 skipped), including `test_no_doc_mentions_a_phase_zero`, and ruff. The two lines in 01-VERIFICATION.md were reworded, so the host (89 passed, 3 skipped) and the container (92 passed) are green again. The code, image, compose file, manifest and CI workflow are unchanged, and the fingerprint digest is the same as before. check-orig and parse-le give the scanned results for both EXEs, and all four protected paths are read-only in the container. All 7 truths and all 5 ING requirements are met.

---

_Verified: 2026-10-19T23:27:05Z_
_Verifier: Claude (gsd-verifier)_
