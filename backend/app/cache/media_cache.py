"""Media cache for Instagram thumbnails"""
import logging
from pathlib import Path
from typing import Optional
import hashlib
import httpx

logger = logging.getLogger(__name__)


class MediaCache:
    """Cache for Instagram media thumbnails"""

    def __init__(self, cache_dir: str = "data/cache", timeout: float = 10.0):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout

    def _get_cache_path(self, username: str, shortcode: str) -> Path:
        """Generate consistent cache filename for a post"""
        filename = f"{username}_{shortcode}.jpg"
        return self.cache_dir / filename

    def get_local_thumbnail(
        self,
        username: str,
        shortcode: str,
        thumbnail_url: Optional[str],
    ) -> Optional[Path]:
        """
        Get local thumbnail path, downloading if necessary.

        Returns:
            Path to local file if available/downloaded, None if unavailable
        """
        if not thumbnail_url:
            logger.debug(f"No thumbnail URL for {username}_{shortcode}")
            return None

        cache_path = self._get_cache_path(username, shortcode)

        # Cache hit
        if cache_path.exists():
            logger.debug(f"Cache hit: {cache_path.name}")
            return cache_path

        # Download
        try:
            return self._download_thumbnail(thumbnail_url, cache_path)
        except Exception as e:
            logger.warning(f"Failed to download thumbnail for {shortcode}: {e}")
            return None

    def _download_thumbnail(self, url: str, destination: Path) -> Optional[Path]:
        """Download and save thumbnail to cache"""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                    },
                    follow_redirects=True,
                )
                response.raise_for_status()

                # Save to disk
                destination.write_bytes(response.content)
                logger.debug(f"Downloaded thumbnail: {destination.name}")
                return destination
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error downloading {url}: {e.response.status_code}")
            return None
        except httpx.TimeoutException:
            logger.warning(f"Timeout downloading thumbnail: {url}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error downloading thumbnail: {e}")
            return None

    def clear_cache(self) -> int:
        """Clear all cached files. Returns count of deleted files."""
        if not self.cache_dir.exists():
            return 0

        count = 0
        for file in self.cache_dir.glob("*.jpg"):
            try:
                file.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"Failed to delete {file}: {e}")

        return count

    def cache_size(self) -> int:
        """Return number of cached files"""
        if not self.cache_dir.exists():
            return 0
        return len(list(self.cache_dir.glob("*.jpg")))
