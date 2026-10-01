"""Tests for Instagram provider implementations"""
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from app.domain.models import InstagramPost, PostType
from app.providers.instagram import InstaloaderInstagramProvider, MockInstagramProvider
from app.repositories.json_repo import JsonRepository
from app.domain.exceptions import (
    InvalidSessionException,
    TooManyRequestsException,
    LoginRequiredException,
    ProfileNotFoundException,
)


@pytest.mark.asyncio
async def test_mock_provider_get_posts_returns_empty_list():
    """Test MockInstagramProvider returns empty list"""
    provider = MockInstagramProvider()
    posts = await provider.get_posts("any_account")
    assert posts == []


@pytest.mark.asyncio
async def test_mock_provider_get_post_returns_none():
    """Test MockInstagramProvider returns None for single post"""
    provider = MockInstagramProvider()
    post = await provider.get_post("any_shortcode")
    assert post is None


@pytest.fixture
def mock_instaloader_post():
    """Create a mock Instaloader Post object"""
    post = MagicMock()
    post.shortcode = "ABC123DEF456"
    post.caption = "Test caption with emoji 🎉"
    post.date = datetime(2024, 10, 1, 15, 30, 0)
    post.display_url = "https://example.com/image.jpg"
    post.is_video = False
    post.is_carousel = False
    post.is_reel = False
    post.owner_username = "testaccount"
    post.get_sidecar_nodes = MagicMock(return_value=[])
    return post


@pytest.fixture
def mock_instaloader_video_post():
    """Create a mock Instaloader Video Post object"""
    post = MagicMock()
    post.shortcode = "VID123DEF456"
    post.caption = "Video test caption"
    post.date = datetime(2024, 10, 2, 10, 0, 0)
    post.display_url = "https://example.com/thumb.jpg"
    post.is_video = True
    post.is_carousel = False
    post.is_reel = False
    post.owner_username = "testaccount"
    post.get_sidecar_nodes = MagicMock(return_value=[])
    return post


@pytest.fixture
def mock_instaloader_carousel_post():
    """Create a mock Instaloader Carousel Post object"""
    post = MagicMock()
    post.shortcode = "CAR123DEF456"
    post.caption = "Carousel caption"
    post.date = datetime(2024, 10, 3, 12, 0, 0)
    post.display_url = "https://example.com/thumb.jpg"
    post.is_video = False
    post.is_carousel = True
    post.is_reel = False
    post.owner_username = "testaccount"
    post.get_sidecar_nodes = MagicMock(return_value=[Mock(), Mock(), Mock()])
    return post


@pytest.mark.asyncio
async def test_instaloader_provider_transforms_photo_post(mock_instaloader_post):
    """Test transformation of a photo post from Instaloader"""
    with patch("app.providers.instagram.InstaloaderInstagramProvider.__init__", return_value=None):
        provider = InstaloaderInstagramProvider()
        provider.loader = MagicMock()

        post = provider._transform_post(mock_instaloader_post, "testaccount")

        assert isinstance(post, InstagramPost)
        assert post.shortcode == "ABC123DEF456"
        assert post.username == "testaccount"
        assert post.caption == "Test caption with emoji 🎉"
        assert post.post_type == PostType.PHOTO
        assert post.published_at == datetime(2024, 10, 1, 15, 30, 0)
        assert post.permalink == "https://www.instagram.com/p/ABC123DEF456/"
        assert post.thumbnail_url == "https://example.com/image.jpg"
        assert post.is_video is False
        assert post.media_count == 1


@pytest.mark.asyncio
async def test_instaloader_provider_transforms_video_post(mock_instaloader_video_post):
    """Test transformation of a video post from Instaloader"""
    with patch("app.providers.instagram.InstaloaderInstagramProvider.__init__", return_value=None):
        provider = InstaloaderInstagramProvider()
        provider.loader = MagicMock()

        post = provider._transform_post(mock_instaloader_video_post, "testaccount")

        assert post.shortcode == "VID123DEF456"
        assert post.post_type == PostType.VIDEO
        assert post.permalink == "https://www.instagram.com/p/VID123DEF456/"
        assert post.is_video is True


@pytest.mark.asyncio
async def test_instaloader_provider_transforms_carousel_post(mock_instaloader_carousel_post):
    """Test transformation of a carousel post from Instaloader"""
    with patch("app.providers.instagram.InstaloaderInstagramProvider.__init__", return_value=None):
        provider = InstaloaderInstagramProvider()
        provider.loader = MagicMock()

        post = provider._transform_post(mock_instaloader_carousel_post, "testaccount")

        assert post.shortcode == "CAR123DEF456"
        assert post.post_type == PostType.CAROUSEL
        assert post.is_video is False
        assert post.media_count == 3


@pytest.mark.asyncio
async def test_instaloader_provider_handles_reel_post():
    """Test transformation of a reel post"""
    reel_post = MagicMock()
    reel_post.shortcode = "REEL123DEF456"
    reel_post.caption = "Reel caption"
    reel_post.date = datetime(2024, 10, 4, 8, 0, 0)
    reel_post.display_url = "https://example.com/thumb.jpg"
    reel_post.is_video = True
    reel_post.is_carousel = False
    reel_post.is_reel = True
    reel_post.owner_username = "testaccount"
    reel_post.get_sidecar_nodes = MagicMock(return_value=[])

    with patch("app.providers.instagram.InstaloaderInstagramProvider.__init__", return_value=None):
        provider = InstaloaderInstagramProvider()
        provider.loader = MagicMock()

        post = provider._transform_post(reel_post, "testaccount")

        assert post.post_type == PostType.REEL
        assert post.permalink == "https://www.instagram.com/reel/REEL123DEF456/"


@pytest.mark.asyncio
async def test_instaloader_provider_get_posts_respects_limit():
    """Test get_posts respects the limit parameter"""
    with patch("app.providers.instagram.InstaloaderInstagramProvider.__init__", return_value=None):
        provider = InstaloaderInstagramProvider()

        # Create mock posts
        mock_posts = []
        for i in range(10):
            post = MagicMock()
            post.shortcode = f"POST{i:03d}"
            post.caption = f"Caption {i}"
            post.date = datetime(2024, 10, 1 + i, 0, 0)
            post.display_url = f"https://example.com/img{i}.jpg"
            post.is_video = False
            post.is_carousel = False
            post.is_reel = False
            post.owner_username = "testaccount"
            post.get_sidecar_nodes = MagicMock(return_value=[])
            mock_posts.append(post)

        mock_profile = MagicMock()
        mock_profile.get_posts = MagicMock(return_value=iter(mock_posts))

        # Setup mock instaloader module
        mock_instaloader = MagicMock()
        mock_instaloader.Profile.from_username = MagicMock(return_value=mock_profile)

        provider.instaloader = mock_instaloader
        provider.loader = MagicMock()

        posts = await provider.get_posts("testaccount", limit=5)

        assert len(posts) == 5
        for i, post in enumerate(posts):
            assert post.shortcode == f"POST{i:03d}"


@pytest.mark.asyncio
async def test_instaloader_provider_handles_missing_caption():
    """Test handling of posts without captions"""
    with patch("app.providers.instagram.InstaloaderInstagramProvider.__init__", return_value=None):
        provider = InstaloaderInstagramProvider()
        provider.loader = MagicMock()

        post = MagicMock()
        post.shortcode = "NOCAP123"
        post.caption = None
        post.date = datetime(2024, 10, 1, 0, 0, 0)
        post.display_url = "https://example.com/img.jpg"
        post.is_video = False
        post.is_carousel = False
        post.is_reel = False
        post.owner_username = "testaccount"
        post.get_sidecar_nodes = MagicMock(return_value=[])

        result = provider._transform_post(post, "testaccount")

        assert result.caption == ""
        assert result.shortcode == "NOCAP123"


@pytest.mark.asyncio
async def test_instaloader_provider_error_handling():
    """Test error handling when fetching posts"""
    with patch("app.providers.instagram.InstaloaderInstagramProvider.__init__", return_value=None):
        provider = InstaloaderInstagramProvider()
        provider.loader = MagicMock()
        provider.loader.get_profile.side_effect = Exception("Private account")

        with pytest.raises(Exception):
            await provider.get_posts("privateaccount")


def test_json_repository_saves_posts(tmp_path):
    """Test persisting posts to JSON"""
    repo = JsonRepository(data_dir=str(tmp_path))

    data = {
        "username": "testaccount",
        "posts": [
            {
                "shortcode": "ABC123",
                "username": "testaccount",
                "caption": "Test 🎉",
                "post_type": "photo",
                "published_at": "2024-10-01T15:30:00",
                "permalink": "https://www.instagram.com/p/ABC123/",
                "thumbnail_url": "https://example.com/img.jpg",
                "is_video": False,
                "media_count": 1,
            }
        ]
    }

    repo.save("testaccount_posts", data)

    loaded = repo.load("testaccount_posts")
    assert loaded is not None
    assert loaded["username"] == "testaccount"
    assert len(loaded["posts"]) == 1
    assert loaded["posts"][0]["caption"] == "Test 🎉"


def test_json_repository_handles_unicode(tmp_path):
    """Test that JSON repository preserves Unicode and emojis"""
    repo = JsonRepository(data_dir=str(tmp_path))

    data = {
        "posts": [
            {
                "shortcode": "TEST",
                "caption": "Hola 👋 Spanish text ñ ü",
                "post_type": "photo",
            }
        ]
    }

    repo.save("unicode_test", data)
    loaded = repo.load("unicode_test")

    assert "👋" in loaded["posts"][0]["caption"]
    assert "ñ" in loaded["posts"][0]["caption"]

@pytest.mark.asyncio
async def test_provider_without_session():
    """Test provider initialization without session"""
    with patch("app.providers.instagram.InstaloaderInstagramProvider.__init__", return_value=None):
        provider = InstaloaderInstagramProvider()
        provider._session_username = None
        provider._session_file = None
        provider.loader = MagicMock()
        provider.instaloader = MagicMock()

        assert provider._session_username is None
        assert provider._session_file is None


@pytest.mark.asyncio
async def test_provider_with_invalid_session(tmp_path):
    """Test provider with non-existent session file"""
    with patch("app.providers.instagram.InstaloaderInstagramProvider.__init__", return_value=None):
        provider = InstaloaderInstagramProvider()
        provider._session_username = "testuser"
        provider._session_file = tmp_path / "nonexistent.session"
        provider.loader = MagicMock()
        
        with pytest.raises(InvalidSessionException):
            provider._load_session()


def test_json_repository_saves_authenticated_posts(tmp_path):
    """Test that repository saves authentication status"""
    repo = JsonRepository(data_dir=str(tmp_path))
    
    data = {
        "username": "testaccount",
        "authenticated": True,
        "posts": [
            {
                "shortcode": "ABC123",
                "username": "testaccount",
                "caption": "Authenticated post",
                "post_type": "photo",
                "published_at": "2024-10-01T15:30:00",
                "permalink": "https://www.instagram.com/p/ABC123/",
                "thumbnail_url": "https://example.com/img.jpg",
                "is_video": False,
                "media_count": 1,
            }
        ]
    }
    
    repo.save("authenticated_test", data)
    loaded = repo.load("authenticated_test")
    
    assert loaded["authenticated"] is True
    assert len(loaded["posts"]) == 1


@pytest.mark.asyncio
async def test_load_session_with_valid_login(tmp_path):
    """Test loading session with valid test_login() result"""
    with patch("app.providers.instagram.InstaloaderInstagramProvider.__init__", return_value=None):
        provider = InstaloaderInstagramProvider()
        session_file = tmp_path / "test.session"
        session_file.write_text("")

        provider._session_username = "testuser"
        provider._session_file = session_file
        provider.loader = MagicMock()

        provider.loader.load_session_from_file = MagicMock()
        provider.loader.test_login = MagicMock(return_value="testuser")

        provider._load_session()

        provider.loader.load_session_from_file.assert_called_once_with("testuser", session_file)
        provider.loader.test_login.assert_called_once()


@pytest.mark.asyncio
async def test_load_session_with_invalid_login(tmp_path):
    """Test loading session when test_login() returns None"""
    with patch("app.providers.instagram.InstaloaderInstagramProvider.__init__", return_value=None):
        provider = InstaloaderInstagramProvider()
        provider._session_username = "testuser"
        session_file = tmp_path / "test.session"
        session_file.write_text("")
        provider._session_file = session_file
        provider.loader = MagicMock()
        
        provider.loader.load_session_from_file = MagicMock()
        provider.loader.test_login = MagicMock(return_value=None)
        
        with pytest.raises(InvalidSessionException) as exc_info:
            provider._load_session()
        
        assert "invalid or expired" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_load_session_username_mismatch(tmp_path):
    """Test loading session when logged-in user differs from expected"""
    with patch("app.providers.instagram.InstaloaderInstagramProvider.__init__", return_value=None):
        provider = InstaloaderInstagramProvider()
        provider._session_username = "expecteduser"
        session_file = tmp_path / "test.session"
        session_file.write_text("")
        provider._session_file = session_file
        provider.loader = MagicMock()
        
        provider.loader.load_session_from_file = MagicMock()
        provider.loader.test_login = MagicMock(return_value="differentuser")
        
        provider._load_session()
        
        provider.loader.load_session_from_file.assert_called_once()
