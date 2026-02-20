"""Configuration management API endpoints."""

import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.auth import verify_credentials
from core.config import get_config, CONFIG_PATHS
from core.network_manager import get_mode, switch_mode

router = APIRouter()


class ModeSwitch(BaseModel):
    mode: str


# Map of config field name -> conf file KEY.
# Only settings listed here are editable via the API.
EDITABLE_SETTINGS: dict[str, dict] = {
    # Network Interfaces
    "nic1":                     {"key": "NIC1",                     "type": "str"},
    "nic2":                     {"key": "NIC2",                     "type": "str"},
    # Capture
    "capture_dir":              {"key": "CAPTURE_DIR",              "type": "str"},
    "capture_iface":            {"key": "CAPTURE_IFACE",            "type": "str"},
    "capture_rotate_seconds":   {"key": "CAPTURE_ROTATE_SECONDS",   "type": "int"},
    "capture_file_limit":       {"key": "CAPTURE_FILE_LIMIT",       "type": "int"},
    "capture_snaplen":          {"key": "CAPTURE_SNAPLEN",          "type": "int"},
    "capture_filter":           {"key": "CAPTURE_FILTER",           "type": "str"},
    "capture_compress":         {"key": "CAPTURE_COMPRESS",         "type": "bool"},
    # Retention
    "retention_days":           {"key": "RETENTION_DAYS",           "type": "int"},
    "min_free_disk_pct":        {"key": "MIN_FREE_DISK_PCT",        "type": "int"},
    # Suricata
    "suricata_enabled":         {"key": "SURICATA_ENABLED",         "type": "bool"},
    "suricata_iface":           {"key": "SURICATA_IFACE",           "type": "str"},
    # Zeek
    "zeek_enabled":             {"key": "ZEEK_ENABLED",             "type": "bool"},
    "zeek_iface":               {"key": "ZEEK_IFACE",              "type": "str"},
    # Web
    "web_host":                 {"key": "WEB_HOST",                 "type": "str"},
    "web_port":                 {"key": "WEB_PORT",                 "type": "int"},
    # TLS
    "tls_enabled":              {"key": "TLS_ENABLED",              "type": "bool"},
    "tls_cert":                 {"key": "TLS_CERT",                 "type": "str"},
    "tls_key":                  {"key": "TLS_KEY",                  "type": "str"},
    # Syslog
    "syslog_enabled":           {"key": "SYSLOG_ENABLED",           "type": "bool"},
    "syslog_server":            {"key": "SYSLOG_SERVER",            "type": "str"},
    "syslog_port":              {"key": "SYSLOG_PORT",              "type": "int"},
    "syslog_protocol":          {"key": "SYSLOG_PROTOCOL",          "type": "str"},
    "syslog_format":            {"key": "SYSLOG_FORMAT",            "type": "str"},
    # Logging
    "log_level":                {"key": "LOG_LEVEL",                "type": "str"},
    # WiFi Capture
    "wifi_capture_iface":       {"key": "WIFI_CAPTURE_IFACE",       "type": "str"},
    "wifi_capture_enabled":     {"key": "WIFI_CAPTURE_ENABLED",     "type": "bool"},
    "wifi_capture_channel":     {"key": "WIFI_CAPTURE_CHANNEL",     "type": "int"},
    "wifi_capture_max_size_mb": {"key": "WIFI_CAPTURE_MAX_SIZE_MB", "type": "int"},
    "wifi_capture_max_files":   {"key": "WIFI_CAPTURE_MAX_FILES",   "type": "int"},
    "wifi_capture_filter":      {"key": "WIFI_CAPTURE_FILTER",      "type": "str"},
    # FR202 Display
    "display_enabled":            {"key": "DISPLAY_ENABLED",            "type": "bool"},
    "display_refresh":            {"key": "DISPLAY_REFRESH",            "type": "int"},
    "display_backlight_timeout":  {"key": "DISPLAY_BACKLIGHT_TIMEOUT",  "type": "int"},
    "display_default_page":       {"key": "DISPLAY_DEFAULT_PAGE",       "type": "str"},
    "display_screensaver":        {"key": "DISPLAY_SCREENSAVER",        "type": "bool"},
    "display_screensaver_color":  {"key": "DISPLAY_SCREENSAVER_COLOR",  "type": "str"},
    # AI
    "anomaly_detection_enabled": {"key": "ANOMALY_DETECTION_ENABLED", "type": "bool"},
    "anomaly_sensitivity":      {"key": "ANOMALY_SENSITIVITY",      "type": "str"},
    "anomaly_interval":         {"key": "ANOMALY_INTERVAL",         "type": "int"},
    "ai_assistant_enabled":     {"key": "AI_ASSISTANT_ENABLED",     "type": "bool"},
    "ollama_url":               {"key": "OLLAMA_URL",               "type": "str"},
    "ollama_model":             {"key": "OLLAMA_MODEL",             "type": "str"},
}


def _find_config_path() -> Path | None:
    """Find the writable config file."""
    for p in CONFIG_PATHS:
        path = Path(p)
        if path.exists():
            return path
    return None


def _update_conf_file(path: Path, updates: dict[str, str]) -> None:
    """Update KEY=VALUE pairs in the config file, preserving comments/order."""
    lines = path.read_text().splitlines()
    updated_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # Append any keys that weren't already in the file
    for key, val in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={val}")

    path.write_text("\n".join(new_lines) + "\n")


@router.get("/")
async def get_configuration(user: Annotated[str, Depends(verify_credentials)]):
    """Get current configuration (sensitive fields redacted)."""
    config = get_config()
    return {
        # Read-only system info
        "mode": config.mode,
        "nic1": config.nic1,
        "nic2": config.nic2,
        "bridge_name": config.bridge_name,
        "capture_interface": config.capture_interface,
        "management_interface": config.management_interface,
        # Capture
        "capture_dir": config.capture_dir,
        "capture_iface": config.capture_iface,
        "capture_rotate_seconds": config.capture_rotate_seconds,
        "capture_file_limit": config.capture_file_limit,
        "capture_snaplen": config.capture_snaplen,
        "capture_filter": config.capture_filter,
        "capture_compress": config.capture_compress,
        # Retention
        "retention_days": config.retention_days,
        "min_free_disk_pct": config.min_free_disk_pct,
        # Suricata
        "suricata_enabled": config.suricata_enabled,
        "suricata_iface": config.suricata_iface,
        # Zeek
        "zeek_enabled": config.zeek_enabled,
        "zeek_iface": config.zeek_iface,
        # Web
        "web_host": config.web_host,
        "web_port": config.web_port,
        # TLS
        "tls_enabled": config.tls_enabled,
        "tls_cert": config.tls_cert,
        "tls_key": config.tls_key,
        # Syslog
        "syslog_enabled": config.syslog_enabled,
        "syslog_server": config.syslog_server,
        "syslog_port": config.syslog_port,
        "syslog_protocol": config.syslog_protocol,
        "syslog_format": config.syslog_format,
        # Logging
        "log_level": config.log_level,
        # WiFi Capture
        "wifi_capture_iface": config.wifi_capture_iface,
        "wifi_capture_enabled": config.wifi_capture_enabled,
        "wifi_capture_channel": config.wifi_capture_channel,
        "wifi_capture_max_size_mb": config.wifi_capture_max_size_mb,
        "wifi_capture_max_files": config.wifi_capture_max_files,
        "wifi_capture_filter": config.wifi_capture_filter,
        # FR202 Display
        "display_enabled": config.display_enabled,
        "display_refresh": config.display_refresh,
        "display_backlight_timeout": config.display_backlight_timeout,
        "display_default_page": config.display_default_page,
        # AI
        "anomaly_detection_enabled": config.anomaly_detection_enabled,
        "anomaly_sensitivity": config.anomaly_sensitivity,
        "anomaly_interval": config.anomaly_interval,
        "ai_assistant_enabled": config.ai_assistant_enabled,
        "ollama_url": config.ollama_url,
        "ollama_model": config.ollama_model,
    }


@router.put("/")
async def update_configuration(
    body: dict,
    user: Annotated[str, Depends(verify_credentials)],
):
    """Update configuration settings. Only whitelisted keys are accepted."""
    config_path = _find_config_path()
    if not config_path:
        return {"success": False, "message": "Config file not found"}

    updates: dict[str, str] = {}
    errors: list[str] = []

    for field_name, value in body.items():
        if field_name not in EDITABLE_SETTINGS:
            errors.append(f"Unknown or read-only setting: {field_name}")
            continue

        spec = EDITABLE_SETTINGS[field_name]
        conf_key = spec["key"]
        field_type = spec["type"]

        # Validate and convert to conf-file string format
        try:
            if field_type == "bool":
                if isinstance(value, bool):
                    updates[conf_key] = "yes" if value else "no"
                elif isinstance(value, str):
                    updates[conf_key] = "yes" if value.lower() in ("yes", "true", "1") else "no"
                else:
                    errors.append(f"{field_name}: expected boolean")
                    continue
            elif field_type == "int":
                updates[conf_key] = str(int(value))
            else:
                # Sanitize: no newlines or shell metacharacters in values
                str_val = str(value)
                if re.search(r'[\n\r;`$]', str_val):
                    errors.append(f"{field_name}: contains invalid characters")
                    continue
                updates[conf_key] = str_val
        except (ValueError, TypeError):
            errors.append(f"{field_name}: invalid value")

    if not updates:
        return {"success": False, "message": "No valid settings to update", "errors": errors}

    try:
        _update_conf_file(config_path, updates)
        # Clear cached config so next read picks up changes
        get_config.cache_clear()
    except Exception as e:
        return {"success": False, "message": f"Failed to write config: {e}"}

    # If NIC assignments changed, re-run network and firewall configuration
    # to update systemd-networkd files and UFW rules
    nic_changed = "NIC1" in updates or "NIC2" in updates
    if nic_changed:
        try:
            import subprocess
            subprocess.run(
                ["bash", "/opt/networktap/setup/configure_network.sh"],
                timeout=30,
                check=True,
            )
            subprocess.run(
                ["bash", "/opt/networktap/setup/configure_firewall.sh"],
                timeout=30,
                check=True,
            )
        except Exception as e:
            return {
                "success": True,
                "message": f"Config saved but reconfiguration failed: {e}",
                "updated": list(updates.keys()),
                "warning": "NIC assignments saved but network/firewall was not fully reconfigured. Reboot to apply.",
            }

    result = {"success": True, "updated": list(updates.keys())}
    if nic_changed:
        result["message"] = f"Updated {len(updates)} setting(s). Network interfaces reconfigured."
    else:
        result["message"] = f"Updated {len(updates)} setting(s)"
    if errors:
        result["errors"] = errors
    return result


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
