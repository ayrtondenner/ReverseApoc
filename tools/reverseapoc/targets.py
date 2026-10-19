"""Hash manifest of the original executables (config/targets.toml) and the orig/ checker."""

from __future__ import annotations

import hashlib
import string
import tomllib
import zlib
from dataclasses import dataclass, field
from pathlib import Path


def _find_repo_root() -> Path:
    """The checkout this package runs from: the nearest ancestor of the working directory that
    holds config/targets.toml, else the directory two levels above this package."""
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "config" / "targets.toml").is_file():
            return candidate
    return Path(__file__).resolve().parents[2]


REPO_ROOT = _find_repo_root()
DEFAULT_MANIFEST = REPO_ROOT / "config" / "targets.toml"
DEFAULT_ORIG = REPO_ROOT / "orig"

_HEX = frozenset(string.hexdigits.lower())


class ManifestError(ValueError):
    """config/targets.toml is missing a field or has a malformed value."""


@dataclass(frozen=True)
class Target:
    name: str  # file name inside orig/
    path: str  # relative path inside the game folder (GOG layout)
    size: int
    md5: str
    sha1: str
    crc32: int | None = None
    module: str | None = None
    description: str = ""


def _text(entry: dict, where: str, key: str, *, required: bool = True) -> str | None:
    value = entry.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{where}: '{key}' must be a non-empty string")
    return value


def _digest(entry: dict, where: str, key: str, length: int) -> str:
    value = _text(entry, where, key).lower()
    if len(value) != length or not set(value) <= _HEX:
        raise ManifestError(f"{where}: '{key}' must be {length} hex digits")
    return value


def _size(entry: dict, where: str) -> int:
    size = entry.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ManifestError(f"{where}: 'size' must be a non-negative integer")
    return size


def _crc32(entry: dict, where: str) -> int | None:
    crc32 = entry.get("crc32")
    if crc32 is not None and (not isinstance(crc32, int) or not 0 <= crc32 <= 0xFFFFFFFF):
        raise ManifestError(f"{where}: 'crc32' must be a 32-bit integer")
    return crc32


def _parse_target(i: int, entry: dict) -> Target:
    where = f"targets[{i}] ({entry.get('name', '?')})"
    name, path = _text(entry, where, "name"), _text(entry, where, "path")
    size = _size(entry, where)
    md5, sha1 = _digest(entry, where, "md5", 32), _digest(entry, where, "sha1", 40)
    crc32 = _crc32(entry, where)
    return Target(
        name=name,
        path=path,
        size=size,
        md5=md5,
        sha1=sha1,
        crc32=crc32,
        module=_text(entry, where, "module", required=False),
        description=entry.get("description", ""),
    )


def load_manifest(path: Path | str | None = None) -> list[Target]:
    """Load and validate the manifest (default: config/targets.toml)."""
    path = Path(path) if path is not None else DEFAULT_MANIFEST
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    entries = data.get("targets")
    if not entries:
        raise ManifestError(f"{path}: no [[targets]] entries")
    return [_parse_target(i, entry) for i, entry in enumerate(entries)]


@dataclass(frozen=True)
class FileHashes:
    size: int
    crc32: int
    md5: str
    sha1: str


def hash_file(path: Path) -> FileHashes:
    md5, sha1, crc, size = hashlib.md5(), hashlib.sha1(), 0, 0
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            md5.update(chunk)
            sha1.update(chunk)
            crc = zlib.crc32(chunk, crc)
            size += len(chunk)
    return FileHashes(size, crc, md5.hexdigest(), sha1.hexdigest())


@dataclass(frozen=True)
class TargetCheck:
    target: Target
    status: str  # "ok", "missing" or "mismatch"
    path: Path
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CheckReport:
    orig_dir: Path
    results: list[TargetCheck]

    @property
    def missing(self) -> list[TargetCheck]:
        return [r for r in self.results if r.status == "missing"]

    @property
    def mismatched(self) -> list[TargetCheck]:
        return [r for r in self.results if r.status == "mismatch"]

    @property
    def ok(self) -> bool:
        return all(r.status == "ok" for r in self.results)

    def format(self) -> str:
        width = max(len(r.target.name) for r in self.results)
        lines = [f"checking {self.orig_dir}"]
        for r in self.results:
            name = r.target.name.ljust(width)
            if r.status == "ok":
                lines.append(f"  OK        {name}  {r.target.size} bytes  sha1 {r.target.sha1}")
            elif r.status == "missing":
                lines.append(
                    f"  MISSING   {name}  (copy {r.target.path} from your game folder: "
                    "`uv run reverseapoc ingest`)"
                )
            else:
                lines.append(f"  MISMATCH  {name}  " + "; ".join(r.problems))
        n_ok = len(self.results) - len(self.missing) - len(self.mismatched)
        lines.append(
            f"{n_ok} ok, {len(self.mismatched)} mismatched, {len(self.missing)} missing"
        )
        return "\n".join(lines)


def check_target(target: Target, path: Path) -> TargetCheck:
    if not path.is_file():
        return TargetCheck(target, "missing", path)
    got = hash_file(path)
    problems = []
    if got.size != target.size:
        problems.append(f"size: expected {target.size}, got {got.size}")
    if target.crc32 is not None and got.crc32 != target.crc32:
        problems.append(f"crc32: expected {target.crc32:08x}, got {got.crc32:08x}")
    if got.md5 != target.md5:
        problems.append(f"md5: expected {target.md5}, got {got.md5}")
    if got.sha1 != target.sha1:
        problems.append(f"sha1: expected {target.sha1}, got {got.sha1}")
    return TargetCheck(target, "mismatch" if problems else "ok", path, problems)


def check_orig(
    orig_dir: Path | str | None = None, manifest: Path | str | None = None
) -> CheckReport:
    """Verify size, CRC32, MD5 and SHA-1 of every manifest target found in `orig_dir` (by file
    name) and report the ones that are missing."""
    orig_dir = Path(orig_dir) if orig_dir is not None else DEFAULT_ORIG
    targets = load_manifest(manifest)
    return CheckReport(orig_dir, [check_target(t, orig_dir / t.name) for t in targets])
