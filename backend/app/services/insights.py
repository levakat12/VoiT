import re
from collections import Counter, defaultdict

from app.schemas import SpeakerAnalytics, TranscriptChapter, TranscriptInsights, TranscriptSegment

INSIGHT_EXPORT_FORMATS = ["json", "txt", "md"]

STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "because",
    "been",
    "but",
    "for",
    "from",
    "have",
    "into",
    "our",
    "that",
    "the",
    "their",
    "this",
    "was",
    "were",
    "with",
    "you",
    "your",
}


def build_transcript_insights(
    job_id: int,
    transcript_text: str,
    segments: list[TranscriptSegment],
) -> TranscriptInsights:
    cleaned_text = clean_transcript(transcript_text)
    return TranscriptInsights(
        job_id=job_id,
        cleaned_text=cleaned_text,
        summary=summarize_text(cleaned_text),
        chapters=build_chapters(segments, cleaned_text),
        keywords=extract_keywords(cleaned_text),
        speaker_analytics=build_speaker_analytics(segments),
    )


def build_insights_export(insights: TranscriptInsights, export_format: str) -> tuple[str, str, str]:
    normalized_format = export_format.casefold().strip()
    if normalized_format == "json":
        return insights.model_dump_json(indent=2), "application/json", "json"
    if normalized_format == "txt":
        return _insights_to_text(insights), "text/plain", "txt"
    if normalized_format == "md":
        return _insights_to_markdown(insights), "text/markdown", "md"
    raise ValueError("Unsupported insight export format.")


def clean_transcript(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return cleaned


def summarize_text(text: str, max_sentences: int = 3) -> str:
    sentences = _sentences(text)
    if not sentences:
        return ""
    return " ".join(sentences[:max_sentences])


def extract_keywords(text: str, limit: int = 10) -> list[str]:
    words = [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", text.casefold())
        if word not in STOP_WORDS
    ]
    counts = Counter(words)
    return [word for word, _ in counts.most_common(limit)]


def build_chapters(
    segments: list[TranscriptSegment],
    fallback_text: str,
    target_chapter_count: int = 4,
) -> list[TranscriptChapter]:
    if not segments:
        summary = summarize_text(fallback_text, max_sentences=1)
        return [TranscriptChapter(title=_chapter_title(summary), start=0, end=0, summary=summary)]

    group_size = max(1, round(len(segments) / target_chapter_count))
    chapters = []
    for index in range(0, len(segments), group_size):
        group = segments[index : index + group_size]
        text = clean_transcript(" ".join(segment.text for segment in group))
        chapters.append(
            TranscriptChapter(
                title=_chapter_title(text),
                start=min(segment.start for segment in group),
                end=max(segment.end for segment in group),
                summary=summarize_text(text, max_sentences=1),
            )
        )
    return chapters


def build_speaker_analytics(segments: list[TranscriptSegment]) -> list[SpeakerAnalytics]:
    stats: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"segment_count": 0, "duration_seconds": 0.0, "word_count": 0}
    )
    for segment in segments:
        speaker = segment.speaker or "Unknown"
        stats[speaker]["segment_count"] += 1
        stats[speaker]["duration_seconds"] += max(segment.end - segment.start, 0)
        stats[speaker]["word_count"] += len(segment.text.split())

    return [
        SpeakerAnalytics(
            speaker=speaker,
            segment_count=int(values["segment_count"]),
            duration_seconds=round(float(values["duration_seconds"]), 3),
            word_count=int(values["word_count"]),
        )
        for speaker, values in sorted(stats.items())
    ]


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def _chapter_title(text: str) -> str:
    keywords = extract_keywords(text, limit=3)
    if keywords:
        return " / ".join(word.title() for word in keywords)
    words = text.split()
    return " ".join(words[:5]) or "Transcript"


def _insights_to_text(insights: TranscriptInsights) -> str:
    lines = [
        f"Transcript Insights for Job {insights.job_id}",
        "",
        "Summary",
        insights.summary or "No summary available.",
        "",
        "Keywords",
        ", ".join(insights.keywords) or "No keywords available.",
        "",
        "Chapters",
    ]
    lines.extend(
        f"- {chapter.title} ({chapter.start:.3f}s-{chapter.end:.3f}s): {chapter.summary}"
        for chapter in insights.chapters
    )
    lines.extend(["", "Speaker Analytics"])
    lines.extend(
        f"- {speaker.speaker}: {speaker.segment_count} segments, "
        f"{speaker.duration_seconds:.3f}s, {speaker.word_count} words"
        for speaker in insights.speaker_analytics
    )
    lines.extend(["", "Cleaned Text", insights.cleaned_text])
    return "\n".join(lines).strip() + "\n"


def _insights_to_markdown(insights: TranscriptInsights) -> str:
    lines = [
        f"# Transcript Insights for Job {insights.job_id}",
        "",
        "## Summary",
        insights.summary or "No summary available.",
        "",
        "## Keywords",
        ", ".join(f"`{keyword}`" for keyword in insights.keywords) or "No keywords available.",
        "",
        "## Chapters",
    ]
    lines.extend(
        f"- **{chapter.title}** ({chapter.start:.3f}s-{chapter.end:.3f}s): {chapter.summary}"
        for chapter in insights.chapters
    )
    lines.extend(["", "## Speaker Analytics"])
    lines.extend(
        f"- **{speaker.speaker}**: {speaker.segment_count} segments, "
        f"{speaker.duration_seconds:.3f}s, {speaker.word_count} words"
        for speaker in insights.speaker_analytics
    )
    lines.extend(["", "## Cleaned Text", insights.cleaned_text])
    return "\n".join(lines).strip() + "\n"
