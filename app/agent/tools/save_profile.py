"""The save_profile tool - lets the agent UPDATE a user's profile mid-conversation (e.g. "I just
paid off that loan", "my income went up"). Initial intake is NOT done here - that's the
deterministic questionnaire in app/onboarding.py. This tool is for later corrections/changes
during normal chat.

user_id is injected from the authenticated request context (the caller's verified JWT), never
taken from the model's tool-call input. The model should never be trusted to state whose profile
it's writing - identity is an app-enforced fact, not something an LLM gets to assert, the same
principle that keeps verdict logic deterministic instead of model discretion (see CLAUDE.md).

NOTE for Day 5: the current upsert path requires the full required set (age/marital_status/
monthly_income/risk_tolerance) on every call, since those columns are NOT NULL without a DB
default and PostgreSQL's INSERT ... ON CONFLICT builds the INSERT row before resolving to an
UPDATE. A true single-field update ("just change my income") will need a PostgREST PATCH (UPDATE
only) or read-modify-write - wire that up when the update tool is actually driven by the chat loop.
"""

from app.services import profiles

SAVE_PROFILE_SCHEMA = {
    "name": "save_profile",
    "description": (
        "Updates the user's saved financial profile when they tell you something has changed "
        "(income changed, paid off debt, etc.) or want to correct a value. The initial profile is "
        "collected during onboarding, not here. Provide age, marital status, monthly income, and "
        "risk tolerance (the current values, with the changed field updated); dependents, existing "
        "debt, and notes are optional."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "age": {"type": "integer", "description": "The user's age in years."},
            "marital_status": {"type": "string", "enum": ["single", "married"]},
            "monthly_income": {
                "type": "number",
                "description": "Net (take-home) monthly income in USD.",
            },
            "dependents": {
                "type": "integer",
                "description": "Number of financial dependents. Defaults to 0 if not mentioned.",
            },
            "existing_debt": {
                "type": "number",
                "description": (
                    "Total existing debt balance across all sources, in USD. Defaults to 0 if "
                    "not mentioned."
                ),
            },
            "risk_tolerance": {"type": "string", "enum": ["low", "medium", "high"]},
            "notes": {
                "type": "string",
                "description": "Any other relevant context the user volunteered.",
            },
        },
        "required": ["age", "marital_status", "monthly_income", "risk_tolerance"],
    },
}


def run_save_profile(user_id: str, jwt: str, tool_input: dict) -> dict:
    return profiles.save_profile(user_id, jwt, tool_input)
