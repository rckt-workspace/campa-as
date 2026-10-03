"""Service for manual links-based content audit"""
import logging
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse

from app.domain.models import InstagramPost
from app.providers.browser_instagram import BrowserInstagramProvider

logger = logging.getLogger(__name__)


class ManualAuditService:
    """Extract posts from manual URLs and audit"""

    def __init__(self, provider: BrowserInstagramProvider):
        self.provider = provider

    def normalize_url(self, url: str) -> str:
        """Normalize Instagram URL by removing query strings"""
        if "?" in url:
            url = url.split("?")[0]
        return url.rstrip("/") + "/"

    def extract_shortcode(self, url: str) -> Optional[str]:
        """Extract shortcode from Instagram URL"""
        try:
            if "/p/" in url:
                parts = url.split("/p/")
                if len(parts) > 1:
                    return parts[1].rstrip("/").split("?")[0]
            elif "/reel/" in url:
                parts = url.split("/reel/")
                if len(parts) > 1:
                    return parts[1].rstrip("/").split("?")[0]
        except Exception:
            pass
        return None

    def validate_url(self, url: str) -> bool:
        """Validate Instagram URL format securely"""
        if not url or not url.strip():
            return False

        url = url.strip()

        try:
            parsed = urlparse(url)
        except Exception:
            return False

        # Must be HTTPS
        if parsed.scheme != "https":
            return False

        # Hostname must be exactly instagram.com or www.instagram.com
        hostname = parsed.hostname
        if hostname not in ("instagram.com", "www.instagram.com"):
            return False

        # Path must contain /p/ or /reel/
        path = parsed.path
        if "/p/" not in path and "/reel/" not in path:
            return False

        return True

    async def extract_posts_from_links(
        self, account: str, links: list[str]
    ) -> tuple[list[InstagramPost], dict]:
        """
        Extract posts from list of URLs.

        Returns:
            (posts, stats)
            stats: {links_received, links_valid, posts_extracted, links_failed}
        """
        links_received = len(links)
        valid_links = []
        seen_shortcodes = set()

        # Validate and deduplicate by shortcode
        for link in links:
            if not self.validate_url(link):
                continue

            link = self.normalize_url(link)
            shortcode = self.extract_shortcode(link)

            if shortcode and shortcode not in seen_shortcodes:
                valid_links.append(link)
                seen_shortcodes.add(shortcode)

        links_valid = len(valid_links)
        posts = []
        failed_count = 0

        # Extract posts
        for link in valid_links:
            try:
                post = await self.provider.get_post_by_permalink(link)
                if post:
                    posts.append(post)
                else:
                    failed_count += 1
            except Exception as e:
                logger.warning(f"Failed to extract {link}: {e}")
                failed_count += 1

        posts_extracted = len(posts)

        stats = {
            "account": account,
            "links_received": links_received,
            "links_valid": links_valid,
            "posts_extracted": posts_extracted,
            "links_failed": failed_count,
        }

        logger.info(
            f"Manual audit @{account}: "
            f"received={links_received} valid={links_valid} extracted={posts_extracted} failed={failed_count}"
        )

        return posts, stats
