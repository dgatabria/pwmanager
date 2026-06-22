"""FastAPI application for the Password Manager."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.api_tokens import router as api_tokens_router
from app.routers.auth import router as auth_router
from app.routers.groups import router as groups_router
from app.routers.secret_groups import router as secret_groups_router
from app.routers.secrets import router as secrets_router

app = FastAPI(
    title="Password Manager API",
    description="Corporate Password Manager for intranet deployment",
    version="0.1.0",
)

# CORS for intranet frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(api_tokens_router)
app.include_router(groups_router)
app.include_router(secret_groups_router)
app.include_router(secrets_router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "password-manager"}
