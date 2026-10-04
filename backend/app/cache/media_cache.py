"""Media cache for Instagram thumbnails"""
import logging
import os
import asyncio
from pathlib import Path
from typing import Optional, Callable
from html import unescape
import httpx

logger = logging.getLogger(__name__)


class MediaCache:
    """Cache for Instagram media thumbnails with async downloads and concurrency limiting"""

    def __init__(
        self,
        cache_dir: str = "data/cache",
        timeout: float = 10.0,
        media_fetcher: Optional[Callable] = None,
        max_concurrent_downloads: int = None,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.media_fetcher = media_fetcher

        # Concurrency limiting
        if max_concurrent_downloads is None:
            max_concurrent_downloads = int(
                os.getenv("MEDIA_DOWNLOAD_CONCURRENCY", "6")
            )
        self.semaphore = asyncio.Semaphore(max_concurrent_downloads)
        self.client: Optional[httpx.AsyncClient] = None

    def _get_cache_path(self, username: str, shortcode: str) -> Path:
        """Generate consistent cache filename for a post"""
        filename = f"{username}_{shortcode}.jpg"
        return self.cache_dir / filename

    async def get_local_thumbnail(
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
            return await self._download_thumbnail(thumbnail_url, cache_path, username, shortcode)
        except Exception as e:
            logger.warning(f"Failed to download thumbnail for {shortcode}: {e}")
            return None

    async def _ensure_client(self):
        """Ensure AsyncClient is initialized"""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self):
        """Close the AsyncClient"""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def _download_thumbnail(
        self,
        url: str,
        destination: Path,
        username: str,
        shortcode: str,
    ) -> Optional[Path]:
        """Download and save thumbnail to cache, with fallback via media_fetcher"""
        # Normalize URL: decode HTML entities (&amp; → &)
        url = unescape(url)

        async with self.semaphore:
            try:
                await self._ensure_client()
                response = await self.client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "Referer": "https://www.instagram.com/",
                        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    },
                    follow_redirects=True,
                )

                # Validate response
                if response.status_code == 200 and response.content:
                    content_type = response.headers.get("content-type", "").lower()
                    if content_type.startswith("image/"):
                        destination.write_bytes(response.content)
                        logger.debug(f"Downloaded via HTTP: @{username}/{shortcode}")
                        return destination

                    # If 200 but not image, try media_fetcher fallback
                    if self.media_fetcher:
                        logger.debug(f"HTTP 200 but non-image content-type, trying fallback for @{username}/{shortcode}")
                        content = await self.media_fetcher(url)
                        if content:
                            destination.write_bytes(content)
                            logger.debug(f"Downloaded via fallback: @{username}/{shortcode}")
                            return destination

                # If 403, try media_fetcher fallback
                if response.status_code == 403 and self.media_fetcher:
                    logger.debug(f"HTTP 403, trying fallback for @{username}/{shortcode}")
                    content = await self.media_fetcher(url)
                    if content:
                        destination.write_bytes(content)
                        logger.debug(f"Downloaded via fallback: @{username}/{shortcode}")
                        return destination

                logger.warning(f"HTTP {response.status_code} for @{username}/{shortcode}")
                return None

            except httpx.TimeoutException:
                logger.warning(f"Timeout downloading @{username}/{shortcode}")
                # Try media_fetcher fallback on timeout
                if self.media_fetcher:
                    try:
                        content = await self.media_fetcher(url)
                        if content:
                            destination.write_bytes(content)
                            logger.debug(f"Downloaded via fallback after timeout: @{username}/{shortcode}")
                            return destination
                    except Exception as e:
                        logger.warning(f"Fallback also failed for @{username}/{shortcode}: {e}")
                return None
            except Exception as e:
                logger.warning(f"Error downloading @{username}/{shortcode}: {e}")
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
