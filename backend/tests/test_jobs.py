from datetime import UTC, datetime

from app.models import JobStatus, TranscriptJob
from app.routers.jobs import (
    _build_search_result,
    _job_matches_filters,
    _mark_job_canceled,
    _normalize_tags,
    _reset_job_for_retry,
    _safe_export_basename,
    _tags_from_job,
)


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
        transcript_text="Old transcript",
        segments_json='[{"text": "Old"}]',
        error_message="Network failed",
    )

    _reset_job_for_retry(job)

    assert job.status == JobStatus.pending
    assert job.current_stage == "Queued"
    assert job.progress_percent == 0
    assert job.processing_time_seconds is None
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
