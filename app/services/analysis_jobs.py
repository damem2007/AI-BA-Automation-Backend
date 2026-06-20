from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from uuid import uuid4

from app.services.analysis_limits import (
    MAX_CONCURRENT_JOBS,
)
from app.services.control_plane import control_plane, utc_now


class AnalysisJobManager:
    """Background analysis runner backed by a shared enterprise control plane.

    Redis owns job status, rate limiting, and cluster-wide capacity when REDIS_URL is set.
    Source bytes remain process-local and memory-only.
    """

    def __init__(self):
        self.executor = ThreadPoolExecutor(
            max_workers=MAX_CONCURRENT_JOBS,
            thread_name_prefix="analysis-job",
        )

    def submit(
        self,
        client_key: str,
        work: Callable[[], dict],
        owner_subject: str,
        tenant_id: str,
    ) -> dict:
        job_id = str(uuid4())
        control_plane.enforce_rate_limit(client_key)
        control_plane.acquire_capacity(job_id)
        job = {
            "job_id": job_id,
            "status": "queued",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "started_at": None,
            "completed_at": None,
            "artifact_id": None,
            "result": None,
            "error": None,
            "owner_subject": owner_subject,
            "tenant_id": tenant_id,
        }
        control_plane.create_job(job)

        try:
            self.executor.submit(self._run, job_id, work)
        except Exception:
            control_plane.release_capacity(job_id)
            control_plane.update_job(
                job_id,
                status="failed",
                completed_at=utc_now(),
                error="Analysis worker could not be started.",
            )
            raise
        return self.get(job_id)

    def _run(self, job_id: str, work: Callable[[], dict]) -> None:
        control_plane.update_job(job_id, status="running", started_at=utc_now())
        try:
            result = work()
            control_plane.update_job(
                job_id,
                status="completed",
                completed_at=utc_now(),
                artifact_id=result.get("id"),
                result=result,
            )
        except Exception as error:
            control_plane.update_job(
                job_id,
                status="failed",
                completed_at=utc_now(),
                error=str(error),
            )
        finally:
            control_plane.release_capacity(job_id)

    def get(self, job_id: str) -> dict:
        return control_plane.get_job(job_id)

    def metrics(self) -> dict:
        return control_plane.metrics()


analysis_jobs = AnalysisJobManager()
