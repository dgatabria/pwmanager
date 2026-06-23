"""FastAPI application for the Password Manager."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers.admin import router as admin_router
from app.routers.api_tokens import router as api_tokens_router
from app.routers.auth import router as auth_router
from app.routers.groups import router as groups_router
from app.routers.secret_groups import router as secret_groups_router
from app.routers.secrets import router as secrets_router

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Password Manager API",
    description="Corporate Password Manager for intranet deployment",
    version="0.1.0",
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
)

# Rate limiter dependency
app.state.limiter = limiter

# ─── Maintenance Mode ───────────────────────────────────────────────
# Persistent flag stored in the database so it survives restarts and works
# correctly across multiple worker processes.
# Used during encryption key rotation to prevent data corruption.


async def set_maintenance_mode(active: bool) -> None:
    """Enable or disable maintenance mode (database-backed)."""
    from app.database import async_session
    from app.models.app_settings import AppSettings

    async with async_session() as session:
        result = await session.execute(
            AppSettings.__table__.select().limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = AppSettings(maintenance_mode=active)
            session.add(row)
        else:
            row.maintenance_mode = active
        await session.commit()


async def is_maintenance_mode() -> bool:
    """Check if the application is in maintenance mode (database-backed)."""
    from app.database import async_session
    from app.models.app_settings import AppSettings

    async with async_session() as session:
        result = await session.execute(
            AppSettings.__table__.select().limit(1)
        )
        row = result.scalar_one_or_none()
        return row.maintenance_mode if row else False


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses.

    Removes the deprecated X-XSS-Protection header (deprecated in all modern
    browsers and can introduce XSS vulnerabilities in Chrome). Adds
    Referrer-Policy and Permissions-Policy for defence-in-depth.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # X-XSS-Protection removed: deprecated and can introduce XSS vulnerabilities
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


# CORS - restricted to specific allowed origins from environment
_allowed_origins = settings.get_allowed_origins_list()
# When allow_credentials=True, allow_origins must NOT contain "*" or "*"
# wildcard patterns. Pydantic validation ensures origins are explicit URLs.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Api-Key"],
)

# Register routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(api_tokens_router)
app.include_router(groups_router)
app.include_router(secret_groups_router)
app.include_router(secrets_router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "password-manager"}
