"""tools/progress.py's mosaic (RPT-02, D-26, D-50): progress.svg, a squarified treemap nested
EXE, then unit, then one cell per function sized by bytes, in five fixed colours. The README
embeds it from GitHub Pages. progress.py is loaded by path (it runs under `python3 -I`); the
synthetic tables are test_progress's, the committed-file tests read config/ only (no game
bytes)."""

from __future__ import annotations

import csv
import random
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import pytest

from reverseapoc.functions import FunctionRow, UnitRow, write_functions_csv, write_units_csv
from reverseapoc.status import MATCHED, StatusRow, status_path, write_status
from test_progress import (
    CONFIG,
    DAY,
    EXE_NAMES,
    SHA,
    T_GAME,
    T_UNIT,
    U_MATCHED,
    U_PARTIAL,
    U_RUNTIME,
    U_THUNK,
    U_UNMATCHED,
    load_progress,
    size,
    synthetic_config,
)

SVG_NS = "{http://www.w3.org/2000/svg}"
# The five fixed colours (D-50), checked with the dataviz palette validator: the three hues pass
# CVD separation on the light surface; unmatched and uncovered are deliberately neutral greys.
COLORS = {
    "matched": "#008300",
    "partial": "#eda100",
    "unmatched": "#898781",
    "library": "#2a78d6",
    "uncovered": "#d8d6cf",
}
GAP = 0x1008C - 0x1007C  # the synthetic UFO2P unit's 16 bytes in no row
SVG_LIMIT = 1_000_000
_ROUNDED = re.compile(r"-?[0-9]+(\.[0-9])?")
EPS = 1e-6


def treemap():
    """progress.py with its treemap API; called in each test body, so a missing function fails
    the test on this assert."""
    progress = load_progress()
    for name in ("squarify", "render_svg", "TREEMAP_COLORS"):
        assert hasattr(progress, name), f"progress.py has no {name}"
    return progress


def overlap(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    width = min(ax + aw, bx + bw) - max(ax, bx)
    height = min(ay + ah, by + bh) - max(ay, by)
    return max(0.0, width) * max(0.0, height)


# ---- squarify ----


def test_squarify_tiles_its_rectangle():
    """Rectangles lie inside the parent, do not overlap, are each proportional to their size and
    together cover the parent's area."""
    progress = treemap()
    rng = random.Random(624)
    sizes = sorted((rng.randint(1, 1000) for _ in range(60)), reverse=True)
    parent = (10.0, 20.0, 300.0, 200.0)
    rects = progress.squarify(sizes, parent)
    assert len(rects) == len(sizes)
    px, py, pw, ph = parent
    for x, y, w, h in rects:
        assert w >= 0 and h >= 0
        assert x >= px - EPS and y >= py - EPS
        assert x + w <= px + pw + EPS and y + h <= py + ph + EPS
    scale = pw * ph / sum(sizes)
    for value, (_, _, w, h) in zip(sizes, rects, strict=True):
        assert w * h == pytest.approx(value * scale, rel=1e-9)
    assert sum(w * h for _, _, w, h in rects) == pytest.approx(pw * ph, rel=1e-9)
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert overlap(a, b) <= EPS


def test_squarify_makes_squares_not_slices():
    """Four equal sizes in a square give four squares (Bruls/Huizing/van Wijk), where
    slice-and-dice would give four 4:1 strips."""
    rects = treemap().squarify([1, 1, 1, 1], (0.0, 0.0, 2.0, 2.0))
    assert sorted((round(x, 9), round(y, 9), round(w, 9), round(h, 9)) for x, y, w, h in rects) == [
        (0.0, 0.0, 1.0, 1.0), (0.0, 1.0, 1.0, 1.0), (1.0, 0.0, 1.0, 1.0), (1.0, 1.0, 1.0, 1.0)]


def test_squarify_edge_cases():
    progress = treemap()
    assert progress.squarify([], (0.0, 0.0, 5.0, 5.0)) == []
    assert progress.squarify([7], (1.0, 2.0, 3.0, 4.0)) == [(1.0, 2.0, 3.0, 4.0)]
    with pytest.raises(ValueError, match="positive"):
        progress.squarify([3, 0], (0.0, 0.0, 1.0, 1.0))


# ---- the SVG ----


def parse(svg: str) -> ET.Element:
    root = ET.fromstring(svg)
    assert root.tag == f"{SVG_NS}svg"
    return root


def cells(group: ET.Element) -> list[ET.Element]:
    """The coloured cells of a unit group (its outline rect has fill="none")."""
    return [r for r in group.findall(f"{SVG_NS}rect") if r.get("fill") != "none"]


def area(rect: ET.Element) -> float:
    return float(rect.get("width")) * float(rect.get("height"))


def colour_of(name: str) -> str:
    return COLORS[name]


def test_treemap_colours_are_the_five_fixed_colours():
    assert treemap().TREEMAP_COLORS == COLORS


def test_treemap_nesting_and_colours(tmp_path):
    """EXE groups hold unit groups that hold one cell per game, thunk and runtime function plus
    one cell for the unit's uncovered bytes; data-in-code is not drawn (D-26, D-50)."""
    progress = treemap()
    root = parse(progress.render_svg(progress.derive(synthetic_config(tmp_path))))
    exes = root.findall(f".//{SVG_NS}g[@data-exe]")
    assert [g.get("data-exe") for g in exes] == ["ufo2p", "tacp"]

    ufo2p_units = exes[0].findall(f"{SVG_NS}g[@data-unit]")
    assert [g.get("data-unit") for g in ufo2p_units] == ["u_00010000"]
    ufo2p = cells(ufo2p_units[0])
    expected = {"matched": [size(U_MATCHED)], "partial": [size(U_PARTIAL)],
                "unmatched": sorted([size(U_UNMATCHED), size(U_THUNK)]),
                "library": [size(U_RUNTIME)], "uncovered": [GAP]}  # fmt: skip
    drawn = sum(sum(v) for v in expected.values())
    total_area = sum(area(r) for r in ufo2p)
    for status, sizes in expected.items():
        mine = [r for r in ufo2p if r.get("fill") == colour_of(status)]
        assert len(mine) == len(sizes), status
        shares = sorted(area(r) / total_area for r in mine)
        assert shares == pytest.approx([s / drawn for s in sizes], rel=0.02), status
    assert len(ufo2p) == sum(len(v) for v in expected.values())

    tacp_units = exes[1].findall(f"{SVG_NS}g[@data-unit]")
    assert [g.get("data-unit") for g in tacp_units] == [T_GAME.unit]
    assert [r.get("fill") for r in cells(tacp_units[0])] == [COLORS["unmatched"]]  # no gap


def test_treemap_titles_on_unit_groups_matched_and_partial_cells_only(tmp_path):
    progress = treemap()
    root = parse(progress.render_svg(progress.derive(synthetic_config(tmp_path))))
    for group in root.findall(f".//{SVG_NS}g[@data-unit]"):
        title = group.find(f"{SVG_NS}title")
        assert title is not None and group.get("data-unit") in title.text
        for rect in cells(group):
            titled = rect.find(f"{SVG_NS}title")
            if rect.get("fill") == COLORS["matched"]:
                assert titled is not None and U_MATCHED.name in titled.text
            elif rect.get("fill") == COLORS["partial"]:
                assert titled is not None and U_PARTIAL.name in titled.text
            else:
                assert titled is None


# ---- tooltips (owner request of 2026-10-26: partials are named, the counting is unchanged) ----

SYNTHETIC_UNIT_TITLE = ("UFO2P.EXE u_00010000: 16 of 228 code bytes matched, 4 functions; "
                        "8 library bytes; 16 uncovered bytes")  # fmt: skip


def cell_titles(group: ET.Element, colour: str) -> list[str]:
    return [r.find(f"{SVG_NS}title").text for r in cells(group) if r.get("fill") == colour]


def unit_group(root: ET.Element, unit: str) -> ET.Element:
    group = root.find(f".//{SVG_NS}g[@data-unit='{unit}']")
    assert group is not None, unit
    return group


def test_partial_cell_title_names_its_best_score(tmp_path):
    """A partial cell's tooltip: name, size, "partial" and status.csv's best_percent, 2 decimals."""
    progress = treemap()
    root = parse(progress.render_svg(progress.derive(synthetic_config(tmp_path))))
    group = unit_group(root, U_PARTIAL.unit)
    assert cell_titles(group, COLORS["partial"]) == [
        f"{U_PARTIAL.name}: {size(U_PARTIAL)} bytes, partial, best 50.00%"]


def test_matched_cell_title_is_unchanged(tmp_path):
    progress = treemap()
    root = parse(progress.render_svg(progress.derive(synthetic_config(tmp_path))))
    group = unit_group(root, U_MATCHED.unit)
    assert cell_titles(group, COLORS["matched"]) == [
        f"{U_MATCHED.name}: {size(U_MATCHED)} bytes, matched"]


def test_unit_title_counts_partials_after_the_matched_bytes(tmp_path):
    """A unit with partials adds "<k> partial (best <max>%)" right after the matched-bytes part;
    the matched bytes still count no partial byte."""
    progress = treemap()
    root = parse(progress.render_svg(progress.derive(synthetic_config(tmp_path))))
    assert unit_group(root, U_PARTIAL.unit).find(f"{SVG_NS}title").text == (
        "UFO2P.EXE u_00010000: 16 of 228 code bytes matched, 4 functions; "
        "1 partial (best 50.00%); 8 library bytes; 16 uncovered bytes")


@pytest.mark.parametrize(("other", "best"), [(12.5, "50.00"), (61.87, "61.87")])
def test_unit_title_takes_the_best_of_two_partials(tmp_path, other, best):
    """The larger partial (U_UNMATCHED made partial, 64 bytes) is drawn first; the max is taken
    over both, whichever comes first or last."""
    progress = treemap()
    derived = progress.derive(synthetic_config(tmp_path))
    exe = derived.exes[0]
    functions = tuple(replace(f, status="partial", best_percent=other)
                      if f.start == U_UNMATCHED.start else f for f in exe.functions)  # fmt: skip
    patched = replace(exe, functions=functions)
    root = parse(progress.render_svg(replace(derived, exes=(patched, derived.exes[1]))))
    group = unit_group(root, U_UNMATCHED.unit)
    assert group.find(f"{SVG_NS}title").text == (
        "UFO2P.EXE u_00010000: 16 of 228 code bytes matched, 4 functions; "
        f"2 partial (best {best}%); 8 library bytes; 16 uncovered bytes")
    assert sorted(cell_titles(group, COLORS["partial"])) == sorted([
        f"{U_PARTIAL.name}: {size(U_PARTIAL)} bytes, partial, best 50.00%",
        f"{U_UNMATCHED.name}: {size(U_UNMATCHED)} bytes, partial, best {other:.2f}%"])


def test_unit_title_without_partials_is_unchanged(tmp_path):
    progress = treemap()
    derived = progress.derive(synthetic_config(tmp_path))
    exe = derived.exes[0]
    functions = tuple(replace(f, status="unmatched", best_percent=0.0)
                      if f.status == "partial" else f for f in exe.functions)  # fmt: skip
    patched = replace(exe, functions=functions)
    root = parse(progress.render_svg(replace(derived, exes=(patched, derived.exes[1]))))
    assert unit_group(root, U_PARTIAL.unit).find(f"{SVG_NS}title").text == SYNTHETIC_UNIT_TITLE
    tacp = unit_group(root, T_GAME.unit)
    assert tacp.find(f"{SVG_NS}title").text == (
        "TACP.EXE u_00020000: 0 of 32 code bytes matched, 1 functions")
    assert all(r.find(f"{SVG_NS}title") is None for r in cells(tacp))  # unmatched: no tooltip


def test_partial_title_is_escaped(tmp_path):
    progress = treemap()
    derived = progress.derive(synthetic_config(tmp_path))
    exe = derived.exes[0]
    functions = tuple(replace(f, name=f"{f.name}<&\">") for f in exe.functions)
    patched = replace(exe, functions=functions)
    svg = progress.render_svg(replace(derived, exes=(patched, derived.exes[1])))
    escaped = f"{U_PARTIAL.name}&lt;&amp;&quot;&gt;"
    assert f"<title>{escaped}: 32 bytes, partial, best 50.00%</title>" in svg
    group = unit_group(parse(svg), U_PARTIAL.unit)
    assert cell_titles(group, COLORS["partial"]) == [
        f"{U_PARTIAL.name}<&\">: 32 bytes, partial, best 50.00%"]


def test_partial_titles_are_deterministic(tmp_path):
    progress = treemap()
    config = synthetic_config(tmp_path)
    first = progress.render_svg(progress.derive(config))
    assert first == progress.render_svg(progress.derive(config))
    assert "partial, best 50.00%" in first


def _committed_partials(stem: str, unit: str) -> list[str]:
    """The best_percent cells, as status.csv stores them, of the unit's partial rows."""
    lines = (CONFIG / stem / "status.csv").read_text(encoding="utf-8").splitlines()
    rows = csv.DictReader(line for line in lines if not line.startswith("#"))
    return [row["best_percent"] for row in rows
            if row["unit"] == unit and row["status"] == "partial"]  # fmt: skip


def test_committed_partial_unit_names_its_partials():
    """u_000c483f (TACP) has a partial row: its unit tooltip counts it with status.csv's best
    score, and every partial cell of the committed mosaic carries a tooltip."""
    progress = treemap()
    derived = progress.derive(CONFIG)
    root = parse(progress.render_svg(derived))
    scores = _committed_partials("tacp", "u_000c483f")
    assert scores, "u_000c483f has no partial row in config/tacp/status.csv"
    best = max(scores, key=float)
    title = unit_group(root, "u_000c483f").find(f"{SVG_NS}title").text
    assert f"; {len(scores)} partial (best {best}%)" in title
    partial = [r for r in root.iter(f"{SVG_NS}rect") if r.get("fill") == COLORS["partial"]]
    assert len(partial) == derived.combined.partial_functions
    for rect in partial:
        assert re.search(r": [0-9,]+ bytes, partial, best [0-9]+\.[0-9]{2}%$",
                         rect.find(f"{SVG_NS}title").text)


def test_treemap_coordinates_are_rounded(tmp_path):
    progress = treemap()
    root = parse(progress.render_svg(progress.derive(synthetic_config(tmp_path))))
    rects = root.findall(f".//{SVG_NS}rect")
    assert rects
    for rect in rects:
        for attribute in ("x", "y", "width", "height"):
            assert _ROUNDED.fullmatch(rect.get(attribute)), (attribute, rect.get(attribute))


def test_treemap_legend_names_every_status_and_the_filler(tmp_path):
    progress = treemap()
    svg = progress.render_svg(progress.derive(synthetic_config(tmp_path)))
    texts = " ".join(t.text or "" for t in parse(svg).iter(f"{SVG_NS}text"))
    for status in COLORS:
        assert status in texts
    assert "uncovered: mostly alignment filler" in texts
    # D-23: signed asm rows are drawn as library cells, so the library entry names both.
    assert "library or assembler, not decompiled" in texts


def test_treemap_escapes_names(tmp_path):
    """Names reach the SVG through xml.sax.saxutils.escape: a unit or function name holding
    markup characters still gives well-formed XML with the name as text."""
    progress = treemap()
    derived = progress.derive(synthetic_config(tmp_path))
    exe = derived.exes[0]
    odd = "u_<a&b>"
    functions = tuple(replace(f, unit=odd, name=f"{f.name}<&>") for f in exe.functions)
    units = tuple(replace(u, unit=odd) for u in exe.units)
    library = tuple(replace(r, unit=odd) for r in exe.library_rows)
    patched = replace(exe, functions=functions, units=units, library_rows=library)
    root = parse(progress.render_svg(replace(derived, exes=(patched, derived.exes[1]))))
    group = root.find(f".//{SVG_NS}g[@data-unit='{odd}']")
    assert group is not None
    assert odd in group.find(f"{SVG_NS}title").text
    assert [t.text for t in group.findall(f"{SVG_NS}text")] == [odd]  # the label, escaped


def test_svg_is_deterministic_and_bounded():
    """Two renders of the committed CSVs are byte-identical, parse as XML and stay under 1 MB
    (D-26); every matched function has its cell."""
    progress = treemap()
    first = progress.render_svg(progress.derive(CONFIG))
    second = progress.render_svg(progress.derive(CONFIG))
    assert first == second
    data = first.encode("utf-8")
    assert len(data) < SVG_LIMIT, len(data)
    root = parse(first)
    derived = progress.derive(CONFIG)
    matched = [r for r in root.iter(f"{SVG_NS}rect") if r.get("fill") == COLORS["matched"]]
    assert len(matched) == derived.combined.matched_functions
    library = [r for r in root.iter(f"{SVG_NS}rect") if r.get("fill") == COLORS["library"]]
    assert len(library) == derived.combined.library_functions


def test_main_creates_output_dirs(tmp_path):
    """Orchestrator ruling F17: the Pages job runs on a checkout without _site/ or build/, so main
    creates every output's directory; --out also gets progress.svg."""
    progress = treemap()
    config = synthetic_config(tmp_path)
    out = tmp_path / "a" / "b"
    report = tmp_path / "c" / "report.json"
    assert not (tmp_path / "a").exists() and not (tmp_path / "c").exists()
    assert progress.main(["--config", str(config), "--out", str(out),
                          "--report", str(report)]) == 0  # fmt: skip
    for path in (out / "progress.json", out / "progress-shield.json", out / "progress.svg",
                 report):  # fmt: skip
        assert path.is_file(), path
    svg = (out / "progress.svg").read_bytes()
    assert svg == progress.render_svg(progress.derive(config)).encode("utf-8")
    assert not list(Path(out).glob(".*.tmp"))


# ---- unit labels (owner ruling 2, 2026-10-26) ----

# UFO2P: a big game unit (one matched row filling it), a library unit whose three runtime rows
# test the tie-break, and a sliver of a game unit too small for a label. Computed against today's
# squarify: u_00010000 913.3 x 750 px, rt_big 285.8 x 748.8, u_0001a800 285.8 x 1.2; TACP's one
# unit is 0.9 px wide.
L_GAME = FunctionRow(0x10000, 0x18000, "func_00010000", "game", "u_00010000", "call")
L_SMALL = FunctionRow(0x18000, 0x18800, "small_", "runtime", "rt_big", "runtime")  # first, small
L_ZETA = FunctionRow(0x18800, 0x19800, "zeta_", "runtime", "rt_big", "runtime")  # largest, low
L_ALPHA = FunctionRow(0x19800, 0x1A800, "alpha_", "runtime", "rt_big", "runtime")  # tie, high
L_TINY = FunctionRow(0x1A800, 0x1A810, "func_0001A800", "game", "u_0001a800", "call")
L_UNITS = [UnitRow("u_00010000", 0x10000, 0x18000, "hand"),
           UnitRow("rt_big", 0x18000, 0x1A800, "hand"),
           UnitRow("u_0001a800", 0x1A800, 0x1A810, "hand")]  # fmt: skip
EXPECTED_LABELS = {"u_00010000": "u_00010000", "rt_big": "zeta_"}
BAND = 0.15  # the 0.1 coordinate rounding, with room: inside it either outcome is accepted


def labelled_config(root: Path) -> Path:
    """A config tree whose UFO2P mosaic has two units large enough for a label and one not."""
    config = root / "config"
    tables = {"ufo2p": ([L_GAME, L_SMALL, L_ZETA, L_ALPHA, L_TINY], L_UNITS),
              "tacp": ([T_GAME], [T_UNIT])}  # fmt: skip
    for exe, (rows, units) in tables.items():
        write_functions_csv(config / exe / "functions.csv", rows, EXE_NAMES[exe])
        write_units_csv(config / exe / "units.csv", units, EXE_NAMES[exe])
    write_status(status_path(config, "ufo2p"), [
        StatusRow(L_GAME.start, L_GAME.name, L_GAME.unit, MATCHED, 100.0, 0, SHA, DAY)])
    return config


def labelled():
    """progress.py with its label API; a missing name fails the test on this assert."""
    progress = treemap()
    for name in ("LABEL_FONT_SIZE", "LABEL_CHAR", "LABEL_PAD", "LABEL_MIN_WIDTH",
                 "LABEL_MIN_HEIGHT"):  # fmt: skip
        assert hasattr(progress, name), f"progress.py has no {name}"
    return progress


def unit_labels(root: ET.Element) -> dict[str, str]:
    """unit -> label text, for every unit group holding a <text>."""
    out = {}
    for group in root.iter(f"{SVG_NS}g"):
        texts = group.findall(f"{SVG_NS}text")
        if group.get("data-unit") is not None and texts:
            out[group.get("data-unit")] = " ".join(t.text or "" for t in texts)
    return out


def test_treemap_labels_large_units_only(tmp_path):
    progress = labelled()
    root = parse(progress.render_svg(progress.derive(labelled_config(tmp_path))))
    assert unit_labels(root) == EXPECTED_LABELS
    for unit in ("u_0001a800", T_UNIT.unit):
        group = root.find(f".//{SVG_NS}g[@data-unit='{unit}']")
        assert group is not None and group.findall(f"{SVG_NS}text") == [], unit


def test_treemap_library_label_is_the_largest_runtime_function(tmp_path):
    """A library unit is labelled with its largest runtime row, the lowest start on a size tie:
    zeta_, not small_ (first by address but smaller) and not alpha_ (as large, a higher start;
    alphabetical order would pick it)."""
    progress = labelled()
    root = parse(progress.render_svg(progress.derive(labelled_config(tmp_path))))
    assert unit_labels(root)["rt_big"] == L_ZETA.name


def test_treemap_labels_keep_the_tooltips(tmp_path):
    """Labels come after every cell of their unit and ignore the pointer, so every <title>
    (the unit group's, the matched cell's) stays reachable."""
    progress = labelled()
    root = parse(progress.render_svg(progress.derive(labelled_config(tmp_path))))
    groups = [g for g in root.iter(f"{SVG_NS}g") if g.findall(f"{SVG_NS}text")
              and g.get("data-unit") is not None]  # fmt: skip
    assert len(groups) == len(EXPECTED_LABELS)
    for group in groups:
        children = list(group)
        assert children[0].tag == f"{SVG_NS}title"
        last_cell = max(i for i, c in enumerate(children)
                        if c.tag == f"{SVG_NS}rect" and c.get("fill") != "none")  # fmt: skip
        for i, child in enumerate(children):
            if child.tag != f"{SVG_NS}text":
                continue
            assert i > last_cell
            assert child.get("pointer-events") == "none"
    game = root.find(f".//{SVG_NS}g[@data-unit='u_00010000']")
    matched = [r for r in cells(game) if r.get("fill") == COLORS["matched"]]
    assert len(matched) == 1
    assert L_GAME.name in matched[0].find(f"{SVG_NS}title").text


def test_treemap_labels_are_deterministic(tmp_path):
    progress = labelled()
    config = labelled_config(tmp_path)
    assert progress.render_svg(progress.derive(config)) == progress.render_svg(
        progress.derive(config))


# ---- cut labels (owner ruling of 2026-10-26: cut a long name instead of dropping it) ----

ELLIPSIS = "…"  # one character, never three periods


def cutting():
    """progress.py with its label-cutting API; a missing name fails the test on this assert."""
    progress = labelled()
    for name in ("LABEL_MIN_CHARS", "LABEL_ELLIPSIS"):
        assert hasattr(progress, name), f"progress.py has no {name}"
    assert progress.LABEL_MIN_CHARS == 6
    assert progress.LABEL_ELLIPSIS == ELLIPSIS
    return progress


def label_of(progress, name: str, width: float, height: float = 30.0) -> str | None:
    """The text _label_svg draws for `name` in a unit of `width` x `height`, or None."""
    svg = progress._label_svg(name, (0.0, 0.0, width, height))
    if svg is None:
        return None
    return ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{svg}</svg>')[0].text


def test_label_that_fits_is_drawn_in_full():
    progress = cutting()
    for name in ("u_0003d8a0", "grafix", "__int7"):
        assert label_of(progress, name, 80.0) == name


def test_label_too_long_is_cut_with_one_ellipsis():
    """A 62 px unit holds (62 - 2 * LABEL_PAD) // LABEL_CHAR = 8 characters: the first 7 of the
    name, then the ellipsis, which counts as one."""
    progress = cutting()
    assert 2 * progress.LABEL_PAD + progress.LABEL_CHAR * 8 <= 62.0
    assert 2 * progress.LABEL_PAD + progress.LABEL_CHAR * 9 > 62.0
    assert label_of(progress, "u_0003d8a0", 62.0) == "u_0003d" + ELLIPSIS
    assert "..." not in progress._label_svg("u_0003d8a0", (0.0, 0.0, 62.0, 30.0))


def test_label_cut_below_six_characters_is_dropped():
    """Six characters plus the ellipsis is the shortest cut label; five plus the ellipsis is
    none. The fixed minimum size still applies."""
    progress = cutting()
    six = 2 * progress.LABEL_PAD + progress.LABEL_CHAR * 7  # 6 kept + the ellipsis
    assert label_of(progress, "u_0003d8a0", six + 0.01) == "u_0003" + ELLIPSIS
    assert label_of(progress, "u_0003d8a0", six - 0.01) is None  # 5 kept + the ellipsis
    assert label_of(progress, "u_0003d8a0", 80.0, progress.LABEL_MIN_HEIGHT - 0.01) is None


def test_short_label_needs_no_minimum_characters():
    """The six-character floor is for cut names only: `zeta_` (5 characters) fits a unit of
    the fixed minimum width and is drawn whole."""
    progress = cutting()
    assert label_of(progress, L_ZETA.name, float(progress.LABEL_MIN_WIDTH)) == L_ZETA.name
    assert label_of(progress, L_ZETA.name, progress.LABEL_MIN_WIDTH - 0.01) is None


def test_cut_label_is_escaped_after_cutting():
    """The raw name is cut, then escaped: `u_<a&b>` keeps its 7 raw characters and no escape
    sequence is split."""
    progress = cutting()
    svg = progress._label_svg("u_<a&b>cdefgh", (0.0, 0.0, 62.0, 30.0))
    assert svg is not None
    assert f">u_&lt;a&amp;b&gt;{ELLIPSIS}</text>" in svg
    assert label_of(progress, "u_<a&b>cdefgh", 62.0) == "u_<a&b>" + ELLIPSIS


def test_svg_file_carries_the_ellipsis_as_utf8(tmp_path):
    """The committed CSVs give cut labels; write_svg keeps the ellipsis as UTF-8 bytes, one per
    cut label, and the bytes are deterministic."""
    progress = cutting()
    derived = progress.derive(CONFIG)
    path = tmp_path / "progress.svg"
    progress.write_svg(derived, path)
    data = path.read_bytes()
    assert data == progress.render_svg(derived).encode("utf-8")
    cut = [t for t in parse(data.decode("utf-8")).iter(f"{SVG_NS}text")
           if (t.text or "").endswith(ELLIPSIS)]  # fmt: skip
    assert cut and data.count(ELLIPSIS.encode("utf-8")) == len(cut)
    assert b"..." not in data


def _expected_labels(derived) -> dict[tuple[str, str], str]:
    """(exe stem, unit) -> the label the rule gives: the unit name, unless the unit holds runtime
    rows and no game/thunk function; then its largest runtime row, the lowest start on a tie."""
    out = {}
    for exe in derived.exes:
        code_units = {f.unit or "unassigned" for f in exe.functions}
        library: dict[str, list] = {}
        for row in exe.library_rows:
            library.setdefault(row.unit or "unassigned", []).append(row)
        for unit in code_units:
            out[(exe.stem, unit)] = unit
        for unit, rows in library.items():
            if unit in code_units:
                continue
            out[(exe.stem, unit)] = min(rows, key=lambda r: (-r.size, r.start)).name
        for unit in exe.units:
            out.setdefault((exe.stem, unit.unit), unit.unit)
    return out


def _outline(group: ET.Element) -> tuple[float, float, float, float]:
    rect = next(r for r in group.findall(f"{SVG_NS}rect") if r.get("fill") == "none")
    return tuple(float(rect.get(a)) for a in ("x", "y", "width", "height"))


def _check_label(progress, text: ET.Element, box) -> None:
    x, y, w, h = box
    tx, ty = text.get("x"), text.get("y")
    assert _ROUNDED.fullmatch(tx) and _ROUNDED.fullmatch(ty), (tx, ty)
    assert float(tx) >= x
    assert float(tx) + progress.LABEL_CHAR * len(text.text) <= x + w + BAND, text.text
    assert y <= float(ty) <= y + h, text.text
    assert text.get("font-size") == str(progress.LABEL_FONT_SIZE)


def _fitted(progress, label: str, w: float, h: float) -> str | None:
    """The owner's rule, computed independently: the full name when it fits, else the most
    characters that fit, the last one being the ellipsis, when at least LABEL_MIN_CHARS of the
    name are left; None below that or below the fixed minimum size."""
    if w < progress.LABEL_MIN_WIDTH or h < progress.LABEL_MIN_HEIGHT:
        return None
    room = 0
    while 2 * progress.LABEL_PAD + progress.LABEL_CHAR * (room + 1) <= w:
        room += 1
    if len(label) <= room:
        return label
    if room - 1 < progress.LABEL_MIN_CHARS:
        return None
    return label[:room - 1] + ELLIPSIS


def test_treemap_labels_fit_their_unit():
    """On the committed CSVs, every unit carries exactly the full-or-cut label the rule gives
    for its size, or none below the minimum, and each label lies inside its unit. The rule is
    decided on the unrounded rect, the test sees the 0.1-rounded one: only inside that band may
    the outcome be either neighbour's."""
    progress = cutting()
    derived = progress.derive(CONFIG)
    expected = _expected_labels(derived)
    root = parse(progress.render_svg(derived))
    seen = {"game": 0, "library": 0, "full": 0, "cut": 0}
    for exe_group in root.findall(f".//{SVG_NS}g[@data-exe]"):
        stem = exe_group.get("data-exe")
        for group in exe_group.findall(f"{SVG_NS}g[@data-unit]"):
            unit = group.get("data-unit")
            label = expected[(stem, unit)]
            x, y, w, h = _outline(group)
            allowed = {_fitted(progress, label, w + dw, h + dh)
                       for dw in (-BAND, 0.0, BAND) for dh in (-BAND, 0.0, BAND)}  # fmt: skip
            texts = group.findall(f"{SVG_NS}text")
            drawn = texts[0].text if texts else None
            assert len(texts) <= 1, (stem, unit)
            assert drawn in allowed, (stem, unit, drawn, allowed)
            for text in texts:
                _check_label(progress, text, (x, y, w, h))
                seen["game" if label == unit else "library"] += 1
                seen["cut" if text.text != label else "full"] += 1
    assert min(seen.values()) >= 1, seen
