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

Todo budget-meter-wiring: each plan names the `meter` a night holds a budget against between
launches (METER_UNITS: the unit it reads), or in `no_meter` why none moves during a night, and
the budget line says which. Todo resumed-held-run-budgets: `spent` is what an arm's records
under a resumed run already spent, in the budget's unit, and `size` buys only what is left.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping, Sequence
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
_PLAN_KEYS = {"name", "credit_usd", "meter", "no_meter", "usd_per_week_point", "point_source"}
_TENTH = Decimal("0.1")
_STEP = Decimal("0.0001")  # a spend and what is left, shown and held to a ten-thousandth

# Todo budget-meter-wiring: a plan's `meter` and the unit it reads: the OpenRouter credits API
# (the account's whole usage, in dollars), the arm's records' `credits` (each Copilot session's
# usage file), the arm's records' API-equivalent `cost_usd` over the plan's usd_per_week_point.
METER_OPENROUTER, METER_CREDITS, METER_COST = "openrouter", "credits", "cost_usd"
METER_UNITS = {METER_OPENROUTER: USD, METER_CREDITS: CREDITS, METER_COST: WEEK}

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
    meter: str | None = None  # one of METER_UNITS; None: `no_meter` says why none reads live
    no_meter: str | None = None
    usd_per_week_point: Decimal | None = None  # a METER_COST plan's calibration
    point_source: str | None = None  # where and when usd_per_week_point was measured

    def meter_text(self) -> str:
        """What the plan's meter reads, for the budget line."""
        if self.meter == METER_OPENROUTER:
            return "the OpenRouter credits API (the account's whole usage)"
        if self.meter == METER_CREDITS:
            return "the arm's records' credits (each session's usage file)"
        return (f"the arm's records' cost_usd at ${format(self.usd_per_week_point, 'f')} a "
                "point of the week")  # fmt: skip


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
    meter, no_meter = table.get("meter"), table.get("no_meter")
    if (meter is None) == (no_meter is None):
        raise QuotaError("needs one of meter (the live meter a budget is held against: "
                         f"{', '.join(METER_UNITS)}) and no_meter (why none reads live)")
    if meter is not None and meter not in METER_UNITS:
        raise QuotaError(f"meter {meter!r} is not one of {', '.join(METER_UNITS)}")
    point = table.get("usd_per_week_point")
    if meter == METER_COST and point is None:
        raise QuotaError(f"meter {METER_COST} needs usd_per_week_point")
    return Plan(name, _text(table, "name"),
                None if credit is None else _positive(credit, "credit_usd"), meter,
                None if no_meter is None else _text(table, "no_meter"),
                None if point is None else _positive(point, "usd_per_week_point"),
                None if point is None else _text(table, "point_source"))  # fmt: skip


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
class Spent:
    """Todo resumed-held-run-budgets: what an arm's `sessions` attempt records under `run`
    already spent, `amount` in a budget unit, and `how` each was counted."""

    run: str
    sessions: int
    amount: Decimal
    how: str


def _rounded(amount: Decimal, unit: str) -> str:
    return _shown(amount.quantize(_STEP, rounding=ROUND_HALF_UP), unit)


def _left(budget: Budget, spent: Spent | None) -> Decimal:
    """The budget less the earlier spend, rounded down to _STEP (never more than is left)."""
    if spent is None:
        return budget.amount
    return (budget.amount - spent.amount).quantize(_STEP, rounding=ROUND_FLOOR)


def _figure(value: object) -> Decimal:
    return Decimal(str(value))


def _measured(entry: ArmQuota, unit: str, record: Mapping) -> tuple[Decimal, str] | None:
    """The record's own figure in `unit` and what it is, or None when it has none: a Copilot
    record's `credits` (null: its usage file named none), through credit_usd for dollars;
    another record's `cost_usd` for dollars, or for the week over usd_per_week_point."""
    plan = entry.plan
    if "credits" in record:
        credits = record["credits"]
        if credits is None:
            return None
        if unit == CREDITS:
            return _figure(credits), "their credits"
        if unit == USD and plan.credit_usd is not None:
            return _figure(credits) * plan.credit_usd, "their credits"
        return None
    if unit == USD:
        return _figure(record["cost_usd"]), "their cost_usd"
    if unit == WEEK and plan.usd_per_week_point is not None:
        point = plan.usd_per_week_point
        return (_figure(record["cost_usd"]) / point,
                f"their cost_usd at ${format(point, 'f')} a point")  # fmt: skip
    return None


def _tally(entry: ArmQuota, unit: str, records: Sequence[Mapping]) -> tuple[Decimal, str]:
    """What `records` spent in `unit` (each record's own figure, `_measured`, else the arm's
    quota per session) and how they were counted. QuotaError when a record needs the quota
    per session and the arm has none in `unit`."""
    amount, measured, estimated, what = Decimal(0), 0, 0, ""
    for record in records:
        found = _measured(entry, unit, record)
        if found is None:
            amount, estimated = amount + _per_session(entry, unit), estimated + 1
            continue
        amount, measured, what = amount + found[0], measured + 1, found[1]
    parts = [f"{measured} by {what}" if measured else "",
             f"{estimated} at {_shown(_per_session(entry, unit), unit)} per session"
             if estimated else ""]  # fmt: skip
    return amount, ", ".join(part for part in parts if part)


def spend(entry: ArmQuota, unit: str, records: Sequence[Mapping]) -> Decimal:
    """Todo budget-meter-wiring: what the arm's attempt `records` spent in `unit` (`_tally`), the
    running total a records meter reads."""
    return _tally(entry, unit, records)[0]


def spent(entry: ArmQuota, unit: str, records: Sequence[Mapping], run: str) -> Spent | None:
    """What `records` (the arm's attempt records under `run`) spent in `unit` (`_tally`); None:
    no record. QuotaError for a unit the arm has no figure for."""
    if not records:
        return None
    _per_session(entry, unit)  # the unit must be the arm's even when every record measures it
    amount, how = _tally(entry, unit, records)
    return Spent(run, len(records), amount, how)


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
    spent: Spent | None = None  # todo resumed-held-run-budgets: the resumed run's earlier spend

    @property
    def left(self) -> Budget:
        """What the night may spend: the budget less the run's earlier spend."""
        if self.spent is None:
            return self.budget
        return Budget(_left(self.budget, self.spent), self.budget.unit)

    def _spent_text(self) -> str:
        if self.spent is None:
            return ""
        unit = self.budget.unit
        return (f", {_rounded(self.spent.amount, unit)} spent earlier by {self.spent.sessions} "
                f"sessions of run {self.spent.run} ({self.spent.how}), "
                f"{_rounded(self.left.amount, unit)} left")  # fmt: skip

    def _meter_text(self) -> str:
        """Todo budget-meter-wiring: what holds the budget between launches."""
        plan, unit = self.quota.plan, self.budget.unit
        if plan.meter is None:
            return f"no live meter ({plan.no_meter}), so the session cap alone holds it"
        if METER_UNITS[plan.meter] != unit:
            return (f"the meter reads {METER_UNITS[plan.meter]} ({plan.meter_text()}), not "
                    f"{unit}, so the session cap alone holds it")  # fmt: skip
        return f"between launches the meter reads {plan.meter_text()}"

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
        return (f"budget {self.arm}: {self.budget} of {entry.plan.name}{self._spent_text()} / "
                f"{_shown(self.per_session, self.budget.unit)} per session ({entry.source}"
                f"{made}) -> {self.sessions} sessions ({bound}) -> {expected}; "
                f"{self._meter_text()}")

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
                "rate_source": entry.rate_source, "meter": self._meter_text(),
                "spent": None if self.spent is None else {
                    "run": self.spent.run, "sessions": self.spent.sessions,
                    "amount": format(self.spent.amount.normalize(), "f"), "how": self.spent.how,
                    "left": format(self.left.amount.normalize(), "f")}}  # fmt: skip


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
         max_sessions: int | None, spent: Spent | None = None) -> Sizing:  # fmt: skip
    """The cap `budget` buys for `arm` tonight, at most `max_sessions` (its backends.toml
    max_sessions; None: none); todo resumed-held-run-budgets: less what `spent` (the resumed
    run's records) already spent. QuotaError for an arm with no entry in `table`, a unit it has
    no figure for, or a budget that buys no session."""
    entry = table.get(arm)
    if entry is None:
        raise QuotaError(f"arm {arm} has no quota entry in {QUOTA_TOML.name}, so a budget "
                         f"cannot size it (arms with one: {', '.join(table)})")
    per = _per_session(entry, budget.unit)
    left = _left(budget, spent)
    by_budget = int((left / per).to_integral_value(rounding=ROUND_FLOOR))
    if by_budget < 1:
        earlier = ("" if spent is None else
                   f" ({_rounded(spent.amount, budget.unit)} spent earlier by {spent.sessions} "
                   f"sessions of run {spent.run})")  # fmt: skip
        raise QuotaError(f"budget {budget} for arm {arm} buys 0 sessions at "
                         f"{_shown(per, budget.unit)} per session{earlier}")  # fmt: skip
    if max_sessions is not None and max_sessions < by_budget:
        return Sizing(arm, budget, entry, per, by_budget, max_sessions, BY_MAX_SESSIONS,
                      max_sessions, spent)  # fmt: skip
    return Sizing(arm, budget, entry, per, by_budget, by_budget, BY_BUDGET, max_sessions, spent)
