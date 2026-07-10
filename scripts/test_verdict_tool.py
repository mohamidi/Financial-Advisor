"""Verifies the get_affordability_verdict tool executor end-to-end against real data (no Claude
API call - it only reads the DB and runs the deterministic verdict). Sets the demo profile to
known values first so the assertions are stable.

Run with: uv run python -m scripts.test_verdict_tool
"""

import httpx

from app.agent.tools.verdict import run_get_affordability_verdict
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


def show(label, r):
    print(f"{label}")
    print(f"  -> {r['verdict'].upper()}: {r['summary']}")
    print(f"     income ${r['monthly_surplus']} surplus | {r['reasoning']}")
    for f in r.get("risk_flags", []):
        print(f"     [flag] {f}")
    print()


def main():
    jwt = sign_in()
    user_id = settings.demo_user_id

    # Known baseline: income 6800, debt 15000 (meaningful, < 3x income so flag-only), risk medium.
    profiles.save_profile(user_id, jwt, {
        "age": 34, "marital_status": "married", "monthly_income": "6800.00",
        "existing_debt": "15000.00", "risk_tolerance": "medium", "dependents": 2, "notes": "",
    })
    print("Demo profile set: income $6800, debt $15000, risk medium.\n")

    show("Q: can I afford a $2,000 trip? (one-time)",
         run_get_affordability_verdict(user_id, jwt, {"cost": 2000, "recurring": False, "description": "a trip"}))
    show("Q: can I afford an $8,000 vacation? (one-time)",
         run_get_affordability_verdict(user_id, jwt, {"cost": 8000, "recurring": False}))
    show("Q: can I afford a $400/mo car payment? (recurring)",
         run_get_affordability_verdict(user_id, jwt, {"cost": 400, "recurring": True, "description": "car payment"}))

    # Sanity: the tool pulled the real surplus (income 6800 - avg spend 3377.41 = 3422.59).
    r = run_get_affordability_verdict(user_id, jwt, {"cost": 2000, "recurring": False})
    assert r["monthly_surplus"] == "3422.59", r["monthly_surplus"]
    assert r["verdict"] == "yes"
    print("OK - tool pulls real financial numbers and returns a deterministic verdict.")


if __name__ == "__main__":
    main()
