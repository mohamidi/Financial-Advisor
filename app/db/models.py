import uuid
from datetime import date as date_type
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Numeric, String
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
