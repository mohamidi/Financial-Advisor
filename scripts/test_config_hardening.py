"""Verifies the Day 8 startup secrets check: the server refuses to boot (clear RuntimeError) when a
required secret is missing, instead of failing cryptically on the first request. Free, no Claude/DB.

TestClient runs the app's lifespan on __enter__, so entering it with a blanked required setting must
raise. Restores the setting afterward.

Run with: uv run python -m scripts.test_config_hardening
"""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def main():
    original = settings.anthropic_api_key
    try:
        settings.anthropic_api_key = ""  # simulate a missing required secret
        raised = False
        try:
            with TestClient(app):  # triggers lifespan startup
                pass
        except RuntimeError as e:
            raised = True
            assert "anthropic_api_key" in str(e), e
            assert "Missing required configuration" in str(e), e
        assert raised, "server booted despite a missing required secret"
        print("OK - server refuses to start with a missing required secret (clear RuntimeError).")
    finally:
        settings.anthropic_api_key = original

    # With everything present, startup succeeds.
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    print("OK - with all required secrets present, startup succeeds and /health responds.")


if __name__ == "__main__":
    main()
