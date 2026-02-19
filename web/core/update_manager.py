"""Update manager for NetworkTap in-place upgrades."""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.github_client import GitHubClient, GitHubRelease, compare_versions

logger = logging.getLogger("networktap.update")


@dataclass
class UpdateInfo:
    """Information about an available update."""
    
    current_version: str
    latest_version: str
    update_available: bool
    changelog: str
    release_date: datetime
    download_url: str
    checksum_url: Optional[str]


@dataclass
class UpdateStatus:
    """Status of an update operation."""
    
    state: str  # idle, checking, downloading, installing, complete, failed, rolled_back
    progress: int  # 0-100
    message: str
    error: Optional[str] = None


class UpdateManager:
    """Manages NetworkTap software updates."""
    
    def __init__(self, repo: str = "JWalen/NetworkTap"):
        """Initialize update manager."""
        self.repo = repo
        self.github = GitHubClient(repo)
        self.install_dir = Path("/opt/networktap")
        self.backup_dir = Path("/opt/networktap-backups")
        self.download_dir = Path("/tmp/networktap-updates")
        self.version_file = Path("/opt/networktap/VERSION")
        self.history_file = Path("/var/lib/networktap/update_history.json")
        
        self._status = UpdateStatus(state="idle", progress=0, message="Ready")
        self._current_task: Optional[asyncio.Task] = None
    
    def get_current_version(self) -> str:
        """Get currently installed version."""
        try:
            # Try /opt/networktap/VERSION first
            if self.version_file.exists():
                return self.version_file.read_text().strip()
            # Fall back to VERSION in project root
            project_version = Path(__file__).parent.parent.parent / "VERSION"
            if project_version.exists():
                return project_version.read_text().strip()
            return "unknown"
        except Exception as e:
            logger.error(f"Failed to read version: {e}")
            return "unknown"
    
    async def check_for_updates(self, include_prerelease: bool = False) -> Optional[UpdateInfo]:
        """
        Check if updates are available.
        
        Args:
            include_prerelease: Include pre-release versions
            
        Returns:
            UpdateInfo or None if no updates available
        """
        try:
            self._update_status("checking", 0, "Checking for updates...")
            
            current_version = self.get_current_version()
            logger.info(f"Current version: {current_version}")
            
            latest_release = await self.github.get_latest_release(include_prerelease)
            if not latest_release:
                self._update_status("idle", 0, "No releases found")
                return None
            
            logger.info(f"Latest version: {latest_release.version}")
            
            # Compare versions
            comparison = compare_versions(current_version, latest_release.version)
            update_available = comparison < 0  # current < latest
            
            # Use GitHub's API tarball URL (always available, contains full repo)
            # Do NOT use release asset checksums — they're for CI-built tarballs,
            # not the API tarball, so hashes will never match
            tarball_url = latest_release.tarball_url

            info = UpdateInfo(
                current_version=current_version,
                latest_version=latest_release.version,
                update_available=update_available,
                changelog=latest_release.body,
                release_date=latest_release.published_at,
                download_url=tarball_url,
                checksum_url=None,
            )
            
            self._update_status("idle", 0, "Check complete")
            return info
            
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            self._update_status("failed", 0, f"Check failed: {e}")
            return None
    
    async def download_update(self, info: UpdateInfo) -> bool:
        """
        Download update package.
        
        Args:
            info: Update information
            
        Returns:
            True if download successful
        """
        try:
            self._update_status("downloading", 10, "Preparing download...")
            
            # Create download directory
            self.download_dir.mkdir(parents=True, exist_ok=True)
            
            tarball_path = self.download_dir / f"networktap-{info.latest_version}.tar.gz"
            checksum_path = self.download_dir / f"networktap-{info.latest_version}.tar.gz.sha256"
            
            # Download checksum first
            expected_hash = None
            if info.checksum_url:
                self._update_status("downloading", 20, "Downloading checksum...")
                success = await self.github.download_asset(
                    info.checksum_url,
                    checksum_path
                )
                if success and checksum_path.exists():
                    # Parse checksum file
                    content = checksum_path.read_text().strip()
                    # Format: "hash  filename" or just "hash"
                    expected_hash = content.split()[0]
                    logger.info(f"Expected SHA256: {expected_hash}")
            
            # Download tarball
            self._update_status("downloading", 30, "Downloading update package...")
            success = await self.github.download_asset(
                info.download_url,
                tarball_path,
                expected_hash=expected_hash
            )
            
            if not success:
                self._update_status("failed", 0, "Download failed")
                return False
            
            self._update_status("downloading", 100, "Download complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download update: {e}")
            self._update_status("failed", 0, f"Download failed: {e}")
            return False
    
    async def install_update(self, version: str, skip_backup: bool = False) -> bool:
        """
        Install a downloaded update.
        
        Args:
            version: Version to install
            skip_backup: Skip backup step (for testing)
            
        Returns:
            True if installation successful
        """
        try:
            self._update_status("installing", 0, "Starting installation...")
            previous_version = self.get_current_version()

            tarball_path = self.download_dir / f"networktap-{version}.tar.gz"
            if not tarball_path.exists():
                self._update_status("failed", 0, "Update package not found")
                return False
            
            # Backup current installation
            if not skip_backup:
                self._update_status("installing", 20, "Backing up current installation...")
                if not await self._backup_installation():
                    self._update_status("failed", 0, "Backup failed")
                    return False
            
            # Extract to temporary location
            self._update_status("installing", 40, "Extracting update...")
            extract_dir = self.download_dir / f"extract-{version}"
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            with tarfile.open(tarball_path, "r:gz") as tar:
                tar.extractall(extract_dir)

            # Find the extracted directory
            # GitHub tarballs extract to "Owner-Repo-sha/" format
            # Look for any single subdirectory that contains a VERSION file
            source_dir = None
            for child in extract_dir.iterdir():
                if child.is_dir() and (child / "VERSION").exists():
                    source_dir = child
                    break

            # Fallback: look for any single subdirectory
            if not source_dir:
                subdirs = [d for d in extract_dir.iterdir() if d.is_dir()]
                if len(subdirs) == 1:
                    source_dir = subdirs[0]
                else:
                    source_dir = extract_dir

            logger.info(f"Source directory: {source_dir}")

            # Verify source has required structure
            for required in ("web", "scripts", "VERSION"):
                if not (source_dir / required).exists():
                    self._update_status("failed", 0, f"Invalid update package: missing {required}")
                    return False

            # Run update script with FORCE=yes and SKIP_WEB_RESTART=yes
            self._update_status("installing", 60, "Installing update...")
            update_script = source_dir / "scripts" / "update.sh"
            if not update_script.exists():
                update_script = Path(__file__).parent.parent.parent / "scripts" / "update.sh"

            env = {**os.environ, "FORCE": "yes", "SKIP_WEB_RESTART": "yes"}

            # Use sudo if not running as root
            cmd = ["sudo", "bash", str(update_script), str(source_dir), str(self.install_dir)]
            if os.geteuid() == 0:
                cmd = ["bash", str(update_script), str(source_dir), str(self.install_dir)]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout, stderr = await proc.communicate()

            logger.info(f"Update script stdout: {stdout.decode()}")
            if stderr:
                logger.warning(f"Update script stderr: {stderr.decode()}")

            if proc.returncode != 0:
                error_msg = stderr.decode()
                logger.error(f"Update script failed: {error_msg}")
                self._update_status("failed", 0, f"Installation failed: {error_msg}")

                # Attempt rollback
                await self._rollback()
                return False

            # Update version file
            self.version_file.write_text(version + "\n")
            
            # Record in history
            await self._record_update(version, success=True, previous_version=previous_version)
            
            # Cleanup
            shutil.rmtree(extract_dir, ignore_errors=True)
            tarball_path.unlink(missing_ok=True)
            
            self._update_status("complete", 100, "Update installed successfully")
            logger.info(f"Successfully updated to version {version}")

            # Schedule web service restart so the new code is loaded
            # Small delay so the status response can be sent first
            try:
                loop = asyncio.get_running_loop()
                loop.call_later(3, self._restart_web_service)
            except RuntimeError:
                # No running loop — restart immediately
                self._restart_web_service()

            return True
            
        except Exception as e:
            logger.error(f"Failed to install update: {e}")
            self._update_status("failed", 0, f"Installation failed: {e}")
            await self._rollback()
            return False
    
    async def _backup_installation(self) -> bool:
        """Backup current installation."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            current_version = self.get_current_version()
            backup_path = self.backup_dir / f"backup-{current_version}-{timestamp}"
            
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Creating backup at {backup_path}...")
            
            # Copy installation directory
            shutil.copytree(
                self.install_dir,
                backup_path,
                ignore=shutil.ignore_patterns("*.pyc", "__pycache__", "*.log")
            )
            
            # Keep only last 5 backups
            backups = sorted(self.backup_dir.glob("backup-*"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old_backup in backups[5:]:
                shutil.rmtree(old_backup)
                logger.info(f"Removed old backup: {old_backup.name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False
    
    async def _rollback(self) -> bool:
        """Rollback to previous version."""
        try:
            self._update_status("rolling_back", 50, "Rolling back to previous version...")
            
            # Find most recent backup
            backups = sorted(self.backup_dir.glob("backup-*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not backups:
                logger.error("No backups found for rollback")
                return False
            
            backup_path = backups[0]
            logger.info(f"Rolling back from {backup_path}...")
            
            # Remove current installation
            if self.install_dir.exists():
                shutil.rmtree(self.install_dir)
            
            # Restore from backup
            shutil.copytree(backup_path, self.install_dir)
            
            self._update_status("rolled_back", 100, "Rolled back to previous version")
            logger.info("Rollback complete")
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    async def _record_update(self, version: str, success: bool, error: Optional[str] = None, previous_version: Optional[str] = None):
        """Record update in history."""
        try:
            history = []
            if self.history_file.exists():
                history = json.loads(self.history_file.read_text())

            history.insert(0, {
                "version": version,
                "previous_version": previous_version,
                "timestamp": datetime.now().isoformat(),
                "success": success,
                "error": error,
            })
            
            # Keep last 20 entries
            history = history[:20]
            
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            self.history_file.write_text(json.dumps(history, indent=2))
            
        except Exception as e:
            logger.error(f"Failed to record update: {e}")
    
    @staticmethod
    def _restart_web_service():
        """Restart the web service to load updated code."""
        try:
            logger.info("Restarting networktap-web service to load new version...")
            subprocess.Popen(
                ["sudo", "systemctl", "restart", "networktap-web"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.error(f"Failed to restart web service: {e}")

    def get_update_history(self) -> list[dict]:
        """Get update history."""
        try:
            if self.history_file.exists():
                return json.loads(self.history_file.read_text())
            return []
        except Exception as e:
            logger.error(f"Failed to read update history: {e}")
            return []
    
    def _update_status(self, state: str, progress: int, message: str, error: Optional[str] = None):
        """Update internal status."""
        self._status = UpdateStatus(state=state, progress=progress, message=message, error=error)
        logger.info(f"Update status: {state} ({progress}%) - {message}")
    
    def get_status(self) -> UpdateStatus:
        """Get current update status."""
        return self._status
    
    async def perform_full_update(self, include_prerelease: bool = False) -> bool:
        """
        Check, download, and install update in one operation.
        
        Args:
            include_prerelease: Include pre-release versions
            
        Returns:
            True if update successful
        """
        try:
            # Check for updates
            info = await self.check_for_updates(include_prerelease)
            if not info or not info.update_available:
                return True  # Nothing to update
            
            # Download
            if not await self.download_update(info):
                return False
            
            # Install
            return await self.install_update(info.latest_version)
            
        except Exception as e:
            logger.error(f"Full update failed: {e}")
            return False
