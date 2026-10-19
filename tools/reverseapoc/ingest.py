"""Copy the original executables from the user's own game install into orig/ and verify them.

The game folders come from APOC_STEAM_FOLDER (preferred) and APOC_GOG_FOLDER, read from the
environment or, failing that, from the .env file at the repository root. Values may use Windows
`%VAR%` or `${VAR}` references (e.g. `%ProgramFiles(x86)%\\Steam\\...`). The game folders are
only ever read.
"""

from __future__ import annotations

import filecmp
import os
import re
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .targets import DEFAULT_ORIG, REPO_ROOT, CheckReport, Target, check_orig, load_manifest

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
