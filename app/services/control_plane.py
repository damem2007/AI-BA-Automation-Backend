import json
import os
from datetime import datetime, timezone
from threading import Lock
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException

from app.services.analysis_limits import (
    JOB_RETENTION_SECONDS,
    MAX_CONCURRENT_JOBS,
    MAX_QUEUED_JOBS,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
)

try:
    import redis
except ImportError:  # pragma: no cover - local fallback when redis-py is not installed.
    redis = None


MAX_ACTIVE_JOBS = MAX_CONCURRENT_JOBS + MAX_QUEUED_JOBS
JOB_STALE_SECONDS = max(
    60,
    int(os.getenv("ANALYSIS_JOB_STALE_SECONDS", str(max(JOB_RETENTION_SECONDS, 7200)))),
)
REDIS_URL = os.getenv("REDIS_URL")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp() -> float:
    return datetime.now(timezone.utc).timestamp()


def json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class LocalControlPlane:
    """Development fallback. Enterprise deployments should configure REDIS_URL."""

    backend = "local_memory"

    def __init__(self):
        self.lock = Lock()
        self.jobs: dict[str, dict] = {}
        self.active_jobs: set[str] = set()
        self.requests_by_client: dict[str, list[float]] = {}

    def enforce_rate_limit(self, client_key: str) -> None:
        now = timestamp()
        with self.lock:
            requests = [
                value
                for value in self.requests_by_client.get(client_key, [])
                if value > now - RATE_LIMIT_WINDOW_SECONDS
            ]
            if len(requests) >= RATE_LIMIT_REQUESTS:
                raise HTTPException(
                    status_code=429,
                    detail="Analysis request limit reached. Wait before starting another analysis.",
                )
            requests.append(now)
            self.requests_by_client[client_key] = requests

    def acquire_capacity(self, job_id: str) -> None:
        self.cleanup()
        with self.lock:
            if len(self.active_jobs) >= MAX_ACTIVE_JOBS:
                raise HTTPException(
                    status_code=503,
                    detail="Analysis queue is full. Retry after an active analysis completes.",
                )
            self.active_jobs.add(job_id)

    def release_capacity(self, job_id: str) -> None:
        with self.lock:
            self.active_jobs.discard(job_id)

    def create_job(self, job: dict) -> None:
        with self.lock:
            self.jobs[job["job_id"]] = dict(job)

    def update_job(self, job_id: str, **changes) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job.update(changes)
            job["updated_at"] = utc_now()

    def get_job(self, job_id: str) -> dict:
        self.cleanup()
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="Analysis job not found")
            self._mark_stale_job(job)
            return dict(job)

    def metrics(self) -> dict:
        self.cleanup()
        with self.lock:
            jobs = list(self.jobs.values())
            statuses = [job["status"] for job in jobs]
        return {
            "control_plane": self.backend,
            "queued": statuses.count("queued"),
            "running": statuses.count("running"),
            "completed": statuses.count("completed"),
            "failed": statuses.count("failed"),
            "active_capacity_used": len(self.active_jobs),
            "active_capacity_limit": MAX_ACTIVE_JOBS,
            "max_concurrent_jobs": MAX_CONCURRENT_JOBS,
            "max_queued_jobs": MAX_QUEUED_JOBS,
            "job_stale_seconds": JOB_STALE_SECONDS,
        }

    def cleanup(self) -> None:
        cutoff = timestamp() - JOB_RETENTION_SECONDS
        stale_cutoff = timestamp() - JOB_STALE_SECONDS
        with self.lock:
            for job in self.jobs.values():
                if job["status"] in {"queued", "running"}:
                    updated = datetime.fromisoformat(job["updated_at"]).timestamp()
                    if updated < stale_cutoff:
                        job.update(
                            status="failed",
                            completed_at=utc_now(),
                            error="Analysis worker became unavailable before completing the job.",
                            updated_at=utc_now(),
                        )
                        self.active_jobs.discard(job["job_id"])

            expired = [
                job_id
                for job_id, job in self.jobs.items()
                if job.get("completed_at")
                and datetime.fromisoformat(job["completed_at"]).timestamp() < cutoff
            ]
            for job_id in expired:
                self.jobs.pop(job_id, None)
                self.active_jobs.discard(job_id)

    def _mark_stale_job(self, job: dict) -> None:
        if job["status"] not in {"queued", "running"}:
            return
        updated = datetime.fromisoformat(job["updated_at"]).timestamp()
        if updated >= timestamp() - JOB_STALE_SECONDS:
            return
        job.update(
            status="failed",
            completed_at=utc_now(),
            error="Analysis worker became unavailable before completing the job.",
            updated_at=utc_now(),
        )
        self.active_jobs.discard(job["job_id"])


class RedisControlPlane:
    backend = "redis"

    def __init__(self, redis_url: str):
        if redis is None:
            raise RuntimeError("redis package is not installed")
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.client.ping()
        self.jobs_index = "ba:analysis:jobs"
        self.active_jobs = "ba:analysis:active-jobs"

    def enforce_rate_limit(self, client_key: str) -> None:
        now = timestamp()
        key = f"ba:analysis:rate:{client_key}"
        allowed = self.client.eval(
            """
            redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1] - ARGV[2])
            local count = redis.call('ZCARD', KEYS[1])
            if count >= tonumber(ARGV[3]) then
                return 0
            end
            redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
            redis.call('EXPIRE', KEYS[1], ARGV[2])
            return 1
            """,
            1,
            key,
            now,
            RATE_LIMIT_WINDOW_SECONDS,
            RATE_LIMIT_REQUESTS,
            str(uuid4()),
        )
        if int(allowed) != 1:
            raise HTTPException(
                status_code=429,
                detail="Analysis request limit reached. Wait before starting another analysis.",
            )

    def acquire_capacity(self, job_id: str) -> None:
        now = timestamp()
        allowed = self.client.eval(
            """
            redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1] - ARGV[2])
            local count = redis.call('ZCARD', KEYS[1])
            if count >= tonumber(ARGV[3]) then
                return 0
            end
            redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
            redis.call('EXPIRE', KEYS[1], ARGV[2])
            return 1
            """,
            1,
            self.active_jobs,
            now,
            JOB_STALE_SECONDS,
            MAX_ACTIVE_JOBS,
            job_id,
        )
        if int(allowed) != 1:
            raise HTTPException(
                status_code=503,
                detail="Analysis queue is full. Retry after an active analysis completes.",
            )

    def release_capacity(self, job_id: str) -> None:
        self.client.zrem(self.active_jobs, job_id)

    def create_job(self, job: dict) -> None:
        job = {**job, "updated_at": utc_now()}
        key = self.job_key(job["job_id"])
        payload = json.dumps(job, default=json_default)
        pipe = self.client.pipeline()
        pipe.set(key, payload, ex=JOB_RETENTION_SECONDS + JOB_STALE_SECONDS)
        pipe.zadd(self.jobs_index, {job["job_id"]: timestamp()})
        pipe.expire(self.jobs_index, JOB_RETENTION_SECONDS + JOB_STALE_SECONDS)
        pipe.execute()

    def update_job(self, job_id: str, **changes) -> None:
        job = self.get_job(job_id, fail_on_missing=False)
        if not job:
            return
        job.update(changes)
        job["updated_at"] = utc_now()
        self.client.set(
            self.job_key(job_id),
            json.dumps(job, default=json_default),
            ex=JOB_RETENTION_SECONDS + JOB_STALE_SECONDS,
        )

    def get_job(self, job_id: str, fail_on_missing: bool = True) -> Optional[dict]:
        self.cleanup()
        payload = self.client.get(self.job_key(job_id))
        if not payload:
            if fail_on_missing:
                raise HTTPException(status_code=404, detail="Analysis job not found")
            return None
        job = json.loads(payload)
        return self._mark_stale_job(job)

    def metrics(self) -> dict:
        self.cleanup()
        job_ids = self.client.zrange(self.jobs_index, 0, -1)
        jobs = []
        if job_ids:
            payloads = self.client.mget([self.job_key(job_id) for job_id in job_ids])
            jobs = [
                self._mark_stale_job(json.loads(payload))
                for payload in payloads
                if payload
            ]
        statuses = [job["status"] for job in jobs]
        return {
            "control_plane": self.backend,
            "queued": statuses.count("queued"),
            "running": statuses.count("running"),
            "completed": statuses.count("completed"),
            "failed": statuses.count("failed"),
            "active_capacity_used": self.client.zcard(self.active_jobs),
            "active_capacity_limit": MAX_ACTIVE_JOBS,
            "max_concurrent_jobs": MAX_CONCURRENT_JOBS,
            "max_queued_jobs": MAX_QUEUED_JOBS,
            "job_stale_seconds": JOB_STALE_SECONDS,
        }

    def cleanup(self) -> None:
        now = timestamp()
        stale_cutoff = now - JOB_STALE_SECONDS
        retention_cutoff = now - JOB_RETENTION_SECONDS
        self.client.zremrangebyscore(self.active_jobs, 0, stale_cutoff)
        expired_ids = self.client.zrangebyscore(self.jobs_index, 0, retention_cutoff)
        if expired_ids:
            pipe = self.client.pipeline()
            for job_id in expired_ids:
                pipe.delete(self.job_key(job_id))
                pipe.zrem(self.jobs_index, job_id)
            pipe.execute()

    def job_key(self, job_id: str) -> str:
        return f"ba:analysis:job:{job_id}"

    def _mark_stale_job(self, job: dict) -> dict:
        if job["status"] not in {"queued", "running"}:
            return job
        updated_at = datetime.fromisoformat(job["updated_at"]).timestamp()
        if updated_at >= timestamp() - JOB_STALE_SECONDS:
            return job
        job.update(
            status="failed",
            completed_at=utc_now(),
            error="Analysis worker became unavailable before completing the job.",
            updated_at=utc_now(),
        )
        self.release_capacity(job["job_id"])
        self.client.set(
            self.job_key(job["job_id"]),
            json.dumps(job, default=json_default),
            ex=JOB_RETENTION_SECONDS,
        )
        return job


def build_control_plane():
    if REDIS_URL:
        try:
            return RedisControlPlane(REDIS_URL)
        except Exception:
            if os.getenv("ANALYSIS_REQUIRE_REDIS", "false").lower() == "true":
                raise
    return LocalControlPlane()


control_plane = build_control_plane()
