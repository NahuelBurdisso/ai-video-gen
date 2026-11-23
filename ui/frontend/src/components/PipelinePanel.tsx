import { useState, useEffect, useCallback, useRef } from "react";
import { useWebSocket } from "../hooks/useWebSocket";
import { Loader2, CheckCircle, XCircle, Film, RefreshCw, Square, Clock, Download, Zap } from "lucide-react";

type ClipState = {
  index: number;
  status: "pending" | "generating" | "done" | "failed";
  type?: string;
  prompt?: string;
  elapsed?: number;
  videoUrl?: string;
  error?: string;
  step?: number;
  totalSteps?: number;
  pct?: number;
  phase?: string;
};

type PipelineStatus = {
  running: boolean;
  title: string | null;
  status?: string;
  error: string | null;
  started_at: number | null;
  progress?: { completed: number; total: number };
  output?: string;
};

type HistoryEntry = {
  title: string;
  has_final: boolean;
  clips?: number;
  total?: number;
};

const WS_URL = `ws://${window.location.host}/ws/chat`;

export default function PipelinePanel() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [clips, setClips] = useState<ClipState[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<string | null>(null);
  // Track completed clip durations for ETA
  const clipDurations = useRef<number[]>([]);

  const fetchStatus = async () => {
    try {
      const res = await fetch("/api/pipeline/status");
      setStatus(await res.json());
    } catch {}
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch("/api/pipeline/history");
      const data = await res.json();
      setHistory(data.projects || []);
    } catch {}
  };

  useEffect(() => {
    fetchStatus();
    fetchHistory();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleWS = useCallback((msg: { type: string; data: Record<string, unknown> }) => {
    switch (msg.type) {
      case "pipeline_started": {
        const total = msg.data.total_clips as number;
        setClips(Array.from({ length: total }, (_, i) => ({ index: i, status: "pending" })));
        setSelectedVideo(null);
        clipDurations.current = [];
        fetchStatus();
        break;
      }
      case "clip_started":
        setClips((prev) => prev.map((c) =>
          c.index === (msg.data.index as number)
            ? { ...c, status: "generating", type: msg.data.type as string, prompt: msg.data.prompt as string, step: 0, totalSteps: 0, pct: 0, phase: "queued" }
            : c
        ));
        break;
      case "clip_progress":
        setClips((prev) => prev.map((c) =>
          c.index === (msg.data.index as number)
            ? {
                ...c,
                elapsed: msg.data.elapsed as number | undefined,
                step: (msg.data.step as number | undefined) ?? c.step,
                totalSteps: (msg.data.total_steps as number | undefined) ?? c.totalSteps,
                pct: (msg.data.pct as number | undefined) ?? c.pct,
                phase: (msg.data.phase as string | undefined) ?? c.phase,
              }
            : c
        ));
        break;
      case "clip_completed": {
        const duration = msg.data.duration as number;
        clipDurations.current.push(duration);
        setClips((prev) => prev.map((c) =>
          c.index === (msg.data.index as number)
            ? { ...c, status: "done", videoUrl: msg.data.video_url as string, elapsed: duration, step: undefined, totalSteps: undefined, pct: undefined, phase: undefined }
            : c
        ));
        fetchStatus();
        break;
      }
      case "clip_failed":
        setClips((prev) => prev.map((c) =>
          c.index === (msg.data.index as number)
            ? { ...c, status: "failed", error: msg.data.error as string }
            : c
        ));
        break;
      case "pipeline_done":
        setSelectedVideo(msg.data.final_video_url as string);
        fetchStatus();
        fetchHistory();
        break;
      case "pipeline_error":
        fetchStatus();
        break;
      case "pipeline_cancelled":
        fetchStatus();
        break;
    }
  }, []);

  useWebSocket(WS_URL, handleWS);

  const handleStop = async () => {
    await fetch("/api/pipeline/stop", { method: "POST" });
    fetchStatus();
  };

  const progress = status?.progress;
  const completedClips = progress?.completed ?? 0;
  const totalClips = progress?.total ?? 0;

  // Find current generating clip for overall progress calculation
  const generatingClip = clips.find((c) => c.status === "generating");
  const clipFraction = generatingClip?.pct ? generatingClip.pct / 100 : 0;
  const overallPct = totalClips > 0
    ? Math.round(((completedClips + clipFraction) / totalClips) * 100)
    : 0;

  // Dynamic ETA based on actual clip durations + step extrapolation
  const historicalAvg = clipDurations.current.length > 0
    ? clipDurations.current.reduce((a, b) => a + b, 0) / clipDurations.current.length
    : null;
  // Extrapolate from current clip's step progress when no history
  const extrapolatedClipTime = generatingClip?.step && generatingClip.step > 0 && generatingClip.elapsed
    ? (generatingClip.elapsed / generatingClip.step) * (generatingClip.totalSteps ?? generatingClip.step)
    : null;
  const avgClipTime = historicalAvg ?? extrapolatedClipTime;
  const remainingClips = totalClips - completedClips;
  const currentClipRemaining = generatingClip?.pct && avgClipTime
    ? (1 - generatingClip.pct / 100) * avgClipTime
    : avgClipTime ?? 0;
  const etaSeconds = avgClipTime !== null
    ? Math.round(Math.max(0, (remainingClips - 1) * avgClipTime + currentClipRemaining))
    : null;

  const isRunning = status?.running || status?.status === "generating";

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  const formatEta = (s: number) => {
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return sec > 0 ? `${m}m ${sec}s` : `${m}m`;
  };

  const phaseLabel = (phase?: string) => {
    switch (phase) {
      case "sampling": return "Sampling";
      case "processing": return "Processing";
      case "downloading": return "Downloading";
      case "queued": return "Queued";
      default: return "Working";
    }
  };

  return (
    <div className="h-full overflow-y-auto p-6 max-w-3xl mx-auto space-y-6">
      {/* Current Status */}
      <section className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Current Pipeline</h2>
          <div className="flex items-center gap-2">
            {isRunning && (
              <button
                onClick={handleStop}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-red-600/20 text-red-400 hover:bg-red-600/40 rounded transition"
              >
                <Square size={12} /> Stop
              </button>
            )}
            <button onClick={fetchStatus} className="text-zinc-400 hover:text-zinc-200">
              <RefreshCw size={16} />
            </button>
          </div>
        </div>

        {!isRunning && !status?.title && (
          <p className="text-zinc-500 text-sm">No pipeline running. Use Chat to create a video plan.</p>
        )}

        {isRunning && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-blue-400">
              <Loader2 size={18} className="animate-spin" />
              <span className="font-medium">{status?.title}</span>
              {status?.status === "assembling" && (
                <span className="text-xs bg-blue-600/20 px-2 py-0.5 rounded">Assembling...</span>
              )}
            </div>

            {totalClips > 0 && (
              <>
                {/* Overall progress bar */}
                <div className="w-full bg-zinc-800 rounded-full h-3 overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-blue-600 to-blue-400 h-3 rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${overallPct}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-zinc-400">
                    Clip {completedClips}/{totalClips} — {overallPct}%
                  </span>
                  {remainingClips > 0 && etaSeconds !== null && (
                    <span className="text-zinc-500 flex items-center gap-1">
                      <Clock size={12} />
                      ~{formatEta(etaSeconds)} remaining
                    </span>
                  )}
                  {remainingClips > 0 && etaSeconds === null && (
                    <span className="text-zinc-500 text-xs">Calculating ETA...</span>
                  )}
                </div>

                {/* Current clip detail */}
                {generatingClip && (
                  <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-lg p-3 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-blue-300 flex items-center gap-1">
                        <Zap size={12} />
                        Clip #{generatingClip.index + 1}
                        {generatingClip.type && <span className="uppercase text-zinc-500 ml-1">{generatingClip.type}</span>}
                      </span>
                      <span className="text-zinc-500">
                        {phaseLabel(generatingClip.phase)}
                        {generatingClip.step !== undefined && generatingClip.totalSteps
                          ? ` — step ${generatingClip.step}/${generatingClip.totalSteps}`
                          : ""}
                      </span>
                    </div>
                    {/* Per-clip progress bar */}
                    <div className="w-full bg-zinc-700 rounded-full h-1.5 overflow-hidden">
                      <div
                        className={`h-1.5 rounded-full transition-all duration-300 ${
                          generatingClip.phase === "downloading"
                            ? "bg-green-400"
                            : "bg-blue-400"
                        }`}
                        style={{ width: `${generatingClip.pct ?? 0}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-xs text-zinc-500">
                      <span>{generatingClip.pct ?? 0}%</span>
                      {generatingClip.elapsed && (
                        <span className="flex items-center gap-0.5">
                          <Clock size={10} /> {formatTime(generatingClip.elapsed)}
                        </span>
                      )}
                    </div>
                    {generatingClip.prompt && (
                      <p className="text-xs text-zinc-600 truncate">{generatingClip.prompt}</p>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {status?.error && (
          <div className="flex items-center gap-2 text-red-400 text-sm mt-2">
            <XCircle size={16} /> {status.error}
          </div>
        )}

        {status?.output && !selectedVideo && (
          <div className="mt-3">
            <p className="text-green-400 text-sm flex items-center gap-1 mb-2">
              <CheckCircle size={16} /> Complete
            </p>
            <video
              src={status.output}
              controls
              className="w-full rounded-lg border border-zinc-700"
            />
          </div>
        )}
      </section>

      {/* Video Player */}
      {selectedVideo && (
        <section className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-semibold text-sm">Player</h2>
            <button onClick={() => setSelectedVideo(null)} className="text-zinc-500 hover:text-zinc-300 text-xs">
              Close
            </button>
          </div>
          <video
            key={selectedVideo}
            src={selectedVideo}
            controls
            autoPlay
            className="w-full rounded-lg border border-zinc-700"
          />
          <a
            href={selectedVideo}
            download
            className="inline-flex items-center gap-1 mt-2 text-xs text-blue-400 hover:text-blue-300"
          >
            <Download size={12} /> Download
          </a>
        </section>
      )}

      {/* Clip Grid */}
      {clips.length > 0 && (
        <section className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <h2 className="font-semibold mb-3">Clips</h2>
          <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
            {clips.map((clip) => (
              <button
                key={clip.index}
                onClick={() => clip.videoUrl && setSelectedVideo(clip.videoUrl)}
                className={`relative rounded-lg border p-2 text-center text-xs transition overflow-hidden
                  ${clip.status === "done" ? "border-green-600/50 bg-green-900/10 cursor-pointer hover:border-green-500" :
                    clip.status === "generating" ? "border-blue-600/50 bg-blue-900/10" :
                    clip.status === "failed" ? "border-red-600/50 bg-red-900/10" :
                    "border-zinc-700 bg-zinc-800/50"}`}
              >
                {/* Mini progress bar at bottom of generating clips */}
                {clip.status === "generating" && (clip.pct ?? 0) > 0 && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-zinc-700">
                    <div
                      className="h-0.5 bg-blue-400 transition-all duration-300"
                      style={{ width: `${clip.pct}%` }}
                    />
                  </div>
                )}
                <div className="font-mono text-zinc-400">#{clip.index + 1}</div>
                {clip.type && <div className="text-zinc-500 uppercase">{clip.type}</div>}
                {clip.status === "generating" && (
                  <Loader2 size={14} className="animate-spin mx-auto mt-1 text-blue-400" />
                )}
                {clip.status === "generating" && clip.elapsed && (
                  <div className="text-zinc-500 flex items-center justify-center gap-0.5 mt-0.5">
                    <Clock size={10} /> {formatTime(clip.elapsed)}
                  </div>
                )}
                {clip.status === "done" && <CheckCircle size={14} className="mx-auto mt-1 text-green-400" />}
                {clip.status === "done" && clip.elapsed && (
                  <div className="text-zinc-600 text-[10px] mt-0.5">{formatTime(clip.elapsed)}</div>
                )}
                {clip.status === "failed" && <XCircle size={14} className="mx-auto mt-1 text-red-400" />}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* History */}
      <section className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <h2 className="font-semibold mb-3">History</h2>
        {history.length === 0 ? (
          <p className="text-zinc-500 text-sm">No completed projects yet.</p>
        ) : (
          <div className="space-y-2">
            {history.map((h) => (
              <button
                key={h.title}
                onClick={() => {
                  if (h.has_final) {
                    setSelectedVideo(`/static/output/${h.title}/final.mp4`);
                    if (h.total) {
                      setClips(Array.from({ length: h.total }, (_, i) => ({
                        index: i,
                        status: i < (h.clips ?? 0) ? "done" as const : "pending" as const,
                        videoUrl: i < (h.clips ?? 0) ? `/static/output/${h.title}/clips/clip_${String(i).padStart(3, "0")}.mp4` : undefined,
                      })));
                    }
                  }
                }}
                className={`flex items-center justify-between w-full py-2 px-3 bg-zinc-800/50 rounded text-left transition
                  ${h.has_final ? "hover:bg-zinc-700/50 cursor-pointer" : ""}`}
              >
                <div className="flex items-center gap-2">
                  <Film size={16} className="text-zinc-500" />
                  <span className="text-sm">{h.title}</span>
                </div>
                <div className="text-xs text-zinc-500">
                  {h.has_final ? (
                    <span className="text-green-400">Complete</span>
                  ) : (
                    <span>{h.clips ?? 0}/{h.total ?? "?"} clips</span>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
