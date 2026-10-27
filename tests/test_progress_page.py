"""tools/progress.py's progress page (owner rulings 3 and 4 of 2026-10-26): a static,
self-contained, deterministic page with one percent bar, the text figures and one function strip
per EXE, the labelled mosaic inline and a short "How it is measured" section. It is written once,
as index.html, so the Pages root serves it. progress.py is loaded by path (it runs under
`python3 -I`); the synthetic tables are test_progress's, the committed-file tests read config/
only (no game bytes)."""

from __future__ import annotations

import dataclasses
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from test_listings import DENOMINATOR, PARTIAL_RULE, RATIO
from test_progress import (
    ASM_PERCENT,
    CONFIG,
    ENTRY_997,
    PROGRESS,
    REPOSITORY,
    SHA,
    TIER_ONE,
    TIER_TWO,
    U_THUNK,
    asm_config,
    item_toml,
    load_progress,
    member,
    synthetic_config,
    tick_config,
    tick_members,
    write_mechanics,
)
from test_treemap import COLORS, SVG_LIMIT

COMMIT_URL = f"{REPOSITORY}/commit/"
WORKFLOW_URL = f"{REPOSITORY}/actions/workflows/pages.yml"
README_URL = f"{REPOSITORY}#progress"
PAGE_LIMIT = SVG_LIMIT + 200_000  # the SVG's bound plus the two strips
# Backlog 999.4 fix #2: the mosaic is a focusable region, so a keyboard user can scroll it.
MOSAIC_REGION = ('<div class="mosaic" tabindex="0" role="region" '
                 'aria-label="Decompilation mosaic, scrolls sideways">')  # fmt: skip
PHONE_QUERY = "@media (max-width: 40rem){"
# Tags that load a resource or run code, and tags whose browser default face is monospace.
FORBIDDEN_TAGS = ("script", "link", "img", "iframe", "object", "embed", "base", "audio", "video",
                  "source", "picture", "noscript", "code", "pre", "kbd", "samp", "tt")  # fmt: skip
# The brief's generic tells, and the owner's no-middle-dot, no-em-dash style.
TELLS = ("url(", "@import", "javascript:", "text-transform", "uppercase", "letter-spacing",
         "monospace", "gradient", "animation", "transition", "@keyframes", "box-shadow",
         "·", "&middot;", "&#183;", "—")  # fmt: skip


def page_module():
    """progress.py with its page API; called in each test body, so a missing name fails the test
    on this assert."""
    progress = load_progress()
    for name in ("render_html", "write_html", "INDEX_HTML"):
        assert hasattr(progress, name), f"progress.py has no {name}"
    return progress


def style_of(page: str) -> str:
    """The inline style sheet: the text between `<style>` and `</style>`."""
    return page.split("<style>\n", 1)[1].split("\n</style>", 1)[0]


class _Tags(HTMLParser):
    """Every start (or self-closing) tag with its attributes, in page order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def tags_of(page: str) -> list[tuple[str, dict[str, str | None]]]:
    parser = _Tags()
    parser.feed(page)
    parser.close()
    return parser.tags


def figures(progress, totals) -> str:
    """The text figures of one EXE, built from derive's totals."""
    return (f"{progress.shield_message(totals.percent)} of code bytes, "
            f"{totals.matched_functions:,} of {totals.total_functions:,} functions matched, "
            f"{totals.partial_functions:,} partial")  # fmt: skip


def bar_html(width: str, *, nonzero: bool = False) -> str:
    """One EXE's percent bar; a non-zero share's segment carries the `nz` class (fix #3)."""
    segment = f'<span class="nz" style="width:{width}">' if nonzero else (
        f'<span style="width:{width}">')
    return f'<div class="bar" aria-hidden="true">{segment}</span></div>'


def commit_line(sha: str) -> str:
    return (f'<p class="meta">Updated from commit <a href="{COMMIT_URL}{sha}">{sha[:7]}</a>'
            f"</p>")  # fmt: skip


# ---- shape ----


def test_page_shape(tmp_path):
    progress = page_module()
    derived = progress.derive(synthetic_config(tmp_path))
    page = progress.render_html(derived, SHA)
    assert page.startswith('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n')
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in page
    assert "<title>ReverseApoc progress</title>" in page
    assert "<h1>X-COM: Apocalypse (DOS) decompilation progress</h1>" in page
    ufo2p, tacp = derived.exes
    assert page.index('<h2 id="exe-ufo2p">UFO2P.EXE</h2>') < page.index(
        '<h2 id="exe-tacp">TACP.EXE</h2>')
    first, second = figures(progress, ufo2p.totals), figures(progress, tacp.totals)
    assert first == "6.5574% of code bytes, 1 of 4 functions matched, 1 partial"
    assert second == "0% of code bytes, 0 of 1 functions matched, 0 partial"
    assert page.index(first) < page.index(second)
    assert page.index(bar_html("6.5574%", nonzero=True)) < page.index(bar_html("0%"))
    assert page.endswith("</main>\n</body>\n</html>\n")


def test_page_embeds_the_mosaic(tmp_path):
    progress = page_module()
    derived = progress.derive(synthetic_config(tmp_path))
    page = progress.render_html(derived, SHA)
    svg = progress.render_svg(derived)
    assert svg in page
    assert page.count("<svg ") == 1
    assert f"{MOSAIC_REGION}\n{svg}</div>\n" in page


def test_page_states_the_commit(tmp_path):
    progress = page_module()
    derived = progress.derive(synthetic_config(tmp_path))
    with_commit = progress.render_html(derived, SHA)
    line = commit_line(SHA)
    assert line in with_commit
    assert progress.render_html(derived) == with_commit.replace(line + "\n", "", 1)
    assert "Updated from commit" not in progress.render_html(derived)


def test_page_how_it_is_measured(tmp_path):
    progress = page_module()
    page = progress.render_html(progress.derive(synthetic_config(tmp_path)), SHA)
    section = page.split("<h2>How it is measured</h2>", 1)[1].split("</main>", 1)[0]
    for needle in (DENOMINATOR, RATIO, PARTIAL_RULE, '<a href="progress.json">progress.json</a>',
                   f'<a href="{WORKFLOW_URL}">report.json</a>',
                   f'<a href="{README_URL}">README</a>'):  # fmt: skip
        assert needle in section, needle


def _check_static(progress, page: str) -> None:
    tags = tags_of(page)
    names = [tag for tag, _attrs in tags]
    assert [t for t in names if t in FORBIDDEN_TAGS] == []
    for tag, attrs in tags:
        bad = [a for a in attrs if a in ("src", "srcset") or a.startswith("on")]
        assert bad == [], (tag, bad)
    assert names.count("style") == 1
    hrefs = {attrs["href"] for tag, attrs in tags if tag == "a"}
    assert hrefs <= {"progress.json", README_URL, WORKFLOW_URL, COMMIT_URL + SHA}, hrefs
    lowered = page.lower()
    assert [tell for tell in TELLS if tell in lowered] == []
    style = style_of(page)
    colors = progress.TREEMAP_COLORS
    for needle in (f"font-family:{progress.FONT};", "font-variant-numeric:tabular-nums",
                   f".bar{{flex:1 1 12rem;height:8px;background:{colors['unmatched']}}}",
                   f".bar span{{display:block;height:100%;background:{colors['matched']}}}",
                   ".mosaic svg{display:block;width:100%;height:auto}"):  # fmt: skip
        assert needle in style, needle


def test_page_is_static_and_self_contained(tmp_path):
    progress = page_module()
    for config in (synthetic_config(tmp_path), CONFIG):
        _check_static(progress, progress.render_html(progress.derive(config), SHA))


def test_page_is_deterministic_and_bounded():
    progress = page_module()
    derived = progress.derive(CONFIG)
    first = progress.render_html(derived, SHA)
    assert first == progress.render_html(progress.derive(CONFIG), SHA)
    assert len(first.encode("utf-8")) < PAGE_LIMIT
    for exe in derived.exes:
        assert figures(progress, exe.totals) in first, exe.label


# ---- the function strip (owner ruling 4, the brief's one memorable element) ----

_STRIP = re.compile(r'<div class="strip" role="img" aria-label="([^"]*)">(.*?)</div>', re.S)
_TICK = re.compile(r'<i class="([a-z]+)"(?: title="([^"]*)")?></i>')
STRIP_KEY = ('<p class="key">Each tick is one game or thunk function, in address order: '
             '<i class="m" aria-hidden="true"></i> matched, <i class="p" aria-hidden="true"></i> '
             'partial, <i class="u" aria-hidden="true"></i> unmatched. Matched and partial ticks '
             "stand taller. The bar is the share of code bytes matched.</p>")  # fmt: skip


def strips(page: str) -> list[tuple[str, list[tuple[str, str | None]]]]:
    """Per strip in page order: its aria-label and the (class, title or None) of its ticks."""
    out = []
    for match in _STRIP.finditer(page):
        ticks = [(cls, title if title else None) for cls, title in _TICK.findall(match[2])]
        assert _TICK.sub("", match[2]) == "", "a strip holds ticks only, no separator"
        out.append((match[1], ticks))
    return out


def strip_module():
    """progress.py with its strip API; a missing name fails the test on this assert."""
    progress = page_module()
    for name in ("TICK_CLASSES", "TICK_WIDTH", "TICK_GAP", "TICK_HEIGHT", "TICK_SHORT",
                 "TICK_ROW_GAP"):  # fmt: skip
        assert hasattr(progress, name), f"progress.py has no {name}"
    return progress


def test_strip_one_tick_per_function(tmp_path):
    progress = strip_module()
    page = progress.render_html(progress.derive(synthetic_config(tmp_path)), SHA)
    found = strips(page)
    assert [ticks for _aria, ticks in found] == [
        [("m", "func_00010000: 16 bytes, matched"),
         ("p", "func_00010010: 32 bytes, partial, best 50.00%"), ("u", None), ("u", None)],
        [("u", None)],
    ]
    for stem in ("ufo2p", "tacp"):
        section = page.split(f'aria-labelledby="exe-{stem}">', 1)[1].split("</section>", 1)[0]
        figures_at = section.index('<p class="figures">')
        assert section.index('<div class="strip" role="img"') > figures_at, stem


def test_strip_aria_labels(tmp_path):
    progress = strip_module()
    page = progress.render_html(progress.derive(synthetic_config(tmp_path)), SHA)
    assert [aria for aria, _ticks in strips(page)] == [
        "UFO2P.EXE, one tick per game and thunk function in address order: 1 matched, "
        "1 partial, 2 unmatched",
        "TACP.EXE, one tick per game and thunk function in address order: 0 matched, "
        "0 partial, 1 unmatched",
    ]


def test_strip_on_committed_csvs():
    progress = strip_module()
    derived = progress.derive(CONFIG)
    found = strips(progress.render_html(derived, SHA))
    assert len(found) == len(derived.exes)
    for exe, (_aria, ticks) in zip(derived.exes, found, strict=True):
        ordered = sorted(exe.functions, key=lambda f: f.start)
        assert [cls for cls, _title in ticks] == [progress.TICK_CLASSES[f.status]
                                                  for f in ordered]  # fmt: skip
        assert sum(cls == "m" for cls, _title in ticks) == exe.totals.matched_functions
        for f, (cls, title) in zip(ordered, ticks, strict=True):
            if cls in ("m", "p"):
                assert title is not None and title.startswith(f.name), (exe.label, f.name)


def test_strip_colours_and_geometry(tmp_path):
    """The tick geometry, and its phone budget: at a 375 px viewport the content is
    375 - 2 * 0.05 * 375 = 337.5 px wide (5vw padding each side, one column below 40rem), so at
    least 100 ticks fit a row and a 1,553-tick strip stays under 300 px tall."""
    progress = strip_module()
    assert progress.TICK_CLASSES == {"matched": "m", "partial": "p", "unmatched": "u"}
    style = style_of(progress.render_html(progress.derive(synthetic_config(tmp_path)), SHA))
    for status, cls in progress.TICK_CLASSES.items():
        assert f"i.{cls}{{background:{progress.TREEMAP_COLORS[status]}}}" in style, status
    geometry = (progress.TICK_WIDTH, progress.TICK_GAP, progress.TICK_HEIGHT, progress.TICK_SHORT,
                progress.TICK_ROW_GAP)  # fmt: skip
    assert geometry == (2, 1, 14, 8, 3)
    width, gap, tall, short, row_gap = geometry
    for rule in (".strip{display:flex;flex-wrap:wrap;align-items:flex-start;"
                 f"gap:{row_gap}px {gap}px;margin-top:.75rem}}",
                 f".strip i,.key i{{flex:none;width:{width}px;height:{tall}px}}",
                 ".key i{display:inline-block}",
                 f".strip .u,.key .u{{height:{short}px;margin-top:{tall - short}px}}"):  # fmt: skip
        assert rule in style, rule
    content = 375 - 2 * 0.05 * 375
    per_row = int((content + gap) // (width + gap))
    assert per_row >= 100
    rows = -(-1553 // per_row)
    assert rows * tall + (rows - 1) * row_gap <= 300


def test_key_explains_the_ticks(tmp_path):
    progress = strip_module()
    page = progress.render_html(progress.derive(synthetic_config(tmp_path)), SHA)
    assert page.count(STRIP_KEY) == 1
    at = page.index(STRIP_KEY)
    assert page.rindex("</section>") < at < page.index("<h2>The mosaic</h2>")


def test_strip_escapes_names(tmp_path):
    progress = strip_module()
    derived = progress.derive(synthetic_config(tmp_path))
    exe = derived.exes[0]
    odd = 'func_"><script>x</script>'
    functions = (dataclasses.replace(exe.functions[0], name=odd), *exe.functions[1:])
    patched = dataclasses.replace(exe, functions=functions)
    page = progress.render_html(dataclasses.replace(derived, exes=(patched, derived.exes[1])), SHA)
    tags = tags_of(page)
    assert "script" not in [tag for tag, _attrs in tags]
    strip = next(i for i, (tag, attrs) in enumerate(tags)
                 if tag == "div" and attrs.get("class") == "strip")  # fmt: skip
    tag, attrs = tags[strip + 1]
    assert tag == "i" and attrs["title"] == f"{odd}: 16 bytes, matched"


def test_strip_partial_tick_shows_its_best_score():
    """A partial tick's title ends with ", best <pct>%", the mosaic cell's best_percent in the
    same 2-decimal form; matched ticks keep "<name>: <size> bytes, matched" and unmatched
    ticks keep no title."""
    progress = strip_module()
    derived = progress.derive(CONFIG)
    found = strips(progress.render_html(derived, SHA))
    titles = {}
    for exe, (_aria, ticks) in zip(derived.exes, found, strict=True):
        ordered = sorted(exe.functions, key=lambda f: f.start)
        for f, (_cls, title) in zip(ordered, ticks, strict=True):
            titles[f.name] = title
            if f.status == progress.MATCHED:
                assert title == f"{f.name}: {f.size:,} bytes, matched", f.name
            elif f.status == progress.UNMATCHED:
                assert title is None, f.name
            else:
                assert title == (f"{f.name}: {f.size:,} bytes, partial, "
                                 f"best {f.best_percent:.2f}%"), f.name  # fmt: skip
    assert titles["func_000C6287"] == "func_000C6287: 53 bytes, partial, best 61.87%"


def test_strip_escapes_partial_names(tmp_path):
    progress = strip_module()
    derived = progress.derive(synthetic_config(tmp_path))
    exe = derived.exes[0]
    odd = 'func_"><script>x</script>&'
    functions = (exe.functions[0], dataclasses.replace(exe.functions[1], name=odd),
                 *exe.functions[2:])  # fmt: skip
    patched = dataclasses.replace(exe, functions=functions)
    page = progress.render_html(dataclasses.replace(derived, exes=(patched, derived.exes[1])), SHA)
    tags = tags_of(page)
    assert "script" not in [tag for tag, _attrs in tags]
    strip = next(i for i, (tag, attrs) in enumerate(tags)
                 if tag == "div" and attrs.get("class") == "strip")  # fmt: skip
    tag, attrs = tags[strip + 2]
    assert tag == "i" and attrs["title"] == f"{odd}: 32 bytes, partial, best 50.00%"


# ---- dark scheme, contrast and phone layout ----


def dark_module():
    """progress.py with its dark tokens; a missing name fails the test on this assert."""
    progress = strip_module()
    for name in ("DARK_SURFACE", "DARK_INK", "DARK_SECONDARY_INK", "MOSAIC_PAINTS"):
        assert hasattr(progress, name), f"progress.py has no {name}"
    return progress


def _luminance(colour: str) -> float:
    """WCAG 2.x relative luminance of a #rrggbb colour."""
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(int(colour[i:i + 2], 16) / 255) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    lighter, darker = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_dark_scheme_swaps_surface_and_ink_only(tmp_path):
    progress = dark_module()
    assert (progress.DARK_SURFACE, progress.DARK_INK, progress.DARK_SECONDARY_INK) == (
        "#161615", "#ecebe7", "#a8a6a0")
    page = progress.render_html(progress.derive(synthetic_config(tmp_path)), SHA)
    style = style_of(page)
    assert (f":root{{--surface:{progress.SURFACE};--ink:{progress.INK};"
            f"--secondary:{progress.SECONDARY_INK};color-scheme:light dark}}") in style
    dark = (f"@media (prefers-color-scheme: dark){{:root{{--surface:{progress.DARK_SURFACE};"
            f"--ink:{progress.DARK_INK};--secondary:{progress.DARK_SECONDARY_INK}}}}}")
    assert dark in style.splitlines()
    assert style.count("prefers-color-scheme") == 1  # no status hue is redefined
    head = page.split("</head>", 1)[0]
    assert '<meta name="color-scheme" content="light dark">' in head
    assert progress.TREEMAP_COLORS == COLORS


def test_palette_contrast():
    """WCAG 2.x contrast. Measured: light ink 19.17, secondary 7.73; dark ink 15.18, secondary
    7.44; on the dark surface matched 3.66, partial 8.36, unmatched 5.04, library 4.10,
    uncovered 12.45 (all >= 3:1 for graphics, WCAG 1.4.11). On the light surface the owner's
    unchanged-hue rule keeps partial at 2.11 and uncovered at 1.42 (the D-50 palette; partial
    ticks also stand taller)."""
    progress = dark_module()
    assert contrast(progress.INK, progress.SURFACE) >= 7.0
    assert contrast(progress.DARK_INK, progress.DARK_SURFACE) >= 7.0
    assert contrast(progress.SECONDARY_INK, progress.SURFACE) >= 4.5
    assert contrast(progress.DARK_SECONDARY_INK, progress.DARK_SURFACE) >= 4.5
    for status, colour in progress.TREEMAP_COLORS.items():
        assert contrast(colour, progress.DARK_SURFACE) >= 3.0, status


def test_mosaic_follows_the_colour_scheme():
    """Every paint of the inline mosaic is a status colour, "none" or a scheme token, and each
    scheme token present is mapped to its CSS variable on the page (9uc's label fill and halo
    stroke included); a later SVG paint with no mapping fails here."""
    progress = dark_module()
    derived = progress.derive(CONFIG)
    root = ET.fromstring(progress.render_svg(derived))
    tokens = {progress.SURFACE: "surface", progress.INK: "ink", progress.SECONDARY_INK: "secondary"}
    allowed = set(progress.TREEMAP_COLORS.values()) | set(tokens) | {"none"}
    pairs = {(attr, element.get(attr)) for element in root.iter() for attr in ("fill", "stroke")
             if element.get(attr) is not None}  # fmt: skip
    assert {value for _attr, value in pairs} <= allowed
    style = style_of(progress.render_html(derived, SHA))
    mapped = [(attr, value) for attr, value in sorted(pairs) if value in tokens]
    assert len(mapped) >= 3, mapped
    for attr, value in mapped:
        assert f'.mosaic [{attr}="{value}"]{{{attr}:var(--{tokens[value]})}}' in style, attr


def test_page_stacks_at_phone_width(tmp_path):
    progress = dark_module()
    page = progress.render_html(progress.derive(synthetic_config(tmp_path)), SHA)
    assert "@media (max-width: 40rem){.exe{grid-template-columns:minmax(0,1fr)}" in style_of(page)
    head = page.split("</head>", 1)[0]
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in head


# ---- backlog 999.4 (06-UI-REVIEW.md fixes #1-#3) ----

_LEGEND = re.compile(r'<ul class="legend">\n(.*?)\n</ul>', re.S)
_LEGEND_ITEM = re.compile(
    r'<li><span class="swatch" style="background:(#[0-9a-f]{6})" aria-hidden="true"></span>'
    r"([^<]*)</li>")


def phone_rules(style: str) -> str:
    """The one style line that holds the 40rem (phone) media block."""
    found = [line for line in style.splitlines() if line.startswith(PHONE_QUERY)]
    assert len(found) == 1, found
    return found[0]


def test_mosaic_scrolls_sideways_on_a_phone(tmp_path):
    """Fix #2: below 40rem the mosaic keeps a 48rem minimum width and its box scrolls sideways,
    instead of scaling the 1200 px SVG to about 31% (labels near 3.5 px)."""
    progress = page_module()
    style = style_of(progress.render_html(progress.derive(synthetic_config(tmp_path)), SHA))
    rules = style.splitlines()
    assert ".mosaic{margin-top:.75rem;overflow-x:auto}" in rules
    assert ".mosaic svg{display:block;width:100%;height:auto}" in rules
    assert ".mosaic svg{min-width:48rem}" in phone_rules(style)
    assert style.count("min-width:48rem") == 1  # the phone block only: wide screens still fit


def test_mosaic_region_is_focusable(tmp_path):
    """Fix #2: the scrolling box takes keyboard focus (tabindex 0) and names itself, so a
    keyboard user can scroll it with the arrow keys; the focus ring is drawn."""
    progress = page_module()
    derived = progress.derive(synthetic_config(tmp_path))
    page = progress.render_html(derived, SHA)
    assert page.count(MOSAIC_REGION) == 1
    assert page.count('<div class="mosaic"') == 1
    assert page.index(MOSAIC_REGION + "\n<svg ") > page.index("<h2>The mosaic</h2>")
    assert ".mosaic:focus-visible{outline:2px solid var(--ink);outline-offset:2px}" in (
        style_of(page).splitlines())


def test_html_legend_above_the_mosaic(tmp_path):
    """Fix #2: an HTML legend, one item per cell status in CELL_STATUSES order with the page's
    status colour and LEGEND_LABELS text, sits right above the mosaic, so it stays readable
    while the SVG scrolls; the SVG keeps its own legend (progress.svg is published alone)."""
    progress = page_module()
    derived = progress.derive(synthetic_config(tmp_path))
    page = progress.render_html(derived, SHA)
    legends = _LEGEND.findall(page)
    assert len(legends) == 1
    items = legends[0].split("\n")
    assert [_LEGEND_ITEM.fullmatch(item).groups() for item in items] == [
        (progress.TREEMAP_COLORS[status], progress._xml(progress.LEGEND_LABELS[status]))
        for status in progress.CELL_STATUSES]
    legend_at = page.index('<ul class="legend">')
    assert page.index("<h2>The mosaic</h2>") < legend_at < page.index(MOSAIC_REGION)
    assert page[legend_at:page.index(MOSAIC_REGION)].endswith("</ul>\n")
    svg = progress.render_svg(derived)
    for status in progress.CELL_STATUSES:
        assert progress._xml(progress.LEGEND_LABELS[status]) in svg, status
    rules = style_of(page).splitlines()
    assert any(rule.startswith(".legend{display:flex;flex-wrap:wrap;") for rule in rules)


_DETAILS = re.compile(r'<details><summary>Matched and partial functions \((\d+)\)</summary><ul>\n'
                      r"(.*?)\n</ul></details>", re.S)  # fmt: skip
_ITEM = re.compile(r"<li>([^<]*)</li>")


def exe_section(page: str, stem: str) -> str:
    return page.split(f'aria-labelledby="exe-{stem}">', 1)[1].split("</section>", 1)[0]


def listed(section: str) -> tuple[int, list[str]] | None:
    """The section's tooltip list: its summary count and its items (raw, still escaped)."""
    found = _DETAILS.findall(section)
    assert len(found) <= 1, found
    if not found:
        return None
    count, body = found[0]
    items = body.split("\n")
    assert [_ITEM.fullmatch(item) is not None for item in items] == [True] * len(items), items
    return int(count), [_ITEM.fullmatch(item)[1] for item in items]


def expected_items(progress, exe) -> list[str]:
    ordered = sorted(exe.functions, key=lambda f: f.start)
    return [progress._xml(progress._function_title(f)) for f in ordered
            if f.status in (progress.MATCHED, progress.PARTIAL)]  # fmt: skip


def test_details_lists_matched_and_partial(tmp_path):
    """Fix #1: per EXE, after its strip, a <details> lists every matched and partial function in
    address order with its tooltip text, so keyboard and touch users reach every tooltip."""
    progress = page_module()
    page = progress.render_html(progress.derive(synthetic_config(tmp_path)), SHA)
    section = exe_section(page, "ufo2p")
    assert listed(section) == (2, ["func_00010000: 16 bytes, matched",
                                   "func_00010010: 32 bytes, partial, best 50.00%"])  # fmt: skip
    assert section.index('<div class="strip" role="img"') < section.index("<details>")
    assert 'title="func_00010000: 16 bytes, matched"' in section  # the tick tooltips stay


def test_details_on_committed_csvs():
    progress = page_module()
    derived = progress.derive(CONFIG)
    page = progress.render_html(derived, SHA)
    for exe in derived.exes:
        items = expected_items(progress, exe)
        want = (len(items), items) if items else None
        assert listed(exe_section(page, exe.stem)) == want, exe.label
        t = exe.totals
        assert len(items) == t.matched_functions + t.partial_functions, exe.label


def test_details_absent_when_none(tmp_path):
    progress = page_module()
    page = progress.render_html(progress.derive(synthetic_config(tmp_path)), SHA)
    assert "<details" not in exe_section(page, "tacp")
    assert page.count("<details>") == 1


def test_details_escapes_names(tmp_path):
    progress = page_module()
    derived = progress.derive(synthetic_config(tmp_path))
    exe = derived.exes[0]
    odd = 'func_"><script>x</script>&'
    functions = (exe.functions[0], dataclasses.replace(exe.functions[1], name=odd),
                 *exe.functions[2:])  # fmt: skip
    patched = dataclasses.replace(exe, functions=functions)
    page = progress.render_html(dataclasses.replace(derived, exes=(patched, derived.exes[1])), SHA)
    assert "script" not in [tag for tag, _attrs in tags_of(page)]
    found = listed(exe_section(page, "ufo2p"))
    assert found is not None, "no matched and partial list"
    items = found[1]
    assert items[1] == progress._xml(f"{odd}: 32 bytes, partial, best 50.00%")
    assert "&lt;script&gt;" in items[1] and "&amp;" in items[1]


def test_nonzero_bar_has_min_width(tmp_path):
    """Fix #3: a non-zero share draws a segment at least 2 px wide, so a tiny matched share is
    visible; a zero share draws no `nz` segment. The figures text is unchanged."""
    progress = page_module()
    derived = progress.derive(synthetic_config(tmp_path))
    ufo2p = derived.exes[0]
    # 16 matched bytes of 4,000: pad the first unit's uncovered bytes up to that denominator.
    extra = 4000 - ufo2p.totals.denominator_bytes
    tiny = dataclasses.replace(ufo2p, uncovered=(ufo2p.uncovered[0] + extra,
                                                 *ufo2p.uncovered[1:]))  # fmt: skip
    assert progress.shield_message(tiny.totals.percent) == "0.4%"
    page = progress.render_html(dataclasses.replace(derived, exes=(tiny, derived.exes[1])), SHA)
    assert bar_html("0.4%", nonzero=True) in exe_section(page, "ufo2p")
    tacp = exe_section(page, "tacp")
    assert bar_html("0%") in tacp and 'class="nz"' not in tacp
    assert figures(progress, tiny.totals) in page
    rules = style_of(page).splitlines()
    assert ".bar .nz{min-width:2px}" in rules
    assert rules.index(".bar .nz{min-width:2px}") > rules.index(
        f".bar span{{display:block;height:100%;background:{progress.TREEMAP_COLORS['matched']}}}")


# ---- publication ----


def test_main_writes_the_page(tmp_path):
    progress = page_module()
    config = synthetic_config(tmp_path)
    out, again = tmp_path / "out", tmp_path / "again"
    for target in (out, again):
        assert progress.main(["--config", str(config), "--out", str(target),
                              "--commit", SHA]) == 0  # fmt: skip
    data = (out / progress.INDEX_HTML).read_bytes()
    assert data == progress.render_html(progress.derive(config), SHA).encode("utf-8")
    assert data.endswith(b"</html>\n") and b"\r" not in data
    assert (again / progress.INDEX_HTML).read_bytes() == data
    assert not list(Path(out).glob(".*.tmp"))


def test_main_writes_the_page_once_at_the_site_root(tmp_path):
    """Owner ruling of 2026-10-26: the page is written once, as index.html, which the Pages root
    (linked by the README, .recomp.json and the docs/listings.md drafts) serves; progress.html,
    a byte-identical duplicate, is no longer written."""
    progress = page_module()
    assert progress.INDEX_HTML == "index.html"
    assert not hasattr(progress, "PROGRESS_HTML")
    config = synthetic_config(tmp_path)
    for name, commit in (("with", SHA), ("without", None)):
        out = tmp_path / name
        extra = [] if commit is None else ["--commit", commit]
        assert progress.main(["--config", str(config), "--out", str(out), *extra]) == 0
        page = progress.render_html(progress.derive(config), commit).encode("utf-8")
        assert (out / "index.html").read_bytes() == page, name
        assert not (out / "progress.html").exists(), name
        assert sorted(path.name for path in out.glob("*.html")) == ["index.html"], name


def test_script_writes_the_page_isolated(tmp_path):
    """The committed CSVs, as CI runs it: `python3 -I tools/progress.py --out DIR --commit SHA`."""
    out = tmp_path / "site"
    done = subprocess.run([sys.executable, "-I", str(PROGRESS), "--out", str(out), "--commit",
                           SHA], capture_output=True, text=True, timeout=120)  # fmt: skip
    assert done.returncode == 0, done.stderr
    data = (out / "index.html").read_bytes()
    assert data.startswith(b"<!DOCTYPE html>")
    for needle in (b"UFO2P.EXE", b"TACP.EXE", f"{COMMIT_URL}{SHA}".encode("ascii")):
        assert needle in data, needle
    assert not (out / "progress.html").exists()


# ---- the mechanics coverage section (DEC-05; D-05, D-22; plan 07-15) ----

COVERAGE_HEADING = "<h2>Mechanics coverage</h2>"
_ITEMS = re.compile(r'<ul class="items">\n(.*?)\n</ul>', re.S)
_COV_ITEM = re.compile(r"<li>(.*?)</li>", re.S)
_COV_BAR = re.compile(r'<div class="cov" aria-hidden="true">(.*?)</div>', re.S)
_SEGMENT = re.compile(r'<span class="([mpu]) nz" style="width:([0-9.]+%)"></span>')


def coverage_items(page: str) -> list[str]:
    """The raw <li> bodies of the coverage section's item list."""
    lists = _ITEMS.findall(page)
    assert len(lists) == 1, lists
    return _COV_ITEM.findall(lists[0])


def segments(body: str) -> list[tuple[str, str]]:
    """The (class, width) of each segment of the one coverage bar in `body`."""
    bars = _COV_BAR.findall(body)
    assert len(bars) == 1, bars
    found = _SEGMENT.findall(bars[0])
    assert _SEGMENT.sub("", bars[0]) == "", "a coverage bar holds segments only"
    return found


def test_coverage_section_markup(tmp_path):
    """The `Mechanics coverage` section sits after the EXE sections and their key, before the
    mosaic: one <li> per `in` item, its text first (label, must-match and full-closure figures,
    the tier and its sign-off state), then an aria-hidden bar of matched, partial and unmatched
    segments by function count, each non-zero one with the 2 px `nz` minimum. No new link."""
    progress = page_module()
    config = tick_config(tmp_path)
    derived = progress.derive(config)
    assert hasattr(progress, "derive_mechanics"), "progress.py has no derive_mechanics"
    page = progress.render_html(derived, SHA, mechanics=progress.derive_mechanics(config, derived))
    assert page.count(COVERAGE_HEADING) == 1
    at = page.index(COVERAGE_HEADING)
    mosaic = page.index("<h2>The mosaic</h2>")
    assert page.rindex("</section>") < page.index(STRIP_KEY) < at < mosaic
    (body,) = coverage_items(page)
    assert body.startswith("#997 Tick rate: must match 1 of 3 functions matched, 1 partial"), body
    assert "full closure 1 of 5 functions matched, 1 partial" in body
    assert "Tier 1: located, not signed off" in body
    assert body.index("full closure") < body.index('<div class="cov"')
    assert segments(body) == [("m", "33.3333%"), ("p", "33.3333%"), ("u", "33.3333%")]
    _check_static(progress, page)
    hrefs = {attrs["href"] for tag, attrs in tags_of(page) if tag == "a"}
    assert hrefs == {attrs["href"] for tag, attrs in tags_of(progress.render_html(derived, SHA))
                     if tag == "a"}  # fmt: skip
    assert ".cov .nz{min-width:2px}" in style_of(page).splitlines()


def coverage_page(progress, config) -> str:
    derived = progress.derive(config)
    return progress.render_html(derived, SHA, mechanics=progress.derive_mechanics(config, derived))


def test_zero_member_item_markup(tmp_path):
    """DEC-05 empty: an item with no rows reads 0 of 0 and its bar has no segment."""
    progress = page_module()
    config = synthetic_config(tmp_path)
    write_mechanics(config, TIER_ONE, item_toml("997", "Tick rate"),
                    item_toml("263-2", "Not reached yet"), ENTRY_997,
                    members=tick_members())  # fmt: skip
    bodies = coverage_items(coverage_page(progress, config))
    labels = [body.split(":", 1)[0] for body in bodies]
    assert labels == ["#263-2 Not reached yet", "#997 Tick rate"]
    assert bodies[0].startswith("#263-2 Not reached yet: must match 0 of 0 functions matched, "
                                "0 partial (0% of 0 bytes matched)")  # fmt: skip
    assert segments(bodies[0]) == []


def test_located_tier_text(tmp_path):
    """D-05: the page names each tier's state and sign-off, and each item repeats its tier's."""
    progress = page_module()
    config = synthetic_config(tmp_path)
    agents = ("263-1",)
    members = [*tick_members()[:3],
               member("ufo2p", U_THUNK, agents, agents, tiers=(2,), via="entry")]  # fmt: skip
    entry = ENTRY_997.replace('"997"', '"263-1"').replace("0x00010000", "0x0001008C")
    write_mechanics(config, TIER_ONE, TIER_TWO, item_toml("997", "Tick rate"),
                    item_toml("263-1", "Agent training", tier=2), ENTRY_997, entry,
                    members=members)  # fmt: skip
    page = coverage_page(progress, config)
    bodies = coverage_items(page)
    assert "Tier 1: located, not signed off." in bodies[0]
    assert "Tier 2: located, signed off by Owner on 2026-10-27." in bodies[1]
    tiers = re.findall(r'<ul class="tiers">\n(.*?)\n</ul>', page, re.S)
    assert len(tiers) == 1
    lines = _COV_ITEM.findall(tiers[0])
    assert lines[0].startswith("Tier 1 (Tick rate and agent training): located, not signed off;")
    assert lines[1].startswith("Tier 2 (The rest of the agents): located, signed off by Owner")


def test_duplicates_listed_once_on_the_page(tmp_path):
    progress = page_module()
    config = synthetic_config(tmp_path)
    write_mechanics(config, TIER_ONE, item_toml("997", "Tick rate"),
                    item_toml("264-1", "Tick rate again", scope="duplicate", duplicate_of="997"),
                    ENTRY_997, members=tick_members())  # fmt: skip
    page = coverage_page(progress, config)
    assert page.count("#264-1") == 1
    listed = '<ul class="duplicates">\n<li>#264-1 Tick rate again: a duplicate of #997</li>\n</ul>'
    assert listed in page
    assert len(coverage_items(page)) == 1


ASM_TICKS = [("m", "func_00010000: 16 bytes, matched"),
             ("p", "func_00010010: 32 bytes, partial, best 50.00%"), ("l", None), ("u", None)]


def test_assembler_group_on_the_page(tmp_path):
    """D-23: the signed asm rows leave the EXE's percent; the page states them outside the
    percentage, the strip draws them in the library colour at their address, the mosaic as
    library cells, and the legend reads library or assembler."""
    progress = page_module()
    config = asm_config(tmp_path)
    out = tmp_path / "out"
    assert progress.main(["--config", str(config), "--out", str(out), "--commit", SHA]) == 0
    page = (out / "index.html").read_text(encoding="utf-8")
    section = exe_section(page, "ufo2p")
    assert (f"{ASM_PERCENT}% of code bytes, 1 of 3 functions matched, 1 partial; 1 assembler "
            "function (64 bytes) outside the percentage") in section  # fmt: skip
    found = strips(page)
    assert found[0][1] == ASM_TICKS
    assert found[0][0].endswith("1 matched, 1 partial, 1 unmatched, 1 assembler")
    assert found[1][1] == [("u", None)] and not found[1][0].endswith("assembler")
    colors = progress.TREEMAP_COLORS
    style = style_of(page).splitlines()
    assert f"i.l{{background:{colors['library']}}}" in style
    assert progress.LEGEND_LABELS["library"] == "library or assembler, not decompiled"
    assert "<li>" + '<span class="swatch" style="background:' + colors["library"] + (
        '" aria-hidden="true"></span>library or assembler, not decompiled</li>') in page
    root = ET.fromstring((out / "progress.svg").read_text(encoding="utf-8"))
    fills = [r.get("fill") for r in root.iter("{http://www.w3.org/2000/svg}rect")]
    assert fills.count(colors["library"]) == 2  # the runtime row and the asm row
    assert "assembler" in page.split('<p class="key">', 2)[2].split("</p>", 1)[0]
    _check_static(progress, page)


def test_page_without_assembler_has_no_assembler_markup(tmp_path):
    progress = page_module()
    page = progress.render_html(progress.derive(synthetic_config(tmp_path)), SHA)
    assert "assembler function" not in page and 'class="l"' not in page
    assert "i.l{" not in style_of(page)


def test_measured_states_the_assembler_group(tmp_path):
    """Ruling F37: How it is measured says which artifacts leave the signed asm rows out of the
    percentage and that the DecompHub feed keeps them."""
    progress = page_module()
    page = progress.render_html(progress.derive(synthetic_config(tmp_path)), SHA)
    section = page.split("<h2>How it is measured</h2>", 1)[1].split("</main>", 1)[0]
    for needle in ("asm-functions.csv", "progress.json", "report.json", "badges",
                   "decomphub.progress.json still counts them"):  # fmt: skip
        assert needle in section, needle
    assert DENOMINATOR in section
