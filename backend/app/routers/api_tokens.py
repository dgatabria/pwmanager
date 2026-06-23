"""API Token management endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.api_token import APIToken
from app.schemas.api_token import (
    APITokenCreate,
    APITokenCreateResponse,
    APITokenListResponse,
    APITokenRecycleRequest,
    APITokenRecycleResponse,
    APITokenRevokeResponse,
)
from app.services.api_token import APITokenService
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/api-tokens", tags=["API Tokens"])

# Rate limiter for API token endpoints
_token_limiter = Limiter(key_func=get_remote_address)


async def get_current_user_with_api_key(
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Dependency to get current user from JWT token or API key.
    Supports both session-based and API key authentication.

    Authentication strategy:
    - If a Bearer token is present (valid or not), use it exclusively.
      This prevents an attacker from supplying an invalid JWT that falls
      through to API-key auth and potentially authenticates as a different user.
    - If no Bearer header is present, fall back to API-key auth.
    Returns user_info dict.
    """
    user_id = None
    user_info = None

    # Try JWT token first (standard Bearer token)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        try:
            from app.services.auth import AuthService
            payload = AuthService.decode_token(token)
            user_id = payload.get("sub")
            if user_id:
                user_info = {
                    "id": int(user_id),
                    "username": payload.get("username", ""),
                    "email": payload.get("email", ""),
                    "full_name": payload.get("full_name", ""),
                    "is_superuser": payload.get("is_superuser", False),
                }
        except Exception as exc:
            # JWT validation failed — reject. Do NOT fall through to API key
            # auth, because that would allow an attacker to supply an invalid
            # JWT that silently bypasses JWT validation and authenticates as
            # whatever user the API key belongs to.
            logging.warning("JWT validation failed, rejecting request: %s", exc)
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Only try API key if no Bearer header was provided at all
    if user_id is None and (x_api_key or (authorization and authorization.startswith("ApiKey "))):
        api_key = x_api_key or (authorization.split(" ", 1)[1] if authorization else None)
        if api_key:
            api_token, user_info = await APITokenService.validate_token(db, api_key)
            if api_token:
                user_id = api_token.user_id

    if user_id is None or user_info is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user_info


UserDep = Annotated[dict, Depends(get_current_user_with_api_key)]


@router.get("")
async def list_tokens(
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """List all API tokens for the current user."""
    user_id = user_info["id"]

    tokens = await APITokenService.list_user_tokens(db, user_id)

    return [
        {
            "id": token.id,
            "name": token.name,
            "description": token.description,
            "is_active": token.is_active,
            "created_at": str(token.created_at),
            "last_used_at": str(token.last_used_at) if token.last_used_at else None,
            "expires_at": str(token.expires_at) if token.expires_at else None,
        }
        for token in tokens
    ]


@router.post("/generate", response_model=APITokenCreateResponse, status_code=201)
@_token_limiter.limit("60/minute")
async def generate_token(
    token_data: APITokenCreate,
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API token.

    Rate limited to 60 requests per minute to prevent abuse.
    """
    user_id = user_info["id"]

    try:
        plain_token, api_token = await APITokenService.create_token(
            db=db,
            user_id=user_id,
            name=token_data.name,
            description=token_data.description,
            expires_at=token_data.expires_at,
        )
    except Exception as e:
        logging.error("Failed to generate API token for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate token. Please try again or contact support.")

    return APITokenCreateResponse(
        token=plain_token,
        token_id=api_token.id,
        name=api_token.name,
        description=api_token.description,
        created_at=str(api_token.created_at),
        expires_at=str(api_token.expires_at) if api_token.expires_at else None,
        warning="Store this token securely. It will not be shown again.",
    )


@router.post("/recycle", response_model=APITokenRecycleResponse)
async def recycle_token(
    recycle_data: APITokenRecycleRequest,
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Recycle an API token: revoke old one and create new one."""
    user_id = user_info["id"]

    try:
        new_token = await APITokenService.recycle_token(
            db=db,
            old_token=recycle_data.api_key,
            user_id=user_id,
            name=recycle_data.name,
            description=recycle_data.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logging.error("Failed to recycle API token for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to recycle token. Please try again or contact support.")

    return APITokenRecycleResponse(
        new_token=new_token,
        warning="The old token has been revoked. Store this new token securely.",
    )


@router.delete("/{token_id}", response_model=APITokenRevokeResponse)
async def revoke_token(
    token_id: int,
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Revoke (delete) an API token."""
    user_id = user_info["id"]

    api_token = await APITokenService.revoke_token(db, token_id, user_id)

    if not api_token:
        raise HTTPException(status_code=404, detail="Token not found")

    return APITokenRevokeResponse(
        message="Token revoked successfully",
        revoked_token_id=api_token.id,
    )
