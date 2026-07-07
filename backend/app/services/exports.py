import json
import textwrap
import zipfile
from html import escape
from io import BytesIO

from app.schemas import TranscriptSegment
from app.services.subtitles import SubtitleOptions, to_srt, to_vtt


def build_export(
    export_format: str,
    transcript_text: str,
    segments: list[TranscriptSegment],
    subtitle_options: SubtitleOptions | None = None,
) -> tuple[str | bytes, str, str]:
    if export_format == "txt":
        return transcript_text + "\n", "text/plain", "txt"
    if export_format == "docx":
        return (
            _build_docx_bytes(transcript_text),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        )
    if export_format == "pdf":
        return _build_pdf_bytes(transcript_text), "application/pdf", "pdf"
    if export_format == "json":
        return (
            json.dumps(
                {
                    "text": transcript_text,
                    "segments": [segment.model_dump() for segment in segments],
                },
                indent=2,
            ),
            "application/json",
            "json",
        )
    if export_format == "srt":
        return to_srt(segments, subtitle_options), "application/x-subrip", "srt"
    if export_format == "vtt":
        return to_vtt(segments, subtitle_options), "text/vtt", "vtt"
    raise ValueError("Unsupported export format.")


def _build_docx_bytes(transcript_text: str) -> bytes:
    paragraphs = transcript_text.splitlines() or [transcript_text]
    document_body = "\n".join(
        f"<w:p><w:r><w:t>{escape(paragraph) or ' '}</w:t></w:r></w:p>"
        for paragraph in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{document_body}<w:sectPr/></w:body>"
        "</w:document>"
    )

    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            "</Relationships>",
        )
        archive.writestr("word/document.xml", document_xml)
    return output.getvalue()


def _build_pdf_bytes(transcript_text: str) -> bytes:
    wrapped_lines = []
    for paragraph in transcript_text.splitlines() or [transcript_text]:
        wrapped_lines.extend(textwrap.wrap(paragraph, width=88) or [""])

    pages = [wrapped_lines[index : index + 48] for index in range(0, len(wrapped_lines), 48)]
    if not pages:
        pages = [[""]]

    objects: list[bytes] = []

    def add_object(body: str) -> int:
        objects.append(body.encode("latin-1", errors="replace"))
        return len(objects)

    catalog_id = add_object("<< /Type /Catalog /Pages 2 0 R >>")
    pages_id = add_object("<< /Type /Pages /Kids [] /Count 0 >>")
    font_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []

    for page_lines in pages:
        commands = ["BT", "/F1 11 Tf", "72 748 Td", "14 TL"]
        for line in page_lines:
            commands.append(f"({_escape_pdf_text(line)}) Tj")
            commands.append("T*")
        commands.append("ET")
        content = "\n".join(commands)
        content_id = add_object(f"<< /Length {len(content.encode('latin-1', errors='replace'))} >>\nstream\n{content}\nendstream")
        page_id = add_object(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)

    objects[pages_id - 1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] "
        f"/Count {len(page_ids)} >>"
    ).encode("latin-1")
    objects[catalog_id - 1] = b"<< /Type /Catalog /Pages 2 0 R >>"

    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{index} 0 obj\n".encode("ascii"))
        output.write(body)
        output.write(b"\nendobj\n")
    xref_start = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010} 00000 n \n".encode("ascii"))
    output.write(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_start}\n"
            "%%EOF\n"
        ).encode("ascii")
    )
    return output.getvalue()


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
