export type JobStatus = "pending" | "running" | "completed" | "failed" | "canceled";

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
  confidence?: number | null;
  speaker?: string | null;
}

export interface JobListItem {
  id: number;
  filename: string;
  status: JobStatus;
  duration_seconds?: number | null;
  current_stage: string;
  progress_percent: number;
  processing_time_seconds?: number | null;
  estimated_remaining_seconds?: number | null;
  processing_speed?: number | null;
  project: string;
  folder: string;
  tags: string[];
  is_favorite: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface JobRead extends JobListItem {
  media_type: string;
  file_size: number;
  sample_rate?: number | null;
  channels?: number | null;
  transcript_text: string;
  segments: TranscriptSegment[];
  export_history: Array<{
    format: string;
    exported_at: string;
  }>;
  error_message: string;
}
