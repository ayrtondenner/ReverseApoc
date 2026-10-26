""".github/workflows/pages.yml (RPT-02..RPT-05, D-27, D-28, D-30): GitHub Pages is built from the
committed CSVs by tools/progress.py and deployed by GitHub's own actions, the recomp.fyi report
is uploaded as one combined artifact, and the DecompHub refresh POST runs only when the owner
turns it on. Pinned by text, like tests/test_hygiene.py: no YAML library. Nothing here touches
the network."""

from __future__ import annotations

import re

from conftest import REPO_ROOT

PAGES = REPO_ROOT / ".github" / "workflows" / "pages.yml"
GITIGNORE = REPO_ROOT / ".gitignore"

# D-27: the inputs of tools/progress.py and the workflow itself.
PATHS = ("config/*/status.csv", "config/*/functions.csv", "config/*/units.csv",
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
    assert [w.name for w in workflows] == ["ci.yml", "pages.yml"]
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
