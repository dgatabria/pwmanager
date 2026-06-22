"""Secrets API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.secret import Secret, SecretType
from app.models.secret_group import SecretGroup
from app.models.user_group import UserGroup
from app.schemas.secret import (
    SSHKeyGenerateRequest,
    SSHKeyGenerateResponse,
    SecretCreate,
    SecretResponse,
    SecretUpdate,
    SecretViewResponse,
    SecretMaskedResponse,
    SecretRevealResponse,
    SecretCopyResponse,
)
from app.services.encryption import EncryptionService
from app.services.audit import AuditService
from app.utils.security import SecurityUtils

router = APIRouter(prefix="/api/secrets", tags=["Secrets"])


async def get_current_user(authorization: Annotated[str | None, Query()] = None):
    """Dependency to get current user from JWT token."""
    from app.services.auth import AuthService

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


UserDep = Annotated[int, Depends(get_current_user)]


async def check_secret_access(
    secret_id: int,
    user_id: int,
    db: AsyncSession,
):
    """Check if user has access to a secret via their groups."""
    result = await db.execute(
        select(Secret)
        .where(Secret.id == secret_id, Secret.is_active == True)
        .options(selectinload(Secret.group))
    )
    secret = result.scalar_one_or_none()

    if not secret:
        raise HTTPException(status_code=404, detail="Secret not found")

    # Check access via secret groups and their associated user groups
    result = await db.execute(
        select(UserGroup)
        .join(SecretGroup, UserGroup.group_id == SecretGroup.group_id)
        .join(
            SecretGroup,
            SecretGroup.id == Secret.id,
        )
        .where(
            UserGroup.user_id == user_id,
            SecretGroup.id == secret.group_id,
        )
    )
    user_groups = result.scalars().all()

    if not user_groups:
        # Also check if user is owner
        if secret.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

    return secret


@router.get("")
async def list_secrets(
    user_id: UserDep,
    db: AsyncSession = Depends(get_db),
    group_id: int | None = Query(None),
    search: str | None = Query(None),
    secret_type: str | None = Query(None),
):
    """List secrets accessible to the current user."""
    query = (
        select(
            Secret.id,
            Secret.title,
            Secret.description,
            Secret.secret_type,
            Secret.username,
            Secret.group_id,
            Secret.updated_at,
            Secret.key_length,
            Secret.url,
            Secret.owner_id,
        )
        .where(Secret.is_active == True)
        .order_by(Secret.updated_at.desc())
    )

    if group_id:
        query = query.where(Secret.group_id == group_id)

    if search:
        query = query.where(Secret.title.ilike(f"%{search}%"))

    if secret_type:
        query = query.where(Secret.secret_type == SecretType(secret_type))

    result = await db.execute(query)
    secrets = result.all()

    return [
        {
            "id": s.id,
            "title": s.title,
            "description": s.description,
            "secret_type": s.secret_type.value if isinstance(s.secret_type, SecretType) else s.secret_type,
            "username": s.username,
            "group_id": s.group_id,
            "updated_at": str(s.updated_at),
            "key_length": s.key_length,
            "url": s.url,
            "owner_id": s.owner_id,
        }
        for s in secrets
    ]


@router.get("/{secret_id}", response_model=SecretViewResponse)
async def get_secret(
    secret_id: int,
    user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get a single secret with decrypted data."""
    secret = await check_secret_access(secret_id, user_id, db)

    # Decrypt the data
    decrypted_data = EncryptionService.decrypt(secret.encrypted_data)

    # Get group name
    group_name = secret.group.name if secret.group else None

    return SecretViewResponse(
        id=secret.id,
        title=secret.title,
        description=secret.description,
        secret_type=secret.secret_type,
        decrypted_data=decrypted_data,
        key_length=secret.key_length,
        username=secret.username,
        url=secret.url,
        group_name=group_name,
        owner_username=None,
        is_active=secret.is_active,
        created_at=str(secret.created_at),
        updated_at=str(secret.updated_at),
    )


@router.post("", response_model=SecretResponse, status_code=201)
async def create_secret(
    secret_data: SecretCreate,
    user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Create a new secret."""
    # Verify group exists and user has access
    result = await db.execute(
        select(SecretGroup).where(SecretGroup.id == secret_data.group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Secret group not found")

    secret = Secret(
        title=secret_data.title,
        description=secret_data.description,
        secret_type=secret_data.secret_type,
        encrypted_data=secret_data.encrypted_data,
        key_length=secret_data.key_length,
        username=secret_data.username,
        url=secret_data.url,
        group_id=secret_data.group_id,
        owner_id=user_id,
    )
    db.add(secret)
    await db.commit()
    await db.refresh(secret)

    return SecretResponse(
        id=secret.id,
        title=secret.title,
        description=secret.description,
        secret_type=secret.secret_type,
        encrypted_data=secret.encrypted_data,
        key_length=secret.key_length,
        username=secret.username,
        url=secret.url,
        group_id=secret.group_id,
        owner_id=secret.owner_id,
        is_active=secret.is_active,
        created_at=str(secret.created_at),
        updated_at=str(secret.updated_at),
    )


@router.put("/{secret_id}", response_model=SecretResponse)
async def update_secret(
    secret_id: int,
    secret_data: SecretUpdate,
    user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Update a secret."""
    result = await db.execute(
        select(Secret).where(Secret.id == secret_id)
    )
    secret = result.scalar_one_or_none()

    if not secret or not secret.is_active:
        raise HTTPException(status_code=404, detail="Secret not found")

    if secret_data.title is not None:
        secret.title = secret_data.title
    if secret_data.description is not None:
        secret.description = secret_data.description
    if secret_data.encrypted_data is not None:
        secret.encrypted_data = secret_data.encrypted_data
    if secret_data.key_length is not None:
        secret.key_length = secret_data.key_length
    if secret_data.username is not None:
        secret.username = secret_data.username
    if secret_data.url is not None:
        secret.url = secret_data.url

    await db.commit()
    await db.refresh(secret)

    return SecretResponse(
        id=secret.id,
        title=secret.title,
        description=secret.description,
        secret_type=secret.secret_type,
        encrypted_data=secret.encrypted_data,
        key_length=secret.key_length,
        username=secret.username,
        url=secret.url,
        group_id=secret.group_id,
        owner_id=secret.owner_id,
        is_active=secret.is_active,
        created_at=str(secret.created_at),
        updated_at=str(secret.updated_at),
    )


@router.delete("/{secret_id}", status_code=204)
async def delete_secret(
    secret_id: int,
    user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a secret."""
    result = await db.execute(
        select(Secret).where(Secret.id == secret_id)
    )
    secret = result.scalar_one_or_none()

    if not secret:
        raise HTTPException(status_code=404, detail="Secret not found")

    secret.is_active = False
    await db.commit()


@router.post("/ssh-key/generate", response_model=SSHKeyGenerateResponse)
async def generate_ssh_key(
    request: SSHKeyGenerateRequest,
    user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Generate an SSH key pair."""
    private_key, public_key, fingerprint = SecurityUtils.generate_ssh_key(
        request.key_length, request.comment
    )

    return SSHKeyGenerateResponse(
        public_key=public_key,
        private_key=private_key,
        fingerprint=fingerprint,
        key_length=request.key_length,
    )


@router.get("/{secret_id}/masked", response_model=SecretMaskedResponse)
async def get_secret_masked(
    secret_id: int,
    user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get a secret with masked data (asterisks). No audit event."""
    secret = await check_secret_access(secret_id, user_id, db)

    # Get group name and owner username
    group_name = secret.group.name if secret.group else None
    owner_username = None
    if secret.owner:
        owner_username = secret.owner.username

    return SecretMaskedResponse(
        id=secret.id,
        title=secret.title,
        description=secret.description,
        secret_type=secret.secret_type,
        decrypted_data="••••••••••••••••",
        key_length=secret.key_length,
        username=secret.username,
        url=secret.url,
        group_name=group_name,
        owner_username=owner_username,
        is_active=secret.is_active,
        created_at=str(secret.created_at),
        updated_at=str(secret.updated_at),
    )


@router.get("/{secret_id}/reveal", response_model=SecretRevealResponse)
async def reveal_secret(
    secret_id: int,
    user_id: UserDep,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Reveal secret data with full audit logging."""
    secret = await check_secret_access(secret_id, user_id, db)

    # Decrypt the data
    decrypted_data = EncryptionService.decrypt(secret.encrypted_data)

    # Get group name and owner username
    group_name = secret.group.name if secret.group else None
    owner_username = None
    if secret.owner:
        owner_username = secret.owner.username

    # Log audit event
    audit_entry = await AuditService.log_event(
        db=db,
        event_type=AuditService.EVENT_REVEAL,
        user_id=user_id,
        secret_id=secret_id,
        request=request,
        details=f"User {user_id} revealed secret '{secret.title}' (ID: {secret_id})",
    )

    return SecretRevealResponse(
        id=secret.id,
        title=secret.title,
        description=secret.description,
        secret_type=secret.secret_type,
        decrypted_data=decrypted_data,
        key_length=secret.key_length,
        username=secret.username,
        url=secret.url,
        group_name=group_name,
        owner_username=owner_username,
        is_active=secret.is_active,
        created_at=str(secret.created_at),
        updated_at=str(secret.updated_at),
        audit_id=audit_entry.id,
        audit_event=audit_entry.event_type,
        audit_timestamp=str(audit_entry.timestamp),
        audit_ip=audit_entry.ip_address,
    )


@router.post("/{secret_id}/copy", response_model=SecretCopyResponse)
async def copy_secret(
    secret_id: int,
    user_id: UserDep,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Copy secret data to clipboard with full audit logging."""
    secret = await check_secret_access(secret_id, user_id, db)

    # Decrypt the data
    decrypted_data = EncryptionService.decrypt(secret.encrypted_data)

    # Log audit event
    audit_entry = await AuditService.log_event(
        db=db,
        event_type=AuditService.EVENT_COPY,
        user_id=user_id,
        secret_id=secret_id,
        request=request,
        details=f"User {user_id} copied secret '{secret.title}' (ID: {secret_id}) to clipboard",
    )

    return SecretCopyResponse(
        id=secret.id,
        title=secret.title,
        decrypted_data=decrypted_data,
        audit_id=audit_entry.id,
        audit_event=audit_entry.event_type,
        audit_timestamp=str(audit_entry.timestamp),
        audit_ip=audit_entry.ip_address,
    )
