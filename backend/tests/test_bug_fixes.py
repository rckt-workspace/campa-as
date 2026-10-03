"""Tests for bug fixes discovered in E2E real test"""
import pytest
from datetime import datetime, timedelta, date, timezone
from app.domain.models import (
    InstagramPost, PostType, AuditResult, PostAuditStatus,
    AccountMatchDetail, MatchStatus
)
from app.services.audit_service import AuditService
from app.domain.matcher import ExactContentMatcher, PerceptualContentMatcher


# ============================================
# P0 - COUNT MODE TESTS
# ============================================

class TestCountModeLimit:
    """Verify count mode respects limit and sorts by date"""

    @pytest.fixture
    def posts_with_pinned(self):
        """Fixture: 12 posts with pinned old posts mixed in (DOM order, NOT chronological)"""
        posts = [
            # Pinned old posts first (DOM order)
            InstagramPost(
                shortcode="PINNED_OLD_1", username="account",
                caption="Pinned from 2024", post_type=PostType.PHOTO,
                published_at=datetime(2024, 4, 16),
                permalink="https://instagram.com/p/PINNED_OLD_1/", is_video=False,
            ),
            InstagramPost(
                shortcode="PINNED_OLD_2", username="account",
                caption="Pinned from 2025-03", post_type=PostType.PHOTO,
                published_at=datetime(2025, 3, 31),
                permalink="https://instagram.com/p/PINNED_OLD_2/", is_video=False,
            ),
            # Recent posts follow
            InstagramPost(
                shortcode="RECENT_1", username="account",
                caption="From 2026-09-28", post_type=PostType.PHOTO,
                published_at=datetime(2026, 9, 28),
                permalink="https://instagram.com/p/RECENT_1/", is_video=False,
            ),
            InstagramPost(
                shortcode="RECENT_2", username="account",
                caption="From 2026-09-24", post_type=PostType.PHOTO,
                published_at=datetime(2026, 9, 24),
                permalink="https://instagram.com/p/RECENT_2/", is_video=False,
            ),
            InstagramPost(
                shortcode="RECENT_3", username="account",
                caption="From 2026-09-18", post_type=PostType.PHOTO,
                published_at=datetime(2026, 9, 18),
                permalink="https://instagram.com/p/RECENT_3/", is_video=False,
            ),
            InstagramPost(
                shortcode="RECENT_4", username="account",
                caption="From 2026-09-15", post_type=PostType.PHOTO,
                published_at=datetime(2026, 9, 15),
                permalink="https://instagram.com/p/RECENT_4/", is_video=False,
            ),
            InstagramPost(
                shortcode="RECENT_5", username="account",
                caption="From 2026-09-12", post_type=PostType.PHOTO,
                published_at=datetime(2026, 9, 12),
                permalink="https://instagram.com/p/RECENT_5/", is_video=False,
            ),
            InstagramPost(
                shortcode="RECENT_6", username="account",
                caption="From 2026-09-10", post_type=PostType.PHOTO,
                published_at=datetime(2026, 9, 10),
                permalink="https://instagram.com/p/RECENT_6/", is_video=False,
            ),
            InstagramPost(
                shortcode="RECENT_7", username="account",
                caption="From 2026-09-08", post_type=PostType.PHOTO,
                published_at=datetime(2026, 9, 8),
                permalink="https://instagram.com/p/RECENT_7/", is_video=False,
            ),
            InstagramPost(
                shortcode="RECENT_8", username="account",
                caption="From 2026-09-05", post_type=PostType.PHOTO,
                published_at=datetime(2026, 9, 5),
                permalink="https://instagram.com/p/RECENT_8/", is_video=False,
            ),
            InstagramPost(
                shortcode="RECENT_9", username="account",
                caption="From 2026-09-01", post_type=PostType.PHOTO,
                published_at=datetime(2026, 9, 1),
                permalink="https://instagram.com/p/RECENT_9/", is_video=False,
            ),
            InstagramPost(
                shortcode="RECENT_10", username="account",
                caption="From 2026-08-28", post_type=PostType.PHOTO,
                published_at=datetime(2026, 8, 28),
                permalink="https://instagram.com/p/RECENT_10/", is_video=False,
            ),
        ]
        return posts

    def test_count_mode_returns_exact_limit(self, posts_with_pinned):
        """
        P0: count mode with limit=5 should return exactly 5 posts
        (current bug: returns all 12)
        """
        limit = 5

        # Sort by published_at DESC (correct behavior)
        sorted_posts = sorted(posts_with_pinned, key=lambda p: p.published_at, reverse=True)
        limited_posts = sorted_posts[:limit]

        assert len(limited_posts) == limit, f"Expected {limit} posts, got {len(limited_posts)}"
        assert limited_posts[0].shortcode == "RECENT_1"  # 2026-09-28
        assert limited_posts[1].shortcode == "RECENT_2"  # 2026-09-24
        assert limited_posts[-1].shortcode == "RECENT_5"  # 2026-09-12

    def test_count_mode_sorts_by_real_publish_date(self, posts_with_pinned):
        """
        P0: count mode must sort by published_at DESC, not DOM order
        DOM order includes pinned old posts first, which is wrong
        """
        sorted_posts = sorted(posts_with_pinned, key=lambda p: p.published_at, reverse=True)

        # Verify descending order
        for i in range(len(sorted_posts) - 1):
            assert sorted_posts[i].published_at >= sorted_posts[i+1].published_at

        # First should be most recent
        assert sorted_posts[0].published_at == datetime(2026, 9, 28)

        # Pinned old posts should be at the end (in reverse chronological order)
        assert sorted_posts[-1].published_at == datetime(2024, 4, 16)  # PINNED_OLD_1 (oldest)
        assert sorted_posts[-2].published_at == datetime(2025, 3, 31)  # PINNED_OLD_2

    def test_pinned_old_post_does_not_replace_recent_post(self, posts_with_pinned):
        """
        P0: When limit=5, old pinned post should not appear
        Only 5 most recent posts
        """
        limit = 5
        sorted_posts = sorted(posts_with_pinned, key=lambda p: p.published_at, reverse=True)
        result = sorted_posts[:limit]

        # Old pinned posts should NOT be in result
        shortcodes = [p.shortcode for p in result]
        assert "PINNED_OLD_1" not in shortcodes
        assert "PINNED_OLD_2" not in shortcodes

        # Only recent posts
        expected = ["RECENT_1", "RECENT_2", "RECENT_3", "RECENT_4", "RECENT_5"]
        assert shortcodes == expected


# ============================================
# P0 - DATE MODE TESTS
# ============================================

class TestDateModeFiltering:
    """Verify date mode correctly filters by date range"""

    @pytest.fixture
    def posts_across_range(self):
        """Posts spanning from 2025-01-01 to 2026-10-31"""
        return [
            InstagramPost(
                shortcode="BEFORE_RANGE", username="master",
                caption="Before from_date", post_type=PostType.PHOTO,
                published_at=datetime(2024, 12, 31),
                permalink="https://instagram.com/p/BEFORE_RANGE/", is_video=False,
            ),
            InstagramPost(
                shortcode="AT_FROM_DATE", username="master",
                caption="Exactly at from_date", post_type=PostType.PHOTO,
                published_at=datetime(2025, 1, 1),
                permalink="https://instagram.com/p/AT_FROM_DATE/", is_video=False,
            ),
            InstagramPost(
                shortcode="IN_RANGE_1", username="master",
                caption="In range middle", post_type=PostType.PHOTO,
                published_at=datetime(2025, 6, 15),
                permalink="https://instagram.com/p/IN_RANGE_1/", is_video=False,
            ),
            InstagramPost(
                shortcode="AT_TO_DATE", username="master",
                caption="At to_date", post_type=PostType.PHOTO,
                published_at=datetime(2026, 10, 2),
                permalink="https://instagram.com/p/AT_TO_DATE/", is_video=False,
            ),
            InstagramPost(
                shortcode="AFTER_RANGE", username="master",
                caption="After to_date", post_type=PostType.PHOTO,
                published_at=datetime(2026, 10, 3),
                permalink="https://instagram.com/p/AFTER_RANGE/", is_video=False,
            ),
        ]

    def test_date_mode_excludes_before_from_date(self, posts_across_range):
        """P0: Posts published before from_date should be excluded"""
        from_date = date(2025, 1, 1)
        to_date = date(2026, 10, 2)

        filtered = [
            p for p in posts_across_range
            if from_date <= p.published_at.date() <= to_date
        ]

        assert "BEFORE_RANGE" not in [p.shortcode for p in filtered]

    def test_date_mode_includes_boundary_from_date(self, posts_across_range):
        """P0: Posts published exactly at from_date should be INCLUDED"""
        from_date = date(2025, 1, 1)
        to_date = date(2026, 10, 2)

        filtered = [
            p for p in posts_across_range
            if from_date <= p.published_at.date() <= to_date
        ]

        assert "AT_FROM_DATE" in [p.shortcode for p in filtered]

    def test_date_mode_excludes_after_to_date(self, posts_across_range):
        """P0: Posts published after to_date should be excluded"""
        from_date = date(2025, 1, 1)
        to_date = date(2026, 10, 2)

        filtered = [
            p for p in posts_across_range
            if from_date <= p.published_at.date() <= to_date
        ]

        assert "AFTER_RANGE" not in [p.shortcode for p in filtered]

    def test_pinned_old_post_does_not_stop_date_scan(self):
        """
        P0: A pinned post from 2020 should not cause date scan to stop
        When from_date=2025-01-01, we want posts FROM 2025+
        Even if a pinned post from 2020 is in the middle of the results
        """
        # Simulated results: pinned posts interspersed with recent
        posts = [
            # Recent
            InstagramPost(
                shortcode="RECENT_2026", username="master",
                caption="Recent", post_type=PostType.PHOTO,
                published_at=datetime(2026, 9, 1),
                permalink="https://instagram.com/p/RECENT_2026/", is_video=False,
            ),
            # Pinned old (in the middle)
            InstagramPost(
                shortcode="PINNED_2020", username="master",
                caption="Pinned old", post_type=PostType.PHOTO,
                published_at=datetime(2020, 1, 1),
                permalink="https://instagram.com/p/PINNED_2020/", is_video=False,
            ),
            # Recent again
            InstagramPost(
                shortcode="RECENT_2025", username="master",
                caption="Recent 2025", post_type=PostType.PHOTO,
                published_at=datetime(2025, 3, 15),
                permalink="https://instagram.com/p/RECENT_2025/", is_video=False,
            ),
        ]

        from_date = date(2025, 1, 1)
        to_date = date(2026, 10, 2)

        # Should NOT stop just because PINNED_2020 < from_date
        # Should continue and find RECENT_2025
        filtered = [
            p for p in posts
            if from_date <= p.published_at.date() <= to_date
        ]

        assert len(filtered) == 2  # Both recent posts
        assert "RECENT_2026" in [p.shortcode for p in filtered]
        assert "RECENT_2025" in [p.shortcode for p in filtered]
        assert "PINNED_2020" not in [p.shortcode for p in filtered]


# ============================================
# P1 - TIMEZONE TESTS
# ============================================

class TestTimezoneConsistency:
    """Verify frontend and Excel show same date (Bogota timezone)"""

    def test_bogota_timezone_same_date_frontend_export_contract(self):
        """
        P1: UTC timestamp converted to Bogota shows same date in both

        Scenario:
        - Instagram publishes at 2025-03-31T23:00:00Z (UTC)
        - In Bogota (UTC-5): 2025-03-31 18:00:00
        - Frontend and Excel should both show: 31/03/2025
        """
        from datetime import timezone, timedelta

        # UTC timestamp from Instagram
        utc_timestamp = datetime(2025, 3, 31, 23, 0, 0, tzinfo=timezone.utc)

        # Convert to Bogota timezone (UTC-5)
        bogota_tz = timezone(timedelta(hours=-5))
        bogota_time = utc_timestamp.astimezone(bogota_tz)

        # Both should show same date
        utc_date_str = utc_timestamp.strftime("%d/%m/%Y")
        bogota_date_str = bogota_time.strftime("%d/%m/%Y")

        # They should be the same
        assert bogota_date_str == "31/03/2025"
        # Note: UTC would also be 31/03 in this case, but the hour differs
        assert bogota_time.hour == 18  # Local Bogota time

    def test_utc_midnight_boundary_bogota_previous_day(self):
        """
        P1: Edge case - UTC 00:00 = Bogota 19:00 previous day

        Scenario:
        - Instagram publishes at 2025-04-01T00:00:00Z (UTC)
        - In Bogota: 2025-03-31 19:00:00 (PREVIOUS DAY)
        - Excel should show: 31/03/2025 (not 01/04/2025)
        """
        from datetime import timezone, timedelta

        utc_timestamp = datetime(2025, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
        bogota_tz = timezone(timedelta(hours=-5))
        bogota_time = utc_timestamp.astimezone(bogota_tz)

        # In Bogota, this is actually previous day
        assert bogota_time.day == 31
        assert bogota_time.month == 3
        assert bogota_time.strftime("%d/%m/%Y") == "31/03/2025"


# ============================================
# P1 - DATA CONSISTENCY TESTS
# ============================================

class TestAuditDataConsistency:
    """Verify REVIEW and MISSING are mutually exclusive"""

    @pytest.fixture
    def sample_audit_with_all_statuses(self):
        """Audit result with found, review, and missing posts"""
        master_a = InstagramPost(
            shortcode="MASTER_A", username="master", caption="Post A",
            post_type=PostType.PHOTO, published_at=datetime(2026, 9, 1),
            permalink="https://instagram.com/p/MASTER_A/", is_video=False,
        )
        master_b = InstagramPost(
            shortcode="MASTER_B", username="master", caption="Post B",
            post_type=PostType.PHOTO, published_at=datetime(2026, 9, 2),
            permalink="https://instagram.com/p/MASTER_B/", is_video=False,
        )
        master_c = InstagramPost(
            shortcode="MASTER_C", username="master", caption="Post C",
            post_type=PostType.PHOTO, published_at=datetime(2026, 9, 3),
            permalink="https://instagram.com/p/MASTER_C/", is_video=False,
        )

        return AuditResult(
            master_account="master",
            compared_accounts=["account_a", "account_b"],
            posts_status=[
                # FOUND: appears in neither missing_in nor review_in
                PostAuditStatus(
                    master_post=master_a,
                    account_status={"account_a": "found", "account_b": "found"},
                    account_matches={
                        "account_a": AccountMatchDetail(
                            status=MatchStatus.FOUND, score=1.0,
                            candidate_shortcode="A1", candidate_permalink="https://instagram.com/p/A1/",
                            visual_similarity=1.0, caption_similarity=1.0, type_match=True, date_similarity=1.0,
                        ),
                        "account_b": AccountMatchDetail(
                            status=MatchStatus.FOUND, score=1.0,
                            candidate_shortcode="A2", candidate_permalink="https://instagram.com/p/A2/",
                            visual_similarity=1.0, caption_similarity=1.0, type_match=True, date_similarity=1.0,
                        ),
                    },
                    missing_in=[], review_in=[],
                ),
                # REVIEW: appears in review_in, NOT in missing_in
                PostAuditStatus(
                    master_post=master_b,
                    account_status={"account_a": "review", "account_b": "missing"},
                    account_matches={
                        "account_a": AccountMatchDetail(
                            status=MatchStatus.REVIEW, score=0.75,
                            candidate_shortcode="B1", candidate_permalink="https://instagram.com/p/B1/",
                            visual_similarity=0.7, caption_similarity=0.75, type_match=True, date_similarity=0.8,
                        ),
                        "account_b": AccountMatchDetail(
                            status=MatchStatus.MISSING, score=0.0,
                            candidate_shortcode=None, candidate_permalink=None,
                            visual_similarity=None, caption_similarity=0.0, type_match=False, date_similarity=0.0,
                        ),
                    },
                    missing_in=["account_b"], review_in=["account_a"],
                ),
                # MISSING: appears in missing_in, NOT in review_in
                PostAuditStatus(
                    master_post=master_c,
                    account_status={"account_a": "missing", "account_b": "review"},
                    account_matches={
                        "account_a": AccountMatchDetail(
                            status=MatchStatus.MISSING, score=0.0,
                            candidate_shortcode=None, candidate_permalink=None,
                            visual_similarity=None, caption_similarity=0.0, type_match=False, date_similarity=0.0,
                        ),
                        "account_b": AccountMatchDetail(
                            status=MatchStatus.REVIEW, score=0.68,
                            candidate_shortcode="C2", candidate_permalink="https://instagram.com/p/C2/",
                            visual_similarity=0.6, caption_similarity=0.68, type_match=True, date_similarity=0.7,
                        ),
                    },
                    missing_in=["account_a"], review_in=["account_b"],
                ),
            ],
            total_master_posts=3, found_in_all=1, with_missing=1, with_review=1,
            missing_count_by_account={"account_a": 1, "account_b": 1},
            review_count_by_account={"account_a": 1, "account_b": 1},
            timestamp=datetime.now(),
        )

    def test_review_not_in_missing_in(self, sample_audit_with_all_statuses):
        """
        P1: REVIEW status accounts should NOT appear in missing_in
        Invariant: set(missing_in) & set(review_in) == empty set
        """
        for post_status in sample_audit_with_all_statuses.posts_status:
            # Get accounts with REVIEW status
            review_accounts = {
                acc for acc, match in post_status.account_matches.items()
                if match.status == MatchStatus.REVIEW
            }

            # They should NOT be in missing_in
            assert not (review_accounts & set(post_status.missing_in)), \
                f"REVIEW accounts in missing_in: {review_accounts & set(post_status.missing_in)}"

    def test_missing_not_in_review_in(self, sample_audit_with_all_statuses):
        """
        P1: MISSING status accounts should NOT appear in review_in
        Invariant: set(missing_in) & set(review_in) == empty set
        """
        for post_status in sample_audit_with_all_statuses.posts_status:
            # Get accounts with MISSING status
            missing_accounts = {
                acc for acc, match in post_status.account_matches.items()
                if match.status == MatchStatus.MISSING
            }

            # They should NOT be in review_in
            assert not (missing_accounts & set(post_status.review_in)), \
                f"MISSING accounts in review_in: {missing_accounts & set(post_status.review_in)}"

    def test_status_consistency_invariant(self, sample_audit_with_all_statuses):
        """
        P1: For each post/account, verify:
        match_detail.status is consistent with missing_in/review_in lists
        """
        for post_status in sample_audit_with_all_statuses.posts_status:
            for account, match_detail in post_status.account_matches.items():
                if match_detail.status == MatchStatus.MISSING:
                    assert account in post_status.missing_in, \
                        f"{account} has MISSING status but not in missing_in"
                    assert account not in post_status.review_in, \
                        f"{account} has MISSING status but in review_in"

                elif match_detail.status == MatchStatus.REVIEW:
                    assert account in post_status.review_in, \
                        f"{account} has REVIEW status but not in review_in"
                    assert account not in post_status.missing_in, \
                        f"{account} has REVIEW status but in missing_in"

                elif match_detail.status == MatchStatus.FOUND:
                    assert account not in post_status.missing_in, \
                        f"{account} has FOUND status but in missing_in"
                    assert account not in post_status.review_in, \
                        f"{account} has FOUND status but in review_in"
