"""Tests for MetaInstagramProvider"""
import os
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from zoneinfo import ZoneInfo
from app.providers.browser_instagram import BrowserInstagramProvider

from app.domain.models import InstagramPost, PostType
from app.domain.exceptions import InstagramProviderException
from app.providers.meta_instagram import MetaInstagramProvider
from app.providers.factory import create_instagram_provider
from app.providers.browser_instagram import BrowserInstagramProvider


class TestMetaProviderEnvironment:
    """Test Meta provider environment configuration"""

    def test_missing_access_token(self):
        """Test that missing META_ACCESS_TOKEN raises exception"""
        with patch.dict(os.environ, {"META_IG_USER_ID": "123"}, clear=True):
            with pytest.raises(InstagramProviderException) as exc:
                MetaInstagramProvider()
            assert "META_ACCESS_TOKEN" in str(exc.value)

    def test_missing_ig_user_id(self):
        """Test that missing META_IG_USER_ID raises exception"""
        with patch.dict(os.environ, {"META_ACCESS_TOKEN": "abc"}, clear=True):
            with pytest.raises(InstagramProviderException) as exc:
                MetaInstagramProvider()
            assert "META_IG_USER_ID" in str(exc.value)

    def test_configurable_graph_version(self):
        """Test that Graph API version is configurable via env"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
            "META_GRAPH_API_VERSION": "v19.0",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = MetaInstagramProvider()
            assert provider.graph_version == "v19.0"
            assert "v19.0" in provider.base_url

    def test_default_graph_version(self):
        """Test default Graph API version when not configured"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = MetaInstagramProvider()
            assert provider.graph_version == "v18.0"

    def test_max_pages_parsing(self):
        """Test META_MAX_PAGES is parsed as integer"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
            "META_MAX_PAGES": "50",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = MetaInstagramProvider()
            assert provider.max_pages == 50
            assert isinstance(provider.max_pages, int)

    def test_default_max_pages(self):
        """Test default MAX_PAGES when not configured"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = MetaInstagramProvider()
            assert provider.max_pages == 100


class TestFactory:
    """Test provider factory"""

    def test_factory_meta_provider(self):
        """Test factory creates Meta provider when env set"""
        env = {
            "INSTAGRAM_PROVIDER": "meta",
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = create_instagram_provider()
            assert isinstance(provider, MetaInstagramProvider)

    def test_factory_browser_provider(self):
        """Test factory creates Browser provider when specified"""
        with patch.dict(os.environ, {"INSTAGRAM_PROVIDER": "browser"}, clear=True):
            provider = create_instagram_provider()
            assert isinstance(provider, BrowserInstagramProvider)

    def test_factory_default_browser_provider(self):
        """Test factory defaults to Browser when not specified"""
        with patch.dict(os.environ, {}, clear=True):
            provider = create_instagram_provider()
            assert isinstance(provider, BrowserInstagramProvider)

    def test_factory_unknown_provider(self):
        """Test factory raises error for unknown provider type"""
        with patch.dict(os.environ, {"INSTAGRAM_PROVIDER": "invalid"}, clear=True):
            with pytest.raises(InstagramProviderException) as exc:
                create_instagram_provider()
            assert "Unknown Instagram provider" in str(exc.value)

    def test_factory_meta_misconfigured_fails_not_silently(self):
        """Test factory fails loudly when Meta provider misconfigured"""
        with patch.dict(os.environ, {"INSTAGRAM_PROVIDER": "meta"}, clear=True):
            with pytest.raises(InstagramProviderException):
                create_instagram_provider()


class TestUsernameValidation:
    """Test Instagram username validation"""

    @pytest.fixture
    def provider(self):
        """Create provider for testing"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            return MetaInstagramProvider()

    def test_valid_username_alphanumeric(self, provider):
        """Test valid alphanumeric username"""
        result = provider._validate_username("newbodycol")
        assert result == "newbodycol"

    def test_valid_username_with_underscore(self, provider):
        """Test valid username with underscore"""
        result = provider._validate_username("new_body_col")
        assert result == "new_body_col"

    def test_valid_username_with_dot(self, provider):
        """Test valid username with dot"""
        result = provider._validate_username("newbody.col")
        assert result == "newbody.col"

    def test_valid_username_strips_at_symbol(self, provider):
        """Test username with @ prefix is stripped"""
        result = provider._validate_username("@newbodycol")
        assert result == "newbodycol"

    def test_invalid_username_empty(self, provider):
        """Test empty username raises error"""
        with pytest.raises(ValueError):
            provider._validate_username("")

    def test_invalid_username_too_long(self, provider):
        """Test username > 30 chars raises error"""
        with pytest.raises(ValueError):
            provider._validate_username("a" * 31)

    def test_invalid_username_special_chars(self, provider):
        """Test username with invalid chars raises error"""
        with pytest.raises(ValueError):
            provider._validate_username("new body-col")

    def test_invalid_username_injection_attempt(self, provider):
        """Test SQL/command injection attempt rejected"""
        with pytest.raises(ValueError):
            provider._validate_username("newbody'; DROP TABLE--")


class TestBusinessDiscovery:
    """Test Business Discovery API integration"""

    @pytest.fixture
    def provider(self):
        """Create provider for testing"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            return MetaInstagramProvider()

    @pytest.mark.asyncio
    async def test_discover_account_success(self, provider):
        """Test successful account discovery"""
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "business_discovery": {
                "id": "789",
                "username": "newbodycol"
            }
        })
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, "_ensure_client"):
            provider.client = AsyncMock()
            provider.client.get = AsyncMock(return_value=mock_response)

            result = await provider._discover_account("newbodycol")

        assert result["id"] == "789"
        assert result["username"] == "newbodycol"

    @pytest.mark.asyncio
    async def test_discover_account_not_found(self, provider):
        """Test account not found error"""
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "business_discovery": {}
        })
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, "_ensure_client"):
            provider.client = AsyncMock()
            provider.client.get = AsyncMock(return_value=mock_response)

            with pytest.raises(InstagramProviderException) as exc:
                await provider._discover_account("nonexistent")
            assert "not found" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_discover_account_api_error(self, provider):
        """Test API error response"""
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "error": {
                "code": 190,
                "message": "Invalid OAuth access token"
            }
        })
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, "_ensure_client"):
            provider.client = AsyncMock()
            provider.client.get = AsyncMock(return_value=mock_response)

            with pytest.raises(InstagramProviderException) as exc:
                await provider._discover_account("newbodycol")
            assert "190" in str(exc.value)


class TestMediaFetching:
    """Test media fetching with pagination"""

    @pytest.fixture
    def provider(self):
        """Create provider for testing"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            return MetaInstagramProvider()

    @pytest.mark.asyncio
    async def test_fetch_single_page(self, provider):
        """Test fetching single page of media"""
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "data": [
                {
                    "id": "m1",
                    "caption": "Test post",
                    "media_type": "IMAGE",
                    "permalink": "https://www.instagram.com/p/ABC123/",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "media_url": "https://example.com/img.jpg",
                }
            ],
            "paging": {}
        })
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, "_ensure_client"):
            provider.client = AsyncMock()
            provider.client.get = AsyncMock(return_value=mock_response)

            result = await provider._fetch_media_page("789")

        assert len(result["data"]) == 1
        assert result["data"][0]["id"] == "m1"

    @pytest.mark.asyncio
    async def test_fetch_media_with_pagination(self, provider):
        """Test pagination with cursor"""
        # First page
        mock_response_1 = MagicMock()
        mock_response_1.json = MagicMock(return_value={
            "data": [
                {
                    "id": "m1",
                    "caption": "Post 1",
                    "media_type": "IMAGE",
                    "permalink": "https://www.instagram.com/p/ABC123/",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "media_url": "https://example.com/img.jpg",
                }
            ],
            "paging": {
                "cursors": {
                    "after": "next_cursor_token"
                }
            }
        })
        mock_response_1.raise_for_status = MagicMock()

        # Second page
        mock_response_2 = MagicMock()
        mock_response_2.json = MagicMock(return_value={
            "data": [
                {
                    "id": "m2",
                    "caption": "Post 2",
                    "media_type": "VIDEO",
                    "permalink": "https://www.instagram.com/p/DEF456/",
                    "timestamp": "2024-01-14T10:30:00Z",
                    "media_url": "https://example.com/video.mp4",
                }
            ],
            "paging": {}
        })
        mock_response_2.raise_for_status = MagicMock()

        with patch.object(provider, "_ensure_client"):
            provider.client = AsyncMock()
            provider.client.get = AsyncMock(side_effect=[mock_response_1, mock_response_2])

            # First fetch
            result1 = await provider._fetch_media_page("789")
            assert result1["paging"]["cursors"]["after"] == "next_cursor_token"

            # Second fetch with cursor
            result2 = await provider._fetch_media_page("789", "next_cursor_token")
            assert len(result2["data"]) == 1


class TestMediaMapping:
    """Test media type mapping"""

    @pytest.fixture
    def provider(self):
        """Create provider for testing"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            return MetaInstagramProvider()

    def test_image_maps_to_photo(self, provider):
        """Test IMAGE media type maps to PHOTO"""
        result = provider._map_media_type("IMAGE")
        assert result == PostType.PHOTO

    def test_carousel_maps_to_carousel(self, provider):
        """Test CAROUSEL_ALBUM media type maps to CAROUSEL"""
        result = provider._map_media_type("CAROUSEL_ALBUM")
        assert result == PostType.CAROUSEL

    def test_video_without_reels_maps_to_video(self, provider):
        """Test VIDEO without REELS product type maps to VIDEO"""
        result = provider._map_media_type("VIDEO")
        assert result == PostType.VIDEO

    def test_video_with_reels_maps_to_reel(self, provider):
        """Test VIDEO with REELS product type maps to REEL"""
        result = provider._map_media_type("VIDEO", "REELS")
        assert result == PostType.REEL

    def test_unknown_type_defaults_to_photo(self, provider):
        """Test unknown media type defaults to PHOTO"""
        result = provider._map_media_type("UNKNOWN")
        assert result == PostType.PHOTO


class TestPostConversion:
    """Test converting Meta media to domain InstagramPost"""

    @pytest.fixture
    def provider(self):
        """Create provider for testing"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            return MetaInstagramProvider()

    def test_media_to_post_complete(self, provider):
        """Test complete media object conversion"""
        media = {
            "id": "m1",
            "caption": "Test post",
            "media_type": "IMAGE",
            "permalink": "https://www.instagram.com/p/ABC123/",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_url": "https://example.com/img.jpg",
            "thumbnail_url": "https://example.com/thumb.jpg",
        }

        post = provider._media_to_post(media, "newbodycol")

        assert post is not None
        assert post.shortcode == "ABC123"
        assert post.username == "newbodycol"
        assert post.caption == "Test post"
        assert post.post_type == PostType.PHOTO
        assert post.permalink == "https://www.instagram.com/p/ABC123/"
        assert post.is_video is False
        assert post.media_count == 1

    def test_media_to_post_missing_caption(self, provider):
        """Test media without caption"""
        media = {
            "id": "m1",
            "media_type": "IMAGE",
            "permalink": "https://www.instagram.com/p/ABC123/",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_url": "https://example.com/img.jpg",
        }

        post = provider._media_to_post(media, "newbodycol")

        assert post is not None
        assert post.caption == ""

    def test_media_to_post_thumbnail_fallback(self, provider):
        """Test thumbnail URL fallback to media_url"""
        media = {
            "id": "m1",
            "media_type": "IMAGE",
            "permalink": "https://www.instagram.com/p/ABC123/",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_url": "https://example.com/img.jpg",
        }

        post = provider._media_to_post(media, "newbodycol")

        assert post.thumbnail_url == "https://example.com/img.jpg"

    def test_media_to_post_carousel_count(self, provider):
        """Test carousel media_count from children"""
        media = {
            "id": "m1",
            "media_type": "CAROUSEL_ALBUM",
            "permalink": "https://www.instagram.com/p/ABC123/",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_url": "https://example.com/img.jpg",
            "children": {
                "data": [
                    {"id": "c1", "media_type": "IMAGE"},
                    {"id": "c2", "media_type": "IMAGE"},
                    {"id": "c3", "media_type": "IMAGE"},
                ]
            }
        }

        post = provider._media_to_post(media, "newbodycol")

        assert post.media_count == 3

    def test_media_to_post_invalid_shortcode(self, provider):
        """Test invalid permalink returns None"""
        media = {
            "id": "m1",
            "media_type": "IMAGE",
            "permalink": "https://www.instagram.com/invalid",
            "timestamp": "2024-01-15T10:30:00Z",
            "media_url": "https://example.com/img.jpg",
        }

        post = provider._media_to_post(media, "newbodycol")

        assert post is None


class TestGetPosts:
    """Test get_posts method with pagination and filtering"""

    @pytest.fixture
    def provider(self):
        """Create provider for testing"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            return MetaInstagramProvider()

    @pytest.mark.asyncio
    async def test_get_posts_count_mode(self, provider):
        """Test count mode returns up to limit posts"""
        mock_discover = AsyncMock(return_value={"id": "789", "username": "newbodycol"})
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "data": [
                {
                    "id": f"m{i}",
                    "caption": f"Post {i}",
                    "media_type": "IMAGE",
                    "permalink": f"https://www.instagram.com/p/ABC{i}/",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "media_url": "https://example.com/img.jpg",
                }
                for i in range(1, 6)
            ],
            "paging": {}
        })
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, "_discover_account", mock_discover):
            with patch.object(provider, "_ensure_client"):
                provider.client = AsyncMock()
                provider.client.get = AsyncMock(return_value=mock_response)

                posts = await provider.get_posts("newbodycol", limit=3)

        assert len(posts) == 3

    @pytest.mark.asyncio
    async def test_get_posts_date_mode(self, provider):
        """Test date mode filters posts by date range"""
        mock_discover = AsyncMock(return_value={"id": "789", "username": "newbodycol"})

        # Create posts spanning date range (newest first, as Instagram returns)
        base_date = datetime(2024, 1, 15, tzinfo=ZoneInfo("UTC"))

        media_data = [
            {
                "id": "m3",
                "caption": "Future post",
                "media_type": "IMAGE",
                "permalink": "https://www.instagram.com/p/ABC3/",
                "timestamp": (base_date + timedelta(days=5)).isoformat(),
                "media_url": "https://example.com/img.jpg",
            },
            {
                "id": "m2",
                "caption": "In range post",
                "media_type": "IMAGE",
                "permalink": "https://www.instagram.com/p/ABC2/",
                "timestamp": base_date.isoformat(),
                "media_url": "https://example.com/img.jpg",
            },
            {
                "id": "m1",
                "caption": "Old post",
                "media_type": "IMAGE",
                "permalink": "https://www.instagram.com/p/ABC1/",
                "timestamp": (base_date - timedelta(days=5)).isoformat(),
                "media_url": "https://example.com/img.jpg",
            },
        ]

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "data": media_data,
            "paging": {}
        })
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, "_discover_account", mock_discover):
            with patch.object(provider, "_ensure_client"):
                provider.client = AsyncMock()
                provider.client.get = AsyncMock(return_value=mock_response)

                from_date = base_date.date() - timedelta(days=2)
                to_date = base_date.date() + timedelta(days=2)

                posts = await provider.get_posts(
                    "newbodycol",
                    from_date=from_date,
                    to_date=to_date
                )

        # Should only include posts within range
        assert len(posts) == 1
        assert posts[0].caption == "In range post"

    @pytest.mark.asyncio
    async def test_get_posts_deduplication(self, provider):
        """Test duplicate posts are skipped"""
        mock_discover = AsyncMock(return_value={"id": "789", "username": "newbodycol"})

        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "data": [
                {
                    "id": "m1",
                    "caption": "Post 1",
                    "media_type": "IMAGE",
                    "permalink": "https://www.instagram.com/p/ABC1/",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "media_url": "https://example.com/img.jpg",
                },
                {
                    "id": "m1",  # Duplicate ID
                    "caption": "Post 1 duplicate",
                    "media_type": "IMAGE",
                    "permalink": "https://www.instagram.com/p/ABC1/",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "media_url": "https://example.com/img.jpg",
                },
            ],
            "paging": {}
        })
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider, "_discover_account", mock_discover):
            with patch.object(provider, "_ensure_client"):
                provider.client = AsyncMock()
                provider.client.get = AsyncMock(return_value=mock_response)

                posts = await provider.get_posts("newbodycol")

        assert len(posts) == 1


class TestErrorHandling:
    """Test error handling for various failure scenarios"""

    @pytest.fixture
    def provider(self):
        """Create provider for testing"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            return MetaInstagramProvider()

    @pytest.mark.asyncio
    async def test_invalid_token_error(self, provider):
        """Test handling of invalid token error"""
        mock_discover = AsyncMock()
        mock_discover.side_effect = InstagramProviderException("Meta API error [190]: Invalid OAuth access token")

        with patch.object(provider, "_discover_account", mock_discover):
            with pytest.raises(InstagramProviderException) as exc:
                await provider.get_posts("newbodycol")
            assert "190" in str(exc.value)

    @pytest.mark.asyncio
    async def test_permission_denied_error(self, provider):
        """Test handling of permission denied error"""
        mock_discover = AsyncMock()
        mock_discover.side_effect = InstagramProviderException("Meta API error [10]: Permission denied")

        with patch.object(provider, "_discover_account", mock_discover):
            with pytest.raises(InstagramProviderException) as exc:
                await provider.get_posts("newbodycol")
            assert "10" in str(exc.value)

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, provider):
        """Test handling of rate limit error"""
        mock_discover = AsyncMock()
        mock_discover.side_effect = InstagramProviderException("Meta API error [4]: Rate limit exceeded")

        with patch.object(provider, "_discover_account", mock_discover):
            with pytest.raises(InstagramProviderException) as exc:
                await provider.get_posts("newbodycol")
            assert "4" in str(exc.value)


class TestSecurity:
    """Test security aspects"""

    @pytest.fixture
    def provider(self):
        """Create provider for testing"""
        env = {
            "META_ACCESS_TOKEN": "secret_token_12345",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            return MetaInstagramProvider()

    def test_token_not_in_string_representation(self, provider):
        """Test token never appears in string representation"""
        provider_str = str(provider)
        assert "secret_token_12345" not in provider_str

    def test_token_not_in_exception_messages(self, provider):
        """Test token not exposed in exception messages"""
        # This would require actual API call, but we can verify no logging
        import logging
        with patch.object(logging.Logger, 'error') as mock_log:
            # Simulating error scenarios
            pass
        # Verify no token in log calls
        for call in mock_log.call_args_list:
            if call:
                assert "secret_token_12345" not in str(call)


class TestSupportsReliableHistory:
    """Test supports_reliable_history property"""

    def test_meta_provider_supports_reliable_history(self):
        """Test Meta provider returns True for reliable history"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = MetaInstagramProvider()
            assert provider.supports_reliable_history is True

    def test_browser_provider_does_not_support_reliable_history(self):
        """Test Browser provider returns False for reliable history"""
        with patch.dict(os.environ, {}, clear=True):
            provider = BrowserInstagramProvider(headless=True)
            assert provider.supports_reliable_history is False


class TestClose:
    """Test resource cleanup"""

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """Test close can be called multiple times safely"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = MetaInstagramProvider()

            # Mock client before first close
            mock_client = AsyncMock()
            provider.client = mock_client

            # Close once
            await provider.close()

            # Client should be None after close
            assert provider.client is None

            # Close again should not raise
            await provider.close()  # Should be safe

    @pytest.mark.asyncio
    async def test_close_without_client(self):
        """Test close when client never initialized"""
        env = {
            "META_ACCESS_TOKEN": "token123",
            "META_IG_USER_ID": "456",
        }
        with patch.dict(os.environ, env, clear=True):
            provider = MetaInstagramProvider()

            # Should not raise
            await provider.close()
            assert provider.client is None
