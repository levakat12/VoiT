import type { JobListItem, JobRead, SearchResult, TranscriptSegment } from "./types";

const DEFAULT_API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8100/api`;
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function uploadMedia(file: File): Promise<JobRead> {
  const body = new FormData();
  body.append("file", file);
  const payload = await request<{ job: JobRead }>("/uploads", {
    method: "POST",
    body
  });
  return payload.job;
}

export function listJobs(): Promise<JobListItem[]> {
  return request<JobListItem[]>("/jobs");
}

export function getJob(id: number): Promise<JobRead> {
  return request<JobRead>(`/jobs/${id}`);
}

export function searchTranscripts(query: string): Promise<SearchResult[]> {
  return request<SearchResult[]>(`/search?q=${encodeURIComponent(query)}`);
}

export function pauseJob(id: number): Promise<JobRead> {
  return request<JobRead>(`/jobs/${id}/pause`, {
    method: "POST"
  });
}

export function resumeJob(id: number): Promise<JobRead> {
  return request<JobRead>(`/jobs/${id}/resume`, {
    method: "POST"
  });
}

export function retryJob(id: number): Promise<JobRead> {
  return request<JobRead>(`/jobs/${id}/retry`, {
    method: "POST"
  });
}

export function cancelJob(id: number): Promise<JobRead> {
  return request<JobRead>(`/jobs/${id}/cancel`, {
    method: "POST"
  });
}

export function saveTranscript(
  id: number,
  transcriptText: string,
  segments?: TranscriptSegment[]
): Promise<JobRead> {
  return request<JobRead>(`/jobs/${id}/transcript`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      transcript_text: transcriptText,
      segments
    })
  });
}

export function exportUrl(id: number, format: string): string {
  return `${API_BASE_URL}/jobs/${id}/exports/${format}`;
}
