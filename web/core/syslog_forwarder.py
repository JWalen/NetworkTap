"""Syslog forwarding configuration."""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config import get_config

logger = logging.getLogger("networktap.syslog")

RSYSLOG_CONF_DIR = Path("/etc/rsyslog.d")
NETWORKTAP_SYSLOG_CONF = RSYSLOG_CONF_DIR / "50-networktap-forward.conf"


@dataclass
class SyslogConfig:
    enabled: bool = False
    server: str = ""
    port: int = 514
    protocol: str = "udp"  # udp, tcp, or relp
    format: str = "syslog"  # syslog or json
    tls: bool = False
    ca_cert: str = ""


def get_syslog_config() -> SyslogConfig:
    """Read current syslog forwarding configuration."""
    config = SyslogConfig()
    
    if not NETWORKTAP_SYSLOG_CONF.exists():
        return config
    
    try:
        with open(NETWORKTAP_SYSLOG_CONF, "r") as f:
            content = f.read()
        
        config.enabled = True
        
        # Parse server and port
        if "@@" in content:
            config.protocol = "tcp"
            match = content.split("@@")[1].split()[0] if "@@" in content else ""
        elif "@" in content:
            config.protocol = "udp"
            match = content.split("@")[1].split()[0] if "@" in content else ""
        else:
            return config
        
        if ":" in match:
            config.server, port_str = match.split(":")
            config.port = int(port_str)
        else:
            config.server = match
        
        # Check for JSON format
        if "template=" in content.lower() or "json" in content.lower():
            config.format = "json"
        
        # Check for TLS
        if "StreamDriver" in content or "tls" in content.lower():
            config.tls = True
        
    except Exception as e:
        logger.error("Error reading syslog config: %s", e)
    
    return config


def configure_syslog(
    enabled: bool,
    server: str = "",
    port: int = 514,
    protocol: str = "udp",
    format: str = "syslog",
    tls: bool = False,
) -> tuple[bool, str]:
    """Configure syslog forwarding."""
    
    if not enabled:
        # Remove configuration
        if NETWORKTAP_SYSLOG_CONF.exists():
            try:
                NETWORKTAP_SYSLOG_CONF.unlink()
                _restart_rsyslog()
                return True, "Syslog forwarding disabled"
            except Exception as e:
                return False, str(e)
        return True, "Syslog forwarding already disabled"
    
    # Validate inputs
    if not server:
        return False, "Server address required"
    
    if protocol not in ("udp", "tcp"):
        return False, "Protocol must be 'udp' or 'tcp'"
    
    if format not in ("syslog", "json"):
        return False, "Format must be 'syslog' or 'json'"
    
    # Build configuration
    config_lines = [
        "# NetworkTap Syslog Forwarding Configuration",
        "# Managed by NetworkTap - do not edit manually",
        "",
    ]
    
    # JSON template if needed
    if format == "json":
        config_lines.extend([
            "# JSON format template",
            'template(name="NetworkTapJSON" type="list") {',
            '    constant(value="{")' ,
            '    constant(value="\\"timestamp\\":\\"") property(name="timereported" dateFormat="rfc3339")' ,
            '    constant(value="\\",\\"host\\":\\"") property(name="hostname")',
            '    constant(value="\\",\\"severity\\":\\"") property(name="syslogseverity-text")',
            '    constant(value="\\",\\"facility\\":\\"") property(name="syslogfacility-text")',
            '    constant(value="\\",\\"program\\":\\"") property(name="programname")',
            '    constant(value="\\",\\"message\\":\\"") property(name="msg" format="json")',
            '    constant(value="\\"}")',
            '    constant(value="\\n")',
            "}",
            "",
        ])
    
    # TLS configuration
    if tls and protocol == "tcp":
        config_lines.extend([
            "# TLS Configuration",
            '$DefaultNetstreamDriver gtls',
            '$DefaultNetstreamDriverCAFile /etc/ssl/certs/ca-certificates.crt',
            '$ActionSendStreamDriverMode 1',
            '$ActionSendStreamDriverAuthMode anon',
            "",
        ])
    
    # Forwarding rule
    proto_char = "@" if protocol == "udp" else "@@"
    
    if format == "json":
        forward_line = f'*.* {proto_char}{server}:{port};NetworkTapJSON'
    else:
        forward_line = f'*.* {proto_char}{server}:{port}'
    
    config_lines.extend([
        "# Forward all logs to remote server",
        forward_line,
    ])
    
    # Write configuration
    try:
        RSYSLOG_CONF_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(NETWORKTAP_SYSLOG_CONF, "w") as f:
            f.write("\n".join(config_lines))
        
        # Restart rsyslog
        success, msg = _restart_rsyslog()
        if not success:
            return False, f"Config saved but rsyslog restart failed: {msg}"
        
        logger.info("Syslog forwarding configured: %s:%d (%s, %s)", server, port, protocol, format)
        return True, f"Syslog forwarding enabled to {server}:{port}"
    
    except Exception as e:
        logger.error("Error configuring syslog: %s", e)
        return False, str(e)


def _restart_rsyslog() -> tuple[bool, str]:
    """Restart rsyslog service."""
    try:
        # First, validate config
        result = subprocess.run(
            ["rsyslogd", "-N1"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode != 0:
            return False, f"Config validation failed: {result.stderr}"
        
        # Restart service
        result = subprocess.run(
            ["systemctl", "restart", "rsyslog"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return False, result.stderr or "Restart failed"
        
        return True, "rsyslog restarted"
    
    except subprocess.TimeoutExpired:
        return False, "Restart timed out"
    except Exception as e:
        return False, str(e)


def test_syslog_connection(server: str, port: int, protocol: str = "udp") -> tuple[bool, str]:
    """Test connection to syslog server."""
    import socket
    
    try:
        sock_type = socket.SOCK_DGRAM if protocol == "udp" else socket.SOCK_STREAM
        
        with socket.socket(socket.AF_INET, sock_type) as s:
            s.settimeout(5)
            
            if protocol == "tcp":
                s.connect((server, port))
                # Send test message
                test_msg = "<14>NetworkTap syslog test message\n"
                s.send(test_msg.encode())
            else:
                # UDP just sends
                test_msg = "<14>NetworkTap syslog test message"
                s.sendto(test_msg.encode(), (server, port))
        
        return True, f"Successfully connected to {server}:{port} ({protocol})"
    
    except socket.timeout:
        return False, "Connection timed out"
    except socket.error as e:
        return False, f"Connection failed: {e}"
    except Exception as e:
        return False, str(e)


def get_syslog_status() -> dict:
    """Get rsyslog service status."""
    status = {
        "service_running": False,
        "forwarding_enabled": False,
        "config": None,
    }
    
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "rsyslog"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        status["service_running"] = result.stdout.strip() == "active"
    except Exception:
        pass
    
    config = get_syslog_config()
    status["forwarding_enabled"] = config.enabled
    if config.enabled:
        status["config"] = {
            "server": config.server,
            "port": config.port,
            "protocol": config.protocol,
            "format": config.format,
            "tls": config.tls,
        }
    
    return status
