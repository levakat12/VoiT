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
- SRT/VTT subtitle cue length, duration, and line-count controls.
- History list.
- Spec-compatible REST aliases for upload, history, transcript lookup, transcript delete, and export.
- Retry endpoint for failed or completed transcription jobs.
- Cancel endpoint with cooperative cancellation checks during processing.
- ETA and processing speed metrics for running jobs.
- Safe settings endpoint for configured formats, limits, language, storage, and API-key presence.
- Cross-transcript search endpoint with result snippets.
- Settings through environment variables.

Next items:

- Confirm the production hosted Parakeet endpoint URL for the provided API key.
- User accounts and encrypted API key storage.
- Durable background queue with retry policies.

## Phase 2: Professional Features

- Batch uploads.
- Pause, resume, cancel, and retry.
- Desktop notifications and webhooks.

## Phase 3: AI Enhancement

- Transcript cleanup.
- Summaries.
- Chapters.
- Keyword extraction.
- Speaker analytics.

## Phase 4: Search

Implemented:

- Search across stored transcript text and timestamp segments through `GET /api/search?q=...`.
- Search filters by date, project, tag, status, and media/file format.

Next items:

- Full-text indexes for large transcript libraries.

## Phase 5: Organization

Implemented:

- Project, folder, tags, favorite, and archive metadata for transcript jobs.
- History filters for archived jobs, project, tag, and favorite state.

Next items:

- Dedicated organization UI.
- Bulk organization actions.
