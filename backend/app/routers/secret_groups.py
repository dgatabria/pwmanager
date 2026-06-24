"""Secret groups management endpoints.

Authorization model:
- Any authenticated user can create secret groups.
- The owner (creator) of a secret group can modify, delete, and manage access.
- Access is granted to user groups via the secret_group_members junction table.
- The list endpoint returns groups the user can access (owned + shared).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.group import Group
from app.models.secret_group import SecretGroup
from app.models.secret_group_member import SecretGroupMember
from app.models.user import User
from app.models.user_group import UserGroup
from app.schemas.secret_group import (
    SecretGroupAccessUpdate,
    SecretGroupCreate,
    SecretGroupDetail,
    SecretGroupResponse,
    SecretGroupUpdate,
)
from app.services.audit import AuditService
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/secret-groups", tags=["Secret Groups"])

UserDep = Annotated[int, Depends(get_current_user)]


async def _get_user_groups(user_id: int, db: AsyncSession) -> list[int]:
    """Return the list of user group IDs the current user belongs to."""
    result = await db.execute(
        select(UserGroup.group_id).where(UserGroup.user_id == user_id)
    )
    return [row[0] for row in result.all()]


async def _require_owner(group_id: int, current_user_id: int, db: AsyncSession):
    """Verify the current user is the owner of the secret group."""
    result = await db.execute(
        select(SecretGroup).where(SecretGroup.id == group_id)
    )
    sg = result.scalar_one_or_none()

    if not sg:
        raise HTTPException(status_code=404, detail="Secret group not found")

    if sg.owner_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can perform this action",
        )

    return sg


@router.get("")
async def list_secret_groups(
    user_id: UserDep,
    db: AsyncSession = Depends(get_db),
    group_id: int | None = Query(None),
):
    """List all secret groups the user can access (owned + shared)."""
    # Get user group memberships
    result = await db.execute(
        select(UserGroup.group_id).where(UserGroup.user_id == user_id)
    )
    user_group_ids = [row[0] for row in result.all()]

    # Build query: owned groups OR groups shared with user's groups
    query = select(SecretGroup).where(
        SecretGroup.is_active == True,
        or_(
            SecretGroup.owner_id == user_id,
            SecretGroup.id.in_(
                select(SecretGroupMember.secret_group_id).where(
                    SecretGroupMember.group_id.in_(user_group_ids) if user_group_ids else [0]
                )
            )
        ),
    )

    if group_id:
        query = query.where(SecretGroup.group_id == group_id)

    query = query.order_by(SecretGroup.name)

    result = await db.execute(query)
    groups = result.scalars().all()

    return [
        SecretGroupResponse(
            id=g.id,
            name=g.name,
            description=g.description,
            parent_id=g.parent_id,
            group_id=g.group_id,
            owner_id=g.owner_id,
            is_active=g.is_active,
        )
        for g in groups
    ]


@router.post("", response_model=SecretGroupResponse, status_code=201)
async def create_secret_group(
    group_data: SecretGroupCreate,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a new secret group. The creator becomes the owner."""
    # Validate member_group_ids exist and user belongs to them
    if group_data.member_group_ids:
        result = await db.execute(
            select(Group.id).where(
                Group.id.in_(group_data.member_group_ids),
                Group.is_active == True,
            )
        )
        valid_group_ids = {row[0] for row in result.all()}
        invalid = set(group_data.member_group_ids) - valid_group_ids
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot share with non-existent or inactive groups: {sorted(invalid)}",
            )

    sg = SecretGroup(
        name=group_data.name,
        description=group_data.description,
        parent_id=group_data.parent_id,
        group_id=group_data.group_id,
        owner_id=current_user_id,
    )
    db.add(sg)
    await db.commit()
    await db.refresh(sg)

    # Grant access to specified user groups
    if group_data.member_group_ids:
        for gid in group_data.member_group_ids:
            sgm = SecretGroupMember(
                secret_group_id=sg.id,
                group_id=gid,
            )
            db.add(sgm)
        await db.commit()

    # Audit: secret group creation
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_SECRET_GROUP,
        AuditService.OP_CREATE,
        current_user_id,
        entity_id=sg.id,
        request=request,
        details=f"Created secret group '{group_data.name}' (parent={group_data.parent_id})",
    )

    return SecretGroupResponse(
        id=sg.id,
        name=sg.name,
        description=sg.description,
        parent_id=sg.parent_id,
        group_id=sg.group_id,
        owner_id=sg.owner_id,
        is_active=sg.is_active,
    )


@router.get("/{group_id}", response_model=SecretGroupDetail)
async def get_secret_group_detail(
    group_id: int,
    user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get secret group details (must be owner or have access)."""
    result = await db.execute(
        select(SecretGroup).where(SecretGroup.id == group_id)
    )
    sg = result.scalar_one_or_none()

    if not sg:
        raise HTTPException(status_code=404, detail="Secret group not found")

    # Check access: owner or shared with user's groups
    result = await db.execute(
        select(UserGroup.group_id).where(UserGroup.user_id == user_id)
    )
    user_group_ids = [row[0] for row in result.all()]

    is_owner = sg.owner_id == user_id
    has_access = is_owner or (
        user_group_ids and
        sg.id in [
            row[0] for row in await db.execute(
                select(SecretGroupMember.secret_group_id).where(
                    SecretGroupMember.group_id.in_(user_group_ids)
                )
            ).all()
        ]
    )

    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get owner info
    result = await db.execute(select(User).where(User.id == sg.owner_id))
    owner = result.scalar_one_or_none()
    owner_username = owner.username if owner else ""

    # Get associated user groups
    result = await db.execute(
        select(SecretGroupMember.group_id)
        .where(SecretGroupMember.secret_group_id == group_id)
    )
    group_ids = [row[0] for row in result.all()]

    # Count children
    result = await db.execute(
        select(SecretGroup).where(SecretGroup.parent_id == group_id)
    )
    children = result.scalars().all()

    # Count secrets
    result = await db.execute(
        select(SecretGroup).where(SecretGroup.id == group_id)
    )
    sg2 = result.scalar_one_or_none()
    secret_count = len(sg2.secrets) if sg2 else 0

    return SecretGroupDetail(
        id=sg.id,
        name=sg.name,
        description=sg.description,
        parent_id=sg.parent_id,
        group_id=sg.group_id,
        owner_id=sg.owner_id,
        owner_username=owner_username,
        is_active=sg.is_active,
        group_ids=group_ids,
        child_count=len(children),
        secret_count=secret_count,
    )


@router.put("/{group_id}", response_model=SecretGroupResponse)
async def update_secret_group(
    group_id: int,
    group_data: SecretGroupUpdate,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update a secret group (owner only)."""
    sg = await _require_owner(group_id, current_user_id, db)

    changes: list[str] = []
    if group_data.name is not None:
        sg.name = group_data.name
        changes.append(f"name={group_data.name}")
    if group_data.description is not None:
        sg.description = group_data.description
        changes.append(f"description={group_data.description}")
    if group_data.is_active is not None:
        sg.is_active = group_data.is_active
        changes.append(f"is_active={group_data.is_active}")

    # Update member access if provided
    if group_data.member_group_ids is not None:
        # Validate group IDs
        result = await db.execute(
            select(Group.id).where(
                Group.id.in_(group_data.member_group_ids),
                Group.is_active == True,
            )
        )
        valid_group_ids = {row[0] for row in result.all()}
        invalid = set(group_data.member_group_ids) - valid_group_ids
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot share with non-existent or inactive groups: {sorted(invalid)}",
            )

        # Remove existing memberships
        await db.execute(
            SecretGroupMember.__table__.delete().where(
                SecretGroupMember.secret_group_id == group_id
            )
        )

        # Add new memberships
        for gid in group_data.member_group_ids:
            sgm = SecretGroupMember(
                secret_group_id=group_id,
                group_id=gid,
            )
            db.add(sgm)
        changes.append(f"member_groups={group_data.member_group_ids}")

    await db.commit()
    await db.refresh(sg)

    # Audit: secret group update
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_SECRET_GROUP,
        AuditService.OP_UPDATE,
        current_user_id,
        entity_id=sg.id,
        request=request,
        details=f"Updated secret group '{sg.name}': {', '.join(changes)}",
    )

    return SecretGroupResponse(
        id=sg.id,
        name=sg.name,
        description=sg.description,
        parent_id=sg.parent_id,
        group_id=sg.group_id,
        owner_id=sg.owner_id,
        is_active=sg.is_active,
    )


@router.delete("/{group_id}", status_code=204)
async def delete_secret_group(
    group_id: int,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a secret group (owner only)."""
    sg = await _require_owner(group_id, current_user_id, db)

    sg.is_active = False
    await db.commit()

    # Audit: secret group deletion
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_SECRET_GROUP,
        AuditService.OP_DELETE,
        current_user_id,
        entity_id=sg.id,
        request=request,
        details=f"Soft-deleted secret group '{sg.name}' (id={group_id})",
    )


@router.post("/{group_id}/access", status_code=200)
async def update_group_access(
    group_id: int,
    access_data: SecretGroupAccessUpdate,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update which user groups can access this secret group (owner only)."""
    sg = await _require_owner(group_id, current_user_id, db)

    # Validate group IDs
    result = await db.execute(
        select(Group.id).where(
            Group.id.in_(access_data.member_group_ids),
            Group.is_active == True,
        )
    )
    valid_group_ids = {row[0] for row in result.all()}
    invalid = set(access_data.member_group_ids) - valid_group_ids
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot share with non-existent or inactive groups: {sorted(invalid)}",
        )

    # Remove existing memberships
    await db.execute(
        SecretGroupMember.__table__.delete().where(
            SecretGroupMember.secret_group_id == group_id
        )
    )

    # Add new memberships
    for gid in access_data.member_group_ids:
        sgm = SecretGroupMember(
            secret_group_id=group_id,
            group_id=gid,
        )
        db.add(sgm)

    await db.commit()

    # Audit: secret group access update
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_SECRET_GROUP,
        AuditService.OP_ACCESS_UPDATE,
        current_user_id,
        entity_id=sg.id,
        request=request,
        details=f"Updated access for secret group '{sg.name}': members={access_data.member_group_ids}",
    )


@router.post("/{group_id}/groups/{user_group_id}", status_code=204)
async def add_group_to_secret_group(
    group_id: int,
    user_group_id: int,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Add a user group to a secret group (owner only)."""
    await _require_owner(group_id, current_user_id, db)

    # Validate group exists and is active
    result = await db.execute(
        select(Group.id).where(Group.id == user_group_id, Group.is_active == True)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Group does not exist or is inactive",
        )

    result = await db.execute(
        select(SecretGroupMember)
        .where(
            SecretGroupMember.secret_group_id == group_id,
            SecretGroupMember.group_id == user_group_id,
        )
    )
    if result.scalar_one_or_none():
        return  # Already associated

    sgm = SecretGroupMember(
        secret_group_id=group_id,
        group_id=user_group_id,
    )
    db.add(sgm)
    await db.commit()

    # Audit: add group to secret group
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_SECRET_GROUP,
        AuditService.OP_ADD_TO_GROUP,
        current_user_id,
        entity_id=group_id,
        request=request,
        details=f"Added group (id={user_group_id}) to secret group (id={group_id})",
    )


@router.delete("/{group_id}/groups/{user_group_id}", status_code=204)
async def remove_group_from_secret_group(
    group_id: int,
    user_group_id: int,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Remove a user group from a secret group (owner only)."""
    await _require_owner(group_id, current_user_id, db)

    result = await db.execute(
        select(SecretGroupMember)
        .where(
            SecretGroupMember.secret_group_id == group_id,
            SecretGroupMember.group_id == user_group_id,
        )
    )
    sgm = result.scalar_one_or_none()
    if sgm:
        await db.delete(sgm)
        await db.commit()

        # Audit: remove group from secret group
        await AuditService.log_crud(
            db,
            AuditService.ENTITY_SECRET_GROUP,
            AuditService.OP_REMOVE_FROM_GROUP,
            current_user_id,
            entity_id=group_id,
            request=request,
            details=f"Removed group (id={user_group_id}) from secret group (id={group_id})",
        )
