"""Generates a fixed (seeded, reproducible) synthetic transaction dataset.

Run with: uv run python data/generate_synthetic_transactions.py
Writes data/synthetic_transactions.csv - safe to commit, contains no real data.
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)

MONTHS_OF_HISTORY = 4
ACCOUNT_ID = "demo-checking"

# (category, [(merchant, min_amount, max_amount)], avg_transactions_per_week)
SPENDING_PATTERNS = [
    ("Groceries", [("Trader Joe's", 20, 90), ("Whole Foods", 25, 130), ("Safeway", 15, 100)], 2.0),
    ("Dining", [("Chipotle", 10, 18), ("Local Cafe", 6, 15), ("Sushi Place", 25, 65), ("Pizza Palace", 15, 40), ("Thai Kitchen", 18, 45)], 3.0),
    ("Transportation", [("Uber", 8, 35), ("Lyft", 8, 32), ("Shell Gas", 30, 60), ("Metro Transit", 3, 8)], 2.5),
    ("Entertainment", [("AMC Theatres", 12, 25), ("Steam", 5, 60), ("Concert Tickets", 40, 150), ("Bowling Alley", 20, 45)], 0.8),
    ("Shopping", [("Amazon", 15, 120), ("Target", 20, 90), ("Best Buy", 30, 250), ("Nike", 40, 130)], 1.2),
    ("Healthcare", [("CVS Pharmacy", 10, 45), ("Dental Clinic", 50, 200), ("Urgent Care", 75, 250)], 0.3),
    ("Home", [("Home Depot", 20, 150), ("IKEA", 30, 300), ("Cleaning Service", 80, 120)], 0.3),
    ("Personal Care", [("Hair Salon", 35, 90), ("Sephora", 15, 70)], 0.4),
    ("Miscellaneous", [("Venmo Transfer", 10, 80), ("ATM Withdrawal", 40, 100)], 0.5),
]

# (category, merchant, amount, day_of_month) - charged once every month
RECURRING_MONTHLY = [
    ("Utilities", "PG&E Electric", 95.0, 3),
    ("Utilities", "Comcast Internet", 79.99, 5),
    ("Utilities", "Verizon Wireless", 85.0, 7),
    ("Subscriptions", "Netflix", 15.49, 12),
    ("Subscriptions", "Spotify", 11.99, 14),
    ("Subscriptions", "Gym Membership", 45.0, 1),
    ("Subscriptions", "iCloud Storage", 2.99, 20),
]

# (category, merchant, amount, days_ago) - rare big-ticket outliers, fixed not random
BIG_PURCHASES = [
    ("Travel", "United Airlines", 487.32, 95),
    ("Travel", "Marriott Hotel", 612.00, 40),
    ("Shopping", "Best Buy", 899.00, 60),
]


def generate_rows(end_date: datetime) -> list[dict]:
    start_date = end_date - timedelta(days=30 * MONTHS_OF_HISTORY)
    rows = []

    for category, merchants, per_week in SPENDING_PATTERNS:
        expected_count = int(per_week * (MONTHS_OF_HISTORY * 4.345))
        for _ in range(expected_count):
            offset_days = random.randint(0, (end_date - start_date).days)
            date = start_date + timedelta(days=offset_days)
            merchant, lo, hi = random.choice(merchants)
            amount = round(random.uniform(lo, hi), 2)
            rows.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "merchant_name": merchant,
                    "category": category,
                    "amount": amount,
                    "account_id": ACCOUNT_ID,
                }
            )

    month_starts = []
    cursor = start_date.replace(day=1)
    while cursor <= end_date:
        month_starts.append(cursor)
        cursor = (cursor + timedelta(days=32)).replace(day=1)

    for month_start in month_starts:
        for category, merchant, amount, day in RECURRING_MONTHLY:
            try:
                date = month_start.replace(day=day)
            except ValueError:
                continue
            if start_date <= date <= end_date:
                rows.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "merchant_name": merchant,
                        "category": category,
                        "amount": amount,
                        "account_id": ACCOUNT_ID,
                    }
                )

    for category, merchant, amount, days_ago in BIG_PURCHASES:
        date = end_date - timedelta(days=days_ago)
        rows.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "merchant_name": merchant,
                "category": category,
                "amount": amount,
                "account_id": ACCOUNT_ID,
            }
        )

    rows.sort(key=lambda r: r["date"])
    return rows


def main():
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = generate_rows(end_date)

    out_path = "data/synthetic_transactions.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "merchant_name", "category", "amount", "account_id"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} transactions to {out_path}")
    print(f"Date range: {rows[0]['date']} to {rows[-1]['date']}")
    total = sum(r["amount"] for r in rows)
    print(f"Total spend: ${total:,.2f}")


if __name__ == "__main__":
    main()
