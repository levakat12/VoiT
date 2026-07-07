from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    get_settings().database_url,
    connect_args={"check_same_thread": False}
    if get_settings().database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    if not get_settings().database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "transcript_jobs" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("transcript_jobs")}
    column_specs = {
        "current_stage": "VARCHAR(100) NOT NULL DEFAULT 'Queued'",
        "progress_percent": "INTEGER NOT NULL DEFAULT 0",
        "processing_time_seconds": "FLOAT",
        "export_history_json": "TEXT NOT NULL DEFAULT '[]'",
        "project": "VARCHAR(120) NOT NULL DEFAULT ''",
        "folder": "VARCHAR(240) NOT NULL DEFAULT ''",
        "tags_json": "TEXT NOT NULL DEFAULT '[]'",
        "is_favorite": "BOOLEAN NOT NULL DEFAULT 0",
        "is_archived": "BOOLEAN NOT NULL DEFAULT 0",
    }

    with engine.begin() as connection:
        for column, spec in column_specs.items():
            if column not in existing_columns:
                connection.execute(text(f"ALTER TABLE transcript_jobs ADD COLUMN {column} {spec}"))
