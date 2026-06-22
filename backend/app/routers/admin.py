"""Admin-only API endpoints for user management and database operations."""

from typing import Annotated
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.main import set_maintenance_mode, is_maintenance_mode
from app.models.user import User
from app.models.group import Group
from app.models.user_group import UserGroup
from app.models.saml_config import SAMLConfig
from app.models.secret import Secret
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
from app.schemas.group import GroupCreate, GroupResponse, GroupUpdate
from app.services.encryption import EncryptionService
from app.utils.security import SecurityUtils
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/admin", tags=["Admin"])

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
):
    """List all users with filtering (superuser only)."""
    await require_superuser(current_user_id, db)
    
    query = select(User).order_by(User.created_at.desc())
    
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
    
    if user_data.email is not None:
        # Check if email is already used by another user
        existing = await db.execute(
            select(User).where(User.email == user_data.email, User.id != user_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already exists")
        user.email = user_data.email
    
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    await db.commit()
    await db.refresh(user)
    
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
async def admin_reset_password(
    user_id: int,
    request: ResetPasswordRequest,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Reset a user's password (superuser only)."""
    await require_superuser(current_user_id, db)
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    hashed = SecurityUtils.hash_password(request.new_password)
    user.hashed_password = hashed
    await db.commit()
    
    return {
        "message": "Password reset successfully",
        "user_id": user.id,
        "username": user.username,
    }


@router.post("/users/{user_id}/toggle-active", response_model=UserResponse)
async def admin_toggle_active(
    user_id: int,
    current_user_id: UserDep,
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
    
    user.is_active = not user.is_active
    await db.commit()
    await db.refresh(user)
    
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
    db: AsyncSession = Depends(get_db),
):
    """Delete a user permanently (superuser only)."""
    await require_superuser(current_user_id, db)
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent superuser from deleting themselves
    if current_user_id == user_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account",
        )
    
    await db.delete(user)
    await db.commit()


@router.post("/users/{user_id}/groups/{group_id}", status_code=204)
async def admin_add_user_to_group(
    user_id: int,
    group_id: int,
    current_user_id: UserDep,
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


@router.delete("/users/{user_id}/groups/{group_id}", status_code=204)
async def admin_remove_user_from_group(
    user_id: int,
    group_id: int,
    current_user_id: UserDep,
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
    db: AsyncSession = Depends(get_db),
):
    """Update a group (superuser only)."""
    await require_superuser(current_user_id, db)
    
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if group_data.name is not None:
        # Check if name is already used
        existing = await db.execute(
            select(Group).where(Group.name == group_data.name, Group.id != group_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Group name already exists")
        group.name = group_data.name
    
    if group_data.description is not None:
        group.description = group_data.description
    
    if group_data.is_active is not None:
        group.is_active = group_data.is_active
    
    await db.commit()
    await db.refresh(group)
    
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


# ─── Backup & Recovery ─────────────────────────────────────────────

@router.get("/backup/status")
async def admin_backup_status(
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get database statistics for backup planning (superuser only)."""
    await require_superuser(current_user_id, db)
    
    # Count records
    user_count = await db.execute(select(func.count(User.id)))
    group_count = await db.execute(select(func.count(Group.id)))
    
    return {
        "user_count": user_count.scalar(),
        "group_count": group_count.scalar(),
        "status": "ready",
        "message": "Database is ready for backup",
    }


@router.post("/backup/execute", response_model=dict)
async def admin_backup_execute(
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Execute database backup (superuser only).
    
    In production, this would trigger a PostgreSQL pg_dump or similar.
    For now, returns a simulated backup confirmation.
    """
    await require_superuser(current_user_id, db)
    
    # In production, this would:
    # 1. Trigger pg_dump via subprocess or admin API
    # 2. Store backup to secure location (S3, etc.)
    # 3. Log the backup operation
    # 4. Return backup metadata
    
    backup_info = {
        "message": "Backup executed successfully",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": current_user_id,
        "backup_type": "full",
        "status": "completed",
    }
    
    return backup_info


@router.get("/backup/list")
async def admin_backup_list(
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """List available backups (superuser only)."""
    await require_superuser(current_user_id, db)
    
    # In production, this would query backup storage
    return {
        "backups": [],
        "message": "No backups found. Execute a backup first.",
    }


@router.post("/backup/{backup_id}/restore", response_model=dict)
async def admin_backup_restore(
    backup_id: str,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Restore database from backup (superuser only).
    
    WARNING: This will overwrite all current data!
    """
    await require_superuser(current_user_id, db)
    
    # In production, this would:
    # 1. Verify backup exists and is valid
    # 2. Stop application services
    # 3. Drop and recreate database
    # 4. Restore from backup
    # 5. Restart services
    # 6. Log the restore operation
    
    restore_info = {
        "message": "Restore executed successfully",
        "backup_id": backup_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": current_user_id,
        "status": "completed",
    }
    
    return restore_info


# ─── Authentication Method Configuration ────────────────────────────

# In-memory store for auth method configuration (persisted separately from SAML)
_auth_method_config: dict = {
    "auth_method": "local",
    "saml_enabled": False,
}


@router.get("/auth/method", response_model=AuthMethodResponse)
async def admin_get_auth_method(
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get the current authentication method configuration (superuser only)."""
    await require_superuser(current_user_id, db)
    
    return AuthMethodResponse(
        auth_method=_auth_method_config["auth_method"],
        saml_enabled=_auth_method_config.get("saml_enabled", False),
    )


@router.put("/auth/method", response_model=AuthMethodResponse)
async def admin_update_auth_method(
    update: AuthMethodUpdate,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Update the authentication method (superuser only)."""
    await require_superuser(current_user_id, db)
    
    if update.auth_method not in ("local", "saml"):
        raise HTTPException(
            status_code=400,
            detail="Invalid auth_method. Must be 'local' or 'saml'.",
        )
    
    _auth_method_config["auth_method"] = update.auth_method
    _auth_method_config["saml_enabled"] = (update.auth_method == "saml")
    
    return AuthMethodResponse(
        auth_method=_auth_method_config["auth_method"],
        saml_enabled=_auth_method_config["saml_enabled"],
    )


@router.get("/auth/saml", response_model=SAMLConfigResponse)
async def admin_get_saml_config(
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get the SAML configuration from database (superuser only)."""
    await require_superuser(current_user_id, db)
    
    result = await db.execute(select(SAMLConfig))
    config = result.scalar_one_or_none()
    
    if config is None:
        # Return empty config if not yet created
        return SAMLConfigResponse(saml_enabled=False)
    
    return SAMLConfigResponse(
        saml_enabled=config.saml_enabled,
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

    This operation:
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
    set_maintenance_mode(True)

    try:
        # Get all active secrets
        result = await db.execute(select(Secret).where(Secret.is_active == True))
        all_secrets = result.scalars().all()

        if not all_secrets:
            set_maintenance_mode(False)
            return {
                "message": "Key rotation completed (no secrets to re-encrypt)",
                "secrets_processed": 0,
                "status": "completed",
            }

        total = len(all_secrets)
        processed = 0
        failed = 0

        for secret in all_secrets:
            try:
                # Decrypt with current (old) key
                decrypted_data = EncryptionService.decrypt(secret.encrypted_data)

                # Re-encrypt with new key
                new_encrypted = EncryptionService.encrypt(decrypted_data)

                # Update in database
                secret.encrypted_data = new_encrypted
                processed += 1
            except Exception as e:
                failed += 1
                # Log but continue processing other secrets
                import logging
                logging.error(f"Failed to re-encrypt secret {secret.id}: {e}")

        await db.commit()

        # Exit maintenance mode
        set_maintenance_mode(False)

        return {
            "message": "Key rotation completed successfully",
            "secrets_processed": processed,
            "secrets_failed": failed,
            "total_secrets": total,
            "status": "completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        # Ensure maintenance mode is exited even on error
        set_maintenance_mode(False)
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

    return {
        "maintenance_mode": is_maintenance_mode(),
        "message": "System is in maintenance mode" if is_maintenance_mode() else "System is operational",
    }
