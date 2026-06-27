"""Secrets API endpoints."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, or_, select
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
from app.routers.auth import get_current_user, get_current_user_info

router = APIRouter(prefix="/api/secrets", tags=["Secrets"])

# Rate limiter for secret access endpoints
_secret_limiter = Limiter(key_func=get_remote_address)


UserDep = Annotated[dict, Depends(get_current_user_info)]


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


async def check_secret_group_access(
    secret_group_id: int,
    user_id: int,
    db: AsyncSession,
    permission: str = "read",
):
    """Check if user has write access to a secret group.

    A user has access if they are the group owner or if one of their
    user groups has been granted access via SecretGroupMember.

    Raises HTTPException(403) if access is denied.
    """
    result = await db.execute(
        select(SecretGroup)
        .where(SecretGroup.id == secret_group_id, SecretGroup.is_active == True)
    )
    sg = result.scalar_one_or_none()

    if not sg:
        raise HTTPException(status_code=404, detail="Secret group not found")

    # Owner always has full access
    if sg.owner_id == user_id:
        return sg

    # Check access via group memberships
    result = await db.execute(
        select(SecretGroupMember)
        .where(
            SecretGroupMember.secret_group_id == secret_group_id,
            SecretGroupMember.permission == permission,
        )
        .join(UserGroup, UserGroup.group_id == SecretGroupMember.group_id)
        .where(UserGroup.user_id == user_id)
    )
    access = result.scalars().first()

    if access is None:
        raise HTTPException(status_code=403, detail="Access denied")

    return sg


@router.get("")
@_secret_limiter.limit("60/minute")
async def list_secrets(
    request: Request,
    user_info: UserDep,
    db: AsyncSession = Depends(get_db),
    group_id: int | None = Query(None),
    search: str | None = Query(None),
    secret_type: str | None = Query(None),
    view_mode: str | None = Query(None, description="personal|group|all. 'personal' returns only secrets in the user's personal group or in non-shared groups owned by the user."),
):
    """List secrets accessible to the current user.

    Only returns secrets that the user owns or has read access to via
    group memberships.

    Note: The username field is intentionally excluded from this endpoint
    to prevent information leakage. Username is only revealed when a user
    explicitly views a specific secret.

    Rate limited to 60 requests per minute to prevent enumeration attacks.
    """
    user_id = user_info["id"]

    # Build a query that returns only secrets the user can access:
    # 1. Secrets owned by the user
    # 2. Secrets in secret groups where a user group of this user has "read" access
    accessible_secret_ids = (
        select(Secret.id)
        .where(
            Secret.is_active == True,
            or_(
                Secret.owner_id == user_id,
                Secret.group_id.in_(
                    select(SecretGroupMember.secret_group_id).where(
                        SecretGroupMember.permission == "read"
                    ).join(
                        UserGroup,
                        UserGroup.group_id == SecretGroupMember.group_id,
                    ).where(
                        UserGroup.user_id == user_id,
                    )
                ),
            ),
        )
    )

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
        )
        .where(Secret.is_active == True)
        .where(Secret.id.in_(accessible_secret_ids))
        .order_by(Secret.updated_at.desc())
    )

    if view_mode == "personal":
        # Personal secrets: owned by user AND in personal group (is_personal=True)
        personal_query = (
            select(Secret.id)
            .where(
                Secret.is_active == True,
                Secret.owner_id == user_id,
                Secret.group_id.in_(
                    select(SecretGroup.id).where(
                        SecretGroup.owner_id == user_id,
                        SecretGroup.is_personal == True,
                    )
                ),
            )
        )
        query = query.where(Secret.id.in_(personal_query))

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
        }
        for s in secrets
    ]


@router.get("/{secret_id}", response_model=SecretViewResponse)
@_secret_limiter.limit("60/minute")
async def get_secret(
    secret_id: int,
    user_info: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get a single secret with decrypted data.

    Audited for compliance — every decryption is logged.

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

    # Audit: secret decryption/view
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_SECRET,
        "view",
        user_id,
        entity_id=secret.id,
        request=request,
        details=f"User {user_id} viewed decrypted secret '{secret.title}' (ID: {secret_id})",
    )

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
@_secret_limiter.limit("30/minute")
async def create_secret(
    secret_data: SecretCreate,
    user_info: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a new secret.

    The plaintext_data is encrypted server-side before being stored in the
    database. This ensures secrets are never stored in plaintext.

    Every secret must belong to a group. Personal secrets belong to the
    user's personal group.

    Rate limited to 30 requests per minute to prevent abuse.
    """
    user_id = user_info["id"]

    # Verify user has write access to the target secret group
    await check_secret_group_access(secret_data.group_id, user_id, db, permission="write")

    # Encrypt plaintext_data server-side before persisting
    encrypted = EncryptionService.encrypt(secret_data.plaintext_data)

    secret = Secret(
        title=secret_data.title,
        description=secret_data.description,
        secret_type=secret_data.secret_type,
        encrypted_data=encrypted,
        key_length=secret_data.key_length,
        username=secret_data.username,
        url=secret_data.url,
        group_id=secret_data.group_id,
        owner_id=user_id,
    )
    db.add(secret)
    await db.commit()
    await db.refresh(secret)

    # Audit: secret creation
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_SECRET,
        AuditService.OP_CREATE,
        user_id,
        entity_id=secret.id,
        request=request,
        details=f"Created secret '{secret_data.title}' (type={secret_data.secret_type})",
    )

    group_name = secret.group.name if secret.group else None

    return SecretResponse(
        id=secret.id,
        title=secret.title,
        description=secret.description,
        secret_type=secret.secret_type,
        key_length=secret.key_length,
        username=secret.username,
        url=secret.url,
        group_id=secret.group_id,
        group_name=group_name,
        is_active=secret.is_active,
        created_at=str(secret.created_at),
        updated_at=str(secret.updated_at),
    )


@router.put("/{secret_id}", response_model=SecretResponse)
@_secret_limiter.limit("30/minute")
async def update_secret(
    secret_id: int,
    secret_data: SecretUpdate,
    user_info: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update a secret.

    Any provided plaintext_data is encrypted server-side before being stored.

    Rate limited to 30 requests per minute to prevent abuse.
    """
    user_id = user_info["id"]
    secret = await check_secret_access(secret_id, user_id, db, permission="write")

    changes: list[str] = []
    if secret_data.title is not None:
        changes.append(f"title={secret_data.title}")
        secret.title = secret_data.title
    if secret_data.description is not None:
        changes.append(f"description={secret_data.description}")
        secret.description = secret_data.description
    if secret_data.plaintext_data is not None:
        secret.encrypted_data = EncryptionService.encrypt(secret_data.plaintext_data)
        changes.append("data=encrypted")
    if secret_data.key_length is not None:
        changes.append(f"key_length={secret_data.key_length}")
        secret.key_length = secret_data.key_length
    if secret_data.username is not None:
        changes.append(f"username={secret_data.username}")
        secret.username = secret_data.username
    if secret_data.url is not None:
        changes.append(f"url={secret_data.url}")
        secret.url = secret_data.url

    await db.commit()
    await db.refresh(secret)

    # Audit: secret update
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_SECRET,
        AuditService.OP_UPDATE,
        user_id,
        entity_id=secret.id,
        request=request,
        details=f"Updated secret '{secret.title}': {', '.join(changes)}",
    )

    return SecretResponse(
        id=secret.id,
        title=secret.title,
        description=secret.description,
        secret_type=secret.secret_type,
        key_length=secret.key_length,
        username=secret.username,
        url=secret.url,
        group_id=secret.group_id,
        is_active=secret.is_active,
        created_at=str(secret.created_at),
        updated_at=str(secret.updated_at),
    )


@router.delete("/{secret_id}", status_code=204)
@_secret_limiter.limit("30/minute")
async def delete_secret(
    secret_id: int,
    user_info: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a secret.

    Rate limited to 30 requests per minute to prevent mass deletion.
    """
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

    # Audit: secret deletion
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_SECRET,
        AuditService.OP_DELETE,
        user_id,
        entity_id=secret.id,
        request=request,
        details=f"Soft-deleted secret '{secret.title}'",
    )


@router.post("/ssh-key/generate", response_model=SSHKeyGenerateResponse)
async def generate_ssh_key(
    request_body: SSHKeyGenerateRequest,
    user_info: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Generate an SSH key pair.
    
    Key length is validated to prevent DoS attacks (2048-8192 bits).
    Comment is limited to 100 characters.
    
    Audited for compliance tracking.
    """
    user_id = user_info["id"]
    
    # Validate key_length to prevent resource exhaustion
    min_key_length = 2048
    max_key_length = 8192
    if request_body.key_length < min_key_length or request_body.key_length > max_key_length:
        raise HTTPException(
            status_code=400,
            detail=f"Key length must be between {min_key_length} and {max_key_length} bits",
        )
    
    # Validate comment length
    if len(request_body.comment) > 100:
        raise HTTPException(
            status_code=400,
            detail="Comment must not exceed 100 characters",
        )
    
    private_key, public_key, fingerprint = SecurityUtils.generate_ssh_key(
        request_body.key_length, request_body.comment
    )

    # The private key is intentionally NOT returned to prevent exposure
    # in logs, browser history, or network traffic.
    # The public key and fingerprint are returned for verification.

    # Audit: SSH key generation
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_API_TOKEN,
        AuditService.OP_SSH_KEY_GENERATE,
        user_id,
        request=request,
        details=f"Generated SSH key (length={request_body.key_length}, comment='{request_body.comment}', fingerprint={fingerprint})",
    )

    return SSHKeyGenerateResponse(
        public_key=public_key,
        fingerprint=fingerprint,
        key_length=request_body.key_length,
    )


@router.get("/{secret_id}/masked", response_model=SecretMaskedResponse)
@_secret_limiter.limit("60/minute")
async def get_secret_masked(
    secret_id: int,
    user_info: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get a secret with masked data (asterisks).

    Audited for compliance — even viewing masked data logs the access.

    Rate limited to 60 requests per minute to prevent enumeration.
    """
    user_id = user_info["id"]
    secret = await check_secret_access(secret_id, user_id, db, permission="read")

    # Get group name and owner username
    group_name = secret.group.name if secret.group else None
    owner_username = None
    if secret.owner:
        owner_username = secret.owner.username

    # Audit: secret masked view
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_SECRET,
        "view",
        user_id,
        entity_id=secret.id,
        request=request,
        details=f"User {user_id} viewed masked secret '{secret.title}' (ID: {secret_id})",
    )

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
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Reveal secret data with full audit logging.

    Audited for compliance — every decryption is logged with IP and timestamp.

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

    # Audit: secret reveal (decryption)
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_SECRET,
        "reveal",
        user_id,
        entity_id=secret.id,
        request=request,
        details=f"User {user_id} revealed (decrypted) secret '{secret.title}' (ID: {secret_id})",
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
        audit_id=secret.id,
        audit_event="secret_reveal",
        audit_timestamp=str(datetime.now(timezone.utc)),
        audit_ip=AuditService._extract_client_ip(request) if request else "unknown",
    )


@router.post("/{secret_id}/copy", response_model=SecretCopyResponse)
@_secret_limiter.limit("60/minute")
async def copy_secret(
    secret_id: int,
    user_info: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Copy secret data to clipboard with full audit logging.

    Audited for compliance — every decryption and copy is logged.

    Rate limited to 60 requests per minute to prevent data exfiltration.
    """
    user_id = user_info["id"]
    secret = await check_secret_access(secret_id, user_id, db, permission="read")

    # Decrypt the data
    decrypted_data = EncryptionService.decrypt(secret.encrypted_data)

    # Audit: secret copy (decryption + clipboard)
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_SECRET,
        "copy",
        user_id,
        entity_id=secret.id,
        request=request,
        details=f"User {user_id} copied (decrypted) secret '{secret.title}' (ID: {secret_id}) to clipboard",
    )

    return SecretCopyResponse(
        id=secret.id,
        title=secret.title,
        decrypted_data=decrypted_data,
        audit_id=secret.id,
        audit_event="secret_copy",
        audit_timestamp=str(datetime.now(timezone.utc)),
        audit_ip=AuditService._extract_client_ip(request) if request else "unknown",
    )
