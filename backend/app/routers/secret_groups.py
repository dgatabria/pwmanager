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
from app.models.secret import Secret
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
    """List all secret groups the user can access (owned + shared).

    Personal groups are returned first, followed by shared groups.
    """
    # Get user group memberships
    result = await db.execute(
        select(UserGroup.group_id).where(UserGroup.user_id == user_id)
    )
    user_group_ids = [row[0] for row in result.all()]

    # Build query: owned groups OR groups shared with user's groups (read access only)
    conditions = [SecretGroup.owner_id == user_id]
    if user_group_ids:
        conditions.append(
            SecretGroup.id.in_(
                select(SecretGroupMember.secret_group_id).where(
                    SecretGroupMember.group_id.in_(user_group_ids),
                    SecretGroupMember.permission == "read",
                )
            )
        )

    query = select(SecretGroup).where(
        SecretGroup.is_active == True,
        or_(*conditions),
    )

    if group_id:
        query = query.where(SecretGroup.group_id == group_id)

    # Order: personal groups first, then by name
    query = query.order_by(
        SecretGroup.is_personal.desc(),
        SecretGroup.name,
    )

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
            user_id=g.user_id,
            is_personal=g.is_personal,
            is_active=g.is_active,
            owner_username=g.owner.username if g.owner else "",
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
    """Create a new secret group. The creator becomes the owner.

    Personal groups are created automatically when a user is created.
    This endpoint cannot be used to create personal groups.

    Authorization: the user may only share with groups they belong to.
    Duplicate names per user are not allowed.
    """
    # Validate member_group_ids: must exist, be active, AND belong to the user
    if group_data.member_group_ids:
        result = await db.execute(
            select(Group.id).where(
                Group.id.in_(group_data.member_group_ids),
                Group.is_active == True,
            )
        )
        existing_group_ids = {row[0] for row in result.all()}
        # Get the user's own group memberships
        result = await db.execute(
            select(UserGroup.group_id).where(UserGroup.user_id == current_user_id)
        )
        user_group_ids = {row[0] for row in result.all()}
        # Groups that don't exist or are inactive
        non_existent = set(group_data.member_group_ids) - existing_group_ids
        # Groups the user doesn't belong to
        not_member = set(group_data.member_group_ids) - user_group_ids
        if non_existent or not_member:
            bad = sorted(non_existent | not_member)
            reason = []
            if non_existent:
                reason.append("non-existent or inactive")
            if not_member:
                reason.append("you are not a member of")
            raise HTTPException(
                status_code=403,
                detail=f"Cannot share with groups: {', '.join(str(g) for g in bad)} ({'; '.join(reason)})"
            )

    # Check for duplicate name (case-insensitive, same owner, active)
    result = await db.execute(
        select(SecretGroup).where(
            SecretGroup.owner_id == current_user_id,
            SecretGroup.is_active == True,
            SecretGroup.name.ilike(group_data.name),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"A secret group with name '{group_data.name}' already exists",
        )

    sg = SecretGroup(
        name=group_data.name,
        description=group_data.description,
        parent_id=group_data.parent_id,
        group_id=group_data.group_id,
        owner_id=current_user_id,
        is_personal=False,
    )
    db.add(sg)
    await db.flush()

    # Get owner username before commit (avoid lazy load after commit)
    result = await db.execute(
        select(User).where(User.id == current_user_id)
    )
    owner = result.scalar_one_or_none()
    owner_username = owner.username if owner else ""

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
        user_id=sg.user_id,
        is_personal=sg.is_personal,
        is_active=sg.is_active,
        owner_username=owner_username,
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
    """Update a secret group (owner only).

    The user's own personal group (identified by personal_group_id in the users
    table) cannot be renamed, have its description changed, or be shared.
    Other personal groups (e.g. other users' personal groups that you own) can
    be edited freely.

    Authorization: the owner may only share with groups they belong to.
    """
    sg = await _require_owner(group_id, current_user_id, db)

    # Protect only the user's OWN personal group from modification
    result = await db.execute(
        select(User).where(User.id == current_user_id)
    )
    user = result.scalar_one_or_none()
    if user and user.personal_group_id == sg.id:
        raise HTTPException(
            status_code=403,
            detail="Your personal group cannot be modified. It is managed automatically.",
        )

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
        # Get the owner's own group memberships
        result = await db.execute(
            select(UserGroup.group_id).where(UserGroup.user_id == current_user_id)
        )
        owner_group_ids = {row[0] for row in result.all()}

        # Validate: must exist, be active, AND belong to the owner
        result = await db.execute(
            select(Group.id).where(
                Group.id.in_(group_data.member_group_ids),
                Group.is_active == True,
            )
        )
        existing_group_ids = {row[0] for row in result.all()}
        non_existent = set(group_data.member_group_ids) - existing_group_ids
        not_member = set(group_data.member_group_ids) - owner_group_ids
        if non_existent or not_member:
            bad = sorted(non_existent | not_member)
            reason = []
            if non_existent:
                reason.append("non-existent or inactive")
            if not_member:
                reason.append("you are not a member of")
            raise HTTPException(
                status_code=403,
                detail=f"Cannot share with groups: {', '.join(str(g) for g in bad)} ({'; '.join(reason)})"
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
        user_id=sg.user_id,
        is_personal=sg.is_personal,
        is_active=sg.is_active,
        owner_username=sg.owner.username if sg.owner else "",
    )


@router.delete("/{group_id}", status_code=204)
async def delete_secret_group(
    group_id: int,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a secret group and all secrets within it (owner only).

    The user's own personal group (identified by personal_group_id in the users
    table) cannot be deleted. Other personal groups can be deleted freely.

    This is a hard delete — all secrets in the group are permanently removed
    along with group memberships. The operation is auditable.
    """
    sg = await _require_owner(group_id, current_user_id, db)

    # Protect only the user's OWN personal group from deletion
    result = await db.execute(
        select(User).where(User.id == current_user_id)
    )
    user = result.scalar_one_or_none()
    if user and user.personal_group_id == sg.id:
        raise HTTPException(
            status_code=403,
            detail="Your personal group cannot be deleted. It is managed automatically.",
        )

    # Delete all secrets in this group (hard delete, not soft)
    result = await db.execute(
        select(Secret).where(Secret.group_id == group_id)
    )
    secrets = result.scalars().all()
    for secret in secrets:
        await db.delete(secret)

    # Delete all group memberships
    await db.execute(
        SecretGroupMember.__table__.delete().where(
            SecretGroupMember.secret_group_id == group_id
        )
    )

    # Delete the group itself
    await db.delete(sg)
    await db.commit()

    # Audit: secret group permanent deletion
    await AuditService.log_crud(
        db,
        AuditService.ENTITY_SECRET_GROUP,
        AuditService.OP_DELETE,
        current_user_id,
        entity_id=sg.id,
        request=request,
        details=f"Permanently deleted secret group '{sg.name}' (id={group_id}) with {len(secrets)} secret(s)",
    )


@router.post("/{group_id}/access", status_code=200)
async def update_group_access(
    group_id: int,
    access_data: SecretGroupAccessUpdate,
    current_user_id: UserDep,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update which user groups can access this secret group (owner only).

    Personal groups cannot be shared.

    Authorization: the owner may only share with groups they belong to.
    """
    sg = await _require_owner(group_id, current_user_id, db)

    # Protect personal groups from sharing
    if sg.is_personal:
        raise HTTPException(
            status_code=403,
            detail="Personal groups cannot be shared.",
        )

    # Get the owner's own group memberships
    result = await db.execute(
        select(UserGroup.group_id).where(UserGroup.user_id == current_user_id)
    )
    owner_group_ids = {row[0] for row in result.all()}

    # Validate: must exist, be active, AND belong to the owner
    result = await db.execute(
        select(Group.id).where(
            Group.id.in_(access_data.member_group_ids),
            Group.is_active == True,
        )
    )
    existing_group_ids = {row[0] for row in result.all()}
    non_existent = set(access_data.member_group_ids) - existing_group_ids
    not_member = set(access_data.member_group_ids) - owner_group_ids
    if non_existent or not_member:
        bad = sorted(non_existent | not_member)
        reason = []
        if non_existent:
            reason.append("non-existent or inactive")
        if not_member:
            reason.append("you are not a member of")
        raise HTTPException(
            status_code=403,
            detail=f"Cannot share with groups: {', '.join(str(g) for g in bad)} ({'; '.join(reason)})"
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
    """Add a user group to a secret group (owner only).

    Personal groups cannot be shared.

    Authorization: the owner may only add groups they belong to.
    """
    sg = await _require_owner(group_id, current_user_id, db)

    # Protect personal groups from sharing
    if sg.is_personal:
        raise HTTPException(
            status_code=403,
            detail="Personal groups cannot be shared.",
        )

    # Get the owner's own group memberships
    result = await db.execute(
        select(UserGroup.group_id).where(UserGroup.user_id == current_user_id)
    )
    owner_group_ids = {row[0] for row in result.all()}

    # Validate group exists, is active, AND owner belongs to it
    result = await db.execute(
        select(Group.id).where(Group.id == user_group_id, Group.is_active == True)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Group does not exist or is inactive",
        )
    if user_group_id not in owner_group_ids:
        raise HTTPException(
            status_code=403,
            detail="You are not a member of this group",
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
    """Remove a user group from a secret group (owner only).

    Personal groups cannot be shared.
    """
    sg = await _require_owner(group_id, current_user_id, db)

    # Protect personal groups from sharing
    if sg.is_personal:
        raise HTTPException(
            status_code=403,
            detail="Personal groups cannot be shared.",
        )

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
