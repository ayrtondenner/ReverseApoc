# Phase 3: Byte-identical round trip - Research

**Researched:** 2026-10-20
**Domain:** LE (Linear Executable) byte layout, in-place page splice, whole-file SHA-1 gate (stdlib Python 3.14 + pytest)
**Confidence:** HIGH for the code base and the measured layout facts (read this session, run read-only against `orig/`); MEDIUM for LE spec field *names* (training knowledge, but every field used was cross-checked by sizes adding up on all three real files)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Splice API
- **D-01:** The API takes linear-address patches, `splice(le, {va: bytes})`. Patches are applied in flat address space, so a patch may cross a page boundary and land in two pages. A whole-object rebuild is just one patch per object. — **Reversibility:** costly — Phase 5's landing step and the Phase 6 driver call this signature.
- **D-02:** Patch bytes that fall on an LE fixup field are not written. The field keeps the original link-time value, as in KKND's `build_kknd.py`. This includes the 14 (UFO2P) / 11 (TACP) / 2 (SMKP) page-straddling off32 fields. Splice reports which fields it masked. Phase 5's relocation check verifies targets separately.
- **D-03:** Splice refuses, with an error naming the patch, the address and the reason:
  - a write to any address not backed by file page bytes (LE header, loader and fixup tables, the DOS/4GW extender, the MZ stub, padding, the trailer, BSS past the last page);
  - any change of file length;
  - any page that is not physical (iterated, zero-filled, invalid). None exist today, but the code fails loudly instead of guessing.
- **D-04:** Splice refuses overlapping patches, naming both patches and the colliding address. It does this even when both write identical bytes. Rationale (owner, after an ELI5 of the trade-off): a function-boundary error must fail immediately where it happens, not later as a SHA-1 mismatch somewhere else.
- **D-05:** The code lives in a new module, `tools/reverseapoc/splice.py`, with the KKND-Decomp (CC0) derivation header used by `le.py`. `le.py` stays a read-only parser. It may gain small public read helpers, for example making `_check_loadable` public, but no write logic.

#### Rebuild command and outputs
- **D-06:** The verb is `uv run reverseapoc rebuild`. Phase 5 reuses it once patches come from compiled functions; there is no separate `roundtrip` verb. — **Reversibility:** costly — the ninja edge, docs and Phase 6 driver will call it by name.
- **D-07:** By default it rebuilds every LE target in `config/targets.toml`: UFO2P.EXE, TACP.EXE and SMKP.EXE. `--exe NAME` restricts it to one. SMKP joins the round trip only, as a second layout without a trailer; it stays out of Phases 4-6, and SMKP-01 remains the v2 requirement for matching it. Outputs go to `build/<NAME>` (gitignored). Nothing is ever written under `orig/`.
- **D-08:** Output is one line per EXE, e.g. `OK  UFO2P.EXE  sha1 e7488bf3… == manifest`. On mismatch it reports:
  - the first differing file offset;
  - the region that offset falls in (page N of object M plus the VA, or header/stub/loader/fixups/padding/trailer);
  - the count of differing bytes.

  Exit code 1 on any mismatch. A `--json` flag prints the same result machine-readably for the Phase 6 driver.
- **D-09:** `configure.py` gains a phony `verify` edge that runs `uv run reverseapoc rebuild`, next to the existing `check-orig` and `parse-le` phony edges. This satisfies RT-03's "a CLI verb and a ninja target".

#### The 27-byte trailer
- **D-10:** The trailer gets a time-boxed spike, then is treated as opaque. The spike spends about an hour on obvious hypotheses: a CRC/checksum over the file or the pages, an installer or patch stamp, a DOS/4GW bind record. The CD v1.00 build is a useful comparison. Whatever the verdict, the rebuild carries the trailer over unchanged as its own region, and nothing regenerates it.
- **D-11:** `parse-le` reports a trailer line and a JSON field, both carrying the offset, length and SHA-1 of the bytes after the last page. For SMKP the length is 0. It never prints the bytes.
- **D-12:** `docs/toolchain.md` records the trailer as offset, length, first 4 bytes and SHA-1 (e.g. "UFO2P: 27 bytes at 0x1A0723, starts 64 00 9B FF, sha1 …"). It never records the full bytes.

#### Test and gate policy
- **D-13:** The negative tests must cover each of these (synthetic LE fixtures, plus one real-file control):
  - **mid-page:** a one-byte mutation in the middle of a page changes the SHA-1 and is reported at the right file offset and VA;
  - **page edges:** the last byte of one page, the first byte of the next, and a patch spanning the boundary each land correctly;
  - **short last page:** a patch in the final partial page works, and one past its end is refused;
  - **fixup field:** a patch covering a fixup field, including a page-straddling one, leaves the original bytes and reports the masked field.
- **D-14:** The real-file round trip runs on the host and inside `docker compose run --rm test`, where `orig/` is mounted read-only and the rebuild writes only to `build/`. It is skipped where `orig/` is absent, i.e. in CI.
- **D-15:** The expected SHA-1s come from `config/targets.toml` through `targets.load_manifest`, the same source the CLI uses. The hash strings are never copied into test files.
- **D-16:** "Rebuilt, not copied" is proven by a region map plus reassembly:
  1. The rebuild writes each region from its own source into a fresh buffer: prefix regions from the original, page bytes re-paged from per-object images through the page map, and the trailer.
  2. A coverage test proves the regions tile the file with no gap or overlap.
  3. A copy-only implementation must fail the tests. This is research Pitfall 1, the tautological round trip.

#### Code quality (rules merged with PR #1, apply to splice.py)
- **D-17:** Follow `.claude/rules/tools.md` and `docs/coding-style.md#python-tooling`:
  - shallow nesting, using generators or helpers and early `continue`;
  - no bare binary-format offsets: LE header fields become module constants named after the spec field;
  - `next(..., None)` for first-match lookups;
  - error context added in one place;
  - reuse existing dataclasses (`LEPage`, `LEObject`, `Fixup`, `targets.FileHashes`);
  - TDD with tests proven to fail; `/code-review` again after any `/simplify` pass.

### Claude's Discretion
- Exact names of the region and patch dataclasses, the masked-field report shape, the internal layout of `splice.py`, and how the region map is exposed (a function on `LE` or in `splice.py`).
- Whether the region map distinguishes padding between the loader/fixup sections and the data pages as its own region (it must tile the file either way).

### Deferred Ideas (OUT OF SCOPE)
- Matching SMKP.EXE functions (compiler ID, split, pilot): stays v2 (SMKP-01). Only its round trip is in Phase 3.
- A full LE rewrite or relinkable build (LE-01, v2). Reopen trigger: a matched function changes size.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RT-01 | The rebuild reassembles each EXE from decomposed parts (untouched prefix regions plus per-object images re-paged through the LE page map), not from a file copy | Region map (below, "Measured layout"); `assemble()` that never sees the original buffer (Pattern 3); permuted-page-map fixture; obj1 page tails past vsize are non-zero in the synthetic fixture so a vsize-truncating rebuild fails (Pitfall B) |
| RT-02 | A splice API writes bytes at a linear address into a copy of the original and refuses writes outside page data and any change of file length; straddling fields are handled in flat address space | Writable-span model (Pattern 1), masking algorithm (Pattern 2), refusal list (D-03 mapping), measured BSS-straddling fixup in every short last page (Pitfall A) |
| RT-03 | A CLI verb rebuilds UFO2P.EXE, TACP.EXE and SMKP.EXE into `build/` and checks the whole-EXE SHA-1 against `config/targets.toml`; `cmp` against `orig/` is silent | CLI/ninja integration points (Pattern 4), `targets` API (all `[[targets]]` are LE; `module` is optional), in-memory prototype reproduced all three SHA-1 prefixes this session |
| RT-04 | Negative tests prove the gate can fail: a one-byte mutation (mid-page, page edge, short last page, across a page boundary) changes the SHA-1 and the failure names the offset | Test design in Validation Architecture; fixture extensions (`trailer=`, `page_numbers=`, custom fixups); D-08 diff report via `region_at()` |
| RT-05 | A byte-region map tiles every byte of each file (extender, MZ stub, LE header/loader section, fixup section, padding, pages, 27-byte trailer) and the LE edge cases on the real files are confirmed and documented (page types, straddling fixups, trailer) | Measured region boundaries for all three files; doc facts list for `docs/toolchain.md`; spike-confirm list |
</phase_requirements>

## Project Constraints (from CLAUDE.md and .claude/rules/)

- Never commit `orig/`, `asm/`, `build/`, `third_party/`; never modify `orig/`, the hash manifests under `config/`, or build scripts to make a check pass. [VERIFIED: CLAUDE.md]
- A matched function stays byte-identical; no inline asm to force a match (not exercised in Phase 3). [VERIFIED: CLAUDE.md]
- Done gate for tooling: `uv run pytest -q && uv run ruff check .` green on the host **and** in `docker compose run --rm test`. [VERIFIED: CLAUDE.md]
- Python 3.14 via uv; TDD (failing pytest first); no third-party dependency without a reason in `docs/tools.md` (Phase 3 needs none). [VERIFIED: .claude/rules/tools.md]
- `tools/` is GPLv3; keep the KKND-Decomp CC0 derivation header on derived files (`splice.py` gets the same style header as `le.py` line 1). [VERIFIED: .claude/rules/tools.md, le.py:1]
- Tests never embed game bytes; real-file tests skip unless `orig/` is present. [VERIFIED: .claude/rules/tools.md]
- Shallow nesting (generators/helpers, early `continue`); named binary-format offsets derived from each other; `next(..., None)`; error context added in one place; reuse existing dataclasses; refactors pinned by tests proven to fail; `/code-review` after `/simplify`. Fixture builders (`tests/conftest.py`) keep their own literals so the tests check the reader against the format. [VERIFIED: docs/coding-style.md "Python tooling"]
- ruff rules E, F, I, UP, B; line length 100. [VERIFIED: pyproject.toml `[tool.ruff]`]
- GSD owns phase sequencing; superpowers owns TDD and verification-before-completion inside the phase. Claude Code only. [VERIFIED: .claude/rules/workflow.md]
- `docs/toolchain.md` "Getting the Watcom compilers" section belongs to PR #1's author: do not edit it. [VERIFIED: 03-CONTEXT.md canonical_refs]

## Summary

Phase 3 is a pure-stdlib job on top of the existing read-only LE parser. Everything needed to tile the file and map linear addresses to file offsets is already parsed by `le.py`; nothing new must be decoded except (optionally) four header fields used only to refuse files whose non-resident-name table or debug info would otherwise be silently swallowed by the "trailer" region. The real-file scan run this session (read-only, through `le.py`) confirms the CONTEXT facts and adds three that change the design: (1) the LE header's *loader section size* in these wlink outputs **includes** the fixup section (loader section and fixup section end at the same byte); (2) in all three files, the code object's last page carries 0x523 / 0xAB1 / 0xC80 bytes of page data **past the object's vsize** (all zero bytes), so a rebuild that sizes object images by vsize (e.g. from `load_flat()`) only works by accident; (3) in all three files, exactly **one off32 fixup field in the short last page runs past the end of page data into BSS** (3 bytes backed + 1 in UFO2P/TACP, 2 + 2 in SMKP). An in-memory decompose/reassemble prototype reproduced the manifest SHA-1 prefix of all three files in about 30 ms each.

The design that satisfies D-01..D-16 is: `layout(le)` returns a sorted list of `Region`s that tiles `[0, len(file))`; `splice(le, patches)` decomposes the file into per-object page-backed images, applies linear-address patches into those images (refusing anything outside the writable spans, masking fixup fields from the de-duplicated `le.fixups()` list), then calls an `assemble(size, pieces)` function that writes every region from its own source into a fresh `bytearray(size)` and never sees the original buffer. `rebuild` = `splice(le, {})` + write `build/<NAME>` + `targets.hash_file` + compare with the manifest; on mismatch it reports first differing offset, its region (via `region_at`) and the differing-byte count. The proof that it is "rebuilt, not copied" comes from three tests a copy-only implementation cannot pass: a permuted page map, a patch that must appear at the page-mapped file offset, and an `assemble()` whose signature has no access to the original.

**Primary recommendation:** Put `Region`, `layout`, `region_at`, `MaskedField`, `SpliceResult`, `SpliceError(LEError)`, `splice` and the rebuild/diff reporting in `tools/reverseapoc/splice.py`; add only read helpers to `le.py` (`check_loadable` made public, `pages_end`/trailer reporting, and optionally named constants for the non-resident-name/debug fields); add `rebuild` to `cli.py` and a phony `verify` edge to `configure.py`.

## Architectural Responsibility Map

The project has no web tiers; the "tiers" are the tool modules.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Parse header, objects, page map, fixups | `le.py` (read-only parser) | — | D-05: le.py stays a parser; already parses all inputs needed |
| Trailer offset/length/SHA-1 in `summary()` | `le.py` (read helper) | `cli.py parse-le` | D-11; pure read of existing fields |
| Byte-region map, tiling check, offset -> region | `splice.py` | — | Claude's discretion; consumed only by splice/rebuild and its diff report |
| VA -> (object, page, file offset), writable spans | `splice.py` | `le.py` (`pages`, `objects`, `page_va`) | Write-path logic stays out of le.py |
| Fixup-field masking + report | `splice.py` | `le.py` (`fixups()`, `SRC_SIZE`) | D-02; uses the de-duplicated list only |
| Reassembly into a fresh buffer | `splice.py` (`assemble`) | — | D-16 |
| Rebuild, hash, compare, write `build/<NAME>` | `splice.py` (`rebuild_target`, result `.format()`) | `targets.py` (`load_manifest`, `hash_file`, `check_target`) | Mirrors `targets.check_orig` + `CheckReport.format()` pattern; keeps cli thin |
| CLI verb `rebuild` | `cli.py` | — | D-06 |
| Ninja `verify` edge | `configure.py` | — | D-09 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`struct`, `hashlib`, `bisect`, `dataclasses`, `pathlib`, `json`, `argparse`) | 3.14.5 | All of Phase 3 | Project rule: no third-party dependency without a recorded reason; `pyproject.toml` has `dependencies = []` [VERIFIED: pyproject.toml; `uv run python --version` -> 3.14.5] |
| pytest | 9.1.1 | Tests | Already the project test framework [VERIFIED: `uv run pytest --version`] |
| ruff | 0.17.1 | Lint | Already configured [VERIFIED: `uv run ruff --version`] |

### Supporting (existing in-repo modules to reuse)
| Module | What to reuse | When |
|--------|---------------|------|
| `reverseapoc.le` | `LE`, `LEObject`, `LEPage`, `Fixup`, `LEError`, `LEUnsupportedError`, `SRC_SIZE`, `PAGE_PHYSICAL`, `fixups()`, `page_va()`, `_check_loadable` (make public) | Everywhere in splice.py |
| `reverseapoc.targets` | `load_manifest`, `Target`, `hash_file`, `FileHashes`, `check_target`, `DEFAULT_MANIFEST`, `DEFAULT_ORIG`, `REPO_ROOT` | rebuild and real-file tests |
| `tests/conftest.py` | `build_le_image`, `SyntheticLE`, `fixup_record`, `page_fill`, `write_manifest`, `ORIG_DIR` | Synthetic and CLI tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-place splice into page images | Theme Hospital `lewrite.py` full rewrite | Locked out: Pitfall 21 / LE-01 deferred |
| `bytearray(le.data)` then overwrite (KKND exactly) | fresh `bytearray(size)` + per-region pieces | KKND's form is tautological (Pitfall 1); D-16 locks the fresh-buffer form |

**Installation:** none (no new packages).

## Package Legitimacy Audit

No external packages are installed in this phase (stdlib only; pytest and ruff are already locked in `uv.lock`).

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| (none) | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Measured layout of the real files (read-only scan, 2026-10-20)

Method: `uv run --no-sync python` scripts in the session scratchpad importing `reverseapoc.le` and reading `orig/*.EXE`; only offsets, lengths, counts, the first 4 trailer bytes and SHA-1 prefixes were printed. Nothing was written. All values below are [VERIFIED: local scan through tools/reverseapoc/le.py]. The spike (D-10, "LE edge cases") should re-confirm them before they become hard-coded regression facts.

### Header fields used (offsets relative to the LE header)

What `le.py` already reads, quoted verbatim [VERIFIED: tools/reverseapoc/le.py:195-209]:

```python
        self.num_pages = h(0x14)
        self.eip_obj, self.eip = h(0x18), h(0x1C)
        self.esp_obj, self.esp = h(0x20), h(0x24)
        self.page_size = h(0x28)
        self.last_page_size = h(0x2C)
        self.fixup_section_size = h(0x30)
        self.loader_section_size = h(0x38)
        self.object_table_offset = self.le_offset + h(0x40)
        self.num_objects = h(0x44)
        self.page_map_offset = self.le_offset + h(0x48)
        self.fixup_page_table_offset = self.le_offset + h(0x68)
        self.fixup_record_table_offset = self.le_offset + h(0x6C)
        # Unlike the other table offsets, the data-pages offset is relative to the MZ stub that
        # owns this LE header (0x352A4 in UFO2P/TACP, behind the bound DOS/4GW loader).
        self.data_pages_offset = self.stub_offset + h(0x80)
```

Field names per the IBM/Microsoft LE/LX layout [ASSUMED: training knowledge; each field's meaning was cross-checked below by sizes and offsets adding up on all three files]:

| Field offset | Spec name | Needed for | UFO2P | TACP | SMKP |
|---|---|---|---|---|---|
| 0x14 | number of pages (module pages) | page count | 0x12F (303) | 0x29A (666) | 0x15 (21) |
| 0x28 | page size | 4096 | 0x1000 | 0x1000 | 0x1000 |
| 0x2C | bytes on last page | short last page | 0x27F | 0x53B | 0xFF8 |
| 0x30 | fixup section size | fixup region | 0x39E4C | 0x31C78 | 0x3F40 |
| 0x38 | loader section size | consistency check | 0x3A342 | 0x32719 | 0x3FCD |
| 0x40 | object table offset | end of LE header region | 0xC4 | 0xC4 | 0xC4 |
| 0x4C | object iterated data map offset | must be 0 | 0 | 0 | 0 |
| 0x68 | fixup page table offset | start of fixup region | 0x5BA | 0xB65 | 0x151 |
| 0x6C | fixup record table offset | (le.py) | 0xA7A | 0x15D1 | 0x1A9 |
| 0x70 / 0x78 | import module / import procedure name table offsets | inside fixup section | 0x3A405 / 0x3A405 | 0x327DC / 0x327DC | 0x4090 / 0x4090 |
| 0x80 | data pages offset (relative to the owning MZ stub) | start of pages | 0x3D200 | 0x35600 | 0x6E00 |
| 0x88 / 0x8C | non-resident name table offset / length | must be 0 (else not tiled) | 0 / 0 | 0 / 0 | 0 / 0 |
| 0x98 / 0x9C | debug info offset / length | must be 0 (else not tiled) | 0 / 0 | 0 / 0 | 0 / 0 |

Measured relationships (all three files):
- `object_table_offset + loader_section_size == fixup_page_table_offset + fixup_section_size`: in these wlink outputs the declared loader section **includes** the fixup section. The non-fixup loader tables are `[object_table_offset, fixup_page_table_offset)` (0x4F6 / 0xAA1 / 0x8D bytes). Do not model "loader section" and "fixup section" as two consecutive regions of the declared sizes; that double-counts the fixups and the tiling check fails.
- `fixup_page_table_offset + 4 * (num_pages + 1) == fixup_record_table_offset` (the page table has `num_pages + 1` entries).
- Fixup records end 1 byte before the fixup section ends; that byte is the (empty) import procedure name table (import module and procedure name table offsets coincide; 0 import modules).
- Data-pages offset (relative to stub) is 0x200-aligned in all three files; the gap between fixup-section end and data pages is **padding of all-zero bytes**: 362 (UFO2P), 403 (TACP), 223 (SMKP).
- Page map is the identity (logical page *i* -> physical page *i*), every page flag is 0 (physical), physical numbers are unique.
- First MZ `e_lfanew` points past EOF in all three (as in the synthetic fixture); the owning stub's `e_lfanew` is 0x2C90 in all three, so the Watcom MZ stub region is 0x2C90 = 11,408 bytes.

### Region boundaries (file offsets, half-open)

| Region | UFO2P.EXE (0x1A073E = 1,705,790) | TACP.EXE (0x303DFA = 3,161,594) | SMKP.EXE (0x4244C = 271,436) |
|---|---|---|---|
| extender (bound DOS/4GW) | [0, 0x352A4) | [0, 0x352A4) | [0, 0x26654) |
| MZ stub | [0x352A4, 0x37F34) | [0x352A4, 0x37F34) | [0x26654, 0x292E4) |
| LE header | [0x37F34, 0x37FF8) = 196 B | [0x37F34, 0x37FF8) = 196 B | [0x292E4, 0x293A8) = 196 B |
| loader tables (object table .. entry table) | [0x37FF8, 0x384EE) | [0x37FF8, 0x38A99) | [0x293A8, 0x29435) |
| fixup section (page table, records, import tables) | [0x384EE, 0x7233A) | [0x38A99, 0x6A711) | [0x29435, 0x2D375) |
| padding (all zero) | [0x7233A, 0x724A4) = 362 B | [0x6A711, 0x6A8A4) = 403 B | [0x2D375, 0x2D454) = 223 B |
| pages 1..N | [0x724A4, 0x1A0723) | [0x6A8A4, 0x303DDF) | [0x2D454, 0x4244C) |
| trailer | [0x1A0723, EOF) = 27 B, starts `64 00 9b ff`, sha1 `33a69cac…` | [0x303DDF, EOF) = 27 B, starts `64 00 9b ff`, sha1 `28ad5c45…` | none (length 0) |

### Objects, page backing and BSS

| | UFO2P | TACP | SMKP |
|---|---|---|---|
| obj1 base / vsize / pages | 0x10000 / 0xBFADD / 1..192 | 0x10000 / 0xC254F / 1..195 | 0x10000 / 0x11380 / 1..18 |
| obj1 page-backed bytes | 0xC0000 (VA end 0xD0000) | 0xC3000 (VA end 0xD3000) | 0x12000 (VA end 0x22000) |
| obj1 page bytes **past vsize** | 0x523, all zero | 0xAB1, all zero | 0xC80, all zero |
| obj2 base / vsize / pages | 0xD0000 / 0x181E20 / 193..303 | 0xE0000 / 0x25F0B0 / 196..666 | 0x30000 / 0xFA70 / 19..21 |
| obj2 page-backed bytes | 0x6E27F (VA end 0x13E27F) | 0x1D653B (VA end 0x2B653B) | 0x2FF8 (VA end 0x32FF8) |
| obj2 BSS (vsize past page data) | 0x113BA1 | 0x88B75 | 0xCA78 |
| object holding the short last physical page | obj2 | obj2 | obj2 |

Note that UFO2P obj1's page-backed VA end (0xD0000) equals obj2's base: page-backed spans of different objects can be VA-contiguous, so a patch must not be allowed to run from one object into the next.

### Fixups

| | UFO2P | TACP | SMKP |
|---|---|---|---|
| de-duplicated fixups | 28,197 (off32 28,183, sel16 10, ptr16:32 4) | 24,438 (off32 24,424, sel16 10, ptr16:32 4) | 2,297 (off32 only) |
| rel32 fixups | 0 | 0 | 0 |
| overlapping fixup fields | 0 | 0 | 0 |
| fields crossing an object end | 0 | 0 | 0 |
| page-straddling fields | 14, all off32, all in obj1 | 11, all off32, all in obj1 | 2, off32, obj1 |
| straddler source VAs | 0x1EFFD 0x28FFD 0x36FFE 0x62FFF 0x67FFE 0x6AFFE 0x7FFFF 0x98FFF 0x9FFFF 0xA3FFE 0xB0FFD 0xB4FFF 0xC6FFD 0xC8FFF | 0x39FFD 0x3BFFF 0x42FFD 0x43FFE 0x52FFD 0x6DFFE 0x89FFD 0x8AFFF 0x9EFFD 0xA8FFD 0xB8FFD | 0x11FFD 0x1CFFE |
| ptr16:32 fields (6 bytes) | 0x1352B4 0x135328 0x13539C 0x135410 (obj2) | 0x2AC494 0x2AC508 0x2AC57C 0x2AC5F0 (obj2) | none |
| fixups inside the short last page | 77 | 107 | 33 |
| **fields running past the end of page data (into BSS)** | **1**: off32 at 0x13E27C, 3 bytes backed + 1 in BSS, target obj1 | **1**: off32 at 0x2B6538, 3 + 1, target obj1 | **1**: off32 at 0x32FF6, 2 + 2, target obj1 |

The last row is new: wlink trimmed the trailing zero bytes of the last page (`last_page_size`), cutting through a fixup field whose high byte(s) are zero. The loader writes all 4 bytes into zero-filled BSS at load time. Consequences: masking must clip each field to page-backed bytes; a field is not "inside page data" just because its `src_va` is; Phase 5's target-object cutter must not read `size` bytes from the page at that field. Straddler VAs are addresses only (no bytes) and may be used as a regression fixture per Pitfall 3.

### Prototype check (in memory, nothing written)

Decompose each file into: prefix `[0, data_pages_offset)`, per-object images of `page_count * page_size` bytes filled from pages through the page map, and the trailer; reassemble into `bytearray(len(file))`. Result: SHA-1 prefixes `e7488bf3`, `48ef0096`, `efdcf2a5`, matching the manifest values quoted in CONTEXT; about 30 ms per file plus about 0.15 s for `fixups()`; a naive `sum(a != b ...)` diff count over 3 MB takes about 0.2 s. [VERIFIED: local run]

## Architecture Patterns

### System Architecture Diagram

```
config/targets.toml --load_manifest--> [Target...] --(--exe filter)--> per target:
                                                                         |
orig/<NAME> --check_target (refuse bad input)--> LE(path) ----------------+
                                                   |
                         +-------------------------+----------------------------+
                         v                         v                            v
                  layout(le) -> [Region]     object images              le.fixups() (dedup, sorted)
                  check_tiling(size)         (page-backed, via              |
                  check_loadable(pages)       page map, per object)         |
                         |                         |                            |
                         |          patches {va: bytes} (Phase 3: {}) ----------+
                         |                         v                            |
                         |               resolve each patch to writable spans --+--> mask fixup fields
                         |               (refuse: unbacked VA, BSS, cross-object,     (restore original
                         |                overlap with another patch, empty)           bytes; MaskedField list)
                         |                         |
                         +-----------> pieces: non-page regions from original bytes,
                                       page regions from (patched) object images,
                                       trailer from original
                                                   v
                                     assemble(size, pieces) -> fresh bytes (no access to original)
                                                   v
                                write build/<NAME> (never under orig/) -> hash_file -> FileHashes
                                                   v
                         sha1 == manifest ? OK : MISMATCH(first diff offset vs orig, region_at, diff count)
                                                   v
                                    text line per EXE / --json ; exit 0 or 1
```

### Recommended Project Structure
```
tools/reverseapoc/
├── le.py          # + check_loadable (public), pages_end, trailer in summary()/format_summary
├── splice.py      # NEW: Region, layout, check_tiling, region_at, MaskedField, SpliceResult,
│                  #      SpliceError, splice, assemble, RebuildResult, rebuild_target
└── cli.py         # + rebuild subcommand
configure.py       # + rule rebuild / build verify: phony
tests/
├── conftest.py    # + trailer=, page_numbers= options on build_le_image
├── test_splice.py         # NEW: synthetic region map, splice, masking, refusals, reassembly
├── test_splice_real.py    # NEW: real-file tiling, round trip, regression facts, control mutation
├── test_le.py / test_cli.py / test_configure.py   # extended
docs/toolchain.md  # LE layout section corrected (RT-05)
```

### Pattern 1: Writable spans (VA -> image offset -> file offset)

**What:** Precompute one span per logical page: `(va_start, va_end, obj, page, image_offset)`, where `va_start = page_va(logical)`, `image_offset = (logical - obj.page_index) * page_size`, and `va_end = min(va_start + page.size, obj.end)`. Sort by `va_start`; resolve a patch `[va, va+n)` by `bisect` and walking consecutive spans. Every byte must fall in a span of the same object as the first byte; otherwise raise `SpliceError` naming the patch, the first unwritable address and the reason.

**Why `min(..., obj.end)`:** it makes "BSS past the last page" (VA beyond page data) and "page tail past vsize" (page data beyond the object) both unwritable, and makes a whole-object patch exactly `min(vsize, page-backed bytes)` long. The page tail past vsize is still carried into the output because the object image is initialised from the full page (`page.size` bytes), not from vsize. This tail refusal goes slightly beyond D-03's literal list; see Open Question 1.

**Reasons to report (D-03):**
- VA in `[obj.base + backed, obj.end)` -> "BSS of object M (past its page data)";
- VA in `[obj.end, obj.base + backed)` -> "past the end of object M (vsize …) in its last page";
- VA in no object -> "not in any object";
- run continues into a different object -> "crosses from object 1 into object 2";
- empty patch -> "empty patch" (recommended refusal; Claude's discretion).

The file-level regions (header, stub, extender, loader, fixups, padding, trailer) have **no VA**, so linear-address patches cannot reach them by construction. Make that explicit with a defence-in-depth check after assembly: every non-page region of the output equals the original bytes (cheap; raises `SpliceError` if a bug ever violates it). Non-physical pages are refused before any patch is applied by calling the public `check_loadable(obj, page)` for every page in `layout()` (D-03 third bullet).

**Helpers to add to le.py (read-only, D-05):**
- rename `_check_loadable` -> `check_loadable` (keep `load_flat` calling it; existing tests `test_non_physical_pages_fail_loudly`, `test_iterated_page_message`, `test_truncated_page_data` pin it);
- `pages_end` property: `data_pages_offset + (num_pages - 1) * page_size + last_page_size` (0 pages -> `data_pages_offset`);
- trailer in `summary()`: `{"offset": pages_end, "length": max(0, len(data) - pages_end), "sha1": ...}` and a `trailer` row in `format_summary` (D-11). Clamp rather than raise so `summary()` keeps working on the truncated fixture (`test_truncated_page_data` only expects `load_flat()` to raise);
- optional: named constants and attributes for the non-resident-name table (0x88/0x8C) and debug info (0x98/0x9C), so `layout()` raises `LEUnsupportedError` when they are non-zero instead of folding them into "trailer". If added, use names such as `_HDR_NONRES_NAMES_LEN = 0x8C` (D-17); do not refactor le.py's existing bare offsets in this phase unless pinned first (they are pre-existing and covered by `test_header_fields`).

### Pattern 2: Fixup-field masking (D-02)

**What:** Take `fixups = le.fixups()` once (it returns a fresh list per call, sorted by `src_va`; straddlers appear once [VERIFIED: le.py:315-320, 340-343]). Build `srcs = [f.src_va for f in fixups]`. For a resolved patch run `[lo, hi)`: start at `bisect_left(srcs, lo - MAX_FIELD + 1)` with `MAX_FIELD = max(SRC_SIZE.values())` (6, ptr16:32), iterate while `src_va < hi`, keep those with `src_va + size > lo`. For each, the masked VA range is `[max(lo, src_va), min(hi, src_va + size, backed_end))`; after writing the patch into the image, copy the original image bytes back over that range. Doing it per patch in VA space (not per page) masks both halves of a straddling field.

Field sizes are quoted verbatim [VERIFIED: tools/reverseapoc/le.py:34-49]:
```python
SRC_BYTE = 0x00
SRC_SEL16 = 0x02
SRC_PTR1616 = 0x03
SRC_OFF16 = 0x05
SRC_PTR1632 = 0x06
SRC_OFF32 = 0x07
SRC_REL32 = 0x08
SRC_SIZE = {
    SRC_BYTE: 1,
    SRC_SEL16: 2,
    SRC_PTR1616: 4,
    SRC_OFF16: 2,
    SRC_PTR1632: 6,
    SRC_OFF32: 4,
    SRC_REL32: 4,
}
```

**Report shape (recommended):** `MaskedField(fixup: Fixup, patch_va: int, start: int, end: int)` with properties `partial` (patch covers only part of the field), `straddles_page` (the field's first and last byte are in different pages) and `clipped` (field runs past page data, the measured last-page case). Report every field the patch covers, whether or not the patch bytes differ from the original (deterministic; Phase 5's relocation check judges targets). `SpliceResult(data: bytes, masked: list[MaskedField])`. The CLI prints only the count. Never put byte values in the report.

### Pattern 3: Reassembly that cannot copy (D-16)

```python
# Shape only; names are Claude's discretion.
def assemble(size: int, pieces: Iterable[tuple[int, bytes]]) -> bytes:
    out = bytearray(size)                 # fresh buffer, zero-filled
    pos = 0
    for offset, chunk in sorted(pieces):  # must tile [0, size) exactly
        if offset != pos:
            raise SpliceError(f"region gap/overlap at {min(offset, pos):#x}")
        out[offset : offset + len(chunk)] = chunk
        pos = offset + len(chunk)
    if pos != size:
        raise SpliceError(f"regions end at {pos:#x}, file is {size:#x} bytes")
    return bytes(out)
```

`splice()` builds the pieces: for each non-page `Region`, `le.data[r.start:r.end]`; for each page region, `image[obj][k*page_size : k*page_size + page.size]` placed at `page.file_offset`. `assemble()` takes no `LE` and no original buffer, so "return the original" is not expressible in it. Coverage is proven twice: `check_tiling(layout(le), len(le.data))` on the region list, and `assemble()`'s own exact-tiling check on the pieces.

Tests that a copy-only implementation fails (each one is required):
1. **Permuted page map.** Build a synthetic LE whose page map swaps logical pages 1 and 2 (`page_numbers=(2, 1, 3)`). A patch at VA 0x10010 must change file bytes inside physical page 2's file range, not page 1's. Real files have an identity page map, so only this fixture catches "file offset computed from the logical page number".
2. **Mutation lands at the mapped offset only.** For each D-13 case, `diff(splice(le, {va: b}).data, le.data)` equals exactly the expected set of file offsets.
3. **Pieces are sourced, not copied.** Call `assemble()` with page pieces from images filled with a marker and non-page pieces from the original: every page byte equals the marker, every non-page byte equals the original. A copy fails.
4. **Page tail past vsize.** In the synthetic fixture obj1 has vsize 0x1800 over two 0x1000 pages, so page 2's last 0x800 bytes lie past vsize and are filled with `page_fill(2)` = 0x22 (non-zero). A rebuild that sizes images by vsize (e.g. builds them from `load_flat()`) zeroes them and fails the round trip. On the real files that bug would pass, because the tails are all zero.

### Pattern 4: CLI and ninja integration

- `cli.py`: add `p = sub.add_parser("rebuild", ...)`, reuse the local `orig_and_manifest(p)` helper, add `--out` (default `REPO_ROOT / "build"`), `--exe NAME`, `--json`, and `p.set_defaults(func=_cmd_rebuild)`. `_cmd_rebuild` returns 0/1 like `_cmd_check_orig`. `SpliceError(LEError)` is already caught by `main()`, quoted verbatim [VERIFIED: tools/reverseapoc/cli.py:158]: `except (IngestError, LEError, ManifestError, ISOError, WatcomError, OSError) as exc:`. No change to the tuple is needed if every new error subclasses `LEError` or `ManifestError`. Keep the PR #1 watcom commands (`_add_watcom_commands(sub)`); update the module docstring list of verbs.
- **Which targets are "LE targets":** `Target.module` is optional, quoted verbatim [VERIFIED: tools/reverseapoc/targets.py:33-42]: `name: str`, `path: str`, `size: int`, `md5: str`, `sha1: str`, `crc32: int | None = None`, `module: str | None = None`, `description: str = ""`. SMKP has no `module` [VERIFIED: config/targets.toml]. The manifest header says "All three are Watcom C/C++ 32-bit programs bound with DOS/4GW Professional (LE format)" [VERIFIED: config/targets.toml], and `load_manifest` reads only `[[targets]]` (the `[[cd_builds]]` table is documentation only). Recommendation: **every `[[targets]]` entry is an LE target**; do not key on `module`, and do not edit `config/targets.toml` (hard rule). A target whose file does not parse raises `LEError` naming the file. `--exe` matches `Target.name` (recommend case-insensitive, since Windows users type `ufo2p.exe`); an unknown name is an error listing the known names.
- **Input check:** run `targets.check_target(target, orig/<name>)` first. Status `missing` -> `MISSING` line, exit 1 (as `check-orig` does). Status `mismatch` -> refuse to rebuild ("orig/X does not match the manifest; run check-orig"); otherwise a rebuilt-equals-orig-but-not-manifest case has no first differing offset to report.
- **Output guard:** refuse an `--out` that resolves to `orig/` or inside it (`out.resolve().is_relative_to(orig.resolve())`), and refuse a `Target.name` that is not a bare file name (`Path(name).name != name`), so nothing can be written under `orig/` or outside `--out`.
- **Diff report (D-08):** compare rebuilt bytes with `orig/<name>` bytes: first differing offset, `region_at(regions, offset).label()` (e.g. `page 17 of object 1, VA 0x00020abc` or `trailer`), and the differing-byte count. A one-line `OK  UFO2P.EXE  sha1 <sha1> == manifest`. `--json` prints a list of result objects (name, status, output path, sha1, expected sha1, first_diff {offset, region, va}, diff_bytes, masked_fields count). Hashing uses `targets.hash_file(out_path)` -> `FileHashes` (reuse, D-17).
- **Testing the mismatch path:** with no patch source in Phase 3, the CLI rebuild always reproduces a good orig. Give the library function a `patches` parameter (`rebuild_target(target, orig_dir, out_dir, patches=None)`) and test the mismatch report there; test the CLI mismatch path with `monkeypatch` on the patch provider, or through the "orig does not match manifest" refusal.
- `configure.py`: add to `HEADER`

  ```
  rule rebuild
    command = uv run reverseapoc rebuild
    description = REBUILD build/
    pool = console
  ```

  and in `render()` add `build $builddir/always/verify: rebuild` and `build verify: phony $builddir/always/verify` next to the `check-orig` lines (same "never written" output trick the header comment describes). Update the header comment's target list ("ninja verify  rebuild every target into build/ and check its SHA-1"). Keep the existing strings that `tests/test_configure.py` asserts (`Phase 5`, `builddir = build`, `build check-orig: phony`, `build parse-le: phony`). `default check-orig` can stay. Ninja is not installed on the host (`command -v ninja` empty); it is in the image (`ninja-build=1.11.1-2` in `docker/Dockerfile`), so the edge is checked by a render test plus a container run.

### Anti-Patterns to Avoid
- **`out = bytearray(le.data)` then overwrite (KKND verbatim):** passes every round trip trivially (Pitfall 1). D-16 forbids it.
- **Images from `load_flat()`:** truncates at vsize; correct on the real files only because the obj1 tails are zero.
- **Per-page masking or re-reading per-page fixup records:** masks half of a straddling field (Pitfall 3). Use `le.fixups()` only.
- **Region sizes from `loader_section_size` + `fixup_section_size` back to back:** double-counts the fixup section in these files.
- **File length from `num_pages * page_size`:** drops the trailer and overcounts the short page (Pitfall 2).
- **Hard-coding the manifest SHA-1s in tests (D-15):** read them via `load_manifest`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LE parsing, page map, fixup decode and straddle de-dup | a second parser in splice.py | `LE`, `LE.pages`, `LE.objects`, `LE.fixups()` | Already tested (`tests/test_le.py`, `tests/test_le_real.py`); a second reader drifts |
| Non-physical page refusal | new flag checks | `LE.check_loadable` (made public) | Same message and tests as `load_flat` |
| Whole-file hashing | ad-hoc hashlib loops | `targets.hash_file` -> `FileHashes` | D-17 reuse; same hashes as check-orig |
| Manifest parsing and input verification | TOML reading in cli | `targets.load_manifest`, `targets.check_target` | D-15; validated fields |
| Synthetic LE images | hand-written byte blobs in test_splice.py | `build_le_image` (extended) | One builder, format literals kept in conftest |
| Interval lookup | linear scans per byte | `bisect` over sorted span starts and fixup `src_va`s | 28k fixups x whole-object patches |

**Key insight:** every mapping fact (logical -> physical page, page -> file offset, field -> VA) already has exactly one implementation in `le.py`. Phase 3's risk is not parsing; it is writing a second, subtly different mapping that the identity page map and zero tails of the real files would never expose.

## Common Pitfalls

### Pitfall A: The fixup field that runs into BSS (new, measured)
**What goes wrong:** masking or a later target cutter reads or writes `fx.size` bytes at a field in the short last page and runs 1-2 bytes past page data.
**Why it happens:** wlink trims trailing zeros off the last page; one off32 field per file is cut.
**How to avoid:** clip every masked range to the span's page-backed end; add a synthetic fixture with an off32 at offset `LAST_PAGE_SIZE - 2` of the last page (2 bytes backed, 2 in BSS) and a real-file regression test asserting exactly one such field per file.
**Warning signs:** an `IndexError`/short slice at the end of an object image; a masked range longer than the page data.

### Pitfall B: Page tail past vsize is real page data
**What goes wrong:** rebuild sizes object images by vsize, so the tail bytes are zero in the output.
**How to avoid:** images are `page_count * page_size` bytes initialised from each page's full `page.size`; the synthetic tail (0x800 bytes of 0x22) catches the bug.

### Pitfall C: Identity page map hides logical/physical confusion
**What goes wrong:** `data_pages_offset + (logical - 1) * page_size` passes on all three real files.
**How to avoid:** `page_numbers=` fixture option and a permuted-map test (Pattern 3, test 1). Use `LEPage.file_offset`, never recompute it.

### Pitfall D: VA-contiguous objects
**What goes wrong:** in UFO2P, obj1's page-backed span ends at 0xD0000, obj2's base; a patch walking spans by VA alone silently continues into obj2.
**How to avoid:** a resolved run must stay inside the object of its first byte; refuse with "crosses from object 1 into object 2".

### Pitfall E: Zero-length regions
**What goes wrong:** SMKP has no trailer; the unbound synthetic fixture has no extender. A zero-length region breaks `region_at` or the tiling check.
**How to avoid:** `layout()` omits zero-length regions; `parse-le` still reports trailer length 0 (D-11).

### Pitfall F: Tautological real-file test (Pitfall 1 of the research)
**What goes wrong:** the only real-file test is "rebuild == orig".
**How to avoid:** add the D-13 real-file control: splice one byte mid-page in UFO2P, assert the SHA-1 differs from the manifest, the reported first offset equals `page.file_offset + delta` and the region names that page and VA; then `splice(le, {})` again equals the manifest SHA-1.

### Pitfall G: Writing outside build/ during tests
**What goes wrong:** a test calls `main(["rebuild"])` with defaults: writes `/work/build/` in the container and fails in CI without `orig/`.
**How to avoid:** tests always pass `--orig`, `--manifest`, `--out tmp_path`. Real-file tests use `tmp_path` for outputs; the `build/` write is exercised by the manual/ninja verify step.

### Pitfall H: Real-file skip granularity
**What goes wrong:** `tests/test_le_real.py` skips the whole module unless UFO2P and TACP exist; SMKP may be absent independently.
**How to avoid:** parametrize over the three names with a per-param `pytest.param(name, marks=pytest.mark.skipif(not (ORIG_DIR / name).is_file(), reason=...))`.

### Pitfall I: Game bytes in messages or artifacts
**What goes wrong:** an error or JSON field prints the differing bytes or the trailer.
**How to avoid:** offsets, lengths, counts, region labels and SHA-1s only (D-11, D-12). Patch bytes come from compiled code in Phase 5, but original bytes at masked fields are game bytes: never include them.

## Code Examples

### Synthetic fixture extension (tests/conftest.py)
```python
# Extend build_le_image's keyword arguments (fixture literals stay in conftest):
def build_le_image(
    *,
    bound: bool = True,
    fixups: list[bytes] | None = None,
    page_flags: tuple[int, ...] = (0, 0, 0),
    page_numbers: tuple[int, ...] | None = None,  # physical page per logical page; default identity
    trailer: bytes = b"",                         # appended after the last page
    entry: tuple[int, int] = ENTRY,
) -> SyntheticLE:
    ...
    # page map: bytes([(n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF, flags])
    #           for n, flags in zip(page_numbers or range(1, num_pages + 1), page_flags)
    # pages are still written in physical order, each filled with page_fill(physical number);
    # the short page is the one with physical number == num_pages (le.py:281).
    # image += trailer;  SyntheticLE gains trailer_offset (= end of last page).
```
Existing behaviour the extension must keep (quoted verbatim [VERIFIED: tests/conftest.py:16-26]):
```python
PAGE_SIZE = 0x1000
LAST_PAGE_SIZE = 0x200
OUTER_STUB_SIZE = 0x180  # fake "bound extender" MZ in front of the MZ that owns the LE header
INNER_LFANEW = 0x80  # e_lfanew of the owning MZ (relative to that MZ)
LE_HEADER_SIZE = 0xC4  # object table follows the header, as wlink lays it out

# (vsize, base, flags, first logical page, page count)
OBJECTS = [
    (0x1800, 0x10000, 0x2045, 1, 2),  # code: readable, executable, big
    (0x3000, 0x20000, 0x2043, 3, 1),  # data: readable, writable, big; tail is bss
]
```
Measured on the default (bound) fixture this session: extender [0, 0x180), stub [0x180, 0x200), LE header [0x200, 0x2C4), loader tables [0x2C4, 0x300), fixups [0x300, 0x363), padding 29 bytes, pages at 0x380 / 0x1380 / 0x2380 (sizes 0x1000, 0x1000, 0x200), no trailer. So the fixture already has padding, a short last page, BSS (obj2 0x20200..0x23000), a page tail past vsize (obj1 0x11800..0x12000) and a straddling off32 at 0x10FFE. It lacks a trailer, a non-identity page map and a field running into BSS. Do not change `DEFAULT_FIXUPS`/`DEFAULT_DECODED` (pinned by `test_le.py`); pass custom `fixups=` in the new tests, e.g. page 3: `fixup_record(7, LAST_PAGE_SIZE - 2, 1, 0x10)` for the BSS-cut field.

### Fixture cases for D-13 (VAs in the default fixture)
| Case | Patch | Expected |
|---|---|---|
| mid-page | 1 byte at 0x10800 (no fixups: `fixups=[b"", b"", b""]`) | file offset `page_offsets[0] + 0x800` changes, nothing else; SHA-1 differs; report names page 1 of object 1, VA 0x10800 |
| last byte of page | 1 byte at 0x10FFF (no fixups) | offset `page_offsets[0] + 0xFFF` |
| first byte of next page | 1 byte at 0x11000 (no fixups) | offset `page_offsets[1]` |
| spanning boundary | 4 bytes at 0x10FFE (no fixups) | 2 bytes at end of physical page 1, 2 at start of page 2; with `page_numbers=(2, 1, 3)` they land in non-adjacent file ranges |
| short last page ok | 1 byte at 0x201FF | offset `page_offsets[2] + 0x1FF` |
| short last page refused | 1 byte at 0x20200 | `SpliceError` naming the patch, 0x20200, "BSS of object 2" |
| straddling fixup masked | 8 bytes at 0x10FFC (default fixups) | bytes 0x10FFE..0x11001 keep original; `MaskedField` for the off32 at 0x10FFE, `straddles_page` true |
| ptr16:32 masked | 8 bytes at 0x1101F (default fixups) | 6 bytes 0x11020..0x11025 keep original |
| overlap refused | {0x10800: 4 bytes, 0x10802: 4 bytes} | `SpliceError` naming both patches and 0x10802 (also when bytes are identical, D-04) |
| outside page data | VA 0x0FFFF, 0x11800 (obj1 past vsize), 0x30000 | `SpliceError` |
| non-physical page | `page_flags=(0, 1, 0)` | `LEUnsupportedError` from `check_loadable` before any patch |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| "page data runs exactly to EOF" (`docs/toolchain.md` Overlays row) | 27-byte trailer after the last page in UFO2P/TACP; none in SMKP | measured 2026-10-19, re-measured 2026-10-20 | Docs row and "To be confirmed in Phase 2/3" line must be replaced (RT-05) |
| KKND `out = bytearray(le.data)` splice | fresh buffer + per-region pieces | D-16 | Round trip can fail |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Spec names of LE header fields 0x30, 0x38, 0x4C, 0x70, 0x78, 0x88, 0x8C, 0x98, 0x9C | Measured layout | Constant names wrong; behaviour unaffected because the measured offsets and sizes are consistent on all three files |
| A2 | The trimmed last page and the BSS-cut off32 are wlink behaviour, not damage | Pitfall A | None for Phase 3 (bytes are carried, field clipped); the spike should confirm |
| A3 | Refusing writes past vsize in an object's last page (beyond D-03's list) is acceptable to the owner | Pattern 1 | If the owner wants D-03 literal (any page-backed byte writable), relax one check; whole-object patch length changes |
| A4 | Case-insensitive `--exe` matching is wanted | Pattern 4 | Cosmetic |
| A5 | Rebuild should refuse an `orig/` file that fails the manifest check rather than rebuild it | Pattern 4 | Owner may prefer rebuild-then-report; affects the mismatch message only |

## Open Questions

1. **Writes into the obj1 page tail past vsize.**
   - What we know: those bytes are page-backed (D-03's criterion says "backed by file page bytes"), all zero, outside the object (`obj_of_va` returns None).
   - What's unclear: whether D-03 intends them writable.
   - Recommendation: refuse ("past the end of object M"), carry them unchanged; record it in the plan as a stricter-than-D-03 choice for owner confirmation at plan review.
2. **Should `layout()` refuse non-zero non-resident-name/debug fields?**
   - Recommendation: yes (LEUnsupportedError), via named constants in le.py; costs a few lines and keeps "trailer" honest. Optional if the planner wants le.py untouched beyond `check_loadable`/trailer.
3. **Spike-confirmed facts the plan should treat as provisional:** all-physical pages and counts (303/666/21), identity page map, no iterated map, 14/11/2 straddlers (and their VAs), the one BSS-cut field per file, loader section including the fixup section, zero padding sizes, trailer offsets/lengths. Write tests so the generic properties (tiling, round trip, masking) do not depend on them, and put the specific numbers in `tests/test_splice_real.py` regression tests only after the spike's verdict.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (uv-managed) | everything | ✓ | 3.14.5 | — |
| pytest | tests | ✓ | 9.1.1 | — |
| ruff | lint gate | ✓ | 0.17.1 | — |
| Docker / compose | D-14 container run | ✓ | 29.6.2 | — |
| ninja | `ninja verify` | ✗ on host; ✓ in image (`ninja-build=1.11.1-2`) | — | run `uv run reverseapoc rebuild` directly on the host; `ninja verify` inside `docker compose run --rm build` |
| cmp | success criterion 1 | ✓ (Git Bash `/usr/bin/cmp`) | — | Python byte compare in the test |
| orig/UFO2P.EXE, TACP.EXE, SMKP.EXE | real-file tests | ✓ (owner's files) | manifest SHA-1 prefixes reproduced | tests skip in CI |

Current suite: `199 passed, 3 skipped` on the host (the 3 skips are container-only hygiene tests). [VERIFIED: `uv run pytest -q -rs`]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (`[tool.pytest.ini_options] testpaths = ["tests"]`, `pythonpath = ["."]`) |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest -q tests/test_splice.py` |
| Full suite command | `uv run pytest -q && uv run ruff check .` |
| Container command | `docker compose run --rm test` (orig/ mounted read-only; real-file tests run there) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RT-01 | Rebuild = assemble(pieces) from regions + page-mapped images; permuted page map lands right; page tail past vsize preserved; marker pieces show sources | unit (synthetic) | `uv run pytest -q tests/test_splice.py -k "assemble or permuted or tail or round_trip"` | ❌ Wave 0 |
| RT-01 | Real files round-trip to the manifest SHA-1 (read via `load_manifest`) through `splice(le, {})` | real-file | `uv run pytest -q tests/test_splice_real.py -k round_trip` | ❌ Wave 0 |
| RT-02 | Refusals: BSS, past vsize, no object, cross-object, overlap (incl. identical bytes), empty, non-physical page; length unchanged; non-page regions equal original | unit (synthetic) | `uv run pytest -q tests/test_splice.py -k "refuse or overlap or length or physical"` | ❌ Wave 0 |
| RT-02 | Masking: off32, straddling off32, ptr16:32, sel16, BSS-cut field; report contents | unit (synthetic) | `uv run pytest -q tests/test_splice.py -k mask` | ❌ Wave 0 |
| RT-02 | Real straddlers: a patch across each straddling field keeps original bytes and reports it (addresses from `le.fixups()`, not hard-coded bytes) | real-file | `uv run pytest -q tests/test_splice_real.py -k straddl` | ❌ Wave 0 |
| RT-03 | `rebuild` CLI: OK line, MISSING, input mismatch refusal, `--exe` filter and unknown name, `--json` shape, `--out` under orig refused, exit codes | unit (synthetic + `write_manifest`) | `uv run pytest -q tests/test_cli.py -k rebuild` | ❌ (file exists, tests new) |
| RT-03 | `verify` ninja edge rendered | unit | `uv run pytest -q tests/test_configure.py -k verify` | ❌ (file exists, test new) |
| RT-03 | Real rebuild into build/ and `cmp` silent | manual + container | `uv run reverseapoc rebuild && for f in UFO2P TACP SMKP; do cmp build/$f.EXE orig/$f.EXE; done`; `docker compose run --rm test`; `docker compose run --rm build ninja verify` (after `python configure.py`) | n/a |
| RT-04 | D-13 cases: mid-page, page edges, spanning, short last page ok/refused, fixup masked; SHA-1 differs; report names file offset, region and VA | unit (synthetic) | `uv run pytest -q tests/test_splice.py -k "mutation or edge or short_page"` | ❌ Wave 0 |
| RT-04 | Real-file control: one-byte mid-page mutation in UFO2P changes SHA-1, reported at `page.file_offset + delta` and that page's VA | real-file | `uv run pytest -q tests/test_splice_real.py -k control` | ❌ Wave 0 |
| RT-05 | `layout()` tiles synthetic files (bound, unbound, trailer, no trailer); `check_tiling` fails on an injected gap and overlap; `region_at` labels | unit | `uv run pytest -q tests/test_splice.py -k "layout or tiling or region_at"` | ❌ Wave 0 |
| RT-05 | `layout()` tiles each real file; regression facts after the spike (straddler counts 14/11/2, one BSS-cut field, trailer 27/27/0, all pages physical) | real-file | `uv run pytest -q tests/test_splice_real.py -k "layout or facts"` | ❌ Wave 0 |
| RT-05 | `parse-le` trailer line and JSON field (offset, length, sha1; length 0 without trailer) | unit | `uv run pytest -q tests/test_le.py tests/test_cli.py -k trailer` | ❌ (files exist, tests new) |
| RT-05 | `docs/toolchain.md` no longer says "runs exactly to EOF" or "To be confirmed in Phase 2/3" | doc check (hygiene-style test or manual grep) | `uv run pytest -q tests/test_hygiene.py -k toolchain` or `grep -n "runs exactly to EOF" docs/toolchain.md` (expect no output) | ❌ |
| D-15 | No manifest SHA-1 string appears under `tests/` | hygiene | `uv run pytest -q tests/test_hygiene.py -k manifest_hashes` | ❌ |

Real-file vs synthetic: every RT behaviour has a synthetic test that runs in CI; the real-file tests (`tests/test_splice_real.py`) add the round trip against the manifest, the control mutation, the straddler sweep and the measured facts, and skip per file when `orig/<name>` is absent.

### Sampling Rate
- **Per task commit:** `uv run pytest -q tests/test_splice.py` (plus the touched test file) and `uv run ruff check .`
- **Per wave merge:** `uv run pytest -q && uv run ruff check .`
- **Phase gate:** full suite on the host, `docker compose run --rm test`, `uv run reverseapoc rebuild` (three OK lines, exit 0), `cmp` silent for all three, `ninja verify` in the container, before `/gsd-verify-work 3`

### Wave 0 Gaps
- [ ] `tests/conftest.py`: `page_numbers=` and `trailer=` options on `build_le_image`, `trailer_offset` on `SyntheticLE`
- [ ] `tests/test_splice.py`: synthetic region map, splice, masking, refusals, reassembly, D-13 cases
- [ ] `tests/test_splice_real.py`: per-file skip, round trip, control mutation, straddler sweep, facts
- [ ] new tests in `tests/test_cli.py`, `tests/test_configure.py`, `tests/test_le.py`, `tests/test_hygiene.py`
- No framework install needed.

## Security Domain

`security_enforcement: true`, ASVS level 1 (`.planning/config.json`). The phase is an offline CLI over local files; no network, auth or sessions.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | partly (filesystem) | never write under `orig/` (resolve-and-compare guard), read-only `orig/` mount in Docker (already tested by `test_hygiene.py`) |
| V5 Input Validation | yes | bounds-checked parsing in `le.py` (`LEError` on truncation); `check_tiling` on regions; validate patch VAs/lengths; bare-filename check on manifest names used for output paths |
| V6 Cryptography | no | SHA-1 is used as an identity check against the manifest, not for security; `hashlib` via `targets.hash_file` |
| V12 Files and Resources | yes | output only under `--out` (default `build/`, gitignored); no path components from the manifest name |
| V7 Error Handling and Logging | yes | errors carry offsets/addresses/reasons only, never file bytes (Pitfall I) |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Output path escaping `build/` via a crafted target name (`../orig/UFO2P.EXE`) | Tampering | reject names where `Path(name).name != name`; refuse `--out` resolving into `orig/` |
| Overwriting the oracle input `orig/` | Tampering | guard above + read-only container mount |
| Malformed LE causing out-of-range slicing or silent truncation | Denial of service / Tampering | `LEError` bounds checks already in `le.py`; `check_loadable` truncation check; `assemble` exact-size check |
| Game bytes leaking through logs, JSON or docs | Information disclosure | report offsets, lengths, counts, labels and SHA-1s only; docs record first 4 trailer bytes + SHA-1 (D-12) |
| Agent editing the manifest to make the gate pass | Tampering (repudiation of the oracle) | hard rule in CLAUDE.md; tests read hashes via `load_manifest`, never copies (D-15) |

## Sources

### Primary (HIGH confidence)
- `tools/reverseapoc/le.py` (read in full): header fields, `LEPage`/`LEObject`/`Fixup`, `fixups()` de-dup, `load_flat`, `_check_loadable`
- `tools/reverseapoc/targets.py`, `tools/reverseapoc/cli.py`, `configure.py`, `config/targets.toml`, `pyproject.toml`, `docker/compose.yaml`, `docker/Dockerfile` (grep)
- `tests/conftest.py`, `tests/test_le.py`, `tests/test_le_real.py`, `tests/test_cli.py`, `tests/test_configure.py`, `tests/test_hygiene.py` (grep)
- Read-only scans of `orig/UFO2P.EXE`, `orig/TACP.EXE`, `orig/SMKP.EXE` through `le.py` (this session)
- `.planning/phases/03-byte-identical-round-trip/03-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md` (phase 3 section)

### Secondary (MEDIUM confidence)
- `.planning/research/PITFALLS.md` Pitfalls 1-3, 21; `.planning/research/ARCHITECTURE.md` C3-C5 and Patterns 1-2; `.planning/research/SUMMARY.md` Phase 3
- `docs/research/notes-own-pipeline-reuse-inventory.md` Q2, Q4 (KKND `build_kknd.py` description); `docs/toolchain.md` LE layout; `docs/coding-style.md` Python tooling; `docs/workflow.md`

### Tertiary (LOW confidence)
- LE/LX header field names (training knowledge, tagged [ASSUMED] above; offsets themselves verified by measurement)

No web, Context7 or search tools were used (source restriction for this phase).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (stdlib plus existing locked dev tools, versions probed)
- Architecture: HIGH (prototype reassembly reproduced all three SHA-1 prefixes; every integration point read)
- Pitfalls: HIGH for A-E (measured), MEDIUM for the interpretation of A (wlink trimming)

**Research date:** 2026-10-20
**Valid until:** stable (format and files do not change); re-check after the Phase 3 spikes
