import json
import zipfile
from datetime import UTC, datetime
from io import BytesIO

from app.models import TranscriptJob
from app.routers.jobs import _export_history_from_job, _record_export
from app.schemas import TranscriptSegment
from app.services.exports import build_export
from app.services.subtitles import SubtitleOptions


def test_build_json_export() -> None:
    content, media_type, extension = build_export(
        "json",
        "Hello",
        [TranscriptSegment(start=0, end=1, text="Hello")],
    )

    payload = json.loads(str(content))
    assert payload["text"] == "Hello"
    assert media_type == "application/json"
    assert extension == "json"


def test_build_docx_export_contains_document_xml() -> None:
    content, media_type, extension = build_export("docx", "Hello DOCX", [])

    with zipfile.ZipFile(BytesIO(content)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")

    assert "Hello DOCX" in document_xml
    assert media_type.endswith("wordprocessingml.document")
    assert extension == "docx"


def test_build_pdf_export_starts_with_pdf_header() -> None:
    content, media_type, extension = build_export("pdf", "Hello PDF", [])

    assert bytes(content).startswith(b"%PDF-1.4")
    assert media_type == "application/pdf"
    assert extension == "pdf"


def test_build_srt_export_accepts_subtitle_options() -> None:
    content, media_type, extension = build_export(
        "srt",
        "alpha beta gamma",
        [TranscriptSegment(start=0, end=2, text="alpha beta gamma")],
        subtitle_options=SubtitleOptions(max_chars=10, max_duration=30, max_lines=1),
    )

    assert "alpha beta" in str(content)
    assert "gamma" in str(content)
    assert media_type == "application/x-subrip"
    assert extension == "srt"


def test_record_export_keeps_history() -> None:
    job = TranscriptJob(
        filename="audio.wav",
        media_type="audio/wav",
        file_path="storage/uploads/audio.wav",
        file_size=10,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    _record_export(job, "pdf")

    history = _export_history_from_job(job)
    assert history[0].format == "pdf"
