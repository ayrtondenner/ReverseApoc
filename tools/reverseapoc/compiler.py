"""`reverseapoc cc`: compile one C source with the Watcom version and flags config/cflags.txt
assigns to it (D-11).

Two backends run the same NT-hosted `BINNT/WCC386.EXE`: natively on the Windows host, and under
wibo (/usr/local/bin/wibo) in the Linux container. Before any compile the hash gate (D-13)
checks size and SHA-1 of every binary the compiler executes or loads against
config/watcom.toml, and captures the compiler's own banner from a no-argument run. Guest paths
are root-relative with backslashes (Watcom reads `/` as an option switch), and the include path
is the compile root's include/ (project headers, D-12) followed by the selected version's own H
directory, and nothing else (D-14). The child environment is rebuilt from
scratch, because Watcom reads WCC386, INCLUDE and friends and they change codegen.

Output and build/logs/cc.log carry banners, paths, argv, exit codes and SHA-1s, never file bytes;
cc.log appends from parallel processes are serialised by an OS lock on the sidecar `<log>.lock`.
"""

from __future__ import annotations

import dataclasses
import errno
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import omf, watcom
from .cflags import Rule, load_cflags, select_rule
from .fileio import write_atomic
from .targets import REPO_ROOT, hash_file

# The log lock is an OS lock, which the kernel frees when its holder exits.
if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

WIBO = "/usr/local/bin/wibo"
WRAPPER_FLAGS = ("-zq", "-zld", "-bt=dos")
DEFAULT_LOG = REPO_ROOT / "build" / "logs" / "cc.log"
LOCK_SUFFIX = ".lock"  # the lock sidecar sits next to whatever --log names
_LOCK_RETRY_SECONDS = 0.001
DEFAULT_STAMPS = REPO_ROOT / "build" / "cache"
KEPT_ENV = ("PATH",)
KEPT_ENV_WIN32 = ("SYSTEMROOT", "TEMP", "TMP")
COMPILER_EXE = "BINNT/WCC386.EXE"  # the NT-hosted driver both backends run
# Project headers (include/common.h). compile_rule joins INCLUDE_DIR to the compile root, not
# to REPO_ROOT, so a worktree (or any other root) compiles with its own include/.
INCLUDE_DIR = "include"
PROJECT_INCLUDE = REPO_ROOT / INCLUDE_DIR
OBJ_SUFFIX = ".obj"  # the only suffix -o accepts: the object is deleted, then rewritten

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


# ---- the gate stamp ----------------------------------------------------------------------------
# ninja runs one `cc` process per source, so "hash once per run" needs a file:
# build/cache/watcom-<compiler>-<version>.json holds {"root", "files": {path: [size, mtime_ns,
# sha1]}, "banner"}. It is reused only while the root is the same, every gated file has the same
# size and mtime, and every recorded SHA-1 is still the manifest's. Parallel processes share
# nothing else: each writes its own temporary file and swaps the stamp in whole
# (fileio.write_atomic), and a torn, unreadable or wrong-shaped stamp is a miss that is
# re-hashed, never trusted.


def _stamp_path(stamps: Path, compiler: str, version: str) -> Path:
    return stamps / f"watcom-{compiler}-{version}.json"


def _stamp_files(root: Path, media: watcom.WatcomMedia) -> dict[str, list] | None:
    """{path: [size, mtime_ns, manifest sha1]} for the gated files, or None if one is missing.
    Taken BEFORE hashing, so a file changed after this stat no longer matches the stamp."""
    files: dict[str, list] = {}
    for kf in media.key_files:
        try:
            st = (root / kf.path).stat()
        except OSError:
            return None
        files[kf.path] = [st.st_size, st.st_mtime_ns, kf.sha1]
    return files


def _read_stamp(stamp: Path, root: Path, files: dict[str, list]) -> str | None:
    """The cached banner if the stamp describes `root` and exactly `files`; otherwise None."""
    try:
        data = json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("root") != str(root):
        return None
    banner = data.get("banner")
    if data.get("files") != files or not isinstance(banner, str):
        return None
    return banner


def _write_stamp(stamp: Path, root: Path, files: dict[str, list], banner: str) -> None:
    """Best effort: the stamp is only a cache, so a write that loses a race with a parallel
    `cc` (or cannot happen at all) costs a re-hash next time, never a failed compile."""
    data = {"root": str(root), "files": files, "banner": banner}
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(stamp, (json.dumps(data, indent=2) + "\n").encode("utf-8"))
    except OSError:
        pass


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
    """Check the gated binaries of `version` against the manifest and capture the banner, or
    reuse both from a still-valid stamp. Any status other than "ok" (missing, mismatch,
    known-bad) is refused before anything runs."""
    watcom_dir = Path(watcom_dir) if watcom_dir is not None else watcom.DEFAULT_INSTALL
    stamps = Path(stamps) if stamps is not None else DEFAULT_STAMPS
    runner = runner if runner is not None else subprocess.run
    platform = platform if platform is not None else sys.platform
    media = _gated_media(compiler, version, manifest)
    root = (watcom_dir / version).resolve()
    gate_files = tuple((kf.path, kf.sha1) for kf in media.key_files)
    stamp = _stamp_path(stamps, compiler, version)
    files = _stamp_files(root, media)
    banner = _read_stamp(stamp, root, files) if files is not None else None
    if banner is not None:
        return Gate(version, root, gate_files, banner)

    if not root.is_dir():
        raise CompilerError(
            f"Watcom {version} is not installed: {root} does not exist; {_install_hint(version)}"
        )
    check = watcom.check_version(media, watcom_dir)
    bad = next((result for result in check.results if result.status != "ok"), None)
    if bad is not None:
        raise CompilerError(_refusal(bad, root, version))
    banner = _banner(root / COMPILER_EXE, version, runner, platform)
    if files is not None:
        _write_stamp(stamp, root, files, banner)
    return Gate(version, root, gate_files, banner)


# ---- paths and argv ----------------------------------------------------------------------------


# What a guest path may hold once it is relative: configure.py's _SAFE_ORIG without ":".
# Watcom reads `/` as an option switch and splits its command line on spaces.
_SAFE_PATH = re.compile(r"[A-Za-z0-9._/-]+")


def _check_guest(path: Path | str, rel: str) -> None:
    """Refuse a relative path the compiler would misread: a leading `-` (an option), a space
    (a split) or any character outside _SAFE_PATH (the first one is named)."""
    if rel.startswith("-"):
        raise CompilerError(f"{path} starts with '-', which Watcom would read as an option")
    if " " in rel:
        raise CompilerError(f"{path} holds a space, which splits Watcom's command line")
    bad = next((c for c in rel if not _SAFE_PATH.fullmatch(c)), None)
    if bad is not None:
        raise CompilerError(f"{path} holds {bad!r}; only [A-Za-z0-9._/-] may reach the compiler")


def _root_relative(path: Path | str, root: Path) -> str:
    """`path` relative to `root` as checked POSIX text. A `..` segment in the path as given, a
    path that resolves outside the root and an unsafe character are refused."""
    if ".." in Path(path).parts:
        raise CompilerError(f"{path} holds a '..' segment; name it without one")
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(root):
        raise CompilerError(f"{path} is outside {root}")
    rel = resolved.relative_to(root).as_posix()
    _check_guest(path, rel)
    return rel


def _tree_relative(path: Path | str, root: Path) -> str:
    """A Watcom tree path relative to `root`, which may climb out of it with `..`."""
    try:
        rel = Path(os.path.relpath(Path(path).resolve(), root)).as_posix()
    except ValueError as exc:  # another drive on Windows
        raise CompilerError(f"the Watcom tree must be on the same drive as {root}") from exc
    _check_guest(path, rel)
    return rel


def guest_path(path: Path | str, root: Path | str, *, inside: bool) -> str:
    """`path` as the compiler gets it: relative to `root`, `/` rewritten to `\\`. With `inside`
    (a source, object or error file) it must lie inside the root; otherwise (a Watcom tree's H
    directory) it is made with os.path.relpath and may hold `..` segments."""
    root = Path(root).resolve()
    rel = _root_relative(path, root) if inside else _tree_relative(path, root)
    return rel.replace("/", "\\")


def _check_object_name(obj: Path) -> None:
    """The object is deleted before the compile and rewritten by it, so it must end in
    OBJ_SUFFIX: -o never names a source, a header or the error file. Checked before the error
    file's name is derived from it, so a path without a name (`-o .`) is refused here too."""
    if obj.suffix != OBJ_SUFFIX:
        raise CompilerError(f"{obj} must end in {OBJ_SUFFIX}; the compile deletes and rewrites it")


def _check_log_name(log: Path) -> None:
    """The log's lock sidecar is `<log>.lock`, so the log needs a file name. Checked before the
    compile, so a path without a name (`--log .`, `--log /`) never reaches the runner."""
    if not log.name:
        raise CompilerError(f"--log {log} names no file; the lock sidecar is <log>{LOCK_SUFFIX}")


def _check_outputs(src: Path, obj: Path, err: Path) -> None:
    """Refuse outputs that would destroy the source: the object is deleted before the compile
    and rewritten by it, and the error file is rewritten, so neither may be the source."""
    source = src.resolve()
    clash = next((out for out in (obj, err) if out.resolve() == source), None)
    if clash is not None:
        raise CompilerError(f"{clash} is the source {src}; the compile would overwrite it")


def _include_list(root: Path, watcom_dir: Path, version: str) -> str:
    """The one -i= value: the compile root's include/ first, then `version`'s own H directory,
    joined by Watcom's `;` list separator. No other directory, so no other tree's headers."""
    project = guest_path(root / INCLUDE_DIR, root, inside=True)
    tree = guest_path(watcom_dir / version / "H", root, inside=False)
    return f"{project};{tree}"


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
    # The object's SHA-1 over the whole file, and omf.normalized_object_sha1 (THEADR and COMENT
    # 0xE9 dropped), which is what native and wibo compiles are compared by (D-03). None when
    # the compile failed.
    object_sha1: str | None = None
    normalized_sha1: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.obj.is_file()

    def hashes(self) -> str:
        """`sha1 <raw>  normalized <normalized>`, or "" when there is no object."""
        if self.object_sha1 is None:
            return ""
        return f"sha1 {self.object_sha1}  normalized {self.normalized_sha1}"

    def format(self) -> str:
        if self.ok:
            return (
                f"OK      {self.src.as_posix()} -> {self.obj.as_posix()}  {self.rule.spec}  "
                f"{self.gate.banner}  {self.hashes()}"
            )
        return f"FAILED  {self.src.as_posix()}  {self.rule.spec}  exit {self.returncode}"

    def to_json(self) -> dict[str, Any]:
        """Names, paths, the spec, the banner, gate and object SHA-1s, argv and the exit code;
        never bytes."""
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
            "object_sha1": self.object_sha1,
            "normalized_sha1": self.normalized_sha1,
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
        result.hashes(),
        f"exit {result.returncode}",
    )
    return "  ".join(field for field in fields if field) + "\n"


def _object_hashes(obj: Path) -> tuple[str, str]:
    """(raw SHA-1, normalized SHA-1) of a freshly written object. An object that is not an OMF
    module cannot be trusted, so it is deleted and the compile refused."""
    try:
        return hash_file(obj).sha1, omf.normalized_object_sha1(obj.read_bytes())
    except omf.OMFError as exc:
        obj.unlink(missing_ok=True)
        raise CompilerError(f"{obj} is not an OMF object module ({exc}); it was deleted") from exc


def _lock_path(log: Path) -> Path:
    return log.with_name(log.name + LOCK_SUFFIX)


if sys.platform == "win32":

    def _try_lock(fd: int) -> bool:
        """One non-blocking try for byte 0. False on EACCES, any other error is raised. EACCES
        is lock contention, but the Windows C runtime also sets it for access-denied,
        sharing-violation and network-denied errors, and `_acquire` retries those too. The
        wait has no deadline by design (plan 04-13), so a failure that persists, or a holder
        that never exits, makes it spin. The blocking msvcrt modes retry once per second, so
        they are not used."""
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno != errno.EACCES:
                raise
            return False
        return True

    def _acquire(fh) -> None:
        fh.seek(0)
        while not _try_lock(fh.fileno()):
            time.sleep(_LOCK_RETRY_SECONDS)

    def _release(fh) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)

else:

    def _acquire(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)

    def _release(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


@contextmanager
def _log_lock(log: Path) -> Iterator[None]:
    """Hold the OS lock on `<log>.lock`. "a+b" creates the sidecar if needed and never
    truncates or writes it. The sidecar is never deleted: deleting would reopen a
    create/delete race, and a dead holder leaves nothing to clean up, because the OS lock
    dies with the process."""
    with open(_lock_path(log), "a+b") as fh:
        _acquire(fh)
        try:
            yield
        finally:
            _release(fh)


def _append_log(log: Path, result: CompileResult) -> None:
    """Append one line for `result`. The log is opened, written and closed inside the lock,
    and closed before the release: on the container's 9p bind mount the bytes reach the
    server at close, and there and in the Windows UCRT append is read-EOF-then-write. Parallel
    `cc` within one environment is safe; the host and a container writing the same log at
    once are not covered, because their OS locks do not see each other. A log that exists but
    is not a regular file (/dev/null, a FIFO, a console) is a device: it needs no append
    serialisation and its directory may not take a sidecar, so it is written without the lock."""
    log.parent.mkdir(parents=True, exist_ok=True)
    line = _log_line(result)
    if log.exists() and not log.is_file():
        with log.open("a", encoding="utf-8") as fh:
            fh.write(line)
        return
    with _log_lock(log):
        with log.open("a", encoding="utf-8") as fh:
            fh.write(line)


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
    """Compile `src` into `obj` with `rule`. Paths and outputs are checked first, then the gate,
    so a refused path or binary never reaches the runner and nothing is deleted. A non-zero exit
    leaves no object behind."""
    root = Path(root if root is not None else REPO_ROOT).resolve()
    watcom_dir = Path(watcom_dir) if watcom_dir is not None else watcom.DEFAULT_INSTALL
    runner = runner if runner is not None else subprocess.run
    platform = platform if platform is not None else sys.platform
    log = Path(log) if log is not None else DEFAULT_LOG
    src, obj = Path(src), Path(obj)
    guest_src = guest_path(src, root, inside=True)
    guest_obj = guest_path(obj, root, inside=True)
    _check_object_name(obj)
    _check_log_name(log)
    err = obj.with_suffix(".err")  # next to the object
    guest_err = guest_path(err, root, inside=True)
    _check_outputs(src, obj, err)
    include = _include_list(root, watcom_dir, rule.version)
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
    hashes: tuple[str | None, str | None] = (None, None)
    if proc.returncode != 0:
        obj.unlink(missing_ok=True)
    elif obj.is_file():
        hashes = _object_hashes(obj)
    output = "".join(part for part in (proc.stdout, proc.stderr) if part)
    result = CompileResult(src, obj, rule, gate, tuple(argv), proc.returncode, output, *hashes)
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
