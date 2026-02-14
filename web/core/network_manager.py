"""Network interface management."""

import ipaddress
import logging
import re
import subprocess
from pathlib import Path

from core.config import get_config

logger = logging.getLogger("networktap.network")

CONFIG_FILE = Path("/etc/networktap.conf")


def get_mode() -> dict:
    """Get current operating mode."""
    config = get_config()
    return {
        "mode": config.mode,
        "nic1": config.nic1,
        "nic2": config.nic2,
        "bridge_name": config.bridge_name,
        "capture_interface": config.capture_interface,
        "management_interface": config.management_interface,
    }


def get_mgmt_network_config() -> dict:
    """Get current management network configuration."""
    config = get_config()
    
    # Get current IP from the management interface
    mgmt_iface = config.management_interface
    current_ip = None
    current_gateway = None
    current_dns = None
    
    try:
        # Get current IP address
        result = subprocess.run(
            ["ip", "-j", "addr", "show", mgmt_iface],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            if data and data[0].get("addr_info"):
                for addr in data[0]["addr_info"]:
                    if addr.get("family") == "inet":
                        current_ip = f"{addr['local']}/{addr['prefixlen']}"
                        break
        
        # Get current default gateway
        result = subprocess.run(
            ["ip", "-j", "route", "show", "default"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            import json
            routes = json.loads(result.stdout)
            for route in routes:
                if route.get("dev") == mgmt_iface:
                    current_gateway = route.get("gateway")
                    break
        
        # Get current DNS from resolv.conf
        resolv = Path("/etc/resolv.conf")
        if resolv.exists():
            for line in resolv.read_text().splitlines():
                if line.startswith("nameserver"):
                    current_dns = line.split()[1]
                    break
                    
    except Exception as e:
        logger.warning("Failed to get current network info: %s", e)
    
    return {
        "mode": "dhcp" if config.mgmt_ip == "dhcp" else "static",
        "interface": mgmt_iface,
        "configured_ip": config.mgmt_ip,
        "configured_gateway": getattr(config, 'mgmt_gateway', None),
        "configured_dns": getattr(config, 'mgmt_dns', None),
        "current_ip": current_ip,
        "current_gateway": current_gateway,
        "current_dns": current_dns,
    }


def set_mgmt_network_config(
    mode: str,
    ip_address: str | None = None,
    gateway: str | None = None,
    dns: str | None = None,
) -> dict:
    """Set management network configuration (DHCP or static)."""
    
    if mode not in ("dhcp", "static"):
        return {"success": False, "message": "Mode must be 'dhcp' or 'static'"}
    
    if mode == "static":
        # Validate IP address with CIDR
        if not ip_address:
            return {"success": False, "message": "IP address required for static mode"}
        
        try:
            # Validate IP/prefix format
            if "/" not in ip_address:
                return {"success": False, "message": "IP address must include prefix (e.g., 192.168.1.100/24)"}
            network = ipaddress.ip_interface(ip_address)
        except ValueError as e:
            return {"success": False, "message": f"Invalid IP address: {e}"}
        
        # Validate gateway if provided
        if gateway:
            try:
                gw = ipaddress.ip_address(gateway)
            except ValueError as e:
                return {"success": False, "message": f"Invalid gateway: {e}"}
        
        # Validate DNS if provided
        if dns:
            try:
                for d in dns.split(","):
                    ipaddress.ip_address(d.strip())
            except ValueError as e:
                return {"success": False, "message": f"Invalid DNS: {e}"}
    
    # Read current config
    if not CONFIG_FILE.exists():
        return {"success": False, "message": "Config file not found"}
    
    config_text = CONFIG_FILE.read_text()
    lines = config_text.splitlines()
    new_lines = []
    
    # Track what we've updated
    updated_ip = False
    updated_gateway = False
    updated_dns = False
    
    def matches_key(line: str, key: str) -> bool:
        """Check if line is a config entry for key (commented or not)."""
        line = line.lstrip("#").lstrip()
        return line.startswith(f"{key}=")

    for line in lines:
        stripped = line.strip()

        # Update MGMT_IP
        if matches_key(stripped, "MGMT_IP"):
            if mode == "dhcp":
                new_lines.append("MGMT_IP=dhcp")
            else:
                new_lines.append(f"MGMT_IP={ip_address}")
            updated_ip = True
            continue

        # Update MGMT_GATEWAY
        if matches_key(stripped, "MGMT_GATEWAY"):
            if mode == "static" and gateway:
                new_lines.append(f"MGMT_GATEWAY={gateway}")
            else:
                new_lines.append("# MGMT_GATEWAY=")
            updated_gateway = True
            continue

        # Update MGMT_DNS
        if matches_key(stripped, "MGMT_DNS"):
            if mode == "static" and dns:
                new_lines.append(f"MGMT_DNS={dns}")
            else:
                new_lines.append("# MGMT_DNS=8.8.8.8")
            updated_dns = True
            continue

        new_lines.append(line)
    
    # Add missing entries if not found
    if not updated_ip:
        if mode == "dhcp":
            new_lines.append("MGMT_IP=dhcp")
        else:
            new_lines.append(f"MGMT_IP={ip_address}")
    
    if not updated_gateway and mode == "static" and gateway:
        new_lines.append(f"MGMT_GATEWAY={gateway}")
    
    if not updated_dns and mode == "static" and dns:
        new_lines.append(f"MGMT_DNS={dns}")
    
    # Write config
    try:
        CONFIG_FILE.write_text("\n".join(new_lines) + "\n")
    except Exception as e:
        return {"success": False, "message": f"Failed to write config: {e}"}
    
    # Apply network configuration
    try:
        result = subprocess.run(
            ["/opt/networktap/setup/configure_network.sh"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.error("Network config failed: %s", result.stderr)
            return {
                "success": False, 
                "message": f"Config saved but failed to apply: {result.stderr.strip()}"
            }
    except FileNotFoundError:
        # Script not found, try restarting networkd directly
        subprocess.run(["systemctl", "restart", "systemd-networkd"], timeout=30)
    except subprocess.SubprocessError as e:
        return {"success": False, "message": f"Failed to apply config: {e}"}
    
    # Clear config cache
    from core.config import get_config as gc
    gc.cache_clear()
    
    logger.info("Management network configured: mode=%s, ip=%s", mode, ip_address or "dhcp")
    
    if mode == "static":
        return {
            "success": True,
            "message": f"Static IP configured: {ip_address}",
            "warning": "If you changed the IP, you may need to reconnect to the new address."
        }
    else:
        return {"success": True, "message": "DHCP enabled"}


def switch_mode(new_mode: str) -> dict:
    """Switch between SPAN and bridge mode."""
    if new_mode not in ("span", "bridge"):
        return {"success": False, "message": f"Invalid mode: {new_mode}"}

    config = get_config()
    if new_mode == config.mode:
        return {"success": False, "message": f"Already in {new_mode} mode"}

    try:
        result = subprocess.run(
            ["/opt/networktap/scripts/switch_mode.sh", new_mode],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            logger.info("Switched to %s mode", new_mode)
            # Clear config cache to reload
            from core.config import get_config as gc
            gc.cache_clear()
            return {"success": True, "message": f"Switched to {new_mode} mode"}
        else:
            logger.error("Mode switch failed: %s", result.stderr)
            return {"success": False, "message": result.stderr.strip() or result.stdout.strip()}
    except subprocess.SubprocessError as e:
        return {"success": False, "message": str(e)}


def get_interface_detail(iface_name: str) -> dict | None:
    """Get detailed information for a specific interface."""
    try:
        result = subprocess.run(
            ["ip", "-j", "addr", "show", iface_name],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None

        import json
        data = json.loads(result.stdout)
        if not data:
            return None

        iface = data[0]
        return {
            "name": iface.get("ifname"),
            "state": iface.get("operstate", "UNKNOWN").lower(),
            "mtu": iface.get("mtu"),
            "mac": iface.get("address"),
            "flags": iface.get("flags", []),
            "addresses": [
                {"address": a["local"], "prefix": a["prefixlen"], "family": a["family"]}
                for a in iface.get("addr_info", [])
            ],
        }
    except (subprocess.SubprocessError, Exception) as e:
        logger.error("Failed to get interface detail for %s: %s", iface_name, e)
        return None


def identify_port(iface_name: str, duration: int = 5) -> dict:
    """Blink the LED on a network port for physical identification.

    Uses ethtool -p (--identify) which causes the NIC LED to flash.
    Not all drivers support this; Intel NICs generally do.
    """
    import re
    import psutil

    # Validate interface name format (alphanumeric, hyphens, dots, underscores)
    if not re.match(r'^[a-zA-Z0-9._-]+$', iface_name):
        return {"success": False, "message": "Invalid interface name"}

    # Validate against known system interfaces
    known = set(psutil.net_if_stats().keys())
    if iface_name not in known:
        return {"success": False, "message": f"Unknown interface: {iface_name}"}

    # Clamp duration
    duration = max(1, min(duration, 15))

    try:
        result = subprocess.run(
            ["ethtool", "-p", iface_name, str(duration)],
            capture_output=True, text=True, timeout=duration + 5,
        )
        if result.returncode == 0:
            logger.info("Identified port %s (%ds)", iface_name, duration)
            return {"success": True, "message": f"Blinking {iface_name} for {duration}s"}
        else:
            err = result.stderr.strip()
            if "not supported" in err.lower() or "operation not supported" in err.lower():
                return {"success": False, "message": f"NIC driver for {iface_name} does not support LED identification"}
            return {"success": False, "message": err or "ethtool failed"}
    except FileNotFoundError:
        return {"success": False, "message": "ethtool is not installed"}
    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Identify command timed out"}
    except subprocess.SubprocessError as e:
        return {"success": False, "message": str(e)}


def get_bridge_status() -> dict | None:
    """Get bridge interface status if in bridge mode."""
    config = get_config()
    if config.mode != "bridge":
        return None

    try:
        result = subprocess.run(
            ["bridge", "-j", "link", "show"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None

        import json
        links = json.loads(result.stdout)
        members = [l for l in links if l.get("master") == config.bridge_name]

        return {
            "bridge": config.bridge_name,
            "members": [
                {"name": m["ifname"], "state": m.get("state", "unknown")}
                for m in members
            ],
        }
    except (subprocess.SubprocessError, Exception):
        return None
