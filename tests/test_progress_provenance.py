"""tools/progress.py's provenance split (todo progress-provenance-split): every function matched
in HEAD's status tables classed by the trailers of the commit that last matched it, the way
`reverseapoc stats` classes it (unattended, human-hints, tool, human-written; the flag-approved
subset apart), and credited to the model that made it (the timeline's credit rule), per EXE and
combined, in progress.json and on the page. The git layer is tested on a synthetic repository
against reverseapoc.stats on the same history. No game bytes: the tables are made up."""

from __future__ import annotations

import json
import re
from pathlib import Path

from reverseapoc import stats
from reverseapoc.status import MATCHED, PARTIAL, StatusRow, format_status
from test_driver import _git, _git_env
from test_progress import (
    DAY,
    SHA,
    T_GAME,
    U_MATCHED,
    U_PARTIAL,
    U_UNMATCHED,
    load_progress,
    synthetic_config,
)

UFO, TACP = "ufo2p", "tacp"
HAIKU = "Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>"
OPUS = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
GLM = "Co-Authored-By: GLM-5.3 <noreply@z.ai>"
DRIVE = "Matched-By: reverseapoc drive"
HINTS = "Match-Hints: the owner's notes"
FLAGS = "Flags-Approved-By: owner (F-0001, 2026-10-05)"
TWINS = "Matched-By: reverseapoc twins"
LIFT = "Matched-By: reverseapoc lift"
_SECTION = re.compile(r'<section class="provenance" aria-labelledby="provenance">(.*?)</section>',
                      re.S)  # fmt: skip


def provenance_module():
    """progress.py with its provenance API; a missing name fails the test on this assert."""
    progress = load_progress()
    for name in ("PROVENANCE_CLASSES", "provenance_class", "MatchEvent", "build_provenance",
                 "load_provenance", "build_provenance_doc"):  # fmt: skip
        assert hasattr(progress, name), f"progress.py has no {name}"
    return progress


def pairs(*trailers: str) -> tuple[tuple[str, str], ...]:
    return tuple(tuple(part.strip() for part in t.split(":", 1)) for t in trailers)


def test_the_classes_are_stats_classes():
    """The same four classes, by the same trailer rule, flag approval apart (DEC-07, R4;
    todo stats-tool-class)."""
    progress = provenance_module()
    assert progress.PROVENANCE_CLASSES == stats.CLASSES
    for trailers in [(DRIVE, HAIKU), (DRIVE, HINTS, OPUS), (OPUS,), (), (DRIVE, OPUS, FLAGS),
                     (LIFT, FLAGS), ("matched-by: reverseapoc drive",), (TWINS,), (TWINS, OPUS),
                     (DRIVE, LIFT), (DRIVE, HINTS, TWINS), ("Matched-By: reverseapoc twins2",),
                     ("Matched-By: reverseapoc search", FLAGS),
                     ("Matched-By: claude subagent (spike 011)", FLAGS),
                     (DRIVE, "Matched-By: z-ai/glm-5.3", GLM), ("Match-Hints: x", OPUS)]:
        assert progress.provenance_class(pairs(*trailers)) == stats.classify(pairs(*trailers)), (
            trailers)


def test_matched_starts_reads_any_hex_start_as_driver_does():
    """A past status.csv is read the way driver.matched_starts reads it (the agreement with
    stats rests on it): any column order, any hex spelling of the start."""
    from reverseapoc import driver

    progress = provenance_module()
    text = ("# a comment\nstatus,start,name\nmatched,0x0001abcd,f\nmatched,0x10,g\n"
            "partial,0x00020000,h\nmatched,zz,i\n")  # fmt: skip
    assert progress._matched_starts(text) == driver.matched_starts(text.encode("utf-8"))
    assert progress._matched_starts(None) == frozenset()


def test_the_split_counts_each_matched_function_by_its_latest_match(tmp_path):
    """Per EXE: each function status.csv calls matched, by its latest match event; a function
    matched with no event in the history is unclassed, and an event of a function no longer
    matched counts for nothing. The classes and unclassed add up to status.csv's matched."""
    progress = provenance_module()
    config = synthetic_config(tmp_path)
    (config / UFO / "status.csv").write_text(format_status([
        StatusRow(U_MATCHED.start, U_MATCHED.name, U_MATCHED.unit, MATCHED, 100.0, 1, SHA, DAY),
        StatusRow(U_PARTIAL.start, U_PARTIAL.name, U_PARTIAL.unit, MATCHED, 100.0, 1, SHA, DAY),
    ]), encoding="utf-8")  # fmt: skip
    derived = progress.derive(config)
    event = progress.MatchEvent
    events = [event(UFO, U_MATCHED.start, "human-written", False, "Claude Opus 5.5"),
              event(UFO, U_MATCHED.start, "unattended", True, "Claude Haiku 5.5"),
              event(UFO, U_UNMATCHED.start, "unattended", False, "Claude Opus 5.5"),
              event(TACP, T_GAME.start, "unattended", False, "GLM-5.3")]  # fmt: skip
    found = progress.build_provenance(events, derived)
    doc = progress.build_provenance_doc(found)
    ufo = doc["exes"][UFO]
    assert ufo["label"] == "UFO2P.EXE" and ufo["matched"] == 2 and ufo["unclassed"] == 1
    assert ufo["classes"] == {
        "unattended": {"functions": 1, "flags_approved": 1, "by_credit": {"Claude Haiku 5.5": 1}},
        "human-hints": {"functions": 0, "flags_approved": 0, "by_credit": {}},
        "tool": {"functions": 0, "flags_approved": 0, "by_credit": {}},
        "human-written": {"functions": 0, "flags_approved": 0, "by_credit": {}},
    }
    assert doc["exes"][TACP] == {"label": "TACP.EXE", "matched": 0, "unclassed": 0,
                                 "classes": {c: {"functions": 0, "flags_approved": 0,
                                                 "by_credit": {}} for c in stats.CLASSES}}
    assert doc["combined"]["matched"] == 2 and doc["combined"]["unclassed"] == 1
    assert doc["note"] == ""


# ---- the git layer, on a synthetic repository ----


def _when(day: str, hour: int) -> str:
    return f"{day}T{hour:02d}:00:00-03:00"


def _status(config: Path, stem: str, *rows: tuple) -> None:
    (config / stem / "status.csv").write_text(format_status([
        StatusRow(fn.start, fn.name, fn.unit, status, 100.0 if status == MATCHED else 50.0, 1,
                  SHA, day) for fn, status, day in rows]), encoding="utf-8")  # fmt: skip


def _commit(repo: Path, env: dict, when: str, subject: str, *trailers: str) -> None:
    dated = {**env, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    _git(repo, dated, "add", "--", "config")
    message = subject + ("\n\nattempt 1/3\n\n" + "\n".join(trailers) if trailers else "")
    _git(repo, dated, "commit", "-q", "-m", message)


def provenance_repo(tmp_path: Path) -> Path:
    """UFO2P: U_MATCHED matched unattended by Haiku on a side branch (merged), U_PARTIAL with
    the owner's hints by Opus, U_UNMATCHED under approved flags by Opus, a re-gate of U_MATCHED
    (no event). TACP: T_GAME written by hand with Opus, reverted, then matched again unattended
    by GLM-5.3 (the latest event counts)."""
    env = _git_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, env, "init", "-q")
    config = synthetic_config(repo)
    (config / UFO / "status.csv").unlink()
    _commit(repo, env, _when("2026-10-01", 10), "feat(05-16): commit the tables")
    _git(repo, env, "checkout", "-q", "-b", "side")
    _status(config, UFO, (U_MATCHED, MATCHED, DAY), (U_PARTIAL, PARTIAL, DAY))
    _commit(repo, env, _when("2026-10-02", 9), "feat(ufo2p): match func_00010000 in u (C89)",
            DRIVE, HAIKU)  # fmt: skip
    _git(repo, env, "checkout", "-q", "main")
    _status(config, TACP, (T_GAME, MATCHED, DAY))
    _commit(repo, env, _when("2026-10-02", 10), "feat(tacp): match func_00020000 in u (C89)",
            OPUS)  # fmt: skip
    merged = {**env, "GIT_AUTHOR_DATE": _when("2026-10-03", 9),
              "GIT_COMMITTER_DATE": _when("2026-10-03", 9)}  # fmt: skip
    _git(repo, merged, "merge", "-q", "--no-ff", "-m", "chore: merge side", "side")
    _status(config, UFO, (U_MATCHED, MATCHED, DAY), (U_PARTIAL, MATCHED, DAY))
    _commit(repo, env, _when("2026-10-04", 9), "feat(ufo2p): match func_00010010 in u (C89)",
            DRIVE, HINTS, OPUS)  # fmt: skip
    _status(config, UFO, (U_MATCHED, MATCHED, "2026-10-05"), (U_PARTIAL, MATCHED, DAY),
            (U_UNMATCHED, MATCHED, DAY))  # fmt: skip
    _commit(repo, env, _when("2026-10-05", 9), "feat(ufo2p): match func_00010030 in u under "
            "approved flags F-0001 (C89)", OPUS, DRIVE, FLAGS)  # fmt: skip
    (config / TACP / "status.csv").unlink()
    _commit(repo, env, _when("2026-10-06", 9), "revert(tacp): func_00020000")
    _status(config, TACP, (T_GAME, MATCHED, DAY))
    _commit(repo, env, _when("2026-10-07", 9), "feat(tacp): match func_00020000 in u (C89)",
            DRIVE, "Matched-By: z-ai/glm-5.3", GLM)  # fmt: skip
    return repo


def test_load_provenance_agrees_with_stats(tmp_path):
    """The walk gives each matched function the class `reverseapoc stats` gives it on the same
    history (side branches, a re-gate, a revert and a re-match included), credited to the
    model that made it."""
    progress = provenance_module()
    repo = provenance_repo(tmp_path)
    derived = progress.derive(repo / "config")
    found = progress.load_provenance(repo, derived)
    assert found.note == ""
    hist = stats.history(repo)
    latest = {(e.exe, e.start): (e.cls, e.flags_approved) for e in hist.events}
    ours = {(e.stem, e.start): (e.cls, e.flagged) for exe in found.exes for e in exe.events}
    assert ours == {key: latest[key] for key in hist.matched}
    doc = progress.build_provenance_doc(found)
    assert doc["exes"][UFO]["classes"] == {
        "unattended": {"functions": 2, "flags_approved": 1,
                       "by_credit": {"Claude Haiku 5.5": 1, "Claude Opus 5.5": 1}},
        "human-hints": {"functions": 1, "flags_approved": 0, "by_credit": {"Claude Opus 5.5": 1}},
        "tool": {"functions": 0, "flags_approved": 0, "by_credit": {}},
        "human-written": {"functions": 0, "flags_approved": 0, "by_credit": {}},
    }  # fmt: skip
    assert doc["exes"][TACP]["classes"]["unattended"] == {
        "functions": 1, "flags_approved": 0, "by_credit": {"GLM-5.3": 1}}
    totals = {exe.stem: exe.totals.matched_functions for exe in derived.exes}
    for stem in (UFO, TACP):
        split = doc["exes"][stem]
        assert split["matched"] == totals[stem]  # status.csv's matched, as progress.json counts
        assert sum(c["functions"] for c in split["classes"].values()) + split["unclassed"] == (
            totals[stem])
    assert doc["combined"]["classes"]["unattended"]["by_credit"] == {
        "Claude Haiku 5.5": 1, "Claude Opus 5.5": 1, "GLM-5.3": 1}


def test_a_shallow_clone_gives_a_note(tmp_path):
    progress = provenance_module()
    repo = provenance_repo(tmp_path)
    clone = tmp_path / "shallow"
    _git(tmp_path, _git_env(tmp_path), "clone", "-q", "--depth", "1", repo.as_uri(), str(clone))
    found = progress.load_provenance(clone, progress.derive(clone / "config"))
    assert found.exes == () and "shallow" in found.note


def test_no_repository_gives_no_provenance(tmp_path):
    progress = provenance_module()
    config = synthetic_config(tmp_path)
    assert progress.load_provenance(tmp_path, progress.derive(config)) is None


def test_main_publishes_the_split(tmp_path):
    """progress.json carries the split and the page shows it, per EXE and combined, with each
    class's models; a config tree outside a checkout has "provenance": null and no section."""
    progress = provenance_module()
    repo = provenance_repo(tmp_path)
    out = tmp_path / "out"
    assert progress.main(["--config", str(repo / "config"), "--out", str(out), "--commit",
                          SHA]) == 0  # fmt: skip
    doc = json.loads((out / "progress.json").read_text(encoding="utf-8"))
    assert doc["provenance"]["exes"][UFO]["matched"] == 3
    assert doc["provenance"]["combined"]["classes"]["human-hints"]["functions"] == 1
    page = (out / "index.html").read_text(encoding="utf-8")
    (section,) = _SECTION.findall(page)
    assert '<h2 id="provenance">Who made the matches</h2>' in section
    assert page.index("Who made the matches") < page.index("<h2>The mosaic</h2>")
    rows = re.findall(r'<tr><th scope="row">(.*?)</th>((?:<td>[^<]*</td>)+)</tr>', section)
    cells = {name: re.findall(r"<td>([^<]*)</td>", tds) for name, tds in rows}
    assert list(cells) == ["unattended", "unattended, under approved flags", "human-hints",
                           "human-hints, under approved flags", "tool",
                           "tool, under approved flags", "human-written",
                           "human-written, under approved flags", "matched in status.csv"]
    assert cells["unattended"] == ["2", "1", "3"]
    assert cells["unattended, under approved flags"] == ["1", "0", "1"]
    assert cells["human-hints"] == ["1", "0", "1"]
    assert cells["human-written"] == ["0", "0", "0"]
    assert cells["matched in status.csv"] == ["3", "1", "4"]
    assert "no match commit in the history" not in section  # none unclassed
    assert "unattended: Claude Haiku 5.5 1, Claude Opus 5.5 1, GLM-5.3 1" in section
    plain = synthetic_config(tmp_path / "plain")
    alone = tmp_path / "alone"
    assert progress.main(["--config", str(plain), "--out", str(alone)]) == 0
    assert json.loads((alone / "progress.json").read_text(encoding="utf-8"))["provenance"] is None
    assert 'class="provenance"' not in (alone / "index.html").read_text(encoding="utf-8")


# ---- todo stats-tool-class: twin and lift landings are the tool class ----


def tool_repo(tmp_path: Path) -> Path:
    """UFO2P: U_MATCHED landed by `reverseapoc twins`, U_PARTIAL by `reverseapoc lift` under
    approved flags, U_UNMATCHED by a spike subagent under approved flags (human-written)."""
    env = _git_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, env, "init", "-q")
    config = synthetic_config(repo)
    (config / UFO / "status.csv").unlink()
    _commit(repo, env, _when("2026-11-01", 10), "feat(05-16): commit the tables")
    _status(config, UFO, (U_MATCHED, MATCHED, DAY))
    _commit(repo, env, _when("2026-11-18", 9), "feat(ufo2p): match func_00010000 in u as a twin "
            "of tacp func_00020000 (C89)", TWINS, "Co-Authored-By: Claude <noreply@anthropic.com>")
    _status(config, UFO, (U_MATCHED, MATCHED, DAY), (U_PARTIAL, MATCHED, DAY))
    _commit(repo, env, _when("2026-11-18", 10), "feat(ufo2p): match func_00010010 in u under "
            "approved flags F-0002 (C89)", LIFT, FLAGS)  # fmt: skip
    _status(config, UFO, (U_MATCHED, MATCHED, DAY), (U_PARTIAL, MATCHED, DAY),
            (U_UNMATCHED, MATCHED, DAY))  # fmt: skip
    _commit(repo, env, _when("2026-11-18", 11), "feat(ufo2p): match func_00010030 in u under "
            "approved flags F-0003 (C89)", "Matched-By: claude subagent (spike 011)", FLAGS)
    return repo


def test_twin_and_lift_landings_are_tool_on_the_page(tmp_path):
    """The walk classes twin and lift landings `tool` as stats does, credited to the tool; the
    page has the tool rows (its flag-approved subset apart) and the caption says what it is."""
    progress = provenance_module()
    repo = tool_repo(tmp_path)
    found = progress.load_provenance(repo, progress.derive(repo / "config"))
    hist = stats.history(repo)
    latest = {(e.exe, e.start): (e.cls, e.flags_approved) for e in hist.events}
    ours = {(e.stem, e.start): (e.cls, e.flagged) for exe in found.exes for e in exe.events}
    assert ours == {key: latest[key] for key in hist.matched}
    doc = progress.build_provenance_doc(found)
    assert doc["exes"][UFO]["classes"]["tool"] == {
        "functions": 2, "flags_approved": 1,
        "by_credit": {"reverseapoc lift": 1, "reverseapoc twins": 1}}  # fmt: skip
    assert doc["exes"][UFO]["classes"]["human-written"]["functions"] == 1
    out = tmp_path / "out"
    assert progress.main(["--config", str(repo / "config"), "--out", str(out), "--commit",
                          SHA]) == 0  # fmt: skip
    (section,) = _SECTION.findall((out / "index.html").read_text(encoding="utf-8"))
    rows = re.findall(r'<tr><th scope="row">(.*?)</th>((?:<td>[^<]*</td>)+)</tr>', section)
    cells = {name: re.findall(r"<td>([^<]*)</td>", tds) for name, tds in rows}
    assert cells["tool"] == ["2", "0", "2"]
    assert cells["tool, under approved flags"] == ["1", "0", "1"]
    assert cells["human-written"] == ["1", "0", "1"]
    assert "tool: reverseapoc lift 1, reverseapoc twins 1" in section
    caption = progress.PROVENANCE_CAPTION
    assert "Tool: a reverseapoc tool wrote the C with no model session" in caption
    assert "Matched-By: reverseapoc twins" in caption and "Matched-By: reverseapoc lift" in caption
    assert "converter (reverseapoc lift)" not in caption  # no longer called human-written
