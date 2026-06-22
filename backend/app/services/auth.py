"""Authentication service using JWT with RS256 asymmetric signing."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings
from app.utils.rsa_keys import get_private_key, get_public_key


class AuthService:
    """Service for JWT token management using RS256 asymmetric signing."""

    ALGORITHM = "RS256"

    @staticmethod
    def create_access_token(data: dict) -> str:
        """Create a JWT access token signed with RS256.

        Uses the RSA private key for signing, which never needs to be
        shared with clients or exposed in environment variables.
        """
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        to_encode.update({"exp": expire})
        private_key = get_private_key()
        return jwt.encode(to_encode, private_key, algorithm=AuthService.ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> dict:
        """Decode and validate a JWT token using the RSA public key.

        The public key can safely be shared — it can only verify tokens,
        not create them.
        """
        try:
            public_key = get_public_key()
            payload = jwt.decode(
                token, public_key, algorithms=[AuthService.ALGORITHM]
            )
            return payload
        except JWTError as e:
            raise ValueError(f"Invalid token: {e}")
