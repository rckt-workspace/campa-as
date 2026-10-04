"""Instagram provider using Meta Graph API"""
import logging
import os
from datetime import datetime, date
from typing import Optional
import httpx
from zoneinfo import ZoneInfo

from app.domain.models import InstagramPost, PostType
from app.domain.exceptions import InstagramProviderException
from app.providers.instagram import InstagramProvider

logger = logging.getLogger(__name__)


class MetaInstagramProvider(InstagramProvider):
    """Instagram provider using Meta Graph API with Business Discovery"""

    def __init__(self):
        """Initialize with Meta API credentials from environment"""
        self.access_token = os.getenv("META_ACCESS_TOKEN")
        self.ig_user_id = os.getenv("META_IG_USER_ID")
        self.graph_version = os.getenv("META_GRAPH_API_VERSION", "v18.0")
        self.max_pages = int(os.getenv("META_MAX_PAGES", "100"))

        if not self.access_token or not self.ig_user_id:
            raise InstagramProviderException(
                "Meta Instagram API no está configurada. "
                "Falta META_ACCESS_TOKEN o META_IG_USER_ID."
            )

        self.base_url = f"https://graph.facebook.com/{self.graph_version}"
        self.client = None

    @property
    def supports_reliable_history(self) -> bool:
        """Meta API provides reliable historical data"""
        return True

    async def _ensure_client(self):
        """Lazily initialize HTTP client"""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Clean up HTTP client"""
        if self.client:
            await self.client.aclose()
            self.client = None

    def _validate_username(self, username: str) -> str:
        """Validate and normalize Instagram username"""
        username = username.strip().lstrip("@")
        if not username or len(username) > 30:
            raise ValueError(f"Invalid username: {username}")
        # Allow alphanumeric, dots, underscores
        if not all(c.isalnum() or c in "._" for c in username):
            raise ValueError(f"Invalid characters in username: {username}")
        return username

    async def _discover_account(self, username: str) -> dict:
        """Use Business Discovery to find target account"""
        await self._ensure_client()

        username = self._validate_username(username)

        params = {
            "access_token": self.access_token,
            "fields": "id,username",
            "user_id": self.ig_user_id,
        }

        # Business Discovery query
        fields = f"business_discovery.username({username}){{id,username}}"
        params["fields"] = fields

        try:
            response = await self.client.get(
                f"{self.base_url}/{self.ig_user_id}",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                error = data["error"]
                code = error.get("code")
                message = error.get("message", "Unknown error")
                raise InstagramProviderException(
                    f"Meta API error [{code}]: {message}"
                )

            discovery = data.get("business_discovery", {})
            if not discovery or not discovery.get("id"):
                raise InstagramProviderException(
                    f"Target account @{username} not found or not accessible"
                )

            return discovery
        except httpx.HTTPError as e:
            logger.error(f"Meta API request failed: {e}")
            raise InstagramProviderException(f"Meta API request failed: {e}")

    async def _fetch_media_page(self, ig_user_id: str, after: str = None) -> dict:
        """Fetch one page of media for an account"""
        await self._ensure_client()

        params = {
            "access_token": self.access_token,
            "fields": (
                "id,caption,media_type,media_product_type,"
                "media_url,thumbnail_url,permalink,timestamp,"
                "children{id,media_type,media_url}"
            ),
            "limit": 50,
        }

        if after:
            params["after"] = after

        try:
            response = await self.client.get(
                f"{self.base_url}/{ig_user_id}/media",
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Media fetch failed: {e}")
            raise InstagramProviderException(f"Media fetch failed: {e}")

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse ISO timestamp from Meta API"""
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        # Convert to Bogota timezone
        bogota_tz = ZoneInfo("America/Bogota")
        return dt.astimezone(bogota_tz)

    def _extract_shortcode(self, permalink: str) -> str:
        """Extract shortcode from Instagram permalink"""
        if "/p/" in permalink:
            return permalink.split("/p/")[1].rstrip("/").split("?")[0]
        elif "/reel/" in permalink:
            return permalink.split("/reel/")[1].rstrip("/").split("?")[0]
        return ""

    def _map_media_type(self, media_type: str, media_product_type: str = None) -> PostType:
        """Map Meta media type to domain PostType"""
        if media_type == "IMAGE":
            return PostType.PHOTO
        elif media_type == "CAROUSEL_ALBUM":
            return PostType.CAROUSEL
        elif media_type == "VIDEO":
            if media_product_type == "REELS":
                return PostType.REEL
            return PostType.VIDEO
        return PostType.PHOTO

    def _media_to_post(self, media: dict, username: str) -> Optional[InstagramPost]:
        """Convert Meta media object to InstagramPost"""
        try:
            permalink = media.get("permalink", "")
            shortcode = self._extract_shortcode(permalink)

            if not shortcode:
                logger.warning(f"Could not extract shortcode from {permalink}")
                return None

            media_type = self._map_media_type(
                media.get("media_type"),
                media.get("media_product_type"),
            )

            timestamp_str = media.get("timestamp")
            published_at = self._parse_timestamp(timestamp_str) if timestamp_str else None

            # Determine media count from children
            children = media.get("children", {}).get("data", [])
            media_count = len(children) if children else 1

            # Use thumbnail if available, else media_url
            thumbnail_url = media.get("thumbnail_url") or media.get("media_url")

            is_video = media_type in (PostType.VIDEO, PostType.REEL)

            return InstagramPost(
                shortcode=shortcode,
                username=username,
                caption=media.get("caption", ""),
                post_type=media_type,
                published_at=published_at,
                permalink=permalink,
                thumbnail_url=thumbnail_url,
                is_video=is_video,
                media_count=media_count,
            )
        except Exception as e:
            logger.warning(f"Error converting media to post: {e}")
            return None

    async def get_posts(
        self,
        account: str,
        limit: int = None,
        from_date: date = None,
        to_date: date = None,
    ) -> list[InstagramPost]:
        """Fetch posts from account using Meta Graph API"""
        try:
            # Discover account
            target = await self._discover_account(account)
            ig_user_id = target["id"]

            posts = []
            seen_ids = set()
            pages_fetched = 0
            after = None

            # Paginate through media
            while pages_fetched < self.max_pages:
                data = await self._fetch_media_page(ig_user_id, after)

                if "error" in data:
                    error = data["error"]
                    code = error.get("code")
                    raise InstagramProviderException(
                        f"Meta API error [{code}]: {error.get('message')}"
                    )

                media_list = data.get("data", [])

                if not media_list:
                    break

                for media in media_list:
                    media_id = media.get("id")

                    # Skip duplicates
                    if media_id in seen_ids:
                        continue

                    seen_ids.add(media_id)

                    post = self._media_to_post(media, account)
                    if not post:
                        continue

                    # Apply date filter
                    if from_date and post.published_at:
                        if post.published_at.date() < from_date:
                            # Dates are newest first, so stop here
                            return posts
                    if to_date and post.published_at:
                        if post.published_at.date() > to_date:
                            continue

                    posts.append(post)

                    # Apply count limit
                    if limit and len(posts) >= limit:
                        return posts

                pages_fetched += 1

                # Check for next page
                paging = data.get("paging", {})
                after = paging.get("cursors", {}).get("after")
                if not after:
                    break

            logger.info(
                f"Fetched {len(posts)} posts from @{account} "
                f"in {pages_fetched} pages"
            )
            return posts

        except InstagramProviderException:
            raise
        except Exception as e:
            logger.error(f"Error fetching posts from @{account}: {e}")
            raise InstagramProviderException(f"Failed to fetch posts from @{account}: {e}")

    async def get_post(self, post_id: str) -> Optional[InstagramPost]:
        """Fetch a single post by ID (not implemented for Meta)"""
        # Meta API requires Business Discovery for specific posts
        # For now, return None - this is not the primary flow
        return None
