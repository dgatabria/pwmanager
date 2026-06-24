"""Backup and restore schemas."""

from pydantic import BaseModel


class BackupStatusResponse(BaseModel):
    """Response for backup status endpoint."""
    user_count: int
    group_count: int
    secret_count: int
    backup_count: int
    last_backup_at: str | None
    status: str
    message: str


class BackupInfo(BaseModel):
    """Info about a single backup."""
    backup_id: str
    filename: str
    created_at: str
    size_bytes: int
    status: str
    message: str


class BackupListResponse(BaseModel):
    """Response for backup list endpoint."""
    backups: list[BackupInfo]


class BackupExecuteResponse(BaseModel):
    """Response for backup execute endpoint."""
    message: str
    backup_id: str | None
    status: str


class BackupRestoreResponse(BaseModel):
    """Response for backup restore endpoint."""
    message: str
    status: str
    backup_id: str | None
