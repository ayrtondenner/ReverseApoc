---
phase: "06"
slug: "reporting-and-agent-pilot"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
block_on: high
audited_commit: 060a001
created: "2026-10-26"
---

# Phase 06 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register: the `<threat_model>` blocks of plans 06-01..06-27, authored at plan time: 94 STRIDE rows (T-06-01..67 plus T-06-SC, which appears in all 27 plans: mitigated in 06-01 (decompnet spike install, high) and 06-24 (workflow actions, medium), accepted at low in the other 25). 69 rows are `mitigate`, 25 are `accept`.
> Verified by gsd-security-auditor in two passes (ASVS 1, block_on high), verdict SECURED, audited commit 060a001. Evidence below cites files and test names; a line number appears only where it was checked against 060a001. Gate logs are in the gitignored build/gate/06-seed/ and build/gate/06-evidence/.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| GitHub tarball -> host scratch dir | decomp.wtf source enters the machine (06-01) | third-party source, read as data only |
| decompnet install -> WSL2 | third-party code runs only inside the owner's WSL2 distro (06-01) | nothing copied back into the repo |
| committed CSVs -> symbol table, tools and public numbers | hand-editable data feeds naming, the oracle and everything published (06-02, 06-18) | addresses, names, counts, percents |
| unit file text -> D-12 parser | agent- or human-written C decides what configure and check treat as marked or defined (06-03) | C source text |
| compiled object -> relocation check | our fixups and pairing rules decide which bytes count as checked (06-03, 06-10) | relocation verdict |
| real EXE -> measurement files and asm/ listings | game-derived analysis and text written locally (06-04, 06-06) | addresses; listings stay in gitignored asm/ |
| matched C edit -> codegen | a comment edit must not reach the compiler (06-05) | comment text |
| owner authorization -> manifest edit | a protected config file changes once, by explicit permission (06-07) | two note lines of config/watcom.toml |
| relocation verdict and build/<exe>/obj -> land | a pass verdict and on-disk objects become bytes in the rebuilt EXE (06-08, 06-09) | row start, length, SHA-1, provenance stamp |
| check verdict -> committed status table | the public progress record is derived from the oracle; callers choose the unit, never the verdict (06-11, 06-16) | status rows |
| agent tool call -> filesystem/shell | every Edit/Write/Bash request of a session crosses the hook (06-12) | paths, file text, commands |
| driver env -> hook and wrapper | the claim and notes path come from the driver, never from the agent (06-12, 06-15) | claim, notes path |
| game-derived listings/drafts -> context pack -> agent prompt | game strings and drafts reach the model as data (06-13) | context.md under build/driver/ |
| scorer output -> driver queue | which functions agents attempt (06-14) | starts |
| agent Bash -> attempt wrapper -> container | the only shell entry point an agent has; the wrapper decides what runs in Docker (06-15) | fixed argv forms |
| claude CLI output -> driver | the session's stream decides backoff, stop and accounting (06-17) | stream-json lines |
| repo and docs -> third-party lists and readers | public statements about the project (06-19, 06-20, 06-22) | listing drafts, .recomp.json, docs |
| planning records -> phase gate | the gate trusts the ledger's hashes and rulings (06-21) | commit hashes, rulings |
| agent session -> working tree -> git history | an unattended session edits files the driver may commit; public commits carry the match claim (06-23) | unit files, attempts.jsonl |
| CI -> GitHub Pages / artifacts / DecompHub | public outputs and one outward POST (06-24) | derived JSON and SVG |
| owner command -> unattended run on the real CLI | one command starts sessions that spend subscription usage; settings merge is only provable on the real CLI (06-25, 06-26) | sessions, outward actions |
| driver log and evidence logs -> phase verdict | the driver's own records are re-checked, not trusted (06-27) | gate logs ending `exit=STATUS` |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-06-01 | Tampering | decomp.wtf source on the host | high | mitigate | .planning/spikes/006-decompwtf-fork-stub/README.md:37 records the tarball sha256, README.md:41 states the source is read with `ast.parse` only (never imported) | closed |
| T-06-02 | Tampering | decompnet in WSL2 | medium | mitigate | spike 006 README.md:131: `uv tool install` of the pinned v0.10.6 tag tarball inside WSL2; no repo dependency changed (pyproject.toml/uv.lock last changed in b398159, Phase 5) | closed |
| T-06-03 | Information disclosure | smoke log and README | medium | mitigate | spike 006 README quotes tool messages, names and addresses only | closed |
| T-06-SC (06-01) | Tampering | package installs | high | mitigate | spike 006 README: pinned tag tarball with sha256, installed inside WSL2 only; no repo dependency change. Residual: how uv got into WSL2 is not recorded (outside the repo) | closed |
| T-06-04 | Tampering | file writes | medium | mitigate | tools/reverseapoc/fileio.py:17 `write_atomic` (temp + os.replace); tests/test_fileio.py `test_write_atomic_replaces_a_link`, `test_splice_alias_is_the_same_object` | closed |
| T-06-05 | Tampering | symbols.csv | low | mitigate | tests/test_symbols.py `test_address_of_refuses_a_placeholder_that_is_not_a_row_start`, `test_data_symbol_outside_every_data_range_is_refused`, `test_two_symbols_for_one_address_are_refused` | closed |
| T-06-SC (06-02) | Tampering | package installs | low | accept | AR-06-01 | closed |
| T-06-06 | Tampering | D-12 parser (configure/check) | high | mitigate | tests/test_configure.py `test_line_comment_continuation_hides_a_marker`, `test_define_continuation_hides_a_definition`, `test_directive_continuation_is_one_directive` | closed |
| T-06-07 | Spoofing | own-public resolution | medium | mitigate | tests/test_relocs.py `test_duplicate_own_publics_are_refused`, `test_wrong_target_inside_function_fails` | closed |
| T-06-08 | Tampering | build.ninja for another config | low | mitigate | tests/test_configure.py `test_config_dir_brings_its_own_manifest`, `test_custom_config_rules_name_its_manifest` | closed |
| T-06-SC (06-03) | Tampering | package installs | low | accept | AR-06-02 | closed |
| T-06-09 | Information disclosure | build/di19-11/*.json | low | mitigate | path under build/, gitignored (`git check-ignore`: .gitignore:5 `build/`); 06-04-SUMMARY | closed |
| T-06-10 | Tampering | committed boundary CSVs | medium | mitigate | 06-04-SUMMARY: the end rule moved 26 real ends, the owner approved, and both functions.csv were regenerated (end column only); boundaries.csv unchanged since Phase 5 (d9f3ff6) | closed |
| T-06-SC (06-04) | Tampering | package installs | low | accept | AR-06-03 | closed |
| T-06-11 | Tampering | src/tacp/u_00054f20.c | medium | mitigate | 43daac3 adds 5 lines to the unit; 06-05-SUMMARY records the comment-blanked comparison with the parent commit; re-proved by the container gate (build/gate/06-seed/, 06-16) and by every re-gate of 06-27 (build/gate/06-evidence/11-regate-1..3.log, `exit=0`) | closed |
| T-06-SC (06-05) | Tampering | package installs | low | accept | AR-06-04 | closed |
| T-06-12 | Spoofing | asm/<exe>/<name>.s | medium | mitigate | tests/test_asm.py `test_ambiguous_name_gets_one_listing_per_row`, `test_write_listings_refuses_a_case_only_clash`, `test_committed_listing_names_are_unique` | closed |
| T-06-SC (06-06) | Tampering | package installs | low | accept | AR-06-05 | closed |
| T-06-13 | Tampering | config/watcom.toml | high | mitigate | one commit, 28342e1: numstat 2/2 on config/watcom.toml only, note lines (D-43) | closed |
| T-06-14 | Information disclosure | real-test failure output | low | mitigate | tests/test_compiler_real.py module docstring: assertions compare SHA-1s, public names and literal encodings, never bytes taken from a file | closed |
| T-06-15 | Denial of service | cc edges with a bad --log | low | mitigate | tests/test_compiler.py `test_log_naming_a_directory_is_refused_before_the_compile`; tests/test_cli.py `test_cc_log_without_a_name_is_an_error_line` | closed |
| T-06-SC (06-07) | Tampering | package installs | low | accept | AR-06-06 | closed |
| T-06-16 | Spoofing | LandedFunction | medium | mitigate | tools/reverseapoc/land.py:56 `LandedFunction`; tests/test_land.py `test_land_refuses_a_verdict_for_another_row`, `test_land_refuses_a_verdict_for_other_bytes` | closed |
| T-06-SC (06-08) | Tampering | package installs | low | accept | AR-06-07 | closed |
| T-06-17 | Tampering | ninja's objects | high | mitigate | tests/test_check.py `test_land_refuses_an_object_without_a_stamp`, `test_land_refuses_an_object_with_a_stale_source`, `test_land_refuses_an_object_with_stale_cflags`, `test_land_refuses_an_object_overwritten_after_its_stamp` | closed |
| T-06-18 | Spoofing | marked rows with data publics | medium | mitigate | tests/test_check.py `test_marked_row_with_a_data_public_is_refused`, `test_land_refuses_a_marked_row_with_a_data_public` | closed |
| T-06-SC (06-09) | Tampering | package installs | low | accept | AR-06-08 | closed |
| T-06-19 | Spoofing | own_publics table pairing | high | mitigate | tests/test_check.py `test_leading_table_pairs_with_its_data_row`, `test_leading_table_with_a_wrong_entry_fails`, `test_mid_unit_table_still_fails_closed`, `test_leading_table_used_by_another_function_is_refused`; real proof tests/test_check_tables_real.py | closed |
| T-06-20 | Tampering | omf2elf symbol resolution | medium | mitigate | tests/test_omf2elf.py `test_self_extdef_resolves_to_the_local_public` | closed |
| T-06-SC (06-10) | Tampering | package installs | low | accept | AR-06-09 | closed |
| T-06-21 | Tampering | config/<exe>/status.csv | high | mitigate | tests/test_status.py `test_only_gate_writes_the_table`, `test_status_refuses_bad_tables`; tests/test_drift.py `test_matched_rows_equal_defined_functions`; tests/test_driver.py `test_session_editing_status_stops_the_night` | closed |
| T-06-22 | Repudiation | regressions in other units | high | mitigate | tests/test_gate.py `test_crosscheck_refuses_a_reverted_match`, `test_crosscheck_refuses_an_extra_landed_function`, `test_gate_all_refuses_a_regression` | closed |
| T-06-23 | Tampering | partial rows | low | mitigate | tests/test_gate.py `test_partial_never_downgrades_a_matched_row`, `test_a_match_replaces_a_partial_row` | closed |
| T-06-SC (06-11) | Tampering | package installs | low | accept | AR-06-10 | closed |
| T-06-24 | Tampering | orig/, manifests, status, tools during matching | high | mitigate | tools/reverseapoc/hooks.py:504 `_always`, hooks.py:576 `matching_write_allowed`; tests/test_hooks.py `test_always_denies_a_write_under_orig`, `test_always_denies_protected_files`, `test_the_always_handlers_are_byte_identical`, `test_matching_write_allowed_is_the_one_allowlist` | closed |
| T-06-25 | Elevation of privilege | matching-session Bash | high | mitigate | hooks.py:105 `ATTEMPT_FORMS`, hooks.py:565 `bash_allowed`; tests/test_hooks.py `test_matching_bash_allows_exact_wrapper_forms`, `test_matching_bash_denies_everything_else`, `test_attempt_forms_are_the_shared_constants` | closed |
| T-06-26 | Information disclosure | reads of credentials/.env | high | mitigate | hooks.py:100 `_SECRET_PREFIX = ".env"`, hooks.py:649 the .env read denial; tests/test_hooks.py `test_matching_reads_stay_in_the_repo`, `test_matching_reads_deny_every_path_form_outside_the_repo` | closed |
| T-06-27 | Denial of service / fail-open | hook crash or timeout | high | mitigate | hooks.py:813 catch-all `except BaseException` (fail closed); `"timeout": 120, "onFailure": "block"` on the always handler at .claude/settings.json:28-29 and config/driver/claude-settings.json:25-26, and on the matching handler at config/driver/claude-settings.json:36-37 (WR-02, 036d478); tests/test_hooks.py `test_project_settings_wire_the_always_layer`, `test_settings_commands_fail_closed_through_the_hook_shell`, `test_unmappable_device_path_exits_2` | closed |
| T-06-28 | Tampering | inline asm / pragmas in src/ | medium | mitigate | hooks.py:441 `_inline_asm`, hooks.py:453 `asm_problem`, hooks.py:472 `include_problem` (CR-02, c7b88c3); configure.py:451 `include_problems` (check and gate refuse before compiling, 9232499); tests/test_hooks.py `test_matching_denies_every_pragma_aux`, `test_matching_denies_a_path_include`, `test_an_edit_that_introduces_a_path_include_is_denied`; tests/test_configure.py `test_unit_source_refuses_a_path_include`; tests/test_check.py `test_a_path_include_is_refused_before_compiling` | closed |
| T-06-SC (06-12) | Tampering | package installs | low | accept | AR-06-11 | closed |
| T-06-29 | Information disclosure | context.md | high | mitigate | tools/reverseapoc/contextpack.py:725 `write_pack`; tests/test_contextpack.py `test_write_pack_refuses_paths_outside_the_repo_build_driver`, `test_write_pack_refuses_a_symlink_out_of_build_driver` | closed |
| T-06-30 | Tampering | prompt injection via strings or drafts | medium | mitigate | session `--tools` and `--strict-mcp-config` (tools/reverseapoc/session.py:71, :75); hooks.py:576 `matching_write_allowed`; tests/test_hooks.py `test_matching_denies_other_tools`, `test_matching_bash_denies_everything_else`; verdict from the container gate only (T-06-53) | closed |
| T-06-31 | Denial of service | oversized pack | low | mitigate | contextpack.py:35 `PACK_CAP = 24576`; tests/test_contextpack.py `test_pack_cap_is_24_kib`, `test_required_sections_alone_over_the_cap` | closed |
| T-06-SC (06-13) | Tampering | package installs | low | accept | AR-06-12 | closed |
| T-06-32 | Denial of service | queue | low | mitigate | tools/reverseapoc/driver.py:1893 `excluded_keys`; tools/reverseapoc/picker.py:44 `END_EXHAUSTED`; tests/test_driver_pick.py `test_queue_skips_excluded_and_difficult`, `test_variety_exhaustion_ends_the_queue`; WR-03 (82cba76): tests/test_gate.py `test_a_kept_better_partial_row_is_skipped_by_the_picker_today` | closed |
| T-06-SC (06-14) | Tampering | package installs | low | accept | AR-06-13 | closed |
| T-06-33 | Elevation of privilege | attempt check | high | mitigate | tools/reverseapoc/attempt.py:128 `form_allowed`, attempt.py:222 `container_check_argv` (argv tuple, no shell); tests/test_attempt_wrapper.py `test_attempt_refuses_an_unknown_subcommand`, `test_attempt_refuses_a_bad_environment`, `test_attempt_forms_match_the_hook` | closed |
| T-06-34 | Tampering | check flags | high | mitigate | attempt.py:222 `container_check_argv` passes only the claim, `--json` and `--sweep <function>`; tests/test_attempt_wrapper.py `test_attempt_sweep_exit_is_never_a_match`, `test_attempt_check_sweep_logs_a_hit` | closed |
| T-06-35 | Denial of service | check loops | medium | mitigate | attempt.py:48 `CHECK_BUDGET = 25`; tests/test_attempt_wrapper.py `test_attempt_check_budget`; WR-04 (6937c8f): hooks.py:114 `CHECK_TIMEOUT_MS = 600_000`, tests/test_hooks.py `test_matching_denies_a_check_without_the_long_bash_timeout`, tests/test_drive.py `test_canary_prompt_asks_for_the_check_timeout_the_hook_requires` | closed |
| T-06-36 | Information disclosure | listings and packs | medium | mitigate | packs written only under build/driver/ (contextpack.py:725 `write_pack`; tests/test_contextpack.py `test_write_pack_stays_under_build_driver`); listings under gitignored asm/ | closed |
| T-06-SC (06-15) | Tampering | package installs | low | accept | AR-06-14 | closed |
| T-06-37 | Tampering | status.csv seeding | high | mitigate | build/gate/06-seed/01-gate-seed.exit = 0 (container gate); tests/test_drift.py `test_matched_rows_equal_defined_functions`, `test_drift_catches_planted_changes` | closed |
| T-06-38 | Information disclosure | evidence logs | low | mitigate | logs under gitignored build/gate/06-seed/; tests assert on names, addresses and SHA-1s | closed |
| T-06-SC (06-16) | Tampering | package installs | low | accept | AR-06-15 | closed |
| T-06-39 | Spoofing | result/goal verdict | high | mitigate | tools/reverseapoc/streamjson.py:90 (dispositions carry no outcome); tests/test_streamjson.py `test_dispositions_carry_no_outcome` | closed |
| T-06-40 | Elevation of privilege | polluted sessions (plugins, MCP, extra tools, bare mode) | high | mitigate | session.py:71 `--tools`, :75 `--strict-mcp-config`, :76 `--setting-sources`; streamjson.py:332 `check_init`; built-in plugins switched off in driver settings (b221245); tests/test_session.py `test_build_argv_is_d06`; tests/test_streamjson.py `test_check_init_problems`; tests/test_hooks.py `test_driver_settings_switch_off_the_cli_builtin_plugins` | closed |
| T-06-41 | Denial of service | runaway sessions | medium | mitigate | session.py:36 `MAX_TURNS = 40`, :37 `MAX_BUDGET_USD = 5`, :39 `TIMEOUT_S = 30 * 60`; tests/test_session.py `test_timeout_kills_the_tree` | closed |
| T-06-42 | Tampering | malformed stream lines | low | mitigate | tests/test_streamjson.py `test_malformed_lines_are_counted`, `test_parse_line_refuses_anything_but_an_object`, `test_parse_line_counts_deep_nesting_as_malformed` | closed |
| T-06-SC (06-17) | Tampering | package installs | low | accept | AR-06-16 | closed |
| T-06-43 | Repudiation | published figures | medium | mitigate | tools/progress.py:377 `derive`; tests/test_drift.py `test_committed_feed_is_derived`, `test_feed_drift_is_caught`; tests/test_report_shape.py `test_report_percent_equals_progress` | closed |
| T-06-44 | Information disclosure | outputs | low | mitigate | tests/test_progress.py `test_decomphub_feed_follows_progress_v1`; tests/test_report_shape.py `test_report_field_names_are_proto_names` | closed |
| T-06-45 | Tampering | partial writes | low | mitigate | tools/progress.py:395 `_write_atomic`; tests/test_progress.py `test_outputs_are_byte_stable_and_atomic` | closed |
| T-06-SC (06-18) | Tampering | package installs | low | accept | AR-06-17 | closed |
| T-06-46 | Repudiation | listing claims | medium | mitigate | docs/listings.md:11 states the project is AI-assisted and every match is proven by byte comparison | closed |
| T-06-47 | Spoofing/abuse | automated submissions | high | mitigate | 06-19-SUMMARY: drafts only, upstream read with read-only `gh api`, decomp.me never accessed, the owner sends each one. The 06-24 incident (one empty POST by a reviewer agent, HTTP 400, no data) was an agent process lapse, mitigated by the no-network rule in every dispatch | closed |
| T-06-SC (06-19) | Tampering | package installs | low | accept | AR-06-18 | closed |
| T-06-48 | Information disclosure | Docker build context | medium | mitigate | .dockerignore:21, :23-25 (`**/*.IMG`, `**/*.CUE`, `**/*.mdf`, `**/*.MDF`); tests/test_hygiene.py `test_dockerignore_excludes_executables_and_disc_images_at_any_depth` | closed |
| T-06-49 | Repudiation | stale claims | low | mitigate | 06-20-SUMMARY: three negative greps plus hygiene (71 passed, 3 skipped); docs/legal.md names progress/attempts.jsonl as the AI-use record | closed |
| T-06-SC (06-20) | Tampering | package installs | low | accept | AR-06-19 | closed |
| T-06-50 | Repudiation | deferred-item closure | medium | mitigate | .planning/phases/06-reporting-and-agent-pilot/06-DEFERRED-LEDGER.md: 61 DI rows, 55 `closed` with commit hashes, 6 `ruled` with a named decision; no `planned` or `pending` row (re-checked by 06-27) | closed |
| T-06-SC (06-21) | Tampering | package installs | low | accept | AR-06-20 | closed |
| T-06-51 | Repudiation | listing claims | medium | mitigate | .recomp.json:51 `ai-assisted`; tests/test_listings.py `test_recomp_json_notes_match_the_pipeline`, `test_note_check_follows_the_spike_verdict` | closed |
| T-06-52 | Tampering | .recomp.json shape | low | mitigate | tests/test_listings.py `test_recomp_json_keys_and_enum`, `test_recomp_json_links_are_https` | closed |
| T-06-SC (06-22) | Tampering | package installs | low | accept | AR-06-21 | closed |
| T-06-53 | Spoofing | match claim | high | mitigate | CR-01 (02f513e): driver.py:472 `claimed_matched`, used at driver.py:1588; tests/test_driver.py `test_gate_pass_without_the_claimed_row_is_no_match`, `test_limit_salvage_without_the_claimed_row_is_no_match`, `test_hundred_percent_with_failing_gate_is_partial`, `test_a_refused_pre_gate_restore_is_named` (bab4a2b) | closed |
| T-06-54 | Tampering | stray edits | high | mitigate | driver.py:1298 `_audit`; tests/test_driver.py `test_stray_write_resets_and_stops`, `test_a_guardrail_stop_restores_tracked_strays_and_quarantines_new_ones` | closed |
| T-06-55 | Information disclosure | commits and the log | high | mitigate | tests/test_driver.py `test_a_plain_new_header_is_committed_with_literal_pathspecs`; tests/test_attempts_schema.py `test_schema_refuses_bad_records`, `test_committed_log_follows_the_schema` | closed |
| T-06-56 | Denial of service | spend | medium | mitigate | driver.py:160 `attempts_per_function: int = 3`; tests/test_driver.py `test_three_attempts_then_difficult`, `test_max_sessions_and_target_matched`, `test_limit_backs_off_and_is_not_counted`, `test_stop_classes_end_the_run` | closed |
| T-06-SC (06-23) | Tampering | package installs | low | accept | AR-06-22 | closed |
| T-06-57 | Elevation of privilege | workflow token | medium | mitigate | .github/workflows/ci.yml:7 and pages.yml:28 `permissions:`; `persist-credentials: false` at ci.yml:16 (WR-01, c574493) and pages.yml:41; tests/test_workflows.py `test_pages_permissions_and_concurrency`, `test_every_checkout_drops_its_credentials` | closed |
| T-06-58 | Information disclosure | site and artifact | medium | mitigate | pages.yml:8-9 (only derived counts and names leave CI; no game file in a checkout); tests/test_workflows.py `test_pages_build_steps`, `test_pages_needs_no_secret` | closed |
| T-06-59 | Spoofing/abuse | DecompHub POST | low | mitigate | pages.yml:79 (repo check, push only, owner's `vars.DECOMPHUB_REFRESH`), :81 `permissions: {}`, :97 `curl --fail ... --max-time 20`; tests/test_workflows.py `test_decomphub_notify_is_gated`, `test_decomphub_notify_never_posts_an_empty_body`, `test_no_other_outward_url` | closed |
| T-06-SC (06-24) | Tampering | package installs / actions | medium | mitigate | no package installed; actions at verified release tags (research audit): `actions/*` and `astral-sh/setup-uv@v10.3.0` (ci.yml:14, :27; pages.yml:39, :48, :56, :71). Residual: tags, not SHAs (IN-04, deferred) | closed |
| T-06-60 | Elevation of privilege | untested CLI (bare default, settings merge) | high | mitigate | driver.py:105 `MIN_CLI_VERSION = (2, 1, 302)`; tests/test_drive.py `test_preflight_passes_a_clean_main_checkout_on_2_1_302`, `test_canary_fails_on_an_init_problem`; owner's canary2 PASS before the pilot (06-26-SUMMARY) | closed |
| T-06-61 | Tampering | run on a dirty tree or worktree | high | mitigate | tests/test_drive.py `test_preflight_refuses_a_worktree`, `test_preflight_refuses_a_dirty_tree_naming_the_paths` | closed |
| T-06-62 | Repudiation | regressions across the night | high | mitigate | tests/test_driver.py `test_end_of_run_checks_land_in_the_ended_record_before_the_chore_commit`; pilot run 20261026-005209 ended with ninja verify and gate --all ok (06-26-SUMMARY) | closed |
| T-06-SC (06-25) | Tampering | package installs | low | accept | AR-06-23 | closed |
| T-06-63 | Elevation of privilege | real sessions | high | mitigate | 06-26-SUMMARY: the owner ran canary1 (FAIL), canary2 (PASS at b221245) and the pilot himself; the executor ran dry-run and preflight only | closed |
| T-06-64 | Spoofing/abuse | third-party submissions | medium | mitigate | 06-27-SUMMARY (owner ruling F40): the owner submitted the DecompHub form himself on 2026-10-24; the listing drafts are sent by the owner (D-31, D-33) | closed |
| T-06-SC (06-26) | Tampering | package installs | low | accept | AR-06-24 | closed |
| T-06-65 | Spoofing | pilot match claims | high | mitigate | build/gate/06-evidence/10-commits.txt (c83cf4e, d288ad6, 955931f), 11-regate-1..3.log, 12-final-ninja.log, 13-final-gate.log, all ending `exit=0` | closed |
| T-06-66 | Repudiation | validation sign-off | medium | mitigate | 06-VALIDATION.md `status: validated`, rows cite build/gate/06-evidence/ logs; 14-drift.log `exit=0` | closed |
| T-06-67 | Information disclosure | tracked files | high | mitigate | build/gate/06-evidence/32-hygiene.log `exit=0` (504 tracked files, no offender per 06-27-SUMMARY) | closed |
| T-06-SC (06-27) | Tampering | package installs | low | accept | AR-06-25 | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-06-01 | T-06-SC (06-02) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-02 | T-06-SC (06-03) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-03 | T-06-SC (06-04) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-04 | T-06-SC (06-05) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-05 | T-06-SC (06-06) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-06 | T-06-SC (06-07) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-07 | T-06-SC (06-08) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-08 | T-06-SC (06-09) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-09 | T-06-SC (06-10) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-10 | T-06-SC (06-11) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-11 | T-06-SC (06-12) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-12 | T-06-SC (06-13) | No package is installed (difflib is stdlib). | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-13 | T-06-SC (06-14) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-14 | T-06-SC (06-15) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-15 | T-06-SC (06-16) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-16 | T-06-SC (06-17) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-17 | T-06-SC (06-18) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-18 | T-06-SC (06-19) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-19 | T-06-SC (06-20) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-20 | T-06-SC (06-21) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-21 | T-06-SC (06-22) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-22 | T-06-SC (06-23) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-23 | T-06-SC (06-25) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-24 | T-06-SC (06-26) | No package is installed by the executor; the CLI upgrade is the owner's. See the 06-26 note below. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |
| AR-06-25 | T-06-SC (06-27) | No package is installed. | plan threat models (owner-approved plans), recorded by the orchestrator | 2026-10-26 |

The rationale holds at 060a001: pyproject.toml and uv.lock are unchanged since b398159 (05-03, capstone), and the one Phase 6 Dockerfile change, d8be60c, edits comments only.

Note for 06-26: CLI 2.1.308 enables built-in plugins by default, which failed canary1. b221245 switches them off in the driver settings, and the canary check stays strict. The frontend-design plugin is off in driver sessions as well (fe7149c).

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-26 | 94 | 94 | 0 | gsd-security-auditor, pass 1 (started at cc53914, ended at c7b88c3; ASVS L1, block_on high). The code review found CR-01 (T-06-53, high) and CR-02 (T-06-28, medium) open during this pass; 02f513e and c7b88c3 closed them and the auditor confirmed both |
| 2026-10-26 | 94 | 94 | 0 | gsd-security-auditor, pass 2: delta c7b88c3..060a001, code and diff reading. 0 open, 0 open at or above high, no mitigation regressed |

Residuals closed in the pass 2 range: WR-02 on T-06-27 (the always handler gets timeout 120 and `onFailure: block` in both settings files), WR-03 on T-06-32 (a kept better partial row takes today's date), WR-04 on T-06-35 (the matching hook denies an attempt check without a Bash timeout of at least 600000; the canary prompt takes it from the constant), and the unregistered ci.yml credentials flag (WR-01).

The DecompHub notify guards were verified: the pages.yml repo check, `permissions: {}`, shell bash, `set -euo pipefail`, refusal of an empty body, `curl --fail --max-time 20`, and tests that pin them.

### Residuals that remain (non-blocking, owner)

- IN-04: workflow actions are pinned by tag, not by commit SHA (deferred).
- T-06-SC (06-01): how uv got into WSL2 is not recorded (outside the repo).
- A fresh owner canary is required before the next real night. The guardrails changed after canary2: fe7149c, CR-01, CR-02, WR-02 and WR-04.
- `onFailure` needs CLI 2.1.295 or later, and the owner's interactive sessions are not version-checked (low).
- A stale check.lock can still follow a wall-clock tree kill (fails closed).
- docs/legal.md:44 wording (the attempt log tense; corrected with this record).

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-26
