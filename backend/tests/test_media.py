import pytest

from app.services.media import MediaValidationError, validate_media_file


def test_validate_media_file_rejects_unknown_extension() -> None:
    with pytest.raises(MediaValidationError):
        validate_media_file("notes.txt", 100, 1024)


def test_validate_media_file_rejects_oversized_file() -> None:
    with pytest.raises(MediaValidationError):
        validate_media_file("audio.wav", 2048, 1024)


def test_validate_media_file_accepts_supported_file() -> None:
    validate_media_file("audio.wav", 100, 1024)

