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
from datetime import timedelta

from sqlalchemy import func, select

from app.config import settings
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

    ts is stored naive-but-UTC (models.utcnow). We bound on `ts >= midnight-UTC-today` rather than
    `func.date(ts) == today`: a ts is never in the future, so the range means exactly "today", and
    unlike func.date() it's sargable - Postgres can use the ts index instead of computing a function
    over every candidate row. Same range-predicate shape the rate limit uses.
    """
    start_of_day = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)  # midnight UTC today, naive
    with SessionLocal() as db:
        row = db.execute(
            select(
                func.coalesce(func.sum(UsageEvent.input_tokens), 0),
                func.coalesce(func.sum(UsageEvent.output_tokens), 0),
                func.coalesce(func.sum(UsageEvent.api_calls), 0),
            ).where(
                UsageEvent.user_id == user_id,
                UsageEvent.ts >= start_of_day,
            )
        ).one()
    return {"input_tokens": int(row[0]), "output_tokens": int(row[1]), "api_calls": int(row[2])}


def over_daily_budget(user_id: str, limit_tokens: int | None = None) -> tuple[bool, int, int]:
    """(exceeded, tokens_used_today, limit) for the per-user daily token cap.

    Sums today's input+output tokens against the limit (settings.daily_token_budget_per_user unless
    overridden - the override exists for tests). Checked BEFORE each call, and usage_today only
    reflects COMPLETED turns, so a single in-flight turn can tip a user just over the line and it's
    the NEXT call that gets blocked. That's the right behavior for a soft daily cap: never truncate a
    reply mid-generation, just refuse to start a new turn once the day's budget is spent.
    """
    limit = settings.daily_token_budget_per_user if limit_tokens is None else limit_tokens
    totals = usage_today(user_id)
    used = totals["input_tokens"] + totals["output_tokens"]
    return used >= limit, used, limit


def messages_last_hour(user_id: str) -> int:
    """Count of completed turns (usage_events rows) for a user in the trailing hour. Reusing the
    Day 7 table means the rate limit needs no separate counter - the same COUNT works across every
    stateless app instance, which an in-process limiter could not."""
    cutoff = utcnow() - timedelta(hours=1)
    with SessionLocal() as db:
        return db.execute(
            select(func.count())
            .select_from(UsageEvent)
            .where(UsageEvent.user_id == user_id, UsageEvent.ts >= cutoff)
        ).scalar_one()


def over_rate_limit(user_id: str, limit: int | None = None) -> tuple[bool, int, int]:
    """(exceeded, messages_in_last_hour, limit) for the per-user messages/hour cap. Same soft-boundary
    behavior as the budget check: the in-flight turn isn't counted until it completes, so this blocks
    starting a NEW turn once the trailing-hour count has reached the limit."""
    limit = settings.max_messages_per_hour_per_user if limit is None else limit
    count = messages_last_hour(user_id)
    return count >= limit, count, limit
