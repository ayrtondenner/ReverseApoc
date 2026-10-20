# Phase 3: Byte-identical round trip - Pattern Map

**Mapped:** 2026-10-20
**Files analyzed:** 11 (3 new, 8 modified)
**Analogs found:** 11 / 11 (all analogs are git-tracked; nothing under orig/ or third_party/ was read)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `tools/reverseapoc/splice.py` (NEW) | service (binary writer + region map) | transform / file-I/O | `tools/reverseapoc/le.py` (`load_flat`, `_check_loadable`) + `tools/reverseapoc/iso9660.py` (constants, generators) + `tools/reverseapoc/targets.py` (`check_target`, `CheckReport.format`) | role-match (composite) |
| `tools/reverseapoc/le.py` (MOD) | parser (read helpers only) | transform | itself: `_check_loadable` L405-419, `summary` L435-465, `format_summary` L472+ | exact |
| `tools/reverseapoc/cli.py` (MOD) | CLI controller | request-response | `_cmd_check_orig` L36-39, `_cmd_parse_le` L42-48, `build_parser` L119-151, `main` L154-160 | exact |
| `configure.py` (MOD) | config generator | batch | `HEADER` L18-43, `render()` L59-74 | exact |
| `tests/conftest.py` (MOD) | test fixture | transform | `build_le_image` L103-199 | exact |
| `tests/test_splice.py` (NEW) | test (synthetic) | transform | `tests/test_le.py`, `tests/test_cli.py` | role-match |
| `tests/test_splice_real.py` (NEW) | test (real-file, skipped in CI) | file-I/O | `tests/test_le_real.py` L1-40 | exact |
| `tests/test_le.py` (MOD) | test | transform | itself (`test_non_physical_pages_fail_loudly`, `test_truncated_page_data`) | exact |
| `tests/test_cli.py` (MOD) | test | request-response | `test_check_orig_exit_codes` L43-52 | exact |
| `tests/test_configure.py` (MOD) | test | batch | `test_render_has_phony_targets_and_phase5_note` L8-17 | exact |
| `docs/toolchain.md` (MOD) | docs | - | its own "LE layout" table L51 ("page data runs exactly to EOF") and L56 ("To be confirmed in Phase 2/3") | exact |

## Pattern Assignments

### `tools/reverseapoc/splice.py` (service, transform/file-I/O)

**Header + docstring** - copy `le.py` L1-20 style: line 1 is the CC0 derivation header, then a module docstring describing the layout.
```python
# Derived from KKND-Decomp tools/le.py (CC0 1.0), https://github.com/Wyrelade/KKND-Decomp
"""Linear Executable (LE) reader for DOS/4GW-bound Watcom executables.
...
"""

from __future__ import annotations

import os
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
```
splice.py imports: `bisect`, `hashlib`/`json` as needed, `dataclasses`, `pathlib`, and `from .le import LE, LEError, LEUnsupportedError, LEObject, LEPage, Fixup, SRC_SIZE` and `from .targets import Target, FileHashes, hash_file, check_target, load_manifest` (relative imports, as cli.py L11-14).

**Error class** - subclass `LEError` exactly like `le.py` L92-97, so `cli.main()` catches it without changing the except tuple:
```python
class LEError(ValueError):
    """The file is not a well-formed LE executable."""


class LEUnsupportedError(LEError):
    """The file uses an LE feature this parser deliberately does not handle."""
```
-> `class SpliceError(LEError): """A patch or rebuild was refused."""`

**Dataclasses** - frozen, small, with properties (`le.py` L100-148, `LEObject.end` / `contains`, `Fixup` uses `order=True`). Use `@dataclass(frozen=True, order=True)` for `Region(start, end, kind, ...)` so sorted lists tile naturally; `MaskedField(fixup: Fixup, patch_va, start, end)` with `partial`/`straddles_page`/`clipped` properties; reuse `LEPage`/`LEObject`/`Fixup`/`FileHashes` instead of copying fields (D-17).

**Named binary offsets** - copy the iso9660.py L26-50 style (private module constants named after the spec field, with an inline comment, derived from each other where possible):
```python
_REC_EXTENT = 2  # u32: first sector of the file or directory
_REC_SIZE = 10  # u32: data length in bytes
_REC_NAME = 33  # the fixed part of a record ends here; the name follows
_MIN_RECORD = _REC_NAME + 1  # shortest record: a one-byte name (`.`, `..` or the root)
```

**Core pattern to mirror (page walking)** - `le.py` `load_flat` L380-403 is the only existing object/page iteration; mirror its loop but size images by `page_count * page_size` filled with full `page.size` (NOT clipped at vsize, Pitfall B) and use `page.file_offset` (never recompute, Pitfall C):
```python
        for obj in self.objects:
            for k in range(obj.page_count):
                dst = k * self.page_size
                if dst >= obj.vsize:
                    break
                page = self.pages[obj.page_index + k - 1]
                self._check_loadable(obj, page)
                n = min(page.size, obj.vsize - dst)
                flat[obj.base + dst : obj.base + dst + n] = self.data[
                    page.file_offset : page.file_offset + n
                ]
```
Writable span per page: `va_end = min(va_start + page.size, obj.end)` (D-18). The `break` on `dst >= obj.vsize` must NOT be copied into image building.

**Shallow nesting + error context in one place** - copy `iso9660.py` `_entries` L181-194 (generator, early `continue`, one wrapping `except` that adds context). Use it for "error names the patch": resolve patches in a generator, wrap once with `raise SpliceError(f"{exc} (patch at {va:#x}, {len(b)} bytes)") from exc`.
```python
        try:
            for rec in self._records(directory):
                if _is_dot_record(rec) or rec[_REC_FLAGS] & _FLAG_ASSOCIATED:
                    continue
                entry = self._parse_record(directory.path, rec)
                ...
                yield entry
        except ISOError as exc:
            raise ISOError(f"{exc} (in {directory.path or '/'!r})") from exc
```

**First-match lookup** - `iso9660.py` `find` L209-214 (`next(..., None)` then raise); use for `region_at(regions, offset)` (or bisect) and `--exe` target lookup:
```python
        entry = next((e for e in self.walk() if e.path == path), None)
        if entry is None:
            raise ISOError(f"{path!r} not found in image")
        return entry
```

**Error message style** - `le.py` `_check_loadable` L405-419: hex with `:#x`, name object/page, state the rule. Never include byte values (Pitfall I).
```python
            raise LEError(
                f"truncated file: page {page.logical} needs bytes {page.file_offset:#x}.."
                f"{end:#x}, file is {len(self.data):#x} bytes"
            )
```

**Rebuild result + format()** - copy `targets.py` `TargetCheck`/`CheckReport` L123-166 (frozen dataclass with `status`, `ok` property, `format()` returning aligned lines) and `check_target` L169-182 for the input check before rebuilding:
```python
@dataclass(frozen=True)
class TargetCheck:
    target: Target
    status: str  # "ok", "missing" or "mismatch"
    path: Path
    problems: list[str] = field(default_factory=list)
...
    def format(self) -> str:
        width = max(len(r.target.name) for r in self.results)
        ...
                lines.append(f"  OK        {name}  {r.target.size} bytes  sha1 {r.target.sha1}")
```
Hash with `hash_file(out_path)` (targets.py L112-121) -> `FileHashes`; compare to `Target.sha1` from `load_manifest` (D-15). Library entry `rebuild_target(target, orig_dir, out_dir, patches=None)` mirrors `check_orig(orig_dir, manifest)` L185-192 (Path normalization + defaults from `DEFAULT_ORIG`).

---

### `tools/reverseapoc/le.py` (MOD, read helpers only)

- Rename `_check_loadable` (L405) -> `check_loadable`; update caller at L396. Pinned by existing `test_non_physical_pages_fail_loudly`, `test_iterated_page_message`, `test_truncated_page_data`.
- Add `pages_end` property next to `entry_va`/`stack_va` (L289-298 are `@property` read helpers - same style).
- Header fields read via `self._header_u32(field)` (L226-227); add named constants for 0x88/0x8C/0x98/0x9C (D-19) in the module-constant block near L31-74, e.g. `_HDR_NONRES_NAMES_OFFSET = 0x88`. Do not refactor existing bare offsets L195-209 in this phase.
- Trailer in `summary()` (L435-465): add `"trailer": {"offset", "length", "sha1"}` (clamp length at 0); add a `("trailer", ...)` row to `format_summary` rows list (L474-482 pattern, `_hex()` helper L468).

---

### `tools/reverseapoc/cli.py` (MOD, CLI controller)

**Command function** (copy L36-39):
```python
def _cmd_check_orig(args: argparse.Namespace) -> int:
    report = check_orig(args.orig, args.manifest)
    print(report.format())
    return 0 if report.ok else 1
```
**--json branch** (copy L42-48 `_cmd_parse_le`: `json.dumps(..., indent=2)` vs formatted text).

**Subparser registration** (copy L125-139, reuse local `orig_and_manifest(p)`):
```python
    p = sub.add_parser("check-orig", help="verify orig/ against config/targets.toml")
    orig_and_manifest(p)
    p.set_defaults(func=_cmd_check_orig)
```
Add `--out` (default `REPO_ROOT / "build"`), `--exe NAME`, `--json`. Insert before `_add_watcom_commands(sub)` (L150) - keep PR #1's watcom commands. Update module docstring verb list (L1-2).

**Error mapping** (L154-160): no change needed if `SpliceError(LEError)`:
```python
    except (IngestError, LEError, ManifestError, ISOError, WatcomError, OSError) as exc:
        print(f"reverseapoc {args.command}: error: {exc}", file=sys.stderr)
        return 1
```

---

### `configure.py` (MOD)

Copy `rule check_orig` block in `HEADER` (L31-34) and the always/phony pair in `render()` (L63-64):
```
rule check_orig
  command = uv run reverseapoc check-orig
  description = CHECK-ORIG orig/
  pool = console
```
```python
        "build $builddir/always/check-orig: check_orig",
        "build check-orig: phony $builddir/always/check-orig",
```
-> `rule rebuild` / `build $builddir/always/verify: rebuild` / `build verify: phony $builddir/always/verify`. Add `ninja verify` line to the header comment list (L21-23). Keep "Phase 5", `builddir = build`, `default check-orig`.

---

### `tests/conftest.py` (MOD)

Extend `build_le_image` (L103-199) keyword args `page_numbers=` and `trailer=`. The page-map line to generalise (L127-130):
```python
    page_map = b"".join(
        bytes([(n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF, flags])
        for n, flags in enumerate(page_flags, start=1)
    )
```
Pages are written in physical order (L188-192, `page_fill(n)`); append `trailer` after; add `trailer_offset` to `SyntheticLE` (dataclass ending L100). Keep literal header field dict (L150-169) - fixture literals stay in conftest (coding-style rule). Do not change `DEFAULT_FIXUPS`/`DEFAULT_DECODED`. Use `fixup_record(...)` (L31) for custom fixups. `write_manifest` (L218) for CLI rebuild tests.

---

### `tests/test_splice_real.py` (NEW)

Copy `tests/test_le_real.py` L1-35 (docstring stating skip reason, `from conftest import ORIG_DIR`, module-scope `LE` fixtures). Per Pitfall H, use per-param skip instead of module `pytestmark`:
```python
pytestmark = pytest.mark.skipif(
    not (UFO2P.is_file() and TACP.is_file()),
    reason="orig/UFO2P.EXE and orig/TACP.EXE not present (run `uv run reverseapoc ingest`)",
)
```
-> `pytest.param(name, marks=pytest.mark.skipif(not (ORIG_DIR / name).is_file(), reason=...))`. Expected SHA-1 via `load_manifest()` (D-15); outputs to `tmp_path` (Pitfall G).

### `tests/test_splice.py` (NEW) / `tests/test_cli.py` (MOD)

CLI test shape (test_cli.py L43-52): build manifest with `write_manifest`, pass explicit `--orig`, `--manifest` (and `--out tmp_path`), assert exit code and output substring:
```python
    manifest = write_manifest(tmp_path / "m.toml", {"A.EXE": b"alpha"})
    orig = tmp_path / "orig"
    orig.mkdir()
    args = ["check-orig", "--orig", str(orig), "--manifest", str(manifest)]
    assert main(args) == 1
    assert "MISSING" in capsys.readouterr().out
```
For rebuild, the file content must be `build_le_image().data` (a real synthetic LE), not `b"alpha"`. Synthetic splice tests use `le_builder`/`synthetic_le` fixtures (conftest L202-215) and `pytest.raises(SpliceError, match=...)`; D-13 cases are tabulated in 03-RESEARCH.md "Fixture cases for D-13".

### `tests/test_configure.py` (MOD)

Copy L8-17: `text = configure.render([...])`; assert `"build verify: phony" in text` and `"uv run reverseapoc rebuild" in text`.

## Shared Patterns

### Error classes and CLI mapping
**Source:** `tools/reverseapoc/le.py` L92-97, `tools/reverseapoc/cli.py` L158
**Apply to:** splice.py, cli.py. Every new error subclasses `LEError` (or `ManifestError`), so the except tuple stays as-is.

### Named spec offsets
**Source:** `tools/reverseapoc/iso9660.py` L19-50
**Apply to:** splice.py and the new le.py header constants (D-17, D-19).

### Generators + one-place error context + `next(..., None)`
**Source:** `tools/reverseapoc/iso9660.py` L181-214
**Apply to:** patch resolution, region lookup, `--exe` lookup.

### Report dataclass + `format()` + `ok`
**Source:** `tools/reverseapoc/targets.py` L123-166
**Apply to:** rebuild result (text line per EXE; `--json` from the same data).

### No game bytes in output
**Source:** `.claude/rules/tools.md`, `le.py` summary (only offsets/sizes/counts)
**Apply to:** all messages, JSON, docs (trailer: offset, length, first 4 bytes, sha1 only in docs; no bytes in parse-le).

## No Analog Found

| File / piece | Role | Data Flow | Reason |
|---|---|---|---|
| `splice.assemble(size, pieces)` | utility | transform | No writer exists in the repo (le.py is read-only); use 03-RESEARCH.md Pattern 3 shape |
| fixup-field masking via `bisect` | utility | transform | No bisect/interval code in repo; use 03-RESEARCH.md Pattern 2 |

## Metadata

**Analog search scope:** `tools/reverseapoc/`, `configure.py`, `tests/`, `docs/toolchain.md` (all git-tracked)
**Files scanned:** 12
**Pattern extraction date:** 2026-10-20
