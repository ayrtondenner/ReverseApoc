"""Fake Watcom trees, a manifest writer and a fake compiler for the `reverseapoc cc` tests.

Every file in a fake tree holds a few made-up bytes, and the manifest is written from their
hashlib digests: no compiler bytes and no hash from config/watcom.toml ever appear here.
"""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Iterable
from pathlib import Path

import omfimage

# What FakeCompiler writes as the object: a tiny synthetic OMF module with a THEADR naming a made
# up source path and a COMENT 0xE9 dependency record, so its raw and normalized SHA-1 differ.
FAKE_OBJECT = omfimage.module(
    "C:\\fake\\src\\a.c",
    omfimage.coment(0xE9, b"\x00\x00\x00\x00\x09fake\\a.h"),
    omfimage.lnames("", "_TEXT", "CODE"),
    omfimage.segdef32(2, 3, 4),
    omfimage.ledata32(1, 0, b"\x90\x90\x90\xc3"),
)

# Per version: the files a fake tree holds. BINNT/WLINK.EXE is a key file the gate must ignore.
TREE_FILES: dict[str, dict[str, bytes]] = {
    "10.6": {
        "BINNT/WCC386.EXE": b"fake 10.6 NT driver",
        "BINW/WCC386.EXE": b"fake 10.6 DOS compiler",
        "BINNT/WLINK.EXE": b"fake 10.6 linker",
    },
    "11.0": {
        "BINNT/WCC386.EXE": b"fake 11.0 NT driver",
        "BINW/WCC386.EXE": b"fake 11.0 DOS compiler",
        "BINNT/WLINK.EXE": b"fake 11.0 linker",
        "BINNT/WCCD386.DLL": b"fake 11.0 code generator",
    },
}

BANNERS = {
    "10.6": "WATCOM C32 Optimizing Compiler  Version 10.6",
    "11.0": "Watcom C32 Optimizing Compiler  Version 11.0",
}


def make_tree(watcom_dir: Path, version: str, files: dict[str, bytes] | None = None) -> Path:
    """Write a fake `<watcom_dir>/<version>` tree with an H/ directory; return its root."""
    root = watcom_dir / version
    for rel, data in (TREE_FILES[version] if files is None else files).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (root / "H").mkdir(parents=True, exist_ok=True)
    (root / "H" / "STDIO.H").write_text("/* fake header */\n")
    return root


def _key_file(rel: str, data: bytes, known_bad: bool) -> str:
    lines = [
        "[[media.key_files]]",
        f'path = "{rel}"',
        f"size = {len(data)}",
        f'md5 = "{hashlib.md5(data).hexdigest()}"',
        f'sha1 = "{hashlib.sha1(data).hexdigest()}"',
    ]
    if known_bad:
        lines += ["known_bad = true", 'note = "damaged on the disc"']
    return "\n".join(lines) + "\n"


def write_watcom_manifest(
    path: Path,
    trees: dict[str, dict[str, bytes]],
    *,
    known_bad: Iterable[tuple[str, str]] = (),
) -> Path:
    """A config/watcom.toml lookalike describing `trees` ({version: {path: bytes}}); the
    (version, path) pairs in `known_bad` are marked known_bad."""
    bad = set(known_bad)
    parts = []
    for version, files in trees.items():
        parts.append(
            f'[[media]]\nversion = "{version}"\nitem = "Item"\nfile = "w{version}.iso"\n'
            f'size = 1\nmd5 = "{"0" * 32}"\nsha1 = "{"0" * 40}"\n'
        )
        parts.extend(_key_file(rel, data, (version, rel) in bad) for rel, data in files.items())
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def sha1_of(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


class FakeCompiler:
    """A runner in place of subprocess.run. A call with no argument after the compiler prints
    the banner of the version whose tree holds the compiler; a compile call writes `obj_bytes`
    (FAKE_OBJECT by default) to the `-fo=` object (relative to `cwd`, backslashes as Watcom gets
    them) and exits with `rc`. A failing compile also writes the `-fr=` error file, as Watcom
    does."""

    def __init__(
        self,
        *,
        rc: int = 0,
        banners: dict[str, str] | None = None,
        write_obj: bool = True,
        output: str = "",
        obj_bytes: bytes = FAKE_OBJECT,
    ) -> None:
        self.rc = rc
        self.banners = dict(BANNERS if banners is None else banners)
        self.write_obj = write_obj
        self.output = output
        self.obj_bytes = obj_bytes
        self.calls: list[tuple[list[str], dict]] = []

    @staticmethod
    def _host_path(kwargs: dict, args: list[str], option: str) -> Path:
        guest = next(arg for arg in args if arg.startswith(option))[len(option) :]
        return Path(kwargs["cwd"]) / guest.replace("\\", "/")

    @staticmethod
    def _exe_index(argv: list[str]) -> int:
        return next(i for i, arg in enumerate(argv) if arg.upper().endswith("WCC386.EXE"))

    def __call__(self, argv, **kwargs) -> subprocess.CompletedProcess:
        argv = list(argv)
        self.calls.append((argv, kwargs))
        exe = self._exe_index(argv)
        args = argv[exe + 1 :]
        if not args:
            version = Path(argv[exe]).parents[1].name
            out = f"{self.banners[version]}\nCopyright by nobody\nUsage: wcc386 [options] file\n"
            return subprocess.CompletedProcess(argv, 1, stdout=out, stderr="")
        if self.write_obj:
            self._host_path(kwargs, args, "-fo=").write_bytes(self.obj_bytes)
        if self.rc != 0:
            self._host_path(kwargs, args, "-fr=").write_text("Error! E1009: fake error\n")
        return subprocess.CompletedProcess(argv, self.rc, stdout=self.output, stderr="")

    @property
    def compiles(self) -> list[list[str]]:
        """The argv of every compile call (banner probes left out)."""
        return [argv for argv, _ in self.calls if argv[self._exe_index(argv) + 1 :]]

    @property
    def probes(self) -> list[list[str]]:
        """The argv of every no-argument banner probe."""
        return [argv for argv, _ in self.calls if not argv[self._exe_index(argv) + 1 :]]
