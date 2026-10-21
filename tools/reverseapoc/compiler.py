"""`reverseapoc cc`: compile one C source with the Watcom version and flags config/cflags.txt
assigns to it (D-11).

Two backends run the same NT-hosted `BINNT/WCC386.EXE`: natively on the Windows host, and under
wibo (/usr/local/bin/wibo) in the Linux container. Before any compile the hash gate (D-13)
checks size and SHA-1 of every binary the compiler executes or loads against
config/watcom.toml, and captures the compiler's own banner from a no-argument run. Guest paths
are root-relative with backslashes (Watcom reads `/` as an option switch), and the include path
is the selected version's own H directory only (D-14). The child environment is rebuilt from
scratch, because Watcom reads WCC386, INCLUDE and friends and they change codegen.

Output and build/logs/cc.log carry banners, paths, argv, exit codes and SHA-1s, never file bytes.
"""

from __future__ import annotations

import dataclasses
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import watcom
from .cflags import Rule, load_cflags, select_rule
from .targets import REPO_ROOT

WIBO = "/usr/local/bin/wibo"
WRAPPER_FLAGS = ("-zq", "-zld", "-bt=dos")
DEFAULT_LOG = REPO_ROOT / "build" / "logs" / "cc.log"
DEFAULT_STAMPS = REPO_ROOT / "build" / "cache"
KEPT_ENV = ("PATH",)
KEPT_ENV_WIN32 = ("SYSTEMROOT", "TEMP", "TMP")
COMPILER_EXE = "BINNT/WCC386.EXE"  # the NT-hosted driver both backends run

# How every compiler run is started: list argv, no shell, output captured as text.
_CAPTURE: dict[str, Any] = dict(
    capture_output=True, text=True, encoding="latin-1", errors="replace", check=False
)

Runner = Callable[..., subprocess.CompletedProcess]


class CompilerError(ValueError):
    """The compiler cannot be run safely: a gate, banner, path or backend check failed."""


def gate_paths(compiler: str, version: str) -> tuple[str, ...]:
    """The tree-relative binaries the gate checks: the NT driver, plus the DOS-extended compiler
    it loads from BINW on 10.x, plus the code generator DLL on 11.x."""
    if compiler != "wcc386":
        raise CompilerError(f"no pinned binaries for {compiler} in config/watcom.toml")
    paths = [COMPILER_EXE]
    if version.startswith("10."):
        paths.append("BINW/WCC386.EXE")
    if version.startswith("11."):
        paths.append("BINNT/WCCD386.DLL")
    return tuple(paths)


@dataclass(frozen=True)
class Gate:
    version: str
    root: Path  # the resolved tree, <watcom_dir>/<version>
    files: tuple[tuple[str, str], ...]  # (tree-relative path, sha1), manifest key-file order
    banner: str


def _install_hint(version: str) -> str:
    return f"run `uv run reverseapoc install-watcom {version}`"


def _gated_media(compiler: str, version: str, manifest: Path | str | None) -> watcom.WatcomMedia:
    """The manifest entry for `version`, cut down to the gated key files in manifest order."""
    media = watcom.load_watcom_manifest(manifest).get(version)
    if media is None:
        raise CompilerError(f"Watcom {version} is not in the manifest {manifest or ''}".rstrip())
    wanted = gate_paths(compiler, version)
    key_files = tuple(kf for kf in media.key_files if kf.path in wanted)
    pinned = {kf.path for kf in key_files}
    unpinned = next((path for path in wanted if path not in pinned), None)
    if unpinned is not None:
        raise CompilerError(
            f"the manifest pins no {unpinned} for Watcom {version}, so the gate cannot check it"
        )
    return dataclasses.replace(media, key_files=key_files)


def _refusal(check: watcom.KeyFileCheck, root: Path, version: str) -> str:
    detail = "; ".join(check.problems) or check.key_file.note
    status = f"{check.status} ({detail})" if detail else check.status
    return (
        f"Watcom {version}: {check.key_file.path} under {root} is {status}; "
        f"{_install_hint(version)}"
    )


def scrubbed_env(environ: Mapping[str, str], platform: str) -> dict[str, str]:
    """A child environment built from scratch: PATH, plus SYSTEMROOT, TEMP and TMP on win32."""
    kept = KEPT_ENV + (KEPT_ENV_WIN32 if platform == "win32" else ())
    return {name: environ[name] for name in kept if name in environ}


def runner_prefix(
    platform: str, *, which: Callable[[str], str | None] | None = None
) -> list[str]:
    """What runs in front of the Windows compiler: nothing on win32, wibo elsewhere."""
    if platform == "win32":
        return []
    which = which if which is not None else shutil.which
    if which(WIBO) is None:
        raise CompilerError(f"wibo not found at {WIBO}; run inside `docker compose run`")
    return [WIBO]


def _banner(exe: Path, version: str, runner: Runner, platform: str) -> str:
    """The first non-empty line of a no-argument run; it must name `Version <version>`."""
    proc = runner(
        [*runner_prefix(platform), str(exe)],
        cwd=exe.parents[1],
        env=scrubbed_env(os.environ, platform),
        **_CAPTURE,
    )
    text = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if f"Version {version}" not in line:
        raise CompilerError(
            f"{exe}: expected a banner naming Version {version}, got {line!r}; "
            f"{_install_hint(version)}"
        )
    return line


def check_gate(
    compiler: str,
    version: str,
    *,
    manifest: Path | str | None = None,
    watcom_dir: Path | str | None = None,
    stamps: Path | str | None = None,
    runner: Runner | None = None,
    platform: str | None = None,
) -> Gate:
    """Check the gated binaries of `version` against the manifest and capture the banner.
    Any status other than "ok" (missing, mismatch, known-bad) is refused before anything runs."""
    watcom_dir = Path(watcom_dir) if watcom_dir is not None else watcom.DEFAULT_INSTALL
    runner = runner if runner is not None else subprocess.run
    platform = platform if platform is not None else sys.platform
    check = watcom.check_version(_gated_media(compiler, version, manifest), watcom_dir)
    root = check.root.resolve()
    bad = next((result for result in check.results if result.status != "ok"), None)
    if bad is not None:
        raise CompilerError(_refusal(bad, root, version))
    banner = _banner(root / COMPILER_EXE, version, runner, platform)
    files = tuple((result.key_file.path, result.key_file.sha1) for result in check.results)
    return Gate(version, root, files, banner)


# ---- paths and argv ----------------------------------------------------------------------------


def _root_relative(path: Path | str, root: Path) -> str:
    """`path` relative to `root` as POSIX text; a path outside the root is refused."""
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(root):
        raise CompilerError(f"{path} is outside {root}")
    return resolved.relative_to(root).as_posix()


def guest_path(path: Path | str, root: Path | str, *, inside: bool) -> str:
    """`path` as the compiler gets it: relative to `root`, `/` rewritten to `\\`. With `inside`
    False (a Watcom tree, which may live outside the root) the path is made with os.path.relpath."""
    root = Path(root).resolve()
    if inside:
        rel = _root_relative(path, root)
    else:
        rel = Path(os.path.relpath(Path(path).resolve(), root)).as_posix()
    return rel.replace("/", "\\")


def build_argv(
    exe: Path | str,
    rule: Rule,
    src: str,
    obj: str,
    err: str,
    include: str,
    *,
    prefix: list[str],
) -> list[str]:
    return [
        *prefix,
        str(exe),
        *WRAPPER_FLAGS,
        f"-fr={err}",
        *rule.flags,
        f"-i={include}",
        src,
        f"-fo={obj}",
    ]


# ---- compile -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class CompileResult:
    src: Path
    obj: Path
    rule: Rule
    gate: Gate
    argv: tuple[str, ...]
    returncode: int
    output: str  # the compiler's own stdout and stderr

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.obj.is_file()

    def format(self) -> str:
        if self.ok:
            return (
                f"OK      {self.src.as_posix()} -> {self.obj.as_posix()}  {self.rule.spec}  "
                f"{self.gate.banner}"
            )
        return f"FAILED  {self.src.as_posix()}  {self.rule.spec}  exit {self.returncode}"

    def to_json(self) -> dict[str, Any]:
        """Names, paths, the spec, the banner, gate SHA-1s, argv and the exit code; never bytes."""
        return {
            "src": self.src.as_posix(),
            "obj": self.obj.as_posix(),
            "ok": self.ok,
            "spec": self.rule.spec,
            "rule_line": self.rule.lineno,
            "flags": list(self.rule.flags),
            "banner": self.gate.banner,
            "gate": [[path, sha1] for path, sha1 in self.gate.files],
            "argv": list(self.argv),
            "returncode": self.returncode,
        }


def _log_line(result: CompileResult) -> str:
    when = datetime.now(UTC).isoformat(timespec="seconds")
    gate = " ".join(f"{path}={sha1}" for path, sha1 in result.gate.files)
    fields = (
        when,
        result.rule.spec,
        result.gate.banner,
        gate,
        " ".join(result.argv),
        f"exit {result.returncode}",
    )
    return "  ".join(fields) + "\n"


def _append_log(log: Path, result: CompileResult) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(_log_line(result))


def compile_rule(
    rule: Rule,
    src: Path | str,
    obj: Path | str,
    *,
    root: Path | str | None = None,
    manifest: Path | str | None = None,
    watcom_dir: Path | str | None = None,
    runner: Runner | None = None,
    platform: str | None = None,
    log: Path | str | None = None,
    stamps: Path | str | None = None,
) -> CompileResult:
    """Compile `src` into `obj` with `rule`. Paths are checked first, then the gate, so a refused
    path or binary never reaches the runner. A non-zero exit leaves no object behind."""
    root = Path(root if root is not None else REPO_ROOT).resolve()
    watcom_dir = Path(watcom_dir) if watcom_dir is not None else watcom.DEFAULT_INSTALL
    runner = runner if runner is not None else subprocess.run
    platform = platform if platform is not None else sys.platform
    log = Path(log) if log is not None else DEFAULT_LOG
    src, obj = Path(src), Path(obj)
    guest_src = guest_path(src, root, inside=True)
    guest_obj = guest_path(obj, root, inside=True)
    guest_err = guest_path(obj.with_suffix(".err"), root, inside=True)  # next to the object
    include = guest_path(watcom_dir / rule.version / "H", root, inside=False)
    prefix = runner_prefix(platform)
    gate = check_gate(
        rule.compiler,
        rule.version,
        manifest=manifest,
        watcom_dir=watcom_dir,
        stamps=stamps,
        runner=runner,
        platform=platform,
    )
    exe = gate.root / COMPILER_EXE
    argv = build_argv(exe, rule, guest_src, guest_obj, guest_err, include, prefix=prefix)
    obj.parent.mkdir(parents=True, exist_ok=True)
    obj.unlink(missing_ok=True)
    proc = runner(argv, cwd=root, env=scrubbed_env(os.environ, platform), **_CAPTURE)
    if proc.returncode != 0:
        obj.unlink(missing_ok=True)
    output = "".join(part for part in (proc.stdout, proc.stderr) if part)
    result = CompileResult(src, obj, rule, gate, tuple(argv), proc.returncode, output)
    _append_log(log, result)
    return result


def compile_source(
    src: Path | str,
    obj: Path | str,
    *,
    cflags: Path | str | None = None,
    root: Path | str | None = None,
    manifest: Path | str | None = None,
    watcom_dir: Path | str | None = None,
    runner: Runner | None = None,
    platform: str | None = None,
    log: Path | str | None = None,
    stamps: Path | str | None = None,
) -> CompileResult:
    """Pick the cflags rule for `src` (by its root-relative POSIX path) and compile with it."""
    root = Path(root if root is not None else REPO_ROOT).resolve()
    versions = tuple(watcom.load_watcom_manifest(manifest))
    rule = select_rule(load_cflags(cflags, versions=versions), _root_relative(src, root))
    return compile_rule(
        rule,
        src,
        obj,
        root=root,
        manifest=manifest,
        watcom_dir=watcom_dir,
        runner=runner,
        platform=platform,
        log=log,
        stamps=stamps,
    )
