from dataclasses import dataclass
from math import ceil
import textwrap

from app.schemas import TranscriptSegment


@dataclass(frozen=True)
class SubtitleOptions:
    max_chars: int = 42
    max_duration: float = 6.0
    max_lines: int = 2

    def __post_init__(self) -> None:
        if not 10 <= self.max_chars <= 120:
            raise ValueError("subtitle_max_chars must be between 10 and 120.")
        if not 0.5 <= self.max_duration <= 30:
            raise ValueError("subtitle_max_duration must be between 0.5 and 30 seconds.")
        if not 1 <= self.max_lines <= 4:
            raise ValueError("subtitle_max_lines must be between 1 and 4.")

    @property
    def text_limit(self) -> int:
        return self.max_chars * self.max_lines


def to_srt(segments: list[TranscriptSegment], options: SubtitleOptions | None = None) -> str:
    options = options or SubtitleOptions()
    blocks = []
    for index, segment in enumerate(_build_cues(segments, options), start=1):
        blocks.append(
            f"{index}\n"
            f"{_srt_timestamp(segment.start)} --> {_srt_timestamp(segment.end)}\n"
            f"{_wrap_text(segment.text, options)}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def to_vtt(segments: list[TranscriptSegment], options: SubtitleOptions | None = None) -> str:
    options = options or SubtitleOptions()
    blocks = ["WEBVTT"]
    for segment in _build_cues(segments, options):
        blocks.append(
            f"{_vtt_timestamp(segment.start)} --> {_vtt_timestamp(segment.end)}\n"
            f"{_wrap_text(segment.text, options)}"
        )
    return "\n\n".join(blocks) + "\n"


def _build_cues(
    segments: list[TranscriptSegment],
    options: SubtitleOptions,
) -> list[TranscriptSegment]:
    cues = []
    for segment in segments:
        cues.extend(_split_segment(segment, options))
    return cues


def _split_segment(segment: TranscriptSegment, options: SubtitleOptions) -> list[TranscriptSegment]:
    words = segment.text.strip().split()
    if not words:
        return [segment]

    chunks = _chunk_words_by_text(words, options.text_limit)
    target_chunks = ceil(max(segment.end - segment.start, 0) / options.max_duration)
    chunks = _split_chunks_for_duration(chunks, target_chunks)

    total_words = sum(len(chunk) for chunk in chunks)
    duration = max(segment.end - segment.start, 0.001)
    cursor = max(segment.start, 0)
    cues = []
    for index, chunk in enumerate(chunks):
        if index == len(chunks) - 1:
            end = max(segment.end, cursor + 0.001)
        else:
            end = cursor + duration * (len(chunk) / total_words)
        cues.append(
            TranscriptSegment(
                start=cursor,
                end=end,
                text=" ".join(chunk),
                confidence=segment.confidence,
                speaker=segment.speaker,
            )
        )
        cursor = end
    return cues


def _chunk_words_by_text(words: list[str], text_limit: int) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    current_length = 0
    for word in words:
        added_length = len(word) if not current else len(word) + 1
        if current and current_length + added_length > text_limit:
            chunks.append(current)
            current = [word]
            current_length = len(word)
        else:
            current.append(word)
            current_length += added_length
    if current:
        chunks.append(current)
    return chunks


def _split_chunks_for_duration(chunks: list[list[str]], target_chunks: int) -> list[list[str]]:
    target_chunks = max(target_chunks, 1)
    while len(chunks) < target_chunks:
        split_index = max(range(len(chunks)), key=lambda index: len(chunks[index]))
        chunk = chunks[split_index]
        if len(chunk) < 2:
            break
        midpoint = ceil(len(chunk) / 2)
        chunks = [*chunks[:split_index], chunk[:midpoint], chunk[midpoint:], *chunks[split_index + 1 :]]
    return chunks


def _wrap_text(text: str, options: SubtitleOptions) -> str:
    lines = textwrap.wrap(
        text.strip(),
        width=options.max_chars,
        break_long_words=True,
        break_on_hyphens=False,
    )
    return "\n".join(lines[: options.max_lines])


def _srt_timestamp(seconds: float) -> str:
    hours, remainder = divmod(max(seconds, 0), 3600)
    minutes, remainder = divmod(remainder, 60)
    whole_seconds = int(remainder)
    milliseconds = int(round((remainder - whole_seconds) * 1000))
    if milliseconds == 1000:
        whole_seconds += 1
        milliseconds = 0
    return f"{int(hours):02}:{int(minutes):02}:{whole_seconds:02},{milliseconds:03}"


def _vtt_timestamp(seconds: float) -> str:
    return _srt_timestamp(seconds).replace(",", ".")
