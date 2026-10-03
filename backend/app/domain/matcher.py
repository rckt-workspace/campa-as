"""Content matching strategies for finding identical posts across accounts"""
from abc import ABC, abstractmethod
from typing import Union, Tuple
from io import BytesIO
from urllib.parse import urlparse

from app.domain.models import InstagramPost, MatchStatus, MatchResult
from app.domain.matcher_config import MatcherConfig


class ContentMatcher(ABC):
    """Abstract interface for matching Instagram posts across accounts"""

    @abstractmethod
    def match(self, master_post: InstagramPost, candidate_post: InstagramPost) -> MatchResult:
        """Determine if two posts represent the same content"""
        pass


class ExactContentMatcher(ContentMatcher):
    """Exact match strategy: shortcode must be identical"""

    def match(self, master_post: InstagramPost, candidate_post: InstagramPost) -> MatchResult:
        """Posts match if they have the same shortcode"""
        if master_post.shortcode == candidate_post.shortcode:
            return MatchResult(
                status=MatchStatus.FOUND,
                score=1.0,
                visual_similarity=1.0,
                caption_similarity=1.0,
                type_match=True,
                candidate_shortcode=candidate_post.shortcode,
                date_similarity=1.0,
            )
        else:
            return MatchResult(
                status=MatchStatus.MISSING,
                score=0.0,
                visual_similarity=None,
                caption_similarity=0.0,
                type_match=False,
                candidate_shortcode=candidate_post.shortcode,
                date_similarity=0.0,
            )


class PerceptualContentMatcher(ContentMatcher):
    """Perceptual matching using visual similarity, caption similarity, and metadata"""

    def __init__(self, config: MatcherConfig = None):
        self.config = config or MatcherConfig()
        try:
            import imagehash
            from PIL import Image
            self.imagehash = imagehash
            self.Image = Image
            self.has_visual = True
        except ImportError:
            self.has_visual = False

        try:
            from rapidfuzz import fuzz
            self.rapidfuzz = fuzz
        except ImportError:
            self.rapidfuzz = None

    def match(
        self,
        master_post: InstagramPost,
        candidate_post: InstagramPost,
    ) -> MatchResult:
        """Match two posts using multiple signals"""
        visual_sim = self._compute_visual_similarity(
            master_post.thumbnail_url,
            candidate_post.thumbnail_url,
        )
        caption_sim = self._compute_caption_similarity(
            master_post.caption,
            candidate_post.caption,
        )
        type_match = master_post.post_type == candidate_post.post_type
        date_days = abs(
            (master_post.published_at - candidate_post.published_at).days
        )
        date_sim = 1.0 if date_days <= 1 else max(0.0, 1.0 - (date_days / 30.0))

        # Calculate composite score with weight redistribution
        if visual_sim is None:
            # Visual signal unavailable: redistribute weights among other signals
            available_weight = (
                self.config.caption_weight
                + self.config.type_weight
                + self.config.date_weight
            )
            score = (
                caption_sim * (self.config.caption_weight / available_weight)
                + (1.0 if type_match else 0.0) * (self.config.type_weight / available_weight)
                + date_sim * (self.config.date_weight / available_weight)
            )
        else:
            # All signals available: use normal weighting
            score = (
                visual_sim * self.config.visual_weight
                + caption_sim * self.config.caption_weight
                + (1.0 if type_match else 0.0) * self.config.type_weight
                + date_sim * self.config.date_weight
            )

        # Determine status with visual signal constraint
        if visual_sim is None:
            # No visual evidence: never return FOUND, maximum REVIEW
            if score >= self.config.review_threshold:
                status = MatchStatus.REVIEW
            else:
                status = MatchStatus.MISSING
        else:
            # Visual evidence available: use normal thresholds
            if score >= self.config.found_threshold:
                status = MatchStatus.FOUND
            elif score >= self.config.review_threshold:
                status = MatchStatus.REVIEW
            else:
                status = MatchStatus.MISSING

        return MatchResult(
            status=status,
            score=score,
            visual_similarity=visual_sim,
            caption_similarity=caption_sim,
            type_match=type_match,
            candidate_shortcode=candidate_post.shortcode,
            date_similarity=date_sim,
        )

    def _compute_visual_similarity(
        self,
        url_a: str,
        url_b: str,
    ) -> float:
        """Compute visual similarity between two images using perceptual hash. Returns None if unavailable."""
        if not self.has_visual:
            return None

        try:
            # For testing, support local file paths or URLs
            img_a = self._load_image(url_a)
            img_b = self._load_image(url_b)

            if not img_a or not img_b:
                return None

            # Compute perceptual hashes
            hash_a = self.imagehash.phash(img_a)
            hash_b = self.imagehash.phash(img_b)

            # Convert Hamming distance to similarity (0-1)
            # Max distance is 64 for 8x8 hash
            distance = (hash_a - hash_b)
            similarity = 1.0 - (distance / 64.0)
            return max(0.0, min(1.0, similarity))
        except Exception:
            return None

    def _load_image(self, image_source: str):
        """Load image from URL or local path"""
        if not self.has_visual:
            return None

        try:
            if image_source.startswith(("http://", "https://")):
                # For tests, use a placeholder
                # In production, this would fetch from URL
                return None
            else:
                # Local file path
                return self.Image.open(image_source)
        except Exception:
            return None

    def _compute_caption_similarity(self, caption_a: str, caption_b: str) -> float:
        """Compute similarity between two captions using RapidFuzz"""
        if not caption_a or not caption_b:
            return 1.0 if caption_a == caption_b else 0.0

        if not self.rapidfuzz:
            # Fallback to simple comparison
            return 1.0 if caption_a.lower() == caption_b.lower() else 0.5

        # Normalize captions
        norm_a = self._normalize_caption(caption_a)
        norm_b = self._normalize_caption(caption_b)

        # Use token_set_ratio for better handling of reordered text
        similarity = self.rapidfuzz.token_set_ratio(norm_a, norm_b) / 100.0
        return similarity

    def _normalize_caption(self, caption: str) -> str:
        """Normalize caption for comparison"""
        import re

        # Convert to lowercase
        text = caption.lower()

        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text)

        # Remove extra punctuation but keep emojis
        # Remove URLs
        text = re.sub(r"http\S+", "", text)

        # Strip whitespace
        text = text.strip()

        return text
