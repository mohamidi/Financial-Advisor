import jwt
from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from app.config import settings

# Supabase's current (2026) default: asymmetric ES256 signing keys, verified against a public
# JWKS endpoint rather than a shared secret - the shared HS256 "JWT Secret" is legacy and Supabase
# itself recommends against it for production. `aud: "authenticated"` marks a logged-in user's
# token. Verify current claim names/algorithm in the Supabase docs if this starts rejecting valid
# tokens - their JWT issuance details are not guaranteed stable across versions.
JWT_AUDIENCE = "authenticated"
JWT_ALGORITHMS = ["ES256"]

_jwks_client = jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")


class AuthenticatedUser(BaseModel):
    id: str
    email: str | None = None


def get_current_user(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    token = authorization.removeprefix("Bearer ")
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=JWT_ALGORITHMS,
            audience=JWT_AUDIENCE,
            issuer=f"{settings.supabase_url}/auth/v1",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    return AuthenticatedUser(id=payload["sub"], email=payload.get("email"))
