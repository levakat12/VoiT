from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobStatus(StrEnum):
    pending = "pending"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"


class TranscriptJob(Base):
    __tablename__ = "transcript_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus),
        default=JobStatus.pending,
        nullable=False,
    )
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(nullable=True)
    channels: Mapped[int | None] = mapped_column(nullable=True)
    current_stage: Mapped[str] = mapped_column(String(100), default="Queued", nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_time_seconds: Mapped[float | None] = mapped_column(nullable=True)
    estimated_remaining_seconds: Mapped[float | None] = mapped_column(nullable=True)
    processing_speed: Mapped[float | None] = mapped_column(nullable=True)
    transcript_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    segments_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    export_history_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    project: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    folder: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
