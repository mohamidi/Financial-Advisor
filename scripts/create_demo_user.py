"""Creates (or finds, if it already exists) a persistent demo Supabase Auth user.

This is a real Auth identity, separate from the project owner's own account, so that
auth.uid()-scoped Row Level Security can be tested against realistic seeded data without
touching the owner's real account. Safe to re-run - it's idempotent.

Run with: uv run python -m scripts.create_demo_user
(not `python scripts/create_demo_user.py` directly - that puts scripts/ rather than the project
root on sys.path, and `app` won't be importable)
"""

import json
import urllib.error
import urllib.request

from app.config import settings

DEMO_EMAIL = "demo@financial-advisor.test"
DEMO_PASSWORD = "demo-user-not-a-real-password-123"


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


def find_existing_demo_user() -> dict | None:
    result = _request("GET", "/auth/v1/admin/users")
    for user in result.get("users", []):
        if user.get("email") == DEMO_EMAIL:
            return user
    return None


def main():
    existing = find_existing_demo_user()
    if existing:
        print(f"Demo user already exists: {existing['id']} ({DEMO_EMAIL})")
        return existing["id"]

    result = _request(
        "POST",
        "/auth/v1/admin/users",
        {"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "email_confirm": True},
    )
    if "_error_status" in result:
        raise RuntimeError(f"Failed to create demo user: {result}")

    print(f"Created demo user: {result['id']} ({DEMO_EMAIL})")
    print("Add this to .env as DEMO_USER_ID:")
    print(f"  DEMO_USER_ID={result['id']}")
    return result["id"]


if __name__ == "__main__":
    main()
