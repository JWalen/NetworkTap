"""Backup and restore API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.auth import require_admin
from core.backup_manager import (
    create_backup,
    restore_backup,
    list_backups,
    get_backup_info,
    delete_backup,
    get_backup_path,
)
from pathlib import Path
import tempfile
import shutil

router = APIRouter()


class CreateBackupRequest(BaseModel):
    description: str = ""


@router.get("/")
async def get_backups(user: Annotated[str, Depends(require_admin)]):
    """List all available backups (admin only)."""
    backups = list_backups()
    return {"backups": backups, "count": len(backups)}


@router.post("/")
async def create_new_backup(
    body: CreateBackupRequest,
    user: Annotated[str, Depends(require_admin)],
):
    """Create a new backup (admin only)."""
    success, message, filename = create_backup(body.description)
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    return {"success": True, "message": message, "filename": filename}


@router.get("/{filename}")
async def get_backup_details(
    filename: str,
    user: Annotated[str, Depends(require_admin)],
):
    """Get details of a specific backup (admin only)."""
    info = get_backup_info(filename)
    
    if info is None:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    return info


@router.get("/{filename}/download")
async def download_backup(
    filename: str,
    user: Annotated[str, Depends(require_admin)],
):
    """Download a backup file (admin only)."""
    backup_path = get_backup_path() / filename
    
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")
    
    return FileResponse(
        path=str(backup_path),
        filename=filename,
        media_type="application/gzip",
    )


@router.post("/{filename}/restore")
async def restore_from_backup(
    filename: str,
    user: Annotated[str, Depends(require_admin)],
    dry_run: bool = False,
):
    """Restore from a backup (admin only)."""
    backup_path = get_backup_path() / filename
    
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")
    
    success, message, restored_files = restore_backup(backup_path, dry_run=dry_run)
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    return {
        "success": True,
        "message": message,
        "restored_files": restored_files,
        "dry_run": dry_run,
    }


@router.delete("/{filename}")
async def remove_backup(
    filename: str,
    user: Annotated[str, Depends(require_admin)],
):
    """Delete a backup (admin only)."""
    success, message = delete_backup(filename)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@router.post("/upload")
async def upload_backup(
    user: Annotated[str, Depends(require_admin)],
    file: UploadFile = File(...),
):
    """Upload a backup file (admin only)."""
    if not file.filename or not file.filename.endswith(".tar.gz"):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be .tar.gz")
    
    # Validate filename
    if not file.filename.startswith("networktap_backup_"):
        raise HTTPException(status_code=400, detail="Invalid backup filename")
    
    backup_dir = get_backup_path()
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    dest_path = backup_dir / file.filename
    
    if dest_path.exists():
        raise HTTPException(status_code=409, detail="Backup already exists")
    
    try:
        # Save uploaded file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        
        # Move to backup directory
        shutil.move(tmp_path, dest_path)
        
        return {"success": True, "message": "Backup uploaded", "filename": file.filename}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
