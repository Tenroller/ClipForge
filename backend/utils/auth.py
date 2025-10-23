"""
Authentication utilities for JWT token management and password hashing.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
import logging

import jwt
import bcrypt

# Config will be lazily loaded to avoid circular imports
_config = None


def _get_config():
    """Lazy load config to avoid circular imports."""
    global _config
    if _config is None:
        from backend.core.config import AppConfig
        _config = AppConfig.from_env()
    return _config


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    # Convert string to bytes for bcrypt
    if isinstance(password, str):
        password = password.encode('utf-8')
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password, salt)
    # Return as string for storage
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    # Convert string to bytes for bcrypt
    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    # Verify password
    return bcrypt.checkpw(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token as string
    """
    config = _get_config()
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=config.jwt_access_token_expire_minutes)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        config.jwt_secret_key,
        algorithm="HS256"
    )

    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload if valid, None otherwise
    """
    config = _get_config()
    try:
        payload = jwt.decode(
            token,
            config.jwt_secret_key,
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.PyJWTError:
        return None


class SimpleUserStore:
    """
    Simple in-memory user store for single-user authentication.
    For production multi-user setup, replace with database-backed storage.
    """

    def __init__(self):
        # Default user credentials (change via environment variables)
        self.username = os.getenv("AUTH_USERNAME", "admin")
        self._password_plain = os.getenv("AUTH_PASSWORD", "admin123")
        logging.info(f"Loaded plain password: {self._password_plain} (type: {type(self._password_plain)})")
        self._password_hash = None  # Lazy initialization

    @property
    def password_hash(self):
        """Lazy hash the password on first access."""
        if self._password_hash is None:
            logging.info(f"Hashing password: {self._password_plain} (type: {type(self._password_plain)})")
            self._password_hash = hash_password(self._password_plain)
        return self._password_hash

    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify username and password."""
        if username != self.username:
            return False
        logging.info(f"Verifying password for user '{username}'")
        return verify_password(password, self.password_hash)

    def get_user_info(self, username: str) -> Optional[dict]:
        """Get user information by username."""
        if username == self.username:
            return {
                "username": self.username,
                "role": "admin"
            }
        return None


# Global user store instance
user_store = SimpleUserStore()
