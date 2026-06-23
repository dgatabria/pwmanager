"""Authentication API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.main import is_maintenance_mode
from app.models.user import User
from app.schemas.auth import LoginRequest, Token, UserCreate, UserResponse
from app.services.auth import AuthService
from app.utils.security import SecurityUtils

router = APIRouter(tags=["Authentication"])

# Rate limiter for auth endpoints - shared with main.py
limiter: Limiter = getattr(settings, "_limiter", Limiter(key_func=get_remote_address))

# JWT cookie name
JWT_COOKIE_NAME = "access_token"


async def get_current_user(
    request: Request = Depends(),
    authorization: Annotated[str | None, Header()] = None,
):
    """Dependency to get current user from JWT token.

    Checks the Authorization header first (Bearer token), then falls back
    to the httpOnly cookie.

    Returns user_id (int).
    Centralized auth function - used by all routers.
    """
    token = None

    # 1. Try Authorization header (Bearer token)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]

    # 2. Fall back to httpOnly cookie
    if not token and request.cookies:
        token = request.cookies.get(JWT_COOKIE_NAME)

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = AuthService.decode_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return int(user_id)
    except (ValueError, Exception):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user_info(
    request: Request = Depends(),
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
):
    """Dependency to get full current user info from JWT token.

    Checks the Authorization header first (Bearer token), then falls back
    to the httpOnly cookie.

    Returns user dict with id, username, email, is_superuser.
    Centralized auth function - used by all routers.
    """
    user_id = await get_current_user(request=request, authorization=authorization)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_superuser": user.is_superuser,
        "is_active": user.is_active,
    }


UserDep = Annotated[int, Depends(get_current_user)]
UserDepInfo = Annotated[dict, Depends(get_current_user_info)]


@router.post("/login")
@limiter.limit(settings.RATE_LIMIT)
async def login(request: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT token.

    The JWT is set as an httpOnly, Secure cookie (for production HTTPS)
    and also returned in the JSON body for clients that cannot use cookies.

    Rate limited to prevent brute force attacks.
    During maintenance mode, only superusers can log in.
    """
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()

    if not user or not SecurityUtils.verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # During maintenance mode, only superusers can log in
    if await is_maintenance_mode() and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is temporarily unavailable. Maintenance in progress.",
        )

    token = AuthService.create_access_token(data={"sub": str(user.id)})

    # Set httpOnly cookie as an additional auth mechanism
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,        # Only send over HTTPS in production
        samesite="lax",     # CSRF protection
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    return {"access_token": token, "token_type": "bearer"}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user.
    
    Rate limited to prevent abuse. Username and email uniqueness enforced.
    Password must meet strength requirements.
    """
    # Validate password strength
    is_valid, error_msg = SecurityUtils.validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Check if username exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already exists")

    hashed = SecurityUtils.hash_password(user_data.password)
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed,
        full_name=user_data.full_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=str(user.created_at),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user info (requires auth)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=str(user.created_at),
    )


@router.post("/logout")
async def logout(response: Response):
    """Logout by clearing the httpOnly JWT cookie."""
    response.delete_cookie(
        key=JWT_COOKIE_NAME,
        path="/",
    )
    return {"message": "Logged out successfully"}
