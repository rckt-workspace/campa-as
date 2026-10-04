import asyncio
import logging
import os
from uuid import uuid4
from pathlib import Path
from fastapi import APIRouter, HTTPException
from starlette.responses import FileResponse
from app.api.schemas import HealthResponse, ScanRequest, ScanResponse, ErrorResponse, PostResultResponse, AccountMatchResponse
from app.config import AccountConfig, ScanConfig
from app.providers.factory import create_instagram_provider
from app.services.scan_service import ScanService
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
        provider = create_instagram_provider(headless=headless)

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
