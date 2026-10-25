"""The C89 lint gate (SPL-12, D-14): `clang -fsyntax-only -std=gnu89` over the C sources, with
the Watcom compat header force-included.

Watcom C 10.x is a C89 compiler; the gate catches what it would reject or compile differently
(above all a declaration after a statement) before a source reaches wcc386. clang 18 is pinned in
the Docker image, so the gate runs in the container; on the host it fails early with the container
command. `include/watcom_compat.h` empties Watcom's keywords and silences `#pragma aux` for clang
only, and `-D__WATCOMC__` is the version the game was built with (10.6 -> 1060; it changes only if
the matches settle on 10.5 or 11.0). `-nostdinc` keeps the gate independent of Watcom's own H
directory, which is user-supplied and absent in CI.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .targets import REPO_ROOT

WATCOMC_VALUE = "1060"  # __WATCOMC__ of Watcom C 10.6 (D-14)
COMPAT_HEADER = "include/watcom_compat.h"  # relative to the repo root, the lint cwd
LINT_FLAGS = (
    "-fsyntax-only",
    "-std=gnu89",
    "-Werror=declaration-after-statement",
    "--target=i386-unknown-none",  # 32-bit int, long and pointers, like wcc386 flat
    "-ffreestanding",
    "-nostdinc",
    "-funsigned-char",  # Watcom's char is unsigned by default
    "-D__386__",
    "-D__FLAT__",
    f"-D__WATCOMC__={WATCOMC_VALUE}",
    "-Iinclude",
    "-include",
    COMPAT_HEADER,
)
# The same dialect for clangd's compile_commands.json (plan 05-14): everything but -fsyntax-only.
CLANGD_FLAGS = tuple(flag for flag in LINT_FLAGS if flag != "-fsyntax-only")
CLANG_NAMES = ("clang-18", "clang")
CONTAINER_HINT = "docker compose run --rm build uv run reverseapoc lint"
SOURCE_SUFFIX = ".c"

Runner = Callable[..., subprocess.CompletedProcess]
_default_runner: Runner = subprocess.run


class LintError(ValueError):
    """The lint gate cannot run: no clang, a path that does not exist, or a named file that is
    not a .c source."""


@dataclass(frozen=True)
class LintResult:
    ok: bool
    files: tuple[Path, ...]
    output: str

    def format(self) -> str:
        verdict = "ok" if self.ok else "FAILED"
        head = f"lint: {len(self.files)} files, {verdict}"
        return f"{head}\n{self.output.rstrip()}" if self.output.strip() else head

    def to_json(self) -> dict[str, Any]:
        return {"ok": self.ok, "files": [str(path) for path in self.files], "output": self.output}


def find_clang() -> str:
    """clang-18, else clang, from PATH; the gate runs in the container when neither is there."""
    for name in CLANG_NAMES:
        found = shutil.which(name)
        if found:
            return found
    raise LintError(
        f"{' / '.join(CLANG_NAMES)} not found on PATH; the lint gate runs in the container: "
        f"{CONTAINER_HINT}"
    )


def lint_argv(path: Path | str, *, clang: str) -> list[str]:
    """The clang command that lints one file (run from the repo root)."""
    return [clang, *LINT_FLAGS, str(path)]


def _sources_under(path: Path) -> Iterable[Path]:
    if path.is_dir():
        return path.rglob(f"*{SOURCE_SUFFIX}")
    if not path.is_file():
        raise LintError(f"{path} not found")
    if path.suffix != SOURCE_SUFFIX:  # named on purpose: refuse it, never skip it silently
        raise LintError(f"{path} is not a {SOURCE_SUFFIX} source")
    return [path]


def collect_sources(paths: Iterable[Path | str]) -> list[Path]:
    """The *.c files under the given directories and the given *.c files, sorted, each once. A
    named file that is not a *.c file raises LintError."""
    found: set[Path] = set()
    for path in paths:
        found.update(_sources_under(Path(path)))
    return sorted(found)


def run_lint(
    paths: Sequence[Path | str],
    *,
    runner: Runner | None = None,
    cwd: Path = REPO_ROOT,
    clang: str | None = None,
) -> LintResult:
    """Lint every C source under `paths`, one clang run per file from `cwd` (the repo root, which
    -Iinclude and the compat header path are relative to). No sources is a pass and needs no
    clang; otherwise a missing clang raises LintError naming the container command."""
    sources = collect_sources(paths)
    if not sources:
        return LintResult(True, (), "")
    clang = clang or find_clang()
    runner = runner if runner is not None else _default_runner
    ok = True
    output = []
    for source in sources:
        proc = runner(
            lint_argv(source, clang=clang),
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        ok = ok and proc.returncode == 0
        output.append(f"{proc.stdout or ''}{proc.stderr or ''}")
    return LintResult(ok, tuple(sources), "".join(output))
