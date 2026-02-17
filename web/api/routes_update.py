"""Update management API endpoints."""

import logging
import subprocess
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

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


def _get_git_info(install_dir: Path) -> dict:
    """Get git commit hash and install date from the install directory."""
    info = {"commit_hash": None, "installed_date": None}
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H %aI"],
            cwd=str(install_dir), capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(" ", 1)
            if len(parts) >= 1:
                info["commit_hash"] = parts[0]
            if len(parts) >= 2:
                info["installed_date"] = parts[1]
    except Exception:
        pass
    return info


@router.get("/current")
async def get_current_version(user: Annotated[str, Depends(verify_credentials)]):
    """Get currently installed version."""
    manager = get_update_manager()
    version = manager.get_current_version()
    git_info = _get_git_info(manager.install_dir)

    return {
        "version": version,
        "repository": manager.repo,
        "commit_hash": git_info["commit_hash"],
        "installed_date": git_info["installed_date"],
    }


@router.get("/check")
async def check_for_updates(
    user: Annotated[str, Depends(verify_credentials)],
    include_prerelease: bool = False
):
    """Check for available updates."""
    manager = get_update_manager()

    try:
        info = await manager.check_for_updates(include_prerelease)

        if not info:
            return {
                "update_available": False,
                "current_version": manager.get_current_version(),
                "latest_version": manager.get_current_version(),
                "message": "No releases found on GitHub",
            }

        return {
            "update_available": info.update_available,
            "current_version": info.current_version,
            "latest_version": info.latest_version,
            "release_notes": info.changelog,
            "published_at": info.release_date.isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to check for updates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_update_status(user: Annotated[str, Depends(verify_credentials)]):
    """Get current update operation status."""
    manager = get_update_manager()
    status = manager.get_status()

    in_progress = status.state not in ("idle", "complete", "failed", "rolled_back")

    return {
        "state": status.state,
        "in_progress": in_progress,
        "operation": status.state,
        "progress": status.progress,
        "message": status.message,
        "error": status.error,
    }


@router.post("/download")
async def download_update(
    user: Annotated[str, Depends(verify_credentials)],
    background_tasks: BackgroundTasks,
    version: str | None = None,
    include_prerelease: bool = False
):
    """Download an update package."""
    manager = get_update_manager()

    try:
        info = await manager.check_for_updates(include_prerelease)

        if not info:
            return {"success": False, "message": "No updates available"}

        if version and info.latest_version != version:
            return {"success": False, "message": f"Requested version {version} does not match latest {info.latest_version}"}

        if not info.update_available:
            return {"success": True, "message": "Already at latest version"}

        async def download_task():
            success = await manager.download_update(info)
            if success:
                logger.info(f"Downloaded version {info.latest_version}")
            else:
                logger.error(f"Failed to download version {info.latest_version}")

        background_tasks.add_task(download_task)

        return {
            "success": True,
            "message": "Download started",
            "version": info.latest_version,
        }

    except Exception as e:
        logger.error(f"Failed to start download: {e}")
        return {"success": False, "message": str(e)}


@router.post("/install")
async def install_update(
    user: Annotated[str, Depends(verify_credentials)],
    background_tasks: BackgroundTasks,
    version: str,
    skip_backup: bool = False
):
    """Install a downloaded update."""
    manager = get_update_manager()

    try:
        tarball_path = manager.download_dir / f"networktap-{version}.tar.gz"
        if not tarball_path.exists():
            return {"success": False, "message": f"Update package for version {version} not found. Download it first."}

        async def install_task():
            success = await manager.install_update(version, skip_backup)
            if success:
                logger.info(f"Successfully installed version {version}")
            else:
                logger.error(f"Failed to install version {version}")

        background_tasks.add_task(install_task)

        return {
            "success": True,
            "message": "Installation started",
            "version": version,
        }

    except Exception as e:
        logger.error(f"Failed to start installation: {e}")
        return {"success": False, "message": str(e)}


@router.post("/update")
async def perform_full_update(
    user: Annotated[str, Depends(verify_credentials)],
    background_tasks: BackgroundTasks,
    include_prerelease: bool = False
):
    """Check, download, and install update in one operation."""
    manager = get_update_manager()

    try:
        info = await manager.check_for_updates(include_prerelease)

        if not info or not info.update_available:
            return {
                "success": True,
                "message": "No updates available",
                "current_version": manager.get_current_version(),
            }

        async def update_task():
            success = await manager.perform_full_update(include_prerelease)
            if success:
                logger.info(f"Successfully updated to version {info.latest_version}")
            else:
                logger.error("Full update failed")

        background_tasks.add_task(update_task)

        return {
            "success": True,
            "message": "Update started",
            "current_version": info.current_version,
            "target_version": info.latest_version,
        }

    except Exception as e:
        logger.error(f"Failed to start update: {e}")
        return {"success": False, "message": str(e)}


@router.get("/history")
async def get_update_history(user: Annotated[str, Depends(verify_credentials)]):
    """Get update history."""
    manager = get_update_manager()
    history = manager.get_update_history()

    return {
        "history": [
            {
                "version": item["version"],
                "timestamp": item["timestamp"],
                "success": item["success"],
                "previous_version": item.get("previous_version"),
                "notes": item.get("notes", item.get("error", "")),
            }
            for item in history
        ]
    }


@router.post("/rollback")
async def rollback_update(
    user: Annotated[str, Depends(verify_credentials)],
    background_tasks: BackgroundTasks
):
    """Rollback to previous version."""
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
            "success": True,
            "message": "Rollback started",
        }

    except Exception as e:
        logger.error(f"Failed to start rollback: {e}")
        return {"success": False, "message": str(e)}


@router.get("/changelog/{version}")
async def get_changelog(
    user: Annotated[str, Depends(verify_credentials)],
    version: str
):
    """Get changelog for a specific version."""
    manager = get_update_manager()

    try:
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
