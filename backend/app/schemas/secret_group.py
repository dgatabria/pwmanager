"""Secret group schemas."""

from pydantic import BaseModel


class SecretGroupCreate(BaseModel):
    name: str
    description: str | None = None
    parent_id: int | None = None
    group_id: int


class SecretGroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class SecretGroupResponse(BaseModel):
    id: int
    name: str
    description: str | None
    parent_id: int | None
    group_id: int
    is_active: bool

    class Config:
        from_attributes = True


class SecretGroupDetail(SecretGroupResponse):
    group_ids: list[int] = []
    child_count: int = 0
    secret_count: int = 0


class SecretGroupTreeItem(SecretGroupResponse):
    children: list["SecretGroupTreeItem"] = []
    group_ids: list[int] = []
