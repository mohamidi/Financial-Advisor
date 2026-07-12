"""Manual Claude tool-calling loop, shared by the onboarding flow (Day 3) and later the real
finance/verdict tools (Day 4/5). Deliberately manual (not the SDK's beta Tool Runner) for
fine-grained control needed later by the eval harness - this generalizes the exact round-trip
proven in scripts/smoke_test_claude.py to handle multiple tool calls and multiple turns.
"""

import anthropic

MODEL = "claude-sonnet-5"

# Hard cap on tool round-trips per user message. Each round is another Claude API call, so an
# unbounded loop is unbounded spend on the owner's API key - this bounds a single message to at
# most MAX_TOOL_ROUNDS + 1 calls. Normal flows use 1-3; 8 is a generous ceiling that stops a
# runaway (buggy tool, adversarial prompt) without cutting off legitimate multi-step questions.
MAX_TOOL_ROUNDS = 8


def run_agent_turn(
    client: anthropic.Anthropic,
    messages: list,
    tools: list,
    tool_executors: dict,
    system: str,
    max_tool_rounds: int = MAX_TOOL_ROUNDS,
    on_usage=None,
) -> list:
    """Sends `messages` to Claude, executing any tool calls, until Claude replies with text.

    tool_executors maps tool name -> callable(tool_input: dict) -> Any. Appends everything that
    happened (tool_use/tool_result pairs, final assistant text) onto `messages` and returns it,
    so the caller can pass the same list straight back in on the next turn. Bounded to
    max_tool_rounds tool round-trips; on the last allowed call, tools are disabled so the model
    must produce a text answer instead of spinning up another round.

    on_usage, if given, is called with each response's `.usage` object (once per API round-trip),
    so the caller can accumulate per-user token spend (see app/services/usage.py). The orchestrator
    itself stays free of any storage concern - it just hands the usage out.
    """
    for round_num in range(max_tool_rounds + 1):
        force_final = round_num == max_tool_rounds
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=tools,
            tool_choice={"type": "none"} if force_final else {"type": "auto"},
            messages=messages,
        )
        if on_usage is not None:
            on_usage(response.usage)
        messages.append({"role": "assistant", "content": response.content})

        if force_final or response.stop_reason != "tool_use":
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

    return messages


def stream_agent_turn(
    client: anthropic.Anthropic,
    messages: list,
    tools: list,
    tool_executors: dict,
    system: str,
    max_tool_rounds: int = MAX_TOOL_ROUNDS,
    on_usage=None,
):
    """Streaming twin of run_agent_turn, for SSE. Same tool-round-trip loop and the same
    max_tool_rounds/on_usage contract, but each round uses the streaming API and yields events as
    they happen instead of returning only once a full reply is ready:
      {"type": "text", "text": "..."}  - a chunk of assistant text, in generation order
      {"type": "tool", "name": "..."}  - a tool the model is about to call (round has one per tool)

    Mutates `messages` in place exactly like run_agent_turn (appends every assistant/tool_result
    turn), so callers should exhaust this generator with a `for` loop and then read `messages` /
    call last_text(messages) - there's no separate return value.
    """
    for round_num in range(max_tool_rounds + 1):
        force_final = round_num == max_tool_rounds
        with client.messages.stream(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=tools,
            tool_choice={"type": "none"} if force_final else {"type": "auto"},
            messages=messages,
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    yield {"type": "text", "text": event.delta.text}
            response = stream.get_final_message()

        if on_usage is not None:
            on_usage(response.usage)
        messages.append({"role": "assistant", "content": response.content})

        if force_final or response.stop_reason != "tool_use":
            return

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            yield {"type": "tool", "name": block.name}
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
