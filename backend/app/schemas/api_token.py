"""Pydantic schemas for API Token model."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class APITokenCreate(BaseModel):
    name: str
    description: Optional[str] = None
    expires_at: Optional[datetime] = None


class APITokenCreateResponse(BaseModel):
    token: str
    token_id: int
    name: str
    description: Optional[str] = None
    created_at: str
    expires_at: Optional[str] = None
    warning: str


class APITokenListResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: str
    last_used_at: Optional[str] = None
    expires_at: Optional[str] = None

    class Config:
        from_attributes = True


class APITokenRecycleRequest(BaseModel):
    api_key: str
    name: Optional[str] = None
    description: Optional[str] = None


class APITokenRecycleResponse(BaseModel):
    new_token: str
    warning: str


class APITokenRevokeResponse(BaseModel):
    message: str
    revoked_token_id: int
