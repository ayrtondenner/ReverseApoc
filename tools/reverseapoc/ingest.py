"""Copy the original executables from the user's own game install into orig/ and verify them.

The game folders come from APOC_STEAM_FOLDER (preferred) and APOC_GOG_FOLDER, read from the
environment or, failing that, from the .env file at the repository root. Values may use Windows
`%VAR%` or `${VAR}` references (e.g. `%ProgramFiles(x86)%\\Steam\\...`). The game folders are
only ever read.

`ingest --cd IMAGE` reads the 1997 disc image instead (a plain ISO9660 image or a MODE1/2352 raw
.bin) and extracts the CD v1.00 builds its [[cd_builds]] entries name into orig/cd/, each written
only when its size, CRC32, MD5 and SHA-1 match. The image is only ever read.
"""

from __future__ import annotations

import filecmp
import io
import os
import re
import shutil
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .fileio import write_atomic
from .iso9660 import _VD_FIRST_SECTOR, _VD_ID, _VD_MAGIC, ISO9660, SECTOR, IsoEntry, ISOError
from .targets import (
    DEFAULT_MANIFEST,
    DEFAULT_ORIG,
    REPO_ROOT,
    CheckReport,
    ManifestError,
    Target,
    TargetCheck,
    _parse_target,
    check_orig,
    hash_bytes,
    load_manifest,
    target_problems,
)

FOLDER_KEYS = ("APOC_STEAM_FOLDER", "APOC_GOG_FOLDER")
DEFAULT_DOTENV = REPO_ROOT / ".env"
# GOG keeps UFOEXE/, TACEXE/ at the root of the game folder; Steam nests them under XCOMA/.
LAYOUT_PREFIXES = ("", "XCOMA")

_VAR = re.compile(r"%([^%\s]+)%|\$\{([^}]+)\}")


class IngestError(RuntimeError):
    """Ingest cannot start (no game folder configured)."""


def parse_dotenv(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines. Supports comments, `export `, single/double quotes (no escape
    processing, so Windows backslashes survive) and ` #` trailing comments on unquoted values."""
    env: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key or " " in key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
        env[key] = value
    return env


def read_dotenv(path: Path) -> dict[str, str]:
    try:
        return parse_dotenv(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}


def _lookup(environ: Mapping[str, str], name: str) -> str | None:
    if name in environ:
        return environ[name]
    folded = name.casefold()
    for key, value in environ.items():
        if key.casefold() == folded:
            return value
    return None


def expand_vars(value: str, environ: Mapping[str, str]) -> str:
    """Expand `%VAR%` and `${VAR}` (names matched case-insensitively, as on Windows).
    Unknown variables are left as written."""

    def replace(match: re.Match[str]) -> str:
        found = _lookup(environ, match.group(1) or match.group(2))
        return match.group(0) if found is None else found

    return _VAR.sub(replace, value)


def game_folders(
    environ: Mapping[str, str] | None = None, dotenv_path: Path | None = None
) -> list[tuple[str, Path]]:
    """The configured game folders in preference order, as (variable name, path)."""
    environ = os.environ if environ is None else environ
    dotenv = read_dotenv(DEFAULT_DOTENV if dotenv_path is None else dotenv_path)
    merged = {**dotenv, **environ}
    folders = []
    for key in FOLDER_KEYS:
        raw = environ.get(key) or dotenv.get(key) or ""
        if raw.strip():
            folders.append((key, Path(expand_vars(raw.strip(), merged))))
    if not folders:
        raise IngestError(
            f"set {' or '.join(FOLDER_KEYS)} to your X-COM Apocalypse folder, in the "
            "environment or in .env (see .env.example)"
        )
    return folders


def _resolve_ignoring_case(base: Path, parts: list[str]) -> Path | None:
    current = base
    for part in parts:
        exact = current / part
        if exact.exists():
            current = exact
            continue
        try:
            matches = [p for p in current.iterdir() if p.name.casefold() == part.casefold()]
        except OSError:
            return None
        if not matches:
            return None
        current = matches[0]
    return current if current.is_file() else None


def find_in_folder(root: Path, relpath: str) -> Path | None:
    """Locate `relpath` (GOG layout) under a game folder in either the GOG or Steam layout."""
    parts = [p for p in relpath.replace("\\", "/").split("/") if p]
    for prefix in LAYOUT_PREFIXES:
        found = _resolve_ignoring_case(root, ([prefix] if prefix else []) + parts)
        if found is not None:
            return found
    return None


@dataclass(frozen=True)
class Copy:
    target: Target
    source: Path
    dest: Path
    action: str  # "copied", "replaced" or "unchanged"


@dataclass(frozen=True)
class IngestResult:
    folders: list[tuple[str, Path]]
    copies: list[Copy]
    not_found: list[Target]
    report: CheckReport

    def format(self) -> str:
        lines = [f"{key} = {path}" for key, path in self.folders]
        for c in self.copies:
            lines.append(f"  {c.action:<9}  {c.source} -> {c.dest}")
        for t in self.not_found:
            lines.append(f"  NOT FOUND  {t.path} ({t.name}) in any configured folder")
        lines.append(self.report.format())
        return "\n".join(lines)


def ingest(
    *,
    orig_dir: Path | None = None,
    manifest: Path | None = None,
    environ: Mapping[str, str] | None = None,
    dotenv_path: Path | None = None,
) -> IngestResult:
    """Copy every manifest target found in the configured game folders into `orig_dir` (each
    file from the first folder that has it), then run `check_orig`."""
    orig_dir = DEFAULT_ORIG if orig_dir is None else Path(orig_dir)
    folders = game_folders(environ, dotenv_path)
    targets = load_manifest(manifest)
    orig_dir.mkdir(parents=True, exist_ok=True)
    copies, not_found = [], []
    for target in targets:
        source = next(
            (f for _, root in folders if (f := find_in_folder(root, target.path)) is not None),
            None,
        )
        if source is None:
            not_found.append(target)
            continue
        dest = orig_dir / target.name
        if dest.is_file() and filecmp.cmp(source, dest, shallow=False):
            action = "unchanged"
        else:
            action = "replaced" if dest.exists() else "copied"
            shutil.copyfile(source, dest)
        copies.append(Copy(target, source, dest, action))
    return IngestResult(folders, copies, not_found, check_orig(orig_dir, manifest))


# ---- ingest --cd IMAGE: the [[cd_builds]] executables from the 1997 disc image ----

CD_DIR = "cd"  # orig/cd/: the CD v1.00 builds, next to the installed ones and gitignored with them
ISO_LAYOUT, RAW_LAYOUT = "ISO9660", "MODE1/2352"

# A MODE1 raw sector (ECMA-130 section 14): sync, header (3-byte MSF address, then the mode
# byte), the 2048 bytes of user data the ISO9660 layer sees, then EDC and ECC (not checked).
_RAW_SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
_RAW_ADDRESS = len(_RAW_SYNC)
_RAW_MODE = _RAW_ADDRESS + 3
_RAW_DATA = _RAW_MODE + 1
_RAW_EDC_ECC = 288
_RAW_SECTOR = _RAW_DATA + SECTOR + _RAW_EDC_ECC  # 2352
_MODE1 = 1
_PVD_MAGIC_OFFSET = _VD_ID.start  # where CD001 sits in the primary volume descriptor's sector


def load_cd_builds(manifest: Path | str | None = None) -> list[Target]:
    """The manifest's [[cd_builds]] entries, validated as [[targets]] entries are."""
    path = Path(manifest) if manifest is not None else DEFAULT_MANIFEST
    try:
        with path.open("rb") as fh:
            entries = tomllib.load(fh).get("cd_builds")
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ManifestError(f"{path}: {exc}") from exc
    if not entries:
        raise ManifestError(f"{path}: no [[cd_builds]] entries")
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise ManifestError(f"{path}: 'cd_builds' must be an array of tables ([[cd_builds]])")
    return [_parse_target(i, entry) for i, entry in enumerate(entries)]


class _Mode1Image:
    """The user data of a MODE1/2352 raw image as one 2048-byte-sector stream: the seek, tell
    and read ISO9660 uses. Each sector read must carry the sync pattern and mode 1."""

    def __init__(self, fh: BinaryIO) -> None:
        fh.seek(0, os.SEEK_END)
        raw_size = fh.tell()
        if raw_size % _RAW_SECTOR:
            raise ISOError(f"raw image of {raw_size} bytes is not a whole number of "
                           f"{_RAW_SECTOR}-byte sectors")  # fmt: skip
        self._fh, self._size, self._pos = fh, raw_size // _RAW_SECTOR * SECTOR, 0

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        base = {os.SEEK_SET: 0, os.SEEK_CUR: self._pos, os.SEEK_END: self._size}[whence]
        self._pos = base + offset
        return self._pos

    def tell(self) -> int:
        return self._pos

    def read(self, n: int = -1) -> bytes:
        end = self._size if n < 0 else min(self._pos + n, self._size)
        out = bytearray()
        while self._pos < end:
            lba, skip = divmod(self._pos, SECTOR)
            take = min(SECTOR - skip, end - self._pos)
            out += self._sector(lba)[skip : skip + take]
            self._pos += take
        return bytes(out)

    def _sector(self, lba: int) -> bytes:
        self._fh.seek(lba * _RAW_SECTOR)
        raw = self._fh.read(_RAW_SECTOR)
        if raw[:_RAW_ADDRESS] != _RAW_SYNC or raw[_RAW_MODE] != _MODE1:
            raise ISOError(f"raw sector {lba} is not a MODE1 sector (sync or mode byte)")
        return raw[_RAW_DATA : _RAW_DATA + SECTOR]


def _magic_at(fh: BinaryIO, offset: int) -> bool:
    fh.seek(offset)
    return fh.read(len(_VD_MAGIC)) == _VD_MAGIC


def disc_layout(fh: BinaryIO) -> str:
    """ISO_LAYOUT or RAW_LAYOUT, told by where the primary volume descriptor's CD001 sits."""
    if _magic_at(fh, _VD_FIRST_SECTOR * SECTOR + _PVD_MAGIC_OFFSET):
        return ISO_LAYOUT
    raw = _VD_FIRST_SECTOR * _RAW_SECTOR
    fh.seek(raw)
    if fh.read(len(_RAW_SYNC)) == _RAW_SYNC and _magic_at(fh, raw + _RAW_DATA + _PVD_MAGIC_OFFSET):
        return RAW_LAYOUT
    raise ISOError("neither an ISO9660 image (2048-byte sectors) nor a MODE1/2352 raw image")


@dataclass(frozen=True)
class CdIngestResult:
    image: Path
    layout: str
    report: CheckReport  # status "ok", "mismatch" or "missing" per [[cd_builds]] entry

    @property
    def ok(self) -> bool:
        return self.report.ok

    def format(self) -> str:
        results = self.report.results
        width = max(len(r.target.name) for r in results)
        lines = [f"reading {self.image} ({self.layout}) into {self.report.orig_dir}"]
        for r in results:
            name = r.target.name.ljust(width)
            if r.status == "ok":
                lines.append(f"  OK        {name}  {r.target.size} bytes  sha1 {r.target.sha1}  "
                             f"-> {r.path}")  # fmt: skip
            elif r.status == "missing":
                lines.append(f"  MISSING   {name}  {r.target.path} is not in the image")
            else:
                lines.append(f"  MISMATCH  {name}  " + "; ".join(r.problems) + " (not written)")
        n_bad, n_missing = len(self.report.mismatched), len(self.report.missing)
        lines.append(f"{len(results) - n_bad - n_missing} ok, {n_bad} mismatched, "
                     f"{n_missing} missing")  # fmt: skip
        return "\n".join(lines)


def _locate(iso: ISO9660, builds: list[Target]) -> dict[str, IsoEntry]:
    """Each build's file in the image by its casefolded path (ISO9660 names are upper case;
    the walk already dropped the `;1` version)."""
    wanted = {b.path.casefold() for b in builds}
    found: dict[str, IsoEntry] = {}
    for entry in iso.walk():
        key = entry.path.casefold()
        if key in wanted and not entry.is_dir:
            found.setdefault(key, entry)
    return found


def _extract(iso: ISO9660, entry: IsoEntry | None, build: Target, dest: Path) -> TargetCheck:
    """Read one build out of the image and write it to `dest` only when its size, CRC32, MD5
    and SHA-1 match the manifest."""
    if entry is None:
        return TargetCheck(build, "missing", dest)
    out = io.BytesIO()
    iso.copy_to(entry, out)
    data = out.getvalue()
    problems = target_problems(build, hash_bytes(data))
    if problems:
        return TargetCheck(build, "mismatch", dest, problems)
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(dest, data)
    return TargetCheck(build, "ok", dest)


def ingest_cd(
    image: Path | str, *, orig_dir: Path | None = None, manifest: Path | None = None
) -> CdIngestResult:
    """Extract every [[cd_builds]] executable from a plain ISO9660 image or a MODE1/2352 raw
    image into <orig_dir>/cd/, verified against the manifest. The image is only read."""
    builds = load_cd_builds(manifest)
    dest_dir = (DEFAULT_ORIG if orig_dir is None else Path(orig_dir)) / CD_DIR
    with Path(image).open("rb") as fh:
        layout = disc_layout(fh)
        iso = ISO9660(fh if layout == ISO_LAYOUT else _Mode1Image(fh))
        found = _locate(iso, builds)
        results = [_extract(iso, found.get(b.path.casefold()), b, dest_dir / b.name)
                   for b in builds]  # fmt: skip
    return CdIngestResult(Path(image), layout, CheckReport(dest_dir, results))
