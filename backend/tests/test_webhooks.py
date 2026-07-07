import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.config import Settings
from app.models import JobStatus, TranscriptJob
from app.services.webhooks import (
    WEBHOOK_EVENT,
    build_job_webhook_payload,
    deliver_job_webhook,
    signature_header,
)


def test_build_job_webhook_payload_excludes_transcript_text() -> None:
    job = TranscriptJob(
        id=12,
        filename="meeting.wav",
        media_type="audio/wav",
        file_path="storage/uploads/meeting.wav",
        file_size=10,
        status=JobStatus.completed,
        duration_seconds=60,
        processing_time_seconds=20,
        transcript_text="Private transcript text",
        tags_json='["Client"]',
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    payload = build_job_webhook_payload(job)

    assert payload["event"] == WEBHOOK_EVENT
    assert payload["job"]["id"] == 12
    assert payload["job"]["tags"] == ["Client"]
    assert "transcript_text" not in payload["job"]


def test_signature_header_uses_sha256_prefix() -> None:
    assert signature_header(b'{"ok":true}', "secret").startswith("sha256=")


def test_deliver_job_webhook_returns_false_when_disabled() -> None:
    settings = Settings(storage_dir=Path("storage"))
    job = TranscriptJob(
        filename="meeting.wav",
        media_type="audio/wav",
        file_path="storage/uploads/meeting.wav",
        file_size=10,
    )

    assert asyncio.run(deliver_job_webhook(job, settings)) is False


def test_deliver_job_webhook_posts_signed_payload() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    settings = Settings(
        storage_dir=Path("storage"),
        VOIT_WEBHOOK_URL="https://example.test/webhook",
        VOIT_WEBHOOK_SECRET="secret",
        VOIT_WEBHOOK_RETRIES=0,
    )
    job = TranscriptJob(
        id=15,
        filename="meeting.wav",
        media_type="audio/wav",
        file_path="storage/uploads/meeting.wav",
        file_size=10,
        status=JobStatus.completed,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    transport = httpx.MockTransport(handler)

    delivered = asyncio.run(deliver_job_webhook(job, settings, transport))

    assert delivered is True
    assert len(requests) == 1
    request = requests[0]
    assert request.headers["X-VoiT-Event"] == WEBHOOK_EVENT
    assert request.headers["X-VoiT-Signature"] == signature_header(request.content, "secret")
    payload = json.loads(request.content)
    assert payload["job"]["id"] == 15
