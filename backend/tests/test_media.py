import subprocess
import wave
from pathlib import Path

import pytest

from app.services.media import (
    MediaValidationError,
    ensure_readable_media,
    extract_metadata,
    normalize_audio,
    validate_media_file,
)


def test_validate_media_file_rejects_unknown_extension() -> None:
    with pytest.raises(MediaValidationError):
        validate_media_file("notes.txt", 100, 1024)


def test_validate_media_file_rejects_oversized_file() -> None:
    with pytest.raises(MediaValidationError):
        validate_media_file("audio.wav", 2048, 1024)


def test_validate_media_file_accepts_supported_file() -> None:
    validate_media_file("audio.wav", 100, 1024)


def test_wav_fallback_validates_extracts_and_normalizes_without_ffmpeg(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "input.wav"
    output_path = tmp_path / "output.wav"
    _write_wav(input_path, sample_rate=22_050, channels=1)

    def fake_run(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", fake_run)

    ensure_readable_media(input_path)
    metadata = extract_metadata(input_path)
    normalized_path = normalize_audio(input_path, output_path, sample_rate=16_000)

    assert metadata["sample_rate"] == 22_050
    assert metadata["channels"] == 1
    assert metadata["duration_seconds"] == pytest.approx(0.1)
    assert normalized_path == output_path
    with wave.open(str(output_path), "rb") as wav:
        assert wav.getframerate() == 16_000
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2


def _write_wav(path: Path, sample_rate: int, channels: int) -> None:
    frame_count = sample_rate // 10
    silence = b"\x00\x00" * frame_count * channels
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(silence)
