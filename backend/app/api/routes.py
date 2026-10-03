import asyncio
import logging
import os
from uuid import uuid4
from pathlib import Path
from fastapi import APIRouter, HTTPException
from starlette.responses import FileResponse
from app.api.schemas import (
    HealthResponse, ScanRequest, ScanResponse, ErrorResponse,
    PostResultResponse, AccountMatchResponse, ManualLinkRequest, ManualLinkResponse,
    ManualAuditRequest, ManualAuditResponse
)
from app.config import AccountConfig, ScanConfig
from app.providers.browser_instagram import BrowserInstagramProvider
from app.services.scan_service import ScanService
from app.services.manual_audit_service import ManualAuditService
from app.domain.exceptions import InstagramProviderException
from app.utils import clean_caption

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["scans"])

# In-memory scan tracking
_scan_results: dict[str, Path] = {}
_scan_lock = asyncio.Lock()
_active_scan = False


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="ok", service="newbody-content-auditor")


@router.post("/scans", response_model=ScanResponse, status_code=200)
async def run_scan(request: ScanRequest):
    """Run a content audit scan"""
    global _active_scan

    async with _scan_lock:
        if _active_scan:
            raise HTTPException(
                status_code=409,
                detail="Ya hay una auditoría en ejecución. Espera a que termine.",
            )
        _active_scan = True

    provider = None
    try:
        headless = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
        provider = BrowserInstagramProvider(headless=headless)

        account_labels = {request.master_username: request.master_label}
        for target in request.targets:
            account_labels[target.username] = target.label

        account_config = AccountConfig(
            master_account=request.master_username,
            comparison_accounts=[t.username for t in request.targets],
            account_labels=account_labels,
        )

        # Build scan config based on mode
        if request.scan_mode == "count":
            scan_config = ScanConfig(
                master_limit=request.limit or 20,
                from_date=None,
                to_date=None,
            )
            scan_period = f"Últimas {request.limit or 20} publicaciones"
        else:  # date mode
            scan_config = ScanConfig(
                master_limit=None,
                from_date=request.from_date,
                to_date=request.to_date,
            )
            from_str = request.from_date.strftime("%d/%m/%Y")
            to_str = request.to_date.strftime("%d/%m/%Y")
            scan_period = f"{from_str} — {to_str}"

        service = ScanService(
            provider=provider,
            account_config=account_config,
            scan_config=scan_config,
        )

        export_dir = os.getenv("EXPORT_DIR", "data/exports")
        result = await service.scan(output_dir=export_dir)

        # Build posts array
        posts_data = []
        for post_status in result.audit_result.posts_status:
            master = post_status.master_post
            post_result = {
                "original": {
                    "shortcode": master.shortcode,
                    "permalink": master.permalink,
                    "published_at": master.published_at.isoformat(),
                    "caption": clean_caption(master.caption)[:200] if master.caption else "",
                    "type": master.post_type.value,
                },
                "accounts": [
                    {
                        "username": account,
                        "label": account_labels.get(account, account),
                        "status": match_detail.status.value,
                        "similarity": int(match_detail.score * 100),
                        "visual_similarity": int((match_detail.visual_similarity or 0) * 100),
                        "caption_similarity": int(match_detail.caption_similarity * 100),
                        "candidate_permalink": match_detail.candidate_permalink,
                    }
                    for account, match_detail in post_status.account_matches.items()
                ],
            }
            posts_data.append(post_result)

        scan_id = str(uuid4())
        _scan_results[scan_id] = Path(result.excel_path)

        return ScanResponse(
            scan_id=scan_id,
            status="completed",
            master_account=result.master_account,
            master_posts=result.master_posts_count,
            regional_posts=result.regional_posts_count,
            found_everywhere=result.audit_result.found_in_all,
            with_missing=result.audit_result.with_missing,
            with_review=result.audit_result.with_review,
            missing_by_account=result.audit_result.missing_count_by_account,
            review_by_account=result.audit_result.review_count_by_account,
            export_url=f"/api/scans/{scan_id}/export",
            posts=posts_data,
            scan_mode=request.scan_mode,
            scan_period=scan_period,
            warnings=result.warnings,
            coverage_by_account=result.coverage_by_account,
        )

    except InstagramProviderException as e:
        logger.warning(f"Instagram provider error: {e}")
        raise HTTPException(
            status_code=400,
            detail="No fue posible acceder públicamente a una de las cuentas de Instagram.",
        )
    except Exception as e:
        logger.error(f"Scan error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="No fue posible completar la auditoría.",
        )
    finally:
        async with _scan_lock:
            _active_scan = False

        if provider:
            try:
                await provider.close()
            except Exception as e:
                logger.warning(f"Error closing provider: {e}")


@router.get("/scans/{scan_id}/export")
async def download_export(scan_id: str):
    """Download scan result Excel file"""
    excel_path = _scan_results.get(scan_id)

    if not excel_path or not excel_path.exists():
        raise HTTPException(status_code=404, detail="Scan not found")

    filename = f"NewBody_Auditoria_{scan_id[:8]}.xlsx"
    return FileResponse(
        excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@router.post("/manual-links", response_model=ManualLinkResponse, status_code=200)
async def extract_posts_from_links(request: ManualLinkRequest):
    """Extract Instagram posts from manual URLs"""
    provider = None
    try:
        headless = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
        provider = BrowserInstagramProvider(headless=headless)

        posts = []
        errors = []

        for link in request.links:
            try:
                post = await provider.get_post_by_permalink(link)
                if post:
                    posts.append({
                        "shortcode": post.shortcode,
                        "permalink": post.permalink,
                        "published_at": post.published_at.isoformat() if post.published_at else None,
                        "caption": clean_caption(post.caption)[:200] if post.caption else "",
                        "type": post.post_type.value,
                        "username": post.username,
                    })
                else:
                    errors.append(f"Could not extract: {link}")
            except Exception as e:
                logger.warning(f"Error processing link {link}: {e}")
                errors.append(f"Error: {link}")

        return ManualLinkResponse(
            status="completed",
            links_processed=len(request.links),
            posts_found=len(posts),
            posts=posts,
            errors=errors,
        )

    except Exception as e:
        logger.error(f"Manual links error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error processing manual links",
        )
    finally:
        if provider:
            try:
                await provider.close()
            except Exception as e:
                logger.warning(f"Error closing provider: {e}")


@router.post("/scans/manual", response_model=ManualAuditResponse, status_code=200)
async def run_manual_audit(request: ManualAuditRequest):
    """Run content audit using manually provided Instagram links"""
    global _active_scan

    async with _scan_lock:
        if _active_scan:
            raise HTTPException(
                status_code=409,
                detail="Ya hay una auditoría en ejecución. Espera a que termine.",
            )
        _active_scan = True

    provider = None
    try:
        headless = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
        provider = BrowserInstagramProvider(headless=headless)

        manual_service = ManualAuditService(provider)

        account_labels = {request.master.username: request.master.label}
        extraction_summary = {}

        # Extract master posts
        logger.info(f"Extracting posts for master: {request.master.username}")
        master_posts, master_stats = await manual_service.extract_posts_from_links(
            request.master.username,
            request.master.links
        )
        extraction_summary[request.master.username] = master_stats

        if not master_posts:
            raise HTTPException(
                status_code=400,
                detail="No fue posible extraer publicaciones de los enlaces proporcionados para la cuenta principal.",
            )

        # Extract regional posts
        account_posts = {}
        unavailable_accounts = []
        for target in request.targets:
            account_labels[target.username] = target.label
            logger.info(f"Extracting posts for target: {target.username}")

            posts, stats = await manual_service.extract_posts_from_links(
                target.username,
                target.links
            )
            extraction_summary[target.username] = stats

            # Only include accounts with at least 1 post (avoid false MISSING)
            if len(posts) > 0:
                account_posts[target.username] = posts
            else:
                unavailable_accounts.append(target.username)

        # Run audit with only accounts that have coverage
        logger.info("Running content audit comparison")
        available_targets = [t.username for t in request.targets if t.username not in unavailable_accounts]
        account_config = AccountConfig(
            master_account=request.master.username,
            comparison_accounts=available_targets,
            account_labels=account_labels,
        )

        from app.services.audit_service import AuditService
        from app.domain.matcher import PerceptualContentMatcher
        audit_service = AuditService(matcher=PerceptualContentMatcher())
        audit_result = audit_service.audit_accounts(
            master_posts=master_posts,
            account_posts=account_posts,
            master_account=request.master.username,
        )

        # Export to Excel
        logger.info("Generating Excel report")
        from app.exporters.excel_exporter import ExcelExporter
        export_dir = os.getenv("EXPORT_DIR", "data/exports")
        excel_exporter = ExcelExporter()
        excel_path = excel_exporter.export(
            audit_result,
            export_dir,
            account_labels=account_labels,
            scan_mode="manual",
            extraction_summary=extraction_summary,
            unavailable_accounts=unavailable_accounts,
        )

        scan_id = str(uuid4())
        _scan_results[scan_id] = Path(excel_path)

        # Build posts array
        posts_data = []
        for post_status in audit_result.posts_status:
            master = post_status.master_post
            post_result = {
                "original": {
                    "shortcode": master.shortcode,
                    "permalink": master.permalink,
                    "published_at": master.published_at.isoformat(),
                    "caption": clean_caption(master.caption)[:200] if master.caption else "",
                    "type": master.post_type.value,
                },
                "accounts": [
                    {
                        "username": account,
                        "label": account_labels.get(account, account),
                        "status": match_detail.status.value,
                        "similarity": int(match_detail.score * 100),
                        "visual_similarity": int((match_detail.visual_similarity or 0) * 100),
                        "caption_similarity": int(match_detail.caption_similarity * 100),
                        "candidate_permalink": match_detail.candidate_permalink,
                    }
                    for account, match_detail in post_status.account_matches.items()
                ],
            }
            posts_data.append(post_result)

        # Build warnings
        warnings = []
        for account, stats in extraction_summary.items():
            if stats["links_failed"] > 0:
                warnings.append(
                    f"{account}: Se procesaron {stats['posts_extracted']} de {stats['links_received']} enlaces."
                )
            # Warn if regional account extracted zero posts
            if account != request.master.username and stats["posts_extracted"] == 0:
                warnings.append(
                    f"{account}: No se pudieron procesar publicaciones. "
                    "Los resultados para esta cuenta no son concluyentes."
                )

        return ManualAuditResponse(
            scan_id=scan_id,
            status="completed",
            master_account=request.master.username,
            master_posts=len(master_posts),
            regional_posts={
                account: len(posts)
                for account, posts in account_posts.items()
            },
            found_everywhere=audit_result.found_in_all,
            with_missing=audit_result.with_missing,
            with_review=audit_result.with_review,
            missing_by_account=audit_result.missing_count_by_account,
            review_by_account=audit_result.review_count_by_account,
            export_url=f"/api/scans/{scan_id}/export",
            posts=posts_data,
            warnings=warnings,
            unavailable_accounts=unavailable_accounts,
            extraction_summary=extraction_summary,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manual audit error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error en auditoría manual de enlaces.",
        )
    finally:
        async with _scan_lock:
            _active_scan = False

        if provider:
            try:
                await provider.close()
            except Exception as e:
                logger.warning(f"Error closing provider: {e}")
