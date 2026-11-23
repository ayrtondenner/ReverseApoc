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
