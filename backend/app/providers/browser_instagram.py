"""Instagram provider using Playwright to access public content"""
import logging
import re
from datetime import datetime, timezone
from html import unescape
from typing import Optional
from urllib.parse import urlparse

from app.domain.models import InstagramPost, PostType, FetchMetadata
from app.domain.exceptions import (
    InstagramProviderException,
    ProfileNotFoundException,
    PrivateProfileException,
)
from app.utils import to_bogota_time

logger = logging.getLogger(__name__)


class BrowserInstagramProvider:
    """Instagram provider using Playwright for public content access"""

    def __init__(self, headless: bool = True, viewport: dict = None):
        """
        Initialize Playwright provider.

        Args:
            headless: Run in headless mode (True) or with visible browser (False)
            viewport: Playwright viewport dict, default 1280x720
        """
        try:
            from playwright.async_api import async_playwright
            self.async_playwright = async_playwright
        except ImportError:
            raise ImportError(
                "Playwright is required. Install with: pip install playwright\n"
                "Then run: python -m playwright install chromium"
            )

        self.headless = headless
        self.viewport = viewport or {"width": 1280, "height": 720}
        self.browser = None
        self.context = None
        self.playwright = None
        self.fetch_metadata_by_account: dict[str, FetchMetadata] = {}

    async def _ensure_browser(self):
        """Lazy initialize browser and context"""
        if self.browser is None:
            self.playwright = await self.async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            self.context = await self.browser.new_context(
                viewport=self.viewport,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

    async def reset_public_context(self):
        """Reset browser context for clean public access (batch retry between attempts)"""
        if self.context is not None:
            try:
                await self.context.close()
            except Exception as e:
                logger.warning(f"Error closing context: {e}")
            self.context = None

        # Re-create fresh context
        if self.browser is not None:
            self.context = await self.browser.new_context(
                viewport=self.viewport,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            logger.info("Public context reset for clean batch attempt")

    async def fetch_media(self, url: str) -> Optional[bytes]:
        """Fetch media using public browser context (fallback for 403 errors)"""
        if not self.context:
            return None

        try:
            response = await self.context.request.get(
                url,
                headers={
                    "Referer": "https://www.instagram.com/",
                }
            )

            if response.ok:
                body = await response.body()
                if body:
                    content_type = response.headers.get("content-type", "").lower()
                    if content_type.startswith("image/"):
                        logger.debug(f"Fetched media via browser context: {url[:50]}...")
                        return body
        except Exception as e:
            logger.debug(f"Error fetching media via browser: {e}")

        return None

    async def close(self):
        """Close browser, context, and playwright (idempotent)"""
        try:
            if self.context:
                await self.context.close()
                self.context = None
        except Exception as e:
            logger.debug(f"Error closing context: {e}")

        try:
            if self.browser:
                await self.browser.close()
                self.browser = None
        except Exception as e:
            logger.debug(f"Error closing browser: {e}")

        try:
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception as e:
            logger.debug(f"Error closing playwright: {e}")

        # Yield to event loop for cleanup
        import asyncio
        await asyncio.sleep(0)

    async def get_posts(
        self,
        account: str,
        limit: int | None = None,
        from_date = None,
        to_date = None,
    ) -> list[InstagramPost]:
        """
        Fetch posts from a public Instagram profile.

        Args:
            account: Instagram username
            limit: Maximum number of posts (for count mode)
            from_date: Start date (for date mode)
            to_date: End date (for date mode)

        Returns:
            List of InstagramPost objects

        Side effect:
            Stores FetchMetadata in self.fetch_metadata_by_account[account]
        """
        from datetime import date as date_type

        try:
            await self._ensure_browser()

            page = await self.context.new_page()
            try:
                # Navigate to profile
                profile_url = f"https://www.instagram.com/{account}/"
                logger.info(f"Navigating to {profile_url}")

                try:
                    await page.goto(profile_url, wait_until="domcontentloaded", timeout=10000)
                except Exception as e:
                    logger.error(f"Failed to navigate to profile: {e}")
                    raise InstagramProviderException(f"Could not access profile @{account}: {e}")

                # Extract post links based on mode (returns stop_reason, completed)
                is_date_mode = from_date is not None
                # Date mode: pass limit=None (no functional limit, only safety max_scrolls)
                # Count mode: pass actual limit
                extract_limit = None if is_date_mode else (limit or 20)
                post_links, stop_reason, completed = await self._extract_post_links(
                    page,
                    account=account,
                    limit=extract_limit,
                    from_date=from_date,
                    to_date=to_date,
                )

                # Map stop_reason to warning message
                warning = None
                if stop_reason == "public_access_limited":
                    warning = (
                        "Instagram limitó el acceso público antes de poder confirmar "
                        "todo el historial solicitado."
                    )
                elif stop_reason == "safety_limit":
                    warning = (
                        "El escaneo alcanzó el límite técnico de seguridad "
                        "antes de confirmar todo el período."
                    )
                elif stop_reason == "scroll_stalled":
                    warning = (
                        "Instagram dejó de entregar nuevas publicaciones "
                        "antes de confirmar todo el período solicitado."
                    )

                if not post_links:
                    logger.warning(f"No posts found for @{account}")
                    # Save metadata even for empty results
                    self.fetch_metadata_by_account[account] = FetchMetadata(
                        account=account,
                        discovered_links=0,
                        posts_with_date=0,
                        undated_posts=0,
                        completed=completed,
                        stop_reason=stop_reason,
                        warning=warning,
                    )
                    return []

                # Fetch post details and count posts with dates
                posts = []
                posts_with_date = 0
                undated_posts = 0

                for link in post_links:
                    try:
                        post = await self._fetch_post_details(page, link, account)
                        if post:
                            posts.append(post)
                            if post.published_at:
                                posts_with_date += 1
                            else:
                                undated_posts += 1
                    except Exception as e:
                        logger.warning(f"Failed to fetch post {link}: {e}")
                        continue

                # Count mode: sort by published_at DESC, then apply limit
                if not is_date_mode and limit:
                    posts.sort(key=lambda p: p.published_at, reverse=True)
                    posts = posts[:limit]

                # Date mode: filter by range (no arbitrary limit)
                if is_date_mode:
                    posts = [
                        p for p in posts
                        if from_date <= p.published_at.date() <= to_date
                    ]

                # Save metadata
                self.fetch_metadata_by_account[account] = FetchMetadata(
                    account=account,
                    discovered_links=len(post_links),
                    posts_with_date=posts_with_date,
                    undated_posts=undated_posts,
                    completed=completed,
                    stop_reason=stop_reason,
                    warning=warning,
                )

                logger.info(f"Successfully fetched {len(posts)} posts from @{account}")
                return posts

            finally:
                await page.close()

        except InstagramProviderException:
            raise
        except Exception as e:
            logger.error(f"Error fetching posts from @{account}: {e}")
            raise InstagramProviderException(f"Failed to fetch posts from @{account}: {e}")

    async def get_post(self, post_id: str) -> Optional[InstagramPost]:
        """Fetch a single post by shortcode"""
        try:
            await self._ensure_browser()

            page = await self.context.new_page()
            try:
                # Determine if reel or photo post
                post_url = f"https://www.instagram.com/p/{post_id}/"

                await page.goto(post_url, wait_until="domcontentloaded", timeout=10000)

                post = await self._extract_post_from_page(page, post_url)

                # Only report block if we couldn't extract post
                if not post:
                    is_blocked, reason = await self._check_for_blocks(page, has_posts=False)
                    if is_blocked:
                        raise InstagramProviderException(
                            f"Instagram blocking public post access ({reason})."
                        )

                return post

            finally:
                await page.close()

        except Exception as e:
            logger.warning(f"Could not fetch post {post_id}: {e}")
            return None

    async def _check_for_blocks(self, page, has_posts: bool = False) -> tuple[bool, str | None]:
        """
        Check if Instagram is blocking access.

        Returns:
            (is_blocked, reason)
            is_blocked=True if totally blocked and no posts
            reason='public_access_limited' if we have posts but hit a wall
        """
        current_url = page.url
        page_content = await page.content()

        # Check for challenge/checkpoint/login in URL
        is_challenge = any(
            path in current_url
            for path in ["/challenge/", "/checkpoint/", "/accounts/login/"]
        )

        if is_challenge:
            logger.warning(f"Challenge/checkpoint URL detected: {current_url}")
            if not has_posts:
                return (True, "challenge_detected")

        # Check for login wall modal
        try:
            login_modal = await page.query_selector(
                'button:has-text("Log in"), a:has-text("Log in"), '
                '[role="dialog"]:has-text("Log in")'
            )
            if login_modal:
                logger.warning("Login wall modal detected")
                if has_posts:
                    # We got some posts but now hit a wall
                    return (False, "public_access_limited")
                else:
                    # No posts AND login wall
                    return (True, "login_wall_no_posts")
        except Exception:
            pass

        return (False, None)

    async def _extract_post_links(
        self, page, account: str, limit: int | None, from_date=None, to_date=None
    ) -> tuple[list[str], str | None, bool]:
        """Extract post links from profile page with smart block detection.

        Returns:
            (post_links, stop_reason, completed)
            stop_reason: None, 'public_access_limited', 'safety_limit', 'scroll_stalled'
            completed: True only if we reached natural end of profile

        Logic:
            - Login modal alone does NOT stop scanning
            - Only stop if: login_modal_seen AND 10 empty scrolls AND height not growing
        """
        from datetime import date as date_type

        post_links = []
        seen_links = set()
        scroll_count = 0
        consecutive_scrolls_without_new = 0
        login_wall_seen = False
        stop_reason = None
        completed = False

        # Determine mode FIRST before any limit operations
        is_date_mode = from_date is not None

        # Safety limits: different for count vs date mode
        if is_date_mode:
            max_scrolls = 300  # High limit for date mode (not a data filter)
            max_empty_scrolls = 10  # Very high threshold - requires real stall
        else:
            # Count mode requires limit
            if limit is None:
                raise ValueError("limit is required for count mode")
            max_scrolls = max(limit + 20, 50)
            max_empty_scrolls = 3

        while scroll_count < max_scrolls:
            # Find all post links
            links = await page.eval_on_selector_all(
                'a[href*="/p/"], a[href*="/reel/"]',
                "elements => elements.map(el => el.href)"
            )

            new_links_found = False
            new_links_count = 0
            for link in links:
                if ("/p/" in link or "/reel/" in link) and link not in seen_links:
                    seen_links.add(link)
                    post_links.append(link)
                    new_links_found = True
                    new_links_count += 1

            # After discovering posts, check for access blocks
            if post_links:
                is_blocked, block_reason = await self._check_for_blocks(
                    page, has_posts=True
                )
                if is_blocked:
                    logger.error(f"Fatal block for @{account}: {block_reason}")
                    raise InstagramProviderException(
                        f"Instagram blocking public profile access ({block_reason})"
                    )
                elif block_reason == "public_access_limited":
                    # Modal/login visible BUT still getting posts - don't stop yet
                    logger.info(f"Login wall detected for @{account} but still discovering posts")
                    login_wall_seen = True

            # Count mode: stop when we have enough
            if not is_date_mode and limit is not None and len(post_links) >= limit:
                completed = True
                break

            # Date mode: continue until no new posts (don't stop on pinned old posts)
            if not new_links_found:
                consecutive_scrolls_without_new += 1
            else:
                consecutive_scrolls_without_new = 0

            # Only declare public_access_limited if:
            # 1. Login wall was seen
            # 2. AND we've hit the empty scroll threshold
            if login_wall_seen and consecutive_scrolls_without_new >= max_empty_scrolls:
                logger.warning(
                    f"Login wall + stall detected for @{account} after {len(post_links)} posts"
                )
                stop_reason = "public_access_limited"
                completed = False
                break

            # If no login wall but empty scrolls, it's natural stall
            if not login_wall_seen and consecutive_scrolls_without_new >= max_empty_scrolls:
                logger.info(f"Natural stall for @{account} after {max_empty_scrolls} empty scrolls")
                stop_reason = "scroll_stalled"
                completed = False
                break

            # Safety limit check
            if scroll_count >= max_scrolls - 1:
                logger.warning(f"Reached safety scroll limit {max_scrolls} for @{account}")
                stop_reason = "safety_limit"
                break

            # Scroll down with robust strategy
            try:
                current_scroll = scroll_count

                # Get scroll height before
                scroll_height_before = await page.evaluate("document.body.scrollHeight")

                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

                # Wait for content to load
                await page.wait_for_timeout(1500)

                # Check if more content loaded
                scroll_height_after = await page.evaluate("document.body.scrollHeight")

                # If height didn't change, try alternative scroll
                if scroll_height_after == scroll_height_before and not new_links_found:
                    logger.debug(f"Profile @{account} scroll {current_scroll}: height unchanged, trying wheel")
                    await page.mouse.wheel(0, 2500)
                    await page.wait_for_timeout(1500)

                # Log scroll progress with all details
                logger.info(
                    f"Profile @{account} scroll={current_scroll} "
                    f"discovered={len(post_links)} new={new_links_count} "
                    f"height_before={scroll_height_before} height_after={scroll_height_after} "
                    f"login_wall={login_wall_seen} consecutive_empty={consecutive_scrolls_without_new}"
                )

                scroll_count += 1
            except Exception as e:
                logger.error(f"Scroll error on @{account}: {e}")
                stop_reason = "scroll_error"
                break

        logger.info(
            f"Found {len(post_links)} post links after {scroll_count} scrolls, "
            f"login_wall_seen={login_wall_seen}, stop_reason={stop_reason}, completed={completed}"
        )
        return post_links, stop_reason, completed

    async def _get_oldest_post_date_from_links(self, page, post_links: list[str]):
        """Check oldest post date from current set of links"""
        from datetime import date as date_type

        if not post_links:
            return None

        # Sample last few links to determine oldest date
        sample_links = post_links[-min(3, len(post_links)):]
        oldest = None

        for link in sample_links:
            try:
                detail_page = await self.context.new_page()
                try:
                    await detail_page.goto(link, wait_until="domcontentloaded", timeout=5000)
                    page_content = await detail_page.content()
                    post_date = self._extract_publish_date(page_content)
                    if post_date:
                        post_date_only = post_date.date() if hasattr(post_date, 'date') else post_date
                        if oldest is None or post_date_only < oldest:
                            oldest = post_date_only
                finally:
                    await detail_page.close()
            except Exception as e:
                logger.debug(f"Error checking date for {link}: {e}")
                continue

        return oldest

    async def _fetch_post_details(self, page, post_url: str, username: str) -> Optional[InstagramPost]:
        """Fetch details for a single post"""
        try:
            # Navigate to post
            await page.goto(post_url, wait_until="domcontentloaded", timeout=10000)

            return await self._extract_post_from_page(page, post_url, username)

        except Exception as e:
            logger.warning(f"Could not fetch post details from {post_url}: {e}")
            return None

    async def _extract_post_from_page(
        self, page, post_url: str, username: str = None
    ) -> Optional[InstagramPost]:
        """Extract post data from loaded page"""
        try:
            # Extract shortcode from URL
            shortcode = self._extract_shortcode_from_url(post_url)
            if not shortcode:
                return None

            # Determine post type from URL
            is_reel = "/reel/" in post_url
            post_type = PostType.REEL if is_reel else PostType.PHOTO

            # Get page content for metadata extraction
            page_content = await page.content()

            # Extract metadata
            caption = self._extract_caption(page_content)
            published_at = self._extract_publish_date(page_content)
            thumbnail_url = self._extract_thumbnail_url(page_content)

            # Convert extracted date to Bogota timezone
            if published_at:
                published_at = to_bogota_time(published_at)

            # If username not provided, extract from URL
            if not username:
                username = self._extract_username_from_url(page_content, post_url)

            if not username:
                logger.warning(f"Could not determine username for {post_url}")
                return None

            # If date could not be extracted, return None
            # This will be handled by caller (skip in date mode, warn in count mode)
            if not published_at:
                logger.warning(f"Could not extract publish date for {post_url}")
                return None  # Skip posts without reliable date

            post = InstagramPost(
                shortcode=shortcode,
                username=username,
                caption=caption or "",
                post_type=post_type,
                published_at=published_at,
                permalink=post_url,
                thumbnail_url=thumbnail_url,
                is_video=is_reel,
                media_count=1,
            )

            return post

        except Exception as e:
            logger.warning(f"Error extracting post from page: {e}")
            return None

    @staticmethod
    def _extract_shortcode_from_url(url: str) -> Optional[str]:
        """Extract shortcode from Instagram URL"""
        match = re.search(r"/(?:p|reel)/([A-Za-z0-9_-]+)/", url)
        return match.group(1) if match else None

    @staticmethod
    def _extract_caption(page_content: str) -> Optional[str]:
        """Extract caption from page content"""
        # Try og:description
        match = re.search(r'<meta property="og:description" content="([^"]*)"', page_content)
        if match:
            caption = match.group(1)
            # Clean Instagram wrapper if present
            if " · " in caption and "www.instagram.com" in caption:
                caption = caption.split(" · ")[0].strip()
            return caption if caption else None

        return None

    @staticmethod
    def _extract_publish_date(page_content: str) -> Optional[datetime]:
        """Extract publish date from page content"""
        # Try article:published_time
        match = re.search(r'<meta property="article:published_time" content="([^"]*)"', page_content)
        if match:
            try:
                return datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
            except Exception:
                pass

        # Try time element
        match = re.search(r'<time[^>]*datetime="([^"]*)"', page_content)
        if match:
            try:
                return datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
            except Exception:
                pass

        return None

    @staticmethod
    def _extract_thumbnail_url(page_content: str) -> Optional[str]:
        """Extract thumbnail URL from page content"""
        # Try og:image
        match = re.search(r'<meta property="og:image" content="([^"]*)"', page_content)
        if match:
            url = match.group(1)
            # Decode HTML entities (&amp; → &, etc.)
            url = unescape(url)
            if url.startswith(("http://", "https://")):
                return url

        return None

    @staticmethod
    def _extract_username_from_url(page_content: str, post_url: str) -> Optional[str]:
        """Extract username from page or URL"""
        # Try @username in page
        match = re.search(r'profile_pic_url_hd":"https://[^"]*/([^/]+)/', page_content)
        if match:
            return match.group(1)

        # Fallback: extract from URL if it's a user's post
        # This is less reliable but better than nothing
        match = re.search(r"@([a-zA-Z0-9_.]+)", page_content)
        if match:
            return match.group(1)

        return None
