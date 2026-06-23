"""Secrets API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.secret import Secret, SecretType
from app.models.secret_group import SecretGroup
from app.models.secret_group_member import SecretGroupMember
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
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/secrets", tags=["Secrets"])

# Rate limiter for secret access endpoints
_secret_limiter = Limiter(key_func=get_remote_address)


UserDep = Annotated[dict, Depends(get_current_user)]


async def check_secret_access(
    secret_id: int,
    user_id: int,
    db: AsyncSession,
    permission: str = "read",
):
    """Check if user has access to a secret via their groups.
    
    Args:
        secret_id: The secret ID to check
        user_id: The user ID
        db: Database session
        permission: Required permission level ("read" or "write")
    """
    result = await db.execute(
        select(Secret)
        .where(Secret.id == secret_id, Secret.is_active == True)
        .options(selectinload(Secret.group))
    )
    secret = result.scalar_one_or_none()

    if not secret:
        raise HTTPException(status_code=404, detail="Secret not found")

    # Check if user is owner (owner always has full access)
    if secret.owner_id == user_id:
        return secret

    # Check access via secret groups and their associated user groups
    result = await db.execute(
        select(SecretGroupMember)
        .join(SecretGroup, SecretGroupMember.secret_group_id == SecretGroup.id)
        .join(UserGroup, UserGroup.group_id == SecretGroupMember.group_id)
        .where(
            UserGroup.user_id == user_id,
            SecretGroup.id == secret.group_id,
            SecretGroupMember.permission == "read",
        )
    )
    read_access = result.scalars().all()

    if permission == "read" and read_access:
        return secret

    # Check for write access
    if permission == "write":
        result = await db.execute(
            select(SecretGroupMember)
            .join(SecretGroup, SecretGroupMember.secret_group_id == SecretGroup.id)
            .join(UserGroup, UserGroup.group_id == SecretGroupMember.group_id)
            .where(
                UserGroup.user_id == user_id,
                SecretGroup.id == secret.group_id,
                SecretGroupMember.permission == "write",
            )
        )
        write_access = result.scalars().all()
        if write_access:
            return secret

    raise HTTPException(status_code=403, detail="Access denied")


@router.get("")
async def list_secrets(
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
    group_id: int | None = Query(None),
    search: str | None = Query(None),
    secret_type: str | None = Query(None),
):
    """List secrets accessible to the current user.

    Note: The username field is intentionally excluded from this endpoint
    to prevent information leakage. Username is only revealed when a user
    explicitly views a specific secret.
    """
    user_id = user_info["id"]

    query = (
        select(
            Secret.id,
            Secret.title,
            Secret.description,
            Secret.secret_type,
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
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get a single secret with decrypted data."""
    user_id = user_info["id"]
    secret = await check_secret_access(secret_id, user_id, db, permission="read")

    # Decrypt the data
    decrypted_data = EncryptionService.decrypt(secret.encrypted_data)

    # Get group name and owner username
    group_name = secret.group.name if secret.group else None
    owner_username = None
    if secret.owner:
        owner_username = secret.owner.username

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
        owner_username=owner_username,
        is_active=secret.is_active,
        created_at=str(secret.created_at),
        updated_at=str(secret.updated_at),
    )


@router.post("", response_model=SecretResponse, status_code=201)
async def create_secret(
    secret_data: SecretCreate,
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Create a new secret."""
    user_id = user_info["id"]

    # Verify group exists
    result = await db.execute(
        select(SecretGroup).where(SecretGroup.id == secret_data.group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Secret group not found")

    # Check write access to the group
    await check_secret_access(secret_data.group_id, user_id, db, permission="write")

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
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Update a secret."""
    user_id = user_info["id"]
    secret = await check_secret_access(secret_id, user_id, db, permission="write")

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
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a secret."""
    user_id = user_info["id"]
    await check_secret_access(secret_id, user_id, db, permission="write")

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
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Generate an SSH key pair.
    
    Key length is validated to prevent DoS attacks (2048-8192 bits).
    Comment is limited to 100 characters.
    """
    user_id = user_info["id"]
    
    # Validate key_length to prevent resource exhaustion
    min_key_length = 2048
    max_key_length = 8192
    if request.key_length < min_key_length or request.key_length > max_key_length:
        raise HTTPException(
            status_code=400,
            detail=f"Key length must be between {min_key_length} and {max_key_length} bits",
        )
    
    # Validate comment length
    if len(request.comment) > 100:
        raise HTTPException(
            status_code=400,
            detail="Comment must not exceed 100 characters",
        )
    
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
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get a secret with masked data (asterisks). No audit event."""
    user_id = user_info["id"]
    secret = await check_secret_access(secret_id, user_id, db, permission="read")

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
@_secret_limiter.limit("60/minute")
async def reveal_secret(
    secret_id: int,
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Reveal secret data with full audit logging.

    Rate limited to 60 requests per minute to prevent data exfiltration.
    """
    user_id = user_info["id"]
    secret = await check_secret_access(secret_id, user_id, db, permission="read")

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
@_secret_limiter.limit("60/minute")
async def copy_secret(
    secret_id: int,
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Copy secret data to clipboard with full audit logging.

    Rate limited to 60 requests per minute to prevent data exfiltration.
    """
    user_id = user_info["id"]
    secret = await check_secret_access(secret_id, user_id, db, permission="read")

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
