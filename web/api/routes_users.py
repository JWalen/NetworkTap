"""User management API endpoints."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from core.auth import verify_credentials, require_admin
from core.user_manager import (
    Role,
    list_users,
    get_user,
    create_user,
    update_user,
    delete_user,
    change_password,
)

router = APIRouter()


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="viewer", pattern="^(admin|viewer)$")


class UpdateUserRequest(BaseModel):
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    role: Optional[str] = Field(default=None, pattern="^(admin|viewer)$")
    enabled: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


@router.get("/")
async def get_users(user: Annotated[str, Depends(require_admin)]):
    """List all users (admin only)."""
    return {"users": list_users()}


@router.post("/")
async def create_new_user(
    body: CreateUserRequest,
    user: Annotated[str, Depends(require_admin)],
):
    """Create a new user (admin only)."""
    role = Role.ADMIN if body.role == "admin" else Role.VIEWER
    
    success, message = create_user(body.username, body.password, role)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@router.get("/{username}")
async def get_user_details(
    username: str,
    current_user: Annotated[str, Depends(verify_credentials)],
):
    """Get user details. Users can view their own profile, admins can view all."""
    # Users can only view their own profile unless admin
    user_obj = get_user(current_user)
    if user_obj is None or (user_obj.role != Role.ADMIN and username != current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    
    target = get_user(username)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "username": target.username,
        "role": target.role.value,
        "enabled": target.enabled,
        "created_at": target.created_at,
        "last_login": target.last_login,
    }


@router.put("/{username}")
async def update_existing_user(
    username: str,
    body: UpdateUserRequest,
    current_user: Annotated[str, Depends(require_admin)],
):
    """Update a user (admin only)."""
    role = None
    if body.role is not None:
        role = Role.ADMIN if body.role == "admin" else Role.VIEWER
    
    success, message = update_user(
        username,
        password=body.password,
        role=role,
        enabled=body.enabled,
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@router.delete("/{username}")
async def delete_existing_user(
    username: str,
    current_user: Annotated[str, Depends(require_admin)],
):
    """Delete a user (admin only)."""
    success, message = delete_user(username)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@router.post("/change-password")
async def change_own_password(
    body: ChangePasswordRequest,
    current_user: Annotated[str, Depends(verify_credentials)],
):
    """Change the current user's password."""
    success, message = change_password(
        current_user,
        body.old_password,
        body.new_password,
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@router.get("/me/role")
async def get_my_role(current_user: Annotated[str, Depends(verify_credentials)]):
    """Get the current user's role."""
    user = get_user(current_user)
    if user is None:
        # Fall back to admin for legacy config-based auth
        return {"username": current_user, "role": "admin"}
    
    return {"username": user.username, "role": user.role.value}
