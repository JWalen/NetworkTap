"""HTTP authentication for NetworkTap with role-based access control."""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from core.config import get_config

security = HTTPBasic()


def verify_credentials(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
) -> str:
    """Verify HTTP Basic credentials against users database or config.

    Returns the username if valid, raises 401 otherwise.
    """
    # Try user database first
    try:
        from core.user_manager import authenticate, has_users

        if has_users():
            user = authenticate(credentials.username, credentials.password)
            if user is not None:
                return user.username
            # Database auth failed — fall through to config check
    except ImportError:
        pass

    # Fall back to config-based auth (always available as emergency admin)
    config = get_config()

    username_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        config.web_user.encode("utf-8"),
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        config.web_pass.encode("utf-8"),
    )

    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


def require_admin(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
) -> str:
    """Verify credentials and require admin role.
    
    Returns the username if valid admin, raises 401/403 otherwise.
    """
    # First verify credentials
    username = verify_credentials(credentials)
    
    # Check role
    try:
        from core.user_manager import get_user, Role, has_users
        
        if has_users():
            user = get_user(username)
            if user is None or user.role != Role.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin access required",
                )
    except ImportError:
        pass
    
    # Config-based auth is always admin
    return username


def get_current_user_role(username: str) -> str:
    """Get the role of the current user."""
    try:
        from core.user_manager import get_user, has_users
        
        if has_users():
            user = get_user(username)
            if user:
                return user.role.value
    except ImportError:
        pass
    
    return "admin"  # Config-based users are admin


def is_viewer_only(username: str) -> bool:
    """Check if user has viewer-only access."""
    return get_current_user_role(username) == "viewer"
