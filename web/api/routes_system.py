"""System status and monitoring API endpoints."""

import subprocess
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from pydantic import BaseModel

from core.auth import verify_credentials, require_admin
from core.config import get_config
from core.alert_parser import _tail_lines
from core.network_manager import (
    identify_port,
    get_mgmt_network_config,
    set_mgmt_network_config,
)
from core.system_monitor import (
    get_system_stats,
    get_interface_stats,
    get_all_services,
)

router = APIRouter()


@router.get("/status")
async def system_status(user: Annotated[str, Depends(verify_credentials)]):
    """Get system resource usage: CPU, memory, disk, uptime."""
    config = get_config()
    stats = get_system_stats(config.capture_dir)
    services = get_all_services()

    return {
        "system": stats,
        "services": services,
        "mode": config.mode,
    }


@router.get("/interfaces")
async def system_interfaces(user: Annotated[str, Depends(verify_credentials)]):
    """Get all network interface statistics."""
    config = get_config()
    interfaces = get_interface_stats()

    return {
        "interfaces": interfaces,
        "mode": config.mode,
        "capture_interface": config.capture_interface,
        "management_interface": config.management_interface,
    }


@router.get("/network")
async def get_network_config(user: Annotated[str, Depends(verify_credentials)]):
    """Get management network configuration (DHCP or static IP)."""
    return get_mgmt_network_config()


class NetworkConfigRequest(BaseModel):
    mode: str  # "dhcp" or "static"
    ip_address: str | None = None  # Required for static, e.g., "192.168.1.100/24"
    gateway: str | None = None
    dns: str | None = None


@router.post("/network")
async def update_network_config(
    body: NetworkConfigRequest,
    user: Annotated[str, Depends(require_admin)],
):
    """Set management network configuration (requires admin).
    
    For static mode, ip_address must include CIDR prefix (e.g., 192.168.1.100/24).
    Gateway and DNS are optional but recommended for static configuration.
    """
    return set_mgmt_network_config(
        mode=body.mode,
        ip_address=body.ip_address,
        gateway=body.gateway,
        dns=body.dns,
    )


class IdentifyPortRequest(BaseModel):
    interface: str
    duration: int = 5


@router.post("/identify-port")
async def identify_interface_port(
    body: IdentifyPortRequest,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Blink the LED on a NIC port for physical identification."""
    result = identify_port(body.interface, body.duration)
    return result


# Allowed services that can be restarted via the API
RESTARTABLE_SERVICES = {
    "networktap-capture",
    "networktap-suricata",
    "networktap-zeek",
    "networktap-web",
    "networktap-display",
    "networktap-console",
    "networktap-stats",
}


@router.post("/service/{service_name}/restart")
async def restart_service(
    service_name: str,
    user: Annotated[str, Depends(require_admin)],
):
    """Restart a NetworkTap systemd service (requires admin)."""
    if service_name not in RESTARTABLE_SERVICES:
        return {"success": False, "message": f"Service not allowed: {service_name}"}

    try:
        result = subprocess.run(
            ["systemctl", "restart", service_name],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return {"success": True, "message": f"{service_name} restarted"}
        return {"success": False, "message": f"Failed: {result.stderr.strip()}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# Hardcoded log sources — no user-supplied paths
# Try journald-style paths first, fall back to traditional syslog
_SYSLOG_PATH = "/var/log/syslog" if Path("/var/log/syslog").exists() else "/var/log/messages"
_AUTH_PATH = "/var/log/auth.log" if Path("/var/log/auth.log").exists() else "/var/log/secure"

LOG_SOURCES = {
    "web": "/var/log/networktap/web.log",
    "syslog": _SYSLOG_PATH,
    "suricata": None,  # resolved from config
    "auth": _AUTH_PATH,
    "kern": "/var/log/kern.log",
}


@router.get("/logs/sources")
async def log_sources(user: Annotated[str, Depends(verify_credentials)]):
    """List available log sources with existence check."""
    config = get_config()
    sources = []
    for name, path in LOG_SOURCES.items():
        if path is None:
            path = config.suricata_eve_log
        exists = Path(path).exists()
        sources.append({"name": name, "path": path, "available": exists})
    return {"sources": sources}


@router.get("/logs")
async def read_logs(
    user: Annotated[str, Depends(verify_credentials)],
    source: str = Query("syslog"),
    lines: int = Query(100, ge=1, le=1000),
):
    """Read last N lines from a log source."""
    if source not in LOG_SOURCES:
        return {"error": f"Unknown source: {source}", "lines": []}

    path = LOG_SOURCES[source]
    if path is None:
        config = get_config()
        path = config.suricata_eve_log

    p = Path(path)
    if not p.exists():
        # Fall back to journalctl for syslog/kern/auth on journald-only systems
        journal_map = {"syslog": "", "kern": "-k", "auth": "-t sshd -t sudo -t login"}
        if source in journal_map:
            import asyncio
            try:
                proc = await asyncio.create_subprocess_exec(
                    "journalctl", "--no-pager", "-n", str(lines),
                    *journal_map[source].split(),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
                jlines = stdout.decode(errors="replace").strip().splitlines()
                return {"source": source, "path": "journalctl", "lines": jlines, "available": True}
            except Exception:
                pass
        return {"source": source, "path": path, "lines": [], "available": False}

    raw_lines = _tail_lines(p, lines)
    return {"source": source, "path": path, "lines": raw_lines, "available": True}


@router.post("/reboot")
async def reboot_system(user: Annotated[str, Depends(require_admin)]):
    """Reboot the appliance (requires admin)."""
    try:
        subprocess.Popen(
            ["shutdown", "-r", "+0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"success": True, "message": "Rebooting..."}
    except Exception as e:
        return {"success": False, "message": str(e)}
