import jwt
from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from app.config import settings

# Supabase issues HS256 JWTs signed with the project's JWT secret, with `aud: "authenticated"`
# for logged-in users. Verify current claim names/algorithm in the Supabase docs if this starts
# rejecting valid tokens - their JWT issuance details are not guaranteed stable across versions.
JWT_AUDIENCE = "authenticated"
JWT_ALGORITHMS = ["HS256"]


class AuthenticatedUser(BaseModel):
    id: str
    email: str | None = None


def get_current_user(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=JWT_ALGORITHMS,
            audience=JWT_AUDIENCE,
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc

    return AuthenticatedUser(id=payload["sub"], email=payload.get("email"))
