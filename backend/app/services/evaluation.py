from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import tarfile
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

from app.config import Settings
from app.services.dataset_adapters import DatasetAdapterError, load_ljspeech_archive
from app.services.parakeet import transcribe_media


@dataclass(frozen=True)
class TranscriptQuality:
    sample_id: str
    reference: str
    hypothesis: str
    word_error_rate: float
    character_error_rate: float


@dataclass(frozen=True)
class EvaluationSummary:
    dataset: str
    sample_count: int
    api_configured: bool
    mean_word_error_rate: float
    mean_character_error_rate: float
    samples: tuple[TranscriptQuality, ...]

    def to_dict(self) -> dict:
        return asdict(self)


async def evaluate_ljspeech_archive(
    archive_path: Path,
    settings: Settings,
    *,
    limit: int | None = None,
    work_dir: Path | None = None,
) -> EvaluationSummary:
    if limit is not None and limit <= 0:
        raise DatasetAdapterError("Evaluation sample limit must be greater than zero.")
    manifest = load_ljspeech_archive(archive_path)

    if work_dir is None:
        with tempfile.TemporaryDirectory(prefix="voit-ljspeech-") as temp_dir:
            return await _evaluate_manifest(archive_path, settings, manifest, Path(temp_dir), limit)
    return await _evaluate_manifest(archive_path, settings, manifest, work_dir, limit)


def word_error_rate(reference: str, hypothesis: str) -> float:
    reference_words = _normalize_for_words(reference)
    hypothesis_words = _normalize_for_words(hypothesis)
    if not reference_words:
        return 0.0 if not hypothesis_words else 1.0
    return _edit_distance(reference_words, hypothesis_words) / len(reference_words)


def character_error_rate(reference: str, hypothesis: str) -> float:
    normalized_reference = _normalize_for_chars(reference)
    normalized_hypothesis = _normalize_for_chars(hypothesis)
    if not normalized_reference:
        return 0.0 if not normalized_hypothesis else 1.0
    return _edit_distance(list(normalized_reference), list(normalized_hypothesis)) / len(normalized_reference)


async def _evaluate_manifest(
    archive_path: Path,
    settings: Settings,
    manifest,
    work_dir: Path,
    limit: int | None,
) -> EvaluationSummary:
    work_dir.mkdir(parents=True, exist_ok=True)
    results = []
    samples_by_member = {sample.wav_member: sample for sample in manifest.samples}

    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive:
            member_name = member.name.replace("\\", "/")
            sample = samples_by_member.get(member_name)
            if sample is None:
                continue
            if not member.isfile():
                raise DatasetAdapterError(f"LJSpeech WAV member is not a file: {member_name}")

            source = archive.extractfile(member)
            if source is None:
                raise DatasetAdapterError(f"Could not read LJSpeech WAV: {member_name}")

            wav_path = work_dir / f"{sample.sample_id}.wav"
            with wav_path.open("wb") as target:
                shutil.copyfileobj(source, target)

            hypothesis, _segments = await transcribe_media(wav_path, settings)
            reference = sample.normalized_transcript
            results.append(
                TranscriptQuality(
                    sample_id=sample.sample_id,
                    reference=reference,
                    hypothesis=hypothesis,
                    word_error_rate=round(word_error_rate(reference, hypothesis), 6),
                    character_error_rate=round(character_error_rate(reference, hypothesis), 6),
                )
            )
            wav_path.unlink(missing_ok=True)
            if limit is not None and len(results) >= limit:
                break

    if not results:
        raise DatasetAdapterError("No matching LJSpeech WAV samples were found in the archive.")

    return EvaluationSummary(
        dataset=manifest.root_name,
        sample_count=len(results),
        api_configured=bool(settings.parakeet_api_key),
        mean_word_error_rate=round(mean(item.word_error_rate for item in results), 6) if results else 0.0,
        mean_character_error_rate=round(mean(item.character_error_rate for item in results), 6) if results else 0.0,
        samples=tuple(results),
    )


def _normalize_for_words(text: str) -> list[str]:
    return _normalize_for_chars(text).split()


def _normalize_for_chars(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9\s']", " ", text.casefold())
    return re.sub(r"\s+", " ", normalized).strip()


def _edit_distance(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            insert_cost = current[right_index - 1] + 1
            delete_cost = previous[right_index] + 1
            replace_cost = previous[right_index - 1] + (left_value != right_value)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate VoiT transcription quality on LJSpeech.")
    parser.add_argument("archive", type=Path, help="Path to LJSpeech-1.1.tar.bz2")
    parser.add_argument("--limit", type=int, default=10, help="Number of samples to evaluate.")
    parser.add_argument("--full", action="store_true", help="Evaluate every sample in metadata.csv.")
    parser.add_argument("--output", type=Path, help="Optional JSON report path.")
    args = parser.parse_args()

    settings = Settings()
    limit = None if args.full else args.limit
    summary = asyncio.run(evaluate_ljspeech_archive(args.archive, settings, limit=limit))
    payload = json.dumps(summary.to_dict(), indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
