"""Interactive terminal advisor - talk to the full agent (all five tools, real data, real verdict).

Signs in as the demo user, hydrates their profile into the advisor's context, and runs a terminal
chat loop. No chat UI yet - that's Day 6, which drives the same app/agent/advisor.py assembly.

Run with: uv run python -m scripts.test_advisor   (type 'quit' to exit)
Try: "can I afford a $3000 trip?", "can I afford a Peloton?", "how much did I spend on dining?",
     "I just took on $2000 more in debt, add that".
"""

import anthropic
import httpx

from app.agent.advisor import ADVISOR_TOOLS, build_executors
from app.agent.orchestrator import last_text, run_agent_turn
from app.agent.prompts import build_advisor_system_prompt
from app.config import settings
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
    user_id = settings.demo_user_id
    profile = profiles.get_profile(user_id, jwt)
    system = build_advisor_system_prompt(profile)
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    executors = build_executors(user_id, jwt)

    print("Advisor ready. Ask me things like \"can I afford a $3000 trip?\". Type 'quit' to exit.\n")
    messages = []
    while True:
        user_text = input("You: ").strip()
        if user_text.lower() in ("quit", "exit"):
            break
        messages.append({"role": "user", "content": user_text})
        messages = run_agent_turn(client, messages, ADVISOR_TOOLS, executors, system)
        print(f"Advisor: {last_text(messages)}\n")


if __name__ == "__main__":
    main()
