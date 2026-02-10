"""Multi-user management with role-based access control."""

import hashlib
import json
import logging
import os
import secrets
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger("networktap.users")

USERS_FILE = Path("/var/lib/networktap/users.json")
USERS_FILE_DEV = Path(__file__).parent.parent.parent / "users.json"


class Role(str, Enum):
    ADMIN = "admin"
    VIEWER = "viewer"


@dataclass
class User:
    username: str
    password_hash: str
    role: Role
    enabled: bool = True
    created_at: str = ""
    last_login: str = ""

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "password_hash": self.password_hash,
            "role": self.role.value,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_login": self.last_login,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            username=data["username"],
            password_hash=data["password_hash"],
            role=Role(data.get("role", "viewer")),
            enabled=data.get("enabled", True),
            created_at=data.get("created_at", ""),
            last_login=data.get("last_login", ""),
        )


def _get_users_path() -> Path:
    """Get the users file path, preferring system location."""
    if USERS_FILE.exists():
        return USERS_FILE
    if USERS_FILE_DEV.exists():
        return USERS_FILE_DEV
    # Default to system path, will be created
    return USERS_FILE


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash a password with PBKDF2-SHA256."""
    if salt is None:
        salt = secrets.token_hex(16)
    
    # Use PBKDF2 with SHA256
    dk = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations=100000
    )
    return f"pbkdf2:sha256:100000${salt}${dk.hex()}"


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    try:
        if password_hash.startswith("pbkdf2:"):
            # Parse PBKDF2 hash
            parts = password_hash.split("$")
            if len(parts) != 3:
                return False
            
            algo_info = parts[0]  # pbkdf2:sha256:100000
            salt = parts[1]
            stored_hash = parts[2]
            
            iterations = int(algo_info.split(":")[-1])
            
            dk = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                iterations=iterations
            )
            return secrets.compare_digest(dk.hex(), stored_hash)
        else:
            # Legacy plaintext comparison (for migration)
            return secrets.compare_digest(password, password_hash)
    except Exception as e:
        logger.error("Password verification error: %s", e)
        return False


def _load_users() -> dict[str, User]:
    """Load users from JSON file."""
    path = _get_users_path()
    
    if not path.exists():
        return {}
    
    try:
        with open(path, "r") as f:
            data = json.load(f)
        
        users = {}
        for user_data in data.get("users", []):
            user = User.from_dict(user_data)
            users[user.username] = user
        return users
    except Exception as e:
        logger.error("Error loading users: %s", e)
        return {}


def _save_users(users: dict[str, User]) -> bool:
    """Save users to JSON file."""
    path = _get_users_path()
    
    try:
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "version": 1,
            "users": [user.to_dict() for user in users.values()]
        }
        
        # Write atomically
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
        
        os.replace(temp_path, path)
        os.chmod(path, 0o600)
        return True
    except Exception as e:
        logger.error("Error saving users: %s", e)
        return False


def get_user(username: str) -> Optional[User]:
    """Get a user by username."""
    users = _load_users()
    return users.get(username)


def list_users() -> list[dict]:
    """List all users (without password hashes)."""
    users = _load_users()
    return [
        {
            "username": u.username,
            "role": u.role.value,
            "enabled": u.enabled,
            "created_at": u.created_at,
            "last_login": u.last_login,
        }
        for u in users.values()
    ]


def authenticate(username: str, password: str) -> Optional[User]:
    """Authenticate a user and return User if valid."""
    user = get_user(username)
    
    if user is None:
        return None
    
    if not user.enabled:
        return None
    
    if not _verify_password(password, user.password_hash):
        return None
    
    # Update last login
    from datetime import datetime
    users = _load_users()
    if username in users:
        users[username].last_login = datetime.now().isoformat()
        _save_users(users)
    
    return user


def create_user(username: str, password: str, role: Role = Role.VIEWER) -> tuple[bool, str]:
    """Create a new user."""
    if not username or len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters"
    
    users = _load_users()
    
    if username in users:
        return False, "User already exists"
    
    from datetime import datetime
    
    user = User(
        username=username,
        password_hash=_hash_password(password),
        role=role,
        enabled=True,
        created_at=datetime.now().isoformat(),
    )
    
    users[username] = user
    
    if _save_users(users):
        logger.info("Created user: %s (role: %s)", username, role.value)
        return True, "User created"
    else:
        return False, "Failed to save user"


def update_user(
    username: str,
    password: Optional[str] = None,
    role: Optional[Role] = None,
    enabled: Optional[bool] = None,
) -> tuple[bool, str]:
    """Update an existing user."""
    users = _load_users()
    
    if username not in users:
        return False, "User not found"
    
    user = users[username]
    
    if password is not None:
        if len(password) < 8:
            return False, "Password must be at least 8 characters"
        user.password_hash = _hash_password(password)
    
    if role is not None:
        user.role = role
    
    if enabled is not None:
        user.enabled = enabled
    
    if _save_users(users):
        logger.info("Updated user: %s", username)
        return True, "User updated"
    else:
        return False, "Failed to save user"


def delete_user(username: str) -> tuple[bool, str]:
    """Delete a user."""
    users = _load_users()
    
    if username not in users:
        return False, "User not found"
    
    # Prevent deleting last admin
    admins = [u for u in users.values() if u.role == Role.ADMIN and u.username != username]
    if users[username].role == Role.ADMIN and len(admins) == 0:
        return False, "Cannot delete the last admin user"
    
    del users[username]
    
    if _save_users(users):
        logger.info("Deleted user: %s", username)
        return True, "User deleted"
    else:
        return False, "Failed to save users"


def change_password(username: str, old_password: str, new_password: str) -> tuple[bool, str]:
    """Change a user's password (requires old password)."""
    user = authenticate(username, old_password)
    
    if user is None:
        return False, "Invalid current password"
    
    return update_user(username, password=new_password)


def initialize_default_users() -> None:
    """Initialize with default admin user if no users exist."""
    from core.config import get_config
    
    users = _load_users()
    
    if len(users) > 0:
        return
    
    # Migrate from config-based auth
    config = get_config()
    
    success, msg = create_user(
        username=config.web_user,
        password=config.web_pass,
        role=Role.ADMIN,
    )
    
    if success:
        logger.info("Initialized default admin user from config")
    else:
        logger.warning("Failed to initialize default user: %s", msg)


def has_users() -> bool:
    """Check if any users are configured."""
    return len(_load_users()) > 0


def user_has_role(username: str, required_role: Role) -> bool:
    """Check if user has at least the required role level."""
    user = get_user(username)
    if user is None:
        return False
    
    # Admin has all permissions
    if user.role == Role.ADMIN:
        return True
    
    # Viewer can only access viewer-level
    return user.role == required_role
