---
title: Map functions between the installed build and the CD v1.00 build
created: 2026-11-18
area: cross-build
files: tools/reverseapoc/ingest.py, tools/reverseapoc/twins.py, config/targets.toml
source: literature mining of 2026-11-18 (docs/research/notes-ideas-tooling-reproducibility.md #6; docs/learnings.md (OpenApoc CRC entry))
---

# Map functions between the installed build and the CD v1.00 build

**Why.** learnings.md calls the build-to-build diff free matching evidence, and D-42 revisits twin matching of the CD build after Phase 7. OpenApoc's offsets apply only to the CD build.

**Do.** A function map between the two builds (byte/relocation-identical and moved functions), exported for OpenApoc offsets.

**Done when.** A committed map with coverage numbers; one OpenApoc offset translated as an example.

**Effort / value.** M / high for OpenApoc. Evidence and sources: docs/research/notes-ideas-tooling-reproducibility.md #6; docs/learnings.md (OpenApoc CRC entry).

## Unblocked (2026-11-18)

The owner put the 1997 disc images in `C:\Users\Ayrton\Documents\x-com-apocalypse\`, outside the repo: two byte-identical ISOs plus a MODE1/2352 bin+cue. Inside each ISO, `XCOM3/UFOEXE/UFO2P.EXE` and `XCOM3/TACEXE/TACP.EXE` hash to the `[[cd_builds]]` SHA-1s in `config/targets.toml`. `UFO2P4.EXE` and `TACP4.EXE` hash to our `orig/` files.

## Resolution (2026-11-18)

Done in batch 2026-11-18 (U13): `ingest --cd` (ISO and MODE1/2352), `reverseapoc cd-map`, committed config/<exe>/cd-map.csv (UFO2P 632 of 1,892 rows mapped, TACP 660 of 1,874). OpenApoc's FUN_0005faf0 has no masked twin; installed func_0005F830 is its counterpart by shape; data offsets carry over (all but 258 bytes equal).
