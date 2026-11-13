# SPDX-License-Identifier: GPL-3.0-or-later
"""Budget-sized drives (todo budget-runs-and-contributors).

`drive --arm-budget NAME=BUDGET` states what a contributor will spend on one arm tonight in the
plan's own terms: `<p>%week` (percent of the plan's weekly meter), `<p>%5h` (percent of its
5-hour window), `$<usd>` or `<n>credits`. `config/driver/quota.toml` names the plans and gives
each arm its quota per session, with the source and date of each figure and the arm's measured
match rate. `size` turns a budget into the arm's session cap tonight: floor(budget / per
session), never above the arm's backends.toml max_sessions, and says which bound won. Every
amount is a Decimal, so $0.90 at $0.30 a session is 3 sessions, never a float's 2.

The plans are named in the file and nowhere here: a plan with a `credit_usd` lets a `$` budget
and a `credits` budget convert into each other. An arm of quota.toml need not be in
backends.toml (and the reverse); only an arm given a budget must have an entry.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from pathlib import Path

from .targets import REPO_ROOT

QUOTA_TOML = REPO_ROOT / "config" / "driver" / "quota.toml"

WEEK, FIVE_HOUR, USD, CREDITS = "%week", "%5h", "$", "credits"  # the budget units
UNITS = (WEEK, FIVE_HOUR, USD, CREDITS)
_FIELDS = {"week_percent": WEEK, "five_hour_percent": FIVE_HOUR, "usd": USD, "credits": CREDITS}
_PERCENT = (WEEK, FIVE_HOUR)
_NUMBER = r"(\d+(?:\.\d+)?)"
_FORMS = {WEEK: re.compile(_NUMBER + "%week"), FIVE_HOUR: re.compile(_NUMBER + "%5h"),
          USD: re.compile(r"\$" + _NUMBER), CREDITS: re.compile(_NUMBER + "credits")}  # fmt: skip
_FORMS_SHOWN = "<p>%week, <p>%5h, $<usd> or <n>credits"
_ARM_KEYS = {"plan", "source", "read", "estimate", "matched", "sessions", "rate_source",
             *_FIELDS}  # fmt: skip
_PLAN_KEYS = {"name", "credit_usd"}
_TENTH = Decimal("0.1")

BY_BUDGET, BY_MAX_SESSIONS = "budget", "max_sessions"  # which bound set the cap


class QuotaError(ValueError):
    """A budget or quota.toml is not usable; the text names the file, the arm and the field."""


@dataclass(frozen=True)
class Budget:
    """One `--arm-budget` amount in one of UNITS."""

    amount: Decimal
    unit: str

    def __str__(self) -> str:
        return _shown(self.amount, self.unit)


def _shown(amount: Decimal, unit: str) -> str:
    text = format(amount.normalize(), "f")
    return f"${text}" if unit == USD else f"{text}{unit}"


def parse_budget(text: str) -> Budget:
    """`<p>%week`, `<p>%5h` (p above 0 and at most 100), `$<usd>` or `<n>credits` (above 0)."""
    for unit, form in _FORMS.items():
        found = form.fullmatch(text)
        if found is None:
            continue
        amount = Decimal(found.group(1))
        if amount <= 0 or (unit in _PERCENT and amount > 100):
            break
        return Budget(amount, unit)
    raise QuotaError(f"budget {text!r} is not one of {_FORMS_SHOWN} (a percent is above 0 and "
                     "at most 100, an amount above 0)")  # fmt: skip


@dataclass(frozen=True)
class Plan:
    """One `[plans.<id>]` table: what a contributor pays for."""

    id: str
    name: str
    credit_usd: Decimal | None = None


@dataclass(frozen=True)
class ArmQuota:
    """One `[arms.<name>]` table: the quota one session takes from `plan`, per unit."""

    arm: str
    plan: Plan
    per_session: Mapping[str, Decimal]
    source: str
    read: date
    estimate: bool = False
    matched: int | None = None
    sessions: int | None = None
    rate_source: str | None = None


def _positive(value: object, key: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise QuotaError(f"{key} {value!r} is not a number above 0")
    return Decimal(str(value))


def _text(table: Mapping, key: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise QuotaError(f"needs {key}, a non-empty string")
    return value


def _plan(name: str, table: object) -> Plan:
    if not isinstance(table, Mapping):
        raise QuotaError("is not a table")
    stray = sorted(set(table) - _PLAN_KEYS)
    if stray:
        raise QuotaError(f"unknown key {stray[0]!r} (keys: {', '.join(sorted(_PLAN_KEYS))})")
    credit = table.get("credit_usd")
    return Plan(name, _text(table, "name"),
                None if credit is None else _positive(credit, "credit_usd"))  # fmt: skip


def _rate(table: Mapping) -> tuple[int | None, int | None, str | None]:
    """The measured `matched` of `sessions` and its `rate_source`: all three, or none."""
    matched, sessions = table.get("matched"), table.get("sessions")
    if matched is None and sessions is None:
        return None, None, None
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (matched, sessions)):
        raise QuotaError("matched and sessions are whole numbers, given together")
    if sessions < 1 or not 0 <= matched <= sessions:
        raise QuotaError(f"matched {matched} of sessions {sessions} is not a rate")
    return matched, sessions, _text(table, "rate_source")


def _arm(name: str, table: object, plans: Mapping[str, Plan]) -> ArmQuota:
    if not isinstance(table, Mapping):
        raise QuotaError("is not a table")
    stray = sorted(set(table) - _ARM_KEYS)
    if stray:
        raise QuotaError(f"unknown key {stray[0]!r} (keys: {', '.join(sorted(_ARM_KEYS))})")
    plan = table.get("plan")
    if plan not in plans:
        raise QuotaError(f"plan {plan!r} is not a [plans.<id>] table: {', '.join(plans)}")
    per = {unit: _positive(table[key], key) for key, unit in _FIELDS.items() if key in table}
    if not per:
        raise QuotaError(f"needs a quota per session: one of {', '.join(_FIELDS)}")
    read = table.get("read")
    if not isinstance(read, date):
        raise QuotaError(f"read {read!r} is not a date (read = 2026-11-13)")
    estimate = table.get("estimate", False)
    if not isinstance(estimate, bool):
        raise QuotaError(f"estimate {estimate!r} is not true or false")
    matched, sessions, rate_source = _rate(table)
    return ArmQuota(name, plans[plan], per, _text(table, "source"), read, estimate, matched,
                    sessions, rate_source)  # fmt: skip


def load_quota(path: Path = QUOTA_TOML) -> dict[str, ArmQuota]:
    """Read and validate quota.toml; QuotaError names the file, the table and the field."""
    path = Path(path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise QuotaError(f"{path}: {exc}") from exc
    plans, arms = data.get("plans"), data.get("arms")
    stray = sorted(set(data) - {"plans", "arms"})
    if stray or not isinstance(plans, Mapping) or not isinstance(arms, Mapping) or not arms:
        extra = f" (found {', '.join(stray)})" if stray else ""
        raise QuotaError(f"{path}: needs [plans.<id>] and [arms.<name>] tables and nothing "
                         f"else{extra}")  # fmt: skip
    named = {}
    for name, table in plans.items():
        try:
            named[name] = _plan(name, table)
        except QuotaError as exc:
            raise QuotaError(f"{path}: plan {name!r}: {exc}") from None
    out = {}
    for name, table in arms.items():
        try:
            out[name] = _arm(name, table, named)
        except QuotaError as exc:
            raise QuotaError(f"{path}: arm {name!r}: {exc}") from None
    return out


@dataclass(frozen=True)
class Sizing:
    """What one arm's budget buys tonight: `by_budget` sessions from floor(budget / per
    session), `sessions` the cap after the arm's max_sessions, and `bound` which one won."""

    arm: str
    budget: Budget
    quota: ArmQuota
    per_session: Decimal  # in the budget's unit
    by_budget: int
    sessions: int
    bound: str
    max_sessions: int | None

    @property
    def expected(self) -> Decimal | None:
        """Expected matches at the measured rate, to a tenth; None: no rate."""
        if self.quota.sessions is None:
            return None
        rate = Decimal(self.quota.matched) / Decimal(self.quota.sessions)
        return (self.sessions * rate).quantize(_TENTH, rounding=ROUND_HALF_UP)

    def line(self) -> str:
        """The dry run's line: budget -> quota per session (source, date) -> sessions ->
        expected matches."""
        entry = self.quota
        made = f", read {entry.read.isoformat()}" + ("; an estimate, re-measure"
                                                     if entry.estimate else "")  # fmt: skip
        bound = ("the budget" if self.bound == BY_BUDGET else
                 f"max_sessions {self.max_sessions} in backends.toml; the budget buys "
                 f"{self.by_budget}")  # fmt: skip
        expected = ("expected matches unmeasured (no rate in quota.toml)"
                    if self.expected is None else
                    f"about {self.expected} expected matches ({entry.matched} of "
                    f"{entry.sessions} sessions, {entry.rate_source})")  # fmt: skip
        return (f"budget {self.arm}: {self.budget} of {entry.plan.name} / "
                f"{_shown(self.per_session, self.budget.unit)} per session ({entry.source}"
                f"{made}) -> {self.sessions} sessions ({bound}) -> {expected}")

    def doc(self) -> dict:
        """The dry run's JSON form of the line."""
        entry = self.quota
        return {"arm": self.arm, "budget": str(self.budget), "plan": entry.plan.name,
                "per_session": format(self.per_session.normalize(), "f"),
                "unit": self.budget.unit, "source": entry.source,
                "read": entry.read.isoformat(), "estimate": entry.estimate,
                "sessions": self.sessions, "by_budget": self.by_budget, "bound": self.bound,
                "max_sessions": self.max_sessions,
                "expected_matches": None if self.expected is None else str(self.expected),
                "rate": None if entry.sessions is None else [entry.matched, entry.sessions],
                "rate_source": entry.rate_source}  # fmt: skip


def _per_session(entry: ArmQuota, unit: str) -> Decimal:
    """The arm's quota per session in `unit`, through its plan's credit_usd between dollars
    and credits; QuotaError when it has no figure in that unit."""
    if unit in entry.per_session:
        return entry.per_session[unit]
    credit = entry.plan.credit_usd
    if credit is not None and unit == USD and CREDITS in entry.per_session:
        return entry.per_session[CREDITS] * credit
    if credit is not None and unit == CREDITS and USD in entry.per_session:
        return entry.per_session[USD] / credit
    have = ", ".join(entry.per_session)
    raise QuotaError(f"arm {entry.arm} has no {unit} quota per session in "
                     f"{QUOTA_TOML.name} (it has: {have})")  # fmt: skip


def size(arm: str, budget: Budget, table: Mapping[str, ArmQuota], *,
         max_sessions: int | None) -> Sizing:  # fmt: skip
    """The cap `budget` buys for `arm` tonight, at most `max_sessions` (its backends.toml
    max_sessions; None: none). QuotaError for an arm with no entry in `table`, a unit it has no
    figure for, or a budget that buys no session."""
    entry = table.get(arm)
    if entry is None:
        raise QuotaError(f"arm {arm} has no quota entry in {QUOTA_TOML.name}, so a budget "
                         f"cannot size it (arms with one: {', '.join(table)})")
    per = _per_session(entry, budget.unit)
    by_budget = int((budget.amount / per).to_integral_value(rounding=ROUND_FLOOR))
    if by_budget < 1:
        raise QuotaError(f"budget {budget} for arm {arm} buys 0 sessions at "
                         f"{_shown(per, budget.unit)} per session")  # fmt: skip
    if max_sessions is not None and max_sessions < by_budget:
        return Sizing(arm, budget, entry, per, by_budget, max_sessions, BY_MAX_SESSIONS,
                      max_sessions)  # fmt: skip
    return Sizing(arm, budget, entry, per, by_budget, by_budget, BY_BUDGET, max_sessions)
