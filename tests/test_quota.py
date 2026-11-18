"""Budget-sized drives (todo budget-runs-and-contributors): config/driver/quota.toml and the
session cap a `drive --arm-budget NAME=BUDGET` buys. No test contacts a provider or reads a
meter."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from reverseapoc import backends, quota
from reverseapoc.quota import Budget, QuotaError, load_quota, parse_budget, size

HAIKU = "claude-haiku-5-5"
DEEPSEEK = "deepseek-flash"
TERRA = "gpt-6.1-terra"
GEMINI = "gemini-flash"
COPILOT = "copilot-haiku-5-5"


# ---- the budget forms ----


@pytest.mark.parametrize(("text", "amount", "unit", "shown"), [
    ("5%week", "5", quota.WEEK, "5%week"),
    ("0.5%week", "0.5", quota.WEEK, "0.5%week"),
    ("100%5h", "100", quota.FIVE_HOUR, "100%5h"),
    ("$30", "30", quota.USD, "$30"),
    ("$7.50", "7.50", quota.USD, "$7.5"),
    ("400credits", "400", quota.CREDITS, "400credits"),
])  # fmt: skip
def test_parse_budget(text, amount, unit, shown):
    budget = parse_budget(text)
    assert budget == Budget(Decimal(amount), unit)
    assert str(budget) == shown


@pytest.mark.parametrize("text", ["", "5", "5%", "5%day", "$", "$-1", "$0", "0%week",
                                  "101%week", "120%5h", "five%week", "5 %week", "credits",
                                  "1e3credits", "$1,000"])  # fmt: skip
def test_parse_budget_refuses(text):
    with pytest.raises(QuotaError) as exc:
        parse_budget(text)
    for form in ("%week", "%5h", "$", "credits"):
        assert form in str(exc.value)


# ---- config/driver/quota.toml ----


def test_sonnet_has_a_measured_quota_entry():
    """Owner's 20-point spend of 2026-11-14/15: Sonnet 5.5 at 0.02% of the week per session
    (measured with Opus at 0.04, from 296 Opus and 415 Sonnet sessions moving the bar 8% to
    28%), no longer an estimate."""
    entry = load_quota()["claude-sonnet-5-5"]
    assert entry.plan.name == "Claude Code Ultra" and not entry.estimate
    assert entry.per_session == {quota.WEEK: Decimal("0.02")}
    sizing = size("claude-sonnet-5-5", parse_budget("10%week"), load_quota(), max_sessions=None)
    assert sizing.sessions == 500


def test_fable_has_a_measured_week_entry():
    """Owner's Fable A/B of 2026-11-16 (quick 261101-b5f's pending comparison): Fable 5.1 at
    0.18% of the Claude week a session, by token math ($3.10 a session at $17.73 a point; the
    bar itself was shared with another project), so 25%week buys 138 sessions."""
    entry = load_quota()["claude-fable-5-1"]
    assert entry.plan.name == "Claude Code Ultra" and not entry.estimate
    assert entry.per_session == {quota.WEEK: Decimal("0.18")}
    assert (entry.matched, entry.sessions) == (2, 133)
    sizing = size("claude-fable-5-1", parse_budget("25%week"), load_quota(), max_sessions=None)
    assert sizing.sessions == 138


def test_copilot_sonnet_has_an_estimated_credit_entry():
    """Owner's Copilot spend of 2026-11-16: Sonnet 5.5 through Copilot, unmeasured, estimated at
    40 credits a session (a Haiku session's tokens at Sonnet's GitHub rates come to about 35),
    so 200 credits buy 5 sessions; the dry run says it is an estimate."""
    entry = load_quota()["copilot-sonnet-5-5"]
    assert entry.plan.name == "GitHub Copilot Pro (AI credits)" and entry.estimate
    assert entry.per_session == {quota.CREDITS: Decimal("40")}
    sizing = size("copilot-sonnet-5-5", parse_budget("200credits"), load_quota(),
                  max_sessions=None)  # fmt: skip
    assert sizing.sessions == 5


def test_the_committed_table_loads_with_its_plans_named_in_config():
    """The plans come from the file, the seeded per-session figures from docs/model-routing.md
    "Quota per session", and the measured rates from docs/model-comparison.md "Cascade
    nights"."""
    table = load_quota()
    assert table[HAIKU].plan.name == "Claude Code Ultra"
    assert table[HAIKU].per_session == {quota.WEEK: Decimal("0.01")}
    assert (table[HAIKU].matched, table[HAIKU].sessions) == (22, 312)
    assert table["claude-opus-5-5"].per_session == {quota.WEEK: Decimal("0.04")}
    assert table[TERRA].per_session == {quota.FIVE_HOUR: Decimal("1.35"),
                                        quota.WEEK: Decimal("0.25"),
                                        quota.CREDITS: Decimal("2.3")}  # fmt: skip
    assert (table[TERRA].matched, table[TERRA].sessions) == (18, 978)
    assert table[GEMINI].per_session == {quota.WEEK: Decimal("15.0")}
    assert (table[GEMINI].matched, table[GEMINI].sessions) == (0, 1)
    assert table[DEEPSEEK].per_session == {quota.USD: Decimal("0.30")}
    assert (table[DEEPSEEK].matched, table[DEEPSEEK].sessions) == (2, 5)
    assert all(isinstance(entry.read, date) and entry.source for entry in table.values())


def test_the_copilot_entry_is_measured_and_needs_no_backends_arm():
    """The Copilot Pro plan (1 credit = $0.01) and its arm's figure, measured from the usage
    files of 123 sessions to 2026-11-14 (it replaced the placeholder of 4), load although
    backends.toml may not have that arm; an arm of backends.toml with no entry is fine."""
    table = load_quota()
    entry = table[COPILOT]
    assert not entry.estimate and "usage files" in entry.source
    assert entry.plan.credit_usd == Decimal("0.01")
    assert entry.per_session == {quota.CREDITS: Decimal("2.2")}
    assert "glm-5.3" in backends.load_arms() and "glm-5.3" not in table


_GOOD = """\
[plans.p]
name = "Plan P"
no_meter = "made up"

[arms.a]
plan = "p"
usd = 0.5
source = "made up"
read = 2026-11-13
"""


@pytest.mark.parametrize(("text", "words"), [
    ("[plans.p]\nname = 'P'\n", "[arms."),
    (_GOOD + "\n[other]\nx = 1\n", "other"),
    (_GOOD.replace('plan = "p"', 'plan = "q"'), "plan 'q'"),
    (_GOOD.replace("usd = 0.5", "usd = 0"), "usd"),
    (_GOOD.replace("usd = 0.5", "usd = true"), "usd"),
    (_GOOD.replace("usd = 0.5", ""), "per session"),
    (_GOOD.replace('source = "made up"', ""), "source"),
    (_GOOD.replace("read = 2026-11-13", 'read = "today"'), "read"),
    (_GOOD + "matched = 3\nsessions = 2\nrate_source = 'x'\n", "matched"),
    (_GOOD + "matched = 1\n", "sessions"),
    (_GOOD + "matched = 1\nsessions = 2\n", "rate_source"),
    (_GOOD + "colour = 'red'\n", "colour"),
    (_GOOD.replace('name = "Plan P"', 'name = "Plan P"\ncredit_usd = -1'), "credit_usd"),
    (_GOOD.replace('name = "Plan P"', ""), "name"),
    (_GOOD.replace('no_meter = "made up"', ""), "meter"),
    (_GOOD.replace('no_meter = "made up"', 'no_meter = "x"\nmeter = "credits"'), "meter"),
    (_GOOD.replace('no_meter = "made up"', 'meter = "bar"'), "bar"),
    (_GOOD.replace('no_meter = "made up"', 'meter = "cost_usd"'), "usd_per_week_point"),
    (_GOOD.replace('no_meter = "made up"', 'no_meter = "x"\nusd_per_week_point = 2'),
     "point_source"),
], ids=["no-arms", "stray-table", "unknown-plan", "zero", "bool", "no-quota", "no-source",
        "bad-date", "rate-above", "rate-half", "rate-no-source", "stray-key", "bad-credit",
        "no-plan-name", "no-meter", "two-meters", "unknown-meter", "cost-no-point",
        "point-no-source"])  # fmt: skip
def test_a_malformed_table_names_the_problem(tmp_path, text, words):
    path = tmp_path / "quota.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(QuotaError) as exc:
        load_quota(path)
    assert str(path) in str(exc.value) and words in str(exc.value), exc.value


def test_a_missing_table_is_a_quota_error(tmp_path):
    with pytest.raises(QuotaError, match="quota.toml"):
        load_quota(tmp_path / "quota.toml")


# ---- the sizing ----


def test_haiku_five_percent_of_the_week():
    """5%week at 0.01% per session (recalibrated 2026-11-14): 500, bounded by the budget (Haiku
    has no max_sessions), and 500 x 22/312 = about 35.3 expected matches."""
    sizing = size(HAIKU, parse_budget("5%week"), load_quota(), max_sessions=None)
    assert (sizing.sessions, sizing.by_budget, sizing.bound) == (500, 500, quota.BY_BUDGET)
    assert sizing.per_session == Decimal("0.01")
    assert sizing.expected == Decimal("35.3")
    line = sizing.line()
    for words in ("claude-haiku-5-5", "5%week", "Claude Code Ultra", "0.01%week per session",
                  "read 2026-11-14", "500 sessions", "budget", "35.3", "22 of 312"):
        assert words in line, (words, line)


def test_deepseek_ten_dollars():
    sizing = size(DEEPSEEK, parse_budget("$10"), load_quota(), max_sessions=None)
    assert (sizing.sessions, sizing.bound) == (33, quota.BY_BUDGET)
    assert "$0.3 per session" in sizing.line()


def test_the_division_is_exact():
    """$0.90 at $0.30 a session is 3 sessions, never a float's 2.9999 floored to 2."""
    assert size(DEEPSEEK, parse_budget("$0.90"), load_quota(), max_sessions=None).sessions == 3


def test_max_sessions_bounds_the_budget_and_says_so():
    """The whole agy week (100% at 15%) buys 6; a max_sessions of 3 wins, and the line names
    that bound and what the budget alone would buy."""
    table = load_quota()
    assert size(GEMINI, parse_budget("100%week"), table, max_sessions=20).sessions == 6
    sizing = size(GEMINI, parse_budget("100%week"), table, max_sessions=3)
    assert (sizing.sessions, sizing.by_budget, sizing.bound) == (3, 6, quota.BY_MAX_SESSIONS)
    assert "max_sessions 3" in sizing.line() and "buys 6" in sizing.line()
    assert sizing.expected == Decimal("0")


def test_terra_takes_either_window():
    table = load_quota()
    assert size(TERRA, parse_budget("100%5h"), table, max_sessions=None).sessions == 74
    assert size(TERRA, parse_budget("10%week"), table, max_sessions=None).sessions == 40
    # past the week: Codex credits, 2.3 a session (2,120 over 910 sessions, 2026-11-14 to 16)
    assert size(TERRA, parse_budget("500credits"), table, max_sessions=None).sessions == 217


def test_a_plan_credit_converts_dollars_and_credits():
    """Copilot Pro: 2.2 credits a session at $0.01 a credit, so $1 buys 45 sessions and 100
    credits buy 45; the line carries its measured rate (6 of 123, 2026-11-14)."""
    table = load_quota()
    dollars = size(COPILOT, parse_budget("$1"), table, max_sessions=None)
    assert (dollars.sessions, dollars.per_session) == (45, Decimal("0.022"))
    assert size(COPILOT, parse_budget("100credits"), table, max_sessions=None).sessions == 45
    assert "6 of 123" in dollars.line()


def test_an_arm_with_no_quota_entry_is_refused():
    with pytest.raises(QuotaError) as exc:
        size("glm-5.3", parse_budget("$5"), load_quota(), max_sessions=None)
    text = str(exc.value)
    assert "glm-5.3" in text and "quota.toml" in text and HAIKU in text


def test_a_unit_the_arm_has_no_figure_for_is_refused():
    with pytest.raises(QuotaError) as exc:
        size(HAIKU, parse_budget("100%5h"), load_quota(), max_sessions=None)
    assert "%5h" in str(exc.value) and "%week" in str(exc.value)


def test_a_budget_below_one_session_is_refused():
    with pytest.raises(QuotaError, match="0 sessions"):
        size(GEMINI, parse_budget("10%week"), load_quota(), max_sessions=None)


def test_the_doc_carries_every_figure():
    doc = size(HAIKU, parse_budget("5%week"), load_quota(), max_sessions=None).doc()
    assert doc == {"arm": HAIKU, "budget": "5%week", "plan": "Claude Code Ultra",
                   "per_session": "0.01", "unit": quota.WEEK,
                   "source": load_quota()[HAIKU].source, "read": "2026-11-14",
                   "estimate": False, "sessions": 500, "by_budget": 500,
                   "bound": quota.BY_BUDGET, "max_sessions": None,
                   "expected_matches": "35.3", "rate": [22, 312],
                   "rate_source": load_quota()[HAIKU].rate_source,
                   "meter": "between launches the meter reads the arm's records' cost_usd at "
                            "$17.73 a point of the week",
                   "spent": None}  # fmt: skip


def test_the_path_is_committed():
    assert quota.QUOTA_TOML == backends.REPO_ROOT / "config" / "driver" / "quota.toml"
    assert Path(quota.QUOTA_TOML).is_file()


# ---- todo budget-meter-wiring: each plan's meter, and the Claude week by cost_usd ----


def test_every_committed_plan_names_its_meter_or_why_none_reads_live():
    """The plans map to a live meter (OpenRouter's credits API, a Copilot session's credits,
    a Claude session's cost_usd at the calibrated $17.73 a point of the week, 2026-11-16) or
    say why none moves during a night (Codex drive sessions run --ephemeral; agy prints no
    machine-readable usage)."""
    table = load_quota()
    plans = {entry.plan.id: entry.plan for entry in table.values()}
    claude = plans["claude-ultra"]
    assert (claude.meter, claude.usd_per_week_point) == ("cost_usd", Decimal("17.73"))
    assert "$354.59" in claude.point_source and "20 points" in claude.point_source
    assert plans["copilot-pro"].meter == "credits"
    assert plans["openrouter"].meter == "openrouter"
    assert plans["chatgpt-plus"].meter is None and "--ephemeral" in plans["chatgpt-plus"].no_meter
    assert plans["google-ai-plus"].meter is None and plans["google-ai-plus"].no_meter
    assert quota.METER_UNITS == {"openrouter": quota.USD, "credits": quota.CREDITS,
                                 "cost_usd": quota.WEEK}  # fmt: skip


def test_the_budget_line_names_the_meter_or_the_cap_alone():
    """A budget whose plan has a live meter in its unit says what the night reads between
    launches; one with none (Codex), or a meter in another unit, says the session cap alone
    holds it."""
    table = load_quota()
    haiku = size(HAIKU, parse_budget("5%week"), table, max_sessions=None).line()
    assert "cost_usd at $17.73 a point" in haiku and "cap alone" not in haiku
    terra = size(TERRA, parse_budget("100%5h"), table, max_sessions=None).line()
    assert "no live meter" in terra and "--ephemeral" in terra and "cap alone" in terra
    dollars = size(COPILOT, parse_budget("$1"), table, max_sessions=None).line()
    assert "reads credits" in dollars and "cap alone" in dollars


# ---- todo resumed-held-run-budgets: what the run's records already spent ----


def _rec(cost: float = 0.0, **extra) -> dict:
    """The fields of an attempt record quota.spent reads."""
    return {"cost_usd": cost, **extra}


def test_spent_reads_each_records_figure_in_the_budgets_unit():
    """Credits from a Copilot record's own `credits` (null: the per-session figure), dollars
    through the plan's credit_usd, the Claude week from cost_usd at $17.73 a point, and a unit
    no record measures (Codex %5h) at the per-session figure."""
    table = load_quota()
    copilot = [_rec(credits=3.0), _rec(credits=2.0), _rec(credits=None)]
    spent = quota.spent(table[COPILOT], quota.CREDITS, copilot, "r1")
    assert (spent.run, spent.sessions, spent.amount) == ("r1", 3, Decimal("7.2"))
    assert "2 by their credits" in spent.how and "1 at 2.2credits per session" in spent.how
    assert quota.spent(table[COPILOT], quota.USD, copilot, "r1").amount == Decimal("0.072")
    week = quota.spent(table[HAIKU], quota.WEEK, [_rec(17.73), _rec(35.46)], "r1")
    assert week.amount == Decimal("3") and "cost_usd at $17.73 a point" in week.how
    terra = quota.spent(table[TERRA], quota.FIVE_HOUR, [_rec(), _rec()], "r1")
    assert terra.amount == Decimal("2.70") and terra.how == "2 at 1.35%5h per session"
    assert quota.spent(table[DEEPSEEK], quota.USD, [_rec(0.25)], "r1").amount == Decimal("0.25")
    assert quota.spent(table[COPILOT], quota.CREDITS, [], "r1") is None


def test_a_resumed_budget_buys_only_what_is_left_and_says_so():
    """100 credits on Copilot Haiku with 50.6 already spent by the run's 23 sessions: 49.4 left
    buy 22 sessions, and the line and the doc name the earlier spend."""
    table = load_quota()
    spent = quota.spent(table[COPILOT], quota.CREDITS, [_rec(credits=2.2)] * 23, "r1-x")
    sizing = size(COPILOT, parse_budget("100credits"), table, max_sessions=None, spent=spent)
    assert (sizing.sessions, sizing.by_budget) == (22, 22)
    assert sizing.left == Budget(Decimal("49.4"), quota.CREDITS)
    line = sizing.line()
    for words in ("100credits", "50.6credits spent earlier by 23 sessions of run r1-x",
                  "49.4credits left", "22 sessions"):
        assert words in line, (words, line)
    doc = sizing.doc()
    assert doc["spent"] == {"run": "r1-x", "sessions": 23, "amount": "50.6",
                            "how": spent.how, "left": "49.4"}  # fmt: skip
    fresh = size(COPILOT, parse_budget("100credits"), table, max_sessions=None)
    assert fresh.left == parse_budget("100credits") and fresh.doc()["spent"] is None
    assert "spent earlier" not in fresh.line()


def test_a_budget_the_run_already_spent_is_refused():
    table = load_quota()
    spent = quota.spent(table[COPILOT], quota.CREDITS, [_rec(credits=30.0)] * 4, "r1")
    with pytest.raises(QuotaError) as exc:
        size(COPILOT, parse_budget("100credits"), table, max_sessions=None, spent=spent)
    assert "0 sessions" in str(exc.value) and "120credits spent earlier" in str(exc.value)
