from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class MatchStatus(str, Enum):
    FOUND = "found"
    REVIEW = "review"
    MISSING = "missing"


class PostType(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"
    CAROUSEL = "carousel"
    REEL = "reel"
    STORY = "story"


@dataclass
class InstagramPost:
    """Represents an Instagram post"""
    shortcode: str
    username: str
    caption: str
    post_type: PostType
    published_at: datetime
    permalink: str
    thumbnail_url: Optional[str] = None
    is_video: bool = False
    media_count: int = 1


@dataclass
class PostAuditStatus:
    """Status of a single post across accounts"""
    master_post: "InstagramPost"
    account_status: dict[str, str]  # account -> "found", "review", or "missing"
    missing_in: list[str]
    review_in: list[str]


@dataclass
class MatchResult:
    """Result of comparing two posts for content matching"""
    status: MatchStatus
    score: float
    visual_similarity: Optional[float]
    caption_similarity: float
    type_match: bool
    candidate_shortcode: str
    date_similarity: float = 0.0


@dataclass
class AuditResult:
    """Result of comparing posts across accounts"""
    master_account: str
    compared_accounts: list[str]
    posts_status: list[PostAuditStatus]
    total_master_posts: int
    found_in_all: int
    with_missing: int
    with_review: int
    missing_count_by_account: dict[str, int]
    review_count_by_account: dict[str, int]
    timestamp: datetime
