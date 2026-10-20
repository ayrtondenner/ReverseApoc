---
spike: 003
idea: le-round-trip-facts
name: trailer
type: standard
validates: "Given the 27 bytes after the last LE page in UFO2P and TACP (starting 64 00 9B FF; SMKP has none), when checksum/CRC hypotheses over the file or the pages, an installer/patch stamp and a DOS/4GW bind record are tested and the CD v1.00 build is compared, then we know what the trailer is, or that it stays opaque"
verdict: PARTIAL
related: [001, 002]
tags: [le, trailer, dos4gw, cd-build, d-10]
---

# Spike 003: The 27-byte trailer (D-10)

This is "the 27-byte trailer spike" that plan 03-05 Task 2 consumes.

## What This Validates

Given the 27 bytes after the last LE page in UFO2P.EXE and TACP.EXE (they start `64 00 9B FF`;
SMKP.EXE has none), we test four hypotheses and compare with the CD v1.00 build:

- a checksum or CRC over the file or the pages;
- an installer or patch stamp;
- a DOS/4GW bind record.

The aim is to learn what the trailer is, within a time box of about 1 hour. **Whatever the
verdict, the rebuild carries the trailer unchanged as its own region and nothing regenerates
it.**

## Research

The quick web check found no format description of DOS/4GW Professional's BW chain or of data
appended after an LE image. The `file` magic database treats the BW chain as a heuristic, and a
VOGONS thread notes that the LE signature is not at the BW header's 0x3C. There is also no
community note on trailing bytes in UFO2P.EXE. So this spike is empirical.

## How to Run

```
uv run python .planning/spikes/003-trailer/probe.py [ORIG_DIR] [GAME_DIR]
uv run python .planning/spikes/003-trailer/followup.py [ORIG_DIR] [GAME_DIR]
```

GAME_DIR defaults to the Steam install, which holds `cd.iso` and `XCOMA/`. The disc is read
read-only, in memory, through `tools/reverseapoc/iso9660.py`. The probes print offsets, lengths,
counts, booleans, trailer positions, the first 4 trailer bytes and SHA-1s, never the remaining
trailer bytes. Each hypothesis is compared inside the script.

## Investigation Trail

1. **Facts.** UFO2P: 27 bytes at 0x1A0723, starting `64 00 9b ff`, sha1
   `33a69cacf0a929fa9a104844a933273b4d0e4ee0`. TACP: 27 bytes at 0x303DDF, starting
   `64 00 9b ff`, sha1 `28ad5c4593a0080fd58cd8a627a996472e68fa34`. SMKP: 0 bytes after the last
   page. The two trailers differ and share 7 of 27 positions.
2. **Layout values and checksums.** None of these appears in the trailer as an aligned or
   unaligned u16/u32, in either byte order, at any position:
   - file size, pages end, data-pages offset, stub, LE offset, page count, last page size,
     loader/fixup section sizes, pages bytes, LE-image bytes;
   - CRC32, Adler-32, 8/16/32-bit byte sums, 16/32-bit word sums or the MZ-style one's-complement
     checksum, over four ranges: the file before the trailer, the pages, the LE image and the
     extender.

   This gives 0 matches in both files, so the hypothesis "checksum over the file or the pages" is
   rejected for these algorithms.
3. **Structure.** The first 4 bytes read as u16 values are 0x0064 then 0xFF9B, the one's
   complement of 0x0064. Scanning for that pattern finds value/complement u16 pairs at trailer
   positions **0, 4 and 8** in both files. The trailer is therefore a structured record, not
   random data. No position holds a plausible 1994-1999 DOS date in UFO2P; the TACP hits sit
   inside the varying bytes and are not repeated in UFO2P, so they are taken as chance.
4. **CD v1.00 comparison.** Every `.EXE` on `cd.iso` was parsed:
   - The CD v1.00 `XCOM3/UFOEXE/UFO2P.EXE` and `XCOM3/TACEXE/TACP.EXE` match the
     `[[cd_builds]]` SHA-1s. They **also** end in a 27-byte trailer starting `64 00 9b ff`,
     with complement pairs at 0, 4 and 8.
   - **The disc also carries `XCOM3/UFOEXE/UFO2P4.EXE` and `XCOM3/TACEXE/TACP4.EXE`, and they
     are byte-identical to the installed UFO2P.EXE and TACP.EXE.** Their whole-file SHA-1s equal
     the manifest's, and the manifest module names are `ufo24`/`tac4`. So the installed build is
     not added by the store installers: it is pressed on the 1997 disc next to the v1.00 build.
     No file under 4 MiB on the disc names `UFO2P4`/`TACP4`, so the installer's copy rule is
     probably in a compressed archive and was not followed (time box).
   - SMKP.EXE (DOS/4GW-bound as well) has no trailer, either on the disc or installed. The
     installers (`INSTALL.EXE`, `INSTALL/*.EXE`, `XCOMAPOC.EXE`, `SETUP.EXE`) are not bound LE
     programs.
5. **Across the four builds that carry a trailer** (CD UFO2P, UFO2P4, CD TACP, TACP4):
   - positions 0-3 (the pair 0x0064 / ~0x0064) and positions 8, 10 and 26 are equal in all four;
   - the complement relation holds at 0, 4 and 8 in all four;
   - the pair values at 4 and 8 differ between every build, even between UFO2P and UFO2P4;
   - positions 12-25 vary.

   28 sixteen-bit candidates per build give no hit for the pair values at 4 and 8:
   - word and byte sums, XOR of words, CRC-16/ARC and CRC-16/CCITT-FALSE, each over the file,
     the LE image, the pages and each object's pages;
   - file size >> 4 and pages end >> 4.
6. **Does the game read it?** The u32 immediate -27 does not occur in the page data of
   UFO2P/TACP, and neither does the first dword. This is weak evidence (a reader could compute
   the offset otherwise), but there is no sign of a direct `lseek(-27, SEEK_END)`.

## Results

**PARTIAL.** The facts the plans rely on are **confirmed**: 27 bytes at 0x1A0723 (UFO2P) and at
0x303DDF (TACP), both starting `64 00 9B FF`, SHA-1s as above, and none in SMKP.

What the trailer *is* stays unknown. It is a fixed 27-byte record:
- a constant u16 0x0064 with its complement at position 0;
- two per-build u16 value/complement pairs at 4 and 8;
- 14 per-build bytes at 12-25;
- one constant byte at 26.

It is:
- **not** a DOS/4GW bind record, because SMKP is bound the same way and has none;
- **not** an installer or patch stamp, because it is already on the pressed CD in both the
  v1.00 and the "4" builds;
- **not** any tested checksum or CRC of the file, pages or objects.

The most likely origin is a post-link stamping tool at the developer, for example a version,
copy-protection or self-check record. The value/complement pairs are a classic integrity
pattern, and 0x0064 = 100 could be "1.00".

Per D-10 the trailer stays **opaque**. The rebuild carries it unchanged as its own region and
nothing regenerates it. If Phase 5 finds the code that reads it, that reopens the question.

**Finding for the owner, outside this phase's scope:** docs/toolchain.md ("OpenApoc CRC
mismatch") says the installed executables are "a later build applied by the store installers".
This spike shows that the installed UFO2P.EXE/TACP.EXE ship on the 1997 disc as
`XCOM3/UFOEXE/UFO2P4.EXE` and `XCOM3/TACEXE/TACP4.EXE`. That doc paragraph should be corrected
by the owner's decision; it is not edited here.

Run output (2026-10-20), probe.py, CD section abridged:

```
UFO2P.EXE                          size=0x1a073e pages_end=0x1a0723 after=27  starts 64 00 9b ff  sha1 33a69cacf0a929fa9a104844a933273b4d0e4ee0
TACP.EXE                           size=0x303dfa pages_end=0x303ddf after=27  starts 64 00 9b ff  sha1 28ad5c4593a0080fd58cd8a627a996472e68fa34
SMKP.EXE                           size=0x4244c pages_end=0x4244c after=0
UFO2P vs TACP trailer: equal=False equal_positions=7/27
UFO2P.EXE  u16 complement pairs at positions [0, 4, 8]
TACP.EXE   u16 complement pairs at positions [0, 4, 8]
UFO2P.EXE  0 matches: []
TACP.EXE   0 matches: []
cd:XCOM3/TACEXE/TACP.EXE           size=0x305ffa pages_end=0x305fdf after=27  starts 64 00 9b ff  sha1 d47f51b612e21b8078aad58d3725480b2771b015
                                   equal to UFO2P trailer=False TACP trailer=False [cd_builds sha1 match=True] ... complement pairs [0, 4, 8]
cd:XCOM3/TACEXE/TACP4.EXE          size=0x303dfa pages_end=0x303ddf after=27  starts 64 00 9b ff  sha1 28ad5c4593a0080fd58cd8a627a996472e68fa34
                                   equal to UFO2P trailer=False TACP trailer=True ... complement pairs [0, 4, 8]
cd:XCOM3/UFOEXE/SMKP.EXE           size=0x4244c pages_end=0x4244c after=0
cd:XCOM3/UFOEXE/UFO2P.EXE          size=0x19f93e pages_end=0x19f923 after=27  starts 64 00 9b ff  sha1 c9124264fed0b47fbfc982d3f5e9090f731661b6
                                   equal to UFO2P trailer=False TACP trailer=False [cd_builds sha1 match=True] ... complement pairs [0, 4, 8]
cd:XCOM3/UFOEXE/UFO2P4.EXE         size=0x1a073e pages_end=0x1a0723 after=27  starts 64 00 9b ff  sha1 33a69cacf0a929fa9a104844a933273b4d0e4ee0
                                   equal to UFO2P trailer=True TACP trailer=False ... complement pairs [0, 4, 8]
```

followup.py:

```
cd:UFO2P4.EXE    sha1 e7488bf3de2efeaa3c1c72d3763eeeb35f727c56 == manifest target ['UFO2P.EXE']
cd:TACP4.EXE     sha1 48ef00969d8880a0a152de1b652853fa7ac27393 == manifest target ['TACP.EXE']
positions equal in all four: [0, 1, 2, 3, 8, 10, 26]
pair@0: complement holds in all four=True value equal across all four=True
pair@4: complement holds in all four=True value equal across all four=False UFO2P==UFO2P4=False TACP==TACP4=False
pair@8: complement holds in all four=True value equal across all four=False UFO2P==UFO2P4=False TACP==TACP4=False
cd:UFO2P.EXE / UFO2P4.EXE / TACP.EXE / TACP4.EXE: 28 candidates each, hits: []
orig:UFO2P.EXE   u32le -27: 0    orig:TACP.EXE   u32le -27: 0
```

The SHA-1s printed for whole files are the manifest and `[[cd_builds]]` values. The trailer
SHA-1s are hashes, never trailer bytes.
