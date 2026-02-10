"""Syslog forwarding API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth import require_admin
from core.syslog_forwarder import (
    get_syslog_config,
    configure_syslog,
    test_syslog_connection,
    get_syslog_status,
)

router = APIRouter()


class SyslogConfigRequest(BaseModel):
    enabled: bool
    server: str = ""
    port: int = 514
    protocol: str = "udp"
    format: str = "syslog"
    tls: bool = False


class SyslogTestRequest(BaseModel):
    server: str
    port: int = 514
    protocol: str = "udp"


@router.get("/status")
async def syslog_status(user: Annotated[str, Depends(require_admin)]):
    """Get syslog forwarding status (admin only)."""
    return get_syslog_status()


@router.get("/config")
async def get_config(user: Annotated[str, Depends(require_admin)]):
    """Get current syslog configuration (admin only)."""
    config = get_syslog_config()
    return {
        "enabled": config.enabled,
        "server": config.server,
        "port": config.port,
        "protocol": config.protocol,
        "format": config.format,
        "tls": config.tls,
    }


@router.put("/config")
async def update_config(
    body: SyslogConfigRequest,
    user: Annotated[str, Depends(require_admin)],
):
    """Update syslog forwarding configuration (admin only)."""
    success, message = configure_syslog(
        enabled=body.enabled,
        server=body.server,
        port=body.port,
        protocol=body.protocol,
        format=body.format,
        tls=body.tls,
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@router.post("/test")
async def test_connection(
    body: SyslogTestRequest,
    user: Annotated[str, Depends(require_admin)],
):
    """Test connection to syslog server (admin only)."""
    success, message = test_syslog_connection(
        body.server,
        body.port,
        body.protocol,
    )
    
    return {"success": success, "message": message}
