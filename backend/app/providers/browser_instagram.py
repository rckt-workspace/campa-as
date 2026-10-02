"""Instagram provider using Playwright to access public content"""
import logging
import re
from datetime import datetime
from html import unescape
from typing import Optional
from urllib.parse import urlparse

from app.domain.models import InstagramPost, PostType
from app.domain.exceptions import (
    InstagramProviderException,
    ProfileNotFoundException,
    PrivateProfileException,
)

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

    async def get_posts(self, account: str, limit: int = 5) -> list[InstagramPost]:
        """
        Fetch posts from a public Instagram profile.

        Args:
            account: Instagram username
            limit: Maximum number of posts to fetch

        Returns:
            List of InstagramPost objects
        """
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

                # Extract post links
                post_links = await self._extract_post_links(page, limit)

                # Check for access blocks AFTER checking for posts
                if await self._check_for_blocks(page, has_posts=len(post_links) > 0):
                    raise InstagramProviderException(
                        "Instagram blocking public profile access. "
                        "Try again later or use --headed to debug."
                    )

                if not post_links:
                    logger.warning(f"No posts found for @{account}")
                    return []

                # Fetch post details
                posts = []
                for link in post_links[:limit]:
                    try:
                        post = await self._fetch_post_details(page, link, account)
                        if post:
                            posts.append(post)
                    except Exception as e:
                        logger.warning(f"Failed to fetch post {link}: {e}")
                        continue

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
                    if await self._check_for_blocks(page, has_posts=False):
                        raise InstagramProviderException(
                            "Instagram blocking public post access."
                        )

                return post

            finally:
                await page.close()

        except Exception as e:
            logger.warning(f"Could not fetch post {post_id}: {e}")
            return None

    async def _check_for_blocks(self, page, has_posts: bool = False) -> bool:
        """
        Check if Instagram is truly blocking access.

        Only return True if:
        1. URL indicates challenge/checkpoint/login redirect
        2. AND no public posts are visible

        Returns:
            True if access is blocked, False otherwise
        """
        current_url = page.url

        # Check for challenge/checkpoint in URL
        if any(path in current_url for path in ["/challenge/", "/checkpoint/", "/accounts/login/"]):
            logger.warning(f"Challenge/checkpoint URL detected: {current_url}")
            if not has_posts:
                return True

        # If we have posts, we're not blocked regardless of navbar text
        if has_posts:
            return False

        # Check for login wall modal without posts
        page_content = await page.content()

        # Look for actual modal/overlay elements, not just text in scripts
        try:
            # Try to find login button or modal
            login_modal = await page.query_selector(
                'button:has-text("Log in"), a:has-text("Log in"), '
                '[role="dialog"]:has-text("Log in")'
            )

            if login_modal and not has_posts:
                logger.warning("Login wall detected without public posts")
                return True
        except Exception:
            pass

        return False

    async def _extract_post_links(self, page, limit: int) -> list[str]:
        """Extract post links from profile page"""
        post_links = set()
        scroll_count = 0
        max_scrolls = limit + 10

        while len(post_links) < limit and scroll_count < max_scrolls:
            # Find all post links
            links = await page.eval_on_selector_all(
                'a[href*="/p/"], a[href*="/reel/"]',
                "elements => elements.map(el => el.href)"
            )

            for link in links:
                if "/p/" in link or "/reel/" in link:
                    post_links.add(link)

            if len(post_links) >= limit:
                break

            # Scroll down
            try:
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await page.wait_for_timeout(500)
                scroll_count += 1
            except Exception as e:
                logger.debug(f"Scroll error: {e}")
                break

        logger.debug(f"Found {len(post_links)} post links after {scroll_count} scrolls")
        return list(post_links)

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

            # If username not provided, extract from URL
            if not username:
                username = self._extract_username_from_url(page_content, post_url)

            if not username:
                logger.warning(f"Could not determine username for {post_url}")
                return None

            post = InstagramPost(
                shortcode=shortcode,
                username=username,
                caption=caption or "",
                post_type=post_type,
                published_at=published_at or datetime.now(),
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
