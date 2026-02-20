"""Configuration loader for NetworkTap."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from functools import lru_cache


CONFIG_PATHS = [
    "/etc/networktap.conf",
    "/opt/networktap/networktap.conf",
    Path(__file__).parent.parent.parent / "networktap.conf",
]


def _read_conf(path: Path) -> dict[str, str]:
    """Parse a shell-style KEY=VALUE config file."""
    values = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            # Strip surrounding quotes
            val = val.strip().strip('"').strip("'")
            values[key.strip()] = val
    return values


@dataclass
class NetworkTapConfig:
    # Mode
    mode: str = "span"

    # Interfaces
    nic1: str = "eth0"
    nic2: str = "eth1"
    bridge_name: str = "br0"

    # Management Network
    mgmt_ip: str = "dhcp"
    mgmt_gateway: str = ""
    mgmt_dns: str = "8.8.8.8"

    # Capture
    capture_dir: str = "/var/lib/networktap/captures"
    capture_iface: str = "auto"
    capture_rotate_seconds: int = 3600
    capture_file_limit: int = 0
    capture_snaplen: int = 0
    capture_filter: str = ""
    capture_compress: bool = True

    # Retention
    retention_days: int = 7
    min_free_disk_pct: int = 10

    # Suricata
    suricata_enabled: bool = True
    suricata_config: str = "/etc/suricata/suricata.yaml"
    suricata_log_dir: str = "/var/log/suricata"
    suricata_eve_log: str = "/var/log/suricata/eve.json"
    suricata_iface: str = "auto"

    # Zeek
    zeek_enabled: bool = True
    zeek_log_dir: str = "/var/log/zeek"
    zeek_iface: str = "auto"

    # Web
    web_host: str = "0.0.0.0"
    web_port: int = 8443
    web_user: str = "admin"
    web_pass: str = "networktap"
    web_secret: str = "change-me"

    # TLS
    tls_enabled: bool = False
    tls_cert: str = "/etc/networktap/tls/server.crt"
    tls_key: str = "/etc/networktap/tls/server.key"

    # Syslog forwarding
    syslog_enabled: bool = False
    syslog_server: str = ""
    syslog_port: int = 514
    syslog_protocol: str = "udp"
    syslog_format: str = "syslog"

    # Logging
    log_dir: str = "/var/log/networktap"
    log_level: str = "INFO"

    # WiFi Capture
    wifi_capture_enabled: bool = False
    wifi_capture_channel: int = 11
    wifi_capture_max_size_mb: int = 100
    wifi_capture_max_files: int = 50
    wifi_capture_filter: str = ""

    # FR202 Display
    display_enabled: bool = True
    display_refresh: int = 5
    display_backlight_timeout: int = 120
    display_default_page: str = "dashboard"
    display_screensaver: bool = True

    # AI Features
    anomaly_detection_enabled: bool = True
    anomaly_sensitivity: str = "medium"
    anomaly_interval: int = 60
    ai_assistant_enabled: bool = True
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "tinyllama"

    @classmethod
    def from_file(cls, path: Path | str) -> "NetworkTapConfig":
        raw = _read_conf(Path(path))
        return cls(
            mode=raw.get("MODE", cls.mode),
            nic1=raw.get("NIC1", cls.nic1),
            nic2=raw.get("NIC2", cls.nic2),
            bridge_name=raw.get("BRIDGE_NAME", cls.bridge_name),
            mgmt_ip=raw.get("MGMT_IP", cls.mgmt_ip),
            mgmt_gateway=raw.get("MGMT_GATEWAY", cls.mgmt_gateway),
            mgmt_dns=raw.get("MGMT_DNS", cls.mgmt_dns),
            capture_dir=raw.get("CAPTURE_DIR", cls.capture_dir),
            capture_iface=raw.get("CAPTURE_IFACE", cls.capture_iface),
            capture_rotate_seconds=int(raw.get("CAPTURE_ROTATE_SECONDS", cls.capture_rotate_seconds)),
            capture_file_limit=int(raw.get("CAPTURE_FILE_LIMIT", cls.capture_file_limit)),
            capture_snaplen=int(raw.get("CAPTURE_SNAPLEN", cls.capture_snaplen)),
            capture_filter=raw.get("CAPTURE_FILTER", cls.capture_filter),
            capture_compress=raw.get("CAPTURE_COMPRESS", "yes").lower() == "yes",
            retention_days=int(raw.get("RETENTION_DAYS", cls.retention_days)),
            min_free_disk_pct=int(raw.get("MIN_FREE_DISK_PCT", cls.min_free_disk_pct)),
            suricata_enabled=raw.get("SURICATA_ENABLED", "yes").lower() == "yes",
            suricata_config=raw.get("SURICATA_CONFIG", cls.suricata_config),
            suricata_log_dir=raw.get("SURICATA_LOG_DIR", cls.suricata_log_dir),
            suricata_eve_log=raw.get("SURICATA_EVE_LOG", cls.suricata_eve_log),
            suricata_iface=raw.get("SURICATA_IFACE", cls.suricata_iface),
            zeek_enabled=raw.get("ZEEK_ENABLED", "yes").lower() == "yes",
            zeek_log_dir=raw.get("ZEEK_LOG_DIR", cls.zeek_log_dir),
            zeek_iface=raw.get("ZEEK_IFACE", cls.zeek_iface),
            web_host=raw.get("WEB_HOST", cls.web_host),
            web_port=int(raw.get("WEB_PORT", cls.web_port)),
            web_user=raw.get("WEB_USER", cls.web_user),
            web_pass=raw.get("WEB_PASS", cls.web_pass),
            web_secret=raw.get("WEB_SECRET", cls.web_secret),
            tls_enabled=raw.get("TLS_ENABLED", "no").lower() == "yes",
            tls_cert=raw.get("TLS_CERT", cls.tls_cert),
            tls_key=raw.get("TLS_KEY", cls.tls_key),
            syslog_enabled=raw.get("SYSLOG_ENABLED", "no").lower() == "yes",
            syslog_server=raw.get("SYSLOG_SERVER", cls.syslog_server),
            syslog_port=int(raw.get("SYSLOG_PORT", cls.syslog_port)),
            syslog_protocol=raw.get("SYSLOG_PROTOCOL", cls.syslog_protocol),
            syslog_format=raw.get("SYSLOG_FORMAT", cls.syslog_format),
            log_dir=raw.get("LOG_DIR", cls.log_dir),
            log_level=raw.get("LOG_LEVEL", cls.log_level),
            wifi_capture_enabled=raw.get("WIFI_CAPTURE_ENABLED", "no").lower() == "yes",
            wifi_capture_channel=int(raw.get("WIFI_CAPTURE_CHANNEL", cls.wifi_capture_channel)),
            wifi_capture_max_size_mb=int(raw.get("WIFI_CAPTURE_MAX_SIZE_MB", cls.wifi_capture_max_size_mb)),
            wifi_capture_max_files=int(raw.get("WIFI_CAPTURE_MAX_FILES", cls.wifi_capture_max_files)),
            wifi_capture_filter=raw.get("WIFI_CAPTURE_FILTER", cls.wifi_capture_filter),
            display_enabled=raw.get("DISPLAY_ENABLED", "yes").lower() == "yes",
            display_refresh=int(raw.get("DISPLAY_REFRESH", cls.display_refresh)),
            display_backlight_timeout=int(raw.get("DISPLAY_BACKLIGHT_TIMEOUT", cls.display_backlight_timeout)),
            display_default_page=raw.get("DISPLAY_DEFAULT_PAGE", cls.display_default_page),
            display_screensaver=raw.get("DISPLAY_SCREENSAVER", "yes").lower() == "yes",
            anomaly_detection_enabled=raw.get("ANOMALY_DETECTION_ENABLED", "yes").lower() == "yes",
            anomaly_sensitivity=raw.get("ANOMALY_SENSITIVITY", cls.anomaly_sensitivity),
            anomaly_interval=int(raw.get("ANOMALY_INTERVAL", cls.anomaly_interval)),
            ai_assistant_enabled=raw.get("AI_ASSISTANT_ENABLED", "yes").lower() == "yes",
            ollama_url=raw.get("OLLAMA_URL", cls.ollama_url),
            ollama_model=raw.get("OLLAMA_MODEL", cls.ollama_model),
        )

    @property
    def capture_interface(self) -> str:
        if self.capture_iface != "auto":
            return self.capture_iface
        return self.bridge_name if self.mode == "bridge" else self.nic1

    @property
    def management_interface(self) -> str:
        return self.bridge_name if self.mode == "bridge" else self.nic2


@lru_cache(maxsize=1)
def get_config() -> NetworkTapConfig:
    """Load and cache the configuration."""
    for path in CONFIG_PATHS:
        p = Path(path)
        if p.exists():
            return NetworkTapConfig.from_file(p)
    return NetworkTapConfig()
