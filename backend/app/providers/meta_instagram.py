"""Instagram provider using Meta Graph API with Business Discovery"""
import os
import logging
from datetime import datetime, date
from typing import Optional
import httpx

from app.domain.models import InstagramPost, PostType, FetchMetadata
from app.domain.exceptions import InstagramProviderException
from app.providers.instagram import InstagramProvider
from app.utils import normalize_instagram_username, to_bogota_time

logger = logging.getLogger(__name__)


class MetaInstagramProvider(InstagramProvider):
    """Instagram provider using Meta Graph API with nested Business Discovery media pagination"""

    def __init__(
        self,
        access_token: str = None,
        ig_user_id: str = None,
        api_version: str = "v26.0",
        page_size: int = 50,
        max_pages: int = 100,
    ):
        """
        Initialize Meta Instagram provider.

        Args:
            access_token: Meta API access token (defaults to META_ACCESS_TOKEN env var)
            ig_user_id: Source Instagram Professional Account ID (defaults to META_IG_USER_ID env var)
            api_version: Graph API version (defaults to META_GRAPH_API_VERSION env var or v26.0)
            page_size: Media items per API page (defaults to META_PAGE_SIZE env var or 50)
            max_pages: Max pages to fetch (defaults to META_MAX_PAGES env var or 100)

        Raises:
            InstagramProviderException: If required credentials missing
        """
        self.access_token = access_token or os.getenv("META_ACCESS_TOKEN")
        self.ig_user_id = ig_user_id or os.getenv("META_IG_USER_ID")
        self.api_version = api_version or os.getenv("META_GRAPH_API_VERSION", "v26.0")
        self.page_size = page_size or int(os.getenv("META_PAGE_SIZE", "50"))
        self.max_pages = max_pages or int(os.getenv("META_MAX_PAGES", "100"))

        if not self.access_token or not self.ig_user_id:
            raise InstagramProviderException(
                "Meta Instagram API requires META_ACCESS_TOKEN and META_IG_USER_ID environment variables"
            )

        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        self.client = None
        self.fetch_metadata_by_account = {}

    @property
    def supports_native_pagination(self) -> bool:
        """Meta API handles pagination internally"""
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

    def _extract_shortcode(self, permalink: str) -> str:
        """
        Extract Instagram shortcode from permalink.

        Supports:
            /p/SHORTCODE/
            /reel/SHORTCODE/

        Returns:
            Shortcode string or empty string if not found
        """
        if not permalink:
            return ""

        # Try /p/ pattern
        if "/p/" in permalink:
            parts = permalink.split("/p/")
            if len(parts) > 1:
                shortcode = parts[1].split("?")[0].split("#")[0].rstrip("/")
                if shortcode:
                    return shortcode

        # Try /reel/ pattern
        if "/reel/" in permalink:
            parts = permalink.split("/reel/")
            if len(parts) > 1:
                shortcode = parts[1].split("?")[0].split("#")[0].rstrip("/")
                if shortcode:
                    return shortcode

        return ""

    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """
        Parse ISO-8601 timestamp from Meta API and convert to Bogota timezone.

        Args:
            timestamp_str: ISO-8601 timestamp string (e.g., "2026-09-28T19:47:53+0000")

        Returns:
            datetime in Bogota timezone, or None if parsing fails
        """
        if not timestamp_str:
            return None

        try:
            # Parse ISO-8601 format
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            # Convert to Bogota timezone
            return to_bogota_time(dt)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp {timestamp_str}: {e}")
            return None

    def _map_media_type(self, media_type: str, is_reel: bool = False) -> PostType:
        """
        Map Meta media_type to domain PostType.

        Args:
            media_type: Meta API media_type string
            is_reel: Whether this is a reel (checked via permalink)

        Returns:
            PostType enum value
        """
        if media_type == "IMAGE":
            return PostType.PHOTO
        elif media_type == "CAROUSEL_ALBUM":
            return PostType.CAROUSEL
        elif media_type == "VIDEO":
            if is_reel:
                return PostType.REEL
            return PostType.VIDEO
        else:
            return PostType.PHOTO

    def _media_to_post(self, media: dict, username: str) -> Optional[InstagramPost]:
        """
        Convert Meta media item to domain InstagramPost.

        Extracts expanded visual data: thumbnails, children, media_product_type.

        Args:
            media: Media item from Meta API
            username: Instagram username (target account)

        Returns:
            InstagramPost instance or None if conversion fails
        """
        try:
            permalink = media.get("permalink", "")
            shortcode = self._extract_shortcode(permalink)

            if not shortcode:
                logger.warning(f"Could not extract shortcode from {permalink}")
                return None

            # Determine if this is a reel (check media_product_type first, then permalink)
            is_reel = (
                media.get("media_product_type") == "REELS"
                or ("/reel/" in permalink if permalink else False)
            )

            media_type = self._map_media_type(
                media.get("media_type", "IMAGE"),
                is_reel=is_reel
            )

            # Parse timestamp and convert to Bogota
            timestamp_str = media.get("timestamp")
            published_at = self._parse_timestamp(timestamp_str) if timestamp_str else None

            # Determine thumbnail_url based on media type and available Meta fields
            thumbnail_url = None
            media_count = 1

            # Check for children (carousel/album items)
            children_data = media.get("children", {})
            children_list = children_data.get("data", [])
            if children_list:
                media_count = len(children_list)

            if media_type == PostType.PHOTO:
                # IMAGE: prefer thumbnail_url from Meta, fallback to media_url
                thumbnail_url = media.get("thumbnail_url") or media.get("media_url")

            elif media_type == PostType.CAROUSEL:
                # CAROUSEL_ALBUM: use thumbnail_url from Meta if available
                # or first child's visual resource
                thumbnail_url = media.get("thumbnail_url")
                if not thumbnail_url and children_list:
                    # Try to get thumbnail from first child
                    first_child = children_list[0]
                    thumbnail_url = first_child.get("thumbnail_url") or first_child.get("media_url")

            elif media_type in (PostType.VIDEO, PostType.REEL):
                # VIDEO/REEL: use thumbnail_url from Meta (not MP4)
                thumbnail_url = media.get("thumbnail_url")
                # Note: media_url for videos is the MP4, not suitable as thumbnail

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

    async def _fetch_business_discovery_page(
        self,
        username: str,
        cursor: Optional[str] = None,
    ) -> dict:
        """
        Fetch one page of media using Business Discovery with nested media pagination.

        Requests expanded media fields including thumbnails and children for better visual matching.

        Args:
            username: Target Instagram username
            cursor: Pagination cursor for nested media.after()

        Returns:
            Full API response dict containing business_discovery object
        """
        await self._ensure_client()

        # Build field expansion with expanded media fields for visual data
        media_fields = (
            "id,caption,media_type,media_product_type,"
            "media_url,thumbnail_url,permalink,timestamp,"
            "children{id,media_type,media_url,thumbnail_url}"
        )

        if cursor:
            # Second and subsequent pages use after cursor
            media_field = f"media.limit({self.page_size}).after({cursor}){{{media_fields}}}"
        else:
            # First page
            media_field = f"media.limit({self.page_size}){{{media_fields}}}"

        fields = f"business_discovery.username({username}){{id,username,{media_field}}}"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }

        try:
            response = await self.client.get(
                f"{self.base_url}/{self.ig_user_id}",
                headers=headers,
                params={"fields": fields},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            # Check for API-level errors
            if "error" in data:
                error = data["error"]
                # Log sanitized error info (no token, no URLs)
                logger.warning(
                    f"Meta API error: code={error.get('code')}, "
                    f"type={error.get('type')}, "
                    f"message={error.get('message', 'no message')}"
                )

            return data

        except httpx.HTTPError as e:
            logger.error(f"Meta API HTTP error: status code not 2xx")
            raise InstagramProviderException(f"Failed to fetch from Meta API: {e}")

    async def get_posts(
        self,
        account: str,
        limit: int | None = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> list[InstagramPost]:
        """
        Fetch posts from Instagram account using Meta Graph API Business Discovery.

        Uses nested media pagination within business_discovery field expansion.

        Args:
            account: Instagram username to fetch
            limit: Max posts to fetch (count mode when set, date mode when None)
            from_date: Start date for date mode
            to_date: End date for date mode

        Returns:
            List of InstagramPost objects
        """
        try:
            # Normalize username
            username = normalize_instagram_username(account)

            posts = []
            seen_ids = set()
            pages_fetched = 0
            cursor = None
            last_cursor = None
            completed = False
            stop_reason = None

            # Paginate through media using nested business_discovery.media
            while pages_fetched < self.max_pages:
                data = await self._fetch_business_discovery_page(username, cursor)

                # Handle errors
                if "error" in data:
                    error = data["error"]
                    raise InstagramProviderException(
                        f"Meta API error: {error.get('message', 'Unknown error')}"
                    )

                # Extract business_discovery object
                business_discovery = data.get("business_discovery", {})
                if not business_discovery:
                    # Target not found or not accessible
                    completed = True
                    stop_reason = "target_not_found"
                    break

                # Extract media and paging
                media_data = business_discovery.get("media", {})
                media_list = media_data.get("data", [])

                if not media_list:
                    # No more media
                    completed = True
                    stop_reason = "end_of_media"
                    break

                # Process each media item
                for media in media_list:
                    media_id = media.get("id")

                    # Deduplicate
                    if media_id in seen_ids:
                        continue

                    seen_ids.add(media_id)

                    # Convert to domain model
                    post = self._media_to_post(media, account)
                    if not post:
                        continue

                    # Apply date filtering if in date mode
                    if from_date and post.published_at:
                        if post.published_at.date() < from_date:
                            # Dates are newest first; stop here
                            completed = True
                            stop_reason = "date_boundary_reached"
                            break
                    if to_date and post.published_at:
                        if post.published_at.date() > to_date:
                            # Skip posts after to_date
                            continue

                    posts.append(post)

                    # Count mode: stop when limit reached
                    if limit and len(posts) >= limit:
                        completed = True
                        stop_reason = "limit_reached"
                        break

                if stop_reason:
                    break

                pages_fetched += 1

                # Get next cursor
                paging = media_data.get("paging", {})
                next_cursor = paging.get("cursors", {}).get("after")

                if not next_cursor or next_cursor == last_cursor:
                    # No more pages or cursor repeated
                    completed = True
                    stop_reason = "end_of_media"
                    break

                last_cursor = next_cursor
                cursor = next_cursor

            # Log completion
            logger.info(
                f"Fetched {len(posts)} posts from @{account} "
                f"in {pages_fetched} pages (completed={completed}, reason={stop_reason})"
            )

            # Store metadata for ScanService
            self.fetch_metadata_by_account[account] = FetchMetadata(
                account=account,
                discovered_links=len(seen_ids),
                posts_with_date=len([p for p in posts if p.published_at]),
                undated_posts=len([p for p in posts if not p.published_at]),
                completed=completed,
                stop_reason=stop_reason,
                warning=None if completed else f"Partial fetch: {stop_reason}",
            )

            # In count mode, return only up to limit
            if limit:
                return posts[:limit]

            return posts

        except InstagramProviderException:
            raise
        except Exception as e:
            logger.error(f"Error fetching posts from @{account}: {e}")
            raise InstagramProviderException(f"Failed to fetch posts from @{account}: {e}")

    async def get_post(self, post_id: str) -> Optional[InstagramPost]:
        """
        Fetch a single post by ID.

        Not implemented for Meta provider yet.

        Args:
            post_id: Post ID or shortcode

        Returns:
            None (not implemented)
        """
        return None
