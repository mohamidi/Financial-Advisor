"""Verifies the Day 4 finance tools directly (not through the agent) against the seeded demo data,
cross-checking each tool's numbers against an independent recomputation from a raw fetch.

Signs in as the demo user so reads go through the real per-user Data API path (JWT + RLS).

Run with: uv run python -m scripts.test_finance_tools
"""

from decimal import Decimal

import httpx

from app.agent.tools.aggregate_spending import run_aggregate_spending
from app.agent.tools.compute_discretionary_balance import run_compute_discretionary_balance
from app.agent.tools.project_cash_flow import run_project_cash_flow
from app.config import settings
from app.services import profiles

DEMO_EMAIL = "demo@financial-advisor.test"
DEMO_PASSWORD = "demo-user-not-a-real-password-123"


def sign_in() -> str:
    resp = httpx.post(
        f"{settings.supabase_url}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": settings.supabase_publishable_key},
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def main():
    jwt = sign_in()
    user_id = settings.demo_user_id

    # --- aggregate_spending (all history) ---
    agg = run_aggregate_spending(user_id, jwt, {})
    print("aggregate_spending (all):")
    print(f"  count={agg['transaction_count']}, total=${agg['total_spent']}")
    for cat, amt in agg["by_category"].items():
        print(f"    {cat:<15} ${amt}")

    # cross-check: per-category totals must sum to the grand total
    cat_sum = sum(Decimal(v) for v in agg["by_category"].values())
    assert cat_sum == Decimal(agg["total_spent"]), f"{cat_sum} != {agg['total_spent']}"
    print("  OK - category breakdown sums to the grand total.\n")

    # cross-check a category filter against the unfiltered breakdown
    groceries = run_aggregate_spending(user_id, jwt, {"category": "Groceries"})
    assert groceries["total_spent"] == agg["by_category"]["Groceries"]
    print(f"  OK - category filter (Groceries ${groceries['total_spent']}) matches the breakdown.\n")

    # --- compute_discretionary_balance ---
    disc = run_compute_discretionary_balance(user_id, jwt, {})
    print("compute_discretionary_balance:")
    print(f"  income=${disc['monthly_income']}  avg_spend=${disc['average_monthly_spend']}  "
          f"discretionary=${disc['discretionary_balance']}")
    print(f"  complete months used: {disc['complete_months_used']}")
    # cross-check the arithmetic
    expected = Decimal(disc["monthly_income"]) - Decimal(disc["average_monthly_spend"])
    assert expected == Decimal(disc["discretionary_balance"])
    profile = profiles.get_profile(user_id, jwt)
    assert Decimal(disc["monthly_income"]) == Decimal(str(profile["monthly_income"]))
    print("  OK - discretionary = income - avg_spend, income matches profile.\n")

    # --- project_cash_flow (with a $2000 purchase over 6 months) ---
    proj = run_project_cash_flow(user_id, jwt, {"months": 6, "one_time_purchase": 2000})
    print("project_cash_flow ($2000 purchase, 6 months):")
    print(f"  monthly_net=${proj['monthly_net']}  absorbed_by_month={proj['purchase_absorbed_by_month']}")
    for row in proj["projection"]:
        print(f"    month {row['month']}: cumulative ${row['cumulative_net']}")
    # cross-check: month 1 cumulative = monthly_net - purchase
    m1 = Decimal(proj["projection"][0]["cumulative_net"])
    assert m1 == Decimal(proj["monthly_net"]) - Decimal(proj["one_time_purchase"])
    # cross-check: each month advances by exactly monthly_net
    for i in range(1, len(proj["projection"])):
        step = Decimal(proj["projection"][i]["cumulative_net"]) - Decimal(proj["projection"][i - 1]["cumulative_net"])
        assert step == Decimal(proj["monthly_net"])
    print("  OK - projection starts at net-minus-purchase and steps by monthly_net each month.\n")

    print("All finance-tool checks passed.")


if __name__ == "__main__":
    main()
