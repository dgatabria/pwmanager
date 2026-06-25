"""Secret group schemas."""

from pydantic import BaseModel


class SecretGroupCreate(BaseModel):
    """Schema for creating a new secret group."""
    name: str
    description: str | None = None
    parent_id: int | None = None
    group_id: int | None = None
    # Which user groups should have access to this secret group
    member_group_ids: list[int] = []


class SecretGroupUpdate(BaseModel):
    """Schema for updating a secret group's properties or access."""
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    # Replace the current access list with this new set of group IDs
    member_group_ids: list[int] | None = None


class SecretGroupResponse(BaseModel):
    id: int
    name: str
    description: str | None
    parent_id: int | None
    group_id: int
    owner_id: int
    is_active: bool

    class Config:
        from_attributes = True


class SecretGroupDetail(SecretGroupResponse):
    owner_username: str = ""
    group_ids: list[int] = []
    child_count: int = 0
    secret_count: int = 0


class SecretGroupTreeItem(SecretGroupResponse):
    children: list["SecretGroupTreeItem"] = []
    group_ids: list[int] = []


class SecretGroupAccessUpdate(BaseModel):
    """Schema for updating which user groups can access a secret group."""
    member_group_ids: list[int]
