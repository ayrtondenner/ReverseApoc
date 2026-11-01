"""The stream lower bound of a timed-out session (quick 261101-js8, owner decisions 1 to 5).

A session the wall clock killed never emits the CLI's `result` event, so its attempt record
carries the lower bound `streamjson.stream_usage` reads from the stream: the distinct assistant
messages (the last event of each `message.id` wins), their token counts, the larger of their
output and the `system/thinking_tokens` estimate, priced per million tokens for the init model.
A session with a result still records the result's figures. Every event here is made up.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from reverseapoc import streamjson
from reverseapoc.session import run_session
from reverseapoc.streamjson import Usage, usage
from test_driver import Night, Sess, _one

OPUS = "claude-opus-5-5"
FABLE = "claude-fable-5-1"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "stream" / "timeout_usage.jsonl"
_FAKE_SLEEP_S = 30  # the fake sleeps this long after its stream, so only the deadline ends it
_STREAM_WAIT_S = 20  # real seconds the stream clock waits for the whole stream at most
_PAST_ANY_DEADLINE = 1.0e9
_NEWLINE = b"\n"
_TOKEN_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens",
               "cache_creation_input_tokens")  # fmt: skip


def _assistant(message_id: object, counts: tuple[object, ...] | None, *,
               kind: str = "assistant") -> dict:  # fmt: skip
    """A made-up assistant event: `counts` in the order input, output, cache_read,
    cache_creation (a None count is left out); `message_id` None leaves the id out."""
    message: dict = {"role": kind, "content": [{"type": "text", "text": "made-up"}]}
    if message_id is not None:
        message["id"] = message_id
    if counts is not None:
        message["usage"] = {k: v for k, v in zip(_TOKEN_KEYS, counts, strict=True)
                            if v is not None}  # fmt: skip
    return {"type": kind, "message": message}


def _thinking(delta: object) -> dict:
    return {"type": "system", "subtype": "thinking_tokens", "estimated_tokens": 0,
            "estimated_tokens_delta": delta}  # fmt: skip


_ONE_MESSAGE = (_assistant("m1", (1000, 500, 20000, 3000)),)


def _tokens(use: Usage) -> tuple[int, int, int, int]:
    return (use.input_tokens, use.output_tokens, use.cache_read_tokens,
            use.cache_creation_tokens)  # fmt: skip


# --- stream_usage on made-up events ---


def test_stream_usage_dedupes_assistant_events_by_message_id():
    events = (
        _assistant("m1", (5, 1, 7, 11)),
        _assistant("m1", (5, 9, 7, 11)),
        _assistant("m2", (3, 2, 0, 0)),
        _assistant("m3", (True, "9", None, None)),
        _assistant(None, (1000, 1000, 1000, 1000)),
        _assistant("u1", (1000, 1000, 1000, 1000), kind="user"),
    )
    use = streamjson.stream_usage(events, OPUS)
    assert use.turns == 3
    assert _tokens(use) == (8, 11, 7, 11)
    assert use.duration_ms == 0


def test_stream_usage_output_takes_the_larger_of_messages_and_thinking():
    thinking = (_assistant("m1", (0, 30, 0, 0)), _thinking(100), _thinking(150))
    assert streamjson.stream_usage(thinking, OPUS).output_tokens == 250
    messages = (_assistant("m1", (0, 400, 0, 0)), _thinking(100))
    assert streamjson.stream_usage(messages, OPUS).output_tokens == 400
    ill_typed = (_assistant("m1", (0, 30, 0, 0)), _thinking(100), _thinking("150"))
    assert streamjson.stream_usage(ill_typed, OPUS).output_tokens == 100


@pytest.mark.parametrize(("model", "cost"), [(OPUS, 0.042), (FABLE, 0.1)])
def test_stream_usage_cost_is_tokens_times_the_model_price(model, cost):
    use = streamjson.stream_usage(_ONE_MESSAGE, model)
    assert use.cost_usd == pytest.approx(cost)
    assert _tokens(use) == (1000, 500, 20000, 3000)
    assert use.turns == 1


def test_stream_usage_prices_are_the_fitted_ones():
    prices = streamjson.PRICES_PER_MTOK
    assert tuple(prices[OPUS]) == (4.0, 20.0, 0.20, 8.0)
    assert tuple(prices[FABLE]) == (10.0, 50.0, 0.25, 20.0)
    assert prices[OPUS]._fields == ("input", "output", "cache_read", "cache_creation")
    init_ids = {i for ids in streamjson.ACCEPTED_INIT_MODELS.values() for i in ids}
    assert init_ids <= set(prices)


@pytest.mark.parametrize("model", ["claude-haiku-4-5", None, [OPUS]])
def test_stream_usage_unknown_model_costs_nothing(model):
    use = streamjson.stream_usage(_ONE_MESSAGE, model)
    assert use.cost_usd == 0.0
    assert _tokens(use) == (1000, 500, 20000, 3000)
    assert use.turns == 1


def test_stream_usage_of_no_events_is_zero():
    assert streamjson.stream_usage((), OPUS) == Usage(0, 0, 0, 0, 0, 0.0, 0) == usage({})


def test_stream_usage_is_a_lower_bound_of_the_result():
    """Owner decision 5: input and the cache classes are exact, output and cost never above."""
    result = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 2,
              "total_cost_usd": 0.072,
              "modelUsage": {OPUS: {"inputTokens": 1000, "outputTokens": 2000,
                                    "cacheReadInputTokens": 20000,
                                    "cacheCreationInputTokens": 3000,
                                    "costUSD": 0.072}}}  # fmt: skip
    events = (
        _assistant("a", (0, 1, 0, 0)),
        _assistant("a", (600, 40, 10000, 3000)),
        _thinking(300),
        _assistant("b", (400, 60, 10000, 0)),
        _thinking(200),
        result,
    )
    bound, full = streamjson.stream_usage(events, OPUS), usage(result)
    assert (bound.input_tokens, bound.cache_read_tokens, bound.cache_creation_tokens) == (
        full.input_tokens, full.cache_read_tokens, full.cache_creation_tokens)  # fmt: skip
    assert bound.output_tokens == 500 <= full.output_tokens
    assert bound.cost_usd == pytest.approx(0.042)
    assert bound.cost_usd <= full.cost_usd


# --- the driver's record of a timed-out session and of a session with a result ---


class _StreamClock:
    """A clock for run_session that stands still until the transcript holds every line of the
    fixture (or `_STREAM_WAIT_S` real seconds passed), then is past any deadline: the session's
    own timeout path kills the sleeping fake with the whole stream read, without a real wait."""

    def __init__(self, transcript: Path, lines: int) -> None:
        self._transcript = transcript
        self._lines = lines
        self._started: float | None = None

    def _read(self) -> int:
        if not self._transcript.is_file():
            return 0
        return self._transcript.read_bytes().count(_NEWLINE)

    def __call__(self) -> float:
        now = time.monotonic()
        if self._started is None:
            self._started = now
        waiting = now - self._started < _STREAM_WAIT_S
        return 0.0 if waiting and self._read() < self._lines else _PAST_ANY_DEADLINE


def _stream_runner(argv, *, cwd, env, transcript, timeout_s, **hooks):
    """Night._session's keyword signature: the fake replays its fixture, then sleeps until the
    stream clock passes the deadline, so the session ends timed out."""
    clock = _StreamClock(Path(transcript), FIXTURE.read_bytes().count(_NEWLINE))
    return run_session([*argv, "--sleep", str(_FAKE_SLEEP_S)], cwd=cwd, env=env,
                       transcript=transcript, timeout_s=timeout_s, clock=clock,
                       **hooks)  # fmt: skip


def test_timeout_record_carries_the_stream_lower_bound(tmp_path):
    night = Night(tmp_path, sessions=[Sess("timeout_usage", write=None)])
    night.run(config={"attempts_per_function": 1}, session=_stream_runner)
    record = _one(night.kinds("attempt"))
    assert (record["outcome"], record["abort_reason"]) == ("GAVE_UP", "timeout")
    assert record["model"] == OPUS
    tokens = {"input": 1200, "output": 500, "cache_read": 20000, "cache_creation": 3000}
    assert (record["turns"], record["tokens"]) == (2, tokens)
    assert record["cost_usd"] == pytest.approx(0.0428)
    assert record["cost_usd"] > 0
    ended = night.kinds("run")[-1]
    assert ended["event"] == "ENDED"
    assert ended["totals"]["cost_usd"] == pytest.approx(0.0428)
    assert ended["totals"]["tokens"] == tokens


def test_result_record_still_copies_the_result(tmp_path):
    """Owner decision 3: a session with a result records exactly the result's figures."""
    night = Night(tmp_path, sessions=[Sess("success", write=None)])
    night.run(config={"attempts_per_function": 1})
    record = _one(night.kinds("attempt"))
    tokens = {"input": 1200, "output": 300, "cache_read": 5000, "cache_creation": 800}
    assert (record["turns"], record["tokens"]) == (3, tokens)
    assert record["cost_usd"] == 0.25
    assert record["abort_reason"] is None
