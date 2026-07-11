"""Verifies the Day 8 CORS hardening (free, no Claude/DB):

1. Unit: the comma-separated allowlist parses correctly.
2. Secure default: the real app ships with an EMPTY allowlist, so a cross-origin browser request
   gets NO Access-Control-Allow-Origin header - i.e. same-origin only, never accidentally "*".
3. Mechanism: a configured allowlist admits a listed origin and still refuses an unlisted one.

Run with: uv run python -m scripts.test_cors
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.main import _parse_origins, app

ACAO = "access-control-allow-origin"


def main():
    # 1. Unit ----------------------------------------------------------------------------------
    assert _parse_origins("") == []
    assert _parse_origins("https://a.com") == ["https://a.com"]
    assert _parse_origins(" https://a.com , ,https://b.com ") == ["https://a.com", "https://b.com"]
    print("OK - _parse_origins: blanks dropped, whitespace trimmed, empty -> [].")

    # 2. Secure default (real app, empty allowlist) --------------------------------------------
    client = TestClient(app)
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert r.status_code == 200
    assert ACAO not in r.headers, f"cross-origin must not be granted by default, got {r.headers.get(ACAO)!r}"
    print("OK - default app grants no cross-origin access (no Access-Control-Allow-Origin header).")

    # 3. Mechanism (a configured allowlist) ----------------------------------------------------
    configured = FastAPI()

    @configured.get("/health")
    def _health():
        return {"status": "ok"}

    configured.add_middleware(
        CORSMiddleware,
        allow_origins=["https://good.example"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    c = TestClient(configured)

    r = c.get("/health", headers={"Origin": "https://good.example"})
    assert r.headers.get(ACAO) == "https://good.example", r.headers
    r = c.get("/health", headers={"Origin": "https://bad.example"})
    assert ACAO not in r.headers, r.headers.get(ACAO)
    print("OK - a configured allowlist admits the listed origin and refuses an unlisted one.")


if __name__ == "__main__":
    main()
