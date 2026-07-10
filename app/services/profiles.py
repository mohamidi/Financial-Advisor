"""Service seam for the profiles table. Nothing above it (the deterministic onboarding flow, the
save_profile update tool) touches the Data API client directly - same principle as the finance
tools going through services/transactions.py (see CLAUDE.md architectural constraints). user_id
is injected here from the authenticated context, never trusted from a caller or the model.
"""

from app.services import postgrest_client


def save_profile(user_id: str, jwt: str, fields: dict) -> dict:
    """Upsert the given user's profile. `fields` holds the profile columns to write, WITHOUT
    user_id - that's supplied here from the verified request identity."""
    return postgrest_client.upsert("profiles", jwt, {"user_id": user_id, **fields})


def get_profile(user_id: str, jwt: str) -> dict | None:
    rows = postgrest_client.select("profiles", jwt, user_id=f"eq.{user_id}")
    return rows[0] if rows else None
