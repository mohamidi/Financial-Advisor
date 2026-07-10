"""Deterministic onboarding questionnaire - the same fixed questions for every user, with no LLM
in the intake path.

Chosen over a Claude-driven interview because initial intake is fixed, structured data where
guaranteed collection and testability matter more than conversational flexibility; the model's
judgment is saved for the verdict layer where it's actually load-bearing. `save_profile` stays a
Claude tool (app/agent/tools/save_profile.py) for *updates* mid-conversation later - only the
initial intake is deterministic.

This module is framework-agnostic: it defines the questions and how to validate each answer, with
no terminal or HTTP specifics, so the terminal harness (scripts/test_onboarding.py) now and the
Day 6 web route later can both drive the same questions.
"""

from dataclasses import dataclass
from typing import Callable

from app.services import profiles


class AnswerError(ValueError):
    """An answer failed validation. The message is written to be safe to show the user."""


@dataclass
class Question:
    field: str
    prompt: str
    parse: Callable[[str], object]  # raw input -> stored value, or raises AnswerError


def _require(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise AnswerError("This one's required - please enter a value.")
    return value


def _money(raw: str) -> str:
    """Parse a dollar amount to an exact 2-decimal string (house style: money as strings/Decimal,
    never a bare float - see CLAUDE.md)."""
    cleaned = raw.strip().lstrip("$").replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        raise AnswerError("Please enter a dollar amount, e.g. 6800 or 6800.50.")
    if value < 0:
        raise AnswerError("Amount can't be negative.")
    return f"{value:.2f}"


def _parse_age(raw: str) -> int:
    try:
        age = int(_require(raw))
    except ValueError:
        raise AnswerError("Please enter your age as a whole number, e.g. 34.")
    if not 0 < age < 120:
        raise AnswerError("Please enter an age between 1 and 119.")
    return age


def _parse_marital_status(raw: str) -> str:
    value = _require(raw).lower()
    if value not in ("single", "married"):
        raise AnswerError("Please answer 'single' or 'married'.")
    return value


def _parse_income(raw: str) -> str:
    return _money(_require(raw))


def _parse_risk(raw: str) -> str:
    value = _require(raw).lower()
    if value not in ("low", "medium", "high"):
        raise AnswerError("Please answer 'low', 'medium', or 'high'.")
    return value


def _parse_dependents(raw: str) -> int:
    if not raw.strip():
        return 0
    try:
        n = int(raw.strip())
    except ValueError:
        raise AnswerError("Please enter a whole number, or press Enter for 0.")
    if n < 0:
        raise AnswerError("Can't be negative.")
    return n


def _parse_debt(raw: str) -> str:
    if not raw.strip():
        return "0.00"
    return _money(raw)


def _parse_notes(raw: str) -> str:
    return raw.strip()


QUESTIONS = [
    Question("age", "How old are you?", _parse_age),
    Question("marital_status", "Are you single or married?", _parse_marital_status),
    Question(
        "monthly_income",
        "What's your monthly take-home (net) income, in dollars?",
        _parse_income,
    ),
    Question(
        "risk_tolerance",
        "How do you handle investment risk? If your portfolio dropped 20% in a bad month, would "
        "you pull out to stop the losses (low), hold and wait it out (medium), or see it as a "
        "chance to buy more (high)? Answer low, medium, or high.",
        _parse_risk,
    ),
    Question(
        "dependents",
        "How many financial dependents do you have? (press Enter for 0)",
        _parse_dependents,
    ),
    Question(
        "existing_debt",
        "Roughly how much total debt do you have across everything - loans, credit cards, etc.? "
        "(press Enter for 0)",
        _parse_debt,
    ),
    Question(
        "notes",
        "Anything else about your finances you'd like on record? (press Enter to skip)",
        _parse_notes,
    ),
]


def save_onboarding_profile(user_id: str, jwt: str, answers: dict) -> dict:
    """Write a profile from already-validated answers (keyed by Question.field)."""
    return profiles.save_profile(user_id, jwt, answers)
