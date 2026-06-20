import os
import time
from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import HTTPException


load_dotenv()


UPLOAD_TTL_SECONDS = max(60, int(os.getenv("ANALYSIS_UPLOAD_TTL_SECONDS", "3600")))
MAX_STAGED_BYTES = max(
    1,
    int(os.getenv("ANALYSIS_MAX_STAGED_MEMORY_BYTES", str(128 * 1024 * 1024))),
)


@dataclass(frozen=True)
class MemoryUpload:
    content: bytes
    created_at: float


_lock = Lock()
_uploads: dict[str, MemoryUpload] = {}
_staged_bytes = 0


def stage_upload(content: bytes) -> str:
    """Retain upload bytes briefly in RAM so background workers never need disk storage."""
    global _staged_bytes
    cleanup_expired_uploads()
    with _lock:
        if _staged_bytes + len(content) > MAX_STAGED_BYTES:
            raise HTTPException(
                status_code=503,
                detail="The in-memory upload budget is full. Retry after active analyses complete.",
            )
        storage_id = str(uuid4())
        _uploads[storage_id] = MemoryUpload(content=content, created_at=time.time())
        _staged_bytes += len(content)
    return storage_id


def cleanup_expired_uploads() -> None:
    global _staged_bytes
    cutoff = time.time() - UPLOAD_TTL_SECONDS
    with _lock:
        expired = [
            storage_id
            for storage_id, upload in _uploads.items()
            if upload.created_at < cutoff
        ]
        for storage_id in expired:
            _staged_bytes -= len(_uploads.pop(storage_id).content)


def read_staged_upload(storage_id: str) -> bytes:
    cleanup_expired_uploads()
    with _lock:
        upload = _uploads.get(storage_id)
    if not upload:
        raise HTTPException(status_code=422, detail="A staged source file is missing or expired.")
    return upload.content


def discard_staged_upload(storage_id: str) -> None:
    global _staged_bytes
    with _lock:
        upload = _uploads.pop(storage_id, None)
        if upload:
            _staged_bytes -= len(upload.content)


def staged_upload_metrics() -> dict:
    cleanup_expired_uploads()
    with _lock:
        return {
            "staged_uploads": len(_uploads),
            "staged_bytes": _staged_bytes,
            "max_staged_bytes": MAX_STAGED_BYTES,
            "storage_mode": "memory_only",
        }
