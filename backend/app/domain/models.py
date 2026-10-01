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
    post_id: str
    account: str
    caption: str
    post_type: PostType
    published_at: datetime
    url: str
    media_count: int = 1


@dataclass
class AuditResult:
    """Result of comparing posts across accounts"""
    master_account: str
    compared_accounts: list[str]
    total_posts: int
    missing_posts: list[dict]
    timestamp: datetime
