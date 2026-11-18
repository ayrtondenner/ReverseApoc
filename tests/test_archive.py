"""The per-function archive of candidate sources (todo candidate-archive): keys, merges, the
checks it reads from the driver's attempt directories, and the seeds it gives `search`. The C
below is made up; nothing compiles here.
"""

from __future__ import annotations

import json

import pytest

from reverseapoc import archive, batch

STEM, START, FUNC = "ufo2p", 0x10000, "func_00010000"


def _c(body: str = "return a + 1;") -> str:
    return f"int {FUNC}(int a)\n{{\n    {body}\n}}\n"


def entry(source: str = "", score: float = 50.0, klass: str | None = "mixed", *,
          exact: bool = False, stack: float | None = 50.0,
          origin: str = "search") -> archive.Entry:  # fmt: skip
    source = source or _c()
    return archive.Entry(archive.source_key(source), exact, score, stack, klass, origin, source)


@pytest.fixture
def roots(monkeypatch, tmp_path):
    monkeypatch.setattr(archive, "ROOT", tmp_path / "archive")
    monkeypatch.setattr(archive, "DRIVER", tmp_path / "driver")
    return tmp_path


# ---- the key ----------------------------------------------------------------------------------


def test_the_key_ignores_comments_and_layout():
    plain = _c()
    commented = f"/* a note */\nint  {FUNC}(int a)\n{{\n\n        return a+1;   /* why */\n}}\n"
    assert archive.source_key(plain) == archive.source_key(commented)
    assert archive.source_key(_c("x = a && b;")) != archive.source_key(_c("x = a & &b;"))
    directive = f"#define N 1\nint {FUNC}(int a)\n{{\n    return a + N;\n}}\n"
    assert archive.source_key(directive) != archive.source_key(directive.replace("\n", " ", 1))


def test_the_key_keeps_literals_and_code():
    assert archive.source_key(_c('puts("a  b");')) != archive.source_key(_c('puts("a b");'))
    assert archive.source_key(_c("return a + 2;")) != archive.source_key(_c())
    assert archive.source_key(_c("/* x */ return a;")) == archive.source_key(_c("return a;"))


def test_a_comment_marker_inside_a_literal_is_code():
    assert archive.source_key(_c('puts("/* x */");')) != archive.source_key(_c('puts("");'))


# ---- the file ---------------------------------------------------------------------------------


def test_an_unarchived_function_has_no_entries(roots):
    assert archive.read(STEM, START) == []


def test_recorded_entries_read_back_best_first(roots):
    low, high = entry(_c("return a;"), 40.0), entry(_c("return 1;"), 70.0)
    archive.record(STEM, START, [low, high])
    assert archive.read(STEM, START) == [high, low]
    assert archive.path(STEM, START) == roots / "archive" / STEM / f"{START:08x}.jsonl"


def test_a_later_measurement_of_one_source_replaces_the_earlier(roots):
    archive.record(STEM, START, [entry(score=80.0, klass=None, origin="check r/attempt-1/0001")])
    archive.record(STEM, START, [entry(score=60.0, klass="branch")])
    (only,) = archive.read(STEM, START)
    assert (only.score, only.klass, only.origin) == (60.0, "branch", "search")


def test_each_class_keeps_only_its_best(roots):
    many = [entry(_c(f"return a + {n};"), float(n)) for n in range(archive.KEEP + 3)]
    archive.record(STEM, START, [*many, entry(_c("return 0;"), 1.0, "register")])
    kept = archive.read(STEM, START)
    mixed = [one.score for one in kept if one.klass == "mixed"]
    assert mixed == sorted((float(n) for n in range(3, archive.KEEP + 3)), reverse=True)
    assert [one.klass for one in kept].count("register") == 1


def test_entries_rank_as_search_ranks_them_a_check_by_its_score():
    """search's rank: exact, the stack score, the raw score. A check has no stack score, so its
    score stands in for it (review finding: the archive must seed what search would pick)."""
    raw = entry(_c("return 1;"), 90.0, stack=60.0)
    stack = entry(_c("return 2;"), 85.0, stack=95.0)
    check = entry(_c("return 3;"), 92.0, None, stack=None, origin="check r/attempt-1/0001")
    assert archive.ranked([raw, check, stack]) == [stack, check, raw]


def test_an_exact_entry_ranks_first():
    exact = entry(_c("return 1;"), 10.0, None, exact=True)
    assert archive.ranked([entry(score=99.0), exact])[0] == exact


@pytest.mark.parametrize(
    "line",
    ["not json", "[1]", json.dumps({"key": "k"}),
     json.dumps({"key": "k", "exact": "no", "score": 1.0, "stack_score": None, "class": None,
                 "origin": "search", "source": "x"})],
)  # fmt: skip
def test_a_malformed_line_is_an_error_naming_the_file_and_line(roots, line):
    path = archive.path(STEM, START)
    path.parent.mkdir(parents=True)
    good = json.dumps(archive.to_json(entry()))
    path.write_text(f"{good}\n{line}\n", encoding="utf-8")
    with pytest.raises(archive.ArchiveError, match=rf"{START:08x}\.jsonl:2:"):
        archive.read(STEM, START)
    assert issubclass(archive.ArchiveError, batch.BatchError)


# ---- agents' checks ---------------------------------------------------------------------------


def _check(roots, run: str, attempt: int, n: int, text: str | None, **line) -> None:
    """One checks.jsonl line of build/driver/<run>/<stem>/<func>/attempt-<n>/, and its C."""
    folder = roots / "driver" / run / STEM / FUNC / f"attempt-{attempt}"
    (folder / "checks").mkdir(parents=True, exist_ok=True)
    name = f"checks/{n:04d}.c"
    if text is not None:
        (folder / name).write_bytes(text.encode("utf-8"))
    record = {"best_percent": 50.0, "exit": 1, "n": n, "source": name, "sweep": False,
              "sweep_hit": None, **line}  # fmt: skip
    with (folder / "checks.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(record) + "\n")


def test_load_adds_each_plain_check_the_archive_does_not_hold(roots):
    _check(roots, "20261101-000000", 1, 1, _c("return a;"), best_percent=61.5)
    _check(roots, "20261101-000000", 1, 2, _c("return a;"), best_percent=61.5)  # the same C
    _check(roots, "20261102-000000", 2, 1, _c("return 2;"), best_percent=70.0)
    loaded = archive.load(STEM, START, FUNC)
    assert [(one.score, one.klass, one.stack_score) for one in loaded] == [
        (70.0, None, None), (61.5, None, None)]  # fmt: skip
    assert loaded[0].origin == "check 20261102-000000/attempt-2/0001"
    assert loaded[0].source == _c("return 2;")


def test_load_skips_sweeps_tool_errors_unscored_and_missing_checks(roots):
    _check(roots, "r1", 1, 1, _c("return 3;"), sweep=True, best_percent=90.0)
    _check(roots, "r1", 1, 2, _c("return 4;"), exit=2)
    _check(roots, "r1", 1, 3, _c("return 5;"), best_percent=None)
    _check(roots, "r1", 1, 4, None)
    _check(roots, "r1", 1, 5, None, best_percent=10.0)
    (roots / "driver" / "r1" / STEM / FUNC / "attempt-1" / "checks" / "0005.c").write_bytes(b"\xff")
    _check(roots, "r1", 1, 6, _c("return 6;"), source="../../escape.c")
    assert archive.load(STEM, START, FUNC) == []


def test_load_leaves_out_a_hold_run(roots):
    _check(roots, "held", 1, 1, _c("return 7;"))
    (roots / "driver" / "held" / archive.HOLD_RUN_MARKER).write_text("", encoding="utf-8")
    assert archive.load(STEM, START, FUNC) == []


def test_load_keeps_what_search_measured_over_a_check_of_the_same_source(roots):
    archive.record(STEM, START, [entry(score=40.0, klass="slot")])
    _check(roots, "r1", 1, 1, _c(), best_percent=90.0)
    (only,) = archive.load(STEM, START, FUNC)
    assert (only.score, only.klass) == (40.0, "slot")


# ---- seeds ------------------------------------------------------------------------------------


def test_seeds_are_the_best_of_each_class_best_first():
    entries = [entry(_c("return 1;"), 90.0, "branch"), entry(_c("return 2;"), 95.0, "branch"),
               entry(_c("return 3;"), 80.0, "register"), entry(_c("return 4;"), 85.0, None),
               entry(_c("return 5;"), 70.0, "slot")]  # fmt: skip
    seeds = archive.seeds(entries)
    best = [(95.0, "branch"), (85.0, None), (80.0, "register"), (70.0, "slot")]
    assert [(one.score, one.klass) for one in seeds] == best[: archive.SEEDS]
