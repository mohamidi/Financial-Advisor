"""Deterministic affordability verdict - the load-bearing rule engine of the whole app.

CLAUDE.md constraint: this logic is DETERMINISTIC, not model discretion. The numbers decide the
verdict here; the agent may present and explain it but must never soften a "risky"/"no" into a
"yes". The reasoning strings are generated from the real numbers, so a verdict is always grounded.

Two lenses:
- ONE-TIME purchases: if we know the user's available balance (cash minus credit-card bills), the
  right question is "can you pay outright, and how much emergency cushion is left after?" - measured
  in months of expenses held in reserve. If we DON'T know the balance (the case today - Plaid brings
  it in Phase 2), we fall back to a cash-flow proxy (how many months of monthly surplus the cost
  equals) and say plainly that it's flow-based, not savings-based.
- RECURRING costs (car payment, subscription): always judged against monthly surplus - they're about
  ongoing flow, not savings.

Still deferred to a later increment: profile modifiers (existing debt, risk tolerance).
"""

from decimal import Decimal

# One-time, balance UNKNOWN: how many MONTHS of monthly surplus the cost equals (a conservative
# proxy for "can you absorb this" when we can't see savings).
ONE_TIME_COMFORTABLE_MONTHS = Decimal("1")
ONE_TIME_CHUNK_MONTHS = Decimal("2")
ONE_TIME_RISKY_MONTHS = Decimal("4")

# One-time, balance KNOWN: months of expenses held in reserve AFTER the purchase (emergency-fund view).
RESERVE_COMFORTABLE_MONTHS = Decimal("6")
RESERVE_OK_MONTHS = Decimal("3")
RESERVE_RISKY_MONTHS = Decimal("1")

# Recurring monthly cost: what FRACTION of monthly surplus it permanently consumes.
RECURRING_COMFORTABLE_FRACTION = Decimal("0.25")
RECURRING_SIGNIFICANT_FRACTION = Decimal("0.50")
RECURRING_RISKY_FRACTION = Decimal("0.80")


def _money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"))


def evaluate_affordability(cost, monthly_surplus, recurring: bool, available_balance=None, monthly_expenses=None) -> dict:
    """Decide yes/risky/no for a purchase, from the numbers alone.

    cost              - price of the thing (one-time) or the monthly amount (recurring)
    monthly_surplus   - net monthly income minus average monthly spend (Day 4 tools)
    recurring         - True for an ongoing monthly cost, False for a one-time purchase
    available_balance - cash minus credit-card bills, if known (None today; Plaid supplies it later)
    monthly_expenses  - average monthly spend, used as the reserve denominator when balance is known
    """
    cost = _money(cost)
    surplus = _money(monthly_surplus)

    if recurring:
        return _recurring(cost, surplus)
    if available_balance is not None and monthly_expenses is not None:
        return _one_time_with_balance(cost, surplus, _money(available_balance), _money(monthly_expenses))
    return _one_time_cash_flow(cost, surplus)


def _recurring(cost: Decimal, surplus: Decimal) -> dict:
    if surplus <= 0:
        return _result("no", "You're spending as much as or more than you earn.",
                       f"You have no monthly surplus (${surplus}) to commit to an ongoing cost.",
                       cost, surplus, True, [], {"basis": "cash flow (monthly surplus)"})
    remaining = surplus - cost
    fraction = cost / surplus
    if cost >= surplus:
        verdict, summary = "no", "This ongoing cost would wipe out your whole monthly surplus."
    elif fraction <= RECURRING_COMFORTABLE_FRACTION:
        verdict, summary = "yes", "Comfortable - a small slice of your monthly surplus."
    elif fraction <= RECURRING_SIGNIFICANT_FRACTION:
        verdict, summary = "yes", "Affordable, but a significant ongoing commitment."
    elif fraction <= RECURRING_RISKY_FRACTION:
        verdict, summary = "risky", "This would consume most of your monthly surplus."
    else:
        verdict, summary = "no", "This leaves you almost no monthly breathing room."
    reasoning = (f"An ongoing ${cost}/month would consume {fraction:.0%} of your ${surplus} monthly "
                 f"surplus, leaving about ${remaining}/month of breathing room afterward.")
    return _result(verdict, summary, reasoning, cost, surplus, True, [],
                   {"basis": "cash flow (monthly surplus)", "monthly_surplus_after": f"{remaining:.2f}"})


def _one_time_cash_flow(cost: Decimal, surplus: Decimal) -> dict:
    """Balance unknown - conservative months-of-surplus proxy, clearly labelled as flow-based."""
    note = ("Based on your monthly cash flow - I don't have your actual savings balance yet, so this "
            "assumes you'd cover it from monthly surplus. With a real balance (via Plaid) a large "
            "one-time purchase you have savings for could be fine.")
    if surplus <= 0:
        return _result("no", "You're spending as much as or more than you earn.",
                       f"You have no monthly surplus (${surplus}) to absorb a one-time cost. {note}",
                       cost, surplus, False, [], {"basis": "cash flow (monthly surplus)", "note": note})
    months = cost / surplus
    if months <= ONE_TIME_COMFORTABLE_MONTHS:
        verdict, summary = "yes", "Comfortable - well within a month's surplus."
    elif months <= ONE_TIME_CHUNK_MONTHS:
        verdict, summary = "yes", "Affordable, but a real chunk of your surplus."
    elif months <= ONE_TIME_RISKY_MONTHS:
        verdict, summary = "risky", "This is a large one-time hit relative to your surplus."
    else:
        verdict, summary = "no", "This would take many months of your entire surplus to absorb."
    reasoning = (f"A one-time cost of ${cost} is about {months:.1f}x your ${surplus} monthly surplus - "
                 f"it would take roughly {months:.1f} months of surplus to absorb.")
    return _result(verdict, summary, reasoning, cost, surplus, False, [],
                   {"basis": "cash flow (monthly surplus)", "months_to_absorb": f"{months:.1f}", "note": note})


def _one_time_with_balance(cost: Decimal, surplus: Decimal, balance: Decimal, expenses: Decimal) -> dict:
    """Balance known - the real question: can you pay outright, and how much cushion remains?"""
    flags: list[str] = []
    if surplus <= 0:
        flags.append("You're spending more than you earn month to month, which will erode this balance over time.")

    remaining = balance - cost
    if remaining < 0:
        reasoning = (f"This ${cost} purchase is more than your ${balance} available balance (cash minus "
                     f"credit-card bills), so you'd have to borrow to cover it.")
        return _result("no", "You don't have the cash for this without borrowing.", reasoning,
                       cost, surplus, False, flags,
                       {"basis": "available balance", "available_balance": f"{balance:.2f}",
                        "balance_after": f"{remaining:.2f}"})

    reserve_months = remaining / expenses if expenses > 0 else Decimal("999")
    if reserve_months >= RESERVE_COMFORTABLE_MONTHS:
        verdict, summary = "yes", "Comfortable - you keep a healthy emergency cushion."
    elif reserve_months >= RESERVE_OK_MONTHS:
        verdict, summary = "yes", "Affordable, but it noticeably thins your cushion."
    elif reserve_months >= RESERVE_RISKY_MONTHS:
        verdict, summary = "risky", "This leaves you with a thin safety net."
    else:
        verdict, summary = "no", "This would leave you dangerously little in reserve."
    reasoning = (f"You have ${balance} available (cash minus credit-card bills). After a ${cost} purchase "
                 f"you'd keep ${remaining} - about {reserve_months:.1f} months of your ${expenses}/mo "
                 f"expenses in reserve.")
    return _result(verdict, summary, reasoning, cost, surplus, False, flags,
                   {"basis": "available balance", "available_balance": f"{balance:.2f}",
                    "balance_after": f"{remaining:.2f}", "reserve_months": f"{reserve_months:.1f}"})


def _result(verdict, summary, reasoning, cost, surplus, recurring, flags, extra=None) -> dict:
    out = {
        "verdict": verdict,
        "summary": summary,
        "reasoning": reasoning,
        "cost": f"{cost:.2f}",
        "expense_type": "recurring monthly" if recurring else "one-time",
        "monthly_surplus": f"{surplus:.2f}",
        "risk_flags": flags,
    }
    if extra:
        out.update(extra)
    return out
