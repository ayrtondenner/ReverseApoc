"""Watcom compiler media: manifest (config/watcom.toml), download, install and key-file check."""

from __future__ import annotations

import hashlib
import os
import shutil
import tomllib
import urllib.parse
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .iso9660 import extract_all
from .targets import (
    REPO_ROOT,
    ManifestError,
    Target,
    _crc32,
    _digest,
    _size,
    _text,
    check_target,
    hash_file,
)

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

    @property
    def local_name(self) -> str:
        return PurePosixPath(self.file).name

    def url(self, base: str = ARCHIVE_BASE) -> str:
        return f"{base}/{self.item}/{urllib.parse.quote(self.file)}"


def _parse_key_file(where: str, entry: object) -> KeyFile:
    if not isinstance(entry, dict):
        raise ManifestError(f"{where}: must be a table")
    known_bad = entry.get("known_bad", False)
    if not isinstance(known_bad, bool):
        raise ManifestError(f"{where}: 'known_bad' must be true or false")
    note = entry.get("note", "")
    if not isinstance(note, str):
        raise ManifestError(f"{where}: 'note' must be a string")
    return KeyFile(
        path=_text(entry, where, "path"),
        size=_size(entry, where),
        md5=_digest(entry, where, "md5", 32),
        sha1=_digest(entry, where, "sha1", 40),
        crc32=_crc32(entry, where),
        known_bad=known_bad,
        note=note,
    )


def _parse_media(i: int, entry: dict) -> WatcomMedia:
    where = f"media[{i}] ({entry.get('version', '?')})"
    raw_keys = entry.get("key_files", [])
    if not isinstance(raw_keys, list):
        raise ManifestError(f"{where}: 'key_files' must be an array of tables")
    key_files = tuple(
        _parse_key_file(f"{where} key_files[{j}]", kf) for j, kf in enumerate(raw_keys)
    )
    return WatcomMedia(
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
    """Load and validate the media manifest (default: config/watcom.toml), keyed by version."""
    path = Path(path) if path is not None else DEFAULT_WATCOM_MANIFEST
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    entries = data.get("media")
    if not entries:
        raise ManifestError(f"{path}: no [[media]] entries")
    manifest: dict[str, WatcomMedia] = {}
    for i, entry in enumerate(entries):
        media = _parse_media(i, entry)
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


def _media_problems(media: WatcomMedia, size: int, md5: str, sha1: str) -> list[str]:
    problems = []
    if size != media.size:
        problems.append(f"size: expected {media.size}, got {size}")
    if md5 != media.md5:
        problems.append(f"md5: expected {media.md5}, got {md5}")
    if sha1 != media.sha1:
        problems.append(f"sha1: expected {media.sha1}, got {sha1}")
    return problems


def _file_problems(media: WatcomMedia, path: Path) -> list[str]:
    got = hash_file(path)
    return _media_problems(media, got.size, got.md5, got.sha1)


# ---- fetch ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class MediaResult:
    media: WatcomMedia
    path: Path
    action: str  # "present", "downloaded" or "mismatch"
    problems: tuple[str, ...] = ()


def fetch_media(
    media: WatcomMedia,
    media_dir: Path | str,
    *,
    base: str = ARCHIVE_BASE,
    opener: Callable = urllib.request.urlopen,
    chunk: int = 1 << 20,
) -> MediaResult:
    """Download one ISO into `media_dir` unless a verified copy is already there. Streams into
    `<file>.part` and only renames it over the final name once size, MD5 and SHA-1 match."""
    media_dir = Path(media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    dest = media_dir / media.local_name
    part = media_dir / (media.local_name + ".part")
    if dest.is_file() and not _file_problems(media, dest):
        return MediaResult(media, dest, "present")

    req = urllib.request.Request(media.url(base), headers={"User-Agent": "reverseapoc"})
    md5, sha1, total = hashlib.md5(), hashlib.sha1(), 0
    try:
        with opener(req, timeout=60) as resp:
            length = resp.headers.get("Content-Length")
            if length is not None and str(length).strip() != str(media.size):
                problem = f"Content-Length: expected {media.size}, server says {length}"
                return MediaResult(media, dest, "mismatch", (problem,))
            with part.open("wb") as out:
                while block := resp.read(chunk):
                    total += len(block)
                    if total > media.size:
                        break
                    out.write(block)
                    md5.update(block)
                    sha1.update(block)
    except OSError as exc:
        return MediaResult(media, dest, "mismatch", (f"download failed: {exc}",))
    if total > media.size:
        part.unlink(missing_ok=True)
        problem = f"size: more than the expected {media.size} bytes were sent"
        return MediaResult(media, dest, "mismatch", (problem,))
    problems = _media_problems(media, total, md5.hexdigest(), sha1.hexdigest())
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
                lines.append(f"  MISMATCH  {path}  " + "; ".join(r.problems))
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


def install_version(
    media: WatcomMedia,
    media_dir: Path | str,
    install_dir: Path | str,
    *,
    force: bool = False,
) -> VersionCheck:
    """Extract a verified ISO into `install_dir/<version>` (via a `.partial` directory)."""
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
        extract_all(iso, partial)
        if target.exists():
            shutil.rmtree(target)
        os.replace(partial, target)
    finally:
        if partial.exists():
            shutil.rmtree(partial, ignore_errors=True)
    return check_version(media, install_dir)
