"""compute_discretionary_balance tool - net monthly income minus average monthly spend.

Definition A (decided 2026-07-10): discretionary balance = monthly_income - actual average monthly
spending (over complete months), i.e. the honest "what's genuinely left" number that accounts for
how the user actually spends, not just their fixed bills. Reads only through the service layer.
"""

from decimal import Decimal

from app.services import profiles, transactions

COMPUTE_DISCRETIONARY_BALANCE_SCHEMA = {
    "name": "compute_discretionary_balance",
    "description": (
        "Estimates how much money the user has left in a typical month: their net monthly income "
        "(from their saved profile) minus their average monthly spending, averaged over complete "
        "months only. A positive number is a monthly surplus; a negative number means they "
        "typically spend more than they earn. Returns the balance and the figures behind it."
    ),
    "input_schema": {"type": "object", "properties": {}, "required": []},
}


def run_compute_discretionary_balance(user_id: str, jwt: str, tool_input: dict) -> dict:
    profile = profiles.get_profile(user_id, jwt)
    if not profile:
        return {"error": "No profile found - the user needs to complete onboarding first."}

    income = Decimal(str(profile["monthly_income"]))
    txns = transactions.get_transactions(jwt)
    avg_spend, months = transactions.average_monthly_spend(txns)
    discretionary = income - avg_spend

    return {
        "monthly_income": f"{income:.2f}",
        "average_monthly_spend": f"{avg_spend:.2f}",
        "discretionary_balance": f"{discretionary:.2f}",
        "complete_months_used": [f"{y}-{m:02d}" for (y, m) in months],
    }
