"""Terminal quick-commands API endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from core.auth import verify_credentials

router = APIRouter()

# Allowed binaries for terminal execution
ALLOWED_COMMANDS = {
    "systemctl", "journalctl", "ip", "ifconfig", "ping", "traceroute",
    "netstat", "ss", "df", "du", "free", "top", "uptime", "uname",
    "cat", "tail", "head", "ls", "find", "grep", "wc", "ps",
    "tcpdump", "suricatasc", "zeekctl", "date", "hostname", "whoami",
    "id", "dmesg", "ethtool",
}

QUICK_COMMANDS = [
    {"label": "Service Status", "cmd": "systemctl status networktap-*"},
    {"label": "Interface Info", "cmd": "ip addr show"},
    {"label": "Disk Usage", "cmd": "df -h"},
    {"label": "Memory", "cmd": "free -h"},
    {"label": "Capture Status", "cmd": "systemctl status networktap-capture"},
    {"label": "Suricata Status", "cmd": "systemctl status networktap-suricata"},
    {"label": "Zeek Status", "cmd": "systemctl status networktap-zeek"},
    {"label": "Recent Syslog", "cmd": "tail -50 /var/log/syslog"},
    {"label": "Network Connections", "cmd": "ss -tuln"},
    {"label": "System Uptime", "cmd": "uptime"},
]


def validate_command(cmd: str) -> str | None:
    """Validate a command against the whitelist.

    Returns an error message if invalid, None if valid.
    """
    parts = cmd.strip().split()
    if not parts:
        return "Empty command"

    binary = parts[0].split("/")[-1]  # Handle absolute paths
    if binary not in ALLOWED_COMMANDS:
        return f"Command '{binary}' is not allowed"

    # Block piping to disallowed commands
    for i, part in enumerate(parts):
        if part in ("|", "&&", "||", ";") and i + 1 < len(parts):
            next_bin = parts[i + 1].split("/")[-1]
            if next_bin not in ALLOWED_COMMANDS:
                return f"Piped command '{next_bin}' is not allowed"

    # Block shell redirects to files (write)
    for part in parts:
        if part.startswith(">") or part == ">>":
            return "Output redirection is not allowed"

    return None


@router.get("/quick-commands")
async def get_quick_commands(user: Annotated[str, Depends(verify_credentials)]):
    """Get list of predefined quick commands."""
    return {"commands": QUICK_COMMANDS}
