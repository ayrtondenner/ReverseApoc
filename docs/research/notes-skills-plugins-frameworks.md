# ReverseApoc kickoff: Skills, plugins, spec frameworks and decomp tools (fit, cost, install)

> Research date: 2026-10-19. All web sources were accessed 2026-10-19. Repo "last push" dates and licenses come from the GitHub REST API (`gh api repos/<r>`) on 2026-10-19 unless noted. Local facts come from read-only inspection of `C:\Users\Ayrton\.claude\plugins\` and the ReverseApoc `.claude/settings.json` and `skills-lock.json`.
> NOTE: Plan mode was active for this researcher, so these notes were written to this plan file instead of the assigned scratchpad path (`...\scratchpad\research_notes\ReverseApoc kickoff research\skills_plugins_frameworks.md`). The coordinator should copy them there.

## Q0. What is actually installed and loaded in ReverseApoc today? (audit, local evidence)

### Takeaway
Of the 7 plugins enabled in ReverseApoc's `.claude/settings.json`, only **superpowers** is actually installed for this project. code-review, code-simplifier, claude-md-management and security-guidance are installed at project scope for a *different* repo (MiceliSystems). clangd-lsp is not installed anywhere. The `i-have-adhd` marketplace is not registered on this machine at all, and the settings file has no `extraKnownMarketplaces` entry for it, so teammates can't get it either.

### Cited Findings
- `C:\Users\Ayrton\.claude\plugins\installed_plugins.json` (local, read 2026-10-19) has these install records:
  - `superpowers@claude-plugins-official`: user scope v7.0.0, project scope for ReverseApoc v7.0.0, and project scope for MiceliSystems v6.4.1.
  - `code-review`, `code-simplifier`, `claude-md-management`, `security-guidance`: project scope for `...\Gitprojects\MiceliSystems` only.
  - No `clangd-lsp` record and no `i-have-adhd` record.
- `known_marketplaces.json` (local) lists only `claude-plugins-official`, `maui-skills` and `dotnet-agent-skills`. There is no `i-have-adhd` marketplace.
- The cache contains no `clangd-lsp` directory and no `i-have-adhd` directory (local `ls ~/.claude/plugins/cache/`).
- The docs explain the consequence: "When a plugin's only `true` is in the project's `.claude/settings.json`, Claude Code doesn't fetch it onto a machine where it isn't installed… the `/plugin` Errors tab shows `Plugin "<name>" is enabled in project settings but isn't installed here`." Each collaborator must run `claude plugin install <name>@<marketplace> --scope project` once. — [Plugin loading reference](https://code.claude.com/docs/en/plugins/loading); [Install and manage plugins](https://code.claude.com/docs/en/discover-plugins)
- If settings declare a marketplace under `extraKnownMarketplaces` that `known_marketplaces.json` lacks, "Claude Code clones it, then reloads plugins and downloads enabled plugins that aren't cached yet". This needs workspace trust and does not happen in cloud sessions. — [Plugin loading reference](https://code.claude.com/docs/en/plugins/loading)
- `skills-lock.json` pins one skill: `unlazy` from `Leonxlnx/unlazy` (`sourceType: github`). Copies exist in both `.agents/skills/unlazy` and `.claude/skills/unlazy` (local). Leonxlnx/unlazy is MIT, 4.0k stars, last push 2026-09-03 (GitHub API).

### Inferences
- The session's own skill list supports the audit. This researcher's session (run inside ReverseApoc) lists superpowers skills, but no `claude-md-management:claude-md-improver` skill and no `code-simplifier` agent type. Those plugins are therefore not loading in ReverseApoc.
- Recommended fix, which needs the owner's approval because it modifies files:
  1. Add `"extraKnownMarketplaces": {"i-have-adhd": {"source": {"source": "github", "repo": "ayghri/i-have-adhd"}}}` to `.claude/settings.json`.
  2. Run `claude plugin install <name>@claude-plugins-official --scope project` for each enabled official plugin, and `claude plugin install i-have-adhd@i-have-adhd --scope project`.
  3. Install `clangd` (LLVM) on PATH before enabling clangd-lsp.
- The exact JSON shape of `extraKnownMarketplaces` above follows the settings reference's GitHub-source form.

### Gaps
- The `extraKnownMarketplaces` JSON shape was not quoted verbatim from the settings-reference page. The loading page links to it but was not fetched. Verify against https://code.claude.com/docs/en/settings-reference#extraknownmarketplaces before editing.

## Q1. Spec/planning frameworks: GSD vs OpenSpec vs superpowers. Which gets a decomp project to "actually decompiling" fastest?

### Takeaway
Superpowers is already installed and has the shortest path: brainstorm, then a written plan, then execution with TDD, where the "test" can be an objdiff 100% match. GSD is the strongest add-on for milestone/phase bookkeeping and has a purpose-built `/gsd-spike`, but it is heavy: 60+ commands, hooks, and a `.planning/` tree. OpenSpec's change-proposal model fits a decomp poorly, because the spec is the binary. Verdicts: superpowers **use**, GSD **later** (trial it on a branch if milestone tracking hurts, or borrow the spike pattern by hand), OpenSpec **skip**.

### Cited Findings
**GSD (open-gsd/gsd-core)**
- What it is: a context-engineering and spec-driven framework for Claude Code, Codex, Copilot, Cursor and others. Heavy work runs in fresh-context subagents to avoid "context rot". — [GitHub README](https://github.com/open-gsd/gsd-core)
- Maintainer: the open-gsd organization (opengsd.net). Licence MIT, ~10.7k stars, last push 2026-10-19. Latest release **v1.18.0, published 2026-10-19** (GitHub API).
- Cost: free (MIT npm package), no paid tier mentioned. — [README](https://github.com/open-gsd/gsd-core)
- Install options:
  - npm, project scope: `npx @opengsd/gsd-core@latest --claude --local`, which writes into `.claude/` at the project root.
  - npm, global: `--claude --global` installs to `~/.claude/`. If both are installed, the global one wins and the installer warns. The installer registers Claude Code hooks automatically. — [install-on-your-runtime.md](https://raw.githubusercontent.com/open-gsd/gsd-core/next/docs/how-to/install-on-your-runtime.md)
  - Native plugin: the repo ships `.claude-plugin/marketplace.json` (marketplace name `gsd-core`, plugin `gsd-core`, source `./`) (GitHub API). Plugin skills are namespaced `/gsd-core:gsd-<command>`. The plugin path "ignores install-time config", and hooks need `node` on PATH. The docs are inconsistent about namespacing (`/gsd:<cmd>` vs `/gsd-*`). — [install-on-your-runtime.md](https://raw.githubusercontent.com/open-gsd/gsd-core/next/docs/how-to/install-on-your-runtime.md)
- `/gsd-spike`: runs 2–5 feasibility experiments, each framed as Given/When/Then, with executable code and a verdict of VALIDATED, INVALIDATED or PARTIAL.
  - Output goes to `.planning/spikes/` plus `.planning/spikes/MANIFEST.md`.
  - `--quick` skips intake. `--wrap-up` packages the findings into a skill at `.claude/skills/spike-findings-[project]/`. — [docs/COMMANDS.md](https://raw.githubusercontent.com/open-gsd/gsd-core/next/docs/COMMANDS.md)
- Milestones and phases:
  - `.planning/ROADMAP.md` lists the phases as `### Phase N:` headings with `**Goal:**` (and optionally `**Mode:** mvp`).
  - Phase directories live under `.planning/phases/`. `/gsd-phase --insert N` creates decimal phases such as 3.1.
  - A phase is complete only when a passing `*-VERIFICATION.md` exists. The ROADMAP checkbox is just an annotation.
  - `/gsd-new-milestone` writes PROJECT.md, REQUIREMENTS.md and ROADMAP.md. `/gsd-complete-milestone` archives to `.planning/milestones/vX.Y-phases/` and appends to MILESTONES.md.
  - Per-phase loop: `/gsd-discuss-phase` (CONTEXT.md), then `/gsd-plan-phase` (RESEARCH.md, PLAN.md, VALIDATION.md; it leads with a "tracer" end-to-end slice by default), then `/gsd-execute-phase` (waves, SUMMARY.md, VERIFICATION.md), then `/gsd-verify-work` (UAT.md). — [docs/COMMANDS.md](https://raw.githubusercontent.com/open-gsd/gsd-core/next/docs/COMMANDS.md)
- Other relevant commands: `/gsd-onboard` (existing repo), `/gsd-map-codebase`, `/gsd-quick` (ad-hoc), `/gsd-autonomous`, `/gsd-debug`, `/gsd-milestone-summary` (a "team-onboarding summary", relevant for OpenApoc handoff). — [docs/COMMANDS.md](https://raw.githubusercontent.com/open-gsd/gsd-core/next/docs/COMMANDS.md)

**OpenSpec (Fission-AI/OpenSpec)**
- What it is: "Spec-driven development (SDD) for AI coding assistants". Maintainer Fission-AI, MIT, ~72.4k stars, last push 2026-10-19. Latest release **v1.14.3 (2026-10-17)** (GitHub API).
- Install: needs Node ≥20.19. Install globally with `npm i -g @fission-ai/openspec@latest` (Homebrew also works), then run `openspec init` in each project. `openspec update` refreshes the generated slash commands.
- Workflow: `/opsx:explore`, `/opsx:propose <name>`, then apply, then archive. An expanded profile adds `/opsx:verify` among others.
- Files: `openspec/changes/<change>/{proposal.md, specs/, design.md, tasks.md}`; completed changes are archived and merged into the specs.
- Cost: no paid tier listed. A beta "Stores" team feature has no stated pricing. — [GitHub README](https://github.com/Fission-AI/openspec)

**Superpowers (already installed)**
- Installed v7.0.0 (also cached at commit bb92a7774141). Source `obra/superpowers` via claude-plugins-official, MIT, ~302k stars, last push 2026-10-10.
- Skills include brainstorming, writing-plans, executing-plans, subagent-driven-development, test-driven-development, systematic-debugging, verification-before-completion, using-git-worktrees, dispatching-parallel-agents and requesting/receiving-code-review. — local `~/.claude/plugins/cache/claude-plugins-official/superpowers/7.0.0/skills/`; GitHub API

**Suggested first-milestone steps (GSD-style ROADMAP format, usable without GSD).** A research proposal, superseded by the adopted Milestone 1 roadmap in `docs/workflow.md`; the steps are named, not numbered, so they are not confused with its phases.

| Step | Goal | Verification gate | Spike candidates |
|---|---|---|---|
| Toolchain reproduction | Dockerised Watcom compiler that reproduces the original codegen | A known hand-written C function compiles byte-identically against a disassembled target | Which Watcom version and flags (10.x, 11.0, OW 1.9, OW 2.0)? Can OW2 reproduce 10.x/11.0 output? |
| Binary split | Parse the DOS/4GW LE executable into per-function asm plus a symbol/address map (decomp config file) | Round-trip: split, reassemble, byte-identical | LE/LX parser choice; data/code boundary detection |
| First matched function | One C function at 100% match in the diff tool | objdiff (or equivalent) reports 100% | Can objdiff consume Watcom objects (see Q4: OMF not supported; objconv conversion)? |
| Progress reporting | Per-function and overall % matched, emitted as JSON/Markdown | Report regenerates in CI and in a Docker container | objdiff `report` vs reccmp-style annotations |
| Loop automation | Agent loop: pick function, draft, compile, diff, iterate | N functions matched unattended with no regressions | Ketbome/decomp-skills `dk.py` and mizuchi designs as references |

### Inferences
- Speed to first match: superpowers needs zero new installs. Its TDD red/green loop maps directly onto decomp: the failing test is a "diff ≠ 100%" check against the target object. Of the three frameworks, it is the fastest path.
- GSD's value is durable state across sessions (STATE.md, ROADMAP.md, VERIFICATION.md gates) and the spike discipline.
  - Its cost is ceremony and context: many commands, auto-registered hooks, and subagent-heavy planning that spends tokens.
  - Running GSD alongside superpowers risks two workflow systems issuing competing instructions. If adopted, trial it in a worktree or branch first.
  - The 5 phases above can be written into a hand-maintained `ROADMAP.md` without GSD.
- OpenSpec's per-change propose/apply/archive cycle adds overhead per function. Requirements-as-scenarios has little to say when the requirement is "emit identical bytes". It could fit the later "readable docs for OpenApoc" stage, but not milestone 1.

### Gaps
- GSD's exact file layout for a project-local Claude install (which hooks, which settings file) is not documented on the pages read.
- No independent benchmarks compare GSD vs OpenSpec vs superpowers speed.
- COMMANDS.md was only read to 100k of 150k characters.

## Q2. Code-quality / review "ceremonies": current command names, sources, and fit

### Takeaway
Several names are overloaded:
- `/code-review`, `/simplify`, `/security-review` and `/verify` are **built-in bundled skills** in Claude Code.
- The official **code-review plugin** adds `/code-review:code-review`. It is PR-only and uses `gh`.
- **code-simplifier** is an agent with no slash command. **security-guidance** is hooks only, with no slash command.
- **claude-md-management** provides `/claude-md-management:revise-claude-md` and the `claude-md-improver` skill.

For a matching decomp, review tools that "simplify" or "restructure" code are dangerous on matched functions, because matched C must keep producing identical bytes. Restrict them to tooling code (Python) and to comments and docs.

### Cited Findings
- **Built-in bundled skills** (Claude Code docs):
  - `/code-review` (alias `/review`, runs as a forked subagent), `/simplify`, `/security-review`, `/batch`, `/debug`, `/loop`.
  - `/verify`: "Build and run your app to confirm a code change does what it should, without falling back to tests or type checks". It runs only when invoked. `/run-skill-generator` records a per-project launch recipe at `.claude/skills/run-<name>/`, which `/run` and `/verify` follow.
  - Plugin skills are namespaced `/plugin-name:skill-name`. — [Skills docs](https://code.claude.com/docs/en/skills)
  - This session's built-in skill list also describes `code-review` with effort levels (low to max, ultra) and `--fix`/`--comment`, and `simplify` as "quality only — it does not hunt for bugs". — local session skill listing
- **`/verify` is not from a plugin.** It is a Claude Code bundled skill (min v2.1.145 per search summary; commit-check behaviour from v2.1.286). — [Skills docs](https://code.claude.com/docs/en/skills). Similar names elsewhere: GSD `/gsd-verify-work`, OpenSpec `/opsx:verify`, cursor-team-kit `verify-this`, superpowers `verification-before-completion`. — [GSD COMMANDS.md](https://raw.githubusercontent.com/open-gsd/gsd-core/next/docs/COMMANDS.md); [OpenSpec](https://github.com/Fission-AI/openspec); GitHub API listing of `cursor/plugins/cursor-team-kit/skills`
- **code-review plugin** (`code-review@claude-plugins-official`, author Anthropic, Apache-2.0 marketplace):
  - Its single command file `commands/code-review.md` reviews a **pull request**.
  - allowed-tools are limited to `gh pr/issue/search` commands.
  - Flow: Haiku pre-checks, 5 parallel Sonnet reviewers (CLAUDE.md adherence, shallow bug scan, git blame history, prior PR comments, code-comment compliance), then Haiku confidence scoring 0–100. Invoke as `/code-review:code-review`, because bare `/code-review` is the built-in. — local `cache/claude-plugins-official/code-review/d4226d062928/commands/code-review.md`; [Skills docs (namespacing)](https://code.claude.com/docs/en/skills)
- **code-simplifier plugin** (v1.0.0, Anthropic): contains only `agents/code-simplifier.md`, with no commands and no skills. It is described as "simplifies and refines code for clarity, consistency, and maintainability while preserving functionality. Focuses on recently modified code". — local cache; official marketplace.json
- **security-guidance plugin** (v2.0.14, author David Dworken, Anthropic):
  - Hooks only (`hooks/hooks.json`, `security_reminder_hook.py`, `llm.py`, `review_api.py`).
  - Description: "Pattern-based warnings on edits, LLM-powered diff review on Stop, and an agentic commit reviewer that catches injection, XSS, SSRF, hardcoded secrets…". — local `cache/.../security-guidance/2.0.14/.claude-plugin/plugin.json`
  - The official marketplace also offers `claude-security` ("Deep vulnerability scanning… at a chosen effort tier"). — local official marketplace.json
- **claude-md-management** (v1.0.0, Anthropic):
  - Command `commands/revise-claude-md.md` ("Update CLAUDE.md with learnings from this session", tools Read/Edit/Glob).
  - Skill `skills/claude-md-improver/SKILL.md` ("Audit and improve CLAUDE.md files… evaluates quality against templates, outputs quality report, then makes targeted updates").
  - Names: `/claude-md-management:revise-claude-md` and `/claude-md-management:claude-md-improver`; bare names work if not shadowed. — local cache; [Skills docs](https://code.claude.com/docs/en/skills)
- **thermo-nuclear-code-quality-review** (cursor/plugins, `cursor-team-kit/skills/`):
  - Frontmatter `disable-model-invocation: true`, so it is manual only. It is a "extremely strict maintainability review for abstraction quality, giant files, and spaghetti-condition growth". Rules include files under 1,000 lines and "code judo" restructuring.
  - It has no Cursor-specific tool calls, so it is technically usable as a Claude Code skill. Its examples lean TypeScript (`any`/`unknown`, casts, subcomponents). — [SKILL.md](https://raw.githubusercontent.com/cursor/plugins/main/cursor-team-kit/skills/thermo-nuclear-code-quality-review/SKILL.md)
  - **Not installable as a Claude plugin.** cursor/plugins' `.claude-plugin/marketplace.json` (marketplace `cursor-plugins`) lists only `origin-apps` and `pstack`, not cursor-team-kit.
  - **GitHub reports no licence** for the cursor/plugins repo, so copying is legally unclear. The repo has 13k stars and was pushed 2026-10-19 (GitHub API). Manual copy or `npx skills add cursor/plugins` are the only routes.
- **Ponytail** (DietrichGebert/ponytail):
  - What it is: "Makes your AI agent think like the laziest senior dev in the room", i.e. write less code and reuse the stdlib.
  - Maintainer DietrichGebert, MIT, ~167.9k stars, latest release v5.3.2 (2026-10-16), last push 2026-10-18. Free; GitHub Sponsors only.
  - Commands: `/ponytail [lite|full|ultra|off]`, `/ponytail band`, `/ponytail-review` (diff), `/ponytail-audit` (repo), `/ponytail-debt` (collects `shortcut:` comments), `/ponytail-gain`, `/ponytail-help`.
  - Self-reported, unverified benchmark: 53% less code, 26% less cost over 39 tasks.
  - Install: `/plugin marketplace add DietrichGebert/ponytail`, then `/plugin install ponytail@ponytail` (marketplace name `ponytail`, per GitHub API). — [GitHub](https://github.com/dietrichgebert/ponytail)
- **pstack** (backnotprop/pstack):
  - What it is: a standalone mirror of Cursor's `cursor/plugins/pstack` by "poteto" (React core team). MIT, 2.3k stars, last push 2026-10-19.
  - Contents: 24 principle skills plus `/poteto-mode`, a router over 23 playbooks. Also `/interrogate`, `/arena`, `/swarm`, `/tdd`, `/unslop`, `/reflect`, plus agents `poteto-agent` and `comment-sicko` (a read-only comment reviewer).
  - Delegates code to **Grok by default** and uses Opus 5.5 for judgment. Some features are Cursor-only, and it references cursor-team-kit skills that it doesn't bundle.
  - Install: `/plugin marketplace add cursor/plugins` then `/plugin install pstack@cursor-plugins`, or `npx skills add backnotprop/pstack`. Commands become `/pstack:poteto-mode`. — [GitHub](https://github.com/backnotprop/pstack)
- **i-have-adhd** (ayghri/i-have-adhd):
  - MIT, ~57.8k stars, last push 2026-10-11, free.
  - Scope: shapes **chat responses** (lead with the next action, numbered steps, no preambles, ≤5 items per group). Its SKILL.md has **no rules for code comments, commits, or docs**. `disable-model-invocation: true`, invoked with `/i-have-adhd`, persists until "stop adhd mode". — [SKILL.md](https://raw.githubusercontent.com/ayghri/i-have-adhd/main/skills/i-have-adhd/SKILL.md)
  - Install: `claude plugin marketplace add ayghri/i-have-adhd`, then `claude plugin install i-have-adhd@i-have-adhd`.
  - Always-on mode: a SessionStart hook runs only if the **user-level** flag file `~/.claude/.i-have-adhd-always` exists. There is no project-scope variant. — [INSTALL.md](https://raw.githubusercontent.com/ayghri/i-have-adhd/main/INSTALL.md)

### Inferences (fit verdicts, decomp-specific)
| Item | Verdict | One-line reason |
|---|---|---|
| Built-in `/code-review` (local diff, effort levels) | **use** | Works on local diffs without a PR. Good for Python tooling and for reviewing comments and docs on matched C. |
| `code-review` plugin (`/code-review:code-review`) | **later** | PR-only via `gh`. Useful once the project uses GitHub PRs for OpenApoc-facing contributions. Spends 5+ subagents per review. |
| Built-in `/simplify` and the `code-simplifier` agent | **skip on matched C / use on tooling** | "Simplifying" a matched function changes codegen and breaks the match. Fine for Python scripts. |
| Built-in `/security-review` | **skip (occasional)** | Decomp of a 1997 offline game has little attack surface. Possibly useful for Docker and CI scripts. |
| `security-guidance` plugin | **skip / disable** | Its web-vuln focus (XSS, SSRF, injection) is noise for decomp, and its LLM review on every Stop adds token cost. |
| `/verify` (built-in) | **use, with a recipe** | Record a `/run-skill-generator` recipe that builds the object and runs the diff tool, so "verify" means "objdiff says 100%". This is an inference from the docs. |
| claude-md-management | **use** | Cheap, and keeping CLAUDE.md accurate (toolchain flags, matching gotchas) is high-leverage for agent decomp loops. Not currently installed for this project. |
| thermo-nuclear-code-quality-review | **skip** | TS-flavoured, unlicensed, not plugin-installable. "Code judo" restructuring conflicts with byte matching. |
| Ponytail | **skip** (maybe later for tooling) | "Write less code" doesn't apply when code shape is dictated by the original binary. Overlaps superpowers. |
| pstack | **skip (overkill)** | Third workflow system on top of superpowers (and GSD), Grok delegation by default, Cursor-only parts. Its `comment-sicko` agent is the one interesting piece for comment quality. |
| i-have-adhd | **keep if the owner likes it; it does not help code comments** | It shapes chat output only. To fix project install, add `extraKnownMarketplaces` and install it (see Q0). Always-on mode is user-level only. |

### Gaps
- Which takes precedence when the plugin `/code-review:code-review` and the built-in `/code-review` are both present was inferred from the namespacing docs, not tested.
- security-guidance's per-Stop LLM cost was not measured. `claude plugin details security-guidance` would show the "Always-on" token count.
- Whether pstack's Grok delegation works inside Claude Code (vs. Cursor only) was not verified.

## Q3. C/C++ skills: cpp-pro, cpp, Qt agent-skills, clangd-lsp, and other C / legacy / RE / decomp skills

### Takeaway
Every general C++ skill found targets C++11–C++23, whose advice (smart pointers, concepts, STL, modernize) is actively wrong for Watcom-era C or pre-standard C++. Skip them. Qt skills are Qt-specific. **clangd-lsp is the only C tool worth enabling**, and only once a clang-parsable compile config exists.

Decomp-specific skills do exist: Ketbome/decomp-skills (Claude plugin), madpai/game-decomp-compendium, and decomp.wtf (now archived). They are all free and MIT, but none covers Watcom or DOS/4GW. RE skills (trailofbits ghidra-headless, mitsuhiko ghidra) are free and useful for the split and analysis phases. No paid skills were found.

### Cited Findings
- **cpp-pro** (sickn33/agentic-awesome-skills):
  - Frontmatter: `risk: critical`, `source: community`, `date_added: 2026-02-27`. Description: "Write idiomatic C++ code with modern features, RAII, smart pointers, and STL algorithms". Focus is C++11/14/17/20/23, and nothing covers C89/C++98/Watcom. — [SKILL.md](https://raw.githubusercontent.com/sickn33/agentic-awesome-skills/main/skills/cpp-pro/SKILL.md)
  - Repo is MIT, ~48k stars, last push 2026-10-19 (GitHub API).
- **cpp** (Mindrally/skills): "Guidelines for modern C++ development with C++17/20 standards". It recommends concepts, ranges, span and coroutines, and replacing C arrays and `NULL`. — [SKILL.md](https://raw.githubusercontent.com/Mindrally/skills/main/cpp/SKILL.md). Repo is Apache-2.0, 278 stars, last push 2026-10-08 (GitHub API).
- **Qt agent-skills** (TheQtCompanyRnD/agent-skills):
  - 13 skills, including `qt-cpp-review` ("Qt C++ code for model rules, memory, threads…"), `qt-cpp-docs` (Markdown docs from Qt/C++ sources), plus QML, Figma and CMake skills.
  - Licence: README says BSD-3-Clause; SKILL frontmatter says `LicenseRef-Qt-Commercial OR BSD-3-Clause`. Using the skills "under Qt commercial licensing" implies accepting the Qt AI Services T&C.
  - Install: `/plugin marketplace add TheQtCompanyRnD/agent-skills`, then `/plugin install qt-development-skills` (marketplace name `qt-skills-and-tools`), or `npx skills add TheQtCompanyRnD/agent-skills`. — [GitHub](https://github.com/TheQtCompanyRnD/agent-skills); GitHub API
  - Also listed in **claude-plugins-official** as `qt-development-skills`, pinned at sha a784c48445e3. — local official marketplace.json
  - Repo last push 2026-10-08, 488 stars (GitHub API).
  - Blog posts (qt.io) were not fetched.
- **clangd-lsp** (official, Anthropic, v1.0.0): manifest `lspServers.clangd` runs `clangd --background-index` for `.c .h .cpp .cc .cxx .hpp .hxx .C .H`. It requires the `clangd` binary on PATH; on Windows, get it from LLVM releases. Install: `claude plugin install clangd-lsp@claude-plugins-official --scope project`. — local `marketplaces/claude-plugins-official/plugins/clangd-lsp/README.md` and marketplace.json
- **Ketbome/decomp-skills**:
  - Skill `matching-decomp` (references for recovery, setup, per-function loop, orchestration, toolchain forensics, permuter), the `dk.py` "decomp kit" (`dk show/check/done/rescue/state`), subagents `decomp-worker`, `decomp-forensics` and `decomp-runner`, and a session-start state hook.
  - Focus is MIPS (PS1/PS2/N64/PSP) with splat. Relocation-aware compare is MIPS-only. The only compiler catalogue is SN ee-gcc. No x86/MSVC/Watcom.
  - Install: `/plugin marketplace add Ketbome/decomp-skills`, then `/plugin install decomp-skills@decomp-skills`, or `npx skills add Ketbome/decomp-skills -a claude-code` (project-local without `-g`). — [GitHub](https://github.com/Ketbome/decomp-skills)
  - MIT, **1 star**, last push 2026-10-19 (GitHub API).
- **madpai/game-decomp-compendium**:
  - 8 skills: gamedecomp-library, decomp-matching-workflow, re-binary-recon, game-hooking-patterns, engine-reimplementation, game-asset-formats, and two engine-specific ones.
  - Its toolchain map includes reccmp, objdiff, dtk, splat and asm-differ. Compiler idioms cover MSVC, MWCC, GCC and IDO, with **no Watcom or DOS**.
  - Install: `./install.sh` copies into `~/.claude/skills`, which is user scope.
  - MIT, 2 stars, last push 2026-10-08. — [GitHub](https://github.com/madpai/game-decomp-compendium); GitHub API
- **i12bp8/decomp.wtf**: a Claude Code plugin with a "decompile" skill (agents claim functions, get the target asm and an objdiff diff, and objdiff judges). MIT, 506 stars, last push 2026-10-15, and **archived = true** per the GitHub API on 2026-10-19. — [search result](https://github.com/i12bp8/decomp.wtf); GitHub API. Another researcher covers it in depth.
- **RE skills**:
  - trailofbits/skills includes `ghidra-headless` (decompile to C pseudocode, signatures, call graphs). The repo is CC-BY-SA-4.0, 7.6k stars, last push 2026-10-15.
  - mitsuhiko/agent-stuff has a `ghidra` skill (headless analyser). Apache-2.0, 3.2k stars, last push 2026-09-27. Install by copying the folder to `.claude/skills`.
  - Others (a5c-ai ghidra/IDA, mukul975 malware-RE, sickn33 `reverse-engineer`, tagged offensive-risk) are malware or security oriented. — [openskillindex/claudeskills search results](https://openskillindex.com/skills/trailofbits-skills-curated-ghidra-headless); GitHub API
- **macabeus write-ups**: an LLM matching experiment reached 80% matched in the best run and 74% on average over 6 runs of 60 functions. The agent "frequently wrongly assumes there is a perfect match" when it can't run objdiff. — [Medium: Can LLMs Really Do Matching Decompilation?](https://macabeus.medium.com/can-llms-really-do-matching-decompilation-i-tested-60-functions-to-find-out-4e39b0ae4288); also [Claude Code and 51% of a 2001 GBA game](https://macabeus.medium.com/starting-a-decompilation-project-from-zero-claude-code-and-51-of-a-2001-gba-game-a9a75a4c1487)
- **skills.sh**: a query for C, legacy C or RE returned no rendered listings, so the page snapshot was empty. — [skills.sh](https://skills.sh/?q=c%20programming)

### Inferences (fit verdicts)
| Item | Verdict | Reason |
|---|---|---|
| cpp-pro | **skip** | C++11–23 advice (RAII, smart pointers, concepts) would push the agent away from Watcom-compatible code. |
| Mindrally cpp | **skip** | Same problem: it tells the agent to replace C arrays and `NULL`, which is wrong for byte-matching 1997 code. |
| Qt agent-skills (qt-cpp-review, qt-cpp-docs) | **skip** | Qt-specific rules. The docs-generation idea could inspire a project-specific "OpenApoc docs" skill later. |
| clangd-lsp | **use (after toolchain reproduction)** | Go-to-definition and diagnostics help on a large C codebase, but clang won't parse Watcom extensions (`#pragma aux`, `__far`/`__near`, `_Packed`, `__watcall`) without a shim header and `compile_flags.txt` (e.g. `--target=i386-pc-none -m32 -std=c89 -D__WATCOMC__=1100`). This is an inference, not verified. |
| Ketbome/decomp-skills | **later (reference)** | Best-shaped Claude plugin for a per-function loop, but MIPS-centric and only 1 star. Borrow `dk.py`'s state and rescue ideas for loop automation. |
| game-decomp-compendium | **later (reference)** | Its reccmp and MSVC idioms are the nearest analogue to x86 Watcom. It installs at user scope only, so read it and don't install it. |
| trailofbits ghidra-headless / mitsuhiko ghidra | **later (binary split, first matched function)** | Useful for initial function discovery and pseudo-C drafts from the LE binary, if Ghidra is used. |
| A project-local custom "watcom-decomp" skill | **use (write one)** | No marketplace skill covers Watcom or DOS/4GW. Capture toolchain flags and codegen idioms as they are discovered, for example with superpowers' writing-skills or GSD `--wrap-up`. |

### Gaps
- mcpmarket.com and awesome-claude-skills lists were not searched directly, because of the tool-call budget. Only openskillindex, claudeskills.info and skills.sh appeared.
- No paid C or decomp skills were found. This is absence of evidence from limited searching, not proof.
- The Qt blog posts were not fetched.
- Whether OpenApoc itself uses Qt (e.g. for its launcher) was not verified. That is the only way the Qt skills could become relevant.

## Q4. Decomp developer tools: install, x86/Watcom support, VS Code integration

### Takeaway
x86 support is thin across the console-decomp ecosystem, and **Watcom's OMF object format is the central blocker**.
- objdiff supports x86 (COFF, per README) but **not OMF**: issue #97 is open, and a WIP `omf` branch was last touched 2025-09-25.
- m2c and decomp-permuter have **no x86**. asm-differ has x86 "to a limited extent".
- reccmp is the one mature x86 matching tool, but it is MSVC-only.

Plan a Phase-1/3 spike for "OMF → COFF/ELF via objconv, then objdiff". The most likely alternative is a custom Python differ on top of Watcom's own `wdis` disassembler (an inference).

### Cited Findings
- **objdiff** (encounter/objdiff):
  - Maintainer encounter (decomp.dev). Licence Apache-2.0 OR MIT, 604 stars, last push 2026-10-19. Latest release **v3.8.2 (2026-09-29)** (GitHub API).
  - Architectures: ARM, ARM64, MIPS, PPC, SuperH, x86/x86_64. GUI and `objdiff-cli` (releases or Cargo); config file `objdiff.json` (units, target/base paths, `custom_make`, watch patterns); WASM and web builds. — [GitHub](https://github.com/encounter/objdiff)
  - One README version says "x86 (COFF only at the moment)" and an older one says "PE only". The x86 backend is iced-x86. Demangling covers CodeWarrior, Itanium and MSVC, **not Watcom**. — [search summary of objdiff README/docs.rs](https://docs.rs/crate/objdiff-core/3.8.1)
  - **OMF:** issue #97 "Support OMF object format" is open. It notes that OMF "would also open objdiff to being used with Borland, really old MSVC, and Watcom targets".
  - Workarounds cited in the issue: OmniBlade's OMF-capable binutils fork (used so decomp.me has a usable objdump), sillyc0n's binutils 2.42 OMF port, and tomsons26's `objconv` fork that "sort of fixes objconv to handle 32 bit OMF records properly", though it strips inlines and comdats.
  - An upstream request was filed at gimli-rs/object#736. The `omf` branch HEAD is "[WIP] OMF object support", dated 2025-09-25. — GitHub API: `repos/encounter/objdiff/issues/97`, `commits/omf`
- **objdiff VS Code extension** `decomp-dev.objdiff`: publisher decomp.dev, 207 installs, Free. The README calls it "WIP". — [VS Marketplace](https://marketplace.visualstudio.com/items?itemName=decomp-dev.objdiff); [objdiff README](https://github.com/encounter/objdiff)
- **asm-differ** (simonlindholm): supports MIPS, PPC, AArch64, ARM32, SH2/4, m68k, "x86 to limited extent". Unlicense, 178 stars, last push 2026-09-06. Install with pip from git (`pip install 'asm-differ @ git+https://github.com/simonlindholm/asm-differ.git'`) or by copying `diff.py`; config in `diff_settings.py`. — [GitHub](https://github.com/simonlindholm/asm-differ); GitHub API
- **m2c**: "a decompiler targeting MIPS, PowerPC, ARM, and SuperH". **No x86.** GPL-3.0, 662 stars, last push 2026-09-16. Install as a git dependency in pyproject. — [GitHub](https://github.com/matt-kempster/m2c); GitHub API
- **decomp-permuter**: "supports MIPS (compiled by IDO, possibly GCC), PowerPC, and ARM32". **No x86.** It scores via objdump diffs; permuter@home needs Docker and doesn't run on native Windows. MIT, 234 stars, last push 2026-10-06. — [GitHub](https://github.com/simonlindholm/decomp-permuter); GitHub API
- **decomp_settings** (`decomp.yaml`): a spec plus a Rust library with Python bindings (PyPI and crates.io `decomp_settings`). Apache-2.0/MIT, 7 stars, last push 2026-01-16. Consumers aren't named on the page. — [GitHub](https://github.com/ethteck/decomp_settings); GitHub API
- **coddog**: "Identify duplicate functions and portions of functions among one or more binaries", with modes match, cluster, submatch, compare2 and compare-n. Its examples use `decomp.yaml`. Architecture isn't stated. Apache-2.0/MIT, 48 stars, last push 2026-07-07. — [GitHub](https://github.com/ethteck/coddog); GitHub API
- **Mizuchi** (macabeus/mizuchi):
  - An automated matching pipeline: m2c, permuter, Claude, compile script, objdiff, then integrate. It retries with extra context and caches Claude responses in `claude-cache.json`.
  - Install: clone, then `npm install && npm run build && npm run build:ui`. Config in `mizuchi.yaml`, not decomp.yaml.
  - **Needs `ANTHROPIC_API_KEY` or a Claude Code login**, so the cost is API tokens. Its optional embeddings download about 2–3 GB.
  - Example targets: gba, n64, ps1. MIT, 78 stars, last push 2026-08-17. — [GitHub](https://github.com/macabeus/mizuchi); GitHub API
- **Kappa** (macabeus/kappa):
  - A VS Code extension, `macabeus.kappa` v1.7.0, 279 installs. MIT, 52 stars, **last commit 2026-02-20**.
  - AI features run through **GitHub Copilot** Agent mode and Chat, not Claude. Bundles objdiff, m2c ("Decompile with m2c") and permuter ("Permute it"); creates decomp.me scratches; works in single-root workspaces only. — [GitHub](https://github.com/macabeus/kappa); [VS Marketplace](https://marketplace.visualstudio.com/items?itemName=macabeus.kappa); GitHub API
  - Plugins are AST-transform scripts in `.kappa-plugins/` at the workspace root, run with "Run Kappa Plugins". Examples: AddCheckOffsetMacroPlugin, AddOffsetCommentsPlugin, ApplyQNotationPlugin, DoubleIntAssignmentPlugin, DummyPlugin and LiftVariableDeclarationsPlugin (GitHub API listing of `example-kappa-plugins/`).
  - **ApplyQNotationPlugin** rewrites raw numbers assigned to `Vec32` into Q fixed-point form (`player.x = 256;` becomes `player.x = Q(1);`), which is GBA-specific. — [README](https://github.com/macabeus/kappa)
  - **AddOffsetCommentsPlugin** "add[s] offset comments to record fields and a size comment to the record", accounting for alignment (`/* 0x08 */ Vec2_32 qValue;`, `} Example; /* size: 0x18 */`). It hard-codes `MEMORY_ALIGNMENT = 8` and a `u8/u16/s32…` type-size map. — source of `example-kappa-plugins/AddOffsetCommentsPlugin.js` via GitHub API
- **reccmp** (isledecomp/reccmp):
  - Annotation-driven matching (`// FUNCTION: LEGO1 0x100b12c0`) that verifies functions, vtables and variable offsets, with CSV metadata.
  - "At the moment, C++ compiled to 32-bit x86 with old versions of MSVC (like 4.20) is supported… Other compilers… not supported".
  - Install: `pip install reccmp`; `reccmp-project create --originals … --cmake-project`. AGPL-3.0, 162 stars, last push 2026-10-19. — README via GitHub API
- **ast-grep**: MIT, 16.3k stars, last push 2026-10-19 (GitHub API).
- **vscode-clangd**: MIT, 830 stars, last push 2026-10-01 (GitHub API).
- **Open Watcom v2**: last push 2026-10-19, 1,284 stars; licence shows NOASSERTION (Sybase Open Watcom Public License) (GitHub API).

### Inferences (fit verdicts)
| Tool | Verdict | Reason (decomp-specific) |
|---|---|---|
| objdiff (+ CLI report) | **use, gated on a spike** | The de facto diff and progress engine with x86 support, but Watcom OMF needs conversion (objconv fork) or a wait for the OMF branch. A spike is needed during toolchain reproduction or the first matched function. |
| objdiff VS Code ext | **later** | WIP, 207 installs. Use the objdiff GUI or CLI first. |
| asm-differ | **later (fallback)** | Limited x86. Relies on objdump, which would need the OMF binutils fork. A fallback if objdiff + objconv fails. |
| m2c | **skip** | No x86. |
| decomp-permuter | **skip** (maybe later via hack) | No x86 scoring support documented. |
| decomp_settings / decomp.yaml | **later** | Low adoption (7 stars). A good neutral config to adopt if coddog or other tools are used. |
| coddog | **later** | Could find duplicated Watcom runtime and library functions, or code shared with other MicroProse/Mythos titles. x86 support unverified. |
| Mizuchi | **later (reference design for loop automation)** | The Claude + compile + objdiff loop is architecture-agnostic, but its m2c and permuter stages are dead on x86, and it costs API tokens. |
| Kappa | **skip for now** | Copilot-centred, its m2c and permuter features don't work on x86, and the last commit was Feb 2026. Port AddOffsetCommentsPlugin's idea (struct offset and size comments) into a Python or ast-grep script. Watcom alignment (`-zp` setting) must replace the hard-coded 8. |
| reccmp | **later (reference)** | MSVC-only, but its source-annotation convention and match % reporting suit a readable, OpenApoc-facing codebase. |
| vscode-clangd | **use** | Same caveats as clangd-lsp: needs a clang-parsable shim config. |
| clang-format | **use with care** | Whitespace doesn't change codegen, but reformatting can shift `__LINE__` in `assert` and debug macros and break matches. Pin a style and run it before matching, not after. This is an inference. |
| clang-tidy | **skip** | modernize-* and cppcoreguidelines checks conflict with byte-matching. Clang can't parse Watcom pragmas without shims. |
| ast-grep | **use** | Structural search and rewrite across thousands of C files: struct-offset comments, renaming, finding patterns. C grammar support assumed via tree-sitter (not verified this session). |

### Gaps
- The exact Watcom version used by X-COM Apocalypse and its default struct packing (`-zp`) were not researched here. That belongs to the toolchain researcher.
- Whether Watcom `wcc386` can emit COFF or ELF objects directly (avoiding OMF) was not verified.
- Whether objconv (stock or tomsons26 fork) output is accepted by objdiff was not verified. This is the top spike candidate.
- objdiff's `report` CLI subcommand was not confirmed from docs. The README only mentions progress reporting powering decomp.dev.
- ast-grep's C language support was not confirmed from its docs this session.

## Q5. Search skills: file-search-skill, deep-codebase-search, intelligent-file-search. Needed or redundant?

### Takeaway
They are largely redundant. Claude Code's built-in Grep is ripgrep-based and Glob covers file finding. file-search-skill mainly adds tool-selection guidance and a Bash hook nudging toward rg/fd. Its only differentiator, ast-grep structural search, is better obtained by installing ast-grep and documenting recipes in CLAUDE.md. Verdict: **skip**.

### Cited Findings
- **file-search-skill** (netresearch):
  - Covers ripgrep, ast-grep, semgrep, fd, ripgrep-all and tokei/scc, with recipes. It adds a **PreToolUse hook on Bash** that reminds the agent to use `fd`/`rg` instead of `find`/`grep`, once per session.
  - Licence: code MIT, content CC-BY-SA-4.0. 41 stars, last push 2026-10-19.
  - Install: add the netresearch marketplace (`netresearch/claude-code-marketplace`, marketplace name `netresearch-claude-code-marketplace`), then `file-search@netresearch-claude-code-marketplace`. `npx skills` installs the SKILL.md without the hooks. — [GitHub](https://github.com/netresearch/file-search-skill); GitHub API
- The Claude Code Grep tool is described in-tool as "Content search built on ripgrep", and Glob does pattern file matching. — local tool definitions in this session

### Inferences
- On Windows with the Bash tool, the hook could still help if agents reach for `find`/`grep` in shell. That is marginal value.

### Gaps
- **deep-codebase-search** and **intelligent-file-search** (mcpmarket.com) were not fetched because of the tool-call budget. Maintainer, licence, cost and install method are unknown.

## Q6. Project-understanding tools: Understand-Anything and Groma (install and fit only)

### Takeaway
Both are free (MIT) and generate onboarding-style artifacts. They are useful **later**, once the repo has a substantial body of decompiled C and identified subsystems. On day 1 there is little source to map.
- Understand-Anything installs as a Claude Code plugin; the token cost of the first run is the main cost.
- Groma is an npm CLI with no Claude plugin. It writes a C4 architecture map as Markdown in git, which suits durable OpenApoc-facing docs.

### Cited Findings
- **Understand-Anything** (Egonex-AI):
  - Produces `.ua/knowledge-graph.json`, an interactive dashboard, guided tours, onboarding guides (`/understand-onboard`), domain maps and diff-impact analysis.
  - Commands: `/understand`, `/understand-dashboard`, `/understand-chat`, `/understand-diff`, `/understand-explain`, `/understand-onboard`, `/understand-domain`, `/understand-knowledge`.
  - Uses Tree-sitter, but supported programming languages are not listed, so C support is unconfirmed.
  - Install: `/plugin marketplace add Egonex-AI/Understand-Anything`, then `/plugin install understand-anything` (marketplace `understand-anything`, plugin source `./understand-anything-plugin`).
  - Cost: no paid tier, but it recommends a token plan or subscription (or Ollama) for the first run on large codebases.
  - MIT, ~87k stars, last push 2026-10-12. — [GitHub](https://github.com/Egonex-AI/Understand-Anything); GitHub API
- **Groma** (MrLesk/groma.md):
  - Scans a repo into a **C4 architecture map** stored as Markdown in `groma/`. Also provides a browser view (`groma web` on :4747) and static site export (`groma export ./site`).
  - Install: `npm i -g groma.md backlog.md`, then `groma init`. Setup adds a pointer in AGENTS.md/CLAUDE.md. There is no Claude plugin marketplace.
  - Free and local, with no account. MIT, 296 stars, last push 2026-10-19. — [GitHub](https://github.com/MrLesk/groma.md); GitHub API

### Inferences
- **Understand-Anything: later.** Run it after milestone 1, when there are named subsystems (geoscape, battlescape, UFOpaedia data). It runs as a Claude plugin at project scope.
- **Groma: later, and likely the better fit for OpenApoc handoff docs.** Its output is plain Markdown committed to git, so it is reviewable and diffable.
- Both are global CLI or npm installs (Groma) or plugins with token cost (Understand-Anything). Neither belongs in milestone 1.

### Gaps
- C language support in Understand-Anything was not confirmed.
- How Groma's scanners handle C (vs. JS/TS) was not confirmed.
- Their use on decomp.wtf is out of scope (covered by another researcher).
