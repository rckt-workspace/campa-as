from abc import ABC, abstractmethod
from typing import Optional

from app.domain.models import InstagramPost


class InstagramProvider(ABC):
    """Abstract interface for Instagram data access"""

    @abstractmethod
    async def get_posts(self, account: str) -> list[InstagramPost]:
        """Fetch posts from an Instagram account"""
        pass

    @abstractmethod
    async def get_post(self, post_id: str) -> Optional[InstagramPost]:
        """Fetch a single post by ID"""
        pass


class MockInstagramProvider(InstagramProvider):
    """Mock implementation for development and testing"""

    async def get_posts(self, account: str) -> list[InstagramPost]:
        return []

    async def get_post(self, post_id: str) -> Optional[InstagramPost]:
        return None
