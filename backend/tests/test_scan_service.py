"""Tests for ScanService and MediaCache"""
import pytest
import asyncio
import httpx
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import AccountConfig, ScanConfig
from app.domain.models import InstagramPost, PostType
from app.providers.instagram import InstagramProvider, MockInstagramProvider
from app.services.scan_service import ScanService, ScanResult
from app.cache.media_cache import MediaCache
from app.providers.browser_instagram import BrowserInstagramProvider


@pytest.fixture
def sample_posts():
    """Create sample posts for testing"""
    return [
        InstagramPost(
            shortcode="ABC123",
            username="newbodycol",
            caption="Master post 1",
            post_type=PostType.PHOTO,
            published_at=datetime(2026, 9, 1),
            permalink="https://instagram.com/p/ABC123/",
            thumbnail_url="https://example.com/thumb1.jpg",
            is_video=False,
        ),
        InstagramPost(
            shortcode="ABC124",
            username="newbodycol",
            caption="Master post 2",
            post_type=PostType.VIDEO,
            published_at=datetime(2026, 9, 2),
            permalink="https://instagram.com/p/ABC124/",
            thumbnail_url="https://example.com/thumb2.jpg",
            is_video=True,
        ),
    ]


@pytest.fixture
def media_cache(tmp_path):
    """Create MediaCache instance with temp directory"""
    return MediaCache(cache_dir=str(tmp_path / "cache"))


@pytest.fixture
def account_config():
    """Create default account config"""
    return AccountConfig()


@pytest.fixture
def scan_config():
    """Create scan config for testing"""
    return ScanConfig(master_limit=5)


class TestMediaCache:
    """Tests for MediaCache functionality"""

    def test_cache_dir_creation(self, media_cache):
        """Cache directory is created on init"""
        assert media_cache.cache_dir.exists()

    def test_get_cache_path(self, media_cache):
        """Cache path is generated correctly"""
        path = media_cache._get_cache_path("testuser", "ABC123")
        assert path.name == "testuser_ABC123.jpg"

    @pytest.mark.asyncio
    async def test_none_thumbnail_url_returns_none(self, media_cache):
        """None thumbnail URL returns None without errors"""
        result = await media_cache.get_local_thumbnail("user", "code", None)
        assert result is None

    def test_cache_size_empty(self, media_cache):
        """Cache size is 0 when empty"""
        assert media_cache.cache_size() == 0

    def test_cache_size_with_files(self, media_cache):
        """Cache size counts files correctly"""
        # Create dummy files
        (media_cache.cache_dir / "file1.jpg").write_text("test")
        (media_cache.cache_dir / "file2.jpg").write_text("test")

        assert media_cache.cache_size() == 2

    def test_clear_cache(self, media_cache):
        """Clear cache removes all files"""
        # Create dummy files
        (media_cache.cache_dir / "file1.jpg").write_text("test")
        (media_cache.cache_dir / "file2.jpg").write_text("test")

        assert media_cache.cache_size() == 2

        count = media_cache.clear_cache()

        assert count == 2
        assert media_cache.cache_size() == 0

    @pytest.mark.asyncio
    async def test_thumbnail_url_html_unescape(self):
        """BrowserInstagramProvider extracts og:image and unescapes HTML entities"""
        page_content = '<meta property="og:image" content="https://cdn.test/image.jpg?a=1&amp;b=2">'
        url = BrowserInstagramProvider._extract_thumbnail_url(page_content)
        assert url == "https://cdn.test/image.jpg?a=1&b=2"
        assert "&amp;" not in url

    @pytest.mark.asyncio
    async def test_media_cache_unescapes_url(self, media_cache, tmp_path):
        """MediaCache unescapes URLs before HTTP request"""
        captured_urls = []

        def mock_get(*args, **kwargs):
            url = kwargs.get('url') or (args[1] if len(args) > 1 else None)
            captured_urls.append(url)
            response = MagicMock()
            response.status_code = 200
            response.headers = {"content-type": "image/jpeg"}
            response.content = b"fake-jpeg"
            return response

        with patch("httpx.Client.get", mock_get):
            result = await media_cache.get_local_thumbnail(
                "user", "code",
                "https://cdn.test/image.jpg?a=1&amp;b=2"
            )

        assert captured_urls
        assert "&amp;" not in captured_urls[0]
        assert captured_urls[0] == "https://cdn.test/image.jpg?a=1&b=2"

    @pytest.mark.asyncio
    async def test_http_403_uses_media_fetcher(self, media_cache, tmp_path):
        """HTTP 403 triggers media_fetcher fallback"""
        async def mock_fetcher(url):
            return b"fallback-image"

        media_cache.media_fetcher = mock_fetcher

        def mock_get(*args, **kwargs):
            response = MagicMock()
            response.status_code = 403
            return response

        with patch("httpx.Client.get", mock_get):
            result = await media_cache.get_local_thumbnail("user", "code", "https://test.com/img.jpg")

        assert result is not None
        assert result.read_bytes() == b"fallback-image"

    @pytest.mark.asyncio
    async def test_non_image_http_response_uses_fallback(self, media_cache):
        """HTTP 200 with non-image content uses media_fetcher"""
        async def mock_fetcher(url):
            return b"real-image"

        media_cache.media_fetcher = mock_fetcher

        def mock_get(*args, **kwargs):
            response = MagicMock()
            response.status_code = 200
            response.headers = {"content-type": "text/html"}
            response.content = b"<html>Error</html>"
            return response

        with patch("httpx.Client.get", mock_get):
            result = await media_cache.get_local_thumbnail("user", "code", "https://test.com/img.jpg")

        assert result is not None
        assert result.read_bytes() == b"real-image"

    @pytest.mark.asyncio
    async def test_media_fetcher_failure_returns_none(self, media_cache):
        """Media fetcher returning None results in None"""
        async def mock_fetcher(url):
            return None

        media_cache.media_fetcher = mock_fetcher

        def mock_get(*args, **kwargs):
            response = MagicMock()
            response.status_code = 403
            return response

        with patch("httpx.Client.get", mock_get):
            result = await media_cache.get_local_thumbnail("user", "code", "https://test.com/img.jpg")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_media_returns_bytes(self):
        """fetch_media returns bytes on success"""
        provider = BrowserInstagramProvider()
        provider.context = MagicMock()

        response = MagicMock()
        response.ok = True
        response.headers = {"content-type": "image/jpeg"}
        response.body = AsyncMock(return_value=b"image-bytes")

        provider.context.request.get = AsyncMock(return_value=response)

        result = await provider.fetch_media("https://test.com/image.jpg")
        assert isinstance(result, bytes)
        assert result == b"image-bytes"

    @pytest.mark.asyncio
    async def test_fetch_media_rejects_non_image(self):
        """fetch_media rejects non-image content"""
        provider = BrowserInstagramProvider()
        provider.context = MagicMock()

        response = MagicMock()
        response.ok = True
        response.headers = {"content-type": "text/html"}
        response.body = AsyncMock(return_value=b"<html>")

        provider.context.request.get = AsyncMock(return_value=response)

        result = await provider.fetch_media("https://test.com/image.jpg")
        assert result is None

    @pytest.mark.asyncio
    async def test_browser_close_is_idempotent(self):
        """Browser close can be called multiple times safely"""
        provider = BrowserInstagramProvider()
        context_mock = AsyncMock()
        browser_mock = AsyncMock()
        playwright_mock = AsyncMock()

        provider.context = context_mock
        provider.browser = browser_mock
        provider.playwright = playwright_mock

        await provider.close()
        await provider.close()

        context_mock.close.assert_awaited()
        browser_mock.close.assert_awaited()
        playwright_mock.stop.assert_awaited()

    @pytest.mark.asyncio
    async def test_browser_close_stops_playwright(self):
        """Browser close stops playwright instance"""
        provider = BrowserInstagramProvider()
        context_mock = AsyncMock()
        browser_mock = AsyncMock()
        playwright_mock = AsyncMock()

        provider.context = context_mock
        provider.browser = browser_mock
        provider.playwright = playwright_mock

        await provider.close()

        playwright_mock.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_browser_references_none_after_close(self):
        """All browser references are None after close"""
        provider = BrowserInstagramProvider()
        provider.context = AsyncMock()
        provider.browser = AsyncMock()
        provider.playwright = AsyncMock()

        await provider.close()

        assert provider.context is None
        assert provider.browser is None
        assert provider.playwright is None

    @pytest.mark.asyncio
    async def test_http_timeout_uses_media_fetcher(self, media_cache):
        """HTTP timeout triggers media_fetcher fallback"""
        async def mock_fetcher(url):
            return b"fallback-image"

        media_cache.media_fetcher = mock_fetcher

        def mock_get(*args, **kwargs):
            raise httpx.TimeoutException("timeout")

        with patch("httpx.Client.get", mock_get):
            result = await media_cache.get_local_thumbnail("user", "code", "https://test.com/img.jpg")

        assert result is not None
        assert result.read_bytes() == b"fallback-image"


class TestScanConfig:
    """Tests for ScanConfig"""

    def test_default_master_limit(self):
        """Default master limit is 20"""
        config = ScanConfig()
        assert config.master_limit == 20

    def test_regional_limit_calculation(self):
        """Regional limit is master_limit * multiplier"""
        config = ScanConfig(master_limit=10, regional_multiplier=2.0)
        assert config.regional_limit == 20

    def test_custom_regional_multiplier(self):
        """Regional multiplier can be customized"""
        config = ScanConfig(master_limit=5, regional_multiplier=3.0)
        assert config.regional_limit == 15


class TestAccountConfig:
    """Tests for AccountConfig"""

    def test_default_accounts(self):
        """Default accounts are set correctly"""
        config = AccountConfig()
        assert config.master_account == "newbodycol"
        assert len(config.comparison_accounts) == 3

    def test_all_accounts_includes_master(self):
        """all_accounts includes master and regionals"""
        config = AccountConfig()
        all_accts = config.all_accounts()

        assert "newbodycol" in all_accts
        assert len(all_accts) == 4


class TestScanService:
    """Tests for ScanService"""

    @pytest.mark.asyncio
    async def test_scan_service_initialization(self, account_config, scan_config):
        """ScanService initializes correctly"""
        provider = MockInstagramProvider()
        service = ScanService(
            provider=provider,
            account_config=account_config,
            scan_config=scan_config,
        )

        assert service.provider == provider
        assert service.account_config == account_config
        assert service.scan_config == scan_config

    @pytest.mark.asyncio
    async def test_prepare_posts_with_no_thumbnail_url(self, sample_posts):
        """Prepare posts handles missing thumbnail URLs"""
        posts = [
            InstagramPost(
                shortcode="TEST001",
                username="newbodycol",
                caption="No thumbnail",
                post_type=PostType.PHOTO,
                published_at=datetime.now(),
                permalink="https://instagram.com/p/TEST001/",
                thumbnail_url=None,
                is_video=False,
            )
        ]

        provider = MockInstagramProvider()
        service = ScanService(provider=provider)

        prepared = await service._prepare_posts(posts)

        assert len(prepared) == 1
        assert prepared[0].thumbnail_url is None

    @pytest.mark.asyncio
    async def test_scan_with_mocked_provider(self, tmp_path, account_config, scan_config, sample_posts):
        """Scan service works with mocked provider"""
        # Create mock provider
        mock_provider = AsyncMock(spec=InstagramProvider)
        mock_provider.get_posts.side_effect = [
            sample_posts,  # Master posts
            sample_posts,  # Regional 1
            sample_posts,  # Regional 2
            sample_posts,  # Regional 3
        ]

        # Create service
        service = ScanService(
            provider=mock_provider,
            account_config=account_config,
            scan_config=scan_config,
        )

        # Mock excel export to avoid actual file creation in test
        service.excel_exporter.export = MagicMock(
            return_value=tmp_path / "test.xlsx"
        )

        # Run scan
        result = await service.scan(output_dir=str(tmp_path))

        # Verify result
        assert isinstance(result, ScanResult)
        assert result.master_account == "newbodycol"
        assert result.master_posts_count == 2
        assert result.completed_at > result.started_at

    @pytest.mark.asyncio
    async def test_scan_result_summary(self, tmp_path, account_config, scan_config, sample_posts):
        """ScanResult generates summary text"""
        mock_provider = AsyncMock(spec=InstagramProvider)
        mock_provider.get_posts.side_effect = [
            sample_posts,
            sample_posts,
            sample_posts,
            sample_posts,
        ]

        service = ScanService(
            provider=mock_provider,
            account_config=account_config,
            scan_config=scan_config,
        )

        service.excel_exporter.export = MagicMock(
            return_value=tmp_path / "test.xlsx"
        )

        result = await service.scan(output_dir=str(tmp_path))
        summary = result.summary()

        assert "Scan completed" in summary
        assert "Master posts:" in summary
        assert "Found everywhere:" in summary
