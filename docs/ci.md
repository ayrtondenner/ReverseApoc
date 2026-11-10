# CI: the match check

`.github/workflows/match.yml` is the base-vs-head match check (999.11, PIPE-08, decisions D-06 to
D-09 and D-23 of phase 07.2). It lets a contributor's pull request prove that it changed no byte
of any matched object, without the owner running the gate by hand. It ships disabled. The owner
registers the runner and turns it on as described below. Agents never register, configure or
start the runner (D-09).

The other workflows are unchanged: `ci.yml` runs the host tests and ruff on GitHub's hosted
runners, and `pages.yml` publishes the progress page.

## What it proves, and what it does not

For every `src/<exe>/<unit>.c` the pull request touches, the job compiles the unit twice with
main's tools and main's `config/cflags.txt`: once from main's tree and once from the pull
request's. Then main's `reverseapoc compare-objects` compares the two objects:

- every segment's name, class, length and bytes;
- every relocation's place, size, mode, location, frame method, target and displacement;
- every public's segment and offset.

Names are not compared as text. An external or public name is first resolved, through its own
tree's `config/<exe>/functions.csv` and `symbols.csv`, to the original address it stands for.
So a rename that comes with its `symbols.csv` row compares equal, and so does a change to
comments only (the object's source path and timestamp records are not read). Any changed code
byte, retargeted relocation or moved public fails. A name neither tree knows, such as a runtime
external like `__CHK`, compares as text. The report names the first difference by segment,
offset and kind. It never prints a byte value, so no game byte reaches a public log.

It proves one thing: the pull request changed no byte of any matched object. It does not land
anything, and it is not the matching gate. A new match, a new unit, a flag change or anything
else still goes through the owner's gate on the owner's machine (D-08). A pull request that
touches no `src/` unit (only a `symbols.csv`, only docs) compares nothing, so the job fails and
says so ("nothing was compared: the owner checks this pull request"); a green result always
means at least one unit was compiled and compared. A `symbols.csv` row that renames a name an
untouched unit uses is not compiled against that unit: whether the C still links under the new
names is the owner's gate's job.

Exit codes of `compare-objects`: 0 the objects match, 1 they differ, 2 an object or a config tree
could not be read or judged. The job fails on 1 and 2, and on any compile failure.

## What a pull request may change

The job lists the paths the pull request changed since its merge base with main, and fails on
any path outside this list:

- `src/ufo2p/<unit>.c` and `src/tacp/<unit>.c`, the units it compiles;
- `config/ufo2p/symbols.csv` and `config/tacp/symbols.csv`, the new names of a rename (read as
  data, names and addresses only);
- Markdown under `docs/` and the root `README.md`.

Cflags, tools, other config, headers under `include/`, workflows and every other Markdown file
need the owner: `CLAUDE.md`, the rules and skills under `.claude/` and any other instruction
file are read into agent sessions, so they steer the agents. A unit that is new (a new match),
removed, or a symbolic link fails too, and so does a pull request with no unit to compare.

## Running it

A maintainer reads the pull request first, then adds the label `match-check`. The run starts on
the label. A push after the label does not start a new run, and a run whose head moved after the
label fails, so each new push needs the label removed and added again. Only people with triage
or write access to the repository can add labels.

The owner can also run it from main for a pull request number:

```sh
gh workflow run "Match check" -f pr=123
```

## Runner setup (owner only)

The job runs on a self-hosted runner, inside the existing ReverseApoc Docker image, because the
Watcom compiler is proprietary and can never be on a hosted runner (see `docs/legal.md`). Set it
up once:

1. Pick a Linux x86-64 machine (or a VM, or a separate user account) with Docker, and put no
   game files on it: never place `orig/` on the runner, and never mount it. The job does not
   need the game; it compares two compiles with each other.
2. Register a runner for this repository only: GitHub, repository Settings, Actions, Runners,
   New self-hosted runner. An ephemeral just-in-time runner is preferred: it takes one job and
   is removed, so nothing a job leaves behind meets the next one. Run the runner service as uid
   1000, the image's `dev` user, so the container can write its objects into the job's temp
   directory. The default `self-hosted` label is the one the workflow asks for.
3. In repository Settings, Actions, General, require approval for fork pull request workflows
   from outside contributors. A fork can edit `ci.yml` in its own pull request, and that copy
   runs on `pull_request`; approval keeps a stranger's workflow from reaching the self-hosted
   runner. Never approve a run of a pull request that edits `.github/workflows/`.
4. On the runner machine, in a checkout of main, build the image (`docker compose build`, which
   tags `reverseapoc-build:local`) and install Watcom (`uv run reverseapoc install-watcom`, see
   `docs/toolchain.md`), which gives `third_party/watcom/`.
5. Tell the runner where Watcom is: add `REVERSEAPOC_WATCOM_DIR=<absolute path to
   third_party/watcom>` to the `.env` file in the runner application's directory. The runner
   loads it into every job. The job mounts that directory read-only at `/watcom`.
6. Prepare the uv environment volume, once and again after every dependency change on main.
   The job runs `uv run --frozen --offline` with no network, so the venv must already be in
   sync. From the same checkout of main:

   ```sh
   docker run --rm -v "$PWD:/work" -v reverseapoc-match-venv:/opt/venv -w /work \
     reverseapoc-build:local uv sync --locked
   ```

   The checkout must be mounted at `/work`, where the job mounts its own checkout of main.
7. Create the label: `gh label create match-check --description "run the match check"`.
8. Turn the check on: `gh variable set MATCH_CHECK_ENABLED --body true` (repository Settings,
   Secrets and variables, Actions, Variables).

To turn it off, set `MATCH_CHECK_ENABLED` to anything but `true` (the job is then skipped), or
disable the workflow: `gh workflow disable "Match check"`.

## Security model

Running a stranger's pull request on the owner's machine is the risk. GitHub's own guidance
names both halves of it, in "Security hardening for GitHub Actions" (docs.github.com, the secure
use reference): avoid `pull_request_target` with untrusted pull requests or code content, and
self-hosted runners should almost never be used for public repositories; keep the
`GITHUB_TOKEN` minimal and prefer ephemeral just-in-time runners. The danger GitHub describes is
a privileged workflow that checks out a pull request and then builds or runs its code ("pwn
requests", GitHub Security Lab). The design stays within that guidance as follows.

- **main's workflow and tools.** `pull_request_target` runs the copy of `match.yml` on the base
  branch, never the pull request's copy, and the job is skipped unless it runs as main's
  workflow (`github.ref` is `refs/heads/main`, which also skips a dispatch from another branch).
  The first checkout is main's commit; every tool the job runs comes from it.
- **The pull request is data.** Its head is checked out into `head/` and nothing there is
  executed: no script, no `uv run`, no build file, no change of directory into it. Its C is
  only read by the Watcom compiler, and the resulting object is only read by main's
  `compare-objects`. Its `config/` is read for names only.
- **No credentials, no secrets.** Every checkout sets `persist-credentials: false`, so the token
  never lands in `.git/config`. The workflow's token has `contents: read` and nothing else, and
  the workflow names no repository secret, so a pull request has nothing to steal.
- **A sealed compile.** Every compile and compare runs in `docker run --rm --network none` on the
  ReverseApoc image. Main's tree and Watcom are mounted read-only, the pull request's `src/` is
  mounted read-only over `src/` for the head compile, and only the job's temp directory for the
  objects and the prepared venv volume are writable. No game file is mounted or present.
- **Narrow input.** Only units, the two `symbols.csv` files, Markdown under `docs/` and the
  root `README.md` may change; anything else fails before a compile. New, removed and linked
  units fail, and so does a pull request with no unit to compare.
- **A human in front.** It ships disabled (the repository variable), a maintainer labels each
  run after reading the pull request, and a push after the label needs a new label.

What is accepted: the Watcom compiler reads whatever files the pull request's C names with
`#include`. Inside the container the only files are the public checkout, the image and Watcom,
all read-only, so the worst a crafted include does is quote a few lines of a Watcom header into
the public job log. There is no game file, no secret and no network to reach.

Agents never register, configure or start the runner, and never set the variable or the label
(D-09). The owner does every step of the runner setup above.
