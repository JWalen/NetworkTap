"""Update management API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from core.auth import verify_credentials
from core.config import get_config
from core.update_manager import UpdateManager

router = APIRouter()
logger = logging.getLogger("networktap.api.update")

# Global update manager instance
_update_manager: UpdateManager | None = None


def get_update_manager() -> UpdateManager:
    """Get or create update manager instance."""
    global _update_manager
    if _update_manager is None:
        config = get_config()
        repo = getattr(config, 'github_repo', 'JWalen/NetworkTap')
        _update_manager = UpdateManager(repo=repo)
    return _update_manager


class UpdateCheckResponse(BaseModel):
    """Response for update check."""
    current_version: str
    latest_version: str
    update_available: bool
    changelog: str
    release_date: str
    prerelease: bool


class UpdateStatusResponse(BaseModel):
    """Response for update status."""
    state: str
    progress: int
    message: str
    error: str | None = None


class UpdateHistoryItem(BaseModel):
    """Update history entry."""
    version: str
    timestamp: str
    success: bool
    error: str | None = None


@router.get("/current")
async def get_current_version(user: Annotated[str, Depends(verify_credentials)]):
    """Get currently installed version."""
    manager = get_update_manager()
    version = manager.get_current_version()
    
    return {
        "version": version,
        "install_dir": str(manager.install_dir),
        "version_file": str(manager.version_file),
    }


@router.get("/check")
async def check_for_updates(
    user: Annotated[str, Depends(verify_credentials)],
    include_prerelease: bool = False
):
    """
    Check for available updates.
    
    Args:
        include_prerelease: Include pre-release versions
    """
    manager = get_update_manager()
    
    try:
        info = await manager.check_for_updates(include_prerelease)
        
        if not info:
            return {
                "update_available": False,
                "message": "No updates available or unable to check"
            }
        
        return UpdateCheckResponse(
            current_version=info.current_version,
            latest_version=info.latest_version,
            update_available=info.update_available,
            changelog=info.changelog,
            release_date=info.release_date.isoformat(),
            prerelease=include_prerelease,
        )
        
    except Exception as e:
        logger.error(f"Failed to check for updates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_update_status(user: Annotated[str, Depends(verify_credentials)]):
    """Get current update operation status."""
    manager = get_update_manager()
    status = manager.get_status()
    
    return UpdateStatusResponse(
        state=status.state,
        progress=status.progress,
        message=status.message,
        error=status.error,
    )


@router.post("/download")
async def download_update(
    user: Annotated[str, Depends(verify_credentials)],
    background_tasks: BackgroundTasks,
    version: str | None = None,
    include_prerelease: bool = False
):
    """
    Download an update package.
    
    Args:
        version: Specific version to download (optional, uses latest if not specified)
        include_prerelease: Include pre-release versions
    """
    manager = get_update_manager()
    
    try:
        # Get update info
        info = await manager.check_for_updates(include_prerelease)
        
        if not info:
            raise HTTPException(status_code=404, detail="No updates available")
        
        if version and info.latest_version != version:
            raise HTTPException(
                status_code=400,
                detail=f"Requested version {version} does not match latest {info.latest_version}"
            )
        
        if not info.update_available:
            return {
                "message": "Already at latest version",
                "current_version": info.current_version,
            }
        
        # Start download in background
        async def download_task():
            success = await manager.download_update(info)
            if success:
                logger.info(f"Downloaded version {info.latest_version}")
            else:
                logger.error(f"Failed to download version {info.latest_version}")
        
        background_tasks.add_task(download_task)
        
        return {
            "message": "Download started",
            "version": info.latest_version,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start download: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/install")
async def install_update(
    user: Annotated[str, Depends(verify_credentials)],
    background_tasks: BackgroundTasks,
    version: str,
    skip_backup: bool = False
):
    """
    Install a downloaded update.
    
    Args:
        version: Version to install
        skip_backup: Skip backup step (not recommended)
    """
    manager = get_update_manager()
    
    try:
        # Verify download exists
        tarball_path = manager.download_dir / f"networktap-{version}.tar.gz"
        if not tarball_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Update package for version {version} not found. Download it first."
            )
        
        # Start installation in background
        async def install_task():
            success = await manager.install_update(version, skip_backup)
            if success:
                logger.info(f"Successfully installed version {version}")
            else:
                logger.error(f"Failed to install version {version}")
        
        background_tasks.add_task(install_task)
        
        return {
            "message": "Installation started",
            "version": version,
            "warning": "Services will restart during installation"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start installation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update")
async def perform_full_update(
    user: Annotated[str, Depends(verify_credentials)],
    background_tasks: BackgroundTasks,
    include_prerelease: bool = False
):
    """
    Check, download, and install update in one operation.
    
    Args:
        include_prerelease: Include pre-release versions
    """
    manager = get_update_manager()
    
    try:
        # Check for updates first
        info = await manager.check_for_updates(include_prerelease)
        
        if not info or not info.update_available:
            return {
                "message": "No updates available",
                "current_version": manager.get_current_version()
            }
        
        # Start full update in background
        async def update_task():
            success = await manager.perform_full_update(include_prerelease)
            if success:
                logger.info(f"Successfully updated to version {info.latest_version}")
            else:
                logger.error("Full update failed")
        
        background_tasks.add_task(update_task)
        
        return {
            "message": "Update started",
            "current_version": info.current_version,
            "target_version": info.latest_version,
            "warning": "Services will restart during installation"
        }
        
    except Exception as e:
        logger.error(f"Failed to start update: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_update_history(user: Annotated[str, Depends(verify_credentials)]):
    """Get update history."""
    manager = get_update_manager()
    history = manager.get_update_history()
    
    return {
        "history": [
            UpdateHistoryItem(
                version=item["version"],
                timestamp=item["timestamp"],
                success=item["success"],
                error=item.get("error")
            )
            for item in history
        ]
    }


@router.post("/rollback")
async def rollback_update(
    user: Annotated[str, Depends(verify_credentials)],
    background_tasks: BackgroundTasks
):
    """
    Rollback to previous version.
    
    WARNING: This will stop services and restore from backup.
    """
    manager = get_update_manager()
    
    try:
        async def rollback_task():
            success = await manager._rollback()
            if success:
                logger.info("Rollback completed successfully")
            else:
                logger.error("Rollback failed")
        
        background_tasks.add_task(rollback_task)
        
        return {
            "message": "Rollback started",
            "warning": "Services will restart"
        }
        
    except Exception as e:
        logger.error(f"Failed to start rollback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/changelog/{version}")
async def get_changelog(
    user: Annotated[str, Depends(verify_credentials)],
    version: str
):
    """
    Get changelog for a specific version.
    
    Args:
        version: Version tag (e.g., "v1.0.1" or "1.0.1")
    """
    manager = get_update_manager()
    
    try:
        # Ensure version has 'v' prefix
        if not version.startswith('v'):
            version = f'v{version}'
        
        release = await manager.github.get_release_by_tag(version)
        
        if not release:
            raise HTTPException(status_code=404, detail=f"Release {version} not found")
        
        return {
            "version": release.version,
            "tag": release.tag_name,
            "name": release.name,
            "changelog": release.body,
            "published_at": release.published_at.isoformat(),
            "prerelease": release.prerelease,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get changelog: {e}")
        raise HTTPException(status_code=500, detail=str(e))
