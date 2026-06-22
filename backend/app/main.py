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
)

# Rate limiter dependency
app.state.limiter = limiter

# ─── Maintenance Mode ───────────────────────────────────────────────
# Global flag: when True, blocks non-admin login and normal API access.
# Used during encryption key rotation to prevent data corruption.
_maintenance_mode: bool = False


def set_maintenance_mode(active: bool) -> None:
    """Enable or disable maintenance mode."""
    global _maintenance_mode
    _maintenance_mode = active


def is_maintenance_mode() -> bool:
    """Check if the application is in maintenance mode."""
    return _maintenance_mode


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


# CORS - restricted to specific allowed origins from environment
_allowed_origins = settings.get_allowed_origins_list()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
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
