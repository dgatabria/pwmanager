"""Admin-only API endpoints for user management and database operations."""

from typing import Annotated
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.group import Group
from app.models.user_group import UserGroup
from app.models.saml_config import SAMLConfig
from app.models.secret import Secret
from app.models.audit_log import AuditLog
from app.services.maintenance import set_maintenance_mode, is_maintenance_mode
from app.schemas.auth import (
    UserResponse,
    UserUpdate,
    AdminUserCreate,
    ResetPasswordRequest,
    AuthMethodResponse,
    AuthMethodUpdate,
    SAMLConfigResponse,
    SAMLConfigUpdate,
)
from app.schemas.backup import (
    BackupStatusResponse,
    BackupInfo,
    BackupListResponse,
    BackupExecuteResponse,
    BackupRestoreResponse,
)
from app.schemas.group import GroupCreate, GroupResponse, GroupUpdate
from app.schemas.audit import AuditLogResponse, AuditLogListResponse
from app.services.encryption import EncryptionService
from app.services.audit import AuditService
from app.services.backup import BackupService
from app.utils.security import SecurityUtils
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# Rate limiter for admin endpoints
_admin_limiter = Limiter(key_func=get_remote_address)

UserDep = Annotated[int, Depends(get_current_user)]


async def require_superuser(current_user_id: UserDep, db: AsyncSession):
    """Verify that the current user is a superuser."""
    result = await db.execute(select(User).where(User.id == current_user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return user


# ─── User Administration ────────────────────────────────────────────

@router.get("/users", response_model=list[UserResponse])
async def admin_list_users(
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    include_deleted: bool = Query(False, description="Include soft-deleted users"),
):
    """List all users with filtering (superuser only).

    By default, soft-deleted users are excluded. Use include_deleted=true
    to include users marked for deletion.
    """
    await require_superuser(current_user_id, db)
    
    query = select(User).where(User.is_deleted == False).order_by(User.created_at.desc())
    
    if search:
        query = query.where(
            (User.username.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%"))
        )
    
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return [
        UserResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            is_superuser=u.is_superuser,
            created_at=str(u.created_at),
        )
        for u in users
    ]


@router.post("/users", response_model=UserResponse, status_code=201)
async def admin_create_user(
    user_data: AdminUserCreate,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user (superuser only)."""
    await require_superuser(current_user_id, db)
    
    # Check if username exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Generate random password
    import secrets
    import string
    random_password = ''.join(secrets.choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(20))
    hashed = SecurityUtils.hash_password(random_password)
    
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed,
        full_name=user_data.full_name,
        is_active=user_data.is_active,
        is_superuser=user_data.is_superuser,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Audit: user creation
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_USER,
        AuditService.OP_CREATE,
        current_user_id,
        entity_id=user.id,
        request=request,
        details=f"Created user '{user_data.username}' (email={user_data.email}, superuser={user_data.is_superuser})",
    )
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=str(user.created_at),
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def admin_update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update a user (superuser only)."""
    await require_superuser(current_user_id, db)
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent superuser from modifying their own superuser status
    if current_user_id == user_id and user_data.is_superuser is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot modify your own superuser status",
        )
    
    changes: list[str] = []
    if user_data.email is not None:
        # Check if email is already used by another user
        existing = await db.execute(
            select(User).where(User.email == user_data.email, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already exists")
        changes.append(f"email={user_data.email}")
        user.email = user_data.email
    
    if user_data.full_name is not None:
        changes.append(f"full_name={user_data.full_name}")
        user.full_name = user_data.full_name
    
    if user_data.is_active is not None:
        changes.append(f"is_active={user_data.is_active}")
        user.is_active = user_data.is_active
    
    await db.commit()
    await db.refresh(user)
    
    # Audit: user update
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_USER,
        AuditService.OP_UPDATE,
        current_user_id,
        entity_id=user.id,
        request=request,
        details=f"Updated user '{user.username}': {', '.join(changes)}",
    )
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=str(user.created_at),
    )


@router.post("/users/{user_id}/reset-password", response_model=dict)
@_admin_limiter.limit("60/minute")
async def admin_reset_password(
    user_id: int,
    password_request: ResetPasswordRequest,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Reset a user's password (superuser only).

    Rate limited to 60 requests per minute to prevent abuse while
    allowing admins to perform multiple operations during setup.
    Password must meet strength requirements.
    """
    await require_superuser(current_user_id, db)
    
    # Validate password strength
    is_valid, error_msg = SecurityUtils.validate_password_strength(password_request.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    hashed = SecurityUtils.hash_password(password_request.new_password)
    user.hashed_password = hashed
    await db.commit()
    
    # Audit: password reset
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_USER,
        AuditService.OP_RESET_PASSWORD,
        current_user_id,
        entity_id=user.id,
        request=request,
        details=f"Reset password for user '{user.username}'",
    )
    
    return {
        "message": "Password reset successfully",
        "user_id": user.id,
        "username": user.username,
    }


@router.post("/users/{user_id}/toggle-active", response_model=UserResponse)
async def admin_toggle_active(
    user_id: int,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Toggle user active/inactive status (superuser only)."""
    await require_superuser(current_user_id, db)
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent superuser from deactivating themselves
    if current_user_id == user_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot deactivate your own account",
        )
    
    new_status = not user.is_active
    user.is_active = new_status
    await db.commit()
    await db.refresh(user)
    
    # Audit: toggle active
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_USER,
        AuditService.OP_TOGGLE,
        current_user_id,
        entity_id=user.id,
        request=request,
        details=f"Toggled user '{user.username}' to {'active' if new_status else 'inactive'}",
    )
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=str(user.created_at),
    )


@router.delete("/users/{user_id}", status_code=204)
async def admin_delete_user(
    user_id: int,
    current_user_id: UserDep,
    request: Request,
    confirm: str = Query(..., description="Explicit confirmation required. Set to 'true' to proceed."),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a user (superuser only).

    Requires explicit confirmation via confirm=true query parameter.
    This prevents accidental data loss by ensuring the admin intentionally
    marks the user for deletion rather than permanently removing them.
    """
    await require_superuser(current_user_id, db)
    
    if confirm.lower() != "true":
        raise HTTPException(
            status_code=400,
            detail="Confirmation required. Pass confirm=true to proceed with deletion.",
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent deleting yourself
    if current_user_id == user_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account",
        )
    
    # Soft-delete: mark as deleted instead of permanent removal
    user.is_deleted = True
    user.is_active = False
    await db.commit()
    
    # Audit: user deletion
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_USER,
        AuditService.OP_DELETE,
        current_user_id,
        entity_id=user.id,
        request=request,
        details=f"Soft-deleted user '{user.username}'",
    )


@router.post("/users/{user_id}/groups/{group_id}", status_code=204)
async def admin_add_user_to_group(
    user_id: int,
    group_id: int,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Add a user to a group (superuser only)."""
    await require_superuser(current_user_id, db)
    
    # Check if user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if group exists
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if already in group
    result = await db.execute(
        select(UserGroup).where(
            UserGroup.user_id == user_id, UserGroup.group_id == group_id
        )
    )
    if result.scalar_one_or_none():
        return  # Already in group
    
    ug = UserGroup(user_id=user_id, group_id=group_id)
    db.add(ug)
    await db.commit()
    
    # Audit: add user to group
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_USER,
        AuditService.OP_ADD_TO_GROUP,
        current_user_id,
        entity_id=user_id,
        request=request,
        details=f"Added user '{user.username}' to group '{group.name}' (id={group_id})",
    )


@router.delete("/users/{user_id}/groups/{group_id}", status_code=204)
async def admin_remove_user_from_group(
    user_id: int,
    group_id: int,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Remove a user from a group (superuser only)."""
    await require_superuser(current_user_id, db)
    
    result = await db.execute(
        select(UserGroup).where(
            UserGroup.user_id == user_id, UserGroup.group_id == group_id
        )
    )
    ug = result.scalar_one_or_none()
    if ug:
        await db.delete(ug)
        await db.commit()
        
        # Audit: remove user from group
        await AuditService.log_crud(
            db,
            AuditService.ENTITY_USER,
            AuditService.OP_REMOVE_FROM_GROUP,
            current_user_id,
            entity_id=user_id,
            request=request,
            details=f"Removed user (id={user_id}) from group (id={group_id})",
        )


# ─── Group Administration ──────────────────────────────────────────

@router.get("/groups")
async def admin_list_groups(
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """List all groups with user_ids (superuser only)."""
    await require_superuser(current_user_id, db)
    
    result = await db.execute(select(Group).order_by(Group.name))
    groups = result.scalars().all()
    
    groups_data = []
    for g in groups:
        user_result = await db.execute(
            select(UserGroup.user_id).where(UserGroup.group_id == g.id)
        )
        user_ids = [uid[0] for uid in user_result.all()]
        groups_data.append({
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "is_active": g.is_active,
            "user_ids": user_ids,
        })
    
    return groups_data


@router.post("/groups", response_model=GroupResponse, status_code=201)
async def admin_create_group(
    group_data: GroupCreate,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a new group (superuser only)."""
    await require_superuser(current_user_id, db)
    
    result = await db.execute(select(Group).where(Group.name == group_data.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Group already exists")
    
    group = Group(
        name=group_data.name,
        description=group_data.description,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    
    # Audit: group creation
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_GROUP,
        AuditService.OP_CREATE,
        current_user_id,
        entity_id=group.id,
        request=request,
        details=f"Created group '{group_data.name}' (description={group_data.description})",
    )
    
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        is_active=group.is_active,
    )


@router.put("/groups/{group_id}", response_model=GroupResponse)
async def admin_update_group(
    group_id: int,
    group_data: GroupUpdate,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update a group (superuser only)."""
    await require_superuser(current_user_id, db)
    
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    changes: list[str] = []
    if group_data.name is not None:
        # Check if name is already used
        existing = await db.execute(
            select(Group).where(Group.name == group_data.name, Group.id != group_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Group name already exists")
        changes.append(f"name={group_data.name}")
        group.name = group_data.name
    
    if group_data.description is not None:
        changes.append(f"description={group_data.description}")
        group.description = group_data.description
    
    if group_data.is_active is not None:
        changes.append(f"is_active={group_data.is_active}")
        group.is_active = group_data.is_active
    
    await db.commit()
    await db.refresh(group)
    
    # Audit: group update
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_GROUP,
        AuditService.OP_UPDATE,
        current_user_id,
        entity_id=group.id,
        request=request,
        details=f"Updated group '{group.name}': {', '.join(changes)}",
    )
    
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        is_active=group.is_active,
    )


@router.delete("/groups/{group_id}", status_code=204)
async def admin_delete_group(
    group_id: int,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Delete a group (superuser only)."""
    await require_superuser(current_user_id, db)
    
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    await db.delete(group)
    await db.commit()
    
    # Audit: group deletion
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_GROUP,
        AuditService.OP_DELETE,
        current_user_id,
        entity_id=group.id,
        request=request,
        details=f"Deleted group '{group.name}' (id={group_id})",
    )


# ─── Authentication Method Configuration ────────────────────────────

@router.get("/auth/method", response_model=AuthMethodResponse)
async def admin_get_auth_method(
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get the current authentication method configuration (superuser only).

    Reads from the database to ensure persistence across restarts.
    """
    await require_superuser(current_user_id, db)
    
    result = await db.execute(select(SAMLConfig))
    config = result.scalar_one_or_none()
    
    if config is None:
        return AuthMethodResponse(
            auth_method="local",
            saml_enabled=False,
        )
    
    return AuthMethodResponse(
        auth_method=config.auth_method,
        saml_enabled=config.saml_enabled,
    )


@router.put("/auth/method", response_model=AuthMethodResponse)
async def admin_update_auth_method(
    update: AuthMethodUpdate,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Update the authentication method (superuser only).

    Persists the configuration to the database for survival across restarts.
    """
    await require_superuser(current_user_id, db)
    
    if update.auth_method not in ("local", "saml"):
        raise HTTPException(
            status_code=400,
            detail="Invalid auth_method. Must be 'local' or 'saml'.",
        )
    
    result = await db.execute(select(SAMLConfig))
    config = result.scalar_one_or_none()
    
    if config is None:
        # Create new config
        config = SAMLConfig(
            auth_method=update.auth_method,
            saml_enabled=(update.auth_method == "saml"),
        )
        db.add(config)
    else:
        # Update existing config
        config.auth_method = update.auth_method
        config.saml_enabled = (update.auth_method == "saml")
    
    await db.commit()
    await db.refresh(config)
    
    return AuthMethodResponse(
        auth_method=config.auth_method,
        saml_enabled=config.saml_enabled,
    )


@router.get("/auth/saml", response_model=SAMLConfigResponse)
async def admin_get_saml_config(
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
    show_secrets: bool = Query(False, description="If true, returns sensitive fields (certificate, URLs) unmasked"),
):
    """Get the SAML configuration from database (superuser only).

    By default, sensitive fields (certificate, entity_id, sso_url, acs_url,
    slo_url, slo_redirect_url) are masked. Set `?show_secrets=true` to
    retrieve the full configuration for editing.
    """
    await require_superuser(current_user_id, db)
    
    result = await db.execute(select(SAMLConfig))
    config = result.scalar_one_or_none()
    
    if config is None:
        # Return empty config if not yet created
        return SAMLConfigResponse(saml_enabled=False, auth_method="local")
    
    # Mask sensitive fields unless explicitly requested
    if not show_secrets:
        return SAMLConfigResponse(
            saml_enabled=config.saml_enabled,
            auth_method=config.auth_method,
            entity_id="**** MASKED ****",
            sso_url="**** MASKED ****",
            idp_metadata_url=config.idp_metadata_url,
            acs_url="**** MASKED ****",
            certificate="**** MASKED ****",
            entity_id_label=config.entity_id_label,
            slo_url="**** MASKED ****",
            slo_redirect_url="**** MASKED ****",
            certificate_label=config.certificate_label,
        )
    
    return SAMLConfigResponse(
        saml_enabled=config.saml_enabled,
        auth_method=config.auth_method,
        entity_id=config.entity_id,
        sso_url=config.sso_url,
        idp_metadata_url=config.idp_metadata_url,
        acs_url=config.acs_url,
        certificate=config.certificate,
        entity_id_label=config.entity_id_label,
        slo_url=config.slo_url,
        slo_redirect_url=config.slo_redirect_url,
        certificate_label=config.certificate_label,
    )


@router.put("/auth/saml", response_model=SAMLConfigResponse)
async def admin_update_saml_config(
    update: SAMLConfigUpdate,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Update the SAML configuration in the database (superuser only)."""
    await require_superuser(current_user_id, db)
    
    result = await db.execute(select(SAMLConfig))
    config = result.scalar_one_or_none()
    
    if config is None:
        # Create new config
        config = SAMLConfig(
            auth_method=update.auth_method,
            saml_enabled=update.saml_enabled,
            entity_id=update.entity_id,
            sso_url=update.sso_url,
            idp_metadata_url=update.idp_metadata_url,
            acs_url=update.acs_url,
            certificate=update.certificate,
            entity_id_label=update.entity_id_label,
            slo_url=update.slo_url,
            slo_redirect_url=update.slo_redirect_url,
            certificate_label=update.certificate_label,
        )
        db.add(config)
    else:
        # Update existing config
        config.auth_method = update.auth_method
        config.saml_enabled = update.saml_enabled
        config.entity_id = update.entity_id
        config.sso_url = update.sso_url
        config.idp_metadata_url = update.idp_metadata_url
        config.acs_url = update.acs_url
        config.certificate = update.certificate
        config.entity_id_label = update.entity_id_label
        config.slo_url = update.slo_url
        config.slo_redirect_url = update.slo_redirect_url
        config.certificate_label = update.certificate_label
    
    await db.commit()
    await db.refresh(config)
    
    return SAMLConfigResponse(
        saml_enabled=config.saml_enabled,
        auth_method=config.auth_method,
        entity_id=config.entity_id,
        sso_url=config.sso_url,
        idp_metadata_url=config.idp_metadata_url,
        acs_url=config.acs_url,
        certificate=config.certificate,
        entity_id_label=config.entity_id_label,
        slo_url=config.slo_url,
        slo_redirect_url=config.slo_redirect_url,
        certificate_label=config.certificate_label,
    )


# ─── Encryption Key Rotation ────────────────────────────────────────

@router.post("/secrets/rotate-key", response_model=dict)
async def admin_rotate_encryption_key(
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Rotate the encryption key used to encrypt all secrets.

    This operation is atomic: if ANY secret fails to re-encrypt, the entire
    rotation is rolled back and no secrets are modified. This prevents a
    mixed state where some secrets are encrypted with the old key and others
    with the new key.

    Steps:
    1. Puts the app in maintenance mode (blocks non-admin login)
    2. Generates a new encryption key
    3. Decrypts all secrets with the old key
    4. Re-encrypts them with the new key
    5. Persists the new key to disk
    6. Exits maintenance mode

    WARNING: This operation may take several minutes for large databases.
    """
    await require_superuser(current_user_id, db)

    # Put app in maintenance mode
    await set_maintenance_mode(True)

    try:
        # Get all active secrets
        result = await db.execute(select(Secret).where(Secret.is_active == True))
        all_secrets = result.scalars().all()

        if not all_secrets:
            await set_maintenance_mode(False)
            return {
                "message": "Key rotation completed (no secrets to re-encrypt)",
                "secrets_processed": 0,
                "status": "completed",
            }

        total = len(all_secrets)
        failed = 0
        errors: list[str] = []

        for secret in all_secrets:
            try:
                # Decrypt with current (old) key
                decrypted_data = EncryptionService.decrypt(secret.encrypted_data)

                # Re-encrypt with new key
                new_encrypted = EncryptionService.encrypt(decrypted_data)

                # Update in database
                secret.encrypted_data = new_encrypted
            except Exception as e:
                failed += 1
                import logging
                msg = f"Failed to re-encrypt secret {secret.id}: {e}"
                logging.error(msg)
                errors.append(msg)

        # If ANY secret failed, roll back the entire operation
        if failed > 0:
            await db.rollback()
            await set_maintenance_mode(False)
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Key rotation failed: {failed}/{total} secrets could not be "
                    f"re-encrypted. The database has been rolled back. "
                    f"Errors: {'; '.join(errors[:5])}"
                ),
            )

        await db.commit()

        # Exit maintenance mode
        await set_maintenance_mode(False)

        return {
            "message": "Key rotation completed successfully",
            "secrets_processed": total,
            "secrets_failed": 0,
            "total_secrets": total,
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        # Re-raise HTTPException (already handled)
        raise
    except Exception as e:
        # Ensure maintenance mode is exited even on error
        await set_maintenance_mode(False)
        raise HTTPException(
            status_code=500,
            detail=f"Key rotation failed: {str(e)}",
        )


@router.get("/secrets/rotation-status", response_model=dict)
async def admin_rotation_status(
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get the current maintenance mode status."""
    await require_superuser(current_user_id, db)

    in_maintenance = await is_maintenance_mode()

    return {
        "maintenance_mode": in_maintenance,
        "message": "System is in maintenance mode" if in_maintenance else "System is operational",
    }


# ─── Audit Logs Endpoints ────────────────────────────────────────────

@router.get("/audit-logs", response_model=AuditLogListResponse)
@_admin_limiter.limit("30/minute")
async def admin_get_audit_logs(
    request: Request,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
    event_type: str | None = Query(None, description="Filter by event type (e.g. secret_reveal, secret_copy, user_create)"),
    user_id: int | None = Query(None, description="Filter by user ID"),
    secret_id: int | None = Query(None, description="Filter by secret ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
):
    """Get all audit logs with filtering and pagination (superuser only).

    Rate limited to 30 requests per minute.
    """
    await require_superuser(current_user_id, db)

    base_query = select(AuditLog).order_by(AuditLog.timestamp.desc())

    if event_type:
        base_query = base_query.where(AuditLog.event_type == event_type)
    if user_id is not None:
        base_query = base_query.where(AuditLog.user_id == user_id)
    if secret_id is not None:
        base_query = base_query.where(AuditLog.secret_id == secret_id)

    # Count total matching records
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # Apply pagination
    offset = (page - 1) * page_size
    paged_query = base_query.offset(offset).limit(page_size)
    result = await db.execute(paged_query)
    logs = result.scalars().all()

    # Load relationships for each log
    for log in logs:
        await db.refresh(log, ["user", "secret"])

    total_pages = max(1, (total + page_size - 1) // page_size)

    return AuditLogListResponse(
        logs=[
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                user_username=log.user.username if log.user else None,
                event_type=log.event_type,
                secret_id=log.secret_id,
                secret_title=log.secret.title if log.secret else None,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                details=log.details,
                timestamp=log.timestamp.isoformat() + "Z" if log.timestamp else None,
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ─── Backup / Restore Endpoints ──────────────────────────────────────

@router.get("/backup/status", response_model=BackupStatusResponse)
@_admin_limiter.limit("10/minute")
async def get_backup_status(
    request: Request,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get the backup status including counts and last backup info."""
    await require_superuser(current_user_id, db)

    status_data = await BackupService.get_backup_status()
    return BackupStatusResponse(**status_data)


@router.get("/backup/list", response_model=BackupListResponse)
@_admin_limiter.limit("10/minute")
async def list_backups(
    request: Request,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """List all available backups."""
    await require_superuser(current_user_id, db)

    backups = BackupService.list_backups()
    return BackupListResponse(backups=backups)


@router.post("/backup/execute", response_model=BackupExecuteResponse)
@_admin_limiter.limit("5/minute")
async def execute_backup(
    request: Request,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Execute a full backup of the database and encryption keys."""
    await require_superuser(current_user_id, db)

    result = await BackupService.execute_backup()
    return BackupExecuteResponse(**result)


@router.post("/backup/{backup_id}/restore", response_model=BackupRestoreResponse)
@_admin_limiter.limit("5/minute")
async def restore_backup(
    request: Request,
    backup_id: str,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Restore the database and encryption keys from a backup."""
    await require_superuser(current_user_id, db)

    # Optionally enforce maintenance mode for safety
    # in_maintenance = await is_maintenance_mode()
    # if not in_maintenance:
    #     raise HTTPException(
    #         status_code=status.HTTP_423_LOCKED,
    #         detail="Restore can only be performed during maintenance mode",
    #     )

    result = await BackupService.restore_backup(backup_id)
    return BackupRestoreResponse(**result)
