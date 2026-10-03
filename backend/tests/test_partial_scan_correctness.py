"""Tests for correctness of partial scan behavior (P0 fix)"""
import pytest
from app.domain.models import FetchMetadata


class TestScrollStalledIsPartial:
    """Test that scroll_stalled generates partial result, not completed"""

    def test_scroll_stalled_completed_is_false(self):
        """scroll_stalled must have completed=False"""
        metadata = FetchMetadata(
            account='test',
            discovered_links=100,
            posts_with_date=100,
            undated_posts=0,
            completed=False,  # MUST be False
            stop_reason='scroll_stalled',
            warning="Instagram dejó de entregar nuevas publicaciones antes de confirmar todo el período solicitado.",
        )
        assert metadata.completed is False
        assert metadata.stop_reason == 'scroll_stalled'

    def test_scroll_stalled_generates_warning(self):
        """scroll_stalled MUST generate warning"""
        warning = "Instagram dejó de entregar nuevas publicaciones antes de confirmar todo el período solicitado."
        metadata = FetchMetadata(
            account='test',
            discovered_links=50,
            posts_with_date=50,
            undated_posts=0,
            completed=False,
            stop_reason='scroll_stalled',
            warning=warning,
        )
        assert metadata.warning is not None
        assert 'dejó de entregar' in metadata.warning


class TestPartialScansNotCompleted:
    """Verify that all limit/block reasons result in completed=False"""

    def test_public_access_limited_not_completed(self):
        """public_access_limited must have completed=False"""
        metadata = FetchMetadata(
            account='test',
            discovered_links=25,
            posts_with_date=25,
            undated_posts=0,
            completed=False,
            stop_reason='public_access_limited',
            warning="Instagram limitó el acceso público",
        )
        assert metadata.completed is False

    def test_safety_limit_not_completed(self):
        """safety_limit must have completed=False"""
        metadata = FetchMetadata(
            account='test',
            discovered_links=300,
            posts_with_date=300,
            undated_posts=0,
            completed=False,
            stop_reason='safety_limit',
            warning="Límite técnico de seguridad",
        )
        assert metadata.completed is False


class TestCountModeCompleted:
    """Test that count mode can be completed"""

    def test_count_mode_completed_true_when_limit_reached(self):
        """Count mode with limit reached is completed"""
        metadata = FetchMetadata(
            account='test',
            discovered_links=20,
            posts_with_date=20,
            undated_posts=0,
            completed=True,  # Count mode CAN be completed
            stop_reason=None,
            warning=None,
        )
        assert metadata.completed is True
        assert metadata.stop_reason is None


class TestDateModeWarnings:
    """Test warning messages for date mode partial scans"""

    def test_date_scroll_stalled_warning_mentions_period(self):
        """scroll_stalled warning should mention period confirmation"""
        warning = "Instagram dejó de entregar nuevas publicaciones antes de confirmar todo el período solicitado."
        metadata = FetchMetadata(
            account='test',
            discovered_links=150,
            posts_with_date=150,
            undated_posts=0,
            completed=False,
            stop_reason='scroll_stalled',
            warning=warning,
        )
        assert 'período' in metadata.warning
        assert metadata.completed is False

    def test_all_partial_scans_have_warnings(self):
        """All partial scans (completed=False) should have warnings"""
        partial_reasons = ['public_access_limited', 'safety_limit', 'scroll_stalled']
        for reason in partial_reasons:
            metadata = FetchMetadata(
                account='test',
                discovered_links=50,
                posts_with_date=50,
                undated_posts=0,
                completed=False,
                stop_reason=reason,
                warning=f"Warning for {reason}",
            )
            assert metadata.completed is False
            assert metadata.warning is not None
            assert len(metadata.warning) > 0
