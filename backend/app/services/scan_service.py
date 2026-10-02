"""Service for orchestrating content scans across Instagram accounts"""
import logging
from datetime import datetime
from dataclasses import dataclass

from app.config import AccountConfig, ScanConfig
from app.domain.models import InstagramPost, AuditResult
from app.providers.instagram import InstagramProvider, InstaloaderInstagramProvider
from app.cache.media_cache import MediaCache
from app.services.audit_service import AuditService
from app.domain.matcher import PerceptualContentMatcher
from app.exporters.excel_exporter import ExcelExporter

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Result of a content scan"""
    master_account: str
    comparison_accounts: list[str]
    master_posts_count: int
    regional_posts_count: dict[str, int]
    audit_result: AuditResult
    excel_path: str
    started_at: datetime
    completed_at: datetime

    def summary(self) -> str:
        """Generate summary text"""
        duration = (self.completed_at - self.started_at).total_seconds()
        lines = [
            f"Scan completed in {duration:.1f}s",
            f"Master posts: {self.master_posts_count}",
            f"Found everywhere: {self.audit_result.found_in_all}",
            f"With missing accounts: {self.audit_result.with_missing}",
            f"With review needed: {self.audit_result.with_review}",
            "",
            "Missing by account:",
        ]

        for account, count in self.audit_result.missing_count_by_account.items():
            lines.append(f"  {account}: {count}")

        lines.extend(["", "Review needed by account:"])
        for account, count in self.audit_result.review_count_by_account.items():
            lines.append(f"  {account}: {count}")

        lines.append(f"\nExcel: {self.excel_path}")

        return "\n".join(lines)


class ScanService:
    """Orchestrates Instagram content audit scans"""

    def __init__(
        self,
        provider: InstagramProvider = None,
        account_config: AccountConfig = None,
        scan_config: ScanConfig = None,
    ):
        self.provider = provider
        self.account_config = account_config or AccountConfig()
        self.scan_config = scan_config or ScanConfig()
        self.media_cache = MediaCache(
            cache_dir=self.scan_config.media_cache_dir,
            timeout=self.scan_config.media_timeout,
        )
        self.audit_service = AuditService(matcher=PerceptualContentMatcher())
        self.excel_exporter = ExcelExporter()

    async def scan(self, output_dir: str = "data/exports") -> ScanResult:
        """
        Execute a complete content audit scan.

        Returns:
            ScanResult with audit outcomes and Excel path
        """
        started_at = datetime.now()
        logger.info("Starting content audit scan")

        # Fetch master posts
        logger.info(f"Fetching posts from master account: {self.account_config.master_account}")
        master_posts = await self.provider.get_posts(
            self.account_config.master_account,
            limit=self.scan_config.master_limit,
        )
        logger.info(f"Fetched {len(master_posts)} master posts")

        # Prepare master posts with local thumbnails
        master_posts = await self._prepare_posts(master_posts)

        # Fetch regional posts
        account_posts = {}
        for account in self.account_config.comparison_accounts:
            logger.info(f"Fetching posts from regional account: {account}")
            posts = await self.provider.get_posts(
                account,
                limit=self.scan_config.regional_limit,
            )
            logger.info(f"Fetched {len(posts)} posts from {account}")

            # Prepare with local thumbnails
            posts = await self._prepare_posts(posts)
            account_posts[account] = posts

        # Run audit
        logger.info("Running content audit comparison")
        audit_result = self.audit_service.audit_accounts(
            master_posts=master_posts,
            account_posts=account_posts,
            master_account=self.account_config.master_account,
        )

        # Export to Excel
        logger.info("Generating Excel report")
        excel_path = self.excel_exporter.export(audit_result, output_dir)

        completed_at = datetime.now()

        result = ScanResult(
            master_account=self.account_config.master_account,
            comparison_accounts=self.account_config.comparison_accounts,
            master_posts_count=len(master_posts),
            regional_posts_count={
                account: len(posts)
                for account, posts in account_posts.items()
            },
            audit_result=audit_result,
            excel_path=str(excel_path),
            started_at=started_at,
            completed_at=completed_at,
        )

        logger.info("Scan completed successfully")
        return result

    async def _prepare_posts(self, posts: list[InstagramPost]) -> list[InstagramPost]:
        """Prepare posts by downloading thumbnails locally"""
        # Set up media_cache fallback if provider has fetch_media
        if hasattr(self.provider, 'fetch_media'):
            self.media_cache.media_fetcher = self.provider.fetch_media

        prepared = []

        for post in posts:
            # Download thumbnail to local cache
            local_path = await self.media_cache.get_local_thumbnail(
                username=post.username,
                shortcode=post.shortcode,
                thumbnail_url=post.thumbnail_url,
            )

            # Update post with local path (or None if download failed)
            prepared_post = InstagramPost(
                shortcode=post.shortcode,
                username=post.username,
                caption=post.caption,
                post_type=post.post_type,
                published_at=post.published_at,
                permalink=post.permalink,
                thumbnail_url=str(local_path) if local_path else None,
                is_video=post.is_video,
                media_count=post.media_count,
            )
            prepared.append(prepared_post)

        return prepared
