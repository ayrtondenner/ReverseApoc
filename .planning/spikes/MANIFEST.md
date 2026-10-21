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

### compiler-identification
Confirm that the original Watcom compilers (10.5, 10.6, 11.0) run under wibo 1.2.0 in the
reverseapoc-build container from the read-only `third_party/watcom` trees, and that the objects
they produce equal the native Windows host compile after normalization (D-03). Spike 004 is the
Phase 4 roadmap spike; its results are logged by plan 04-11 in `build/gate/04-native-vs-wibo.txt`.

**Requirements:**

- The compilers and the game are user-supplied and stay out of the image and the repo.
- Compare raw and normalized SHA-1s (THEADR and COMENT class 0xE9 dropped); gate on normalized.
- Record SHA-1s and banners only, never compiler or object bytes.
- 10.5 runs only with the BINW compiler that `install-watcom 10.5` decodes (D-01).

## Spikes

| # | Idea | Name | Type | Validates | Verdict | Tags |
|---|------|------|------|-----------|---------|------|
| 001 | le-round-trip-facts | le-pages-and-fixups | standard | Given the three EXEs, when every page-map entry and fixup record is walked raw, then pages are physical/identity, fixups internal, 14/11/2 straddlers on both pages, one off32 per file cut into BSS, le.fixups() agrees | VALIDATED | le, fixups, page-map, straddlers, dos4gw |
| 002 | le-round-trip-facts | le-region-tiling | standard | Given the LE header fields, when each file is cut into extender/stub/header/loader/fixups/padding/pages/trailer, then the regions tile [0, size), loader section ends at fixup end, padding is zero, and reassembly reproduces the load_manifest() SHA-1 | VALIDATED | le, region-map, tiling, reassembly, sha1 |
| 003 | le-round-trip-facts | trailer | standard | Given the 27 bytes after the last page in UFO2P/TACP, when checksum, installer-stamp and DOS/4GW-bind hypotheses are tested and the CD v1.00 build compared, then the trailer is identified or stays opaque (D-10) | PARTIAL | le, trailer, dos4gw, cd-build, d-10 |
| 004 | compiler-identification | wibo-watcom | standard | Given wibo 1.2.0 in the reverseapoc-build image and the read-only third_party/watcom trees, when each version's BINNT/WCC386.EXE compiles a C89 probe, then 10.5 (decoded BINW), 10.6 and 11.0 produce objects whose normalized SHA-1 equals the native host compile | VALIDATED | watcom, wibo, compiler, d-01, d-03 |
