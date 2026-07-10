"""Verifies the Day 7 usage-logging path WITHOUT a Claude call (uses a fake usage object), so it's
free and deterministic. Checks two things:

1. Storage + read-back: log a turn's usage, then usage_today() reflects it (delta-based, so reruns
   don't break the assertion).
2. RLS lockdown (adversarial, same spirit as smoke_test_postgrest.py): after an admin-written
   usage row exists for the demo user, that same user's JWT reading usage_events via the Data API
   gets NOTHING back - the table is system-only, not user-readable.

Run with: uv run python -m scripts.test_usage_logging
"""

from types import SimpleNamespace

import httpx

from app.config import settings
from app.services import postgrest_client, usage

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


def fake_usage(inp, out, cache_read=0, cache_create=0):
    # Mirrors the fields the accumulator reads off a real anthropic response.usage.
    return SimpleNamespace(
        input_tokens=inp,
        output_tokens=out,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_create,
    )


def main():
    user_id = settings.demo_user_id

    # 1. Storage + read-back --------------------------------------------------------------------
    before = usage.usage_today(user_id)

    acc = usage.UsageAccumulator()
    acc.add(fake_usage(800, 120))   # round-trip 1 (e.g. a tool call)
    acc.add(fake_usage(950, 210))   # round-trip 2 (final answer)
    assert acc.api_calls == 2, acc
    assert acc.input_tokens == 1750 and acc.output_tokens == 330, acc

    usage.log_usage(user_id, "claude-sonnet-5", acc)

    after = usage.usage_today(user_id)
    assert after["input_tokens"] - before["input_tokens"] == 1750, (before, after)
    assert after["output_tokens"] - before["output_tokens"] == 330, (before, after)
    assert after["api_calls"] - before["api_calls"] == 2, (before, after)
    print(f"OK - usage_today rose by the logged turn "
          f"(+1750 in / +330 out / +2 calls). Today so far: {after}")

    # log_usage with an empty accumulator is a no-op (nothing spent -> no row).
    empty_before = usage.usage_today(user_id)
    usage.log_usage(user_id, "claude-sonnet-5", usage.UsageAccumulator())
    assert usage.usage_today(user_id) == empty_before
    print("OK - a zero-spend turn writes no row.")

    # 2. RLS lockdown (adversarial) -------------------------------------------------------------
    # A user JWT reading usage_events must get nothing. Depending on Supabase's default table
    # grants that surfaces as either an empty result (RLS filtered every row) or a permission
    # error (no grant at all) - both prove the table is not user-readable.
    jwt = sign_in()
    try:
        rows = postgrest_client.select("usage_events", jwt, user_id=f"eq.{user_id}")
    except httpx.HTTPStatusError as e:
        assert e.response.status_code in (401, 403), e
        print(f"OK - a user JWT is denied usage_events entirely ({e.response.status_code}); RLS lockdown holds.")
    else:
        assert rows == [], f"usage_events must be unreadable via a user JWT, got {len(rows)} rows"
        print("OK - the demo user's own JWT reads back 0 usage_events rows (RLS lockdown holds).")


if __name__ == "__main__":
    main()
