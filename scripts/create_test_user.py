"""Creates (or finds) a throwaway, PROFILE-LESS Supabase Auth user for browser-testing the web
onboarding flow.

The demo user already has a profile, so logging in as demo routes straight to chat and never shows
onboarding. This mints a separate confirmed account with no profile, so logging in as it in the
browser lands on the onboarding questionnaire. It also clears any profile the account picked up from
a previous test run, so onboarding shows again every time you run this (uses the admin DATABASE_URL
connection - a maintenance op, exactly what that connection is for).

Real self-serve signup (with its email-confirmation UX) is deferred to the UI/UX design pass; this
is just a tester's shortcut until then.

Run with: uv run python -m scripts.create_test_user
"""

import json
import urllib.error
import urllib.request

from sqlalchemy import text

from app.config import settings
from app.db.database import engine

TEST_EMAIL = "onboarding-test@financial-advisor.test"
TEST_PASSWORD = "onboarding-test-not-a-real-password-123"


def _request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{settings.supabase_url}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "apikey": settings.supabase_secret_key,
            "Authorization": f"Bearer {settings.supabase_secret_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"_error_status": exc.code, "_error_body": json.loads(exc.read())}


def find_existing() -> dict | None:
    result = _request("GET", "/auth/v1/admin/users")
    for user in result.get("users", []):
        if user.get("email") == TEST_EMAIL:
            return user
    return None


def clear_profile(user_id: str) -> None:
    """Delete any profile row for this user so onboarding shows on next login. Admin connection
    (bypasses RLS) - a deliberate maintenance action, not a per-user request."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM profiles WHERE user_id = :uid"), {"uid": user_id})


def main():
    existing = find_existing()
    if existing:
        user_id = existing["id"]
        print(f"Test user already exists: {user_id} ({TEST_EMAIL})")
    else:
        result = _request(
            "POST",
            "/auth/v1/admin/users",
            {"email": TEST_EMAIL, "password": TEST_PASSWORD, "email_confirm": True},
        )
        if "_error_status" in result:
            raise RuntimeError(f"Failed to create test user: {result}")
        user_id = result["id"]
        print(f"Created test user: {user_id} ({TEST_EMAIL})")

    clear_profile(user_id)
    print("Cleared its profile (if any) - it will land on onboarding.\n")
    print("Log in to the browser app with:")
    print(f"  email:    {TEST_EMAIL}")
    print(f"  password: {TEST_PASSWORD}")
    print("\nRun this script again anytime to reset it back to the onboarding screen.")


if __name__ == "__main__":
    main()
