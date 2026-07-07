from app.schemas import TranscriptSegment
from app.services.subtitles import SubtitleOptions, to_srt, to_vtt


def test_to_srt_formats_timestamp() -> None:
    output = to_srt([TranscriptSegment(start=1.25, end=2.5, text="Hello")])

    assert "00:00:01,250 --> 00:00:02,500" in output
    assert output.startswith("1\n")


def test_to_vtt_adds_header() -> None:
    output = to_vtt([TranscriptSegment(start=0, end=1, text="Hello")])

    assert output.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.000" in output


def test_to_srt_splits_long_segments_by_character_limit() -> None:
    output = to_srt(
        [
            TranscriptSegment(
                start=0,
                end=6,
                text="alpha beta gamma delta epsilon zeta",
            )
        ],
        SubtitleOptions(max_chars=10, max_duration=30, max_lines=1),
    )

    assert output.count("\n\n") >= 2
    assert "1\n00:00:00,000 -->" in output
    assert "2\n" in output


def test_to_vtt_wraps_cue_lines() -> None:
    output = to_vtt(
        [TranscriptSegment(start=0, end=1, text="hello world")],
        SubtitleOptions(max_chars=10, max_duration=30, max_lines=2),
    )

    assert "hello\nworld" in output
