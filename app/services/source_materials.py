import base64
import re
from io import BytesIO
from typing import Dict, List, Optional
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree
from pypdf import PdfReader

from app.services.analysis_limits import MAX_EXTRACTED_CHARS_PER_FILE
from app.services.source_uploads import read_staged_upload

TEXT_EXTENSIONS = {".txt", ".csv", ".md", ".rtf", ".bpmn", ".xml"}
DOCX_EXTENSIONS = {".docx"}
XLSX_EXTENSIONS = {".xlsx"}
PDF_EXTENSIONS = {".pdf"}
# File types become source-context metadata even when text extraction is not possible.
SOURCE_TYPE_BY_EXTENSION = {
    ".mp3": "audio",
    ".mp4": "audio",
    ".mpeg": "audio",
    ".mpga": "audio",
    ".wav": "audio",
    ".m4a": "audio",
    ".webm": "audio",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    ".svg": "image",
    ".bpmn": "bpm",
    ".vsdx": "visio",
    ".vdx": "visio",
    ".xls": "spreadsheet",
    ".xlsx": "spreadsheet",
    ".csv": "csv",
    ".pdf": "pdf",
    ".doc": "docx",
    ".docx": "docx",
    ".rtf": "notes",
    ".txt": "notes",
    ".md": "notes",
}


def build_source_bundle(
    source_text: str,
    source_files: Optional[List[Dict[str, object]]] = None,
) -> str:
    parts = []

    if source_text.strip():
        parts.append("Typed source material:\n" + source_text.strip())

    file_summaries = []
    for index, source_file in enumerate(source_files or [], start=1):
        enriched_source_file = {
            **source_file,
            "source_code": source_file.get("source_code") or f"SRC-{index:03d}",
        }
        file_summaries.append(describe_source_file(enriched_source_file))

    if file_summaries:
        parts.append("Uploaded source materials:\n" + "\n\n".join(file_summaries))

    return "\n\n---\n\n".join(parts).strip()


def build_source_context(
    source_text: str,
    source_files: Optional[List[Dict[str, object]]] = None,
    source_intent: str = "unknown",
    source_subtype: Optional[str] = None,
) -> Dict[str, object]:
    # Source context is canonical metadata; text extraction is only one signal.
    source_materials = []

    if source_text.strip():
        source_materials.append(
             {
                "type": "notes",
                "name": "Typed source material",
                "source_code": "SRC-TYPED",
                "content_fingerprint": "",
                "cache_status": "canonical_text",
                "metadata": [
                    {"key": "characters", "value": str(len(source_text.strip()))},
                    {"key": "extraction_status", "value": "provided_text"},
                ],
                "source_reference": "source:typed",
            }
        )

    for index, source_file in enumerate(source_files or [], start=1):
        name = str(source_file.get("name") or f"source-file-{index}")
        media_type = str(source_file.get("type") or "application/octet-stream")
        size = int(source_file.get("size") or 0)
        extension = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
        source_type = classify_source_type(name, media_type)
        has_embedded_content = bool(source_file.get("content_base64") or source_file.get("storage_id"))
        extracted_text = str(source_file.get("extracted_text") or "")
        extraction_method = str(source_file.get("extraction_method") or "")

        if has_embedded_content and not extraction_method:
            try:
                content = source_file_content(source_file)
                extracted_text = extract_file_text(content, extension, media_type)
            except ValueError:
                extracted_text = ""
            extraction_method = "local_text" if extracted_text else "unsupported_or_unreadable"

        extraction_status = "metadata_only"
        if extracted_text:
            extraction_status = (
                "text_extracted"
                if extraction_method == "local_text"
                else "multimodal_extracted"
            )
        elif extraction_method == "unsupported_or_unreadable":
            extraction_status = "unsupported_or_unreadable"

        metadata = [
            {"key": "media_type", "value": media_type},
            {"key": "size_bytes", "value": str(size)},
            {"key": "extension", "value": extension},
            {
                "key": "has_embedded_content",
                "value": str(has_embedded_content).lower(),
            },
            {"key": "extraction_status", "value": extraction_status},
        ]
        if extraction_method:
            metadata.append({"key": "extraction_method", "value": extraction_method})
        if source_file.get("content_sha256"):
            metadata.append(
                {"key": "content_sha256", "value": str(source_file["content_sha256"])}
            )
        source_code = f"SRC-{index:03d}"
        content_fingerprint = str(source_file.get("content_sha256") or "")

        source_materials.append(
            {
                "type": source_type,
                "name": name,
                "source_code": source_code,
                "content_fingerprint": content_fingerprint,
                "cache_status": (
                    "raw_bytes_ephemeral_canonical_saved"
                    if has_embedded_content
                    else "metadata_only"
                ),
                "metadata": metadata,
                "source_reference": f"source:file:{index}",
            }
        )

    return {
       "source_intent": source_intent,
        "source_subtype": source_subtype or "",
        "source_materials": source_materials,
        "participants": [],
        "sessions": [],
        "attachments": [
            item for item in source_materials if item["source_reference"] != "source:typed"
        ],
        "timestamps": [],
        "follow_up_actions": [],
    }


def classify_source_type(name: str, media_type: str) -> str:
    extension = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension in SOURCE_TYPE_BY_EXTENSION:
        return SOURCE_TYPE_BY_EXTENSION[extension]
    if media_type.startswith("audio/"):
        return "audio"
    if media_type.startswith("image/"):
        return "image"
    #if media_type == "application/pdf":
    if extension in PDF_EXTENSIONS or media_type in {"application/pdf", "pdf"}:
        return "pdf"
    if "spreadsheet" in media_type or "excel" in media_type:
        return "spreadsheet"
    if "word" in media_type:
        return "docx"
    if media_type.startswith("text/"):
        return "notes"
    return "artifact"


def describe_source_file(source_file: Dict[str, object]) -> str:
    name = str(source_file.get("name") or "unnamed file")
    media_type = str(source_file.get("type") or "application/octet-stream")
    size = source_file.get("size") or 0
    source_code = str(source_file.get("source_code") or "")
    content_hash = str(source_file.get("content_sha256") or "")
    extension = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    content_base64 = source_file.get("content_base64")
    storage_id = source_file.get("storage_id")

    header = (
        f"Source code: {source_code or 'pending'}\n"
        f"File: {name}\nType: {media_type}\nSize: {size} bytes"
        + (f"\nContent fingerprint: {content_hash}" if content_hash else "")
    )
    prepared_text = str(source_file.get("extracted_text") or "")
    extraction_method = str(source_file.get("extraction_method") or "")

    if prepared_text:
        return (
            header
            + f"\nExtraction method: {extraction_method or 'prepared_evidence'}"
            + "\nExtracted content:\n"
            + truncate_text(prepared_text)
        )

    if not storage_id and (not isinstance(content_base64, str) or not content_base64):
        return header + "\nExtraction status: Prior-source metadata only; no file bytes provided."

    try:
        content = source_file_content(source_file)
    except ValueError:
        return header + "\nExtracted content: Could not decode file payload."

    extracted_text = extract_file_text(content, extension, media_type)

    if extracted_text:
        return header + "\nExtracted content:\n" + truncate_text(extracted_text)

    return (
        header
        + f"\nExtraction method: {extraction_method or 'unsupported_or_unreadable'}"
        + "\nExtraction status: No reliable evidence could be extracted. "
        "Do not infer facts from the filename alone; flag the source for follow-up."
    )


def source_file_content(source_file: Dict[str, object]) -> bytes:
    storage_id = source_file.get("storage_id")
    if isinstance(storage_id, str) and storage_id:
        return read_staged_upload(storage_id)
    return base64.b64decode(str(source_file.get("content_base64") or ""))


def extract_file_text(content: bytes, extension: str, media_type: str) -> str:
    if extension in DOCX_EXTENSIONS:
        return extract_docx_text(content)
    if extension in XLSX_EXTENSIONS:
        return extract_xlsx_text(content)
    if extension in TEXT_EXTENSIONS or media_type.startswith("text/"):
        return extract_plain_text(content, extension)
    if extension in PDF_EXTENSIONS or media_type == "application/pdf":
        return extract_pdf_text(content)
    return ""

def extract_pdf_text(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
    except Exception:
        return ""

    pages = []

    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        text = normalize_text(text)

        if text:
            pages.append(f"[Page {index}]\n{text}")

    return normalize_text("\n\n".join(pages))

def extract_plain_text(content: bytes, extension: str) -> str:
    text = content.decode("utf-8", errors="ignore")
    if extension == ".rtf":
        text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text)
        text = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", text)
        text = re.sub(r"[{}]", " ", text)
    return normalize_text(text)


def extract_docx_text(content: bytes) -> str:
    try:
        with ZipFile(BytesIO(content)) as archive:
            xml = archive.read("word/document.xml")
    except (KeyError, BadZipFile):
        return ""

    return extract_xml_text(xml)


def extract_xlsx_text(content: bytes) -> str:
    try:
        with ZipFile(BytesIO(content)) as archive:
            shared_strings = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared_strings = extract_xml_text(
                    archive.read("xl/sharedStrings.xml")
                ).splitlines()

            sheet_text = []
            for name in archive.namelist():
                if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                    text = extract_xml_text(archive.read(name))
                    sheet_text.append(text)

            combined = "\n".join(shared_strings + sheet_text)
            return normalize_text(combined)
    except BadZipFile:
        return ""


def extract_xml_text(xml: bytes) -> str:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return ""

    text_parts = [
        node.text.strip()
        for node in root.iter()
        if node.text and node.text.strip()
    ]
    return normalize_text("\n".join(text_parts))


def normalize_text(value: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def truncate_text(value: str, limit: int = MAX_EXTRACTED_CHARS_PER_FILE) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "\n[Content truncated for prompt size.]"
