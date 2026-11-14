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


def test_the_committed_table_loads_with_its_plans_named_in_config():
    """The plans come from the file, the seeded per-session figures from docs/model-routing.md
    "Quota per session", and the measured rates from docs/model-comparison.md "Cascade
    nights"."""
    table = load_quota()
    assert table[HAIKU].plan.name == "Claude Code Ultra"
    assert table[HAIKU].per_session == {quota.WEEK: Decimal("0.03")}
    assert (table[HAIKU].matched, table[HAIKU].sessions) == (4, 78)
    assert table["claude-opus-5-5"].per_session == {quota.WEEK: Decimal("0.1")}
    assert table[TERRA].per_session == {quota.FIVE_HOUR: Decimal("1.35"),
                                        quota.WEEK: Decimal("0.22")}  # fmt: skip
    assert (table[TERRA].matched, table[TERRA].sessions) == (1, 91)
    assert table[GEMINI].per_session == {quota.WEEK: Decimal("15.0")}
    assert (table[GEMINI].matched, table[GEMINI].sessions) == (0, 1)
    assert table[DEEPSEEK].per_session == {quota.USD: Decimal("0.30")}
    assert (table[DEEPSEEK].matched, table[DEEPSEEK].sessions) == (2, 5)
    assert all(isinstance(entry.read, date) and entry.source for entry in table.values())


def test_the_copilot_entry_is_measured_and_needs_no_backends_arm():
    """The Copilot Pro plan (1 credit = $0.01) and its arm's figure, measured from the usage
    files of 8 sessions on 2026-11-14 (it replaced the placeholder of 4), load although
    backends.toml may not have that arm; an arm of backends.toml with no entry is fine."""
    table = load_quota()
    entry = table[COPILOT]
    assert not entry.estimate and "usage files" in entry.source
    assert entry.plan.credit_usd == Decimal("0.01")
    assert entry.per_session == {quota.CREDITS: Decimal("2.6")}
    assert "glm-5.3" in backends.load_arms() and "glm-5.3" not in table


_GOOD = """\
[plans.p]
name = "Plan P"

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
], ids=["no-arms", "stray-table", "unknown-plan", "zero", "bool", "no-quota", "no-source",
        "bad-date", "rate-above", "rate-half", "rate-no-source", "stray-key", "bad-credit",
        "no-plan-name"])  # fmt: skip
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
    """5%week at 0.03% per session: floor(166.67) = 166, bounded by the budget (Haiku has no
    max_sessions), and 166 x 4/78 = about 8.5 expected matches."""
    sizing = size(HAIKU, parse_budget("5%week"), load_quota(), max_sessions=None)
    assert (sizing.sessions, sizing.by_budget, sizing.bound) == (166, 166, quota.BY_BUDGET)
    assert sizing.per_session == Decimal("0.03")
    assert sizing.expected == Decimal("8.5")
    line = sizing.line()
    for words in ("claude-haiku-5-5", "5%week", "Claude Code Ultra", "0.03%week per session",
                  "read 2026-11-13", "166 sessions", "budget", "8.5", "4 of 78"):
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
    assert size(TERRA, parse_budget("10%week"), table, max_sessions=None).sessions == 45


def test_a_plan_credit_converts_dollars_and_credits():
    """Copilot Pro: 2.6 credits a session at $0.01 a credit, so $1 buys 38 sessions and 100
    credits buy 38; the line names no rate yet (unmeasured)."""
    table = load_quota()
    dollars = size(COPILOT, parse_budget("$1"), table, max_sessions=None)
    assert (dollars.sessions, dollars.per_session) == (38, Decimal("0.026"))
    assert size(COPILOT, parse_budget("100credits"), table, max_sessions=None).sessions == 38
    assert "unmeasured" in dollars.line()


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
                   "per_session": "0.03", "unit": quota.WEEK,
                   "source": load_quota()[HAIKU].source, "read": "2026-11-13",
                   "estimate": False, "sessions": 166, "by_budget": 166,
                   "bound": quota.BY_BUDGET, "max_sessions": None,
                   "expected_matches": "8.5", "rate": [4, 78],
                   "rate_source": load_quota()[HAIKU].rate_source}  # fmt: skip


def test_the_path_is_committed():
    assert quota.QUOTA_TOML == backends.REPO_ROOT / "config" / "driver" / "quota.toml"
    assert Path(quota.QUOTA_TOML).is_file()
