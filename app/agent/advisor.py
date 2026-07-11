"""Assembles the advisor agent: the tool set it can call, and a per-request executor map binding
each tool to the logged-in user (user_id + their JWT). Both the interactive test script now and the
Day 6 chat endpoint later build the agent from here, so the wiring lives in one place.
"""

from app.agent.tools import (
    aggregate_spending,
    compute_discretionary_balance,
    project_cash_flow,
    save_profile,
    verdict,
)

ADVISOR_TOOLS = [
    verdict.GET_AFFORDABILITY_VERDICT_SCHEMA,
    aggregate_spending.AGGREGATE_SPENDING_SCHEMA,
    compute_discretionary_balance.COMPUTE_DISCRETIONARY_BALANCE_SCHEMA,
    project_cash_flow.PROJECT_CASH_FLOW_SCHEMA,
    save_profile.SAVE_PROFILE_SCHEMA,
]


def build_executors(user_id: str, jwt: str, verdict_sink: list | None = None) -> dict:
    """Map of tool name -> callable(tool_input) -> result, bound to this user's identity + JWT.

    Built fresh per request (never a shared global) so one user's identity can never leak into
    another's tool calls - the same per-request-scoping discipline as the PostgREST client.

    verdict_sink, if given, collects each get_affordability_verdict result so the caller (the /chat
    endpoint) can return the structured verdict to the UI for the verdict card. This is display-only,
    server->browser: the verdict is still recomputed server-side every turn and never trusted back
    from client history, so surfacing it here doesn't weaken the "no client-forged verdict" rule.
    """
    def run_verdict(ti):
        result = verdict.run_get_affordability_verdict(user_id, jwt, ti)
        if verdict_sink is not None:
            verdict_sink.append(result)
        return result

    return {
        "get_affordability_verdict": run_verdict,
        "aggregate_spending": lambda ti: aggregate_spending.run_aggregate_spending(user_id, jwt, ti),
        "compute_discretionary_balance": lambda ti: compute_discretionary_balance.run_compute_discretionary_balance(user_id, jwt, ti),
        "project_cash_flow": lambda ti: project_cash_flow.run_project_cash_flow(user_id, jwt, ti),
        "save_profile": lambda ti: save_profile.run_save_profile(user_id, jwt, ti),
    }
