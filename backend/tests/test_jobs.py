import asyncio
from datetime import UTC, datetime

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.models import JobStatus, TranscriptJob
from app.routers.jobs import (
    _apply_organization_update,
    _build_search_result,
    get_transcript_insights,
    _job_matches_format,
    _job_matches_filters,
    _job_matches_search_filters,
    _mark_job_canceled,
    _normalize_tags,
    _processing_speed,
    _reset_job_for_retry,
    _safe_export_basename,
    _tags_from_job,
    _unique_job_ids,
    upload_files_batch,
)
from app.schemas import OrganizationUpdate


def test_reset_job_for_retry_clears_previous_failure() -> None:
    job = TranscriptJob(
        filename="audio.wav",
        media_type="audio/wav",
        file_path="storage/uploads/audio.wav",
        file_size=10,
        status=JobStatus.failed,
        current_stage="Failed",
        progress_percent=55,
        processing_time_seconds=4.2,
        estimated_remaining_seconds=12.5,
        processing_speed=3.1,
        transcript_text="Old transcript",
        segments_json='[{"text": "Old"}]',
        error_message="Network failed",
    )

    _reset_job_for_retry(job)

    assert job.status == JobStatus.pending
    assert job.current_stage == "Queued"
    assert job.progress_percent == 0
    assert job.processing_time_seconds is None
    assert job.estimated_remaining_seconds is None
    assert job.processing_speed is None
    assert job.transcript_text == ""
    assert job.segments_json == "[]"
    assert job.error_message == ""


def test_reset_job_for_retry_handles_canceled_job() -> None:
    job = TranscriptJob(
        filename="audio.wav",
        media_type="audio/wav",
        file_path="storage/uploads/audio.wav",
        file_size=10,
        status=JobStatus.canceled,
        current_stage="Canceled",
        progress_percent=45,
    )

    _reset_job_for_retry(job)

    assert job.status == JobStatus.pending
    assert job.current_stage == "Queued"
    assert job.progress_percent == 0


def test_mark_job_canceled_updates_status_without_failure() -> None:
    job = TranscriptJob(
        filename="audio.wav",
        media_type="audio/wav",
        file_path="storage/uploads/audio.wav",
        file_size=10,
        status=JobStatus.running,
        current_stage="Transcribing",
        progress_percent=75,
        error_message="",
    )

    _mark_job_canceled(job)

    assert job.status == JobStatus.canceled
    assert job.current_stage == "Canceled"
    assert job.progress_percent == 75
    assert job.error_message == ""


def test_processing_speed_uses_media_duration_and_progress() -> None:
    job = TranscriptJob(
        filename="audio.wav",
        media_type="audio/wav",
        file_path="storage/uploads/audio.wav",
        file_size=10,
        duration_seconds=120,
    )

    assert _processing_speed(job, elapsed_seconds=30, progress_percent=50) == 2
    assert _processing_speed(job, elapsed_seconds=30, progress_percent=100) == 4


def test_processing_speed_waits_for_duration() -> None:
    job = TranscriptJob(
        filename="audio.wav",
        media_type="audio/wav",
        file_path="storage/uploads/audio.wav",
        file_size=10,
    )

    assert _processing_speed(job, elapsed_seconds=30, progress_percent=50) is None


def test_get_transcript_insights_requires_completed_job() -> None:
    class FakeDb:
        @staticmethod
        def get(_model: type[TranscriptJob], _job_id: int) -> TranscriptJob:
            return TranscriptJob(
                id=5,
                filename="audio.wav",
                media_type="audio/wav",
                file_path="storage/uploads/audio.wav",
                file_size=10,
                status=JobStatus.running,
            )

    with pytest.raises(HTTPException) as exc_info:
        get_transcript_insights(5, FakeDb())  # type: ignore[arg-type]

    assert exc_info.value.status_code == 409


def test_batch_upload_requires_files() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(upload_files_batch(BackgroundTasks(), [], None))  # type: ignore[arg-type]

    assert exc_info.value.status_code == 400


def test_batch_upload_limits_file_count() -> None:
    files = [object() for _ in range(51)]

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(upload_files_batch(BackgroundTasks(), files, None))  # type: ignore[arg-type]

    assert exc_info.value.status_code == 400


def test_safe_export_basename_removes_header_unfriendly_characters() -> None:
    assert _safe_export_basename("meeting notes: q1/q2") == "meeting_notes_q1_q2"
    assert _safe_export_basename("...") == "transcript"


def test_build_search_result_finds_segment_matches() -> None:
    job = TranscriptJob(
        id=7,
        filename="meeting.wav",
        media_type="audio/wav",
        file_path="storage/uploads/meeting.wav",
        file_size=10,
        status=JobStatus.completed,
        transcript_text="We talked about GPU scheduling and budgets.",
        segments_json='[{"start": 0, "end": 2, "text": "GPU scheduling", "confidence": 0.9}]',
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    result = _build_search_result(job, "gpu")

    assert result is not None
    assert result.job_id == 7
    assert result.match_count == 1
    assert result.snippets == ["GPU scheduling"]


def test_build_search_result_returns_none_when_missing() -> None:
    job = TranscriptJob(
        id=8,
        filename="meeting.wav",
        media_type="audio/wav",
        file_path="storage/uploads/meeting.wav",
        file_size=10,
        status=JobStatus.completed,
        transcript_text="No matching word here.",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    assert _build_search_result(job, "gpu") is None


def test_normalize_tags_removes_duplicates_and_blanks() -> None:
    assert _normalize_tags(["GPU", "gpu", "  Budget ", ""]) == ["GPU", "Budget"]


def test_unique_job_ids_removes_duplicates_and_invalid_ids() -> None:
    assert _unique_job_ids([3, 1, 3, 0, -2, 2]) == [3, 1, 2]


def test_apply_organization_update_updates_only_provided_fields() -> None:
    job = TranscriptJob(
        filename="meeting.wav",
        media_type="audio/wav",
        file_path="storage/uploads/meeting.wav",
        file_size=10,
        project="Old",
        folder="Inbox",
        tags_json='["Old"]',
        is_favorite=False,
        is_archived=False,
    )

    _apply_organization_update(
        job,
        OrganizationUpdate(
            project="  Client A ",
            tags=["GPU", "gpu", "Budget"],
            is_favorite=True,
        ),
    )

    assert job.project == "Client A"
    assert job.folder == "Inbox"
    assert _tags_from_job(job) == ["GPU", "Budget"]
    assert job.is_favorite is True
    assert job.is_archived is False


def test_tags_from_job_recovers_valid_tags() -> None:
    job = TranscriptJob(
        filename="meeting.wav",
        media_type="audio/wav",
        file_path="storage/uploads/meeting.wav",
        file_size=10,
        tags_json='["GPU", "Budget"]',
    )

    assert _tags_from_job(job) == ["GPU", "Budget"]


def test_job_matches_organization_filters() -> None:
    job = TranscriptJob(
        filename="meeting.wav",
        media_type="audio/wav",
        file_path="storage/uploads/meeting.wav",
        file_size=10,
        project="Client A",
        tags_json='["GPU"]',
        is_favorite=True,
        is_archived=False,
    )

    assert _job_matches_filters(job, False, "client a", "gpu", True)
    assert not _job_matches_filters(job, False, "Client B", "gpu", True)
    assert not _job_matches_filters(job, False, "Client A", "budget", True)
    assert not _job_matches_filters(job, False, "Client A", "gpu", False)


def test_archived_job_is_hidden_unless_requested() -> None:
    job = TranscriptJob(
        filename="meeting.wav",
        media_type="audio/wav",
        file_path="storage/uploads/meeting.wav",
        file_size=10,
        is_archived=True,
    )

    assert not _job_matches_filters(job, False, None, None, None)
    assert _job_matches_filters(job, True, None, None, None)


def test_job_matches_search_filters_combines_metadata() -> None:
    job = TranscriptJob(
        filename="meeting.mp4",
        media_type="video/mp4",
        file_path="storage/uploads/meeting.mp4",
        file_size=10,
        status=JobStatus.completed,
        project="Client A",
        tags_json='["Budget"]',
        is_archived=False,
        created_at=datetime(2026, 1, 15, tzinfo=UTC),
        updated_at=datetime(2026, 1, 15, tzinfo=UTC),
    )

    assert _job_matches_search_filters(
        job,
        include_archived=False,
        project="client a",
        tag="budget",
        status=JobStatus.completed,
        created_from=datetime(2026, 1, 1, tzinfo=UTC),
        created_to=datetime(2026, 1, 31, tzinfo=UTC),
        format="mp4",
    )
    assert not _job_matches_search_filters(
        job,
        include_archived=False,
        project="client a",
        tag="budget",
        status=JobStatus.failed,
        created_from=None,
        created_to=None,
        format="mp4",
    )
    assert not _job_matches_search_filters(
        job,
        include_archived=False,
        project="client a",
        tag="budget",
        status=JobStatus.completed,
        created_from=datetime(2026, 2, 1, tzinfo=UTC),
        created_to=None,
        format="mp4",
    )


def test_job_matches_format_uses_extension_or_media_type() -> None:
    job = TranscriptJob(
        filename="meeting.wav",
        media_type="audio/wav",
        file_path="storage/uploads/meeting.wav",
        file_size=10,
    )

    assert _job_matches_format(job, "wav")
    assert _job_matches_format(job, ".wav")
    assert _job_matches_format(job, "audio")
    assert not _job_matches_format(job, "mp4")
