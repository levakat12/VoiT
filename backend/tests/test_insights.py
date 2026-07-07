from app.schemas import TranscriptSegment
from app.services.insights import (
    build_insights_export,
    build_chapters,
    build_speaker_analytics,
    build_transcript_insights,
    clean_transcript,
    extract_keywords,
    summarize_text,
)


def test_clean_transcript_collapses_whitespace_and_punctuation() -> None:
    assert clean_transcript(" Hello   world  !  Next line. ") == "Hello world! Next line."


def test_summarize_text_uses_first_sentences() -> None:
    summary = summarize_text("First point. Second point. Third point. Fourth point.")

    assert summary == "First point. Second point. Third point."


def test_extract_keywords_counts_non_stop_words() -> None:
    keywords = extract_keywords("GPU budget planning. GPU scheduling and budget review.")

    assert keywords[:3] == ["gpu", "budget", "planning"]


def test_build_chapters_groups_segments() -> None:
    chapters = build_chapters(
        [
            TranscriptSegment(start=0, end=1, text="GPU scheduling starts."),
            TranscriptSegment(start=1, end=2, text="Budget review follows."),
            TranscriptSegment(start=2, end=3, text="Launch tasks close."),
        ],
        "",
        target_chapter_count=2,
    )

    assert len(chapters) == 2
    assert chapters[0].start == 0
    assert chapters[-1].end == 3


def test_build_speaker_analytics_rolls_up_segments() -> None:
    analytics = build_speaker_analytics(
        [
            TranscriptSegment(start=0, end=2, text="hello world", speaker="A"),
            TranscriptSegment(start=2, end=5, text="next topic", speaker="A"),
            TranscriptSegment(start=5, end=6, text="reply", speaker="B"),
        ]
    )

    assert analytics[0].speaker == "A"
    assert analytics[0].segment_count == 2
    assert analytics[0].duration_seconds == 5
    assert analytics[0].word_count == 4


def test_build_transcript_insights_returns_all_sections() -> None:
    insights = build_transcript_insights(
        9,
        "GPU planning is important. Budget planning is next.",
        [TranscriptSegment(start=0, end=4, text="GPU planning is important.", speaker="Speaker 1")],
    )

    assert insights.job_id == 9
    assert insights.summary.startswith("GPU planning")
    assert "planning" in insights.keywords
    assert insights.chapters
    assert insights.speaker_analytics[0].speaker == "Speaker 1"


def test_build_insights_export_supports_json_text_and_markdown() -> None:
    insights = build_transcript_insights(
        4,
        "GPU planning is important.",
        [TranscriptSegment(start=0, end=4, text="GPU planning is important.", speaker="A")],
    )

    json_content, json_media_type, json_extension = build_insights_export(insights, "json")
    text_content, text_media_type, text_extension = build_insights_export(insights, "txt")
    markdown_content, markdown_media_type, markdown_extension = build_insights_export(insights, "md")

    assert '"job_id": 4' in json_content
    assert json_media_type == "application/json"
    assert json_extension == "json"
    assert "Transcript Insights for Job 4" in text_content
    assert text_media_type == "text/plain"
    assert text_extension == "txt"
    assert "# Transcript Insights for Job 4" in markdown_content
    assert markdown_media_type == "text/markdown"
    assert markdown_extension == "md"
