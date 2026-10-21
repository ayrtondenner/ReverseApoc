# Phase 4: Compiler identification - Pattern Map

**Mapped:** 2026-10-21
**Files analyzed:** 27 (new + modified)
**Analogs found:** 24 / 27

All analogs below are git-tracked (`git ls-files tools tests configure.py` verified). No game or compiler bytes appear in any excerpt.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `tools/reverseapoc/wpack.py` | utility (binary decoder) | transform | `tools/reverseapoc/iso9660.py` (guards, named offsets) + `le.py` (header style) | role-match |
| `tools/reverseapoc/omf.py` | utility (binary reader) | file-I/O / transform | `tools/reverseapoc/le.py` | exact |
| `tools/reverseapoc/libmatch.py` | service (scan + CSV writer) | batch | `tools/reverseapoc/splice.py` (masking over LE fixups, result dataclasses) | role-match |
| `tools/reverseapoc/cflags.py` (or in compiler.py) | config parser | transform | `tools/reverseapoc/watcom.py` `_parse_key_file`/`_parse_media` | role-match |
| `tools/reverseapoc/compiler.py` | service (subprocess wrapper) | request-response | `watcom.py` `check_version` + `configure.py` `_SAFE_ORIG` | partial |
| `tools/reverseapoc/probe.py` | service (scanner) | batch | `splice.py` (`_unmasked` runs) + `le.py` `load_flat` | partial |
| `tools/reverseapoc/cppscan.py` | service (scanner) | batch | same as probe.py | partial |
| `tools/reverseapoc/watcom.py` (modify: wpack key-file fields, decode in install, exe-dir helper?) | service | file-I/O | itself (`_parse_key_file` L91-108, `install_version` L414-453) | exact |
| `tools/reverseapoc/cli.py` (modify: `cc`, `libmatch`, `probe`, `cppscan` verbs) | controller | request-response | itself (`_cmd_rebuild` L52-65, `main` L186-192) | exact |
| `tools/reverseapoc/targets.py` (maybe: `config_dir(name)` helper D-16) | utility | transform | `targets.py` itself | exact |
| `config/cflags.txt` | config | — | `docs/matching.md` table | no code analog |
| `config/ufo2p/runtime.csv`, `config/tacp/runtime.csv` | config (generated) | — | none | no analog |
| `config/watcom.toml` (modify 10.5 entry) | config | — | existing entries | exact |
| `probe/*.c`, `probe/README.md` | source (C89) | — | none | no analog |
| `tests/omfimage.py`, `tests/wpackimage.py` | test builder | — | `tests/isoimage.py` | exact |
| `tests/test_omf.py`, `test_wpack.py`, `test_libmatch.py`, `test_cflags.py`, `test_compiler.py`, `test_probe.py`, `test_cppscan.py` | test | — | `tests/test_iso9660.py`, `tests/test_watcom.py`, `tests/test_splice.py` | exact |
| `tests/test_*_real.py` (wpack, omf, libmatch drift, compiler, toolchain) | test (real-file) | — | `tests/test_le_real.py`, `tests/test_watcom_real.py` | exact |
| `tests/test_cli.py` (modify) | test | — | itself | exact |
| `docs/research/wpack-format.md`, `docs/toolchain.md`, `docs/matching.md`, `docs/learnings.md`, `.planning/spikes/004-wibo-watcom/README.md` | docs | — | existing docs | n/a |

## Pattern Assignments

### `tools/reverseapoc/omf.py` (binary reader) — analog `tools/reverseapoc/le.py`

**Derivation header + module docstring** (le.py lines 1-19): first line
```python
# Derived from KKND-Decomp tools/le.py (CC0 1.0), https://github.com/Wyrelade/KKND-Decomp
"""Linear Executable (LE) reader for DOS/4GW-bound Watcom executables.
...
Only what Watcom's flat-model wlink emits is supported: ... raise `LEUnsupportedError` instead of being mis-parsed.
"""
```
omf.py: same shape, cite KKND `omf.py` (CC0) if any code is lifted; docstring lists supported records (THEADR, COMENT 0x9B/0x9F/0xAA/0xE9, LNAMES, SEGDEF, GRPDEF, EXTDEF, PUBDEF, LEDATA, LIDATA, FIXUPP, COMDAT, MODEND, LIB 0xF0/0xF1) and what raises.

**Imports** (le.py lines 21-30): `from __future__ import annotations`, `struct`, `dataclass`, `Path`.

**Named offsets / constants** (le.py lines 32-86):
```python
LE_SIGNATURE = b"LE\x00\x00"  # "LE", little-endian byte order, little-endian word order
TGT_TYPE_MASK = 0x03
TGT_INTERNAL = 0x00
_HDR_PAGE_SIZE = 0x28  # u32: size of every data page but the last
```
Apply: record type constants (`REC_THEADR = 0x80`, `REC_LEDATA32 = 0xA1`, ...), FIXUPP bit fields (`LOCAT_M = 0x40`, `LOC_OFFSET32 = 9`), each commented with the spec field (rule: no bare offsets).

**Typed error** (le.py line 104 `class LEError(ValueError)`): `class OMFError(ValueError)`; add to `cli.main()` except tuple.

**Frozen dataclasses** (le.py `LEObject` L113, `Fixup` L150): use `@dataclass(frozen=True)` for `Segment`, `OMFFixup`, `Public`, `Module`, `Library`.

### `tools/reverseapoc/wpack.py` (decoder) — analogs `iso9660.py` + `le.py`

**Named field constants** (iso9660.py lines 19-50):
```python
SECTOR = 2048
_REC_EXTENT = 2  # u32: first sector of the file or directory
_REC_SIZE = 10  # u32: data length in bytes
_VD_MAGIC = b"CD001"
```
Apply to the 12-byte header (`_HDR_SIGNATURE`, `_HDR_NUM_FILES`, `_HDR_INFO_LEN`, `_HDR_INFO_OFFSET`), file_info fields, `NO_SHANNON = 0x80`, LZSS `WINDOW = 4096`, `LOOKAHEAD = 60`, `THRESHOLD = 2`.

**Guards with typed error** (iso9660.py L53, L127-154):
```python
class ISOError(ValueError):
...
            raise ISOError(f"image is truncated ({entry.path or 'root'!r} lies beyond the end)")
            raise ISOError("not an ISO9660 image (no CD001 volume descriptor)")
```
`WpackError(ValueError)`: bad signature, truncated parts, CRC mismatch (`zlib.crc32`), length disagreeing with manifest size (bound output). Derivation header: state "independent implementation from docs/research/wpack-format.md; OW bld/wpack cited as format reference only" (D-15) — no OW code/comments.

### `tools/reverseapoc/watcom.py` (modify) — itself

**Key-file validator pattern** (lines 91-108) — add optional `wpack` (list of non-empty str) and `wpack_member` (str) exactly like `known_bad`/`note`:
```python
    known_bad = entry.get("known_bad", False)
    if not isinstance(known_bad, bool):
        raise ManifestError(f"{where}: 'known_bad' must be true or false")
```
and `skip_dirs` list check (lines 117-119). Extend `KeyFile` (lines 49-68) with `wpack: tuple[str, ...] = ()`, `wpack_member: str = ""`.

**Install hook point** (lines 436-441): decode inside `partial` after `extract_all(...)` and before `_replace_with_retry(partial, target)`; wrap `WpackError` like ISOError:
```python
        try:
            extract_all(iso, partial, skip_dirs=media.skip_dirs)
        except ISOError as exc:
            raise WatcomError(f"cannot extract Watcom {media.version} from {iso}: {exc}") from exc
```
**Check reuse for D-13** (lines 357-366 `check_version`, statuses `ok/missing/mismatch/known-bad` at L313): compiler.py filters `VersionCheck.results` to the gate paths and refuses any status other than `ok`.

### `tools/reverseapoc/compiler.py` + `cflags.py` — analogs `watcom.py`, `configure.py`

**Path allowlist** (configure.py lines 55-65):
```python
class ConfigureError(ValueError):
    """build.ninja cannot safely carry the named path."""
_SAFE_ORIG = re.compile(r"[A-Za-z0-9._/:-]+")
```
Use `_SAFE_PATH = re.compile(r"[A-Za-z0-9._/-]+")` (no `:`), plus refuse leading `-` and `..`, then `/`→`\`. First-bad-char pattern via `next(..., None)` (configure.py `ninja_path`, lines 68-74).

**Defaults from REPO_ROOT** (watcom.py lines 33-35): `DEFAULT_CFLAGS = REPO_ROOT / "config" / "cflags.txt"`, gate stamp under `REPO_ROOT / "build" / "gate"`.

**cflags parse errors**: mirror `_parse_media` "where" prefix style (watcom.py L111-119): `f"{path}:{lineno}: ..."` raising `CompilerError` (or ManifestError). Glob with `fnmatch.fnmatchcase`; last match wins; first rule must be `*`.

**Subprocess**: list argv, `env=` built from scratch, injectable runner callable (mirror `opener: Callable` injection in watcom.py `fetch_media`, L239 / `_download` L229) so tests can assert the scrubbed env without a compiler.

### `tools/reverseapoc/libmatch.py`, `probe.py`, `cppscan.py` — analog `splice.py`

**Target-side masking** — `splice.py` L475-516 (`_covered_fixups`, `_masked_fields`, `_unmasked`, `_unmasked_runs`) show how LE `Fixup.src_va`/`size` become masked byte sets; reuse `le.LE.fixups()` (le.py L346) and `load_flat(relocate=False)` (L411).

**Result dataclass + `format()` + `to_json()`** (splice.py L577-664):
```python
class RebuildResult:
    status: str  # "ok", "mismatch", "missing", "refused" or "error"
    error: str | None = None  # why an "error" target failed: names and offsets, never bytes
    def format(self, width: int, manifest: Path | None = None) -> str:
    def to_json(self) -> dict[str, Any]:
        """... names, a status, a path, numbers, ... never file bytes."""
class RebuildReport:
    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)
```
Apply: `MatchRange(start, end, segment, module, libraries, versions, publics, status)`, `SkippedLibrary(path, reason)` ("not OMF", "unmaskable", "short", parse failure), `LibMatchReport.format()/to_json()`; `ProbeCounts`/`CppScanReport` likewise. Derivation header in libmatch.py: KKND `tools/lib_match.py` CC0 at commit a371547.

**Atomic write** for runtime.csv: `splice._write_atomic` (L684).

### `tools/reverseapoc/cli.py` (modify) — itself

**Verb** (lines 52-65), **registration** (lines 162-174), **error mapping** (lines 186-192):
```python
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (IngestError, LEError, ManifestError, ISOError, WatcomError, OSError) as exc:
        print(f"reverseapoc {args.command}: error: {exc}", file=sys.stderr)
        return 1
```
Add `_cmd_cc` (`SRC`, `-o OBJ`), `_cmd_libmatch` (`EXE`, `--json`, `--write`), `_cmd_probe`, `_cmd_cppscan`; extend except tuple with `OMFError, WpackError, CompilerError` (and LibMatch errors). Update module docstring verb list (line 1-2). Group helpers like `_add_watcom_commands` (L101).

### Tests

**Synthetic builders** `tests/omfimage.py`, `tests/wpackimage.py` — copy `tests/isoimage.py` lines 1-25: docstring "Test-only builder of tiny synthetic ...", own literals, `struct.pack` helpers, poisoned fields (`GARBAGE = 0xA5`) to catch readers that look at the wrong field.

**Real-file tests** — `tests/test_le_real.py` lines 1-40:
```python
from conftest import ORIG_DIR
UFO2P = ORIG_DIR / "UFO2P.EXE"
pytestmark = pytest.mark.skipif(
    not (UFO2P.is_file() and TACP.is_file()),
    reason="orig/UFO2P.EXE and orig/TACP.EXE not present (run `uv run reverseapoc ingest`)",
)
@pytest.fixture(params=[...], ids=["UFO2P", "TACP"])
```
and `tests/test_watcom_real.py` lines 20-28 (`REVERSEAPOC_WATCOM_MEDIA` override). For third_party/watcom trees add an analogous `REVERSEAPOC_WATCOM` override in `conftest.py` next to `ORIG_DIR` (lines 19-22). Expected hashes always via `load_watcom_manifest`, never literals. `test_libmatch_real.py` drift test: re-derive and compare text to committed `config/<stem>/runtime.csv`.

**Unit test style**: `tests/test_watcom.py` (manifest validator cases, injected opener), `tests/test_splice.py` (result/format/json), `tests/test_cli.py` (verb wiring, exit codes, stderr error line).

## Shared Patterns

- **Typed error per module, mapped once in `cli.main()`** — `le.py:104`, `iso9660.py:53`, `watcom.py:45`, `cli.py:190`. Apply to omf, wpack, compiler, libmatch.
- **Hashing** — `targets.hash_file`/`hash_bytes`/`FileHashes` (targets.py L135-157). Use for gate stamp and normalized-object SHA-1 helper (hashlib over kept records).
- **Manifest field validators** — `targets._text/_size/_digest/_crc32` imported in watcom.py L20-30; reuse for any new manifest fields.
- **Repo-root defaults** — `targets.REPO_ROOT`; `watcom.py` L33-35.
- **No bytes in output** — splice.py `to_json` docstring; outputs are offsets, counts, names, hashes, banners.
- **`from __future__ import annotations`** + frozen dataclasses in every module.
- **D-16 exe→dir helper**: one function (e.g. in `targets.py`) `config_dir(name) -> REPO_ROOT/"config"/PurePosixPath(name).stem.lower()`; all of libmatch/probe/cppscan go through it.

## No Analog Found

| File | Role | Reason |
|---|---|---|
| `config/cflags.txt` | config | New format; spec in RESEARCH "Pattern 4" and docs/matching.md table |
| `config/<stem>/runtime.csv` | generated config | New format; columns in RESEARCH "Pattern 3" |
| `probe/*.c` | C89 sources | First C in repo; follow `docs/coding-style.md` C89 rules |

## Metadata

**Analog search scope:** `tools/reverseapoc/`, `tests/`, `configure.py`
**Files scanned:** 24
**Pattern extraction date:** 2026-10-21
