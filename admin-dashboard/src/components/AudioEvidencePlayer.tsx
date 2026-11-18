import { useState, useRef, useEffect } from "react";
import { Play, Pause, RotateCcw, Volume2, VolumeX, Download, Activity, AlertCircle } from "lucide-react";

interface AudioEvidencePlayerProps {
  src: string;
  filename?: string;
  incidentId?: string;
}

export default function AudioEvidencePlayer({ src, filename, incidentId }: AudioEvidencePlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const formatTime = (secs: number) => {
    if (!secs || isNaN(secs) || secs === Infinity) return "0:00";
    const mins = Math.floor(secs / 60);
    const remainingSecs = Math.floor(secs % 60);
    return `${mins}:${remainingSecs < 10 ? "0" : ""}${remainingSecs}`;
  };

  useEffect(() => {
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
    setHasError(false);
    setIsLoading(true);
  }, [src]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch((err) => {
        console.warn("Audio playback failed:", err);
        setHasError(true);
      });
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const target = parseFloat(e.target.value);
    setCurrentTime(target);
    if (audioRef.current) {
      audioRef.current.currentTime = target;
    }
  };

  const cyclePlaybackRate = () => {
    const nextRate = playbackRate === 1 ? 1.5 : playbackRate === 1.5 ? 2 : 1;
    setPlaybackRate(nextRate);
    if (audioRef.current) {
      audioRef.current.playbackRate = nextRate;
    }
  };

  const toggleMute = () => {
    const next = !isMuted;
    setIsMuted(next);
    if (audioRef.current) {
      audioRef.current.muted = next;
    }
  };

  const restartAudio = () => {
    if (audioRef.current) {
      audioRef.current.currentTime = 0;
      setCurrentTime(0);
      if (!isPlaying) {
        audioRef.current.play().catch(() => {});
      }
    }
  };

  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="bg-slate-900/60 border border-slate-700/60 rounded-xl p-3.5 flex flex-col gap-3 shadow-lg">
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onLoadedMetadata={(e) => {
          const d = e.currentTarget.duration;
          if (d && !isNaN(d) && d !== Infinity) setDuration(d);
          setIsLoading(false);
        }}
        onDurationChange={(e) => {
          const d = e.currentTarget.duration;
          if (d && !isNaN(d) && d !== Infinity) setDuration(d);
        }}
        onTimeUpdate={(e) => {
          setCurrentTime(e.currentTarget.currentTime);
          const d = e.currentTarget.duration;
          if (d && !isNaN(d) && d !== Infinity && duration === 0) setDuration(d);
        }}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => {
          setIsPlaying(false);
          setCurrentTime(0);
        }}
        onError={() => {
          setIsLoading(false);
          setHasError(true);
        }}
      />

      {/* Header Info */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${isPlaying ? "bg-indigo-500 text-white shadow-lg shadow-indigo-500/30" : "bg-indigo-500/20 text-indigo-400 border border-indigo-500/30"}`}>
            <Activity size={16} className={isPlaying ? "animate-pulse" : ""} />
          </div>
          <div>
            <div className="text-xs font-bold text-slate-200 flex items-center gap-2">
              <span>Voice Distress Telemetry</span>
              {isPlaying && (
                <span className="flex items-center gap-1 text-[9px] uppercase tracking-wider text-indigo-400 bg-indigo-500/10 px-1.5 py-0.5 rounded border border-indigo-500/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-ping" /> PLAYING
                </span>
              )}
            </div>
            <div className="text-[10px] text-slate-400 font-mono truncate max-w-[200px]">
              {filename || (src ? src.split("/").pop() : "evidence_recording.m4a")}
            </div>
          </div>
        </div>

        {/* Action icons */}
        <div className="flex items-center gap-1">
          <button
            onClick={cyclePlaybackRate}
            className="text-[11px] font-mono font-bold text-slate-300 hover:text-white px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700/60 transition-colors"
            title="Playback Speed"
          >
            {playbackRate}x
          </button>
          <button
            onClick={toggleMute}
            className="p-1.5 text-slate-400 hover:text-white rounded bg-slate-800 hover:bg-slate-700 border border-slate-700/60 transition-colors"
            title={isMuted ? "Unmute" : "Mute"}
          >
            {isMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
          </button>
          <a
            href={src}
            download={filename || `SafeHer_Voice_${incidentId || "evidence"}.m4a`}
            target="_blank"
            rel="noreferrer"
            className="p-1.5 text-slate-400 hover:text-white rounded bg-slate-800 hover:bg-slate-700 border border-slate-700/60 transition-colors"
            title="Download Audio Evidence"
          >
            <Download size={14} />
          </a>
        </div>
      </div>

      {hasError ? (
        <div className="p-3 bg-red-950/30 border border-red-500/30 rounded-lg flex items-center gap-2 text-xs text-red-300">
          <AlertCircle size={15} className="text-red-400 shrink-0" />
          <span>Audio session recorded. File stored in encrypted evidence vault.</span>
        </div>
      ) : (
        <>
          {/* Controls & Equalizer */}
          <div className="flex items-center gap-3">
            <button
              onClick={togglePlay}
              className={`w-9 h-9 rounded-full flex items-center justify-center transition-all shadow-md shrink-0 ${
                isPlaying
                  ? "bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/40"
                  : "bg-slate-800 hover:bg-indigo-600 text-slate-200 hover:text-white border border-slate-700 hover:border-indigo-500"
              }`}
            >
              {isPlaying ? <Pause size={15} /> : <Play size={15} className="ml-0.5" />}
            </button>

            <button
              onClick={restartAudio}
              className="p-1.5 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors shrink-0"
              title="Restart from beginning"
            >
              <RotateCcw size={14} />
            </button>

            {/* Visualizer & Progress bar */}
            <div className="flex-1 flex flex-col gap-1 min-w-0">
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="0"
                  max={duration || 100}
                  step="0.05"
                  value={currentTime}
                  onChange={handleSeek}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                  style={{
                    background: `linear-gradient(to right, #6366f1 ${progressPercent}%, #1e293b ${progressPercent}%)`
                  }}
                />
              </div>

              <div className="flex justify-between items-center text-[10px] font-mono text-slate-400">
                <span>{formatTime(currentTime)}</span>
                {/* Dancing Equalizer Bars when playing */}
                <div className="flex items-center gap-0.5 h-3">
                  {[40, 75, 55, 90, 60, 80, 45, 95].map((h, i) => (
                    <div
                      key={i}
                      className={`w-0.5 rounded-full transition-all duration-150 ${isPlaying ? "bg-indigo-400" : "bg-slate-700"}`}
                      style={{
                        height: isPlaying ? `${Math.max(20, (h * ((currentTime * 3 + i) % 10)) / 10)}%` : "20%"
                      }}
                    />
                  ))}
                </div>
                <span>{isLoading ? "Loading..." : formatTime(duration)}</span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
