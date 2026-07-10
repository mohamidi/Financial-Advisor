"""Exercises the /chat endpoint end-to-end through the real HTTP layer (FastAPI TestClient):
real JWT verification, real per-user data, real advisor loop. Confirms the stateless design -
the client passes plain-text history back each turn and the server rebuilds context from it.

Run with: uv run python -m scripts.test_chat_endpoint
"""

import httpx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
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
    profiles.save_profile(settings.demo_user_id, jwt, {
        "age": 34, "marital_status": "married", "monthly_income": "6800.00",
        "existing_debt": "15000.00", "risk_tolerance": "medium", "dependents": 2, "notes": "",
    })
    client = TestClient(app)
    auth = {"Authorization": f"Bearer {jwt}"}

    # 401 when unauthenticated.
    r = client.post("/chat", json={"message": "hi"})
    assert r.status_code == 401, r.status_code
    print("OK - unauthenticated request rejected (401).")

    # 400 on empty message.
    r = client.post("/chat", headers=auth, json={"message": "   "})
    assert r.status_code == 400, r.status_code
    print("OK - empty message rejected (400).")

    # Turn 1.
    r = client.post("/chat", headers=auth, json={"history": [], "message": "Can I afford a $2000 trip?"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["reply"].strip()
    assert len(data["history"]) == 2
    print(f"\nTurn 1 -> {data['reply'][:220]}...")

    # Turn 2 - client sends back the history it got; server rebuilds context statelessly.
    r = client.post("/chat", headers=auth, json={"history": data["history"], "message": "What about $9000 instead?"})
    assert r.status_code == 200, r.text
    data2 = r.json()
    assert len(data2["history"]) == 4
    print(f"\nTurn 2 -> {data2['reply'][:220]}...")

    print("\nOK - /chat works end-to-end: auth enforced, stateless history round-trips, advisor replies.")


if __name__ == "__main__":
    main()
