from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


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
    account_status: dict[str, str]  # account -> "found" or "missing"
    missing_in: list[str]


@dataclass
class AuditResult:
    """Result of comparing posts across accounts"""
    master_account: str
    compared_accounts: list[str]
    posts_status: list[PostAuditStatus]
    total_master_posts: int
    found_in_all: int
    with_missing: int
    missing_count_by_account: dict[str, int]
    timestamp: datetime
