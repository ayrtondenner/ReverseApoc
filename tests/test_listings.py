"""Listing metadata the repo publishes itself (RPT-05, D-29, D-31, D-32): `.recomp.json` for
recomp.fyi, README's Progress section and the DecompHub verification file. No network: the
recomp.fyi schema is pinned below, because CI cannot fetch it."""

from __future__ import annotations

import json
import re

import pytest

from conftest import REPO_ROOT

# from recomp.fyi/schema/v1.json, 2026-10-24 (additionalProperties: false)
RECOMP_PROPERTIES = frozenset(
    {
        "$schema",
        "game",
        "wikidata",
        "system",
        "type",
        "original",
        "project",
        "status",
        "targets",
        "toolchain",
        "approach",
        "maintainers",
        "links",
        "help",
        "tags",
        "notes",
    }
)
# from recomp.fyi/schema/v1.json, 2026-10-24 (the `status` enum)
RECOMP_STATUSES = frozenset(
    {"exploring", "in-progress", "playable", "released", "complete", "paused", "unknown"}
)
# from recomp.fyi/schema/v1.json, 2026-10-24 (`links[].url` and `maintainers[].link` pattern)
HTTPS = "https://"

PAGES = "https://ayrtondenner.github.io/ReverseApoc/"
RECOMP_JSON = REPO_ROOT / ".recomp.json"
SPIKE_006 = REPO_ROOT / ".planning" / "spikes" / "006-decompwtf-fork-stub" / "README.md"
# The LE loader Phase 5 dropped (D-03); the notes must not name it (D-32, D-41).
DROPPED_LOADER = "retrokit"

README = REPO_ROOT / "README.md"
VERIFICATION = REPO_ROOT / "docs" / "DECOMPHUB_VERIFICATION.md"
REPOSITORY = "https://github.com/ayrtondenner/ReverseApoc"
# The file names published since Phase 1 and kept by D-26.
PAGES_FILES = ("progress-shield.json", "progress.svg", "progress.json")
# The mosaic's categories (D-26, D-50), each defined as a bold `**name**:` list item.
CATEGORIES = ("matched", "partial", "unmatched", "library", "uncovered")
# D-50: the uncovered bytes are counted in the denominator, as tools/progress.py does.
DENOMINATOR = "over all game and thunk bytes plus the uncovered bytes"
# What the figures are computed from (tools/progress.py inputs) and what they leave out.
PROGRESS_NEEDLES = ("status.csv", "functions.csv", "units.csv", "data-in-code", "3-byte")
# Stale Toolchain summary wording from Phase 1 (DI-25).
STALE_TOOLCHAIN = ("working hypothesis", "settled in Phase 4")


def _recomp() -> dict:
    return json.loads(RECOMP_JSON.read_text(encoding="utf-8"))


def _schema_problems(doc: dict) -> list[str]:
    """What breaks the pinned recomp.fyi v1 shape (empty = it validates)."""
    problems = [f"key {key!r} is not in schema v1" for key in sorted(set(doc) - RECOMP_PROPERTIES)]
    if doc.get("status") not in RECOMP_STATUSES:
        problems.append(f"status {doc.get('status')!r} is not in the v1 enum")
    return problems


def _non_https(doc: dict) -> list[str]:
    """Every links[].url and maintainers[].link that does not start with https://."""
    urls = [link.get("url", "") for link in doc.get("links", [])]
    urls += [person.get("link", "") for person in doc.get("maintainers", [])]
    return [url for url in urls if not url.startswith(HTTPS)]


def _spike_006_verdict() -> str:
    match = re.search(r"^verdict: (\S+)$", SPIKE_006.read_text(encoding="utf-8"), re.M)
    assert match, "spike 006 has no verdict line"
    return match[1]


def _stale_note_phrases(notes: str, verdict: str) -> list[str]:
    """Phrases the notes may not carry: the dropped loader, and decomp.wtf unless spike 006
    VALIDATED fork mode."""
    stale = [DROPPED_LOADER] if DROPPED_LOADER in notes.lower() else []
    if verdict != "VALIDATED" and "decomp.wtf" in notes.lower():
        stale.append("decomp.wtf")
    return stale


def test_recomp_json_keys_and_enum():
    assert _schema_problems(_recomp()) == []


def test_recomp_json_links_are_https():
    assert _non_https(_recomp()) == []


def test_recomp_json_lists_the_progress_page():
    assert PAGES in [link.get("url") for link in _recomp().get("links", [])]


def test_recomp_json_notes_match_the_pipeline():
    doc = _recomp()
    assert "ai-assisted" in doc.get("tags", [])
    assert _stale_note_phrases(doc.get("notes", ""), _spike_006_verdict()) == []


@pytest.mark.parametrize(
    ("planted", "check"),
    [
        ({"status": "exploring", "website": "https://x"}, _schema_problems),
        ({"status": "wip"}, _schema_problems),
        ({"links": [{"label": "a", "url": "http://x"}]}, _non_https),
        ({"maintainers": [{"name": "a", "link": "github.com/a"}]}, _non_https),
    ],
)
def test_recomp_checks_catch_planted_defects(planted, check):
    # Each check is only worth something if it can fail: a key outside the schema, a status
    # outside the enum and a non-https link are all reported.
    assert check(planted) != []


@pytest.mark.parametrize(
    ("notes", "verdict", "stale"),
    [
        ("Ghidra with retrokit", "INVALIDATED", ["retrokit"]),
        ("decomp.wtf fork mode", "INVALIDATED", ["decomp.wtf"]),
        ("decomp.wtf fork mode", "VALIDATED", []),
    ],
)
def test_note_check_follows_the_spike_verdict(notes, verdict, stale):
    assert _stale_note_phrases(notes, verdict) == stale


def _section(text: str, heading: str) -> str:
    """The body of `## <heading>` up to the next level-2 heading."""
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, f"no '## {heading}' section"
    return match[1]


def _sentences(text: str) -> int:
    """Sentences in the prose of a Markdown file: headings are skipped, and a full stop only
    ends a sentence before whitespace or the end, so dots inside URLs do not count."""
    prose = " ".join(line for line in text.splitlines() if not line.startswith("#"))
    return len(re.findall(r"[.!?](?=\s|$)", prose.strip()))


def test_readme_progress_section():
    # DI-08, D-26, D-29, D-50: the Phase 6 placeholder gives way to what the figures count.
    section = _section(README.read_text(encoding="utf-8"), "Progress")
    assert [name for name in PAGES_FILES if f"{PAGES}{name}" not in section] == []
    assert "[Progress data](decomphub.progress.json)" in section
    # A bold `**name**:` label, so "matched" is not satisfied by "unmatched".
    undefined = [name for name in CATEGORIES if not re.search(rf"\*\*{name}\*\*:", section)]
    assert undefined == []
    assert [needle for needle in PROGRESS_NEEDLES if needle not in section] == []
    assert "Placeholder" not in section
    assert "coming in Phase 6" not in section


def test_readme_percentage_counts_uncovered_bytes():
    # D-50: tools/progress.py divides by game + thunk + uncovered bytes.
    section = _section(README.read_text(encoding="utf-8"), "Progress")
    assert DENOMINATOR in section


def test_readme_progress_makes_no_stub_claim():
    # Only units with C are compiled; every other function keeps the original EXE's bytes
    # through the splice, so "unmatched" must not be described as an INCLUDE_ASM stub.
    section = _section(README.read_text(encoding="utf-8"), "Progress")
    assert "INCLUDE_ASM" not in section
    assert "original" in _category_line(section, "unmatched")


def _category_line(section: str, name: str) -> str:
    match = re.search(rf"^- \*\*{name}\*\*:.*$", section, re.M)
    assert match, f"no '**{name}**:' item"
    return match[0]


def _unannotated_agent_lines(section: str) -> list[str]:
    """Lines that name decomp.wtf or an MCP server without the Phase 6 outcome: spike 006
    INVALIDATED fork mode (06-01) and there is no MCP server (D-44). The retrokit row carries
    its own D-41 annotation ("not used")."""
    hits = []
    for line in section.splitlines():
        if "decomp.wtf" in line and "spike 006" not in line:
            hits.append(line)
        elif "MCP" in line and "D-44" not in line and "not used" not in line:
            hits.append(line)
    return hits


def test_readme_approach_annotates_the_agent_layer():
    section = _section(README.read_text(encoding="utf-8"), "Approach")
    assert _unannotated_agent_lines(section) == []


@pytest.mark.parametrize(
    ("line", "flagged"),
    [
        ("- decomp.wtf v0.10.6 in fork mode", True),
        ("- the fallback is an MCP server", True),
        ("- decomp.wtf fork mode (not used: spike 006 INVALIDATED it; no MCP, D-44)", False),
        ("| retrokit | MCP server (not used: lastonesky) |", False),
    ],
)
def test_agent_line_check_catches_unannotated_lines(line, flagged):
    assert bool(_unannotated_agent_lines(line)) is flagged


def test_readme_toolchain_summary_is_current():
    # DI-25: 10.5, 10.6 and 11.0 stay tied on game code after the two Phase 5 leaf matches.
    section = _section(README.read_text(encoding="utf-8"), "Toolchain summary")
    assert [phrase for phrase in STALE_TOOLCHAIN if phrase in section] == []
    assert "tied" in section
    assert "docs/toolchain.md" in section


def test_decomphub_verification_file():
    # D-31: a short ownership statement the owner cites when filing the maintainer claim.
    assert VERIFICATION.is_file()
    text = VERIFICATION.read_text(encoding="utf-8")
    assert 1 <= _sentences(text) <= 3
    assert "ayrtondenner" in text
    assert REPOSITORY in text
    assert "decomphub.progress.json" in text


@pytest.mark.parametrize(
    ("text", "count"),
    [
        ("# Title\n\nOne. Two.\n", 2),
        ("See https://example.org/a/b and decomphub.progress.json.\n", 1),
        ("One. Two. Three. Four.", 4),
    ],
)
def test_sentence_count_skips_headings_and_url_dots(text, count):
    assert _sentences(text) == count
