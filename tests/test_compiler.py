"""`reverseapoc cc` wrapper: hash gate, banner, argv shape, scrubbed environment (D-11/D-13/D-14).

Every test runs a FakeCompiler in place of subprocess.run against a fake tree, so no compiler is
needed; the real compile is a separate, manual verification step.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from reverseapoc import compiler, omf, watcom
from reverseapoc.cflags import CflagsError, load_cflags
from reverseapoc.compiler import (
    WIBO,
    CompilerError,
    compile_source,
    gate_paths,
    guest_path,
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
    # two gated compiler SHA-1s, then the object's raw and normalized SHA-1
    assert len(re.findall(r"\b[0-9a-f]{40}\b", log)) == 4


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
        "-i=include;w\\10.6\\H",
        "src\\a.c",
        "-fo=out\\a.obj",
    ]
    assert runner.compiles == [expected]

    monkeypatch.setattr(compiler.shutil, "which", lambda path: path)
    linux = FakeCompiler()
    # A stamp of its own, or the win32 run's stamp would spare this run its banner probe.
    stamps = ws.root / "cache-linux"
    ws.compile(ws.source(), ws.root / "out" / "a.obj", linux, platform="linux", stamps=stamps)
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


def test_include_is_own_tree_only(tmp_path):
    ws = make_workspace(tmp_path, versions=("10.6", "11.0"), rules="*  wcc386@11.0  -3r\n")
    runner = FakeCompiler()
    ws.compile(ws.source(), ws.root / "out" / "a.obj", runner)
    (argv,) = runner.compiles
    includes = [arg for arg in argv if arg.startswith("-i=")]
    assert includes == ["-i=include;w\\11.0\\H"]


def test_include_list_puts_the_repo_include_first(ws):
    # One -i= option: the compile root's include/ (project headers such as common.h) first, then
    # the rule's own H directory. Nothing else, so no other Watcom tree's headers can leak in.
    runner = FakeCompiler()
    ws.compile(ws.source(), ws.root / "out" / "a.obj", runner)
    (argv,) = runner.compiles
    includes = [arg for arg in argv if arg.startswith("-i=")]
    project = guest_path(ws.root / "include", ws.root, inside=True)
    tree = guest_path(ws.watcom / "10.6" / "H", ws.root, inside=False)
    assert includes == [f"-i={project};{tree}"]
    assert project == "include"


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_include_list_on_wibo_and_native(ws, monkeypatch, platform):
    # Natively and under wibo the compiler is the same Windows binary, so both entries use
    # Watcom's `\` separators (a `/` would be read as an option switch) and `;` splits the list.
    monkeypatch.setattr(compiler.shutil, "which", lambda path: path)
    runner = FakeCompiler()
    stamps = ws.root / f"cache-{platform}"
    ws.compile(ws.source(), ws.root / "out" / "a.obj", runner, platform=platform, stamps=stamps)
    (argv,) = runner.compiles
    assert (argv[0] == WIBO) == (platform == "linux")
    value = _include(argv).removeprefix("-i=")
    assert "/" not in value
    assert value.split(";") == ["include", "w\\10.6\\H"]


def test_cflags_cannot_add_an_include(ws):
    # -i stays wrapper-owned: a cflags rule cannot widen the include list in any spelling.
    ws.cflags.write_text("*  wcc386@10.6  -5r -i=x\n", encoding="utf-8")
    with pytest.raises(CflagsError, match="wrapper"):
        load_cflags(ws.cflags, versions=("10.6",))
    runner = FakeCompiler()
    with pytest.raises(CflagsError, match=":1:"):
        ws.compile(ws.source(), ws.root / "out" / "a.obj", runner)
    assert runner.calls == []


# 4. paths (D-14) --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rel", "named"),
    [
        ("a b.c", "space"),
        ("-x.c", "'-'"),
        ("src/../a.c", ".."),
        ("src/a$.c", "'$'"),
    ],
)
@pytest.mark.parametrize("which", ["src", "obj"])
def test_guest_path_refusals(ws, rel, named, which):
    runner = FakeCompiler()
    good_src, good_obj = ws.source(), ws.root / "out" / "a.obj"
    bad = ws.root / rel
    if which == "src":
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("int x;\n")
    src, obj = (bad, good_obj) if which == "src" else (good_src, bad)
    with pytest.raises(CompilerError) as info:
        ws.compile(src, obj, runner)
    message = str(info.value)
    assert rel.split("/")[-1] in message
    assert named in message
    assert runner.calls == []


@pytest.mark.parametrize("which", ["src", "obj"])
def test_guest_path_outside_root_refused(tmp_path, which):
    ws = make_workspace(tmp_path / "repo")
    outside = tmp_path / "elsewhere" / "a.c"
    outside.parent.mkdir()
    outside.write_text("int x;\n")
    runner = FakeCompiler()
    src, obj = (outside, ws.root / "a.obj") if which == "src" else (ws.source(), outside)
    with pytest.raises(CompilerError, match="outside"):
        ws.compile(src, obj, runner)
    assert runner.calls == []


def test_guest_path_reports_the_first_bad_character(tmp_path):
    with pytest.raises(CompilerError) as info:
        guest_path(tmp_path / "src" / "a$b%.c", tmp_path, inside=True)
    assert "'$'" in str(info.value)
    assert "'%'" not in str(info.value)


def test_guest_path_rewrites_slashes(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    assert guest_path(root / "src" / "sub" / "a.c", root, inside=True) == "src\\sub\\a.c"
    assert guest_path(tmp_path / "w" / "10.6" / "H", root, inside=False) == "..\\w\\10.6\\H"
    with pytest.raises(CompilerError):
        guest_path(tmp_path / "w w" / "10.6" / "H", root, inside=False)


def test_include_path_from_a_tree_outside_the_root(tmp_path):
    ws = make_workspace(tmp_path / "repo")
    tree_dir = tmp_path / "trees"
    make_tree(tree_dir, "10.6")
    runner = FakeCompiler()
    assert ws.compile(ws.source(), ws.root / "out" / "a.obj", runner, watcom_dir=tree_dir).ok
    (argv,) = runner.compiles
    assert _include(argv) == "-i=include;..\\trees\\10.6\\H"


# 5. the gate stamp ------------------------------------------------------------------------------


def _count_checks(monkeypatch) -> list[str]:
    calls: list[str] = []
    real = watcom.check_version

    def counting(media, install_dir):
        calls.append(media.version)
        return real(media, install_dir)

    monkeypatch.setattr(watcom, "check_version", counting)
    return calls


def _stamp(ws: Workspace) -> Path:
    return ws.stamps / "watcom-wcc386-10.6.json"


def test_stamp_cache_skips_rehash(ws, monkeypatch):
    checks = _count_checks(monkeypatch)
    runner = FakeCompiler()
    src, obj = ws.source(), ws.root / "out" / "a.obj"
    assert ws.compile(src, obj, runner).ok
    assert (len(checks), len(runner.probes)) == (1, 1)
    assert json.loads(_stamp(ws).read_text(encoding="utf-8"))["banner"].endswith("Version 10.6")

    second = ws.compile(src, obj, runner)
    assert second.ok
    assert (len(checks), len(runner.probes)) == (1, 1)
    assert "Version 10.6" in second.gate.banner
    assert len(runner.compiles) == 2

    gated = ws.watcom / "10.6" / "BINW" / "WCC386.EXE"
    st = gated.stat()
    os.utime(gated, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
    assert ws.compile(src, obj, runner).ok
    assert (len(checks), len(runner.probes)) == (2, 2)

    _stamp(ws).write_text("{ not json", encoding="utf-8")
    assert ws.compile(src, obj, runner).ok
    assert (len(checks), len(runner.probes)) == (3, 3)
    assert json.loads(_stamp(ws).read_text(encoding="utf-8"))["files"]


@pytest.mark.parametrize(
    "stamp",
    ['["a list"]', '{"root": 1}', '{"root": "x", "files": [], "banner": "b"}', ""],
)
def test_stamp_with_the_wrong_shape_is_a_miss(ws, monkeypatch, stamp):
    checks = _count_checks(monkeypatch)
    ws.stamps.mkdir(parents=True)
    _stamp(ws).write_text(stamp, encoding="utf-8")
    assert ws.compile(ws.source(), ws.root / "out" / "a.obj", FakeCompiler()).ok
    assert checks == ["10.6"]


def test_stamp_written_atomically(ws, monkeypatch):
    written: list[Path] = []
    real = compiler.write_atomic

    def recording(path, data):
        written.append(Path(path))
        real(path, data)

    monkeypatch.setattr(compiler, "write_atomic", recording)
    obj = ws.root / "out" / "a.obj"
    assert ws.compile(ws.source(), obj, FakeCompiler()).ok
    assert written == [_stamp(ws), _prov(obj)]  # the gate stamp, then the object's provenance
    assert sorted(p.name for p in ws.stamps.iterdir()) == [_stamp(ws).name]


def _disk_full(path, data):
    raise OSError(28, "No space left on device")


@pytest.mark.parametrize("failure", ["write", "parent is a file"])
def test_a_stamp_that_cannot_be_written_never_fails_a_compile(ws, monkeypatch, failure):
    # The stamp is only a cache: losing it costs a re-hash next time, never the compile.
    stamps = ws.stamps
    if failure == "write":
        real = compiler.write_atomic

        def gate_stamp_disk_full(path, data):  # the object's provenance stamp is no cache
            (_disk_full if Path(path).parent == stamps else real)(path, data)

        monkeypatch.setattr(compiler, "write_atomic", gate_stamp_disk_full)
    else:
        (ws.root / "a-file").write_text("not a directory\n")
        stamps = ws.root / "a-file" / "cache"
    runner = FakeCompiler()
    result = ws.compile(ws.source(), ws.root / "out" / "a.obj", runner, stamps=stamps)
    assert result.ok
    assert (len(runner.probes), len(runner.compiles)) == (1, 1)
    assert not _stamp(ws).exists()


def test_stamp_rechecks_manifest(ws):
    src, obj = ws.source(), ws.root / "out" / "a.obj"
    assert ws.compile(src, obj, FakeCompiler()).ok
    # Same size, different SHA-1: only the stamp-versus-manifest comparison can catch it.
    files = dict(TREE_FILES["10.6"])
    files["BINW/WCC386.EXE"] = files["BINW/WCC386.EXE"][:-1] + b"X"
    write_watcom_manifest(ws.manifest, {"10.6": files})
    runner = FakeCompiler()
    with pytest.raises(CompilerError) as info:
        ws.compile(src, obj, runner)
    assert "BINW/WCC386.EXE" in str(info.value)
    assert "mismatch" in str(info.value)
    assert runner.calls == []


def test_stamp_for_another_root_is_a_miss(tmp_path, monkeypatch):
    ws = make_workspace(tmp_path)
    other = tmp_path / "other"
    make_tree(other, "10.6")
    checks = _count_checks(monkeypatch)
    src, obj = ws.source(), ws.root / "out" / "a.obj"
    assert ws.compile(src, obj, FakeCompiler()).ok
    assert ws.compile(src, obj, FakeCompiler(), watcom_dir=other).ok
    assert checks == ["10.6", "10.6"]


# 6. failures, error files and the log -----------------------------------------------------------


def test_result_carries_object_hashes(ws):
    obj = ws.root / "out" / "a.obj"
    result = ws.compile(ws.source(), obj, FakeCompiler())
    data = obj.read_bytes()
    assert result.object_sha1 == hashlib.sha1(data).hexdigest()
    assert result.normalized_sha1 == omf.normalized_object_sha1(data)
    assert result.object_sha1 != result.normalized_sha1  # THEADR and COMENT 0xE9 are dropped
    assert f"sha1 {result.object_sha1}  normalized {result.normalized_sha1}" in result.format()
    (line,) = ws.log.read_text(encoding="utf-8").splitlines()
    assert f"sha1 {result.object_sha1}  normalized {result.normalized_sha1}" in line
    assert line.endswith("exit 0")
    data_json = result.to_json()
    assert data_json["object_sha1"] == result.object_sha1
    assert data_json["normalized_sha1"] == result.normalized_sha1


def test_failed_compile_has_no_object_hashes(ws):
    result = ws.compile(ws.source(), ws.root / "out" / "a.obj", FakeCompiler(rc=2))
    assert (result.object_sha1, result.normalized_sha1) == (None, None)
    assert result.to_json()["object_sha1"] is None
    assert result.to_json()["normalized_sha1"] is None
    assert "normalized" not in ws.log.read_text(encoding="utf-8")


def test_object_that_is_not_omf_is_refused(ws):
    # exit 0 but not an OMF module: no hash can be trusted, so the object does not survive
    obj = ws.root / "out" / "a.obj"
    with pytest.raises(CompilerError) as info:
        ws.compile(ws.source(), obj, FakeCompiler(obj_bytes=b"not an object"))
    assert "a.obj" in str(info.value)
    assert not obj.exists()


def test_failed_compile_cleans_up(ws):
    obj = ws.root / "out" / "a.obj"
    result = ws.compile(ws.source(), obj, FakeCompiler(rc=2))
    assert not result.ok
    assert not obj.exists()
    assert result.format().startswith("FAILED")
    assert "exit 2" in result.format()


def test_stale_object_is_removed_before_the_compile(ws):
    obj = ws.root / "out" / "a.obj"
    obj.parent.mkdir(parents=True)
    obj.write_bytes(b"stale object from an earlier run")
    result = ws.compile(ws.source(), obj, FakeCompiler(write_obj=False))
    assert not result.ok
    assert not obj.exists()


# DI-06 part a: every object carries a record of what built it --------------------------------

PROV_KEYS = {"compiler", "flags", "source_sha256", "cflags_sha256", "watcom_sha256", "version"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _prov(obj: Path) -> Path:
    return obj.with_name(obj.name + ".prov.json")


def test_compile_writes_a_provenance_stamp(ws):
    """A successful compile writes <obj>.prov.json: the rule's compiler and flags, SHA-256 of the
    source (CRLF read as LF), of the cflags table and the Watcom manifest it used, and the stamp
    format version, nothing else. A failed compile removes it and writes none."""
    src = ws.source()
    src.write_bytes(b"int x;\r\nint y;\n")
    obj = ws.root / "out" / "a.obj"
    result = ws.compile(src, obj, FakeCompiler())
    assert result.ok
    assert _prov(obj).is_file()
    doc = json.loads(_prov(obj).read_text(encoding="utf-8"))
    assert set(doc) == PROV_KEYS
    assert (doc["compiler"], doc["flags"]) == ("wcc386@10.6", ["-5r", "-s"])
    assert doc["source_sha256"] == _sha256(b"int x;\nint y;\n")
    assert doc["cflags_sha256"] == _sha256(ws.cflags.read_bytes())
    assert doc["watcom_sha256"] == _sha256(ws.manifest.read_bytes())
    assert doc["version"] == compiler.PROV_VERSION
    assert compiler.provenance_path(obj) == _prov(obj)

    failed = ws.compile(src, obj, FakeCompiler(rc=2))
    assert not failed.ok
    assert not _prov(obj).exists()


def test_a_refused_compile_leaves_no_stamp(ws):
    """An object the compile refuses (not OMF) is deleted, and an old stamp goes with it."""
    src, obj = ws.source(), ws.root / "out" / "a.obj"
    assert ws.compile(src, obj, FakeCompiler()).ok
    assert _prov(obj).is_file()
    with pytest.raises(CompilerError):
        ws.compile(src, obj, FakeCompiler(obj_bytes=b"not an object"))
    assert not obj.exists() and not _prov(obj).exists()


def test_provenance_stamp_is_written_atomically(ws, monkeypatch):
    written = []
    real = compiler.write_atomic

    def record(path, data):
        written.append(Path(path))
        real(path, data)

    monkeypatch.setattr(compiler, "write_atomic", record)
    obj = ws.root / "out" / "a.obj"
    assert ws.compile(ws.source(), obj, FakeCompiler()).ok
    assert _prov(obj) in written


def test_a_provenance_stamp_that_cannot_be_written_fails_the_compile(ws, monkeypatch):
    """Unlike the gate stamp, the provenance stamp is what the land step trusts: without it the
    compile fails and leaves no object."""
    real = compiler.write_atomic
    obj = ws.root / "out" / "a.obj"

    def prov_disk_full(path, data):
        (_disk_full if Path(path) == _prov(obj) else real)(path, data)

    monkeypatch.setattr(compiler, "write_atomic", prov_disk_full)
    with pytest.raises(CompilerError, match="provenance stamp cannot be written"):
        ws.compile(ws.source(), obj, FakeCompiler())
    assert not obj.exists() and not _prov(obj).exists()


KEPT ="int kept;\n"  # what a file the compile must not touch holds


@pytest.mark.parametrize(
    ("src_rel", "obj_rel", "named"),
    [
        ("src/a.c", "src/a.c", ".obj"),  # -o is the source: the stale-object unlink deleted it
        ("src/a.c", "src/b.c", ".obj"),  # -o is another source
        ("src/a.c", "out/a.err", ".obj"),  # -fo= and -fr= would name one file
        ("src/a.c", "out/a", ".obj"),
        ("src/a.obj", "src/a.obj", "source"),  # a source that is itself named .obj
        ("src/a.err", "src/a.obj", "source"),  # the error file would overwrite the source
    ],
)
def test_outputs_that_would_destroy_a_file_are_refused(ws, src_rel, obj_rel, named):
    src, obj = ws.source(src_rel), ws.root / obj_rel
    if not obj.exists():
        obj.parent.mkdir(parents=True, exist_ok=True)
        obj.write_text(KEPT)
    runner = FakeCompiler()
    with pytest.raises(CompilerError) as info:
        ws.compile(src, obj, runner)
    message = str(info.value)
    assert named in message
    assert Path(obj_rel).name in message or Path(src_rel).name in message
    assert runner.calls == []  # refused before the banner probe and the compile
    assert src.read_text() == "int x;\n"
    assert obj.is_file()  # nothing was deleted


def test_err_file_stays_under_object_dir(ws, tmp_path_factory, monkeypatch):
    cwd = tmp_path_factory.mktemp("cwd")
    monkeypatch.chdir(cwd)
    before = sorted(p.name for p in ws.root.iterdir())
    runner = FakeCompiler(rc=2)
    ws.compile(ws.source(), ws.root / "out" / "a.obj", runner)
    (argv,) = runner.compiles
    assert [arg for arg in argv if arg.startswith("-fr=")] == ["-fr=out\\a.err"]
    assert (ws.root / "out" / "a.err").is_file()  # kept for the reader
    after = sorted(p.name for p in ws.root.iterdir())
    assert set(after) - set(before) <= {"src", "out", "logs", "cache"}
    assert not list(ws.root.glob("*.err"))
    assert list(cwd.iterdir()) == []


def test_log_lists_gate_files_in_manifest_order(tmp_path):
    # The manifest lists BINW before BINNT: the log follows the manifest, not gate_paths().
    files = TREE_FILES["10.6"]
    reordered = {path: files[path] for path in ("BINW/WCC386.EXE", "BINNT/WCC386.EXE")}
    ws = make_workspace(tmp_path, trees={"10.6": reordered})
    src, obj = ws.source(), ws.root / "out" / "a.obj"
    ws.compile(src, obj, FakeCompiler())
    ws.compile(src, obj, FakeCompiler())
    lines = ws.log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    gates = [re.findall(r"(\S+)=([0-9a-f]{40})\b", line) for line in lines]
    assert gates[0] == gates[1]
    assert [path for path, _ in gates[0]] == ["BINW/WCC386.EXE", "BINNT/WCC386.EXE"]
    assert all(line.endswith("exit 0") for line in lines)


# A bad --log fails before the compile, so a good compile never ends as a failed edge with a
# stray object (04-REVIEW IN-08, IN-09).

KEEP = b"object from an earlier run"


def _kept_object(ws: Workspace) -> Path:
    obj = ws.root / "out" / "a.obj"
    obj.parent.mkdir(parents=True, exist_ok=True)
    obj.write_bytes(KEEP)
    return obj


def test_log_naming_a_directory_is_refused_before_the_compile(ws):
    logdir = ws.root / "logdir"
    logdir.mkdir()
    obj = ws.root / "out" / "a.obj"
    runner = FakeCompiler()
    with pytest.raises(CompilerError) as info:
        ws.compile(ws.source(), obj, runner, log=logdir)
    message = str(info.value)
    assert str(logdir) in message
    assert "is a directory" in message
    assert runner.calls == []
    assert not obj.exists()
    assert list(logdir.iterdir()) == []


@pytest.mark.parametrize("parts", [("new", ".."), ("..",)])
def test_log_ending_in_dotdot_names_no_file(ws, parts):
    """`--log new/..` names a directory, not a file, even while `new` does not exist (POSIX then
    passes is_dir(), the probe would create `new`, and the append would fail after the
    compile). Refused by name, before anything is created, on both platforms."""
    log = ws.root.joinpath(*parts)
    runner = FakeCompiler()
    with pytest.raises(CompilerError) as info:
        ws.compile(ws.source(), ws.root / "out" / "a.obj", runner, log=log)
    assert "names no file" in str(info.value)
    assert runner.calls == []
    assert not (ws.root / "new").exists()


def test_unwritable_lock_is_refused_before_the_compile(ws, monkeypatch):
    real_open = open
    lock = compiler._lock_path(ws.log)

    def deny_lock(file, mode="r", *args, **kwargs):
        if Path(file) == lock and mode == "a+b":
            raise PermissionError(13, "Permission denied", str(file))
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(compiler, "open", deny_lock, raising=False)
    obj = _kept_object(ws)
    runner = FakeCompiler()
    with pytest.raises(CompilerError) as info:
        ws.compile(ws.source(), obj, runner)
    message = str(info.value)
    assert str(lock) in message
    assert "Permission denied" in message
    assert runner.calls == []  # refused before the banner probe and the compile
    assert obj.read_bytes() == KEEP  # nothing was deleted


def _no_sidecar(log: Path):
    raise AssertionError(f"touched the lock sidecar of {log}")


def test_device_log_still_works(ws, monkeypatch):
    """A device log keeps the device branch: no sidecar is probed or locked, on either platform
    (`/dev/null` on POSIX, `NUL` on Windows)."""
    device = Path("NUL") if sys.platform == "win32" else Path("/dev/null")
    monkeypatch.setattr(compiler, "_lock_path", _no_sidecar)
    result = ws.compile(ws.source(), ws.root / "out" / "a.obj", FakeCompiler(), log=device)
    assert result.ok


def test_missing_tree_refused(ws):
    runner = FakeCompiler()
    with pytest.raises(CompilerError) as info:
        ws.compile(ws.source(), ws.root / "out" / "a.obj", runner, watcom_dir=ws.root / "none")
    message = str(info.value)
    assert str((ws.root / "none" / "10.6").resolve()) in message
    assert "install-watcom 10.6" in message
    assert runner.calls == []


def test_zero_length_compiler_is_a_mismatch(ws):
    (ws.watcom / "10.6" / "BINNT" / "WCC386.EXE").write_bytes(b"")
    runner = FakeCompiler()
    with pytest.raises(CompilerError) as info:
        ws.compile(ws.source(), ws.root / "out" / "a.obj", runner)
    message = str(info.value)
    assert "BINNT/WCC386.EXE" in message
    assert "mismatch" in message
    assert "install-watcom 10.6" in message
    assert runner.calls == []


def test_invalid_cflags_is_refused_before_anything_runs(ws):
    ws.cflags.write_text("*  wcc386@10.6  -5r -fo=elsewhere.obj\n", encoding="utf-8")
    runner = FakeCompiler()
    with pytest.raises(CflagsError, match=":1:"):
        ws.compile(ws.source(), ws.root / "out" / "a.obj", runner)
    assert runner.calls == []
