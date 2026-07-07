import hashlib
import hmac
import json
from datetime import UTC, datetime

import httpx

from app.config import Settings
from app.models import TranscriptJob

WEBHOOK_EVENT = "transcript.job.finished"
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}


async def deliver_job_webhook(
    job: TranscriptJob,
    settings: Settings,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bool:
    if not settings.webhook_url:
        return False

    payload = build_job_webhook_payload(job)
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-VoiT-Event": WEBHOOK_EVENT,
    }
    if settings.webhook_secret:
        headers["X-VoiT-Signature"] = signature_header(body, settings.webhook_secret)

    timeout = httpx.Timeout(settings.webhook_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        for attempt in range(settings.webhook_retries + 1):
            try:
                response = await client.post(settings.webhook_url, content=body, headers=headers)
                if response.status_code in RETRY_STATUSES:
                    response.raise_for_status()
                response.raise_for_status()
                return True
            except (httpx.HTTPError, httpx.TimeoutException):
                if attempt >= settings.webhook_retries:
                    return False
    return False


def build_job_webhook_payload(job: TranscriptJob) -> dict:
    return {
        "event": WEBHOOK_EVENT,
        "sent_at": datetime.now(UTC).isoformat(),
        "job": {
            "id": job.id,
            "filename": job.filename,
            "media_type": job.media_type,
            "status": job.status,
            "duration_seconds": job.duration_seconds,
            "progress_percent": job.progress_percent,
            "processing_time_seconds": job.processing_time_seconds,
            "estimated_remaining_seconds": job.estimated_remaining_seconds,
            "processing_speed": job.processing_speed,
            "project": job.project,
            "folder": job.folder,
            "tags": _tags_from_json(job.tags_json),
            "error_message": job.error_message,
            "created_at": _datetime_to_iso(job.created_at),
            "updated_at": _datetime_to_iso(job.updated_at),
        },
    }


def signature_header(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _tags_from_json(tags_json: str) -> list[str]:
    try:
        raw_tags = json.loads(tags_json or "[]")
    except json.JSONDecodeError:
        raw_tags = []
    return [str(tag) for tag in raw_tags if str(tag).strip()]


def _datetime_to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).isoformat()
    return value.astimezone(UTC).isoformat()
