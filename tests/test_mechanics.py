"""config/mechanics.toml and the generated config/mechanics-members.csv (DEC-01, D-01, D-02, D-04,
D-22, D-23, D-31): the strict loader, the members generator over hand-made call graphs, roles,
tier digests, the committed-data check and the `mechanics` verb. No game files: every graph here
is built by hand from made-up addresses."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from reverseapoc import cli, mechanics
from reverseapoc.callgraph import DIRECT, CallGraph, Edge
from reverseapoc.functions import FunctionRow, format_functions_csv
from reverseapoc.mechanics import (
    MEMBERS_COLUMNS,
    MEMBERS_COMMENT,
    MechanicsError,
    MemberRow,
    compute_members,
    format_members_csv,
    load,
    read_members,
    write_members,
)

E, A, B, C, D, F, G, H, X, Y = (0x00010000 + 0x100 * i for i in range(10))
RUNTIME = 0x000C0000


# ---- TOML text for the tests (tomllib only reads) ----


def _value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_value(v) for v in value) + "]"
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def toml_text(top: dict | None = None, **tables) -> str:
    """`top` holds top-level keys and single tables (dict values); every keyword is an array of
    tables, e.g. item=[{...}, {...}]."""
    top = {"schema": 1} if top is None else top
    lines = [f"{k} = {_value(v)}" for k, v in top.items() if not isinstance(v, dict)]
    for name, body in ((k, v) for k, v in top.items() if isinstance(v, dict)):
        lines += ["", f"[{name}]"] + [f"{k} = {_value(v)}" for k, v in body.items()]
    for name, entries in tables.items():
        for body in entries:
            lines += ["", f"[[{name}]]"] + [f"{k} = {_value(v)}" for k, v in body.items()]
    return "\n".join(lines) + "\n"


def tier(id_=1, **extra) -> dict:
    return {"id": id_, "title": f"Tier {id_}", **extra}


def item(id_="997", tier_=1, scope="in", exes=("ufo2p",), **extra) -> dict:
    issue = int(id_.split("-")[0])
    body = {"id": id_, "issue": issue, "title": f"Item {id_}",
            "url": f"https://github.com/OpenApoc/OpenApoc/issues/{issue}", "tier": tier_,
            "scope": scope}  # fmt: skip
    if exes is not None:
        body["exes"] = list(exes)
    return {**body, **extra}


def entry(item_="997", address=E, exe="ufo2p", **extra) -> dict:
    return {"item": item_, "exe": exe, "address": f"0x{address:08X}", "evidence": "bios-tick",
            "detail": "reads the tick", "source": "spike 007", **extra}  # fmt: skip


def minimal_tables() -> dict:
    return {"tier": [tier()], "item": [item()], "entry": [entry()]}


def write_toml(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "mechanics.toml"
    path.write_text(text, encoding="utf-8")
    return path


def graph(*edges: tuple[int, int], nodes=()) -> CallGraph:
    """A CallGraph with direct edges `src -> dst`; every named node gets an entry."""
    found: dict[int, list[Edge]] = {n: [] for n in nodes}
    for src, dst in edges:
        found.setdefault(src, []).append(Edge(src, dst, DIRECT))
        found.setdefault(dst, [])
    return CallGraph(edges={s: tuple(sorted(es)) for s, es in sorted(found.items())})


def game_rows(*starts: int, runtime=(RUNTIME,)) -> list[FunctionRow]:
    rows = [FunctionRow(s, s + 0x10, f"func_{s:08X}", "game", "u_main", "call") for s in starts]
    rows += [FunctionRow(s, s + 0x10, "rt_", "runtime", "", "runtime") for s in runtime]
    return sorted(rows, key=lambda r: r.start)


ALL = (E, A, B, C, D, F, G, H, X, Y)


# ---- Task 1: loader, members from one entry, the write verb ----


def test_load_minimal(tmp_path):
    mech = load(write_toml(tmp_path, toml_text(**minimal_tables())))
    assert mech.schema == 1
    assert [t.id for t in mech.tiers] == [1]
    items = [(i.id, i.issue, i.scope, i.exes) for i in mech.items]
    assert items == [("997", 997, "in", ("ufo2p",))]
    assert [(e.item, e.exe, e.address, e.evidence) for e in mech.entries] == [
        ("997", "ufo2p", E, "bios-tick")
    ]
    with pytest.raises(AttributeError):
        mech.items[0].scope = "out"  # frozen


def _refusal_cases():
    t = minimal_tables()
    yield "unknown key", {**t, "item": [item(colour="red")]}, ("item", "colour")
    yield "unknown scope", {**t, "item": [item(scope="maybe")]}, ("item", "scope")
    yield "out without reason", {**t, "item": [item(), item("263-19", scope="out")]}, (
        "item", "reason")  # fmt: skip
    yield "duplicate of out", {**t, "item": [
        item(), item("263-19", scope="out", reason="tooling"),
        item("263-21", scope="duplicate", duplicate_of="263-19")]}, ("item", "duplicate_of")
    yield "entry on out item", {**t, "item": [item(), item("263-19", scope="out",
                                                             reason="tooling")],
                                "entry": [entry(), entry("263-19")]}, ("entry", "item")  # fmt: skip
    yield "entry exe not listed", {**t, "entry": [entry(exe="tacp")]}, ("entry", "exe")
    yield "bad address", {**t, "entry": [{**entry(), "address": "0x10000"}]}, ("entry", "address")
    yield "lower-case address", {**t, "entry": [{**entry(), "address": "0x0001000a"}]}, (
        "entry", "address")  # fmt: skip
    yield "bad evidence", {**t, "entry": [entry(evidence="vibes")]}, ("entry", "evidence")
    yield "non-ASCII title", {**t, "item": [item(title="Ticks é")]}, ("item", "title")
    yield "overlong detail", {**t, "entry": [entry(detail="x" * 500)]}, ("entry", "detail")
    yield "hex run", {**t, "entry": [entry(detail="ab" * 40)]}, ("entry", "detail")
    yield "partial sign-off", {**t, "tier": [tier(signed_off_by="owner")]}, (
        "tier", "signed_off")  # fmt: skip
    yield "wrong type", {**t, "item": [item(issue="997")]}, ("item", "issue")
    yield "unknown tier", {**t, "item": [item(tier_=9)]}, ("item", "tier")
    yield "unknown top-level", {"schema": 1, "colour": "red"}, ("colour",)


@pytest.mark.parametrize(("case", "tables", "words"),
                         [pytest.param(*c, id=c[0]) for c in _refusal_cases()])  # fmt: skip
def test_load_refusals(tmp_path, case, tables, words):
    tables = dict(tables)
    top = {"schema": 1}
    if "colour" in tables:
        top = {"schema": 1, "colour": tables.pop("colour")}
        tables.pop("schema", None)
    path = write_toml(tmp_path, toml_text(top, **tables))
    with pytest.raises(MechanicsError) as exc:
        load(path)
    for word in words:
        assert word in str(exc.value), (case, str(exc.value))


def test_load_refuses_bad_toml_and_schema(tmp_path):
    with pytest.raises(MechanicsError, match="mechanics.toml"):
        load(write_toml(tmp_path, "schema = \n"))
    with pytest.raises(MechanicsError, match="schema"):
        load(write_toml(tmp_path, "schema = 2\n"))


def test_members_from_one_entry():
    mech = mechanics.Mechanics(
        tiers=(mechanics.Tier(1, "Tier 1"),),
        items=(mechanics.Item("997", 997, "Item 997", "", 1, "in", exes=("ufo2p",)),),
        entries=(mechanics.Entry("997", "ufo2p", E, "bios-tick", "reads the tick"),),
    )
    rows = compute_members(mech, {"ufo2p": graph((E, A), (A, B), (A, RUNTIME))},
                           {"ufo2p": game_rows(E, A, B)})  # fmt: skip
    assert rows == [
        MemberRow("ufo2p", E, ("997",), (1,), ("997",), "entry", "member"),
        MemberRow("ufo2p", A, ("997",), (1,), ("997",), "direct", "member"),
        MemberRow("ufo2p", B, ("997",), (1,), ("997",), "direct", "member"),
    ]
    text = format_members_csv(rows)
    assert text.splitlines()[0] == MEMBERS_COMMENT
    assert text.splitlines()[1] == ",".join(MEMBERS_COLUMNS)
    assert text.splitlines()[2:] == [
        "ufo2p,0x00010000,997,1,997,entry,member",
        "ufo2p,0x00010100,997,1,997,direct,member",
        "ufo2p,0x00010200,997,1,997,direct,member",
    ]


def test_members_written_atomically_and_deterministically(tmp_path):
    rows = [MemberRow("tacp", A, ("997",), (1,), ("997",), "entry", "member"),
            MemberRow("ufo2p", B, ("997",), (1,), ("997",), "direct", "member"),
            MemberRow("ufo2p", E, ("997",), (1,), ("997",), "entry", "member")]  # fmt: skip
    out = tmp_path / "m.csv"
    write_members(out, rows)
    first = out.read_bytes()
    write_members(out, list(reversed(rows)))
    assert out.read_bytes() == first
    assert b"\r" not in first
    assert first.decode().splitlines()[2].startswith("ufo2p,0x00010000")  # ufo2p before tacp
    assert first.decode().splitlines()[-1].startswith("tacp,")
    assert read_members(out) == sorted(rows, key=lambda r: (r.exe != "ufo2p", r.address))
    assert [p.name for p in tmp_path.iterdir()] == ["m.csv"]  # no temporary file left


def _config(tmp_path: Path, text: str, rows=None) -> Path:
    root = tmp_path / "config"
    (root / "ufo2p").mkdir(parents=True)
    (root / "mechanics.toml").write_text(text, encoding="utf-8")
    funcs = format_functions_csv(rows if rows is not None else game_rows(E, A, B), "UFO2P.EXE")
    (root / "ufo2p" / "functions.csv").write_text(funcs, encoding="utf-8")
    return root


def test_cli_write_with_injected_graphs(tmp_path, monkeypatch):
    root = _config(tmp_path, toml_text(**minimal_tables()))
    monkeypatch.setattr(mechanics, "load_graphs",
                        lambda *a, **k: {"ufo2p": graph((E, A), (A, B))})  # fmt: skip
    assert cli.main(["mechanics", "write", "--config", str(root)]) == 0
    lines = (root / "mechanics-members.csv").read_text(encoding="utf-8").splitlines()
    assert lines[2:] == ["ufo2p,0x00010000,997,1,997,entry,member",
                         "ufo2p,0x00010100,997,1,997,direct,member",
                         "ufo2p,0x00010200,997,1,997,direct,member"]  # fmt: skip
    (root / "mechanics.toml").write_text("schema = [\n", encoding="utf-8")
    assert cli.main(["mechanics", "write", "--config", str(root)]) == 2
