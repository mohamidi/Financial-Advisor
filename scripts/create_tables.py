"""Creates app-owned tables and locks them down with Row Level Security.

Deliberately NOT run automatically on app startup - schema changes should be a reviewed, one-off
action, not something that happens as a side effect of the server booting (especially with more
than one server instance, where auto-migration on startup can race).

Safe to re-run - table creation is a no-op if it already exists, and policies are dropped and
recreated each time so edits here take effect on a rerun.

Run with: uv run python -m scripts.create_tables
"""

from sqlalchemy import text

from app.db import models  # noqa: F401 - import registers Transaction on Base.metadata
from app.db.database import Base, engine

# Only a SELECT policy: every write path (the seed script now, Plaid sync in Phase 2) goes
# through the admin DATABASE_URL connection as a deliberate backend operation, not a per-user
# request - so there's no INSERT/UPDATE/DELETE via the authenticated role to authorize yet.
POLICIES = [
    (
        "transactions",
        "Users can view their own transactions",
        """
        CREATE POLICY "Users can view their own transactions"
        ON transactions FOR SELECT
        TO authenticated
        USING (auth.uid() = user_id);
        """,
    ),
]

# (table, column, referenced table) - added via raw SQL since auth.users isn't declared in our
# own SQLAlchemy metadata (Supabase manages it), so create_all() can't resolve a DDL dependency
# against it directly.
FOREIGN_KEYS = [
    ("transactions", "user_id", "auth.users"),
]


def main():
    Base.metadata.create_all(bind=engine)
    print("Tables created (or already existed).")

    with engine.begin() as conn:
        for table, column, ref_table in FOREIGN_KEYS:
            constraint_name = f"{table}_{column}_fkey"
            exists = conn.execute(
                text("SELECT 1 FROM pg_constraint WHERE conname = :name"),
                {"name": constraint_name},
            ).first()
            if exists:
                print(f"FK {constraint_name} already exists.")
            else:
                conn.execute(
                    text(
                        f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} "
                        f"FOREIGN KEY ({column}) REFERENCES {ref_table}(id) ON DELETE CASCADE;"
                    )
                )
                print(f"Added FK {constraint_name} -> {ref_table}.")

        for table, policy_name, create_sql in POLICIES:
            row = conn.execute(
                text("SELECT relrowsecurity FROM pg_class WHERE relname = :table"),
                {"table": table},
            ).first()
            if not row or not row[0]:
                conn.execute(text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;'))
                print(f"Enabled RLS on {table}.")
            else:
                print(f"RLS already enabled on {table}.")

            conn.execute(text(f'DROP POLICY IF EXISTS "{policy_name}" ON {table};'))
            conn.execute(text(create_sql))
            print(f'Applied policy "{policy_name}" on {table}.')


if __name__ == "__main__":
    main()
