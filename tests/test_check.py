"""check: compile, convert, cut, objdiff per function, relocation check, land and the SHA-1 of every
EXE (SPL-11, D-16). Only the compiler and objdiff-cli are faked; omf2elf, target, relocs and land
run for real on synthetic inputs. Every byte, name and address is made up (tests/relocpair.py)."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import write_manifest
from omfimage import (
    extdef,
    fixupp32,
    grpdef,
    ledata32,
    lnames,
    lpubdef32,
    module,
    pubdef32,
    segdef32,
)
from relocpair import (
    CODE_BASE,
    FLAT_LNAME,
    GOOD_ORIGINAL,
    GOOD_OURS,
    LOAD_FIELD,
    TEXT_INDEX,
    absolute,
    call,
    le_off32,
    original,
    our_module,
    to_segment,
)
from relocpair import table as symbol_table
from reverseapoc import check
from reverseapoc.asm import data_ranges
from reverseapoc.cflags import Rule
from reverseapoc.cli import main as cli_main
from reverseapoc.compiler import provenance_path, source_rule
from reverseapoc.functions import (
    FunctionRow,
    SymbolRow,
    UnitRow,
    game_name,
    write_functions_csv,
    write_symbols_csv,
    write_units_csv,
)
from reverseapoc.le import LE
from reverseapoc.symbols import SymbolTable
from reverseapoc.target import RawField, TargetResult, build_target
from reverseapoc.watcom import DEFAULT_WATCOM_MANIFEST

EXE = "SYN.EXE"
STEM = "syn"
UNIT = "u_00010000"
FAR_UNIT = "u_00010020"
ROW = FunctionRow(CODE_BASE, CODE_BASE + len(GOOD_ORIGINAL), "func_00010000", "game", UNIT, "call")
OTHER = FunctionRow(0x10010, 0x10018, "func_00010010", "game", UNIT, "call")
FAR = FunctionRow(0x10020, 0x10028, "func_00010020", "game", FAR_UNIT, "call")
UNITS = [UnitRow(UNIT, 0x10000, 0x10018, "first"), UnitRow(FAR_UNIT, 0x10020, 0x10028, "hand")]
SOURCE = "/* synthetic */\nint func_00010000(void) { return 0; }\nINCLUDE_ASM(func_00010010);\n"
RULE = Rule("*", "wcc386", "10.6", ("-4r", "-s", "-fpi"), 1)
SYMBOL = "func_00010000_"


def omf_object(
    code: bytes = GOOD_OURS,
    callee: str = "func_00010010_",
    *,
    public: str = SYMBOL,
    extra: tuple[tuple[str, int], ...] = (),
) -> bytes:
    """Our compiled unit: `_TEXT` holding `code` with `public` (func_00010000_) at 0, a
    self-relative call to `callee` at 1, an absolute load of _D_00020004 at 6, and `extra`
    publics (name, offset) besides."""
    return module(
        "u_00010000",
        lnames("", "_TEXT", "CODE", FLAT_LNAME),
        segdef32(2, 3, len(code)),
        grpdef(4),  # FLAT, the frame of the relocpair fixups
        pubdef32(1, [(public, 0), *extra]),
        extdef(callee, "_D_00020004"),
        ledata32(1, 0, code),
        fixupp32(call(1, 1), absolute(6, 2)),
    )


class FakeCompiler:
    """Stands in for compile_source: writes `data` to the object path and records each call."""

    def __init__(self, data: bytes | None = None, *, ok: bool = True) -> None:
        self.data = omf_object() if data is None else data
        self.ok = ok
        self.calls: list[tuple[Path, Path, dict]] = []

    def __call__(self, src, obj, **kwargs):
        self.calls.append((Path(src), Path(obj), kwargs))
        obj = Path(obj)
        if self.ok:
            obj.parent.mkdir(parents=True, exist_ok=True)
            obj.write_bytes(self.data)
        return SimpleNamespace(
            ok=self.ok, rule=RULE, output="", returncode=0 if self.ok else 1,
            format=lambda: f"{'OK' if self.ok else 'FAILED'}  {src}",
        )  # fmt: skip


def objdiff_json(percent: float | None = 100.0, symbol: str = SYMBOL) -> str:
    entry = {"name": symbol, "size": "11"}
    if percent is not None:
        entry["match_percent"] = percent
    return json.dumps({"left": {"symbols": [entry]}, "right": {"symbols": []}})


class FakeObjdiff:
    def __init__(self, percent: float | None = 100.0) -> None:
        self.percent = percent
        self.argvs: list[list[str]] = []

    def __call__(self, argv):
        self.argvs.append(list(argv))
        return objdiff_json(self.percent, argv[-1])


@dataclass
class Env:
    root: Path
    data: bytes

    @property
    def orig(self) -> Path:
        return self.root / "orig"

    @property
    def manifest(self) -> Path:
        return self.root / "targets.toml"

    @property
    def config(self) -> Path:
        return self.root / "config"

    @property
    def src(self) -> Path:
        return self.root / "src"

    @property
    def build(self) -> Path:
        return self.root / "build"

    def kwargs(self) -> dict:
        return {"orig_dir": self.orig, "manifest": self.manifest, "config_root": self.config,
                "src_root": self.src, "build_dir": self.build}  # fmt: skip

    def argv(self) -> list[str]:
        paths = {"--orig": self.orig, "--manifest": self.manifest, "--config": self.config,
                 "--src": self.src, "--build": self.build}  # fmt: skip
        return [part for option, path in paths.items() for part in (option, str(path))]


def make_env(
    tmp_path: Path, *, exes: tuple[str, ...] = (EXE,), with_units: tuple[str, ...] = (EXE,)
) -> Env:
    """A synthetic EXE per name (all the same image), a manifest, and config/src for the names in
    `with_units`."""
    data = original({CODE_BASE: GOOD_ORIGINAL}, page1=le_off32(LOAD_FIELD, 0x4)).data
    env = Env(tmp_path, data)
    env.orig.mkdir()
    for name in exes:
        (env.orig / name).write_bytes(data)
    write_manifest(env.manifest, {name: data for name in exes})
    for name in with_units:
        stem = Path(name).stem.lower()
        (env.config / stem).mkdir(parents=True)
        write_functions_csv(env.config / stem / "functions.csv", [ROW, OTHER, FAR], name)
        write_units_csv(env.config / stem / "units.csv", UNITS, name)
        (env.src / stem).mkdir(parents=True)
        (env.src / stem / f"{UNIT}.c").write_text(SOURCE, encoding="utf-8")
    return env


@pytest.fixture
def env(tmp_path, monkeypatch):
    """The synthetic tree, standing in for the committed src/ and config/ (DI-06 part b): check
    compiles into ninja's build/<exe>/obj only for the default roots. The patch raises if the
    constants are renamed, so a dead attribute cannot hide the change."""
    env = make_env(tmp_path)
    monkeypatch.setattr(check, "DEFAULT_SRC", env.src)
    monkeypatch.setattr(check, "DEFAULT_CONFIG", env.config)
    # The env root stands in for the repository too (07-03 fix round 1): every tree that is not a
    # D-24 view compiles from REPO_ROOT. configure.py is loaded first, from the real checkout.
    check._configure()
    monkeypatch.setattr(check, "REPO_ROOT", env.root)
    return env


def run_check(env: Env, compiler=None, objdiff=None, **kwargs):
    return check.check_unit(
        STEM, UNIT, **env.kwargs(), compile_fn=compiler or FakeCompiler(),
        objdiff_runner=objdiff or FakeObjdiff(), **kwargs,
    )  # fmt: skip


def patch_tools(monkeypatch, compiler=None, objdiff=None):
    monkeypatch.setattr(check, "compile_source", compiler or FakeCompiler())
    runner = objdiff or FakeObjdiff()
    monkeypatch.setattr(check, "default_objdiff_runner", lambda *args: runner)
    return runner


# ---- Task 1: the tracer -------------------------------------------------------------------------


def test_check_passes_a_matching_unit(env, monkeypatch, capsys):
    objdiff = FakeObjdiff()
    result = run_check(env, objdiff=objdiff)

    assert result.ok, result.format()
    assert result.exit_code == check.EXIT_OK
    (fn,) = result.functions
    assert (fn.name, fn.va, fn.size, fn.objdiff_percent) == ("func_00010000", CODE_BASE, 11, 100.0)
    assert fn.reloc.ok and fn.bytes_ok and fn.differing == 0 and fn.first_va is None
    target = env.build / STEM / "target" / f"{UNIT}.o"
    base = env.build / STEM / "base" / f"{UNIT}.o"
    assert objdiff.argvs == [["objdiff-cli", "diff", "-1", str(target), "-2", str(base),
                              "-o", "-", SYMBOL]]  # fmt: skip
    assert target.is_file() and base.is_file()
    assert (env.build / STEM / "obj" / f"{UNIT}.obj").is_file()

    patch_tools(monkeypatch)
    assert cli_main(["check", f"{STEM}/{UNIT}", *env.argv(), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert set(doc) >= {"exe", "unit", "compiler", "flags", "functions", "splice", "ok"}
    assert (doc["exe"], doc["unit"], doc["compiler"]) == (STEM, UNIT, "wcc386@10.6")
    assert doc["flags"] == ["-4r", "-s", "-fpi"]
    (fn_doc,) = doc["functions"]
    assert set(fn_doc) >= {"name", "va", "size", "objdiff_percent", "reloc", "bytes"}
    assert fn_doc["objdiff_percent"] == 100.0
    assert fn_doc["reloc"] == {"ok": True, "problems": []}
    assert fn_doc["bytes"] == {"ok": True, "differing": 0, "first_va": None}
    (splice,) = doc["splice"]
    assert set(splice) >= {"exe", "sha1", "expected", "ok", "landed"}
    assert splice["exe"] == EXE and splice["ok"] is True and splice["landed"] == 1
    assert splice["sha1"] == splice["expected"]
    assert doc["ok"] is True


# ---- Task 2: exit codes, objdiff edge cases, the target and land verbs ---------------------------


def test_reloc_failure_beats_objdiff(env, monkeypatch, capsys):
    """objdiff says 100.0, but the call lands on func_00010020: the relocation check decides."""
    wrong = FakeCompiler(omf_object(callee="func_00010020_"))
    result = run_check(env, compiler=wrong, objdiff=FakeObjdiff(100.0))

    (fn,) = result.functions
    assert fn.objdiff_percent == 100.0
    assert not fn.reloc.ok and fn.reloc.problems
    assert fn.bytes_ok  # only the call target is wrong: the function verdict must still fail
    assert not fn.ok and fn.format()[0].startswith("MISMATCH")
    assert not result.ok and result.exit_code == check.EXIT_MISMATCH
    (splice,) = result.splices
    assert not splice.ok and [r.name for r in splice.refused] == ["func_00010000"]

    patch_tools(monkeypatch, compiler=wrong)
    assert cli_main(["check", f"{STEM}/{UNIT}", *env.argv(), "--json"]) == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc["functions"][0]["reloc"]["ok"] is False
    assert doc["ok"] is False


def test_absent_percent_is_zero(env):
    result = run_check(env, objdiff=FakeObjdiff(None))
    (fn,) = result.functions
    assert fn.objdiff_percent == 0.0
    assert fn.reloc.ok
    assert result.exit_code == check.EXIT_MISMATCH


@pytest.mark.parametrize("value", [True, "100.0", 150.0, float("nan"), -1.0])
def test_absent_percent_or_nonsense_is_zero_not_a_match(value):
    doc = {"left": {"symbols": [{"name": SYMBOL, "match_percent": value}]}}
    assert check.match_percent(doc, SYMBOL) == 0.0
    assert check.match_percent({"left": {"symbols": []}}, SYMBOL) == 0.0
    assert check.match_percent([], SYMBOL) == 0.0


def test_objdiff_missing(env, monkeypatch, capsys):
    compiler = FakeCompiler()
    monkeypatch.setattr(check, "compile_source", compiler)
    monkeypatch.setattr(check.shutil, "which", lambda name: None)

    assert cli_main(["check", f"{STEM}/{UNIT}", *env.argv()]) == check.EXIT_TOOL
    err = capsys.readouterr().err
    assert f"docker compose run --rm build uv run reverseapoc check {STEM}/{UNIT}" in err
    assert compiler.calls == []  # it fails before compiling anything


@pytest.mark.parametrize(
    ("target", "message"),
    [(f"{STEM}/u_99999999", "no unit 'u_99999999'"), ("nope/u_00010000", "no target named"),
     (f"{STEM}/Bad-Unit", "must match"), (STEM, "expected EXE/UNIT")],
)  # fmt: skip
def test_unknown_unit(env, monkeypatch, capsys, target, message):
    patch_tools(monkeypatch)
    assert cli_main(["check", target, *env.argv()]) == check.EXIT_TOOL
    assert message in capsys.readouterr().err


def test_compile_failure(env, monkeypatch, capsys):
    patch_tools(monkeypatch, compiler=FakeCompiler(ok=False))
    assert cli_main(["check", f"{STEM}/{UNIT}", *env.argv()]) == check.EXIT_TOOL
    assert "compile failed" in capsys.readouterr().err


def test_missing_source_is_a_tool_error(env, monkeypatch, capsys):
    (env.src / STEM / f"{UNIT}.c").unlink()
    patch_tools(monkeypatch)
    assert cli_main(["check", f"{STEM}/{UNIT}", *env.argv()]) == check.EXIT_TOOL
    assert "--write-src" in capsys.readouterr().err


def expected_target(env: Env) -> bytes:
    le = LE(env.data)
    table = SymbolTable.build([ROW, OTHER, FAR], data_ranges=data_ranges(le))
    return build_target(le, [ROW, OTHER], table).data


@pytest.mark.parametrize("exe", [EXE, STEM])
def test_target_verb(env, capsys, exe):
    out = env.build / STEM / "target" / f"{UNIT}.o"
    argv = ["target", exe, UNIT, "--orig", str(env.orig), "--manifest", str(env.manifest),
            "--config", str(env.config), "-o", str(out)]  # fmt: skip
    assert cli_main(argv) == 0
    assert out.read_bytes() == expected_target(env)
    assert out.name in capsys.readouterr().out


def test_target_verb_unknown_unit(env, capsys):
    out = env.build / "x.o"
    argv = ["target", STEM, "u_99999999", "--orig", str(env.orig), "--manifest",
            str(env.manifest), "--config", str(env.config), "-o", str(out)]  # fmt: skip
    assert cli_main(argv) == 1
    assert "no unit 'u_99999999'" in capsys.readouterr().err


def land_argv(env: Env, *extra: str) -> list[str]:
    return ["land", *env.argv(), *extra]


def test_land_verb_without_units(tmp_path, capsys):
    """Orchestrator ruling F4: an EXE without units.csv is not landed and not listed."""
    env = make_env(tmp_path, with_units=())
    assert cli_main(land_argv(env, "--json")) == 0
    assert json.loads(capsys.readouterr().out) == []
    assert not (env.build / "land").exists()


def unit_source(env: Env) -> Path:
    return env.src / STEM / f"{UNIT}.c"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text_sha256(data: bytes) -> str:
    return _sha256(data.replace(b"\r\n", b"\n"))


def headers_sha256(include: Path) -> str:
    """include_sha256, computed here from its definition: per top-level include/*.h (the
    headers build.ninja's cc edge declares), sorted by name, `<name>\\0<SHA-256 of the content,
    CRLF as LF>\\n`, hashed."""
    files = sorted((p.name, p) for p in include.glob("*.h") if p.is_file())
    lines = "".join(f"{rel}\0{_text_sha256(path.read_bytes())}\n" for rel, path in files)
    return _sha256(lines.encode("utf-8"))


def put_stamp(env: Env, *, cflags: Path | None = None, manifest: Path | None = None) -> Path:
    """The provenance stamp `reverseapoc cc` writes for the unit's object (format 2), computed
    here from today's files: the unit file, `cflags` (default config/cflags.txt), `manifest`
    (default config/watcom.toml), the env's include/ and the object on disk. The env tree's
    root is the compile root, as REPO_ROOT is for src/."""
    obj, src = ninja_object(env), unit_source(env)
    rule = source_rule(src, cflags=cflags, root=env.root, manifest=manifest)
    doc = {
        "compiler": rule.spec,
        "flags": list(rule.flags),
        "source_sha256": _text_sha256(src.read_bytes()),
        "cflags_sha256": _sha256(Path(cflags or check.DEFAULT_CFLAGS).read_bytes()),
        "watcom_sha256": _sha256(Path(manifest or DEFAULT_WATCOM_MANIFEST).read_bytes()),
        "include_sha256": headers_sha256(env.root / "include"),
        "object_sha256": _sha256(obj.read_bytes()),
        "version": 2,
    }
    stamp = provenance_path(obj)
    stamp.write_text(json.dumps(doc), encoding="utf-8")
    return stamp


def put_object(env: Env, data: bytes, *, stamp: bool = True) -> None:
    """The object ninja's cc edge built, with its fresh provenance stamp unless `stamp` is
    False."""
    obj = env.build / STEM / "obj" / f"{UNIT}.obj"
    obj.parent.mkdir(parents=True, exist_ok=True)
    obj.write_bytes(data)
    if stamp:
        put_stamp(env)


def test_land_verb_with_a_matched_unit(env, capsys):
    put_object(env, omf_object())
    assert cli_main(land_argv(env)) == 0
    out = capsys.readouterr().out
    assert re.search(rf"^OK {EXE} sha1 [0-9a-f]{{40}} landed 1$", out, re.M), out
    assert (env.build / "land" / EXE).read_bytes() == env.data


def test_land_verb_refuses_a_failing_function(env, capsys):
    put_object(env, omf_object(callee="func_00010020_"))
    assert cli_main(land_argv(env, "--out", str(env.root / "landed"))) == 1
    out = capsys.readouterr().out
    assert f"MISMATCH {EXE}" in out and "REFUSED func_00010000" in out
    assert (env.root / "landed" / EXE).is_file()


def test_land_verb_missing_object_says_run_ninja(env, capsys):
    assert cli_main(land_argv(env)) == 1
    assert "run ninja first" in capsys.readouterr().err


def test_land_all_lists_only_exes_with_units(tmp_path, monkeypatch, capsys):
    """Orchestrator ruling F4: three manifest targets, units.csv for two: exactly two splices."""
    names = ("ONE.EXE", "TWO.EXE", "SMK.EXE")
    env = make_env(tmp_path, exes=names, with_units=names[:2])
    patch_tools(monkeypatch)
    assert cli_main(["check", f"one/{UNIT}", *env.argv(), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert [s["exe"] for s in doc["splice"]] == ["ONE.EXE", "TWO.EXE"]
    assert all(s["ok"] and s["landed"] == 1 for s in doc["splice"])


# ---- Task 3: the logged D-17 sweep -------------------------------------------------------------


def test_sweep_matrix():
    assert check.SWEEP_VERSIONS == ("10.6", "10.5", "11.0")
    assert check.SWEEP_CPU == ("-4r", "-5r")
    assert check.SWEEP_OPT == ((), ("-ox",), ("-os",), ("-ot",), ("-oneatx",))
    cells = check.sweep_cells(chk=False)
    assert len(cells) == 30 and len(set(cells)) == 30
    assert all("-s" in flags and "-fpi" in flags for _, flags in cells)
    assert cells[0] == ("10.6", ("-4r", "-s", "-fpi"))
    chk = check.sweep_cells(chk=True)
    assert len(chk) == 60 and len(set(chk)) == 60
    assert sum("-s" in flags for _, flags in chk) == 30
    assert all("-fpi" in flags for _, flags in chk)
    assert {version for version, _ in chk} == set(check.SWEEP_VERSIONS)


class FlagCompiler(FakeCompiler):
    """Writes the matching object only when the cell's temporary cflags rule holds `-ox`."""

    def __call__(self, src, obj, **kwargs):
        good = "-ox" in Path(kwargs["cflags"]).read_text(encoding="utf-8").split()
        self.data = omf_object() if good else omf_object(callee="func_00010020_")
        return super().__call__(src, obj, **kwargs)


def watcom_tree(env: Env, versions=None) -> Path:
    root = env.root / "watcom"
    for version in check.SWEEP_VERSIONS if versions is None else versions:
        (root / version).mkdir(parents=True)
    return root


def run_sweep(env: Env, compiler, *, versions=None):
    return check.sweep(
        STEM, UNIT, "func_00010000", **env.kwargs(), watcom_dir=watcom_tree(env, versions),
        compile_fn=compiler, objdiff_runner=FakeObjdiff(100.0),
    )  # fmt: skip


def cell_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("cell ")]


def test_sweep_logs_one_line_per_cell(env, monkeypatch):
    def no_land(*args, **kwargs):
        raise AssertionError("the sweep landed something")

    monkeypatch.setattr(check, "land", no_land)
    monkeypatch.setattr(check, "land_all", no_land)
    report = run_sweep(env, FlagCompiler())

    log = env.build / "logs" / f"sweep-{STEM}-{UNIT}-func_00010000.log"
    assert report.log_path == log
    text = log.read_text(encoding="utf-8")
    lines = cell_lines(text)
    assert len(lines) == 30
    assert lines[0].split()[:3] == ["cell", "01", "wcc386@10.6"]
    assert "-4r -s -fpi" in lines[0] and "reloc FAILED" in lines[0]
    ox = [line for line in lines if " -ox " in line]
    assert len(ox) == 6 and all("objdiff 100%" in line and "reloc ok" in line and
                                "differing 0" in line for line in ox)  # fmt: skip
    (best,) = [line for line in text.splitlines() if line.startswith("best:")]
    assert [n for n in re.findall(r"cell (\d+)", best)] == [line.split()[1] for line in ox]
    assert [cell.number for cell in report.best] == [int(line.split()[1]) for line in ox]
    assert report.lines == text.splitlines()


def test_sweep_log_carries_no_bytes(env):
    run_sweep(env, FlagCompiler())
    text = (env.build / "logs" / f"sweep-{STEM}-{UNIT}-func_00010000.log").read_text("utf-8")
    for line in cell_lines(text):
        words = line.split()
        assert words[0] == "cell" and words[2].startswith("wcc386@")
        assert not re.search(r"\b[0-9a-f]{8,}\b", line)  # no hex dumps, no SHA-1s


def test_sweep_leaves_cflags_alone(env):
    cflags = env.config / "cflags.txt"
    original_text = Path(check.DEFAULT_CFLAGS).read_bytes()
    cflags.write_bytes(original_text)
    compiler = FlagCompiler()
    run_sweep(env, compiler)

    assert cflags.read_bytes() == original_text
    assert Path(check.DEFAULT_CFLAGS).read_bytes() == original_text
    sweep_dir = env.build / "sweep" / STEM / UNIT
    assert len(compiler.calls) == 30
    for _, obj, kwargs in compiler.calls:
        assert Path(kwargs["cflags"]).is_relative_to(sweep_dir)
        assert obj.is_relative_to(sweep_dir)
    rule = Path(compiler.calls[1][2]["cflags"]).read_text(encoding="utf-8")
    assert rule.split() == ["*", "wcc386@10.6", "-4r", "-ox", "-s", "-fpi"]


def test_sweep_not_installed(env):
    compiler = FlagCompiler()
    report = run_sweep(env, compiler, versions=("10.6",))
    lines = cell_lines("\n".join(report.lines))
    assert len(lines) == 30
    missing = [line for line in lines if line.endswith("not installed")]
    assert len(missing) == 20
    assert all("wcc386@10.6" not in line for line in missing)
    assert len(compiler.calls) == 10


def test_sweep_doubles_the_matrix_for_a_chk_caller(tmp_path):
    """The function calls the runtime public __CHK: the sweep toggles -s (60 cells)."""
    env = make_env(tmp_path)
    chk = FunctionRow(OTHER.start, OTHER.end, "__CHK", "runtime", UNIT, "runtime")
    write_functions_csv(env.config / STEM / "functions.csv", [ROW, chk, FAR], EXE)
    report = run_sweep(env, FakeCompiler(omf_object(callee="__CHK")))
    assert report.chk
    assert len(cell_lines("\n".join(report.lines))) == 60


def test_sweep_cli(env, monkeypatch, capsys):
    patch_tools(monkeypatch, compiler=FlagCompiler())
    watcom = watcom_tree(env)
    argv = ["check", f"{STEM}/{UNIT}", *env.argv(), "--watcom-dir", str(watcom),
            "--sweep", "func_00010000"]  # fmt: skip
    assert cli_main(argv) == 0
    out = capsys.readouterr().out
    assert len(cell_lines(out)) == 30 and "best:" in out
    assert not (env.build / "land").exists()


def test_sweep_unknown_function(env, monkeypatch, capsys):
    patch_tools(monkeypatch)
    argv = ["check", f"{STEM}/{UNIT}", *env.argv(), "--sweep", "func_00010020"]
    assert cli_main(argv) == check.EXIT_TOOL
    assert "func_00010020" in capsys.readouterr().err


# ---- review round 1: every game/thunk row of the unit is exported or marked, never skipped ----


def check_json(env: Env, monkeypatch, capsys, compiler) -> tuple[int, dict]:
    patch_tools(monkeypatch, compiler=compiler)
    code = cli_main(["check", f"{STEM}/{UNIT}", *env.argv(), "--json"])
    return code, json.loads(capsys.readouterr().out)


def problems_by_name(doc: dict) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for problem in doc["problems"]:
        found.setdefault(problem["name"], []).append(problem["reason"])
    return found


def test_defined_but_misnamed_is_a_mismatch(env, monkeypatch, capsys):
    """The C defines func_00010000, but the object exports it under another name (cdecl): the
    row was never checked, so the unit must not pass on the original bytes."""
    misnamed = FakeCompiler(omf_object(public="func_00010000"))
    code, doc = check_json(env, monkeypatch, capsys, misnamed)
    assert code == check.EXIT_MISMATCH
    assert doc["ok"] is False
    row = "defined in C but not exported as func_00010000_"
    stray = "public func_00010000 is not a function of the unit"
    assert {"name": "func_00010000", "va": "0x00010000", "reason": row} in doc["problems"]
    # the stray public itself is named too, without an address (it is no row)
    assert {"name": "func_00010000", "va": None, "reason": stray} in doc["problems"]
    assert doc["functions"] == []


def test_neither_exported_nor_marked_is_a_mismatch(env, monkeypatch, capsys):
    (env.src / STEM / f"{UNIT}.c").write_text(
        "int func_00010000(void) { return 0; }\n", encoding="utf-8"
    )
    code, doc = check_json(env, monkeypatch, capsys, FakeCompiler())
    assert code == check.EXIT_MISMATCH
    assert problems_by_name(doc)["func_00010010"] == [
        "neither exported nor marked INCLUDE_ASM (expected public func_00010010_)"
    ]
    assert doc["functions"][0]["objdiff_percent"] == 100.0  # the exported one is still checked


def test_marked_stub_is_reported_not_landed(env, monkeypatch, capsys):
    code, doc = check_json(env, monkeypatch, capsys, FakeCompiler())
    assert code == check.EXIT_OK and doc["ok"] is True
    assert doc["stubs"] == [{"name": "func_00010010", "va": "0x00010010",
                             "status": "stub, not checked"}]  # fmt: skip
    assert doc["problems"] == []
    assert [s["landed"] for s in doc["splice"]] == [1]  # only func_00010000 landed


def test_exported_and_marked_is_a_mismatch(env, monkeypatch, capsys):
    (env.src / STEM / f"{UNIT}.c").write_text(SOURCE + "INCLUDE_ASM(func_00010000);\n",
                                              encoding="utf-8")  # fmt: skip
    code, doc = check_json(env, monkeypatch, capsys, FakeCompiler())
    assert code == check.EXIT_MISMATCH
    assert "func_00010000" in problems_by_name(doc)


def test_extra_public_not_in_the_unit_is_a_mismatch(env, monkeypatch, capsys):
    helper = omf_object(GOOD_OURS + b"\xc3", extra=(("helper_", len(GOOD_OURS)),))
    code, doc = check_json(env, monkeypatch, capsys, FakeCompiler(helper))
    assert code == check.EXIT_MISMATCH
    assert problems_by_name(doc)["helper_"] == ["public helper_ is not a function of the unit"]
    assert doc["functions"][0]["reloc"]["ok"] is True  # func_00010000 itself still matches


def test_land_refuses_a_misnamed_function(env, capsys):
    put_object(env, omf_object(public="func_00010000"))
    assert cli_main(land_argv(env)) == 1
    out = capsys.readouterr().out
    assert f"MISMATCH {EXE}" in out
    reason = "defined in C but not exported as func_00010000_"
    assert f"REFUSED func_00010000 at 0x00010000: {reason}" in out


def test_land_refuses_an_extra_public(env, capsys):
    put_object(env, omf_object(GOOD_OURS + b"\xc3", extra=(("helper_", len(GOOD_OURS)),)))
    assert cli_main(land_argv(env)) == 1
    out = capsys.readouterr().out
    assert "REFUSED helper_: public helper_ is not a function of the unit" in out


def test_a_problem_alone_fails_the_result(env):
    """The result-level gate does not lean on the splice: a problem with every function and
    every splice ok is still a mismatch."""
    result = run_check(env)
    assert result.ok
    problem = check.Unaccounted("func_00010010", OTHER.start, "neither exported nor marked")
    broken = check.CheckResult(result.exe, result.unit, result.compiler, result.flags,
                               result.functions, result.splices, problems=(problem,))  # fmt: skip
    assert all(s.ok for s in broken.splices) and all(fn.ok for fn in broken.functions)
    assert not broken.ok and broken.exit_code == check.EXIT_MISMATCH


# ---- code review IN-01: a static function's mismatch says why ---------------------------------

STATIC_REASON = ("public helper_ is a static (LPUBDEF) function, which check cannot pair with a "
                 "row: give it its row's func_ name or keep the row INCLUDE_ASM")  # fmt: skip


def static_helper_object() -> bytes:
    """omf_object with a `static` helper after func_00010000, as wcc386 emits it: LPUBDEF."""
    code = GOOD_OURS + b"\xc3"
    return module(
        "u_00010000", lnames("", "_TEXT", "CODE", FLAT_LNAME), segdef32(2, 3, len(code)),
        grpdef(4), pubdef32(1, [(SYMBOL, 0)]), lpubdef32(1, [("helper_", len(GOOD_OURS))]),
        extdef("func_00010010_", "_D_00020004"), ledata32(1, 0, code),
        fixupp32(call(1, 1), absolute(6, 2)),
    )  # fmt: skip


def test_static_function_mismatch_names_the_reason(env, monkeypatch, capsys):
    code, doc = check_json(env, monkeypatch, capsys, FakeCompiler(static_helper_object()))
    assert code == check.EXIT_MISMATCH
    assert problems_by_name(doc)["helper_"] == [STATIC_REASON]


def test_land_refuses_a_static_function_naming_the_reason(env, capsys):
    put_object(env, static_helper_object())
    assert cli_main(land_argv(env)) == 1
    assert f"REFUSED helper_: {STATIC_REASON}" in capsys.readouterr().out


def test_static_data_mismatch_names_the_reason():
    data = module(
        "u_00010000", lnames("", "_TEXT", "CODE", "_DATA", "DATA"),
        segdef32(2, 3, len(GOOD_OURS)), segdef32(4, 5, 4),
        pubdef32(1, [(SYMBOL, 0)]), lpubdef32(2, [("counter", 0)]),
        ledata32(1, 0, GOOD_OURS), ledata32(2, 0, b"\0\0\0\0"),
    )  # fmt: skip
    table = SymbolTable.build([ROW, OTHER, FAR])
    account = check.account_unit(check.read_object(data), [ROW, OTHER], table, SOURCE)
    (stray,) = [p for p in account.problems if p.name == "counter"]
    assert stray.reason == ("public counter is static (LPUBDEF) data, which check cannot pair "
                            "with a row: make it non-static")  # fmt: skip


# ---- code review IN-03: the D-12 source checks run for a unit of runtime rows only too ---------

RT_MAIN = FunctionRow(ROW.start, ROW.end, "main_", "runtime", UNIT, "runtime")
RT_CHK = FunctionRow(OTHER.start, OTHER.end, "__CHK", "runtime", UNIT, "runtime")
RUNTIME_SOURCES = {
    "clean": ("int main(void) { return 0; }\n", None),
    "ifdef": ("#ifdef X\nint main(void) { return 0; }\n#endif\n", "line 1: #ifdef"),
    "foreign-marker": ("INCLUDE_ASM(func_00010020);\nint main(void) { return 0; }\n",
                       "func_00010020 is marked INCLUDE_ASM but is not a function of the unit"),
}  # fmt: skip


def runtime_unit(env: Env, source: str) -> FakeCompiler:
    """UNIT holds only runtime rows (main_, __CHK): no game or thunk row is required."""
    write_functions_csv(env.config / STEM / "functions.csv", [RT_MAIN, RT_CHK, FAR], EXE)
    (env.src / STEM / f"{UNIT}.c").write_text(source, encoding="utf-8")
    return FakeCompiler(omf_object(public="main_", callee="__CHK"))


@pytest.mark.parametrize("case", sorted(RUNTIME_SOURCES))
def test_runtime_only_unit_gets_the_source_checks(env, monkeypatch, capsys, case):
    source, problem = RUNTIME_SOURCES[case]
    compiler = runtime_unit(env, source)
    code, doc = check_json(env, monkeypatch, capsys, compiler)
    if problem is None:  # the control: the same unit with a clean file passes
        assert code == check.EXIT_OK and doc["problems"] == [], doc["problems"]
        return
    assert code == check.EXIT_MISMATCH
    reasons = problems_by_name(doc)[check.SOURCE_PROBLEM]
    assert any(problem in reason for reason in reasons), reasons

    put_object(env, compiler.data)
    assert cli_main(land_argv(env)) == 1  # the land step refuses the unit file too
    assert problem in capsys.readouterr().out


def test_source_checks_skip_a_file_that_is_no_unit_file():
    """check_source on a file that is no units.csv unit (the 05-18 runtime pair, Watcom's own
    CMAIN386.C) keeps the exemption: configure never reads that file either."""
    module = check.read_object(omf_object(public="main_", callee="__CHK"))
    table = SymbolTable.build([RT_MAIN, RT_CHK, FAR])
    text = RUNTIME_SOURCES["ifdef"][0]
    assert check.account_unit(module, [RT_MAIN, RT_CHK], table, text).problems
    assert not check.account_unit(module, [RT_MAIN, RT_CHK], table, text,
                                  unit_file=False).problems  # fmt: skip


# ---- code review WR-01: check never writes ninja's objects with options ninja does not use ------


class OptionCompiler(FakeCompiler):
    """The object a non-default option set compiles differs from the committed flags' one."""

    def __call__(self, src, obj, **kwargs):
        default = kwargs["cflags"] is None or Path(kwargs["cflags"]) == check.DEFAULT_CFLAGS
        self.data = omf_object() if default else omf_object(callee="func_00010020_")
        return super().__call__(src, obj, **kwargs)


def ninja_object(env: Env) -> Path:
    return env.build / STEM / "obj" / f"{UNIT}.obj"


def test_check_with_custom_cflags_leaves_ninja_objects_alone(env, monkeypatch, capsys):
    """WR-01: ninja built build/<exe>/obj/<unit>.obj with config/cflags.txt; `check --cflags`
    compiles elsewhere, so the object ninja's land step (`ninja verify`) reads is still the one
    the committed flags produced, with its mtime, and lands with the manifest SHA-1."""
    put_object(env, omf_object())
    obj = ninja_object(env)
    before = (obj.read_bytes(), obj.stat().st_mtime_ns)
    custom = env.root / "experiment.txt"
    custom.write_text("*  wcc386@10.6  -4r -fpi\n", encoding="utf-8")
    compiler = OptionCompiler()
    patch_tools(monkeypatch, compiler=compiler)

    argv = ["check", f"{STEM}/{UNIT}", *env.argv(), "--cflags", str(custom), "--json"]
    assert cli_main(argv) == check.EXIT_MISMATCH  # the experiment's object does not match
    capsys.readouterr()
    assert compiler.calls
    custom_root = env.build / check.CUSTOM_ROOT
    for _, written, kwargs in compiler.calls:
        assert written.is_relative_to(custom_root), written
        assert Path(kwargs["cflags"]) == custom
    assert (obj.read_bytes(), obj.stat().st_mtime_ns) == before
    for kind in ("base", "target"):
        assert not (env.build / STEM / kind).exists(), kind

    assert cli_main(land_argv(env)) == 0  # ninja verify's land step: the committed flags' object
    assert re.search(rf"^OK {EXE} sha1 [0-9a-f]{{40}} landed 1$", capsys.readouterr().out, re.M)


@pytest.mark.parametrize(
    "option", ["--cflags", "--watcom-manifest", "--watcom-dir"]
)  # fmt: skip
def test_any_custom_option_compiles_outside_ninja_paths(env, monkeypatch, capsys, option):
    other = env.root / "other"
    other.mkdir()
    compiler = FakeCompiler()
    patch_tools(monkeypatch, compiler=compiler)
    cli_main(["check", f"{STEM}/{UNIT}", *env.argv(), option, str(other / "x"), "--json"])
    capsys.readouterr()
    assert compiler.calls
    assert all(obj.is_relative_to(env.build / check.CUSTOM_ROOT) for _, obj, _ in compiler.calls)
    assert not ninja_object(env).exists()


def test_check_with_default_options_keeps_ninja_paths(env, monkeypatch, capsys):
    """The CLI passes the committed defaults explicitly; those objects are what ninja's cc edge
    would write, so check keeps writing build/<exe>/obj|base|target (behaviour unchanged)."""
    compiler = FakeCompiler()
    patch_tools(monkeypatch, compiler=compiler)
    assert cli_main(["check", f"{STEM}/{UNIT}", *env.argv(), "--json"]) == 0
    capsys.readouterr()
    assert [obj for _, obj, _ in compiler.calls] == [ninja_object(env)]
    assert not (env.build / check.CUSTOM_ROOT).exists()


# ---- DI-06 part b: check --src/--config OTHER never writes ninja's objects either -------------


def with_option(env: Env, option: str, value: Path) -> list[str]:
    """env.argv() with `option` set to `value` instead of the env tree."""
    argv = env.argv()
    argv[argv.index(option) + 1] = str(value)
    return argv


def other_tree(env: Env, option: str) -> Path:
    """A copy of the env's src or config tree elsewhere: the same files under another root."""
    source = {"--src": env.src, "--config": env.config}[option]
    other = env.root / f"other-{option.lstrip('-')}"
    shutil.copytree(source, other)
    return other


def keeps_ninja_objects(env: Env, monkeypatch, capsys, option: str) -> None:
    put_object(env, omf_object())
    obj = ninja_object(env)
    before = (obj.read_bytes(), obj.stat().st_mtime_ns)
    compiler = FakeCompiler(omf_object(callee="func_00010020_"))  # another object than ninja's
    patch_tools(monkeypatch, compiler=compiler)
    argv = ["check", f"{STEM}/{UNIT}", *with_option(env, option, other_tree(env, option)),
            "--json"]  # fmt: skip
    assert cli_main(argv) == check.EXIT_MISMATCH
    capsys.readouterr()
    assert compiler.calls
    for _, written, _ in compiler.calls:
        assert written.is_relative_to(env.build / check.CUSTOM_ROOT), written
    assert (obj.read_bytes(), obj.stat().st_mtime_ns) == before
    for kind in ("base", "target"):
        assert not (env.build / STEM / kind).exists(), kind


def test_check_with_other_src_keeps_ninja_objects(env, monkeypatch, capsys):
    """DI-06 part b: ninja's cc edge compiles the committed src/; `check --src OTHER` compiles
    other files, so its objects go to build/check-custom/ and ninja's keep bytes and mtime."""
    keeps_ninja_objects(env, monkeypatch, capsys, "--src")


def test_check_with_other_config_keeps_ninja_objects(env, monkeypatch, capsys):
    """DI-06 part b: likewise for `check --config OTHER`."""
    keeps_ninja_objects(env, monkeypatch, capsys, "--config")


def test_default_roots_keep_ninja_paths(env):
    """The committed src/ and config/ (here the env tree, see the fixture) keep build/<exe>/obj,
    for check_unit and for its land step."""
    compiler = FakeCompiler()
    result = run_check(env, compiler)
    assert result.ok, result.format()
    assert [obj for _, obj, _ in compiler.calls] == [ninja_object(env)]
    assert not (env.build / check.CUSTOM_ROOT).exists()


def test_object_root_keys_on_the_src_and_config_roots(env, tmp_path):
    """Orchestrator ruling F7: CompileOptions carries src_root and config_root; None or the
    committed default keeps the build dir, anything else is check-custom."""
    build, custom = env.build, env.build / check.CUSTOM_ROOT
    assert check.object_root(build, check.CompileOptions()) == build
    defaults = check.CompileOptions(src_root=env.src, config_root=env.config)
    assert check.object_root(build, defaults) == build
    assert check.object_root(build, check.CompileOptions(src_root=tmp_path / "x")) == custom
    assert check.object_root(build, check.CompileOptions(config_root=tmp_path / "x")) == custom


def test_land_all_with_other_src_compiles_outside_ninja_paths(env):
    """land_all compiling from another src root (check's land step) never writes ninja's
    objects, even when its options carry no src_root."""
    other = other_tree(env, "--src")
    compiler = FakeCompiler()
    kwargs = {**env.kwargs(), "src_root": other}
    (landed,) = check.land_all(**kwargs, compile_fn=compiler)
    assert landed.ok
    assert compiler.calls
    assert all(obj.is_relative_to(env.build / check.CUSTOM_ROOT) for _, obj, _ in compiler.calls)
    assert not ninja_object(env).exists()


def test_cli_takes_its_default_roots_from_check():
    """Fix round 1, M8: one definition of the committed src/ and config/ trees, so the CLI's
    defaults and object_root's can never drift apart."""
    from reverseapoc import cli

    assert cli.DEFAULT_SRC is check.DEFAULT_SRC
    assert cli.DEFAULT_CONFIG is check.DEFAULT_CONFIG


def test_custom_root_is_no_exe_stem():
    """build/<stem>/ belongs to ninja; the custom root can never be an EXE config stem."""
    assert not check._UNIT_NAME.fullmatch(check.CUSTOM_ROOT)


def test_configure_parser_loads_by_path(monkeypatch):
    """Outside pytest nothing has imported configure.py; check loads it from the checkout."""
    monkeypatch.delitem(sys.modules, "configure", raising=False)
    check._configure.cache_clear()
    try:
        marks = check.source_marks(SOURCE, [ROW, OTHER])
        assert marks.marked == {"func_00010010"} and marks.defined == {"func_00010000"}
        assert Path(check._configure().__file__).name == "configure.py"
    finally:
        check._configure.cache_clear()


# ---- DI-06 part a: ninja's land step lands only objects ninja built from today's files ---------


def ninja_land(env: Env, **kwargs) -> list[check.ExeLand]:
    """`ninja verify`'s land step: land_all without compile_fn."""
    return check.land_all(**{**env.kwargs(), **kwargs})


def assert_stale(env: Env, *words: str, **kwargs) -> None:
    with pytest.raises(check.CheckError) as info:
        ninja_land(env, **kwargs)
    message = str(info.value)
    assert str(ninja_object(env)) in message and "run ninja" in message, message
    for word in words:
        assert word in message, message


def test_land_refuses_an_object_without_a_stamp(env):
    put_object(env, omf_object(), stamp=False)
    assert_stale(env, "stale object", "no provenance stamp")


def test_land_refuses_an_object_with_a_stale_source(env):
    put_object(env, omf_object())
    unit_source(env).write_text(SOURCE + "/* edited after the build */\n", encoding="utf-8")
    assert_stale(env, "stale object", "the source")


def custom_cflags(env: Env, text: str) -> Path:
    path = env.root / "cflags.txt"
    path.write_text(text, encoding="utf-8")
    return path


def test_land_refuses_an_object_with_stale_cflags(env):
    """The table changed since the build, even where the unit's rule did not."""
    cflags = custom_cflags(env, "*  wcc386@10.6  -4r -s -fpi\n")
    put_object(env, omf_object(), stamp=False)
    put_stamp(env, cflags=cflags)
    options = check.CompileOptions(cflags=cflags)
    (landed,) = ninja_land(env, options=options)  # the control: the stamp is fresh
    assert landed.ok
    custom_cflags(env, "# a comment\n*  wcc386@10.6  -4r -s -fpi\n")
    assert_stale(env, "stale object", str(cflags), options=options)


def test_land_refuses_an_object_built_with_other_flags(env):
    cflags = custom_cflags(env, "*  wcc386@10.6  -4r -s -fpi\n")
    put_object(env, omf_object(), stamp=False)
    put_stamp(env, cflags=cflags)
    custom_cflags(env, "*  wcc386@10.6  -4r -fpi\n")
    assert_stale(env, "stale object", "the flags", options=check.CompileOptions(cflags=cflags))


@pytest.mark.parametrize("text", ["", "{torn", "[]", '{"compiler": "wcc386@10.6"}'])
def test_land_refuses_an_unreadable_or_wrong_shaped_stamp(env, text):
    put_object(env, omf_object())
    provenance_path(ninja_object(env)).write_text(text, encoding="utf-8")
    assert_stale(env, "stale object", "unreadable")


def test_land_refuses_a_stamp_of_another_format(env):
    put_object(env, omf_object())
    stamp = provenance_path(ninja_object(env))
    doc = json.loads(stamp.read_text(encoding="utf-8"))
    stamp.write_text(json.dumps({**doc, "version": doc["version"] + 1}), encoding="utf-8")
    assert_stale(env, "stale object", "the stamp format")


def test_land_refuses_an_old_format_stamp(env):
    """A format-1 stamp (06-09's first round: six keys, no header or object hash) is stale."""
    put_object(env, omf_object())
    stamp = provenance_path(ninja_object(env))
    doc = json.loads(stamp.read_text(encoding="utf-8"))
    old = {key: doc[key] for key in ("compiler", "flags", "source_sha256", "cflags_sha256",
                                     "watcom_sha256")} | {"version": 1}  # fmt: skip
    stamp.write_text(json.dumps(old), encoding="utf-8")
    assert_stale(env, "stale object", "format")


def test_land_refuses_an_object_after_a_header_edit(env):
    """I1: the compile reads include/; a header edit since the build makes the object stale."""
    header = env.root / "include" / "common.h"
    header.parent.mkdir()
    header.write_text("#define INCLUDE_ASM(name) extern int INCLUDE_ASM_##name\n",
                      encoding="utf-8")  # fmt: skip
    put_object(env, omf_object())
    (landed,) = ninja_land(env)  # the control: the stamp names today's headers
    assert landed.ok
    header.write_text(header.read_text(encoding="utf-8") + "#define MORE 1\n", encoding="utf-8")
    assert_stale(env, "stale object", "the headers")


def test_land_ignores_files_in_include_that_are_no_project_header(env):
    """Fix round 2, N1: a README, an editor backup or a header in a subdirectory of include/ is
    nothing build.ninja's cc edge declares, so `ninja objects` could never clear a refusal for
    it; the stamp covers exactly the top-level include/*.h."""
    include = env.root / "include"
    include.mkdir()
    (include / "common.h").write_text("#define A 1\n", encoding="utf-8")
    put_object(env, omf_object())
    (include / "README.md").write_text("notes\n", encoding="utf-8")
    (include / "common.h~").write_text("backup\n", encoding="utf-8")
    (include / "sub").mkdir()
    (include / "sub" / "x.h").write_text("int x;\n", encoding="utf-8")
    (landed,) = ninja_land(env)
    assert landed.ok, landed.format()


def test_land_reads_the_object_once(env, monkeypatch):
    """Fix round 2, N3: the bytes land hashes are the bytes it parses and lands."""
    put_object(env, omf_object())
    obj = ninja_object(env)
    reads = []
    real = Path.read_bytes

    def counting(self):
        if self == obj:
            reads.append(self)
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", counting)
    (landed,) = ninja_land(env)
    assert landed.ok
    assert len(reads) == 1


def test_land_refuses_an_object_overwritten_after_its_stamp(env):
    """I2 (T-06-17): another object copied over ninja's keeps the old, fresh-looking stamp; the
    stamp binds the object's bytes, so it is refused."""
    put_object(env, omf_object())
    ninja_object(env).write_bytes(omf_object(callee="func_00010020_"))
    assert_stale(env, "stale object", "the object")


def test_land_refuses_an_object_after_a_watcom_manifest_change(env):
    """M7: the Watcom manifest the compile used changed since the build."""
    manifest = env.root / "watcom.toml"
    manifest.write_bytes(DEFAULT_WATCOM_MANIFEST.read_bytes())
    options = check.CompileOptions(watcom_manifest=manifest)
    put_object(env, omf_object(), stamp=False)
    put_stamp(env, manifest=manifest)
    (landed,) = ninja_land(env, options=options)  # the control
    assert landed.ok
    manifest.write_bytes(manifest.read_bytes() + b"# edited\n")
    assert_stale(env, "stale object", str(manifest), options=options)


def test_land_refuses_an_object_built_by_another_compiler(env):
    """M7: the rule now names another compiler version, with the same flags."""
    cflags = custom_cflags(env, "*  wcc386@10.6  -4r -s -fpi\n")
    put_object(env, omf_object(), stamp=False)
    put_stamp(env, cflags=cflags)
    custom_cflags(env, "*  wcc386@10.5  -4r -s -fpi\n")
    assert_stale(env, "stale object", "the compiler", options=check.CompileOptions(cflags=cflags))


def test_land_accepts_a_fresh_stamp(env):
    put_object(env, omf_object())
    (landed,) = ninja_land(env)
    assert landed.ok, landed.format()
    assert landed.result.landed == (ROW.start,)


def test_land_reads_a_crlf_checkout_as_the_same_source(env):
    """A Windows checkout of the same commit (CRLF) is the same source to the stamp."""
    put_object(env, omf_object())
    unit_source(env).write_bytes(SOURCE.replace("\n", "\r\n").encode("utf-8"))
    (landed,) = ninja_land(env)
    assert landed.ok, landed.format()


def test_land_verb_refuses_a_stale_object(env, capsys):
    put_object(env, omf_object(), stamp=False)
    assert cli_main(land_argv(env)) != 0
    assert "run ninja" in capsys.readouterr().err


def test_check_compiles_past_a_stale_ninja_object(env):
    """The compiling land step (check's) never reads ninja's stamps: it compiles the unit."""
    put_object(env, omf_object(), stamp=False)
    result = run_check(env)
    assert result.ok, result.format()


# ---- 05-REVIEW rows 17a, 17b, 17c and 18b -----------------------------------------------------


def data_public_object(name: str) -> bytes:
    """omf_object's code with `name` exported from a data segment as well."""
    return module(
        "u_00010000", lnames("", "_TEXT", "CODE", "_DATA", "DATA", FLAT_LNAME),
        segdef32(2, 3, len(GOOD_OURS)), segdef32(4, 5, 4), grpdef(6),
        pubdef32(1, [(SYMBOL, 0)]), pubdef32(2, [(name, 0)]),
        extdef("func_00010010_", "_D_00020004"), ledata32(2, 0, b"\0\0\0\0"),
        ledata32(1, 0, GOOD_OURS), fixupp32(call(1, 1), absolute(6, 2)),  # fixups follow code
    )  # fmt: skip


def test_marked_row_with_a_data_public_is_refused():
    """17a: func_00010010 is marked INCLUDE_ASM, but the object exports its linker name as
    data: that is a mismatch naming the row, not a stub."""
    table = SymbolTable.build([ROW, OTHER, FAR])
    module_ = check.read_object(data_public_object("func_00010010_"))
    account = check.account_unit(module_, [ROW, OTHER], table, SOURCE)
    assert OTHER not in account.stubs
    (problem,) = [p for p in account.problems if p.name == OTHER.name]
    assert problem.va == OTHER.start
    assert problem.reason == ("marked INCLUDE_ASM but exported as func_00010010_ outside a code "
                              "segment (data)")  # fmt: skip


def test_land_refuses_a_marked_row_with_a_data_public(env, capsys):
    put_object(env, data_public_object("func_00010010_"))
    assert cli_main(land_argv(env)) == 1
    assert "REFUSED func_00010010 at 0x00010010: marked INCLUDE_ASM" in capsys.readouterr().out


def test_non_utf8_unit_file_is_refused(env):
    """17b: a unit file that is not UTF-8 is refused as configure refuses it, never read with
    replacement characters."""
    unit_source(env).write_bytes(SOURCE.encode("utf-8") + b"/* \xff */\n")
    with pytest.raises(check.CheckError, match="not UTF-8"):
        run_check(env)
    put_object(env, omf_object())
    with pytest.raises(check.CheckError, match="not UTF-8"):
        ninja_land(env)


def test_unit_file_with_a_lone_cr_is_a_source_problem(env):
    """read_source keeps the file's line breaks as they are (no newline translation), so the
    D-12 parser refuses a lone CR as configure does (06-03 fix round 3), and the account names
    it as a source problem of the unit; check refuses such a file before compiling it."""
    text = SOURCE + "int y;\rint z;\n"
    marks = check.source_marks(text, [ROW, OTHER])
    assert any("carriage return" in p for p in marks.problems), marks.problems
    unit_source(env).write_bytes(text.encode("utf-8"))
    compiler = FakeCompiler()
    with pytest.raises(check.CheckError, match="carriage return"):
        run_check(env, compiler=compiler)
    assert compiler.calls == []


# ---- 06-REVIEW CR-02 (fix round 2): a path include is refused before anything compiles ---------

NOTES_INCLUDE = '#include "../../build/driver/r/syn/func_00010000/attempt-1/notes.md"\n'


def test_source_marks_names_a_path_include():
    """source_marks keeps configure's include problems (not only the out-of-unit ones), so the
    account of check, the land step and gate --partial refuse a path include too."""
    marks = check.source_marks(NOTES_INCLUDE + SOURCE, [ROW, OTHER])
    assert any("#include" in p and "notes.md" in p for p in marks.problems), marks.problems
    assert check.source_marks(SOURCE, [ROW, OTHER]).problems == ()


# ---- 07-09 (D-29): the unit's account by start, through the shared unitdefs finder ------------

RENAMED_SOURCE = "/* synthetic */\nint Foo(void) { return 0; }\nINCLUDE_ASM(Bar);\n"
RENAMES = [SymbolRow(ROW.start, "Foo_", "func"), SymbolRow(OTHER.start, "Bar_", "func")]


def test_source_marks_reports_starts():
    """source_marks keeps its name sets and adds the starts; by default names are the rows'
    placeholders, as before D-29."""
    marks = check.source_marks(SOURCE, [ROW, OTHER])
    assert marks.marked == {"func_00010010"} and marks.defined == {"func_00010000"}
    assert marks.marked_starts == {OTHER.start} and marks.defined_starts == {ROW.start}


def test_source_marks_with_c_names_finds_a_renamed_function():
    names = {"Foo": ROW.start, "Bar": OTHER.start}
    marks = check.source_marks(RENAMED_SOURCE, [ROW, OTHER], names=names)
    assert marks.defined_starts == {ROW.start} and marks.marked_starts == {OTHER.start}
    assert marks.problems == ()
    stale = RENAMED_SOURCE.replace("int Foo(", "int func_00010000(")
    (problem,) = check.source_marks(stale, [ROW, OTHER], names=names).problems
    assert "func_00010000" in problem and "Foo" in problem


def test_source_marks_with_all_names_reads_a_renamed_row_by_its_current_name():
    """Fix round 1: all_names alone is authoritative for the unit's own rows."""
    names = {"Foo": ROW.start, "Bar": OTHER.start}
    marks = check.source_marks(RENAMED_SOURCE, [ROW, OTHER], all_names=names)
    assert marks.defined_starts == {ROW.start} and marks.problems == ()
    stale = RENAMED_SOURCE.replace("int Foo(", "int func_00010000(")
    marks = check.source_marks(stale, [ROW, OTHER], all_names=names)
    assert ROW.start not in marks.defined_starts
    (problem,) = marks.problems
    assert "func_00010000" in problem and "Foo" in problem


def test_check_accounts_a_renamed_unit_by_start(env):
    """Orchestrator ruling F27 (b): account_unit reads the unit file with the EXE's C names, so a
    unit whose rows symbols.csv renames (Foo defined, Bar marked under its new name) checks and
    lands like the placeholder unit."""
    write_symbols_csv(env.config / STEM / "symbols.csv", RENAMES, EXE)
    unit_source(env).write_text(RENAMED_SOURCE, encoding="utf-8")
    compiler = FakeCompiler(omf_object(callee="Bar_", public="Foo_"))
    result = run_check(env, compiler=compiler, objdiff=FakeObjdiff())
    assert result.ok, result.format()
    (fn,) = result.functions
    assert fn.va == ROW.start and fn.objdiff_percent == 100.0


@pytest.mark.parametrize("verb", ["check", "gate"])
def test_a_path_include_is_refused_before_compiling(env, monkeypatch, capsys, verb):
    """The attempt check (`check`) and the per-unit gate refuse a unit that includes a path,
    naming the include, before the compiler ever reads the included file."""
    unit_source(env).write_text(NOTES_INCLUDE + SOURCE, encoding="utf-8")
    compiler = FakeCompiler()
    patch_tools(monkeypatch, compiler=compiler)
    assert cli_main([verb, f"{STEM}/{UNIT}", *env.argv()]) == check.EXIT_TOOL
    err = capsys.readouterr().err
    assert "#include" in err and "notes.md" in err, err
    assert compiler.calls == []
    assert not (env.config / STEM / "status.csv").exists()


def test_land_all_refuses_a_path_include_before_compiling(env):
    """land_all with compile_fn (check's land of the other units) refuses the unit too."""
    unit_source(env).write_text(NOTES_INCLUDE + SOURCE, encoding="utf-8")
    compiler = FakeCompiler()
    with pytest.raises(check.CheckError, match="notes.md"):
        check.land_all(**env.kwargs(), compile_fn=compiler)
    assert compiler.calls == []


def test_a_lone_cr_unit_with_a_path_include_is_refused_before_compiling(env):
    """Text configure cannot read (a lone CR) hides its includes from include_problems, so
    refuse_includes refuses it outright, naming why, before the compiler reads any include."""
    unit_source(env).write_bytes(NOTES_INCLUDE.encode("utf-8") + b"int y;\rint z;\n"
                                 + SOURCE.encode("utf-8"))  # fmt: skip
    compiler = FakeCompiler()
    with pytest.raises(check.CheckError, match="refused before compiling.*carriage return"):
        run_check(env, compiler=compiler)
    assert compiler.calls == []
    with pytest.raises(check.CheckError, match="carriage return"):
        check.land_all(**env.kwargs(), compile_fn=compiler)
    assert compiler.calls == []


def test_stray_data_public_message_says_data():
    """17c: a public data symbol that names no row is reported as data."""
    table = SymbolTable.build([ROW, OTHER, FAR])
    module_ = check.read_object(data_public_object("counter"))
    account = check.account_unit(module_, [ROW, OTHER], table, SOURCE)
    (stray,) = [p for p in account.problems if p.name == "counter"]
    assert stray.reason == "public counter is data, not a function of the unit"


def test_a_code_public_check_does_not_take_is_not_called_data(monkeypatch):
    """Fix round 1, M3: `elsewhere` is any public of the row's linker name that
    defined_functions did not take, which can be a code public too (here simulated by a
    defined_functions that takes none). The reason says data only for a public outside a code
    segment, as 17c's does; the row is still a mismatch, never a stub."""
    monkeypatch.setattr(check, "defined_functions", lambda *args: [])
    table = SymbolTable.build([ROW, OTHER, FAR])
    data = omf_object(GOOD_OURS + b"\xc3", extra=(("func_00010010_", len(GOOD_OURS)),))
    account = check.account_unit(check.read_object(data), [ROW, OTHER], table, SOURCE)
    assert account.stubs == ()
    reasons = {p.name: p.reason for p in account.problems}
    in_code = "in a code segment, but not as a function check can pair with its row"
    assert reasons[OTHER.name] == f"marked INCLUDE_ASM but exported as func_00010010_ {in_code}"
    assert reasons[ROW.name] == f"exported as {SYMBOL} {in_code}"


def test_check_json_lists_raw_fields_per_function(env, monkeypatch, capsys):
    """18b: each function's JSON lists the unit's raw fields inside its row; the unit-level
    target.raw_fields keeps all of them."""
    real = check.build_target
    fields = (RawField(ROW.start + 1, "branch"), RawField(OTHER.start + 2, "off32"))

    def with_raw_fields(*args, **kwargs) -> TargetResult:
        return TargetResult(real(*args, **kwargs).data, fields)

    monkeypatch.setattr(check, "build_target", with_raw_fields)
    _, doc = check_json(env, monkeypatch, capsys, FakeCompiler())
    (fn,) = doc["functions"]
    assert fn["raw_fields"] == [{"va": "0x00010001", "kind": "branch"}]
    assert doc["target"]["raw_fields"] == [{"va": "0x00010001", "kind": "branch"},
                                           {"va": "0x00010012", "kind": "off32"}]  # fmt: skip


# ---- DI-02 (05-REVIEW IN-02): a jump table that leads its function ------------------------------
#
# wcc386 puts a switch's table at _TEXT+0, before the function's public, and the function jumps
# through `jmp cs:[eax*4+_TEXT+0]`. The table's entries are fixups to case labels inside the
# function. Made-up layout: a 3-entry table row D_00010100, 4 filler bytes, then func_00010110.

TABLE_VA = CODE_BASE + 0x100
TABLE_ENTRIES = 3
TABLE_SIZE = TABLE_ENTRIES * 4
TABLE_FILLER = bytes.fromhex("8bc08bc0")  # mov eax,eax twice: made-up filler, the same both sides
SWITCH_OFF = TABLE_SIZE + len(TABLE_FILLER)  # our public's offset in _TEXT
SWITCH_VA = TABLE_VA + SWITCH_OFF
# cmp eax,2; ja default; jmp cs:[eax*4+table]; three `mov eax,imm; ret` cases; default: xor; ret
SWITCH_BODY = bytes.fromhex(
    "83f802" "771a" "2eff2485" "00000000" "b80a000000c3" "b815000000c3" "b820000000c3" "31c0c3"
)
JUMP_FIELD = 9  # the table address in the jmp, from the function start
CASES = (13, 19, 25)  # the case labels, from the function start
TABLE_ROW = FunctionRow(TABLE_VA, TABLE_VA + TABLE_SIZE, "D_00010100", "data-in-code", UNIT,
                        "fixup")  # fmt: skip
SWITCH_ROW = FunctionRow(SWITCH_VA, SWITCH_VA + len(SWITCH_BODY), "func_00010110", "game", UNIT,
                         "call")  # fmt: skip
SWITCH_SYMBOL = "func_00010110_"


def _entries(base: int, cases: tuple[int, ...]) -> bytes:
    return b"".join((base + case).to_bytes(4, "little") for case in cases)


def table_module(prefix: bytes = b"", publics: tuple[tuple[str, int], ...] = ()):
    """Our compiled unit: `prefix` (with `publics` in it), the table, the filler and the
    function. Table entries and the jmp's table address are fixups to our own _TEXT."""
    table_off = len(prefix)
    switch_off = table_off + SWITCH_OFF
    data = prefix + _entries(switch_off, CASES) + TABLE_FILLER + SWITCH_BODY
    fixups = [to_segment(table_off + 4 * i, TEXT_INDEX) for i in range(TABLE_ENTRIES)]
    jump = switch_off + JUMP_FIELD
    data = data[:jump] + table_off.to_bytes(4, "little") + data[jump + 4 :]
    fixups.append(to_segment(jump, TEXT_INDEX))
    return our_module(data, fixups, publics=(*publics, (SWITCH_SYMBOL, switch_off)))


def table_original(cases: tuple[int, ...] = CASES, prefix: bytes = b""):
    """The LE: `prefix` right before the table, the table row, the filler and the function, with
    an off32 LE fixup per table entry (to `cases`) and one for the jmp's table address."""
    start = TABLE_VA - len(prefix)
    patch = prefix + bytes(TABLE_SIZE) + TABLE_FILLER + SWITCH_BODY
    records = [le_off32(TABLE_VA + 4 * i, SWITCH_VA - CODE_BASE + case, obj=1)
               for i, case in enumerate(cases)]  # fmt: skip
    records.append(le_off32(SWITCH_VA + JUMP_FIELD, TABLE_VA - CODE_BASE, obj=1))
    return original({start: patch}, page1=b"".join(records))


def table_check(module_, orig, rows):
    exe = SimpleNamespace(flat=orig.flat, fixups=tuple(orig.fixups),
                          symbols=symbol_table(*rows))  # fmt: skip
    return {d.row.name: reloc for d, reloc in check.checked_functions(module_, rows, exe)}


def test_leading_table_pairs_with_its_data_row():
    """The table [0, first public) pairs with the data-in-code row that ends (filler after it)
    right before the function's row: the jmp's table address resolves to the row, and each
    entry is checked against its LE fixup."""
    rows = [TABLE_ROW, SWITCH_ROW]
    module_ = table_module()
    segment = next(seg for seg in module_.segments if seg.name == "_TEXT")
    table = check.leading_table(module_, segment, rows, symbol_table(*rows))
    assert table is not None and table.head == SWITCH_ROW
    assert table.public == check.OwnPublic("_D_00010100", 0, SWITCH_OFF, TABLE_VA)
    verdicts = table_check(module_, table_original(), rows)
    assert list(verdicts) == [SWITCH_ROW.name]
    assert verdicts[SWITCH_ROW.name].ok, verdicts[SWITCH_ROW.name].problems


def test_leading_table_with_a_wrong_entry_fails():
    """One table entry of ours points one case off the original's: the function fails, naming
    the entry's VA."""
    rows = [TABLE_ROW, SWITCH_ROW]
    wrong = (CASES[0], CASES[2], CASES[2])  # the original's entry 1 is case 2, ours case 1
    reloc = table_check(table_module(), table_original(wrong), rows)[SWITCH_ROW.name]
    assert not reloc.ok
    field = f"0x{TABLE_VA + 4:08X}: "
    assert any(p.startswith(field) for p in reloc.problems), reloc.problems


def test_mid_unit_table_still_fails_closed():
    """A table between two publics (func_000100FC, then the table, then the switch) stays
    refused, even when our layout coincides with the original's: the first public's span ends
    at its row's length, so the jmp's table address lies in no own public."""
    first = FunctionRow(TABLE_VA - 4, TABLE_VA - 1, game_name(TABLE_VA - 4), "game", UNIT, "call")
    prefix = bytes.fromhex("31c0c3" "90")  # xor eax,eax; ret; one filler byte
    rows = [first, TABLE_ROW, SWITCH_ROW]
    module_ = table_module(prefix, publics=((f"{first.name}_", 0),))
    verdicts = table_check(module_, table_original(prefix=prefix), rows)
    switch = verdicts[SWITCH_ROW.name]
    assert not switch.ok
    field = f"0x{SWITCH_VA + JUMP_FIELD:08X}: "
    (problem,) = [p for p in switch.problems if p.startswith(field)]
    assert "needs the unit's public-to-row map" in problem


# 06-10 fix round 1, C1: the leading table belongs to the head (the function whose row follows the
# table row). Made-up layout: [D_00010100][filler][func_00010110: mov eax,1; ret][func_00010116:
# the switch through _TEXT+0, its entries to its own cases].
LEAF_BODY = bytes.fromhex("b801000000c3")
LEAF_VA = SWITCH_VA
JUMPER_OFF = SWITCH_OFF + len(LEAF_BODY)
JUMPER_VA = TABLE_VA + JUMPER_OFF
LEAF_ROW = FunctionRow(LEAF_VA, LEAF_VA + len(LEAF_BODY), game_name(LEAF_VA), "game", UNIT, "call")
JUMPER_ROW = FunctionRow(JUMPER_VA, JUMPER_VA + len(SWITCH_BODY), game_name(JUMPER_VA), "game",
                         UNIT, "call")  # fmt: skip
NOT_HEAD_ROWS = [TABLE_ROW, LEAF_ROW, JUMPER_ROW]


def not_head_module():
    """Our unit with the table owned by its second function: entries and jmp into it."""
    data = _entries(JUMPER_OFF, CASES) + TABLE_FILLER + LEAF_BODY + SWITCH_BODY
    fixups = [to_segment(4 * i, TEXT_INDEX) for i in range(TABLE_ENTRIES)]
    fixups.append(to_segment(JUMPER_OFF + JUMP_FIELD, TEXT_INDEX))
    publics = ((f"{LEAF_ROW.name}_", SWITCH_OFF), (f"{JUMPER_ROW.name}_", JUMPER_OFF))
    return our_module(data, fixups, publics=publics)


def not_head_original(cases: tuple[int, ...] = CASES):
    patch = bytes(TABLE_SIZE) + TABLE_FILLER + LEAF_BODY + SWITCH_BODY
    records = [le_off32(TABLE_VA + 4 * i, JUMPER_VA - CODE_BASE + case, obj=1)
               for i, case in enumerate(cases)]  # fmt: skip
    records.append(le_off32(JUMPER_VA + JUMP_FIELD, TABLE_VA - CODE_BASE, obj=1))
    return original({TABLE_VA: patch}, page1=b"".join(records))


@pytest.mark.parametrize("cases", [CASES, (CASES[0], CASES[2], CASES[2])],
                         ids=["same-table", "planted-entry"])  # fmt: skip
def test_leading_table_used_by_another_function_is_refused(cases):
    """Only the head may resolve a reference into the leading table: a later function that
    jumps through `_TEXT+0` is refused, whatever the table holds (it was passed with the table
    checked only in the head's verdict: a planted wrong entry got that function landed)."""
    verdicts = table_check(not_head_module(), not_head_original(cases), NOT_HEAD_ROWS)
    jumper = verdicts[JUMPER_ROW.name]
    assert not jumper.ok
    field = f"0x{JUMPER_VA + JUMP_FIELD:08X}: "
    (problem,) = [p for p in jumper.problems if p.startswith(field)]
    assert "needs the unit's public-to-row map" in problem


def test_leading_table_entry_outside_the_head_fails():
    """Each table entry must land inside the head: an entry to another function of the unit is
    refused even when the original targets the same address (fix round 1, M1)."""
    head = table_check(not_head_module(), not_head_original(), NOT_HEAD_ROWS)[LEAF_ROW.name]
    assert not head.ok
    for i in range(TABLE_ENTRIES):
        field = f"0x{TABLE_VA + 4 * i:08X}: "
        (problem,) = [p for p in head.problems if p.startswith(field)]
        assert "needs the unit's public-to-row map" in problem


def _table_original_with(filler: bytes = TABLE_FILLER, *, extra_entry: bool = False):
    """table_original with other filler, or with a 4th LE table entry where ours has filler."""
    patch = bytes(TABLE_SIZE) + filler + SWITCH_BODY
    records = [le_off32(TABLE_VA + 4 * i, SWITCH_VA - CODE_BASE + case, obj=1)
               for i, case in enumerate(CASES)]  # fmt: skip
    if extra_entry:
        records.append(le_off32(TABLE_VA + TABLE_SIZE, SWITCH_VA - CODE_BASE + CASES[0], obj=1))
    records.append(le_off32(SWITCH_VA + JUMP_FIELD, TABLE_VA - CODE_BASE, obj=1))
    return original({TABLE_VA: patch}, page1=b"".join(records))


@pytest.mark.parametrize(
    ("original_", "expected"),
    [(lambda: _table_original_with(bytes.fromhex("90909090")),
      f"0x{TABLE_VA + TABLE_SIZE:08X}: first of 4 differing bytes outside the relocated fields"),
     (lambda: _table_original_with(bytes(4), extra_entry=True),
      f"0x{TABLE_VA + TABLE_SIZE:08X}: the original has an off32 LE fixup here and ours has "
      "none")],
    ids=["filler-differs", "original-table-longer"],
)  # fmt: skip
def test_leading_table_span_compares_filler_and_length(original_, expected):
    """The span [table row start, head start) is compared like a function, the filler after
    the table included: other filler, or an original table that runs into our filler, fails."""
    reloc = table_check(table_module(), original_(), [TABLE_ROW, SWITCH_ROW])[SWITCH_ROW.name]
    assert not reloc.ok
    assert any(p.startswith(expected) for p in reloc.problems), reloc.problems


@pytest.mark.parametrize(
    "rows",
    [[replace(TABLE_ROW, kind="game", name=game_name(TABLE_VA)), SWITCH_ROW],
     [replace(TABLE_ROW, end=SWITCH_VA + 1), SWITCH_ROW],
     [SWITCH_ROW]],
    ids=["game-row-before-head", "data-row-past-head-start", "no-data-row"],
)  # fmt: skip
def test_no_leading_table_without_its_data_row(rows):
    """leading_table pairs nothing unless the row right before the head is a data-in-code row
    ending at or before the head's start; the jmp through _TEXT+0 then stays refused."""
    module_ = table_module()
    segment = next(seg for seg in module_.segments if seg.name == "_TEXT")
    assert check.leading_table(module_, segment, rows, symbol_table(*rows)) is None
    switch = table_check(module_, table_original(), rows)[SWITCH_ROW.name]
    field = f"0x{SWITCH_VA + JUMP_FIELD:08X}: "
    (problem,) = [p for p in switch.problems if p.startswith(field)]
    assert "needs the unit's public-to-row map" in problem


# ---- 07-03 (D-27 P1): the cflags rule by the unit's logical path src/<exe>/<unit>.c ------------

UNIT_RULE = f"src/{STEM}/{UNIT}.c"


def repo_stand_in(env: Env, monkeypatch) -> Path:
    """The env tree stands in for the repository, so a tree under it is "inside the repo" for
    the compile root. configure.py is loaded first: check finds it under REPO_ROOT."""
    check._configure()
    monkeypatch.setattr(check, "REPO_ROOT", env.root)
    return env.root


def view_tree(env: Env, *parts: str, include: bool = True) -> Path:
    """A copy of the env's src/ under env.root/<parts>/src, with an include/ beside it unless
    `include` is False (a D-24 view holds one, a flag re-gate copy does not)."""
    top = env.root.joinpath(*parts)
    shutil.copytree(env.src, top / "src")
    if include:
        (top / "include").mkdir()
    return top / "src"


def test_check_compiles_a_view_unit_under_its_rule(env, monkeypatch):
    """A D-24 view (build/driver/.../view/src with include/ beside it) compiles each unit with
    its logical path src/<exe>/<unit>.c and the view as compile root, the claimed unit and every
    unit the land step compiles alike."""
    repo_stand_in(env, monkeypatch)
    src = view_tree(env, "build", "driver", "run1", "view")
    (src / STEM / f"{FAR_UNIT}.c").write_text("int func_00010020(void) { return 0; }\n",
                                              encoding="utf-8")  # fmt: skip
    compiler = FakeCompiler()
    check.check_unit(STEM, UNIT, **{**env.kwargs(), "src_root": src}, compile_fn=compiler,
                     objdiff_runner=FakeObjdiff())  # fmt: skip
    seen = [(path.name, kwargs.get("rule_path"), kwargs.get("root"))
            for path, _, kwargs in compiler.calls]  # fmt: skip
    assert seen == [(f"{UNIT}.c", UNIT_RULE, src.parent),
                    (f"{FAR_UNIT}.c", f"src/{STEM}/{FAR_UNIT}.c", src.parent)]  # fmt: skip


def test_default_tree_compile_passes_repo_root(env, monkeypatch):
    """The committed src tree compiles from the repository root, with its logical path."""
    root = repo_stand_in(env, monkeypatch)
    compiler = FakeCompiler()
    assert run_check(env, compiler).ok
    calls = [(kwargs.get("rule_path"), kwargs.get("root")) for _, _, kwargs in compiler.calls]
    assert calls == [(UNIT_RULE, root)]


def test_compile_root_for_each_kind_of_tree(env, monkeypatch, tmp_path):
    """Only a D-24 view (build/driver/.../view/src with include/ beside it) compiles from its
    view root; any other tree (a copy without include/, a saved attempt's best/, the committed
    src/) from the repository root."""
    root = repo_stand_in(env, monkeypatch)
    view = view_tree(env, "build", "driver", "run1", "view")
    copy = view_tree(env, "build", "flags", "p1", include=False)
    best = env.root / "build" / "driver" / "run1" / "best"
    best.mkdir(parents=True)
    assert check._compile_root_for(view) == view.parent
    assert check._compile_root_for(copy) == root
    assert check._compile_root_for(best) == root
    assert check._compile_root_for(env.src) == root


def test_a_tree_outside_the_repository_compiles_from_the_repository(env, monkeypatch, tmp_path):
    """Fix round 1: a tree outside the repository is no view, so it compiles from REPO_ROOT (and
    compile_rule refuses its sources, as it did before 07-03), never from its parent's
    include/."""
    root = repo_stand_in(env, monkeypatch)
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    (outside / "include").mkdir(parents=True)
    assert check._compile_root_for(outside / "src") == root
    assert check._compile_root_for(outside / "view" / "src") == root


@pytest.mark.parametrize(
    "parts",
    [("build", "flags", "p1"), ("elsewhere",), ("build", "driver", "run1", "notview"),
     ("build", "test-view", "x", "view")],
    ids=["flags-copy", "elsewhere", "driver-not-view", "view-outside-driver"],
)  # fmt: skip
def test_an_in_repo_src_with_include_that_is_no_view_compiles_from_the_repository(
    env, monkeypatch, parts
):
    """Fix round 1: <x>/src with <x>/include beside it compiles from <x> only when it is a D-24
    view, build/driver/.../view/src; otherwise from REPO_ROOT, with the committed headers."""
    root = repo_stand_in(env, monkeypatch)
    src = view_tree(env, *parts)  # include/ beside it
    assert check._compile_root_for(src) == root


def test_committed_src_compiles_from_the_repository():
    """Unpatched: the committed src/ (and None, its stand-in) compile from REPO_ROOT."""
    assert check._compile_root_for(None) == check.REPO_ROOT
    assert check._compile_root_for(check.REPO_ROOT / "src") == check.REPO_ROOT


def test_provenance_agrees_with_the_compile_rule(env, monkeypatch):
    """An object ninja built under a per-unit rule lands from a copy of src/ (a flag re-gate's
    tree, no include/): check_provenance selects the rule by the logical path, as the compile
    did. The same stamp checked as if under `*` is stale."""
    repo_stand_in(env, monkeypatch)
    copy = view_tree(env, "build", "flags", "p1", include=False)
    cflags = custom_cflags(env, f"*  wcc386@10.6  -4r -s -fpi\n"
                                f"{UNIT_RULE}  wcc386@10.6  -4r -s -fpi -ot\n")  # fmt: skip
    put_object(env, omf_object(), stamp=False)
    stamp = put_stamp(env, cflags=cflags)  # env.src/syn/<unit>.c is UNIT_RULE: the unit's rule
    assert json.loads(stamp.read_text(encoding="utf-8"))["flags"] == ["-4r", "-s", "-fpi", "-ot"]
    options = check.CompileOptions(cflags=cflags)
    (landed,) = ninja_land(env, src_root=copy, options=options)
    assert landed.ok, landed.format()
    doc = json.loads(stamp.read_text(encoding="utf-8"))
    stamp.write_text(json.dumps({**doc, "flags": ["-4r", "-s", "-fpi"]}), encoding="utf-8")
    assert_stale(env, "stale object", "the flags", src_root=copy, options=options)


def test_sweep_compiles_a_view_against_the_views_include(env, monkeypatch):
    """07-11 (orchestrator note on 07-03 as built): a sweep of a D-24 view compiles every cell
    from the view root (its include/), with its objects in the view's build/; a sweep of any
    other tree still compiles from the repository root."""
    root = repo_stand_in(env, monkeypatch)
    committed = FlagCompiler()
    run_sweep(env, committed, versions=("10.6",))  # writes the env's watcom/10.6
    assert {call_kwargs["root"] for _, _, call_kwargs in committed.calls} == {root}
    src = view_tree(env, "build", "driver", "run1", "view")
    compiler = FlagCompiler()
    kwargs = {**env.kwargs(), "src_root": src, "build_dir": src.parent / "build"}
    check.sweep(STEM, UNIT, "func_00010000", **kwargs, watcom_dir=env.root / "watcom",
                compile_fn=compiler, objdiff_runner=FakeObjdiff(100.0))  # fmt: skip
    assert compiler.calls
    assert {call_kwargs["root"] for _, _, call_kwargs in compiler.calls} == {src.parent}
    assert all(obj.is_relative_to(src.parent / "build") for _, obj, _ in compiler.calls)


# ---- 07-14: the D-15 second-stage sweep ---------------------------------------------------------


def cell_rule(base_elf: str) -> list[str]:
    """The flags of the cell whose ELF objdiff is diffing: its temporary rule `cell-NN.cflags`
    sits beside `cell-NN.elf` in the sweep's work directory."""
    words = Path(base_elf).with_suffix(".cflags").read_text(encoding="utf-8").split()
    return words[2:]  # drop the glob and the compiler spec


class RuleObjdiff(FakeObjdiff):
    """objdiff's percent per cell: `hits` (flag tuples) score 100.0, every other cell `near`."""

    def __init__(self, near: float, *hits: tuple[str, ...]) -> None:
        super().__init__(near)
        self.near = near
        self.hits = set(hits)

    def __call__(self, argv):
        self.argvs.append(list(argv))
        percent = 100.0 if tuple(cell_rule(argv[5])) in self.hits else self.near
        return objdiff_json(percent, argv[-1])


def run_near_miss(env: Env, objdiff: FakeObjdiff, compiler=None):
    """A sweep where every cell compiles the matching object; `objdiff` alone sets the score."""
    return check.sweep(
        STEM, UNIT, "func_00010000", **env.kwargs(), watcom_dir=watcom_tree(env),
        compile_fn=compiler or FakeCompiler(), objdiff_runner=objdiff,
    )  # fmt: skip


OF_PLUS = ("-4r", "-of+", "-s", "-fpi")


def test_stage2_runs_on_a_near_miss(env):
    """D-15: stage 1's best is 92.0 with relocations passing, so stage 2 runs; its O1 cell
    `-4r -of+ -s -fpi` (the -o set of the best cell, cell 01, replaced) measures 100.0."""
    report = run_near_miss(env, RuleObjdiff(92.0, OF_PLUS))
    doc = report.to_json()
    assert doc.get("stage2") is not None
    stage2 = report.stage2
    assert 0 < len(stage2) <= 24
    assert all(cell.version == "10.6" for cell in stage2)
    assert [cell.number for cell in stage2] == list(range(31, 31 + len(stage2)))
    (hit,) = [cell for cell in stage2 if cell.flags == OF_PLUS]
    assert (hit.percent, hit.reloc_ok, hit.differing) == (100.0, True, 0)
    assert report.stage2_best == (hit,)
    assert doc["stage2"]["from"] == 1
    assert doc["stage2"]["best"] == [hit.number]
    assert hit.to_json() in doc["stage2"]["cells"]
    log = report.log_path.read_text(encoding="utf-8")
    assert f"stage 2 best: cell {hit.number}" in log
    assert hit.line() in log.splitlines()


def test_stage2_skipped_when_stage1_hits(env):
    """A perfect stage-1 cell (objdiff 100.0, relocations passing, 0 differing) leaves stage 2
    unrun: the report's stage2 is null and nothing past stage 1 compiles."""
    compiler = FlagCompiler()
    report = run_sweep(env, compiler)
    doc = report.to_json()
    assert "stage2" in doc and doc["stage2"] is None
    assert report.stage2 is None and report.stage2_best is None
    assert len(compiler.calls) == 30


def best_cell(*flags: str) -> check.SweepCell:
    return check.SweepCell(1, "10.6", flags, "", 95.0, True, 2)


def test_sweep2_cells_from_ot():
    """D-15 composition for best `-4r -ot -s -fpi`: O1 replaces -ot (8 letters, KKND's set), O2
    adds each letter to -ot, Z adds a packing, F an FP scheduling; all under 10.6, all keeping
    -4r, -s and -fpi (M, -zm, is Task 3's)."""
    cells = check.sweep2_cells(best_cell("-4r", "-ot", "-s", "-fpi"))
    letters = ("-od", "-of+", "-or", "-oi", "-om", "-ol", "-on", "-op")
    o1 = [("-4r", letter, "-s", "-fpi") for letter in letters]
    o1.append(("-4r", "-of+", "-omiler", "-s", "-fpi"))
    o2 = [("-4r", "-ot", letter, "-s", "-fpi") for letter in letters]
    z = [("-4r", "-ot", "-s", "-fpi", pack) for pack in ("-zp1", "-zp2", "-zp4", "-zp8")]
    f = [("-4r", "-ot", "-s", "-fpi", fp) for fp in ("-fp3", "-fp5")]
    flags = [cell_flags for _, cell_flags in cells]
    assert flags[:9] == o1 and flags[9:17] == o2 and flags[17:21] == z and flags[-2:] == f
    assert len(cells) <= 24
    assert {version for version, _ in cells} == {"10.6"}
    assert len(set(flags)) == len(flags)
    assert all({"-4r", "-s", "-fpi"} <= set(cell_flags) for cell_flags in flags)
    assert check.SWEEP2_LETTERS == letters and check.SWEEP2_KKND == ("-of+", "-omiler")
    assert check.SWEEP2_PACK == ("-zp1", "-zp2", "-zp4", "-zp8")
    assert check.SWEEP2_FP == ("-fp3", "-fp5")


def test_sweep2_cells_from_no_o():
    """A best cell without an -o set (`-5r -s -fpi`) has no O2 cell; a __CHK caller's best cell
    without -s still has none in any stage-2 cell."""
    cells = check.sweep2_cells(best_cell("-5r", "-s", "-fpi"))
    flags = [cell_flags for _, cell_flags in cells]
    o1 = [("-5r", letter, "-s", "-fpi") for letter in check.SWEEP2_LETTERS]
    o1.append(("-5r", "-of+", "-omiler", "-s", "-fpi"))
    assert flags[:9] == o1
    assert flags[9:13] == [("-5r", "-s", "-fpi", pack) for pack in ("-zp1", "-zp2", "-zp4", "-zp8")]
    assert flags[-2:] == [("-5r", "-s", "-fpi", fp) for fp in ("-fp3", "-fp5")]
    assert not [f for f in flags if set(f) & {"-ox", "-os", "-ot", "-oneatx"}]
    no_stack = [cell_flags for _, cell_flags in check.sweep2_cells(best_cell("-4r", "-ox", "-fpi"))]
    assert all("-s" not in cell_flags for cell_flags in no_stack)
    assert ("-4r", "-ox", "-od", "-fpi") in no_stack


def reloc_fails() -> FakeCompiler:
    return FakeCompiler(omf_object(callee="func_00010020_"))


@pytest.mark.parametrize(
    ("percent", "compiler", "reloc_ok", "runs"),
    [(90.0, FakeCompiler, True, True), (89.99, FakeCompiler, True, False),
     (95.0, reloc_fails, False, False)],
    ids=["90.0-runs", "89.99-not", "reloc-failed-not"],
)  # fmt: skip
def test_trigger_edges(env, percent, compiler, reloc_ok, runs):
    """D-15/DEC-03 adjacency, end to end: stage 2 runs when no stage-1 cell is perfect and the
    best one reaches 90.0 with its relocations passing."""
    report = run_near_miss(env, FakeObjdiff(percent), compiler())
    best = report.best[0]
    assert (best.percent, best.reloc_ok) == (percent, reloc_ok)
    assert (report.stage2 is not None) is runs
    assert (report.to_json()["stage2"] is not None) is runs


def sweep_cell(number: int, percent: float, *, reloc_ok: bool = True, differing: int = 0):
    return check.SweepCell(number, "10.6", ("-4r", "-s", "-fpi"), "", percent, reloc_ok, differing)


def test_trigger_edges_perfect_needs_zero_differing():
    """A stage-1 cell at 100.0 with one differing byte is not perfect: stage 2 still runs from it.
    (check's relocation check compares bytes too, so a compiled object cannot show this; the
    trigger is judged on the cells.) A perfect cell anywhere stops stage 2; so does a best cell
    whose relocations fail, and an empty or unmeasured stage 1."""
    near = sweep_cell(1, 100.0, differing=1)
    assert check.sweep2_trigger([near, sweep_cell(2, 91.0)]) == near
    assert check.sweep2_trigger([sweep_cell(1, 92.0), sweep_cell(2, 100.0)]) is None
    assert check.sweep2_trigger([sweep_cell(1, 90.0)]) == sweep_cell(1, 90.0)
    assert check.sweep2_trigger([sweep_cell(1, 89.99)]) is None
    assert check.sweep2_trigger([sweep_cell(1, 95.0, reloc_ok=False)]) is None
    assert check.sweep2_trigger([]) is None
    assert check.sweep2_trigger([check.SweepCell(1, "10.6", ("-4r",), check.NOT_INSTALLED)]) is None


def test_every_cell_rule_parses():
    """Every second-stage cell's one-rule text, for the best of any stage-1 cell, passes
    parse_cflags: each flag is _SAFE_FLAG-legal, one option and not wrapper-owned."""
    from reverseapoc.cflags import WRAPPER_OWNED, parse_cflags

    for version, flags in check.sweep_cells(chk=True):
        best = check.SweepCell(1, version, flags, "", 95.0, True, 1)
        for cell_version, cell_flags in check.sweep2_cells(best):
            spec = f"{check.SWEEP_COMPILER}@{cell_version}"
            text = check.SWEEP_RULE.format(spec=spec, flags=" ".join(cell_flags))
            (rule,) = parse_cflags(text, versions=check.SWEEP_VERSIONS)
            assert rule.flags == cell_flags
            assert not any(f.lower().startswith(WRAPPER_OWNED) for f in cell_flags)
