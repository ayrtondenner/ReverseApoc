"""tools/progress.py's progress-over-days charts (todo progress-timeline-chart): the three
figures (strict, functions, fuzzy) of each EXE at the end of each day since the first commit,
back-filled from the git history of config/<exe>/{functions,units,status}.csv with derive's own
figures, one small chart per figure, plus what each
day did (match commits and their trailers, flags approvals, tooling and plan commits, drive runs
from progress/attempts.jsonl, dated docs/learnings.md entries) and its biggest driver. The walk
and the per-day aggregation are one pure function over log records and CSV texts; the git layer
is tested on a synthetic repository with fixed dates. No game bytes: the tables are made up."""

from __future__ import annotations

import json
import re
from pathlib import Path

from reverseapoc.status import MATCHED, PARTIAL, StatusRow, format_status
from test_driver import _git, _git_env
from test_progress import (
    DAY,
    EXE_NAMES,
    SHA,
    U_MATCHED,
    U_PARTIAL,
    U_UNMATCHED,
    load_progress,
    synthetic_config,
)
from test_progress_page import style_of, tags_of

UFO, TACP = "ufo2p", "tacp"
FILES = ("functions.csv", "units.csv", "status.csv")
HAIKU = "Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>"
OPUS = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
DRIVE = "Matched-By: reverseapoc drive"


def timeline_module():
    """progress.py with its timeline API; called in each test body, so a missing name fails
    the test on this assert."""
    progress = load_progress()
    for name in ("Snapshot", "LoggedCommit", "build_timeline", "parse_runs", "parse_learnings",
                 "load_timeline"):  # fmt: skip
        assert hasattr(progress, name), f"progress.py has no {name}"
    return progress


def status_text(*matched: StatusRow) -> str:
    return format_status(matched)


def row(fn, status: str = MATCHED) -> StatusRow:
    return StatusRow(fn.start, fn.name, fn.unit, status, 100.0 if status == MATCHED else 50.0,
                     1, SHA, DAY)  # fmt: skip


def tables(tmp_path: Path) -> dict[str, tuple[str, str]]:
    """The synthetic functions.csv and units.csv texts per EXE."""
    config = synthetic_config(tmp_path / "tables")
    return {stem: tuple((config / stem / name).read_text(encoding="utf-8")
                        for name in FILES[:2]) for stem in (UFO, TACP)}  # fmt: skip


def expected_totals(tmp_path: Path, stem: str, status: str | None):
    """derive's own totals for the synthetic tables with `status` as the EXE's status.csv."""
    progress = load_progress()
    config = synthetic_config(tmp_path / f"expected-{stem}-{len(status or '')}")
    path = config / stem / "status.csv"
    if status is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(status, encoding="utf-8")
    return progress.derive(config).exe(stem).totals


def expected_percent(tmp_path: Path, stem: str, status: str | None) -> float:
    """derive's own strict figure for the synthetic tables with `status` as the status.csv."""
    return expected_totals(tmp_path, stem, status).percent


def snapshot(progress, sha: str, day: str, texts: dict[str, tuple]):
    return progress.Snapshot(sha, day, texts)


def commit(progress, sha: str, day: str, subject: str, *trailers: str):
    pairs = tuple(tuple(part.strip() for part in t.split(":", 1)) for t in trailers)
    return progress.LoggedCommit(sha, day, subject, pairs)


# ---- the pure walk ----


def test_percent_at_the_end_of_each_day(tmp_path):
    """Two snapshots on day 0: the day's figure is the last one's. Day 1 has no table change and
    carries day 0's figure; day 2's partial row adds nothing (only matched rows count)."""
    progress = timeline_module()
    (uf, uu), (tf, tu) = tables(tmp_path).values()
    one = status_text(row(U_MATCHED))
    partial = status_text(row(U_MATCHED), row(U_PARTIAL, PARTIAL))
    snaps = [snapshot(progress, "a1", "2026-10-01", {UFO: (uf, uu, None), TACP: (tf, tu, None)}),
             snapshot(progress, "a2", "2026-10-01", {UFO: (uf, uu, one), TACP: (tf, tu, None)}),
             snapshot(progress, "a4", "2026-10-03", {UFO: (uf, uu, partial),
                                                     TACP: (tf, tu, None)})]  # fmt: skip
    commits = [commit(progress, "a1", "2026-10-01", "feat(05-16): commit the tables"),
               commit(progress, "a3", "2026-10-02", "docs(06): a plan"),
               commit(progress, "a4", "2026-10-03", "feat(ufo2p): record a partial")]
    found = progress.build_timeline(snaps, commits, (), (), ())
    assert [d.date for d in found.days] == ["2026-10-01", "2026-10-02", "2026-10-03"]
    assert [d.index for d in found.days] == [0, 1, 2]
    matched = expected_percent(tmp_path, UFO, one)
    assert matched == 6.5574
    assert [d.percents for d in found.days] == [(matched, 0.0), (matched, 0.0), (matched, 0.0)]
    # The functions and fuzzy figures are derive's too, day by day: the partial row moves the
    # fuzzy figure on day 2 while strict and functions stay.
    one_totals, partial_totals = (expected_totals(tmp_path, UFO, s) for s in (one, partial))
    assert (one_totals.functions_percent, one_totals.fuzzy_percent) == (25.0, 6.5574)
    assert partial_totals.fuzzy_percent == 13.1148
    assert [d.functions for d in found.days] == [(25.0, 0.0)] * 3
    assert [d.fuzzy for d in found.days] == [(6.5574, 0.0), (6.5574, 0.0), (13.1148, 0.0)]
    assert found.days[0].deltas == (None, None)  # each EXE's first day
    assert found.days[1].deltas == (0.0, 0.0)
    assert found.labels == (EXE_NAMES[UFO], EXE_NAMES[TACP])


def test_a_later_exe_starts_its_line_on_its_first_day(tmp_path):
    """TACP's tables appear on day 1: no TACP figure on day 0, its first figure on day 1. A
    status row before units.csv exists gives no figure either (the EXE has no tables yet)."""
    progress = timeline_module()
    (uf, uu), (tf, tu) = tables(tmp_path).values()
    snaps = [snapshot(progress, "b1", "2026-10-01", {UFO: (uf, uu, None), TACP: (tf, None, None)}),
             snapshot(progress, "b2", "2026-10-02", {UFO: (uf, uu, status_text(row(U_MATCHED))),
                                                     TACP: (tf, tu, None)})]  # fmt: skip
    found = progress.build_timeline(snaps, [], (), (), ())
    first, second = found.days
    assert first.percents == (0.0, None) and first.deltas == (None, None)
    assert first.functions == (0.0, None) and first.fuzzy == (0.0, None)
    assert second.percents == (6.5574, 0.0)
    assert second.deltas == (6.5574, None)


def test_the_signed_assembler_rows_leave_every_day(tmp_path):
    """The page's figure excludes the owner-signed asm rows (D-23); so does every day's, so the
    last point is the figure the page shows."""
    progress = timeline_module()
    (uf, uu), (tf, tu) = tables(tmp_path).values()
    snaps = [snapshot(progress, "c1", "2026-10-01", {UFO: (uf, uu, status_text(row(U_MATCHED))),
                                                     TACP: (tf, tu, None)})]  # fmt: skip
    found = progress.build_timeline(snaps, [], (), (), ((UFO, U_UNMATCHED.start),))
    config = synthetic_config(tmp_path / "asm")
    (config / UFO / "status.csv").write_text(snaps[0].texts[UFO][2], encoding="utf-8")
    shown = progress.exclude_assembler(progress.derive(config), ((UFO, U_UNMATCHED.start),))
    totals = shown.exe(UFO).totals
    assert found.days[0].percents[0] == totals.percent != 6.5574
    assert found.days[0].functions[0] == totals.functions_percent != 25.0
    assert found.days[0].fuzzy[0] == totals.fuzzy_percent != 6.5574


def test_a_mainline_date_going_back_never_moves_a_figure_into_the_past(tmp_path):
    """Code review: committer dates can go backwards along the mainline (another zone, a
    rebase). A snapshot dated before the one it follows counts on that one's day, so the line
    never drops back to an older state."""
    progress = timeline_module()
    (uf, uu), (tf, tu) = tables(tmp_path).values()
    one = status_text(row(U_MATCHED))
    snaps = [snapshot(progress, "k1", "2026-10-02", {UFO: (uf, uu, None), TACP: (tf, tu, None)}),
             snapshot(progress, "k2", "2026-10-01", {UFO: (uf, uu, one), TACP: (tf, tu, None)})]
    commits = [commit(progress, "k2", "2026-10-01", "feat(ufo2p): rebased, dated a day early")]
    first, second = progress.build_timeline(snaps, commits, (), (), ()).days
    assert (first.date, first.percents) == ("2026-10-01", (None, None))
    assert (second.date, second.percents) == ("2026-10-02", (6.5574, 0.0))


def test_a_merge_that_moves_the_figure_drives_its_day(tmp_path):
    """Code review: a day whose only mainline change is a merge bringing matched rows is active
    and names the merge; merges are counted in the summary, never as other commits."""
    progress = timeline_module()
    (uf, uu), (tf, tu) = tables(tmp_path).values()
    one = status_text(row(U_MATCHED))
    snaps = [snapshot(progress, "m0", "2026-10-01", {UFO: (uf, uu, None), TACP: (tf, tu, None)}),
             snapshot(progress, "m1", "2026-10-03", {UFO: (uf, uu, one), TACP: (tf, tu, None)})]
    commits = [commit(progress, "m0", "2026-10-01", "feat(05-16): the tables"),
               progress.LoggedCommit("m2", "2026-10-03", "chore: merge the tooling", (), True),
               progress.LoggedCommit("m1", "2026-10-03", "chore: merge the night", (), True)]
    *_rest, day = progress.build_timeline(snaps, commits, (), (), ()).days
    assert day.active and day.driver == "merge: chore: merge the night"
    assert day.summary == "2 merges."


def test_an_impossible_run_date_is_refused():
    progress = timeline_module()
    record = {"kind": "run", "run": "x", "event": "ENDED", "sessions": 1, "matched": 0,
              "date": "2026-13-01"}  # fmt: skip
    try:
        progress.parse_runs(json.dumps(record) + "\n")
    except progress.ProgressError as exc:
        assert "line 1" in str(exc), exc
    else:
        raise AssertionError("accepted month 13")


def test_a_breaking_match_subject_is_a_match_and_unscoped_tooling_counts_itself():
    progress = timeline_module()
    commits = [commit(progress, "n1", "2026-10-01", "feat(tacp)!: match func_000A6740 in u (C89)",
                      HAIKU),
               commit(progress, "n2", "2026-10-02", "fix: one"),
               commit(progress, "n3", "2026-10-02", "fix: two"),
               commit(progress, "n4", "2026-10-02", "fix: three"),
               commit(progress, "n5", "2026-10-02", "test(driver): four"),
               commit(progress, "n6", "2026-10-02", "test(driver): five")]  # fmt: skip
    match, tooling = progress.build_timeline([], commits, (), (), ()).days
    assert match.driver == "Claude Haiku 5.5: 1 match"
    assert tooling.driver == "tooling: 3 unscoped commits"


def test_end_labels_stay_inside_the_plot(tmp_path):
    """Code review: lines ending together at 0% push their labels apart upwards from the
    plot's bottom, never below it onto the day axis."""
    progress = timeline_module()
    days = tuple(progress.Day(f"2026-10-0{i + 1}", i, percents=(0.0, 0.0), functions=(0.0, 0.0),
                              fuzzy=(0.0, 0.0), deltas=(None, None), driver="x", summary="x.")
                 for i in range(3))  # fmt: skip
    timeline = progress.Timeline(("UFO2P.EXE", "TACP.EXE"), days)
    svg = progress.render_timeline_svg(timeline, progress.TIMELINE_CHARTS[0])
    bottom = progress.CHART_HEIGHT - progress.CHART_BOTTOM
    ys = [float(y) for y in re.findall(r'<text class="tl-name" x="[0-9.]+" y="([0-9.]+)"', svg)]
    assert len(ys) == 2 and max(ys) <= bottom + progress.CHART_FONT / 3
    assert abs(ys[0] - ys[1]) >= progress.CHART_LABEL_GAP


def test_a_table_the_reader_refuses_fails_the_walk(tmp_path):
    """A malformed table in the history is a ProgressError naming the commit and the file."""
    progress = timeline_module()
    (uf, uu), (tf, tu) = tables(tmp_path).values()
    snaps = [snapshot(progress, "d1", "2026-10-01", {UFO: (uf, uu, "not,a,status\n"),
                                                     TACP: (tf, tu, None)})]  # fmt: skip
    try:
        progress.build_timeline(snaps, [], (), (), ())
    except progress.ProgressError as exc:
        assert "d1:config/ufo2p/status.csv" in str(exc)
    else:
        raise AssertionError("a malformed status.csv was accepted")


def test_match_credits_and_the_biggest_driver(tmp_path):
    """Match commits are credited to their Co-Authored-By name (Matched-By's model when there is
    none); a subject naming three functions counts three, `match 23 ...` counts 23. The biggest
    group is the day's driver."""
    progress = timeline_module()
    day = "2026-10-05"
    commits = [
        commit(progress, "e1", day, "feat(ufo2p): match func_00010000 in u_00010000 (C89)",
               DRIVE, HAIKU),
        commit(progress, "e2", day, "feat(tacp): match func_000A8A10, func_000A8A60, "
               "func_000A8AB0 in u_000a87c0 (C89)", DRIVE, HAIKU),
        commit(progress, "e3", day, "feat(ufo2p): match func_00010030 in u_00010000 (C89)",
               DRIVE, OPUS),
        commit(progress, "e4", day, "feat(tacp): match func_00020000 in u_00020000 (C89)",
               DRIVE, "Matched-By: deepseek/deepseek-v4.1-flash"),
        commit(progress, "e5", day, "fix(05-04): match runtime segments by name"),
    ]  # fmt: skip
    (found,) = progress.build_timeline([], commits, (), (), ()).days
    assert found.driver == "Claude Haiku 5.5: 4 matches"
    assert found.summary.startswith("6 matches (Claude Haiku 5.5 4, Claude Opus 5.5 1, "
                                    "deepseek/deepseek-v4.1-flash 1); 1 tooling commit")
    big = commit(progress, "e6", day, "feat(ufo2p,tacp): match 23 Tier 1 functions (C89)", OPUS)
    (again,) = progress.build_timeline([], [*commits, big], (), (), ()).days
    assert again.driver == "Claude Opus 5.5: 24 matches"
    pair = commit(progress, "e7", "2026-10-06", "feat(ufo2p): match func_00010010 in u (C89)",
                  OPUS, "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>")
    crowd = commit(progress, "e8", "2026-10-07", "feat(ufo2p): match func_00010020 in u (C89)",
                   OPUS, HAIKU, "Co-Authored-By: GLM-5.3 <noreply@z.ai>")
    _day, two, three = progress.build_timeline([], [commits[0], pair, crowd], (), (), ()).days
    assert two.driver == "Claude Opus 5.5: 1 match"  # the first co-author made the match
    assert three.driver == "Claude Opus 5.5: 1 match"


def test_a_landing_credits_its_own_model_and_a_tie_counts_the_models():
    """Owner ruling 2026-11-18 (todo progress-coauthor-driver-label): a landing from a hold run
    carries one Co-Authored-By per arm that held the function exact after its own credit lines,
    so the first co-author is the model that matched. The day names the model with the most
    matches; models tied for the most are counted ("N models")."""
    progress = timeline_module()
    sonnet = "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
    holders = (OPUS, sonnet, "Co-Authored-By: GLM-5.3 <noreply@z.ai>",
               "Co-Authored-By: GPT-6.1 Terra <noreply@openai.com>")  # fmt: skip
    day = "2026-11-11"
    landings = [commit(progress, f"l{n}", day, f"feat(tacp): match func_0009D1{n}0 in u (C89)",
                       HAIKU, DRIVE, *holders) for n in range(3)]  # fmt: skip
    alone = commit(progress, "l9", day, "feat(ufo2p): match func_00038550 in u (C89)", sonnet,
                   DRIVE)  # fmt: skip
    (found,) = progress.build_timeline([], [*landings, alone], (), (), ()).days
    assert found.driver == "Claude Haiku 5.5: 3 matches"
    assert found.summary.startswith("4 matches (Claude Haiku 5.5 3, Claude Sonnet 5.5 1)")
    tie = [commit(progress, "t1", day, "feat(ufo2p): match func_00010000 in u (C89)", HAIKU),
           commit(progress, "t2", day, "feat(ufo2p): match func_00010010 in u (C89)", OPUS),
           commit(progress, "t3", day, "feat(tacp): match func_00020000 in u (C89)", DRIVE,
                  "Matched-By: deepseek/deepseek-v4.1-flash")]  # fmt: skip
    (tied,) = progress.build_timeline([], tie, (), (), ()).days
    assert tied.driver == "3 models: 1 match each"
    # A tie with the flags group goes to the models; more flagged matches name the flags.
    flagged = commit(progress, "t4", day, "feat(tacp): match func_00020010 in u under approved "
                     "flags F-0070 (C89)", DRIVE, OPUS)  # fmt: skip
    (with_flags,) = progress.build_timeline([], [*tie, flagged], (), (), ()).days
    assert with_flags.driver == "3 models: 1 match each"
    more = commit(progress, "t5", day, "feat(tacp): match func_00020020 in u under approved "
                  "flags F-0071 (C89)", DRIVE, OPUS)  # fmt: skip
    (flags_win,) = progress.build_timeline([], [*tie, flagged, more], (), (), ()).days
    assert flags_win.driver == "flags F-0070..F-0071: 2 matches"


def test_a_converter_match_is_credited_to_the_converter():
    """`Matched-By: reverseapoc lift` names the converter that wrote the C: it is the credit,
    not the session's co-author; `Matched-By: reverseapoc drive` names no one."""
    progress = timeline_module()
    lift = commit(progress, "c1", "2026-11-03", "feat(ufo2p): match func_000B63C0 in u (C89)",
                  "Matched-By: reverseapoc lift", "Co-Authored-By: Claude <noreply@anthropic.com>")
    (found,) = progress.build_timeline([], [lift], (), (), ()).days
    assert found.driver == "reverseapoc lift: 1 match"
    # A batch landing names its author in Matched-By alone (flags.py, 07-48c); the commit hook's
    # Co-Authored-By: Claude is the approving session's, not the author's.
    batch = commit(progress, "c2", "2026-11-03", "feat(ufo2p): match func_0005FBD0 in u (C89)",
                   "Matched-By: claude subagent (spike 011)",
                   "Co-Authored-By: Claude <noreply@anthropic.com>")  # fmt: skip
    (found,) = progress.build_timeline([], [batch], (), (), ()).days
    assert found.driver == "claude subagent (spike 011): 1 match"


def test_flags_approvals_drive_a_day():
    """Matches landed under approved flags are one group, named by their flag ids as ranges."""
    progress = timeline_module()
    day = "2026-11-12"
    commits = [commit(progress, f"f{n}", day, f"feat(tacp): match func_0009D1{n}0 in u_0009d140 "
                      f"under approved flags F-00{n} (C89)", DRIVE, OPUS)
               for n in (69, 70, 71, 73)]
    commits.append(commit(progress, "f9", day, "feat(tacp): match func_00010000 in u (C89)",
                          DRIVE, HAIKU))
    (found,) = progress.build_timeline([], commits, (), (), ()).days
    assert found.driver == "flags F-0069..F-0071, F-0073: 4 matches"
    assert "flags F-0069..F-0071, F-0073" in found.summary


def test_a_day_without_matches_names_its_tooling_or_plans():
    progress = timeline_module()
    commits = [commit(progress, "g1", "2026-11-06", "feat(07.1-03): the converter"),
               commit(progress, "g2", "2026-11-06", "fix(07.1-03): a flag on a copy"),
               commit(progress, "g3", "2026-11-06", "test(driver): RED for a stop"),
               commit(progress, "g4", "2026-11-06", "docs(07.1): close the phase"),
               commit(progress, "g5", "2026-11-06", "chore: merge it"),
               commit(progress, "g6", "2026-11-07", "docs(08): plan the specs"),
               commit(progress, "g7", "2026-11-07", "docs(08): plan more")]
    tooling, plans = progress.build_timeline([], commits, (), (), ()).days
    assert tooling.driver == "tooling: 07.1-03 (2 commits)"
    assert tooling.summary == "3 tooling commits; 1 plan or docs commit; 1 other commit."
    assert plans.driver == "plans or docs: 2 commits"


def test_drive_runs_and_learnings_by_day():
    """A run counts on its record's date, by its last ENDED or STOPPED record (STARTED alone is a
    run still going); a learnings heading counts on its date, the template line never."""
    progress = timeline_module()
    records = [
        {"kind": "run", "run": "20261107-a", "event": "STARTED", "sessions": 0, "matched": 0,
         "date": "2026-11-07"},
        {"kind": "run", "run": "20261107-a", "event": "STOPPED", "sessions": 9, "matched": 0,
         "date": "2026-11-07"},
        {"kind": "run", "run": "20261107-a", "event": "ENDED", "sessions": 40, "matched": 3,
         "date": "2026-11-07", "totals": {"by_model": {
             "claude-haiku-5-5": {"sessions": 30, "matched": 3, "cost_usd": 0.0},
             "claude-opus-5-5": {"sessions": 10, "matched": 0, "cost_usd": 0.0}}}},
        {"kind": "attempt", "run": "20261107-a", "date": "2026-11-07"},
        {"kind": "run", "run": "20261108-b", "event": "STARTED", "sessions": 0, "matched": 0,
         "date": "2026-11-08"},
    ]  # fmt: skip
    runs = progress.parse_runs("\n".join(json.dumps(r) for r in records) + "\n\n")
    assert [(r.run, r.day, r.sessions, r.matched) for r in runs] == [
        ("20261107-a", "2026-11-07", 40, 3)]
    assert runs[0].by_model == (("claude-haiku-5-5", 30, 3), ("claude-opus-5-5", 10, 0))
    learnings = progress.parse_learnings(
        "# Learnings journal\n\n## YYYY-MM-DD: short title\n\n"
        "## 2026-11-07: cheap models match the small functions too (spike 012)\nbody\n")
    assert learnings == (("2026-11-07", "cheap models match the small functions too (spike 012)"),)
    commits = [commit(progress, "h1", "2026-11-06", "docs: a note")]
    _note, day = progress.build_timeline([], commits, runs, learnings, ()).days
    assert day.driver == "drive run 20261107-a: 40 sessions, 3 matched"
    assert day.summary == ("1 drive run (40 sessions, 3 matched: claude-haiku-5-5 3 of 30, "
                           "claude-opus-5-5 0 of 10); learning: cheap models match the small "
                           "functions too (spike 012).")


def test_a_malformed_run_record_names_its_line():
    progress = timeline_module()
    for text in ('{"kind":"run"\n', '{"kind":"run","run":"x","event":"ENDED","date":"d"}\n'):
        try:
            progress.parse_runs('{"kind":"attempt"}\n' + text)
        except progress.ProgressError as exc:
            assert "line 2" in str(exc), exc
        else:
            raise AssertionError(f"accepted {text!r}")


# ---- the git layer, on a synthetic repository ----


def _when(day: str, hour: int) -> str:
    return f"{day}T{hour:02d}:00:00-03:00"


def _commit(repo: Path, env: dict, when: str, message: str, *paths: str) -> None:
    dated = {**env, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    _git(repo, dated, "add", "--", *paths)
    _git(repo, dated, "commit", "-q", "-m", message)


def history_repo(tmp_path: Path) -> tuple[Path, dict]:
    """Day 0: the tables, then a learnings entry; day 1: a side branch matches U_MATCHED (and
    records U_PARTIAL as partial) with a Haiku trailer, merged with --no-ff on day 2 next to a
    drive run's record."""
    env = _git_env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, env, "init", "-q")
    config = synthetic_config(repo)
    (config / UFO / "status.csv").unlink()
    _commit(repo, env, _when("2026-10-01", 10), "feat(05-16): commit the tables", "config")
    (repo / "docs").mkdir()
    (repo / "docs" / "learnings.md").write_text(
        "# Learnings journal\n\n## 2026-10-01: the tables are in\n", encoding="utf-8")
    _commit(repo, env, _when("2026-10-01", 11), "docs: the first learning", "docs")
    _git(repo, env, "checkout", "-q", "-b", "side")
    (config / UFO / "status.csv").write_text(status_text(row(U_MATCHED), row(U_PARTIAL, PARTIAL)),
                                             encoding="utf-8")  # fmt: skip
    _commit(repo, env, _when("2026-10-02", 9), "feat(ufo2p): match func_00010000 in "
            f"u_00010000 (C89)\n\nattempt 1/3\n\n{DRIVE}\n{HAIKU}", "config")  # fmt: skip
    _git(repo, env, "checkout", "-q", "main")
    (repo / "progress").mkdir()
    (repo / "progress" / "attempts.jsonl").write_text(json.dumps(
        {"kind": "run", "run": "20261003-x", "event": "ENDED", "sessions": 4, "matched": 1,
         "date": "2026-10-03"}) + "\n", encoding="utf-8")  # fmt: skip
    _commit(repo, env, _when("2026-10-03", 8), "chore(driver): the run's log", "progress")
    merged = {**env, "GIT_AUTHOR_DATE": _when("2026-10-03", 9),
              "GIT_COMMITTER_DATE": _when("2026-10-03", 9)}  # fmt: skip
    _git(repo, merged, "merge", "-q", "--no-ff", "-m", "chore: merge side", "side")
    return repo, env


def test_load_timeline_walks_the_first_parent_history(tmp_path):
    """The figure moves on the day the match reached the mainline (the merge, day 2), while the
    match commit itself is listed on its own day (day 1); the run and the learning on theirs."""
    progress = timeline_module()
    repo, _env = history_repo(tmp_path)
    found = progress.load_timeline(repo, ())
    assert found.note == ""
    assert [d.date for d in found.days] == ["2026-10-01", "2026-10-02", "2026-10-03"]
    assert [d.percents for d in found.days] == [(0.0, 0.0), (0.0, 0.0), (6.5574, 0.0)]
    assert [d.functions for d in found.days] == [(0.0, 0.0), (0.0, 0.0), (25.0, 0.0)]
    assert [d.fuzzy for d in found.days] == [(0.0, 0.0), (0.0, 0.0), (13.1148, 0.0)]
    first, second, third = found.days
    assert "learning: the tables are in" in first.summary
    assert second.driver == "Claude Haiku 5.5: 1 match"
    assert third.driver == "merge: chore: merge side"  # the merge moved the figure
    assert "1 drive run (4 sessions, 1 matched)" in third.summary
    assert third.summary.endswith("1 other commit; 1 merge.")
    assert third.deltas == (6.5574, 0.0)


def test_a_shallow_clone_gives_a_note(tmp_path):
    progress = timeline_module()
    repo, env = history_repo(tmp_path)
    clone = tmp_path / "shallow"
    _git(tmp_path, env, "clone", "-q", "--depth", "1", repo.as_uri(), str(clone))
    found = progress.load_timeline(clone, ())
    assert found.days == ()
    assert "shallow" in found.note


def test_no_repository_gives_no_timeline(tmp_path):
    progress = timeline_module()
    synthetic_config(tmp_path)
    assert progress.load_timeline(tmp_path, ()) is None


# ---- the page ----

_SECTION = re.compile(r'<section class="timeline" aria-labelledby="timeline">(.*?)</section>',
                      re.S)  # fmt: skip
# A day is two rows: its figures, then what it did across the EXE columns (one narrow column of
# summaries squeezed the figures to a character wide at 390 px).
_ROW = re.compile(r'<tr class="fig"><th scope="row" rowspan="2">(.*?)</th>(.*?)</tr>\n'
                  r'<tr><td class="what" colspan="2">(.*?)</td></tr>')  # fmt: skip
# One small chart per figure, strict first, each titled above its own SVG.
_CHART = re.compile(r'<div class="tl">\n<h3>(.*?)</h3>\n(<svg .*?</svg>)\n</div>', re.S)
CHART_TITLES = ["strict (matched code bytes)",
                "functions (matched / all game and thunk functions)",
                "fuzzy (objdiff closeness, partial credit)"]  # fmt: skip


def timeline_section(page: str) -> str:
    found = _SECTION.findall(page)
    assert len(found) == 1, "the page has no timeline section, or two"
    return found[0]


def test_main_charts_the_history_of_a_checkout(tmp_path):
    """main charts the history of the repository its config tree sits in: three small charts
    (strict, functions, fuzzy), each with one line per EXE, a percent y-axis of its own, a
    marker per active day with its driver, and the same data as a table, newest day first. Two
    runs give the same bytes."""
    progress = timeline_module()
    repo, _env = history_repo(tmp_path)
    pages = []
    for name in ("one", "two"):
        out = tmp_path / name
        assert progress.main(["--config", str(repo / "config"), "--out", str(out),
                              "--commit", SHA]) == 0  # fmt: skip
        pages.append((out / "index.html").read_bytes())
    assert pages[0] == pages[1]
    page = pages[0].decode("utf-8")
    section = timeline_section(page)
    assert '<h2 id="timeline">Progress over days</h2>' in section
    assert page.index("Progress over days") < page.index("<h2>The mosaic</h2>")
    charts = _CHART.findall(section)
    assert [title for title, _svg in charts] == CHART_TITLES
    assert section.count("<svg") == 3
    for _title, svg in charts:
        assert 'role="img"' in svg and "aria-label=" in svg
        lines = re.findall(r'<path class="tl-line s(\d)" d="([^"]+)"', svg)
        assert [n for n, _d in lines] == ["0", "1"]
        assert all(d.startswith("M") and d.count("L") == 2 for _n, d in lines)  # three days
        assert re.search(r">[0-9.]+%</text>", svg), "the y ticks are percents"
        assert ">UFO2P<" in svg and ">TACP<" in svg  # direct labels
        titles = re.findall(r"<title>(.*?)</title>", svg)
        assert any("Claude Haiku 5.5: 1 match" in t for t in titles)
        # Every chart's tooltip names all three figures, strict labelled too.
        assert any("UFO2P strict 6.5574% (+6.5574), functions 25%, fuzzy 13.1148%" in t
                   for t in titles)  # fmt: skip
    # Each chart has its own y-axis: functions tops out near 25%, strict near 6.6%.
    tops = [max(float(v) for v in re.findall(r'text-anchor="end">([0-9.]+)%</text>', svg))
            for _title, svg in charts]  # fmt: skip
    assert tops[0] < 10 < tops[1] and tops[1] != tops[2]
    rows = _ROW.findall(section)
    assert [r[0] for r in rows] == ["Day 2<br>2026-10-03", "Day 1<br>2026-10-02",
                                    "Day 0<br>2026-10-01"]  # fmt: skip
    assert rows[0][1] == ('<td>6.5574% (+6.5574)<br><span class="sub">functions 25%<br>'
                          'fuzzy 13.1148%</span></td><td>0% (no change)<br><span class="sub">'
                          "functions 0%<br>fuzzy 0%</span></td>")  # fmt: skip
    assert rows[0][2].startswith("<strong>merge: chore: merge side</strong><br>1 drive run")
    assert "0% (first day)" in rows[2][1]
    head = section[section.index("<thead>"):section.index("</thead>")]
    assert [t for t, _a in tags_of(head) if t == "th"] == ["th"] * 3
    style = style_of(page)
    assert ".tl-line" in style and "@media (prefers-color-scheme: dark)" in style


def test_each_chart_ends_on_the_headline(tmp_path):
    """The last point of each chart is the figure the page and progress.json show for it: each
    chart's aria-label states every EXE's last value, and it is progress.json's."""
    progress = timeline_module()
    repo, _env = history_repo(tmp_path)
    out = tmp_path / "out"
    assert progress.main(["--config", str(repo / "config"), "--out", str(out)]) == 0
    doc = json.loads((out / "progress.json").read_text(encoding="utf-8"))
    charts = _CHART.findall(timeline_section((out / "index.html").read_text(encoding="utf-8")))
    keys = ("percent", "functions_percent", "fuzzy_percent")
    for (_title, svg), key in zip(charts, keys, strict=True):
        aria = re.search(r'aria-label="([^"]*)"', svg)[1]
        for stem, label in EXE_NAMES.items():
            headline = progress.shield_message(doc["exes"][stem][key])
            assert f"{label} {headline}" in aria, (key, aria)
    last = progress.load_timeline(repo, ()).days[-1]
    shown = progress.derive(repo / "config")
    for i, (stem, _label) in enumerate(progress.EXES):
        totals = shown.exe(stem).totals
        assert (last.percents[i], last.functions[i], last.fuzzy[i]) == (
            totals.percent, totals.functions_percent, totals.fuzzy_percent)


def test_the_page_without_history_has_no_timeline_rule(tmp_path):
    """A config tree outside a checkout (a test, a tarball) has no timeline: no section and no
    rule of it, byte for byte the page it was before."""
    progress = timeline_module()
    config = synthetic_config(tmp_path)
    out = tmp_path / "out"
    assert progress.main(["--config", str(config), "--out", str(out), "--commit", SHA]) == 0
    page = (out / "index.html").read_text(encoding="utf-8")
    assert 'class="timeline"' not in page and ".tl-line" not in page
    assert page == progress.render_html(progress.derive(config), SHA)


def test_a_shallow_checkout_still_builds_the_page_with_a_note(tmp_path):
    progress = timeline_module()
    repo, env = history_repo(tmp_path)
    clone = tmp_path / "shallow"
    _git(tmp_path, env, "clone", "-q", "--depth", "1", repo.as_uri(), str(clone))
    out = tmp_path / "out"
    assert progress.main(["--config", str(clone / "config"), "--out", str(out)]) == 0
    section = timeline_section((out / "index.html").read_text(encoding="utf-8"))
    assert "<svg" not in section and "<table" not in section
    assert "shallow" in section


def test_the_chart_stays_inside_a_phone(tmp_path):
    """Phone-legible (backlog 999.4's lessons): the chart scales to the column with its own
    viewBox, no minimum width, and the table wraps instead of widening the page."""
    progress = timeline_module()
    repo, _env = history_repo(tmp_path)
    page = progress.render_html(progress.derive(repo / "config"), SHA,
                                timeline=progress.load_timeline(repo, ()))  # fmt: skip
    style = style_of(page)
    assert re.search(r"\.tl svg\{display:block;width:100%;height:auto;max-width:[0-9.]+rem\}",
                     style)  # fmt: skip
    assert "min-width" not in style.split(".tl svg", 1)[1].split("}", 1)[0]
    width = int(re.search(r'<svg class="tl-chart" viewBox="0 0 (\d+) ', page)[1])
    assert width <= 480, "at 390 px the labels would shrink below legibility"
    assert ".days{width:100%" in style
    assert ".days .what{overflow-wrap:anywhere}" in style  # only the summary breaks anywhere
