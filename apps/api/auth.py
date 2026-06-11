"""Supabase JWT verification."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from apps.api.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    id: UUID
    email: str | None = None


def _decode_token(token: str, settings: Settings) -> dict:
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_JWT_SECRET is not configured",
        )
    options = {"verify_aud": bool(settings.supabase_url)}
    audience = "authenticated" if settings.supabase_url else None
    issuer = f"{settings.supabase_url.rstrip('/')}/auth/v1" if settings.supabase_url else None
    return jwt.decode(
        token,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience=audience,
        issuer=issuer,
        options=options,
    )


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = _decode_token(creds.credentials, settings)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return AuthUser(id=UUID(sub), email=payload.get("email"))


async def verify_ws_token(token: str, settings: Settings) -> AuthUser:
    try:
        payload = _decode_token(token, settings)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return AuthUser(id=UUID(sub), email=payload.get("email"))
