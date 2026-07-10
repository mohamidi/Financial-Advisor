"""Smoke test: confirms the per-user PostgREST client (app/services/postgrest_client.py) works
against the real Supabase project, that Row Level Security lets an authenticated user write and
read their own `profiles` row, and - the property RLS actually exists for - that it blocks that
same user from writing or reading a row stamped with someone else's user_id.

Signs in as the demo user (real Supabase Auth identity, see scripts/create_demo_user.py) to get
a real JWT, then upserts and reads back a profile using ONLY that JWT - proving the Data API
path works end-to-end before Day 3 builds the real save_profile tool on top of it.

Run with: uv run python -m scripts.smoke_test_postgrest
"""

import httpx

from app.config import settings
from app.services import postgrest_client

DEMO_EMAIL = "demo@financial-advisor.test"
DEMO_PASSWORD = "demo-user-not-a-real-password-123"

# Not a real user - just needs to be a UUID that isn't the demo user's, to prove the demo user's
# JWT can't touch a row stamped with someone else's id.
OTHER_USER_ID = "11111111-1111-1111-1111-111111111111"


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
    print("Signed in as demo user, got JWT.")

    profile = postgrest_client.upsert(
        "profiles",
        jwt,
        {
            "user_id": settings.demo_user_id,
            "age": 29,
            "marital_status": "single",
            "monthly_income": "5200.00",
            "dependents": 0,
            "existing_debt": "8000.00",
            "risk_tolerance": "medium",
            "notes": "smoke test row",
        },
    )
    print(f"Upserted profile: {profile}")

    rows = postgrest_client.select("profiles", jwt, user_id=f"eq.{settings.demo_user_id}")
    print(f"Read back: {rows}")

    assert len(rows) == 1, "expected exactly one profile row for the demo user"
    assert rows[0]["monthly_income"] == 5200.0
    print("OK - per-user PostgREST client works, RLS allows the demo user their own row.\n")

    try:
        postgrest_client.upsert(
            "profiles",
            jwt,
            {
                "user_id": OTHER_USER_ID,
                "age": 40,
                "marital_status": "married",
                "monthly_income": "9999.00",
                "risk_tolerance": "high",
            },
        )
        raise AssertionError("demo user's JWT was able to write another user's profile row")
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 403, f"expected 403, got {exc.response.status_code}"
        print("OK - writing another user's row was blocked (403, RLS policy violation).")

    other_rows = postgrest_client.select("profiles", jwt, user_id=f"eq.{OTHER_USER_ID}")
    assert other_rows == [], "demo user's JWT could read another user's row"
    print("OK - reading another user's row returned nothing (RLS filters it out).")

    print("\nAll checks passed - isolation between users is enforced by the database, not just app code.")


if __name__ == "__main__":
    main()
