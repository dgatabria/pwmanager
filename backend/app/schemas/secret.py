"""Secret schemas."""

from pydantic import BaseModel

from app.models.secret import SecretType


class SecretCreate(BaseModel):
    title: str
    description: str | None = None
    secret_type: SecretType
    encrypted_data: str
    key_length: int | None = None
    username: str | None = None
    url: str | None = None
    group_id: int


class SecretUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    encrypted_data: str | None = None
    key_length: int | None = None
    username: str | None = None
    url: str | None = None


class SecretResponse(BaseModel):
    id: int
    title: str
    description: str | None
    secret_type: SecretType
    encrypted_data: str
    key_length: int | None
    username: str | None
    url: str | None
    group_id: int
    owner_id: int
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SecretViewResponse(BaseModel):
    id: int
    title: str
    description: str | None
    secret_type: SecretType
    decrypted_data: str | None
    key_length: int | None
    username: str | None
    url: str | None
    group_name: str | None
    owner_username: str | None
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SSHKeyGenerateRequest(BaseModel):
    key_length: int = 4096
    comment: str = "corporate-ssh-key"


class SSHKeyGenerateResponse(BaseModel):
    public_key: str
    private_key: str
    fingerprint: str
    key_length: int
