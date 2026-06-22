"""Groups and user management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.group import Group
from app.models.user import User
from app.models.user_group import UserGroup
from app.schemas.group import GroupCreate, GroupDetail, GroupResponse, GroupUpdate
from app.schemas.auth import UserResponse
from app.services.auth import AuthService
from app.utils.security import SecurityUtils
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api", tags=["Groups & Users"])

UserDep = Annotated[int, Depends(get_current_user)]


# ─── User Management ────────────────────────────────────────────────

@router.get("/users", response_model=list[UserResponse])
async def list_users(user_id: UserDep, db: AsyncSession = Depends(get_db)):
    """List all users (requires authentication)."""
    result = await db.execute(select(User).order_by(User.username))
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
async def create_user(
    user_data: UserResponse,
    current_user_id: UserDep,
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user (superuser only).
    
    Requires superuser privileges to prevent unauthorized user creation.
    Random password is generated and must be changed on first login.
    """
    # Verify caller is superuser
    result = await db.execute(select(User).where(User.id == current_user_id))
    current_user = result.scalar_one_or_none()
    
    if not current_user or not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required to create users",
        )

    # Check if username exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already exists")

    # Generate random password (user must change on first login)
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


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    user_data: UserResponse,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Update a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_data.email is not None:
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


@router.post("/users/{user_id}/groups/{group_id}", status_code=204)
async def add_user_to_group(
    user_id: int,
    group_id: int,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Add a user to a group."""
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
    """Remove a user from a group."""
    result = await db.execute(
        select(UserGroup).where(
            UserGroup.user_id == user_id, UserGroup.group_id == group_id
        )
    )
    ug = result.scalar_one_or_none()
    if ug:
        await db.delete(ug)
        await db.commit()


# ─── Group Management ───────────────────────────────────────────────

@router.get("/groups", response_model=list[GroupResponse])
async def list_groups(current_user_id: UserDep, db: AsyncSession = Depends(get_db)):
    """List all groups."""
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


@router.post("/groups", response_model=GroupResponse, status_code=201)
async def create_group(
    group_data: GroupCreate,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Create a new group."""
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
async def update_group(
    group_id: int,
    group_data: GroupUpdate,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Update a group."""
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if group_data.name is not None:
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


@router.get("/groups/{group_id}", response_model=GroupDetail)
async def get_group_detail(
    group_id: int,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Get group details with user list."""
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


@router.delete("/groups/{group_id}", status_code=204)
async def delete_group(
    group_id: int,
    current_user_id: UserDep,
    db: AsyncSession = Depends(get_db),
):
    """Delete a group."""
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    await db.delete(group)
    await db.commit()
