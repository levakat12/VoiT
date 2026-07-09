import { ChangeEvent, FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Clipboard, Download, Loader2, Pause, Play, RefreshCw, RotateCcw, Save, Search, Upload, X } from "lucide-react";
import {
  cancelJob,
  exportUrl,
  getJob,
  listJobs,
  pauseJob,
  resumeJob,
  retryJob,
  saveTranscript,
  searchTranscripts,
  uploadMedia,
  uploadMediaUrl,
} from "./api";
import BorderGlow from "./BorderGlow";
import GlassSurface from "./GlassSurface";
import LineWaves from "./LineWaves";
import StaggeredMenu from "./StaggeredMenu";
import type { JobListItem, JobRead, SearchResult } from "./types";

type ExportFormat = "txt" | "docx" | "pdf" | "json" | "srt" | "vtt";

const menuItems = [
  { label: "Transcriber", ariaLabel: "Go to transcriber workspace", link: "#transcriber" },
];

export default function App() {
  const [job, setJob] = useState<JobRead | null>(null);
  const [text, setText] = useState("");
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [mediaUrl, setMediaUrl] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [exportFormat, setExportFormat] = useState<ExportFormat>("txt");
  const [isDirty, setDirty] = useState(false);
  const [isUploading, setUploading] = useState(false);
  const [isSearching, setSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [isUploadOpen, setUploadOpen] = useState(false);
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

  useEffect(() => {
    if (!isUploadOpen) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setUploadOpen(false);
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isUploadOpen]);

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

  async function handleUrlUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const url = mediaUrl.trim();
    if (!url) return;

    requestNotificationPermission();
    setUploading(true);
    setMessage("Reading link...");
    setDirty(false);

    try {
      const nextJob = await uploadMediaUrl(url);
      setJob(nextJob);
      setText(nextJob.transcript_text);
      setMessage(statusMessage(nextJob));
      setMediaUrl("");
      await refreshJobs();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Link upload failed.");
    } finally {
      setUploading(false);
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

  async function handleJobAction(action: "pause" | "resume" | "retry" | "cancel") {
    if (!job) return;

    try {
      const nextJob =
        action === "pause"
          ? await pauseJob(job.id)
          : action === "resume"
            ? await resumeJob(job.id)
            : action === "retry"
              ? await retryJob(job.id)
              : await cancelJob(job.id);
      setJob(nextJob);
      setMessage(statusMessage(nextJob));
      await refreshJobs();
      if (action === "retry") {
        setDirty(false);
        setText(nextJob.transcript_text);
      } else if (!isDirty) {
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

  async function handleCopy() {
    if (!text.trim()) return;

    try {
      await navigator.clipboard.writeText(text);
      setMessage("Copied");
    } catch {
      setMessage("Copy unavailable");
    }
  }

  return (
    <main className="appShell">
      <div className="backgroundLayer" aria-hidden="true">
        <div className="lineWavesFrame">
          <LineWaves
            speed={0.5}
            innerLineCount={15}
            outerLineCount={28}
            warpIntensity={0.5}
            rotation={-45}
            edgeFadeWidth={0}
            colorCycleSpeed={3}
            brightness={0.2}
            color1="#ff4800"
            color2="#e300ff"
            color3="#00fff3"
            enableMouseInteraction
            mouseInfluence={1.2}
          />
        </div>
      </div>
      <header className="navReserve" aria-label="Navigation">
        <StaggeredMenu
          items={menuItems}
          displaySocials={false}
          displayItemNumbering
          colors={["#ff4800", "#e300ff", "#00fff3"]}
          accentColor="#f5f5f5"
        />
      </header>
      {isUploadOpen ? (
        <div className="uploadOverlay" role="presentation" onMouseDown={() => setUploadOpen(false)}>
                <GlassSurface
                  className="uploadDialogSurface"
                  width="min(1120px, calc(100vw - 48px))"
                  height="min(680px, calc(100vh - 48px))"
                  borderRadius={18}
            backgroundOpacity={0.1}
            saturation={1.35}
            brightness={16}
            opacity={0.72}
            blur={18}
            displace={0.34}
            distortionScale={-72}
            redOffset={0}
            greenOffset={0}
            blueOffset={0}
          >
            <BorderGlow
              className="tileCornerGlow"
              edgeSensitivity={20}
              glowColor="184 100 62"
              borderRadius={18}
              glowRadius={34}
              glowIntensity={0.48}
              coneSpread={18}
              colors={["#ff4800", "#e300ff", "#00fff3"]}
              fillOpacity={0}
              animated
            >
              <section
                id="upload"
                className="window uploadWindow uploadDialogWindow"
                role="dialog"
                aria-modal="true"
                aria-labelledby="upload-dialog-title"
                onMouseDown={(event) => event.stopPropagation()}
              >
                <div className="uploadDialogHeader">
                  <div>
                    <h1 id="upload-dialog-title">Upload</h1>
                    <p>{message}</p>
                  </div>
                  <button
                    type="button"
                    className="smallIconButton"
                    onClick={() => setUploadOpen(false)}
                    title="Close"
                    aria-label="Close upload window"
                  >
                    <X size={16} />
                  </button>
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

                <form className="urlUploadForm" onSubmit={(event) => void handleUrlUpload(event)}>
                  <input
                    className="urlInput"
                    type="url"
                    value={mediaUrl}
                    onChange={(event) => setMediaUrl(event.target.value)}
                    placeholder="Video or media URL"
                    disabled={isUploading}
                    aria-label="Media link"
                  />
                  <button type="submit" className="uploadButton urlUploadButton" disabled={isUploading || !mediaUrl.trim()}>
                    {isUploading ? <Loader2 className="spin" size={18} /> : <Upload size={18} />}
                    <span>Link</span>
                  </button>
                </form>

                <div className="fileName">{job?.filename ?? "No file selected"}</div>

                {job && shouldShowProgress(job.status) ? (
                  <div
                    className="progressBlock"
                    role="progressbar"
                    aria-label="Transcription progress"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={clampedProgress(job.progress_percent)}
                  >
                    <div className="progressTrack">
                      <div className="progressFill" style={{ width: `${clampedProgress(job.progress_percent)}%` }} />
                    </div>
                    <span>{job.progress_percent}%</span>
                  </div>
                ) : null}

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

                {job && isRetryableStatus(job.status) ? (
                  <div className="jobControls">
                    <button
                      type="button"
                      className="iconButton"
                      onClick={() => void handleJobAction("retry")}
                      title="Retry"
                      aria-label="Retry transcription"
                    >
                      <RotateCcw size={18} />
                    </button>
                  </div>
                ) : null}

                <div id="recent" className="recentBlock">
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
                            <span className="recentJobText">
                              <span>{item.filename}</span>
                              <small>{searchSnippet(item)}</small>
                            </span>
                            <small>{item.match_count === 1 ? "1 match" : `${item.match_count} matches`}</small>
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
            </BorderGlow>
          </GlassSurface>
        </div>
      ) : null}
      <div id="transcriber" className="workspace">
        <GlassSurface
          className="tileSurface textTile"
          borderRadius={18}
          backgroundOpacity={0.1}
          saturation={1.35}
          brightness={16}
          opacity={0.72}
          blur={18}
          displace={0.34}
          distortionScale={-72}
          redOffset={0}
          greenOffset={0}
          blueOffset={0}
        >
          <BorderGlow
            className="tileCornerGlow"
            edgeSensitivity={20}
            glowColor="184 100 62"
            borderRadius={18}
            glowRadius={34}
            glowIntensity={0.48}
            coneSpread={18}
            colors={["#ff4800", "#e300ff", "#00fff3"]}
            fillOpacity={0}
            animated
          >
          <section id="text" className="window textWindow">
            <div className="textHeader">
              <h2>Transcriber</h2>
              <div className="textActions">
                <button
                  type="button"
                  className="uploadActionButton"
                  onClick={() => setUploadOpen(true)}
                  title="Open upload window"
                  aria-label="Open upload window"
                >
                  <Upload size={18} />
                  <span>Upload</span>
                </button>
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
                  onClick={() => void handleCopy()}
                  disabled={!text.trim()}
                  title="Copy"
                  aria-label="Copy transcript"
                >
                  <Clipboard size={18} />
                </button>
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

            <div className="outputStage">
              <textarea
                className="outputEditor"
                value={text}
                onChange={(event) => {
                  setText(event.target.value);
                  setDirty(true);
                }}
                placeholder="Transcript will appear here."
                aria-label="Transcript output"
              />
            </div>
          </section>
          </BorderGlow>
        </GlassSurface>
      </div>
    </main>
  );
}

function searchSnippet(result: SearchResult): string {
  return result.snippets[0] || statusLabel(result.status);
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

function isRetryableStatus(status: JobRead["status"]): boolean {
  return status === "completed" || status === "failed" || status === "canceled";
}

function shouldShowProgress(status: JobRead["status"]): boolean {
  return status === "pending" || status === "running" || status === "paused";
}

function clampedProgress(progress: number): number {
  return Math.min(100, Math.max(0, progress));
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
