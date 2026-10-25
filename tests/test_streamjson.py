"""The stream-json reader (AGT-03, AGT-04, D-08, D-36): every way a session ends maps to one
driver action, the init event is asserted fail closed, and usage is summed from modelUsage.
The streams are the synthetic fixtures under tests/fixtures/stream/ (no game bytes)."""

from __future__ import annotations

import pytest

from conftest import REPO_ROOT
from reverseapoc import session
from reverseapoc.streamjson import (
    EXPECTED_MODEL,
    Disposition,
    ToolUse,
    Usage,
    check_init,
    classify,
    init_event,
    parse,
    parse_line,
    parse_version,
    tool_uses,
    usage,
)

STREAMS = REPO_ROOT / "tests" / "fixtures" / "stream"
TESTED_MAJOR = 2
MIN_VERSION = (2, 1, 240)


def _events(name: str) -> tuple[dict, ...]:
    parsed = parse((STREAMS / f"{name}.jsonl").read_text(encoding="utf-8").splitlines())
    assert parsed.malformed == 0
    return parsed.events


def _classify(name: str, exit_code: int | None, timed_out: bool = False) -> Disposition:
    return classify(_events(name), exit_code, timed_out)


@pytest.mark.parametrize(
    ("name", "exit_code"),
    [("rate_limit", 1), ("rejected", 1), ("http429", 1), ("limit_text", 1)],
)
def test_classify_limit(name, exit_code):
    assert _classify(name, exit_code) is Disposition.LIMIT


@pytest.mark.parametrize(
    ("name", "exit_code"),
    [
        ("auth", 1),
        ("oauth", 1),
        ("hold", 1),
        ("billing", 1),
        ("credits", 1),
        ("low_credit_text", 1),
        ("not_logged_in", 1),
    ],
)
def test_classify_stop(name, exit_code):
    assert _classify(name, exit_code) is Disposition.STOP


@pytest.mark.parametrize(
    ("name", "exit_code"),
    [("overloaded", 1), ("server_error", 1), ("no_result", 1)],
)
def test_classify_transient(name, exit_code):
    assert _classify(name, exit_code) is Disposition.TRANSIENT


def test_classify_transient_without_any_event():
    assert classify((), 0, False) is Disposition.TRANSIENT
    assert classify((), None, False) is Disposition.TRANSIENT


@pytest.mark.parametrize(
    ("name", "exit_code", "timed_out"),
    [
        ("success", 0, False),
        ("max_turns", 1, False),
        ("max_budget", 1, False),
        ("during_execution", 1, False),
        ("no_result", None, True),
    ],
)
def test_classify_attempt_done(name, exit_code, timed_out):
    assert _classify(name, exit_code, timed_out) is Disposition.ATTEMPT_DONE


def test_classify_precedence_stop_over_limit_over_transient_over_done():
    auth, limit, overloaded, done = (
        _events("auth")[1],
        _events("rate_limit")[1],
        _events("overloaded")[1],
        _events("success")[-1],
    )
    assert classify((limit, auth, done), 1, False) is Disposition.STOP
    assert classify((limit, done), 0, False) is Disposition.LIMIT
    assert classify((limit,), None, True) is Disposition.LIMIT
    assert classify((overloaded,), 1, False) is Disposition.TRANSIENT
    assert classify((overloaded, done), 0, False) is Disposition.ATTEMPT_DONE


def test_classify_rejected_with_an_unknown_error_code_stops():
    event = {
        "type": "rate_limit_event",
        "rate_limit_info": {"status": "rejected", "errorCode": "x"},
    }
    assert classify((event,), 1, False) is Disposition.STOP


def test_classify_ignores_limit_words_outside_the_result():
    said = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "Not logged in? hit your limit?"}]},
    }
    assert classify((said, _events("success")[-1]), 0, False) is Disposition.ATTEMPT_DONE


def test_dispositions_carry_no_outcome():
    """T-06-39: the stream never says MATCHED; the gate does."""
    assert {d.name for d in Disposition} == {"LIMIT", "STOP", "TRANSIENT", "ATTEMPT_DONE"}


def _problems(name: str) -> list[str]:
    init = init_event(_events(name))
    return check_init(init, tested_major=TESTED_MAJOR, min_version=MIN_VERSION)


@pytest.mark.parametrize(
    ("name", "word"),
    [
        ("bad_init_v1", "major"),
        ("bad_init_v3", "major"),
        ("bad_init_old", "minimum"),
        ("bad_init_model", "model"),
        ("bad_init_no_bash", "Bash"),
        ("bad_init_extra_tool", "WebFetch"),
        ("bad_init_mcp", "tavily"),
        ("bad_init_plugin", "security-guidance"),
    ],
)
def test_check_init_problems(name, word):
    problems = _problems(name)
    assert len(problems) == 1, problems
    assert word in problems[0]


def test_check_init_passes_the_success_init():
    assert _problems("success") == []
    init = init_event(_events("success"))
    assert check_init(init, tested_major=2, min_version="2.1.240") == []


def test_check_init_fails_closed_on_a_missing_or_unreadable_init():
    assert check_init(None, tested_major=2, min_version=MIN_VERSION) != []
    init = dict(init_event(_events("success")), claude_code_version="two")
    assert len(check_init(init, tested_major=2, min_version=MIN_VERSION)) == 1
    init = dict(init_event(_events("success")), tools="Read")
    assert len(check_init(init, tested_major=2, min_version=MIN_VERSION)) == 1


def test_expected_model_is_the_argv_model():
    assert EXPECTED_MODEL == session.MODEL == "claude-opus-5-5"


@pytest.mark.parametrize(
    ("text", "version"),
    [("2.1.240", (2, 1, 240)), ("2.1.240 (Claude Code)\n", (2, 1, 240)), ("10.0.3", (10, 0, 3))],
)
def test_parse_version(text, version):
    assert parse_version(text) == version


@pytest.mark.parametrize("text", ["", "two", "2.1", "v2.1.240", "2.1.240-beta"])
def test_parse_version_refuses(text):
    with pytest.raises(ValueError):
        parse_version(text)


def test_usage_sums_model_usage():
    result = {
        "type": "result",
        "num_turns": 7,
        "total_cost_usd": 1.25,
        "duration_ms": 61000,
        "modelUsage": {
            "claude-opus-5-5": {
                "inputTokens": 1000,
                "outputTokens": 200,
                "cacheReadInputTokens": 3000,
                "cacheCreationInputTokens": 400,
                "costUSD": 1.2,
            },
            "claude-haiku-4-5": {
                "inputTokens": 10,
                "outputTokens": 2,
                "cacheReadInputTokens": 30,
                "cacheCreationInputTokens": 4,
                "costUSD": 0.05,
            },
        },
    }
    assert usage(result) == Usage(
        input_tokens=1010,
        output_tokens=202,
        cache_read_tokens=3030,
        cache_creation_tokens=404,
        turns=7,
        cost_usd=1.25,
        duration_ms=61000,
    )


def test_usage_of_a_result_without_model_usage_is_zero():
    assert usage({"type": "result"}) == Usage(0, 0, 0, 0, 0, 0.0, 0)


def test_tool_uses_lists_paths():
    def call(name: str, **inp) -> dict:
        return {"type": "tool_use", "name": name, "input": inp}

    events = (
        {"type": "assistant", "message": {"content": [call("Read", file_path="/repo/a.c")]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "checking"},
                    call("Bash", command="uv run --frozen reverseapoc attempt check"),
                    call("Edit", file_path="/repo/src/ufo2p/u_00010000.c"),
                ]
            },
        },
        {"type": "assistant", "message": {"content": [call("Glob", pattern="*.c")]}},
        {"type": "result", "subtype": "success"},
    )
    assert tool_uses(events) == [
        ToolUse("Read", "/repo/a.c"),
        ToolUse("Bash", "uv run --frozen reverseapoc attempt check"),
        ToolUse("Edit", "/repo/src/ufo2p/u_00010000.c"),
        ToolUse("Glob", None),
    ]


def test_tool_uses_of_the_success_fixture():
    assert tool_uses(_events("success")) == [ToolUse("Edit", "/repo/src/ufo2p/u_00010000.c")]


def test_malformed_lines_are_counted():
    lines = (STREAMS / "malformed.jsonl").read_text(encoding="utf-8").splitlines()
    parsed = parse(lines)
    assert parsed.malformed == 2
    assert [event["type"] for event in parsed.events] == ["system", "assistant", "result"]


@pytest.mark.parametrize("line", ["[1, 2]", "42", '"text"', "null", "{", b"\xff\xfe"])
def test_parse_line_refuses_anything_but_an_object(line):
    assert parse_line(line) is None
