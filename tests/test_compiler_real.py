"""Real compiles through `reverseapoc cc`'s wrapper (CID-01, CID-02).

The same tests run natively on the Windows host and under wibo inside `docker compose run`. They
are skipped only without a compiler runner or an installed tree (conftest.requires_runner and
requires_version), or when a version's hash gate refuses its tree (the skip reason then starts
`Watcom <version>:`). Sources, objects, logs and gate stamps live under build/test-cc/<test>/
(gitignored); nothing is ever written under third_party/ or orig/. Assertions compare SHA-1s,
public names and short x86 encodings written here as literals, never bytes taken from a file.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT, WATCOM_DIR, requires_runner, requires_version
from reverseapoc import omf
from reverseapoc.cflags import Rule
from reverseapoc.compiler import (
    CompilerError,
    CompileResult,
    check_gate,
    compile_rule,
    compile_source,
    gate_paths,
)
from reverseapoc.watcom import load_watcom_manifest

CC_ROOT = REPO_ROOT / "build" / "test-cc"
VERSIONS = ("10.5", "10.6", "11.0")
FLAGS = ("-5r", "-s")

# C89: declarations first, block comments only.
BYTE_COMPARE = """\
/* a byte compare: -5r gives setcc al; and eax,0FFh and -3r gives setcc al; movzx eax,al */
int pr_eq5(unsigned char c)
{
    return c == 5;
}
"""


@pytest.fixture
def cc_root(request) -> Path:
    """A fresh build/test-cc/<test name> directory for this test (removed and recreated)."""
    path = CC_ROOT / re.sub(r"[^A-Za-z0-9._-]", "_", request.node.name)
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def _require_compiler(version: str, root_dir: Path) -> None:
    """Skip unless `version` can run here: a runner, its tree, and a gate that accepts it."""
    requires_runner()
    requires_version(version)
    try:
        check_gate("wcc386", version, watcom_dir=WATCOM_DIR, stamps=root_dir / "stamps")
    except CompilerError as exc:
        pytest.skip(f"Watcom {version}: gate refused ({exc})")


def _compile(
    root_dir: Path, version: str, flags: tuple[str, ...], name: str, text: str
) -> CompileResult:
    """Write `text` to root_dir/name and compile it into root_dir/<stem>.obj with one rule."""
    src = root_dir / name
    src.write_text(text, encoding="ascii")
    return compile_rule(
        Rule("*", "wcc386", version, flags, 0),
        src,
        src.with_suffix(".obj"),
        root=REPO_ROOT,
        watcom_dir=WATCOM_DIR,
        log=root_dir / "cc.log",
        stamps=root_dir / "stamps",
    )


def _gated_sha1s(version: str) -> tuple[tuple[str, str], ...]:
    """(path, sha1) of the gated binaries, in manifest key-file order, from config/watcom.toml."""
    wanted = gate_paths("wcc386", version)
    media = load_watcom_manifest()[version]
    return tuple((kf.path, kf.sha1) for kf in media.key_files if kf.path in wanted)


def _last_log_line(root_dir: Path) -> str:
    return (root_dir / "cc.log").read_text(encoding="utf-8").splitlines()[-1]


# ---- Task 1: one real compile per version ------------------------------------------------------


@pytest.mark.parametrize("version", VERSIONS)
def test_compile_real(cc_root, version):
    _require_compiler(version, cc_root)
    result = _compile(cc_root, version, FLAGS, "eq.c", BYTE_COMPARE)
    assert result.ok, result.output
    assert result.obj.is_file()
    assert f"Version {version}" in result.gate.banner
    expected = _gated_sha1s(version)
    assert len(expected) == len(gate_paths("wcc386", version))
    assert result.gate.files == expected
    assert result.object_sha1 is not None and result.normalized_sha1 is not None
    line = _last_log_line(cc_root)
    assert result.gate.banner in line
    for path, sha1 in expected:
        assert f"{path}={sha1}" in line
    assert f"sha1 {result.object_sha1}  normalized {result.normalized_sha1}" in line


@pytest.mark.parametrize("version", VERSIONS)
def test_normalized_hash_is_stable(cc_root, version):
    _require_compiler(version, cc_root)
    first = _compile(cc_root, version, FLAGS, "eq.c", BYTE_COMPARE)
    second = _compile(cc_root, version, FLAGS, "eq.c", BYTE_COMPARE)
    assert first.ok and second.ok, first.output + second.output
    assert first.normalized_sha1 == second.normalized_sha1


# ---- Task 2: real codegen proves the wrapper's invariants --------------------------------------

# setcc al (0F 90..9F C0), then the zero extension each CPU option picks (04-RESEARCH Pattern 6):
SETCC_AND = re.compile(rb"\x0f[\x90-\x9f]\xc0\x25\xff\x00\x00\x00")  # and eax,0FFh: -4r/-5r
SETCC_MOVZX = re.compile(rb"\x0f[\x90-\x9f]\xc0\x0f\xb6\xc0")  # movzx eax,al: -3r

TARGETS = """\
/* -bt=dos predefines __DOS__; the NT-hosted compiler would otherwise predefine __NT__ */
#if defined(__DOS__)
int pr_target_dos = 1;
#endif
#if defined(__NT__)
int pr_target_nt = 1;
#endif
"""

BROKEN = """\
/* a syntax error: the compile must fail and leave nothing behind */
int pr_broken(int x)
{
    return x +;
}
"""


def _module(result: CompileResult) -> omf.Module:
    return omf.read_object(result.obj.read_bytes())


def _code(result: CompileResult) -> bytes:
    return b"".join(seg.data for seg in _module(result).segments if seg.is_code)


@pytest.mark.parametrize("version", VERSIONS)
def test_env_injection_has_no_effect(cc_root, version, monkeypatch):
    # No CPU option in the rule, so an injected WCC386=-3r would decide the zero extension.
    _require_compiler(version, cc_root)
    flags = ("-s",)
    for name in ("WCC386", "INCLUDE"):
        monkeypatch.delenv(name, raising=False)
    clean = _compile(cc_root, version, flags, "eq.c", BYTE_COMPARE)
    explicit = _compile(cc_root, version, ("-3r", "-s"), "eq3.c", BYTE_COMPARE)
    monkeypatch.setenv("WCC386", "-3r")
    monkeypatch.setenv("INCLUDE", "nowhere")
    injected = _compile(cc_root, version, flags, "eq.c", BYTE_COMPARE)
    assert clean.ok and explicit.ok and injected.ok, clean.output + injected.output
    # the injected option would change codegen if it reached the compiler ...
    assert SETCC_MOVZX.search(_code(explicit))
    assert not SETCC_MOVZX.search(_code(clean))
    # ... and it does not reach it
    assert injected.normalized_sha1 == clean.normalized_sha1


@pytest.mark.parametrize("version", VERSIONS)
def test_target_is_dos(cc_root, version):
    _require_compiler(version, cc_root)
    result = _compile(cc_root, version, FLAGS, "target.c", TARGETS)
    assert result.ok, result.output
    names = [public.name for public in _module(result).publics]
    assert any("pr_target_dos" in name for name in names), names
    assert not any("pr_target_nt" in name for name in names), names


def test_cflags_two_sources_real(cc_root):
    # CID-02: the cflags table, not the caller, decides the flags of each source.
    _require_compiler("10.6", cc_root)
    rel_dir = cc_root.relative_to(REPO_ROOT).as_posix()
    cflags = cc_root / "cflags.txt"
    cflags.write_text(
        f"*  wcc386@10.6  -5r -s\n{rel_dir}/b*.c  wcc386@10.6  -3r -s\n", encoding="utf-8"
    )
    results = {}
    for stem in ("a", "b1"):
        src = cc_root / f"{stem}.c"
        src.write_text(BYTE_COMPARE, encoding="ascii")
        results[stem] = compile_source(
            src,
            src.with_suffix(".obj"),
            cflags=cflags,
            root=REPO_ROOT,
            watcom_dir=WATCOM_DIR,
            log=cc_root / "cc.log",
            stamps=cc_root / "stamps",
        )
    a, b1 = results["a"], results["b1"]
    assert a.ok and b1.ok, a.output + b1.output
    assert (a.rule.flags, b1.rule.flags) == (("-5r", "-s"), ("-3r", "-s"))
    code_a, code_b1 = _code(a), _code(b1)
    assert SETCC_AND.search(code_a) and not SETCC_MOVZX.search(code_a)
    assert SETCC_MOVZX.search(code_b1) and not SETCC_AND.search(code_b1)


@pytest.mark.parametrize("version", VERSIONS)
def test_compile_error_cleans_up(cc_root, version):
    _require_compiler(version, cc_root)
    before = set(REPO_ROOT.glob("*.err")) | set(Path.cwd().glob("*.err"))
    result = _compile(cc_root, version, FLAGS, "broken.c", BROKEN)
    assert not result.ok
    assert result.returncode != 0
    assert not result.obj.exists()
    assert (result.object_sha1, result.normalized_sha1) == (None, None)
    errs = list(cc_root.rglob("*.err"))
    # -fr= puts the error file next to the object. Measured: 10.5 writes no error file at all
    # (the message still reaches the captured output), and none anywhere else either.
    assert errs == ([] if version == "10.5" else [result.obj.with_suffix(".err")])
    assert "Error!" in result.output
    after = set(REPO_ROOT.glob("*.err")) | set(Path.cwd().glob("*.err"))
    assert after == before


PARALLEL_CC = 16
CC_MAIN = "import sys; from reverseapoc.cli import main; sys.exit(main(sys.argv[1:]))"
# The log lock has no deadline, so each wait on a `cc` is bounded here: a lock that never comes
# free fails the test instead of hanging the gate. One compile takes seconds.
CC_WAIT_SECONDS = 300


def _start_cc(obj: str, options: list[str]) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", CC_MAIN, "cc", "probe/cg_basic.c", "-o", obj, *options],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def _reap(procs: list[subprocess.Popen]) -> None:
    """Kill and reap every `cc` still running, so a failed test leaves none writing into
    build/test-cc/ (on Windows their open files would make the next run's rmtree fail)."""
    for proc in procs:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()


def test_parallel_cc_keeps_one_log_line_per_compile(cc_root):
    # G-04-2: parallel `reverseapoc cc` runs sharing one --log leave one intact line each.
    _require_compiler("10.6", cc_root)
    rel = cc_root.relative_to(REPO_ROOT).as_posix()
    cflags = cc_root / "cflags.txt"
    cflags.write_text("*  wcc386@10.6  -4r -s -fpi\n", encoding="utf-8")
    log = cc_root / "cc.log"
    objs = [f"{rel}/o{i}.obj" for i in range(PARALLEL_CC)]
    options = [
        "--cflags",
        str(cflags),
        "--watcom-dir",
        str(WATCOM_DIR),
        "--log",
        str(log),
        "--json",
    ]
    procs: list[subprocess.Popen] = []
    try:
        procs.extend(_start_cc(obj, options) for obj in objs)
        errs = [proc.communicate(timeout=CC_WAIT_SECONDS)[1] for proc in procs]
    finally:
        _reap(procs)
    for proc, err in zip(procs, errs, strict=True):
        assert proc.returncode == 0, err
    assert all((REPO_ROOT / obj).is_file() for obj in objs)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == PARALLEL_CC, lines
    for line in lines:
        assert line.endswith("  exit 0"), line
        assert line.count("Version 10.6") == 1, line
        assert line.count("-fo=") == 1, line
    logged = {re.search(r"-fo=(\S+)", line).group(1).replace("\\", "/") for line in lines}
    assert logged == set(objs)
