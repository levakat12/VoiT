import json
import ipaddress
import mimetypes
import re
import socket
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from urllib.parse import unquote, urlparse
from uuid import uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import JobStatus, TranscriptJob
from app.schemas import (
    ExportRequest,
    ExportHistoryItem,
    JobListItem,
    JobRead,
    OrganizationBulkResult,
    OrganizationBulkUpdate,
    OrganizationUpdate,
    SearchResult,
    TranscriptInsights,
    TranscriptSegment,
    TranscriptUpdate,
    UploadBatchResponse,
    UploadResponse,
    UploadUrlRequest,
)
from app.services.exports import build_export
from app.services.insights import build_insights_export, build_transcript_insights
from app.services.media import (
    MediaValidationError,
    SUPPORTED_EXTENSIONS,
    ensure_readable_media,
    extract_metadata,
    normalize_audio,
    validate_media_file,
)
from app.services.parakeet import transcribe_media
from app.services.link_downloads import LinkDownloadError, download_link_audio, is_youtube_host
from app.services.search_index import delete_job_search_index, search_index_job_ids, sync_job_search_index
from app.services.subtitles import SubtitleOptions
from app.services.webhooks import deliver_job_webhook

router = APIRouter()

MEDIA_TYPE_EXTENSIONS = {
    "audio/aac": ".aac",
    "audio/flac": ".flac",
    "audio/m4a": ".m4a",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/wave": ".wav",
    "audio/webm": ".webm",
    "audio/x-m4a": ".m4a",
    "audio/x-wav": ".wav",
    "video/mp4": ".mp4",
    "video/msvideo": ".avi",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
    "video/x-msvideo": ".avi",
}


class JobCanceled(RuntimeError):
    pass


class JobPaused(RuntimeError):
    pass


class DirectMediaUnsupported(RuntimeError):
    pass


@router.post("/upload", response_model=UploadResponse)
@router.post("/uploads", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    job = await _create_upload_job(file, db, settings)
    background_tasks.add_task(process_job, job.id)
    return UploadResponse(job=_job_to_schema(job))


@router.post("/uploads/batch", response_model=UploadBatchResponse)
async def upload_files_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UploadBatchResponse:
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Batch uploads are limited to 50 files.")

    jobs = []
    for file in files:
        job = await _create_upload_job(file, db, settings)
        jobs.append(job)
        background_tasks.add_task(process_job, job.id)
    return UploadBatchResponse(jobs=[_job_to_schema(job) for job in jobs])


@router.post("/uploads/url", response_model=UploadResponse)
async def upload_from_url(
    request: UploadUrlRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    job = await _create_url_upload_job(request, db, settings)
    background_tasks.add_task(process_job, job.id)
    return UploadResponse(job=_job_to_schema(job))


async def _create_upload_job(
    file: UploadFile,
    db: Session,
    settings: Settings,
) -> TranscriptJob:
    upload_dir = settings.storage_dir / "uploads"
    suffix = Path(file.filename or "upload").suffix.lower()
    stored_name = f"{uuid4().hex}{suffix}"
    path = upload_dir / stored_name

    size = 0
    with path.open("wb") as target:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_upload_bytes:
                target.close()
                path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File exceeds upload size limit.")
            target.write(chunk)

    try:
        validate_media_file(file.filename or stored_name, size, settings.max_upload_bytes)
    except MediaValidationError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = TranscriptJob(
        filename=file.filename or stored_name,
        media_type=file.content_type or "application/octet-stream",
        file_path=str(path),
        file_size=size,
        status=JobStatus.pending,
        current_stage="Queued",
        progress_percent=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


async def _create_url_upload_job(
    request: UploadUrlRequest,
    db: Session,
    settings: Settings,
) -> TranscriptJob:
    parsed = _validated_remote_media_url(request.url)
    upload_dir = settings.storage_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    if is_youtube_host(parsed.hostname or ""):
        return _create_extracted_link_upload_job(request.url, upload_dir, db, settings)

    try:
        path, filename, media_type, size = await _download_direct_media(request, parsed, upload_dir, settings)
    except DirectMediaUnsupported:
        return _create_extracted_link_upload_job(request.url, upload_dir, db, settings)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=400, detail=f"Remote URL returned {exc.response.status_code}.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=400, detail="Remote URL could not be downloaded.") from exc

    try:
        validate_media_file(filename, size, settings.max_upload_bytes)
    except MediaValidationError:
        path.unlink(missing_ok=True)
        return _create_extracted_link_upload_job(request.url, upload_dir, db, settings)

    job = TranscriptJob(
        filename=filename,
        media_type=media_type,
        file_path=str(path),
        file_size=size,
        status=JobStatus.pending,
        current_stage="Queued",
        progress_percent=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


async def _download_direct_media(
    request: UploadUrlRequest,
    parsed,
    upload_dir: Path,
    settings: Settings,
) -> tuple[Path, str, str, int]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(60.0)) as client:
        async with client.stream("GET", parsed.geturl()) as response:
            response.raise_for_status()
            final_url = _validated_remote_media_url(str(response.url))
            content_type = response.headers.get("content-type")
            filename = _download_filename(
                request.filename,
                final_url,
                content_type,
                response.headers.get("content-disposition"),
            )
            if not _looks_like_direct_media(filename, content_type):
                raise DirectMediaUnsupported

            suffix = Path(filename).suffix.lower()
            stored_name = f"{uuid4().hex}{suffix}"
            path = upload_dir / stored_name
            size = 0
            with path.open("wb") as target:
                async for chunk in response.aiter_bytes(1024 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        target.close()
                        path.unlink(missing_ok=True)
                        raise HTTPException(status_code=413, detail="Remote file exceeds upload size limit.")
                    target.write(chunk)
    media_type = (content_type or "application/octet-stream").split(";", 1)[0]
    return path, filename, media_type, size


def _create_extracted_link_upload_job(
    url: str,
    upload_dir: Path,
    db: Session,
    settings: Settings,
) -> TranscriptJob:
    try:
        path, filename, media_type = download_link_audio(url, upload_dir, settings.max_upload_bytes)
        validate_media_file(filename, path.stat().st_size, settings.max_upload_bytes)
    except LinkDownloadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MediaValidationError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=(
                "The link was downloaded, but its media format is not supported yet. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
            ),
        ) from exc

    job = TranscriptJob(
        filename=filename,
        media_type=media_type,
        file_path=str(path),
        file_size=path.stat().st_size,
        status=JobStatus.pending,
        current_stage="Queued",
        progress_percent=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _looks_like_direct_media(filename: str, content_type: str | None) -> bool:
    if Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS:
        return True
    if not content_type:
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in MEDIA_TYPE_EXTENSIONS


def _validated_remote_media_url(url: str):
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://.")
    _ensure_public_host(parsed.hostname)
    return parsed


def _ensure_public_host(hostname: str) -> None:
    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        try:
            address_info = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise HTTPException(status_code=400, detail="URL host could not be resolved.") from exc
        addresses = [ipaddress.ip_address(item[4][0]) for item in address_info]

    if not addresses or any(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        for address in addresses
    ):
        raise HTTPException(status_code=400, detail="URL host is not allowed.")


def _download_filename(
    requested_filename: str | None,
    parsed_url,
    content_type: str | None,
    content_disposition: str | None,
) -> str:
    candidates = [
        requested_filename,
        _filename_from_content_disposition(content_disposition),
        unquote(Path(parsed_url.path).name),
    ]
    filename = next((candidate.strip() for candidate in candidates if candidate and candidate.strip()), "remote-media")
    filename = Path(filename).name
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS and content_type:
        guessed = _extension_from_content_type(content_type)
        if guessed in SUPPORTED_EXTENSIONS:
            filename = f"{Path(filename).stem or 'remote-media'}{guessed}"
    return _safe_download_filename(filename)


def _extension_from_content_type(content_type: str) -> str | None:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return MEDIA_TYPE_EXTENSIONS.get(media_type) or mimetypes.guess_extension(media_type)


def _filename_from_content_disposition(header: str | None) -> str | None:
    if not header:
        return None
    utf8_match = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", header, flags=re.IGNORECASE)
    if utf8_match:
        return unquote(utf8_match.group(1).strip().strip('"'))
    match = re.search(r'filename\s*=\s*"([^"]+)"', header, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"filename\s*=\s*([^;]+)", header, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip().strip('"')
    return None


def _safe_download_filename(filename: str) -> str:
    path = Path(filename)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("._-") or "remote-media"
    return f"{stem}{path.suffix.lower()}"


@router.patch("/jobs/organization/bulk", response_model=OrganizationBulkResult)
def bulk_update_organization(
    request: OrganizationBulkUpdate,
    db: Session = Depends(get_db),
) -> OrganizationBulkResult:
    job_ids = _unique_job_ids(request.job_ids)
    if not job_ids:
        raise HTTPException(status_code=400, detail="At least one job id is required.")
    if len(job_ids) > 500:
        raise HTTPException(status_code=400, detail="Bulk organization updates are limited to 500 jobs.")

    jobs = db.scalars(select(TranscriptJob).where(TranscriptJob.id.in_(job_ids))).all()
    jobs_by_id = {job.id: job for job in jobs}
    for job_id in job_ids:
        if job := jobs_by_id.get(job_id):
            _apply_organization_update(job, request.update)

    db.commit()
    for job in jobs:
        db.refresh(job)

    return OrganizationBulkResult(
        updated_count=len(jobs),
        missing_job_ids=[job_id for job_id in job_ids if job_id not in jobs_by_id],
        jobs=[_job_to_schema(job) for job in jobs],
    )


@router.get("/history", response_model=list[JobListItem])
@router.get("/jobs", response_model=list[JobListItem])
def list_jobs(
    include_archived: bool = False,
    project: str | None = None,
    tag: str | None = None,
    favorite: bool | None = None,
    db: Session = Depends(get_db),
) -> list[JobListItem]:
    jobs = db.scalars(select(TranscriptJob).order_by(TranscriptJob.created_at.desc())).all()
    return [
        JobListItem(
            id=job.id,
            filename=job.filename,
            status=job.status,
            duration_seconds=job.duration_seconds,
            current_stage=job.current_stage,
            progress_percent=job.progress_percent,
            processing_time_seconds=job.processing_time_seconds,
            estimated_remaining_seconds=job.estimated_remaining_seconds,
            processing_speed=job.processing_speed,
            project=job.project,
            folder=job.folder,
            tags=_tags_from_job(job),
            is_favorite=job.is_favorite,
            is_archived=job.is_archived,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        for job in jobs
        if _job_matches_filters(job, include_archived, project, tag, favorite)
    ]


def recover_interrupted_jobs(db: Session) -> list[int]:
    jobs = db.scalars(
        select(TranscriptJob).where(TranscriptJob.status.in_([JobStatus.pending, JobStatus.running]))
    ).all()
    job_ids = []
    for job in jobs:
        if job.status == JobStatus.running:
            job.status = JobStatus.pending
            job.current_stage = "Queued after restart"
            job.processing_time_seconds = None
            job.estimated_remaining_seconds = None
            job.processing_speed = None
        job_ids.append(job.id)
    db.commit()
    return job_ids


@router.get("/search", response_model=list[SearchResult])
def search_transcripts(
    q: str,
    include_archived: bool = False,
    project: str | None = None,
    tag: str | None = None,
    status: JobStatus | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    format: str | None = None,
    db: Session = Depends(get_db),
) -> list[SearchResult]:
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")

    indexed_job_ids = search_index_job_ids(db, query)
    statement = select(TranscriptJob).order_by(TranscriptJob.created_at.desc())
    if indexed_job_ids is not None:
        if not indexed_job_ids:
            return []
        statement = statement.where(TranscriptJob.id.in_(indexed_job_ids))
    jobs = db.scalars(statement).all()
    return [
        result
        for job in jobs
        if _job_matches_search_filters(
            job,
            include_archived,
            project,
            tag,
            status,
            created_from,
            created_to,
            format,
        )
        if (result := _build_search_result(job, query)) is not None
    ]


@router.get("/transcript/{job_id}", response_model=JobRead)
@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobRead:
    job = db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcript job not found.")
    return _job_to_schema(job)


@router.get("/jobs/{job_id}/media")
def get_job_media(
    job_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    job = db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcript job not found.")

    media_path = _job_media_path(job, settings)
    media_type = job.media_type or mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"
    return FileResponse(media_path, media_type=media_type, filename=job.filename, content_disposition_type="inline")


@router.get("/jobs/{job_id}/insights", response_model=TranscriptInsights)
def get_transcript_insights(job_id: int, db: Session = Depends(get_db)) -> TranscriptInsights:
    return _build_transcript_insights_response(job_id, db)


@router.get("/jobs/{job_id}/insights/exports/{export_format}")
def export_transcript_insights(
    job_id: int,
    export_format: str,
    db: Session = Depends(get_db),
) -> Response:
    insights = _build_transcript_insights_response(job_id, db)
    try:
        content, media_type, extension = build_insights_export(insights, export_format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    filename = f"job_{job_id}_insights.{extension}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


def _build_transcript_insights_response(job_id: int, db: Session) -> TranscriptInsights:
    job = db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcript job not found.")
    if job.status != JobStatus.completed or not job.transcript_text.strip():
        raise HTTPException(status_code=409, detail="Transcript insights are not ready yet.")
    return build_transcript_insights(job.id, job.transcript_text, _segments_from_job(job))


@router.post("/jobs/{job_id}/retry", response_model=JobRead)
def retry_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobRead:
    job = db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcript job not found.")
    if job.status in {JobStatus.pending, JobStatus.running}:
        raise HTTPException(status_code=409, detail="Transcript job is already queued or running.")

    _reset_job_for_retry(job)
    sync_job_search_index(db, job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(process_job, job.id)
    return _job_to_schema(job)


@router.post("/jobs/{job_id}/pause", response_model=JobRead)
def pause_job(job_id: int, db: Session = Depends(get_db)) -> JobRead:
    job = db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcript job not found.")
    if job.status not in {JobStatus.pending, JobStatus.running}:
        raise HTTPException(status_code=409, detail="Only queued or running jobs can be paused.")

    _mark_job_paused(job)
    sync_job_search_index(db, job)
    db.commit()
    db.refresh(job)
    return _job_to_schema(job)


@router.post("/jobs/{job_id}/resume", response_model=JobRead)
def resume_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobRead:
    job = db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcript job not found.")
    if job.status != JobStatus.paused:
        raise HTTPException(status_code=409, detail="Only paused jobs can be resumed.")

    _prepare_job_for_resume(job)
    sync_job_search_index(db, job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(process_job, job.id)
    return _job_to_schema(job)


@router.patch("/jobs/{job_id}/organization", response_model=JobRead)
def update_organization(
    job_id: int,
    update: OrganizationUpdate,
    db: Session = Depends(get_db),
) -> JobRead:
    job = db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcript job not found.")

    _apply_organization_update(job, update)

    db.commit()
    db.refresh(job)
    return _job_to_schema(job)


@router.post("/jobs/{job_id}/cancel", response_model=JobRead)
def cancel_job(job_id: int, db: Session = Depends(get_db)) -> JobRead:
    job = db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcript job not found.")
    if job.status not in {JobStatus.pending, JobStatus.running}:
        raise HTTPException(status_code=409, detail="Only queued or running jobs can be canceled.")

    _mark_job_canceled(job)
    db.commit()
    db.refresh(job)
    return _job_to_schema(job)


@router.delete("/transcript/{job_id}", status_code=204)
def delete_transcript(
    job_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    job = db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcript job not found.")

    _delete_job_files(job, settings)
    delete_job_search_index(db, job.id)
    db.delete(job)
    db.commit()
    return Response(status_code=204)


@router.patch("/jobs/{job_id}/transcript", response_model=JobRead)
def update_transcript(
    job_id: int,
    update: TranscriptUpdate,
    db: Session = Depends(get_db),
) -> JobRead:
    job = db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcript job not found.")

    job.transcript_text = update.transcript_text
    if update.segments is not None:
        job.segments_json = json.dumps([segment.model_dump() for segment in update.segments])
    sync_job_search_index(db, job)
    db.commit()
    db.refresh(job)
    return _job_to_schema(job)


@router.post("/export")
def export_from_request(request: ExportRequest, db: Session = Depends(get_db)) -> Response:
    return _build_export_response(
        request.job_id,
        request.format,
        db,
        _subtitle_options(
            request.subtitle_max_chars,
            request.subtitle_max_duration,
            request.subtitle_max_lines,
        ),
    )


@router.get("/jobs/{job_id}/exports/{export_format}")
def export_transcript(
    job_id: int,
    export_format: str,
    subtitle_max_chars: int | None = None,
    subtitle_max_duration: float | None = None,
    subtitle_max_lines: int | None = None,
    db: Session = Depends(get_db),
) -> Response:
    return _build_export_response(
        job_id,
        export_format,
        db,
        _subtitle_options(subtitle_max_chars, subtitle_max_duration, subtitle_max_lines),
    )


def _build_export_response(
    job_id: int,
    export_format: str,
    db: Session,
    subtitle_options: SubtitleOptions | None = None,
) -> Response:
    job = db.get(TranscriptJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Transcript job not found.")
    if job.status != JobStatus.completed:
        raise HTTPException(status_code=409, detail="Transcript is not ready yet.")

    try:
        content, media_type, extension = build_export(
            export_format,
            job.transcript_text,
            _segments_from_job(job),
            subtitle_options,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _record_export(job, extension)
    db.commit()

    filename = _safe_export_basename(Path(job.filename).stem)
    headers = {"Content-Disposition": f'attachment; filename="{filename}.{extension}"'}
    return Response(content=content, media_type=media_type, headers=headers)


def _subtitle_options(
    max_chars: int | None,
    max_duration: float | None,
    max_lines: int | None,
) -> SubtitleOptions | None:
    if max_chars is None and max_duration is None and max_lines is None:
        return None
    try:
        return SubtitleOptions(
            max_chars=SubtitleOptions.max_chars if max_chars is None else max_chars,
            max_duration=SubtitleOptions.max_duration if max_duration is None else max_duration,
            max_lines=SubtitleOptions.max_lines if max_lines is None else max_lines,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def process_job(job_id: int) -> None:
    from app.database import SessionLocal

    settings = get_settings()
    with SessionLocal() as db:
        job = db.get(TranscriptJob, job_id)
        if not job:
            return
        started_at = perf_counter()

        try:
            _raise_if_canceled_or_paused(db, job)
            _set_progress(db, job, JobStatus.running, "Starting", 5, started_at)
            source_path = Path(job.file_path)
            _raise_if_canceled_or_paused(db, job)
            _set_progress(db, job, JobStatus.running, "Validating media", 15, started_at)
            ensure_readable_media(source_path)
            _raise_if_canceled_or_paused(db, job)
            _set_progress(db, job, JobStatus.running, "Extracting metadata", 25, started_at)
            metadata = extract_metadata(source_path)
            job.duration_seconds = metadata["duration_seconds"]
            job.sample_rate = metadata["sample_rate"]
            job.channels = metadata["channels"]
            db.commit()

            _raise_if_canceled_or_paused(db, job)
            _set_progress(db, job, JobStatus.running, "Normalizing audio", 45, started_at)
            normalized_path = settings.storage_dir / "audio" / f"{source_path.stem}.wav"
            normalize_audio(source_path, normalized_path, settings.normalized_sample_rate)
            _raise_if_canceled_or_paused(db, job)
            _set_progress(db, job, JobStatus.running, "Transcribing", 75, started_at)
            transcript_text, segments = await transcribe_media(normalized_path, settings)
            _raise_if_canceled_or_paused(db, job)
            job.transcript_text = transcript_text
            job.segments_json = json.dumps([segment.model_dump() for segment in segments])
            job.status = JobStatus.completed
            job.current_stage = "Complete"
            job.progress_percent = 100
            elapsed = perf_counter() - started_at
            job.processing_time_seconds = round(elapsed, 3)
            job.estimated_remaining_seconds = 0
            job.processing_speed = _processing_speed(job, elapsed, 100)
            job.error_message = ""
            sync_job_search_index(db, job)
        except JobCanceled:
            _mark_job_canceled(job)
            _update_timing_metrics(job, started_at)
            job.estimated_remaining_seconds = None
            sync_job_search_index(db, job)
        except JobPaused:
            _mark_job_paused(job)
            _update_timing_metrics(job, started_at)
            job.estimated_remaining_seconds = None
            sync_job_search_index(db, job)
        except Exception as exc:  # noqa: BLE001
            job.status = JobStatus.failed
            job.current_stage = "Failed"
            _update_timing_metrics(job, started_at)
            job.estimated_remaining_seconds = None
            job.error_message = str(exc)
            sync_job_search_index(db, job)
        db.commit()
        await deliver_job_webhook(job, settings)


def _segments_from_job(job: TranscriptJob) -> list[TranscriptSegment]:
    try:
        raw_segments = json.loads(job.segments_json or "[]")
    except json.JSONDecodeError:
        raw_segments = []
    return [TranscriptSegment(**segment) for segment in raw_segments]


def _export_history_from_job(job: TranscriptJob) -> list[ExportHistoryItem]:
    try:
        raw_history = json.loads(job.export_history_json or "[]")
    except json.JSONDecodeError:
        raw_history = []
    return [ExportHistoryItem(**item) for item in raw_history]


def _job_to_schema(job: TranscriptJob) -> JobRead:
    return JobRead(
        id=job.id,
        filename=job.filename,
        media_type=job.media_type,
        file_size=job.file_size,
        status=job.status,
        duration_seconds=job.duration_seconds,
        sample_rate=job.sample_rate,
        channels=job.channels,
        current_stage=job.current_stage,
        progress_percent=job.progress_percent,
        processing_time_seconds=job.processing_time_seconds,
        estimated_remaining_seconds=job.estimated_remaining_seconds,
        processing_speed=job.processing_speed,
        transcript_text=job.transcript_text,
        segments=_segments_from_job(job),
        export_history=_export_history_from_job(job),
        project=job.project,
        folder=job.folder,
        tags=_tags_from_job(job),
        is_favorite=job.is_favorite,
        is_archived=job.is_archived,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _build_search_result(job: TranscriptJob, query: str) -> SearchResult | None:
    needle = query.casefold()
    haystack = job.transcript_text.casefold()
    matching_segments = [
        segment.text
        for segment in _segments_from_job(job)
        if needle in segment.text.casefold()
    ]
    full_text_match = needle in haystack
    if not matching_segments and not full_text_match:
        return None

    snippets = matching_segments[:5]
    if not snippets and full_text_match:
        snippets = [_snippet_around_match(job.transcript_text, query)]

    return SearchResult(
        job_id=job.id,
        filename=job.filename,
        status=job.status,
        match_count=max(len(matching_segments), 1 if full_text_match else 0),
        snippets=snippets,
        created_at=job.created_at,
    )


def _snippet_around_match(text: str, query: str, radius: int = 80) -> str:
    index = text.casefold().find(query.casefold())
    if index < 0:
        return text[: radius * 2].strip()
    start = max(index - radius, 0)
    end = min(index + len(query) + radius, len(text))
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def _delete_job_files(job: TranscriptJob, settings: Settings) -> None:
    storage_root = settings.storage_dir.resolve()
    candidates = [
        Path(job.file_path),
        settings.storage_dir / "audio" / f"{Path(job.file_path).stem}.wav",
    ]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except FileNotFoundError:
            continue
        if storage_root in resolved.parents and resolved.is_file():
            resolved.unlink(missing_ok=True)


def _job_media_path(job: TranscriptJob, settings: Settings) -> Path:
    storage_root = settings.storage_dir.resolve()
    try:
        resolved = Path(job.file_path).resolve()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Media file not found.") from exc

    if storage_root != resolved and storage_root not in resolved.parents:
        raise HTTPException(status_code=403, detail="Media file is outside storage.")
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="Media file not found.")
    return resolved


def _set_progress(
    db: Session,
    job: TranscriptJob,
    status: JobStatus,
    stage: str,
    progress_percent: int,
    started_at: float | None = None,
) -> None:
    job.status = status
    job.current_stage = stage
    job.progress_percent = progress_percent
    if started_at is not None:
        _update_timing_metrics(job, started_at)
    db.commit()


def _update_timing_metrics(job: TranscriptJob, started_at: float) -> None:
    elapsed = max(perf_counter() - started_at, 0.001)
    job.processing_time_seconds = round(elapsed, 3)
    job.processing_speed = _processing_speed(job, elapsed, job.progress_percent)
    if job.status == JobStatus.running and 0 < job.progress_percent < 100:
        remaining = elapsed * ((100 - job.progress_percent) / job.progress_percent)
        job.estimated_remaining_seconds = round(remaining, 3)
    elif job.status == JobStatus.completed:
        job.estimated_remaining_seconds = 0
    else:
        job.estimated_remaining_seconds = None


def _processing_speed(
    job: TranscriptJob,
    elapsed_seconds: float,
    progress_percent: int,
) -> float | None:
    if not job.duration_seconds or elapsed_seconds <= 0:
        return None
    completed_fraction = max(min(progress_percent / 100, 1), 0.01)
    return round((job.duration_seconds * completed_fraction) / elapsed_seconds, 3)


def _record_export(job: TranscriptJob, export_format: str) -> None:
    history = [item.model_dump(mode="json") for item in _export_history_from_job(job)]
    history.append(
        {
            "format": export_format,
            "exported_at": datetime.now(UTC).isoformat(),
        }
    )
    job.export_history_json = json.dumps(history[-50:])


def _reset_job_for_retry(job: TranscriptJob) -> None:
    job.status = JobStatus.pending
    job.current_stage = "Queued"
    job.progress_percent = 0
    job.processing_time_seconds = None
    job.estimated_remaining_seconds = None
    job.processing_speed = None
    job.transcript_text = ""
    job.segments_json = "[]"
    job.error_message = ""


def _mark_job_canceled(job: TranscriptJob) -> None:
    job.status = JobStatus.canceled
    job.current_stage = "Canceled"
    job.progress_percent = min(job.progress_percent, 99)
    job.error_message = ""


def _mark_job_paused(job: TranscriptJob) -> None:
    job.status = JobStatus.paused
    job.current_stage = "Paused"
    job.progress_percent = min(job.progress_percent, 99)
    job.estimated_remaining_seconds = None
    job.error_message = ""


def _prepare_job_for_resume(job: TranscriptJob) -> None:
    job.status = JobStatus.pending
    job.current_stage = "Queued"
    job.progress_percent = 0
    job.processing_time_seconds = None
    job.estimated_remaining_seconds = None
    job.processing_speed = None
    job.error_message = ""


def _raise_if_canceled_or_paused(db: Session, job: TranscriptJob) -> None:
    db.refresh(job)
    if job.status == JobStatus.canceled:
        raise JobCanceled()
    if job.status == JobStatus.paused:
        raise JobPaused()


def _safe_export_basename(filename: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._-")
    return sanitized or "transcript"


def _tags_from_job(job: TranscriptJob) -> list[str]:
    try:
        raw_tags = json.loads(job.tags_json or "[]")
    except json.JSONDecodeError:
        raw_tags = []
    return [str(tag) for tag in raw_tags if str(tag).strip()]


def _normalize_tags(tags: list[str]) -> list[str]:
    normalized = []
    seen = set()
    for tag in tags:
        cleaned = tag.strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            normalized.append(cleaned)
            seen.add(key)
    return normalized


def _unique_job_ids(job_ids: list[int]) -> list[int]:
    unique_ids = []
    seen = set()
    for job_id in job_ids:
        if job_id > 0 and job_id not in seen:
            unique_ids.append(job_id)
            seen.add(job_id)
    return unique_ids


def _apply_organization_update(job: TranscriptJob, update: OrganizationUpdate) -> None:
    if update.project is not None:
        job.project = update.project.strip()
    if update.folder is not None:
        job.folder = update.folder.strip()
    if update.tags is not None:
        job.tags_json = json.dumps(_normalize_tags(update.tags))
    if update.is_favorite is not None:
        job.is_favorite = update.is_favorite
    if update.is_archived is not None:
        job.is_archived = update.is_archived


def _job_matches_filters(
    job: TranscriptJob,
    include_archived: bool,
    project: str | None,
    tag: str | None,
    favorite: bool | None,
) -> bool:
    if job.is_archived and not include_archived:
        return False
    if project is not None and job.project.casefold() != project.strip().casefold():
        return False
    if tag is not None:
        tag_key = tag.strip().casefold()
        if tag_key not in {item.casefold() for item in _tags_from_job(job)}:
            return False
    if favorite is not None and job.is_favorite != favorite:
        return False
    return True


def _job_matches_search_filters(
    job: TranscriptJob,
    include_archived: bool,
    project: str | None,
    tag: str | None,
    status: JobStatus | None,
    created_from: datetime | None,
    created_to: datetime | None,
    format: str | None,
) -> bool:
    if not _job_matches_filters(job, include_archived, project, tag, None):
        return False
    if status is not None and job.status != status:
        return False
    created_at = _as_utc(job.created_at)
    if created_from is not None and created_at < _as_utc(created_from):
        return False
    if created_to is not None and created_at > _as_utc(created_to):
        return False
    if format is not None and not _job_matches_format(job, format):
        return False
    return True


def _job_matches_format(job: TranscriptJob, requested_format: str) -> bool:
    normalized = requested_format.strip().casefold().lstrip(".")
    if not normalized:
        return True

    extension = Path(job.filename).suffix.casefold().lstrip(".")
    media_type = job.media_type.casefold()
    return normalized == extension or normalized in media_type


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
