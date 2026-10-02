"""Tests for AuditService and related functionality"""
import pytest
from datetime import datetime
from app.domain.models import InstagramPost, PostType
from app.domain.matcher import ExactContentMatcher
from app.services.audit_service import AuditService


@pytest.fixture
def sample_posts():
    """Create sample posts for testing"""
    return [
        InstagramPost(
            shortcode="POST001",
            username="master",
            caption="Post 1",
            post_type=PostType.PHOTO,
            published_at=datetime(2026, 9, 1),
            permalink="https://instagram.com/p/POST001/",
            thumbnail_url="https://example.com/001.jpg",
            is_video=False,
            media_count=1,
        ),
        InstagramPost(
            shortcode="POST002",
            username="master",
            caption="Post 2 with emoji 😀",
            post_type=PostType.VIDEO,
            published_at=datetime(2026, 9, 2),
            permalink="https://instagram.com/p/POST002/",
            thumbnail_url="https://example.com/002.jpg",
            is_video=True,
            media_count=1,
        ),
        InstagramPost(
            shortcode="POST003",
            username="master",
            caption="Post 3",
            post_type=PostType.CAROUSEL,
            published_at=datetime(2026, 9, 3),
            permalink="https://instagram.com/p/POST003/",
            thumbnail_url="https://example.com/003.jpg",
            is_video=False,
            media_count=3,
        ),
    ]


def test_post_found_everywhere(sample_posts):
    """Test post found in all accounts"""
    service = AuditService()

    account_posts = {
        "account_a": sample_posts[:1],
        "account_b": sample_posts[:1],
    }

    result = service.audit_accounts(sample_posts[:1], account_posts)

    assert result.total_master_posts == 1
    assert result.found_in_all == 1
    assert result.with_missing == 0
    assert result.posts_status[0].missing_in == []


def test_post_missing_in_one_account(sample_posts):
    """Test post missing in one account"""
    service = AuditService()

    account_posts = {
        "account_a": sample_posts[:2],
        "account_b": sample_posts[:1],
    }

    result = service.audit_accounts(sample_posts[:2], account_posts)

    assert result.total_master_posts == 2
    assert result.found_in_all == 1
    assert result.with_missing == 1
    assert result.missing_count_by_account["account_b"] == 1
    assert result.posts_status[1].missing_in == ["account_b"]


def test_post_missing_in_multiple_accounts(sample_posts):
    """Test post missing in multiple accounts"""
    service = AuditService()

    account_posts = {
        "account_a": sample_posts[:2],
        "account_b": sample_posts[:1],
        "account_c": sample_posts[:1],
    }

    result = service.audit_accounts(sample_posts[:2], account_posts)

    assert result.total_master_posts == 2
    assert result.found_in_all == 1
    assert result.with_missing == 1
    assert result.missing_count_by_account["account_b"] == 1
    assert result.missing_count_by_account["account_c"] == 1


def test_post_missing_in_all_accounts(sample_posts):
    """Test post missing in all accounts"""
    service = AuditService()

    account_posts = {
        "account_a": [],
        "account_b": [],
    }

    result = service.audit_accounts(sample_posts[:1], account_posts)

    assert result.total_master_posts == 1
    assert result.found_in_all == 0
    assert result.with_missing == 1
    assert result.missing_count_by_account["account_a"] == 1
    assert result.missing_count_by_account["account_b"] == 1
    assert result.posts_status[0].missing_in == ["account_a", "account_b"]


def test_metrics_calculation(sample_posts):
    """Test metrics calculation"""
    service = AuditService()

    account_posts = {
        "account_a": sample_posts[:2],  # Has POST001, POST002
        "account_b": sample_posts[1:],  # Has POST002, POST003
    }

    result = service.audit_accounts(sample_posts, account_posts)

    # POST001: found in account_a, missing in account_b
    # POST002: found in both
    # POST003: missing in account_a, found in account_b

    assert result.total_master_posts == 3
    assert result.found_in_all == 1  # Only POST002
    assert result.with_missing == 2  # POST001 and POST003
    assert result.missing_count_by_account["account_a"] == 1  # POST003
    assert result.missing_count_by_account["account_b"] == 1  # POST001


def test_exact_content_matcher():
    """Test ExactContentMatcher"""
    matcher = ExactContentMatcher()

    post1 = InstagramPost(
        shortcode="ABC123",
        username="account_a",
        caption="Test",
        post_type=PostType.PHOTO,
        published_at=datetime.now(),
        permalink="https://instagram.com/p/ABC123/",
        is_video=False,
    )

    post2 = InstagramPost(
        shortcode="ABC123",
        username="account_b",
        caption="Different caption",
        post_type=PostType.VIDEO,
        published_at=datetime.now(),
        permalink="https://instagram.com/p/ABC123/",
        is_video=True,
    )

    post3 = InstagramPost(
        shortcode="XYZ789",
        username="account_a",
        caption="Test",
        post_type=PostType.PHOTO,
        published_at=datetime.now(),
        permalink="https://instagram.com/p/XYZ789/",
        is_video=False,
    )

    from app.domain.models import MatchStatus
    result1 = matcher.match(post1, post2)
    assert result1.status == MatchStatus.FOUND

    result2 = matcher.match(post1, post3)
    assert result2.status == MatchStatus.MISSING


def test_audit_preserves_unicode(sample_posts):
    """Test that audit preserves unicode and emojis"""
    service = AuditService()

    account_posts = {
        "account_a": sample_posts[1:2],  # POST002 with emoji
    }

    result = service.audit_accounts(sample_posts[1:2], account_posts)

    assert "😀" in result.posts_status[0].master_post.caption
