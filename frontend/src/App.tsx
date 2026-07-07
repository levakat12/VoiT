import { ChangeEvent, useEffect, useRef, useState } from "react";
import { Loader2, Save, Upload } from "lucide-react";
import { getJob, saveTranscript, uploadMedia } from "./api";
import type { JobRead } from "./types";

export default function App() {
  const [job, setJob] = useState<JobRead | null>(null);
  const [text, setText] = useState("");
  const [isDirty, setDirty] = useState(false);
  const [isUploading, setUploading] = useState(false);
  const [message, setMessage] = useState("Ready");
  const notifiedJobRef = useRef<string | null>(null);

  useEffect(() => {
    if (!job || isFinalStatus(job.status)) return;

    const timer = window.setInterval(async () => {
      const nextJob = await getJob(job.id);
      setJob(nextJob);
      setMessage(statusMessage(nextJob));
      if (!isDirty) {
        setText(nextJob.transcript_text);
      }
    }, 2000);

    return () => window.clearInterval(timer);
  }, [isDirty, job]);

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
      </section>

      <section className="window textWindow">
        <div className="textHeader">
          <h2>Text</h2>
          <button className="saveButton" onClick={() => void handleSave()} disabled={!job || !isDirty}>
            <Save size={18} />
            <span>Save</span>
          </button>
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

function isFinalStatus(status: JobRead["status"]): boolean {
  return status === "completed" || status === "failed" || status === "canceled";
}

function statusMessage(job: JobRead): string {
  if (job.status === "completed") return "Complete";
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
