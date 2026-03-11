"""
Authentication utilities for JWT token management and password hashing.
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import jwt
import bcrypt

try:
    from ..logging_config import get_logger
except ImportError:
    from logging_config import get_logger

logger = get_logger("auth")

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


def _get_session():
    """Get a database session. Lazy import to avoid circular dependencies."""
    from backend.database import SessionLocal
    return SessionLocal()


class DatabaseUserStore:
    """
    Database-backed user store for multi-user authentication.
    Uses SQLAlchemy to persist users in PostgreSQL.
    """

    def __init__(self):
        self._initialized = False

    def _ensure_admin(self) -> None:
        """Auto-create the admin user from env vars if no users exist."""
        if self._initialized:
            return
        self._initialized = True

        admin_username = os.getenv("AUTH_USERNAME", "admin")
        admin_password = os.getenv("AUTH_PASSWORD")

        if not admin_password:
            raise ValueError(
                "AUTH_PASSWORD environment variable is required. "
                "Set it to a strong password before starting the application."
            )

        session = _get_session()
        try:
            from backend.database import User
            user_count = session.query(User).count()
            if user_count == 0:
                # No users exist yet — seed the admin
                admin_user = User(
                    id=uuid.uuid4(),
                    username=admin_username,
                    password_hash=hash_password(admin_password),
                    role="admin",
                    is_active=True,
                )
                session.add(admin_user)
                session.commit()
                logger.info(f"Auto-created admin user: {admin_username}")
            else:
                # Users exist; ensure the env-specified admin exists and
                # update their password if it changed.
                admin = session.query(User).filter(User.username == admin_username).first()
                if admin is None:
                    # The configured admin username doesn't exist — create it
                    admin_user = User(
                        id=uuid.uuid4(),
                        username=admin_username,
                        password_hash=hash_password(admin_password),
                        role="admin",
                        is_active=True,
                    )
                    session.add(admin_user)
                    session.commit()
                    logger.info(f"Created admin user from env: {admin_username}")
                elif not verify_password(admin_password, admin.password_hash):
                    # Password changed in env — update it
                    admin.password_hash = hash_password(admin_password)
                    session.commit()
                    logger.info(f"Updated password for admin user: {admin_username}")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to ensure admin user: {e}")
            raise
        finally:
            session.close()

    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify username and password against the database."""
        self._ensure_admin()

        session = _get_session()
        try:
            from backend.database import User
            user = session.query(User).filter(
                User.username == username,
                User.is_active == True  # noqa: E712
            ).first()

            if not user:
                return False
            return verify_password(password, user.password_hash)
        finally:
            session.close()

    def get_user_info(self, username: str) -> Optional[dict]:
        """Get user information by username."""
        self._ensure_admin()

        session = _get_session()
        try:
            from backend.database import User
            user = session.query(User).filter(
                User.username == username,
                User.is_active == True  # noqa: E712
            ).first()

            if not user:
                return None

            return {
                "id": str(user.id),
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
        finally:
            session.close()

    def create_user(self, username: str, password: str, role: str = "user") -> dict:
        """
        Create a new user.

        Args:
            username: Unique username
            password: Plain-text password (will be hashed)
            role: User role (default "user")

        Returns:
            Created user info dict

        Raises:
            ValueError: If username already exists
        """
        self._ensure_admin()

        session = _get_session()
        try:
            from backend.database import User

            existing = session.query(User).filter(User.username == username).first()
            if existing:
                raise ValueError(f"Username '{username}' already exists")

            new_user = User(
                id=uuid.uuid4(),
                username=username,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
            )
            session.add(new_user)
            session.commit()

            logger.info(f"Created new user: {username} (role={role})")

            return {
                "id": str(new_user.id),
                "username": new_user.username,
                "role": new_user.role,
                "is_active": new_user.is_active,
                "created_at": new_user.created_at.isoformat() if new_user.created_at else None,
            }
        except ValueError:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create user {username}: {e}")
            raise
        finally:
            session.close()

    def list_users(self) -> List[dict]:
        """List all users (without password hashes)."""
        self._ensure_admin()

        session = _get_session()
        try:
            from backend.database import User
            users = session.query(User).order_by(User.created_at.asc()).all()

            return [
                {
                    "id": str(u.id),
                    "username": u.username,
                    "role": u.role,
                    "is_active": u.is_active,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "updated_at": u.updated_at.isoformat() if u.updated_at else None,
                }
                for u in users
            ]
        finally:
            session.close()


# Global user store instance — now database-backed
user_store = DatabaseUserStore()
