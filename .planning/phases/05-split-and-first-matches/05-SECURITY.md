---
phase: "05"
slug: "split-and-first-matches"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-10-24"
---

# Phase 05 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register: the `<threat_model>` blocks of plans 05-01..05-20 (T-05-01..46 plus T-05-SC, which appears in all 20 plans: accepted at low in 18, mitigated in 05-03 (capstone install, high) and 05-12 (apt packages, medium)). SUMMARY threat flags (05-07, 05-08, 05-10, 05-13, 05-16, 05-18, 05-19, 05-20) report no new surface.
> Verified at L1 grep depth against main at 25c5c49 (short-circuit: threats_open 0, plan-time register, ASVS 1, block_on high). Evidence per threat is in the Mitigation column; gate logs are in the gitignored build/gate/05-evidence/.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| owner's Watcom tree and orig/ -> spike 005 output | proprietary source and game bytes are read | names, addresses, counts, booleans, percentages, SHA-1s only; objects stay in build/spike005/ |
| spike verdict -> later plans | a wrong verdict would pick the wrong pipeline | verdict text (P3: objdiff is not the gate) |
| compiled OMF object -> omf2elf | malformed or unexpected objects | refused with Omf2ElfError/ElfError before output |
| PyPI -> uv.lock -> host and container venvs | third-party native code (capstone C library) | wheel pinned by exact version and lockfile hashes |
| committed CSVs -> every tool | hand-edited or malformed config feeds the writers and checkers | addresses, names, enums, evidence words (no bytes) |
| repository include/ -> proprietary compiler | headers reach every compile | `-i=` list, repo include first |
| OMF libraries and objects -> omf.py | LIB386 and our objects parsed; NBKPAT writes into data | bounded cursor, range-checked writes |
| orig/ bytes -> discovery, target objects, asm listings | game bytes decoded or copied | counts and addresses out; objects and listings stay in gitignored build/ and asm/ |
| our compiled object -> match oracle | an objdiff-100% but wrong function must not land | relocation check verdict, whole-EXE SHA-1 |
| landed image -> build/ | rebuilt EXE written beside the originals' copies | refused inside orig/ and over the source |
| Python driver -> Ghidra JVM and LE loader | subprocess on the game EXE | list argv, manifest-selected target; export holds addresses and names |
| GitHub release downloads -> image | Ghidra, loader, objdiff-cli, Open Watcom snapshot | SHA-256 checked in the build |
| build context -> image layers | checkout holds orig/ and third_party/ | none: only `COPY --from=<stage>`, .dockerignore |
| tool output -> committed config and src/ | generated rows, verdicts and unit scaffolds | verdicts need reasons; unit files never overwritten |
| unit and file names -> build.ninja commands | names reach /bin/sh and CreateProcess | `[a-z0-9_]+` names, escaped and option-checked paths |
| check verdict -> Phase 6 driver and commits | exit 0 means "matched" | exit 0 only when objdiff, reloc check and every splice SHA-1 agree |
| agent-drafted C -> match verdict | only `check` decides | check JSON, `ninja verify` |
| evidence logs -> sign-off | recorded outputs become the phase's proof | log exit lines and JSON, not prose |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-05-01 | Information disclosure | spike.py output, README | high | mitigate | spike.py prints only PASS/FAIL claim lines; README holds counts, percentages and SHA-1s; objects under gitignored build/spike005/ | closed |
| T-05-02 | Tampering | third_party/watcom/10.6 | medium | mitigate | docker/compose.yaml mounts third_party and third_party/watcom `:ro`; no CMAIN386 file is tracked (`git ls-files` empty) | closed |
| T-05-03 | Spoofing | objdiff as the oracle | high | mitigate | spike 005 README records the P3 blind spot (2nd relocation scores 100.0) and states the relocation check (plan 05-09) is the gate | closed |
| T-05-04 | Denial of service | omf2elf.convert on malformed input | low | mitigate | `_refuse()` runs every refusal (publics, unmaskable, iterated COMDAT, BSS, location, target, field) before any section is built; cli.py funnels Omf2ElfError and ElfError to exit 1 | closed |
| T-05-05 | Tampering | convert_file output | low | mitigate | `convert_file` refuses `dst.resolve() == src.resolve()` and writes through `splice._write_atomic` | closed |
| T-05-06 | Information disclosure | tests/test_x86.py | medium | mitigate | module docstring states every byte string is made up; no `orig` reference in the file | closed |
| T-05-07 | Tampering | capstone version drift | low | mitigate | `x86.check_capstone` compares `importlib.metadata.version` to `CAPSTONE_VERSION = "5.0.9"`; uv.lock pins sha256; CI and compose test run `uv sync --locked` | closed |
| T-05-08 | Tampering | CSV readers | medium | mitigate | functions.py `_load` checks the exact header, enums, sorted/non-overlapping rows, and raises FunctionsError with the data row number | closed |
| T-05-09 | Information disclosure | committed CSV schemas | medium | mitigate | headers are address/name/kind/unit/evidence/verdict/reason only and readers refuse extra fields; a scan of the eight committed CSVs finds no byte-like or instruction content | closed |
| T-05-10 | Tampering | `-i=` include list | medium | mitigate | compiler.py builds one `-i=` with the root's include/ first then the version's H; test_include_is_own_tree_only, test_include_list_puts_the_repo_include_first, test_cflags_cannot_add_an_include | closed |
| T-05-11 | Spoofing | INCLUDE_ASM marker | medium | mitigate | tests/test_stub_real.py compiles markers for real: no marker EXTDEF, no public, identical `_TEXT` to the control, empty text for a markers-only file | closed |
| T-05-12 | Denial of service | `_nbkpat`, `_comdat` 0xC2 | low | mitigate | `_add_patches` calls `target.check_range` before each write; unknown COMDAT names and continuation-without-first raise OMFError | closed |
| T-05-13 | Tampering | omf2elf on unsupported input | medium | mitigate | refusals run before conversion; `_write_atomic` only after `write_elf`; no fallback path | closed |
| T-05-14 | Denial of service | recursive descent | low | mitigate | discover.py uses a `pending` worklist (no recursion), a `visited` set and decode windows clipped to the code object end | closed |
| T-05-15 | Information disclosure | Discovery.format/to_json | medium | mitigate | `to_json` and `format`/`__repr__` emit counts only | closed |
| T-05-16 | Spoofing | target byte source | high | mitigate | target.py cuts from `load_flat(relocate=False)` only, no Ghidra input; tests compare unrelocated bytes | closed |
| T-05-17 | Tampering | page-straddling fields | medium | mitigate | relocations from `le.fixups()`; test_straddler pins one relocation and the rewrite across the page | closed |
| T-05-18 | Spoofing | match decision | high | mitigate | relocs.py imports no ELF or objdiff code; test_wrong_second_relocation plants spike P3; `build_patch` raises LandError when `reloc.ok` is false | closed |
| T-05-19 | Tampering | splice of call fields | high | mitigate | `build_patch` keeps original bytes at fields only after a passing check; `land` compares the whole-EXE SHA-1 to the manifest (no default expected SHA-1) | closed |
| T-05-20 | Tampering | landed EXE path | medium | mitigate | `write_landed` calls `_refuse_inside_orig` and `_refuse_same_file`, then `_write_atomic` | closed |
| T-05-21 | Elevation of privilege | analyzeHeadless on orig/ | medium | mitigate | ghidra.py: container-only (missing install gives the container hint), `TemporaryDirectory` project with `-deleteProject`, outputs refused inside orig/; orig mounted `:ro` | closed |
| T-05-22 | Tampering | argv construction | medium | mitigate | argv is a list passed to `subprocess.run` (no shell); target name from `select_target(load_manifest(...))` | closed |
| T-05-23 | Information disclosure | drafts and export | medium | mitigate | ExportFunctions.java writes addresses and names only; drafts go to asm/<exe>/ghidra/ (asm/ gitignored) | closed |
| T-05-24 | Information disclosure | asm listings, score output | high | mitigate | listings written under asm/ (gitignored, `git check-ignore` confirms); score.py states nothing prints bytes; test_asm uses a synthetic LE | closed |
| T-05-25 | Tampering | asm output path | low | mitigate | `_cmd_asm` calls `refuse_output(out_dir, orig, DEFAULT_ORIG, DEFAULT_INSTALL)`; `write_listings` uses `_write_atomic` | closed |
| T-05-26 | Tampering | Ghidra and loader zips | high | mitigate | Dockerfile pins GHIDRA_SHA256 and LXLOADER_SHA256 with `sha256sum -c`; test_dockerfile_pins_ghidra, test_dockerfile_checks_every_download | closed |
| T-05-27 | Information disclosure | image layers | high | mitigate | only `COPY --from=<stage>`, no ADD; .dockerignore excludes orig/, third_party/, asm/, build/, executables and disc images; test_dockerfile_copies_nothing_from_the_context | closed |
| T-05-28 | Elevation of privilege | analyzeHeadless in the container | medium | mitigate | Dockerfile `USER dev`; orig/ and third_party/ mounted `:ro` (test_every_mount_of_a_protected_dir_is_read_only); `-deleteProject` | closed |
| T-05-29 | Repudiation | boundaries.csv verdicts | medium | mitigate | `_parse_boundary` raises "verdict needs a reason"; `missing_verdicts` reports open rows | closed |
| T-05-30 | Tampering | scaffolded unit files | medium | mitigate | `write_unit_source` opens with `"xb"` and raises UnitsError if the file exists | closed |
| T-05-31 | Tampering | names and paths in build.ninja | medium | mitigate | configure.py: `_UNIT_NAME.fullmatch` `[a-z0-9_]+`, `ninja_path()`, `_refuse_option_like()`, `_SAFE_ORIG.fullmatch` | closed |
| T-05-32 | Information disclosure | compile_commands.json, objdiff.json | low | mitigate | both (and build.ninja) gitignored per `git check-ignore`; none tracked | closed |
| T-05-33 | Repudiation | docs claiming beyond evidence | low | mitigate | hygiene tests pin the doc corrections (test_toolchain_records_spike_005, test_docs_place_ghidra_in_the_image, test_cflags_default_rule_is_documented) | closed |
| T-05-34 | Information disclosure | committed CSVs and reasons | high | mitigate | reasons hold addresses, row names and evidence words only (scan of both boundaries.csv); no listing tracked | closed |
| T-05-35 | Repudiation | hand verdicts | medium | mitigate | test_every_disagreement_has_a_verdict; test_functions_csv_has_no_drift and test_boundaries_csv_has_no_drift | closed |
| T-05-36 | Spoofing | check exit code | high | mitigate | `CheckResult.ok` needs every function ok, no problems and every splice ok; EXIT_TOOL = 2; test_reloc_failure_beats_objdiff | closed |
| T-05-37 | Tampering | objdiff-cli invocation | low | mitigate | `json.loads` parse; absent or non-finite/out-of-range `match_percent` is 0.0 (test_absent_percent_is_zero, test_absent_percent_or_nonsense_is_zero_not_a_match) | closed |
| T-05-38 | Tampering | sweep side effects | medium | mitigate | sweep work dir build/sweep/<exe>/<unit>; never lands; test_sweep_leaves_cflags_alone | closed |
| T-05-39 | Spoofing | the UFO2P match claim | high | mitigate | build/gate/05-evidence/02-check-ufo2p.json: objdiff_percent 100.0, no `"ok": false`, exit 0; 01-ninja.log `ninja verify` landed SHA-1 identical | closed |
| T-05-40 | Tampering | src/ unit files | high | mitigate | `git grep` for `_asm`/`__asm`/`#pragma aux`/`asm(` in src/ is empty; ninja `lint` rule runs over every unit | closed |
| T-05-41 | Tampering | config/cflags.txt default | medium | mitigate | the only rule is `*  wcc386@10.6  -4r -s -fpi`; no Phase 5 commit touches config/cflags.txt (last change 0965dbf, Phase 4) | closed |
| T-05-42 | Information disclosure | asm/ listings and Ghidra drafts | high | mitigate | asm/ and build/ gitignored; no tracked path under them at 25c5c49 | closed |
| T-05-43 | Spoofing | TACP match claim | high | mitigate | build/gate/05-evidence/03-check-tacp.json: objdiff_percent 100.0, no `"ok": false`, exit 0; `ninja verify` re-lands both units | closed |
| T-05-44 | Tampering | regression of the UFO2P match | high | mitigate | 01-ninja.log (clean graph) lands UFO2P.EXE and TACP.EXE SHA-1 identical; 04-rebuild.log `== manifest` x3 | closed |
| T-05-45 | Repudiation | validation sign-off | medium | mitigate | 05-VALIDATION.md rows cite logs 01..11, each ending `exit=0`; 09-rows.log runs every row command | closed |
| T-05-46 | Information disclosure | tracked files | high | mitigate | 08-hygiene.log: 345 tracked files, 0 forbidden matches; re-run at 25c5c49 also finds none | closed |
| T-05-SC (05-03) | Tampering | `uv add capstone==5.0.9` | high | mitigate | docs/tools.md records the reason; owner approved at the blocking-human checkpoint on 2026-10-23 before install (05-03-SUMMARY); exact pin in pyproject.toml, sha256 in uv.lock | closed |
| T-05-SC (05-12) | Tampering | apt packages (JDK, clang) | medium | mitigate | every apt package version-pinned on `ubuntu:24.04@sha256:68ee...`; no pip or npm install in the Dockerfile | closed |
| T-05-SC (other 18 plans) | Tampering | package installs | low | accept | AR-05-01 | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-05-01 | T-05-SC | Supply chain: the 18 plans other than 05-03 and 05-12 install no package. pyproject.toml and uv.lock change once in Phase 5 (b398159, capstone, covered by the 05-03 mitigation). | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-24 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-24 | 49 | 49 | 0 | orchestrator L1 grep short-circuit via /gsd-execute-phase 05 verify:post (ASVS L1, block_on high) |

The 49 register rows are T-05-01..46 and the three T-05-SC entries.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-24
