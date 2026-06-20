import base64
import binascii
import os

from dotenv import load_dotenv
from fastapi import HTTPException

from app.schemas.analysis import TranscriptRequest


load_dotenv()


def env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


MAX_CONCURRENT_JOBS = env_int("ANALYSIS_MAX_CONCURRENT_JOBS", 2)
MAX_QUEUED_JOBS = env_int("ANALYSIS_MAX_QUEUED_JOBS", 20)
RATE_LIMIT_REQUESTS = env_int("ANALYSIS_RATE_LIMIT_REQUESTS", 10)
RATE_LIMIT_WINDOW_SECONDS = env_int("ANALYSIS_RATE_LIMIT_WINDOW_SECONDS", 60)
JOB_RETENTION_SECONDS = env_int("ANALYSIS_JOB_RETENTION_SECONDS", 3600)
MAX_FILES = env_int("ANALYSIS_MAX_FILES", 10)
MAX_FILE_BYTES = env_int("ANALYSIS_MAX_FILE_BYTES", 15 * 1024 * 1024)
MAX_TOTAL_FILE_BYTES = env_int("ANALYSIS_MAX_TOTAL_FILE_BYTES", 40 * 1024 * 1024)
MAX_SOURCE_TEXT_CHARS = env_int("ANALYSIS_MAX_SOURCE_TEXT_CHARS", 200_000)
MAX_EXTRACTED_CHARS_PER_FILE = env_int(
    "ANALYSIS_MAX_EXTRACTED_CHARS_PER_FILE",
    50_000,
)
MAX_STAGED_MEMORY_BYTES = env_int("ANALYSIS_MAX_STAGED_MEMORY_BYTES", 128 * 1024 * 1024)


def public_limits() -> dict:
    return {
        "configured_control_plane_backend": "redis" if os.getenv("REDIS_URL") else "local_memory",
        "max_concurrent_jobs": MAX_CONCURRENT_JOBS,
        "max_queued_jobs": MAX_QUEUED_JOBS,
        "rate_limit_requests": RATE_LIMIT_REQUESTS,
        "rate_limit_window_seconds": RATE_LIMIT_WINDOW_SECONDS,
        "job_retention_seconds": JOB_RETENTION_SECONDS,
        "max_files": MAX_FILES,
        "max_file_bytes": MAX_FILE_BYTES,
        "max_total_file_bytes": MAX_TOTAL_FILE_BYTES,
        "max_source_text_chars": MAX_SOURCE_TEXT_CHARS,
        "max_extracted_chars_per_file": MAX_EXTRACTED_CHARS_PER_FILE,
        "max_staged_memory_bytes": MAX_STAGED_MEMORY_BYTES,
        "upload_storage_mode": "memory_only",
        "supported_text_extraction_extensions": [
            ".pdf",
            ".docx",
            ".xlsx",
            ".txt",
            ".csv",
            ".md",
            ".rtf",
            ".xml",
            ".bpmn",
        ],
        "multimodal_extensions": [
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
            ".mp3",
            ".mp4",
            ".mpeg",
            ".mpga",
            ".wav",
            ".m4a",
            ".webm",
            ".pdf",
        ],
        "unsupported_or_metadata_only_extensions": [
            ".svg",
            ".vsdx",
            ".doc",
            ".xls",
        ],
    }


def validate_analysis_request(request: TranscriptRequest) -> None:
    source_text = request.source_text if request.source_text is not None else request.transcript
    if len(source_text or "") > MAX_SOURCE_TEXT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Source text exceeds the configured {MAX_SOURCE_TEXT_CHARS:,} character limit.",
        )

    source_files = request.source_files or []
    if len(source_files) > MAX_FILES:
        raise HTTPException(
            status_code=413,
            detail=f"At most {MAX_FILES} source files may be analyzed in one request.",
        )

    total_bytes = 0
    for source_file in source_files:
        declared_size = source_file.size or 0
        if declared_size > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"{source_file.name} exceeds the configured per-file limit.",
            )

        actual_size = declared_size
        if source_file.content_base64:
            try:
                actual_size = len(base64.b64decode(source_file.content_base64, validate=True))
            except (binascii.Error, ValueError) as error:
                raise HTTPException(
                    status_code=422,
                    detail=f"{source_file.name} contains invalid base64 content.",
                ) from error
            if actual_size > MAX_FILE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"{source_file.name} exceeds the configured per-file limit.",
                )

        total_bytes += actual_size

    if total_bytes > MAX_TOTAL_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Combined source files exceed the configured request limit.",
        )
