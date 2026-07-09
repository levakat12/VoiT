import mimetypes
import re
from pathlib import Path
from uuid import uuid4


class LinkDownloadError(RuntimeError):
    pass


YOUTUBE_HOSTS = {
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "youtube.com",
    "youtube-nocookie.com",
    "www.youtube.com",
    "www.youtube-nocookie.com",
}


def is_youtube_host(hostname: str) -> bool:
    host = hostname.lower().strip(".")
    return host in YOUTUBE_HOSTS or host.endswith(".youtube.com")


def download_youtube_audio(url: str, destination_dir: Path, max_bytes: int) -> tuple[Path, str, str]:
    try:
        import yt_dlp
    except ImportError as exc:
        raise LinkDownloadError("YouTube links require yt-dlp. Install backend dependencies first.") from exc

    destination_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(destination_dir / f"{uuid4().hex}.%(ext)s")

    def progress_hook(progress: dict[str, object]) -> None:
        downloaded = progress.get("downloaded_bytes")
        if isinstance(downloaded, int) and downloaded > max_bytes:
            raise LinkDownloadError("Downloaded media exceeds upload size limit.")

    options = {
        "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "noplaylist": True,
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],
    }

    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
            downloaded_path = Path(downloader.prepare_filename(info))
    except LinkDownloadError:
        raise
    except Exception as exc:
        raise LinkDownloadError("YouTube media could not be downloaded.") from exc

    if not downloaded_path.exists():
        matches = sorted(destination_dir.glob(f"{downloaded_path.stem}.*"))
        if not matches:
            raise LinkDownloadError("YouTube media download did not create a file.")
        downloaded_path = matches[0]

    if downloaded_path.stat().st_size > max_bytes:
        downloaded_path.unlink(missing_ok=True)
        raise LinkDownloadError("Downloaded media exceeds upload size limit.")

    title = str(info.get("title") or "youtube-media")
    filename = _safe_media_filename(title, downloaded_path.suffix)
    media_type = mimetypes.guess_type(downloaded_path.name)[0] or "application/octet-stream"
    return downloaded_path, filename, media_type


def _safe_media_filename(title: str, suffix: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("._-") or "youtube-media"
    return f"{stem[:120]}{suffix.lower()}"
