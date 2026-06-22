"""Group schemas."""

from pydantic import BaseModel


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class GroupResponse(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool

    class Config:
        from_attributes = True


class GroupDetail(GroupResponse):
    user_ids: list[int] = []
