"""Internal transaction service - the ONLY path the finance tools read transaction data through
(see CLAUDE.md: finance tools never touch a data source directly). Reads go through the per-user
Data API (JWT + RLS), and every row is mapped into the source-agnostic `Txn` view - so when Plaid
arrives (Phase 2) it's just more rows in the same table tagged source="plaid", with no tool changes.
"""

import calendar
from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal

from app.services import postgrest_client


@dataclass
class Txn:
    """Source-agnostic transaction view the finance tools operate on - never the ORM model or a
    raw PostgREST/Plaid dict. Money is Decimal, never float, for exact aggregation."""

    date: date_type
    merchant_name: str
    category: str
    amount: Decimal
    account_id: str
    source: str


def _to_txn(row: dict) -> Txn:
    return Txn(
        date=date_type.fromisoformat(row["date"]),
        merchant_name=row["merchant_name"],
        category=row["category"],
        # PostgREST returns numeric as a JSON float; str() first so we recover the exact 2-dp
        # value rather than the float's binary approximation.
        amount=Decimal(str(row["amount"])),
        account_id=row["account_id"],
        source=row["source"],
    )


def get_transactions(jwt, start=None, end=None, category=None) -> list[Txn]:
    """All of the caller's transactions (RLS scopes to them via the JWT), optionally filtered by
    date range (inclusive) and/or category.

    Fetches the user's rows once and filters in Python - fine at this scale (hundreds of rows, well
    under PostgREST's default 1000-row cap). If a user ever has thousands, push the date/category
    filters into the PostgREST query instead.
    """
    rows = postgrest_client.select("transactions", jwt)
    txns = [_to_txn(r) for r in rows]
    if start is not None:
        txns = [t for t in txns if t.date >= start]
    if end is not None:
        txns = [t for t in txns if t.date <= end]
    if category is not None:
        txns = [t for t in txns if t.category.lower() == category.lower()]
    return txns


def complete_months(txns) -> list[tuple[int, int]]:
    """The (year, month) pairs fully covered by the data window - the whole calendar month falls
    between the earliest and latest transaction. Partial months at the edges (data starting
    mid-March or ending mid-July) are excluded so they don't drag down a monthly average.
    """
    if not txns:
        return []
    dates = [t.date for t in txns]
    lo, hi = min(dates), max(dates)
    result = []
    for (y, m) in sorted({(t.date.year, t.date.month) for t in txns}):
        first = date_type(y, m, 1)
        last = date_type(y, m, calendar.monthrange(y, m)[1])
        if first >= lo and last <= hi:
            result.append((y, m))
    return result


def total_spend(txns) -> Decimal:
    return sum((t.amount for t in txns), Decimal("0"))


def spending_by_category(txns) -> dict:
    out: dict[str, Decimal] = {}
    for t in txns:
        out[t.category] = out.get(t.category, Decimal("0")) + t.amount
    return dict(sorted(out.items(), key=lambda kv: kv[1], reverse=True))


def average_monthly_spend(txns) -> tuple[Decimal, list[tuple[int, int]]]:
    """(average total spend per complete month, list of complete months used). Averaged over
    complete months only - see complete_months()."""
    months = complete_months(txns)
    if not months:
        return Decimal("0"), []
    month_set = set(months)
    in_scope = [t for t in txns if (t.date.year, t.date.month) in month_set]
    # Quantize to cents at the source so every downstream tool derives the SAME monthly figure -
    # otherwise a full-precision average makes cumulative projections step by inconsistent cents.
    avg = total_spend(in_scope) / Decimal(len(months))
    return avg.quantize(Decimal("0.01")), months
