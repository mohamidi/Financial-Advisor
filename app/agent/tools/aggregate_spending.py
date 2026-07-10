"""aggregate_spending tool - totals the user's spending over an optional date range/category.

Reads only through app/services/transactions.py, never a data source directly (CLAUDE.md). user_id
is accepted for a uniform executor signature across tools even though RLS + the JWT already scope
the read to the caller.
"""

from datetime import date

from app.services import transactions

AGGREGATE_SPENDING_SCHEMA = {
    "name": "aggregate_spending",
    "description": (
        "Totals the user's spending over an optional date range and/or a single category, and "
        "returns the grand total plus a per-category breakdown. Dates are ISO (YYYY-MM-DD), "
        "inclusive; omit them to cover all available history. Every amount is money the user "
        "spent (an outflow)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": "ISO date (YYYY-MM-DD), inclusive lower bound. Omit for no lower bound.",
            },
            "end_date": {
                "type": "string",
                "description": "ISO date (YYYY-MM-DD), inclusive upper bound. Omit for no upper bound.",
            },
            "category": {
                "type": "string",
                "description": "Restrict to one spending category, e.g. 'Groceries'. Omit for all.",
            },
        },
        "required": [],
    },
}


def run_aggregate_spending(user_id: str, jwt: str, tool_input: dict) -> dict:
    start = date.fromisoformat(tool_input["start_date"]) if tool_input.get("start_date") else None
    end = date.fromisoformat(tool_input["end_date"]) if tool_input.get("end_date") else None
    category = tool_input.get("category")

    txns = transactions.get_transactions(jwt, start=start, end=end, category=category)
    by_category = transactions.spending_by_category(txns)
    total = transactions.total_spend(txns)

    return {
        "transaction_count": len(txns),
        "total_spent": f"{total:.2f}",
        "by_category": {k: f"{v:.2f}" for k, v in by_category.items()},
        "window": {
            "start": tool_input.get("start_date"),
            "end": tool_input.get("end_date"),
            "category": category,
        },
    }
