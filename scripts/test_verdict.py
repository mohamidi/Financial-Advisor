"""Exercises the pure verdict logic (app/agent/tools/verdict.py) across a spread of scenarios.

No auth, no DB, no Claude - just the deterministic math, so it's fast to run while we tune the
thresholds. Uses the demo user's real numbers as a realistic baseline.

Run with: uv run python -m scripts.test_verdict
"""

from app.agent.tools.verdict import evaluate_affordability

SURPLUS = "3422.59"    # demo user's income 6800 - avg monthly spend 3377.41
EXPENSES = "3377.41"   # avg monthly spend (reserve denominator when balance is known)
BALANCE = "40000.00"   # hypothetical available balance (cash - card bills); real value comes from Plaid


INCOME = "6800.00"  # demo user's net monthly income (yardstick for "heavy" debt)


def show(label, r):
    print(f"{label}")
    print(f"  -> {r['verdict'].upper()}: {r['summary']}")
    print(f"     {r['reasoning']}")
    if r.get("risk_flags"):
        for f in r["risk_flags"]:
            print(f"     [flag] {f}")
    if r.get("tone_for_agent"):
        print(f"     [tone] {r['tone_for_agent']}")
    print()


def main():
    print(f"Monthly surplus: ${SURPLUS}   Avg expenses: ${EXPENSES}\n")

    print("=== ONE-TIME, balance UNKNOWN (today - cash-flow proxy) ===\n")
    for label, cost in [("$2,000 trip", "2000"), ("$8,000 vacation", "8000"),
                        ("$25,000 car", "25000")]:
        show(label, evaluate_affordability(cost, SURPLUS, recurring=False))

    print(f"=== ONE-TIME, balance KNOWN = ${BALANCE} (Plaid future - emergency-fund view) ===\n")
    for label, cost in [("$8,000 vacation", "8000"), ("$25,000 car", "25000"),
                        ("$35,000 car", "35000"), ("$45,000 boat", "45000")]:
        show(label, evaluate_affordability(cost, SURPLUS, recurring=False,
                                           available_balance=BALANCE, monthly_expenses=EXPENSES))

    print("=== RECURRING (always surplus-based) ===\n")
    for label, cost in [("$400/mo car payment", "400"), ("$1,800/mo apartment", "1800"),
                        ("$3,000/mo second home", "3000")]:
        show(label, evaluate_affordability(cost, SURPLUS, recurring=True))

    print("=== MODIFIERS (income $6,800/mo; heavy-debt line = >$20,400) ===\n")
    show("$2,000 trip, no debt (baseline)",
         evaluate_affordability("2000", SURPLUS, recurring=False))
    show("$2,000 trip, $15k debt (meaningful, not heavy)",
         evaluate_affordability("2000", SURPLUS, recurring=False,
                                existing_debt="15000", monthly_income=INCOME))
    show("$2,000 trip, $25k debt (heavy -> one step stricter)",
         evaluate_affordability("2000", SURPLUS, recurring=False,
                                existing_debt="25000", monthly_income=INCOME))
    show("$2,000 trip, risk tolerance LOW (tone only, verdict unchanged)",
         evaluate_affordability("2000", SURPLUS, recurring=False, risk_tolerance="low"))
    show("$2,000 trip, risk tolerance HIGH (tone only, verdict unchanged)",
         evaluate_affordability("2000", SURPLUS, recurring=False, risk_tolerance="high"))


if __name__ == "__main__":
    main()
