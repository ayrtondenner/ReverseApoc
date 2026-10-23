---
phase: "04"
slug: "compiler-identification"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-10-21"
---

# Phase 04 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register: the `<threat_model>` blocks of plans 04-01..04-12 (41 unique threats). Verified against the code on main at 0f5f4ac by gsd-security-auditor (ASVS L1, block_on: high); evidence per threat is in the audit run recorded below.
> Gap closure 04-13 (G-04-2) adds T-04-41..47 and re-accepts T-04-SC. They were verified at L1 grep depth against main at f1cc86d (short-circuit: threats_open 0, plan-time register, ASVS 1). The 2026-10-22 audit row below records the evidence.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| config/cflags.txt -> compiler argv | committed per-file rules reach the compiler's command line | flags (refused: wrapper-owned prefixes in any case, a second `-`, `/`, `\`, whitespace) |
| host environment -> compiler child | WCC386/INCLUDE/WATCOM could inject options | environment (scrubbed to PATH, plus SYSTEMROOT/TEMP/TMP on win32) |
| compiler output -> repository tree | objects and `.err` files land on disk | object files (must end `.obj`, never resolve to the source) |
| third_party/watcom trees -> compiler gate | user-supplied compiler binaries are executed | executables (size, CRC-32, MD5, SHA-1 checked against config/watcom.toml; KNOWN BAD refused) |
| ISO / wpack parts -> decoder -> installed tree | user-supplied archive bytes become an executable | archive parts (bounds, CRC, size checked; writes contained in the `.partial` tree) |
| manifest edit -> every contributor's gate | the 10.5 pin decides what binary all builds trust | hashes of the decoded compiler (owner-sanctioned D-01) |
| Watcom LIB/OBJ bytes -> OMF parser | user-supplied binaries parsed record by record | library modules (bounded; failures recorded, never fatal to the sweep) |
| orig/ EXE + LIB bytes -> matcher, probe, C/C++ scan | game and library bytes parsed and compared | addresses, names, counts out (never bytes) |
| matcher -> runtime.csv (committed) | the only Phase 4 file derived from game and library bytes that is committed | hex addresses, Watcom symbol names, versions, status |
| CLI arguments -> filesystem | `--output`/`--write` choose where files go | paths (refused inside orig/ or the Watcom tree) |
| Open Watcom source -> our code | licence boundary (OWPL vs GPLv3) | format knowledge only (D-15) |
| concurrent `cc` processes -> one cc.log (04-13) | many writers append the provenance record at once, within one environment | one log line per compile (serialised by the OS lock on `<log>.lock`) |
| host process and container process -> one cc.log on the bind mount (04-13) | two OS lock domains that do not see each other | log lines (declared unsupported; each side uses its own `--log`) |
| `--log` argument -> sidecar `<log>.lock` (04-13) | a user-chosen path decides where the lock file is created | an empty lock file beside the log |
| tests -> REPO_ROOT/build (04-13) | tests write logs, objects and lock files into the gitignored build tree | build/test-cclog/<test>/ and build/test-cc/<test>/ only |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-04-01 | Tampering | compiler child environment | high | mitigate | scrubbed_env keeps only PATH (+SYSTEMROOT/TEMP/TMP on win32); test_env_is_scrubbed asserts WCC386/WPP386/WCL386/INCLUDE/WATCOM are absent | closed |
| T-04-02 | Tampering | guest_path / build_argv | high | mitigate | _SAFE_PATH allowlist, refusal of spaces, leading `-`, `..` and outside-root sources/objects, `/` rewritten to `\\`; list argv, never a shell; test_guest_path_refusals | closed |
| T-04-03 | Tampering | cflags flags | medium | mitigate | WRAPPER_OWNED prefixes and `/`, `\\`, whitespace refused per line with file:line errors (Task 2 tests) | closed |
| T-04-04 | Spoofing | compiler binary | high | mitigate | check_gate verifies size+SHA-1 of every executed/loaded binary against config/watcom.toml and refuses known-bad; the stamp is rechecked against the manifest's current SHA-1 and file mtime/size | closed |
| T-04-05 | Tampering | files written by the compiler | medium | mitigate | -fo and -fr targets derive from the -o path inside the root; stale and failed objects are removed; test_err_file_stays_under_object_dir | closed |
| T-04-06 | Information disclosure | stdout and build/logs/cc.log | low | mitigate | lines carry banner, paths, argv, exit status and SHA-1s only; no compiler bytes are read into output | closed |
| T-04-07 | Denial of service | LIDATA expansion | medium | mitigate | LIDATA_MAX_DEPTH recursion cap and output bounded by the SEGDEF length (test_lidata_expands_nested_blocks) | closed |
| T-04-08 | Denial of service | record and segment bounds | medium | mitigate | _Cursor bounds checks raise OMFError; LEDATA writes are checked against the SEGDEF length; record lengths running past the data raise | closed |
| T-04-09 | Repudiation | library sweep completeness | medium | mitigate | ModuleFailure records every unparsed module with library, index and offset; non-OMF libraries are reported, never skipped silently (test_lib386_sweep) | closed |
| T-04-10 | Information disclosure | errors, tests and summaries | low | mitigate | messages name record types, offsets and counts only; fixtures are synthetic literals in tests/omfimage.py | closed |
| T-04-11 | Denial of service | decode_member output | medium | mitigate | output bounded by the member length, which must equal expected_size (the manifest size) before decoding starts; overruns raise WpackError | closed |
| T-04-12 | Tampering | malformed archives | medium | mitigate | signature, info-table bounds and the compressed-span CRC-32 are checked before decoding; truncated streams raise WpackError (tests per case) | closed |
| T-04-13 | Tampering (licence) | tools/reverseapoc/wpack.py | medium | mitigate | format description committed first (verify checks ancestry), header states no OWPL code or comments copied; owner confirms A1 | open — below high threshold (non-blocking): owner sign-off of A1 pending |
| T-04-14 | Tampering | archive-embedded names | low | mitigate | the decoder returns bytes only and never writes a file under an archive-supplied name; plan 04-06 writes only the manifest path | closed |
| T-04-15 | Tampering | option injection through WCC386/INCLUDE | high | mitigate | test_env_injection_has_no_effect proves on real codegen that the scrubbed environment neutralises them (normalized SHA-1 equal) | closed |
| T-04-16 | Tampering | stray files from failed compiles | medium | mitigate | test_compile_error_cleans_up asserts no object at -o and no .err in the repository root | closed |
| T-04-17 | Information disclosure | logs and test output | low | mitigate | logs and assertions use SHA-1s, names and short literal encodings; no object bytes are printed | closed |
| T-04-18 | Information disclosure | runtime.csv, reports, JSON | high | mitigate | rows hold hex addresses, segment/module/library/public names, versions and status only; test_runtime_csv_holds_addresses_and_names_only rejects byte-like cells | closed |
| T-04-19 | Repudiation | false or silent matches | medium | mitigate | both-side masks with required LE fixups at absolute sites; skipped, dropped and ambiguous results are all reported; disambiguation never empties a group | closed |
| T-04-20 | Denial of service | malformed LE/OMF input | low | mitigate | LEError/OMFError bounds checks; parse failures recorded as skips; partial overlaps raise LibMatchError | closed |
| T-04-21 | Tampering | CSV output path | medium | mitigate | --write goes only to config_dir(name)/runtime.csv (bare-name check), --output only to the named file, both through _write_atomic; the orig file must pass check_target first | closed |
| T-04-22 | Tampering | config/watcom.toml 10.5 pin | high | mitigate | values derived from this plan's decode, cross-checked by an independent hash_file run and plan 04-03's LANDED values, banner checked before pinning, one reviewed commit touching one entry; test_decoded_compiler_matches_manifest re-derives them from the ISO on every real run | closed |
| T-04-23 | Tampering | install_version write targets | medium | mitigate | decoded bytes are written only to partial / kf.path from the manifest, never to an archive-supplied name; extract_all keeps its path-traversal guard | closed |
| T-04-24 | Denial of service | bad or oversized decode | low | mitigate | decode_member refuses a member length that differs from the manifest size before decoding; failures remove the partial tree (test_install_wpack_corrupt_part_fails_cleanly) | closed |
| T-04-25 | Tampering | hand edits of runtime.csv | medium | mitigate | the drift test re-derives both files from orig/ and the libraries and fails on any difference; the files carry a "do not edit" header | closed |
| T-04-26 | Information disclosure | committed CSVs | high | mitigate | test_committed_runtime_csvs_are_names_and_addresses runs in CI and rejects byte-like cells; review before commit | closed |
| T-04-27 | Tampering (licence) | probe/cg_basic.c | medium | mitigate | clean-room C89 written in-house with a header saying so; mosura files are not copied (licence unverified) | closed |
| T-04-28 | Information disclosure | calibration output | low | mitigate | Calibration.format/to_json carry counts, library names and SHA-1s only; tests use hand-written instruction encodings | closed |
| T-04-29 | Repudiation | calibration results | medium | mitigate | deviations from research are recorded, not forced; ties are reported as ties (D-10) | closed |
| T-04-30 | Information disclosure | strings and tables in output | medium | mitigate | string_counts returns counts only; the report holds addresses, priorities, counts and module names | closed |
| T-04-31 | Repudiation | false C++ evidence from identical stubs | medium | mitigate | only unique C++-only rows count (plan 04-05's disambiguation resolves the Pitfall 4 stubs first); vtable-shaped runs never decide; test_vtables_never_decide | closed |
| T-04-32 | Denial of service | malformed tables | low | mitigate | table length must be a multiple of 6 and inside the data object, else CppScanError | closed |
| T-04-33 | Repudiation | counts include library code | medium | mitigate | scan_exe excludes every runtime.csv range; a missing map is refused; boundary-touching matches are not counted (tests) | closed |
| T-04-34 | Information disclosure | scan output | low | mitigate | output holds counts, addresses, blocks and names only | closed |
| T-04-35 | Tampering | calibration JSON input | low | mitigate | Calibration.from_json validates the shape and refuses malformed files (test_probe_scan_bad_calibration_json) | closed |
| T-04-36 | Repudiation | docs claiming beyond evidence | medium | mitigate | every Result/Flags cell cites the command and log behind it; candidates are labelled; hygiene tests pin the cflags rule to the docs | closed |
| T-04-37 | Information disclosure | docs, logs, spike record | medium | mitigate | only counts, addresses, names, banners and SHA-1s are written; logs are gitignored and reproduced in the SUMMARY | closed |
| T-04-38 | Tampering | third_party/watcom/10.5 | low | mitigate | changed only through `install-watcom 10.5 --force` against the pinned manifest, then verified by check-watcom | closed |
| T-04-39 | Repudiation | gate completeness | medium | mitigate | one log per step with an exit line; verify fails on any missing log, non-zero exit or skipped real-file test; notes cannot replace a run | closed |
| T-04-40 | Information disclosure | logs and SUMMARY | low | mitigate | cmp without -l; logs hold summaries, OK lines with manifest SHA-1s, counts and names | closed |
| T-04-41 | Repudiation | compiler._append_log: cc.log, the record of which compiler@version and flags built each object | medium | mitigate | `_append_log` writes the precomputed line inside `with _log_lock(log)`, opening and closing the log inside the lock (compiler.py:466-476). The concurrent-append test (16x25, repo-build and tmp-path) and the 16 real parallel `cc` test pass; mutants M1 (host, container) and M2 (container) fail them (build/gate/04-13/mutants) | closed |
| T-04-42 | Denial of service | the log lock when a `cc` dies while holding it | medium | mitigate | fcntl.flock / msvcrt.locking OS locks; the sidecar is opened "a+b" and never deleted, and compiler.py has no mkdir/O_EXCL lock (its only `unlink` calls are for objects). test_a_killed_lock_holder_does_not_block_later_appends passes, and M5 (mkdir lock) fails it | closed |
| T-04-43 | Denial of service | the win32 lock spin | low | mitigate | `_try_lock` uses LK_NBLCK only and re-raises any errno other than EACCES (compiler.py:421-430), with a 1 ms `_LOCK_RETRY_SECONDS`. test_lock_does_not_swallow_other_errors (EBADF) passes, and M3 fails it | closed |
| T-04-44 | Tampering | host and container appending to one log at the same time | low | accept | docs/toolchain.md "wibo" says the host and a container writing the same log at the same time is not supported, and says to give each its own `--log` | closed (accepted risk, logged below) |
| T-04-45 | Information disclosure | cc.log content and the sidecar | low | mitigate | `_log_line` is byte-identical to the version before 04-13 (the plan's invariant diff exits 0). The sidecar test asserts `my.log.lock` has size 0 | closed |
| T-04-46 | Tampering | tests writing under REPO_ROOT/build | low | mitigate | the `shared_dir` fixture is build/test-cclog/<test> and is removed before and after each test (shutil.rmtree, tests/test_cc_log.py:118-122). The real test uses the existing build/test-cc/<test> fixture | closed |
| T-04-47 | Repudiation | gate completeness | medium | mitigate | build/gate/04-13/01..05 each end in `exit=0`, and the 6 required mutant logs end in `exit=1`. The plan's Task 3 verify checks (real-file skips, container skip reasons, 5x repeats) and the SUMMARY "## Phase gate output" check exit 0, re-run by the orchestrator | closed |
| T-04-SC | Tampering | package installs | low | accept | no package is installed: stdlib only, pytest and ruff already locked in uv.lock | closed (accepted risk, logged below) |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-04-01 | T-04-SC | Supply chain: Phase 4 adds no dependency (pyproject.toml/uv.lock unchanged since Phase 1, `dependencies = []`; every new module imports the stdlib only). Accepted in all twelve plan threat models. Re-accepted by 04-13: the lock uses fcntl/msvcrt/contextlib/errno/time, and pyproject.toml and uv.lock are unchanged from 9b4dca2 to f1cc86d. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-21 |
| AR-04-02 | T-04-44 | The host and a container appending to one cc.log at the same time can still lose lines (measured: 222/1200), because their OS locks do not see each other. A server-enforced mkdir/O_EXCL lock was rejected: it wedges on a stale lock after a crash. Documented as unsupported in docs/toolchain.md "wibo". | plan 04-13 threat model (design A of the G-04-2 diagnosis), recorded by the orchestrator | 2026-10-22 |

---

## Open Item for the Owner

- **T-04-13 (licence, medium, non-blocking).** Two of its three mitigations are verified: the wpack format description was committed first (43eb1fa is an ancestor of b5d8e3d) and wpack.py's header states no OWPL code or comments were copied (an independent review compared it against the OW reference copies and found nothing copied; the LZHUF tables equal the published 1988 values). The third, "owner confirms A1" after implementation, is not recorded: D-15 records the approach decided beforehand. Close it by confirming A1 (or recording the remainder as an accepted risk) and re-running `/gsd-secure-phase 4`.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-21 | 41 | 40 | 1 (non-blocking, below high) | gsd-security-auditor (ASVS L1, block_on high) via /gsd-execute-phase 4 verify:post |
| 2026-10-22 | 48 | 47 | 1 (T-04-13, unchanged, non-blocking, below high) | orchestrator L1 grep short-circuit via /gsd-execute-phase 04 --gaps-only verify:post (04-13 adds T-04-41..47, all closed) |

Observations from the audit (status unchanged): the real env-injection and failed-compile cleanup proofs (T-04-15/16) still run for 10.6 and 11.0 only (`tests/test_compiler_real.py` RUNNABLE); a failing assertion in those tests would print a shortened repr of in-repo probe object bytes (T-04-17); three supplementary doc claims rest on scratch checks cited in 04-11-SUMMARY rather than build/gate logs (T-04-36).

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-21; 04-13 threats verified 2026-10-22 (T-04-13 owner sign-off pending, non-blocking)
