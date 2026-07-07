# VoiT Roadmap

## Phase 1: Core MVP

Implemented in this starter version:

- File upload validation.
- Multiple file selection from the simple upload window.
- Media metadata extraction.
- Corrupted or unreadable media detection when FFmpeg is available.
- Audio extraction and normalization to mono 16 kHz WAV.
- Transcription service boundary for Parakeet/NVIDIA ASR HTTP APIs.
- Processing stage, progress percentage, processing time, and export history tracking.
- Simple transcript viewer workflow.
- Editable transcript persistence.
- TXT, DOCX, PDF, JSON, SRT, and VTT exports.
- Text-window export format selector and download control.
- SRT/VTT subtitle cue length, duration, and line-count controls.
- History list with a compact recent-transcripts picker and search field in the upload window.
- Spec-compatible REST aliases for upload, history, transcript lookup, transcript delete, and export.
- Retry endpoint for failed or completed transcription jobs.
- Cancel endpoint with cooperative cancellation checks during processing.
- Startup recovery for queued or interrupted background jobs.
- ETA and processing speed metrics for running jobs.
- Optional signed webhooks for finished background jobs.
- Safe settings endpoint for configured formats, limits, language, storage, and API-key presence.
- Cross-transcript search endpoint with result snippets.
- Settings through environment variables.

Next items:

- Confirm the production hosted Parakeet endpoint URL for the provided API key.
- User accounts and encrypted API key storage.
- External worker queue for multi-process production deployments.

## Phase 2: Professional Features

Implemented:

- Backend batch upload endpoint through `POST /api/uploads/batch`.
- Pause and resume endpoints for queued or running jobs.
- Dedicated pause, resume, and cancel controls in the frontend upload window.
- Browser desktop notifications when active jobs complete, fail, or are canceled.

## Phase 3: AI Enhancement

Implemented:

- Local transcript cleanup, summaries, chapters, keyword extraction, and speaker analytics through `GET /api/jobs/{job_id}/insights`.
- JSON, TXT, and Markdown insight exports through `GET /api/jobs/{job_id}/insights/exports/{format}`.

Next items:

- AI model-backed transcript cleanup and summaries.

## Phase 4: Search

Implemented:

- Search across stored transcript text and timestamp segments through `GET /api/search?q=...`.
- Search filters by date, project, tag, status, and media/file format.
- SQLite full-text indexes for larger transcript libraries.

## Phase 5: Organization

Implemented:

- Project, folder, tags, favorite, and archive metadata for transcript jobs.
- History filters for archived jobs, project, tag, and favorite state.
- Bulk organization updates through `PATCH /api/jobs/organization/bulk`.

Next items:

- Dedicated organization UI.
