"""Secret schemas."""

from pydantic import BaseModel

from app.models.secret import SecretType


class SecretCreate(BaseModel):
    title: str
    description: str | None = None
    secret_type: SecretType
    plaintext_data: str
    key_length: int | None = None
    username: str | None = None
    url: str | None = None
    group_id: int


class SecretUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    plaintext_data: str | None = None
    key_length: int | None = None
    username: str | None = None
    url: str | None = None


class SecretResponse(BaseModel):
    """Response for create/update — encrypted_data is intentionally excluded
    so the server never echoes back ciphertext in response bodies.
    owner_id is intentionally excluded to prevent user enumeration."""

    id: int
    title: str
    description: str | None
    secret_type: SecretType
    key_length: int | None
    username: str | None
    url: str | None
    group_id: int
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


class SecretMaskedResponse(BaseModel):
    """Response with masked data (asterisks)."""
    id: int
    title: str
    description: str | None
    secret_type: SecretType
    decrypted_data: str = "••••••••••••••••"
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


class SecretRevealResponse(BaseModel):
    """Response with revealed data + audit info."""
    id: int
    title: str
    description: str | None
    secret_type: SecretType
    decrypted_data: str
    key_length: int | None
    username: str | None
    url: str | None
    group_name: str | None
    owner_username: str | None
    is_active: bool
    created_at: str
    updated_at: str
    audit_id: int
    audit_event: str
    audit_timestamp: str
    audit_ip: str

    class Config:
        from_attributes = True


class SecretCopyResponse(BaseModel):
    """Response with data for clipboard + audit info."""
    id: int
    title: str
    decrypted_data: str
    audit_id: int
    audit_event: str
    audit_timestamp: str
    audit_ip: str

    class Config:
        from_attributes = True


class SSHKeyGenerateRequest(BaseModel):
    key_length: int = 4096
    comment: str = "corporate-ssh-key"


class SSHKeyGenerateResponse(BaseModel):
    """SSH key pair response. The private_key is encrypted server-side
    so it is never transmitted or stored in plaintext."""
    public_key: str
    private_key_encrypted: str
    fingerprint: str
    key_length: int
