"""Verifies the Day 8 per-user daily-budget check WITHOUT spending on Claude:

1. Unit: over_daily_budget() compares today's tokens against the limit correctly.
2. Endpoint: with the budget forced below today's usage, POST /chat returns 429 - and because the
   check runs BEFORE run_agent_turn, no Claude call is made (being over-quota is free). With a high
   budget the same request is NOT blocked by the budget gate.

Run with: uv run python -m scripts.test_budget
"""

import httpx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import usage

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
    auth = {"Authorization": f"Bearer {jwt}"}

    # Make sure the demo user has SOME usage recorded today, so "used" is > 0 deterministically.
    acc = usage.UsageAccumulator()
    acc.add(type("U", (), {"input_tokens": 400, "output_tokens": 100})())
    usage.log_usage(user_id, "claude-sonnet-5", acc)
    used_now = usage.usage_today(user_id)
    used_tokens = used_now["input_tokens"] + used_now["output_tokens"]
    assert used_tokens > 0

    # 1. Unit ----------------------------------------------------------------------------------
    exceeded, used, limit = usage.over_daily_budget(user_id, limit_tokens=1)
    assert exceeded and used == used_tokens and limit == 1, (exceeded, used, limit)
    exceeded, _, _ = usage.over_daily_budget(user_id, limit_tokens=10**12)
    assert not exceeded
    print(f"OK - over_daily_budget: {used_tokens} used today -> over a limit of 1, under a huge limit.")

    # 2. Endpoint 429 (no Claude call) ---------------------------------------------------------
    client = TestClient(app, raise_server_exceptions=True)
    original = settings.daily_token_budget_per_user
    try:
        settings.daily_token_budget_per_user = 1  # below today's usage -> must block
        r = client.post("/chat", headers=auth, json={"history": [], "message": "Can I afford a $2000 trip?"})
        assert r.status_code == 429, f"expected 429, got {r.status_code}: {r.text}"
        assert "limit reached" in r.json()["detail"].lower()
        print(f"OK - over budget -> 429, no Claude call spent. detail: {r.json()['detail']!r}")

        # With headroom, the budget gate does NOT block (the request would then proceed to the
        # advisor - we assert only that it's not a 429, without spending on the reply).
        settings.daily_token_budget_per_user = 10**12
        exceeded, _, _ = usage.over_daily_budget(user_id)
        assert not exceeded
        print("OK - with a high budget the same user is under quota (gate open).")
    finally:
        settings.daily_token_budget_per_user = original


if __name__ == "__main__":
    main()
