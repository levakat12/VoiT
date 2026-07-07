from app.services.parakeet import _parse_parakeet_response, _parse_text_response


def test_parse_parakeet_json_response_with_segments() -> None:
    text, segments = _parse_parakeet_response(
        {
            "text": "Hello world.",
            "segments": [
                {
                    "start": 0,
                    "end": 1.5,
                    "text": "Hello world.",
                    "confidence": 0.98,
                    "speaker": "Speaker 1",
                }
            ],
        }
    )

    assert text == "Hello world."
    assert segments[0].end == 1.5
    assert segments[0].confidence == 0.98


def test_parse_plain_text_response() -> None:
    text, segments = _parse_text_response("Hello from Parakeet.")

    assert text == "Hello from Parakeet."
    assert segments[0].text == text

