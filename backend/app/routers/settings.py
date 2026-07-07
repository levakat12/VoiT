from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas import SettingsRead
from app.services.insights import INSIGHT_EXPORT_FORMATS
from app.services.media import SUPPORTED_EXTENSIONS

router = APIRouter()


@router.get("/settings", response_model=SettingsRead)
def read_settings(settings: Settings = Depends(get_settings)) -> SettingsRead:
    return SettingsRead(
        env=settings.env,
        api_configured=bool(settings.parakeet_api_key),
        language=settings.parakeet_language,
        model=settings.parakeet_model or None,
        max_upload_mb=settings.max_upload_mb,
        allowed_origins=settings.allowed_origin_list,
        webhook_configured=bool(settings.webhook_url),
        supported_formats=sorted(SUPPORTED_EXTENSIONS),
        export_formats=["txt", "docx", "pdf", "json", "srt", "vtt"],
        insight_export_formats=INSIGHT_EXPORT_FORMATS,
        storage_dir=str(settings.storage_dir),
        normalized_sample_rate=settings.normalized_sample_rate,
    )
