"""Service for orchestrating content scans across Instagram accounts"""
import logging
import asyncio
from datetime import datetime, date
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable

from app.config import AccountConfig, ScanConfig
from app.domain.models import InstagramPost, AuditResult, AccountScanProgress
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
    warnings: list[str] = None
    coverage_by_account: dict = None  # AccountScanProgress summary per account

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.coverage_by_account is None:
            self.coverage_by_account = {}

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
        progress_callback: Optional[Callable[[str, int, str], Awaitable[None]]] = None,
    ):
        self.provider = provider
        self.account_config = account_config or AccountConfig()
        self.scan_config = scan_config or ScanConfig()
        self.progress_callback = progress_callback
        self.media_cache = MediaCache(
            cache_dir=self.scan_config.media_cache_dir,
            timeout=self.scan_config.media_timeout,
        )
        self.audit_service = AuditService(matcher=PerceptualContentMatcher())
        self.excel_exporter = ExcelExporter()

    async def _report_progress(self, stage: str, progress: int, message: str):
        """Report progress via callback if available"""
        if self.progress_callback:
            try:
                await self.progress_callback(stage, progress, message)
            except Exception as e:
                logger.warning(f"Error in progress callback: {e}")

    async def scan(self, output_dir: str = "data/exports") -> ScanResult:
        """
        Execute a complete content audit scan.

        Returns:
            ScanResult with audit outcomes and Excel path
        """
        started_at = datetime.now()
        logger.info("Starting content audit scan")

        warnings = []
        coverage_by_account = {}
        is_date_mode = self.scan_config.from_date is not None

        # Fetch master posts
        logger.info(f"Fetching posts from master account: {self.account_config.master_account}")
        if is_date_mode:
            if self.provider.supports_native_pagination:
                # Provider has native pagination (Meta): single call with date range
                logger.info("Provider supports native pagination; using direct date range fetch")
                master_posts = await self.provider.get_posts(
                    self.account_config.master_account,
                    limit=None,
                    from_date=self.scan_config.from_date,
                    to_date=self.scan_config.to_date,
                )
                # Get metadata
                if hasattr(self.provider, 'fetch_metadata_by_account'):
                    master_metadata = self.provider.fetch_metadata_by_account.get(
                        self.account_config.master_account
                    )
                    if master_metadata:
                        coverage_by_account[self.account_config.master_account] = {
                            "label": self.account_config.account_labels.get(self.account_config.master_account, self.account_config.master_account),
                            "discovered_unique_posts": master_metadata.discovered_links,
                            "completed": master_metadata.completed,
                            "stop_reason": master_metadata.stop_reason,
                            "warning": master_metadata.warning,
                        }
                        if master_metadata.warning:
                            warnings.append(f"{self.account_config.master_account}: {master_metadata.warning}")
            else:
                # Browser provider: use batch retry
                master_posts, master_progress = await self._batch_fetch_posts_date_mode(
                    self.account_config.master_account,
                    self.scan_config.from_date,
                    self.scan_config.to_date,
                )
                if master_progress.warnings:
                    warnings.extend(master_progress.warnings)
                # Save coverage info
                coverage_by_account[self.account_config.master_account] = {
                    "label": self.account_config.account_labels.get(self.account_config.master_account, self.account_config.master_account),
                    "discovered_unique_posts": master_progress.total_unique_posts,
                    "batches_attempted": master_progress.batches_attempted,
                    "no_progress_attempts": master_progress.no_progress_attempts,
                    "min_date_found": master_progress.min_date_found.isoformat() if master_progress.min_date_found else None,
                    "max_date_found": master_progress.max_date_found.isoformat() if master_progress.max_date_found else None,
                    "completed": master_progress.completed,
                    "stop_reason": master_progress.stop_reason,
                }
        else:
            # Count mode: simple fetch (all providers handle same way)
            master_posts = await self.provider.get_posts(
                self.account_config.master_account,
                limit=self.scan_config.master_limit,
                from_date=self.scan_config.from_date,
                to_date=self.scan_config.to_date,
            )
            # Collect warnings from simple fetch
            if hasattr(self.provider, 'fetch_metadata_by_account'):
                master_metadata = self.provider.fetch_metadata_by_account.get(
                    self.account_config.master_account
                )
                if master_metadata and master_metadata.warning:
                    warnings.append(f"{self.account_config.master_account}: {master_metadata.warning}")

        logger.info(f"Fetched {len(master_posts)} master posts")
        await self._report_progress("downloading_media", 40, "Descargando recursos visuales del maestro...")

        # Prepare master posts with local thumbnails
        master_posts = await self._prepare_posts(master_posts)

        # Fetch regional posts
        account_posts = {}
        total_regional = len(self.account_config.comparison_accounts)
        for idx, account in enumerate(self.account_config.comparison_accounts):
            logger.info(f"Fetching posts from regional account: {account}")
            if is_date_mode:
                if self.provider.supports_native_pagination:
                    # Provider has native pagination (Meta): single call with date range
                    posts = await self.provider.get_posts(
                        account,
                        limit=None,
                        from_date=self.scan_config.from_date,
                        to_date=self.scan_config.to_date,
                    )
                    # Get metadata
                    if hasattr(self.provider, 'fetch_metadata_by_account'):
                        regional_metadata = self.provider.fetch_metadata_by_account.get(account)
                        if regional_metadata:
                            coverage_by_account[account] = {
                                "label": self.account_config.account_labels.get(account, account),
                                "discovered_unique_posts": regional_metadata.discovered_links,
                                "completed": regional_metadata.completed,
                                "stop_reason": regional_metadata.stop_reason,
                                "warning": regional_metadata.warning,
                            }
                            if regional_metadata.warning:
                                warnings.append(f"{account}: {regional_metadata.warning}")
                else:
                    # Browser provider: use batch retry
                    posts, regional_progress = await self._batch_fetch_posts_date_mode(
                        account,
                        self.scan_config.from_date,
                        self.scan_config.to_date,
                    )
                    if regional_progress.warnings:
                        warnings.extend(regional_progress.warnings)
                    # Save coverage info
                    coverage_by_account[account] = {
                        "label": self.account_config.account_labels.get(account, account),
                        "discovered_unique_posts": regional_progress.total_unique_posts,
                        "batches_attempted": regional_progress.batches_attempted,
                        "no_progress_attempts": regional_progress.no_progress_attempts,
                        "min_date_found": regional_progress.min_date_found.isoformat() if regional_progress.min_date_found else None,
                        "max_date_found": regional_progress.max_date_found.isoformat() if regional_progress.max_date_found else None,
                        "completed": regional_progress.completed,
                        "stop_reason": regional_progress.stop_reason,
                    }
            else:
                # Count mode: simple fetch (all providers handle same way)
                posts = await self.provider.get_posts(
                    account,
                    limit=self.scan_config.regional_limit,
                    from_date=self.scan_config.from_date,
                    to_date=self.scan_config.to_date,
                )
                # Collect warnings
                if hasattr(self.provider, 'fetch_metadata_by_account'):
                    regional_metadata = self.provider.fetch_metadata_by_account.get(account)
                    if regional_metadata and regional_metadata.warning:
                        warnings.append(f"{account}: {regional_metadata.warning}")

            logger.info(f"Fetched {len(posts)} posts from {account}")

            # Prepare with local thumbnails
            posts = await self._prepare_posts(posts)
            account_posts[account] = posts

            # Update progress
            progress = 40 + int((idx + 1) / total_regional * 20)
            await self._report_progress("downloading_media", progress, f"Descargando recursos de {account}...")

        # Run audit
        logger.info("Running content audit comparison")
        await self._report_progress("matching", 60, "Comparando contenido...")

        audit_result = await asyncio.to_thread(
            self.audit_service.audit_accounts,
            master_posts,
            account_posts,
            self.account_config.master_account,
        )

        # Export to Excel
        logger.info("Generating Excel report")
        await self._report_progress("exporting", 90, "Generando Excel...")

        excel_path = await asyncio.to_thread(
            self.excel_exporter.export,
            audit_result,
            output_dir,
            self.account_config.account_labels,
        )

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
            warnings=warnings,
            coverage_by_account=coverage_by_account,
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

    async def _batch_fetch_posts_date_mode(
        self, account: str, from_date: date, to_date: date
    ) -> tuple[list[InstagramPost], AccountScanProgress]:
        """
        Fetch posts for a single account in date mode with batch retries.

        Returns:
            (posts, progress)
        """
        MAX_BATCH_ATTEMPTS = 4
        MAX_NO_PROGRESS_ATTEMPTS = 2

        progress = AccountScanProgress(
            account=account,
            requested_from_date=from_date,
            requested_to_date=to_date,
        )

        for batch_index in range(MAX_BATCH_ATTEMPTS):
            # Reset context for clean batch attempt (except first)
            if batch_index > 0:
                if hasattr(self.provider, 'reset_public_context'):
                    await self.provider.reset_public_context()

            logger.info(f"@{account} batch={batch_index + 1} starting")

            try:
                # Fetch posts for this batch
                batch_posts = await self.provider.get_posts(
                    account,
                    limit=None,
                    from_date=from_date,
                    to_date=to_date,
                )

                # Identify new posts by shortcode
                new_posts = [
                    p for p in batch_posts
                    if p.shortcode not in progress.discovered_unique_shortcodes
                ]

                # Update progress
                for post in new_posts:
                    progress.discovered_unique_shortcodes.add(post.shortcode)
                    progress.discovered_posts.append(post)
                    if progress.min_date_found is None or post.published_at.date() < progress.min_date_found:
                        progress.min_date_found = post.published_at.date()
                    if progress.max_date_found is None or post.published_at.date() > progress.max_date_found:
                        progress.max_date_found = post.published_at.date()

                progress.total_unique_posts = len(progress.discovered_unique_shortcodes)
                progress.batches_attempted += 1

                # Check for progress
                if len(new_posts) > 0:
                    progress.no_progress_attempts = 0
                else:
                    progress.no_progress_attempts += 1

                logger.info(
                    f"@{account} batch={batch_index + 1} "
                    f"unique_total={progress.total_unique_posts} new_unique={len(new_posts)}"
                )

                # Check stopping criteria
                if progress.no_progress_attempts >= MAX_NO_PROGRESS_ATTEMPTS:
                    progress.stop_reason = "public_history_limit"
                    progress.completed = False
                    progress.warnings.append(
                        "Instagram dejó de entregar publicaciones públicas nuevas "
                        "después de varios intentos. No fue posible confirmar "
                        "todo el período solicitado."
                    )
                    logger.info(
                        f"@{account} batch scan finished: "
                        f"unique={progress.total_unique_posts} "
                        f"batches={progress.batches_attempted} "
                        f"completed={progress.completed} reason={progress.stop_reason}"
                    )
                    break

            except Exception as e:
                logger.warning(f"Batch {batch_index + 1} failed for @{account}: {e}")
                progress.no_progress_attempts += 1
                if progress.no_progress_attempts >= MAX_NO_PROGRESS_ATTEMPTS:
                    progress.stop_reason = "fetch_error"
                    break

        return progress.discovered_posts, progress
