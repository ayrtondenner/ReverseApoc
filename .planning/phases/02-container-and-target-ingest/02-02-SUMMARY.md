---
phase: 02-container-and-target-ingest
plan: 02
subsystem: infra
tags: [docker, compose, read-only-mounts, gap-closure]
gap_closure: true
requires:
  - phase: 02-container-and-target-ingest
    provides: "02-01 compose services"
provides:
  - "third_party/ read-only at /work/third_party inside the container"
  - "Container-only tests asserting the protected paths are not writable"
key-files:
  created: [tests/test_hygiene.py]
  modified: [docker/compose.yaml, docker/README.md]
key-decisions:
  - "Keep /work/watcom as the sanctioned compiler path and overlay /work/third_party read-only"
requirements-completed: [ING-01]
coverage:
  - id: D1
    description: "compose mounts third_party read-only at its own in-repo path; every protected mount is :ro"
    requirement: ING-01
    verification:
      - kind: unit
        ref: "tests/test_hygiene.py::test_protected_dir_is_read_only_at_its_own_path_inside_the_repo_mount, ::test_every_mount_of_a_protected_dir_is_read_only"
        status: pass
    human_judgment: false
  - id: D2
    description: "Inside the container /work/orig, /work/watcom, /work/third_party(/watcom) are not writable"
    requirement: ING-01
    verification:
      - kind: integration
        ref: "docker compose run --rm test -> 90 passed incl. test_protected_paths_are_not_writable_in_the_container; test -w on 4 paths -> read-only"
        status: pass
    human_judgment: false
completed: 2026-10-19
status: complete
---

# Phase 2 Plan 02: Read-only third_party mount Summary

**The Watcom folder is no longer writable through the rw repo mount: `../third_party:/work/third_party:ro` overlays it, pinned by host and in-container tests.**

- Reproduced before the fix: `/work/third_party/watcom WRITABLE` (`test -w` in the container).
- After the fix (commit `fa9c1a0`): `/work/orig`, `/work/watcom`, `/work/third_party`, `/work/third_party/watcom` all `read-only`; container `90 passed`.
- TDD: `test_protected_dir_is_read_only_at_its_own_path_inside_the_repo_mount[third_party]` failed before, passes after.
