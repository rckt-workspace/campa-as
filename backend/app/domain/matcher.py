"""Content matching strategies for finding identical posts across accounts"""
from abc import ABC, abstractmethod
from app.domain.models import InstagramPost


class ContentMatcher(ABC):
    """Abstract interface for matching Instagram posts across accounts"""

    @abstractmethod
    def is_same_content(self, master_post: InstagramPost, candidate_post: InstagramPost) -> bool:
        """Determine if two posts represent the same content"""
        pass


class ExactContentMatcher(ContentMatcher):
    """Exact match strategy: shortcode must be identical"""

    def is_same_content(self, master_post: InstagramPost, candidate_post: InstagramPost) -> bool:
        """Posts match if they have the same shortcode"""
        return master_post.shortcode == candidate_post.shortcode
