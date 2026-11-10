"""The arm table and the per-arm session environment (07.2-12; D-10, D-11, D-12, D-26).

Owner rule: no test reads, prints or asserts on a real API key. Every environment below is
built from scratch with made-up values; nothing is read from os.environ, so a key the owner
has set can never reach an assertion or a log. No test contacts a provider.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from reverseapoc import backends
from reverseapoc.backends import ArmError, load_arms, preflight, session_env

DEEPSEEK = "deepseek-flash"
DEEPSEEK_URL = "https://api.deepseek.com/anthropic"
OPUS = "claude-opus-5-5"
CLAUDE_ARMS = ("claude-opus-5-5", "claude-fable-5-1", "claude-haiku-5-5", "claude-sonnet-5-5")
FAKE_DEEPSEEK = "made-up-deepseek-value-0001"  # never a real key
FAKE_ZAI = "made-up-zai-value-0002"
PINS = ("ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL")  # fmt: skip

_DEEPSEEK_TOML = """\
[arms."deepseek-flash"]
harness = "claude"
backend = "deepseek"
model = "deepseek-flash"
base_url = "https://api.deepseek.com/anthropic"
key_env = "DEEPSEEK_API_KEY"
sends_disassembly = true
accepted_init = ["deepseek-flash"]
coauthor = "DeepSeek V4.1-Flash <noreply@deepseek.com>"
max_workers = 3

[arms."deepseek-flash".prices]
input = 0.30
output = 1.20
cache_read = 0.30
cache_creation = 0.30
"""


def _arms() -> dict[str, backends.Arm]:
    return load_arms(backends.ARMS_TOML)


def _table(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "backends.toml"
    path.write_text(text, encoding="utf-8")
    return path


# ---- the table ----


def test_load_arms():
    """The committed table: each Claude arm keyed by its model id on the Claude login (no base
    URL, no key variable), and deepseek-flash on DeepSeek's endpoint with its key's NAME."""
    arms = _arms()
    for name in CLAUDE_ARMS:
        arm = arms[name]
        assert (arm.name, arm.model, arm.backend, arm.harness) == (name, name, "anthropic", "claude")
        assert (arm.base_url, arm.key_env, arm.coauthor, arm.prices) == (None, None, None, None)
        assert arm.sends_disassembly is True and not arm.egress
    arm = arms[DEEPSEEK]
    assert (arm.backend, arm.model, arm.key_env) == ("deepseek", DEEPSEEK, "DEEPSEEK_API_KEY")
    assert arm.base_url == DEEPSEEK_URL and arm.base_url.startswith("https://")
    assert arm.sends_disassembly is True and arm.egress
    assert arm.accepted_init == (DEEPSEEK,)


def test_a_valid_table_loads(tmp_path):
    arms = load_arms(_table(tmp_path, _DEEPSEEK_TOML))
    assert list(arms) == [DEEPSEEK] and arms[DEEPSEEK].prices.output == 1.20


@pytest.mark.parametrize(("old", "new", "field"), [
    ("max_workers = 3\n", "max_workers = 3\ncolour = \"red\"\n", "colour"),  # unknown
    ('model = "deepseek-flash"\n', "", "model"),  # missing
    ('key_env = "DEEPSEEK_API_KEY"', 'key_env = "sk-made-up-0003"', "key_env"),  # key-shaped
    ('key_env = "DEEPSEEK_API_KEY"', 'key_env = "deepseek_api_key"', "key_env"),
    ("https://api.deepseek.com/anthropic", "http://api.deepseek.com/anthropic", "base_url"),
    ("https://api.deepseek.com/anthropic", "ftp://127.0.0.1/x", "base_url"),
    ('harness = "claude"', 'harness = "cursor"', "harness"),
    ('backend = "deepseek"', 'backend = "Deep Seek"', "backend"),
    ("sends_disassembly = true", 'sends_disassembly = "yes"', "sends_disassembly"),
    ("max_workers = 3", "max_workers = 0", "max_workers"),
    ("input = 0.30", "input = -1.0", "prices"),
])  # fmt: skip
def test_a_bad_field_is_refused_naming_the_arm_and_field(tmp_path, old, new, field):
    assert old in _DEEPSEEK_TOML
    with pytest.raises(ArmError) as exc:
        load_arms(_table(tmp_path, _DEEPSEEK_TOML.replace(old, new, 1)))
    assert DEEPSEEK in str(exc.value) and field in str(exc.value), str(exc.value)


def test_an_anthropic_arm_has_no_endpoint_or_key(tmp_path):
    text = ('[arms."claude-opus-5-5"]\nharness = "claude"\nbackend = "anthropic"\n'
            'model = "claude-opus-5-5"\nsends_disassembly = true\nmax_workers = 3\n'
            'base_url = "https://example.invalid/anthropic"\n')  # fmt: skip
    with pytest.raises(ArmError) as exc:
        load_arms(_table(tmp_path, text))
    assert OPUS in str(exc.value) and "base_url" in str(exc.value)


# ---- the session environment (D-12) ----


def test_session_env_hosted():
    """The hosted arm's endpoint, its key as the bearer token, an empty API key, no
    nonessential traffic and the three default-model pins; no arm's key variable is left."""
    arms = _arms()
    zai = dataclasses.replace(arms[DEEPSEEK], name="other-hosted", key_env="ZAI_API_KEY")
    arms = {**arms, zai.name: zai}
    base = {"PATH": "made-up", "DEEPSEEK_API_KEY": FAKE_DEEPSEEK, "ZAI_API_KEY": FAKE_ZAI}
    env = session_env(arms[DEEPSEEK], base, arms)
    assert env["ANTHROPIC_BASE_URL"] == DEEPSEEK_URL
    assert env["ANTHROPIC_AUTH_TOKEN"] == FAKE_DEEPSEEK
    assert env["ANTHROPIC_API_KEY"] == ""
    assert env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    assert [env[pin] for pin in PINS] == [DEEPSEEK] * 3
    assert "DEEPSEEK_API_KEY" not in env and "ZAI_API_KEY" not in env
    assert FAKE_ZAI not in env.values()
    assert env["PATH"] == "made-up"
    assert base["DEEPSEEK_API_KEY"] == FAKE_DEEPSEEK  # the base is not modified


def test_session_env_anthropic_strips():
    """A Claude arm: an inherited base URL, token and default-model pin are removed (they
    would route the claude.ai login elsewhere), and so is every arm's key variable."""
    arms = _arms()
    base = {"PATH": "made-up", "ANTHROPIC_BASE_URL": "https://example.invalid/anthropic",
            "ANTHROPIC_AUTH_TOKEN": "made-up-token-0004",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "made-up-model",
            "DEEPSEEK_API_KEY": FAKE_DEEPSEEK}  # fmt: skip
    env = session_env(arms[OPUS], base, arms)
    for name in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_DEFAULT_HAIKU_MODEL"):
        assert name not in env, name
    for arm in arms.values():
        assert arm.key_env is None or arm.key_env not in env, arm.name
    assert env == {"PATH": "made-up"}


def test_session_env_without_the_table_uses_the_committed_one():
    """RULINGS names session_env(arm, base_env): the table defaults to the committed one."""
    arms = _arms()
    base = {"DEEPSEEK_API_KEY": FAKE_DEEPSEEK}
    assert session_env(arms[OPUS], base) == {}


def test_session_env_refuses_an_empty_token():
    """The env builder itself never sets a base URL without a token (Pitfall 5)."""
    arms = _arms()
    with pytest.raises(ArmError) as exc:
        session_env(arms[DEEPSEEK], {"DEEPSEEK_API_KEY": ""}, arms)
    assert "DEEPSEEK_API_KEY" in str(exc.value)


# ---- the preflight (D-11, D-26 token-leak guard) ----


@pytest.mark.parametrize("value", [None, "", "\t \t"])
def test_preflight_refusals(value):
    """A missing, empty or whitespace key: refused naming the variable and the endpoint, never
    the value."""
    arm = _arms()[DEEPSEEK]
    env = {"PATH": "made-up"} if value is None else {"DEEPSEEK_API_KEY": value}
    with pytest.raises(ArmError) as exc:
        preflight(arm, env, allow_egress=(DEEPSEEK,))
    text = str(exc.value)
    assert "DEEPSEEK_API_KEY" in text and DEEPSEEK_URL in text, text
    if value:
        assert value not in text


def test_preflight_refuses_egress_without_the_flag():
    arm = _arms()[DEEPSEEK]
    with pytest.raises(ArmError) as exc:
        preflight(arm, {"DEEPSEEK_API_KEY": FAKE_DEEPSEEK}, allow_egress=())
    text = str(exc.value)
    assert DEEPSEEK in text and "--allow-egress" in text and FAKE_DEEPSEEK not in text


@pytest.mark.parametrize("stray", ["glm-5.3", OPUS])
def test_preflight_refuses_a_stray_egress_name(stray):
    """D-11: an --allow-egress that names no selected sending arm is refused, so a typo can
    never open a backend."""
    arms = _arms()
    with pytest.raises(ArmError) as exc:
        preflight(arms[DEEPSEEK], {"DEEPSEEK_API_KEY": FAKE_DEEPSEEK},
                  allow_egress=(DEEPSEEK, stray))  # fmt: skip
    assert stray in str(exc.value)
    with pytest.raises(ArmError):
        preflight(arms[OPUS], {}, allow_egress=(OPUS,))


def test_preflight_passes():
    arms = _arms()
    preflight(arms[DEEPSEEK], {"DEEPSEEK_API_KEY": FAKE_DEEPSEEK}, allow_egress=(DEEPSEEK,))
    preflight(arms[OPUS], {}, allow_egress=())
