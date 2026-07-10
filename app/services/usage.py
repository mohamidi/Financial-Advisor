"""Per-user token-usage accounting - the Day 7 foundation for Day 8's daily-budget check.

Deliberately written on the ADMIN (DATABASE_URL) connection, not the user's JWT via the Data API.
This is a considered exception to the "per-user data goes through the Data API" rule, not a
violation of it: a usage counter is SYSTEM telemetry that gates spending on the owner's API key.
The user must NOT be able to write, edit, or delete it (that would let them escape a quota), and
they don't manage it the way they manage their profile. So it's an admin/system write, exactly the
case DATABASE_URL is for. The table is RLS-locked with no authenticated policy (create_tables.py),
so the user's JWT can't reach it through the Data API either.
"""

from dataclasses import dataclass

from sqlalchemy import func, select

from app.db.database import SessionLocal
from app.db.models import UsageEvent, utcnow


@dataclass
class UsageAccumulator:
    """Sums the token spend of one user message-turn across its (possibly several) API calls.

    Passed to run_agent_turn as the on_usage callback; .add() is called once per round-trip. Kept
    here (not in the orchestrator) so the orchestrator stays free of any storage concern.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    api_calls: int = 0

    def add(self, usage) -> None:
        # getattr with defaults: cache fields are absent unless caching is on (not yet), and this
        # keeps the accumulator decoupled from the exact anthropic usage shape.
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.cache_creation_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.api_calls += 1


def log_usage(user_id: str, model: str, acc: UsageAccumulator) -> None:
    """Persist one row for a completed message-turn. No-op if nothing was spent (0 API calls)."""
    if acc.api_calls == 0:
        return
    with SessionLocal() as db:
        db.add(
            UsageEvent(
                user_id=user_id,
                model=model,
                input_tokens=acc.input_tokens,
                output_tokens=acc.output_tokens,
                cache_read_tokens=acc.cache_read_tokens,
                cache_creation_tokens=acc.cache_creation_tokens,
                api_calls=acc.api_calls,
            )
        )
        db.commit()


def usage_today(user_id: str) -> dict:
    """Today's (UTC) token totals for a user - the read Day 8's pre-call budget check builds on.

    ts is stored naive-but-UTC (models.utcnow), so comparing its calendar date to the UTC 'today'
    keeps the day boundary consistent regardless of server timezone.
    """
    today_utc = utcnow().date()  # utcnow() is naive-but-UTC, so its .date() is the UTC calendar date
    with SessionLocal() as db:
        row = db.execute(
            select(
                func.coalesce(func.sum(UsageEvent.input_tokens), 0),
                func.coalesce(func.sum(UsageEvent.output_tokens), 0),
                func.coalesce(func.sum(UsageEvent.api_calls), 0),
            ).where(
                UsageEvent.user_id == user_id,
                func.date(UsageEvent.ts) == today_utc,
            )
        ).one()
    return {"input_tokens": int(row[0]), "output_tokens": int(row[1]), "api_calls": int(row[2])}
