import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Download, Loader2, Pause, Play, RefreshCw, Save, Search, Upload, X } from "lucide-react";
import {
  cancelJob,
  exportUrl,
  getJob,
  listJobs,
  pauseJob,
  resumeJob,
  saveTranscript,
  searchTranscripts,
  uploadMedia,
} from "./api";
import type { JobListItem, JobRead, SearchResult } from "./types";

type ExportFormat = "txt" | "docx" | "pdf" | "json" | "srt" | "vtt";

export default function App() {
  const [job, setJob] = useState<JobRead | null>(null);
  const [text, setText] = useState("");
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [exportFormat, setExportFormat] = useState<ExportFormat>("txt");
  const [isDirty, setDirty] = useState(false);
  const [isUploading, setUploading] = useState(false);
  const [isSearching, setSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [message, setMessage] = useState("Ready");
  const notifiedJobRef = useRef<string | null>(null);

  const refreshJobs = useCallback(async () => {
    const nextJobs = await listJobs();
    setJobs(nextJobs.slice(0, 8));
  }, []);

  useEffect(() => {
    void refreshJobs().catch(() => setMessage("History unavailable"));
  }, [refreshJobs]);

  useEffect(() => {
    if (!job || !isActiveStatus(job.status)) return;

    const timer = window.setInterval(async () => {
      const nextJob = await getJob(job.id);
      setJob(nextJob);
      setMessage(statusMessage(nextJob));
      if (isFinalStatus(nextJob.status)) {
        void refreshJobs().catch(() => undefined);
      }
      if (!isDirty) {
        setText(nextJob.transcript_text);
      }
    }, 2000);

    return () => window.clearInterval(timer);
  }, [isDirty, job, refreshJobs]);

  useEffect(() => {
    if (!job || !isFinalStatus(job.status)) return;

    const notificationKey = `${job.id}:${job.status}`;
    if (notifiedJobRef.current === notificationKey) return;
    notifiedJobRef.current = notificationKey;
    showJobNotification(job);
  }, [job]);

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (files.length === 0) return;

    requestNotificationPermission();
    setUploading(true);
    setMessage("Uploading...");
    setDirty(false);

    try {
      for (const [index, file] of files.entries()) {
        setMessage(files.length > 1 ? `Uploading ${index + 1} of ${files.length}...` : "Uploading...");
        const nextJob = await uploadMedia(file);
        setJob(nextJob);
        setText(nextJob.transcript_text);
        setMessage(statusMessage(nextJob));
        await refreshJobs();
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function handleSave() {
    if (!job) return;

    const saved = await saveTranscript(job.id, text, job.segments);
    setJob(saved);
    setDirty(false);
    setMessage("Saved");
    await refreshJobs();
  }

  async function handleJobAction(action: "pause" | "resume" | "cancel") {
    if (!job) return;

    try {
      const nextJob =
        action === "pause"
          ? await pauseJob(job.id)
          : action === "resume"
            ? await resumeJob(job.id)
            : await cancelJob(job.id);
      setJob(nextJob);
      setMessage(statusMessage(nextJob));
      await refreshJobs();
      if (!isDirty) {
        setText(nextJob.transcript_text);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed.");
    }
  }

  async function handleSelectJob(jobId: number) {
    try {
      const selectedJob = await getJob(jobId);
      setJob(selectedJob);
      setText(selectedJob.transcript_text);
      setDirty(false);
      setMessage(statusMessage(selectedJob));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load transcript.");
    }
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = searchQuery.trim();
    if (!query) {
      setHasSearched(false);
      setSearchResults([]);
      await refreshJobs();
      return;
    }

    setSearching(true);
    try {
      const results = await searchTranscripts(query);
      setSearchResults(results);
      setHasSearched(true);
      setMessage(results.length ? `${results.length} found` : "No matches");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Search failed.");
    } finally {
      setSearching(false);
    }
  }

  function handleExport() {
    if (!job || job.status !== "completed") return;
    window.open(exportUrl(job.id, exportFormat), "_blank", "noopener,noreferrer");
  }

  return (
    <main className="appShell">
      <section className="window uploadWindow">
        <div>
          <h1>VoiT</h1>
          <p>{message}</p>
        </div>

        <label className="uploadButton">
          {isUploading || job?.status === "running" || job?.status === "pending" ? (
            <Loader2 className="spin" size={20} />
          ) : (
            <Upload size={20} />
          )}
          <span>Upload</span>
          <input
            type="file"
            multiple
            accept=".mp4,.mov,.mkv,.avi,.webm,.mp3,.wav,.flac,.m4a,.aac"
            onChange={handleUpload}
          />
        </label>

        <div className="fileName">{job?.filename ?? "No file selected"}</div>

        {job && !isFinalStatus(job.status) ? (
          <div className="jobControls">
            <button
              type="button"
              className="iconButton"
              onClick={() => void handleJobAction(job.status === "paused" ? "resume" : "pause")}
              disabled={job.status !== "paused" && !isActiveStatus(job.status)}
              title={job.status === "paused" ? "Resume" : "Pause"}
              aria-label={job.status === "paused" ? "Resume" : "Pause"}
            >
              {job.status === "paused" ? <Play size={18} /> : <Pause size={18} />}
            </button>
            <button
              type="button"
              className="iconButton"
              onClick={() => void handleJobAction("cancel")}
              disabled={!isActiveStatus(job.status)}
              title="Cancel"
              aria-label="Cancel"
            >
              <X size={18} />
            </button>
          </div>
        ) : null}

        <div className="recentBlock">
          <div className="recentHeader">
            <span>Recent</span>
            <button
              type="button"
              className="smallIconButton"
              onClick={() => void refreshJobs().catch(() => setMessage("History unavailable"))}
              title="Refresh"
              aria-label="Refresh recent transcripts"
            >
              <RefreshCw size={16} />
            </button>
          </div>
          <form className="searchForm" onSubmit={(event) => void handleSearch(event)}>
            <input
              className="searchInput"
              value={searchQuery}
              onChange={(event) => {
                setSearchQuery(event.target.value);
                if (!event.target.value.trim()) {
                  setHasSearched(false);
                  setSearchResults([]);
                }
              }}
              placeholder="Search"
              aria-label="Search transcripts"
            />
            <button
              type="submit"
              className="smallIconButton"
              disabled={isSearching}
              title="Search"
              aria-label="Search transcripts"
            >
              {isSearching ? <Loader2 className="spin" size={16} /> : <Search size={16} />}
            </button>
          </form>
          <div className="recentList">
            {hasSearched ? (
              searchResults.length ? (
                searchResults.map((item) => (
                  <button
                    type="button"
                    key={item.job_id}
                    className={item.job_id === job?.id ? "recentJob active" : "recentJob"}
                    onClick={() => void handleSelectJob(item.job_id)}
                    title={item.filename}
                  >
                    <span>{item.filename}</span>
                    <small>{statusLabel(item.status)}</small>
                  </button>
                ))
              ) : (
                <div className="emptyRecent">No matches</div>
              )
            ) : jobs.length ? (
              jobs.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  className={item.id === job?.id ? "recentJob active" : "recentJob"}
                  onClick={() => void handleSelectJob(item.id)}
                  title={item.filename}
                >
                  <span>{item.filename}</span>
                  <small>{statusLabel(item.status)}</small>
                </button>
              ))
            ) : (
              <div className="emptyRecent">No transcripts yet</div>
            )}
          </div>
        </div>
      </section>

      <section className="window textWindow">
        <div className="textHeader">
          <h2>Text</h2>
          <div className="textActions">
            <select
              className="exportSelect"
              value={exportFormat}
              onChange={(event) => setExportFormat(event.target.value as ExportFormat)}
              aria-label="Export format"
              disabled={!job || job.status !== "completed"}
            >
              <option value="txt">TXT</option>
              <option value="docx">DOCX</option>
              <option value="pdf">PDF</option>
              <option value="json">JSON</option>
              <option value="srt">SRT</option>
              <option value="vtt">VTT</option>
            </select>
            <button
              className="exportButton"
              onClick={handleExport}
              disabled={!job || job.status !== "completed"}
              title="Download"
              aria-label="Download transcript"
            >
              <Download size={18} />
            </button>
            <button className="saveButton" onClick={() => void handleSave()} disabled={!job || !isDirty}>
              <Save size={18} />
              <span>Save</span>
            </button>
          </div>
        </div>

        <textarea
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            setDirty(true);
          }}
          placeholder="Transcript will appear here."
        />
      </section>
    </main>
  );
}

function statusLabel(status: JobRead["status"]): string {
  if (status === "completed") return "Complete";
  if (status === "failed") return "Failed";
  if (status === "canceled") return "Canceled";
  if (status === "paused") return "Paused";
  if (status === "running") return "Running";
  return "Waiting";
}

function isFinalStatus(status: JobRead["status"]): boolean {
  return status === "completed" || status === "failed" || status === "canceled";
}

function isActiveStatus(status: JobRead["status"]): boolean {
  return status === "pending" || status === "running";
}

function statusMessage(job: JobRead): string {
  if (job.status === "completed") return "Complete";
  if (job.status === "paused") return "Paused";
  if (job.status === "canceled") return "Canceled";
  if (job.status === "failed") return job.error_message || "Failed";
  if (job.status === "running") {
    return `${job.current_stage} (${job.progress_percent}%)${metricMessage(job)}`;
  }
  return "Waiting...";
}

function requestNotificationPermission(): void {
  if (!("Notification" in window) || Notification.permission !== "default") return;
  void Notification.requestPermission();
}

function showJobNotification(job: JobRead): void {
  if (!("Notification" in window) || Notification.permission !== "granted") return;

  const body =
    job.status === "completed"
      ? `${job.filename} is ready.`
      : job.status === "failed"
        ? `${job.filename} failed: ${job.error_message || "Transcription failed."}`
        : `${job.filename} was canceled.`;

  new Notification("VoiT", {
    body,
    tag: `voit-job-${job.id}`,
  });
}

function metricMessage(job: JobRead): string {
  const parts = [];
  if (job.estimated_remaining_seconds != null) {
    parts.push(`${formatDuration(job.estimated_remaining_seconds)} left`);
  }
  if (job.processing_speed != null) {
    parts.push(`${job.processing_speed.toFixed(1)}x`);
  }
  return parts.length ? ` - ${parts.join(" / ")}` : "";
}

function formatDuration(seconds: number): string {
  const safeSeconds = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  const remainder = safeSeconds % 60;
  if (minutes === 0) return `${remainder}s`;
  return `${minutes}m ${remainder.toString().padStart(2, "0")}s`;
}
