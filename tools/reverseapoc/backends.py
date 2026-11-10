# SPDX-License-Identifier: GPL-3.0-or-later
"""The drive arms (Phase 07.2 plan 12; D-10, D-11, D-12, D-26; RESEARCH Q7, Pitfall 5).

`config/driver/backends.toml` names every arm a night can run: the Claude arms (the Claude
Code login, keyed by their model id) and the hosted arms, which run in the same Claude Code
harness against a provider's Anthropic-compatible endpoint. `load_arms` reads and validates
it (stdlib tomllib, as mechanics.py reads config/mechanics.toml).

The table holds the NAME of the environment variable with each hosted arm's key, never a key.
`session_env` builds a session's environment from the driver's base environment: every arm's
key variable and every inherited endpoint, token and default-model variable are removed, so no
session sees another arm's key and a Claude arm never inherits a base URL that would route the
owner's claude.ai login elsewhere (D-12); a hosted arm then gets its endpoint, its own key as
the bearer token (ANTHROPIC_AUTH_TOKEN), an empty ANTHROPIC_API_KEY, no nonessential traffic
and the three default-model pins set to its model. Every non-Anthropic arm's session also gets
hooks.EGRESS_ENV=1, so the matching hook denies its reads of orig/ and third_party/ (D-10).
`estimate_cost` prices a session's tokens at its arm's backends.toml prices (RESEARCH A3).

`preflight` runs before any session (D-11, D-26): a non-Anthropic arm that sends disassembly
runs only when it is also named by `--allow-egress`, an `--allow-egress` naming anything else is
refused, and an arm with a base URL whose key variable is missing, empty or blank is refused,
because Claude Code would otherwise send the claude.ai login to that endpoint (Pitfall 5). The
env builder refuses the same empty token on its own. No message ever holds a key's value. A
loopback arm with no key variable (the local llama.cpp server, D-18) gets the fixed
LOOPBACK_TOKEN instead; a non-loopback base URL always needs a key variable.

07.2-13 (D-12, D-13): a Codex arm (harness `codex`) runs the Codex CLI on the owner's ChatGPT
login, so it takes no base URL and no key variable, and lists no init ids (Codex streams no
init event). Its session env loses, besides every arm key, OPENAI_API_KEY and OPENAI_BASE_URL
(which would move the CLI off that login), every inherited ANTHROPIC_* variable and every
Google key variable (RULINGS "Token-leak guard covers every arm"): no harness ever sees another
vendor's credential.
"""

from __future__ import annotations

import math
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .hooks import EGRESS_ENV
from .streamjson import _COST_DIGITS, TOKENS_PER_MTOK, Price, Usage
from .targets import REPO_ROOT

ARMS_TOML = REPO_ROOT / "config" / "driver" / "backends.toml"
HARNESSES = ("claude", "codex", "agy")  # the agent CLI a session runs under (schema 3)
ANTHROPIC = "anthropic"  # the backend of the Claude Code login (no base URL, no key variable)
# D-18, D-26: the bearer token of a loopback arm with no key variable (the local llama.cpp
# server), non-empty so Claude Code never falls back to the claude.ai login; loopback only.
LOOPBACK_TOKEN = "local"
BACKEND_RE = re.compile(r"[a-z][a-z0-9-]{0,31}")  # a record's `backend` (RULINGS "Schema 3")

BASE_URL_ENV = "ANTHROPIC_BASE_URL"
AUTH_TOKEN_ENV = "ANTHROPIC_AUTH_TOKEN"
API_KEY_ENV = "ANTHROPIC_API_KEY"
NONESSENTIAL_ENV = "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"
MODEL_PINS = ("ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
              "ANTHROPIC_DEFAULT_HAIKU_MODEL")  # fmt: skip
INHERITED = (BASE_URL_ENV, AUTH_TOKEN_ENV, *MODEL_PINS, EGRESS_ENV)  # stripped from every session
CODEX = "codex"  # the Codex CLI harness (07.2-13, D-13)
OPENAI_ENV = ("OPENAI_API_KEY", "OPENAI_BASE_URL")  # stripped from a Codex session (D-12)
_ANTHROPIC_PREFIX = "ANTHROPIC_"
_GOOGLE_KEY = re.compile(r"(?:GOOGLE|GEMINI)[A-Z0-9_]*_(?:KEY|CREDENTIALS)", re.IGNORECASE)

_REQUIRED = ("harness", "backend", "model", "sends_disassembly", "max_workers")
_HOSTED = ("accepted_init", "prices", "coauthor")  # required off the Claude login
_ENDPOINT = ("base_url", "key_env")  # a claude-harness arm off the Claude login
_FIELDS = (*_REQUIRED, *_ENDPOINT, *_HOSTED)
_PRICE_FIELDS = Price._fields
_NAME = re.compile(r"[a-z0-9][a-z0-9.-]{0,63}")
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:-]{0,63}")
_KEY_ENV = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")  # an UPPER_SNAKE variable name
_COAUTHOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .+-]{0,63} <[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+>")
_LOOPBACK = ("127.0.0.1", "localhost", "::1")


class ArmError(ValueError):
    """backends.toml or an arm's environment is not usable; the text names the arm and field."""


@dataclass(frozen=True)
class Arm:
    """One `[arms.<name>]` table."""

    name: str
    harness: str
    backend: str
    model: str
    sends_disassembly: bool
    max_workers: int
    base_url: str | None = None
    key_env: str | None = None
    accepted_init: tuple[str, ...] = ()
    prices: Price | None = None
    coauthor: str | None = None

    @property
    def egress(self) -> bool:
        """The arm sends the context pack to a backend other than Anthropic (D-11)."""
        return self.sends_disassembly and self.backend != ANTHROPIC


def _text(table: Mapping, key: str, pattern: re.Pattern) -> str:
    value = table[key]
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ArmError(f"{key}: {value!r} is not a {pattern.pattern} string")
    return value


def _key_env(value: object) -> str:
    """An UPPER_SNAKE variable name. The value is never repeated in the error: a key pasted
    here by mistake must not reach a console or a log."""
    if not isinstance(value, str) or not _KEY_ENV.fullmatch(value):
        raise ArmError("key_env: is not an UPPER_SNAKE environment variable name; it names "
                       "the variable that holds the key, never the key (D-12)")  # fmt: skip
    return value


def _loopback(url: str) -> bool:
    return urlsplit(url).hostname in _LOOPBACK


def _base_url(value: object) -> str:
    """https://, or plain http:// to a loopback host only (a local server)."""
    if not isinstance(value, str):
        raise ArmError(f"base_url: {value!r} is not a string")
    parts = urlsplit(value)
    loopback = parts.scheme == "http" and _loopback(value)
    if not (parts.scheme == "https" and parts.hostname) and not loopback:
        raise ArmError(f"base_url: {value!r} is neither https:// nor http:// to a loopback host")
    return value


def _prices(value: object) -> Price:
    if not isinstance(value, Mapping) or set(value) != set(_PRICE_FIELDS):
        raise ArmError(f"prices: needs exactly {', '.join(_PRICE_FIELDS)} (USD per MTok)")
    numbers = [value[key] for key in _PRICE_FIELDS]
    if any(isinstance(n, bool) or not isinstance(n, int | float) or not math.isfinite(n) or n < 0
           for n in numbers):  # fmt: skip
        raise ArmError(f"prices: {dict(value)!r} holds a value that is not a number >= 0")
    return Price(*(float(n) for n in numbers))


def _accepted(value: object, harness: str) -> tuple[str, ...]:
    """The init ids; empty only off the Claude Code harness, whose CLI streams no init event
    (07.2-13: Codex)."""
    if not isinstance(value, list) or (not value and harness == "claude"):
        raise ArmError(f"accepted_init: {value!r} is not a non-empty list of model ids")
    for item in value:
        if not isinstance(item, str) or not _MODEL.fullmatch(item):
            raise ArmError(f"accepted_init: {item!r} is not a model id")
    return tuple(value)


def _present(table: Mapping, hosted: bool, harness: str) -> None:
    """The field set: unknown names refused; the required five always; off the Claude login
    the three hosted fields, and a Claude-harness arm its endpoint and key variable; on the
    Claude login none of those."""
    unknown = sorted(set(table) - set(_FIELDS))
    if unknown:
        raise ArmError(f"{', '.join(unknown)}: unknown field (fields: {', '.join(_FIELDS)})")
    need = [*_REQUIRED, *(_HOSTED if hosted else ())]
    if hosted and harness == "claude":  # key_env too, unless the endpoint is loopback (_arm)
        need.append("base_url")
    missing = [key for key in need if key not in table]
    if missing:
        raise ArmError(f"{', '.join(missing)}: missing")
    if harness != "claude":  # 07.2-13 (D-12): its CLI's own login, never an endpoint or a key
        extra = [key for key in _ENDPOINT if key in table]
        if extra:
            raise ArmError(f"{', '.join(extra)}: not allowed on the {harness} harness, which "
                           "signs in with its own CLI login (D-12)")  # fmt: skip
    if not hosted:
        extra = [key for key in (*_ENDPOINT, *_HOSTED) if key in table]
        if extra:
            raise ArmError(f"{', '.join(extra)}: not allowed on the {ANTHROPIC} login "
                           "(its model keeps streamjson's tables and driver.coauthor)")  # fmt: skip


def _arm(name: str, table: object) -> Arm:
    if not _NAME.fullmatch(name):
        raise ArmError(f"the arm name is not {_NAME.pattern}")
    if not isinstance(table, Mapping):
        raise ArmError("is not a table")
    harness = table.get("harness")
    if harness not in HARNESSES:
        raise ArmError(f"harness: {harness!r} is not one of {', '.join(HARNESSES)}")
    backend = _text(table, "backend", BACKEND_RE) if "backend" in table else None
    _present(table, backend != ANTHROPIC, harness)
    if not isinstance(table["sends_disassembly"], bool):
        raise ArmError(f"sends_disassembly: {table['sends_disassembly']!r} is not true or false")
    workers = table["max_workers"]
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ArmError(f"max_workers: {workers!r} is not an integer >= 1")
    url = table.get("base_url")
    if url is not None and "key_env" not in table and not _loopback(_base_url(url)):
        raise ArmError("key_env: missing; only a loopback base_url runs without a key variable "
                       "(it gets LOOPBACK_TOKEN, D-26)")  # fmt: skip
    return Arm(name=name, harness=harness, backend=backend, model=_text(table, "model", _MODEL),
               sends_disassembly=table["sends_disassembly"], max_workers=workers,
               base_url=_base_url(table["base_url"]) if "base_url" in table else None,
               key_env=_key_env(table["key_env"]) if "key_env" in table else None,
               accepted_init=_accepted(table["accepted_init"], harness)
               if "accepted_init" in table
               else (),
               prices=_prices(table["prices"]) if "prices" in table else None,
               coauthor=_text(table, "coauthor", _COAUTHOR) if "coauthor" in table
               else None)  # fmt: skip


def load_arms(path: Path = ARMS_TOML) -> dict[str, Arm]:
    """Read and validate backends.toml; ArmError names the file, the arm and the field."""
    path = Path(path)
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ArmError(f"{path}: {exc}") from exc
    arms = data.get("arms")
    if set(data) != {"arms"} or not isinstance(arms, Mapping) or not arms:
        raise ArmError(f"{path}: needs one [arms.<name>] table per arm and nothing else")
    out = {}
    for name, table in arms.items():
        try:
            out[name] = _arm(name, table)
        except ArmError as exc:
            raise ArmError(f"{path}: arm {name!r}: {exc}") from None
    return out


def _token(arm: Arm, env: Mapping[str, str]) -> str:
    """The value of the arm's key variable; ArmError, naming the variable and the endpoint but
    never the value, when it is missing, empty or blank (the token-leak guard, D-26). An arm
    with no key variable (load_arms allows that on a loopback base URL only) gets
    LOOPBACK_TOKEN: llama-server ignores it without --api-key (RESEARCH Q7)."""
    if arm.key_env is None and arm.base_url is not None and _loopback(arm.base_url):
        return LOOPBACK_TOKEN
    value = env.get(arm.key_env, "") if arm.key_env else ""
    if not value.strip():
        raise ArmError(f"arm {arm.name}: {arm.key_env} is missing or empty, so the session would "
                       f"send the claude.ai login to {arm.base_url}; set {arm.key_env} as a user "
                       "environment variable (D-12, D-26)")  # fmt: skip
    return value


def _foreign(name: str) -> bool:
    """Another vendor's variable in a Codex session: any ANTHROPIC_* name, any Google key or
    credentials name (case-insensitive: Windows names are)."""
    return name.upper().startswith(_ANTHROPIC_PREFIX) or bool(_GOOGLE_KEY.fullmatch(name))


def session_env(arm: Arm, base_env: Mapping[str, str],
                arms: Mapping[str, Arm] | None = None) -> dict[str, str]:  # fmt: skip
    """A session's environment (D-12): `base_env` without every arm's key variable (the
    committed table's when `arms` is None) and without INHERITED; then, for an arm with a base
    URL, the endpoint, its own key as ANTHROPIC_AUTH_TOKEN, an empty ANTHROPIC_API_KEY, no
    nonessential traffic and the default-model pins (RESEARCH Q7). A Codex arm's session also
    loses OPENAI_ENV, every ANTHROPIC_* variable and every Google key variable (07.2-13).
    `base_env` is not changed."""
    table = load_arms() if arms is None else arms
    drop = {*INHERITED, *(a.key_env for a in (*table.values(), arm) if a.key_env)}
    if arm.harness == CODEX:
        drop.update(OPENAI_ENV)
    env = {key: value for key, value in base_env.items()
           if key not in drop and not (arm.harness == CODEX and _foreign(key))}  # fmt: skip
    if arm.backend != ANTHROPIC:  # D-10: the hook then denies its reads of orig/, third_party/
        env[EGRESS_ENV] = "1"
    if arm.base_url is None:
        return env
    env.update({BASE_URL_ENV: arm.base_url, AUTH_TOKEN_ENV: _token(arm, base_env),
                API_KEY_ENV: "", NONESSENTIAL_ENV: "1"})  # fmt: skip
    env.update(dict.fromkeys(MODEL_PINS, arm.model))
    return env


def estimate_cost(usage: Usage, arm: Arm) -> float:
    """`usage`'s four token classes at the arm's prices per million tokens, rounded like the
    driver's totals: a hosted session's cost (RESEARCH A3: the CLI's own figure for a model it
    does not know is not trusted)."""
    counts = (usage.input_tokens, usage.output_tokens, usage.cache_read_tokens,
              usage.cache_creation_tokens)  # fmt: skip
    total = sum(n * p for n, p in zip(counts, arm.prices, strict=True)) / TOKENS_PER_MTOK
    return round(total, _COST_DIGITS)


def preflight(arm: Arm, env: Mapping[str, str], *, allow_egress: Sequence[str]) -> None:
    """Before any session (D-11, D-26): every `--allow-egress` name must be this arm, and this
    arm one that sends disassembly off the machine; such an arm needs its name there; and an
    arm with a base URL needs a non-blank key in `env`. ArmError otherwise."""
    for name in allow_egress:
        if name != arm.name or not arm.egress:
            raise ArmError(f"--allow-egress {name} names no arm of this night that sends the "
                           f"context pack off the machine (the night runs {arm.name}); refused "
                           "so that a typo opens no backend (D-11)")  # fmt: skip
    if arm.egress and arm.name not in allow_egress:
        raise ArmError(f"arm {arm.name} sends the context pack to {arm.backend}: give "
                       f"--allow-egress {arm.name} as well as --night-model {arm.name} (D-11)")
    if arm.base_url is not None:
        _token(arm, env)
