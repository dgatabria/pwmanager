"""SAML configuration model for persistent storage."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SAMLConfig(Base):
    """Persistent SAML identity provider configuration."""

    __tablename__ = "saml_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
        return f"<SAMLConfig enabled={self.saml_enabled}>"
