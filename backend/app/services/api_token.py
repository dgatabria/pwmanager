"""API Token management service."""

import secrets
import bcrypt
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_token import APIToken

logger = logging.getLogger(__name__)


class APITokenService:
    """Service for managing API tokens."""

    TOKEN_PREFIX = "pm_"

    @staticmethod
    def generate_token() -> str:
        """Generate a new API token."""
        random_part = secrets.token_hex(32)
        return f"{APITokenService.TOKEN_PREFIX}{random_part}"

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for storage (bcrypt).

        bcrypt is used instead of SHA-256 because it is computationally
        expensive, making offline brute-force attacks significantly harder.
        """
        return bcrypt.hashpw(
            token.encode("utf-8"),
            bcrypt.gensalt(rounds=12),
        ).decode("utf-8")

    @staticmethod
    async def create_token(
        db: AsyncSession,
        user_id: int,
        name: str,
        description: str | None = None,
        expires_at: datetime | None = None,
    ) -> tuple[str, APIToken]:
        """Create a new API token. Returns (plain_token, token_record)."""
        plain_token = APITokenService.generate_token()
        token_hash = APITokenService.hash_token(plain_token)

        api_token = APIToken(
            token_hash=token_hash,
            user_id=user_id,
            name=name,
            description=description,
            expires_at=expires_at,
        )

        db.add(api_token)
        await db.commit()
        await db.refresh(api_token)

        return plain_token, api_token

    @staticmethod
    async def validate_token(
        db: AsyncSession, token: str
    ) -> tuple[APIToken | None, dict | None]:
        """
        Validate an API token using bcrypt.checkpw.

        Queries all active tokens and verifies each with bcrypt.checkpw.
        bcrypt includes a random salt, so the token hash cannot be used
        for deterministic lookups.

        Returns (api_token, user_info) if valid, (None, None) if invalid.
        """
        result = await db.execute(
            select(APIToken)
            .where(APIToken.is_active == True)
        )
        api_tokens = result.scalars().all()

        logger.info("validate_token: token starts with %s, found %d active tokens",
                     token[:10] if len(token) > 10 else token, len(api_tokens))

        for api_token in api_tokens:
            logger.info("validate_token: checking against token id=%s, hash starts with %s",
                        api_token.id, api_token.token_hash[:15] if api_token.token_hash else None)
            try:
                match = bcrypt.checkpw(
                    token.encode("utf-8"),
                    api_token.token_hash.encode("utf-8"),
                )
                logger.info("validate_token: token id=%s, match=%s", api_token.id, match)
            except Exception as e:
                logger.error("validate_token: checkpw failed for id=%s: %s", api_token.id, e)
                continue

            if not match:
                continue

            # Check expiration
            if api_token.expires_at and datetime.now(timezone.utc) > api_token.expires_at:
                api_token.is_active = False
                await db.commit()
                return None, None

            # Update last used
            api_token.last_used_at = datetime.now(timezone.utc)
            await db.commit()

            # Get user info
            user_info = {
                "id": api_token.user_id,
                "username": api_token.user.username,
                "email": api_token.user.email,
                "full_name": api_token.user.full_name,
                "is_superuser": api_token.user.is_superuser,
            }

            logger.info("validate_token: SUCCESS - token id=%s, user_id=%s", api_token.id, api_token.user_id)
            return api_token, user_info

        logger.warning("validate_token: no matching token found")
        return None, None

    @staticmethod
    async def list_user_tokens(
        db: AsyncSession, user_id: int
    ) -> list[APIToken]:
        """List all tokens for a user."""
        result = await db.execute(
            select(APIToken)
            .where(APIToken.user_id == user_id)
            .order_by(APIToken.created_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def revoke_token(
        db: AsyncSession, token_id: int, user_id: int
    ) -> APIToken | None:
        """Revoke (soft delete) a token."""
        result = await db.execute(
            select(APIToken)
            .where(APIToken.id == token_id)
            .where(APIToken.user_id == user_id)
        )
        api_token = result.scalar_one_or_none()

        if api_token:
            api_token.is_active = False
            await db.commit()
            await db.refresh(api_token)

        return api_token

    @staticmethod
    async def recycle_token(
        db: AsyncSession, old_token: str, user_id: int, name: str, description: str | None = None
    ) -> tuple[str, APIToken]:
        """
        Recycle an API token: revoke the old one and create a new one.
        Returns (new_plain_token, new_token_record).
        """
        # Validate old token using bcrypt.checkpw
        result = await db.execute(
            select(APIToken)
            .where(APIToken.user_id == user_id)
            .where(APIToken.is_active == True)
        )
        old_api_token = result.scalar_one_or_none()

        if not old_api_token or not bcrypt.checkpw(
            old_token.encode("utf-8"),
            old_api_token.token_hash.encode("utf-8"),
        ):
            raise ValueError("Invalid or expired token")

        # Revoke old token
        old_api_token.is_active = False
        await db.commit()

        # Create new token with same name/description
        new_token, _ = await APITokenService.create_token(
            db=db,
            user_id=user_id,
            name=name,
            description=description,
            expires_at=old_api_token.expires_at,
        )

        return new_token
