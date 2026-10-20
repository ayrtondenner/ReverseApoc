# Phase 3: Byte-identical round trip - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-20
**Phase:** 03-byte-identical-round-trip
**Areas discussed:** Splice API shape, Rebuild command & outputs, 27-byte trailer, Test & gate policy

---

## Splice API shape

| Option | Description | Selected |
|--------|-------------|----------|
| Linear-address patches | `splice(le, {va: bytes})`, flat address space, crosses pages | ✓ |
| Whole object images | `splice(le, {obj: image})` | |
| Both | VA primitive plus object-image helper | |

| Fixup-field overlap | Description | Selected |
|--------|-------------|----------|
| Keep the original bytes | KKND behaviour, report masked fields | ✓ |
| Refuse the patch | Any overlap raises | |
| Write as-is | No special handling | |

| Guards | Description | Selected |
|--------|-------------|----------|
| Outside page data | Header/tables/stub/trailer/BSS raise | ✓ |
| Length change | Output length fixed | ✓ |
| Non-physical pages | Iterated/zero pages raise | ✓ |
| Overlapping patches | Asked for an ELI5 first; then chose "Refuse any overlap" over "Refuse unless identical" and "Last writer wins" | ✓ |

| Module | Description | Selected |
|--------|-------------|----------|
| New `tools/reverseapoc/splice.py` | KKND derivation header, le.py stays read-only | ✓ |
| Inside le.py | | |
| You decide | | |

**Notes:** Owner wanted the pros/cons of the overlap guard explained before deciding; chose the strict guard so function-boundary errors fail at the collision, not later as a SHA-1 mismatch.

---

## Rebuild command & outputs

| Option | Description | Selected |
|--------|-------------|----------|
| `rebuild` | Reused by Phase 5 | ✓ |
| `roundtrip` | Phase-3-specific name | |
| `verify` | Confusable with GSD/Claude verify | |

| Targets | Description | Selected |
|--------|-------------|----------|
| UFO2P + TACP + SMKP | Round trip only for SMKP; out of Phases 4-6 | ✓ |
| UFO2P + TACP only | SMKP fully deferred | |

| Output | Description | Selected |
|--------|-------------|----------|
| One line per EXE + diff on failure | | |
| Also `--json` | Same plus machine-readable output for the Phase 6 driver | ✓ |
| Minimal | | |

| Ninja | Description | Selected |
|--------|-------------|----------|
| Phony `verify` edge now | | ✓ |
| Not yet | | |

**Notes:** Owner asked for an ELI5 of SMKP.EXE and the effort to include it. Answer given: it is the Smacker cutscene player (`smk/intro1.smk`, `lose1.smk`, `wingame2.smk`), ~70 KB code, separately bound, no game logic; round trip costs ~1 hour (21 physical pages, 2,297 fixups, 2 straddling, no trailer), matching it is low value. Owner chose to include it in the round trip only.

---

## 27-byte trailer

| Option | Description | Selected |
|--------|-------------|----------|
| Time-boxed spike, then opaque | ~1 h on checksum/stamp/bind hypotheses | ✓ |
| Opaque, no investigation | | |
| Explain it fully | Open-ended | |

| parse-le | Description | Selected |
|--------|-------------|----------|
| Offset, length, sha1 | | ✓ |
| Full region map | | |
| No | | |

| Docs | Description | Selected |
|--------|-------------|----------|
| Offset, length, first 4 bytes, sha1 | | ✓ |
| Offset, length, sha1 only | | |

---

## Test & gate policy

| Mutations | Selected |
|--------|----------|
| Mid-page byte | ✓ |
| Page edges | ✓ |
| Short last page | ✓ |
| Fixup field masked | ✓ |

| Container | Description | Selected |
|--------|-------------|----------|
| Host and container | orig/ mounted ro in the container | ✓ |
| Host only | | |

| Oracle | Description | Selected |
|--------|-------------|----------|
| From config/targets.toml | Via targets.load_manifest | ✓ |
| Hard-coded | | |

| No-copy proof | Description | Selected |
|--------|-------------|----------|
| Region map + reassembly | Fresh buffer, tiling coverage test, copy-only implementation fails | ✓ |
| Copy + patch | KKND-style | |

---

## Claude's Discretion

- Dataclass names, masked-field report shape, splice.py internal layout, where the region map is exposed, whether inter-section padding is its own region.

## Deferred Ideas

- Matching SMKP.EXE functions (v2, SMKP-01).
- Full LE rewrite / relinkable build (v2, LE-01).
