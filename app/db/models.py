import uuid
from datetime import date as date_type
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def utcnow() -> datetime:
    """Naive datetime representing the current UTC instant (see CLAUDE.md for why naive-but-UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Transaction(Base):
    """A single spending transaction, from either the synthetic dataset or (Phase 2) Plaid.

    Finance tools (Day 4) must only read this via app/services/transactions.py, never query
    this model directly - see CLAUDE.md's architectural constraints.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("source IN ('synthetic', 'plaid')", name="transactions_source_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # References auth.users.id (Supabase-managed, not declared here - see scripts/create_tables.py
    # for the actual FK constraint, added via raw SQL since SQLAlchemy can't resolve DDL
    # dependencies against a table it doesn't know about).
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    merchant_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, default="synthetic")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class UsageEvent(Base):
    """One row per user message-turn, summarizing the Claude token spend it cost (a turn can be
    several API round-trips when tools are called - they're summed into one row here).

    System telemetry, NOT user data: written on the ADMIN (DATABASE_URL) connection, never the
    user's JWT, so a user can't write or delete their own counter to escape a budget. RLS is
    enabled with NO authenticated policy (see scripts/create_tables.py), which is load-bearing:
    Supabase's Data API auto-exposes every public table, so without a lockdown a user could read
    everyone's usage via the Data API with their own JWT. Day 8's daily-budget check reads this
    back (via app/services/usage.py) before each call.
    """

    __tablename__ = "usage_events"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # References auth.users.id (FK added via raw SQL in scripts/create_tables.py, same pattern as
    # the other tables).
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, server_default=text("now()"), index=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    # Cache token counts carried now (cheap) so the planned system-prompt prompt-caching optimization
    # (CLAUDE.md "Token-cost controls") is observable the day it lands, without a schema change.
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    cache_creation_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    # How many Claude API round-trips this turn took (1 = plain answer; >1 = tool calls).
    api_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))


class Profile(Base):
    """A user's self-reported financial profile, built via the Day 3 onboarding interview.

    Only holds facts a bank connection can't supply (age, marital status, dependents, risk
    tolerance) plus two self-reported numbers (income, existing debt) that Plaid's Income and
    Liabilities products could eventually supply directly (Phase 2 - not built). Fixed monthly
    costs are deliberately NOT stored here - Day 4 computes them on demand from recurring
    transactions instead of asking the user to estimate six numbers from memory.
    """

    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("marital_status IN ('single', 'married')", name="profiles_marital_status_check"),
        CheckConstraint(
            "risk_tolerance IN ('low', 'medium', 'high')", name="profiles_risk_tolerance_check"
        ),
    )

    # One profile per user - user_id is the primary key, not a separate id + unique column.
    # References auth.users.id (added via raw SQL in scripts/create_tables.py, same pattern as
    # Transaction.user_id).
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    marital_status: Mapped[str] = mapped_column(String, nullable=False)
    monthly_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    dependents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    existing_debt: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0, server_default=text("0")
    )
    risk_tolerance: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    # server_default (not just default=) because rows can be written via the Data API/PostgREST
    # (save_profile, on behalf of a real user) as well as via SQLAlchemy - a Python-side default
    # only fires when SQLAlchemy itself builds the INSERT, so the database needs its own default
    # too. updated_at also gets a trigger (see scripts/create_tables.py) since PostgREST UPDATEs
    # bypass SQLAlchemy's onupdate= the same way.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, server_default=text("now()")
    )
