"""Configuration management API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.auth import verify_credentials
from core.config import get_config
from core.network_manager import get_mode, switch_mode

router = APIRouter()


class ModeSwitch(BaseModel):
    mode: str


@router.get("/")
async def get_configuration(user: Annotated[str, Depends(verify_credentials)]):
    """Get current configuration (sensitive fields redacted)."""
    config = get_config()
    return {
        "mode": config.mode,
        "nic1": config.nic1,
        "nic2": config.nic2,
        "bridge_name": config.bridge_name,
        "capture_dir": config.capture_dir,
        "capture_interface": config.capture_interface,
        "management_interface": config.management_interface,
        "capture_rotate_seconds": config.capture_rotate_seconds,
        "capture_compress": config.capture_compress,
        "capture_filter": config.capture_filter,
        "retention_days": config.retention_days,
        "suricata_enabled": config.suricata_enabled,
        "zeek_enabled": config.zeek_enabled,
        "web_port": config.web_port,
    }


@router.get("/mode")
async def get_current_mode(user: Annotated[str, Depends(verify_credentials)]):
    """Get current operating mode details."""
    return get_mode()


@router.put("/mode")
async def set_mode(
    body: ModeSwitch,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Switch operating mode (span or bridge)."""
    return switch_mode(body.mode)
