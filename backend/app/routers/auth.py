"""Authentication API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, Token, UserCreate, UserResponse
from app.services.auth import AuthService
from app.utils.security import SecurityUtils

router = APIRouter(tags=["Authentication"])

# Rate limiter for auth endpoints - shared with main.py
limiter: Limiter = getattr(settings, "_limiter", Limiter(key_func=get_remote_address))


async def get_current_user(authorization: Annotated[str | None, Header()] = None):
    """Dependency to get current user from JWT token.
    
    Returns user_id (int).
    Centralized auth function - used by all routers.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ", 1)[1]
    try:
        payload = AuthService.decode_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return int(user_id)
    except (ValueError, Exception):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user_info(authorization: Annotated[str | None, Header()] = None, db: AsyncSession = Depends(get_db)):
    """Dependency to get full current user info from JWT token.
    
    Returns user dict with id, username, email, is_superuser.
    Centralized auth function - used by all routers.
    """
    user_id = await get_current_user(authorization=authorization)
    
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


@router.post("/login", response_model=Token)
@limiter.limit(settings.RATE_LIMIT)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT token.
    
    Rate limited to prevent brute force attacks.
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

    token = AuthService.create_access_token(data={"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user.
    
    Rate limited to prevent abuse. Username and email uniqueness enforced.
    """
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
async def get_me(user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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
