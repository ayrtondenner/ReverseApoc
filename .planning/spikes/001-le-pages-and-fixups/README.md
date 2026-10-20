---
spike: 001
idea: le-round-trip-facts
name: le-pages-and-fixups
type: standard
validates: "Given UFO2P, TACP and SMKP, when every page-map entry and every fixup record is walked raw (per page, without de-duplication), then every page is physical with an identity map, every fixup is internal, each page-straddling field (14/11/2) appears on both pages with the same target and kind, exactly one off32 field per file is cut by the short last page into BSS, and le.fixups() agrees field for field"
verdict: VALIDATED
related: [002, 003]
tags: [le, fixups, page-map, straddlers, dos4gw]
---

# Spike 001: LE pages and fixups

Together with spike 002, this is the "LE edge-case spike" that plan 03-05 Task 2 consumes.

## What This Validates

Given UFO2P.EXE, TACP.EXE and SMKP.EXE in orig/, when every page-map entry and every fixup
record is walked raw (per page, without de-duplication), then:

- every page is physical with an identity page map;
- every fixup is internal;
- each page-straddling field (14 / 11 / 2) appears on both pages with the same target and kind;
- exactly one off32 field per file is cut by the short last page into BSS;
- `le.fixups()` agrees field for field.

## How to Run

```
uv run python .planning/spikes/001-le-pages-and-fixups/check.py [ORIG_DIR]
uv run python .planning/spikes/001-le-pages-and-fixups/extender_chain.py [ORIG_DIR]
```

- `rawle.py` is an independent raw reader. It uses only `struct` and never imports
  `reverseapoc.le`.
- `check.py` holds the provisional facts from 03-RESEARCH.md and prints one PASS/FAIL line per
  claim. It exits 1 on any FAIL.
- Output is offsets, VAs, counts and booleans only. Nothing is written.

## What to Expect

`ALL PASS` and exit 0: 99 PASS lines and 0 FAIL.

## Investigation Trail

1. **Locating the LE header independently.** le.py finds the stub by scanning backwards from an
   `LE\0\0` signature for an MZ whose e_lfanew points at it. To get a second, independent
   reading, the first attempt walked MZ headers by their declared image size (e_cp/e_cblp). It
   failed: the first MZ declares an image of 0xF474 bytes, and 0xF474 is not an MZ.
   `extender_chain.py` showed that 0xF474 holds a DOS/4GW **BW** header, whose u32 at 0x1C is
   the absolute offset of the next header. Following it gives:
   - UFO2P/TACP: MZ@0 (image 0xF474) → BW@0xF474 (image 0xEA50, next 0x1E0C4) → BW@0x1E0C4
     (image 0x16FE0, next 0x352A4) → MZ stub@0x352A4;
   - SMKP: MZ@0 (image 0xF474) → BW@0xF474 (image 0x16FE0, next 0x26654) → MZ stub@0x26654.

   So the bound extender is an MZ loader plus a BW-module chain, two modules in the game EXEs and
   one in SMKP. The last BW's next pointer is the LE's owning stub. `rawle.locate_by_mz_chain`
   now follows this chain. It agrees with a forward MZ scan and with `le.stub_offset` and
   `le.le_offset` on all three files.
2. **Page-map entry encoding.** Read as a 24-bit big-endian page number (bytes 0..2, flags in
   byte 3), as le.py does, the map is the identity on every page. The other plausible reading,
   u16 little-endian high word << 8 | byte 2, matches only pages 1..255 (255/303, 255/666), so it
   is wrong. The entry format is confirmed independently, not just copied from le.py.
3. **Straddlers.** The raw walk lists 28,211 / 24,449 / 2,299 record entries. That is exactly
   the de-duplicated 28,197 / 24,438 / 2,297 plus one extra entry per straddler. The fields
   listed twice are exactly the fields whose bytes cross a 4 KiB page boundary, in both
   directions. Each sits on two adjacent pages with one kind and target, and none is listed twice
   on the same page or more than twice.
4. **Field cut into BSS.** The page-backed end of each object comes from the page sizes, with
   the last physical page at `last_page_size`. Exactly one field per file runs past it. It is an
   off32 in the short last page (logical 303 / 666 / 21) of object 2, targeting object 1:
   - UFO2P 0x13E27C, 3 bytes backed + 1 in BSS;
   - TACP 0x2B6538, 3 + 1;
   - SMKP 0x32FF6, 2 + 2.

   No field crosses its object's vsize end.
5. **Negative control.** One wrong expected straddler VA (SMKP 0x1CFFF) and one wrong
   backed-byte count (TACP 4) each produce a FAIL line and exit 1, so the checker can fail.

## Results

**VALIDATED.** Every provisional fact holds on the real files, read by a second parser:

| | UFO2P.EXE | TACP.EXE | SMKP.EXE |
|---|---|---|---|
| bound extender chain | MZ 0xF474 → BW → BW → stub 0x352A4 | same as UFO2P | MZ 0xF474 → BW → stub 0x26654 |
| LE header | 0x37F34 | 0x37F34 | 0x292E4 |
| pages, all physical, identity map | 303 | 666 | 21 |
| raw record entries / de-duplicated fields | 28,211 / 28,197 | 24,449 / 24,438 | 2,299 / 2,297 |
| off32 / sel16 / ptr16:32 / rel32 | 28,183 / 10 / 4 / 0 | 24,424 / 10 / 4 / 0 | 2,297 / 0 / 0 / 0 |
| fixup targets | internal only, no additive or chained records | same | same |
| page-straddling fields (off32, obj1, on both pages) | 14 | 11 | 2 |
| field cut by the end of page data (off32, obj2) | 0x13E27C, 3 backed + 1 BSS | 0x2B6538, 3 + 1 | 0x32FF6, 2 + 2 |
| pages end / file size | 0x1A0723 / 0x1A073E | 0x303DDF / 0x303DFA | 0x4244C / 0x4244C |
| `le.fixups()` vs raw, `le.pages` vs raw | equal (0 / 0 differences) | equal | equal |

Straddler VAs:
- UFO2P: 0x1EFFD 0x28FFD 0x36FFE 0x62FFF 0x67FFE 0x6AFFE 0x7FFFF 0x98FFF 0x9FFFF 0xA3FFE 0xB0FFD
  0xB4FFF 0xC6FFD 0xC8FFF;
- TACP: 0x39FFD 0x3BFFF 0x42FFD 0x43FFE 0x52FFD 0x6DFFE 0x89FFD 0x8AFFF 0x9EFFD 0xA8FFD 0xB8FFD;
- SMKP: 0x11FFD 0x1CFFE.

New fact, not in 03-RESEARCH.md: the extender region [0, stub) is itself structured as an MZ
loader plus BW modules. The rebuild still carries it as one opaque region, so nothing in the
plans changes.

Run output (2026-10-20), with the per-straddler lines left out:

```
PASS  UFO2P.EXE  stub found by the MZ -> BW header chain  stub=0x352a4 le=0x37f34
PASS  UFO2P.EXE  forward MZ scan agrees with the header chain
PASS  UFO2P.EXE  page count 303
PASS  UFO2P.EXE  every page-map flag is 0 (physical)
PASS  UFO2P.EXE  identity map (24-bit big-endian page number == logical)
INFO  UFO2P.EXE  u16-LE<<8 reading matches logical on 255/303 pages
PASS  UFO2P.EXE  pages end inside the file  pages_end=0x1a0723 size=0x1a073e
PASS  UFO2P.EXE  every record is a plain internal fixup (28211 entries, raw)
PASS  UFO2P.EXE  fields listed twice == fields crossing a page boundary  twice=14 crossing=14
PASS  UFO2P.EXE  exactly one field cut by the end of page data (1)
PASS  UFO2P.EXE  cut field VA and backed bytes == expected  va=0x13e27c backed=3 bss=1 obj=2 target_obj=1
PASS  UFO2P.EXE  de-duplicated kind counts == expected  {'off32': 28183, 'sel16': 10, 'ptr16:32': 4}
PASS  UFO2P.EXE  le.fixups() == de-duplicated raw fields  raw=28197 le.py=28197 only_raw=0 only_le=0
PASS  TACP.EXE   stub found by the MZ -> BW header chain  stub=0x352a4 le=0x37f34
PASS  TACP.EXE   identity map (24-bit big-endian page number == logical)
PASS  TACP.EXE   every record is a plain internal fixup (24449 entries, raw)
PASS  TACP.EXE   fields listed twice == fields crossing a page boundary  twice=11 crossing=11
PASS  TACP.EXE   cut field VA and backed bytes == expected  va=0x2b6538 backed=3 bss=1 obj=2 target_obj=1
PASS  TACP.EXE   le.fixups() == de-duplicated raw fields  raw=24438 le.py=24438 only_raw=0 only_le=0
PASS  SMKP.EXE   stub found by the MZ -> BW header chain  stub=0x26654 le=0x292e4
PASS  SMKP.EXE   pages end inside the file  pages_end=0x4244c size=0x4244c
PASS  SMKP.EXE   fields listed twice == fields crossing a page boundary  twice=2 crossing=2
PASS  SMKP.EXE   cut field VA and backed bytes == expected  va=0x32ff6 backed=2 bss=2 obj=2 target_obj=1
PASS  SMKP.EXE   le.fixups() == de-duplicated raw fields  raw=2297 le.py=2297 only_raw=0 only_le=0
ALL PASS
```

The full run prints 99 PASS lines and 0 FAIL, including every individual straddler line.
