from __future__ import annotations

import re
import shutil
import tarfile
from dataclasses import dataclass
from pathlib import Path


LJSPEECH_METADATA = "metadata.csv"
LJSPEECH_SAMPLE_ID = re.compile(r"^LJ\d{3}-\d{4}$")


class DatasetAdapterError(ValueError):
    pass


@dataclass(frozen=True)
class LJSpeechSample:
    sample_id: str
    transcript: str
    normalized_transcript: str
    wav_member: str


@dataclass(frozen=True)
class LJSpeechArchive:
    archive_path: Path
    root_name: str
    samples: tuple[LJSpeechSample, ...]

    @property
    def sample_count(self) -> int:
        return len(self.samples)

    def get_sample(self, sample_id: str) -> LJSpeechSample:
        for sample in self.samples:
            if sample.sample_id == sample_id:
                return sample
        raise DatasetAdapterError(f"LJSpeech sample not found: {sample_id}")


def load_ljspeech_archive(archive_path: Path, limit: int | None = None) -> LJSpeechArchive:
    if limit is not None and limit <= 0:
        raise DatasetAdapterError("LJSpeech sample limit must be greater than zero.")
    if not archive_path.is_file():
        raise DatasetAdapterError(f"LJSpeech archive not found: {archive_path}")

    with tarfile.open(archive_path, "r:*") as archive:
        metadata_member = _find_ljspeech_metadata(archive)
        if metadata_member is None:
            raise DatasetAdapterError("LJSpeech archive is missing metadata.csv.")

        root_name = _archive_root(metadata_member.name)
        metadata_file = archive.extractfile(metadata_member)
        if metadata_file is None:
            raise DatasetAdapterError("Could not read LJSpeech metadata.csv.")

        metadata_text = metadata_file.read().decode("utf-8-sig")
        samples = parse_ljspeech_metadata(metadata_text, root_name, limit)

    return LJSpeechArchive(archive_path=archive_path, root_name=root_name, samples=tuple(samples))


def parse_ljspeech_metadata(
    metadata_text: str,
    root_name: str = "LJSpeech-1.1",
    limit: int | None = None,
) -> list[LJSpeechSample]:
    samples: list[LJSpeechSample] = []
    seen_ids: set[str] = set()

    for line_number, raw_line in enumerate(metadata_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split("|", 2)
        if len(parts) != 3:
            raise DatasetAdapterError(f"Invalid LJSpeech metadata row at line {line_number}.")

        sample_id, transcript, normalized_transcript = (part.strip() for part in parts)
        if not LJSPEECH_SAMPLE_ID.fullmatch(sample_id):
            raise DatasetAdapterError(f"Invalid LJSpeech sample id at line {line_number}: {sample_id}")
        if sample_id in seen_ids:
            raise DatasetAdapterError(f"Duplicate LJSpeech sample id: {sample_id}")
        if not transcript or not normalized_transcript:
            raise DatasetAdapterError(f"LJSpeech transcript text is missing at line {line_number}.")

        seen_ids.add(sample_id)
        samples.append(
            LJSpeechSample(
                sample_id=sample_id,
                transcript=transcript,
                normalized_transcript=normalized_transcript,
                wav_member=f"{root_name}/wavs/{sample_id}.wav",
            )
        )
        if limit is not None and len(samples) >= limit:
            break

    if not samples:
        raise DatasetAdapterError("LJSpeech metadata.csv contains no samples.")

    return samples


def extract_ljspeech_sample(
    archive_path: Path,
    sample_id: str,
    destination_dir: Path,
    *,
    manifest: LJSpeechArchive | None = None,
) -> Path:
    manifest = manifest or load_ljspeech_archive(archive_path)
    sample = manifest.get_sample(sample_id)

    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_path = destination_dir / f"{sample.sample_id}.wav"

    with tarfile.open(archive_path, "r:*") as archive:
        try:
            wav_member = archive.getmember(sample.wav_member)
        except KeyError as exc:
            raise DatasetAdapterError(f"LJSpeech WAV is missing: {sample.wav_member}") from exc
        if not wav_member.isfile():
            raise DatasetAdapterError(f"LJSpeech WAV member is not a file: {sample.wav_member}")

        source = archive.extractfile(wav_member)
        if source is None:
            raise DatasetAdapterError(f"Could not read LJSpeech WAV: {sample.wav_member}")

        with destination_path.open("wb") as target:
            shutil.copyfileobj(source, target)

    return destination_path


def _find_ljspeech_metadata(archive: tarfile.TarFile) -> tarfile.TarInfo | None:
    for member in archive:
        if member.isfile() and member.name.replace("\\", "/").endswith(f"/{LJSPEECH_METADATA}"):
            return member
    return None


def _archive_root(member_name: str) -> str:
    parts = member_name.replace("\\", "/").split("/")
    if len(parts) < 2 or parts[-1] != LJSPEECH_METADATA or not parts[0]:
        raise DatasetAdapterError("LJSpeech metadata.csv must live under a dataset root directory.")
    return parts[0]
