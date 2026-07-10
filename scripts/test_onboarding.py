"""Deterministic terminal harness for the hardcoded onboarding questionnaire (app/onboarding.py).

No Claude in the intake path - fixed questions, validated answers, one write at the end. Signs in
as the demo user for a real JWT so the write goes through the real per-user Data API path (RLS
enforced), exactly as the Day 6 web route will. Re-prompts on invalid input.

Run with: uv run python -m scripts.test_onboarding
"""

import httpx

from app.config import settings
from app.onboarding import QUESTIONS, AnswerError, save_onboarding_profile

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


def ask(question) -> object:
    while True:
        raw = input(f"{question.prompt}\n> ")
        try:
            return question.parse(raw)
        except AnswerError as exc:
            print(f"  ({exc})")


def main():
    jwt = sign_in()
    user_id = settings.demo_user_id
    print("Let's set up your financial profile.\n")

    answers = {q.field: ask(q) for q in QUESTIONS}
    saved = save_onboarding_profile(user_id, jwt, answers)

    print("\nSaved your profile:")
    print(f"  Age: {saved['age']}, {saved['marital_status']}")
    print(f"  Monthly income: ${float(saved['monthly_income']):,.2f}")
    print(f"  Dependents: {saved['dependents']}")
    print(f"  Existing debt: ${float(saved['existing_debt']):,.2f}")
    print(f"  Risk tolerance: {saved['risk_tolerance']}")
    if saved.get("notes"):
        print(f"  Notes: {saved['notes']}")
    print('\nYou\'re all set - you can now ask things like "can I afford X?"')


if __name__ == "__main__":
    main()
