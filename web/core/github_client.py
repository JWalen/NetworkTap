"""GitHub API client for release management."""

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("networktap.github")


@dataclass
class GitHubRelease:
    """GitHub release information."""
    
    tag_name: str
    name: str
    body: str  # Markdown changelog
    published_at: datetime
    tarball_url: str
    assets: dict[str, str]  # filename -> download_url
    prerelease: bool
    draft: bool
    
    @property
    def version(self) -> str:
        """Extract version from tag (remove 'v' prefix)."""
        return self.tag_name.lstrip('v')


class GitHubClient:
    """Client for GitHub API operations."""
    
    def __init__(self, repo: str, timeout: int = 30):
        """
        Initialize GitHub client.
        
        Args:
            repo: Repository in format "owner/repo"
            timeout: Request timeout in seconds
        """
        self.repo = repo
        self.timeout = timeout
        self.base_url = "https://api.github.com"
        self.headers = {
            "User-Agent": "NetworkTap-Updater",
            "Accept": "application/vnd.github+json",
        }
        self._cache: dict[str, tuple[datetime, any]] = {}
        self._cache_ttl = timedelta(minutes=5)
    
    def _get_cache(self, key: str) -> Optional[any]:
        """Get cached value if not expired."""
        if key in self._cache:
            timestamp, value = self._cache[key]
            if datetime.now() - timestamp < self._cache_ttl:
                return value
        return None
    
    def _set_cache(self, key: str, value: any):
        """Store value in cache."""
        self._cache[key] = (datetime.now(), value)

    def flush_cache(self):
        """Clear all cached responses."""
        self._cache.clear()
    
    async def get_latest_release(self, include_prerelease: bool = False) -> Optional[GitHubRelease]:
        """
        Get the latest release from GitHub.
        
        Args:
            include_prerelease: Include pre-release versions
            
        Returns:
            GitHubRelease or None if no releases found
        """
        cache_key = f"latest_release_{include_prerelease}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                # Get latest release (non-prerelease by default)
                if not include_prerelease:
                    url = f"{self.base_url}/repos/{self.repo}/releases/latest"
                    response = await client.get(url)
                    
                    if response.status_code == 404:
                        logger.warning("No releases found")
                        return None
                    
                    response.raise_for_status()
                    data = response.json()
                    release = self._parse_release(data)
                    
                else:
                    # Get all releases and pick the latest (including prereleases)
                    url = f"{self.base_url}/repos/{self.repo}/releases"
                    response = await client.get(url, params={"per_page": 10})
                    response.raise_for_status()
                    
                    releases = response.json()
                    if not releases:
                        return None
                    
                    # Filter out drafts
                    releases = [r for r in releases if not r.get("draft", False)]
                    if not releases:
                        return None
                    
                    # Most recent is first
                    release = self._parse_release(releases[0])
                
                self._set_cache(cache_key, release)
                return release
                
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch latest release: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching release: {e}")
            return None
    
    async def get_release_by_tag(self, tag: str) -> Optional[GitHubRelease]:
        """Get a specific release by tag name."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                url = f"{self.base_url}/repos/{self.repo}/releases/tags/{tag}"
                response = await client.get(url)
                
                if response.status_code == 404:
                    logger.warning(f"Release {tag} not found")
                    return None
                
                response.raise_for_status()
                return self._parse_release(response.json())
                
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch release {tag}: {e}")
            return None
    
    async def list_releases(self, limit: int = 10) -> list[GitHubRelease]:
        """List recent releases."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                url = f"{self.base_url}/repos/{self.repo}/releases"
                response = await client.get(url, params={"per_page": limit})
                response.raise_for_status()
                
                releases = response.json()
                # Filter out drafts
                releases = [r for r in releases if not r.get("draft", False)]
                return [self._parse_release(r) for r in releases]
                
        except httpx.HTTPError as e:
            logger.error(f"Failed to list releases: {e}")
            return []
    
    async def download_asset(self, url: str, dest: Path, expected_hash: Optional[str] = None) -> bool:
        """
        Download a release asset.
        
        Args:
            url: Asset download URL
            dest: Destination file path
            expected_hash: Expected SHA256 hash (optional)
            
        Returns:
            True if download successful and hash matches
        """
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
                logger.info(f"Downloading {url}...")
                
                # Stream download
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    
                    hasher = hashlib.sha256()
                    with open(dest, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
                            hasher.update(chunk)
                
                # Verify hash if provided
                if expected_hash:
                    actual_hash = hasher.hexdigest()
                    if actual_hash != expected_hash:
                        logger.error(f"Hash mismatch! Expected {expected_hash}, got {actual_hash}")
                        dest.unlink()
                        return False
                    logger.info("Hash verified successfully")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to download asset: {e}")
            if dest.exists():
                dest.unlink()
            return False
    
    def _parse_release(self, data: dict) -> GitHubRelease:
        """Parse GitHub release JSON into GitHubRelease object."""
        assets = {}
        for asset in data.get("assets", []):
            assets[asset["name"]] = asset["browser_download_url"]
        
        return GitHubRelease(
            tag_name=data["tag_name"],
            name=data["name"],
            body=data.get("body", ""),
            published_at=datetime.fromisoformat(data["published_at"].replace("Z", "+00:00")),
            tarball_url=data["tarball_url"],
            assets=assets,
            prerelease=data.get("prerelease", False),
            draft=data.get("draft", False),
        )


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two semantic version strings.
    
    Args:
        v1: First version (e.g., "1.0.1")
        v2: Second version (e.g., "1.0.2")
    
    Returns:
        -1 if v1 < v2
         0 if v1 == v2
         1 if v1 > v2
    """
    def parse_version(v: str) -> tuple:
        """Parse version string into comparable tuple."""
        # Remove 'v' prefix if present
        v = v.lstrip('v')
        
        # Split by dots and handle pre-release tags
        parts = v.split('-')[0].split('.')
        
        # Convert to integers, pad with zeros
        nums = []
        for part in parts:
            try:
                nums.append(int(part))
            except ValueError:
                nums.append(0)
        
        # Ensure at least 3 components
        while len(nums) < 3:
            nums.append(0)
        
        return tuple(nums[:3])
    
    v1_tuple = parse_version(v1)
    v2_tuple = parse_version(v2)
    
    if v1_tuple < v2_tuple:
        return -1
    elif v1_tuple > v2_tuple:
        return 1
    else:
        return 0
