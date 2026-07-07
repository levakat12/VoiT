from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import JobStatus, TranscriptJob
from app.services.search_index import (
    _fts_query,
    delete_job_search_index,
    init_search_index,
    search_index_job_ids,
    sync_job_search_index,
)


def test_fts_query_builds_prefix_terms() -> None:
    assert _fts_query("GPU scheduling!") == "GPU* scheduling*"


def test_search_index_finds_synced_completed_job() -> None:
    engine = create_engine("sqlite:///:memory:")
    init_search_index(engine)

    with Session(engine) as session:
        job = TranscriptJob(
            id=7,
            filename="meeting.wav",
            media_type="audio/wav",
            file_path="storage/uploads/meeting.wav",
            file_size=10,
            status=JobStatus.completed,
            transcript_text="GPU scheduling and budget review",
            segments_json='[{"text": "launch planning"}]',
        )

        assert sync_job_search_index(session, job)
        session.commit()

        assert search_index_job_ids(session, "gpu sched") == [7]
        assert search_index_job_ids(session, "launch") == [7]


def test_search_index_delete_removes_job() -> None:
    engine = create_engine("sqlite:///:memory:")
    init_search_index(engine)

    with Session(engine) as session:
        job = TranscriptJob(
            id=8,
            filename="meeting.wav",
            media_type="audio/wav",
            file_path="storage/uploads/meeting.wav",
            file_size=10,
            status=JobStatus.completed,
            transcript_text="Budget review",
        )

        sync_job_search_index(session, job)
        delete_job_search_index(session, 8)
        session.commit()

        assert search_index_job_ids(session, "budget") == []


def test_search_index_skips_unfinished_jobs() -> None:
    engine = create_engine("sqlite:///:memory:")
    init_search_index(engine)

    with Session(engine) as session:
        job = TranscriptJob(
            id=9,
            filename="meeting.wav",
            media_type="audio/wav",
            file_path="storage/uploads/meeting.wav",
            file_size=10,
            status=JobStatus.pending,
            transcript_text="Should not be indexed",
        )

        assert sync_job_search_index(session, job)
        session.commit()

        assert search_index_job_ids(session, "indexed") == []
