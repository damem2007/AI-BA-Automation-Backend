import html
import json
import re
import textwrap
from io import BytesIO
from typing import Any, Dict, Iterable, List, Tuple
from zipfile import ZIP_DEFLATED, ZipFile


EXPORT_SECTIONS = [
    # Canonical sections are exportable directly; legacy sections remain for older artifacts.
    {"key": "project_metadata", "label": "Project Metadata"},
    {"key": "analysis_orchestration", "label": "Analysis Orchestration"},
    {"key": "source_context", "label": "Source Context"},
    {"key": "semantic_model", "label": "Semantic Model"},
    {"key": "strategic_analysis", "label": "Strategic Analysis"},
    {"key": "delivery_analysis", "label": "Delivery Analysis"},
    {"key": "governance_analysis", "label": "Governance Analysis"},
    {"key": "output_views", "label": "Output Views"},
    {"key": "action_points", "label": "Action Points"},
    {"key": "business_summary", "label": "Business Summary"},
    {"key": "user_stories", "label": "User Stories"},
    {"key": "acceptance_criteria", "label": "Acceptance Criteria"},
    {"key": "functional_requirements", "label": "Functional Requirements"},
    {
        "key": "non_functional_requirements",
        "label": "Non-Functional Requirements",
    },
    {"key": "assumptions", "label": "Assumptions"},
    {"key": "risks", "label": "Risks"},
    {"key": "dependencies", "label": "Dependencies"},
    {"key": "open_questions", "label": "Open Questions"},
    {"key": "uat_scenarios", "label": "UAT Scenarios"},
    {"key": "use_cases", "label": "Use Cases"},
    {"key": "context_diagram", "label": "Context Diagram"},
    {"key": "focus_area_outputs", "label": "Focus Area Outputs"},
    {"key": "data_mapping_matrix", "label": "Data Mapping Matrix"},
    {"key": "swot_analysis", "label": "SWOT Analysis"},
    {"key": "pestel_analysis", "label": "PESTEL Analysis"},
    {"key": "baccm_analysis", "label": "BABOK BACCM Analysis"},
]

SECTION_LABELS = {section["key"]: section["label"] for section in EXPORT_SECTIONS}

EXPORT_FORMATS = {
    "pdf": {
        "extension": "pdf",
        "media_type": "application/pdf",
    },
    "docx": {
        "extension": "docx",
        "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    "markdown": {
        "extension": "md",
        "media_type": "text/markdown; charset=utf-8",
    },
    "image": {
        "extension": "svg",
        "media_type": "image/svg+xml; charset=utf-8",
    },
    "csv": {
        "extension": "csv",
        "media_type": "text/csv; charset=utf-8",
    },
    "xlsx": {
        "extension": "xlsx",
        "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
}


def sanitize_filename(value: str) -> str:
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return filename.strip("_") or "artifact"


def build_export(
    project_name: str,
    analysis: Dict[str, Any],
    sections: List[str],
    export_format: str,
) -> Tuple[bytes, str, str]:
    selected_sections = normalize_sections(sections, analysis)

    if not selected_sections:
        raise ValueError("Select at least one export section")

    if export_format not in EXPORT_FORMATS:
        raise ValueError("Unsupported export format")

    if export_format == "pdf":
        content = render_pdf(project_name, analysis, selected_sections)
    elif export_format == "docx":
        content = render_docx(project_name, analysis, selected_sections)
    elif export_format == "markdown":
        content = render_markdown(project_name, analysis, selected_sections).encode(
            "utf-8"
        )
    elif export_format == "image":
        content = render_svg(project_name, analysis, selected_sections).encode("utf-8")
    elif export_format == "csv":
        content = render_csv(project_name, analysis, selected_sections).encode("utf-8")
    else:
        content = render_xlsx(project_name, analysis, selected_sections)

    format_meta = EXPORT_FORMATS[export_format]
    filename = (
        f"{sanitize_filename(project_name)}_BA_Artifacts."
        f"{format_meta['extension']}"
    )
    return content, filename, format_meta["media_type"]


def normalize_sections(sections: List[str], analysis: Dict[str, Any]) -> List[str]:
    valid_keys = {section["key"] for section in EXPORT_SECTIONS}
    requested = [section for section in sections if section in valid_keys]

    if not requested:
        requested = [section["key"] for section in EXPORT_SECTIONS]

    return [section for section in requested if has_section_content(analysis, section)]


def has_section_content(analysis: Dict[str, Any], section: str) -> bool:
    value = resolve_section_value(analysis, section)
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return len(value) > 0
    return True


def render_markdown(
    project_name: str, analysis: Dict[str, Any], sections: Iterable[str]
) -> str:
    lines = [f"# {project_name}", ""]

    for section in sections:
        lines.append(f"## {SECTION_LABELS[section]}")
        lines.extend(render_markdown_value(resolve_section_value(analysis, section)))
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_markdown_value(value: Any, indent: int = 0) -> List[str]:
    prefix = "  " * indent

    if value is None:
        return []
    if isinstance(value, str):
        return [prefix + line for line in value.splitlines()]
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{prefix}- {summarize_dict(item)}")
                for key, nested_value in item.items():
                    if isinstance(nested_value, (list, dict)):
                        lines.append(f"{prefix}  - {labelize(key)}:")
                        lines.extend(render_markdown_value(nested_value, indent + 2))
            else:
                lines.append(f"{prefix}- {format_scalar(item)}")
        return lines
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            if isinstance(item, (list, dict)):
                lines.append(f"{prefix}- {labelize(key)}:")
                lines.extend(render_markdown_value(item, indent + 1))
            else:
                lines.append(f"{prefix}- **{labelize(key)}:** {format_scalar(item)}")
        return lines

    return [f"{prefix}{format_scalar(value)}"]


def summarize_dict(value: Dict[str, Any]) -> str:
    preferred_keys = [
        "story",
        "description",
        "criteria",
        "risk",
        "dependency",
        "scenario",
        "title",
        "name",
        "id",
    ]
    for key in preferred_keys:
        item = value.get(key)
        if isinstance(item, str) and item:
            return item
        if isinstance(item, list) and item:
            return "; ".join(format_scalar(entry) for entry in item)

    return "; ".join(
        f"{labelize(key)}: {format_scalar(item)}"
        for key, item in value.items()
        if not isinstance(item, (list, dict))
    )


def render_confluence(
    project_name: str, analysis: Dict[str, Any], sections: Iterable[str]
) -> str:
    body = [f"<h1>{html.escape(project_name)}</h1>"]

    for section in sections:
        body.append(f"<h2>{html.escape(SECTION_LABELS[section])}</h2>")
        body.append(render_html_value(resolve_section_value(analysis, section)))

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8" />',
            f"<title>{html.escape(project_name)} BA Artifacts</title>",
            "</head>",
            "<body>",
            *body,
            "</body>",
            "</html>",
        ]
    )


def render_html_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return f"<p>{html.escape(value).replace(chr(10), '<br />')}</p>"
    if isinstance(value, list):
        items = "".join(f"<li>{render_html_item(item)}</li>" for item in value)
        return f"<ul>{items}</ul>"
    if isinstance(value, dict):
        rows = "".join(
            "<tr>"
            f"<th>{html.escape(labelize(key))}</th>"
            f"<td>{render_html_value(item)}</td>"
            "</tr>"
            for key, item in value.items()
        )
        return f"<table><tbody>{rows}</tbody></table>"

    return f"<p>{html.escape(format_scalar(value))}</p>"


def render_html_item(value: Any) -> str:
    if isinstance(value, dict):
        return render_html_value(value)
    if isinstance(value, list):
        return render_html_value(value)
    return html.escape(format_scalar(value))


def render_csv(
    project_name: str, analysis: Dict[str, Any], sections: Iterable[str]
) -> str:
    rows = [["Project", "Section", "Item", "Field", "Value"]]
    rows.extend(build_tabular_rows(project_name, analysis, sections))
    return (
        "\ufeff"
        + "\n".join(",".join(csv_escape(cell) for cell in row) for row in rows)
        + "\n"
    )


def render_xlsx(
    project_name: str, analysis: Dict[str, Any], sections: Iterable[str]
) -> bytes:
    rows = [["Project", "Section", "Item", "Field", "Value"]]
    rows.extend(build_tabular_rows(project_name, analysis, sections))
    sheet_xml = build_sheet_xml(rows)

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as xlsx:
        xlsx.writestr("[Content_Types].xml", XLSX_CONTENT_TYPES)
        xlsx.writestr("_rels/.rels", XLSX_RELS)
        xlsx.writestr("xl/_rels/workbook.xml.rels", XLSX_WORKBOOK_RELS)
        xlsx.writestr("xl/workbook.xml", XLSX_WORKBOOK)
        xlsx.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        xlsx.writestr("xl/styles.xml", XLSX_STYLES)

    return buffer.getvalue()


def build_tabular_rows(
    project_name: str, analysis: Dict[str, Any], sections: Iterable[str]
) -> List[List[str]]:
    rows = []
    for section in sections:
        section_label = SECTION_LABELS[section]
        rows.extend(
            flatten_section(
                project_name,
                section_label,
                resolve_section_value(analysis, section),
            )
        )
    return rows


def resolve_section_value(analysis: Dict[str, Any], section: str) -> Any:
    # Map document-style export choices back to their canonical semantic source.
    if section == "action_points":
        return (
            analysis.get("semantic_model", {})
            .get("action_points", [])
        )
    if section == "business_summary":
        executive_summary = (
            analysis.get("output_views", {})
            .get("executive_summary", {})
        )
        if executive_summary:
            return executive_summary
    if section == "functional_requirements":
        return (
            analysis.get("semantic_model", {})
            .get("requirements", {})
            .get("functional", analysis.get(section))
        )
    if section == "non_functional_requirements":
        return (
            analysis.get("semantic_model", {})
            .get("requirements", {})
            .get("non_functional", analysis.get(section))
        )
    if section == "assumptions":
        return analysis.get("semantic_model", {}).get("assumptions", analysis.get(section))
    if section == "risks":
        return analysis.get("semantic_model", {}).get("risks", analysis.get(section))
    if section == "dependencies":
        return analysis.get("semantic_model", {}).get("dependencies", analysis.get(section))
    if section == "open_questions":
        return analysis.get("semantic_model", {}).get("open_questions", analysis.get(section))
    if section == "user_stories":
        return analysis.get("delivery_analysis", {}).get("user_stories", analysis.get(section))
    if section == "acceptance_criteria":
        return analysis.get("delivery_analysis", {}).get("acceptance_criteria", analysis.get(section))
    if section == "uat_scenarios":
        return analysis.get("delivery_analysis", {}).get("uat_scenarios", analysis.get(section))
    if section == "swot_analysis":
        return analysis.get("strategic_analysis", {}).get("swot", analysis.get(section))
    if section == "pestel_analysis":
        return analysis.get("strategic_analysis", {}).get("pestel", analysis.get(section))
    if section == "baccm_analysis":
        return analysis.get("strategic_analysis", {}).get("baccm", analysis.get(section))
    return analysis.get(section)


def flatten_section(
    project_name: str,
    section_label: str,
    value: Any,
    item_label: str = "",
    parent_field: str = "",
) -> List[List[str]]:
    if value is None:
        return []

    if isinstance(value, str):
        return [[project_name, section_label, item_label, parent_field, value]]

    if isinstance(value, list):
        rows = []
        for index, item in enumerate(value, start=1):
            rows.extend(
                flatten_section(
                    project_name,
                    section_label,
                    item,
                    item_label or f"Item {index}",
                    parent_field,
                )
            )
        return rows

    if isinstance(value, dict):
        rows = []
        for key, item in value.items():
            field = labelize(key)
            if isinstance(item, (list, dict)):
                rows.extend(
                    flatten_section(project_name, section_label, item, item_label, field)
                )
            else:
                rows.append(
                    [
                        project_name,
                        section_label,
                        item_label,
                        field,
                        format_scalar(item),
                    ]
                )
        return rows

    return [[project_name, section_label, item_label, parent_field, format_scalar(value)]]


def build_sheet_xml(rows: List[List[str]]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{column_name(column_index)}{row_index}"
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{xml_escape(value)}</t></is></c>'
            )
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        + "".join(xml_rows)
        + "</sheetData></worksheet>"
    )


def column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def csv_escape(value: Any) -> str:
    text = format_scalar(value)
    return '"' + text.replace('"', '""') + '"'


def render_svg(project_name: str, analysis: Dict[str, Any], sections: Iterable[str]) -> str:
    markdown = render_markdown(project_name, analysis, sections)
    lines = []
    for raw_line in markdown.splitlines():
        if raw_line.startswith("# "):
            lines.append((raw_line[2:], 28, "#f8fafc", 700))
        elif raw_line.startswith("## "):
            lines.append((raw_line[3:], 20, "#5eead4", 700))
        elif raw_line.strip():
            for wrapped in textwrap.wrap(raw_line, width=96):
                lines.append((wrapped, 14, "#cbd5e1", 400))
        else:
            lines.append(("", 8, "#cbd5e1", 400))

    height = max(480, 80 + len(lines) * 24)
    text_nodes = []
    y = 56
    for text, size, color, weight in lines:
        if text:
            text_nodes.append(
                f'<text x="40" y="{y}" fill="{color}" font-size="{size}" '
                f'font-weight="{weight}">{html.escape(text)}</text>'
            )
        y += 24

    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">',
            "<defs>",
            '<linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">',
            '<stop offset="0%" stop-color="#09090b" />',
            '<stop offset="52%" stop-color="#111827" />',
            '<stop offset="100%" stop-color="#0f172a" />',
            "</linearGradient>",
            "</defs>",
            '<rect width="1200" height="100%" fill="url(#bg)" />',
            '<circle cx="120" cy="70" r="260" fill="#14b8a6" opacity="0.14" />',
            '<circle cx="1040" cy="90" r="220" fill="#fbbf24" opacity="0.1" />',
            *text_nodes,
            "</svg>",
        ]
    )


def render_docx(
    project_name: str, analysis: Dict[str, Any], sections: Iterable[str]
) -> bytes:
    paragraphs = [(project_name, "Title")]
    markdown = render_markdown(project_name, analysis, sections)
    for line in markdown.splitlines()[1:]:
        if line.startswith("## "):
            paragraphs.append((line[3:], "Heading1"))
        elif line:
            paragraphs.append((line, "Normal"))
        else:
            paragraphs.append(("", "Normal"))

    document_xml = build_document_xml(paragraphs)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", DOCX_CONTENT_TYPES)
        docx.writestr("_rels/.rels", DOCX_RELS)
        docx.writestr("word/_rels/document.xml.rels", DOCX_DOCUMENT_RELS)
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", DOCX_STYLES)

    return buffer.getvalue()


def build_document_xml(paragraphs: List[Tuple[str, str]]) -> str:
    body = []
    for text, style in paragraphs:
        style_xml = ""
        if style == "Title":
            style_xml = '<w:pPr><w:pStyle w:val="Title"/></w:pPr>'
        elif style == "Heading1":
            style_xml = '<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'

        body.append(
            "<w:p>"
            f"{style_xml}"
            "<w:r>"
            f"<w:t>{xml_escape(text)}</w:t>"
            "</w:r>"
            "</w:p>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(body)
        + "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/><w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\"/></w:sectPr>"
        "</w:body></w:document>"
    )


def render_pdf(
    project_name: str, analysis: Dict[str, Any], sections: Iterable[str]
) -> bytes:
    markdown = render_markdown(project_name, analysis, sections)
    pdf_lines = []
    for line in markdown.splitlines():
        if line.startswith("# "):
            pdf_lines.append(line[2:])
            pdf_lines.append("")
        elif line.startswith("## "):
            pdf_lines.append(line[3:])
        else:
            pdf_lines.extend(textwrap.wrap(line, width=92) or [""])

    pages = [pdf_lines[index : index + 42] for index in range(0, len(pdf_lines), 42)]
    return build_simple_pdf(pages or [[]])


def build_simple_pdf(pages: List[List[str]]) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{3 + i * 2} 0 R' for i in range(len(pages)))}] /Count {len(pages)} >>".encode(),
    ]

    for index, page_lines in enumerate(pages):
        page_object = 3 + index * 2
        content_object = page_object + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {3 + len(pages) * 2} 0 R >> >> /Contents {content_object} 0 R >>".encode()
        )
        stream = render_pdf_stream(page_lines)
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode()
            + stream
            + b"\nendstream"
        )

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    buffer = BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{number} 0 obj\n".encode())
        buffer.write(obj)
        buffer.write(b"\nendobj\n")

    xref = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode())
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode())

    buffer.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return buffer.getvalue()


def render_pdf_stream(lines: List[str]) -> bytes:
    commands = ["BT", "/F1 11 Tf", "50 750 Td", "16 TL"]
    for line in lines:
        commands.append(f"({pdf_escape(line)}) Tj")
        commands.append("T*")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def labelize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def format_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, default=str)


def xml_escape(value: str) -> str:
    return html.escape(value, quote=True)


def pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


DOCX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

DOCX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOCX_DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>"""

DOCX_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:rPr><w:sz w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:rPr><w:b/><w:sz w:val="36"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:rPr><w:b/><w:color w:val="0F766E"/><w:sz w:val="28"/></w:rPr>
  </w:style>
</w:styles>"""

XLSX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

XLSX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

XLSX_WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

XLSX_WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="BA Artifacts" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""

XLSX_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
</styleSheet>"""
