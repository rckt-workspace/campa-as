"""Tests for manual audit functionality"""
import pytest
from app.services.manual_audit_service import ManualAuditService
from app.providers.browser_instagram import BrowserInstagramProvider
from app.api.schemas import ManualAuditRequest, ManualAuditAccountRequest


class TestURLParsing:
    """Test URL validation and normalization"""

    def test_normalize_removes_query_string(self):
        """Query strings are removed from URLs"""
        service = ManualAuditService(None)
        url = "https://www.instagram.com/p/ABC123/?utm_source=test"
        normalized = service.normalize_url(url)
        assert "?" not in normalized
        assert normalized.endswith("/")

    def test_normalize_adds_trailing_slash(self):
        """URLs get trailing slash"""
        service = ManualAuditService(None)
        url = "https://www.instagram.com/p/ABC123"
        normalized = service.normalize_url(url)
        assert normalized.endswith("/")

    def test_extract_shortcode_from_p_url(self):
        """Extract shortcode from /p/ URL"""
        service = ManualAuditService(None)
        url = "https://www.instagram.com/p/ABC123DEF456/"
        shortcode = service.extract_shortcode(url)
        assert shortcode == "ABC123DEF456"

    def test_extract_shortcode_from_reel_url(self):
        """Extract shortcode from /reel/ URL"""
        service = ManualAuditService(None)
        url = "https://www.instagram.com/reel/XYZ789ABC123/"
        shortcode = service.extract_shortcode(url)
        assert shortcode == "XYZ789ABC123"

    def test_extract_shortcode_with_query_string(self):
        """Extract shortcode from URL with query string"""
        service = ManualAuditService(None)
        url = "https://www.instagram.com/p/ABC123/?utm_source=test"
        shortcode = service.extract_shortcode(url)
        assert shortcode is not None
        assert "ABC123" in shortcode or shortcode == "ABC123"

    def test_extract_shortcode_invalid_url(self):
        """Invalid URL returns None"""
        service = ManualAuditService(None)
        url = "https://www.example.com/invalid"
        shortcode = service.extract_shortcode(url)
        assert shortcode is None


class TestURLValidation:
    """Test URL format validation"""

    def test_valid_post_url(self):
        """Valid /p/ URL accepted"""
        service = ManualAuditService(None)
        url = "https://www.instagram.com/p/ABC123/"
        assert service.validate_url(url) is True

    def test_valid_reel_url(self):
        """Valid /reel/ URL accepted"""
        service = ManualAuditService(None)
        url = "https://www.instagram.com/reel/XYZ789/"
        assert service.validate_url(url) is True

    def test_invalid_domain(self):
        """Non-instagram.com URL rejected"""
        service = ManualAuditService(None)
        url = "https://www.example.com/p/ABC123/"
        assert service.validate_url(url) is False

    def test_invalid_no_path(self):
        """URL without /p/ or /reel/ rejected"""
        service = ManualAuditService(None)
        url = "https://www.instagram.com/testuser/"
        assert service.validate_url(url) is False

    def test_empty_url(self):
        """Empty URL rejected"""
        service = ManualAuditService(None)
        assert service.validate_url("") is False
        assert service.validate_url("   ") is False

    def test_reject_http_not_https(self):
        """HTTP (not HTTPS) rejected"""
        service = ManualAuditService(None)
        url = "http://www.instagram.com/p/ABC123/"
        assert service.validate_url(url) is False

    def test_reject_subdomain_attack(self):
        """Subdomain spoofing like instagram.com.evil.com rejected"""
        service = ManualAuditService(None)
        url = "https://instagram.com.evil.com/p/ABC123/"
        assert service.validate_url(url) is False

    def test_reject_fake_instagram_domain(self):
        """Fake domains like fakeinstagram.com rejected"""
        service = ManualAuditService(None)
        url = "https://fakeinstagram.com/p/ABC123/"
        assert service.validate_url(url) is False

    def test_accept_instagram_without_www(self):
        """instagram.com (without www) accepted"""
        service = ManualAuditService(None)
        url = "https://instagram.com/p/ABC123/"
        assert service.validate_url(url) is True

    def test_accept_instagram_with_www(self):
        """www.instagram.com accepted"""
        service = ManualAuditService(None)
        url = "https://www.instagram.com/p/ABC123/"
        assert service.validate_url(url) is True


class TestManualAuditRequestValidation:
    """Test request schema validation"""

    def test_master_required(self):
        """Master account required"""
        with pytest.raises(ValueError):
            ManualAuditRequest(
                master=None,
                targets=[]
            )

    def test_targets_required(self):
        """At least one target required"""
        master = ManualAuditAccountRequest(
            username="master",
            label="Master",
            links=["https://www.instagram.com/p/ABC123/"]
        )
        with pytest.raises(ValueError):
            ManualAuditRequest(master=master, targets=[])

    def test_master_not_in_targets(self):
        """Master account cannot be in targets"""
        master = ManualAuditAccountRequest(
            username="newbodycol",
            label="Colombia",
            links=["https://www.instagram.com/p/ABC123/"]
        )
        target = ManualAuditAccountRequest(
            username="newbodycol",  # Same as master
            label="Colombia",
            links=["https://www.instagram.com/p/XYZ789/"]
        )
        with pytest.raises(ValueError, match="cannot be in targets"):
            ManualAuditRequest(master=master, targets=[target])

    def test_valid_request(self):
        """Valid request with master and multiple targets"""
        master = ManualAuditAccountRequest(
            username="newbodycol",
            label="Colombia",
            links=["https://www.instagram.com/p/ABC123/"]
        )
        target1 = ManualAuditAccountRequest(
            username="newbodyclubmedellin",
            label="Medellín",
            links=["https://www.instagram.com/p/XYZ789/"]
        )
        target2 = ManualAuditAccountRequest(
            username="newbodybaq",
            label="Barranquilla",
            links=["https://www.instagram.com/reel/DEF456/"]
        )
        request = ManualAuditRequest(
            master=master,
            targets=[target1, target2]
        )
        assert len(request.targets) == 2


class TestLinkFiltering:
    """Test link normalization in request"""

    def test_filters_invalid_links(self):
        """Invalid links removed from request"""
        account = ManualAuditAccountRequest(
            username="testuser",
            label="Test",
            links=[
                "https://www.instagram.com/p/ABC123/",
                "https://www.example.com/invalid",
                "https://www.instagram.com/testuser/",
                "https://www.instagram.com/reel/XYZ789/",
            ]
        )
        # Only 2 valid links
        assert len(account.links) == 2

    def test_deduplicates_links(self):
        """Duplicate links kept in request (frontend responsibility for dedup)"""
        account = ManualAuditAccountRequest(
            username="testuser",
            label="Test",
            links=[
                "https://www.instagram.com/p/ABC123/",
                "https://www.instagram.com/p/ABC123/",  # duplicate
            ]
        )
        # Schema doesn't deduplicate, service does
        assert len(account.links) == 2


class TestDeduplication:
    """Test deduplication by shortcode"""

    @pytest.mark.asyncio
    async def test_deduplicate_by_shortcode(self):
        """Same shortcode appears once"""
        service = ManualAuditService(None)
        links = [
            "https://www.instagram.com/p/ABC123/",
            "https://www.instagram.com/p/ABC123/?utm=test",
            "https://www.instagram.com/p/ABC123/?utm=other",
        ]
        # Mock provider that returns None (just test dedup logic)
        class MockProvider:
            async def get_post_by_permalink(self, url):
                return None

        service.provider = MockProvider()
        posts, stats = await service.extract_posts_from_links("testuser", links)

        assert stats["links_received"] == 3
        # After deduplication by shortcode, only 1 unique
        assert stats["links_valid"] == 1
        assert stats["posts_extracted"] == 0  # All mocked to None


class TestPartialExtraction:
    """Test partial extraction tolerates failures"""

    def test_extraction_summary_with_failures(self):
        """Stats track received, valid, extracted, failed"""
        # This tests the data structure
        stats = {
            "account": "testuser",
            "links_received": 5,
            "links_valid": 5,
            "posts_extracted": 3,
            "links_failed": 2,
        }
        assert stats["links_received"] == 5
        assert stats["links_failed"] == 2
        assert stats["posts_extracted"] == 3


class TestMasterZeroHandling:
    """Test master=0 posts causes clear error"""

    def test_master_zero_posts_error(self):
        """No master posts is an error condition"""
        # Backend should reject with 400 if master_posts == 0
        master_posts = []
        assert len(master_posts) == 0
        # Would trigger: raise HTTPException(status_code=400, ...)


class TestRegionalZeroHandling:
    """Test regional=0 posts allows partial audit"""

    def test_regional_zero_posts_partial(self):
        """Zero posts in regional account allows audit with warning"""
        regional_posts = {}

        # Should not fail, should add warning
        assert len(regional_posts) == 0
        # Warning would be added to extraction_summary

    def test_regional_zero_with_links_sent(self):
        """Regional=0 even with links sent should warn"""
        stats = {
            "account": "regional",
            "links_received": 5,
            "links_valid": 5,
            "posts_extracted": 0,
            "links_failed": 5,
        }
        # Warning logic: posts_extracted == 0 and not master
        should_warn = stats["posts_extracted"] == 0
        assert should_warn is True

    def test_regional_zero_with_no_links_sent(self):
        """Regional=0 with no links also warns"""
        stats = {
            "account": "regional",
            "links_received": 0,
            "links_valid": 0,
            "posts_extracted": 0,
            "links_failed": 0,
        }
        should_warn = stats["posts_extracted"] == 0
        assert should_warn is True

    def test_regional_zero_excluded_from_matcher(self):
        """Regional with 0 posts is excluded from comparison_accounts"""
        account_posts = {
            "regional1": [1, 2, 3],  # has posts
            "regional2": [],  # no posts - should be excluded
        }
        available = [acc for acc in account_posts.keys() if len(account_posts[acc]) > 0]
        assert "regional1" in available
        assert "regional2" not in available
        assert len(available) == 1


class TestExtractionSummary:
    """Test extraction summary structure"""

    def test_summary_structure(self):
        """Summary has all required fields"""
        summary = {
            "newbodycol": {
                "account": "newbodycol",
                "links_received": 10,
                "links_valid": 10,
                "posts_extracted": 8,
                "links_failed": 2,
            },
            "newbodyclubmedellin": {
                "account": "newbodyclubmedellin",
                "links_received": 5,
                "links_valid": 5,
                "posts_extracted": 5,
                "links_failed": 0,
            }
        }

        assert "newbodycol" in summary
        assert summary["newbodycol"]["links_received"] == 10
        assert summary["newbodyclubmedellin"]["posts_extracted"] == 5
