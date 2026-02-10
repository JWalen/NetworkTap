"""Unified Zeek log parsing with filtering, pagination, and search."""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from core.config import get_config

logger = logging.getLogger("networktap.zeek")

# Supported Zeek log types and their key fields
LOG_TYPES = {
    "conn": {
        "display": "Connections",
        "fields": ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p",
                   "proto", "service", "duration", "orig_bytes", "resp_bytes",
                   "conn_state", "missed_bytes", "history"],
    },
    "dns": {
        "display": "DNS",
        "fields": ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p",
                   "proto", "query", "qclass", "qtype", "rcode", "answers", "TTLs"],
    },
    "http": {
        "display": "HTTP",
        "fields": ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p",
                   "method", "host", "uri", "user_agent", "status_code", "resp_mime_types"],
    },
    "ssl": {
        "display": "SSL/TLS",
        "fields": ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p",
                   "version", "cipher", "server_name", "established", "cert_chain_fps"],
    },
    "files": {
        "display": "Files",
        "fields": ["ts", "fuid", "source", "mime_type", "filename", "total_bytes",
                   "md5", "sha1", "sha256"],
    },
    "notice": {
        "display": "Notices",
        "fields": ["ts", "uid", "note", "msg", "src", "dst", "p", "n", "actions"],
    },
    "weird": {
        "display": "Weird",
        "fields": ["ts", "uid", "name", "addl", "notice", "peer"],
    },
}


@dataclass
class ZeekLogEntry:
    """A single Zeek log entry."""
    log_type: str
    data: dict
    timestamp: datetime


@dataclass
class ZeekLogResult:
    """Result of a Zeek log query."""
    entries: list[dict]
    total: int
    page: int
    per_page: int
    log_type: str


def _find_log_file(log_type: str) -> Optional[Path]:
    """Find the active Zeek log file for a given type."""
    config = get_config()
    log_dir = Path(config.zeek_log_dir)

    # Try current directory first (active logs)
    current = log_dir / "current" / f"{log_type}.log"
    if current.exists():
        return current

    # Try root log directory
    root = log_dir / f"{log_type}.log"
    if root.exists():
        return root

    return None


def _tail_file(path: Path, max_lines: int = 10000) -> list[str]:
    """Read the last N lines from a file efficiently."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            chunk_size = min(size, max_lines * 512)
            f.seek(max(0, size - chunk_size))
            data = f.read().decode("utf-8", errors="replace")
            lines = data.splitlines()
            return lines[-max_lines:] if len(lines) > max_lines else lines
    except Exception as e:
        logger.error("Error reading %s: %s", path, e)
        return []


def _parse_timestamp(ts) -> Optional[datetime]:
    """Parse Zeek timestamp (epoch float or ISO string). Returns UTC-aware datetime."""
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        if isinstance(ts, str):
            # Handle ISO format with Z suffix (UTC)
            ts_str = ts
            if ts_str.endswith("Z"):
                ts_str = ts_str[:-1] + "+00:00"
            dt = datetime.fromisoformat(ts_str)
            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except (ValueError, TypeError, OSError):
        pass
    return None


def _normalize_entry(entry: dict, log_type: str) -> dict:
    """Normalize a Zeek log entry for API response."""
    result = dict(entry)
    result["_log_type"] = log_type

    # Convert timestamp
    if "ts" in result:
        ts = _parse_timestamp(result["ts"])
        if ts:
            result["ts"] = ts.isoformat()
            result["_ts_epoch"] = ts.timestamp()

    return result


def _matches_filter(entry: dict, filters: dict) -> bool:
    """Check if an entry matches the given filters."""
    # Time range filter
    if "start_time" in filters or "end_time" in filters:
        ts = _parse_timestamp(entry.get("ts"))
        if ts:
            if "start_time" in filters and ts < filters["start_time"]:
                return False
            if "end_time" in filters and ts > filters["end_time"]:
                return False

    # IP filter
    if "ip" in filters:
        ip = filters["ip"]
        src = entry.get("id.orig_h", entry.get("src", ""))
        dst = entry.get("id.resp_h", entry.get("dst", ""))
        if ip not in str(src) and ip not in str(dst):
            return False

    # Port filter
    if "port" in filters:
        port = filters["port"]
        src_p = entry.get("id.orig_p", entry.get("p", 0))
        dst_p = entry.get("id.resp_p", 0)
        if port != src_p and port != dst_p:
            return False

    # Protocol filter
    if "proto" in filters:
        proto = filters["proto"].lower()
        entry_proto = str(entry.get("proto", "")).lower()
        if proto != entry_proto:
            return False

    # Text search
    if "search" in filters:
        search = filters["search"].lower()
        text = json.dumps(entry).lower()
        if search not in text:
            return False

    return True


def get_available_logs() -> list[dict]:
    """Get list of available Zeek log types with entry counts."""
    config = get_config()
    results = []

    for log_type, info in LOG_TYPES.items():
        log_file = _find_log_file(log_type)
        count = 0

        if log_file and log_file.exists():
            # Estimate count from file size
            try:
                size = log_file.stat().st_size
                # Rough estimate: ~300 bytes per entry
                count = max(1, size // 300)
            except OSError:
                pass

        results.append({
            "type": log_type,
            "display": info["display"],
            "available": log_file is not None,
            "estimated_count": count,
        })

    return results


def get_log_entries(
    log_type: str,
    page: int = 1,
    per_page: int = 50,
    filters: Optional[dict] = None,
) -> ZeekLogResult:
    """Get paginated log entries with optional filtering."""
    if log_type not in LOG_TYPES:
        return ZeekLogResult([], 0, page, per_page, log_type)

    log_file = _find_log_file(log_type)
    if not log_file:
        return ZeekLogResult([], 0, page, per_page, log_type)

    filters = filters or {}
    entries = []

    # Read and parse log file
    lines = _tail_file(log_file, max_lines=50000)

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Apply filters
        if not _matches_filter(entry, filters):
            continue

        entries.append(_normalize_entry(entry, log_type))

    # Sort by timestamp descending (most recent first)
    entries.sort(key=lambda x: x.get("_ts_epoch", 0), reverse=True)

    # Paginate
    total = len(entries)
    start = (page - 1) * per_page
    end = start + per_page
    page_entries = entries[start:end]

    return ZeekLogResult(page_entries, total, page, per_page, log_type)


def get_log_entry_by_uid(log_type: str, uid: str) -> Optional[dict]:
    """Get a specific log entry by UID."""
    if log_type not in LOG_TYPES:
        return None

    log_file = _find_log_file(log_type)
    if not log_file:
        return None

    lines = _tail_file(log_file, max_lines=50000)

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        entry_uid = entry.get("uid", entry.get("fuid", ""))
        if entry_uid == uid:
            return _normalize_entry(entry, log_type)

    return None


def search_logs(
    query: str,
    log_types: Optional[list[str]] = None,
    limit: int = 100,
    hours: int = 24,
) -> list[dict]:
    """Search across multiple Zeek log types."""
    if not query:
        return []

    log_types = log_types or list(LOG_TYPES.keys())
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results = []
    query_lower = query.lower()

    for log_type in log_types:
        if log_type not in LOG_TYPES:
            continue

        log_file = _find_log_file(log_type)
        if not log_file:
            continue

        lines = _tail_file(log_file, max_lines=20000)

        for line in lines:
            if len(results) >= limit:
                break

            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Quick text match before parsing JSON
            if query_lower not in line.lower():
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Check timestamp
            ts = _parse_timestamp(entry.get("ts"))
            if ts and ts < cutoff:
                continue

            results.append(_normalize_entry(entry, log_type))

        if len(results) >= limit:
            break

    # Sort by timestamp
    results.sort(key=lambda x: x.get("_ts_epoch", 0), reverse=True)
    return results[:limit]


def get_dns_stats(hours: int = 24) -> dict:
    """Get DNS statistics from Zeek dns.log."""
    log_file = _find_log_file("dns")
    if not log_file:
        return {"top_domains": [], "query_types": {}, "response_codes": {}}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    domain_counts: dict[str, int] = {}
    qtype_counts: dict[str, int] = {}
    rcode_counts: dict[str, int] = {}

    lines = _tail_file(log_file, max_lines=50000)

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        ts = _parse_timestamp(entry.get("ts"))
        if ts and ts < cutoff:
            continue

        # Count domains
        query = entry.get("query", "")
        if query:
            # Extract base domain (last two parts)
            parts = query.rstrip(".").split(".")
            if len(parts) >= 2:
                base = ".".join(parts[-2:])
            else:
                base = query
            domain_counts[base] = domain_counts.get(base, 0) + 1

        # Count query types
        qtype = entry.get("qtype_name", entry.get("qtype", ""))
        if qtype:
            qtype_counts[str(qtype)] = qtype_counts.get(str(qtype), 0) + 1

        # Count response codes
        rcode = entry.get("rcode_name", entry.get("rcode", ""))
        if rcode:
            rcode_counts[str(rcode)] = rcode_counts.get(str(rcode), 0) + 1

    # Sort and limit
    top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        "top_domains": [{"domain": d, "count": c} for d, c in top_domains],
        "query_types": qtype_counts,
        "response_codes": rcode_counts,
        "total_queries": sum(qtype_counts.values()),
    }


def get_connection_trends(hours: int = 24, interval_minutes: int = 15) -> list[dict]:
    """Get connection count trends over time."""
    log_file = _find_log_file("conn")
    if not log_file:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    buckets: dict[str, int] = {}

    lines = _tail_file(log_file, max_lines=100000)

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        ts = _parse_timestamp(entry.get("ts"))
        if not ts or ts < cutoff:
            continue

        # Bucket by interval
        bucket_ts = ts.replace(
            minute=(ts.minute // interval_minutes) * interval_minutes,
            second=0,
            microsecond=0,
        )
        bucket_key = bucket_ts.isoformat()
        buckets[bucket_key] = buckets.get(bucket_key, 0) + 1

    # Sort and return
    sorted_buckets = sorted(buckets.items())
    return [{"time": t, "connections": c} for t, c in sorted_buckets]


def get_service_distribution(hours: int = 24) -> list[dict]:
    """Get service distribution from connection logs."""
    log_file = _find_log_file("conn")
    if not log_file:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    service_counts: dict[str, int] = {}

    lines = _tail_file(log_file, max_lines=50000)

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        ts = _parse_timestamp(entry.get("ts"))
        if ts and ts < cutoff:
            continue

        service = entry.get("service", "")
        if service:
            service_counts[service] = service_counts.get(service, 0) + 1
        else:
            # Use protocol:port as fallback
            proto = entry.get("proto", "")
            port = entry.get("id.resp_p", 0)
            if proto and port:
                key = f"{proto}/{port}"
                service_counts[key] = service_counts.get(key, 0) + 1

    # Sort and return top services
    sorted_services = sorted(service_counts.items(), key=lambda x: x[1], reverse=True)
    return [{"service": s, "count": c} for s, c in sorted_services[:15]]
