# Financial Advisor Agent

A conversational financial advisor. You complete a short onboarding interview (age, income, debt,
risk tolerance), then ask things like *"can I afford a $3,000 trip?"* and get a grounded,
sometimes-pushback verdict computed from **real numbers** — your profile plus your transaction
history — not vibes. When the honest answer is *risky* or *no*, it says so and explains why, and it
holds that line even if you push back.

Built to run as a real multi-user app, frugally. It uses synthetic transaction data today; a real
bank connection (Plaid) is a later phase.

## How it works

- **Deterministic verdicts.** The affordability decision is a real rule engine
  ([`app/agent/tools/verdict.py`](app/agent/tools/verdict.py)) that runs threshold checks against
  computed numbers — one-time vs. recurring cost, an emergency-fund reserve lens, debt modifiers.
  The language model presents and explains the verdict and cites the numbers behind it, but it
  **cannot soften a "risky"/"no" into a "yes"** to please the user. That property is covered by an
  eval suite, not just a prompt instruction.
- **Tools over a service seam.** The advisor's finance tools (`aggregate_spending`,
  `compute_discretionary_balance`, `project_cash_flow`) only read through
  [`app/services/transactions.py`](app/services/transactions.py). Transactions carry a `source`
  field (`synthetic` / `plaid`), so adding Plaid later is a new data source, not a tool rewrite.
- **Deterministic onboarding.** Intake is a fixed, validated questionnaire
  ([`app/onboarding.py`](app/onboarding.py)) with no LLM in the path — guaranteed collection and
  trivially testable. The model's judgment is reserved for the verdict layer, where it's load-bearing.

## Stack

- **Backend:** Python / FastAPI, tool-calling loop against the Anthropic API (Claude Sonnet 5).
- **Data + auth:** Supabase — managed Postgres with Row Level Security, and Supabase Auth (JWTs).
- **Frontend:** a single self-contained page ([`frontend/index.html`](frontend/index.html)), served
  by FastAPI; talks to Supabase Auth directly for login and to the API for chat.
- **Hosting (planned):** the stateless FastAPI app on Fly.io; Supabase owns persistence.

## Security & isolation

- **Auth is delegated to Supabase.** The API verifies Supabase-issued JWTs against the project's
  public JWKS endpoint (ES256) — no local password store, no sessions table.
- **Per-user data isolation is database-enforced.** User-scoped reads/writes go through Supabase's
  Data API using *that request's own JWT*, so Postgres Row Level Security (`auth.uid()`-scoped
  policies) applies — not just an app-level `WHERE user_id = ...`. The superuser `DATABASE_URL`
  connection is reserved for admin/seed/migration code (it bypasses RLS by design).
- **Cost & abuse controls** (spending runs on the owner's API key):
  - Per-response `max_tokens` and a tool-loop iteration cap.
  - A **per-user daily token budget** and a **per-user messages/hour rate limit** — both reject with
    `429` *before* any Claude call, so a throttled request costs nothing. Defaults live in
    [`app/config.py`](app/config.py) and are env-overridable.
  - Startup fails fast with a clear error if a required secret is missing.
  - An explicit CORS origin allowlist (empty = same-origin only; never `*`).
- **No real financial data is committed.** The repo is public; `.env`, `*.db`, and `data/real_*`
  are gitignored. Today's data is synthetic.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) and a Supabase project + an Anthropic API key.

```bash
uv sync                       # install dependencies
cp .env.example .env          # then fill in the values (see comments in that file)
```

One-time database + demo-data setup (uses the admin connection):

```bash
uv run python -m scripts.create_tables                   # create tables, FKs, RLS policies
uv run python -m scripts.create_demo_user                # a persistent demo Auth identity
uv run python -m scripts.seed_synthetic_transactions     # load synthetic transactions for the demo user
```

## Run

```bash
uv run uvicorn app.main:app --reload      # http://localhost:8000  (login + chat UI at /)
```

Prefer the terminal? The same advisor assembly drives an interactive terminal chat:

```bash
uv run python -m scripts.test_advisor
```

## Tests & evals

Most scripts run against the real services (Supabase + API) and verify behavior end-to-end. The
ones that make Claude calls are noted; the rest are free.

```bash
# Eval harness (pass-rate report; non-zero exit on any failure)
uv run python -m scripts.run_evals               # logic + agent tiers (agent tier makes Claude calls)
uv run python -m scripts.run_evals --logic-only  # free: deterministic verdict-band checks only

# Focused checks (all free unless noted)
uv run python -m scripts.test_verdict            # verdict engine, pure logic
uv run python -m scripts.test_finance_tools      # finance tools vs. an independent recomputation
uv run python -m scripts.test_usage_logging      # usage logging + RLS lockdown (adversarial)
uv run python -m scripts.test_budget             # daily token budget -> 429
uv run python -m scripts.test_rate_limit         # messages/hour rate limit -> 429
uv run python -m scripts.test_cors               # CORS allowlist
uv run python -m scripts.test_config_hardening   # startup fails fast on a missing secret
uv run python -m scripts.test_chat_endpoint      # /chat end-to-end (makes Claude calls)
```

The eval harness deliberately includes scenarios that push the advisor to soften a *risky*/*no*
verdict under social pressure and assert that it doesn't — the core promise of the project.

## Status

Core build complete on synthetic data: auth, onboarding, finance tools, the deterministic verdict
layer, a browser chat UI, an eval harness, per-user usage logging, and cost/abuse hardening.

Next: **Plaid** (real transactions + account balances, which unlock the savings-based verdict lens),
then **deployment** to Fly.io.
