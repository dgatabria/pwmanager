"""FastAPI application for the Password Manager."""

import inspect
import secrets as secrets_module
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

# ─── Monkey-patch slowapi to preserve function signatures ───────────
# slowapi uses functools.wraps but inspect.signature() still sees
# the wrapper's (*args, **kwargs) signature. FastAPI uses
# inspect.signature() to determine endpoint parameters, so it
# interprets *args/**kwargs as query params "args" and "kwargs",
# causing 422 errors. This patch preserves the original signature.
# MUST be applied BEFORE importing routers (which apply the decorator).
import slowapi.extension
_original_limit = slowapi.extension.Limiter.limit


def _patched_limit(self, limit_value, key_func=None, per_method=False,
                   methods=None, error_message=None, cost=1,
                   override_defaults=True):
    decorator = _original_limit(self, limit_value, key_func, per_method,
                                methods, error_message, cost,
                                override_defaults)
    def patched_decorator(func):
        wrapped = decorator(func)
        # Preserve the original function signature for FastAPI
        if hasattr(wrapped, '__wrapped__'):
            wrapped.__signature__ = inspect.signature(func)
        return wrapped
    return patched_decorator


slowapi.extension.Limiter.limit = _patched_limit

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Import routers AFTER monkey-patch is applied
from app.routers.admin import router as admin_router
from app.routers.api_tokens import router as api_tokens_router
from app.routers.auth import router as auth_router
from app.routers.groups import router as groups_router
from app.routers.secret_groups import router as secret_groups_router
from app.routers.secrets import router as secrets_router
from app.services.maintenance import set_maintenance_mode, is_maintenance_mode

app = FastAPI(
    title="Password Manager API",
    description="Corporate Password Manager for intranet deployment",
    version="0.1.0",
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
)

# Rate limiter dependency
app.state.limiter = limiter

# ─── CSRF Protection ─────────────────────────────────────────────────
# Generates a cryptographically random token stored in a secure,
# httpOnly cookie and validated on all state-changing requests via
# the "X-CSRF-Token" header.  This protects cookie-based auth against
# CSRF attacks.

CSRF_TOKEN_COOKIE = "csrf_token"


async def csrf_protect(request: Request, call_next):
    """Middleware that validates CSRF tokens on unsafe HTTP methods."""
    # Safe methods never need CSRF validation.
    if request.method in ("GET", "HEAD", "OPTIONS"):
        response = await call_next(request)
        # Ensure the cookie is present so the frontend can read it.
        if CSRF_TOKEN_COOKIE not in request.cookies:
            _set_csrf_cookie(response)
        return response

    # Authentication endpoints do not require CSRF — they are the entry
    # point that establishes the session / cookie in the first place.
    auth_paths = ("/login", "/register", "/change-password", "/api/auth/login", "/api/auth/register", "/api/auth/change-password")
    if request.url.path in auth_paths:
        return await call_next(request)

    # For unsafe methods, require the CSRF token header.
    token = request.headers.get("x-csrf-token")
    cookie_token = request.cookies.get(CSRF_TOKEN_COOKIE)

    if not token or not cookie_token or not secrets_module.compare_digest(token, cookie_token):
        return JSONResponse(
            status_code=403,
            content={"detail": "CSRF token missing or invalid"},
        )

    response = await call_next(request)
    return response


def _set_csrf_cookie(response: Response) -> None:
    """Set a new CSRF token cookie if one is not already present."""
    if CSRF_TOKEN_COOKIE not in response.headers.get("set-cookie", ""):
        token = secrets_module.token_hex(32)
        response.set_cookie(
            key=CSRF_TOKEN_COOKIE,
            value=token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=3600,  # 1 hour
            path="/",
        )

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
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


# HTTPS enforcement — redirect HTTP → HTTPS in production.
# Skipped when HTTPS_ENFORCE is False (e.g., behind a reverse proxy
# that terminates TLS).  Also respects the X-Forwarded-Proto header
# so the middleware works correctly when the app is behind a proxy.
async def enforce_https(request: Request, call_next):
    """Redirect HTTP requests to HTTPS when configured."""
    if not settings.HTTPS_ENFORCE:
        return await call_next(request)

    # Only redirect non-health, non-API-root requests to avoid breaking
    # internal health checks that may not preserve the scheme.
    # Also skip auth endpoints so the frontend can reach them over HTTP
    # in local development where there is no TLS termination.
    if request.url.path in ("/", "/health", "/api/health"):
        return await call_next(request)
    if request.url.path.startswith("/api/auth/"):
        return await call_next(request)

    # Check the actual protocol — respect X-Forwarded-Proto for proxy setups.
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    if scheme != "https":
        # Build the HTTPS URL preserving host, port, path and query.
        url_str = str(request.url).replace("http://", "https://", 1)
        return JSONResponse(
            status_code=307,
            content={"detail": "Redirecting to HTTPS"},
            headers={"Location": url_str},
        )

    return await call_next(request)


app.middleware("http")(enforce_https)

# CSRF middleware — must run before CORS so the cookie is set correctly.
app.middleware("http")(csrf_protect)

# CORS - restricted to specific allowed origins from environment
_allowed_origins = settings.get_allowed_origins_list()
# When allow_credentials=True, allow_origins must NOT contain "*" or "*"
# wildcard patterns. Pydantic validation ensures origins are explicit URLs.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Api-Key", "X-CSRF-Token"],
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
