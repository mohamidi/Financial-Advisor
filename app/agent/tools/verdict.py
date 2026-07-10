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

Profile modifiers: existing debt can push a verdict ONE step stricter (capped) plus raise a flag;
risk tolerance never moves the verdict - it only sets a tone hint for how the agent should phrase
the explanation (a spending call shouldn't loosen just because someone tolerates investment risk).
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


def evaluate_affordability(cost, monthly_surplus, recurring: bool, available_balance=None,
                           monthly_expenses=None, existing_debt=None, monthly_income=None,
                           risk_tolerance=None) -> dict:
    """Decide yes/risky/no for a purchase, from the numbers alone.

    cost              - price of the thing (one-time) or the monthly amount (recurring)
    monthly_surplus   - net monthly income minus average monthly spend (Day 4 tools)
    recurring         - True for an ongoing monthly cost, False for a one-time purchase
    available_balance - cash minus credit-card bills, if known (None today; Plaid supplies it later)
    monthly_expenses  - average monthly spend, used as the reserve denominator when balance is known
    existing_debt     - total debt balance from the profile (modifier: heavy debt → stricter + flag)
    monthly_income    - net monthly income from the profile (the yardstick for "heavy" debt)
    risk_tolerance    - 'low'|'medium'|'high' from the profile (tone hint only, never moves the verdict)
    """
    cost = _money(cost)
    surplus = _money(monthly_surplus)

    if recurring:
        base = _recurring(cost, surplus)
    elif available_balance is not None and monthly_expenses is not None:
        base = _one_time_with_balance(cost, surplus, _money(available_balance), _money(monthly_expenses))
    else:
        base = _one_time_cash_flow(cost, surplus)

    return _apply_modifiers(base, existing_debt, monthly_income, risk_tolerance)


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


# Verdict severity order; "stricter" moves toward "no". The only verdict-moving modifier is heavy
# debt (one step), so the "cap at one step" agreed with the owner holds by construction.
_ORDER = ["yes", "risky", "no"]


def _stricter(verdict: str) -> str:
    return _ORDER[min(_ORDER.index(verdict) + 1, len(_ORDER) - 1)]


def _apply_modifiers(result: dict, existing_debt, monthly_income, risk_tolerance) -> dict:
    flags = list(result["risk_flags"])

    # Existing debt: heavy debt (> 3x monthly income) nudges the verdict one step stricter AND flags;
    # merely meaningful debt (>= a month's income) only flags. Trivial debt is ignored so we don't nag.
    if existing_debt is not None and monthly_income is not None:
        debt = _money(existing_debt)
        income = _money(monthly_income)
        if income > 0 and debt > 0:
            if debt > 3 * income:
                result["verdict"] = _stricter(result["verdict"])
                # The base summary described the pre-downgrade verdict - refresh it so summary and
                # verdict don't contradict each other.
                result["summary"] = "Your debt load pushes this to a more conservative call."
                flags.append(
                    f"You carry ${debt} in debt - more than 3x your monthly income - so I've weighted "
                    f"this more conservatively; paying that down likely deserves priority."
                )
            elif debt >= income:
                flags.append(
                    f"You carry ${debt} in existing debt; putting money toward that may deserve "
                    f"priority over this."
                )

    # Risk tolerance: tone hint for the agent's wording ONLY - it must not move the verdict.
    if risk_tolerance == "low":
        result["tone_for_agent"] = "Risk-averse user: frame cautiously and don't downplay the downsides."
    elif risk_tolerance == "high":
        result["tone_for_agent"] = (
            "Risk-tolerant user: you may acknowledge their comfort with risk, but do NOT overturn or "
            "soften the verdict itself."
        )

    result["risk_flags"] = flags
    return result


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


# --- The Claude tool wrapper ---------------------------------------------------------------
# The model supplies ONLY `cost` and `recurring`. Every financial figure that drives the verdict
# (surplus, expenses, debt, risk tolerance) is pulled from the user's real data here in the
# executor, so the model can't fudge the inputs to a deterministic decision - the same "identity/
# facts are app-enforced, not model-asserted" principle behind save_profile's injected user_id.

GET_AFFORDABILITY_VERDICT_SCHEMA = {
    "name": "get_affordability_verdict",
    "description": (
        "Get a grounded yes/risky/no verdict on whether the user can afford a purchase. You supply "
        "only the cost and whether it's a one-time purchase or a recurring monthly cost - every "
        "financial figure behind the verdict (income, average spending, surplus, existing debt, "
        "risk tolerance) is pulled automatically from the user's real data. If the user stated a "
        "price, pass that exact number; otherwise pass your best estimate. The returned verdict is "
        "deterministic: present it and its reasoning to the user and never soften a 'risky' or 'no'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "cost": {
                "type": "number",
                "description": "Purchase amount in USD - the one-time total, or the monthly amount if recurring.",
            },
            "recurring": {
                "type": "boolean",
                "description": "True for an ongoing monthly cost (car payment, subscription); false for a one-time purchase.",
            },
            "description": {
                "type": "string",
                "description": "Short description of the purchase, e.g. 'trip to Japan'. Optional.",
            },
        },
        "required": ["cost", "recurring"],
    },
}


def run_get_affordability_verdict(user_id: str, jwt: str, tool_input: dict) -> dict:
    # Local imports so the pure verdict logic above stays importable without pulling in the DB/HTTP
    # service layer (keeps scripts/test_verdict.py dependency-light).
    from app.services import profiles, transactions

    profile = profiles.get_profile(user_id, jwt)
    if not profile:
        return {"error": "No profile found - the user needs to complete onboarding first."}

    income = Decimal(str(profile["monthly_income"]))
    txns = transactions.get_transactions(jwt)
    avg_spend, _ = transactions.average_monthly_spend(txns)

    result = evaluate_affordability(
        cost=tool_input["cost"],
        monthly_surplus=income - avg_spend,
        recurring=bool(tool_input["recurring"]),
        available_balance=None,  # Plaid supplies this in Phase 2; verdict falls back to cash-flow
        monthly_expenses=avg_spend,
        existing_debt=profile.get("existing_debt"),
        monthly_income=income,
        risk_tolerance=profile.get("risk_tolerance"),
    )
    if tool_input.get("description"):
        result["purchase"] = tool_input["description"]
    return result
