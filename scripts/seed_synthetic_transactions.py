"""Loads data/synthetic_transactions.csv into the transactions table for the demo user.

Safe to re-run - deletes the demo user's existing synthetic transactions first, then reloads,
so this always ends up matching whatever's currently in the CSV rather than accumulating dupes.

Run with: uv run python -m scripts.seed_synthetic_transactions
"""

import csv
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete

from app.config import settings
from app.db.database import SessionLocal
from app.db.models import Transaction

CSV_PATH = "data/synthetic_transactions.csv"


def main():
    if not settings.demo_user_id:
        raise RuntimeError("DEMO_USER_ID is not set in .env - run scripts.create_demo_user first")

    demo_user_id = uuid.UUID(settings.demo_user_id)

    with open(CSV_PATH, newline="") as f:
        csv_rows = list(csv.DictReader(f))

    db = SessionLocal()
    try:
        deleted = db.execute(
            delete(Transaction).where(
                Transaction.user_id == demo_user_id,
                Transaction.source == "synthetic",
            )
        )
        print(f"Cleared {deleted.rowcount} existing synthetic transactions for demo user.")

        db.add_all(
            [
                Transaction(
                    user_id=demo_user_id,
                    account_id=row["account_id"],
                    date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
                    merchant_name=row["merchant_name"],
                    category=row["category"],
                    amount=Decimal(row["amount"]),
                    source="synthetic",
                )
                for row in csv_rows
            ]
        )
        db.commit()
        print(f"Inserted {len(csv_rows)} transactions for demo user {demo_user_id}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
