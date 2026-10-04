"""In-memory job management for async scans"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ScanJob:
    """Represents a scan job"""
    scan_id: str
    status: str = "queued"  # queued|fetching_master|fetching_targets|downloading_media|matching|exporting|completed|failed
    progress: int = 0
    message: str = ""
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class ScanJobManager:
    """Manages in-memory scan jobs and task references"""

    def __init__(self):
        self._scan_jobs: dict[str, ScanJob] = {}
        self._scan_tasks: set[asyncio.Task] = set()
        self._lock = asyncio.Lock()

    async def create_job(self, scan_id: str) -> ScanJob:
        """Create a new scan job"""
        async with self._lock:
            job = ScanJob(scan_id=scan_id)
            self._scan_jobs[scan_id] = job
            logger.info(f"Created scan job: {scan_id}")
            return job

    async def get_job(self, scan_id: str) -> Optional[ScanJob]:
        """Get job by ID"""
        async with self._lock:
            return self._scan_jobs.get(scan_id)

    async def update_job_status(
        self,
        scan_id: str,
        status: str,
        progress: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        """Update job status and progress"""
        async with self._lock:
            if scan_id not in self._scan_jobs:
                logger.warning(f"Job not found: {scan_id}")
                return

            job = self._scan_jobs[scan_id]
            job.status = status
            if progress is not None:
                job.progress = min(100, max(0, progress))
            if message is not None:
                job.message = message

            logger.debug(f"Updated job {scan_id}: status={status}, progress={job.progress}")

    async def complete_job(self, scan_id: str, result: Any) -> None:
        """Mark job as completed with result"""
        async with self._lock:
            if scan_id not in self._scan_jobs:
                logger.warning(f"Job not found: {scan_id}")
                return

            job = self._scan_jobs[scan_id]
            job.status = "completed"
            job.progress = 100
            job.result = result
            job.completed_at = datetime.now()
            logger.info(f"Completed job: {scan_id}")

    async def fail_job(self, scan_id: str, error: str) -> None:
        """Mark job as failed with error message"""
        async with self._lock:
            if scan_id not in self._scan_jobs:
                logger.warning(f"Job not found: {scan_id}")
                return

            job = self._scan_jobs[scan_id]
            job.status = "failed"
            job.error = error
            job.completed_at = datetime.now()
            logger.error(f"Failed job {scan_id}: {error}")

    def add_task(self, task: asyncio.Task) -> None:
        """Add task reference and set up done callback"""
        self._scan_tasks.add(task)
        task.add_done_callback(self._scan_tasks.discard)
        logger.debug(f"Added task reference, total: {len(self._scan_tasks)}")

    def get_active_task_count(self) -> int:
        """Get count of active tasks"""
        return len(self._scan_tasks)
