"""Per-request client for Supabase's Data API (PostgREST) - the path for queries scoped to a
specific logged-in user, so Row Level Security actually applies (see CLAUDE.md's "Data access
pattern correction"). Never share one of these calls' state across users: every function here
takes the caller's JWT explicitly and builds a fresh request each time, so there's no client
object sitting around that could carry one user's auth context into another user's request.
"""

import httpx

from app.config import settings

_BASE_URL = f"{settings.supabase_url}/rest/v1"


def _headers(jwt: str, prefer: str | None = None) -> dict:
    headers = {
        "apikey": settings.supabase_publishable_key,
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def select(table: str, jwt: str, **filters: str) -> list[dict]:
    """GET rows from `table` visible to the JWT's user.

    Filters use PostgREST operator syntax, e.g. select("profiles", jwt, user_id="eq.<uuid>").
    """
    resp = httpx.get(f"{_BASE_URL}/{table}", headers=_headers(jwt), params=dict(filters))
    resp.raise_for_status()
    return resp.json()


def upsert(table: str, jwt: str, data: dict) -> dict:
    """INSERT `data`, or UPDATE the existing row if its primary key already exists."""
    resp = httpx.post(
        f"{_BASE_URL}/{table}",
        headers=_headers(jwt, prefer="resolution=merge-duplicates,return=representation"),
        json=data,
    )
    resp.raise_for_status()
    return resp.json()[0]
