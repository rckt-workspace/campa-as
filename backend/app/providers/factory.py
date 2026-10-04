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
    Create Instagram provider based on environment.

    INSTAGRAM_PROVIDER env var:
    - "meta" -> MetaInstagramProvider
    - "browser" -> BrowserInstagramProvider
    - not set -> BrowserInstagramProvider (default for backwards compatibility)

    Args:
        headless: Only used for BrowserInstagramProvider

    Returns:
        Configured InstagramProvider instance

    Raises:
        InstagramProviderException: If provider is misconfigured
    """
    provider_type = os.getenv("INSTAGRAM_PROVIDER", "browser").lower()

    logger.info(f"Creating Instagram provider: {provider_type}")

    if provider_type == "meta":
        try:
            return MetaInstagramProvider()
        except InstagramProviderException as e:
            logger.error(f"Failed to initialize Meta provider: {e}")
            raise
    elif provider_type == "browser":
        return BrowserInstagramProvider(headless=headless)
    else:
        raise InstagramProviderException(
            f"Unknown Instagram provider: {provider_type}. "
            "Must be 'meta' or 'browser'."
        )
