---
title: Refuse the other commands that can move the drive's image tag
created: 2026-11-24
area: hooks
files: tools/reverseapoc/hooks.py (the image-build guard), tests/test_hooks.py, docs/toolchain.md
source: review of todo image-build-during-drive (hook agent, 2026-11-23); owner ruling 2026-11-24
---

# Builds are not the only way to retag

**Why.** Since 06ae5fcf the hook refuses image builds and `docker tag ... reverseapoc-build`
while a drive holds its lock (completed/image-build-during-drive.md). `docker commit`, `docker
load`, `docker pull` and `docker import` can also move `reverseapoc-build:local`, which the
running drive recorded in STARTED. With `docker load`, the tag comes from the tarball, so the
command text never shows it. On 2026-11-24 the owner ruled that these should be refused too.

**Do.** Test first: while a live drive lock is held, refuse from any cwd `docker commit` and
`docker import` with a target naming `reverseapoc-build`, `docker pull reverseapoc-build...`,
and every `docker load` or `docker image load` (the tag cannot be checked). With no drive, each
passes. Add a line to the image note in docs/toolchain.md.

**Done when.** The four forms are refused during a drive and pass without one, and tests pin both.

## Result (2026-11-24)

Owner ruling (2026-11-24): refuse during a drive, from any cwd, `docker commit`/`docker container commit` and
`docker import`/`docker image import` with a target naming reverseapoc-build, `docker pull`/`docker image pull`
naming reverseapoc-build, and every `docker load`/`docker image load`. With no drive, all of them pass.

Done in `tools/reverseapoc/hooks.py` (`_image_build`), test first (26 cases failed before the change). The
subcommand may sit under `image` or `container` (`_DOCKER_GROUPS`); `commit`, `import` and `pull` join `tag` in
`_IMAGE_RETAGS` (refused when any word after them names `reverseapoc-build`, so committing the build container
under that name is refused too), and `load` is refused in every form, its tag being in the tarball. The check
runs where the build check runs, so `bash -c`, `cd <clone> &&` and PowerShell `& docker.exe` are covered. The
denial now says "image build or retag" and names the six commands. docs/toolchain.md, the image note, has a line
on them.

Tests (tests/test_hooks.py): `IMAGE_RETAGS` (13 commands, Bash and PowerShell) refused from a clone and from the
checkout (`test_drive_guard_refuses_other_retags_from_any_cwd`, 26), allowed with a stale drive and with none
(`test_drive_guard_allows_other_retags_without_a_live_drive`, 26), and
`test_drive_guard_allows_retags_of_other_images_from_a_clone` (5).

Security review follow-up (2026-11-24, asked by the orchestrator): a target behind shell expansion never showed
`reverseapoc-build`, so it passed. Now a tag, commit, import or pull argument, or the docker subcommand itself,
that holds `$`, a backtick, `%` or a leading `~` fails closed; and `docker compose pull` (also `docker-compose
pull`) and `run`/`up`/`create` with `--pull` (any value) join the compose build rule. `HIDDEN_RETAGS` (13) is
refused from both cwds (26) and passes with a stale drive and with none (26).

Not covered (no ruling): `docker rmi`/`docker image rm reverseapoc-build:local`, which
would remove the tag rather than move it.
