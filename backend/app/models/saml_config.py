"""SAML configuration model for persistent storage."""

from sqlalchemy import Boolean, Column, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SAMLConfig(Base):
    """Persistent SAML identity provider and authentication method configuration."""

    __tablename__ = "saml_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    auth_method: Mapped[str] = mapped_column(String(20), default="local")
    saml_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    entity_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sso_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    idp_metadata_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    acs_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    certificate: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_id_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    slo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    slo_redirect_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    certificate_label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<SAMLConfig method={self.auth_method} enabled={self.saml_enabled}>"
