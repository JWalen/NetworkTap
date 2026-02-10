"""Lightweight anomaly detection for network traffic.

Uses statistical methods and simple ML to detect:
- Traffic volume anomalies
- Unusual connection patterns (beaconing, scans)
- Rare destination IPs/ports
- DNS anomalies (potential DGA, tunneling)
"""

import asyncio
import json
import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from core.config import get_config

logger = logging.getLogger("networktap.anomaly")


@dataclass
class Anomaly:
    """Detected anomaly."""
    timestamp: str
    anomaly_type: str
    severity: int  # 1-4 (1=critical, 4=low)
    title: str
    description: str
    source_ip: str = ""
    dest_ip: str = ""
    dest_port: int = 0
    score: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "source_ip": self.source_ip,
            "dest_ip": self.dest_ip,
            "dest_port": self.dest_port,
            "score": self.score,
            "metadata": self.metadata,
        }


class BaselineStats:
    """Rolling baseline statistics for anomaly detection."""

    def __init__(self, window_hours: int = 24):
        self.window_hours = window_hours
        self.hourly_conn_counts: list[int] = []
        self.hourly_bytes: list[int] = []
        self.known_dest_ips: set[str] = set()
        self.known_dest_ports: set[int] = set()
        self.ip_conn_counts: dict[str, int] = defaultdict(int)
        self.dns_domains: dict[str, int] = defaultdict(int)
        self.last_update: Optional[datetime] = None

    def update(self, conn_count: int, total_bytes: int, dest_ips: set, dest_ports: set):
        """Update baseline with new hourly stats."""
        max_samples = self.window_hours

        self.hourly_conn_counts.append(conn_count)
        if len(self.hourly_conn_counts) > max_samples:
            self.hourly_conn_counts.pop(0)

        self.hourly_bytes.append(total_bytes)
        if len(self.hourly_bytes) > max_samples:
            self.hourly_bytes.pop(0)

        self.known_dest_ips.update(dest_ips)
        self.known_dest_ports.update(dest_ports)
        self.last_update = datetime.now(timezone.utc)

    @property
    def avg_conn_count(self) -> float:
        if not self.hourly_conn_counts:
            return 0
        return sum(self.hourly_conn_counts) / len(self.hourly_conn_counts)

    @property
    def std_conn_count(self) -> float:
        if len(self.hourly_conn_counts) < 2:
            return 0
        avg = self.avg_conn_count
        variance = sum((x - avg) ** 2 for x in self.hourly_conn_counts) / len(self.hourly_conn_counts)
        return math.sqrt(variance)

    @property
    def avg_bytes(self) -> float:
        if not self.hourly_bytes:
            return 0
        return sum(self.hourly_bytes) / len(self.hourly_bytes)

    @property
    def std_bytes(self) -> float:
        if len(self.hourly_bytes) < 2:
            return 0
        avg = self.avg_bytes
        variance = sum((x - avg) ** 2 for x in self.hourly_bytes) / len(self.hourly_bytes)
        return math.sqrt(variance)


class AnomalyDetector:
    """Main anomaly detection engine."""

    SENSITIVITY_THRESHOLDS = {
        "low": {"z_score": 3.5, "rare_threshold": 0.01},
        "medium": {"z_score": 2.5, "rare_threshold": 0.05},
        "high": {"z_score": 2.0, "rare_threshold": 0.10},
    }

    def __init__(self, config=None):
        self.config = config or get_config()
        self.baseline = BaselineStats()
        self.anomalies: list[Anomaly] = []
        self.max_anomalies = 1000
        self._running = False
        self._task: Optional[asyncio.Task] = None

        sensitivity = self.config.anomaly_sensitivity
        self.thresholds = self.SENSITIVITY_THRESHOLDS.get(sensitivity, self.SENSITIVITY_THRESHOLDS["medium"])

    async def start(self, callback: Optional[Callable] = None):
        """Start the anomaly detection background task."""
        if not self.config.anomaly_detection_enabled:
            logger.info("Anomaly detection is disabled")
            return

        self._running = True
        self._callback = callback
        logger.info("Starting anomaly detection (sensitivity=%s, interval=%ds)",
                    self.config.anomaly_sensitivity, self.config.anomaly_interval)

        while self._running:
            try:
                await self._run_detection_cycle()
            except Exception as e:
                logger.error("Anomaly detection error: %s", e)

            await asyncio.sleep(self.config.anomaly_interval)

    def stop(self):
        """Stop the anomaly detection."""
        self._running = False
        logger.info("Anomaly detection stopped")

    async def _run_detection_cycle(self):
        """Run one detection cycle."""
        # Load recent connection data
        connections = self._load_recent_connections(minutes=5)
        if not connections:
            return

        # Detect various anomaly types
        anomalies = []
        anomalies.extend(self._detect_volume_anomalies(connections))
        anomalies.extend(self._detect_rare_destinations(connections))
        anomalies.extend(self._detect_port_scan(connections))
        anomalies.extend(self._detect_beaconing(connections))
        anomalies.extend(self._detect_dns_anomalies())

        # Store and broadcast anomalies
        for anomaly in anomalies:
            self.anomalies.append(anomaly)
            if self._callback:
                await self._callback(anomaly.to_dict())

        # Trim old anomalies
        if len(self.anomalies) > self.max_anomalies:
            self.anomalies = self.anomalies[-self.max_anomalies:]

        # Update baseline periodically
        if not self.baseline.last_update or \
           (datetime.now(timezone.utc) - self.baseline.last_update).seconds > 3600:
            self._update_baseline(connections)

    def _load_recent_connections(self, minutes: int = 5) -> list[dict]:
        """Load recent connections from Zeek conn.log."""
        log_path = Path(self.config.zeek_log_dir) / "conn.log"
        if not log_path.exists():
            log_path = Path(self.config.zeek_log_dir) / "current" / "conn.log"
        if not log_path.exists():
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        connections = []

        try:
            with open(log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        entry = json.loads(line)
                        ts = entry.get("ts", "")
                        if isinstance(ts, str) and ts.endswith("Z"):
                            ts = ts[:-1] + "+00:00"
                        entry_time = datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.fromtimestamp(ts, tz=timezone.utc)
                        if entry_time >= cutoff:
                            connections.append(entry)
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception as e:
            logger.error("Error loading connections: %s", e)

        return connections

    def _detect_volume_anomalies(self, connections: list[dict]) -> list[Anomaly]:
        """Detect unusual traffic volume."""
        anomalies = []
        if len(self.baseline.hourly_conn_counts) < 3:
            return anomalies  # Need baseline data

        current_count = len(connections)
        expected_5min = self.baseline.avg_conn_count / 12  # Hourly avg / 12

        if expected_5min > 0 and self.baseline.std_conn_count > 0:
            z_score = (current_count - expected_5min) / (self.baseline.std_conn_count / 12)

            if abs(z_score) > self.thresholds["z_score"]:
                severity = 2 if z_score > 0 else 3  # Spike is more concerning than drop
                anomalies.append(Anomaly(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    anomaly_type="volume_anomaly",
                    severity=severity,
                    title="Traffic Volume Anomaly",
                    description=f"Connection count ({current_count}) is {abs(z_score):.1f} std devs from normal ({expected_5min:.0f})",
                    score=abs(z_score),
                    metadata={"current": current_count, "expected": expected_5min, "z_score": z_score}
                ))

        return anomalies

    def _detect_rare_destinations(self, connections: list[dict]) -> list[Anomaly]:
        """Detect connections to rare/new destinations."""
        anomalies = []
        if len(self.baseline.known_dest_ips) < 10:
            return anomalies  # Need baseline

        for conn in connections:
            dest_ip = conn.get("id.resp_h", "")
            dest_port = conn.get("id.resp_p", 0)
            src_ip = conn.get("id.orig_h", "")

            # Skip internal/broadcast addresses
            if dest_ip.startswith(("10.", "192.168.", "172.16.", "224.", "255.", "ff")):
                continue

            if dest_ip and dest_ip not in self.baseline.known_dest_ips:
                anomalies.append(Anomaly(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    anomaly_type="rare_destination",
                    severity=3,
                    title="Connection to New External IP",
                    description=f"First-time connection to {dest_ip}:{dest_port}",
                    source_ip=src_ip,
                    dest_ip=dest_ip,
                    dest_port=dest_port,
                    score=0.7,
                    metadata={"service": conn.get("service", "")}
                ))
                # Add to known to avoid duplicate alerts
                self.baseline.known_dest_ips.add(dest_ip)

        return anomalies[:5]  # Limit to prevent alert flood

    def _detect_port_scan(self, connections: list[dict]) -> list[Anomaly]:
        """Detect potential port scanning activity."""
        anomalies = []

        # Group connections by source IP
        src_to_ports: dict[str, set] = defaultdict(set)
        src_to_dests: dict[str, set] = defaultdict(set)

        for conn in connections:
            src_ip = conn.get("id.orig_h", "")
            dest_ip = conn.get("id.resp_h", "")
            dest_port = conn.get("id.resp_p", 0)

            if src_ip and dest_port:
                src_to_ports[src_ip].add(dest_port)
                src_to_dests[src_ip].add(dest_ip)

        # Detect horizontal scan (many ports on one host)
        for src_ip, ports in src_to_ports.items():
            if len(ports) > 20:  # Threshold for port scan
                anomalies.append(Anomaly(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    anomaly_type="port_scan",
                    severity=2,
                    title="Potential Port Scan Detected",
                    description=f"{src_ip} connected to {len(ports)} different ports in 5 minutes",
                    source_ip=src_ip,
                    score=min(1.0, len(ports) / 50),
                    metadata={"port_count": len(ports), "sample_ports": list(ports)[:10]}
                ))

        # Detect vertical scan (one port on many hosts)
        port_to_dests: dict[int, set] = defaultdict(set)
        for conn in connections:
            dest_ip = conn.get("id.resp_h", "")
            dest_port = conn.get("id.resp_p", 0)
            if dest_port:
                port_to_dests[dest_port].add(dest_ip)

        for port, dests in port_to_dests.items():
            if len(dests) > 10:  # Many hosts on same port
                anomalies.append(Anomaly(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    anomaly_type="host_scan",
                    severity=2,
                    title="Potential Host Scan Detected",
                    description=f"Port {port} probed on {len(dests)} different hosts",
                    dest_port=port,
                    score=min(1.0, len(dests) / 20),
                    metadata={"host_count": len(dests)}
                ))

        return anomalies

    def _detect_beaconing(self, connections: list[dict]) -> list[Anomaly]:
        """Detect periodic beaconing behavior (C2 indicator)."""
        anomalies = []

        # Group by src->dest pair and look for regular intervals
        pair_times: dict[str, list[float]] = defaultdict(list)

        for conn in connections:
            src_ip = conn.get("id.orig_h", "")
            dest_ip = conn.get("id.resp_h", "")
            ts = conn.get("ts", "")

            if not (src_ip and dest_ip and ts):
                continue

            try:
                if isinstance(ts, str):
                    if ts.endswith("Z"):
                        ts = ts[:-1] + "+00:00"
                    entry_time = datetime.fromisoformat(ts)
                else:
                    entry_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                pair_key = f"{src_ip}->{dest_ip}"
                pair_times[pair_key].append(entry_time.timestamp())
            except (ValueError, TypeError):
                continue

        # Analyze intervals for regularity
        for pair, times in pair_times.items():
            if len(times) < 5:
                continue

            times.sort()
            intervals = [times[i+1] - times[i] for i in range(len(times)-1)]

            if not intervals:
                continue

            avg_interval = sum(intervals) / len(intervals)
            if avg_interval < 1:  # Too fast, probably normal traffic
                continue

            # Check for regularity (low variance in intervals)
            variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals)
            std_dev = math.sqrt(variance)
            cv = std_dev / avg_interval if avg_interval > 0 else float('inf')

            # Low coefficient of variation = regular beaconing
            if cv < 0.3 and len(times) >= 5:
                src_ip, dest_ip = pair.split("->")
                anomalies.append(Anomaly(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    anomaly_type="beaconing",
                    severity=2,
                    title="Potential Beaconing Detected",
                    description=f"Regular {avg_interval:.0f}s intervals from {src_ip} to {dest_ip}",
                    source_ip=src_ip,
                    dest_ip=dest_ip,
                    score=1.0 - cv,
                    metadata={"interval_seconds": avg_interval, "beacon_count": len(times), "regularity": 1 - cv}
                ))

        return anomalies

    def _detect_dns_anomalies(self) -> list[Anomaly]:
        """Detect DNS-based anomalies (DGA, tunneling)."""
        anomalies = []

        log_path = Path(self.config.zeek_log_dir) / "dns.log"
        if not log_path.exists():
            log_path = Path(self.config.zeek_log_dir) / "current" / "dns.log"
        if not log_path.exists():
            return anomalies

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        queries: list[dict] = []

        try:
            # Read recent DNS queries
            with open(log_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        entry = json.loads(line)
                        ts = entry.get("ts", "")
                        if isinstance(ts, str) and ts.endswith("Z"):
                            ts = ts[:-1] + "+00:00"
                        entry_time = datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.fromtimestamp(ts, tz=timezone.utc)
                        if entry_time >= cutoff:
                            queries.append(entry)
                    except (json.JSONDecodeError, ValueError):
                        continue
        except Exception as e:
            logger.error("Error reading DNS log: %s", e)
            return anomalies

        # Detect potential DGA (high entropy domain names)
        for query in queries:
            domain = query.get("query", "")
            if not domain or len(domain) < 10:
                continue

            # Skip common TLDs and known domains
            if any(domain.endswith(tld) for tld in [".local", ".lan", ".internal", ".arpa"]):
                continue

            # Calculate entropy of subdomain
            subdomain = domain.split(".")[0]
            if len(subdomain) > 15:
                entropy = self._calculate_entropy(subdomain)
                if entropy > 3.5:  # High entropy threshold
                    anomalies.append(Anomaly(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        anomaly_type="dns_dga",
                        severity=2,
                        title="Potential DGA Domain",
                        description=f"High-entropy domain query: {domain}",
                        source_ip=query.get("id.orig_h", ""),
                        score=min(1.0, entropy / 4.0),
                        metadata={"domain": domain, "entropy": entropy}
                    ))

        # Detect DNS tunneling (unusually long queries or many TXT queries)
        txt_queries = [q for q in queries if q.get("qtype_name") == "TXT"]
        if len(txt_queries) > 20:
            anomalies.append(Anomaly(
                timestamp=datetime.now(timezone.utc).isoformat(),
                anomaly_type="dns_tunneling",
                severity=2,
                title="Potential DNS Tunneling",
                description=f"Unusual number of TXT queries: {len(txt_queries)} in 5 minutes",
                score=min(1.0, len(txt_queries) / 50),
                metadata={"txt_query_count": len(txt_queries)}
            ))

        return anomalies[:5]

    def _calculate_entropy(self, s: str) -> float:
        """Calculate Shannon entropy of a string."""
        if not s:
            return 0
        freq = defaultdict(int)
        for c in s.lower():
            freq[c] += 1
        length = len(s)
        entropy = 0
        for count in freq.values():
            p = count / length
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    def _update_baseline(self, connections: list[dict]):
        """Update baseline statistics."""
        dest_ips = {c.get("id.resp_h", "") for c in connections if c.get("id.resp_h")}
        dest_ports = {c.get("id.resp_p", 0) for c in connections if c.get("id.resp_p")}
        total_bytes = sum(
            (c.get("orig_bytes", 0) or 0) + (c.get("resp_bytes", 0) or 0)
            for c in connections
        )

        # Scale to hourly estimate
        hourly_conn_estimate = len(connections) * 12
        hourly_bytes_estimate = total_bytes * 12

        self.baseline.update(hourly_conn_estimate, hourly_bytes_estimate, dest_ips, dest_ports)
        logger.debug("Updated baseline: avg_conn=%d, known_ips=%d",
                     self.baseline.avg_conn_count, len(self.baseline.known_dest_ips))

    def get_recent_anomalies(self, limit: int = 50) -> list[dict]:
        """Get recent anomalies."""
        return [a.to_dict() for a in self.anomalies[-limit:]]

    def get_stats(self) -> dict:
        """Get anomaly detection statistics."""
        return {
            "enabled": self.config.anomaly_detection_enabled,
            "running": self._running,
            "sensitivity": self.config.anomaly_sensitivity,
            "interval_seconds": self.config.anomaly_interval,
            "total_anomalies": len(self.anomalies),
            "baseline": {
                "samples": len(self.baseline.hourly_conn_counts),
                "avg_connections_hourly": self.baseline.avg_conn_count,
                "known_dest_ips": len(self.baseline.known_dest_ips),
                "known_dest_ports": len(self.baseline.known_dest_ports),
            }
        }


# Global detector instance
_detector: Optional[AnomalyDetector] = None


def get_detector() -> AnomalyDetector:
    """Get or create the global anomaly detector."""
    global _detector
    if _detector is None:
        _detector = AnomalyDetector()
    return _detector


async def start_anomaly_detection(callback: Optional[Callable] = None):
    """Start the global anomaly detector."""
    detector = get_detector()
    await detector.start(callback)


def stop_anomaly_detection():
    """Stop the global anomaly detector."""
    global _detector
    if _detector:
        _detector.stop()
