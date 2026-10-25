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
