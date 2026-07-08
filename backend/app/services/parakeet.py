import asyncio
import wave
from pathlib import Path

import httpx

from app.config import Settings
from app.schemas import TranscriptSegment


async def transcribe_media(path: Path, settings: Settings) -> tuple[str, list[TranscriptSegment]]:
    if not settings.parakeet_api_key:
        return _development_transcript(path)
    if _uses_riva_grpc(settings):
        return await asyncio.to_thread(_transcribe_with_riva_grpc, path, settings)

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


def _uses_riva_grpc(settings: Settings) -> bool:
    url = settings.parakeet_api_url.strip().lower()
    return bool(settings.parakeet_function_id.strip()) or url.startswith(("grpc://", "grpcs://"))


def _transcribe_with_riva_grpc(path: Path, settings: Settings) -> tuple[str, list[TranscriptSegment]]:
    try:
        import riva.client
    except ImportError as exc:
        raise RuntimeError("nvidia-riva-client is required for hosted NVIDIA Parakeet ASR.") from exc

    uri = settings.parakeet_api_url.removeprefix("grpc://").removeprefix("grpcs://")
    metadata_args = [["authorization", f"Bearer {settings.parakeet_api_key}"]]
    if settings.parakeet_function_id:
        metadata_args.append(["function-id", settings.parakeet_function_id])

    auth = riva.client.Auth(use_ssl=True, uri=uri, metadata_args=metadata_args)
    service = riva.client.ASRService(auth)
    audio_bytes, sample_rate, channels = _read_wav_pcm(path)
    config = riva.client.RecognitionConfig(
        encoding=riva.client.AudioEncoding.LINEAR_PCM,
        sample_rate_hertz=sample_rate,
        language_code=settings.parakeet_language,
        max_alternatives=1,
        audio_channel_count=channels,
        enable_word_time_offsets=True,
        enable_automatic_punctuation=True,
    )
    if settings.parakeet_model:
        config.model = settings.parakeet_model

    response = service.offline_recognize(audio_bytes, config)
    return _parse_riva_response(response)


def _read_wav_pcm(path: Path) -> tuple[bytes, int, int]:
    with wave.open(str(path), "rb") as wav:
        sample_width = wav.getsampwidth()
        if sample_width != 2:
            raise RuntimeError("Riva ASR expects 16-bit PCM WAV audio.")
        return wav.readframes(wav.getnframes()), wav.getframerate(), wav.getnchannels()


def _parse_riva_response(response: object) -> tuple[str, list[TranscriptSegment]]:
    text_parts = []
    segments = []
    cursor = 0.0
    for result in getattr(response, "results", []):
        alternatives = getattr(result, "alternatives", [])
        if not alternatives:
            continue
        alternative = alternatives[0]
        transcript = str(getattr(alternative, "transcript", "")).strip()
        if not transcript:
            continue
        words = list(getattr(alternative, "words", []))
        if words:
            start = _duration_seconds(getattr(words[0], "start_time", None))
            end = _duration_seconds(getattr(words[-1], "end_time", None))
            confidence = _mean_confidence(words)
        else:
            start = cursor
            end = cursor + 3
            confidence = getattr(alternative, "confidence", None)
        cursor = max(cursor, end)
        text_parts.append(transcript)
        segments.append(
            TranscriptSegment(
                start=start,
                end=end,
                text=transcript,
                confidence=confidence,
            )
        )

    text = " ".join(text_parts).strip()
    if text and not segments:
        segments = [TranscriptSegment(start=0, end=3, text=text, confidence=None)]
    return text, segments


def _duration_seconds(duration: object) -> float:
    seconds = float(getattr(duration, "seconds", 0) or 0)
    nanos = float(getattr(duration, "nanos", 0) or 0)
    return seconds + nanos / 1_000_000_000


def _mean_confidence(words: list[object]) -> float | None:
    confidences = [float(value) for word in words if (value := getattr(word, "confidence", None)) is not None]
    if not confidences:
        return None
    return sum(confidences) / len(confidences)
