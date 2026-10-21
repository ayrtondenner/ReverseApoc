# Learnings journal

A dated, append-only log of what we learned while working: surprises, dead ends, things that worked. Newest entry first. Keep entries short and searchable; once a learning becomes a verified rule, move it to [matching.md](matching.md) (codegen), [toolchain.md](toolchain.md) (tools) or [coding-style.md](coding-style.md) (source rules) and leave a one-line pointer here.

Entry format:

```
## YYYY-MM-DD: short title

- What happened or what we found, with the function address, EXE or tool involved.
- Why it matters and what we will do differently.
```

## 2026-10-21: running the 1990s compilers (Phase 4, plans 04-01..04-06, 04-11)

- **wpack needs Watcom's own qsort.** The 10.5 compiler's archive (PCK00017.1 + .2) builds its Shannon-Fano code table with the Watcom C library's qsort (shell sort below 16 items, Bentley-McIlroy partition above). A stable sort assigns tied symbols in another order and decodes garbage ("a match runs past the member length"). The 10.5 header is 12 bytes (the first member's `disk_addr` is 12); Open Watcom v2's 16-byte variant is refused. Format: [research/wpack-format.md](research/wpack-format.md).
- **The decoded 10.5 compiler is an LX image, not LE.** `BINW/WCC386.EXE` (567,558 bytes) has `LX\0\0` at `e_lfanew`; the 10.6 one is LE. `config/watcom.toml`'s 10.5 and 10.6 BINNT notes still say "the real LE compiler"; that string is stale for 10.5, and the manifest is protected, so it stays until the owner edits it.
- **The 10.x BINNT loader finds BINW by itself.** It reads its own path (`GetModuleFileNameA`) and opens `..\BINW\WCC386.EXE`; PATH, `WATCOM` and DOS4GW are not needed. This replaces the "to be confirmed in Phase 4" in the 2026-10-19 entry below. Rule: [toolchain.md "What is on the discs"](toolchain.md#what-is-on-the-discs).
- **The compiler reads options from the environment.** `WCC386=-3r` turned `and eax,0FFh` into `movzx` on 10.6 and 11.0; `INCLUDE` changes the header search, and compose loads `.env` into the container. The wrapper builds the child environment from scratch. Rule: [matching.md "Pitfalls"](matching.md#pitfalls).
- **NT-hosted compilers target NT.** Without `-bt=dos`, `__NT__` is defined and the headers and default libraries change. The wrapper always passes `-bt=dos`.
- **Objects carry absolute paths, so compare the normalized hash.** THEADR holds the absolute source path and COMENT class 0xE9 absolute header paths and timestamps, even for a relative command line. Raw SHA-1s never agree across host and container; the SHA-1 without those records was equal native vs wibo for 10.5, 10.6 and 11.0 (D-03, spike 004). Rule: [toolchain.md "wibo"](toolchain.md#wibo).

## 2026-10-21: what the game-code scan says, and what it cannot say (Phase 4, plans 04-08..04-11)

- **mosura's register claim did not reproduce.** On our clean-room counted loop, 10.6 kept the bound in `ecx` and 11.0 in `ebx`, the opposite of the published table. Register choice is construct-specific; every idiom is now calibrated per version and flag set from our own probe. Rule: [matching.md "Known idioms"](matching.md#known-idioms).
- **The research's adjacent `B9 n 00 00 00 F3 A5` pattern could not see a `-4` struct copy.** The probe's own `-4r` copy has register moves between `mov ecx,5` and `rep movsd`, so the research's "0 hits, so no `-4`" never ruled `-4` out. The corrected counter, and then a sized count of every rep copy (04-10 review), found 5-dword rep copies in both EXEs (UFO2P 2 plus about 2 the recogniser skips, TACP 6 plus 2) and no unrolled 5-dword run. Only the 5-dword size separates `-4` from `-5`. Result: `-4r`, recorded in [toolchain.md "Flags"](toolchain.md#flags).
- **The switch-order counter had a defect, and switch order is not a version signal.** A compare that turned the direction dropped the chain before it, and chains crossed function boundaries; that made 11.0 `-ox` look descending. Fixed (04-08 review): every cell except `-oneatx` (none) has one ascending chain on both versions. The compare forms still cover only `eax`/`al`.
- **"No 11.0, no `-4r`" did not hold.** With the corrected counters, 11.0 `-4r` stays consistent with both EXEs, and so do 10.5/10.6 at `-4r` and `-5r`. 10.5 and 10.6 are byte-identical on all ten probe flag sets. The decisive idioms leave 10.6 and 11.0 tied at `-4r`; the first Phase 5 matches decide. Recorded as a tie in [toolchain.md "Result"](toolchain.md#result).
- **Stack checks are off for most code.** 40 (UFO2P) and 32 (TACP) `push imm32; call __CHK` sites sit in two 64 KiB blocks. A throwaway count (not a committed command) found at least 714 / 801 near-call targets in non-library code that two or more call sites reach, so `-s` is the default and the `__CHK` functions are exceptions for per-glob rules.
- **Library stubs fake the C++ runtime.** At a 16-byte threshold, CLIB's 18-byte `noefgfmt`/`nomem` stubs match the C++ `__wcpp_` undefined-member stubs, and C++ `fatalerr` matches the head of CLIB's `__fatal_runtime_error_`. Only exclusive, consistent C++ matches count; none remain, and `cppscan` says `C (wcc386): ...` for both EXEs. Rule: [matching.md "Pitfalls"](matching.md#pitfalls).

## 2026-10-20: ninja quotes $in, nothing else (Phase 3 review WR-05, WR-06)

- **ninja already shell-quotes `$in` and `$out`** (single quotes on POSIX, double quotes on Windows only where needed), so quoting them in a rule double-quotes them. `configure.py` keeps `parse-le $in` unquoted, and a test pins the rule line.
- **Literal text in a rule command reaches /bin/sh or CreateProcess as written**, so `configure.py` accepts only letters, digits and `. _ - / :` in the `--orig` path it writes. ninja 1.11.1 has no escape for `|`, LF or CR in a build path, so `configure.py` refuses such executable names with an error instead of writing a broken `build.ninja`.

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

- **What we found.** OpenApoc reads `ufo2p.exe` from the CD image, and the Steam `cd.iso` / GOG `XCOM.BIN` carry the v1.00 CD build (UFO2P.EXE 1,702,206 bytes, CRC32 `0x4749FFC1`; TACP.EXE 3,170,298 bytes). The installed `XCOMA/` tree holds a second build (1,705,790 / 3,161,594 bytes) that is also on the disc, as `XCOM3/UFOEXE/UFO2P4.EXE` and `XCOM3/TACEXE/TACP4.EXE` (byte-identical; trailer spike 003, 2026-10-20), so it is not a store patch. Verified with pycdlib on both disc images; SMKP.EXE and XCOMAPOC.EXE are identical in both.
- **Why it matters.** OpenApoc's offsets and `FUN_` addresses only apply to the CD build. We keep the installed build as primary target, record the CD build in `config/targets.toml`, and treat the build-to-build diff as free matching evidence later. Which build is newer is unknown; a build-to-build diff after Phase 5 may tell.
