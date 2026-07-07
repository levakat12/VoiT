from pathlib import Path

import httpx

from app.config import Settings
from app.schemas import TranscriptSegment


async def transcribe_media(path: Path, settings: Settings) -> tuple[str, list[TranscriptSegment]]:
    if not settings.parakeet_api_key:
        return _development_transcript(path)

    headers = {"Authorization": f"Bearer {settings.parakeet_api_key}"}
    timeout = httpx.Timeout(settings.parakeet_timeout_seconds)
    form_data = {
        "language": settings.parakeet_language,
        "response_format": "json",
    }
    if settings.parakeet_model:
        form_data["model"] = settings.parakeet_model

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(settings.parakeet_retries + 1):
            try:
                with path.open("rb") as media:
                    response = await client.post(
                        settings.parakeet_api_url,
                        headers=headers,
                        data=form_data,
                        files={"file": (path.name, media, "audio/wav")},
                    )
                if response.status_code in {408, 429, 500, 502, 503, 504}:
                    response.raise_for_status()
                break
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt >= settings.parakeet_retries:
                    raise
        else:
            raise RuntimeError("Parakeet transcription failed.") from last_error

    response.raise_for_status()
    if response.headers.get("content-type", "").startswith("text/plain"):
        return _parse_text_response(response.text)
    payload = response.json()
    return _parse_parakeet_response(payload)


def _parse_parakeet_response(payload: dict) -> tuple[str, list[TranscriptSegment]]:
    raw_segments = payload.get("segments") or []
    segments = [
        TranscriptSegment(
            start=float(item.get("start", 0)),
            end=float(item.get("end", item.get("start", 0))),
            text=str(item.get("text", "")).strip(),
            confidence=item.get("confidence"),
            speaker=item.get("speaker"),
        )
        for item in raw_segments
        if str(item.get("text", "")).strip()
    ]
    text = str(payload.get("text") or " ".join(segment.text for segment in segments)).strip()
    if not segments and text:
        segments = [TranscriptSegment(start=0, end=3, text=text, confidence=None)]
    return text, segments


def _parse_text_response(text: str) -> tuple[str, list[TranscriptSegment]]:
    transcript = text.strip()
    segments = []
    if transcript:
        segments = [TranscriptSegment(start=0, end=3, text=transcript, confidence=None)]
    return transcript, segments


def _development_transcript(path: Path) -> tuple[str, list[TranscriptSegment]]:
    text = (
        f"Development transcript for {path.name}. Configure PARAKEET_API_KEY and "
        "PARAKEET_API_URL to use the live transcription service."
    )
    return text, [TranscriptSegment(start=0, end=6, text=text, confidence=1.0, speaker="Speaker 1")]
