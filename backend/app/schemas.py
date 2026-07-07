from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models import JobStatus


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    confidence: float | None = None
    speaker: str | None = None


class ExportHistoryItem(BaseModel):
    format: str
    exported_at: datetime


class JobRead(BaseModel):
    id: int
    filename: str
    media_type: str
    file_size: int
    status: JobStatus
    duration_seconds: float | None
    sample_rate: int | None
    channels: int | None
    current_stage: str
    progress_percent: int
    processing_time_seconds: float | None
    estimated_remaining_seconds: float | None
    processing_speed: float | None
    transcript_text: str
    segments: list[TranscriptSegment]
    export_history: list[ExportHistoryItem]
    project: str
    folder: str
    tags: list[str]
    is_favorite: bool
    is_archived: bool
    error_message: str
    created_at: datetime
    updated_at: datetime


class JobListItem(BaseModel):
    id: int
    filename: str
    status: JobStatus
    duration_seconds: float | None
    current_stage: str
    progress_percent: int
    processing_time_seconds: float | None
    estimated_remaining_seconds: float | None
    processing_speed: float | None
    project: str
    folder: str
    tags: list[str]
    is_favorite: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class SearchResult(BaseModel):
    job_id: int
    filename: str
    status: JobStatus
    match_count: int
    snippets: list[str]
    created_at: datetime


class TranscriptUpdate(BaseModel):
    transcript_text: str
    segments: list[TranscriptSegment] | None = None


class OrganizationUpdate(BaseModel):
    project: str | None = None
    folder: str | None = None
    tags: list[str] | None = None
    is_favorite: bool | None = None
    is_archived: bool | None = None


class UploadResponse(BaseModel):
    job: JobRead


ExportFormat = Literal["txt", "docx", "pdf", "json", "srt", "vtt"]


class ExportRequest(BaseModel):
    job_id: int
    format: ExportFormat
    subtitle_max_chars: int | None = None
    subtitle_max_duration: float | None = None
    subtitle_max_lines: int | None = None


class SettingsRead(BaseModel):
    env: str
    api_configured: bool
    language: str
    model: str | None
    max_upload_mb: int
    allowed_origins: list[str]
    supported_formats: list[str]
    export_formats: list[str]
    storage_dir: str
    normalized_sample_rate: int
