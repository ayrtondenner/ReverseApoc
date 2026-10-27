"""config/mechanics.toml and the generated config/mechanics-members.csv (DEC-01, D-01, D-02, D-04,
D-22, D-23, D-31): the strict loader, the members generator over hand-made call graphs, roles,
tier digests, the committed-data check and the `mechanics` verb. No game files: every graph here
is built by hand from made-up addresses."""

from __future__ import annotations

import dataclasses
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


# ---- Task 2: hubs, entries always members, asm and closure roles, digests, check ----


def M(*, items=(("997", 1),), entries=(("997", E),), rule=None, tiers=(1, 2), edges=(),
      signed=None) -> mechanics.Mechanics:  # fmt: skip
    """A Mechanics: items as (id, tier), entries as (item, address) in ufo2p."""
    return mechanics.Mechanics(
        hub_rule=rule or mechanics.HubRule(),
        tiers=tuple(mechanics.Tier(t, f"Tier {t}", *(signed or {}).get(t, ())) for t in tiers),
        items=tuple(mechanics.Item(i, int(i.split("-")[0]), f"Item {i}", "", t, "in",
                                   exes=("ufo2p",)) for i, t in items),  # fmt: skip
        entries=tuple(mechanics.Entry(i, "ufo2p", a, "hand", "proved") for i, a in entries),
        edges=edges,
    )


def by_address(rows):
    return {row.address: row for row in rows}


def members(mech, g, nodes=ALL, asm=frozenset()):
    return compute_members(mech, {"ufo2p": g}, {"ufo2p": game_rows(*nodes)}, asm)


def test_hub_stops_the_member_walk():
    g = graph((E, H), (C, H), (D, H), (H, X))
    rows = by_address(members(M(rule=mechanics.HubRule(min_direct_callers=3)), g))
    assert (rows[E].role, rows[H].role, rows[X].role) == ("member", "hub", "closure")
    assert rows[H].member_items == () and rows[X].member_items == ()
    assert rows[X].items == ("997",)  # still in the full closure (D-02)
    assert set(rows) == {E, H, X}


def test_hub_rule_off_walks_everything():
    g = graph((E, H), (C, H), (D, H), (H, X))
    rows = by_address(members(M(), g))
    assert {a: r.role for a, r in rows.items()} == {E: "member", H: "member", X: "member"}


def test_entry_that_is_a_hub_stays_a_member():
    g = graph((E, H), (C, H), (D, H), (H, X))
    mech = M(items=(("263-1", 1), ("263-2", 1)), entries=(("263-1", H), ("263-2", E)),
             rule=mechanics.HubRule(min_direct_callers=3))  # fmt: skip
    rows = by_address(members(mech, g))
    assert rows[H].role == "member"
    assert rows[H].member_items == ("263-1",)
    assert rows[H].items == ("263-1", "263-2")
    assert rows[X].member_items == ("263-1",)  # the entry is expanded for its own item
    assert rows[E].member_items == ("263-2",)


def test_other_hub_criteria():
    # largest SCC: A <-> B is the only cycle; E -> A -> B -> Y
    g = graph((E, A), (A, B), (B, A), (B, Y))
    rows = by_address(members(M(rule=mechanics.HubRule(largest_scc=True)), g))
    assert (rows[A].role, rows[B].role, rows[Y].role) == ("hub", "hub", "closure")
    # closure share: A reaches 4 of 10 rows (A, B, C, D) > 0.3; B reaches 3 (not above)
    g = graph((E, A), (A, B), (B, C), (C, D))
    rows = by_address(members(M(rule=mechanics.HubRule(max_closure_share=0.3)), g))
    assert (rows[A].role, rows[B].role) == ("hub", "closure")
    assert rows[E].role == "member"  # an entry is always a member (D-31)
    # min_items: F and everything below it is reached by both items; A only by 997
    g = graph((E, F), (C, F), (F, Y), (E, A))
    mech = M(items=(("997", 1), ("263-1", 1)), entries=(("997", E), ("263-1", C)),
             rule=mechanics.HubRule(min_items=2))  # fmt: skip
    rows = by_address(members(mech, g))
    assert (rows[F].role, rows[Y].role, rows[A].role) == ("hub", "hub", "member")
    assert rows[F].items == ("263-1", "997")


def test_is_hub_reports_each_criterion():
    g = graph((E, H), (C, H), (D, H))
    stats = mechanics.hub_stats(g, frozenset(ALL), {"997": frozenset({E, H})})
    assert mechanics.is_hub(H, mechanics.HubRule(min_direct_callers=3), g, stats)
    assert not mechanics.is_hub(H, mechanics.HubRule(min_direct_callers=4), g, stats)
    assert not mechanics.is_hub(H, mechanics.HubRule(), g, stats)


def test_hand_edges_join_the_walk():
    edge = mechanics.HandEdge("ufo2p", A, B, "call through a table (proved)")
    rows = by_address(members(M(edges=(edge,)), graph((E, A), nodes=(B,))))
    assert B in rows and rows[B].via == "hand" and rows[B].role == "member"
    stray = mechanics.HandEdge("ufo2p", A, RUNTIME, "into the runtime")
    with pytest.raises(MechanicsError, match="edge"):
        members(M(edges=(stray,)), graph((E, A)))


def test_asm_row_is_a_boundary():
    S = C
    g = graph((E, S), (S, Y))
    rows = by_address(members(M(), g, asm=frozenset({("ufo2p", S)})))
    assert (rows[E].role, rows[S].role, rows[Y].role) == ("member", "asm", "closure")
    with pytest.raises(MechanicsError, match="D-23"):
        members(M(entries=(("997", S),)), g, asm=frozenset({("ufo2p", S)}))


ASM_COMMENT = (
    "# generated by: uv run reverseapoc mechanics asm --write; the tool owns exe, address and "
    "evidence; verdict and reason are written by hand where the owner overrides (D-23)"
)


def asm_text(*rows: tuple[int, str]) -> str:
    lines = [ASM_COMMENT, "exe,address,evidence,verdict,reason"]
    lines += [f"ufo2p,0x{a:08X},off-alignment,{v}," for a, v in rows]
    return "\n".join(lines) + "\n"


def test_asm_list_round_trip(tmp_path):
    path = tmp_path / mechanics.ASM_CSV
    path.write_bytes(asm_text((C, "asm"), (D, "unclear")).encode("ascii"))  # LF on every host
    rows = mechanics.read_asm_list(path)
    got = [(r.exe, r.address, r.verdict) for r in rows]
    assert got == [("ufo2p", C, "asm"), ("ufo2p", D, "unclear")]
    assert mechanics.format_asm_csv(rows) == path.read_text(encoding="utf-8")
    assert mechanics.ASM_COLUMNS == ("exe", "address", "evidence", "verdict", "reason")
    crlf = tmp_path / "crlf.csv"
    crlf.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert mechanics.asm_list_sha256(crlf) == mechanics.asm_list_sha256(path)
    path.write_text(asm_text((C, "maybe")), encoding="utf-8")
    with pytest.raises(MechanicsError, match="verdict"):
        mechanics.read_asm_list(path)


def _asm_signoff(path: Path) -> dict:
    return {"signed_off_by": "owner", "signed_off_date": datetime.date(2026, 11, 1),
            "list_sha256": mechanics.asm_list_sha256(path)}  # fmt: skip


def _asm_config(tmp_path, *, signed: bool) -> Path:
    root = _config(tmp_path, "", rows=game_rows(E, A, C, Y))
    (root / mechanics.ASM_CSV).write_text(asm_text((C, "asm")), encoding="utf-8")
    top = {"schema": 1}
    if signed:
        top["asm_list"] = _asm_signoff(root / mechanics.ASM_CSV)
    (root / "mechanics.toml").write_text(toml_text(top, **minimal_tables()), encoding="utf-8")
    return root


def test_write_refuses_an_unsigned_or_changed_asm_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mechanics, "load_graphs",
                        lambda *a, **k: {"ufo2p": graph((E, C), (C, Y))})  # fmt: skip
    root = _asm_config(tmp_path / "unsigned", signed=False)
    assert cli.main(["mechanics", "write", "--config", str(root)]) == 2
    assert "D-23" in capsys.readouterr().err
    root = _asm_config(tmp_path / "signed", signed=True)
    assert cli.main(["mechanics", "write", "--config", str(root)]) == 0
    rows = by_address(read_members(root / mechanics.MEMBERS_CSV))
    assert (rows[C].role, rows[Y].role) == ("asm", "closure")
    with (root / mechanics.ASM_CSV).open("a", encoding="utf-8") as fh:
        fh.write("ufo2p,0x00010A00,off-alignment,asm,\n")
    assert cli.main(["mechanics", "write", "--config", str(root)]) == 2
    assert "changed since" in capsys.readouterr().err


def test_shared_function_one_row():
    g = graph((E, F), (C, F))
    mech = M(items=(("997", 1), ("263-10", 2), ("263-2", 2)),
             entries=(("997", E), ("263-10", C), ("263-2", C)))  # fmt: skip
    shared = [r for r in members(mech, g) if r.address == F]
    assert len(shared) == 1
    assert shared[0].items == ("263-2", "263-10", "997")  # by (issue, number), not text
    assert shared[0].tiers == (1, 2)
    assert shared[0].member_items == ("263-2", "263-10", "997")


def test_empty_item_and_empty_file(tmp_path, monkeypatch):
    mech = M(items=(("997", 1), ("263-1", 1)))  # 263-1 has no entries
    rows = members(mech, graph((E, A)))
    assert rows and all("263-1" not in r.items for r in rows)
    root = _config(tmp_path, "schema = 1\n")
    monkeypatch.setattr(mechanics, "load_graphs", lambda *a, **k: pytest.fail("needs no EXE"))
    assert cli.main(["mechanics", "write", "--config", str(root)]) == 0
    text = (root / mechanics.MEMBERS_CSV).read_text(encoding="utf-8")
    assert text == MEMBERS_COMMENT + "\n" + ",".join(MEMBERS_COLUMNS) + "\n"


def _digest_world():
    """E (tier 1) -> H (hub: callers E, C, D) -> X; D -> H and D -> X."""
    return graph((E, H), (C, H), (D, H), (H, X), (D, X)), mechanics.HubRule(min_direct_callers=3)


def test_tier_digest_changes_on_change():
    g, rule = _digest_world()
    base = M(rule=rule)
    digest = mechanics.tier_digest(base, members(base, g), 1)
    assert len(digest) == 64
    assert mechanics.tier_digest(base, members(base, g), 1) == digest  # deterministic
    other_rule = M(rule=mechanics.HubRule(min_direct_callers=4))
    assert mechanics.tier_digest(other_rule, members(other_rule, g), 1) != digest
    more = M(rule=rule, entries=(("997", E), ("997", C)))
    assert mechanics.tier_digest(more, members(more, g), 1) != digest
    as_asm = members(base, g, asm=frozenset({("ufo2p", X)}))
    assert by_address(as_asm)[X].role == "asm"
    assert mechanics.tier_digest(base, as_asm, 1) != digest
    # a Tier 2 item that makes Tier 1's closure row X a Tier 2 member leaves Tier 1 alone
    later = M(rule=rule, items=(("997", 1), ("263-2", 2)), entries=(("997", E), ("263-2", D)))
    later_rows = members(later, g)
    assert by_address(later_rows)[X].role == "member"
    assert by_address(later_rows)[X].member_items == ("263-2",)
    assert mechanics.tier_digest(later, later_rows, 1) == digest
    assert mechanics.tier_digest(later, later_rows, 2) != digest


def test_signed_tiers():
    g, rule = _digest_world()
    base = M(rule=rule)
    rows = members(base, g)
    digest = mechanics.tier_digest(base, rows, 1)
    signed = M(rule=rule, signed={1: ("owner", datetime.date(2026, 11, 2), digest)})
    assert mechanics.signed_tiers(signed, rows) == (1,)
    stale = M(rule=rule, signed={1: ("owner", datetime.date(2026, 11, 2), "0" * 64)})
    assert mechanics.signed_tiers(stale, rows) == ()


def _committed(tmp_path, *, sign=True, asm=()) -> Path:
    """A config root with mechanics.toml (tier 1 signed), members, functions.csv, asm list."""
    g, rule = _digest_world()
    nodes = (E, C, D, H, X)
    root = _config(tmp_path, "", rows=game_rows(*nodes))
    top = {"schema": 1, "hub_rule": {"min_direct_callers": 3}}
    if asm:
        path = root / mechanics.ASM_CSV
        path.write_text(asm_text(*((a, "asm") for a in asm)), encoding="utf-8")
        top["asm_list"] = _asm_signoff(path)
    mech = M(rule=rule)
    rows = members(mech, g, nodes=nodes, asm=frozenset(("ufo2p", a) for a in asm))
    write_members(root / mechanics.MEMBERS_CSV, rows)
    t1 = tier(1)
    if sign:
        t1 |= {"signed_off_by": "owner", "signed_off_date": datetime.date(2026, 11, 2),
               "members_sha256": mechanics.tier_digest(mech, rows, 1)}  # fmt: skip
    text = toml_text(top, tier=[t1, tier(2)], item=[item()], entry=[entry()])
    (root / "mechanics.toml").write_text(text, encoding="utf-8")
    return root


def _rewrite(root: Path, change) -> None:
    path = root / mechanics.MEMBERS_CSV
    write_members(path, [change(row) for row in read_members(path)])


def test_check_clean(tmp_path):
    root = _committed(tmp_path)
    assert mechanics.check_committed(root) == []
    assert cli.main(["mechanics", "check", "--config", str(root)]) == 0
    assert mechanics.check_committed(tmp_path / "nothing") == []  # no mechanics.toml yet


def _runtime_member(root):
    rows = read_members(root / mechanics.MEMBERS_CSV)
    rows.append(MemberRow("ufo2p", RUNTIME, ("997",), (1,), ("997",), "direct", "member"))
    write_members(root / mechanics.MEMBERS_CSV, rows)


def _entry_not_entry(root):
    _rewrite(root, lambda r: dataclasses.replace(r, via="direct") if r.address == E else r)


def _digest_drift(root):
    _rewrite(root, lambda r: dataclasses.replace(r, role="hub") if r.address == X else r)


def _entryless_item(root):
    text = (root / "mechanics.toml").read_text(encoding="utf-8")
    extra = toml_text({}, item=[item("263-1")])
    (root / "mechanics.toml").write_text(text + extra, encoding="utf-8")


def _asm_entry(root):
    (root / mechanics.ASM_CSV).write_text(asm_text((E, "asm")), encoding="utf-8")
    table = toml_text({"asm_list": _asm_signoff(root / mechanics.ASM_CSV)})
    text = (root / "mechanics.toml").read_text(encoding="utf-8")
    text = text.replace("schema = 1\n", "schema = 1\n" + table, 1)
    (root / "mechanics.toml").write_text(text, encoding="utf-8")


def _changed_asm(root):
    with (root / mechanics.ASM_CSV).open("a", encoding="utf-8") as fh:
        fh.write("ufo2p,0x00010A00,off-alignment,asm,\n")


@pytest.mark.parametrize(("change", "word", "asm"), [
    pytest.param(_runtime_member, "game or thunk", (), id="runtime row"),
    pytest.param(_entry_not_entry, "via entry", (), id="entry without via entry"),
    pytest.param(_digest_drift, "re-sign", (), id="signed tier changed"),
    pytest.param(_entryless_item, "no entry", (), id="signed tier entry-less item"),
    pytest.param(_asm_entry, "asm list", (), id="asm-listed entry"),
    pytest.param(_changed_asm, "changed since", (C,), id="changed asm list"),
])  # fmt: skip
def test_check_refuses(tmp_path, change, word, asm):
    root = _committed(tmp_path, asm=asm)
    assert mechanics.check_committed(root) == []
    change(root)
    problems = mechanics.check_committed(root)
    assert problems and any(word in p for p in problems), problems
    assert cli.main(["mechanics", "check", "--config", str(root)]) == 1


def test_check_without_members_file(tmp_path):
    root = _committed(tmp_path, sign=False)
    (root / mechanics.MEMBERS_CSV).unlink()
    assert any("mechanics write" in p for p in mechanics.check_committed(root))
    (root / "mechanics.toml").write_text("schema = 1\n", encoding="utf-8")
    assert mechanics.check_committed(root) == []  # nothing to generate yet


def test_digest_verb(tmp_path, capsys):
    root = _committed(tmp_path)
    mech = load(root / "mechanics.toml")
    rows = read_members(root / mechanics.MEMBERS_CSV)
    assert cli.main(["mechanics", "digest", "--tier", "1", "--config", str(root)]) == 0
    assert capsys.readouterr().out.strip() == mechanics.tier_digest(mech, rows, 1)
    assert cli.main(["mechanics", "digest", "--tier", "7", "--config", str(root)]) == 2
