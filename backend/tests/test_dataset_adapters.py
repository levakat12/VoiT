import io
import tarfile
from pathlib import Path

import pytest

from app.services.dataset_adapters import (
    DatasetAdapterError,
    extract_ljspeech_sample,
    load_ljspeech_archive,
    parse_ljspeech_metadata,
)


def test_load_ljspeech_archive_reads_metadata_manifest(tmp_path: Path) -> None:
    archive_path = _write_ljspeech_archive(
        tmp_path,
        [
            "LJ001-0001|Original text.|Normalized text.",
            "LJ001-0002|Second original.|Second normalized.",
        ],
        {"LJ001-0001": b"one", "LJ001-0002": b"two"},
    )

    manifest = load_ljspeech_archive(archive_path)

    assert manifest.root_name == "LJSpeech-1.1"
    assert manifest.sample_count == 2
    assert manifest.samples[0].sample_id == "LJ001-0001"
    assert manifest.samples[0].transcript == "Original text."
    assert manifest.samples[0].normalized_transcript == "Normalized text."
    assert manifest.samples[0].wav_member == "LJSpeech-1.1/wavs/LJ001-0001.wav"


def test_load_ljspeech_archive_can_limit_manifest_rows(tmp_path: Path) -> None:
    archive_path = _write_ljspeech_archive(
        tmp_path,
        [
            "LJ001-0001|Original text.|Normalized text.",
            "LJ001-0002|Second original.|Second normalized.",
        ],
        {"LJ001-0001": b"one", "LJ001-0002": b"two"},
    )

    manifest = load_ljspeech_archive(archive_path, limit=1)

    assert manifest.sample_count == 1
    assert manifest.samples[0].sample_id == "LJ001-0001"


def test_extract_ljspeech_sample_streams_wav_to_destination(tmp_path: Path) -> None:
    archive_path = _write_ljspeech_archive(
        tmp_path,
        ["LJ001-0001|Original text.|Normalized text."],
        {"LJ001-0001": b"fake wav bytes"},
    )
    manifest = load_ljspeech_archive(archive_path)

    output_path = extract_ljspeech_sample(
        archive_path,
        "LJ001-0001",
        tmp_path / "samples",
        manifest=manifest,
    )

    assert output_path == tmp_path / "samples" / "LJ001-0001.wav"
    assert output_path.read_bytes() == b"fake wav bytes"


def test_extract_ljspeech_sample_rejects_missing_wav(tmp_path: Path) -> None:
    archive_path = _write_ljspeech_archive(
        tmp_path,
        ["LJ001-0001|Original text.|Normalized text."],
        {},
    )
    manifest = load_ljspeech_archive(archive_path)

    with pytest.raises(DatasetAdapterError, match="WAV is missing"):
        extract_ljspeech_sample(archive_path, "LJ001-0001", tmp_path / "samples", manifest=manifest)


def test_parse_ljspeech_metadata_rejects_malformed_rows() -> None:
    with pytest.raises(DatasetAdapterError, match="Invalid LJSpeech metadata row"):
        parse_ljspeech_metadata("LJ001-0001|Only two fields")


def test_parse_ljspeech_metadata_rejects_unsafe_sample_ids() -> None:
    with pytest.raises(DatasetAdapterError, match="Invalid LJSpeech sample id"):
        parse_ljspeech_metadata("../evil|Original text.|Normalized text.")


def test_parse_ljspeech_metadata_rejects_duplicate_ids() -> None:
    with pytest.raises(DatasetAdapterError, match="Duplicate LJSpeech sample id"):
        parse_ljspeech_metadata(
            "\n".join(
                [
                    "LJ001-0001|Original text.|Normalized text.",
                    "LJ001-0001|Other text.|Other normalized.",
                ]
            )
        )


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
