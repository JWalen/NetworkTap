"""Parse Suricata EVE JSON and Zeek logs into structured alerts."""

import asyncio
import json
import logging
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from core.config import NetworkTapConfig, get_config

logger = logging.getLogger("networktap.alerts")


def parse_suricata_alerts(eve_path: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """Read recent alerts from Suricata EVE JSON log."""
    alerts = []
    path = Path(eve_path)

    if not path.exists():
        return alerts

    try:
        # Read from the end of the file for recent alerts
        lines = _tail_lines(path, limit + offset + 500)

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("event_type") != "alert":
                continue

            alert_data = entry.get("alert", {})
            alerts.append({
                "source": "suricata",
                "timestamp": entry.get("timestamp", ""),
                "severity": alert_data.get("severity", 3),
                "signature": alert_data.get("signature", "Unknown"),
                "signature_id": alert_data.get("signature_id", 0),
                "category": alert_data.get("category", ""),
                "src_ip": entry.get("src_ip", ""),
                "src_port": entry.get("src_port", 0),
                "dest_ip": entry.get("dest_ip", ""),
                "dest_port": entry.get("dest_port", 0),
                "proto": entry.get("proto", ""),
                "action": alert_data.get("action", ""),
            })

    except Exception as e:
        logger.error("Error parsing Suricata alerts: %s", e)

    # Return most recent alerts, applying offset
    alerts.reverse()
    return alerts[offset:offset + limit]


def parse_zeek_logs(log_dir: str, log_type: str = "conn", limit: int = 100) -> list[dict]:
    """Read recent entries from Zeek JSON logs."""
    entries = []
    log_path = Path(log_dir) / f"{log_type}.log"

    if not log_path.exists():
        # Try current directory (Zeek rotates logs)
        log_path = Path(log_dir) / "current" / f"{log_type}.log"
        if not log_path.exists():
            return entries

    try:
        lines = _tail_lines(log_path, limit + 100)

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                entry = json.loads(line)
                entries.append(_normalize_zeek_entry(entry, log_type))
            except json.JSONDecodeError:
                continue

    except Exception as e:
        logger.error("Error parsing Zeek %s log: %s", log_type, e)

    entries.reverse()
    return entries[:limit]


def parse_zeek_alerts(log_dir: str, limit: int = 100) -> list[dict]:
    """Get alert-worthy entries from Zeek notice and weird logs."""
    alerts = []

    # Parse notice.log
    notices = parse_zeek_logs(log_dir, "notice", limit)
    for n in notices:
        alerts.append({
            "source": "zeek",
            "timestamp": n.get("ts", ""),
            "severity": 2,
            "signature": n.get("note", "Zeek Notice"),
            "category": "notice",
            "src_ip": n.get("src", ""),
            "src_port": n.get("p", 0),
            "dest_ip": n.get("dst", ""),
            "dest_port": 0,
            "proto": "",
            "message": n.get("msg", ""),
        })

    # Parse weird.log
    weirds = parse_zeek_logs(log_dir, "weird", limit)
    for w in weirds:
        alerts.append({
            "source": "zeek",
            "timestamp": w.get("ts", ""),
            "severity": 3,
            "signature": w.get("name", "Zeek Weird"),
            "category": "weird",
            "src_ip": w.get("id.orig_h", ""),
            "src_port": w.get("id.orig_p", 0),
            "dest_ip": w.get("id.resp_h", ""),
            "dest_port": w.get("id.resp_p", 0),
            "proto": "",
            "message": w.get("addl", ""),
        })

    alerts.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
    return alerts[:limit]


def _normalize_zeek_entry(entry: dict, log_type: str) -> dict:
    """Normalize a Zeek log entry."""
    result = dict(entry)
    result["_log_type"] = log_type

    # Convert Zeek timestamps (epoch float) to ISO format
    if "ts" in result:
        try:
            ts = float(result["ts"])
            result["ts"] = datetime.fromtimestamp(ts).isoformat()
        except (ValueError, TypeError, OSError):
            pass

    return result


def _tail_lines(path: Path, n: int) -> list[str]:
    """Read the last n lines from a file efficiently."""
    try:
        with open(path, "rb") as f:
            # Seek to end
            f.seek(0, 2)
            size = f.tell()

            # Read in chunks from the end
            chunk_size = min(size, n * 512)
            f.seek(max(0, size - chunk_size))
            data = f.read().decode("utf-8", errors="replace")
            lines = data.splitlines()
            return lines[-n:] if len(lines) > n else lines
    except Exception as e:
        logger.error("Error tailing %s: %s", path, e)
        return []


class AlertWatcher:
    """Watches Suricata EVE log for new alerts and broadcasts them."""

    def __init__(self, config: NetworkTapConfig):
        self.config = config
        self.eve_path = Path(config.suricata_eve_log)
        self._position = 0

    async def watch(self, callback: Callable):
        """Continuously watch for new alerts and invoke callback."""
        logger.info("Alert watcher started for %s", self.eve_path)

        # Seek to end of file on startup
        if self.eve_path.exists():
            self._position = self.eve_path.stat().st_size

        while True:
            try:
                await self._check_new_alerts(callback)
            except Exception as e:
                logger.error("Alert watcher error: %s", e)
            await asyncio.sleep(1)

    async def _check_new_alerts(self, callback: Callable):
        """Check for new lines in EVE log."""
        if not self.eve_path.exists():
            return

        current_size = self.eve_path.stat().st_size

        # File was truncated/rotated
        if current_size < self._position:
            self._position = 0

        if current_size <= self._position:
            return

        try:
            with open(self.eve_path, "r") as f:
                f.seek(self._position)
                new_data = f.read()
                self._position = f.tell()

            for line in new_data.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("event_type") == "alert":
                    alert_data = entry.get("alert", {})
                    alert = {
                        "source": "suricata",
                        "timestamp": entry.get("timestamp", ""),
                        "severity": alert_data.get("severity", 3),
                        "signature": alert_data.get("signature", "Unknown"),
                        "signature_id": alert_data.get("signature_id", 0),
                        "category": alert_data.get("category", ""),
                        "src_ip": entry.get("src_ip", ""),
                        "src_port": entry.get("src_port", 0),
                        "dest_ip": entry.get("dest_ip", ""),
                        "dest_port": entry.get("dest_port", 0),
                        "proto": entry.get("proto", ""),
                        "action": alert_data.get("action", ""),
                    }
                    await callback(alert)

        except Exception as e:
            logger.error("Error reading new alerts: %s", e)
