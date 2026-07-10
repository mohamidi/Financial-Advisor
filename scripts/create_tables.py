"""Creates app-owned tables and locks them down with Row Level Security.

Deliberately NOT run automatically on app startup - schema changes should be a reviewed, one-off
action, not something that happens as a side effect of the server booting (especially with more
than one server instance, where auto-migration on startup can race).

Safe to re-run - table creation is a no-op if it already exists, and policies are dropped and
recreated each time so edits here take effect on a rerun.

Run with: uv run python -m scripts.create_tables
"""

from sqlalchemy import text

from app.db import models  # noqa: F401 - import registers models on Base.metadata
from app.db.database import Base, engine

# transactions: only a SELECT policy - every write path (the seed script now, Plaid sync in
# Phase 2) goes through the admin DATABASE_URL connection as a deliberate backend operation, not
# a per-user request - so there's no INSERT/UPDATE/DELETE via the authenticated role to authorize
# yet.
# profiles: SELECT/INSERT/UPDATE - save_profile (Day 3) writes on behalf of a real logged-in
# user via the Data API with that user's own JWT, so the authenticated role needs to be able to
# create and edit its own row, not just read it. No DELETE policy - no use case yet.
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
    (
        "profiles",
        "Users can view their own profile",
        """
        CREATE POLICY "Users can view their own profile"
        ON profiles FOR SELECT
        TO authenticated
        USING (auth.uid() = user_id);
        """,
    ),
    (
        "profiles",
        "Users can insert their own profile",
        """
        CREATE POLICY "Users can insert their own profile"
        ON profiles FOR INSERT
        TO authenticated
        WITH CHECK (auth.uid() = user_id);
        """,
    ),
    (
        "profiles",
        "Users can update their own profile",
        """
        CREATE POLICY "Users can update their own profile"
        ON profiles FOR UPDATE
        TO authenticated
        USING (auth.uid() = user_id)
        WITH CHECK (auth.uid() = user_id);
        """,
    ),
]

# Tables with RLS ENABLED but no authenticated policy - the authenticated role (a user's JWT) can
# neither read nor write them at all. usage_events is system telemetry written only on the admin
# DATABASE_URL connection (which bypasses RLS); this lockdown is load-bearing because Supabase's
# Data API auto-exposes every public table, so without it a user could GET /rest/v1/usage_events
# with their own JWT and read everyone's token counts. See app/services/usage.py.
LOCKDOWN_TABLES = ["usage_events"]

# (table, column, referenced table) - added via raw SQL since auth.users isn't declared in our
# own SQLAlchemy metadata (Supabase manages it), so create_all() can't resolve a DDL dependency
# against it directly.
FOREIGN_KEYS = [
    ("transactions", "user_id", "auth.users"),
    ("profiles", "user_id", "auth.users"),
    ("usage_events", "user_id", "auth.users"),
]

# create_all() only creates a column's default when it makes the column itself - it never
# retrofits ALTER COLUMN ... SET DEFAULT onto a column that already exists. Needed so that
# profiles rows written via PostgREST (which never goes through SQLAlchemy's Python-side
# defaults) still get created_at/updated_at/dependents/existing_debt filled in.
COLUMN_DEFAULTS = [
    ("profiles", "created_at", "now()"),
    ("profiles", "updated_at", "now()"),
    ("profiles", "dependents", "0"),
    ("profiles", "existing_debt", "0"),
]

# Auto-touches updated_at on every UPDATE, regardless of whether it came from SQLAlchemy (which
# has its own onupdate=) or PostgREST (which doesn't) - database-enforced, so it can't be
# forgotten by a future write path the way the column defaults above just were.
UPDATED_AT_TRIGGER = """
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS profiles_set_updated_at ON profiles;
CREATE TRIGGER profiles_set_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
"""


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

        for table in LOCKDOWN_TABLES:
            row = conn.execute(
                text("SELECT relrowsecurity FROM pg_class WHERE relname = :table"),
                {"table": table},
            ).first()
            if not row or not row[0]:
                conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;"))
                print(f"Enabled RLS on {table} (locked down - no authenticated policy).")
            else:
                print(f"RLS already enabled on {table} (locked down - no authenticated policy).")

        for table, column, default_sql in COLUMN_DEFAULTS:
            conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT {default_sql};"))
            print(f"Set default {default_sql} on {table}.{column}.")

        conn.execute(text(UPDATED_AT_TRIGGER))
        print("Applied updated_at trigger on profiles.")


if __name__ == "__main__":
    main()
