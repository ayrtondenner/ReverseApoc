# Spike Manifest

## Ideas

### le-round-trip-facts
Confirm, on the real UFO2P.EXE, TACP.EXE and SMKP.EXE, the LE layout facts the Phase 3
byte-identical round trip relies on: page map, fixup records and straddlers, the byte-region
tiling, and the 27 bytes after the last page. Each spike cross-checks `tools/reverseapoc/le.py`
against an independent raw reader. The spikes feed plan 03-05 Task 2, which pins only confirmed
facts as regression tests and in docs/toolchain.md. Spikes 001 + 002 together are "the LE
edge-case spike" named in that task's precondition, and spike 003 is "the 27-byte trailer spike".

**Requirements:**

- Read orig/ only and write nothing.
- Print only offsets, lengths, counts, booleans, the first 4 trailer bytes and SHA-1s, never
  game bytes.
- Cross-check le.py with an independent raw reader (`001-le-pages-and-fixups/rawle.py`, struct
  only), not with le.py's own view.
- Take expected SHA-1s from `targets.load_manifest`, never from a copied string.
- Whatever spike 003 finds, the trailer stays opaque and is carried unchanged (D-10).

## Spikes

| # | Idea | Name | Type | Validates | Verdict | Tags |
|---|------|------|------|-----------|---------|------|
| 001 | le-round-trip-facts | le-pages-and-fixups | standard | Given the three EXEs, when every page-map entry and fixup record is walked raw, then pages are physical/identity, fixups internal, 14/11/2 straddlers on both pages, one off32 per file cut into BSS, le.fixups() agrees | VALIDATED | le, fixups, page-map, straddlers, dos4gw |
