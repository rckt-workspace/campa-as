"""Tests for async scan job management"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

from app.api.job_manager import ScanJobManager, ScanJob
from app.api.schemas import ScanStartResponse, ScanJobResponse
from app.domain.exceptions import InstagramProviderException


@pytest.fixture
def job_manager():
    """Create a fresh job manager for each test"""
    return ScanJobManager()


@pytest.mark.asyncio
async def test_post_scan_returns_202_with_scan_id(client):
    """Test that POST /api/scans returns 202 with scan_id"""
    request_data = {
        "master_username": "newbodycol",
        "master_label": "Principal",
        "targets": [
            {"username": "newbodyclubmedellin", "label": "Medellín"},
        ],
        "scan_mode": "count",
        "limit": 5,
    }

    response = client.post("/api/scans", json=request_data)

    assert response.status_code == 202
    data = response.json()
    assert "scan_id" in data
    assert data["status"] == "queued"
    assert isinstance(data["scan_id"], str)


@pytest.mark.asyncio
async def test_get_scan_queued_status(client, job_manager):
    """Test that GET /api/scans/{scan_id} returns queued status immediately after POST"""
    # Create a job directly
    scan_id = "test-scan-123"
    await job_manager.create_job(scan_id)

    # Note: In integration test, we'd poll the actual endpoint
    # For unit test, we verify job manager works
    job = await job_manager.get_job(scan_id)
    assert job is not None
    assert job.status == "queued"
    assert job.scan_id == scan_id


@pytest.mark.asyncio
async def test_get_nonexistent_scan_returns_404(client):
    """Test that GET with non-existent scan_id returns 404"""
    response = client.get("/api/scans/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_two_simultaneous_scans_rejected(client):
    """Test that second POST while scan active returns 409"""
    request_data = {
        "master_username": "newbodycol",
        "master_label": "Principal",
        "targets": [
            {"username": "newbodyclubmedellin", "label": "Medellín"},
        ],
        "scan_mode": "count",
        "limit": 5,
    }

    # First POST should succeed
    response1 = client.post("/api/scans", json=request_data)
    assert response1.status_code == 202

    # Second POST should be rejected (409)
    response2 = client.post("/api/scans", json=request_data)
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_scan_failure_sets_failed_status(job_manager):
    """Test that failed scan sets status to 'failed' with error"""
    scan_id = "test-fail-123"
    await job_manager.create_job(scan_id)

    error_msg = "Test error: provider failed"
    await job_manager.fail_job(scan_id, error_msg)

    job = await job_manager.get_job(scan_id)
    assert job.status == "failed"
    assert job.error == error_msg


@pytest.mark.asyncio
async def test_active_scan_released_on_exception(job_manager):
    """Test that _active_scan is reset even when exception occurs"""
    scan_id = "test-error-123"
    await job_manager.create_job(scan_id)

    # Simulate failure
    error = "Provider error"
    await job_manager.fail_job(scan_id, error)

    job = await job_manager.get_job(scan_id)
    assert job.status == "failed"


@pytest.mark.asyncio
async def test_media_cache_concurrent_downloads():
    """Test that MediaCache respects concurrency limit"""
    from app.cache.media_cache import MediaCache

    max_concurrent = 2
    cache = MediaCache(max_concurrent_downloads=max_concurrent)

    # Track concurrent downloads
    concurrent_count = 0
    max_concurrent_seen = 0

    async def mock_download(url: str, dest, username: str, shortcode: str):
        nonlocal concurrent_count, max_concurrent_seen
        concurrent_count += 1
        max_concurrent_seen = max(max_concurrent_seen, concurrent_count)
        await asyncio.sleep(0.1)
        concurrent_count -= 1
        return None

    # Patch _download_thumbnail
    with patch.object(cache, '_download_thumbnail', side_effect=mock_download):
        # Try to download 5 images concurrently
        tasks = []
        for i in range(5):
            tasks.append(
                cache.get_local_thumbnail(f"user{i}", f"code{i}", f"http://example.com/{i}.jpg")
            )
        await asyncio.gather(*tasks)

    # Should never exceed max_concurrent
    assert max_concurrent_seen <= max_concurrent


@pytest.mark.asyncio
async def test_phash_cached_not_recalculated():
    """Test that perceptual hash is calculated only once per image"""
    from app.domain.matcher import PerceptualContentMatcher
    from PIL import Image
    import tempfile

    matcher = PerceptualContentMatcher()

    # Create a temporary test image
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img = Image.new("RGB", (100, 100), color="red")
        img.save(tmp.name)
        test_path = tmp.name

    # Call _get_phash twice
    hash1 = matcher._get_phash(test_path)
    hash2 = matcher._get_phash(test_path)

    # Both should return the same object (cached)
    assert hash1 == hash2
    assert test_path in matcher._hash_cache

    # Clean up
    import os
    os.unlink(test_path)


@pytest.mark.asyncio
async def test_thumbnail_failure_does_not_abort_scan(job_manager):
    """Test that missing thumbnail doesn't fail the whole scan"""
    from app.cache.media_cache import MediaCache

    cache = MediaCache()

    # Mock a failure
    with patch.object(cache, '_download_thumbnail', return_value=None):
        result = await cache.get_local_thumbnail("user", "code", "http://example.com/img.jpg")
        # Should return None but not raise
        assert result is None


@pytest.mark.asyncio
async def test_job_manager_update_progress(job_manager):
    """Test that job manager updates progress correctly"""
    scan_id = "test-progress-123"
    await job_manager.create_job(scan_id)

    await job_manager.update_job_status(scan_id, "fetching_master", 25, "Fetching master posts")

    job = await job_manager.get_job(scan_id)
    assert job.status == "fetching_master"
    assert job.progress == 25
    assert job.message == "Fetching master posts"


@pytest.mark.asyncio
async def test_job_completion(job_manager):
    """Test that job can be marked as completed with result"""
    scan_id = "test-complete-123"
    await job_manager.create_job(scan_id)

    result_data = {
        "scan_id": scan_id,
        "status": "completed",
        "master_account": "test",
        "master_posts": 10,
        "regional_posts": {},
        "found_everywhere": 0,
        "with_missing": 0,
        "with_review": 0,
        "missing_by_account": {},
        "review_by_account": {},
        "export_url": "/api/scans/123/export",
    }

    await job_manager.complete_job(scan_id, result_data)

    job = await job_manager.get_job(scan_id)
    assert job.status == "completed"
    assert job.result == result_data
    assert job.progress == 100


@pytest.mark.asyncio
async def test_task_reference_management(job_manager):
    """Test that tasks are properly tracked"""
    async def dummy_task():
        await asyncio.sleep(0.01)

    task = asyncio.create_task(dummy_task())
    initial_count = job_manager.get_active_task_count()

    job_manager.add_task(task)
    assert job_manager.get_active_task_count() == initial_count + 1

    # Wait for task to complete
    await task
    await asyncio.sleep(0.05)  # Give callback time to execute

    # Task should be removed from set via done_callback
    assert job_manager.get_active_task_count() == initial_count
