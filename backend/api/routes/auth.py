"""
Authentication routes for login, logout, token management, and user management.
"""

from datetime import timedelta
from fastapi import APIRouter, HTTPException, Depends, Header, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import os
import secrets

from backend.models.requests import LoginRequest, RegisterRequest, LoginResponse, TokenVerifyResponse
from backend.utils.auth import (
    user_store,
    create_access_token,
    verify_token,
)
from backend.middleware.auth import require_role
from backend.core.config import AppConfig
from backend.logging_config import get_logger

router = APIRouter()
security = HTTPBearer()
logger = get_logger("auth")
config = AppConfig.from_env()


_TOKEN_BYTES = 32


@router.get("/auth/csrf-token", summary="Get CSRF token")
async def get_csrf_token(request: Request, response: Response):
    """
    Return the CSRF token so cross-origin frontends can read it from the JSON body
    (the cookie is not accessible via JS when the backend is on a different origin).
    """
    is_debug = os.getenv("DEBUG_MODE", "").lower() in ("true", "1")
    token = request.cookies.get("csrf_token") or secrets.token_hex(_TOKEN_BYTES)
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=False,
        secure=not is_debug,
        samesite="none" if not is_debug else "lax",
        path="/",
    )
    return {"csrf_token": token}


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return JWT token.

    Args:
        request: Login credentials

    Returns:
        LoginResponse with access token

    Raises:
        HTTPException: 401 if credentials are invalid
    """
    # Verify credentials
    if not user_store.verify_credentials(request.username, request.password):
        logger.warning(
            f"Failed login attempt for user: {request.username}",
            extra={"username": request.username}
        )
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )

    # Get user info
    user_info = user_store.get_user_info(request.username)

    # Create access token with user id in the claims
    access_token = create_access_token(
        data={
            "sub": request.username,
            "role": user_info.get("role", "user"),
            "user_id": user_info.get("id"),
        }
    )

    logger.info(
        f"User logged in successfully: {request.username}",
        extra={"username": request.username}
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=config.jwt_access_token_expire_minutes * 60,  # Convert to seconds
        user=user_info
    )


@router.post("/auth/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Logout endpoint (client-side token deletion).

    Note: Since JWT is stateless, the client must delete the token.
    This endpoint is here for consistency and future token blacklisting.
    """
    token = credentials.credentials
    payload = verify_token(token)

    if payload:
        username = payload.get("sub")
        logger.info(
            f"User logged out: {username}",
            extra={"username": username}
        )

    return {"message": "Successfully logged out"}


@router.get("/auth/verify", response_model=TokenVerifyResponse)
async def verify(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify JWT token and return user information.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        TokenVerifyResponse with validity status and user info
    """
    token = credentials.credentials
    payload = verify_token(token)

    if not payload:
        return TokenVerifyResponse(valid=False)

    username = payload.get("sub")
    user_info = user_store.get_user_info(username)

    if not user_info:
        return TokenVerifyResponse(valid=False)

    return TokenVerifyResponse(
        valid=True,
        user=user_info
    )


@router.get("/auth/me")
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Get current authenticated user information.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        User information dictionary

    Raises:
        HTTPException: 401 if token is invalid
    """
    token = credentials.credentials
    payload = verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    username = payload.get("sub")
    user_info = user_store.get_user_info(username)

    if not user_info:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user_info


@router.post("/auth/register", status_code=201)
async def register_user(
    request: RegisterRequest,
    admin: dict = Depends(require_role("admin")),
):
    """
    Register a new user (admin only).

    Args:
        request: Registration data (username, password, role)
        admin: Current admin user (injected by require_role)

    Returns:
        Created user information

    Raises:
        HTTPException: 409 if username already exists
        HTTPException: 403 if caller is not admin
    """
    try:
        new_user = user_store.create_user(
            username=request.username,
            password=request.password,
            role=request.role,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    logger.info(
        f"Admin '{admin.get('username')}' created user '{request.username}' with role '{request.role}'"
    )

    return new_user


@router.get("/auth/users")
async def list_users(
    admin: dict = Depends(require_role("admin")),
):
    """
    List all users (admin only).

    Args:
        admin: Current admin user (injected by require_role)

    Returns:
        List of user information dictionaries
    """
    return user_store.list_users()
