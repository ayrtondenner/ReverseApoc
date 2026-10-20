# Learnings journal

A dated, append-only log of what we learned while working: surprises, dead ends, things that worked. Newest entry first. Keep entries short and searchable; once a learning becomes a verified rule, move it to [matching.md](matching.md) (codegen), [toolchain.md](toolchain.md) (tools) or [coding-style.md](coding-style.md) (source rules) and leave a one-line pointer here.

Entry format:

```
## YYYY-MM-DD: short title

- What happened or what we found, with the function address, EXE or tool involved.
- Why it matters and what we will do differently.
```

## 2026-10-20: refactors need their own review (PR #1, Python tooling)

- **Flattening changed behaviour twice.** In the `code-simplifier` refactor of the ISO9660 walk, a lazy generator became a list, so `find()` failed on a bad record that came after the match. In the `fetch_media` refactor, a Content-Length refusal started deleting an older `.part` file. Both were caught by a `/code-review` run after the refactor, not by the existing tests, and both are now pinned by tests.
- **Characterize first, then prove the tests bite.** Before moving code, add tests for the behaviour being moved, then break the code briefly to watch each one fail. Two tests written this way (the associated-file skip and directory-named errors) had no coverage before.
- **Named offsets read better than comments.** The bare `25`, `32`, `33` and `34` in the ISO reader became constants named after their ECMA-119 fields. The rules now live in [coding-style.md](coding-style.md#python-tooling).

## 2026-10-19: what is actually on the Watcom CDs

- **BINNT is a stub on 10.5 and 10.6.** `BINNT/WCC386.EXE` is a 9,216-byte Win32 loader that tells you to put `BINW` in your path first; the real compiler is the LE program `BINW/WCC386.EXE` (567,698 bytes in 10.6). Running 10.x under wibo needs `BINW` next to `BINNT` (to be confirmed in Phase 4). 11.0 and later ship a native Win32 `BINNT`.
- **The 10.5 disc has a damaged compiler.** `BINW/WCC386.EXE` is a 65,536-byte stub; the real 567,558-byte binary is wpack-packed in `DISKIMGS/DISK02/PCK00017.1` + `DISK03/PCK00017.2`. `check-watcom` reports it as KNOWN BAD; decoding is Phase 4 work.
- **The 11.0b dump has a damaged directory sector (353)** covering the 3-file `SAMPLES/WIN/DATACTL/WIN16` folder. 7-Zip cannot open the image; our reader installs it and skips that folder (manifest `skip_dirs`). The compiler, headers and libraries are fine.
- **The archive.org and WinWorld copies are byte-identical** (10.5, 10.6, 11.0), so the collection item's SHA256SUMS and cross-verification notes corroborate our SHA-1s in `config/watcom.toml`.

## 2026-10-19: kickoff research outcome

- **Targets are clean and fixed.** Steam and GOG ship byte-identical UFO2P.EXE (`ufo24`) and TACP.EXE (`tac4`): Watcom LE executables bound with DOS/4GW Professional, two objects each, no debug info, almost certainly C rather than C++. OpenApoc expects a different UFO2P build (CRC32 `0x4749ffc1` vs our `0xDBD3B41D`): resolved the same day, see below.
- **The compiler hypothesis is Watcom 10.6 (10.5 equivalent).** The runtime banner excludes only 10.0/10.0a; codegen idioms point away from Open Watcom, which cannot match. 11.0 is told apart by a codegen probe. Phase 4 settles it with owner-supplied compilers.
- **objdiff cannot read Watcom OMF.** Theme Hospital's GPLv3 `omf2elf.py` is the bridge, which is why `tools/` is GPLv3. Whether objdiff diffs converted objects cleanly decides hybrid vs fallback in Phase 5.
- **Pipeline is hybrid.** Our own oracle (KKND's LE reader and in-place splice, Theme Hospital's build pattern, wibo + Docker) plus decomp.wtf's fork mode as the agent layer. decomp.wtf was archived and decomp.dev closed in October 2026, both citing AI-driven behaviour, so we state AI use openly and self-host progress.
- **The driver, not the agent, owns verification.** Successful AI decomps (Lewis, Macabeus) stood on deterministic verifiers; agents that could judge themselves claimed false matches and edited hashes. Hence a 3-5 attempt cap with re-queue, hooks on hashes and build scripts, and a driver that re-checks bytes before every commit.

## 2026-10-19: the OpenApoc CRC mismatch is two builds on the same disc

- **What we found.** OpenApoc reads `ufo2p.exe` from the CD image, and the Steam `cd.iso` / GOG `XCOM.BIN` carry the v1.00 CD build (UFO2P.EXE 1,702,206 bytes, CRC32 `0x4749FFC1`; TACP.EXE 3,170,298 bytes). The installed `XCOMA/` tree holds a later build (1,705,790 / 3,161,594 bytes). Verified with pycdlib on both disc images; SMKP.EXE and XCOMAPOC.EXE are identical in both.
- **Why it matters.** OpenApoc's offsets and `FUN_` addresses only apply to the CD build. We keep the installed build as primary target, record the CD build in `config/targets.toml`, and treat the build-to-build diff as free matching evidence later. Patch level of the installed build is unknown; a build-to-build diff after Phase 5 may date it.
