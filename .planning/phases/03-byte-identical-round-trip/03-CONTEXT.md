# Phase 3: Byte-identical round trip - Context

**Gathered:** 2026-10-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Rebuild UFO2P.EXE, TACP.EXE and SMKP.EXE from their decomposed parts through a KKND-style in-place
page splice, so that `cmp` against `orig/` is silent and each SHA-1 equals `config/targets.toml`,
with a gate that is proven able to fail. The splice API built here is the primitive Phase 5 uses
to land matched functions, so it takes linear-address patches from day one. No compiler, no OMF,
no function split: Phase 3 is stdlib Python plus pytest on top of the existing `le.py`.

Requirements: RT-01..RT-05 (`.planning/REQUIREMENTS.md`).

</domain>

<decisions>
## Implementation Decisions

### Splice API
- **D-01:** The API takes linear-address patches, `splice(le, {va: bytes})`. Patches are applied in flat address space, so a patch may cross a page boundary and land in two pages. A whole-object rebuild is just one patch per object. — **Reversibility:** costly — Phase 5's landing step and the Phase 6 driver call this signature.
- **D-02:** Patch bytes that fall on an LE fixup field are not written. The field keeps the original link-time value, as in KKND's `build_kknd.py`. This includes the 14 (UFO2P) / 11 (TACP) / 2 (SMKP) page-straddling off32 fields. Splice reports which fields it masked. Phase 5's relocation check verifies targets separately.
- **D-03:** Splice refuses, with an error naming the patch, the address and the reason:
  - a write to any address not backed by file page bytes (LE header, loader and fixup tables, the DOS/4GW extender, the MZ stub, padding, the trailer, BSS past the last page);
  - any change of file length;
  - any page that is not physical (iterated, zero-filled, invalid). None exist today, but the code fails loudly instead of guessing.
- **D-04:** Splice refuses overlapping patches, naming both patches and the colliding address. It does this even when both write identical bytes. Rationale (owner, after an ELI5 of the trade-off): a function-boundary error must fail immediately where it happens, not later as a SHA-1 mismatch somewhere else.
- **D-05:** The code lives in a new module, `tools/reverseapoc/splice.py`, with the KKND-Decomp (CC0) derivation header used by `le.py`. `le.py` stays a read-only parser. It may gain small public read helpers, for example making `_check_loadable` public, but no write logic.

### Rebuild command and outputs
- **D-06:** The verb is `uv run reverseapoc rebuild`. Phase 5 reuses it once patches come from compiled functions; there is no separate `roundtrip` verb. — **Reversibility:** costly — the ninja edge, docs and Phase 6 driver will call it by name.
- **D-07:** By default it rebuilds every LE target in `config/targets.toml`: UFO2P.EXE, TACP.EXE and SMKP.EXE. `--exe NAME` restricts it to one. SMKP joins the round trip only, as a second layout without a trailer; it stays out of Phases 4-6, and SMKP-01 remains the v2 requirement for matching it. Outputs go to `build/<NAME>` (gitignored). Nothing is ever written under `orig/`.
- **D-08:** Output is one line per EXE, e.g. `OK  UFO2P.EXE  sha1 e7488bf3… == manifest`. On mismatch it reports:
  - the first differing file offset;
  - the region that offset falls in (page N of object M plus the VA, or header/stub/loader/fixups/padding/trailer);
  - the count of differing bytes.

  Exit code 1 on any mismatch. A `--json` flag prints the same result machine-readably for the Phase 6 driver.
- **D-09:** `configure.py` gains a phony `verify` edge that runs `uv run reverseapoc rebuild`, next to the existing `check-orig` and `parse-le` phony edges. This satisfies RT-03's "a CLI verb and a ninja target".

### The 27-byte trailer
- **D-10:** The trailer gets a time-boxed spike, then is treated as opaque. The spike spends about an hour on obvious hypotheses: a CRC/checksum over the file or the pages, an installer or patch stamp, a DOS/4GW bind record. The CD v1.00 build is a useful comparison. Whatever the verdict, the rebuild carries the trailer over unchanged as its own region, and nothing regenerates it.
- **D-11:** `parse-le` reports a trailer line and a JSON field, both carrying the offset, length and SHA-1 of the bytes after the last page. For SMKP the length is 0. It never prints the bytes.
- **D-12:** `docs/toolchain.md` records the trailer as offset, length, first 4 bytes and SHA-1 (e.g. "UFO2P: 27 bytes at 0x1A0723, starts 64 00 9B FF, sha1 …"). It never records the full bytes.

### Test and gate policy
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

### Code quality (rules merged with PR #1, apply to splice.py)
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and gates
- `.planning/ROADMAP.md` (Phase 3 section): goal, success criteria, spike line.
- `.planning/REQUIREMENTS.md`: RT-01..RT-05.
- `docs/workflow.md` ("Milestone 1 roadmap" table): owner-approved gate wording.
- `docs/superpowers/specs/2026-10-19-reverseapoc-design.md` ("What is left to the builder", "Exact LE writer strategy (Phase 3)").

### Prior art and research
- `docs/research/notes-own-pipeline-reuse-inventory.md` Q2 and Q4: KKND `build_kknd.py` in-place splice, `le.py`; why in-place beats a full rewrite.
- `.planning/research/PITFALLS.md` Pitfalls 1-3 (tautological round trip, trailer, straddling fixups) and 21 (full-rewrite scope creep).
- `.planning/research/ARCHITECTURE.md` components C3 (region map), C4 (splicer), C5 (rebuild/SHA-1 gate).
- `.planning/research/SUMMARY.md` "Phase 3" section.

### Code and docs to change or reuse
- `tools/reverseapoc/le.py`: LE reader (`LE`, `LEPage`, `LEObject`, `Fixup`, `fixups()` with straddle de-duplication, `_check_loadable`, `load_flat`).
- `tools/reverseapoc/targets.py`: `load_manifest`, `Target`, `hash_file`, `FileHashes`.
- `tools/reverseapoc/cli.py`: subcommand pattern (`build_parser`, `_cmd_*`, `main` except tuple). PR #1 added the watcom commands; keep both.
- `configure.py`: phony `check-orig` and `parse-le` edges, the pattern for `verify`.
- `tests/conftest.py`: `build_le_image()` synthetic LE builder (bound/unbound, custom fixups, page flags) and `write_manifest()`.
- `tests/test_le_real.py`: real-file skip pattern (`ORIG_DIR`, `pytestmark = skipif`).
- `docs/toolchain.md` "LE layout" section: correct "page data runs exactly to EOF" and the "To be confirmed in Phase 2/3" line. The "Getting the Watcom compilers" section belongs to PR #1's author; do not edit it.
- `.claude/rules/tools.md`, `docs/coding-style.md#python-tooling`: tooling rules (D-17).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LE` already resolves the bound-stub offset, page map (`pages[i].file_offset`, `.size`, `.flags`), objects (`base`, `vsize`, `page_index`, `page_count`), `page_va()`, `obj_of_va()`, and de-duplicated `fixups()` with `src_va` and `size`, which is enough to compute masked fields and VA-to-file-offset mapping without new parsing.
- `LE.load_flat(relocate=False)` builds the flat image by object base. The splice's flat-address view can mirror it.
- `build_le_image()` makes small bound LEs with a page-straddling fixup (`0xFFE` on page 1) and a short last page (`LAST_PAGE_SIZE = 0x200`), covering D-13's synthetic cases. It may need a `trailer=` option for the trailer region.
- `write_manifest()` writes a hash manifest for synthetic files, for CLI tests of `rebuild`.

### Established Patterns
- Real-file tests are skipped unless `orig/` holds the EXEs. Synthetic fixtures never embed game bytes.
- CLI: one `_cmd_<verb>` per subcommand returning an exit code, and errors mapped in `main()`'s except tuple.
- `LEError` / `LEUnsupportedError` for format problems. A splice error class should subclass `LEError` so `main()` reports it.

### Integration Points
- `cli.py`: new `rebuild` subcommand (`--orig`, `--manifest`, `--out build`, `--exe`, `--json`).
- `configure.py`: new phony `verify` edge.
- `le.py` / `cli.py parse-le`: trailer reporting (D-11).
- Phase 5 will call `splice()` with compiled function bytes at their VAs.

</code_context>

<specifics>
## Specific Ideas

- Local scan facts (2026-10-19), to be confirmed by the spike:
  - all pages are physical: 303 (UFO2P), 666 (TACP), 21 (SMKP);
  - every fixup is internal;
  - straddling off32 fields: 14, 11 and 2;
  - 27 trailing bytes after the last page in UFO2P (at 0x1A0723) and TACP (at 0x303DDF), both starting `64 00 9B FF`; SMKP has none;
  - there are no rel32 fixups at all, only sel16, ptr16:32 and off32.
- Expected SHA-1s (from the manifest, not to be copied into tests): UFO2P `e7488bf3…7c56`, TACP `48ef0096…7393`, SMKP `efdcf2a5…e8bc`.

</specifics>

<deferred>
## Deferred Ideas

- Matching SMKP.EXE functions (compiler ID, split, pilot): stays v2 (SMKP-01). Only its round trip is in Phase 3.
- A full LE rewrite or relinkable build (LE-01, v2). Reopen trigger: a matched function changes size.

</deferred>

---

*Phase: 03-byte-identical-round-trip*
*Context gathered: 2026-10-20*
