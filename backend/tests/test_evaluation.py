import asyncio
import io
import tarfile
from pathlib import Path

import pytest

from app.config import Settings
from app.services.evaluation import (
    character_error_rate,
    evaluate_ljspeech_archive,
    word_error_rate,
)


def test_word_error_rate_counts_insertions_deletions_and_replacements() -> None:
    assert word_error_rate("the quick brown fox", "the quick fox") == 0.25
    assert word_error_rate("the quick brown fox", "the slow brown fox") == 0.25
    assert word_error_rate("the quick brown fox", "the very quick brown fox") == 0.25


def test_word_error_rate_normalizes_case_and_punctuation() -> None:
    assert word_error_rate("Hello, WORLD!", "hello world") == 0


def test_character_error_rate_normalizes_spacing_and_punctuation() -> None:
    assert character_error_rate("Hello, WORLD!", "hello world") == 0
    assert character_error_rate("abc", "axc") == pytest.approx(1 / 3)


def test_evaluate_ljspeech_archive_uses_transcription_boundary(tmp_path: Path) -> None:
    archive_path = _write_ljspeech_archive(
        tmp_path,
        ["LJ001-0001|Original words.|Original words."],
        {"LJ001-0001": b"fake wav"},
    )
    settings = Settings(
        _env_file=None,
        PARAKEET_API_KEY="",
        PARAKEET_FUNCTION_ID="",
        PARAKEET_API_URL="http://localhost:9000/v1/audio/transcriptions",
    )

    summary = asyncio.run(evaluate_ljspeech_archive(archive_path, settings, limit=1))

    assert summary.dataset == "LJSpeech-1.1"
    assert summary.sample_count == 1
    assert summary.api_configured is False
    assert summary.samples[0].sample_id == "LJ001-0001"
    assert summary.samples[0].hypothesis.startswith("Development transcript")
    assert summary.mean_word_error_rate > 0

def _write_ljspeech_archive(
    tmp_path: Path,
    metadata_lines: list[str],
    wavs: dict[str, bytes],
) -> Path:
    archive_path = tmp_path / "LJSpeech-1.1.tar.bz2"
    with tarfile.open(archive_path, "w:bz2") as archive:
        _add_directory(archive, "LJSpeech-1.1")
        _add_bytes(archive, "LJSpeech-1.1/metadata.csv", ("\n".join(metadata_lines) + "\n").encode())
        _add_directory(archive, "LJSpeech-1.1/wavs")
        for sample_id, payload in wavs.items():
            _add_bytes(archive, f"LJSpeech-1.1/wavs/{sample_id}.wav", payload)
    return archive_path


def _add_directory(archive: tarfile.TarFile, name: str) -> None:
    info = tarfile.TarInfo(f"{name}/")
    info.type = tarfile.DIRTYPE
    archive.addfile(info)


def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    archive.addfile(info, io.BytesIO(payload))
