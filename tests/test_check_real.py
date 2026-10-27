"""The production pipeline on the spike 005 pair (plan 05-18): Watcom's own CMAIN386.C, read in
place from the owner's 10.6 tree and never copied, against the `__CMain` runtime row of each EXE.

check_source compiles it with `reverseapoc cc` (the `*` cflags rule), converts it with omf2elf, cuts
the target with target.py and scores it with objdiff-cli, the relocation check and the byte
compare; land() of that one function must give the manifest SHA-1. A planted wrong call target in
our object must fail the relocation check.

These tests skip unless CMAIN386.C, orig/<EXE>, a compiler runner and objdiff-cli all exist (the
main checkout's container). They write only under build/test-check/ (the compiler writes only
inside the repository) and assert on names, VAs, percentages, counts and SHA-1s, never on bytes.

The WR-01 test also needs ninja: it runs configure.py and ninja on the committed units, then
`check` with an experimental cflags file, and shows that ninja's object is still the one
config/cflags.txt compiled. It compares our own compiled objects with each other, never with
game bytes.
"""

from __future__ import annotations

import dataclasses
import re
import secrets
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

import configure
from conftest import ORIG_DIR, REPO_ROOT, WATCOM_DIR, requires_objdiff, requires_runner
from reverseapoc import check
from reverseapoc.cflags import load_cflags, select_rule
from reverseapoc.compiler import compile_source, read_provenance
from reverseapoc.land import LandedFunction, land
from reverseapoc.relocs import check_function
from reverseapoc.targets import load_manifest
from reverseapoc.watcom import DEFAULT_INSTALL

CMAIN386 = WATCOM_DIR / "10.6" / "SRC" / "STARTUP" / "386" / "CMAIN386.C"
SYMBOL = "__CMain"  # the runtime row's name and its linker name
UNIT = "rt_cmain386"
MANIFEST = REPO_ROOT / "config" / "targets.toml"
CONFIG = REPO_ROOT / "config"
BUILD_ROOT = REPO_ROOT / "build" / "test-check"  # the compiler writes only inside the repository
CALLEE, PLANTED = "exit_", "main_"  # two externs CMAIN386.C calls; the plant swaps them


@pytest.fixture
def build_dir(request) -> Path:
    """A fresh build/test-check/<test name> directory for this test (removed and recreated)."""
    path = BUILD_ROOT / re.sub(r"[^A-Za-z0-9._-]", "_", request.node.name)
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


def _exe(name: str) -> check.ExeInputs:
    if not CMAIN386.is_file():
        pytest.skip(f"{CMAIN386} not found (the owner's Watcom 10.6 tree)")
    if not (ORIG_DIR / name).is_file():
        pytest.skip(f"orig/{name} not present (run uv run reverseapoc ingest)")
    requires_runner()
    requires_objdiff()
    target = check.select_exe(load_manifest(MANIFEST), name, MANIFEST)
    return check.load_exe(target, orig_dir=ORIG_DIR, manifest=MANIFEST, config_root=CONFIG)


def _row(exe: check.ExeInputs):
    (row,) = [row for row in exe.rows if row.name == SYMBOL]
    return row


def _compile(exe: check.ExeInputs, build_dir):
    """check_source on the pair, with the compiled object read back for the land step."""
    row = _row(exe)
    options = check.CompileOptions(watcom_dir=WATCOM_DIR, log=build_dir / "cc.log")
    result = check.check_source(
        exe, UNIT, CMAIN386, [row], build_dir=build_dir, compile_fn=compile_source,
        objdiff_runner=check.default_objdiff_runner(f"{exe.stem}/{UNIT}"), options=options,
        unit_file=False,  # Watcom's own file, not src/<exe>/<unit>.c: no D-12 source checks
    )  # fmt: skip
    root = check.object_root(build_dir, options)
    module = check.read_module(check.UnitPaths.of(root, exe.stem, UNIT).obj)
    return row, result, module


@pytest.mark.parametrize("name", ["UFO2P.EXE", "TACP.EXE"])
def test_cmain386_pair_matches(name, build_dir):
    exe = _exe(name)
    row, result, module = _compile(exe, build_dir)
    assert result.compiler == "wcc386@10.6"
    assert result.problems == (), [p.format() for p in result.problems]
    assert result.target.raw_fields == () and result.target.undecoded == ()
    (fn,) = result.functions
    assert (fn.name, fn.va, fn.size) == (SYMBOL, row.start, row.end - row.start)
    assert fn.objdiff_percent == check.PERFECT
    assert fn.reloc.ok, fn.reloc.problems
    assert fn.bytes_ok and fn.differing == 0
    ((d, reloc),) = check.checked_functions(module, [row], exe)
    assert reloc.ok
    landed = land(exe.le, [LandedFunction(row, d.ours, reloc)], expected_sha1=exe.target.sha1,
                  flat=exe.flat)  # fmt: skip
    assert landed.landed == (row.start,)
    assert landed.ok, landed.format()


def test_cmain386_wrong_call_target_fails(build_dir):
    exe = _exe("UFO2P.EXE")
    row, _, module = _compile(exe, build_dir)
    assert {CALLEE, PLANTED} <= set(module.externs)
    (d,) = check.defined_functions(module, [row], exe.symbols)
    (fx,) = [fx for fx in d.segment.fixups
             if fx.target_kind == "extern" and fx.target_name == CALLEE]  # fmt: skip
    planted = dataclasses.replace(d.segment, fixups=tuple(
        dataclasses.replace(f, target_name=PLANTED) if f is fx else f for f in d.segment.fixups
    ))  # fmt: skip
    kwargs = {"off": d.off, "size": d.size, "row": row, "flat": exe.flat, "fixups": exe.fixups,
              "symbols": exe.symbols}  # fmt: skip
    assert check_function(d.segment, **kwargs).ok  # the control: the unplanted object passes
    result = check_function(planted, **kwargs)
    assert not result.ok
    field = f"0x{row.start + fx.offset - d.off:08X}"
    problems = result.problems
    assert any(p.startswith(f"{field}: ") and PLANTED in p for p in problems), problems


# ---- code review WR-01: `check --cflags` never feeds ninja an object of other flags ------------

NINJA_ROOT = REPO_ROOT / "build" / "test-ninja"  # the compiler writes only inside the repository
NINJA_EXE, NINJA_UNIT = "ufo2p", "u_000a34f0"  # a committed unit with a matched function
EXPERIMENT = "*  wcc386@10.6  -4r -fpi\n"  # stack checks on: not what config/cflags.txt compiles


def _ninja(base: Path, *args: str) -> str:
    proc = subprocess.run(["ninja", "-C", str(base), *args], capture_output=True, text=True,
                          check=False, timeout=600)  # fmt: skip
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout


def test_ninja_keeps_committed_objects_after_a_custom_check(request):
    """configure + ninja build the unit's object with config/cflags.txt; `check --cflags
    experiment` then compiles a different object, but ninja's object, its mtime and ninja's
    verdict (nothing to do) are unchanged, and a further ninja run still yields the committed
    flags' object. Before WR-01 check overwrote it, ninja took it as up to date, and
    `ninja verify` landed it."""
    if shutil.which("ninja") is None:
        pytest.skip("ninja is not on PATH (run in the container)")
    for target in load_manifest(MANIFEST):
        if (CONFIG / check.exe_stem(target.name) / "units.csv").is_file() and not (
            ORIG_DIR / target.name
        ).is_file():
            pytest.skip(f"orig/{target.name} not present (run uv run reverseapoc ingest)")
    if not (DEFAULT_INSTALL / "10.6").is_dir():
        pytest.skip(f"{DEFAULT_INSTALL / '10.6'} not installed (ninja's cc edge uses it)")
    requires_runner()
    requires_objdiff()
    base = NINJA_ROOT / re.sub(r"[^A-Za-z0-9._-]", "_", request.node.name)
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    # `reverseapoc cc` refuses a source path with `..`, so the unit files are copied next to
    # this build.ninja (the same committed C; the `*` cflags rule matches any path).
    src = base / "src"
    shutil.copytree(REPO_ROOT / "src", src)
    assert configure.main(["--src", str(src), "--output", str(base / "build.ninja")]) == 0
    rel = f"{configure.BUILDDIR}/{NINJA_EXE}/obj/{NINJA_UNIT}.obj"
    _ninja(base, rel)
    obj = base / rel
    committed = (obj.read_bytes(), obj.stat().st_mtime_ns)

    experiment = base / "experiment.txt"
    experiment.write_text(EXPERIMENT, encoding="ascii")
    build_dir = base / configure.BUILDDIR
    result = check.check_unit(
        NINJA_EXE, NINJA_UNIT, orig_dir=ORIG_DIR, manifest=MANIFEST, config_root=CONFIG,
        src_root=src, build_dir=build_dir, cflags=experiment,
        log=base / "cc.log",
    )  # fmt: skip
    assert result.flags == ("-4r", "-fpi")
    assert (obj.read_bytes(), obj.stat().st_mtime_ns) == committed
    custom = check.UnitPaths.of(build_dir / check.CUSTOM_ROOT, NINJA_EXE, NINJA_UNIT).obj
    assert custom.read_bytes() != committed[0]  # the experiment really compiles another object

    assert "no work to do" in _ninja(base, "-n", rel)
    _ninja(base, rel)
    assert obj.read_bytes() == committed[0]


# ---- 07-03 (D-27 P1, research K4): a D-24 view compiles from its own root, under the unit rule --

# Inside the repository (the container mount sees it) and under build/driver/, where D-24 views
# live: only build/driver/.../view/src compiles from its view root (07-03 fix round 1).
VIEW_ROOT = REPO_ROOT / "build" / "driver" / "test-view"
VIEW_EXE, VIEW_UNIT = "ufo2p", "u_000a34f0"  # a committed unit with a matched function
UNIT_FLAG = "-ot"  # what the temporary per-unit rule adds to the `*` rule's flags


@pytest.fixture
def view() -> Iterator[Path]:
    """build/driver/test-view/<random hex>/view: a snapshot of src/, include/ and config/ as D-24's
    per-attempt view holds them; removed at teardown. Skips (orchestrator ruling F40: through
    requires_runner/requires_objdiff first) before anything is copied."""
    requires_runner()
    requires_objdiff()
    for target in load_manifest(MANIFEST):
        if (CONFIG / check.exe_stem(target.name) / "units.csv").is_file() and not (
            ORIG_DIR / target.name
        ).is_file():
            pytest.skip(f"orig/{target.name} not present (run in the container)")
    if not (WATCOM_DIR / "10.6").is_dir():
        pytest.skip(f"{WATCOM_DIR / '10.6'} not installed (run in the container)")
    top = VIEW_ROOT / secrets.token_hex(4)
    path = top / "view"
    for tree in ("src", "include", "config"):
        shutil.copytree(REPO_ROOT / tree, path / tree)
    yield path
    shutil.rmtree(top, ignore_errors=True)


def test_view_unit_compiles_under_its_logical_rule(view):
    """A copy of the unit inside a view, checked with the view's src/config/build and a
    temporary cflags file that gives src/ufo2p/u_000a34f0.c the `*` rule's compiler and flags
    plus -ot: the unit's object is compiled from the view root under that rule (its stamp records
    -ot) into the view's build/check-custom/, and each unit the land step compiles keeps its
    committed rule. It does not assert a match: the evidence is which rule and which root the
    compile used."""
    rule_path = check.unit_rule_path(VIEW_EXE, VIEW_UNIT)
    star = next(rule for rule in load_cflags() if rule.glob == "*")
    cflags = view / "unit-rule.cflags"
    committed = (REPO_ROOT / "config" / "cflags.txt").read_text(encoding="utf-8")
    cflags.write_text(f"{committed.rstrip()}\n{rule_path}  {star.spec}  "
                      f"{' '.join((*star.flags, UNIT_FLAG))}\n", encoding="utf-8")  # fmt: skip
    build = view / "build"
    result = check.check_unit(
        VIEW_EXE, VIEW_UNIT, orig_dir=ORIG_DIR, manifest=view / "config" / "targets.toml",
        config_root=view / "config", src_root=view / "src", build_dir=build, cflags=cflags,
        watcom_dir=WATCOM_DIR, log=build / "cc.log",
    )  # fmt: skip
    assert result.flags == (*star.flags, UNIT_FLAG)
    custom = build / check.CUSTOM_ROOT
    obj = check.UnitPaths.of(custom, VIEW_EXE, VIEW_UNIT).obj
    assert obj.is_file()
    # The compile ran from the view root: the guest object path in the log is view-relative.
    assert check._compile_root_for(view / "src") == view.resolve()
    guest_obj = obj.resolve().relative_to(view.resolve()).as_posix().replace("/", "\\")
    log = (build / "cc.log").read_text(encoding="utf-8")
    assert f"-fo={guest_obj}" in log, log
    stamp = read_provenance(obj)
    assert stamp is not None and UNIT_FLAG in stamp["flags"], stamp
    others = [path for path in (custom / VIEW_EXE / "obj").glob("*.obj") if path != obj]
    assert others  # the land step compiled the other units of the view too
    for other in others:
        committed_rule = select_rule(load_cflags(), check.unit_rule_path(VIEW_EXE, other.stem))
        assert read_provenance(other)["flags"] == list(committed_rule.flags), other
