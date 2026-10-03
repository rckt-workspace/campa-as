"""Tests for PerceptualContentMatcher with real images"""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from app.domain.models import InstagramPost, PostType, MatchStatus
from app.domain.matcher import PerceptualContentMatcher
from app.domain.matcher_config import MatcherConfig
from tests.fixtures.create_test_images import create_test_images


@pytest.fixture
def test_images():
    """Create test images and return paths"""
    return create_test_images()


@pytest.fixture
def matcher():
    """Create a perceptual matcher with default config"""
    return PerceptualContentMatcher()


def test_same_image_is_found(test_images, matcher):
    """A vs A => FOUND"""
    post_a1 = InstagramPost(
        shortcode="A001",
        username="account_a",
        caption="Test image A",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A001/",
        thumbnail_url=test_images["image_a"],
        is_video=False,
    )

    post_a2 = InstagramPost(
        shortcode="A002",
        username="account_b",
        caption="Test image A",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A002/",
        thumbnail_url=test_images["image_a"],
        is_video=False,
    )

    result = matcher.match(post_a1, post_a2)

    assert result.status == MatchStatus.FOUND
    assert result.score >= 0.85
    assert result.visual_similarity is not None
    assert result.visual_similarity > 0.9


def test_resized_image_is_found(test_images, matcher):
    """A vs A_resized => FOUND"""
    post_a = InstagramPost(
        shortcode="A001",
        username="account_a",
        caption="Original",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A001/",
        thumbnail_url=test_images["image_a"],
        is_video=False,
    )

    post_resized = InstagramPost(
        shortcode="A002",
        username="account_b",
        caption="Original",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A002/",
        thumbnail_url=test_images["image_a2"],
        is_video=False,
    )

    result = matcher.match(post_a, post_resized)

    assert result.status == MatchStatus.FOUND
    assert result.score >= 0.85
    assert result.visual_similarity is not None
    assert result.visual_similarity > 0.8


def test_compressed_image_is_found(test_images, matcher):
    """A vs A_compressed => FOUND"""
    post_a = InstagramPost(
        shortcode="A001",
        username="account_a",
        caption="Quality check",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A001/",
        thumbnail_url=test_images["image_a"],
        is_video=False,
    )

    post_compressed = InstagramPost(
        shortcode="A003",
        username="account_b",
        caption="Quality check",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A003/",
        thumbnail_url=test_images["image_a3"],
        is_video=False,
    )

    result = matcher.match(post_a, post_compressed)

    assert result.status == MatchStatus.FOUND
    assert result.score >= 0.85


def test_different_image_with_same_caption_not_found(test_images, matcher):
    """A vs B + caption idéntico => NOT FOUND or REVIEW"""
    post_a = InstagramPost(
        shortcode="A001",
        username="account_a",
        caption="Same caption",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A001/",
        thumbnail_url=test_images["image_a"],
        is_video=False,
    )

    post_b = InstagramPost(
        shortcode="B001",
        username="account_b",
        caption="Same caption",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/B001/",
        thumbnail_url=test_images["image_b"],
        is_video=False,
    )

    result = matcher.match(post_a, post_b)

    # Visual is very different (red vs blue), but caption is identical
    # With caption_weight=0.20 and type_match=True, we might hit REVIEW zone
    assert result.status in [MatchStatus.REVIEW, MatchStatus.MISSING]
    assert result.visual_similarity is not None
    assert result.visual_similarity < 0.6


def test_different_image_similar_caption_may_review(test_images, matcher):
    """A vs C + caption parecido => high visual similarity may push to FOUND"""
    post_a = InstagramPost(
        shortcode="A001",
        username="account_a",
        caption="New Body special offer discount",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A001/",
        thumbnail_url=test_images["image_a"],
        is_video=False,
    )

    post_c = InstagramPost(
        shortcode="C001",
        username="account_b",
        caption="NewBody special promo sale",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/C001/",
        thumbnail_url=test_images["image_c"],
        is_video=False,
    )

    result = matcher.match(post_a, post_c)

    # Caption is similar, visual depends on image_a vs image_c
    # Either way, caption_similarity should be > 0.5
    assert result.caption_similarity > 0.5
    # Status may vary based on visual similarity
    assert result.status in [MatchStatus.FOUND, MatchStatus.REVIEW, MatchStatus.MISSING]


def test_ambiguous_content_review(test_images, matcher):
    """Ambiguous case => FOUND or REVIEW"""
    post_master = InstagramPost(
        shortcode="A001",
        username="account_a",
        caption="Beauty treatment promotion",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A001/",
        thumbnail_url=test_images["image_a"],
        is_video=False,
    )

    post_candidate = InstagramPost(
        shortcode="X001",
        username="account_b",
        caption="Beauty and wellness treatment",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 2),
        permalink="https://instagram.com/p/X001/",
        thumbnail_url=test_images["image_a2"],
        is_video=False,
    )

    result = matcher.match(post_master, post_candidate)

    # Similar visual + similar caption + date close = likely FOUND
    assert result.status in [MatchStatus.FOUND, MatchStatus.REVIEW]
    assert result.score >= 0.65


def test_completely_different_content_missing(test_images, matcher):
    """Completely different => MISSING"""
    post_a = InstagramPost(
        shortcode="A001",
        username="account_a",
        caption="One type of content",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A001/",
        thumbnail_url=test_images["image_a"],
        is_video=False,
    )

    post_b = InstagramPost(
        shortcode="B001",
        username="account_b",
        caption="Different content entirely",
        post_type=PostType.VIDEO,
        published_at=datetime(2026, 9, 15),
        permalink="https://instagram.com/p/B001/",
        thumbnail_url=test_images["image_b"],
        is_video=True,
    )

    result = matcher.match(post_a, post_b)

    assert result.status == MatchStatus.MISSING
    assert result.score < 0.65


def test_visual_unavailable_still_scores(matcher):
    """Visual unavailable => score valid without inventing 0.5"""
    post_a = InstagramPost(
        shortcode="A001",
        username="account_a",
        caption="Test with emoji 🎉",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A001/",
        thumbnail_url="https://example.com/nonexistent.jpg",
        is_video=False,
    )

    post_b = InstagramPost(
        shortcode="B001",
        username="account_b",
        caption="Test with emoji 🎉",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/B001/",
        thumbnail_url="https://example.com/also_nonexistent.jpg",
        is_video=False,
    )

    result = matcher.match(post_a, post_b)

    # Visual is None => maximum status is REVIEW (security: no visual evidence)
    assert result.visual_similarity is None
    assert result.caption_similarity > 0.9
    # Without visual signal, status is capped at REVIEW even if score is high
    assert result.status == MatchStatus.REVIEW
    assert result.score >= 0.65


def test_caption_with_emojis(test_images, matcher):
    """Caption with emojis is preserved and compared"""
    post_a = InstagramPost(
        shortcode="A001",
        username="account_a",
        caption="🎉 Special offer 🔥 only today!",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A001/",
        thumbnail_url=test_images["image_a"],
        is_video=False,
    )

    post_b = InstagramPost(
        shortcode="B001",
        username="account_b",
        caption="🎉 Special offer 🔥 only today!",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/B001/",
        thumbnail_url=test_images["image_a"],
        is_video=False,
    )

    result = matcher.match(post_a, post_b)

    assert result.caption_similarity > 0.9
    assert result.status == MatchStatus.FOUND


def test_caption_slightly_modified(matcher):
    """Slightly modified caption is still considered similar"""
    post_a = InstagramPost(
        shortcode="A001",
        username="account_a",
        caption="New Body at Medellin is amazing",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A001/",
        thumbnail_url="https://example.com/a.jpg",
        is_video=False,
    )

    post_b = InstagramPost(
        shortcode="B001",
        username="account_b",
        caption="NewBody in Medellin is so amazing",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/B001/",
        thumbnail_url="https://example.com/b.jpg",
        is_video=False,
    )

    result = matcher.match(post_a, post_b)

    # Captions are similar
    assert result.caption_similarity > 0.7


def test_date_similarity_calculation(matcher):
    """Date similarity degrades with distance"""
    post_master = InstagramPost(
        shortcode="A001",
        username="account_a",
        caption="Same content",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A001/",
        thumbnail_url="https://example.com/a.jpg",
        is_video=False,
    )

    # Same day
    post_same_day = InstagramPost(
        shortcode="B001",
        username="account_b",
        caption="Same content",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/B001/",
        thumbnail_url="https://example.com/a.jpg",
        is_video=False,
    )

    # 5 days later
    post_later = InstagramPost(
        shortcode="C001",
        username="account_b",
        caption="Same content",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 6),
        permalink="https://instagram.com/p/C001/",
        thumbnail_url="https://example.com/a.jpg",
        is_video=False,
    )

    result_same = matcher.match(post_master, post_same_day)
    result_later = matcher.match(post_master, post_later)

    assert result_same.date_similarity == 1.0
    assert result_later.date_similarity < 1.0
    assert result_same.score >= result_later.score


def test_weight_normalization_without_visual(matcher):
    """When visual is unavailable, weights are redistributed"""
    post_a = InstagramPost(
        shortcode="A001",
        username="account_a",
        caption="Test content",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A001/",
        thumbnail_url="https://nonexistent.invalid/a.jpg",
        is_video=False,
    )

    post_b = InstagramPost(
        shortcode="B001",
        username="account_b",
        caption="Test content",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/B001/",
        thumbnail_url="https://nonexistent.invalid/b.jpg",
        is_video=False,
    )

    result = matcher.match(post_a, post_b)

    # Visual unavailable (None)
    assert result.visual_similarity is None
    # Caption identical, type match, date match
    # Maximum status without visual is REVIEW (security rule)
    assert result.status == MatchStatus.REVIEW
    assert result.score >= 0.65


def test_no_visual_signal_never_returns_found(matcher):
    """SECURITY: Without visual evidence, status never FOUND even with high score"""
    post_master = InstagramPost(
        shortcode="A001",
        username="account_a",
        caption="Exclusive treatment at NewBody clinic",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/A001/",
        thumbnail_url="https://unreachable.invalid/image_a.jpg",
        is_video=False,
    )

    post_candidate = InstagramPost(
        shortcode="B001",
        username="account_b",
        caption="Exclusive treatment at NewBody clinic",
        post_type=PostType.PHOTO,
        published_at=datetime(2026, 9, 1),
        permalink="https://instagram.com/p/B001/",
        thumbnail_url="https://unreachable.invalid/image_b.jpg",
        is_video=False,
    )

    result = matcher.match(post_master, post_candidate)

    # All signals match but visual unavailable
    assert result.visual_similarity is None
    assert result.caption_similarity > 0.95
    assert result.type_match is True
    assert result.date_similarity == 1.0

    # Score redistributed is high
    assert result.score >= 0.85

    # BUT status must be REVIEW, NOT FOUND (security rule)
    assert result.status == MatchStatus.REVIEW
    assert result.status != MatchStatus.FOUND
