import json
import re

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import JobStatus, TranscriptJob

SEARCH_INDEX_TABLE = "transcript_search"


def init_search_index(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE VIRTUAL TABLE IF NOT EXISTS {SEARCH_INDEX_TABLE} "
                    "USING fts5(job_id UNINDEXED, filename, transcript_text, segments_text)"
                )
            )
    except SQLAlchemyError:
        return


def sync_job_search_index(db: Session, job: TranscriptJob) -> bool:
    if not _is_sqlite_session(db):
        return False
    try:
        db.execute(text(f"DELETE FROM {SEARCH_INDEX_TABLE} WHERE job_id = :job_id"), {"job_id": job.id})
        if job.status == JobStatus.completed and job.transcript_text.strip():
            db.execute(
                text(
                    f"INSERT INTO {SEARCH_INDEX_TABLE} "
                    "(job_id, filename, transcript_text, segments_text) "
                    "VALUES (:job_id, :filename, :transcript_text, :segments_text)"
                ),
                {
                    "job_id": job.id,
                    "filename": job.filename,
                    "transcript_text": job.transcript_text,
                    "segments_text": _segments_text(job.segments_json),
                },
            )
        return True
    except SQLAlchemyError:
        return False


def delete_job_search_index(db: Session, job_id: int) -> bool:
    if not _is_sqlite_session(db):
        return False
    try:
        db.execute(text(f"DELETE FROM {SEARCH_INDEX_TABLE} WHERE job_id = :job_id"), {"job_id": job_id})
        return True
    except SQLAlchemyError:
        return False


def search_index_job_ids(db: Session, query: str) -> list[int] | None:
    if not _is_sqlite_session(db):
        return None
    fts_query = _fts_query(query)
    if not fts_query:
        return None
    try:
        rows = db.execute(
            text(
                f"SELECT job_id FROM {SEARCH_INDEX_TABLE} "
                f"WHERE {SEARCH_INDEX_TABLE} MATCH :query"
            ),
            {"query": fts_query},
        ).all()
    except SQLAlchemyError:
        return None
    return [int(row.job_id) for row in rows]


def _fts_query(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_]+", query)
    return " ".join(f"{token}*" for token in tokens)


def _segments_text(segments_json: str) -> str:
    try:
        raw_segments = json.loads(segments_json or "[]")
    except json.JSONDecodeError:
        raw_segments = []
    return " ".join(str(segment.get("text", "")) for segment in raw_segments if isinstance(segment, dict))


def _is_sqlite_session(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "sqlite"
