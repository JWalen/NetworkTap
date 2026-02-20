"""Parse Suricata EVE JSON log into structured event types with filtering and pagination."""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from core.config import get_config

logger = logging.getLogger("networktap.suricata")

# Suricata EVE event types we expose for browsing
EVE_TYPES = {
    "alert": {
        "display": "Alerts",
        "description": "IDS signature matches",
    },
    "dns": {
        "display": "DNS",
        "description": "DNS queries and responses",
    },
    "http": {
        "display": "HTTP",
        "description": "HTTP transactions",
    },
    "tls": {
        "display": "TLS",
        "description": "TLS/SSL handshakes",
    },
    "flow": {
        "display": "Flows",
        "description": "Connection flow records",
    },
    "fileinfo": {
        "display": "Files",
        "description": "File transfers detected",
    },
    "stats": {
        "display": "Stats",
        "description": "Engine performance counters",
    },
}


@dataclass
class SuricataLogResult:
    """Result of a Suricata log query."""
    entries: list[dict]
    total: int
    page: int
    per_page: int
    event_type: str


# Simple cache for parsed EVE entries per event type
_eve_cache: dict[str, dict] = {}
_EVE_CACHE_TTL = 10  # seconds


def _get_eve_path() -> Path:
    """Get the path to the Suricata EVE JSON log."""
    config = get_config()
    return Path(config.suricata_eve_log)


def _parse_eve_entries(event_type: str, max_lines: int = 50000) -> list[dict]:
    """Parse EVE JSON log and return entries of the specified event type.

    Reads from the end of the file for efficiency.
    """
    now = time.time()
    cached = _eve_cache.get(event_type)
    if cached and now - cached["time"] < _EVE_CACHE_TTL:
        return cached["entries"]

    eve_path = _get_eve_path()
    if not eve_path.exists():
        return []

    entries = []
    try:
        # Read from end of file
        file_size = eve_path.stat().st_size
        read_size = min(file_size, max_lines * 512)  # ~512 bytes per line estimate

        with open(eve_path, "rb") as f:
            if read_size < file_size:
                f.seek(file_size - read_size)
                f.readline()  # skip partial first line
            data = f.read().decode("utf-8", errors="replace")

        for line in data.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("event_type") != event_type:
                continue

            # Normalize timestamp
            ts = entry.get("timestamp", "")
            if ts:
                entry["_ts"] = ts

            entries.append(entry)

    except Exception as e:
        logger.error("Failed to parse EVE log: %s", e)

    _eve_cache[event_type] = {"entries": entries, "time": now}
    return entries


def get_available_event_types() -> list[dict]:
    """List available Suricata EVE event types with counts."""
    eve_path = _get_eve_path()
    result = []

    # Quick count scan
    counts: dict[str, int] = {}
    if eve_path.exists():
        try:
            file_size = eve_path.stat().st_size
            read_size = min(file_size, 20 * 1024 * 1024)  # last 20MB

            with open(eve_path, "rb") as f:
                if read_size < file_size:
                    f.seek(file_size - read_size)
                    f.readline()
                data = f.read().decode("utf-8", errors="replace")

            for line in data.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Quick extract event_type without full JSON parse
                if '"event_type"' in line:
                    try:
                        entry = json.loads(line)
                        et = entry.get("event_type", "")
                        if et in EVE_TYPES:
                            counts[et] = counts.get(et, 0) + 1
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error("Failed to count EVE events: %s", e)

    for etype, info in EVE_TYPES.items():
        count = counts.get(etype, 0)
        result.append({
            "type": etype,
            "display": info["display"],
            "description": info["description"],
            "available": count > 0,
            "estimated_count": count,
        })

    return result


def get_eve_entries(
    event_type: str,
    page: int = 1,
    per_page: int = 50,
    filters: Optional[dict] = None,
) -> SuricataLogResult:
    """Get paginated Suricata EVE entries with optional filters."""
    if event_type not in EVE_TYPES:
        return SuricataLogResult(entries=[], total=0, page=page, per_page=per_page, event_type=event_type)

    all_entries = _parse_eve_entries(event_type)
    filtered = _apply_filters(all_entries, event_type, filters or {})

    # Sort by timestamp descending (newest first)
    filtered.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    page_entries = filtered[start:end]

    # Flatten entries for display
    display_entries = [_flatten_entry(e, event_type) for e in page_entries]

    return SuricataLogResult(
        entries=display_entries,
        total=total,
        page=page,
        per_page=per_page,
        event_type=event_type,
    )


def _apply_filters(entries: list[dict], event_type: str, filters: dict) -> list[dict]:
    """Apply filters to EVE entries."""
    result = entries

    if "start_time" in filters:
        start = filters["start_time"]
        result = [e for e in result if _parse_ts(e.get("timestamp", "")) >= start]

    if "ip" in filters:
        ip = filters["ip"]
        result = [e for e in result if ip in (e.get("src_ip", "") or "") or ip in (e.get("dest_ip", "") or "")]

    if "port" in filters:
        port = int(filters["port"])
        result = [e for e in result if e.get("src_port") == port or e.get("dest_port") == port]

    if "proto" in filters:
        proto = filters["proto"].lower()
        result = [e for e in result if (e.get("proto", "") or "").lower() == proto]

    if "search" in filters:
        search = filters["search"].lower()
        result = [e for e in result if search in json.dumps(e).lower()]

    return result


def _parse_ts(ts_str: str) -> datetime:
    """Parse Suricata timestamp string."""
    try:
        # Suricata uses ISO 8601 with timezone: 2026-02-20T10:30:45.123456+0000
        if "+" in ts_str or ts_str.endswith("Z"):
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return datetime.fromisoformat(ts_str)
    except Exception:
        return datetime.min


def _flatten_entry(entry: dict, event_type: str) -> dict:
    """Flatten a Suricata EVE entry for display."""
    flat = {
        "timestamp": entry.get("timestamp", ""),
        "src_ip": entry.get("src_ip", ""),
        "src_port": entry.get("src_port"),
        "dest_ip": entry.get("dest_ip", ""),
        "dest_port": entry.get("dest_port"),
        "proto": entry.get("proto", ""),
    }

    if event_type == "alert":
        alert = entry.get("alert", {})
        flat["signature"] = alert.get("signature", "")
        flat["signature_id"] = alert.get("signature_id")
        flat["severity"] = alert.get("severity")
        flat["category"] = alert.get("category", "")
        flat["action"] = alert.get("action", "")
        flat["rev"] = alert.get("rev")

    elif event_type == "dns":
        dns = entry.get("dns", {})
        flat["query_type"] = dns.get("type", "")  # "query" or "answer"
        flat["rrname"] = dns.get("rrname", "")
        flat["rrtype"] = dns.get("rrtype", "")
        flat["rcode"] = dns.get("rcode", "")
        flat["rdata"] = dns.get("rdata", "")
        flat["tx_id"] = dns.get("tx_id")
        # Grouped format (newer Suricata)
        if "grouped" in dns:
            flat["answers"] = dns["grouped"]

    elif event_type == "http":
        http = entry.get("http", {})
        flat["hostname"] = http.get("hostname", "")
        flat["url"] = http.get("url", "")
        flat["http_method"] = http.get("http_method", "")
        flat["http_user_agent"] = http.get("http_user_agent", "")
        flat["http_content_type"] = http.get("http_content_type", "")
        flat["status"] = http.get("status")
        flat["length"] = http.get("length")
        flat["http_refer"] = http.get("http_refer", "")

    elif event_type == "tls":
        tls = entry.get("tls", {})
        flat["sni"] = tls.get("sni", "")
        flat["version"] = tls.get("version", "")
        flat["subject"] = tls.get("subject", "")
        flat["issuerdn"] = tls.get("issuerdn", "")
        flat["fingerprint"] = tls.get("fingerprint", "")
        flat["ja3_hash"] = tls.get("ja3", {}).get("hash", "") if isinstance(tls.get("ja3"), dict) else ""
        flat["ja3s_hash"] = tls.get("ja3s", {}).get("hash", "") if isinstance(tls.get("ja3s"), dict) else ""
        flat["notbefore"] = tls.get("notbefore", "")
        flat["notafter"] = tls.get("notafter", "")

    elif event_type == "flow":
        flat["app_proto"] = entry.get("app_proto", "")
        flat["flow_id"] = entry.get("flow_id")
        flow = entry.get("flow", {})
        flat["bytes_toserver"] = flow.get("bytes_toserver", 0)
        flat["bytes_toclient"] = flow.get("bytes_toclient", 0)
        flat["pkts_toserver"] = flow.get("pkts_toserver", 0)
        flat["pkts_toclient"] = flow.get("pkts_toclient", 0)
        flat["start"] = flow.get("start", "")
        flat["end"] = flow.get("end", "")
        flat["state"] = flow.get("state", "")
        flat["reason"] = flow.get("reason", "")

    elif event_type == "fileinfo":
        fileinfo = entry.get("fileinfo", {})
        flat["filename"] = fileinfo.get("filename", "")
        flat["size"] = fileinfo.get("size", 0)
        flat["state"] = fileinfo.get("state", "")
        flat["md5"] = fileinfo.get("md5", "")
        flat["sha256"] = fileinfo.get("sha256", "")
        flat["stored"] = fileinfo.get("stored", False)
        flat["app_proto"] = entry.get("app_proto", "")
        http = entry.get("http", {})
        flat["http_url"] = http.get("url", "")
        flat["http_hostname"] = http.get("hostname", "")

    elif event_type == "stats":
        stats = entry.get("stats", {})
        capture = stats.get("capture", {})
        decoder = stats.get("decoder", {})
        flat["uptime"] = stats.get("uptime", 0)
        flat["capture_kernel_packets"] = capture.get("kernel_packets", 0)
        flat["capture_kernel_drops"] = capture.get("kernel_drops", 0)
        flat["decoder_pkts"] = decoder.get("pkts", 0)
        flat["decoder_bytes"] = decoder.get("bytes", 0)
        flat["detect_alert"] = stats.get("detect", {}).get("alert", 0)

    # Generate a unique ID for row expansion
    flat["_id"] = entry.get("flow_id", "") or f"{flat['timestamp']}_{flat['src_ip']}_{flat.get('src_port', '')}"

    return flat
