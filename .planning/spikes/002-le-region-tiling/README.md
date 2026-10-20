---
spike: 002
idea: le-round-trip-facts
name: le-region-tiling
type: standard
validates: "Given the LE header fields, when each file is cut into extender, MZ stub, LE header, loader tables, fixup section, padding, pages and trailer, then the regions tile [0, size) exactly, the declared loader section ends where the fixup section ends, the padding is all zero, and reassembling the regions from their own sources reproduces the manifest SHA-1"
verdict: VALIDATED
related: [001, 003]
tags: [le, region-map, tiling, reassembly, sha1]
---

# Spike 002: LE region tiling

Together with spike 001, this is the "LE edge-case spike" that plan 03-05 Task 2 consumes.

## What This Validates

Given the LE header fields of UFO2P.EXE, TACP.EXE and SMKP.EXE, when each file is cut into
extender, MZ stub, LE header, loader tables, fixup section, padding, pages and trailer, then:

- the regions tile [0, size) exactly;
- the declared loader section ends where the fixup section ends;
- the padding is all zero;
- reassembling the regions from their own sources reproduces the manifest SHA-1, read through
  `targets.load_manifest`.

## How to Run

```
uv run python .planning/spikes/002-le-region-tiling/regions.py [ORIG_DIR]
```

It uses spike 001's independent raw reader (`../001-le-pages-and-fixups/rawle.py`, loaded by
path) for every boundary. It uses `reverseapoc.le` only for the cross-check and
`reverseapoc.targets.load_manifest` for the expected SHA-1. It reads orig/ only, writes nothing,
and exits 1 on any FAIL.

## What to Expect

`ALL PASS` and exit 0: 54 PASS lines, 0 FAIL, plus INFO lines for the region table and for the
two mutants that real files cannot catch.

## Investigation Trail

1. **Boundaries from the file's own header.** extender [0, stub), MZ stub [stub, le), LE header
   [le, object table), loader tables [object table, fixup page table), fixup section
   [fixup page table, + fixup section size), padding [fixup end, data pages), pages
   [data pages, pages end), trailer [pages end, EOF). Zero-length regions are dropped, so SMKP
   has no trailer region. The stub and LE offsets come from 001's MZ → BW chain walk, not from
   le.py.
2. **Loader section vs fixup section.** object table + loader section size == fixup page
   table + fixup section size in all three files. The declared loader section *includes* the
   fixup section, so modelling them as two consecutive regions of the declared sizes would count
   the fixups twice. The fixup page table has num_pages + 1 entries and ends where the record
   table starts. There is no iterated data map, and the non-resident name and debug-info fields
   are 0, so no hidden data can sit in "padding" or "trailer" (D-19's refusal never triggers on
   these files).
3. **Reassembly.** A fresh `bytearray(size)` is built from two sources:
   - non-page regions sliced from the original;
   - per-object images of `page_count * page_size` bytes, filled from each page's full size
     through the raw page map (so the obj1 tail past vsize is carried) and written back to
     `page_file_offset(number)`.

   The result reproduces the manifest SHA-1 for all three files, also when everything is written
   in reverse order.
4. **Can the check fail?** Each of the following is caught:
   - one flipped page byte;
   - pages 1 and 2 written to each other's file slot;
   - dropping the trailer region (UFO2P/TACP; for SMKP nothing is dropped and the SHA-1 is
     unchanged, as expected).
5. **Surprise: two D-16 mutants are invisible on the real files.** A first swap mutant, which
   swapped two page-map entries, was not caught. It moves the read slot and the write slot
   together, so a self-consistent page-map mistake reproduces the file. Following that up:
   - **vsize-sized images**: the image stops at vsize, as a flat loader does. They give the same
     SHA-1, because the obj1 tail past vsize is all zero (0x523 / 0xAB1 / 0xC80 bytes).
   - **logical-number page offsets**: they give the same SHA-1, because the page map is the
     identity (spike 001).

   So the real-file round trip cannot prove "page-mapped, tail carried" on its own. Plan 03-01
   Task 3 already proves both through synthetic fixtures: a non-zero tail
   (`test_round_trip_keeps_page_tail_past_vsize`) and a permuted page map
   (`page_numbers=(2, 1, 3)`). This spike confirms that those synthetic tests are load-bearing
   and that no real-file test can stand in for them (Pitfalls C and F).

## Results

**VALIDATED.** The region map from 03-RESEARCH.md is confirmed exactly:

| Region (half-open file offsets) | UFO2P.EXE (1,705,790 B) | TACP.EXE (3,161,594 B) | SMKP.EXE (271,436 B) |
|---|---|---|---|
| extender (MZ loader + BW modules) | [0x0, 0x352A4) | [0x0, 0x352A4) | [0x0, 0x26654) |
| MZ stub | [0x352A4, 0x37F34) 11,408 B | [0x352A4, 0x37F34) 11,408 B | [0x26654, 0x292E4) 11,408 B |
| LE header | [0x37F34, 0x37FF8) 196 B | [0x37F34, 0x37FF8) 196 B | [0x292E4, 0x293A8) 196 B |
| loader tables | [0x37FF8, 0x384EE) 1,270 B | [0x37FF8, 0x38A99) 2,721 B | [0x293A8, 0x29435) 141 B |
| fixup section | [0x384EE, 0x7233A) 237,132 B | [0x38A99, 0x6A711) 203,896 B | [0x29435, 0x2D375) 16,192 B |
| padding (all zero) | [0x7233A, 0x724A4) 362 B | [0x6A711, 0x6A8A4) 403 B | [0x2D375, 0x2D454) 223 B |
| pages 1..N | [0x724A4, 0x1A0723) | [0x6A8A4, 0x303DDF) | [0x2D454, 0x4244C) |
| trailer | [0x1A0723, 0x1A073E) 27 B | [0x303DDF, 0x303DFA) 27 B | none |

Further confirmed:
- obj1 page bytes past vsize are 0x523 / 0xAB1 / 0xC80, all zero;
- le.py's data-pages offset, last page size, page count and page geometry equal the raw values;
- the reassembled SHA-1 equals `load_manifest()`'s for every target.

Run output (2026-10-20), with the INFO region rows shown in the table above:

```
PASS  UFO2P.EXE  regions tile [0, size) with no gap or overlap  sum=1705790 size=1705790
PASS  UFO2P.EXE  region starts == 03-RESEARCH table
PASS  UFO2P.EXE  declared loader section ends where the fixup section ends  0x7233a vs 0x7233a
PASS  UFO2P.EXE  fixup page table has num_pages + 1 entries
PASS  UFO2P.EXE  no iterated data map
PASS  UFO2P.EXE  non-resident name and debug fields are zero  []
PASS  UFO2P.EXE  padding length 362
PASS  UFO2P.EXE  padding is all zero
PASS  UFO2P.EXE  obj1 page bytes past vsize 0x523
PASS  UFO2P.EXE  obj1 page tail past vsize is all zero
PASS  UFO2P.EXE  bytes after the last page 27  at 0x1a0723
PASS  UFO2P.EXE  le.py data-pages offset, last page size and page count == raw
PASS  UFO2P.EXE  le.py page geometry ends where raw pages end
PASS  UFO2P.EXE  reassembled SHA-1 == load_manifest() sha1  e7488bf3de2efeaa3c1c72d3763eeeb35f727c56
PASS  UFO2P.EXE  one flipped page byte changes the SHA-1  flipped at 0x108ca4
PASS  UFO2P.EXE  reassembly in reverse region/object/page order gives the same SHA-1
PASS  UFO2P.EXE  mutant: pages 1/2 written to each other's slot is caught
PASS  UFO2P.EXE  mutant: dropping the trailer region is caught iff one exists  caught=True
INFO  UFO2P.EXE  mutant: vsize-sized images caught=False (page tail past vsize is all zero)
INFO  UFO2P.EXE  mutant: logical-number page offsets caught=False (identity page map)
PASS  TACP.EXE   regions tile [0, size) with no gap or overlap  sum=3161594 size=3161594
PASS  TACP.EXE   declared loader section ends where the fixup section ends  0x6a711 vs 0x6a711
PASS  TACP.EXE   padding length 403
PASS  TACP.EXE   obj1 page bytes past vsize 0xab1
PASS  TACP.EXE   bytes after the last page 27  at 0x303ddf
PASS  TACP.EXE   reassembled SHA-1 == load_manifest() sha1  48ef00969d8880a0a152de1b652853fa7ac27393
PASS  TACP.EXE   mutant: pages 1/2 written to each other's slot is caught
PASS  TACP.EXE   mutant: dropping the trailer region is caught iff one exists  caught=True
PASS  SMKP.EXE   regions tile [0, size) with no gap or overlap  sum=271436 size=271436
PASS  SMKP.EXE   declared loader section ends where the fixup section ends  0x2d375 vs 0x2d375
PASS  SMKP.EXE   padding length 223
PASS  SMKP.EXE   obj1 page bytes past vsize 0xc80
PASS  SMKP.EXE   bytes after the last page 0  at 0x4244c
PASS  SMKP.EXE   reassembled SHA-1 == load_manifest() sha1  efdcf2a5adf50a8d0e4fb6a5796a663f6a48e8bc
PASS  SMKP.EXE   mutant: pages 1/2 written to each other's slot is caught
PASS  SMKP.EXE   mutant: dropping the trailer region is caught iff one exists  caught=False
ALL PASS
```

The full run prints 54 PASS lines and 0 FAIL, with the same claims for every file. The SHA-1s
printed are the manifest values from config/targets.toml.
