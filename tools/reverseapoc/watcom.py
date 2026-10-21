"""Watcom compiler media: manifest (config/watcom.toml), download, install and key-file check."""

from __future__ import annotations

import hashlib
import http.client
import os
import shutil
import time
import tomllib
import urllib.parse
import urllib.request
import zlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from .iso9660 import ISOError, extract_all
from .targets import (
    REPO_ROOT,
    FileHashes,
    ManifestError,
    Target,
    _crc32,
    _digest,
    _size,
    _text,
    check_target,
    hash_file,
)
from .wpack import WpackError, decode_member, join_parts

DEFAULT_WATCOM_MANIFEST = REPO_ROOT / "config" / "watcom.toml"
DEFAULT_MEDIA = REPO_ROOT / "third_party" / "watcom-media"
DEFAULT_INSTALL = REPO_ROOT / "third_party" / "watcom"
ARCHIVE_BASE = "https://archive.org/download"

MEDIA_NOTICE = (
    "Watcom C/C++ is proprietary software. This downloads the original CD images from the\n"
    "Internet Archive, a third party. You are responsible for having the right to use them;\n"
    "nothing is redistributed by this repository."
)


class WatcomError(RuntimeError):
    """A media file is missing or corrupt, or an install target is in the way."""


@dataclass(frozen=True)
class KeyFile:
    path: str  # POSIX, exact on-disc case, relative to the installed version directory
    size: int
    md5: str
    sha1: str
    crc32: int | None = None
    known_bad: bool = False
    note: str = ""
    # D-01: the CD's copy is damaged; install decodes the real file from this wpack archive.
    wpack: tuple[str, ...] = ()  # archive parts in order, POSIX paths inside the installed tree
    wpack_member: str = ""  # member name inside the archive (matched without case)

    def as_target(self) -> Target:
        return Target(
            name=self.path,
            path=self.path,
            size=self.size,
            md5=self.md5,
            sha1=self.sha1,
            crc32=self.crc32,
        )


@dataclass(frozen=True)
class WatcomMedia:
    version: str
    item: str  # archive.org item
    file: str  # path inside the item; may contain "/"
    size: int
    md5: str
    sha1: str
    crc32: int | None = None
    key_files: tuple[KeyFile, ...] = ()
    skip_dirs: tuple[str, ...] = ()  # damaged directories that install leaves out
    note: str = ""

    @property
    def local_name(self) -> str:
        return PurePosixPath(self.file).name

    def url(self, base: str = ARCHIVE_BASE) -> str:
        return f"{base}/{self.item}/{urllib.parse.quote(self.file)}"


def _parse_wpack(where: str, entry: dict) -> tuple[tuple[str, ...], str]:
    """The optional `wpack` parts and `wpack_member` of a key file: both or neither."""
    parts = entry.get("wpack", [])
    if not isinstance(parts, list) or not all(isinstance(p, str) and p for p in parts):
        raise ManifestError(f"{where}: 'wpack' must be a list of non-empty strings")
    member = entry.get("wpack_member", "")
    if not isinstance(member, str):
        raise ManifestError(f"{where}: 'wpack_member' must be a string")
    if bool(parts) != bool(member):
        raise ManifestError(
            f"{where}: 'wpack' and a non-empty 'wpack_member' go together (both or neither)"
        )
    return tuple(parts), member


def _parse_key_file(where: str, entry: object) -> KeyFile:
    if not isinstance(entry, dict):
        raise ManifestError(f"{where}: must be a table")
    known_bad = entry.get("known_bad", False)
    if not isinstance(known_bad, bool):
        raise ManifestError(f"{where}: 'known_bad' must be true or false")
    note = entry.get("note", "")
    if not isinstance(note, str):
        raise ManifestError(f"{where}: 'note' must be a string")
    wpack, wpack_member = _parse_wpack(where, entry)
    return KeyFile(
        path=_text(entry, where, "path"),
        size=_size(entry, where),
        md5=_digest(entry, where, "md5", 32),
        sha1=_digest(entry, where, "sha1", 40),
        crc32=_crc32(entry, where),
        known_bad=known_bad,
        note=note,
        wpack=wpack,
        wpack_member=wpack_member,
    )


def _parse_media(i: int, entry: dict) -> WatcomMedia:
    where = f"media[{i}] ({entry.get('version', '?')})"
    raw_keys = entry.get("key_files", [])
    if not isinstance(raw_keys, list) or not all(isinstance(kf, dict) for kf in raw_keys):
        raise ManifestError(f"{where}: 'key_files' must be an array of tables")
    key_files = tuple(
        _parse_key_file(f"{where} key_files[{j}]", kf) for j, kf in enumerate(raw_keys)
    )
    skip_dirs = entry.get("skip_dirs", [])
    if not isinstance(skip_dirs, list) or not all(isinstance(d, str) and d for d in skip_dirs):
        raise ManifestError(f"{where}: 'skip_dirs' must be a list of non-empty strings")
    note = entry.get("note", "")
    if not isinstance(note, str):
        raise ManifestError(f"{where}: 'note' must be a string")
    return WatcomMedia(
        skip_dirs=tuple(skip_dirs),
        note=note,
        version=_text(entry, where, "version"),
        item=_text(entry, where, "item"),
        file=_text(entry, where, "file"),
        size=_size(entry, where),
        md5=_digest(entry, where, "md5", 32),
        sha1=_digest(entry, where, "sha1", 40),
        crc32=_crc32(entry, where),
        key_files=key_files,
    )


def load_watcom_manifest(path: Path | str | None = None) -> dict[str, WatcomMedia]:
    """Load and validate the media manifest (default: config/watcom.toml), keyed by version.
    Bytes that are not UTF-8, invalid TOML, a `media` or `key_files` value that is not an array
    of tables and any bad entry raise ManifestError naming the manifest; a missing file stays
    an OSError."""
    path = Path(path) if path is not None else DEFAULT_WATCOM_MANIFEST
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ManifestError(f"{path}: {exc}") from exc
    entries = data.get("media")
    if not entries:
        raise ManifestError(f"{path}: no [[media]] entries")
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise ManifestError(f"{path}: 'media' must be an array of tables ([[media]])")
    manifest: dict[str, WatcomMedia] = {}
    for i, entry in enumerate(entries):
        try:
            media = _parse_media(i, entry)
        except ManifestError as exc:
            raise ManifestError(f"{path}: {exc}") from exc
        if media.version in manifest:
            raise ManifestError(f"{path}: duplicate media version {media.version!r}")
        manifest[media.version] = media
    return manifest


def select(manifest: dict[str, WatcomMedia], versions: Sequence[str]) -> list[WatcomMedia]:
    """The requested versions in the given order; no versions means all of them."""
    if not versions:
        return list(manifest.values())
    unknown = [v for v in versions if v not in manifest]
    if unknown:
        raise ManifestError(
            f"unknown Watcom version(s) {', '.join(unknown)}; known: {', '.join(manifest)}"
        )
    return [manifest[v] for v in versions]


def _media_problems(media: WatcomMedia, got: FileHashes) -> list[str]:
    problems = []
    if got.size != media.size:
        problems.append(f"size: expected {media.size}, got {got.size}")
    if got.md5 != media.md5:
        problems.append(f"md5: expected {media.md5}, got {got.md5}")
    if got.sha1 != media.sha1:
        problems.append(f"sha1: expected {media.sha1}, got {got.sha1}")
    if media.crc32 is not None and got.crc32 != media.crc32:
        problems.append(f"crc32: expected {media.crc32:08x}, got {got.crc32:08x}")
    return problems


def _file_problems(media: WatcomMedia, path: Path) -> list[str]:
    return _media_problems(media, hash_file(path))


# ---- fetch ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class MediaResult:
    media: WatcomMedia
    path: Path
    action: str  # "present", "downloaded" or "mismatch"
    problems: tuple[str, ...] = ()


class _SizeMismatch(Exception):
    """The server announced or sent a size other than the manifest's."""


def _copy_hashed(src: BinaryIO, part: Path, limit: int, chunk: int) -> FileHashes:
    """Stream `src` into `part`, hashing as it goes. More than `limit` bytes discards `part`."""
    md5, sha1, crc, total = hashlib.md5(), hashlib.sha1(), 0, 0
    with part.open("wb") as out:
        while block := src.read(chunk):
            total += len(block)
            if total > limit:
                break
            out.write(block)
            md5.update(block)
            sha1.update(block)
            crc = zlib.crc32(block, crc)
    if total > limit:
        part.unlink()
        raise _SizeMismatch(f"size: more than the expected {limit} bytes were sent")
    return FileHashes(total, crc, md5.hexdigest(), sha1.hexdigest())


def _download(url: str, part: Path, size: int, opener: Callable, chunk: int) -> FileHashes:
    """Fetch `url` into `part`; a wrong Content-Length is refused before `part` is created."""
    req = urllib.request.Request(url, headers={"User-Agent": "reverseapoc"})
    with opener(req, timeout=60) as resp:
        length = resp.headers.get("Content-Length")
        if length is not None and str(length).strip() != str(size):
            raise _SizeMismatch(f"Content-Length: expected {size}, server says {length}")
        return _copy_hashed(resp, part, size, chunk)


def fetch_media(
    media: WatcomMedia,
    media_dir: Path | str,
    *,
    base: str = ARCHIVE_BASE,
    opener: Callable = urllib.request.urlopen,
    chunk: int = 1 << 20,
) -> MediaResult:
    """Download one ISO into `media_dir` unless a verified copy is already there. Streams into
    `<file>.part` and only renames it over the final name once size, MD5, SHA-1 and CRC32 match."""
    media_dir = Path(media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    dest = media_dir / media.local_name
    part = media_dir / (media.local_name + ".part")
    if dest.is_file() and not _file_problems(media, dest):
        return MediaResult(media, dest, "present")

    try:
        got = _download(media.url(base), part, media.size, opener, chunk)
    except _SizeMismatch as exc:
        return MediaResult(media, dest, "mismatch", (str(exc),))
    except (OSError, ValueError, http.client.HTTPException) as exc:
        return MediaResult(media, dest, "mismatch", (f"download failed: {exc}",))
    problems = _media_problems(media, got)
    if problems:
        return MediaResult(media, dest, "mismatch", tuple(problems))
    os.replace(part, dest)
    return MediaResult(media, dest, "downloaded")


@dataclass(frozen=True)
class FetchReport:
    results: tuple[MediaResult, ...]

    @property
    def ok(self) -> bool:
        return all(r.action in ("present", "downloaded") for r in self.results)

    def format(self) -> str:
        lines = []
        for r in self.results:
            tag = r.action.upper().ljust(10)
            line = f"  {tag}  {r.media.version.ljust(6)}  {r.path}"
            if r.problems:
                line += "  " + "; ".join(r.problems)
            lines.append(line)
        n = {a: sum(r.action == a for r in self.results) for a in ("present", "downloaded")}
        bad = len(self.results) - n["present"] - n["downloaded"]
        lines.append(f"{n['present']} present, {n['downloaded']} downloaded, {bad} mismatched")
        return "\n".join(lines)


def fetch_watcom(
    versions: Sequence[str] = (),
    *,
    manifest: Path | str | None = None,
    media_dir: Path | str | None = None,
    base: str = ARCHIVE_BASE,
    opener: Callable = urllib.request.urlopen,
) -> FetchReport:
    media_dir = Path(media_dir) if media_dir is not None else DEFAULT_MEDIA
    chosen = select(load_watcom_manifest(manifest), versions)
    return FetchReport(
        tuple(fetch_media(m, media_dir, base=base, opener=opener) for m in chosen)
    )


# ---- check ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class KeyFileCheck:
    key_file: KeyFile
    status: str  # "ok", "missing", "mismatch" or "known-bad"
    problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class VersionCheck:
    media: WatcomMedia
    root: Path
    results: tuple[KeyFileCheck, ...]

    def count(self, status: str) -> int:
        return sum(r.status == status for r in self.results)

    @property
    def ok(self) -> bool:
        """Known-bad files do not fail the check; having no key files to check does."""
        return bool(self.results) and all(r.status in ("ok", "known-bad") for r in self.results)

    def format(self) -> str:
        lines = [f"Watcom {self.media.version}: {self.root}"]
        if self.media.note:
            lines.append(f"  note: {self.media.note}")
        if not self.results:
            lines.append("  no key files recorded")
            return "\n".join(lines)
        for r in self.results:
            path = r.key_file.path
            if r.status == "ok":
                lines.append(f"  OK        {path}")
            elif r.status == "missing":
                lines.append(
                    f"  MISSING   {path}  (run `uv run reverseapoc install-watcom "
                    f"{self.media.version}`)"
                )
            elif r.status == "mismatch":
                line = f"  MISMATCH  {path}  " + "; ".join(r.problems)
                if r.key_file.wpack:
                    line += (
                        f"  (re-run `uv run reverseapoc install-watcom {self.media.version} "
                        "--force` to decode it)"
                    )
                lines.append(line)
            else:
                lines.append(f"  KNOWN BAD {path}  {r.key_file.note}".rstrip())
        lines.append(
            f"{self.count('ok')} ok, {self.count('mismatch')} mismatched, "
            f"{self.count('missing')} missing, {self.count('known-bad')} known bad"
        )
        return "\n".join(lines)


def check_version(media: WatcomMedia, install_dir: Path | str) -> VersionCheck:
    """Verify the key files of one installed version under `install_dir/<version>`."""
    root = Path(install_dir) / media.version
    results = []
    for kf in media.key_files:
        res = check_target(kf.as_target(), root / kf.path)
        status = "known-bad" if res.status == "ok" and kf.known_bad else res.status
        results.append(KeyFileCheck(kf, status, tuple(res.problems)))
    return VersionCheck(media, root, tuple(results))


@dataclass(frozen=True)
class WatcomReport:
    versions: tuple[VersionCheck, ...]

    @property
    def ok(self) -> bool:
        return all(v.ok for v in self.versions)

    def format(self) -> str:
        return "\n".join(v.format() for v in self.versions)


def check_watcom(
    versions: Sequence[str] = (),
    *,
    manifest: Path | str | None = None,
    install_dir: Path | str | None = None,
) -> WatcomReport:
    install_dir = Path(install_dir) if install_dir is not None else DEFAULT_INSTALL
    chosen = select(load_watcom_manifest(manifest), versions)
    return WatcomReport(tuple(check_version(m, install_dir) for m in chosen))


# ---- install -------------------------------------------------------------------------------


def _replace_with_retry(
    src: Path,
    dst: Path,
    *,
    attempts: int = 8,
    delay: float = 0.25,
    sleep: Callable[[float], None] | None = None,
) -> None:
    """os.replace, retrying PermissionError (Windows scanners briefly lock fresh files)."""
    sleep = sleep if sleep is not None else time.sleep
    for attempt in range(1, attempts + 1):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == attempts:
                raise
            sleep(delay * attempt)


def _decode_wpack_key_files(media: WatcomMedia, root: Path) -> None:
    """Replace each wpack key file in the extracted tree `root` by its decoded archive member
    (D-01). The parts are read from `root`; the result goes to the key file's own manifest path,
    never to a name taken from the archive."""
    for kf in media.key_files:
        if not kf.wpack:
            continue
        what = f"cannot decode {kf.path} for Watcom {media.version} from {', '.join(kf.wpack)}"
        missing = [part for part in kf.wpack if not (root / part).is_file()]
        if missing:
            raise WatcomError(f"{what}: {', '.join(missing)} not found")
        data = join_parts((root / part).read_bytes() for part in kf.wpack)
        try:
            decoded = decode_member(data, kf.wpack_member, expected_size=kf.size)
        except WpackError as exc:
            raise WatcomError(f"{what}: {exc}") from exc
        dest = root / kf.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(decoded)


def install_version(
    media: WatcomMedia,
    media_dir: Path | str,
    install_dir: Path | str,
    *,
    force: bool = False,
) -> VersionCheck:
    """Extract a verified ISO into `install_dir/<version>` (via a `.partial` directory) and
    decode its wpack key files there, before the finished tree replaces the old one."""
    iso = Path(media_dir) / media.local_name
    hint = f"run `uv run reverseapoc fetch-watcom {media.version}`"
    if not iso.is_file():
        raise WatcomError(f"{iso} not found; {hint}")
    problems = _file_problems(media, iso)
    if problems:
        raise WatcomError(f"{iso} does not match the manifest ({'; '.join(problems)}); {hint}")
    install_dir = Path(install_dir)
    target = install_dir / media.version
    if target.exists() and not force:
        raise WatcomError(f"{target} already exists; use --force to replace it")
    partial = install_dir / f".{media.version}.partial"
    if partial.exists():
        shutil.rmtree(partial)
    try:
        try:
            extract_all(iso, partial, skip_dirs=media.skip_dirs)
        except ISOError as exc:
            raise WatcomError(f"cannot extract Watcom {media.version} from {iso}: {exc}") from exc
        _decode_wpack_key_files(media, partial)
        if target.exists():
            shutil.rmtree(target)
        try:
            _replace_with_retry(partial, target)
        except PermissionError as exc:
            raise WatcomError(
                f"cannot move Watcom {media.version} into place ({exc}); "
                "something is holding the files (antivirus or indexer?), re-run the install"
            ) from exc
    finally:
        if partial.exists():
            shutil.rmtree(partial, ignore_errors=True)
    return check_version(media, install_dir)
