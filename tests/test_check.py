"""check: compile, convert, cut, objdiff per function, relocation check, land and the SHA-1 of every
EXE (SPL-11, D-16). Only the compiler and objdiff-cli are faked; omf2elf, target, relocs and land
run for real on synthetic inputs. Every byte, name and address is made up (tests/relocpair.py)."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import write_manifest
from omfimage import extdef, fixupp32, ledata32, lnames, lpubdef32, module, pubdef32, segdef32
from relocpair import (
    CODE_BASE,
    GOOD_ORIGINAL,
    GOOD_OURS,
    LOAD_FIELD,
    absolute,
    call,
    le_off32,
    original,
)
from reverseapoc import check
from reverseapoc.asm import data_ranges
from reverseapoc.cflags import Rule
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import FunctionRow, UnitRow, write_functions_csv, write_units_csv
from reverseapoc.le import LE
from reverseapoc.symbols import SymbolTable
from reverseapoc.target import build_target

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
        lnames("", "_TEXT", "CODE"),
        segdef32(2, 3, len(code)),
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
def env(tmp_path):
    return make_env(tmp_path)


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


def put_object(env: Env, data: bytes) -> None:
    obj = env.build / STEM / "obj" / f"{UNIT}.obj"
    obj.parent.mkdir(parents=True, exist_ok=True)
    obj.write_bytes(data)


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
        "u_00010000", lnames("", "_TEXT", "CODE"), segdef32(2, 3, len(code)),
        pubdef32(1, [(SYMBOL, 0)]), lpubdef32(1, [("helper_", len(GOOD_OURS))]),
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
