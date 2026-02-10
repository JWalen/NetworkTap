"""WiFi management API endpoints."""

import asyncio
import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.auth import verify_credentials

router = APIRouter()

WIFI_SCRIPT = "/opt/networktap/scripts/wifi.sh"


def _find_wifi_iface() -> str | None:
    """Check if a wireless interface exists on the system."""
    wifi_dir = Path("/sys/class/net")
    if not wifi_dir.exists():
        return None
    for iface in wifi_dir.iterdir():
        if (iface / "wireless").exists() or (iface / "phy80211").exists():
            return iface.name
    return None


async def _run_wifi(args: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Run wifi.sh asynchronously to avoid blocking the event loop."""
    iface = _find_wifi_iface()
    if not iface:
        return 1, "", "No WiFi interface found"

    env = {**os.environ, "WIFI_IFACE": iface}
    proc = await asyncio.create_subprocess_exec(
        WIFI_SCRIPT, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return 1, "", "Command timed out"

    return proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")


class WiFiConnect(BaseModel):
    ssid: str
    psk: str


@router.get("/status")
async def wifi_status(user: Annotated[str, Depends(verify_credentials)]):
    """Get WiFi connection status."""
    iface = _find_wifi_iface()
    if not iface:
        return {"available": False, "connected": False}

    try:
        rc, stdout, stderr = await _run_wifi(["status"])
        status = {}
        for line in stdout.strip().splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                status[key.strip().lower()] = val.strip()

        return {"available": True, "connected": bool(status.get("ip") and status.get("ip") != "(none)"), **status}
    except Exception as e:
        return {"available": True, "connected": False, "error": str(e)}


@router.get("/scan")
async def wifi_scan(user: Annotated[str, Depends(verify_credentials)]):
    """Scan for available WiFi networks."""
    try:
        rc, stdout, stderr = await _run_wifi(["scan"], timeout=30)
        networks = []
        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("["):
                continue
            parts = line.split()
            if len(parts) >= 4:
                ssid = parts[0]
                networks.append({"ssid": ssid, "raw": line})

        return {"networks": networks}
    except Exception as e:
        return {"networks": [], "error": str(e)}


@router.post("/connect")
async def wifi_connect(
    body: WiFiConnect,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Connect to a WiFi network."""
    try:
        rc, stdout, stderr = await _run_wifi(["connect", body.ssid, body.psk], timeout=30)
        success = rc == 0 and "Connected" in stdout
        return {
            "success": success,
            "message": stdout.strip().split("\n")[-1] if stdout else stderr.strip(),
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/disconnect")
async def wifi_disconnect(user: Annotated[str, Depends(verify_credentials)]):
    """Disconnect from WiFi."""
    try:
        rc, stdout, stderr = await _run_wifi(["disconnect"])
        return {"success": rc == 0, "message": "Disconnected"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/forget")
async def wifi_forget(user: Annotated[str, Depends(verify_credentials)]):
    """Remove saved WiFi configuration."""
    try:
        rc, stdout, stderr = await _run_wifi(["forget"])
        return {"success": rc == 0, "message": "WiFi configuration removed"}
    except Exception as e:
        return {"success": False, "message": str(e)}
