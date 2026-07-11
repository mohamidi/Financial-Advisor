from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""

    # Supabase project connection info (Project Settings -> API / Database in the Supabase dashboard)
    database_url: str = ""
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""
    demo_user_id: str = ""

    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"
    plaid_token_encryption_key: str = ""

    # Day 8 cost control: a per-user DAILY token cap (input+output summed), checked before each
    # /chat call so one user can't burn the owner's API key. Token-based, not dollar-based, to avoid
    # maintaining a per-model pricing table that goes stale (the org-level $ ceiling in the Anthropic
    # Console is the real dollar backstop). ~200k tokens is roughly 15-40 advisor turns/day depending
    # on tool rounds - generous for a real user, a hard wall against abuse. Override via env.
    daily_token_budget_per_user: int = 200_000

    # Day 8 abuse control: a per-user MESSAGES-per-hour cap, checked before each /chat call. Reuses
    # the usage_events table (one row per completed turn) - a trailing-hour COUNT, no separate
    # counter/store, so it's durable and correct across Fly.io's stateless multi-instance restarts
    # (an in-memory limiter would not be). 30/hr is generous for a human, a wall against a script.
    max_messages_per_hour_per_user: int = 30

    # Day 8 hardening: CORS origin allowlist (comma-separated). Auth is a Bearer token in the
    # Authorization header, not a cookie, so classic CSRF doesn't apply; the browser control that
    # matters is which ORIGINS may make cross-origin requests to the API. Empty = same-origin only,
    # which is the current setup (FastAPI serves the SPA itself, so the browser and API share an
    # origin and need no CORS grant). When the frontend moves to a separate origin, list it here
    # explicitly - never widen this to "*".
    cors_allowed_origins: str = ""


settings = Settings()
