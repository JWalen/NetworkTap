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
AP_SCRIPT = "/opt/networktap/scripts/ap.sh"
WIFI_CAPTURE_SCRIPT = "/opt/networktap/scripts/wifi_capture.sh"


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


async def _run_ap(args: list[str], timeout: int = 15) -> tuple[int, str, str]:
    """Run ap.sh asynchronously for Access Point management."""
    proc = await asyncio.create_subprocess_exec(
        AP_SCRIPT, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return 1, "", "Command timed out"

    return proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")


async def _run_wifi_capture(args: list[str], timeout: int = 20) -> tuple[int, str, str]:
    """Run wifi_capture.sh asynchronously for monitor mode capture."""
    proc = await asyncio.create_subprocess_exec(
        WIFI_CAPTURE_SCRIPT, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
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


class APConfig(BaseModel):
    """Access Point configuration."""
    ssid: str
    passphrase: str
    channel: int = 11


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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Access Point (AP) Mode Endpoints
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/ap/status")
async def ap_status(user: Annotated[str, Depends(verify_credentials)]):
    """Get Access Point status and configuration."""
    try:
        rc, stdout, stderr = await _run_ap(["status"], timeout=10)
        
        # Parse status output
        status_info = {
            "enabled": False,
            "running": False,
            "ssid": None,
            "channel": None,
            "ip": None,
            "clients": 0,
        }
        
        current_section = None
        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line or "━" in line:
                continue
            
            if line.startswith("Configuration:"):
                current_section = "config"
            elif line.startswith("Services:"):
                current_section = "services"
            elif line.startswith("Connected Clients:"):
                current_section = "clients"
            elif ":" in line and current_section:
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip()
                
                if current_section == "config":
                    if key == "enabled":
                        status_info["enabled"] = value == "yes"
                    elif key == "ssid":
                        status_info["ssid"] = value
                    elif key == "channel":
                        status_info["channel"] = value
                    elif key == "ip":
                        status_info["ip"] = value
                elif current_section == "services":
                    if key == "hostapd" and value == "active":
                        status_info["running"] = True
                elif current_section == "clients":
                    if key == "count":
                        status_info["clients"] = int(value) if value.isdigit() else 0
        
        return status_info
    except Exception as e:
        return {"enabled": False, "running": False, "error": str(e)}


@router.post("/ap/start")
async def ap_start(user: Annotated[str, Depends(verify_credentials)]):
    """Start the WiFi Access Point."""
    try:
        rc, stdout, stderr = await _run_ap(["start"], timeout=30)
        success = rc == 0 and "started successfully" in stdout.lower()
        
        # Extract SSID from output
        ssid = None
        for line in stdout.splitlines():
            if "SSID:" in line:
                ssid = line.split("SSID:")[-1].strip()
                break
        
        return {
            "success": success,
            "message": "Access Point started" if success else (stderr or "Failed to start AP"),
            "ssid": ssid,
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/ap/stop")
async def ap_stop(user: Annotated[str, Depends(verify_credentials)]):
    """Stop the WiFi Access Point."""
    try:
        rc, stdout, stderr = await _run_ap(["stop"], timeout=20)
        success = rc == 0
        return {
            "success": success,
            "message": "Access Point stopped" if success else (stderr or "Failed to stop AP"),
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/ap/restart")
async def ap_restart(user: Annotated[str, Depends(verify_credentials)]):
    """Restart the WiFi Access Point."""
    try:
        rc, stdout, stderr = await _run_ap(["restart"], timeout=40)
        success = rc == 0 and "started successfully" in stdout.lower()
        return {
            "success": success,
            "message": "Access Point restarted" if success else (stderr or "Failed to restart AP"),
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/ap/clients")
async def ap_clients(user: Annotated[str, Depends(verify_credentials)]):
    """List connected Access Point clients."""
    try:
        rc, stdout, stderr = await _run_ap(["clients"], timeout=10)
        
        clients = []
        for line in stdout.strip().splitlines():
            line = line.strip()
            if line.startswith("MAC:"):
                mac = line.replace("MAC:", "").strip()
                clients.append({"mac": mac, "connected": True})
            elif "(" in line and ")" in line:
                # dnsmasq lease format: "MAC (hostname)"
                parts = line.split()
                if len(parts) >= 2:
                    clients.append({
                        "mac": parts[0],
                        "hostname": parts[1].strip("()"),
                        "connected": True,
                    })
        
        return {"clients": clients, "count": len(clients)}
    except Exception as e:
        return {"clients": [], "count": 0, "error": str(e)}


@router.post("/ap/configure")
async def ap_configure(
    config: APConfig,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Update Access Point configuration (requires restart)."""
    try:
        from core.config import get_config
        
        config_path = Path("/etc/networktap.conf")
        if not config_path.exists():
            return {"success": False, "message": "Config file not found"}
        
        # Read current config
        lines = config_path.read_text().splitlines()
        
        # Update AP settings
        updated = False
        new_lines = []
        for line in lines:
            if line.startswith("WIFI_AP_SSID="):
                new_lines.append(f"WIFI_AP_SSID={config.ssid}")
                updated = True
            elif line.startswith("WIFI_AP_PASSPHRASE="):
                new_lines.append(f"WIFI_AP_PASSPHRASE={config.passphrase}")
                updated = True
            elif line.startswith("WIFI_AP_CHANNEL="):
                new_lines.append(f"WIFI_AP_CHANNEL={config.channel}")
                updated = True
            else:
                new_lines.append(line)
        
        # Write back
        config_path.write_text("\n".join(new_lines) + "\n")
        
        # Update hostapd config
        hostapd_conf = Path("/etc/hostapd/hostapd.conf")
        if hostapd_conf.exists():
            hostapd_lines = hostapd_conf.read_text().splitlines()
            new_hostapd = []
            for line in hostapd_lines:
                if line.startswith("ssid="):
                    new_hostapd.append(f"ssid={config.ssid}")
                elif line.startswith("wpa_passphrase="):
                    new_hostapd.append(f"wpa_passphrase={config.passphrase}")
                elif line.startswith("channel="):
                    new_hostapd.append(f"channel={config.channel}")
                else:
                    new_hostapd.append(line)
            hostapd_conf.write_text("\n".join(new_hostapd) + "\n")
        
        # Clear config cache
        get_config.cache_clear()
        
        return {
            "success": True,
            "message": "Configuration updated. Restart AP to apply changes.",
            "requires_restart": True,
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WiFi Packet Capture (Monitor Mode) Endpoints
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/capture/status")
async def wifi_capture_status(user: Annotated[str, Depends(verify_credentials)]):
    """Get WiFi packet capture status."""
    try:
        rc, stdout, stderr = await _run_wifi_capture(["status"], timeout=10)
        
        status_info = {
            "enabled": False,
            "running": False,
            "channel": None,
            "max_size_mb": None,
            "max_files": None,
            "file_count": 0,
            "total_size": None,
        }
        
        current_section = None
        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line or "━" in line:
                continue
            
            if "Configuration:" in line:
                current_section = "config"
            elif "Capture:" in line:
                current_section = "capture"
            elif "Storage:" in line:
                current_section = "storage"
            elif ":" in line and current_section:
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip()
                
                if current_section == "config":
                    if key == "enabled":
                        status_info["enabled"] = value == "yes"
                    elif key == "channel":
                        status_info["channel"] = value
                    elif key == "max size":
                        status_info["max_size_mb"] = value.replace("MB", "").strip()
                    elif key == "max files":
                        status_info["max_files"] = value
                elif current_section == "capture":
                    if key == "status":
                        status_info["running"] = value == "RUNNING"
                elif current_section == "storage":
                    if key == "files":
                        status_info["file_count"] = int(value) if value.isdigit() else 0
                    elif key == "total size":
                        status_info["total_size"] = value
        
        return status_info
    except Exception as e:
        return {"enabled": False, "running": False, "error": str(e)}


@router.post("/capture/start")
async def wifi_capture_start(user: Annotated[str, Depends(verify_credentials)]):
    """Start WiFi packet capture in monitor mode."""
    try:
        rc, stdout, stderr = await _run_wifi_capture(["start"], timeout=30)
        success = rc == 0 and "started" in stdout.lower()
        
        return {
            "success": success,
            "message": "WiFi capture started" if success else (stderr or "Failed to start capture"),
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/capture/stop")
async def wifi_capture_stop(user: Annotated[str, Depends(verify_credentials)]):
    """Stop WiFi packet capture."""
    try:
        rc, stdout, stderr = await _run_wifi_capture(["stop"], timeout=20)
        success = rc == 0
        return {
            "success": success,
            "message": "WiFi capture stopped" if success else (stderr or "Failed to stop capture"),
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/capture/restart")
async def wifi_capture_restart(user: Annotated[str, Depends(verify_credentials)]):
    """Restart WiFi packet capture."""
    try:
        rc, stdout, stderr = await _run_wifi_capture(["restart"], timeout=40)
        success = rc == 0 and "started" in stdout.lower()
        return {
            "success": success,
            "message": "WiFi capture restarted" if success else (stderr or "Failed to restart capture"),
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/capture/list")
async def wifi_capture_list(user: Annotated[str, Depends(verify_credentials)]):
    """List WiFi capture files."""
    try:
        rc, stdout, stderr = await _run_wifi_capture(["list"], timeout=10)
        
        captures = []
        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line or "━" in line or "WiFi Capture Files:" in line or "(No captures" in line:
                continue
            
            # Parse format: "2024-01-15 10:30:00  100.50 MB  wifi-20240115-103000.pcap"
            parts = line.split()
            if len(parts) >= 4:
                date_part = f"{parts[0]} {parts[1]}"
                size_part = parts[2]
                filename = parts[3] if len(parts) == 4 else " ".join(parts[3:])
                
                captures.append({
                    "filename": filename,
                    "size": size_part,
                    "date": date_part,
                })
        
        return {"captures": captures, "count": len(captures)}
    except Exception as e:
        return {"captures": [], "count": 0, "error": str(e)}
