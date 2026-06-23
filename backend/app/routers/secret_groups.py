"""Secret groups management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.secret_group import SecretGroup
from app.models.secret_group_member import SecretGroupMember
from app.models.user import User
from app.schemas.secret_group import (
    SecretGroupCreate,
    SecretGroupDetail,
    SecretGroupResponse,
    SecretGroupUpdate,
)
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/secret-groups", tags=["Secret Groups"])

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


@router.get("")
async def list_secret_groups(
    user_id: UserDep,
    db: AsyncSession = Depends(get_db),
    group_id: int | None = Query(None),
):
    """List all secret groups."""
    query = select(SecretGroup).where(SecretGroup.is_active == True)
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
            is_active=g.is_active,
        )
        for g in groups
    ]


@router.post("", response_model=SecretGroupResponse, status_code=201)
async def create_secret_group(
    group_data: SecretGroupCreate,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Create a new secret group (superuser only)."""
    await require_superuser(current_user_id, db)

    sg = SecretGroup(
        name=group_data.name,
        description=group_data.description,
        parent_id=group_data.parent_id,
        group_id=group_data.group_id,
    )
    db.add(sg)
    await db.commit()
    await db.refresh(sg)

    return SecretGroupResponse(
        id=sg.id,
        name=sg.name,
        description=sg.description,
        parent_id=sg.parent_id,
        group_id=sg.group_id,
        is_active=sg.is_active,
    )


@router.get("/{group_id}", response_model=SecretGroupDetail)
async def get_secret_group_detail(
    group_id: int,
    user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get secret group details."""
    result = await db.execute(
        select(SecretGroup)
        .where(SecretGroup.id == group_id)
    )
    sg = result.scalar_one_or_none()

    if not sg:
        raise HTTPException(status_code=404, detail="Secret group not found")

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
    db: AsyncSession = Depends(get_db),
):
    """Update a secret group (superuser only)."""
    await require_superuser(current_user_id, db)

    result = await db.execute(
        select(SecretGroup).where(SecretGroup.id == group_id)
    )
    sg = result.scalar_one_or_none()

    if not sg:
        raise HTTPException(status_code=404, detail="Secret group not found")

    if group_data.name is not None:
        sg.name = group_data.name
    if group_data.description is not None:
        sg.description = group_data.description
    if group_data.is_active is not None:
        sg.is_active = group_data.is_active

    await db.commit()
    await db.refresh(sg)

    return SecretGroupResponse(
        id=sg.id,
        name=sg.name,
        description=sg.description,
        parent_id=sg.parent_id,
        group_id=sg.group_id,
        is_active=sg.is_active,
    )


@router.delete("/{group_id}", status_code=204)
async def delete_secret_group(
    group_id: int,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a secret group (superuser only)."""
    await require_superuser(current_user_id, db)

    result = await db.execute(
        select(SecretGroup).where(SecretGroup.id == group_id)
    )
    sg = result.scalar_one_or_none()

    if not sg:
        raise HTTPException(status_code=404, detail="Secret group not found")

    sg.is_active = False
    await db.commit()


@router.post("/{group_id}/groups/{user_group_id}", status_code=204)
async def add_group_to_secret_group(
    group_id: int,
    user_group_id: int,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Add a user group to a secret group (RBAC, superuser only)."""
    await require_superuser(current_user_id, db)

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


@router.delete("/{group_id}/groups/{user_group_id}", status_code=204)
async def remove_group_from_secret_group(
    group_id: int,
    user_group_id: int,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Remove a user group from a secret group (superuser only)."""
    await require_superuser(current_user_id, db)

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
