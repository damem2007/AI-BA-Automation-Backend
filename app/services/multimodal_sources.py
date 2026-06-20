import base64
import hashlib
import io
import os
from typing import Optional

from openai import OpenAI

from app.services.source_materials import (
    classify_source_type,
    extract_file_text,
    normalize_text,
    source_file_content,
    truncate_text,
)


MULTIMODAL_MODEL = os.getenv("OPENAI_MULTIMODAL_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
TRANSCRIPTION_MODEL = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-transcribe")
PDF_TEXT_QUALITY_MIN_CHARS = max(1, int(os.getenv("ANALYSIS_PDF_TEXT_QUALITY_MIN_CHARS", "250")))
VISION_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
AUDIO_EXTENSIONS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}
IMAGE_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def prepare_source_files_for_analysis(
    source_files: Optional[list[dict]],
    client: OpenAI,
) -> list[dict]:
    """Normalize every modality into stable text evidence before canonical analysis."""
    prepared = []
    ordered_files = sorted(
        source_files or [],
        key=lambda item: (
            str(item.get("name") or "").casefold(),
            str(item.get("type") or "").casefold(),
            int(item.get("size") or 0),
        ),
    )
    for source_file in ordered_files:
        item = dict(source_file)
        name = str(item.get("name") or "unnamed file")
        media_type = str(item.get("type") or "application/octet-stream")
        extension = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
        has_content = bool(item.get("content_base64") or item.get("storage_id"))
        if not has_content:
            item["extracted_text"] = ""
            item["extraction_method"] = "prior_source_metadata"
            prepared.append(item)
            continue

        content = source_file_content(item)
        local_text = extract_file_text(content, extension, media_type)
        source_type = classify_source_type(name, media_type)
        extraction_method = "local_text"
        extracted_text = local_text

        if source_type == "audio" or extension in AUDIO_EXTENSIONS:
            extracted_text = transcribe_audio(content, name, client)
            extraction_method = "openai_transcription"
        elif source_type == "image" and extension in VISION_EXTENSIONS:
            extracted_text = analyze_image(
                content,
                IMAGE_MEDIA_TYPES.get(extension, media_type),
                name,
                client,
            )
            extraction_method = "openai_vision"
        elif source_type == "pdf" and len(normalize_text(local_text)) < PDF_TEXT_QUALITY_MIN_CHARS:
            extracted_text = analyze_pdf(content, name, client)
            extraction_method = "openai_pdf_vision_fallback"
        elif not local_text:
            extraction_method = "unsupported_or_unreadable"

        item["extracted_text"] = truncate_text(normalize_text(extracted_text or ""))
        item["extraction_method"] = extraction_method
        item["content_sha256"] = hashlib.sha256(content).hexdigest()
        prepared.append(item)
    return prepared


def analyze_image(content: bytes, media_type: str, name: str, client: OpenAI) -> str:
    data_url = f"data:{media_type};base64,{base64.b64encode(content).decode('ascii')}"
    response = client.responses.create(
        model=MULTIMODAL_MODEL,
        input=[{
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": modality_prompt(name, "image"),
                },
                {"type": "input_image", "image_url": data_url},
            ],
        }],
    )
    return response.output_text or ""


def analyze_pdf(content: bytes, name: str, client: OpenAI) -> str:
    data_url = f"data:application/pdf;base64,{base64.b64encode(content).decode('ascii')}"
    response = client.responses.create(
        model=MULTIMODAL_MODEL,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": modality_prompt(name, "scanned or visual PDF")},
                {
                    "type": "input_file",
                    "filename": name,
                    "file_data": data_url,
                },
            ],
        }],
    )
    return response.output_text or ""


def transcribe_audio(content: bytes, name: str, client: OpenAI) -> str:
    audio = io.BytesIO(content)
    audio.name = name
    transcription = client.audio.transcriptions.create(
        model=TRANSCRIPTION_MODEL,
        file=audio,
        response_format="text",
        prompt=(
            "Transcribe accurately for business analysis. Preserve speaker names, decisions, "
            "requirements, risks, dates, systems, process steps, approvals, and action items."
        ),
    )
    if isinstance(transcription, str):
        return transcription
    return str(getattr(transcription, "text", "") or "")


def modality_prompt(name: str, modality: str) -> str:
    return (
        f"Extract evidence from the {modality} source '{name}' for consistent business analysis. "
        "Return plain text with these headings when supported: Visible text; Actors and roles; "
        "Process steps and sequence; Systems and integrations; Data entities and flows; "
        "Requirements and business rules; Decisions and approvals; Risks and controls; "
        "Open questions. Preserve exact identifiers, labels, arrows, relationships, and source "
        "ambiguity. Do not invent missing content."
    )
