# VoiT

VoiT is a simple transcription app for audio and video files. You upload a file on the left, and the transcript appears in the text window on the right. The interface is intentionally small: one upload area, one transcript area, and enough controls to search, save, copy, and export the text without turning the app into a dashboard.

Behind that simple screen, VoiT does the heavier work for you:

- accepts common audio and video files
- checks that the file has a readable audio stream
- converts the audio to clean mono 16 kHz WAV for transcription
- sends the normalized audio to a Parakeet/NVIDIA-compatible ASR service
- stores jobs and transcript history in SQLite
- lets you reopen, search, edit, save, and export transcripts
- creates TXT, DOCX, PDF, JSON, SRT, and VTT exports
- can pause, resume, retry, or cancel jobs
- can generate basic transcript insights such as cleanup text, summary, chapters, keywords, and speaker analytics

If no Parakeet API key is configured, the backend returns a predictable development transcript. That means you can still run the app locally, test uploads, and work on the UI before connecting a real transcription service.

## Project Structure

```text
backend/      FastAPI app, database models, media processing, transcription, exports
frontend/     React + TypeScript Vite app
docs/         Roadmap and product notes
docker/       Container files
```

## Supported Uploads

VoiT accepts:

```text
.mp4, .mov, .mkv, .avi, .webm, .mp3, .wav, .flac, .m4a, .aac
```

FFmpeg is required for non-WAV files because the backend uses `ffprobe` to inspect media and `ffmpeg` to extract/normalize audio. Simple PCM WAV files can work without FFmpeg, but installing FFmpeg is strongly recommended.

On Windows, one easy option is:

```powershell
winget install --id Gyan.FFmpeg --exact --scope user
```

If FFmpeg is installed but not on PATH yet, VoiT also tries to find WinGet and Chocolatey installations automatically.

## Requirements

- Python 3.12
- Node.js
- pnpm
- FFmpeg and FFprobe

The backend currently uses Python 3.12 because Python 3.13 removed `audioop`, which the WAV fallback path still uses.

## Setup

Clone the repository and move into it:

```powershell
git clone https://github.com/levakat12/VoiT.git D:\VoiT
cd D:\VoiT
```

Create your environment file:

```powershell
Copy-Item .env.example .env
```

Install and start the backend:

```powershell
cd D:\VoiT\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8100
```

In a second terminal, install and start the frontend:

```powershell
cd D:\VoiT
pnpm install
pnpm --dir frontend dev --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173/
```

The backend health check is:

```text
http://127.0.0.1:8100/api/health
```

## Configuration

Most local settings live in `.env`. Do not commit `.env`.

```env
VOIT_ENV=development
VOIT_DATABASE_URL=sqlite:///./voit.db
VOIT_STORAGE_DIR=./storage
VOIT_MAX_UPLOAD_MB=2048
VOIT_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

PARAKEET_API_KEY=
PARAKEET_API_URL=http://localhost:9000/v1/audio/transcriptions
PARAKEET_FUNCTION_ID=
PARAKEET_LANGUAGE=en-US
PARAKEET_MODEL=
PARAKEET_RETRIES=2
PARAKEET_TIMEOUT_SECONDS=180
```

For a live transcription service, set `PARAKEET_API_KEY` and point `PARAKEET_API_URL` at your Parakeet/NVIDIA ASR endpoint.

For hosted NVIDIA Riva/Parakeet gRPC-style usage, you can also set:

```env
PARAKEET_FUNCTION_ID=your-function-id
```

## Webhooks

VoiT can call a webhook after a job finishes. This is optional.

```env
VOIT_WEBHOOK_URL=https://example.com/voit-webhook
VOIT_WEBHOOK_SECRET=your-signing-secret
VOIT_WEBHOOK_RETRIES=2
VOIT_WEBHOOK_TIMEOUT_SECONDS=10
```

When `VOIT_WEBHOOK_SECRET` is set, VoiT sends an `X-VoiT-Signature` HMAC header. Webhook payloads include job metadata, not the transcript text.

## Running Tests

Backend:

```powershell
cd D:\VoiT\backend
.\.venv\Scripts\Activate.ps1
python -m pytest
```

Frontend build:

```powershell
cd D:\VoiT
pnpm --dir frontend build
```

## API Overview

The frontend uses the API automatically, but these are the main routes:

- `GET /api/health`
- `GET /api/settings`
- `POST /api/upload`
- `POST /api/uploads`
- `POST /api/uploads/batch`
- `GET /api/history`
- `GET /api/search?q={query}`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/retry`
- `POST /api/jobs/{job_id}/pause`
- `POST /api/jobs/{job_id}/resume`
- `POST /api/jobs/{job_id}/cancel`
- `PATCH /api/jobs/{job_id}/transcript`
- `GET /api/jobs/{job_id}/insights`
- `GET /api/jobs/{job_id}/exports/{format}`
- `POST /api/export`

Search supports filters such as project, tag, status, date range, format, and archived state.

Subtitle exports support optional controls for cue length, duration, and line count.

## Docker

The repository includes Docker files, so the app can also be started with:

```powershell
docker compose up --build
```

For day-to-day development on Windows, the two-terminal local setup above is usually easier to debug.
