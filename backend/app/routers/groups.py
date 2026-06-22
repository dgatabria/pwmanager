"""Groups and user management endpoints.

NOTE: All user/group CRUD operations are intentionally removed from this router.
User and group management is exclusively handled via the /api/admin endpoints
which enforce superuser authorization. This router only provides group membership
operations (add/remove user from group) which are used by the frontend for RBAC.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.group import Group
from app.models.user import User
from app.models.user_group import UserGroup
from app.schemas.group import GroupDetail, GroupResponse
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api", tags=["Groups & Users"])

UserDep = Annotated[int, Depends(get_current_user)]


# ─── Group Membership Operations ────────────────────────────────────

@router.post("/users/{user_id}/groups/{group_id}", status_code=204)
async def add_user_to_group(
    user_id: int,
    group_id: int,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Add a user to a group (superuser only)."""
    # Verify caller is superuser
    result = await db.execute(select(User).where(User.id == current_user_id))
    current_user = result.scalar_one_or_none()
    if not current_user or not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )

    # Verify target user exists
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    # Verify group exists
    result = await db.execute(select(Group).where(Group.id == group_id))
    if not result.scalar_one_or_none():
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
async def remove_user_from_group(
    user_id: int,
    group_id: int,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Remove a user from a group (superuser only)."""
    # Verify caller is superuser
    result = await db.execute(select(User).where(User.id == current_user_id))
    current_user = result.scalar_one_or_none()
    if not current_user or not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )

    result = await db.execute(
        select(UserGroup).where(
            UserGroup.user_id == user_id, UserGroup.group_id == group_id
        )
    )
    ug = result.scalar_one_or_none()
    if ug:
        await db.delete(ug)
        await db.commit()


# ─── Group Read Operations ──────────────────────────────────────────

@router.get("/groups", response_model=list[GroupResponse])
async def list_groups(current_user_id: UserDep, db: AsyncSession = Depends(get_db)):
    """List all groups (requires authentication)."""
    result = await db.execute(select(Group).order_by(Group.name))
    groups = result.scalars().all()
    return [
        GroupResponse(
            id=g.id,
            name=g.name,
            description=g.description,
            is_active=g.is_active,
        )
        for g in groups
    ]


@router.get("/groups/{group_id}", response_model=GroupDetail)
async def get_group_detail(
    group_id: int,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get group details with user list (requires authentication)."""
    result = await db.execute(
        select(Group)
        .where(Group.id == group_id)
        .options(selectinload(Group.users))
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    return GroupDetail(
        id=group.id,
        name=group.name,
        description=group.description,
        is_active=group.is_active,
        user_ids=[u.id for u in group.users],
    )
