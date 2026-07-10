"""project_cash_flow tool - projects net cash flow (income minus typical spend) forward.

No account balance exists in the data yet (transactions are outflows only; Plaid brings a real
balance in Phase 2), so this projects CUMULATIVE net surplus/deficit from today, not an absolute
balance - decision A (2026-07-10). Useful for "is this purchase absorbed by my surplus, and when?"
Reads only through the service layer.
"""

import math
from decimal import Decimal

from app.services import profiles, transactions

PROJECT_CASH_FLOW_SCHEMA = {
    "name": "project_cash_flow",
    "description": (
        "Projects the user's net cash flow (net monthly income minus their typical monthly "
        "spending) forward over a number of months, optionally after a one-time purchase made now. "
        "Because the user's actual account balance isn't available yet, this projects CUMULATIVE "
        "net surplus/deficit from today - not an absolute account balance. Use it to see whether a "
        "one-time purchase is absorbed by their monthly surplus and how many months that takes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "months": {
                "type": "integer",
                "description": "How many months to project forward. Defaults to 6.",
            },
            "one_time_purchase": {
                "type": "number",
                "description": "A one-off purchase amount in USD applied now (month 1). Omit for none.",
            },
        },
        "required": [],
    },
}


def run_project_cash_flow(user_id: str, jwt: str, tool_input: dict) -> dict:
    profile = profiles.get_profile(user_id, jwt)
    if not profile:
        return {"error": "No profile found - the user needs to complete onboarding first."}

    income = Decimal(str(profile["monthly_income"]))
    txns = transactions.get_transactions(jwt)
    avg_spend, _ = transactions.average_monthly_spend(txns)
    monthly_net = income - avg_spend

    horizon = int(tool_input.get("months") or 6)
    purchase = (
        Decimal(str(tool_input["one_time_purchase"])).quantize(Decimal("0.01"))
        if tool_input.get("one_time_purchase")
        else Decimal("0")
    )

    projection = []
    cumulative = -purchase
    for month in range(1, horizon + 1):
        cumulative += monthly_net
        projection.append({"month": month, "cumulative_net": f"{cumulative:.2f}"})

    # Months for the monthly surplus to fully recover a one-time purchase, if it ever does.
    absorbed_by_month = None
    if purchase > 0 and monthly_net > 0:
        absorbed_by_month = math.ceil(purchase / monthly_net)

    return {
        "monthly_income": f"{income:.2f}",
        "average_monthly_spend": f"{avg_spend:.2f}",
        "monthly_net": f"{monthly_net:.2f}",
        "one_time_purchase": f"{purchase:.2f}",
        "horizon_months": horizon,
        "projection": projection,
        "purchase_absorbed_by_month": absorbed_by_month,
        "note": (
            "Cumulative net surplus/deficit from today, not an absolute balance "
            "(no account balance available yet)."
        ),
    }
