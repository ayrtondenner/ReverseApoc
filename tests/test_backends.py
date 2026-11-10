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
        assert (arm.name, arm.model, arm.backend) == (name, name, "anthropic")
        assert arm.harness == "claude"
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


def test_a_key_pasted_into_key_env_is_not_repeated(tmp_path):
    """D-12: a value under key_env that is not a variable name is refused without echoing it,
    in case it is a real key pasted by mistake."""
    text = _DEEPSEEK_TOML.replace('"DEEPSEEK_API_KEY"', '"made-up-pasted-value-0005"')
    with pytest.raises(ArmError) as exc:
        load_arms(_table(tmp_path, text))
    assert "key_env" in str(exc.value) and "made-up-pasted-value-0005" not in str(exc.value)


_SIGNED_IN_TOML = """\
[arms."made-up-arm"]
harness = "{harness}"
backend = "{backend}"
model = "made-up-model"
sends_disassembly = false
accepted_init = []
coauthor = "Made Up <noreply@example.invalid>"
max_workers = 1

[arms."made-up-arm".prices]
input = 0.0
output = 0.0
cache_read = 0.0
cache_creation = 0.0
"""


@pytest.mark.parametrize("text", [
    _SIGNED_IN_TOML.format(harness="codex", backend="openai"),
    _SIGNED_IN_TOML.format(harness="agy", backend="google"),
    _DEEPSEEK_TOML.replace("sends_disassembly = true", "sends_disassembly = false"),
    _DEEPSEEK_TOML.replace("sends_disassembly = true", "sends_disassembly = false").replace(
        "https://api.deepseek.com/anthropic", "https://127.0.0.1.example.invalid/anthropic"),
], ids=["codex", "agy", "https", "loopback-lookalike"])  # fmt: skip
def test_a_sending_arm_cannot_declare_it_sends_nothing(tmp_path, text):
    """07.2 review WR-01 (D-11): `sends_disassembly = false` is believed only of an arm that
    keeps the pack on the machine: the Claude Code harness on the Claude login or on a
    loopback endpoint. A Codex or agy arm (its CLI sends the prompt to OpenAI or Google) or an
    arm on a non-loopback endpoint that says false is refused at load time, so one wrong
    boolean never lets it run without --allow-egress."""
    with pytest.raises(ArmError) as exc:
        load_arms(_table(tmp_path, text))
    assert "sends_disassembly" in str(exc.value), str(exc.value)


def test_a_loopback_arm_may_send_nothing(tmp_path):
    """WR-01's one exception: the local arm on loopback keeps sends_disassembly = false."""
    text = (_DEEPSEEK_TOML.replace("sends_disassembly = true", "sends_disassembly = false")
            .replace("https://api.deepseek.com/anthropic", "http://127.0.0.1:8080"))
    arm = load_arms(_table(tmp_path, text))[DEEPSEEK]
    assert arm.sends_disassembly is False and not arm.egress


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


# ---- Task 2: the other hosted arms, the cost estimate and the egress marker ----


@pytest.mark.parametrize(("name", "backend", "url", "key_env", "model"), [
    ("glm-5.3", "zai", "https://api.z.ai/api/anthropic", "ZAI_API_KEY", "glm-5.3"),
    ("muse-spark-open", "openrouter", "https://openrouter.ai/api", "OPENROUTER_API_KEY",
     "meta/muse-spark-open"),
    ("qwen-hosted", "openrouter", "https://openrouter.ai/api", "OPENROUTER_API_KEY",
     "qwen/qwen3.6-35b-a3b"),
])  # fmt: skip
def test_hosted_arms_load(name, backend, url, key_env, model):
    """D-18 and the owner's Qwen ruling: GLM on z.ai, Muse Spark Open and the hosted Qwen
    through OpenRouter, each with its prices, its own init id and its vendor's credit line."""
    arm = _arms()[name]
    assert (arm.backend, arm.base_url, arm.key_env, arm.model) == (backend, url, key_env, model)
    assert arm.egress and arm.accepted_init == (model,)
    assert arm.prices is not None and arm.prices.input > 0 and arm.prices.output > 0
    assert arm.coauthor is not None and "<noreply@" in arm.coauthor


def test_every_hosted_cache_price_is_at_least_the_input_price():
    """Until the owner records the providers' cache prices, both cache classes are priced as
    input, so an estimate may overstate and never understate."""
    for arm in _arms().values():
        if arm.egress:
            assert arm.prices.cache_read == arm.prices.input == arm.prices.cache_creation, arm.name


def test_estimate_cost():
    """Tokens times the arm's prices per million tokens, over the four classes (RESEARCH A3:
    the CLI's figure for an unknown model is not trusted)."""
    from reverseapoc.streamjson import Usage

    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000, cache_read_tokens=1_000_000,
                  cache_creation_tokens=0, turns=3, cost_usd=9.99, duration_ms=1)  # fmt: skip
    assert backends.estimate_cost(usage, _arms()[DEEPSEEK]) == pytest.approx(0.30 + 1.20 + 0.30)


LOCAL = "qwen-local"
LOCAL_URL = "http://127.0.0.1:8080"


def test_local_arm():
    """D-18: the local llama.cpp arm on loopback, one worker, sending nothing off the machine,
    free, and needing no key variable."""
    arm = _arms()[LOCAL]
    assert (arm.backend, arm.base_url, arm.key_env, arm.model) == (
        "local", LOCAL_URL, None, "qwen3.6-35b-a3b")  # fmt: skip
    assert arm.sends_disassembly is False and not arm.egress
    assert arm.max_workers == 1 and arm.prices == (0.0, 0.0, 0.0, 0.0)
    assert arm.accepted_init == ("qwen3.6-35b-a3b",) and arm.coauthor


def test_claude_arms_take_a_night_of_ten_workers():
    """Nights run `--workers 10` on the Claude login (night 20261107-030004), and spike 012's
    Claude arms run at the same count, so a Claude arm's cap must not refuse it."""
    claude = [arm for arm in _arms().values() if arm.backend == "anthropic"]
    assert claude and all(arm.max_workers >= 10 for arm in claude)


def test_both_qwen_entries_are_one_model_family():
    """The owner's Qwen ruling: the hosted and the local Qwen run the same weights, and differ
    in backend (and so in endpoint, key, egress, price and workers), not in model family."""
    arms = _arms()
    hosted, local = arms["qwen-hosted"], arms[LOCAL]
    assert hosted.model.rsplit("/", 1)[-1] == local.model
    assert (hosted.backend, local.backend) == ("openrouter", "local")
    assert (hosted.harness, hosted.coauthor) == (local.harness, local.coauthor)


def test_session_env_local():
    """RESEARCH Q7: llama-server ignores the token without --api-key, but the token-leak guard
    needs a non-empty one, so a loopback arm with no key variable gets LOOPBACK_TOKEN."""
    arms = _arms()
    env = session_env(arms[LOCAL], {"PATH": "made-up", "OPENROUTER_API_KEY": "made-up"}, arms)
    assert backends.LOOPBACK_TOKEN == "local"
    assert env["ANTHROPIC_BASE_URL"] == LOCAL_URL
    assert env["ANTHROPIC_AUTH_TOKEN"] == backends.LOOPBACK_TOKEN
    assert env["ANTHROPIC_API_KEY"] == "" and "OPENROUTER_API_KEY" not in env
    assert [env[pin] for pin in PINS] == ["qwen3.6-35b-a3b"] * 3


@pytest.mark.parametrize("url", ["https://llm.example.invalid/anthropic",
                                 "http://192.168.1.5:8080"])  # fmt: skip
def test_no_key_variable_needs_a_loopback_url(tmp_path, url):
    """Without key_env the fixed loopback token would be sent: allowed for loopback only (plain
    http to another host is refused by the base_url rule first)."""
    text = (_DEEPSEEK_TOML.replace('key_env = "DEEPSEEK_API_KEY"\n', "")
            .replace(DEEPSEEK_URL, url))  # fmt: skip
    with pytest.raises(ArmError) as exc:
        load_arms(_table(tmp_path, text))
    field = "key_env" if url.startswith("https://") else "base_url"
    assert DEEPSEEK in str(exc.value) and field in str(exc.value), str(exc.value)


def test_the_local_arm_takes_no_allow_egress():
    arm = _arms()[LOCAL]
    preflight(arm, {}, allow_egress=())
    with pytest.raises(ArmError) as exc:
        preflight(arm, {}, allow_egress=(LOCAL,))
    assert LOCAL in str(exc.value)


def test_session_env_marks_egress_sessions():
    """D-10: a hosted arm's session carries REVERSEAPOC_EGRESS=1, so the hook denies its reads
    of orig/ and third_party/; a Claude arm's never does, even when the variable is inherited."""
    from reverseapoc import hooks

    arms = _arms()
    base = {"DEEPSEEK_API_KEY": FAKE_DEEPSEEK, hooks.EGRESS_ENV: "1"}
    assert session_env(arms[DEEPSEEK], base, arms)[hooks.EGRESS_ENV] == "1"
    assert hooks.EGRESS_ENV not in session_env(arms[OPUS], base, arms)


# ---- 07.2-13 (D-12, D-13, D-26): the Codex arms ----

CODEX_ARMS = {"gpt-6-luna": "GPT-6 Luna <noreply@openai.com>",
              "gpt-6.1-sol": "GPT-6.1 Sol <noreply@openai.com>"}  # fmt: skip


def test_codex_arms_load():
    """GPT-6 Luna and GPT-6.1 Sol run through the Codex CLI on the owner's ChatGPT login: no
    endpoint, no key variable, no init ids (Codex streams no init event), free on Plus (counted
    in tokens), one worker, sending the pack to OpenAI (so --allow-egress)."""
    arms = _arms()
    for name, credit in CODEX_ARMS.items():
        arm = arms[name]
        assert (arm.harness, arm.backend, arm.model) == ("codex", "openai", name)
        assert (arm.base_url, arm.key_env, arm.accepted_init) == (None, None, ())
        assert arm.prices == (0.0, 0.0, 0.0, 0.0) and arm.coauthor == credit
        assert arm.max_workers == 1 and arm.egress


_CODEX_TOML = """\
[arms."gpt-6-luna"]
harness = "codex"
backend = "openai"
model = "gpt-6-luna"
sends_disassembly = true
accepted_init = []
coauthor = "GPT-6 Luna <noreply@openai.com>"
max_workers = 1

[arms."gpt-6-luna".prices]
input = 0.0
output = 0.0
cache_read = 0.0
cache_creation = 0.0
"""


@pytest.mark.parametrize("extra", ['base_url = "https://api.openai.com/v1"\n',
                                   'key_env = "OPENAI_API_KEY"\n'])  # fmt: skip
def test_a_codex_arm_takes_no_endpoint_or_key(tmp_path, extra):
    """D-12: a Codex arm uses the ChatGPT login; an endpoint or key variable is refused."""
    load_arms(_table(tmp_path, _CODEX_TOML))
    text = _CODEX_TOML.replace("max_workers = 1\n", f"max_workers = 1\n{extra}")
    with pytest.raises(ArmError) as exc:
        load_arms(_table(tmp_path, text))
    assert "gpt-6-luna" in str(exc.value) and extra.split(" ")[0] in str(exc.value)


def test_gemini_openrouter_fallback_arm_loads():
    """D-21: if the agy canary finds no usable AI Plus quota, Gemini runs through OpenRouter in
    the Claude Code harness instead: a paid arm with OpenRouter's endpoint and key variable,
    its own init id and prices (cache priced as input), needing --allow-egress."""
    arm = _arms()["gemini-3.8-flash-openrouter"]
    assert (arm.harness, arm.backend, arm.base_url, arm.key_env, arm.model) == (
        "claude", "openrouter", "https://openrouter.ai/api", "OPENROUTER_API_KEY",
        "google/gemini-3.8-flash")  # fmt: skip
    assert arm.egress and arm.accepted_init == ("google/gemini-3.8-flash",)
    assert arm.prices.input > 0 and arm.prices.output > 0
    assert arm.coauthor == "Gemini 3.8 Flash <noreply@google.com>"
    assert not [name for name in _arms() if "gemini-4" in name or name.endswith("pro")]


def test_a_claude_harness_arm_still_needs_init_ids(tmp_path):
    """Only an arm with no init event may list no init ids."""
    with pytest.raises(ArmError) as exc:
        load_arms(_table(tmp_path, _DEEPSEEK_TOML.replace('["deepseek-flash"]', "[]")))
    assert "accepted_init" in str(exc.value)


# ---- 07.2-16 (D-22): an arm's own session cap ----


def test_max_sessions_is_optional(tmp_path):
    """`max_sessions` is optional: absent, the arm has no cap of its own (None); present, a
    whole number of 1 or more."""
    assert load_arms(_table(tmp_path, _DEEPSEEK_TOML))[DEEPSEEK].max_sessions is None
    text = _DEEPSEEK_TOML.replace("max_workers = 3\n", "max_workers = 3\nmax_sessions = 5\n")
    assert load_arms(_table(tmp_path, text))[DEEPSEEK].max_sessions == 5


@pytest.mark.parametrize("value", ["0", "-1", "true", '"5"', "1.5"])
def test_a_bad_max_sessions_is_refused(tmp_path, value):
    text = _DEEPSEEK_TOML.replace("max_workers = 3\n", f"max_workers = 3\nmax_sessions = {value}\n")
    with pytest.raises(ArmError) as exc:
        load_arms(_table(tmp_path, text))
    assert DEEPSEEK in str(exc.value) and "max_sessions" in str(exc.value)


def test_agy_arms_carry_the_cap_their_canary_sizes():
    """The Antigravity arms carry a session cap the owner sets from the quota the agy canary
    measures (a comment in backends.toml says so); the Claude arms have none."""
    arms = _arms()
    for name in ("gemini-flash", "gpt-oss"):
        assert isinstance(arms[name].max_sessions, int) and arms[name].max_sessions >= 1, name
    assert [name for name in CLAUDE_ARMS if arms[name].max_sessions is not None] == []
    text = backends.ARMS_TOML.read_text(encoding="utf-8")
    comment = text[:text.index('[arms."gemini-flash"]')].rsplit("\n\n", 1)[-1]
    assert "max_sessions" in comment and "canary" in comment and "quota" in comment
