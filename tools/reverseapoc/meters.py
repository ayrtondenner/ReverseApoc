# SPDX-License-Identifier: GPL-3.0-or-later
"""`reverseapoc meters` (todo usage-meters-per-subscription): the subscription and credit meters
read from the tools themselves, so a run can be sized to a budget without the owner's
screenshots (docs/model-routing.md "Reading the meters").

One reading per meter: source, meter, used, limit or remaining, unit (percent, credits, usd),
window (5h, week, month, total), resets_at when known, read_at (UTC, this read) and as_of (when
the source itself took the figure, for a cached or logged one), and how it was read (a file path
or an endpoint, never a secret). A source that cannot be read gives one reading with an `error`,
never an exception: `read` and `read_all` are what a budget-sized drive calls.

The sources:
- openrouter: GET https://openrouter.ai/api/v1/credits with OPENROUTER_API_KEY (Seams.fetch).
- codex: the newest `token_count` event with `rate_limits` in ~/.codex/sessions/**/rollout-*.jsonl
  (only non-ephemeral sessions write these; a drive's `codex exec --ephemeral` writes none).
- copilot: the AI credits (totalNanoAiu / 1e9) of this UTC month's Copilot CLI sessions under
  ~/.copilot/session-state/*/events.jsonl; the account's balance is not stored locally.
- agy: `agy -p /usage` (Seams.run_agy) parsed by driver.agy_quota.
- claude-code: the usage panel's cache, ~/.claude.json `cachedUsageUtilization`.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import subprocess
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import backends
from .driver import AGY_EXE, AGY_USAGE, agy_quota

SOURCES = ("openrouter", "codex", "copilot", "agy", "claude-code")

OPENROUTER_URL = "https://openrouter.ai/api/v1/credits"
OPENROUTER_KEY = "OPENROUTER_API_KEY"
HTTP_TIMEOUT_S = 30
AGY_TIMEOUT_S = 60
NANO_PER_CREDIT = 1e9  # Copilot's totalNanoAiu counts nano AI units (assumed: 1 AIU = 1 credit)

_CODEX_WINDOWS = {300: "5h", 10080: "week"}  # window_minutes
_CLAUDE_WINDOWS = {"weekly": "week", "five_hour": "5h"}  # a limit's `group`
_PERCENT = 100.0


class MeterError(Exception):
    """A source that cannot be read; its message becomes the reading's `error`."""


@dataclass(frozen=True)
class Reading:
    source: str
    meter: str
    read_at: str
    how: str
    used: float | None = None
    limit: float | None = None
    remaining: float | None = None
    unit: str | None = None
    window: str | None = None
    resets_at: str | None = None
    as_of: str | None = None
    error: str | None = None

    def to_json(self) -> dict:
        return dataclasses.asdict(self)


def _http_get(url: str, headers: Mapping[str, str]) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "reverseapoc", **headers})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
        return resp.read()


def _run_agy(env: Mapping[str, str]) -> str:
    agy = shutil.which(AGY_EXE)
    if agy is None:
        raise MeterError(f"unavailable: {AGY_EXE} is not on PATH")
    done = subprocess.run([agy, *AGY_USAGE], env=dict(env), capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=AGY_TIMEOUT_S, check=False)  # fmt: skip
    return f"{done.stdout or ''}\n{done.stderr or ''}"


@dataclass(frozen=True)
class Seams:
    """What a read touches outside its own files: the environment, the home whose tool stores
    are read, the clock, the HTTP GET (url, headers) -> body and the `agy -p /usage` run
    (env) -> its output."""

    env: Mapping[str, str] = field(default_factory=lambda: os.environ)
    home: Path = field(default_factory=Path.home)
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    fetch: Callable[[str, Mapping[str, str]], bytes] = _http_get
    run_agy: Callable[[Mapping[str, str]], str] = _run_agy


def default_seams() -> Seams:
    return Seams()


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _utc(text: str) -> datetime:
    """An ISO 8601 time from a tool's store, in UTC; one without an offset is taken as UTC
    (never the machine's local time)."""
    moment = datetime.fromisoformat(text)
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def _codex_sessions(seams: Seams) -> Path:
    return seams.home / ".codex" / "sessions"


def _copilot_state(seams: Seams) -> Path:
    return seams.home / ".copilot" / "session-state"


def _claude_json(seams: Seams) -> Path:
    return seams.home / ".claude.json"


def _number(doc: Mapping, key: str, what: str) -> float:
    value = doc.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MeterError(f"{what}: `{key}` is not a number")
    return value


def _jsonl(path: Path) -> Iterator[dict]:
    """The JSON object lines of `path`; a line that is not one is skipped (a log being written
    can end mid-line)."""
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            doc = json.loads(raw)
        except ValueError:
            continue
        if isinstance(doc, dict):
            yield doc


# ---- OpenRouter ----


def _openrouter(seams: Seams, base: dict) -> list[Reading]:
    key = seams.env.get(OPENROUTER_KEY)
    if not key:
        raise MeterError(f"unavailable: {OPENROUTER_KEY} is not set")
    doc = json.loads(seams.fetch(OPENROUTER_URL, {"Authorization": f"Bearer {key}"}))
    data = doc.get("data") if isinstance(doc, dict) else None
    if not isinstance(data, dict):
        raise MeterError("the credits response holds no `data` object")
    credits = _number(data, "total_credits", "credits response")
    usage = _number(data, "total_usage", "credits response")
    return [Reading(**base, meter="credits", used=usage, limit=credits, remaining=credits - usage,
                    unit="usd", window="total")]  # fmt: skip


# ---- Codex ----


def _codex_record(sessions: Path) -> tuple[Path, dict] | None:
    """The newest rate-limit record: the last one in the most recently written rollout file
    that holds any."""
    files = sorted(sessions.rglob("rollout-*.jsonl"), key=lambda p: p.stat().st_mtime,
                   reverse=True)  # fmt: skip
    for path in files:
        records = [doc for doc in _jsonl(path) if isinstance(doc.get("payload"), dict)
                   and isinstance(doc["payload"].get("rate_limits"), dict)]  # fmt: skip
        if records:
            return path, records[-1]
    return None


def _codex_window(name: str, limit: Mapping, as_of: datetime, base: dict) -> Reading:
    used = _number(limit, "used_percent", f"rate_limits.{name}")
    minutes = limit.get("window_minutes")
    window = _CODEX_WINDOWS.get(minutes, f"{minutes}min") if minutes is not None else None
    resets_at = None
    if isinstance(limit.get("resets_at"), int | float):
        resets_at = _iso(datetime.fromtimestamp(limit["resets_at"], UTC))
    elif isinstance(limit.get("resets_in_seconds"), int | float):
        resets_at = _iso(as_of + timedelta(seconds=limit["resets_in_seconds"]))
    return Reading(**base, meter=name, used=used, limit=_PERCENT, remaining=_PERCENT - used,
                   unit="percent", window=window, resets_at=resets_at,
                   as_of=_iso(as_of))  # fmt: skip


def _codex(seams: Seams, base: dict) -> list[Reading]:
    sessions = _codex_sessions(seams)
    found = _codex_record(sessions) if sessions.is_dir() else None
    if found is None:
        raise MeterError(f"unavailable: no rate-limit record under {sessions}")
    path, record = found
    as_of = _utc(record["timestamp"])
    limits = record["payload"]["rate_limits"]
    base = {**base, "how": str(path)}
    readings = [_codex_window(name, limits[name], as_of, base) for name in ("primary", "secondary")
                if isinstance(limits.get(name), dict)]  # fmt: skip
    credits = limits.get("credits")
    if isinstance(credits, dict) and credits.get("balance") is not None:
        readings.append(Reading(**base, meter="credits", remaining=float(credits["balance"]),
                                unit="credits", window="total", as_of=_iso(as_of)))  # fmt: skip
    return readings


# ---- Copilot ----


def _copilot_snapshot(events: Path) -> tuple[datetime, float] | None:
    """The time and AI credits of the session's last accounting snapshot, if any."""
    last = None
    for doc in _jsonl(events):
        data = doc.get("data")
        snapshot = data.get("accountingSnapshot") if isinstance(data, dict) else None
        if isinstance(snapshot, dict) and "totalNanoAiu" in snapshot:
            nano = _number(snapshot, "totalNanoAiu", "accountingSnapshot")
            last = _utc(doc["timestamp"]), nano / NANO_PER_CREDIT
    return last


def _copilot_session(events: Path) -> tuple[datetime, float] | None:
    """_copilot_snapshot, its error naming the session's file."""
    try:
        return _copilot_snapshot(events)
    except (MeterError, KeyError, TypeError, ValueError) as exc:
        raise MeterError(f"{events}: {type(exc).__name__}: {exc}") from exc


def _copilot(seams: Seams, base: dict) -> list[Reading]:
    state = _copilot_state(seams)
    if not state.is_dir():
        raise MeterError(f"unavailable: no Copilot CLI session state at {state}")
    now = seams.now().astimezone(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # A file last written before the month cannot hold a snapshot taken in it.
    recent = (events for events in state.glob("*/events.jsonl")
              if events.stat().st_mtime >= start.timestamp())  # fmt: skip
    sessions = filter(None, map(_copilot_session, recent))
    month = [(at, credits) for at, credits in sessions if at >= start]
    as_of = _iso(max(at for at, _ in month)) if month else None
    return [Reading(**base, meter="AI credits (CLI sessions)",
                    used=sum(credits for _, credits in month), unit="credits", window="month",
                    as_of=as_of)]  # fmt: skip


# ---- agy ----


def _agy_env(env: Mapping[str, str]) -> dict[str, str]:
    """The env `agy -p /usage` runs with: an agy arm's session env (backends.session_env), as
    the driver's quota step runs it (driver.cli_query_env, the token-leak guard)."""
    try:
        arms = backends.load_arms()
    except backends.ArmError as exc:
        raise MeterError(f"unavailable: {exc}") from exc
    arm = next((a for a in arms.values() if a.harness == backends.AGY), None)
    if arm is None:
        raise MeterError(f"unavailable: no {backends.AGY} arm in {backends.ARMS_TOML}")
    return backends.session_env(arm, env, arms)


def _agy(seams: Seams, base: dict) -> list[Reading]:
    quota = agy_quota(seams.run_agy(_agy_env(seams.env)))
    if not quota["measured"]:
        raise MeterError(f"unavailable: `{AGY_EXE} {' '.join(AGY_USAGE)}` printed nothing "
                         "machine-readable (spike 012)")  # fmt: skip
    remaining = quota["remaining"] if quota["remaining"] is not None else 0
    return [Reading(**base, meter="weekly quota", remaining=remaining, window="week")]


# ---- Claude Code ----


def _claude_limit(limit: Mapping, as_of: str, base: dict) -> Reading:
    used = _number(limit, "percent", "cachedUsageUtilization limit")
    model = ((limit.get("scope") or {}).get("model") or {}).get("display_name")
    meter = f"{limit.get('kind')} {model}" if model else str(limit.get("kind"))
    group = limit.get("group")
    resets_at = _iso(_utc(limit["resets_at"])) if limit.get("resets_at") else None
    return Reading(**base, meter=meter, used=used, limit=_PERCENT, remaining=_PERCENT - used,
                   unit="percent", window=_CLAUDE_WINDOWS.get(group, group),
                   resets_at=resets_at, as_of=as_of)  # fmt: skip


def _claude_code(seams: Seams, base: dict) -> list[Reading]:
    path = _claude_json(seams)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise MeterError(f"{path} is not a JSON object")
    cache = doc.get("cachedUsageUtilization")
    utilization = cache.get("utilization") if isinstance(cache, dict) else None
    limits = utilization.get("limits") if isinstance(utilization, dict) else None
    if not isinstance(limits, list) or not limits:
        raise MeterError(f"unavailable: no cachedUsageUtilization limits in {path} (the usage "
                         "panel has not been opened since the CLI started caching it)")  # fmt: skip
    as_of = _iso(datetime.fromtimestamp(_number(cache, "fetchedAtMs", str(path)) / 1000, UTC))
    return [_claude_limit(limit, as_of, base) for limit in limits if isinstance(limit, dict)]


_READERS: dict[str, tuple[Callable[[Seams, dict], list[Reading]], Callable[[Seams], str]]] = {
    "openrouter": (_openrouter, lambda s: f"GET {OPENROUTER_URL}"),
    "codex": (_codex, lambda s: str(_codex_sessions(s))),  # a reading names its rollout file
    "copilot": (_copilot, lambda s: str(_copilot_state(s))),
    "agy": (_agy, lambda s: f"{AGY_EXE} {' '.join(AGY_USAGE)}"),
    "claude-code": (_claude_code, lambda s: str(_claude_json(s))),
}


def read(source: str, seams: Seams | None = None) -> list[Reading]:
    """The readings of one source; a source that cannot be read gives one error reading."""
    if source not in _READERS:
        raise ValueError(f"unknown meter source {source!r} (known: {', '.join(SOURCES)})")
    seams = seams or default_seams()
    reader, how = _READERS[source]
    base = {"source": source, "read_at": _iso(seams.now()), "how": how(seams)}
    try:
        return reader(seams, base)
    except MeterError as exc:
        return [Reading(**base, meter="-", error=str(exc))]
    except (OSError, ValueError, KeyError, TypeError, AttributeError,
            subprocess.SubprocessError) as exc:  # a malformed store or a failed call  # fmt: skip
        return [Reading(**base, meter="-", error=f"{type(exc).__name__}: {exc}")]


def read_all(sources: Iterable[str] = SOURCES, seams: Seams | None = None) -> list[Reading]:
    seams = seams or default_seams()
    return [reading for source in sources for reading in read(source, seams)]


# ---- the text report ----


def _figure(value: float, unit: str | None) -> str:
    number = f"{value:,.2f}".rstrip("0").rstrip(".")  # 1,500,000 and 2,336.21, never 1.5e+06
    return f"{number}%" if unit == "percent" else f"{number} {unit or ''}".rstrip()


def _line(r: Reading, now: datetime) -> str:
    head = f"{r.source:<12} {r.meter:<28}"
    if r.error:
        return f"{head} {r.error}"
    parts = [r.window or "-"]
    if r.used is not None:
        of = f" of {_figure(r.limit, r.unit)}" if r.limit is not None else ""
        parts.append(f"{_figure(r.used, r.unit)} used{of}")
    if r.remaining is not None:
        parts.append(f"{_figure(r.remaining, r.unit)} left")
    if r.resets_at:
        stale = datetime.fromisoformat(r.resets_at) <= now
        parts.append(f"resets {r.resets_at}" + (" (reset since)" if stale else ""))
    if r.as_of:
        parts.append(f"as of {r.as_of}")
    return f"{head} {', '.join(parts)}  [{r.how}]"


def format_readings(readings: Sequence[Reading], now: datetime) -> str:
    """One line per reading; a window whose reset is already past is marked `reset since`
    (its figure predates the reset)."""
    return "\n".join(_line(r, now) for r in readings)
