"""Traffic statistics collector from Zeek and system data."""

import heapq
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

from core.config import get_config

logger = logging.getLogger("networktap.stats")

# Cache for parsed connections with TTL
_connections_cache = {"timestamp": 0, "data": None, "hours": 24}
_CONN_CACHE_TTL = 30  # seconds


@dataclass
class TrafficStats:
    total_bytes: int = 0
    total_packets: int = 0
    total_connections: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    unique_src_ips: int = 0
    unique_dest_ips: int = 0
    top_talkers: list = None
    top_ports: list = None
    protocols: dict = None
    timeline: list = None

    def __post_init__(self):
        if self.top_talkers is None:
            self.top_talkers = []
        if self.top_ports is None:
            self.top_ports = []
        if self.protocols is None:
            self.protocols = {}
        if self.timeline is None:
            self.timeline = []

    def to_dict(self) -> dict:
        return {
            "total_bytes": self.total_bytes,
            "total_packets": self.total_packets,
            "total_connections": self.total_connections,
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "unique_src_ips": self.unique_src_ips,
            "unique_dest_ips": self.unique_dest_ips,
            "top_talkers": self.top_talkers,
            "top_ports": self.top_ports,
            "protocols": self.protocols,
            "timeline": self.timeline,
        }


def parse_zeek_conn_log(log_path: Path, hours: int = 24) -> list[dict]:
    """Parse Zeek conn.log for connection data with caching."""
    current_time = time.time()
    if (_connections_cache["data"] is not None and
            current_time - _connections_cache["timestamp"] < _CONN_CACHE_TTL and
            _connections_cache["hours"] == hours):
        return _connections_cache["data"]

    connections = []

    if not log_path.exists():
        return connections
    
    # Use UTC cutoff since Zeek logs are in UTC
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    try:
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                # Parse timestamp
                ts = entry.get("ts", 0)
                try:
                    if isinstance(ts, (int, float)):
                        entry_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                    else:
                        # Handle ISO format with Z suffix (UTC)
                        ts_str = str(ts)
                        if ts_str.endswith("Z"):
                            ts_str = ts_str[:-1] + "+00:00"
                        entry_time = datetime.fromisoformat(ts_str)
                        # Ensure timezone-aware
                        if entry_time.tzinfo is None:
                            entry_time = entry_time.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError, OSError):
                    continue
                
                if entry_time < cutoff:
                    continue
                
                connections.append({
                    "ts": entry_time.isoformat(),
                    "src_ip": entry.get("id.orig_h", ""),
                    "src_port": entry.get("id.orig_p", 0),
                    "dest_ip": entry.get("id.resp_h", ""),
                    "dest_port": entry.get("id.resp_p", 0),
                    "proto": entry.get("proto", ""),
                    "service": entry.get("service", ""),
                    "duration": entry.get("duration", 0),
                    "bytes_orig": entry.get("orig_bytes", 0) or 0,
                    "bytes_resp": entry.get("resp_bytes", 0) or 0,
                    "packets_orig": entry.get("orig_pkts", 0) or 0,
                    "packets_resp": entry.get("resp_pkts", 0) or 0,
                    "conn_state": entry.get("conn_state", ""),
                })
    except Exception as e:
        logger.error("Error parsing conn.log: %s", e)

    _connections_cache["timestamp"] = current_time
    _connections_cache["data"] = connections
    _connections_cache["hours"] = hours

    return connections


def get_traffic_stats(hours: int = 24) -> TrafficStats:
    """Collect traffic statistics from Zeek logs."""
    config = get_config()
    stats = TrafficStats()
    
    # Find conn.log
    log_dir = Path(config.zeek_log_dir)
    conn_log = log_dir / "conn.log"
    if not conn_log.exists():
        conn_log = log_dir / "current" / "conn.log"
    
    connections = parse_zeek_conn_log(conn_log, hours)
    
    if not connections:
        return stats
    
    # Calculate stats
    src_ips = set()
    dest_ips = set()
    ip_bytes = defaultdict(int)
    port_counts = defaultdict(int)
    protocol_counts = defaultdict(int)
    hourly_bytes = defaultdict(int)
    
    for conn in connections:
        src_ip = conn["src_ip"]
        dest_ip = conn["dest_ip"]
        dest_port = conn["dest_port"]
        proto = conn["proto"]
        bytes_total = conn["bytes_orig"] + conn["bytes_resp"]
        packets_total = conn["packets_orig"] + conn["packets_resp"]
        
        stats.total_bytes += bytes_total
        stats.total_packets += packets_total
        stats.total_connections += 1
        stats.bytes_in += conn["bytes_resp"]
        stats.bytes_out += conn["bytes_orig"]
        
        src_ips.add(src_ip)
        dest_ips.add(dest_ip)
        
        ip_bytes[src_ip] += bytes_total
        
        if dest_port > 0:
            port_counts[dest_port] += 1
        
        protocol_counts[proto.upper()] += 1
        
        # Timeline (hourly buckets)
        try:
            ts = datetime.fromisoformat(conn["ts"])
            hour_key = ts.strftime("%Y-%m-%d %H:00")
            hourly_bytes[hour_key] += bytes_total
        except (ValueError, TypeError):
            pass
    
    stats.unique_src_ips = len(src_ips)
    stats.unique_dest_ips = len(dest_ips)
    
    # Top talkers — heapq.nlargest is more efficient than full sort
    stats.top_talkers = [
        {"ip": ip, "bytes": b}
        for ip, b in heapq.nlargest(10, ip_bytes.items(), key=lambda x: x[1])
    ]

    # Top ports
    stats.top_ports = [
        {"port": port, "count": c, "service": get_service_name(port)}
        for port, c in heapq.nlargest(10, port_counts.items(), key=lambda x: x[1])
    ]
    
    # Protocols
    stats.protocols = dict(protocol_counts)
    
    # Timeline
    sorted_timeline = sorted(hourly_bytes.items())
    stats.timeline = [
        {"time": t, "bytes": b} for t, b in sorted_timeline[-48:]  # Last 48 hours
    ]
    
    return stats


@lru_cache(maxsize=128)
def get_service_name(port: int) -> str:
    """Get common service name for a port."""
    services = {
        20: "FTP-DATA",
        21: "FTP",
        22: "SSH",
        23: "Telnet",
        25: "SMTP",
        53: "DNS",
        67: "DHCP",
        68: "DHCP",
        80: "HTTP",
        110: "POP3",
        123: "NTP",
        143: "IMAP",
        443: "HTTPS",
        445: "SMB",
        993: "IMAPS",
        995: "POP3S",
        3306: "MySQL",
        3389: "RDP",
        5432: "PostgreSQL",
        8080: "HTTP-Alt",
        8443: "HTTPS-Alt",
    }
    return services.get(port, "")


def get_connection_summary(hours: int = 1, limit: int = 100) -> list[dict]:
    """Get recent connection summaries."""
    config = get_config()
    log_dir = Path(config.zeek_log_dir)
    conn_log = log_dir / "conn.log"
    if not conn_log.exists():
        conn_log = log_dir / "current" / "conn.log"
    
    connections = parse_zeek_conn_log(conn_log, hours)
    
    # Return most recent
    connections.sort(key=lambda x: x.get("ts", ""), reverse=True)
    return connections[:limit]


def get_bandwidth_history(minutes: int = 60) -> list[dict]:
    """Get bandwidth data points for charting."""
    config = get_config()
    log_dir = Path(config.zeek_log_dir)
    conn_log = log_dir / "conn.log"
    if not conn_log.exists():
        conn_log = log_dir / "current" / "conn.log"
    
    # Get connections from the specified time window
    connections = parse_zeek_conn_log(conn_log, hours=max(1, minutes // 60 + 1))
    
    if not connections:
        return []
    
    # Bucket by minute (use UTC for consistency with Zeek logs)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    minute_bytes = defaultdict(lambda: {"in": 0, "out": 0})
    
    for conn in connections:
        try:
            ts_str = conn["ts"]
            if ts_str.endswith("Z"):
                ts_str = ts_str[:-1] + "+00:00"
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                continue
            minute_key = ts.strftime("%H:%M")
            minute_bytes[minute_key]["in"] += conn["bytes_resp"]
            minute_bytes[minute_key]["out"] += conn["bytes_orig"]
        except (ValueError, TypeError):
            pass
    
    # Sort and return
    sorted_data = sorted(minute_bytes.items())
    return [
        {"time": t, "bytes_in": d["in"], "bytes_out": d["out"]}
        for t, d in sorted_data
    ]
