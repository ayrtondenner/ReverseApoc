"""tools/progress.py's progress.html (owner rulings 3 and 4 of 2026-10-26): a static,
self-contained, deterministic page with one percent bar, the text figures and one function strip
per EXE, the labelled mosaic inline and a short "How it is measured" section. It is also written
as index.html, so the Pages root serves it. progress.py is loaded by path (it runs under
`python3 -I`); the synthetic tables are test_progress's, the committed-file tests read config/
only (no game bytes)."""

from __future__ import annotations

import dataclasses
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

from test_listings import DENOMINATOR, PARTIAL_RULE, RATIO
from test_progress import CONFIG, PROGRESS, REPOSITORY, SHA, load_progress, synthetic_config
from test_treemap import SVG_LIMIT

COMMIT_URL = f"{REPOSITORY}/commit/"
WORKFLOW_URL = f"{REPOSITORY}/actions/workflows/pages.yml"
README_URL = f"{REPOSITORY}#progress"
PAGE_LIMIT = SVG_LIMIT + 200_000  # the SVG's bound plus the two strips
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
    for name in ("render_html", "write_html", "PROGRESS_HTML", "INDEX_HTML"):
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
    bar = '<div class="bar" aria-hidden="true"><span style="width:{}"></span></div>'
    assert page.index(bar.format("6.5574%")) < page.index(bar.format("0%"))
    assert page.endswith("</main>\n</body>\n</html>\n")


def test_page_embeds_the_mosaic(tmp_path):
    progress = page_module()
    derived = progress.derive(synthetic_config(tmp_path))
    page = progress.render_html(derived, SHA)
    svg = progress.render_svg(derived)
    assert svg in page
    assert page.count("<svg ") == 1
    assert f'<div class="mosaic">\n{svg}</div>\n' in page


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
        [("m", "func_00010000: 16 bytes, matched"), ("p", "func_00010010: 32 bytes, partial"),
         ("u", None), ("u", None)],
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


# ---- publication ----


def test_main_writes_the_page(tmp_path):
    progress = page_module()
    config = synthetic_config(tmp_path)
    out, again = tmp_path / "out", tmp_path / "again"
    for target in (out, again):
        assert progress.main(["--config", str(config), "--out", str(target),
                              "--commit", SHA]) == 0  # fmt: skip
    data = (out / progress.PROGRESS_HTML).read_bytes()
    assert data == progress.render_html(progress.derive(config), SHA).encode("utf-8")
    assert data.endswith(b"</html>\n") and b"\r" not in data
    assert (again / progress.PROGRESS_HTML).read_bytes() == data
    assert not list(Path(out).glob(".*.tmp"))


def test_main_publishes_the_page_at_the_site_root(tmp_path):
    """Orchestrator ruling of 2026-10-26: the same bytes as index.html, so the Pages root (which
    .recomp.json's Progress link and the docs/listings.md drafts point at) serves the page."""
    progress = page_module()
    assert progress.INDEX_HTML == "index.html"
    config = synthetic_config(tmp_path)
    for name, extra in (("with", ["--commit", SHA]), ("without", [])):
        out = tmp_path / name
        assert progress.main(["--config", str(config), "--out", str(out), *extra]) == 0
        assert (out / "index.html").read_bytes() == (out / "progress.html").read_bytes(), name


def test_script_writes_the_page_isolated(tmp_path):
    """The committed CSVs, as CI runs it: `python3 -I tools/progress.py --out DIR --commit SHA`."""
    out = tmp_path / "site"
    done = subprocess.run([sys.executable, "-I", str(PROGRESS), "--out", str(out), "--commit",
                           SHA], capture_output=True, text=True, timeout=120)  # fmt: skip
    assert done.returncode == 0, done.stderr
    data = (out / "progress.html").read_bytes()
    assert data.startswith(b"<!DOCTYPE html>")
    for needle in (b"UFO2P.EXE", b"TACP.EXE", f"{COMMIT_URL}{SHA}".encode("ascii")):
        assert needle in data, needle
    assert (out / "index.html").read_bytes() == data
