from dataclasses import dataclass, field
from datetime import datetime, date
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
class AccountMatchDetail:
    """Detailed match information for a post in a specific account"""
    status: MatchStatus
    score: float
    candidate_shortcode: Optional[str]
    candidate_permalink: Optional[str]
    visual_similarity: Optional[float]
    caption_similarity: float
    type_match: bool
    date_similarity: float = 0.0


@dataclass
class PostAuditStatus:
    """Status of a single post across accounts"""
    master_post: "InstagramPost"
    account_status: dict[str, str]
    account_matches: dict[str, AccountMatchDetail]
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


@dataclass
class FetchMetadata:
    """Metadata about how posts were fetched from an account"""
    account: str
    discovered_links: int
    posts_with_date: int
    undated_posts: int
    completed: bool
    stop_reason: str
    warning: Optional[str] = None


@dataclass
class AccountScanProgress:
    """Track progress of batch scanning for a single account"""
    account: str
    requested_from_date: Optional[date] = None
    requested_to_date: Optional[date] = None
    discovered_unique_shortcodes: set = field(default_factory=set)
    discovered_posts: list["InstagramPost"] = field(default_factory=list)
    batches_attempted: int = 0
    no_progress_attempts: int = 0
    total_unique_posts: int = 0
    min_date_found: Optional[date] = None
    max_date_found: Optional[date] = None
    completed: bool = False
    stop_reason: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
