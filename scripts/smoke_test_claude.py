"""Smoke test: confirms the Claude API key works and the tool-calling round trip functions.

Deliberately minimal - a mock tool returning fake data, not the real finance tools - just
proving the mechanism (Claude asks to call a tool, we run it, we send the result back, Claude
gives a final answer) before Day 4/5 build real tools on the same manual-loop pattern.

Run with: uv run python -m scripts.smoke_test_claude
"""

import anthropic

from app.config import settings

MODEL = "claude-sonnet-5"

TOOLS = [
    {
        "name": "get_demo_balance",
        "description": "Returns the user's current account balance in USD.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    }
]


def get_demo_balance() -> dict:
    # Fake implementation - Day 4 replaces this with a real query against `transactions`.
    return {"balance_usd": 1523.47}


def main():
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    messages = [{"role": "user", "content": "What's my current account balance?"}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        tools=TOOLS,
        messages=messages,
    )

    print(f"stop_reason: {response.stop_reason}")
    for block in response.content:
        print(f"  {block.type}: {block}")

    if response.stop_reason != "tool_use":
        print("\nModel didn't call the tool - smoke test inconclusive.")
        return

    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    print(f"\nModel wants to call: {tool_use_block.name}({tool_use_block.input})")

    result = get_demo_balance()

    messages.append({"role": "assistant", "content": response.content})
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_block.id,
                    "content": str(result),
                }
            ],
        }
    )

    final_response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        tools=TOOLS,
        messages=messages,
    )

    print("\nFinal model response:")
    for block in final_response.content:
        if block.type == "text":
            print(f"  {block.text}")


if __name__ == "__main__":
    main()
