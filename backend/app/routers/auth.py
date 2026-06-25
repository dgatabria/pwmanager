"""Authentication API endpoints."""

import secrets as secrets_module
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.maintenance import is_maintenance_mode
from app.schemas.auth import LoginRequest, Token, UserCreate, UserResponse, ResetPasswordRequest
from app.services.auth import AuthService
from app.utils.security import SecurityUtils

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Rate limiter for auth endpoints — independent from main.py limiter
# to avoid circular imports.
_auth_limiter = Limiter(key_func=get_remote_address)

# JWT cookie name
JWT_COOKIE_NAME = "access_token"

# CSRF cookie name (must match main.py)
CSRF_TOKEN_COOKIE = "csrf_token"


async def get_current_user(
    request = Depends(),
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
):
    """Dependency to get current user from JWT token.

    Checks the Authorization header first (Bearer token), then falls back
    to the httpOnly cookie.

    Validates:
    - token_version claim (tv) against the database to prevent session fixation
    - JTI claim against the revoked_tokens table to prevent replay of
      explicitly revoked tokens (e.g., on logout)

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

        # Validate token_version to prevent session fixation
        token_version = payload.get("tv")
        if token_version is not None:
            result = await db.execute(
                select(User).where(User.id == int(user_id))
            )
            user = result.scalar_one_or_none()
            if not user or user.token_version != token_version:
                raise HTTPException(
                    status_code=401, detail="Token has been revoked"
                )

        # Check JTI against revoked_tokens to prevent replay of revoked tokens
        jti = payload.get("jti")
        if jti:
            result = await db.execute(
                text(
                    "SELECT 1 FROM revoked_tokens WHERE jti = :jti "
                    "AND expires_at > NOW()"
                ).bindparams(jti=jti)
            )
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=401, detail="Token has been revoked"
                )

        return int(user_id)
    except (ValueError, Exception):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user_info(
    request = Depends(),
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
@_auth_limiter.limit(settings.RATE_LIMIT)
async def login(request: Request, login_data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT token.

    The JWT is set as an httpOnly, Secure cookie (for production HTTPS)
    and also returned in the JSON body for clients that cannot use cookies.

    Rate limited to prevent brute force attacks.
    Account lockout: after N failed attempts the account is locked for
    LOCKOUT_DURATION_MINUTES.

    During maintenance mode, only superusers can log in.

    Returns password_change_required flag to indicate if the user must
    change their password on first login.
    """
    result = await db.execute(select(User).where(User.username == login_data.username))
    user = result.scalar_one_or_none()

    # Check if user exists and verify password
    if not user or not SecurityUtils.verify_password(login_data.password, user.hashed_password):
        # Increment failed attempts (even if user doesn't exist — prevents user enumeration)
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.LOCKOUT_DURATION_MINUTES
                )
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if account is locked
    if user.locked_until and datetime.now(timezone.utc) < user.locked_until:
        remaining = int((user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account is locked. Try again in {remaining} minute(s).",
        )

    # Reset failed login attempts and lock status on successful login
    if user.failed_login_attempts > 0 or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        await db.commit()

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

    # Increment token_version to invalidate all previously issued JWT tokens
    # for this user (session fixation prevention).
    user.token_version += 1
    await db.commit()

    token, jti = AuthService.create_access_token(
        data={
            "sub": str(user.id),
            "tv": user.token_version,
        }
    )

    # Store JTI for server-side token revocation on logout
    await db.execute(
        text(
            "INSERT INTO revoked_tokens (jti, user_id, reason, expires_at) "
            "VALUES (:jti, :user_id, :reason, :expires_at) "
            "ON CONFLICT (jti) DO NOTHING"
        ).bindparams(
            jti=jti,
            user_id=str(user.id),
            reason="login",
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
    )
    await db.commit()

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

    return {
        "access_token": token,
        "token_type": "bearer",
        "password_change_required": user.password_change_required,
    }


@router.post("/change-password")
@_auth_limiter.limit(settings.RATE_LIMIT)
async def change_password(
    req: Request,
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Change the authenticated user's password.

    Validates the new password strength, hashes it, stores it, and clears
    the password_change_required flag so the user is not prompted again.
    """
    # Validate password strength
    is_valid, error_msg = SecurityUtils.validate_password_strength(request.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = SecurityUtils.hash_password(request.new_password)
    user.password_change_required = False
    # Invalidate all existing sessions
    user.token_version += 1
    await db.commit()

    return {"message": "Password updated successfully"}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@_auth_limiter.limit("10/hour")
async def register(request: Request, user_data: UserCreate, db: AsyncSession = Depends(get_db)):
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
async def logout(
    response: Response,
    request = Depends(),
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
):
    """Logout by clearing the httpOnly JWT cookie AND revoking the token.

    The JWT JTI (JWT ID) is extracted from both the cookie and the
    Authorization header (Bearer token) and inserted into the
    revoked_tokens table so that the token is rejected server-side even
    before it expires. This prevents replay attacks on stolen tokens
    from any authentication mechanism.
    """
    revoked_any = False

    # Revoke token from cookie
    token = request.cookies.get(JWT_COOKIE_NAME)
    if token:
        try:
            payload = AuthService.decode_token(token)
            jti = payload.get("jti")
            if jti:
                await db.execute(
                    text(
                        "INSERT INTO revoked_tokens (jti, user_id, reason, expires_at) "
                        "VALUES (:jti, :user_id, :reason, :expires_at) "
                        "ON CONFLICT (jti) DO NOTHING"
                    ).bindparams(
                        jti=jti,
                        user_id=str(payload.get("sub", "")),
                        reason="logout",
                        expires_at=datetime.now(timezone.utc)
                        + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
                    )
                )
                revoked_any = True
        except Exception:
            # Token may be expired or invalid — still clear the cookie
            pass

    # Revoke token from Authorization header (Bearer token)
    if authorization and authorization.startswith("Bearer "):
        bearer_token = authorization.split(" ", 1)[1]
        try:
            payload = AuthService.decode_token(bearer_token)
            jti = payload.get("jti")
            if jti:
                await db.execute(
                    text(
                        "INSERT INTO revoked_tokens (jti, user_id, reason, expires_at) "
                        "VALUES (:jti, :user_id, :reason, :expires_at) "
                        "ON CONFLICT (jti) DO NOTHING"
                    ).bindparams(
                        jti=jti,
                        user_id=str(payload.get("sub", "")),
                        reason="logout",
                        expires_at=datetime.now(timezone.utc)
                        + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
                    )
                )
                revoked_any = True
        except Exception:
            # Token may be expired or invalid — still proceed with logout
            pass

    if revoked_any:
        await db.commit()

    response.delete_cookie(
        key=JWT_COOKIE_NAME,
        path="/",
    )
    return {"message": "Logged out successfully"}


@router.get("/csrf-token")
async def get_csrf_token(response: Response):
    """Return a new CSRF token.

    The token is set as an httpOnly, Secure cookie and also returned in the
    JSON body so the frontend can read it and attach ``X-CSRF-Token`` to
    subsequent state-changing requests.
    """
    token = secrets_module.token_hex(32)
    response.set_cookie(
        key=CSRF_TOKEN_COOKIE,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=3600,
        path="/",
    )
    return {"csrf_token": token}
