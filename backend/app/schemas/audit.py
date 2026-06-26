"""Audit log schemas."""

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    user_username: str | None
    event_type: str
    secret_id: int | None
    secret_title: str | None
    ip_address: str | None
    user_agent: str | None
    details: str | None
    timestamp: str | None


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
