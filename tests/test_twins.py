"""twins and cd-map: the relocation-masked body matcher, the twin transfer through the real gate
(check, relocation check and land; only the compiler, objdiff and the container are faked), and the
installed-to-CD function map. Every byte, name and address is made up (tests/relocpair.py)."""

from __future__ import annotations

import functools
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import write_manifest
from omfimage import extdef, fixupp32, grpdef, ledata32, lnames, module, pubdef32, segdef32
from relocpair import FLAT_LNAME, absolute, call, le_off32, original
from reverseapoc import check, driver, gate, twins
from reverseapoc.cflags import Rule
from reverseapoc.cli import main as cli_main
from reverseapoc.functions import (
    FunctionRow,
    SymbolRow,
    UnitRow,
    write_functions_csv,
    write_symbols_csv,
    write_units_csv,
)
from reverseapoc.le import LE
from reverseapoc.status import MATCHED, StatusRow, lf_sha256, read_status, status_path, write_status

UFO, TACP = "UFO2P.EXE", "TACP.EXE"
A_START, B_START = 0x10000, 0x10040  # the twin in each EXE
A_CALLEE, B_CALLEE = 0x10010, 0x10060
# call <callee>; mov eax, [D_...]; ret: the rel32 and the off32 field differ, the masked body not
A_BODY = bytes.fromhex("e80b000000" "a104000000" "c3")  # call 0x10010, [0x20004]
B_BODY = bytes.fromhex("e81b000000" "a108000000" "c3")  # call 0x10060, [0x20008]
OURS = bytes.fromhex("e800000000" "a100000000" "c3")  # what our compiler emits
LOAD_AT = 6  # the off32 field's offset in the body
A_UNIT, B_UNIT = "u_00010000", "u_00010040"
A_SOURCE = """#include "common.h"

extern int D_00020004;
int func_00010010(void);
extern int D_00020300; /* not used by the twin */

int func_00010000(void)
{
    func_00010010();
    return D_00020004;
}

INCLUDE_ASM(func_00010010);
INCLUDE_ASM(func_00010020);
"""
B_SOURCE = """#include "common.h"

INCLUDE_ASM(func_00010040);
INCLUDE_ASM(func_00010060);
"""
RULE = Rule("*", "wcc386", "10.6", ("-4r", "-s", "-fpi"), 1)


def fname(start: int) -> str:
    return f"func_{start:08X}"


def image_a() -> bytes:
    return original({A_START: A_BODY}, page1=le_off32(A_START + LOAD_AT, 0x4)).data


def image_b() -> bytes:
    return original({B_START: B_BODY}, page1=le_off32(B_START + LOAD_AT, 0x8)).data


def code_of(data: bytes) -> twins.Code:
    return twins.Code.of(LE(data))


# ---- the masked body ----------------------------------------------------------------------------


def test_masked_body_hides_fixups_and_outgoing_rel32():
    a = twins.masked(code_of(image_a()), A_START, len(A_BODY))
    b = twins.masked(code_of(image_b()), B_START, len(B_BODY))
    assert a == b
    body, mask = a
    assert mask == (1, 2, 3, 4, 6, 7, 8, 9)
    assert body == OURS


def test_masked_body_keeps_other_bytes():
    other = original({B_START: B_BODY[:-1] + b"\xcc"}, page1=le_off32(B_START + LOAD_AT, 0x8))
    assert twins.masked(code_of(image_a()), A_START, len(A_BODY)) != twins.masked(
        code_of(other.data), B_START, len(B_BODY))


def test_masked_body_keeps_a_branch_inside_the_span():
    loop = bytes.fromhex("e9fbffffff")  # jmp to itself: rel32 inside the span
    code = code_of(original({A_START: loop}).data)
    assert twins.masked(code, A_START, len(loop)) == (loop, ())


def test_masked_body_refuses_a_span_outside_the_code_object():
    with pytest.raises(twins.TwinsError, match="outside the code object"):
        twins.masked(code_of(image_a()), 0x20000, 4)


# ---- the tree: two EXEs, a matched function in one and its unmatched twin in the other ---------


def omf_for(source: str) -> bytes:
    """A stand-in compiler: the object the C of a unit file asks for. Each `int func_X(void)`
    definition becomes OURS, calling the first func_ the body calls and loading the first D_ it
    reads; a unit that defines nothing gets an empty `_TEXT`."""
    found = re.search(r"int (func_[0-9A-F]{8})\(void\)\s*\{([^}]*)\}", source)
    head = (lnames("", "_TEXT", "CODE", FLAT_LNAME), grpdef(4))
    if found is None:
        return module("unit", head[0], segdef32(2, 3, 0), head[1])
    public, body = found.groups()
    callee = re.search(r"(func_[0-9A-F]{8})\(\)", body).group(1)
    data = re.search(r"D_[0-9A-F]{8}", body).group(0)
    return module("unit", head[0], segdef32(2, 3, len(OURS)), head[1],
                  pubdef32(1, [(public + "_", 0)]), extdef(callee + "_", "_" + data),
                  ledata32(1, 0, OURS), fixupp32(call(1, 1), absolute(LOAD_AT, 2)))  # fmt: skip


def fake_compile(src, obj, **kwargs):
    obj = Path(obj)
    obj.parent.mkdir(parents=True, exist_ok=True)
    obj.write_bytes(omf_for(Path(src).read_text(encoding="utf-8")))
    return SimpleNamespace(ok=True, rule=RULE, output="", returncode=0,
                           format=lambda: f"OK  {src}")  # fmt: skip


def fake_objdiff(argv):
    symbol = argv[-1]
    return json.dumps({"left": {"symbols": [{"name": symbol, "match_percent": 100.0}]},
                       "right": {"symbols": []}})  # fmt: skip


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout


@pytest.fixture
def repo(tmp_path, monkeypatch) -> Path:
    """A git checkout with orig/, the manifest, config/ and src/ of both synthetic EXEs, standing
    in for the committed trees (as tests/test_gate.py's as_committed does)."""
    root = tmp_path / "repo"
    images = {UFO: image_a(), TACP: image_b()}
    (root / "orig").mkdir(parents=True)
    (root / "config").mkdir()
    for name, data in images.items():
        (root / "orig" / name).write_bytes(data)
    write_manifest(root / "config" / "targets.toml", images)
    spans = {UFO: [(A_START, len(A_BODY)), (A_CALLEE, 8), (0x10020, 7)],
             TACP: [(B_START, len(B_BODY)), (B_CALLEE, 6)]}
    unit_of = {UFO: A_UNIT, TACP: B_UNIT}
    rows = {name: [FunctionRow(s, s + n, fname(s), "game", unit_of[name], "call") for s, n in rows]
            for name, rows in spans.items()}  # fmt: skip
    units = {UFO: [UnitRow(A_UNIT, 0x10000, 0x10030, "first")],
             TACP: [UnitRow(B_UNIT, 0x10040, 0x10070, "first")]}  # fmt: skip
    for name in images:
        stem = name.split(".")[0].lower()
        write_functions_csv(root / "config" / stem / "functions.csv", rows[name], name)
        write_units_csv(root / "config" / stem / "units.csv", units[name], name)
    for stem, unit, text in (("ufo2p", A_UNIT, A_SOURCE), ("tacp", B_UNIT, B_SOURCE)):
        (root / "src" / stem).mkdir(parents=True)
        (root / "src" / stem / f"{unit}.c").write_text(text, encoding="utf-8", newline="\n")
    write_status(status_path(root / "config", "ufo2p"),
                 [StatusRow(A_START, fname(A_START), A_UNIT, MATCHED, 100.0, 1,
                            lf_sha256(A_SOURCE), "2026-11-01")])  # fmt: skip
    write_status(status_path(root / "config", "tacp"), [])
    monkeypatch.setattr(check, "DEFAULT_SRC", root / "src")
    monkeypatch.setattr(check, "DEFAULT_CONFIG", root / "config")
    check._configure()
    monkeypatch.setattr(check, "REPO_ROOT", root)
    for key, value in (("GIT_AUTHOR_NAME", "t"), ("GIT_AUTHOR_EMAIL", "t@example.invalid"),
                       ("GIT_COMMITTER_NAME", "t"), ("GIT_COMMITTER_EMAIL", "t@example.invalid")):
        monkeypatch.setenv(key, value)
    (root / ".gitignore").write_text("build/\n", encoding="utf-8")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def roots(repo: Path) -> gate.GateRoots:
    return gate.GateRoots(orig_dir=repo / "orig", manifest=repo / "config" / "targets.toml",
                          config_root=repo / "config", src_root=repo / "src",
                          build_dir=repo / "build")  # fmt: skip


class Container:
    """Stands in for `docker compose run ... reverseapoc lint|gate`: lint passes, gate runs the
    real gate_units in-process, with check_unit's compiler and objdiff faked."""

    def __init__(self, repo: Path, compile_fn=fake_compile) -> None:
        self.repo, self.compile_fn = repo, compile_fn
        self.argvs: list[list[str]] = []

    def __call__(self, argv, env=None):
        argv = list(argv)
        self.argvs.append(argv)
        verb = argv[len(driver.CONTAINER_CLI)]
        if verb == "lint":
            return subprocess.CompletedProcess(argv, 0, "", "")
        assert verb == "gate"
        exe, unit = argv[len(driver.CONTAINER_CLI) + 1].split("/")
        check_fn = functools.partial(check.check_unit, compile_fn=self.compile_fn,
                                     objdiff_runner=fake_objdiff)  # fmt: skip
        result = gate.gate_units([(exe, unit)], roots=roots(self.repo), attempts=0,
                                 check_fn=check_fn)  # fmt: skip
        return subprocess.CompletedProcess(argv, result.exit_code, json.dumps(result.to_json()),
                                           result.format())  # fmt: skip


def plan(repo: Path) -> twins.TwinsPlan:
    return twins.plan_twins(repo=repo, orig_dir=repo / "orig",
                            manifest=repo / "config" / "targets.toml")  # fmt: skip


def test_plan_counts_and_finds_the_transfer(repo):
    p = plan(repo)
    assert [(c.exe, c.rows, c.groups, c.grouped) for c in p.counts] == [(UFO, 3, 0, 0),
                                                                         (TACP, 2, 0, 0)]
    assert (p.cross_bodies, p.cross_rows) == (1, {UFO: 1, TACP: 1})
    (t,) = p.transfers
    assert (t.source.exe, t.source.row.start, t.target.exe, t.target.row.start) == (
        UFO, A_START, TACP, B_START)
    assert t.reason == ""
    assert t.renames == {"func_00010000": "func_00010040", "func_00010010": "func_00010060",
                         "D_00020004": "D_00020008"}  # fmt: skip
    assert t.candidate == """#include "common.h"

extern int D_00020008;
int func_00010060(void);

int func_00010040(void)
{
    func_00010060();
    return D_00020008;
}
INCLUDE_ASM(func_00010060);
"""


def test_dry_run_writes_nothing(repo, capsys):
    argv = ["twins", "--dry-run", "--repo", str(repo), "--orig", str(repo / "orig"),
            "--manifest", str(repo / "config" / "targets.toml")]  # fmt: skip
    assert cli_main(argv) == 0
    out = capsys.readouterr().out
    assert "across the EXEs: 1 bodies (UFO2P.EXE 1 rows, TACP.EXE 1 rows)" in out
    assert "1 unmatched rows have a matched twin: 1 candidates, 0 skipped" in out
    assert "candidate TACP.EXE func_00010040 (u_00010040) <- UFO2P.EXE func_00010000" in out
    assert git(repo, "status", "--porcelain") == ""


def land(repo: Path, container: Container) -> twins.LandReport:
    return twins.land_twins(repo=repo, orig_dir=repo / "orig",
                            manifest=repo / "config" / "targets.toml", runner=container,
                            git=driver.git_runner(repo), env={})  # fmt: skip


def test_a_twin_lands_through_the_gate(repo):
    container = Container(repo)
    report = land(repo, container)

    assert report.landed == ((TACP, fname(B_START)),) and report.failed == ()
    (row,) = read_status(status_path(repo / "config", "tacp"))
    assert (row.start, row.status, row.unit, row.attempts) == (B_START, MATCHED, B_UNIT, 0)
    unit = repo / "src" / "tacp" / f"{B_UNIT}.c"
    assert row.source_sha256 == lf_sha256(unit.read_text(encoding="utf-8"))
    gates = [a for a in container.argvs if a[len(driver.CONTAINER_CLI)] == "gate"]
    assert gates == [[*driver.CONTAINER_CLI, "gate", f"tacp/{B_UNIT}", "--attempts", "0",
                      "--json"]]  # fmt: skip
    message = git(repo, "log", "-1", "--format=%B")
    assert message.startswith(f"feat(tacp): match {fname(B_START)} in {B_UNIT} as a twin of "
                              f"ufo2p {fname(A_START)} (C89)\n")  # fmt: skip
    assert message.rstrip().endswith("Matched-By: reverseapoc twins")
    committed = git(repo, "show", "--name-only", "--format=", "HEAD").split()
    assert sorted(committed) == ["config/tacp/status.csv", "decomphub.progress.json",
                                 f"src/tacp/{B_UNIT}.c"]  # fmt: skip
    assert git(repo, "status", "--porcelain") == ""


def test_a_failing_gate_restores_every_file(repo):
    def wrong_compile(src, obj, **kwargs):  # the C calls another callee: the reloc check fails
        done = fake_compile(src, obj, **kwargs)
        text = Path(src).read_text(encoding="utf-8")
        if "func_00010040(void)" in text:
            Path(obj).write_bytes(omf_for(text.replace("func_00010060();", "func_00010040();")))
        return done

    before = (repo / "src" / "tacp" / f"{B_UNIT}.c").read_bytes()
    head = git(repo, "rev-parse", "HEAD")
    report = land(repo, Container(repo, wrong_compile))

    assert report.landed == ()
    ((exe, name, why),) = report.failed
    assert (exe, name) == (TACP, fname(B_START)) and why.startswith("gate exit 1")
    assert (repo / "src" / "tacp" / f"{B_UNIT}.c").read_bytes() == before
    assert read_status(status_path(repo / "config", "tacp")) == []
    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "status", "--porcelain") == ""


def test_a_dirty_unit_fails_its_transfer_and_is_left_alone(repo):
    unit = repo / "src" / "tacp" / f"{B_UNIT}.c"
    unit.write_text(B_SOURCE + "\n", encoding="utf-8", newline="\n")
    container = Container(repo)
    report = land(repo, container)
    ((exe, name, why),) = report.failed
    assert (exe, name) == (TACP, fname(B_START)) and why.startswith("uncommitted changes in ")
    assert unit.read_text(encoding="utf-8") == B_SOURCE + "\n"
    assert container.argvs == []
    assert "0 twins landed, 1 failed" in report.format()


def items_text(source: str) -> list[tuple[str, str]]:
    return [(item.kind, item.text) for item in twins._items(source)]


def test_a_continued_define_is_one_item():
    source = "#define SWAP(a, b) \\\n    { int t = a; a = b; b = t; }\nextern int g_x;\n"
    assert items_text(source) == [
        ("define", "#define SWAP(a, b) \\\n    { int t = a; a = b; b = t; }"),
        ("decl", "extern int g_x;")]


def test_dead_code_and_conditionals_are_never_items():
    source = "#if 0\nextern int g_dead;\n#endif\n#undef X\nextern int g_live;\n"
    assert items_text(source) == [("directive", "#undef X"), ("decl", "extern int g_live;")]
    needed = twins._needed(twins._items(source), "int f(void) { return g_live; }", "f")
    assert [i.text for i in needed] == ["extern int g_live;"]


def test_a_rename_leaves_string_literals_alone():
    text = 'x = D_00020004; puts("D_00020004"); /* D_00020004 */'
    assert twins._rename(text, {"D_00020004": "D_00020008"}) == (
        'x = D_00020008; puts("D_00020004"); /* D_00020008 */')


def test_a_name_the_body_does_not_use_never_borrows_a_pair(repo):
    """D_00020000 shares a declaration with a used name: it is not renamed, and it does not
    take the D_00020004 field as `the data it points into`."""
    text = A_SOURCE.replace("extern int D_00020004;", "extern int D_00020000, D_00020004;")
    (repo / "src" / "ufo2p" / f"{A_UNIT}.c").write_text(text, encoding="utf-8", newline="\n")
    (t,) = plan(repo).transfers
    assert t.reason == "" and "D_00020000" not in t.renames
    assert t.renames["D_00020004"] == "D_00020008"


def test_sources_are_tried_in_order():
    calls = []

    def attempt(source, target):
        calls.append(source)
        return twins.Transfer(source, target, "no C" if source == "a" else "")

    assert twins._first_candidate(["a", "b", "c"], "t", attempt).source == "b"
    assert calls == ["a", "b"]
    assert twins._first_candidate(["a"], "t", attempt).reason == "no C"


def test_cd_map_never_maps_two_rows_to_one_cd_start():
    stub = bytes.fromhex("b878563412" "c3")
    installed = original({0x10100: stub, 0x10200: stub})
    cd = original({0x10180: stub})
    rows = [FunctionRow(0x10100, 0x10106, fname(0x10100), "game", "u", "call"),
            FunctionRow(0x10200, 0x10206, fname(0x10200), "game", "u", "call")]
    mapped = twins.cd_map(rows, twins.Code.of(installed.le), twins.Code.of(cd.le))
    assert [(m.cd_start, m.status) for m in mapped] == [(0x10180, "moved"), (None, "unmapped")]


def test_landing_refuses_a_matching_session(repo):
    with pytest.raises(twins.TwinsError, match="REVERSEAPOC_CLAIM"):
        twins.land_twins(repo=repo, orig_dir=repo / "orig",
                         manifest=repo / "config" / "targets.toml", runner=Container(repo),
                         git=driver.git_runner(repo), env={"REVERSEAPOC_CLAIM": "x"})  # fmt: skip


@pytest.mark.parametrize("before", [True, False])
def test_a_declaration_the_target_has_above_the_marker_is_not_repeated(repo, before):
    extern = "extern int D_00020008;\n"
    marker = "INCLUDE_ASM(func_00010040);\n"
    text = B_SOURCE.replace(marker, extern + marker if before else marker + extern)
    (repo / "src" / "tacp" / f"{B_UNIT}.c").write_text(text, encoding="utf-8", newline="\n")
    (t,) = plan(repo).transfers
    assert t.candidate.count(extern) == (1 if before else 2)
    assert t.candidate.index(extern) < t.candidate.index("int func_00010040(void)")


def test_an_unused_name_is_never_renamed(repo):
    (t,) = plan(repo).transfers
    assert "D_00020300" not in t.renames and "D_00020300" not in t.candidate


def test_a_renamed_source_transfers_under_the_target_name(repo):
    write_symbols_csv(repo / "config" / "ufo2p" / "symbols.csv",
                      [SymbolRow(A_START, "read_slot_", "func")], UFO)
    unit = repo / "src" / "ufo2p" / f"{A_UNIT}.c"
    unit.write_text(A_SOURCE.replace("func_00010000", "read_slot"), encoding="utf-8")
    (t,) = plan(repo).transfers
    assert t.reason == ""
    assert t.renames["read_slot"] == "func_00010040"
    assert "int func_00010040(void)\n{" in t.candidate and "read_slot" not in t.candidate


def test_a_renamed_target_is_defined_under_its_new_name(repo):
    write_symbols_csv(repo / "config" / "tacp" / "symbols.csv",
                      [SymbolRow(B_START, "twin_copy_", "func")], TACP)
    (t,) = plan(repo).transfers
    assert t.renames["func_00010000"] == "twin_copy"
    assert "int twin_copy(void)\n{" in t.candidate
    assert "INCLUDE_ASM(func_00010040)" not in t.candidate


def test_a_twin_whose_call_lands_mid_function_is_skipped(repo):
    rows = repo / "config" / "tacp" / "functions.csv"
    rows.write_text(rows.read_text(encoding="utf-8").replace("0x00010060,0x00010066",
                                                             "0x00010058,0x00010066"))
    rows.write_text(rows.read_text(encoding="utf-8").replace("func_00010060", "func_00010058"))
    (t,) = plan(repo).transfers
    assert t.reason == ("func_00010010 pairs with 0x00010060, which the target EXE names no "
                        "func")  # fmt: skip


# ---- cd-map: the installed build against the CD build -------------------------------------------


CD_BODY = bytes.fromhex("535152") + A_BODY  # push ebx; push ecx; push edx: a 4-byte anchor
CD_LOAD = 3 + LOAD_AT
UNIQUE = bytes.fromhex("b878563412" "c3")  # mov eax, 0x12345678; ret


def test_cd_map_finds_identical_moved_and_unmapped():
    installed = original({A_START: CD_BODY, 0x10100: bytes.fromhex("31c0" "40" "c3"),
                          0x10200: UNIQUE}, page1=le_off32(A_START + CD_LOAD, 0x4))  # fmt: skip
    cd = original({A_START + 0x20: CD_BODY, 0x10100: bytes.fromhex("31c0" "48" "c3"),
                   0x10200: UNIQUE}, page1=le_off32(A_START + 0x20 + CD_LOAD, 0x10))  # fmt: skip
    rows = [FunctionRow(A_START, A_START + len(CD_BODY), fname(A_START), "game", "u", "call"),
            FunctionRow(0x10100, 0x10104, fname(0x10100), "game", "u", "call"),
            FunctionRow(0x10200, 0x10206, fname(0x10200), "game", "u", "call")]
    mapped = twins.cd_map(rows, twins.Code.of(installed.le), twins.Code.of(cd.le))
    assert [(m.row.start, m.cd_start, m.status) for m in mapped] == [
        (A_START, A_START + 0x20, "moved"), (0x10100, None, "unmapped"),
        (0x10200, 0x10200, "identical")]


def test_cd_map_csv_has_the_coverage_line():
    rows = [FunctionRow(0x10000, 0x10010, fname(0x10000), "game", "u", "call"),
            FunctionRow(0x10010, 0x10020, fname(0x10010), "runtime", "u", "runtime")]
    mapped = [twins.CdMapRow(rows[0], 0x10000, "identical"), twins.CdMapRow(rows[1], None,
                                                                             "unmapped")]
    text = twins.format_cd_map(mapped, UFO)
    assert text.splitlines() == [
        "# generated by: uv run reverseapoc cd-map UFO2P.EXE --write; do not edit",
        "# coverage: 1 identical (16 bytes), 0 moved (0 bytes), 1 unmapped (16 bytes) of 2 rows",
        "start,end,name,kind,cd_start,status",
        "0x00010000,0x00010010,func_00010000,game,0x00010000,identical",
        "0x00010010,0x00010020,func_00010010,runtime,,unmapped",
    ]


def add_cd_build(repo: Path, name: str, data: bytes) -> None:
    """A [[cd_builds]] entry for `data` appended to the tree's manifest."""
    manifest = repo / "config" / "targets.toml"
    single = write_manifest(repo / "cd.toml", {name: data}).read_text(encoding="utf-8")
    entry = single.replace("[[targets]]", "[[cd_builds]]")
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n" + entry, encoding="utf-8")


def cd_map_argv(repo: Path, *extra: str) -> list[str]:
    return ["cd-map", "ufo2p", "--orig", str(repo / "orig"), "--manifest",
            str(repo / "config" / "targets.toml"), "--config", str(repo / "config"),
            "--cd", str(repo / "cd"), *extra]  # fmt: skip


def test_cd_map_cli_writes_the_map(repo, capsys):
    add_cd_build(repo, UFO, image_b())
    (repo / "cd").mkdir()
    (repo / "cd" / UFO).write_bytes(image_b())
    assert cli_main(cd_map_argv(repo, "--write")) == 0
    out = capsys.readouterr().out
    # the twin body has no 4-byte unmasked run to search for away from its own address
    assert "UFO2P.EXE: 2 identical (15 bytes), 0 moved (0 bytes), 1 unmapped (11 bytes)" in out
    lines = (repo / "config" / "ufo2p" / "cd-map.csv").read_text(encoding="utf-8").splitlines()
    assert lines[3:] == ["0x00010000,0x0001000B,func_00010000,game,,unmapped",
                         "0x00010010,0x00010018,func_00010010,game,0x00010010,identical",
                         "0x00010020,0x00010027,func_00010020,game,0x00010020,identical"]


def test_cd_map_refuses_a_cd_build_that_is_not_the_manifest_one(repo, capsys):
    add_cd_build(repo, UFO, image_b())
    (repo / "cd").mkdir()
    (repo / "cd" / UFO).write_bytes(image_a())
    assert cli_main(cd_map_argv(repo)) == 1
    assert re.search(r"is not the CD build: .*sha1: expected", capsys.readouterr().err)


def test_cd_map_names_the_ingest_step_when_the_cd_build_is_missing(repo, capsys):
    add_cd_build(repo, UFO, image_b())
    assert cli_main(cd_map_argv(repo)) == 1
    assert "ingest --cd IMAGE" in capsys.readouterr().err


def test_twins_and_cd_map_write_refuse_while_a_drive_holds_the_lock(repo, capsys):
    from reverseapoc.locks import DRIVE_LOCK, ProcessLock

    add_cd_build(repo, UFO, image_b())
    (repo / "cd").mkdir()
    (repo / "cd" / UFO).write_bytes(image_b())
    other = ProcessLock(repo / DRIVE_LOCK)
    assert other.try_acquire()
    try:
        with pytest.raises(Exception, match="drive"):
            land(repo, Container(repo))
        assert cli_main(cd_map_argv(repo, "--write")) == 1
        assert "drive" in capsys.readouterr().err
        assert not (repo / "config" / "ufo2p" / "cd-map.csv").exists()
        assert cli_main(cd_map_argv(repo)) == 0  # without --write it only reads
    finally:
        other.release()
