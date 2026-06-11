"""Supabase JWT verification."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt

from apps.api.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    id: UUID
    email: str | None = None


def _jwt_issuer(settings: Settings) -> str | None:
    return f"{settings.supabase_url.rstrip('/')}/auth/v1" if settings.supabase_url else None


def encode_dev_token(user_id: UUID, email: str | None, settings: Settings) -> tuple[str, int]:
    """Mint a Supabase-compatible JWT for local dev testing."""
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_JWT_SECRET is not configured",
        )
    ttl = settings.dev_token_ttl_seconds
    now = datetime.now(tz=UTC)
    payload: dict[str, str | datetime] = {
        "sub": str(user_id),
        "aud": "authenticated",
        "exp": now + timedelta(seconds=ttl),
    }
    issuer = _jwt_issuer(settings)
    if issuer:
        payload["iss"] = issuer
    if email:
        payload["email"] = email
    token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
    return token, ttl


_JWKS_ALGORITHMS = frozenset({"ES256", "RS256"})


@lru_cache(maxsize=4)
def _fetch_jwks(supabase_url: str) -> dict[str, Any]:
    """Load Supabase Auth JWKS (ES256 user access tokens)."""
    base = supabase_url.rstrip("/")
    url = f"{base}/auth/v1/.well-known/jwks.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        raise JWTError(f"Failed to load JWKS: {exc}") from exc


def _jwks_verification_key(token: str, settings: Settings) -> Any:
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    jwks = _fetch_jwks(settings.supabase_url)
    keys = jwks.get("keys", [])
    if not keys:
        raise JWTError("JWKS has no keys")
    for key_data in keys:
        if kid is None or key_data.get("kid") == kid:
            return jwk.construct(key_data)
    raise JWTError("No matching JWK for token kid")


def _decode_token(token: str, settings: Settings) -> dict:
    options = {"verify_aud": bool(settings.supabase_url)}
    audience = "authenticated" if settings.supabase_url else None
    issuer = _jwt_issuer(settings)
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "HS256")

    if alg in _JWKS_ALGORITHMS:
        if not settings.supabase_url:
            raise JWTError("JWKS verification requires SUPABASE_URL")
        key = _jwks_verification_key(token, settings)
        return jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience=audience,
            issuer=issuer,
            options=options,
        )

    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_JWT_SECRET is not configured",
        )
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
