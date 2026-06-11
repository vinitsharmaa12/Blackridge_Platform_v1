"""Dev-only helpers (local testing)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from apps.api.auth import encode_dev_token
from apps.api.config import Settings, get_settings

DEFAULT_DEV_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
DEFAULT_DEV_EMAIL = "dev@local.test"

router = APIRouter(prefix="/dev", tags=["dev"])


class DevTokenRequest(BaseModel):
    user_id: UUID = Field(default=DEFAULT_DEV_USER_ID)
    email: str = Field(default=DEFAULT_DEV_EMAIL)


class DevTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/token", response_model=DevTokenResponse)
async def mint_dev_token(
    body: DevTokenRequest | None = None,
    settings: Settings = Depends(get_settings),
) -> DevTokenResponse:
    req = body or DevTokenRequest()
    token, ttl = encode_dev_token(req.user_id, req.email, settings)
    return DevTokenResponse(access_token=token, expires_in=ttl)
