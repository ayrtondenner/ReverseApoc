"""gate (D-21, D-24, AGT-06): the only writer of config/<exe>/status.csv. check itself is faked
here (its own tests are tests/test_check.py): a fake check models a tree of unit files, each
defining some functions, and lands every defined function of every unit file present, as
check's land step does. Every name, address and hash is made up."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest

from conftest import write_manifest
from reverseapoc import gate
from reverseapoc.check import CheckError, CheckResult, ExeLand, FunctionCheck
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import FunctionRow, UnitRow, write_functions_csv, write_units_csv
from reverseapoc.land import LandResult
from reverseapoc.relocs import RelocResult
from reverseapoc.status import MATCHED, StatusRow, lf_sha256, read_status, status_path, write_status

UFO, TACP = "UFO2P.EXE", "TACP.EXE"
STEMS = {UFO: "ufo2p", TACP: "tacp"}
A1, A2, B1, C1 = 0x10000, 0x10010, 0x10020, 0x10030  # UFO2P
T1 = 0x20000  # TACP
UNIT_A, UNIT_B, UNIT_C, UNIT_T = "u_00010000", "u_00010020", "u_00010030", "u_00020000"
ROWS = {
    UFO: [(A1, UNIT_A), (A2, UNIT_A), (B1, UNIT_B), (C1, UNIT_C)],
    TACP: [(T1, UNIT_T)],
}
TODAY = date(2026, 10, 25)
SHA1 = "0" * 40


def fname(start: int) -> str:
    return f"func_{start:08X}"


@dataclass
class Tree:
    """A tmp repository: manifest, config/<exe>/{functions,units}.csv, src/<exe>/<unit>.c, and
    which functions each unit file defines in C (`defined`)."""

    root: Path
    defined: dict[tuple[str, str], list[int]] = field(default_factory=dict)

    @property
    def config(self) -> Path:
        return self.root / "config"

    @property
    def src(self) -> Path:
        return self.root / "src"

    @property
    def roots(self) -> gate.GateRoots:
        return gate.GateRoots(orig_dir=self.root / "orig", manifest=self.root / "targets.toml",
                              config_root=self.config, src_root=self.src,
                              build_dir=self.root / "build")  # fmt: skip

    def argv(self) -> list[str]:
        r = self.roots
        return ["--orig", str(r.orig_dir), "--manifest", str(r.manifest), "--config",
                str(r.config_root), "--src", str(r.src_root), "--build", str(r.build_dir)]  # fmt: skip

    def source(self, exe: str, unit: str) -> Path:
        return self.src / STEMS[exe] / f"{unit}.c"

    def write_unit(self, exe: str, unit: str, starts: list[int], *, crlf: bool = False) -> str:
        """Write the unit file defining `starts` in C (the other rows of the unit stay
        INCLUDE_ASM) and return its LF text."""
        rows = [start for start, u in ROWS[exe] if u == unit]
        lines = ['#include "common.h"']
        for start in rows:
            lines.append(f"int {fname(start)}(void) {{ return {start}; }}" if start in starts
                         else f"INCLUDE_ASM({fname(start)});")  # fmt: skip
        text = "\n".join(lines) + "\n"
        path = self.source(exe, unit)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
        self.defined[(exe, unit)] = list(starts)
        return text

    def remove_unit(self, exe: str, unit: str) -> None:
        self.source(exe, unit).unlink()
        del self.defined[(exe, unit)]

    def status(self, exe: str) -> Path:
        return status_path(self.config, STEMS[exe])

    def rows(self, exe: str) -> list[StatusRow]:
        return read_status(self.status(exe))


def make_tree(root: Path) -> Tree:
    write_manifest(root / "targets.toml", {UFO: b"ufo", TACP: b"tacp"})
    for exe, rows in ROWS.items():
        config = root / "config" / STEMS[exe]
        functions = [FunctionRow(s, s + 0x10, fname(s), "game", u, "call") for s, u in rows]
        write_functions_csv(config / "functions.csv", functions, exe)
        units = sorted({u for _, u in rows})
        spans = [UnitRow(u, min(s for s, x in rows if x == u),
                         max(s for s, x in rows if x == u) + 0x10, "hand") for u in units]  # fmt: skip
        write_units_csv(config / "units.csv", spans, exe)
    return Tree(root)


@pytest.fixture
def tree(tmp_path) -> Tree:
    return make_tree(tmp_path)


def ok_function(start: int, percent: float = 100.0, *, ok: bool = True) -> FunctionCheck:
    reloc = RelocResult(ok, () if ok else ("0x00010001: wrong target",), frozenset(), frozenset(),
                        start, 0x10, "1" * 40)  # fmt: skip
    return FunctionCheck(fname(start), start, 0x10, percent, reloc, ok, 0 if ok else 1,
                         None if ok else start)  # fmt: skip


def splice(exe: str, landed, *, ok: bool = True) -> ExeLand:
    result = LandResult(b"", SHA1 if ok else "f" * 40, SHA1, tuple(sorted(landed)), 0)
    return ExeLand(exe, result)


class FakeCheck:
    """Stands in for check_unit. It defines the functions the tree's unit file defines, all at
    100.0 unless `percent` says otherwise, and lands every function every present unit file
    defines (or `landed[exe]` when given). `mismatch` makes the gated unit's check fail;
    `error` raises it as a tool error."""

    def __init__(self, tree: Tree, *, mismatch: bool = False, error: Exception | None = None,
                 landed: dict[str, set[int]] | None = None) -> None:  # fmt: skip
        self.tree, self.mismatch, self.error = tree, mismatch, error
        self.landed = landed or {}
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, exe: str, unit: str, **kwargs) -> CheckResult:
        self.calls.append((exe, unit, kwargs))
        if self.error is not None:
            raise self.error
        name = next(n for n, s in STEMS.items() if s == exe.lower() or n.lower() == exe.lower())
        functions = tuple(ok_function(s, 50.0 if self.mismatch else 100.0)
                          for s in self.tree.defined.get((name, unit), []))  # fmt: skip
        splices = []
        for other in (UFO, TACP):
            default = {s for (e, _), starts in self.tree.defined.items() if e == other
                       for s in starts}  # fmt: skip
            splices.append(splice(other, self.landed.get(other, default)))
        return CheckResult(exe, unit, "wcc386", ("-4r",), functions, tuple(splices))


def run_gate(tree: Tree, *targets: str, check: FakeCheck | None = None, attempts: int = 0):
    pairs = [tuple(t.split("/")) for t in targets]
    return gate.gate_units(pairs, roots=tree.roots, attempts=attempts, today=TODAY,
                           check_fn=check or FakeCheck(tree))  # fmt: skip


# ---- Task 1: the tracer -------------------------------------------------------------------------


def test_gate_writes_matched_rows_on_pass(tree):
    text = tree.write_unit(UFO, UNIT_A, [A1], crlf=True)
    check = FakeCheck(tree)
    result = gate.gate_unit("ufo2p", UNIT_A, roots=tree.roots, attempts=2, today=TODAY,
                            check_fn=check)  # fmt: skip
    assert result.exit_code == 0 and result.ok
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert lf_sha256(text) == sha
    assert tree.rows(UFO) == [StatusRow(A1, fname(A1), UNIT_A, MATCHED, 100.0, 2, sha,
                                        "2026-10-25")]  # fmt: skip
    assert not tree.status(TACP).exists()  # sparse: no row, no file
    assert [(exe, unit) for exe, unit, _ in check.calls] == [("ufo2p", UNIT_A)]
    doc = result.to_json()
    assert doc["ok"] is True and doc["exit_code"] == 0
    assert [w["start"] for w in doc["written"]] == ["0x00010000"]


def test_gate_writes_nothing_on_mismatch(tree):
    tree.write_unit(UFO, UNIT_A, [A1])
    write_status(tree.status(UFO), [StatusRow(B1, fname(B1), UNIT_B, MATCHED, 100.0, 1,
                                              "c" * 64, "2026-10-01")])  # fmt: skip
    before = tree.status(UFO).read_bytes()
    result = run_gate(tree, f"ufo2p/{UNIT_A}", check=FakeCheck(tree, mismatch=True))
    assert result.exit_code == 1 and not result.ok
    assert result.written == ()
    assert tree.status(UFO).read_bytes() == before


def test_gate_writes_nothing_on_a_tool_error(tree):
    tree.write_unit(UFO, UNIT_A, [A1])
    with pytest.raises(CheckError, match="objdiff"):
        run_gate(tree, f"ufo2p/{UNIT_A}", check=FakeCheck(tree, error=CheckError("objdiff")))
    assert not tree.status(UFO).exists()


def test_gate_refuses_negative_attempts(tree):
    tree.write_unit(UFO, UNIT_A, [A1])
    with pytest.raises(CheckError, match="attempts"):
        run_gate(tree, f"ufo2p/{UNIT_A}", attempts=-1)
    assert not tree.status(UFO).exists()


@pytest.mark.parametrize(
    ("fake", "code"),
    [({}, 0), ({"mismatch": True}, 1), ({"error": CheckError("objdiff-cli not found")}, 2)],
    ids=["pass", "mismatch", "tool"],
)
def test_gate_cli_exit_codes(tree, monkeypatch, capsys, fake, code):
    tree.write_unit(UFO, UNIT_A, [A1])
    monkeypatch.setattr(gate, "check_unit", FakeCheck(tree, **fake))
    assert cli_main(["gate", f"ufo2p/{UNIT_A}", *tree.argv(), "--attempts", "1", "--json"]) == code
    out = capsys.readouterr()
    if code == 2:
        assert "reverseapoc gate: error: objdiff-cli not found" in out.err
        assert not tree.status(UFO).exists()
    else:
        assert json.loads(out.out)["ok"] is (code == 0)
        assert (tree.rows(UFO)[0].attempts == 1) if code == 0 else not tree.status(UFO).exists()


@pytest.mark.parametrize("target", ["ufo2p", "ufo2p/", "/u_x", "ufo2p/a/b"])
def test_gate_cli_refuses_a_bad_target(tree, monkeypatch, capsys, target):
    monkeypatch.setattr(gate, "check_unit", FakeCheck(tree))
    assert cli_main(["gate", target, *tree.argv()]) == 2
    assert "expected EXE/UNIT" in capsys.readouterr().err


def test_gate_cli_text_output(tree, monkeypatch, capsys):
    tree.write_unit(UFO, UNIT_A, [A1])
    monkeypatch.setattr(gate, "check_unit", FakeCheck(tree))
    assert cli_main(["gate", f"ufo2p/{UNIT_A}", *tree.argv()]) == 0
    out = capsys.readouterr().out
    assert f"matched {fname(A1)}" in out
    assert out.rstrip().endswith("ok")
