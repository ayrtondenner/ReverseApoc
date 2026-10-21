"""`reverseapoc cc` wrapper: hash gate, banner, argv shape, scrubbed environment (D-11/D-13/D-14).

Every test runs a FakeCompiler in place of subprocess.run against a fake tree, so no compiler is
needed; the real compile is a separate, manual verification step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from reverseapoc import compiler
from reverseapoc.cflags import CflagsError
from reverseapoc.compiler import (
    WIBO,
    CompilerError,
    compile_source,
    gate_paths,
    runner_prefix,
    scrubbed_env,
)
from watcomtree import TREE_FILES, FakeCompiler, make_tree, sha1_of, write_watcom_manifest

DEFAULT_RULES = "*  wcc386@10.6  -5r -s\n"


@dataclass
class Workspace:
    root: Path
    watcom: Path
    manifest: Path
    cflags: Path
    log: Path
    stamps: Path

    def source(self, rel: str = "src/a.c") -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("int x;\n")
        return path

    def compile(self, src: Path, obj: Path, runner: FakeCompiler, **kwargs):
        options = dict(
            cflags=self.cflags,
            root=self.root,
            manifest=self.manifest,
            watcom_dir=self.watcom,
            runner=runner,
            platform="win32",
            log=self.log,
            stamps=self.stamps,
        )
        options.update(kwargs)
        return compile_source(src, obj, **options)


def make_workspace(
    root: Path,
    versions=("10.6",),
    rules: str = DEFAULT_RULES,
    *,
    trees: dict[str, dict[str, bytes]] | None = None,
    known_bad=(),
) -> Workspace:
    """A root with fake trees under w/ and a manifest describing `trees` (default: the trees as
    written), so a test can make the manifest and the tree disagree."""
    watcom = root / "w"
    for version in versions:
        make_tree(watcom, version)
    described = trees if trees is not None else {v: TREE_FILES[v] for v in versions}
    manifest = write_watcom_manifest(root / "watcom.toml", described, known_bad=known_bad)
    cflags = root / "cflags.txt"
    cflags.write_text(rules, encoding="utf-8")
    return Workspace(root, watcom, manifest, cflags, root / "logs" / "cc.log", root / "cache")


@pytest.fixture
def ws(tmp_path) -> Workspace:
    return make_workspace(tmp_path)


# 1. the tracer: one source through the gate ----------------------------------------------------


def test_cc_compiles_through_gate(ws):
    runner = FakeCompiler()
    obj = ws.root / "out" / "a.obj"
    result = ws.compile(ws.source(), obj, runner)
    assert result.ok
    assert result.returncode == 0
    assert obj.is_file()
    assert "Version 10.6" in result.gate.banner
    assert result.rule.spec == "wcc386@10.6"
    assert result.format().startswith("OK")
    files = TREE_FILES["10.6"]
    assert result.gate.files == (
        ("BINNT/WCC386.EXE", sha1_of(files["BINNT/WCC386.EXE"])),
        ("BINW/WCC386.EXE", sha1_of(files["BINW/WCC386.EXE"])),
    )
    log = ws.log.read_text(encoding="utf-8")
    assert "Version 10.6" in log
    assert len(re.findall(r"\b[0-9a-f]{40}\b", log)) == 2


def test_argv_shape(ws, monkeypatch):
    runner = FakeCompiler()
    ws.compile(ws.source(), ws.root / "out" / "a.obj", runner)
    exe = str((ws.watcom / "10.6").resolve() / "BINNT" / "WCC386.EXE")
    expected = [
        exe,
        "-zq",
        "-zld",
        "-bt=dos",
        "-fr=out\\a.err",
        "-5r",
        "-s",
        "-i=w\\10.6\\H",
        "src\\a.c",
        "-fo=out\\a.obj",
    ]
    assert runner.compiles == [expected]

    monkeypatch.setattr(compiler.shutil, "which", lambda path: path)
    linux = FakeCompiler()
    ws.compile(ws.source(), ws.root / "out" / "a.obj", linux, platform="linux")
    assert linux.compiles == [[WIBO, *expected]]
    assert linux.probes == [[WIBO, exe]]


def test_runner_prefix():
    assert runner_prefix("win32") == []
    assert runner_prefix("linux", which=lambda path: path) == [WIBO]
    with pytest.raises(CompilerError, match="wibo not found"):
        runner_prefix("linux", which=lambda path: None)


def test_env_is_scrubbed(ws, monkeypatch):
    parent = {
        "PATH": "/bin",
        "SYSTEMROOT": "C:\\Windows",
        "TEMP": "C:\\t",
        "TMP": "C:\\t",
        "WCC386": "-3r",
        "WPP386": "-3r",
        "WCL386": "-3r",
        "INCLUDE": "C:\\inc",
        "WATCOM": "C:\\watcom",
        "HOME": "/home/x",
    }
    assert scrubbed_env(parent, "win32") == {
        "PATH": "/bin",
        "SYSTEMROOT": "C:\\Windows",
        "TEMP": "C:\\t",
        "TMP": "C:\\t",
    }
    assert scrubbed_env(parent, "linux") == {"PATH": "/bin"}

    for name, value in parent.items():
        monkeypatch.setenv(name, value)
    runner = FakeCompiler()
    ws.compile(ws.source(), ws.root / "out" / "a.obj", runner)
    assert runner.calls
    for _argv, kwargs in runner.calls:
        env = kwargs["env"]
        for name in ("WCC386", "WPP386", "WCL386", "INCLUDE", "WATCOM", "HOME"):
            assert name not in env
        assert env["PATH"] == "/bin"
        assert env["SYSTEMROOT"] == "C:\\Windows"


# 2. the hash gate -------------------------------------------------------------------------------


def _assert_refused(ws: Workspace, path: str) -> None:
    runner = FakeCompiler()
    obj = ws.root / "out" / "a.obj"
    with pytest.raises(CompilerError) as info:
        ws.compile(ws.source(), obj, runner)
    message = str(info.value)
    assert path in message
    assert "install-watcom 10.6" in message
    assert runner.calls == []
    assert not obj.exists()


def test_gate_refuses_known_bad(tmp_path):
    ws = make_workspace(tmp_path, known_bad=[("10.6", "BINW/WCC386.EXE")])
    _assert_refused(ws, "BINW/WCC386.EXE")


def test_gate_refuses_mismatch(tmp_path):
    described = dict(TREE_FILES["10.6"], **{"BINW/WCC386.EXE": b"something else"})
    ws = make_workspace(tmp_path, trees={"10.6": described})
    _assert_refused(ws, "BINW/WCC386.EXE")


def test_gate_refuses_missing(ws):
    (ws.watcom / "10.6" / "BINW" / "WCC386.EXE").unlink()
    _assert_refused(ws, "BINW/WCC386.EXE")


def test_gate_ignores_other_key_files(ws):
    # BINNT/WLINK.EXE is a key file but not a gated one: its absence must not block a compile.
    (ws.watcom / "10.6" / "BINNT" / "WLINK.EXE").unlink()
    assert ws.compile(ws.source(), ws.root / "out" / "a.obj", FakeCompiler()).ok


def test_gate_paths():
    assert gate_paths("wcc386", "10.6") == ("BINNT/WCC386.EXE", "BINW/WCC386.EXE")
    assert gate_paths("wcc386", "11.0") == ("BINNT/WCC386.EXE", "BINNT/WCCD386.DLL")
    with pytest.raises(CompilerError, match="wpp386"):
        gate_paths("wpp386", "10.6")


def test_banner_must_name_version(ws):
    runner = FakeCompiler(banners={"10.6": "Watcom C32 Optimizing Compiler  Version 11.0"})
    with pytest.raises(CompilerError) as info:
        ws.compile(ws.source(), ws.root / "out" / "a.obj", runner)
    assert "Version 10.6" in str(info.value)
    assert "Version 11.0" in str(info.value)
    assert runner.compiles == []


# 3. per-file rules (CID-02) ---------------------------------------------------------------------


def _include(argv: list[str]) -> str:
    (include,) = [arg for arg in argv if arg.startswith("-i=")]
    return include


def test_two_sources_get_their_rules(tmp_path):
    rules = "*  wcc386@10.6  -5r -s\nsrc/b*.c  wcc386@11.0  -3r\n"
    ws = make_workspace(tmp_path, versions=("10.6", "11.0"), rules=rules)
    runner = FakeCompiler()
    a = ws.compile(ws.source("src/a.c"), ws.root / "out" / "a.obj", runner)
    b = ws.compile(ws.source("src/b1.c"), ws.root / "out" / "b1.obj", runner)
    assert (a.ok, b.ok) == (True, True)
    a_argv, b_argv = runner.compiles
    exe = "BINNT/WCC386.EXE"
    assert a_argv[0] == str((ws.watcom / "10.6").resolve() / exe)
    assert "-5r" in a_argv and "-s" in a_argv
    assert _include(a_argv).endswith("10.6\\H")
    assert b_argv[0] == str((ws.watcom / "11.0").resolve() / exe)
    assert "-3r" in b_argv and "-5r" not in b_argv
    assert _include(b_argv).endswith("11.0\\H")
    assert (a.rule.spec, b.rule.spec) == ("wcc386@10.6", "wcc386@11.0")
    assert "Version 11.0" in b.gate.banner
    assert [path for path, _ in b.gate.files] == ["BINNT/WCC386.EXE", "BINNT/WCCD386.DLL"]


def test_invalid_cflags_is_refused_before_anything_runs(ws):
    ws.cflags.write_text("*  wcc386@10.6  -5r -fo=elsewhere.obj\n", encoding="utf-8")
    runner = FakeCompiler()
    with pytest.raises(CflagsError, match=":1:"):
        ws.compile(ws.source(), ws.root / "out" / "a.obj", runner)
    assert runner.calls == []
