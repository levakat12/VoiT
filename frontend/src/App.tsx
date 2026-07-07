import { ChangeEvent, useEffect, useState } from "react";
import { Loader2, Save, Upload } from "lucide-react";
import { getJob, saveTranscript, uploadMedia } from "./api";
import type { JobRead } from "./types";

export default function App() {
  const [job, setJob] = useState<JobRead | null>(null);
  const [text, setText] = useState("");
  const [isDirty, setDirty] = useState(false);
  const [isUploading, setUploading] = useState(false);
  const [message, setMessage] = useState("Ready");

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;

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

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (files.length === 0) return;

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

function statusMessage(job: JobRead): string {
  if (job.status === "completed") return "Complete";
  if (job.status === "canceled") return "Canceled";
  if (job.status === "failed") return job.error_message || "Failed";
  if (job.status === "running") return `${job.current_stage} (${job.progress_percent}%)`;
  return "Waiting...";
}
