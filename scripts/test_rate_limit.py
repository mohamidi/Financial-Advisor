"""Verifies the Day 8 per-user rate limit WITHOUT spending on Claude:

1. Unit: over_rate_limit() counts the user's usage_events rows in the trailing hour vs the limit.
2. Endpoint: with the limit forced at/below the current count, POST /chat returns 429 (with a
   Retry-After header) - and because the check runs BEFORE run_agent_turn, no Claude call is made.

Run with: uv run python -m scripts.test_rate_limit
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

    # Guarantee at least one completed-turn row in the trailing hour, so count > 0 deterministically.
    acc = usage.UsageAccumulator()
    acc.add(type("U", (), {"input_tokens": 10, "output_tokens": 10})())
    usage.log_usage(user_id, "claude-sonnet-5", acc)
    count = usage.messages_last_hour(user_id)
    assert count >= 1, count

    # 1. Unit ----------------------------------------------------------------------------------
    exceeded, c, limit = usage.over_rate_limit(user_id, limit=count)
    assert exceeded and c == count and limit == count, (exceeded, c, limit)
    exceeded, _, _ = usage.over_rate_limit(user_id, limit=count + 1)
    assert not exceeded
    print(f"OK - over_rate_limit: {count} msgs in last hour -> over a limit of {count}, under {count + 1}.")

    # 2. Endpoint 429 (no Claude call) ---------------------------------------------------------
    client = TestClient(app)
    original = settings.max_messages_per_hour_per_user
    try:
        settings.max_messages_per_hour_per_user = 1  # <= count -> must throttle
        r = client.post("/chat", headers=auth, json={"history": [], "message": "Can I afford a $2000 trip?"})
        assert r.status_code == 429, f"expected 429, got {r.status_code}: {r.text}"
        assert "too many messages" in r.json()["detail"].lower()
        assert r.headers.get("Retry-After") == "3600", r.headers
        print(f"OK - over rate limit -> 429 + Retry-After, no Claude call spent. detail: {r.json()['detail']!r}")
    finally:
        settings.max_messages_per_hour_per_user = original


if __name__ == "__main__":
    main()
