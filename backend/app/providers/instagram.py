from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path
import logging

from app.domain.models import InstagramPost, PostType
from app.domain.exceptions import (
    InstagramProviderException,
    TooManyRequestsException,
    LoginRequiredException,
    ProfileNotFoundException,
    PrivateProfileException,
    InvalidSessionException,
    ConnectionException,
)

logger = logging.getLogger(__name__)


class InstagramProvider(ABC):
    """Abstract interface for Instagram data access"""

    @property
    def supports_native_pagination(self) -> bool:
        """Whether provider can reliably handle pagination/date filtering internally"""
        return False

    @abstractmethod
    async def get_posts(
        self,
        account: str,
        limit: int | None = None,
        from_date = None,
        to_date = None,
    ) -> list[InstagramPost]:
        """Fetch posts from an Instagram account"""
        pass

    @abstractmethod
    async def get_post(self, post_id: str) -> Optional[InstagramPost]:
        """Fetch a single post by ID"""
        pass

    async def close(self):
        """Clean up resources (called at end of scan)"""
        pass


class MockInstagramProvider(InstagramProvider):
    """Mock implementation for development and testing"""

    async def get_posts(self, account: str, limit: int = 5) -> list[InstagramPost]:
        return []

    async def get_post(self, post_id: str) -> Optional[InstagramPost]:
        return None


class InstaloaderInstagramProvider(InstagramProvider):
    """Instagram provider using Instaloader library with optional session support"""

    def __init__(
        self,
        session_username: Optional[str] = None,
        session_file: Optional[Path] = None,
    ):
        try:
            import instaloader
            self.instaloader = instaloader
            self.loader = instaloader.Instaloader(
                quiet=True,
                max_connection_attempts=1,
                fatal_status_codes=[429],
            )
            self._session_username = session_username
            self._session_file = session_file

            if session_file and session_username:
                self._load_session()
        except ImportError:
            raise ImportError("Instaloader is required. Install with: pip install instaloader")

    def _load_session(self) -> None:
        """Load session from file and validate"""
        session_file_path = Path(self._session_file)
        if not session_file_path.exists():
            raise InvalidSessionException(f"Session file not found: {self._session_file}")

        try:
            self.loader.load_session_from_file(self._session_username, session_file_path)
            logged_user = self.loader.test_login()

            if logged_user is None:
                raise InvalidSessionException("Session is invalid or expired (test_login returned None)")

            if logged_user != self._session_username:
                logger.warning(
                    f"Session username mismatch: session file is for @{logged_user} "
                    f"but {self._session_username} was expected"
                )

            logger.info(f"Session loaded successfully for @{logged_user}")
        except InvalidSessionException:
            raise
        except Exception as e:
            logger.error(f"Failed to load or validate session: {e}")
            raise InvalidSessionException(f"Invalid or expired session: {e}")

    async def get_posts(self, account: str, limit: int = 5) -> list[InstagramPost]:
        """Fetch posts from an Instagram account"""
        try:
            profile = self.instaloader.Profile.from_username(self.loader.context, account)
            posts = []

            for post in profile.get_posts():
                if len(posts) >= limit:
                    break
                try:
                    instagram_post = self._transform_post(post, account)
                    posts.append(instagram_post)
                except Exception as e:
                    logger.warning(f"Error transforming post {post.shortcode}: {e}")
                    continue

            logger.info(f"Successfully fetched {len(posts)} posts from @{account}")
            return posts

        # Specific exceptions from Instaloader - ordered from specific to general
        except self.instaloader.exceptions.TooManyRequestsException:
            raise TooManyRequestsException("Instagram rate limit reached (HTTP 429). Please try again later.")
        except self.instaloader.exceptions.AbortDownloadException as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                raise TooManyRequestsException("Instagram rate limit reached (HTTP 429). Please try again later.")
            elif any(keyword in error_msg.lower() for keyword in ["challenge", "checkpoint", "feedback"]):
                raise InstagramProviderException(f"Instagram requires verification/interaction: {e}")
            else:
                raise InstagramProviderException(f"Download aborted: {e}")
        except self.instaloader.exceptions.ProfileNotExistsException:
            raise ProfileNotFoundException(f"Profile @{account} not found or inaccessible")
        except self.instaloader.exceptions.PrivateProfileNotFollowedException:
            raise PrivateProfileException(f"Cannot access private profile @{account}")
        except self.instaloader.exceptions.LoginRequiredException:
            raise LoginRequiredException(f"Authentication required to access @{account}")
        except self.instaloader.exceptions.ConnectionException as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                raise TooManyRequestsException("Instagram rate limit reached (HTTP 429). Please try again later.")
            else:
                raise ConnectionException(f"Connection error: {e}")
        except ConnectionError as e:
            raise ConnectionException(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Error fetching posts from @{account}: {type(e).__name__}: {e}")
            raise InstagramProviderException(f"Failed to fetch posts from @{account}: {e}")

    async def get_post(self, post_id: str) -> Optional[InstagramPost]:
        """Fetch a single post by shortcode"""
        try:
            post = self.instaloader.Post.from_shortcode(self.loader.context, post_id)
            return self._transform_post(post, post.owner_username)
        except self.instaloader.exceptions.TooManyRequestsException:
            raise TooManyRequestsException("Instagram rate limit reached (HTTP 429)")
        except self.instaloader.exceptions.AbortDownloadException as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                raise TooManyRequestsException("Instagram rate limit reached (HTTP 429)")
            logger.warning(f"Failed to fetch post {post_id}: {e}")
            return None
        except (self.instaloader.exceptions.QueryReturnedNotFoundException,
                self.instaloader.exceptions.ProfileNotExistsException):
            logger.warning(f"Post {post_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error fetching post {post_id}: {type(e).__name__}: {e}")
            return None

    def _transform_post(self, instaloader_post, account: str) -> InstagramPost:
        """Transform Instaloader Post object to domain InstagramPost"""
        post_type = self._determine_post_type(instaloader_post)
        permalink = self._generate_permalink(instaloader_post)

        return InstagramPost(
            shortcode=instaloader_post.shortcode,
            username=account,
            caption=instaloader_post.caption or "",
            post_type=post_type,
            published_at=instaloader_post.date,
            permalink=permalink,
            thumbnail_url=instaloader_post.display_url,
            is_video=instaloader_post.is_video,
            media_count=len(instaloader_post.get_sidecar_nodes()) if instaloader_post.is_carousel else 1,
        )

    def _determine_post_type(self, instaloader_post) -> PostType:
        """Determine post type from Instaloader post"""
        if instaloader_post.is_carousel:
            return PostType.CAROUSEL
        elif instaloader_post.is_video:
            return PostType.REEL if instaloader_post.is_reel else PostType.VIDEO
        else:
            return PostType.PHOTO

    def _generate_permalink(self, instaloader_post) -> str:
        """Generate Instagram permalink from post"""
        shortcode = instaloader_post.shortcode
        if instaloader_post.is_video and instaloader_post.is_reel:
            return f"https://www.instagram.com/reel/{shortcode}/"
        else:
            return f"https://www.instagram.com/p/{shortcode}/"
