import json
import subprocess
from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
    ".aac",
}


class MediaValidationError(ValueError):
    pass


class MediaProcessingError(RuntimeError):
    pass


def validate_media_file(filename: str, file_size: int, max_upload_bytes: int) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise MediaValidationError(f"Unsupported file type. Allowed formats: {allowed}")
    if file_size > max_upload_bytes:
        raise MediaValidationError("File exceeds the configured upload size limit.")


def ensure_readable_media(path: Path) -> None:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_type",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, check=True, text=True, timeout=30)
    except FileNotFoundError as exc:
        raise MediaProcessingError("FFmpeg is required for media validation.") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaProcessingError("Media validation timed out.") from exc
    except subprocess.CalledProcessError as exc:
        reason = (exc.stderr or "").strip() or "Invalid or corrupted media file."
        raise MediaProcessingError(reason) from exc

    payload = json.loads(result.stdout or "{}")
    if not payload.get("streams"):
        raise MediaProcessingError("No readable audio stream was found in this file.")


def extract_metadata(path: Path) -> dict[str, int | float | None]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=sample_rate,channels",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, check=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {"duration_seconds": None, "sample_rate": None, "channels": None}

    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams", [])
    audio_stream = next((stream for stream in streams if "channels" in stream), {})
    duration = payload.get("format", {}).get("duration")

    return {
        "duration_seconds": float(duration) if duration else None,
        "sample_rate": int(audio_stream["sample_rate"]) if audio_stream.get("sample_rate") else None,
        "channels": int(audio_stream["channels"]) if audio_stream.get("channels") else None,
    }


def normalize_audio(input_path: Path, output_path: Path, sample_rate: int) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-sample_fmt",
        "s16",
        str(output_path),
    ]
    try:
        subprocess.run(command, capture_output=True, check=True, text=True, timeout=600)
    except FileNotFoundError as exc:
        raise MediaProcessingError("FFmpeg is required for audio extraction.") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaProcessingError("Audio extraction timed out.") from exc
    except subprocess.CalledProcessError as exc:
        reason = (exc.stderr or "").strip() or "Audio extraction failed."
        raise MediaProcessingError(reason) from exc

    return output_path
