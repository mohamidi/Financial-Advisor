from contextlib import asynccontextmanager
from typing import Literal

import anthropic
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import onboarding
from app.agent.advisor import ADVISOR_TOOLS, build_executors
from app.agent.orchestrator import MODEL, last_text, run_agent_turn
from app.agent.prompts import build_advisor_system_prompt
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.config import settings
from app.services import profiles, usage

# Secrets the server genuinely can't function without. Validated at startup (below) so a
# misconfigured deploy fails fast with a clear message, instead of booting fine and then throwing a
# cryptic auth/HTTP error on the first real request. (demo_user_id and the Plaid keys aren't here -
# they're only needed by scripts / Phase 2, not to serve /chat.)
REQUIRED_SETTINGS = ["anthropic_api_key", "supabase_url", "supabase_publishable_key", "database_url"]


@asynccontextmanager
async def lifespan(app: "FastAPI"):
    missing = [name for name in REQUIRED_SETTINGS if not getattr(settings, name)]
    if missing:
        raise RuntimeError(
            f"Missing required configuration: {', '.join(missing)}. "
            f"Set them in .env (local) or as host secrets (deploy) before starting the server."
        )
    yield


app = FastAPI(title="Financial Advisor Agent", lifespan=lifespan)


def _parse_origins(raw: str) -> list[str]:
    """Comma-separated allowlist -> clean list; blanks dropped. Empty string -> [] (same-origin only)."""
    return [o.strip() for o in raw.split(",") if o.strip()]


# Explicit CORS allowlist. With an empty list the browser grants no cross-origin access at all (the
# secure default for our same-origin SPA); a separately-hosted frontend is added via
# settings.cors_allowed_origins, never "*". Only the methods/headers /chat actually uses are allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_origins(settings.cors_allowed_origins),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# One shared Claude client - it carries no user state (all per-user scoping is via the tools' JWT),
# so it's safe to reuse across requests rather than rebuilding it each time.
_claude = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# Cost guards (see CLAUDE.md "Token-cost controls"): bound a single message and how much history
# is resent each turn, so one request can't carry tens of thousands of tokens of context.
MAX_MESSAGE_CHARS = 4000
MAX_HISTORY_MESSAGES = 50


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class ChatRequest(BaseModel):
    # The conversation so far, held by the client as plain text. Tool results / verdicts are NEVER
    # here - they're recomputed fresh server-side each turn, so client-held history can't forge a
    # verdict or reach another user's data (see CLAUDE.md Day 6 decision).
    history: list[ChatMessage] = Field(default_factory=list)
    message: str


class ChatResponse(BaseModel):
    reply: str
    history: list[ChatMessage]  # updated - includes this turn's user message + reply


@app.get("/")
def index():
    # The single-page login + chat UI. Path is relative to the working directory the server runs
    # from (project root); on Fly the frontend/ dir ships alongside the app.
    return FileResponse("frontend/index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/protected-ping")
def protected_ping(user: AuthenticatedUser = Depends(get_current_user)):
    return {"message": f"hello {user.email or user.id}, you are authenticated"}


class OnboardingRequest(BaseModel):
    # field -> raw string answer. Values are validated server-side (never trusted from the client) by
    # the same parsers the terminal harness uses, so the web path can't bypass a rule the CLI enforces.
    answers: dict[str, str] = Field(default_factory=dict)


@app.get("/profile")
def get_profile(user: AuthenticatedUser = Depends(get_current_user), authorization: str = Header(...)):
    """The logged-in user's profile, or null if they haven't onboarded yet - lets the client route a
    fresh login to onboarding vs. straight to chat."""
    jwt = authorization.removeprefix("Bearer ")
    return {"profile": profiles.get_profile(user.id, jwt)}


@app.get("/onboarding/questions")
def onboarding_questions(user: AuthenticatedUser = Depends(get_current_user)):
    """The ordered intake questions - server is the single source of truth so the browser form and
    the terminal harness ask exactly the same things."""
    return {"questions": [{"field": q.field, "prompt": q.prompt} for q in onboarding.QUESTIONS]}


@app.post("/onboarding")
def submit_onboarding(
    req: OnboardingRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    authorization: str = Header(...),
):
    """Validate all answers and write the profile. Deterministic - no Claude. On validation failure
    returns 422 with {detail: {errors: {field: message}}} so the client can show each inline."""
    jwt = authorization.removeprefix("Bearer ")
    try:
        parsed = onboarding.validate_answers(req.answers)
    except onboarding.OnboardingValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"errors": exc.errors})
    saved = onboarding.save_onboarding_profile(user.id, jwt, parsed)
    return {"profile": saved}


@app.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    authorization: str = Header(...),
):
    if not req.message.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Message is empty.")
    if len(req.message) > MAX_MESSAGE_CHARS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Message is too long.")
    if len(req.history) > MAX_HISTORY_MESSAGES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Conversation is too long - start a new one.")

    # Per-user rate limit + daily budget: both checked here, BEFORE any Claude call, so a throttled
    # or over-quota request costs nothing.
    rate_exceeded, count, rate_limit = usage.over_rate_limit(user.id)
    if rate_exceeded:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many messages ({count} in the last hour, limit {rate_limit}). Please slow down and try again shortly.",
            headers={"Retry-After": "3600"},
        )

    exceeded, used, limit = usage.over_daily_budget(user.id)
    if exceeded:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Daily usage limit reached ({used:,} of {limit:,} tokens). Please try again tomorrow.",
        )

    # get_current_user already verified this token; re-read the raw string to pass to the tools,
    # which use the user's own JWT for RLS-scoped data access.
    jwt = authorization.removeprefix("Bearer ")

    profile = profiles.get_profile(user.id, jwt)
    system = build_advisor_system_prompt(profile)
    executors = build_executors(user.id, jwt)

    messages = [{"role": m.role, "content": m.text} for m in req.history]
    messages.append({"role": "user", "content": req.message})

    # Accumulate this turn's token spend across every tool round-trip and persist one row for it,
    # attributed to the user - the foundation for Day 8's per-user daily-budget check.
    acc = usage.UsageAccumulator()
    messages = run_agent_turn(_claude, messages, ADVISOR_TOOLS, executors, system, on_usage=acc.add)
    reply = last_text(messages)
    usage.log_usage(user.id, MODEL, acc)

    new_history = req.history + [
        ChatMessage(role="user", text=req.message),
        ChatMessage(role="assistant", text=reply),
    ]
    return ChatResponse(reply=reply, history=new_history)
