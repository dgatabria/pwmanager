"""Authentication schemas."""

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    """Schema for regular user registration."""
    username: str
    email: EmailStr
    password: str
    full_name: str | None = None


class AdminUserCreate(BaseModel):
    """Schema for admin user creation."""
    username: str
    email: EmailStr
    full_name: str | None = None
    is_active: bool = True
    is_superuser: bool = False


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str | None
    is_active: bool
    is_superuser: bool
    created_at: str

    class Config:
        from_attributes = True
