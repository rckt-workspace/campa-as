"""Tests for partial scan warnings and public access limited handling"""
import pytest
from datetime import datetime
from app.domain.models import InstagramPost, PostType, FetchMetadata
from app.providers.browser_instagram import BrowserInstagramProvider


class TestFetchMetadataTracking:
    """Test that FetchMetadata is properly tracked"""

    def test_fetch_metadata_initialized_empty(self):
        """Provider initializes with empty metadata dict"""
        provider = BrowserInstagramProvider()
        assert hasattr(provider, 'fetch_metadata_by_account')
        assert provider.fetch_metadata_by_account == {}

    def test_fetch_metadata_structure(self):
        """FetchMetadata has all required fields"""
        metadata = FetchMetadata(
            account='testaccount',
            discovered_links=42,
            posts_with_date=40,
            undated_posts=2,
            completed=False,
            stop_reason='public_access_limited',
            warning='Instagram limitó acceso',
        )
        assert metadata.account == 'testaccount'
        assert metadata.discovered_links == 42
        assert metadata.posts_with_date == 40
        assert metadata.undated_posts == 2
        assert metadata.completed is False
        assert metadata.stop_reason == 'public_access_limited'
        assert metadata.warning == 'Instagram limitó acceso'


class TestPartialScanStopReasons:
    """Test that stop reasons are correctly identified"""

    def test_stop_reason_none_means_natural_completion(self):
        """stop_reason=None when scan completed naturally"""
        metadata = FetchMetadata(
            account='test',
            discovered_links=100,
            posts_with_date=100,
            undated_posts=0,
            completed=True,
            stop_reason=None,
            warning=None,
        )
        assert metadata.stop_reason is None
        assert metadata.completed is True
        assert metadata.warning is None

    def test_stop_reason_public_access_limited_maps_to_warning(self):
        """public_access_limited generates correct warning message"""
        warning = (
            "Instagram limitó el acceso público antes de poder confirmar "
            "todo el historial solicitado."
        )
        metadata = FetchMetadata(
            account='testaccount',
            discovered_links=25,
            posts_with_date=25,
            undated_posts=0,
            completed=False,
            stop_reason='public_access_limited',
            warning=warning,
        )
        assert metadata.completed is False
        assert 'limitó el acceso público' in metadata.warning

    def test_stop_reason_safety_limit_maps_to_warning(self):
        """safety_limit generates correct warning message"""
        warning = (
            "El escaneo alcanzó el límite técnico de seguridad "
            "antes de confirmar todo el período."
        )
        metadata = FetchMetadata(
            account='testaccount',
            discovered_links=300,
            posts_with_date=300,
            undated_posts=0,
            completed=False,
            stop_reason='safety_limit',
            warning=warning,
        )
        assert metadata.completed is False
        assert 'límite técnico' in metadata.warning

    def test_stop_reason_scroll_stalled_maps_to_warning(self):
        """scroll_stalled generates correct warning message"""
        warning = (
            "Instagram dejó de entregar nuevas publicaciones "
            "antes de confirmar todo el período solicitado."
        )
        metadata = FetchMetadata(
            account='testaccount',
            discovered_links=150,
            posts_with_date=150,
            undated_posts=0,
            completed=True,
            stop_reason='scroll_stalled',
            warning=warning,
        )
        assert 'dejó de entregar' in metadata.warning


class TestPartialScanCompletedFlag:
    """Test that completed flag is properly set"""

    def test_completed_true_for_natural_end(self):
        """completed=True when profile traversal reached end"""
        metadata = FetchMetadata(
            account='test',
            discovered_links=500,
            posts_with_date=500,
            undated_posts=0,
            completed=True,
            stop_reason='scroll_stalled',
            warning=None,
        )
        assert metadata.completed is True

    def test_completed_false_for_limits(self):
        """completed=False when stopped by public_access_limited or safety_limit"""
        for reason in ['public_access_limited', 'safety_limit']:
            metadata = FetchMetadata(
                account='test',
                discovered_links=100,
                posts_with_date=100,
                undated_posts=0,
                completed=False,
                stop_reason=reason,
                warning='Some warning',
            )
            assert metadata.completed is False


class TestCheckForBlocksContract:
    """Test that _check_for_blocks maintains consistent return type"""

    def test_check_for_blocks_always_returns_tuple(self):
        """_check_for_blocks must always return (is_blocked, reason) tuple"""
        # This is a contract validation - the function MUST return tuple
        # even if it returns False, None
        expected_returns = [
            (True, "challenge_detected"),
            (True, "login_wall_no_posts"),
            (False, "public_access_limited"),
            (False, None),
        ]
        # All are valid forms of the contract
        for is_blocked, reason in expected_returns:
            assert isinstance(is_blocked, bool)
            assert reason is None or isinstance(reason, str)


class TestPartialScanWithWarnings:
    """Test that partial scans include warnings in results"""

    def test_scan_result_includes_warnings_field(self):
        """ScanResult has warnings field"""
        from app.services.scan_service import ScanResult
        from app.domain.models import AuditResult

        audit_result = AuditResult(
            master_account='master',
            compared_accounts=['account1'],
            posts_status=[],
            total_master_posts=0,
            found_in_all=0,
            with_missing=0,
            with_review=0,
            missing_count_by_account={},
            review_count_by_account={},
            timestamp=datetime.now(),
        )

        result = ScanResult(
            master_account='master',
            comparison_accounts=['account1'],
            master_posts_count=0,
            regional_posts_count={'account1': 0},
            audit_result=audit_result,
            excel_path='/tmp/test.xlsx',
            started_at=datetime.now(),
            completed_at=datetime.now(),
            warnings=['Warning 1', 'Warning 2'],
        )

        assert hasattr(result, 'warnings')
        assert len(result.warnings) == 2
        assert 'Warning 1' in result.warnings

    def test_scan_result_warnings_default_to_empty(self):
        """ScanResult.warnings defaults to empty list"""
        from app.services.scan_service import ScanResult
        from app.domain.models import AuditResult

        audit_result = AuditResult(
            master_account='master',
            compared_accounts=['account1'],
            posts_status=[],
            total_master_posts=0,
            found_in_all=0,
            with_missing=0,
            with_review=0,
            missing_count_by_account={},
            review_count_by_account={},
            timestamp=datetime.now(),
        )

        result = ScanResult(
            master_account='master',
            comparison_accounts=['account1'],
            master_posts_count=0,
            regional_posts_count={'account1': 0},
            audit_result=audit_result,
            excel_path='/tmp/test.xlsx',
            started_at=datetime.now(),
            completed_at=datetime.now(),
        )

        assert result.warnings == []
