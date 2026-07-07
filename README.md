# VoiT

VoiT is an AI video and audio transcription platform. This repository starts the product described in `AI_Video_Transcription_Platform_Project_Outline.md` with a FastAPI backend and a React/TypeScript frontend.

## Current MVP

- Upload one or more audio/video files with extension and size validation.
- Store processing history in SQLite.
- Extract media metadata with `ffprobe` when FFmpeg is installed.
- Validate readable audio streams with `ffprobe`.
- Extract and normalize audio to mono 16 kHz WAV with `ffmpeg`.
- Send normalized audio through a Parakeet/NVIDIA ASR-compatible service boundary.
- Track current processing stage, progress percentage, processing time, and export history.
- Expose safe settings metadata without returning secrets.
- Search across stored transcripts with matching snippets and metadata filters.
- Organize jobs with project, folder, tags, favorite, and archive metadata.
- Use a development transcript fallback when no Parakeet API key is configured.
- View, search, edit, save, and export transcripts.
- Generate TXT, DOCX, PDF, JSON, SRT, and VTT exports.
- Tune SRT/VTT exports with maximum cue characters, duration, and line count.

The visible app is intentionally simple: an upload window and a text window. Additional export routes are available through the API.

## Repository Layout

```text
backend/     FastAPI app, persistence, transcription, subtitle, and export services
frontend/    React + TypeScript app
docs/        Product notes and implementation roadmap
docker/      Container files
```

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8100
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### Docker Compose

```bash
docker compose up --build
```

## Parakeet Configuration

Set `PARAKEET_API_KEY` and `PARAKEET_API_URL` in `.env` or the deployment environment. Do not commit `.env`.

```bash
PARAKEET_API_KEY=your-secret-key
PARAKEET_API_URL=http://localhost:9000/v1/audio/transcriptions
PARAKEET_LANGUAGE=en-US
```

The default API shape follows NVIDIA Speech NIM's HTTP ASR endpoint, `POST /v1/audio/transcriptions`, which accepts `multipart/form-data` with a WAV, OPUS, or FLAC file plus language/model selection. Without a key, VoiT returns a deterministic development transcript so the rest of the app remains usable during local development.

## API Summary

- `GET /api/health`
- `GET /api/settings`
- `POST /api/upload`
- `POST /api/uploads`
- `GET /api/history`
- `GET /api/search?q={query}` with optional `project`, `tag`, `status`, `created_from`, `created_to`, `format`, and `include_archived` filters
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/retry`
- `POST /api/jobs/{job_id}/cancel`
- `PATCH /api/jobs/{job_id}/organization`
- `GET /api/transcript/{job_id}`
- `DELETE /api/transcript/{job_id}`
- `PATCH /api/jobs/{job_id}/transcript`
- `POST /api/export`
- `GET /api/jobs/{job_id}/exports/{format}`

SRT/VTT exports accept optional subtitle controls:

- `subtitle_max_chars` between 10 and 120
- `subtitle_max_duration` between 0.5 and 30 seconds
- `subtitle_max_lines` between 1 and 4
