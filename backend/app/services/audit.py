"""Audit logging service for tracking secret access events."""

from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.audit_log import AuditLog


class AuditService:
    """Service for creating and querying audit logs."""

    EVENT_REVEAL = "secret_reveal"
    EVENT_COPY = "secret_copy"
    EVENT_VIEW = "secret_view"

    @staticmethod
    def _is_trusted_proxy(request: Request) -> bool:
        """Check if the request comes from a trusted proxy.

        If TRUSTED_PROXY_IPS is configured, only requests from those IPs
        are allowed to set X-Forwarded-For. Otherwise, all proxies are
        trusted (backward-compatible default).
        """
        trusted_ips = settings.get_trusted_proxy_ips()
        if not trusted_ips:
            # No trusted proxies configured — trust all (backward-compatible)
            return True

        # Check the direct connection IP against the trusted list
        if request.client:
            return request.client.host in trusted_ips

        return False

    @staticmethod
    def _extract_client_ip(request: Request) -> str:
        """Extract real client IP from request, handling proxies.

        X-Forwarded-For is only trusted when the request originates from
        a known reverse proxy IP (configured via TRUSTED_PROXY_IPS).
        Otherwise, the direct connection IP is used to prevent spoofing.
        """
        # Only trust X-Forwarded-For if the request comes from a trusted proxy
        if AuditService._is_trusted_proxy(request):
            forwarded_for = request.headers.get("x-forwarded-for")
            if forwarded_for:
                return forwarded_for.split(",")[0].strip()

            real_ip = request.headers.get("x-real-ip")
            if real_ip:
                return real_ip

        # Fall back to direct connection IP (untrusted proxy or no proxy)
        if request.client:
            return request.client.host

        return "unknown"

    @staticmethod
    def _extract_user_agent(request: Request) -> str:
        """Extract user agent from request."""
        return request.headers.get("user-agent", "unknown")[:500]

    @staticmethod
    async def log_event(
        db: AsyncSession,
        event_type: str,
        user_id: int | None,
        secret_id: int | None,
        request: Request,
        details: str | None = None,
    ) -> AuditLog:
        """Create an audit log entry for a secret access event."""
        audit_entry = AuditLog(
            user_id=user_id,
            event_type=event_type,
            secret_id=secret_id,
            ip_address=AuditService._extract_client_ip(request),
            user_agent=AuditService._extract_user_agent(request),
            details=details,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(audit_entry)
        await db.commit()
        await db.refresh(audit_entry)
        return audit_entry

    @staticmethod
    async def get_user_audit_logs(
        db: AsyncSession,
        user_id: int,
        limit: int = 50,
    ) -> list[AuditLog]:
        """Get audit logs for a specific user."""
        from app.models.user import User

        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_secret_audit_logs(
        db: AsyncSession,
        secret_id: int,
        limit: int = 50,
    ) -> list[AuditLog]:
        """Get audit logs for a specific secret."""
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.secret_id == secret_id)
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_all_audit_logs(
        db: AsyncSession,
        limit: int = 100,
        event_type: str | None = None,
    ) -> list[AuditLog]:
        """Get all audit logs, optionally filtered by event type."""
        query = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)

        if event_type:
            query = query.where(AuditLog.event_type == event_type)

        result = await db.execute(query)
        return result.scalars().all()
