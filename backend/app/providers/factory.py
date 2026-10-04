"""Factory for creating Instagram providers based on environment"""
import os
import logging

from app.providers.instagram import InstagramProvider
from app.providers.browser_instagram import BrowserInstagramProvider
from app.providers.meta_instagram import MetaInstagramProvider
from app.domain.exceptions import InstagramProviderException

logger = logging.getLogger(__name__)


def create_instagram_provider(headless: bool = True) -> InstagramProvider:
    """
    Create Instagram provider based on environment variables.

    INSTAGRAM_PROVIDER env var controls selection:
    - "meta" -> MetaInstagramProvider
    - "browser" -> BrowserInstagramProvider
    - "auto" -> MetaInstagramProvider if credentials exist, else Browser

    Args:
        headless: Only used for BrowserInstagramProvider

    Returns:
        Configured InstagramProvider instance

    Raises:
        InstagramProviderException: If provider selection or config fails
    """
    provider_type = os.getenv("INSTAGRAM_PROVIDER", "auto").lower()

    logger.info(f"Creating Instagram provider: {provider_type}")

    if provider_type == "meta":
        # Meta explicitly requested - must have credentials
        access_token = os.getenv("META_ACCESS_TOKEN")
        ig_user_id = os.getenv("META_IG_USER_ID")

        if not access_token or not ig_user_id:
            raise InstagramProviderException(
                "Meta provider requested but META_ACCESS_TOKEN or META_IG_USER_ID not configured"
            )

        return MetaInstagramProvider(
            access_token=access_token,
            ig_user_id=ig_user_id,
        )

    elif provider_type == "browser":
        # Browser explicitly requested
        return BrowserInstagramProvider(headless=headless)

    elif provider_type == "auto":
        # Auto-select: prefer Meta if credentials exist
        access_token = os.getenv("META_ACCESS_TOKEN")
        ig_user_id = os.getenv("META_IG_USER_ID")

        if access_token and ig_user_id:
            logger.info("Auto-selecting Meta provider (credentials found)")
            return MetaInstagramProvider(
                access_token=access_token,
                ig_user_id=ig_user_id,
            )
        else:
            logger.info("Auto-selecting Browser provider (Meta credentials not found)")
            return BrowserInstagramProvider(headless=headless)

    else:
        raise InstagramProviderException(
            f"Unknown INSTAGRAM_PROVIDER: {provider_type}. "
            "Must be 'meta', 'browser', or 'auto'"
        )
