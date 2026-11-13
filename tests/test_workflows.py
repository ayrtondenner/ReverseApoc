""".github/workflows/pages.yml (RPT-02..RPT-05, D-27, D-28, D-30): GitHub Pages is built from the
committed CSVs by tools/progress.py and deployed by GitHub's own actions, the recomp.fyi report
is uploaded as one combined artifact, and the DecompHub refresh POST runs only when the owner
turns it on. .github/workflows/match.yml (PIPE-08, D-06 to D-09, plan 07.2-08): the disabled,
label-gated base-vs-head match check runs main's tools on the pull request as data, compiling in
the image with no network. Pinned by text, like tests/test_hygiene.py: no YAML library. Nothing
here touches the network."""

from __future__ import annotations

import re

from conftest import REPO_ROOT

PAGES = REPO_ROOT / ".github" / "workflows" / "pages.yml"
GITIGNORE = REPO_ROOT / ".gitignore"

# D-27: the inputs of tools/progress.py and the workflow itself; plan 07-15 adds the mechanics
# coverage view's inputs and the signed asm list (DEC-05, D-23).
PATHS = ("config/*/status.csv", "config/*/functions.csv", "config/*/units.csv",
         "config/mechanics.toml", "config/mechanics-members.csv", "config/asm-functions.csv",
         "tools/progress.py", "decomphub.progress.json", ".github/workflows/pages.yml")  # fmt: skip
PROGRESS_RUN = "python3 -I tools/progress.py --out _site --report build/report.json"
# D-28: one combined artifact; recomp.fyi reads it by this name from the default branch.
ARTIFACT = "X-COM_Apocalypse_DOS_report"


def pages_text() -> str:
    assert PAGES.is_file(), f"{PAGES} does not exist"
    return PAGES.read_text(encoding="utf-8")


def block(lines: list[str], header: str) -> list[str]:
    """The lines nested under `header` (matched stripped, at any indent), up to the next line
    indented no deeper than it."""
    for i, line in enumerate(lines):
        if line.strip() != header:
            continue
        indent = len(line) - len(line.lstrip())
        out = []
        for nested in lines[i + 1:]:
            if nested.strip() and len(nested) - len(nested.lstrip()) <= indent:
                break
            out.append(nested)
        return out
    raise AssertionError(f"pages.yml has no {header!r} block")


def top(header: str) -> list[str]:
    """A top-level block, e.g. `on:`; its lines stripped, blanks and comments dropped."""
    lines = [line for line in pages_text().splitlines() if not line.lstrip().startswith("#")]
    top_level = [i for i, line in enumerate(lines) if line == header]
    assert top_level, f"pages.yml has no top-level {header!r}"
    return [line.strip() for line in block(lines[top_level[0]:], header) if line.strip()]


def job_lines(name: str) -> list[str]:
    """The raw lines of job `name` under `jobs:`, comments dropped."""
    lines = [line for line in pages_text().splitlines() if not line.lstrip().startswith("#")]
    return block(block(lines, "jobs:"), f"{name}:")


def job(name: str) -> list[str]:
    """The stripped lines of job `name` under `jobs:`."""
    return [line.strip() for line in job_lines(name) if line.strip()]


def indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def keys(lines: list[str]) -> list[str]:
    """The mapping keys at the shallowest indent of `lines` (a block's own keys)."""
    body = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
    least = min(indent(line) for line in body)
    return [line.strip().split(":")[0] for line in body if indent(line) == least]


def job_permissions(name: str) -> list[str]:
    """The sorted `permissions:` entries of job `name`; [] when it has no block."""
    lines = job_lines(name)
    if not any(line.strip() == "permissions:" for line in lines):
        return []
    return sorted(line.strip() for line in block(lines, "permissions:") if line.strip())


def test_pages_triggers():
    """Push to main with the paths filter, a weekly cron (it also renews the 90-day artifact)
    and workflow_dispatch (D-27)."""
    on = top("on:")
    push = on[on.index("push:"):]
    assert "branches: [main]" in push
    assert "schedule:" in push, "the push trigger comes first, then the schedule"
    paths = push[push.index("paths:") + 1:push.index("schedule:")]
    assert [p.removeprefix("- ").strip('"') for p in paths] == list(PATHS)
    crons = [line for line in on if line.startswith("- cron:")]
    assert len(crons) == 1
    fields = crons[0].removeprefix("- cron:").strip().strip('"').split()
    assert len(fields) == 5 and fields[2:4] == ["*", "*"] and fields[4].isdigit(), fields
    assert "workflow_dispatch:" in on


def test_pages_trigger_set_is_closed():
    """Fix round 1: exactly the triggers D-27 names. A pull_request or pull_request_target
    trigger would run the workflow for code that is not on main."""
    lines = [line for line in pages_text().splitlines() if not line.lstrip().startswith("#")]
    on = block(lines[lines.index("on:"):], "on:")
    assert keys(on) == ["push", "schedule", "workflow_dispatch"]
    assert "pull_request" not in pages_text()


def test_pages_permissions_and_concurrency():
    """Least privilege (T-06-57, orchestrator ruling of fix round 1: permissions per job). The
    workflow reads the repository; only deploy writes Pages and mints the OIDC token Pages
    needs; build runs repository code with read access only; notify needs no token. One deploy
    at a time, never cancelling a running one."""
    assert top("permissions:") == ["contents: read"]
    assert job_permissions("build") == []  # inherits contents: read
    assert job_permissions("deploy") == ["id-token: write", "pages: write"]
    assert "permissions: {}" in job("notify-decomphub")
    assert pages_text().count("pages: write") == 1 and pages_text().count("id-token: write") == 1
    assert top("concurrency:") == ["group: pages", "cancel-in-progress: false"]


def test_every_checkout_drops_its_credentials():
    """Fix round 1, review WR-01: no checkout in any workflow leaves the job token in .git/config
    for later steps (ci.yml runs a pull request's own code with it)."""
    workflows = sorted(PAGES.parent.glob("*.yml"))
    assert [w.name for w in workflows] == ["ci.yml", "match.yml", "pages.yml"]
    for workflow in workflows:
        text = workflow.read_text(encoding="utf-8")
        lines = text.splitlines()
        checkouts = [i for i, line in enumerate(lines) if "actions/checkout@" in line]
        assert checkouts, workflow.name
        for i in checkouts:
            step = []
            for line in lines[i + 1:]:
                if line.strip() and (indent(line) < indent(lines[i])
                                     or line.lstrip().startswith("- ")):  # fmt: skip
                    break
                step.append(line.strip())
            assert "persist-credentials: false" in step, (workflow.name, lines[i])
        assert "persist-credentials: true" not in text, workflow.name


def test_pages_build_steps():
    build = job("build")
    assert "runs-on: ubuntu-latest" in build
    assert "- uses: actions/checkout@v7" in build
    # The progress-over-days chart walks the whole history; a shallow clone gets a note only.
    assert "fetch-depth: 0" in build
    runs = [line for line in build if line.startswith("run:")]
    assert any(PROGRESS_RUN in line for line in runs), runs
    assert not any("uv " in line or "pip " in line for line in runs), "progress.py is stdlib"
    upload = build[build.index("uses: actions/upload-artifact@v7"):]
    assert f"name: {ARTIFACT}" in upload
    assert "path: build/report.json" in upload
    assert "retention-days: 90" in upload
    assert "if-no-files-found: error" in upload
    pages = build[build.index("uses: actions/upload-pages-artifact@v5"):]
    assert "path: _site" in pages


def test_pages_deploy_job():
    deploy = job("deploy")
    assert "needs: build" in deploy
    environment = deploy[deploy.index("environment:"):]
    assert "name: github-pages" in environment
    assert "url: ${{ steps.deployment.outputs.page_url }}" in environment
    assert "- id: deployment" in deploy
    assert "uses: actions/deploy-pages@v5" in deploy


def test_pages_uploads_one_report_artifact():
    """D-28: exactly one upload-artifact step, so recomp.fyi never sees several versions."""
    text = pages_text()
    assert text.count("actions/upload-artifact@") == 1
    assert text.count(ARTIFACT) == 1


def test_pages_needs_no_secret():
    """The workflow passes with no secret configured (owner rule): it names none."""
    assert "secrets." not in pages_text()


def gitignore_patterns() -> list[str]:
    return [line.strip() for line in GITIGNORE.read_text(encoding="utf-8").splitlines()]


def test_gitignore_ignores_site():
    """A local run of the Pages step writes _site/; it is never committed."""
    assert "_site/" in gitignore_patterns()


def test_gitignore_ignores_playwright_mcp():
    """Orchestrator ruling F14 (owner-approved): the Playwright MCP's output directory stays out
    of `git status`, so the clean-tree preconditions of 06-26/06-27 and the driver hold."""
    patterns = gitignore_patterns()
    assert ".playwright-mcp/" in patterns
    section = patterns[patterns.index("# --- Generated by analysis/doc tools (opt-in later) ---"):]
    assert ".playwright-mcp/" in section[:section.index("")]


# ---- Task 3: the DecompHub refresh POST (D-30) ----

REFRESH = "https://app.decomphub.com/api/progress/refresh"
# The job-level condition: this repository (never a fork, fix round 1), a push to main, and only
# once the owner sets the repository variable DECOMPHUB_REFRESH to true. Otherwise the job is
# skipped, so the workflow is inert by default.
GATE = ("if: github.repository == 'ayrtondenner/ReverseApoc' && github.event_name == 'push' "
        "&& vars.DECOMPHUB_REFRESH == 'true'")  # fmt: skip
URL = re.compile(r"https?://[^\s\"']+")
JQ = ('body="$(jq -n --arg repository "$PROJECT_REPOSITORY" --arg revision "$PROJECT_REVISION" \\',
      "'{repository: $repository, revision: $revision}')\"")  # fmt: skip
EMPTY_CHECK = 'if [ -z "$body" ]; then'
CURL = ("curl --fail --silent --show-error --max-time 20 \\",
        '-H "Content-Type: application/json" --data-binary @- \\', REFRESH)  # fmt: skip


def notify_script() -> list[str]:
    """The stripped lines of the notify step's `run: |` script."""
    notify = job_lines("notify-decomphub")
    return [line.strip() for line in block(notify, "run: |") if line.strip()]


def test_decomphub_notify_is_gated():
    notify = job("notify-decomphub")
    assert "needs: deploy" in notify
    assert GATE in notify
    assert notify.index(GATE) < notify.index("steps:"), "the gate is on the job, not a step"
    assert "||" not in GATE and "!" not in GATE
    assert "permissions: {}" in notify, "the POST needs no token"
    assert "PROJECT_REPOSITORY: https://github.com/${{ github.repository }}" in notify
    assert "PROJECT_REVISION: ${{ github.sha }}" in notify


def test_decomphub_notify_never_posts_an_empty_body():
    """Fix round 1: bash with -euo pipefail; jq builds the body into a variable, an empty body
    fails the step before curl runs, and only then is it posted with a 20 s timeout. (The
    review's stub run showed that without pipefail a missing jq let curl POST nothing.)"""
    notify = job("notify-decomphub")
    assert "shell: bash" in notify and notify.index("shell: bash") < notify.index("run: |")
    script = notify_script()
    assert script[0] == "set -euo pipefail"
    assert list(script[1:3]) == list(JQ)
    check = script.index(EMPTY_CHECK)
    assert script[check + 1].startswith('echo "::error::') and script[check + 2] == "exit 1"
    assert script[check + 3] == "fi"
    post = script[check + 4:]
    assert post[0] == "printf '%s\\n' \"$body\" |"
    assert post[1:] == list(CURL)
    assert all("curl" not in line for line in script[:check + 4])


def test_no_other_outward_url():
    """T-06-59: the only outward call is the refresh POST. Outside `uses:` lines, the only URLs
    are the refresh endpoint and the github.com repository prefix; nothing else downloads or
    posts."""
    text = pages_text()
    urls = set()
    for line in text.splitlines():
        if line.strip().removeprefix("- ").startswith("uses:"):
            continue
        urls |= set(URL.findall(line))
    assert urls == {REFRESH, "https://github.com/${{"}, urls
    assert "http://" not in text
    assert text.count("curl ") == 1 and "curl " in "\n".join(job("notify-decomphub"))
    for tool in ("wget", "Invoke-WebRequest", "Invoke-RestMethod", "urllib", "requests"):
        assert tool not in text, tool


# ---- match.yml: the base-vs-head match check (PIPE-08; D-06 to D-09, D-23; plan 07.2-08) ----

MATCH = PAGES.parent / "match.yml"
# The job runs only once the owner sets the repository variable, only as main's own workflow, and
# a labeled run only for the match-check label (D-06, D-09).
MATCH_GATE = ("if: vars.MATCH_CHECK_ENABLED == 'true' && github.ref == 'refs/heads/main' && "
              "(github.event_name == 'workflow_dispatch' || "
              "github.event.label.name == 'match-check')")  # fmt: skip
PR_NUMBER = "${{ github.event.pull_request.number || inputs.pr }}"
MATCH_ENV = ("PR_NUMBER: " + PR_NUMBER, "BASE_SHA: ${{ github.sha }}",
             "LABELED_HEAD: ${{ github.event.pull_request.head.sha }}",
             "IMAGE: reverseapoc-build:local", "VENV_VOLUME: reverseapoc-match-venv")  # fmt: skip
PATHS_STEP = ("List the changed paths; refuse any outside the src units, symbols.csv, docs/ and "
              "README.md")  # fmt: skip
UNITS_STEP = "Refuse a new, removed or linked unit"
PIN_STEP = "Refuse a head that moved after the label"
COMPILE_STEP = "Compile each touched unit at base and at head, then compare"
UNIT_PATTERN = r"'^src/(ufo2p|tacp)/[a-z0-9_]+\.c$'"
# D-07: the image, no network, the base tree and Watcom read-only, no game files, the uv venv
# the owner prepared, read-only (07.2 review WR-08: no container that compiles a pull request's
# C can change what a later run executes) and never synced (`--no-sync`); only the outputs are
# writable, under the runner's temp directory.
DOCKER_RUN = "docker run --rm --network none \\"
MOUNTS = ('-v "$GITHUB_WORKSPACE:/work:ro" \\', '-v "$RUNNER_TEMP/match:/work/build/match" \\',
          '-v "$REVERSEAPOC_WATCOM_DIR:/watcom:ro" \\', '-v "$VENV_VOLUME:/opt/venv:ro" \\',
          '-w /work "$@" < /dev/null')  # fmt: skip
HEAD_SRC = '-v "$GITHUB_WORKSPACE/head/src:/work/src:ro"'
IN_IMAGE = '"$IMAGE" uv run --frozen --offline --no-sync reverseapoc '
CC_FLAGS = "--cflags config/cflags.txt --watcom-dir /watcom --log build/match/cc.log"
COMPARE = (f'image {IN_IMAGE}compare-objects "build/match/base/$name.obj" '
           '"build/match/head/$name.obj" --base-config config --head-config head/config '
           '--exe "$exe" || status=1')  # fmt: skip


def match_lines() -> list[str]:
    """match.yml's lines without comment lines."""
    assert MATCH.is_file(), f"{MATCH} does not exist"
    text = MATCH.read_text(encoding="utf-8")
    return [line for line in text.splitlines() if not line.lstrip().startswith("#")]


def match_top(header: str) -> list[str]:
    lines = match_lines()
    assert header in lines, f"match.yml has no top-level {header!r}"
    return [line.strip() for line in block(lines[lines.index(header):], header) if line.strip()]


def match_job() -> list[str]:
    return [line.strip() for line in block(block(match_lines(), "jobs:"), "match:")
            if line.strip()]  # fmt: skip


def match_steps() -> list[list[str]]:
    """The stripped lines of each step, its leading `- ` dropped."""
    raw = [line for line in block(block(block(match_lines(), "jobs:"), "match:"), "steps:")
           if line.strip()]  # fmt: skip
    least = min(indent(line) for line in raw)
    steps: list[list[str]] = []
    for line in raw:
        if indent(line) == least and line.lstrip().startswith("- "):
            steps.append([])
        steps[-1].append(line.strip().removeprefix("- "))
    return steps


def match_step(name: str) -> list[str]:
    [step] = [s for s in match_steps() if s[0] == f"name: {name}"]
    return step


def script(step: list[str]) -> list[str]:
    """The lines of a step's `run: |` script."""
    return step[step.index("run: |") + 1:]


def test_match_triggers():
    """D-09: a label on a pull request (pull_request_target: main's workflow) or a dispatch
    naming the pull request; never a push or a plain pull_request, which would run the PR's own
    copy of the workflow."""
    lines = match_lines()
    on = block(lines[lines.index("on:"):], "on:")
    assert keys(on) == ["pull_request_target", "workflow_dispatch"]
    target = [line.strip() for line in block(on, "pull_request_target:") if line.strip()]
    assert target == ["types: [labeled]"]
    dispatch = [line.strip() for line in block(on, "workflow_dispatch:") if line.strip()]
    assert dispatch[:2] == ["inputs:", "pr:"]
    assert {"required: true", "type: number"} <= set(dispatch)
    assert not any(re.match(r"\s*(push|pull_request|schedule):", line) for line in lines)


def test_match_gates():
    """Off until the owner sets MATCH_CHECK_ENABLED; a labeled run needs the match-check label,
    and each new push needs it again (only `labeled` triggers). One check per pull request."""
    job = match_job()
    assert MATCH_GATE in job
    assert job.index(MATCH_GATE) < job.index("steps:"), "the gate is on the job, not a step"
    assert match_top("concurrency:") == [f"group: match-{PR_NUMBER}", "cancel-in-progress: true"]
    env = block(block(block(match_lines(), "jobs:"), "match:"), "env:")
    assert [line.strip() for line in env if line.strip()] == list(MATCH_ENV)


def test_match_permissions():
    """T-07.2-22: the job token reads the repository and nothing else; no secret is named; the
    job runs on the owner's self-hosted runner."""
    assert match_top("permissions:") == ["contents: read"]
    text = "\n".join(match_lines())
    assert text.count("permissions:") == 1
    assert re.search(r"\bwrite\b", text) is None
    assert "secrets." not in MATCH.read_text(encoding="utf-8")
    assert "runs-on: [self-hosted]" in match_job()


def test_match_runs_main_tools():
    """D-06: the first checkout is main's commit (its workflow and tools); the pull request head
    goes to head/ as data, without credentials, and nothing under head/ is ever run: every
    `uv run` runs main's reverseapoc inside the image, and no step changes into head/."""
    steps = match_steps()
    checkouts = [step for step in steps if "uses: actions/checkout@v7" in step]
    assert len(checkouts) == 2 and steps[0] is checkouts[0]
    base, head = checkouts
    assert "ref: ${{ github.sha }}" in base
    assert not any(line.startswith("path:") for line in base)
    assert f"ref: refs/pull/{PR_NUMBER}/head" in head and "path: head" in head
    assert all("persist-credentials: false" in step for step in checkouts)
    text = "\n".join(match_lines())
    assert "working-directory" not in text
    assert re.search(r"(^|[\s;&|(])(cd|pushd)\s", text, re.MULTILINE) is None
    assert re.search(r"(bash|sh|source|python3?|node|make|ninja|perl)\s+\S*head/", text) is None
    assert "./head" not in text and "python" not in text and "setup-uv" not in text
    uv_lines = [line for line in match_lines() if "uv run" in line]
    assert uv_lines and all(IN_IMAGE in line for line in uv_lines)


def test_match_pins_the_labeled_head():
    """A push after the label brings code nobody labeled: the labeled run checks that the head it
    checked out is the one the label event named, and fails otherwise."""
    pin = match_step(PIN_STEP)
    assert "if: github.event_name == 'pull_request_target'" in pin
    run = script(pin)
    moved = 'if [ "$(git -C head rev-parse HEAD)" != "$LABELED_HEAD" ]; then'
    assert moved in run
    assert run[run.index(moved) + 1].startswith('echo "::error::')
    assert run[run.index(moved) + 2] == "exit 1"


def test_match_compiles_in_the_image_offline():
    """D-07, D-08: one `docker run --rm --network none` helper with read-only mounts and no game
    files; each unit compiles at base and at head (head/src mounted over src/, so the base tree's
    cflags rule applies to the unit's own path) with main's `reverseapoc cc` and the base tree's
    config/cflags.txt, then main's compare-objects judges the pair; any failure fails the job."""
    text = MATCH.read_text(encoding="utf-8")
    assert text.count("docker run") == 1 and "docker compose" not in text
    assert "orig" not in text
    run = script(match_step(COMPILE_STEP))
    assert run[0] == "set -euo pipefail"
    assert ': "${REVERSEAPOC_WATCOM_DIR:?set it in the .env file of the runner, see docs/ci.md}"' \
        in run
    start = run.index(DOCKER_RUN)
    assert run[start + 1:start + 1 + len(MOUNTS)] == list(MOUNTS)
    ccs = [line for line in run if "reverseapoc cc " in line]
    assert len(ccs) == 2
    assert all(line.startswith("image ") and IN_IMAGE + "cc " in line and CC_FLAGS in line
               for line in ccs)  # fmt: skip
    base_cc, head_cc = ccs
    assert HEAD_SRC not in base_cc and '-o "build/match/base/$name.obj"' in base_cc
    assert HEAD_SRC in head_cc and '-o "build/match/head/$name.obj"' in head_cc
    assert [line for line in run if "compare-objects" in line] == [COMPARE]
    assert run[-1] == 'exit "$status"'


def test_match_never_writes_the_venv_volume():
    """07.2 review WR-08: the persistent venv volume is mounted read-only in every container
    the job starts, so a compile of hostile C cannot plant code that a later compare runs;
    the owner fills it in a separate step (docs/ci.md)."""
    text = MATCH.read_text(encoding="utf-8")
    mounts = re.findall(r'-v "\$VENV_VOLUME:[^"]*"', text)
    assert mounts == ['-v "$VENV_VOLUME:/opt/venv:ro"']
    assert "uv sync" not in text


def test_ci_doc_asks_the_owner_to_pin_checkout_by_sha():
    """WR-08: actions/checkout is a mutable tag; no commit SHA can be checked offline, so the
    owner pins it by full SHA as a setup step, before the runner is registered."""
    doc = (REPO_ROOT / "docs" / "ci.md").read_text(encoding="utf-8")
    setup = doc[doc.index("## Runner setup (owner only)"):doc.index("## Security model")]
    pin = setup.index("Pin `actions/checkout`")
    assert pin < setup.index("Register a runner for this repository only")
    assert "full commit SHA" in setup[pin:pin + 600]


def test_match_refuses_other_paths():
    """D-08, T-07.2-21: the paths the pull request changed since its merge base with main may be
    src/<exe>/<unit>.c units, the two symbols.csv files (a rename's new names, read as data) and
    the Markdown of docs/ and the root README.md; anything else (cflags, tools, config, headers,
    workflows, and 07.2 review WR-07: CLAUDE.md, .claude/ rules and skills, any Markdown a
    session reads as instructions) fails the job and goes to the owner."""
    run = script(match_step(PATHS_STEP))
    assert run[0] == "set -euo pipefail"
    # main's commit reaches head/'s repository from the local checkout, not over the network.
    fetch = 'git -C head fetch --quiet --no-tags "$GITHUB_WORKSPACE" HEAD'
    assert run[1:3] == [fetch, 'test "$(git -C head rev-parse FETCH_HEAD)" = "$BASE_SHA"']
    assert 'merge_base="$(git -C head merge-base "$BASE_SHA" HEAD)"' in run
    diff = ('git -C head diff --name-only --no-renames "$merge_base" HEAD '
            '> "$RUNNER_TEMP/changed.txt"')  # fmt: skip
    assert diff in run
    case = run[run.index('case "$path" in') + 1:run.index("esac")]
    assert case == ["docs/*.md|README.md) continue ;;",
                    "config/ufo2p/symbols.csv|config/tacp/symbols.csv) continue ;;"]  # fmt: skip
    assert not any(line.startswith("*.md)") for line in run)
    assert f"if printf '%s\\n' \"$path\" | grep -Eq {UNIT_PATTERN}; then" in run
    assert "refused=1" in run and run[-1] == '[ "$refused" -eq 0 ]'


def test_match_refuses_new_removed_and_linked_units():
    """A new unit is a new match (the owner's gate, D-08); a removed one cannot be compared; a
    symbolic link is never followed. 07.2 review WR-07: a pull request with no src unit to
    compare (only symbols.csv, only docs) fails, naming that nothing was compared, so a green
    result always means a compared unit."""
    run = script(match_step(UNITS_STEP))
    pick = f'grep -E {UNIT_PATTERN} "$RUNNER_TEMP/changed.txt" > "$RUNNER_TEMP/units.txt" || true'
    assert pick in run
    empty = 'if [ ! -s "$RUNNER_TEMP/units.txt" ]; then'
    assert run[run.index(pick) + 1] == empty
    assert run[run.index(empty) + 1] == ('echo "::error::no src unit changed, so nothing was '
                                         'compared: the owner checks this pull request"')
    assert run[run.index(empty) + 2] == "exit 1"
    assert 'if [ ! -f "$unit" ] || [ -L "$unit" ]; then' in run
    assert 'if [ ! -f "head/$unit" ] || [ -L "head/$unit" ]; then' in run
    assert run.count("exit 1") == 3
