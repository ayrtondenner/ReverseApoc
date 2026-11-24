---
title: Refuse a build of the shared image while a drive runs
created: 2026-11-23
area: toolchain
files: docker/compose.yaml, .claude/hooks (reverseapoc hook), docs/toolchain.md
source: run 20261120-codex (2026-11-20)
---

# A clone's build moved the drive's image tag

**Why.** During run 20261120-codex, `docker compose build` in a scratchpad clone re-tagged
`reverseapoc-build:local` (the compose image name is fixed, not per project). The image `.Id` went
from the drive's STARTED `79f99708...` to `48d709f2...` with the same config, most likely
BuildKit provenance changing the index digest, and the old digest was gone, so the tag could not be
put back. The drive was unaffected in substance (the image holds tools only) but its recorded
environment no longer matched the tag. Today only a memory note guards this.

**Do.** Add the guard where builds start: the reverseapoc hook (or a compose wrapper) refuses
`docker compose build` while build/driver/drive.lock is held, with a message pointing at
docs/toolchain.md. Test first if the guard is Python.

**Done when.** A build attempted during a drive is refused with a clear reason, and a build with no
drive running still works.

## Result (2026-11-23)

Done in the reverseapoc hook (`tools/reverseapoc/hooks.py`), test first (32 cases failed before the change). While a live
drive holds `build/driver/drive.lock` (the same live-root logic: cwd ancestors and `$CLAUDE_PROJECT_DIR`), every image
build or retag is refused from any cwd, a clone included, with its own reason: the shared `reverseapoc-build:local`
tag the drive recorded in STARTED would move; build after the drive exits (docs/toolchain.md).

- Refused (`_image_build`, `_compose_build`): `docker build`, `buildx`, `builder`, `image build`; `docker tag` or
  `image tag` naming `reverseapoc-build`; `docker compose` / `docker-compose` `build` and `watch`, and `run`, `up` or
  `create` with `--build`. An unlisted docker or compose option before the subcommand fails closed as a build, since it
  may take a value and hide the subcommand. The check runs in the drive guard's segment walk, so a build inside
  `bash -c`, `eval` or a `$(...)` is refused too (raised as `_ImageBuild`, which the nested-shell catch does not swallow).
- Still allowed during a drive, from a clone: `docker compose run --rm -T build ...`, `docker compose run --rm -T test`,
  `docker ps`, `docker images`, a `docker tag` of another image. With no live drive (stale lock or none) every build
  passes.
- docs/toolchain.md, the image section, says why (the 2026-11-20 incident, `79f99708…` to `48d709f2…`).

Tests (tests/test_hooks.py): `IMAGE_BUILDS` (16 commands, Bash and PowerShell) refused from the clone and from the
checkout (`test_drive_guard_refuses_an_image_build_from_any_cwd`, 32 cases), allowed with a stale drive and with none
(`test_drive_guard_allows_image_builds_without_a_live_drive`, 32), and
`test_drive_guard_allows_image_use_from_a_clone` (5).

Not covered: `docker commit`, `docker load`, `docker pull` or `docker import` can also move a tag (`load` takes it from
the tarball, so the command text does not show it).
