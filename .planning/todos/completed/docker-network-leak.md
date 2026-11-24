---
title: Compose networks from clones fill Docker's address pools
created: 2026-11-23
area: toolchain
files: docker/compose.yaml, docs/toolchain.md
source: 2026-11-21 records correction in a scratchpad clone
---

# Every clone leaves a network

**Why.** Each `docker compose run` from a new clone directory creates a `<dir>_default` network
(compose project name = directory). Clones made for drives, reviews and proofs (`cn*`, `r-*`,
`proof*`, `agent-*`, ...) left about 29 such networks. On 2026-11-21 a new clone's
`docker compose run` failed with "all predefined address pools have been fully subnetted"; an
agent worked around it with `-p <stale project>`, and the owner approved `docker network prune`
(32 networks down to 3).

**Do.** Pick the smallest fix: a fixed compose project name for the build/test services (so every
clone reuses one network), `--rm` cleanup of the network, or a documented prune step after clone
work. Mind that the checkout's drive also uses compose; do not change what a running drive sees.

**Done when.** Running the container suite from several clones leaves no extra networks behind,
or docs/toolchain.md names the cleanup step and when to run it.

## Resolution (2026-11-23)

Owner ruling (2026-11-23): docs only, no compose or driver change. Options were a documented
prune step after clone work, a fixed `-p` for clones, or a `name:` in compose.yaml. Chosen: the
documented prune step.

- docs/toolchain.md "Clone work": every clone is its own compose project, so its first
  `docker compose run` leaves a `<dir>_default` network and `<dir>_uv-venv`/`<dir>_uv-cache`
  volumes; run `docker compose down -v` in the clone when its work is done, then delete it;
  `docker network prune` only with the owner's OK.
- Why no fixed name: the driver's container cleanup filters on the directory-derived project
  (`driver.compose_project`), so a shared project would let a drive's cleanup remove a clone's
  containers, and clones would share one uv-venv.
- No code change, so no test.
