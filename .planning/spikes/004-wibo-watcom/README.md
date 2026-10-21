---
spike: 004
idea: compiler-identification
name: wibo-watcom
type: standard
validates: "Given wibo 1.2.0 in the reverseapoc-build image and the read-only third_party/watcom trees, when each version's BINNT/WCC386.EXE compiles a C89 probe, then 10.5 (with the decoded BINW), 10.6 and 11.0 produce objects whose normalized SHA-1 equals the native host compile"
verdict: VALIDATED
related: []
tags: [watcom, wibo, compiler, d-01, d-03]
---

# Spike 004: wibo 1.2.0 runs wcc386 for 10.5, 10.6 and 11.0 in Docker

This is the spike named in the Phase 4 roadmap entry ("wibo 1.2.0 runs wcc386.exe for each
version in Docker"). Its results are the D-03 cross-check of plan 04-11.

## What This Validates

Given wibo 1.2.0 (`ghcr.io/decompals/wibo:1.2.0`, copied to `/usr/local/bin/wibo` in the
`reverseapoc-build` image) and the owner's Watcom trees mounted read-only, we check that:

- each version's `BINNT/WCC386.EXE` runs under wibo and compiles a C89 source;
- 10.5 runs with the `BINW/WCC386.EXE` that `uv run reverseapoc install-watcom 10.5` decodes
  from `DISKIMGS/DISK02/PCK00017.1` + `DISKIMGS/DISK03/PCK00017.2` (D-01; the CD's own BINW file
  is a damaged 65,536-byte stub);
- the object compiled under wibo equals the object compiled natively on the Windows host after
  normalization (D-03). A difference would be a wibo bug, not codegen.

## Research

Restated from 04-RESEARCH.md "Spike results" (run 2026-10-21, read-only, scratch output only):

| Version | Under wibo 1.2.0 (container) | Native on Windows host | Banner (first line) |
|---|---|---|---|
| 10.5 (CD stub) | `Loader read error`, rc 3 | not tried (same stub) | none |
| 10.5 (decoded BINW) | compiles, rc 0 | compiles, rc 0 | `WATCOM C32 Optimizing Compiler  Version 10.5` |
| 10.6 | compiles, rc 0, ~43 ms per compile | compiles, rc 0, ~49 ms | `WATCOM C32 Optimizing Compiler  Version 10.6` |
| 11.0 | compiles, rc 0, ~88 ms per compile | compiles, rc 0 | `Watcom C32 Optimizing Compiler  Version 11.0` |
| 11.0 `BINW/WCC386.EXE` run directly | `Failed to load PE image` (expected: not a PE) | n/a | n/a |

Facts the research established:

1. **10.x loader.** The 10.x `BINNT/WCC386.EXE` is a 9,216-byte Win32 loader. Under
   `WIBO_DEBUG=1` it calls `GetModuleFileNameA` and then opens `..\BINW\WCC386.EXE` relative to
   its own path. PATH, `WATCOM`, DOS4GW and W32RUN are not needed; a tree needs `BINNT/`,
   `BINW/` and `H/`. 11.0's BINNT compiler is native (`WCC386.EXE` + `WCCD386.DLL`). The 10.6
   BINW compiler is an LE program; the decoded 10.5 one is an LX image (plan 04-03).
2. **Paths.** wibo maps `Z:\` to `/` and resolves relative paths against the cwd. Forward slashes
   break the command line (Watcom reads `/` as an option switch).
3. **Headers.** Without `-i=` or `INCLUDE`, `#include <stdio.h>` fails. `-i=<tree>\H` works;
   `WATCOM=<tree>` alone does not.
4. **Banner.** `-zq` hides it; a run with no arguments prints it and exits non-zero.
5. **Exit codes.** 0 on success; 10.6 returns 1 or 2 and 11.0 returns 8 on a compile error.
6. **Error file.** On errors the compiler writes `<stem>.err` into the cwd unless `-fr=` is given.
7. **Environment.** `WCC386=-3r` in the environment changes codegen on 10.6 and 11.0.
8. **Target.** The NT-hosted compilers define `__NT__` by default; `-bt=dos` gives `__DOS__`.
9. **Objects.** Raw objects differ between host and container: THEADR holds the absolute source
   path and COMENT class 0xE9 holds absolute header paths and DOS timestamps. The SHA-1 over all
   other records was equal native vs wibo for 10.6 and 11.0.

The wrapper (`uv run reverseapoc cc`, plans 04-01/04-04) encodes 2, 3, 6, 7 and 8: it passes
`-zq -zld -bt=dos -fr=` and `-i=<tree>\H`, rewrites paths to relative backslash paths, and
scrubs the environment. It logs the raw and the normalized SHA-1 of every object.

## How to Run

From the repo root, after `uv run reverseapoc install-watcom 10.5 --force` (older installs hold
the stub) and with `build/d03/cflags-<v>.txt` holding `*  wcc386@<v>  -5r -s` (the comparison
flag set, not the game's flags):

```
uv run reverseapoc cc probe/cg_basic.c -o build/d03/native-<v>.obj --cflags build/d03/cflags-<v>.txt
(cd docker && docker compose run --rm build bash -lc "uv sync --locked && uv run reverseapoc cc probe/cg_basic.c -o build/d03/wibo-<v>.obj --cflags build/d03/cflags-<v>.txt")
```

The comparison is logged in `build/gate/04-native-vs-wibo.txt` (gitignored). The log and this
record hold SHA-1s and banners only, never compiler or object bytes.

## Results

Run 2026-10-21 on the main checkout (plan 04-11). `check-watcom 10.5 10.6 11.0` reported every
key file OK first (10.5: 8 ok, 10.6: 8 ok, 11.0: 10 ok). The D-03 lines, as logged:

```
10.5  native sha1 a8959f459c510fe3214c3704bd0cb5b13af582e9 normalized f3f0be4fdd01a1eaf7e91c7cf11f913a6f6783f2  wibo sha1 1c3ad3b57a332f31dd1d488357fd354e5f12571b normalized f3f0be4fdd01a1eaf7e91c7cf11f913a6f6783f2  normalized equal
  native banner: WATCOM C32 Optimizing Compiler  Version 10.5
  wibo banner:   WATCOM C32 Optimizing Compiler  Version 10.5
10.6  native sha1 a8959f459c510fe3214c3704bd0cb5b13af582e9 normalized f3f0be4fdd01a1eaf7e91c7cf11f913a6f6783f2  wibo sha1 1c3ad3b57a332f31dd1d488357fd354e5f12571b normalized f3f0be4fdd01a1eaf7e91c7cf11f913a6f6783f2  normalized equal
  native banner: WATCOM C32 Optimizing Compiler  Version 10.6
  wibo banner:   WATCOM C32 Optimizing Compiler  Version 10.6
11.0  native sha1 538da4b77b57e90c772bb0dd01c80db04e31bc7e normalized 419decf88073e026a0ebfff588ccc3ff1bd5f03c  wibo sha1 7f2f562574abdb9695b6aa687711af0f863cba84 normalized 419decf88073e026a0ebfff588ccc3ff1bd5f03c  normalized equal
  native banner: Watcom C32 Optimizing Compiler  Version 11.0
  wibo banner:   Watcom C32 Optimizing Compiler  Version 11.0
D-03: normalized equal for 10.5, 10.6, 11.0
```

- Raw SHA-1s differ between host and container for every version, as fact 9 predicts. The
  normalized SHA-1s are equal for every version.
- 10.5 and 10.6 give the same object at `-5r -s`, raw and normalized, on both backends. The full
  calibration (`uv run reverseapoc probe calibrate`) finds 10.5 and 10.6 byte-identical on the
  probe in all ten flag sets.

## Verdict

**VALIDATED.** wibo 1.2.0 runs `wcc386` for 10.5 (with the decoded BINW), 10.6 and 11.0 from the
read-only trees, and the wibo objects equal the native host objects after normalization for all
three versions. No wibo bug was seen.
