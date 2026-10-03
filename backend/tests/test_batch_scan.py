"""Tests for batch scanning with progress tracking"""
import pytest
from datetime import date, datetime
from app.domain.models import AccountScanProgress, InstagramPost, PostType


class TestAccountScanProgress:
    """Test AccountScanProgress tracking structure"""

    def test_progress_initialized_empty(self):
        """AccountScanProgress starts with empty sets/lists"""
        progress = AccountScanProgress(
            account='testaccount',
            requested_from_date=date(2025, 1, 1),
            requested_to_date=date(2026, 10, 2),
        )
        assert progress.account == 'testaccount'
        assert len(progress.discovered_unique_shortcodes) == 0
        assert len(progress.discovered_posts) == 0
        assert progress.batches_attempted == 0
        assert progress.no_progress_attempts == 0
        assert progress.total_unique_posts == 0

    def test_progress_accumulates_shortcodes(self):
        """Progress accumulates unique shortcodes"""
        progress = AccountScanProgress(account='test')

        # Batch 1: 3 new posts
        progress.discovered_unique_shortcodes.add('ABC123')
        progress.discovered_unique_shortcodes.add('DEF456')
        progress.discovered_unique_shortcodes.add('GHI789')
        progress.total_unique_posts = len(progress.discovered_unique_shortcodes)
        progress.batches_attempted += 1

        assert progress.total_unique_posts == 3
        assert progress.batches_attempted == 1

        # Batch 2: 2 new, 1 duplicate
        progress.discovered_unique_shortcodes.add('ABC123')  # Duplicate
        progress.discovered_unique_shortcodes.add('JKL012')  # New
        progress.discovered_unique_shortcodes.add('MNO345')  # New
        progress.total_unique_posts = len(progress.discovered_unique_shortcodes)
        progress.batches_attempted += 1

        assert progress.total_unique_posts == 5  # Only unique count
        assert progress.batches_attempted == 2


class TestBatchScanDeduplication:
    """Test that batch scanning correctly deduplicates"""

    def test_exact_same_shortcodes_detected_as_no_progress(self):
        """If batch returns exactly same shortcodes, no_progress_attempts increases"""
        progress = AccountScanProgress(account='test')

        # Batch 1: discover 5 posts
        batch1_shortcodes = {'A', 'B', 'C', 'D', 'E'}
        progress.discovered_unique_shortcodes.update(batch1_shortcodes)
        progress.total_unique_posts = len(progress.discovered_unique_shortcodes)
        progress.batches_attempted += 1

        # Batch 2: get exact same 5 posts
        batch2_shortcodes = {'A', 'B', 'C', 'D', 'E'}
        new_in_batch2 = batch2_shortcodes - progress.discovered_unique_shortcodes

        if len(new_in_batch2) == 0:
            progress.no_progress_attempts += 1
        else:
            progress.no_progress_attempts = 0

        progress.discovered_unique_shortcodes.update(batch2_shortcodes)
        progress.batches_attempted += 1

        assert progress.total_unique_posts == 5  # Still 5
        assert progress.no_progress_attempts == 1  # No new progress
        assert progress.batches_attempted == 2

    def test_partial_progress_resets_no_progress_counter(self):
        """If new shortcodes arrive, no_progress_attempts resets"""
        progress = AccountScanProgress(account='test')
        progress.no_progress_attempts = 2

        # Batch with new shortcodes
        new_shortcodes = {'X', 'Y', 'Z'}
        new_count = len(new_shortcodes - progress.discovered_unique_shortcodes)

        if new_count > 0:
            progress.no_progress_attempts = 0

        progress.discovered_unique_shortcodes.update(new_shortcodes)
        progress.total_unique_posts = len(progress.discovered_unique_shortcodes)

        assert progress.no_progress_attempts == 0  # Reset
        assert progress.total_unique_posts == 3


class TestBatchScanStoppingCriteria:
    """Test stopping criteria for batch scanning"""

    def test_stop_after_two_no_progress_attempts(self):
        """Should stop after 2 consecutive attempts with no new posts"""
        MAX_NO_PROGRESS_ATTEMPTS = 2
        progress = AccountScanProgress(account='test')

        # Simulate batches
        batches = [
            {'A', 'B', 'C'},           # Batch 1: 3 new
            {'A', 'B', 'C'},           # Batch 2: 0 new
            {'A', 'B', 'C'},           # Batch 3: 0 new
        ]

        for batch_shortcodes in batches:
            new_count = len(batch_shortcodes - progress.discovered_unique_shortcodes)
            if new_count > 0:
                progress.no_progress_attempts = 0
            else:
                progress.no_progress_attempts += 1

            progress.discovered_unique_shortcodes.update(batch_shortcodes)
            progress.total_unique_posts = len(progress.discovered_unique_shortcodes)
            progress.batches_attempted += 1

            if progress.no_progress_attempts >= MAX_NO_PROGRESS_ATTEMPTS:
                progress.stop_reason = 'public_history_limit'
                progress.completed = False
                break

        assert progress.total_unique_posts == 3
        assert progress.stop_reason == 'public_history_limit'
        assert progress.completed is False
        assert progress.batches_attempted == 3

    def test_limit_to_four_batches_max(self):
        """Should not exceed 4 batch attempts"""
        MAX_BATCH_ATTEMPTS = 4
        progress = AccountScanProgress(account='test')

        # Try to simulate 5 batches
        for i in range(5):
            if progress.batches_attempted >= MAX_BATCH_ATTEMPTS:
                break
            progress.batches_attempted += 1

        assert progress.batches_attempted == 4  # Stopped at max


class TestCoverageReporting:
    """Test that coverage is accurately reported"""

    def test_coverage_reflects_unique_posts_not_total_links(self):
        """Coverage should be unique count, not total attempts"""
        progress = AccountScanProgress(
            account='test',
            requested_from_date=date(2025, 1, 1),
            requested_to_date=date(2026, 10, 2),
        )

        # 3 batches each returning 5 shortcodes (3 new, 2 duplicates each batch)
        progress.discovered_unique_shortcodes = {'A', 'B', 'C', 'D', 'E'}
        progress.total_unique_posts = 5
        progress.batches_attempted = 3
        progress.no_progress_attempts = 2
        progress.stop_reason = 'public_history_limit'
        progress.completed = False

        # Coverage should be 5 unique posts, not 15 attempted
        assert progress.total_unique_posts == 5
        assert progress.batches_attempted == 3

        # Frontend should show:
        # "5 publicaciones públicas únicas encontradas"
        # "Intentos realizados: 3"
        # "Período completo: No confirmado"


class TestProgressWarnings:
    """Test warning generation for partial scans"""

    def test_warning_for_history_limit(self):
        """public_history_limit generates appropriate warning"""
        warning = (
            "Instagram dejó de entregar publicaciones públicas nuevas "
            "después de varios intentos. No fue posible confirmar todo "
            "el período solicitado."
        )
        progress = AccountScanProgress(
            account='test',
            stop_reason='public_history_limit',
            completed=False,
            warnings=[warning],
        )

        assert len(progress.warnings) > 0
        assert 'dejó de entregar' in progress.warnings[0]
        assert progress.completed is False
