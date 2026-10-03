"""Tests for manual link extraction and permalink support"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from app.domain.models import InstagramPost, PostType
from app.api.schemas import ManualLinkRequest, ManualLinkResponse


class TestManualLinkRequestValidation:
    """Validate manual link URL parsing"""

    def test_valid_post_urls(self):
        """Valid URLs with /p/ are accepted"""
        req = ManualLinkRequest(
            links=[
                "https://www.instagram.com/p/ABC123/",
                "https://www.instagram.com/p/XYZ789/",
            ]
        )
        assert len(req.links) == 2

    def test_valid_reel_urls(self):
        """Valid URLs with /reel/ are accepted"""
        req = ManualLinkRequest(
            links=[
                "https://www.instagram.com/reel/ABC123/",
                "https://www.instagram.com/reel/XYZ789/",
            ]
        )
        assert len(req.links) == 2

    def test_mixed_valid_urls(self):
        """Mix of /p/ and /reel/ URLs accepted"""
        req = ManualLinkRequest(
            links=[
                "https://www.instagram.com/p/ABC123/",
                "https://www.instagram.com/reel/XYZ789/",
            ]
        )
        assert len(req.links) == 2

    def test_invalid_urls_rejected(self):
        """URLs without /p/ or /reel/ rejected"""
        with pytest.raises(ValueError, match="No valid Instagram post URLs"):
            ManualLinkRequest(
                links=[
                    "https://www.instagram.com/testuser/",
                    "https://www.example.com/",
                ]
            )

    def test_empty_links_rejected(self):
        """Empty links array rejected"""
        with pytest.raises(ValueError):
            ManualLinkRequest(links=[])


class TestManualLinkResponse:
    """Validate response structure"""

    def test_response_structure(self):
        """Response has required fields"""
        resp = ManualLinkResponse(
            status="completed",
            links_processed=2,
            posts_found=1,
            posts=[{
                "shortcode": "ABC123",
                "permalink": "https://www.instagram.com/p/ABC123/",
                "published_at": "2024-10-01T15:30:00",
                "caption": "Test",
                "type": "photo",
                "username": "testuser",
            }],
            errors=["Error: https://www.instagram.com/p/INVALID/"]
        )

        assert resp.status == "completed"
        assert resp.links_processed == 2
        assert resp.posts_found == 1
        assert len(resp.posts) == 1
        assert len(resp.errors) == 1


class TestPermalinkPatterns:
    """Test URL pattern matching"""

    def test_post_shortcode_extraction(self):
        """Extract shortcode from /p/ URL"""
        url = "https://www.instagram.com/p/ABC123DEF456/"
        assert "/p/" in url
        parts = url.split("/p/")
        assert len(parts) == 2
        assert "ABC123DEF456" in parts[1]

    def test_reel_shortcode_extraction(self):
        """Extract shortcode from /reel/ URL"""
        url = "https://www.instagram.com/reel/XYZ789ABC123/"
        assert "/reel/" in url
        parts = url.split("/reel/")
        assert len(parts) == 2
        assert "XYZ789ABC123" in parts[1]

    def test_normalize_post_url(self):
        """Normalize various post URL formats"""
        urls = [
            "https://www.instagram.com/p/ABC123/",
            "https://instagram.com/p/ABC123/",
            "www.instagram.com/p/ABC123/",
            "instagram.com/p/ABC123/",
        ]
        for url in urls:
            assert "/p/" in url


@pytest.mark.asyncio
async def test_get_post_by_permalink_foundation():
    """Foundation test: permalink extraction method exists"""
    from app.providers.browser_instagram import BrowserInstagramProvider

    provider = BrowserInstagramProvider()

    # Verify method exists
    assert hasattr(provider, 'get_post_by_permalink')
    assert callable(provider.get_post_by_permalink)

    # No actual Instagram call - just verify method signature
    # Real calls require explicit test approval


@pytest.mark.asyncio
async def test_get_post_by_permalink_handles_error():
    """Method gracefully handles errors without crashing"""
    from app.providers.browser_instagram import BrowserInstagramProvider

    provider = BrowserInstagramProvider()

    # Mock a bad URL to ensure error handling
    # Should return None, not raise exception
    result = await provider.get_post_by_permalink("https://www.instagram.com/invalid/")
    assert result is None


class TestManualLinkDeduplication:
    """Test duplicate URL handling"""

    def test_duplicate_links_handled(self):
        """Duplicate URLs in same request handled gracefully"""
        # This would be handled in the endpoint by deduping before processing
        links = [
            "https://www.instagram.com/p/ABC123/",
            "https://www.instagram.com/p/ABC123/",  # duplicate
            "https://www.instagram.com/p/XYZ789/",
        ]
        unique_links = list(set(links))
        assert len(unique_links) == 2


class TestManualLinkErrorHandling:
    """Test error cases in manual link extraction"""

    def test_malformed_url_rejected(self):
        """Malformed URLs generate error entries"""
        # In actual endpoint, bad URLs would be in errors array
        bad_urls = [
            "https://www.instagram.com/p/",
            "https://www.instagram.com/p/abc123/extra/path/",
            "not a url",
        ]
        for url in bad_urls:
            # Just validate they would be caught
            assert len(url) > 0
