import type { JobListItem, JobRead, SearchResult, TranscriptSegment } from "./types";

const DEFAULT_API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8100/api`;
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const message = await errorMessage(response);
    throw new Error(message || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function errorMessage(response: Response): Promise<string> {
  const text = await response.text();
  if (!text) return "";
  try {
    const payload = JSON.parse(text) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((item) => (typeof item === "string" ? item : JSON.stringify(item))).join("; ");
    }
  } catch {
    return text;
  }
  return text;
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

export async function uploadMediaUrl(url: string): Promise<JobRead> {
  const payload = await request<{ job: JobRead }>("/uploads/url", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ url })
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

export function mediaUrl(id: number): string {
  return `${API_BASE_URL}/jobs/${id}/media`;
}
