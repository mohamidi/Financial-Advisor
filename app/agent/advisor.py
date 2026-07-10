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


def build_executors(user_id: str, jwt: str) -> dict:
    """Map of tool name -> callable(tool_input) -> result, bound to this user's identity + JWT.

    Built fresh per request (never a shared global) so one user's identity can never leak into
    another's tool calls - the same per-request-scoping discipline as the PostgREST client.
    """
    return {
        "get_affordability_verdict": lambda ti: verdict.run_get_affordability_verdict(user_id, jwt, ti),
        "aggregate_spending": lambda ti: aggregate_spending.run_aggregate_spending(user_id, jwt, ti),
        "compute_discretionary_balance": lambda ti: compute_discretionary_balance.run_compute_discretionary_balance(user_id, jwt, ti),
        "project_cash_flow": lambda ti: project_cash_flow.run_project_cash_flow(user_id, jwt, ti),
        "save_profile": lambda ti: save_profile.run_save_profile(user_id, jwt, ti),
    }
