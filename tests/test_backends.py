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
DEEPSEEK_URL = "https://api.deepseek.com/anthropic"  # the synthetic _DEEPSEEK_TOML's endpoint
DEEPSEEK_MODEL = "deepseek/deepseek-v4.1-flash"  # the committed arm runs through OpenRouter
ROUTER_URL = "https://openrouter.ai/api"
ROUTER_KEY = "OPENROUTER_API_KEY"
RETIRED_KEYS = ("DEEPSEEK_API_KEY", "ZAI_API_KEY")  # the direct providers' (owner, 2026-11-10)
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
    URL, no key variable), and deepseek-flash through OpenRouter (owner, 2026-11-10) with its
    key's NAME."""
    arms = _arms()
    for name in CLAUDE_ARMS:
        arm = arms[name]
        assert (arm.name, arm.model, arm.backend) == (name, name, "anthropic")
        assert arm.harness == "claude"
        assert (arm.base_url, arm.key_env, arm.coauthor, arm.prices) == (None, None, None, None)
        assert arm.sends_disassembly is True and not arm.egress
    arm = arms[DEEPSEEK]
    assert (arm.backend, arm.model, arm.key_env) == ("openrouter", DEEPSEEK_MODEL, ROUTER_KEY)
    assert arm.base_url == ROUTER_URL and arm.base_url.startswith("https://")
    assert arm.sends_disassembly is True and arm.egress
    assert arm.accepted_init == (DEEPSEEK_MODEL,)


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
    other = dataclasses.replace(arms[DEEPSEEK], name="other-hosted", key_env="OTHER_API_KEY")
    arms = {**arms, other.name: other}
    base = {"PATH": "made-up", ROUTER_KEY: FAKE_DEEPSEEK, "OTHER_API_KEY": FAKE_ZAI}
    env = session_env(arms[DEEPSEEK], base, arms)
    assert env["ANTHROPIC_BASE_URL"] == ROUTER_URL
    assert env["ANTHROPIC_AUTH_TOKEN"] == FAKE_DEEPSEEK
    assert env["ANTHROPIC_API_KEY"] == ""
    assert env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    assert [env[pin] for pin in PINS] == [DEEPSEEK_MODEL] * 3
    # spike012 (owner, 2026-11-11): a hosted model's reply may run past Claude Code's default
    # 32000-token output cap; every OpenRouter provider in use allows at least 117964.
    assert backends.HOSTED_MAX_OUTPUT_TOKENS == 64_000
    assert env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] == "64000"
    assert ROUTER_KEY not in env and "OTHER_API_KEY" not in env
    assert FAKE_ZAI not in env.values()
    assert env["PATH"] == "made-up"
    assert base[ROUTER_KEY] == FAKE_DEEPSEEK  # the base is not modified


def test_session_env_anthropic_strips():
    """A Claude arm: an inherited base URL, token and default-model pin are removed (they
    would route the claude.ai login elsewhere), and so is every arm's key variable."""
    arms = _arms()
    base = {"PATH": "made-up", "ANTHROPIC_BASE_URL": "https://example.invalid/anthropic",
            "ANTHROPIC_AUTH_TOKEN": "made-up-token-0004",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "made-up-model",
            ROUTER_KEY: FAKE_DEEPSEEK}  # fmt: skip
    env = session_env(arms[OPUS], base, arms)
    for name in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_DEFAULT_HAIKU_MODEL"):
        assert name not in env, name
    for arm in arms.values():
        assert arm.key_env is None or arm.key_env not in env, arm.name
    assert env == {"PATH": "made-up"}


_VENDOR_LEAKS = {
    "ANTHROPIC_CUSTOM_HEADERS": "X-Made-Up: 1", "ANTHROPIC_MODEL": "made-up",
    "ANTHROPIC_SMALL_FAST_MODEL": "made-up", "ANTHROPIC_API_KEY": "made-up-0010",
    "ANTHROPIC_BEDROCK_BASE_URL": "https://bedrock.invalid", "CLAUDE_CODE_USE_BEDROCK": "1",
    "CLAUDE_CODE_USE_VERTEX": "1", "OPENAI_API_KEY": "made-up-0011",
    "OPENAI_ORG_ID": "made-up-org", "GOOGLE_API_KEY": "made-up-0012",
    "GEMINI_API_KEY": "made-up-0013", "GOOGLE_APPLICATION_CREDENTIALS": "C:/made-up.json",
}  # fmt: skip
_OAUTH = "CLAUDE_CODE_OAUTH_TOKEN"


@pytest.mark.parametrize("name", [OPUS, DEEPSEEK, "qwen-local", "gpt-6-luna", "gemini-flash"])
def test_session_env_strips_every_vendor_routing_and_credential_variable(name):
    """07.2 review WR-09: no session inherits a vendor's routing or credential variable that is
    not its arm's own: every ANTHROPIC_* (custom headers, model, Bedrock and Vertex URLs among
    them), every CLAUDE_CODE_USE_* (which would reroute a Claude session off its base URL),
    every OPENAI_* and every Google key or credentials variable. The Claude Code login's own
    token (CLAUDE_CODE_OAUTH_TOKEN) reaches only an Anthropic-login session. What is left is
    the base's other variables plus what the arm itself sets."""
    arms = _arms()
    arm = arms[name]
    base = {"PATH": "made-up", ROUTER_KEY: FAKE_DEEPSEEK, **_VENDOR_LEAKS,
            _OAUTH: "made-up-oauth-0014"}  # fmt: skip
    env = session_env(arm, base, arms)
    own = session_env(arm, {"PATH": "made-up", ROUTER_KEY: FAKE_DEEPSEEK}, arms)
    if arm.backend == "anthropic":
        own[_OAUTH] = "made-up-oauth-0014"
    assert env == own, sorted(set(env) ^ set(own))
    for leak, value in _VENDOR_LEAKS.items():
        assert env.get(leak) != value, leak


@pytest.mark.parametrize("name", [OPUS, DEEPSEEK, "qwen-local", "gpt-6-luna", "gemini-flash"])
def test_session_env_strips_the_retired_direct_provider_keys(name):
    """Owner ruling 2026-11-10: DeepSeek and GLM run only through OpenRouter, so no arm names
    DEEPSEEK_API_KEY or ZAI_API_KEY any more; a key the owner still has set under either name
    reaches no session all the same."""
    arms = _arms()
    retired = {key: f"made-up-retired-{n:04d}" for n, key in enumerate(RETIRED_KEYS, 15)}
    env = session_env(arms[name], {"PATH": "made-up", ROUTER_KEY: FAKE_DEEPSEEK, **retired},
                      arms)  # fmt: skip
    assert sorted(set(env) & set(retired)) == []
    assert [value for value in retired.values() if value in env.values()] == []


def test_session_env_without_the_table_uses_the_committed_one():
    """RULINGS names session_env(arm, base_env): the table defaults to the committed one."""
    arms = _arms()
    base = {ROUTER_KEY: FAKE_DEEPSEEK}
    assert session_env(arms[OPUS], base) == {}


def test_session_env_refuses_an_empty_token():
    """The env builder itself never sets a base URL without a token (Pitfall 5)."""
    arms = _arms()
    with pytest.raises(ArmError) as exc:
        session_env(arms[DEEPSEEK], {ROUTER_KEY: ""}, arms)
    assert ROUTER_KEY in str(exc.value)


# ---- the preflight (D-11, D-26 token-leak guard) ----


@pytest.mark.parametrize("value", [None, "", "\t \t"])
def test_preflight_refusals(value):
    """A missing, empty or whitespace key: refused naming the variable and the endpoint, never
    the value."""
    arm = _arms()[DEEPSEEK]
    env = {"PATH": "made-up"} if value is None else {ROUTER_KEY: value}
    with pytest.raises(ArmError) as exc:
        preflight(arm, env, allow_egress=(DEEPSEEK,))
    text = str(exc.value)
    assert ROUTER_KEY in text and ROUTER_URL in text, text
    if value:
        assert value not in text


def test_preflight_refuses_egress_without_the_flag():
    arm = _arms()[DEEPSEEK]
    with pytest.raises(ArmError) as exc:
        preflight(arm, {ROUTER_KEY: FAKE_DEEPSEEK}, allow_egress=())
    text = str(exc.value)
    assert DEEPSEEK in text and "--allow-egress" in text and FAKE_DEEPSEEK not in text


@pytest.mark.parametrize("stray", ["glm-5.3", OPUS])
def test_preflight_refuses_a_stray_egress_name(stray):
    """D-11: an --allow-egress that names no selected sending arm is refused, so a typo can
    never open a backend."""
    arms = _arms()
    with pytest.raises(ArmError) as exc:
        preflight(arms[DEEPSEEK], {ROUTER_KEY: FAKE_DEEPSEEK},
                  allow_egress=(DEEPSEEK, stray))  # fmt: skip
    assert stray in str(exc.value)
    with pytest.raises(ArmError):
        preflight(arms[OPUS], {}, allow_egress=(OPUS,))


def test_preflight_passes():
    arms = _arms()
    preflight(arms[DEEPSEEK], {ROUTER_KEY: FAKE_DEEPSEEK}, allow_egress=(DEEPSEEK,))
    preflight(arms[OPUS], {}, allow_egress=())


# ---- Task 2: the other hosted arms, the cost estimate and the egress marker ----


@pytest.mark.parametrize(("name", "backend", "url", "key_env", "model"), [
    ("deepseek-flash", "openrouter", "https://openrouter.ai/api", "OPENROUTER_API_KEY",
     "deepseek/deepseek-v4.1-flash"),
    ("glm-5.3", "openrouter", "https://openrouter.ai/api", "OPENROUTER_API_KEY", "z-ai/glm-5.3"),
    ("glm-4.7-flash", "openrouter", "https://openrouter.ai/api", "OPENROUTER_API_KEY",
     "z-ai/glm-4.7-flash"),
    ("gpt-oss-20b", "openrouter", "https://openrouter.ai/api", "OPENROUTER_API_KEY",
     "openai/gpt-oss-20b"),
    ("muse-spark-open", "openrouter", "https://openrouter.ai/api", "OPENROUTER_API_KEY",
     "meta/muse-spark-open"),
    ("qwen-hosted", "openrouter", "https://openrouter.ai/api", "OPENROUTER_API_KEY",
     "qwen/qwen3.6-35b-a3b"),
])  # fmt: skip
def test_hosted_arms_load(name, backend, url, key_env, model):
    """D-18, the owner's Qwen ruling and his OpenRouter ruling of 2026-11-10: DeepSeek, both
    GLMs, GPT-OSS 20B, Muse Spark Open and the hosted Qwen all through OpenRouter, each with
    its prices, its own init id and its vendor's credit line."""
    arm = _arms()[name]
    assert (arm.backend, arm.base_url, arm.key_env, arm.model) == (backend, url, key_env, model)
    assert arm.egress and arm.accepted_init == (model,)
    assert arm.prices is not None and arm.prices.input > 0 and arm.prices.output > 0
    assert arm.coauthor is not None and "<noreply@" in arm.coauthor


@pytest.mark.parametrize(("name", "input_price", "output_price"), [
    ("deepseek-flash", 0.30, 1.20),
    ("glm-5.3", 0.07, 1.40),
    ("glm-4.7-flash", 0.061, 0.40),
    ("gpt-oss-20b", 0.03, 0.13),
    ("muse-spark-open", 1.25, 4.25),
    ("qwen-hosted", 0.10, 0.90),
])  # fmt: skip
def test_openrouter_list_prices(name, input_price, output_price):
    """OpenRouter's public model list, read 2026-11-10 (USD per MTok); both cache classes stay
    priced as input (the never-understate rule above)."""
    prices = _arms()[name].prices
    assert (prices.input, prices.output) == (input_price, output_price)
    assert prices.cache_read == prices.cache_creation == input_price


def test_every_hosted_cache_price_is_at_least_the_input_price():
    """Until the owner records the providers' cache prices, a metered arm prices both cache
    classes as input, so an estimate may overstate and never understate. Quick 261110-f30: a
    subscription arm's prices are public list prices with their published cache-read price,
    and only its unrecorded cache_creation class is priced as input. Spike 013: a Copilot arm's
    cache-write rate is recorded (GitHub's published AI-credit rates), and it is above input."""
    for arm in _arms().values():
        if arm.harness == backends.COPILOT:
            assert arm.prices.cache_creation >= arm.prices.input, arm.name
        elif arm.egress:
            assert arm.prices.cache_creation == arm.prices.input, arm.name
        if arm.billing == backends.METERED:
            assert arm.prices.cache_read == arm.prices.input, arm.name


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
    assert arm.billing == backends.FREE


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
    # a 64K-context llama-server cannot take the hosted arms' raised output cap
    assert "CLAUDE_CODE_MAX_OUTPUT_TOKENS" not in env


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
    base = {ROUTER_KEY: FAKE_DEEPSEEK, hooks.EGRESS_ENV: "1"}
    assert session_env(arms[DEEPSEEK], base, arms)[hooks.EGRESS_ENV] == "1"
    assert hooks.EGRESS_ENV not in session_env(arms[OPUS], base, arms)


# ---- 07.2-13 (D-12, D-13, D-26): the Codex arms ----

CODEX_ARMS = {"gpt-6-luna": "GPT-6 Luna <noreply@openai.com>",
              "gpt-6.1-sol": "GPT-6.1 Sol <noreply@openai.com>",
              "gpt-6.1-terra": "GPT-6.1 Terra <noreply@openai.com>",
              "gpt-6-astra": "GPT-6 Astra <noreply@openai.com>"}  # fmt: skip


def test_codex_arms_load():
    """GPT-6 Luna and GPT-6.1 Sol run through the Codex CLI on the owner's ChatGPT login: no
    endpoint, no key variable, no init ids (Codex streams no init event), a subscription arm
    (counted in tokens), one worker, sending the pack to OpenAI (so --allow-egress). Quick
    261110-f30: their prices are the public API list prices (input, output, cache_read,
    cache_creation; cache_creation priced as input), for the comparison only."""
    from reverseapoc.streamjson import Price

    arms = _arms()
    prices = {"gpt-6-luna": Price(0.10, 0.50, 0.01, 0.10),
              "gpt-6.1-sol": Price(2.00, 10.00, 0.10, 2.00),
              "gpt-6.1-terra": Price(1.00, 5.00, 0.05, 1.00),
              "gpt-6-astra": Price(10.00, 50.00, 1.00, 10.00)}  # fmt: skip
    for name, credit in CODEX_ARMS.items():
        arm = arms[name]
        assert (arm.harness, arm.backend, arm.model) == ("codex", "openai", name)
        assert (arm.base_url, arm.key_env, arm.accepted_init) == (None, None, ())
        assert arm.prices == prices[name] and arm.coauthor == credit
        # owner, 2026-11-12: Terra runs 5 at once on cascade nights; the others stay at 1
        assert arm.max_workers == (5 if name == "gpt-6.1-terra" else 1) and arm.egress
        assert arm.billing == backends.SUBSCRIPTION


LIST_PRICED = ("gpt-6-luna", "gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-astra", "gemini-flash",
               "gpt-oss", "gemini-3.8-flash-openrouter")  # fmt: skip


def _price_comment(text: str, name: str) -> str:
    """The comment lines right above `[arms."<name>".prices]`."""
    head = text[:text.index(f'[arms."{name}".prices]')].rstrip("\n").splitlines()
    lines = []
    for line in reversed(head):
        if not line.startswith("#"):
            break
        lines.insert(0, line)
    return " ".join(line.lstrip("# ") for line in lines)


def test_list_prices_are_marked_confirm_at_setup():
    """Quick 261110-f30: each list price read from third-party trackers names its source and
    date and is marked for the owner to confirm at setup; Gemini's notes its introductory
    price; gpt-oss notes that trackers disagree."""
    text = backends.ARMS_TOML.read_text(encoding="utf-8")
    for name in LIST_PRICED:
        comment = _price_comment(text, name)
        assert "confirm at setup" in comment and "2026-11-10" in comment, name
        assert "price trackers" in comment, name
    assert "272K" in _price_comment(text, "gpt-6.1-sol")
    for name in ("gemini-flash", "gemini-3.8-flash-openrouter"):
        assert "introductory" in _price_comment(text, name), name
        assert "2026-12-31" in _price_comment(text, name), name
    assert "disagree" in _price_comment(text, "gpt-oss")


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
    # quick 261110-f30: OpenRouter's listed price (the agy arm's), cache priced as input
    assert arm.prices == (0.75, 3.75, 0.75, 0.75) and arm.billing == backends.METERED
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


# ---- quick 261110-f30 (spike 012): billing, list prices, the record's arm ----

SUBSCRIBED = (*CLAUDE_ARMS, *CODEX_ARMS, "gemini-flash", "gpt-oss", "agy-sonnet-4-6",
              "agy-opus-4-6", "copilot-haiku-5-5", "copilot-sonnet-5-5",
              "copilot-gpt-6-luna")  # fmt: skip
METERED_ARMS = ("deepseek-flash", "glm-5.3", "glm-4.7-flash", "gpt-oss-20b", "muse-spark-open",
                "gemini-3.8-flash-openrouter", "qwen-hosted")  # fmt: skip


def test_billing_comes_from_the_base_url():
    """No base_url: a CLI's own sign-in (subscription); a loopback one: the local server
    (free); any other: paid per token (metered). backends.toml has no billing field."""
    arms = _arms()
    assert backends.BILLINGS == ("subscription", "metered", "free")
    assert {name: arms[name].billing for name in SUBSCRIBED} == dict.fromkeys(
        SUBSCRIBED, backends.SUBSCRIPTION)  # fmt: skip
    assert {name: arms[name].billing for name in METERED_ARMS} == dict.fromkeys(
        METERED_ARMS, backends.METERED)  # fmt: skip
    assert arms[LOCAL].billing == backends.FREE
    assert set(arms) == {*SUBSCRIBED, *METERED_ARMS, LOCAL}


def test_list_price():
    """A Claude arm's list price is streamjson's table (RULINGS "Harness"); a hosted arm's is
    its backends.toml prices."""
    from reverseapoc.streamjson import PRICES_PER_MTOK

    arms = _arms()
    for name in CLAUDE_ARMS:
        assert arms[name].list_price == PRICES_PER_MTOK[name], name
    assert arms[DEEPSEEK].list_price == arms[DEEPSEEK].prices


def _v3(**change) -> dict:
    record = {"schema": 3, "model": "claude-haiku-5-5", "model_requested": "claude-haiku-5-5",
              "backend": "anthropic", "harness": "claude"}  # fmt: skip
    record.update(change)
    return record


def test_record_arm():
    """The record's (backend, harness, requested model); v1 and v2 records default to the
    Claude Code login, as stats.arm_key does, and a landing names its model."""
    arms = _arms()
    haiku = arms["claude-haiku-5-5"]
    assert backends.record_arm({"model": "claude-haiku-5-5"}, arms) is haiku  # v1
    assert backends.record_arm({"schema": 2, "model": None,
                                "model_requested": "claude-haiku-5-5"}, arms) is haiku  # fmt: skip
    assert backends.record_arm(_v3(), arms) is haiku
    luna = _v3(backend="openai", harness="codex", model_requested="gpt-6-luna", model=None)
    assert backends.record_arm(luna, arms) is arms["gpt-6-luna"]
    landing = {"kind": "landing", "model": DEEPSEEK_MODEL, "backend": "openrouter",
               "harness": "claude"}  # fmt: skip
    assert backends.record_arm(landing, arms) is arms[DEEPSEEK]
    gemini = _v3(backend="google", harness="agy", model_requested="gemini-3.8-flash")
    assert backends.record_arm(gemini, arms) is None


def test_token_cost_is_exact():
    from decimal import Decimal

    from reverseapoc.streamjson import Price

    tokens = {"input": 1_000_000, "output": 100_000, "cache_read": 2_000_000, "cache_creation": 0}
    cost = backends.token_cost(tokens, Price(0.10, 0.50, 0.01, 0.20))
    assert cost == Decimal("0.17") and isinstance(cost, Decimal)


# ---- quick 261112-fds (backlog 999.12a): the size-routed cascade's [routing] table ----

HAIKU = "claude-haiku-5-5"
TERRA = "gpt-6.1-terra"
GEMINI = "gemini-flash"
GLM = "glm-5.3"
DEEPSEEK = "deepseek-flash"


def test_committed_routing_table():
    """The owner's default rows, in bucket order, keyed by stats' own labels; every arm is an
    [arms."..."] entry, and load_arms still loads the file that now holds [routing]. Owner,
    2026-11-12: GLM-5.3 and DeepSeek V4.1-Flash join the rows to spend the OpenRouter credit."""
    rows = backends.load_routing()
    assert [(row.label, row.buckets, row.arms) for row in rows] == [
        ("[0, 64)", (0,), (TERRA, HAIKU, DEEPSEEK)),
        ("[64, 256)", (1,), (TERRA, HAIKU, DEEPSEEK)),
        ("[256, inf)", (2, 3), (TERRA, DEEPSEEK)),
    ]
    arms = _arms()
    assert {arm for row in rows for arm in row.arms} <= set(arms)
    assert backends.routing_arms(rows) == (TERRA, HAIKU, DEEPSEEK)
    assert arms[DEEPSEEK].max_workers == 12  # owner, 2026-11-13: spend the OpenRouter credit fast


def test_routing_rows_use_the_stats_buckets():
    """route_for goes through stats.size_bucket, and each one-bucket row's key is stats' own
    label of that bucket: no new threshold."""
    from reverseapoc import stats

    rows = backends.load_routing()
    for size, label in ((0, "[0, 64)"), (63, "[0, 64)"), (64, "[64, 256)"), (255, "[64, 256)"),
                        (256, "[256, inf)"), (1023, "[256, inf)"), (1024, "[256, inf)"),
                        (4096, "[256, inf)")):  # fmt: skip
        assert backends.route_for(rows, size).label == label, size
    for row in rows:
        if len(row.buckets) == 1:
            assert row.label == stats._bucket_label(row.buckets[0])


_TWO_CLAUDE_ARMS = """\
[arms."claude-haiku-5-5"]
harness = "claude"
backend = "anthropic"
model = "claude-haiku-5-5"
sends_disassembly = true
max_workers = 10

[arms."claude-sonnet-5-5"]
harness = "claude"
backend = "anthropic"
model = "claude-sonnet-5-5"
sends_disassembly = true
max_workers = 10
"""
_SMALL = '"[0, 64)" = ["claude-haiku-5-5"]\n'
_MEDIUM = '"[64, 256)" = ["claude-sonnet-5-5"]\n'
_LARGE = '"[256, inf)" = ["claude-sonnet-5-5"]\n'


@pytest.mark.parametrize(("before", "routing", "named"), [
    ("", '[routing]\n"[0, 64)" = ["claude-haiku-9-9"]\n' + _MEDIUM + _LARGE, "claude-haiku-9-9"),
    ("", '[routing]\n"[0, 64)" = []\n' + _MEDIUM + _LARGE, "[0, 64)"),
    ("", '[routing]\n"[0, 100)" = ["claude-haiku-5-5"]\n' + _MEDIUM + _LARGE, "[0, 100)"),
    ("", '[routing]\n"under 64" = ["claude-haiku-5-5"]\n' + _MEDIUM + _LARGE, "under 64"),
    ("", "[routing]\n" + _SMALL + '"[0, 256)" = ["claude-sonnet-5-5"]\n' + _LARGE, "[0, 256)"),
    ("", "[routing]\n" + _SMALL + _MEDIUM, "[256, 1024)"),
    ("", '[routing]\n"[0, 64)" = "claude-haiku-5-5"\n' + _MEDIUM + _LARGE, "[0, 64)"),
    ("", '[routing]\n"[0, 64)" = [5]\n' + _MEDIUM + _LARGE, "[0, 64)"),
    ("", "", "[routing]"),
    ("routing = 5\n", "", "[routing]"),
], ids=["unknown-arm", "empty-row", "unknown-bucket", "not-a-label", "bucket-twice",
        "bucket-in-no-row", "a-string", "a-number", "no-table", "not-a-table"])  # fmt: skip
def test_a_bad_routing_table_is_refused(tmp_path, before, routing, named):
    """T-261112-fds-05: load_routing fails loudly, naming the file, the routing table and the
    offending key or arm."""
    path = _table(tmp_path, before + _TWO_CLAUDE_ARMS + "\n" + routing)
    with pytest.raises(ArmError) as exc:
        backends.load_routing(path)
    text = str(exc.value)
    assert str(path) in text and "routing" in text and named in text, text


def test_load_arms_refuses_any_other_top_level_table(tmp_path):
    path = _table(tmp_path, _TWO_CLAUDE_ARMS + "\n[other]\nx = 1\n")
    with pytest.raises(ArmError, match="routing"):
        load_arms(path)
