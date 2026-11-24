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
