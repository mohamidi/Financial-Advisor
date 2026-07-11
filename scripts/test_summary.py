"""Verifies the Increment-1 backend prep WITHOUT spending on Claude:

1. GET /summary end-to-end (real demo data): surplus/income/avg spend, per-category monthly averages
   that sum back to avg spend, and a 6-month cumulative projection stepping by the surplus.
2. The structured verdict block: build_executors' sink captures the deterministic verdict, and
   _verdict_block curates it into the fields the verdict card renders. (The verdict tool reads the
   DB and runs pure logic - no Claude - so this is free.)

Run with: uv run python -m scripts.test_summary
"""

from decimal import Decimal

import httpx
from fastapi.testclient import TestClient

from app.agent.advisor import build_executors
from app.config import settings
from app.main import _verdict_block, app
from app.services import profiles

DEMO_EMAIL = "demo@financial-advisor.test"
DEMO_PASSWORD = "demo-user-not-a-real-password-123"

BASELINE = {
    "age": 34, "marital_status": "married", "monthly_income": "6800.00",
    "existing_debt": "15000.00", "risk_tolerance": "medium", "dependents": 2, "notes": "",
}


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
    profiles.save_profile(user_id, jwt, BASELINE)
    client = TestClient(app)
    auth = {"Authorization": f"Bearer {jwt}"}

    # --- /summary ---------------------------------------------------------------------------
    assert client.get("/summary").status_code == 401
    r = client.get("/summary", headers=auth)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["monthly_income"] == "6800.00" and s["avg_spend"] == "3377.41", s
    assert s["monthly_surplus"] == "3422.59", s["monthly_surplus"]

    cats = s["spending_by_category"]
    assert cats and all("category" in c and "amount" in c for c in cats)
    cat_sum = sum(Decimal(c["amount"]) for c in cats)
    # Per-category monthly averages should sum back to avg monthly spend (allow a few cents of
    # per-category rounding drift).
    assert abs(cat_sum - Decimal("3377.41")) < Decimal("0.10"), cat_sum
    # Sorted descending by amount.
    amounts = [Decimal(c["amount"]) for c in cats]
    assert amounts == sorted(amounts, reverse=True), amounts

    proj = s["projection"]
    assert len(proj) == 6 and proj[0]["month"] == 1 and proj[5]["month"] == 6
    assert proj[0]["cumulative"] == "3422.59", proj[0]
    assert proj[5]["cumulative"] == "20535.54", proj[5]  # 3422.59 * 6
    assert s["profile"]["age"] == 34
    print(f"OK - /summary: surplus $3,422.59, {len(cats)} categories summing to ${cat_sum}, "
          f"6-mo projection to ${proj[5]['cumulative']}.")

    # --- verdict block ----------------------------------------------------------------------
    sink: list = []
    execs = build_executors(user_id, jwt, verdict_sink=sink)
    execs["get_affordability_verdict"]({"cost": 8000, "recurring": False, "description": "trip to Italy"})
    assert len(sink) == 1, sink
    block = _verdict_block(sink)
    assert block["verdict"] == "risky", block  # $8k one-time vs $3,422.59 surplus = 2.3x
    assert block["cost"] == "8000.00" and block["monthly_surplus"] == "3422.59", block
    assert block["months_to_absorb"] == "2.3", block
    assert block["expense_type"] == "one-time" and block["purchase"] == "trip to Italy"
    assert isinstance(block["risk_flags"], list)
    print(f"OK - verdict block: {block['verdict'].upper()}, cost {block['cost']}, "
          f"{block['months_to_absorb']} mo to absorb, {len(block['risk_flags'])} flag(s).")

    # Edge cases: nothing ran, or the tool errored -> no card.
    assert _verdict_block([]) is None
    assert _verdict_block([{"error": "No profile found"}]) is None
    print("OK - no verdict / errored verdict -> no card block.")


if __name__ == "__main__":
    main()
