from pathlib import Path

from app.config import Settings
from app.routers.settings import read_settings


def test_read_settings_does_not_expose_api_key() -> None:
    settings = Settings(
        storage_dir=Path("storage"),
        PARAKEET_API_KEY="secret",
        PARAKEET_MODEL="parakeet-0.6b-tdt",
        VOIT_WEBHOOK_URL="https://example.test/webhook",
        VOIT_WEBHOOK_SECRET="webhook-secret",
    )

    payload = read_settings(settings)

    assert payload.api_configured is True
    assert payload.model == "parakeet-0.6b-tdt"
    assert payload.webhook_configured is True
    assert not hasattr(payload, "parakeet_api_key")
    assert not hasattr(payload, "webhook_url")
    assert not hasattr(payload, "webhook_secret")
