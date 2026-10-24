"""check: compile, convert, cut, objdiff per function, relocation check, land and the SHA-1 of every
EXE (SPL-11, D-16). Only the compiler and objdiff-cli are faked; omf2elf, target, relocs and land
run for real on synthetic inputs. Every byte, name and address is made up (tests/relocpair.py)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import write_manifest
from omfimage import extdef, fixupp32, ledata32, lnames, module, pubdef32, segdef32
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
from reverseapoc.cflags import Rule
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import FunctionRow, UnitRow, write_functions_csv, write_units_csv

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


def omf_object(code: bytes = GOOD_OURS, callee: str = "func_00010010_") -> bytes:
    """Our compiled unit: `_TEXT` holding `code` with func_00010000_ at 0, a self-relative call
    to `callee` at 1 and an absolute load of _D_00020004 at 6."""
    return module(
        "u_00010000",
        lnames("", "_TEXT", "CODE"),
        segdef32(2, 3, len(code)),
        pubdef32(1, [(SYMBOL, 0)]),
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
