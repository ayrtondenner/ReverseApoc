# Progress reporting, progress mosaics, and recomp.fyi registration (for ReverseApoc)

Research date: 2026-10-19. Intended path was `...\scratchpad\research_notes\ReverseApoc kickoff research\progress_reporting_and_recompfyi.md`. Plan mode blocked writes outside this plan file, so the notes are here. Copy them to that path once plan mode ends. No repo was cloned and nothing was installed or run; every source was read through WebFetch, WebSearch, or read-only GitHub API/raw fetches.

## 1. AnyPS5 tools/progress.py and CI: what it consumes, outputs, and whether it can be reused

### Takeaway
AnyPS5's `progress.py` is not a decomp tool. It scans the project's own C++ sources for stubbed functions and counts shader opcodes, so it cannot be reused as-is for a Watcom/x86 matching decomp. Only its output half is reusable: the squarified-treemap SVG renderer, the `progress.json`, and the Pages deploy pattern. For ReverseApoc the input stage would be rewritten and the renderer kept.

### Cited Findings
- Inputs are every `.cpp` under `core/libs/prx/<library>/`, skipping `tests`. Each `APS5_VABI` function body is checked for calls to the stub `NotImplemented_nid_no_patch`. It also reads the `RdnaOpcode` enum in `RdnaOpcode.hpp`, `tools/rdna_isa.txt`, and the sibling module `nid_names.py` for the comment/string tokenizer. [AnyPS5 progress.py](https://github.com/boykopovar/AnyPS5/blob/main/tools/progress.py), summarized through WebFetch of [raw](https://raw.githubusercontent.com/boykopovar/AnyPS5/main/tools/progress.py). The summarizer could not reproduce the source verbatim.
- Outputs are `progress.json`, `badge-libraries.svg`, `badge-shaders.svg`, `progress.svg` (two-panel treemap), and `progress.html`. It also prints a Markdown diff in `--compare BASE HEAD` mode. [progress.py](https://raw.githubusercontent.com/boykopovar/AnyPS5/main/tools/progress.py)
- The mosaic algorithm is a squarified treemap. Groups are sorted largest first, and each group's rectangle area is proportional to its item count. Inside a group, cells form a near-square grid with `round(sqrt(count*h/w))` rows. The first `done` cells are green (`#2ea043`) and the rest gray (`#6e7681`). Each group gets a tooltip, and a label is drawn only if it fits. [progress.py](https://raw.githubusercontent.com/boykopovar/AnyPS5/main/tools/progress.py)
- Dependencies are the Python 3.9+ standard library only. [progress.py](https://raw.githubusercontent.com/boykopovar/AnyPS5/main/tools/progress.py)
- Wiring: `.github/workflows/pages-progress.yml` runs on push to `main` when only the relevant source paths change. It has one concurrency group, `pages-progress`, with cancel-in-progress. It runs `tools/progress.py` to write `progress.json` to a temp dir. It then fetches the live deployed `progress.json`, compares it, and dispatches `pages.yml` only if the content changed. [pages-progress.yml](https://raw.githubusercontent.com/boykopovar/AnyPS5/main/.github/workflows/pages-progress.yml)
- `pages.yml` runs on push to `main`, `workflow_dispatch`, release, and workflow_run. It uses permissions `contents: read`, `pages: write`, `id-token: write` and environment `github-pages`. It runs `progress.py`/`progress_history.py`, then `actions/upload-pages-artifact@v5` and `actions/deploy-pages@v5`. [pages.yml](https://raw.githubusercontent.com/boykopovar/AnyPS5/main/.github/workflows/pages.yml)
- The README embeds `https://boykopovar.github.io/AnyPS5/progress.svg` (through GitHub's camo proxy), linking to `progress.html`. [AnyPS5 README](https://github.com/boykopovar/AnyPS5)
- AnyPS5 also has `progress-report.yml` and `progress-comment.yml`, presumably for PR comments. Their contents were not read. [workflow list](https://api.github.com/repos/boykopovar/AnyPS5/contents/.github/workflows)
- Compare mode (`--compare`) lets CI post per-PR progress deltas. [progress.py](https://raw.githubusercontent.com/boykopovar/AnyPS5/main/tools/progress.py)

### Inferences
- The renderer is license-compatible to study (the repo is GPL-2.0, per its [README](https://github.com/boykopovar/AnyPS5)), but copying code would carry GPL-2.0 terms. A ReverseApoc treemap script written from scratch (stdlib Python, about 100 lines) avoids that.
- For ReverseApoc the natural grouping is source file/module, with one cell per function. This would be colored by status: green for matched, gray for not started, and an optional amber for partial.
- The "dispatch Pages only if progress.json changed" trick avoids a redeploy on every push. It is worth copying.

### Gaps
- I did not read the full text of `progress.py`, so exact color thresholds and SVG sizing are unverified.
- I did not read `progress-report.yml` or `progress-comment.yml`.

## 2. bw1-decomp, decomp.dev, and its sunset status

### Takeaway
bw1-decomp is an x86/MSVC 6 decomp that produced an objdiff `report.json` in CI and uploaded it as a `<version>_report` artifact, which decomp.dev ingested. It rendered the README mosaic and badges as decomp.dev-hosted images. decomp.dev is partly shut down: existing project pages and historical data stay up, but the index and new-project registration are disabled, with no recommended replacement. Any README image that hot-links `decomp.dev/<org>/<repo>.svg` for a new project is not an option.

### Cited Findings
- The bw1-decomp README uses `https://decomp.dev/openblack/bw1-decomp.svg?mode=shield&measure=code&label=Code`, the same with `measure=data`, and a mosaic image `https://decomp.dev/openblack/bw1-decomp.svg?w=512&h=256`. It describes decomp.dev as a "Decompilation progress hub and API". [README raw](https://raw.githubusercontent.com/openblack/bw1-decomp/main/README.md)
- bw1-decomp targets Windows x86 with MSVC 6.0 and CodeWarrior Mac. It uses decomp-toolkit (an openblack fork), Python `configure.py`, and Ninja, and generates an `objdiff.json` in the project root. [bw1-decomp](https://github.com/openblack/bw1-decomp)
- Its CI runs `ninja all_source progress build/<version>/report.json` and uploads `build/<version>/report.json` as artifact `<version>_report` with `actions/upload-artifact@v4`. [build.yml](https://raw.githubusercontent.com/openblack/bw1-decomp/main/.github/workflows/build.yml)
- It does not use `decomp.yaml`, per the repo file listing (it has `configure.py`, `config/`, `docs/`, `reports/`, and `tools/`). [file list](https://api.github.com/repos/openblack/bw1-decomp/contents/). Its `reports/` folder holds only two markdown reports, not progress data.
- The decomp.dev page "Sunsetting decomp.dev" is authored by @encounter and carries no explicit date. It says the public index and leaderboard "cause more harm than good". Existing project pages and historical data remain. The main index and the ability to add new projects are disabled. The code has never had an open-source license, the author reserves all rights, and replicas may not use it. It recommends no replacement and links only to decomp.wiki. [decomp.dev](https://decomp.dev)
- Press dates the closure: 404 Media first reported it on 2026-10-15, according to [AI Weekly](https://aiweekly.co/alerts/decompdev-shuts-down-as-ai-breaks-reverse-engineering-scene). Time Extension covers it in October 2026, but that page returned HTTP 403, so only the headline was seen. [Time Extension](https://www.timeextension.com/news/2026/10/the-community-aspect-of-decompilation-has-been-broken-decomp-dev-closes-in-the-wake-of-ai-based-bad-actors). Search snippets say decomp.me and ghidra.decomp.dev remain operational. This is a snippet-level claim from a secondary source ([search result](https://aiweekly.co/alerts/decompdev-shuts-down-as-ai-breaks-reverse-engineering-scene)).
- The stated reasons are AI-assisted "hostile forks" and the author's view that an index now harms the community. [decomp.dev](https://decomp.dev)

### Inferences
- "Sunsetting" in the owner's phrasing is accurate but partial. The site is not gone, but new registration is closed. ReverseApoc cannot onboard.
- The artifact name `<version>_report` is the same convention recomp.fyi reads (section 4). If ReverseApoc ever produces an objdiff-format report, a bw1-style workflow would work as-is.

### Gaps
- No exact shutdown date for the remaining project pages. The announcement gives none.
- Time Extension and 404 Media originals were not readable.

## 3. objdiff, report format, and x86 / Watcom OMF support

### Takeaway
`objdiff-cli report generate` produces an objdiff JSON/protobuf report that feeds badges and mosaics, and objdiff supports x86 and x86_64. However, objdiff on `main` reads only ELF and COFF. Watcom produces OMF `.obj` files, and OMF support is an open issue plus a stale work-in-progress branch. A direct objdiff pipeline is therefore not available for ReverseApoc today.

### Cited Findings
- Latest release is v3.8.2, published 2026-09-29. The repo was last pushed 2026-10-19 and is not archived. The release assets include `objdiff-cli-windows-x86_64.exe` and the Linux builds. [GitHub API](https://api.github.com/repos/encounter/objdiff/releases/latest)
- The README lists supported architectures as ARM, ARM64, MIPS, PowerPC, SuperH, and "x86, x86_64 (PC)". It is dual-licensed Apache-2.0/MIT. [objdiff README](https://github.com/encounter/objdiff)
- `report generate` takes `-p <project dir>`, `-o <output>`, `-d` (deduplicate global/weak symbols), `-f json|json-pretty|proto`, and `-c key=value`. `report changes <previous> <current>` diffs two reports. [report.rs](https://raw.githubusercontent.com/encounter/objdiff/main/objdiff-cli/src/cmd/report.rs)
- It requires a project config (`objdiff.json`) containing units with `target_path` and `base_path` objects. [report.rs](https://raw.githubusercontent.com/encounter/objdiff/main/objdiff-cli/src/cmd/report.rs); [README](https://github.com/encounter/objdiff)
- The report proto has `Report { measures, units[], version, categories[] }`. `Measures` includes `fuzzy_match_percent`, `total_code`, `matched_code`, `matched_code_percent`, `total_data`, `matched_data`, `total_functions`, `matched_functions`, `matched_functions_percent`, `complete_code`, `total_units`, and `complete_units`. `ReportUnit` has `name`, `measures`, `sections[]`, `functions[]` (each with `name`, `size`, `fuzzy_match_percent`, optional `virtual_address`), and metadata including `source_path`. [report.proto](https://raw.githubusercontent.com/encounter/objdiff/main/objdiff-core/protos/report.proto)
- On `main`, `obj/read.rs` handles only `BinaryFormat::Elf` and `BinaryFormat::Coff` (no "omf" reference). [read.rs](https://raw.githubusercontent.com/encounter/objdiff/main/objdiff-core/src/obj/read.rs)
- Issue #97 "Support OMF object format" has been open since 2024-08-19, with the last update on 2024-10-11. It notes that OMF would open objdiff to Borland, old MSVC, and Watcom targets. Upstream `gimli-rs/object` was asked for OMF support (object issue #736). [issue 97](https://github.com/encounter/objdiff/issues/97)
- The branch `omf` contains a commit "[WIP] OMF object support" dated 2025-09-25. It is 1 commit ahead of and 104 behind `main`, so it is stale. [branches](https://api.github.com/repos/encounter/objdiff/branches); [compare](https://api.github.com/repos/encounter/objdiff/compare/main...omf)
- None of the last 30 objdiff releases (v3.0.0-beta.9 through v3.8.2) mention OMF or Watcom in their notes. [releases API](https://api.github.com/repos/encounter/objdiff/releases)

### Inferences
- Because the report is a plain per-function list with `fuzzy_match_percent`, ReverseApoc can emit the same JSON shape from its own comparison tool (for example, comparing compiled function bytes against the original EXE bytes). That keeps compatibility with recomp.fyi's "report.json" ingestion and any future objdiff-based tooling. Whether recomp.fyi's reader accepts a hand-built report is unverified.
- Alternatives that avoid OMF: convert the Watcom OMF to COFF (for example, via a custom tool or `objconv`, which the issue thread mentions) or compare the final linked LE image instead of per-unit objects. Both are speculative.

### Gaps
- I did not verify whether any other tool (for example, decomp.me or a fork) exposes a Watcom-aware matcher.
- I did not verify whether the objdiff `omf` branch is usable.

## 4. decomp_settings (decomp.yaml)

### Takeaway
`decomp.yaml` is a small shared-settings standard by Ethteck for decomp tooling (decomp.me presets, permuter, frogress). It is optional, mostly N64/MIPS-era in practice, and neither recomp.fyi nor the mosaic approaches need it.

### Cited Findings
- Purpose: centralize common metadata such as the map and target file locations, so tools such as m2c, decomp-permuter, frogress, spimdisasm, mapfile_parser, splat, and coddog can share settings. It ships as a Rust library with Python bindings (PyPI and crates.io). The README's spec section says "More shoon". [README](https://github.com/ethteck/decomp_settings)
- The spec is the example `test/decomp.yaml`. Top-level fields: `name`, `repo`, `platform`, `versions[]`, `tools`. Each version has `name`, `fullname`, `sha1`, and `paths` (`target`, `build_dir`, `map`, `compiled_target`, `elf`, `expected_dir`, `asm`, `nonmatchings`). `tools` has `decompme: {preset}`, `permuter: {decompme_compilers}`, and `frogress: {project, versions}`. [test/decomp.yaml](https://raw.githubusercontent.com/ethteck/decomp_settings/main/test/decomp.yaml)
- Maintenance: created 2024-08-01, last pushed 2026-01-16, not archived. [GitHub API](https://api.github.com/repos/ethteck/decomp_settings)
- The README names frogress, permuter, and others as intended consumers. It does not say that objdiff, decomp.dev, or recomp.fyi read the file. [README](https://github.com/ethteck/decomp_settings)

### Inferences
- bw1-decomp and the recomp.fyi route do not need `decomp.yaml`. Skip it unless using decomp.me or frogress.

### Gaps
- `platform` values and the full field schema are unconfirmed beyond the one example (no x86/DOS example seen). I did not verify whether decomp.dev read `decomp.yaml` (an older claim in the task prompt).

## 5. recomp.fyi: what it is, the .recomp.json schema, and how progress is pulled

### Takeaway
recomp.fyi hosts "recomp.board", a table of recompilation, source-port, and decompilation projects, run by GitHub user neurocontrarian. It is very new: the submissions repo was created 2026-09-24. A project registers by committing a `.recomp.json` at the root of its default branch; decomp progress is pulled daily from an objdiff `report.json` GitHub Actions artifact. It does not render an embeddable badge or mosaic.

### Cited Findings
- The page title is "recomp.board", credited to neurocontrarian, and lists 2,505 rows as of 2026-10-19. It has a feed (`feed.xml`), a stats page, and a "Last commit" dot that turns green for activity in the last 3 months. Statuses are owner-written. Rows are mostly script-read and "scripts misread". [recomp.fyi](https://recomp.fyi/); [stats](https://recomp.fyi/stats.html)
- Submissions live in `neurocontrarian/recomp-board`, created 2026-09-24 and last pushed 2026-10-16, no license listed. The spec and JSON Schema are CC BY 4.0; the table itself may not be copied without written permission. A bot checks the repo and replies, usually within minutes. [repo](https://github.com/neurocontrarian/recomp-board); [API](https://api.github.com/repos/neurocontrarian/recomp-board)
- Two routes to add: commit `.recomp.json` at the repo root (no account needed; the board never writes to your repo), or open a GitHub issue form. For a new row, `game`, `system`, and `type` are required. [add page](https://recomp.fyi/add)
- Spec version 1 (draft), file at the root of the default branch, UTF-8 JSON, one object. Schema URL is `https://recomp.fyi/schema/v1.json`. Fields: `$schema`, `game`, `wikidata` (`Q` plus digits), `system` (string or list), `type` (`recomp`|`port`|`decomp`, or a list), `original` (object or list with optional `region`, `revision`, `serial`, `sha1`), `project`, `status` (`exploring`|`in-progress`|`playable`|`released`|`complete`|`paused`|`unknown`), `targets` (list), `toolchain` (string or list, free text), `approach`, `maintainers` (`[{name, link?}]`), `links` (`[{label, url}]`, https only), `help` (list), `tags` (list), `notes`, and `x-*` extensions. [spec](https://recomp.fyi/spec); [schema](https://recomp.fyi/schema/v1.json)
- Valid `system` spelling for this project: "PC (DOS)". Valid `targets` include "Windows", "Linux", "macOS", "Steam Deck", "Android", "iOS", "Switch", "Browser". `additionalProperties` is false except for `^x-` keys. `version`, `builds`, and `lastCommit` are read from the repo and must be left out. [spec](https://recomp.fyi/spec); [add page](https://recomp.fyi/add)
- The add page says the file must stay under 8 KB and must not mention ROMs, ISOs, or where to obtain them. It also states per-field caps (system up to 8, targets 8, toolchain 4, original 6, maintainers 6, links 6, help 8, tags 8, toolchain custom names up to 32 characters). [add page](https://recomp.fyi/add). The spec page states no numeric limits, and the JSON schema has no `maxLength`/`maxItems` ([spec](https://recomp.fyi/spec), [schema](https://recomp.fyi/schema/v1.json)). The caps come from the add-page summary only and could not be copied verbatim (WebFetch limits quotes), so treat them as a conservative target.
- Files for several games in one repo: `.recomp-2.json` through `.recomp-9.json`. Legacy name `.recomp-board.json` is also read. [spec](https://recomp.fyi/spec)
- Progress for decomps: upload `build/report.json` (an objdiff progress report) as a GitHub Actions artifact named `VERSION_report` (example `SLUS_203.88_report`) from a workflow on the default branch. The board reads it daily and shows the percentage of matched code. Status is "In progress" until 100%, then "Complete" once data also matches, unless the owner sets one. With several versions, a figure appears only if one matches the `original` field or they agree within half a point. A `.recomp.json` is still needed for maintainers, status, notes, help, and original release. [add page](https://recomp.fyi/add)
- The board shows no embeddable badge or image. The pages that mention progress mention only a displayed percentage on the game page; no badge or progress image endpoint is mentioned. [add page](https://recomp.fyi/add); [home](https://recomp.fyi/)
- Existing DOS rows (Doom, Quake, Alley Cat) and a PC (Windows) decomp row (Crimsonland) exist, but no X-COM or Watcom rows were seen in the first 100,000 characters of the page. [home](https://recomp.fyi/)
- Hosts other than GitHub (GitLab, Codeberg, sourcehut, self-hosted) are accepted when public over HTTPS; it checks the file daily. [add page](https://recomp.fyi/add)

### Inferences
- A candidate `.recomp.json` for ReverseApoc (fields chosen from the spec; values are our draft, not verified against the live validator):
  ```json
  {
    "$schema": "https://recomp.fyi/schema/v1.json",
    "game": "X-COM: Apocalypse",
    "system": "PC (DOS)",
    "type": "decomp",
    "original": { "region": "...", "revision": "..." },
    "project": "ReverseApoc",
    "status": "in-progress",
    "targets": ["Windows", "Linux"],
    "toolchain": ["Open Watcom C/C++", "DOS/4GW"],
    "approach": "Matching decompilation of the DOS executable with Watcom C/C++",
    "maintainers": [{ "name": "ayrtondenner", "link": "https://github.com/ayrtondenner" }],
    "links": [{ "label": "Progress", "url": "https://<user>.github.io/ReverseApoc/progress.html" }],
    "notes": "..."
  }
  ```
  `original.sha1` can be added after hashing the exact executable the project targets. `wikidata` is optional; the X-COM: Apocalypse Q-ID was not looked up. `targets` should reflect what the project will actually build for.
- Because the progress ingestion expects an objdiff-format `report.json`, ReverseApoc would need to emit that shape (see section 3) for percentage display. Without it, the row would show no percentage, and `status` plus `notes` would carry the information.
- The board is about 4 weeks old, run by a single person, and its table is not freely reusable, so it is a visibility channel, not infrastructure to depend on. Keep the project's own progress page as the source of truth.

### Gaps
- The exact artifact-ingestion code was not read. Whether a hand-built report is accepted, and how strictly the `VERSION_report` name is parsed, is unverified.
- The Rules and Terms text on recomp.fyi was not captured (the page was 268k characters; only the first 100k were read).
- The WebFetch summaries differ on caps (8 KB, per-field maxima) versus the schema. The authoritative live validator was not run.

## 6. Other approaches in the community: comparison

### Takeaway
There are three families: a hosted service (decomp.dev, now closed to new projects), a hosted API (frogress), and self-hosted static pipelines (JSON + shields badge + Pages, as in sa3 and AnyPS5). For a new Watcom/OMF project, only the self-hosted option is realistic.

### Cited Findings
- frogress: an API for storing/retrieving decompilation progress, organized as project > version > category > entry > measure. It needs an API key, and a site admin creates the project and gives a slug and key. Hosted at `https://progress.deco.mp`, or self-hosted with Docker Compose (`docker-compose up --build`). It documents no badge format. [frogress](https://github.com/decompals/frogress)
- sa3 (Sonic Advance 3): `.github/workflows/build.yml` on push to `main` builds the ROM, then runs `python3 scripts/progress.py {csv,shield-json}` (with and without `-m`). It writes to `gh-pages/reports/`, uploads the artifact, and a second job commits `reports` and `maps` to the `gh-pages` branch with `EndBug/add-and-commit@v7`. [build.yml](https://raw.githubusercontent.com/SAT-R/sa3/main/.github/workflows/build.yml)
- sa3 `scripts/progress.py` computes progress from the linker map (`sa3.map`) by summing `.text`/`.rodata` section sizes by source directory, and subtracting `NONMATCH`/`ASM_FUNC` function sizes found by regex over `src/*.c`. [progress.py](https://raw.githubusercontent.com/SAT-R/sa3/main/scripts/progress.py)
- sa3's live shield JSON is `{"schemaVersion": 1, "label": "progress", "message": "90.3%", "color": "yellow"}` at `https://sat-r.github.io/sa3/reports/progress-sa3-shield.json`. [live JSON](https://sat-r.github.io/sa3/reports/progress-sa3-shield.json)
- shields.io endpoint badge: requires `schemaVersion: 1`, `label`, `message`; optional `color`, `labelColor`, `isError`, `namedLogo`, `style`. Use `https://img.shields.io/endpoint?url=<json url>`. `cacheSeconds` cannot go below Shields' default, so badge updates can lag. [shields.io](https://shields.io/badges/endpoint-badge)
- Mizuchi (macabeus): an LLM-driven matching-decompilation pipeline runner (m2c, decomp-permuter, objdiff, plus Claude). It outputs per-run `run-results-*.json` and `run-report-*.html`. The benchmark-reports site compares AI models on Sonic Advance 3 and Animal Forest. It is a pipeline/benchmark report, not a project progress tracker. [Mizuchi](https://github.com/macabeus/mizuchi); [benchmark reports](https://macabeus.github.io/mizuchi-benchmark-reports/)
- One web search for a ready-made generic "decomp progress mosaic SVG + shields JSON" tool returned only unrelated shields.io pages. This is an absence-of-evidence result from a single query, not a confirmed non-existence; no source to cite.
- I could not confirm sm64 or pokered progress scripts: the `n64decomp/sm64` root listing shows no progress script. [sm64 root](https://api.github.com/repos/n64decomp/sm64/contents/)

### Inferences
| Approach | Setup effort | Data needed | Hosting | Fit for Watcom/OMF |
|---|---|---|---|---|
| decomp.dev | closed to new projects | objdiff report.json | service | not available |
| recomp.fyi | one JSON file | objdiff-style report.json artifact (optional) | service, no badge | visibility only |
| frogress | needs an admin-issued key | any per-category integers | hosted or Docker | possible, extra moving part |
| sa3-style shield JSON on Pages | small Python script | per-function status | self-hosted | yes |
| AnyPS5-style treemap SVG on Pages | small Python script | per-function status | self-hosted | yes |
| Mizuchi reports | n/a | n/a | n/a | not a progress tracker |

### Gaps
- No evidence for how sm64 or pokered report progress was found (not verified; I did not read them).
- The mizuchi benchmark reports page was read for its summary only.

## 7. Recommended pipeline for ReverseApoc

### Takeaway
Use a self-hosted pipeline: a per-function status source, a stdlib Python script that writes JSON, an SVG mosaic and a shields endpoint JSON, deployed to GitHub Pages by a GitHub Actions workflow on push to `main`. Add a `.recomp.json` for recomp.fyi listing. Do not use a git hook; it would run on a contributor's machine, not on `main`.

### Cited Findings
- The AnyPS5 and sa3 patterns above prove the design: the AnyPS5 `pages.yml` deploys Pages through `actions/upload-pages-artifact@v5` and `actions/deploy-pages@v5` ([pages.yml](https://raw.githubusercontent.com/boykopovar/AnyPS5/main/.github/workflows/pages.yml)); sa3 commits JSON into a `gh-pages` branch ([build.yml](https://raw.githubusercontent.com/SAT-R/sa3/main/.github/workflows/build.yml)).
- The default GitHub Pages URL is `https://<user>.github.io/<repo>/`, with no custom domain needed (same pattern as the AnyPS5 and sa3 URLs above).

### Inferences
Design (proposal, not tested):
1. Data source: a per-function table the project owns, for example `progress/functions.json` or CSV (`module, function, address, size, status`, with `status` in matched / partial / unmatched, and optional `fuzzy_percent`). Fill it either by (a) a regex over source markers such as `MATCHING`/`NONMATCHING` comments (the sa3 approach), or (b) a build step that compares each compiled function's bytes against the original EXE. Weight cells by function size in bytes.
2. `tools/progress.py` (stdlib only, run with `python -I`): reads the table and writes `progress.json` (totals, per-module counts, git SHA, timestamp), `progress.svg` (squarified treemap, one cell per function, green/amber/gray, modules as groups), `shield.json` (`{"schemaVersion":1,"label":"progress","message":"12.3%","color":"yellow"}`), and optionally an objdiff-shaped `report.json`.
3. Workflow `.github/workflows/progress.yml` on `push: branches: [main]`, with `paths` filters, `concurrency: pages`, and `permissions: pages: write, id-token: write, contents: read`. Steps: checkout, run the script, `actions/upload-pages-artifact`, `actions/deploy-pages`. Pin action versions at release time (AnyPS5 uses `checkout@v7` and Pages `@v5` as of this research). Optionally gate on content change as AnyPS5 does.
4. README: `[![progress](https://<user>.github.io/ReverseApoc/progress.svg)](https://<user>.github.io/ReverseApoc/progress.html)` plus `![Progress](https://img.shields.io/endpoint?url=https://<user>.github.io/ReverseApoc/shield.json)`. Note that GitHub README rendering proxies images via camo and may cache them.
5. recomp.fyi: commit `.recomp.json` (draft in section 5). If an objdiff-style `report.json` is built, also upload it as a `<VERSION>_report` artifact on `main` so the board shows a percentage.
6. Enable Pages with source "GitHub Actions" (repo Settings, Pages). Serving from a `gh-pages` branch is the alternative (sa3's way).

### Gaps
- Whether a hand-built report is accepted by recomp.fyi (see section 5).
- Whether the project repo will be public (Pages on private repos needs a paid plan; not checked).
- None of the proposed scripts or workflows were written or run in this session.
