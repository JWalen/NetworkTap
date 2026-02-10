"""Backup and restore functionality."""

import json
import logging
import os
import shutil
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.config import get_config

logger = logging.getLogger("networktap.backup")

BACKUP_DIR = Path("/var/lib/networktap/backups")
MAX_BACKUPS = 10

# Files and directories to back up
BACKUP_ITEMS = [
    "/etc/networktap.conf",
    "/var/lib/networktap/users.json",
    "/etc/suricata/suricata.yaml",
    "/etc/suricata/disable.conf",
    "/etc/suricata/enable.conf",
    "/etc/suricata/threshold.config",
    "/etc/suricata/rules/local.rules",
    "/etc/zeek/site/local.zeek",
    "/etc/networktap/tls",
]


def create_backup(description: str = "") -> tuple[bool, str, Optional[str]]:
    """Create a backup of all configuration files.
    
    Returns: (success, message, backup_filename)
    """
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"networktap_backup_{timestamp}.tar.gz"
        backup_path = BACKUP_DIR / backup_name
        
        # Create metadata
        metadata = {
            "version": 1,
            "created_at": datetime.now().isoformat(),
            "description": description,
            "hostname": os.uname().nodename if hasattr(os, 'uname') else "unknown",
            "files": [],
        }
        
        with tarfile.open(backup_path, "w:gz") as tar:
            # Add each backup item
            for item_path in BACKUP_ITEMS:
                path = Path(item_path)
                if path.exists():
                    arcname = str(path).lstrip("/")
                    tar.add(path, arcname=arcname)
                    metadata["files"].append({
                        "path": item_path,
                        "size": path.stat().st_size if path.is_file() else 0,
                    })
            
            # Add metadata file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(metadata, f, indent=2)
                temp_meta = f.name
            
            tar.add(temp_meta, arcname="backup_metadata.json")
            os.unlink(temp_meta)
        
        # Cleanup old backups
        cleanup_old_backups()
        
        logger.info("Backup created: %s", backup_name)
        return True, f"Backup created: {backup_name}", backup_name
    
    except Exception as e:
        logger.error("Backup failed: %s", e)
        return False, str(e), None


def restore_backup(backup_path: Path, dry_run: bool = False) -> tuple[bool, str, list[str]]:
    """Restore configuration from a backup.
    
    Returns: (success, message, restored_files)
    """
    restored_files = []
    
    if not backup_path.exists():
        return False, "Backup file not found", restored_files
    
    try:
        with tarfile.open(backup_path, "r:gz") as tar:
            # Verify backup
            metadata = None
            for member in tar.getmembers():
                if member.name == "backup_metadata.json":
                    f = tar.extractfile(member)
                    if f:
                        metadata = json.load(f)
                    break
            
            if metadata is None:
                return False, "Invalid backup: missing metadata", restored_files
            
            if dry_run:
                # Just list what would be restored
                for member in tar.getmembers():
                    if member.name != "backup_metadata.json":
                        restored_files.append("/" + member.name)
                return True, "Dry run complete", restored_files
            
            # Create a pre-restore backup
            pre_backup_success, _, _ = create_backup("Pre-restore automatic backup")
            if not pre_backup_success:
                logger.warning("Failed to create pre-restore backup")
            
            # Extract files
            for member in tar.getmembers():
                if member.name == "backup_metadata.json":
                    continue
                
                dest_path = Path("/") / member.name
                
                # Ensure parent directory exists
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Extract
                if member.isfile():
                    with tar.extractfile(member) as src:
                        if src:
                            with open(dest_path, "wb") as dst:
                                dst.write(src.read())
                    
                    # Preserve permissions
                    os.chmod(dest_path, member.mode)
                    restored_files.append(str(dest_path))
                elif member.isdir():
                    dest_path.mkdir(parents=True, exist_ok=True)
        
        logger.info("Restored %d files from backup", len(restored_files))
        return True, f"Restored {len(restored_files)} files", restored_files
    
    except Exception as e:
        logger.error("Restore failed: %s", e)
        return False, str(e), restored_files


def list_backups() -> list[dict]:
    """List available backups."""
    backups = []
    
    if not BACKUP_DIR.exists():
        return backups
    
    for backup_file in sorted(BACKUP_DIR.glob("*.tar.gz"), reverse=True):
        try:
            stat = backup_file.stat()
            
            # Try to read metadata
            metadata = {}
            with tarfile.open(backup_file, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name == "backup_metadata.json":
                        f = tar.extractfile(member)
                        if f:
                            metadata = json.load(f)
                        break
            
            backups.append({
                "filename": backup_file.name,
                "path": str(backup_file),
                "size": stat.st_size,
                "created_at": metadata.get("created_at", datetime.fromtimestamp(stat.st_mtime).isoformat()),
                "description": metadata.get("description", ""),
                "file_count": len(metadata.get("files", [])),
            })
        except Exception as e:
            logger.warning("Error reading backup %s: %s", backup_file, e)
    
    return backups


def get_backup_info(filename: str) -> Optional[dict]:
    """Get detailed info about a specific backup."""
    backup_path = BACKUP_DIR / filename
    
    if not backup_path.exists():
        return None
    
    try:
        with tarfile.open(backup_path, "r:gz") as tar:
            metadata = {}
            files = []
            
            for member in tar.getmembers():
                if member.name == "backup_metadata.json":
                    f = tar.extractfile(member)
                    if f:
                        metadata = json.load(f)
                else:
                    files.append({
                        "path": "/" + member.name,
                        "size": member.size,
                        "is_dir": member.isdir(),
                    })
            
            return {
                "filename": filename,
                "path": str(backup_path),
                "size": backup_path.stat().st_size,
                "metadata": metadata,
                "files": files,
            }
    except Exception as e:
        logger.error("Error reading backup info: %s", e)
        return None


def delete_backup(filename: str) -> tuple[bool, str]:
    """Delete a specific backup."""
    backup_path = BACKUP_DIR / filename
    
    if not backup_path.exists():
        return False, "Backup not found"
    
    # Verify it's a backup file
    if not filename.startswith("networktap_backup_") or not filename.endswith(".tar.gz"):
        return False, "Invalid backup filename"
    
    try:
        backup_path.unlink()
        logger.info("Deleted backup: %s", filename)
        return True, "Backup deleted"
    except Exception as e:
        logger.error("Error deleting backup: %s", e)
        return False, str(e)


def cleanup_old_backups(keep: int = MAX_BACKUPS) -> int:
    """Remove old backups, keeping the most recent ones."""
    if not BACKUP_DIR.exists():
        return 0
    
    backups = sorted(BACKUP_DIR.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    removed = 0
    for backup in backups[keep:]:
        try:
            backup.unlink()
            removed += 1
            logger.info("Cleaned up old backup: %s", backup.name)
        except Exception as e:
            logger.warning("Failed to remove old backup %s: %s", backup.name, e)
    
    return removed


def get_backup_path() -> Path:
    """Get the backup directory path."""
    return BACKUP_DIR
