"""tools/progress.py's mosaic (RPT-02, D-26, D-50): progress.svg, a squarified treemap nested
EXE, then unit, then one cell per function sized by bytes, in five fixed colours. The README
embeds it from GitHub Pages. progress.py is loaded by path (it runs under `python3 -I`); the
synthetic tables are test_progress's, the committed-file tests read config/ only (no game
bytes)."""

from __future__ import annotations

import random
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import pytest

from test_progress import (
    CONFIG,
    T_GAME,
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


def test_treemap_titles_on_unit_groups_and_matched_cells_only(tmp_path):
    progress = treemap()
    root = parse(progress.render_svg(progress.derive(synthetic_config(tmp_path))))
    for group in root.findall(f".//{SVG_NS}g[@data-unit]"):
        title = group.find(f"{SVG_NS}title")
        assert title is not None and group.get("data-unit") in title.text
        for rect in cells(group):
            titled = rect.find(f"{SVG_NS}title")
            if rect.get("fill") == COLORS["matched"]:
                assert titled is not None and U_MATCHED.name in titled.text
            else:
                assert titled is None


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
