"""Manual Claude tool-calling loop, shared by the onboarding flow (Day 3) and later the real
finance/verdict tools (Day 4/5). Deliberately manual (not the SDK's beta Tool Runner) for
fine-grained control needed later by the eval harness - this generalizes the exact round-trip
proven in scripts/smoke_test_claude.py to handle multiple tool calls and multiple turns.
"""

import anthropic

MODEL = "claude-sonnet-5"


def run_agent_turn(
    client: anthropic.Anthropic,
    messages: list,
    tools: list,
    tool_executors: dict,
    system: str,
) -> list:
    """Sends `messages` to Claude, executing any tool calls, until Claude replies with text.

    tool_executors maps tool name -> callable(tool_input: dict) -> Any. Appends everything that
    happened (tool_use/tool_result pairs, final assistant text) onto `messages` and returns it,
    so the caller can pass the same list straight back in on the next turn.
    """
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return messages

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            executor = tool_executors[block.name]
            result = executor(block.input)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": str(result)}
            )
        messages.append({"role": "user", "content": tool_results})


def last_text(messages: list) -> str:
    """Extracts the text of the most recent assistant message, for printing to the user."""
    for message in reversed(messages):
        if message["role"] != "assistant":
            continue
        return "".join(block.text for block in message["content"] if block.type == "text")
    return ""
