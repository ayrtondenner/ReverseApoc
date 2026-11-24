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
        "resets_at": None, "as_of": None, "stale": False, "error": None}  # fmt: skip


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


def _claude_bar(tmp_path: Path, resets_at: str) -> meters.Reading:
    """The weekly_all bar of a cache fetched 2026-11-13T09:00Z whose bar resets at `resets_at`,
    read at _NOW (2026-11-13T12:00Z)."""
    doc = json.loads((_FIXTURES / "claude.json").read_text(encoding="utf-8"))
    doc["cachedUsageUtilization"]["utilization"]["limits"][0]["resets_at"] = resets_at
    (tmp_path / ".claude.json").write_text(json.dumps(doc), encoding="utf-8")
    return _one(meters.read("claude-code", _seams(tmp_path)), "weekly_all")


def test_claude_code_withholds_a_bar_that_reset_since_the_cache(tmp_path):
    """todo claude-meter-stale (owner ruling: withhold): a bar whose reset is already past was
    read before that reset, so its figure is last window's and is not reported."""
    bar = _claude_bar(tmp_path, "2026-11-13T10:00:00+00:00")
    assert bar.stale is True and bar.error is None
    assert (bar.used, bar.remaining) == (None, None)
    assert (bar.as_of, bar.resets_at) == ("2026-11-13T09:00:00Z", "2026-11-13T10:00:00Z")
    doc = bar.to_json()
    assert doc["used"] is None and doc["remaining"] is None and doc["stale"] is True
    line = meters.format_readings([bar], _NOW)
    assert "stale (read 2026-11-13T09:00:00Z, reset 2026-11-13T10:00:00Z)" in line
    assert "used" not in line and "left" not in line


def test_claude_code_keeps_a_bar_whose_reset_is_ahead(tmp_path):
    bar = _claude_bar(tmp_path, "2026-11-16T19:00:00+00:00")
    assert bar.stale is False and (bar.used, bar.remaining) == (61, 39)
    line = meters.format_readings([bar], _NOW)
    assert "61% used of 100%" in line and "stale" not in line


def test_the_verb_prints_a_withheld_bar_as_json_null(tmp_path, monkeypatch, capsys):
    _claude_bar(tmp_path, "2026-11-13T10:00:00+00:00")
    monkeypatch.setattr(meters, "default_seams", lambda: _seams(tmp_path))
    assert cli.main(["meters", "--json", "--source", "claude-code"]) == 0
    bar = next(r for r in json.loads(capsys.readouterr().out) if r["meter"] == "weekly_all")
    assert (bar["used"], bar["remaining"], bar["stale"]) == (None, None, True)
    assert cli.main(["meters", "--source", "claude-code"]) == 0
    assert "stale (read" in capsys.readouterr().out


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


# ---- todo budget-meter-wiring: the drive's meter seam ----


def _log(repo: Path, records: list[dict]) -> None:
    """attempts.jsonl under `repo` holding `records` (only the fields the meter reads)."""
    from reverseapoc import driver

    path = repo / driver.ATTEMPT_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def _attempt(harness: str, backend: str, model: str, **figures) -> dict:
    return {"kind": "attempt", "harness": harness, "backend": backend, "model_requested": model,
            "cost_usd": 0.0, **figures}  # fmt: skip


def test_the_budget_meter_reads_the_copilot_arms_own_credits(tmp_path):
    """A Copilot arm's reading is the credits its records carry (each session's usage file):
    a running total in `credits`, other arms' records and other lines left out."""
    _log(tmp_path, [_attempt("copilot", "github", "claude-haiku-5.5", credits=2.5),
                    _attempt("copilot", "github", "claude-haiku-5.5", credits=3.0),
                    _attempt("copilot", "github", "claude-sonnet-5.5", credits=40.0),
                    {"kind": "run", "event": "ENDED"}])  # fmt: skip
    reading = meters.budget_meter(tmp_path)("copilot-haiku-5-5")
    assert (reading.used, reading.unit) == (5.5, "credits")


def test_the_budget_meter_reads_a_claude_arms_week_from_its_cost(tmp_path):
    """A Claude arm's `%week` is its records' cost_usd at $17.73 a point (quota.toml)."""
    _log(tmp_path, [_attempt("claude", "anthropic", "claude-haiku-5-5", cost_usd=17.73),
                    _attempt("claude", "anthropic", "claude-haiku-5-5", cost_usd=8.865),
                    _attempt("claude", "anthropic", "claude-opus-5-5", cost_usd=100.0)])
    reading = meters.budget_meter(tmp_path)("claude-haiku-5-5")
    assert reading.unit == "%week" and reading.used == pytest.approx(1.5)
    assert meters.budget_meter(tmp_path / "none")("claude-haiku-5-5").used == 0


def test_the_budget_meter_reads_openrouter_live(tmp_path):
    """An OpenRouter arm's reading is the credits API's total usage, in dollars; a failed read
    is no reading."""
    body = json.dumps({"data": {"total_credits": 20.0, "total_usage": 7.25}}).encode()
    keyed = _seams(tmp_path, env={"OPENROUTER_API_KEY": _KEY}, fetch=lambda url, headers: body)
    reading = meters.budget_meter(tmp_path, keyed)("deepseek-flash")
    assert (reading.used, reading.unit) == (7.25, "$")
    assert meters.budget_meter(tmp_path, _seams(tmp_path))("deepseek-flash") is None


def test_the_budget_meter_reads_nothing_where_no_meter_moves(tmp_path):
    """Codex (--ephemeral sessions write no rollout), agy, and an arm with no quota entry: no
    reading, so a budget holds by its session cap alone."""
    meter = meters.budget_meter(tmp_path, _seams(tmp_path))
    assert [meter(arm) for arm in ("gpt-6.1-terra", "gemini-flash", "glm-5.3")] == [None] * 3


def test_the_drives_default_meter_seam_is_the_budget_meter(tmp_path):
    from reverseapoc import driver

    _log(tmp_path, [_attempt("claude", "anthropic", "claude-haiku-5-5", cost_usd=17.73)])
    seams = driver.default_seams(tmp_path)
    assert seams.meter("claude-haiku-5-5").used == pytest.approx(1.0)
    assert seams.meter("gpt-6.1-terra") is None


def test_an_unusable_table_mid_night_is_no_reading(tmp_path, monkeypatch):
    """refuse_budgets read quota.toml and backends.toml before the night; one that turns
    unusable during it gives no reading (the session cap holds), never a stopped night."""
    from reverseapoc import quota

    def broken():
        raise quota.QuotaError("quota.toml: made up")

    _log(tmp_path, [_attempt("claude", "anthropic", "claude-haiku-5-5", cost_usd=17.73)])
    monkeypatch.setattr(quota, "load_quota", broken)
    assert meters.budget_meter(tmp_path)("claude-haiku-5-5") is None
