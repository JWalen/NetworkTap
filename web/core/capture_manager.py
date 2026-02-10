"""Capture process management for tcpdump."""

import logging
import os
import subprocess
from pathlib import Path

from core.config import get_config

logger = logging.getLogger("networktap.capture")


def is_capture_running() -> bool:
    """Check if a tcpdump capture process is running."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "networktap-capture"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() == "active"
    except (subprocess.SubprocessError, FileNotFoundError):
        # Fallback: check for tcpdump process
        try:
            result = subprocess.run(
                ["pgrep", "-f", "tcpdump.*networktap"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False


def start_capture() -> dict:
    """Start the capture service."""
    if is_capture_running():
        return {"success": False, "message": "Capture already running"}

    try:
        result = subprocess.run(
            ["systemctl", "start", "networktap-capture"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            logger.info("Capture started")
            return {"success": True, "message": "Capture started"}
        else:
            logger.error("Failed to start capture: %s", result.stderr)
            return {"success": False, "message": result.stderr.strip()}
    except subprocess.SubprocessError as e:
        return {"success": False, "message": str(e)}


def stop_capture() -> dict:
    """Stop the capture service."""
    if not is_capture_running():
        return {"success": False, "message": "Capture not running"}

    try:
        result = subprocess.run(
            ["systemctl", "stop", "networktap-capture"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            logger.info("Capture stopped")
            return {"success": True, "message": "Capture stopped"}
        else:
            return {"success": False, "message": result.stderr.strip()}
    except subprocess.SubprocessError as e:
        return {"success": False, "message": str(e)}


def get_capture_status() -> dict:
    """Get detailed capture status."""
    config = get_config()
    running = is_capture_running()

    # Count capture files
    capture_dir = Path(config.capture_dir)
    pcap_files = []
    total_size = 0

    if capture_dir.exists():
        for f in capture_dir.rglob("*.pcap*"):
            size = f.stat().st_size
            total_size += size
            pcap_files.append({
                "name": f.name,
                "path": str(f),
                "size": size,
                "modified": f.stat().st_mtime,
            })

    pcap_files.sort(key=lambda x: x["modified"], reverse=True)

    return {
        "running": running,
        "interface": config.capture_interface,
        "mode": config.mode,
        "capture_dir": config.capture_dir,
        "rotation_seconds": config.capture_rotate_seconds,
        "compress": config.capture_compress,
        "filter": config.capture_filter,
        "file_count": len(pcap_files),
        "total_size": total_size,
        "recent_files": pcap_files[:10],
    }


def list_pcap_files() -> list[dict]:
    """List all pcap files with metadata."""
    config = get_config()
    capture_dir = Path(config.capture_dir)

    files = []
    if capture_dir.exists():
        for f in capture_dir.rglob("*.pcap*"):
            stat = f.stat()
            files.append({
                "name": f.name,
                "path": str(f.relative_to(capture_dir)),
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })

    files.sort(key=lambda x: x["modified"], reverse=True)
    return files


def get_pcap_path(filename: str) -> Path | None:
    """Get the full path to a pcap file, validating it exists."""
    config = get_config()
    capture_dir = Path(config.capture_dir)

    # Prevent path traversal
    target = (capture_dir / filename).resolve()
    if not str(target).startswith(str(capture_dir.resolve())):
        return None

    if target.exists() and target.is_file():
        return target
    return None


def delete_pcap_file(filename: str) -> dict:
    """Delete a single pcap file."""
    path = get_pcap_path(filename)
    if path is None:
        return {"success": False, "message": "File not found or invalid path"}

    try:
        path.unlink()
        logger.info("Deleted pcap file: %s", filename)
        return {"success": True, "message": f"Deleted {filename}"}
    except OSError as e:
        logger.error("Failed to delete %s: %s", filename, e)
        return {"success": False, "message": f"Failed to delete: {e}"}


def delete_pcap_files(filenames: list[str]) -> dict:
    """Delete multiple pcap files."""
    deleted = 0
    errors = []

    for filename in filenames:
        result = delete_pcap_file(filename)
        if result["success"]:
            deleted += 1
        else:
            errors.append(f"{filename}: {result['message']}")

    if errors:
        return {
            "success": deleted > 0,
            "message": f"Deleted {deleted} files, {len(errors)} errors",
            "errors": errors,
        }
    return {"success": True, "message": f"Deleted {deleted} files"}


def delete_all_pcap_files() -> dict:
    """Delete all pcap files in the capture directory."""
    config = get_config()
    capture_dir = Path(config.capture_dir)

    if not capture_dir.exists():
        return {"success": False, "message": "Capture directory not found"}

    deleted = 0
    errors = []

    for f in capture_dir.rglob("*.pcap*"):
        try:
            f.unlink()
            deleted += 1
        except OSError as e:
            errors.append(f"{f.name}: {e}")

    logger.info("Deleted %d pcap files", deleted)

    if errors:
        return {
            "success": deleted > 0,
            "message": f"Deleted {deleted} files, {len(errors)} errors",
            "errors": errors,
        }
    return {"success": True, "message": f"Deleted {deleted} files"}
