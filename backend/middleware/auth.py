"""
Authentication middleware and dependencies.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from backend.utils.auth import verify_token, user_store
from backend.logging_config import get_logger

logger = get_logger("auth.middleware")
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency to get the current authenticated user.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        User information dictionary

    Raises:
        HTTPException: 401 if authentication fails
    """
    token = credentials.credentials
    payload = verify_token(token)

    if not payload:
        logger.warning("Invalid or expired token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    if not username:
        logger.warning("Token missing username claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_info = user_store.get_user_info(username)
    if not user_info:
        logger.warning(f"User not found: {username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_info


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    )
) -> Optional[dict]:
    """
    Dependency to optionally get the current authenticated user.
    Returns None if no valid token is provided.

    Args:
        credentials: Optional bearer token from Authorization header

    Returns:
        User information dictionary or None
    """
    if not credentials:
        return None

    token = credentials.credentials
    payload = verify_token(token)

    if not payload:
        return None

    username = payload.get("sub")
    if not username:
        return None

    return user_store.get_user_info(username)


def require_role(required_role: str):
    """
    Dependency factory to require a specific role.

    Args:
        required_role: Role required to access the endpoint

    Returns:
        Dependency function

    Example:
        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
    """

    async def role_checker(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role", "")
        if user_role != required_role:
            logger.warning(
                f"User {user.get('username')} attempted to access {required_role}-only endpoint"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {required_role}",
            )
        return user

    return role_checker
