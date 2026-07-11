"""Exercises the web onboarding endpoints end-to-end through the real HTTP layer (no Claude):
GET /onboarding/questions, POST /onboarding (validation + save), GET /profile, and auth enforcement.
Restores the demo profile to the shared baseline at the end so other scripts keep a known profile.

Run with: uv run python -m scripts.test_onboarding_endpoint
"""

import httpx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.onboarding import QUESTIONS
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
    client = TestClient(app)
    auth = {"Authorization": f"Bearer {jwt}"}

    # Auth enforced.
    assert client.get("/profile").status_code == 401
    assert client.post("/onboarding", json={"answers": {}}).status_code == 401
    print("OK - onboarding endpoints reject unauthenticated requests (401).")

    # Questions come from the server, matching app/onboarding.py exactly.
    r = client.get("/onboarding/questions", headers=auth)
    assert r.status_code == 200, r.text
    fields = [q["field"] for q in r.json()["questions"]]
    assert fields == [q.field for q in QUESTIONS], fields
    print(f"OK - GET /onboarding/questions returns {len(fields)} questions: {fields}")

    # Invalid answers -> 422 with per-field errors, no write.
    r = client.post("/onboarding", headers=auth, json={"answers": {
        "age": "abc", "marital_status": "unknown", "monthly_income": "not-money",
        "risk_tolerance": "high", "dependents": "", "existing_debt": "", "notes": "",
    }})
    assert r.status_code == 422, r.text
    errors = r.json()["detail"]["errors"]
    assert set(errors) == {"age", "marital_status", "monthly_income"}, errors
    print(f"OK - invalid answers -> 422 with field errors: {sorted(errors)}")

    # Valid answers -> 200, saved with money normalized and blank optionals defaulted.
    r = client.post("/onboarding", headers=auth, json={"answers": {
        "age": "40", "marital_status": "single", "monthly_income": "5000",
        "risk_tolerance": "high", "dependents": "", "existing_debt": "", "notes": "  ",
    }})
    assert r.status_code == 200, r.text
    saved = r.json()["profile"]
    assert saved["age"] == 40 and saved["marital_status"] == "single"
    # PostgREST returns numeric columns as JSON floats (same reason transactions.py does
    # Decimal(str(...))); the stored value is exact, so compare numerically.
    assert float(saved["monthly_income"]) == 5000.0, saved["monthly_income"]
    assert saved["dependents"] == 0 and float(saved["existing_debt"]) == 0.0, saved
    assert saved["risk_tolerance"] == "high"
    print("OK - valid answers saved (money -> 2dp, blank optionals defaulted).")

    # GET /profile reflects the write.
    r = client.get("/profile", headers=auth)
    assert r.status_code == 200 and r.json()["profile"]["age"] == 40
    print("OK - GET /profile returns the saved profile.")

    # Over-long notes rejected.
    r = client.post("/onboarding", headers=auth, json={"answers": {
        "age": "40", "marital_status": "single", "monthly_income": "5000",
        "risk_tolerance": "high", "dependents": "0", "existing_debt": "0", "notes": "x" * 501,
    }})
    assert r.status_code == 422 and "notes" in r.json()["detail"]["errors"]
    print("OK - over-long notes rejected (422).")

    # Restore the shared baseline for other scripts.
    profiles.save_profile(settings.demo_user_id, jwt, BASELINE)
    print("OK - demo profile restored to baseline.")


if __name__ == "__main__":
    main()
