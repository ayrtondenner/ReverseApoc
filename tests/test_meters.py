"""`reverseapoc meters` (todo usage-meters-per-subscription): the subscription and credit meters
read from the tools themselves.

Every test builds a synthetic home under tmp_path from the hand-written fixtures in
tests/fixtures/meters/ (the real files' key shapes, made-up values, no prompts) and injects the
HTTP and agy seams: no test touches the network, the real home or a live CLI."""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from reverseapoc import cli, meters

_FIXTURES = Path(__file__).parent / "fixtures" / "meters"
_AGY = Path(__file__).parent / "fixtures" / "agy"
_NOW = datetime(2026, 11, 13, 12, 0, 0, tzinfo=UTC)
_READ_AT = "2026-11-13T12:00:00Z"
_KEY = "sk-or-v1-made-up-key-never-printed"


def _no_fetch(url, headers):
    raise AssertionError(f"no HTTP call expected: {url}")


def _no_agy(env):
    raise AssertionError("no agy run expected")


def _seams(home: Path, *, env=None, fetch=_no_fetch, run_agy=_no_agy) -> meters.Seams:
    return meters.Seams(env={} if env is None else env, home=home, now=lambda: _NOW,
                        fetch=fetch, run_agy=run_agy)  # fmt: skip


def _codex_home(home: Path) -> Path:
    day = home / ".codex" / "sessions" / "2026" / "11" / "12"
    day.mkdir(parents=True)
    rollout = day / "rollout-2026-11-12T10-00-00-made-up.jsonl"
    shutil.copy(_FIXTURES / "codex_rollout.jsonl", rollout)
    return rollout


def _copilot_session(home: Path, name: str, lines: list[dict] | None = None) -> Path:
    session = home / ".copilot" / "session-state" / name
    session.mkdir(parents=True)
    events = session / "events.jsonl"
    if lines is None:
        shutil.copy(_FIXTURES / "copilot_events.jsonl", events)
    else:
        events.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return events


def _one(readings, meter=None):
    picked = [r for r in readings if meter is None or r.meter == meter]
    assert len(picked) == 1, readings
    return picked[0]


# ---- the reading ----


def test_reading_json_holds_every_field():
    reading = meters.Reading(source="codex", meter="primary", read_at=_READ_AT, how="x",
                             used=1.0, limit=100.0, remaining=99.0, unit="percent", window="5h")
    assert reading.to_json() == {
        "source": "codex", "meter": "primary", "read_at": _READ_AT, "how": "x", "used": 1.0,
        "limit": 100.0, "remaining": 99.0, "unit": "percent", "window": "5h",
        "resets_at": None, "as_of": None, "error": None}  # fmt: skip


def test_unknown_source_is_refused():
    with pytest.raises(ValueError, match="unknown meter source"):
        meters.read("nope", _seams(Path(".")))


# ---- OpenRouter ----


def test_openrouter_without_key_is_unavailable(tmp_path):
    reading = _one(meters.read("openrouter", _seams(tmp_path)))
    assert reading.error == "unavailable: OPENROUTER_API_KEY is not set"
    assert reading.used is None and reading.read_at == _READ_AT
    assert reading.how == "GET https://openrouter.ai/api/v1/credits"


def test_openrouter_reads_credits_and_usage_with_the_key(tmp_path):
    calls = []

    def fetch(url, headers):
        calls.append((url, dict(headers)))
        return json.dumps({"data": {"total_credits": 20.0, "total_usage": 7.25}}).encode()

    reading = _one(meters.read("openrouter", _seams(tmp_path, env={"OPENROUTER_API_KEY": _KEY},
                                                    fetch=fetch)))  # fmt: skip
    assert calls == [("https://openrouter.ai/api/v1/credits",
                      {"Authorization": f"Bearer {_KEY}"})]  # fmt: skip
    assert (reading.used, reading.limit, reading.remaining) == (7.25, 20.0, 12.75)
    assert (reading.unit, reading.window, reading.error) == ("usd", "total", None)
    assert _KEY not in json.dumps(reading.to_json())


def test_openrouter_http_failure_is_an_error_reading_without_the_key(tmp_path):
    def fetch(url, headers):
        raise OSError(f"connection refused to {url}")

    reading = _one(meters.read("openrouter", _seams(tmp_path, env={"OPENROUTER_API_KEY": _KEY},
                                                    fetch=fetch)))  # fmt: skip
    assert reading.error.startswith("OSError: connection refused")
    assert _KEY not in json.dumps(reading.to_json())


def test_openrouter_wrong_shape_is_an_error_reading(tmp_path):
    reading = _one(meters.read("openrouter", _seams(
        tmp_path, env={"OPENROUTER_API_KEY": _KEY}, fetch=lambda url, headers: b'{"data": {}}')))
    assert "total_credits" in reading.error


# ---- Codex ----


def test_codex_reads_the_newest_rate_limit_record(tmp_path):
    rollout = _codex_home(tmp_path)
    readings = meters.read("codex", _seams(tmp_path))
    primary, secondary, credits = (_one(readings, m) for m in ("primary", "secondary", "credits"))
    assert (primary.used, primary.limit, primary.remaining) == (15.5, 100.0, 84.5)
    assert (primary.unit, primary.window) == ("percent", "5h")
    assert primary.resets_at == "2026-11-12T11:01:00Z"  # resets_in_seconds from the record
    assert primary.as_of == "2026-11-12T10:01:00Z" and primary.how == str(rollout)
    assert (secondary.used, secondary.window) == (41.0, "week")
    assert secondary.resets_at == "2026-11-16T16:00:00Z"  # resets_at, epoch seconds
    assert (credits.remaining, credits.used, credits.unit, credits.window) == (
        99.25, None, "credits", "total")
    assert all(r.read_at == _READ_AT and r.error is None for r in readings)


def test_codex_picks_the_newest_file_with_a_record(tmp_path):
    older = _codex_home(tmp_path)
    newer = older.with_name("rollout-2026-11-13T09-00-00-made-up.jsonl")
    newer.write_text('{"timestamp":"2026-11-13T09:00:00Z","type":"session_meta","payload":{}}\n',
                     encoding="utf-8")  # fmt: skip
    os.utime(older, (1_000_000_000, 1_000_000_000))
    readings = meters.read("codex", _seams(tmp_path))
    assert {r.how for r in readings} == {str(older)}  # the newer file holds no record


def test_codex_window_other_than_5h_or_week_is_named_in_minutes(tmp_path):
    day = tmp_path / ".codex" / "sessions" / "2026" / "11" / "13"
    day.mkdir(parents=True)
    record = {"timestamp": "2026-11-13T09:00:00Z", "type": "event_msg",
              "payload": {"type": "token_count", "rate_limits": {
                  "primary": {"used_percent": 5, "window_minutes": 60}}}}  # fmt: skip
    (day / "rollout-x.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    reading = _one(meters.read("codex", _seams(tmp_path)))
    assert (reading.window, reading.resets_at, reading.used) == ("60min", None, 5)


def test_codex_timestamp_without_offset_is_utc(tmp_path):
    day = tmp_path / ".codex" / "sessions" / "2026" / "11" / "13"
    day.mkdir(parents=True)
    record = {"timestamp": "2026-11-13T09:00:00", "type": "event_msg",
              "payload": {"type": "token_count", "rate_limits": {
                  "primary": {"used_percent": 5, "window_minutes": 300,
                              "resets_in_seconds": 60}}}}  # fmt: skip
    (day / "rollout-x.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    reading = _one(meters.read("codex", _seams(tmp_path)))
    assert (reading.as_of, reading.resets_at) == ("2026-11-13T09:00:00Z", "2026-11-13T09:01:00Z")


def test_codex_malformed_limit_is_an_error_reading(tmp_path):
    day = tmp_path / ".codex" / "sessions" / "2026" / "11" / "13"
    day.mkdir(parents=True)
    record = {"timestamp": "2026-11-13T09:00:00Z", "type": "event_msg",
              "payload": {"type": "token_count", "rate_limits": {"primary": {"used_percent": "x"}}}}
    (day / "rollout-x.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    reading = _one(meters.read("codex", _seams(tmp_path)))
    assert "used_percent" in reading.error


def test_codex_without_sessions_is_unavailable(tmp_path):
    reading = _one(meters.read("codex", _seams(tmp_path)))
    assert reading.error.startswith("unavailable: no rate-limit record")


# ---- Copilot ----


def test_copilot_sums_this_months_ai_credits(tmp_path):
    _copilot_session(tmp_path, "a")  # 0.75 credits at its shutdown, 2026-11-12
    _copilot_session(tmp_path, "b", [  # running: its last checkpoint counts
        {"type": "session.usage_checkpoint", "timestamp": "2026-11-13T11:00:00Z",
         "data": {"accountingSnapshot": {"totalNanoAiu": 125000000.0}}}])
    _copilot_session(tmp_path, "c", [  # last month: not counted
        {"type": "session.shutdown", "timestamp": "2026-10-31T23:59:00Z",
         "data": {"accountingSnapshot": {"totalNanoAiu": 9000000000.0}}}])
    _copilot_session(tmp_path, "d", [  # no accounting at all
        {"type": "session.shutdown", "timestamp": "2026-11-13T10:00:00Z",
         "data": {"totalPremiumRequests": 0}}])
    reading = _one(meters.read("copilot", _seams(tmp_path)))
    assert reading.used == pytest.approx(0.875)
    assert (reading.unit, reading.window, reading.limit, reading.error) == (
        "credits", "month", None, None)
    assert reading.as_of == "2026-11-13T11:00:00Z"
    assert reading.how == str(tmp_path / ".copilot" / "session-state")


def test_copilot_month_is_the_utc_month(tmp_path):
    _copilot_session(tmp_path, "a", [  # 2026-10-31T23:30Z, so last month in UTC
        {"type": "session.shutdown", "timestamp": "2026-11-01T01:30:00+02:00",
         "data": {"accountingSnapshot": {"totalNanoAiu": 9000000000.0}}}])
    _copilot_session(tmp_path, "b", [  # no offset: UTC
        {"type": "session.shutdown", "timestamp": "2026-11-01T00:30:00",
         "data": {"accountingSnapshot": {"totalNanoAiu": 1000000000.0}}}])
    reading = _one(meters.read("copilot", _seams(tmp_path)))
    assert (reading.used, reading.as_of) == (1.0, "2026-11-01T00:30:00Z")


def test_copilot_skips_sessions_last_written_before_the_month(tmp_path):
    events = _copilot_session(tmp_path, "old", [
        {"type": "session.shutdown", "timestamp": "2026-11-02T00:00:00Z",
         "data": {"accountingSnapshot": {"totalNanoAiu": 1000000000.0}}}])
    os.utime(events, (1_000_000_000, 1_000_000_000))  # 2001: it cannot hold this month
    assert _one(meters.read("copilot", _seams(tmp_path))).used == 0


def test_copilot_bad_snapshot_names_its_file(tmp_path):
    events = _copilot_session(tmp_path, "bad", [
        {"type": "session.shutdown", "timestamp": "2026-11-12T00:00:00Z",
         "data": {"accountingSnapshot": {"totalNanoAiu": None}}}])
    reading = _one(meters.read("copilot", _seams(tmp_path)))
    assert str(events) in reading.error and "totalNanoAiu" in reading.error


def test_copilot_non_object_data_holds_no_snapshot(tmp_path):
    _copilot_session(tmp_path, "odd", [{"type": "session.shutdown", "data": "x"}])
    reading = _one(meters.read("copilot", _seams(tmp_path)))
    assert (reading.used, reading.error) == (0, None)


def test_copilot_without_session_state_is_unavailable(tmp_path):
    reading = _one(meters.read("copilot", _seams(tmp_path)))
    assert reading.error.startswith("unavailable: no Copilot CLI session state")


# ---- agy ----


def test_agy_reuses_the_driver_parser_for_remaining_quota(tmp_path):
    text = (_AGY / "usage_remaining.txt").read_text(encoding="utf-8")
    envs = []

    def run_agy(env):
        envs.append(env)
        return text

    env = {"PATH": "x", "OPENROUTER_API_KEY": _KEY, "ANTHROPIC_API_KEY": "k", "OPENAI_API_KEY": "k"}
    reading = _one(meters.read("agy", _seams(tmp_path, env=env, run_agy=run_agy)))
    assert len(envs) == 1 and envs[0]["PATH"] == "x"  # the session env (token-leak guard)
    assert not {"OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"} & set(envs[0])
    assert (reading.remaining, reading.window, reading.error) == (1500000, "week", None)
    assert reading.how == "agy -p /usage"


def test_agy_exhausted_quota_reads_zero_remaining(tmp_path):
    text = (_AGY / "usage_quota_error.txt").read_text(encoding="utf-8")
    reading = _one(meters.read("agy", _seams(tmp_path, run_agy=lambda env: text)))
    assert (reading.remaining, reading.error) == (0, None)


def test_agy_unreadable_usage_is_unavailable(tmp_path):
    text = (_AGY / "usage_unreadable.txt").read_text(encoding="utf-8")
    reading = _one(meters.read("agy", _seams(tmp_path, run_agy=lambda env: text)))
    assert reading.error == ("unavailable: `agy -p /usage` printed nothing machine-readable "
                             "(spike 012)")  # fmt: skip


def test_agy_missing_cli_is_an_error_reading(tmp_path):
    def run_agy(env):
        raise meters.MeterError("unavailable: agy is not on PATH")

    reading = _one(meters.read("agy", _seams(tmp_path, run_agy=run_agy)))
    assert reading.error == "unavailable: agy is not on PATH"


# ---- Claude Code ----


def test_claude_code_reads_the_cached_usage_panel(tmp_path):
    shutil.copy(_FIXTURES / "claude.json", tmp_path / ".claude.json")
    readings = meters.read("claude-code", _seams(tmp_path))
    weekly = _one(readings, "weekly_all")
    assert (weekly.used, weekly.limit, weekly.remaining) == (61, 100.0, 39)
    assert (weekly.unit, weekly.window) == ("percent", "week")
    assert weekly.resets_at == "2026-11-16T19:00:00Z"
    assert weekly.as_of == "2026-11-13T09:00:00Z"  # fetchedAtMs
    assert weekly.how == str(tmp_path / ".claude.json")
    assert _one(readings, "weekly_scoped Fable").used == 9
    assert _one(readings, "session").window == "5h"


def test_claude_code_without_the_cache_is_unavailable(tmp_path):
    (tmp_path / ".claude.json").write_text('{"numStartups": 1}', encoding="utf-8")
    reading = _one(meters.read("claude-code", _seams(tmp_path)))
    assert reading.error.startswith("unavailable: no cachedUsageUtilization")


def test_claude_code_non_object_cache_is_an_error_reading(tmp_path):
    (tmp_path / ".claude.json").write_text('{"cachedUsageUtilization": []}', encoding="utf-8")
    assert _one(meters.read("claude-code", _seams(tmp_path))).error.startswith("unavailable")
    (tmp_path / ".claude.json").write_text("[]", encoding="utf-8")
    assert _one(meters.read("claude-code", _seams(tmp_path))).error


def test_claude_code_unreadable_file_is_an_error_reading(tmp_path):
    (tmp_path / ".claude.json").write_text("{", encoding="utf-8")
    reading = _one(meters.read("claude-code", _seams(tmp_path)))
    assert reading.error.startswith("JSONDecodeError")


# ---- read_all and the verb ----


def test_read_all_never_crashes_and_keeps_source_order(tmp_path):
    readings = meters.read_all(meters.SOURCES, _seams(
        tmp_path, run_agy=lambda env: (_ for _ in ()).throw(OSError("boom"))))
    assert [r.source for r in readings] == list(meters.SOURCES)
    assert all(r.error for r in readings)


def test_format_marks_a_window_reset_since_the_record(tmp_path):
    _codex_home(tmp_path)
    text = meters.format_readings(meters.read("codex", _seams(tmp_path)), _NOW)
    primary = next(line for line in text.splitlines() if "primary" in line)
    assert "15.5% used" in primary and "reset since" in primary
    secondary = next(line for line in text.splitlines() if "secondary" in line)
    assert "reset since" not in secondary
    credits = next(line for line in text.splitlines() if "credits" in line)
    assert "99.25 credits left" in credits


def test_format_writes_large_figures_in_full():
    reading = meters.Reading(source="agy", meter="weekly quota", read_at=_READ_AT, how="x",
                             remaining=1500000, window="week")  # fmt: skip
    assert "1,500,000 left" in meters.format_readings([reading], _NOW)


def test_verb_prints_json_for_the_picked_sources(tmp_path, monkeypatch, capsys):
    _codex_home(tmp_path)
    monkeypatch.setattr(meters, "default_seams", lambda: _seams(tmp_path))
    assert cli.main(["meters", "--json", "--source", "codex", "--source", "openrouter"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert [r["source"] for r in doc] == ["codex"] * 3 + ["openrouter"]
    assert doc[-1]["error"] == "unavailable: OPENROUTER_API_KEY is not set"


def test_verb_prints_text_by_default(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(meters, "default_seams", lambda: _seams(tmp_path))
    assert cli.main(["meters", "--source", "openrouter"]) == 0
    out = capsys.readouterr().out
    assert "openrouter" in out and "unavailable: OPENROUTER_API_KEY is not set" in out
