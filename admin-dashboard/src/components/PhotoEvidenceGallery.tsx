import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Camera, ZoomIn, ZoomOut, RotateCw, ExternalLink, Download, Clock, MapPin, X, Copy, Check, ShieldCheck } from "lucide-react";

interface PhotoItem {
  id: string;
  photo_path?: string;
  url?: string;
  direct_url?: string;
  timestamp?: string;
  location?: { latitude?: number; longitude?: number };
}

interface PhotoEvidenceGalleryProps {
  photos: PhotoItem[];
  baseUrl: string;
}

export default function PhotoEvidenceGallery({ photos, baseUrl }: PhotoEvidenceGalleryProps) {
  const [selectedPhoto, setSelectedPhoto] = useState<PhotoItem | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [copied, setCopied] = useState(false);
  const [imageStates, setImageStates] = useState<{ [key: string]: { loaded: boolean; error: boolean } }>({});

  const resolvePhotoSrc = (photo: PhotoItem) => {
    if (!photo) return "";
    const rawUrl = photo.url || (photo.id ? `/api/sos/evidence/photo/${photo.id}` : "");
    if (!rawUrl) return "";
    return rawUrl.startsWith("http") ? rawUrl : baseUrl + rawUrl;
  };

  const handleOpenLightbox = (photo: PhotoItem) => {
    setSelectedPhoto(photo);
    setZoomLevel(1);
    setRotation(0);
  };

  const handleCloseLightbox = () => {
    setSelectedPhoto(null);
  };

  const handleCopyLink = (url: string) => {
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleCloseLightbox();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl overflow-hidden shadow-lg">
      {/* Header */}
      <div className="bg-slate-900/60 px-4 py-3 border-b border-slate-700/50 flex justify-between items-center">
        <span className="flex items-center gap-2 text-[11px] uppercase tracking-widest text-slate-400 font-bold">
          <Camera size={13} className="text-pink-400" /> Photo Evidence Vault
        </span>
        <span className={(photos?.length > 0 ? "bg-pink-500/20 text-pink-400 border-pink-500/30" : "bg-slate-700/50 text-slate-400 border-slate-600/30") + " px-2 py-0.5 text-[9px] font-bold tracking-widest uppercase rounded border"}>
          {photos?.length || 0} Snapshots Stored
        </span>
      </div>

      {photos && photos.length > 0 ? (
        <div className="p-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
          {photos.map((photo, idx) => {
            const src = resolvePhotoSrc(photo);
            const state = imageStates[photo.id] || { loaded: false, error: false };

            return (
              <div
                key={photo.id || idx}
                onClick={() => handleOpenLightbox(photo)}
                className="group relative bg-slate-950 rounded-xl overflow-hidden cursor-pointer border border-slate-800/80 hover:border-pink-500/60 transition-all duration-300 shadow-md hover:shadow-pink-500/10"
                style={{ aspectRatio: "4/3" }}
              >
                {/* Skeleton shimmer while loading */}
                {!state.loaded && !state.error && (
                  <div className="absolute inset-0 bg-slate-900 animate-pulse flex flex-col items-center justify-center gap-2 text-slate-600">
                    <Camera size={20} className="animate-bounce text-pink-400/50" />
                    <span className="text-[9px] font-mono tracking-wider">RETRIEVING...</span>
                  </div>
                )}

                {state.error ? (
                  /* Fallback card if image cannot be decoded */
                  <div className="w-full h-full bg-slate-900/90 flex flex-col items-center justify-center p-3 text-center border border-slate-800">
                    <Camera size={24} className="text-pink-400/70 mb-1" />
                    <span className="text-[10px] font-bold text-slate-300">Evidence Snapshot</span>
                    <span className="text-[9px] font-mono text-slate-500">#{photo.id?.substring(0, 8)}</span>
                    <span className="text-[9px] text-pink-400/80 mt-1 font-semibold">Click to Inspect</span>
                  </div>
                ) : (
                  <img
                    src={src}
                    alt={`Evidence Snapshot ${idx + 1}`}
                    className={`w-full h-full object-cover transition-all duration-300 ${
                      state.loaded ? "opacity-95 group-hover:opacity-100 group-hover:scale-105" : "opacity-0"
                    }`}
                    onLoad={() => {
                      setImageStates((prev) => ({ ...prev, [photo.id]: { loaded: true, error: false } }));
                    }}
                    onError={() => {
                      setImageStates((prev) => ({ ...prev, [photo.id]: { loaded: false, error: true } }));
                    }}
                  />
                )}

                {/* Hover overlay with zoom icon */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <div className="w-10 h-10 rounded-full bg-pink-600/90 text-white flex items-center justify-center shadow-lg shadow-pink-600/30">
                    <ZoomIn size={18} />
                  </div>
                </div>

                {/* Bottom telemetry bar */}
                <div className="absolute bottom-0 left-0 right-0 bg-black/80 backdrop-blur-md px-2 py-1 flex justify-between items-center border-t border-white/5">
                  <span className="text-[9px] text-slate-300 font-mono flex items-center gap-1">
                    <Clock size={8} className="text-indigo-400" />
                    {photo.timestamp ? new Date(photo.timestamp).toLocaleTimeString() : "N/A"}
                  </span>
                  <span className="text-[9px] text-slate-400 font-mono">
                    {photo.location?.latitude ? `${Number(photo.location.latitude).toFixed(3)}, ${Number(photo.location.longitude).toFixed(3)}` : "No GPS"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="p-6 flex items-center gap-3 m-4 rounded-lg border border-dashed border-slate-700/50 bg-slate-900/20">
          <div className="w-9 h-9 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 shrink-0">
            <Camera size={18} />
          </div>
          <div className="text-xs text-slate-400">
            <span className="font-semibold text-slate-300">No photo evidence recorded yet.</span>
            <br />
            Covert photographic snapshots capture automatically during active SOS.
          </div>
        </div>
      )}

      {/* LIGHTBOX MODAL */}
      <AnimatePresence>
        {selectedPhoto && (
          <div
            className="fixed inset-0 z-[200] flex items-center justify-center bg-black/90 backdrop-blur-md p-4"
            onClick={handleCloseLightbox}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative max-w-5xl w-full bg-slate-900 border border-slate-700/80 rounded-2xl overflow-hidden shadow-2xl flex flex-col max-h-[92vh]"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="bg-slate-950 px-5 py-3.5 border-b border-slate-800 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-pink-500/20 text-pink-400 flex items-center justify-center border border-pink-500/30">
                    <Camera size={14} />
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white flex items-center gap-2">
                      <span>SOS Photographic Evidence Inspection</span>
                      <span className="flex items-center gap-1 text-[9px] font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-1.5 py-0.5 rounded">
                        <ShieldCheck size={10} /> FORENSIC VERIFIED
                      </span>
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono">
                      ID: {selectedPhoto.id}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {/* Zoom controls */}
                  <div className="flex items-center bg-slate-800/80 rounded-lg p-0.5 border border-slate-700">
                    <button
                      onClick={() => setZoomLevel((z) => Math.max(1, z - 0.25))}
                      className="p-1.5 text-slate-400 hover:text-white rounded hover:bg-slate-700 transition-colors"
                      title="Zoom Out"
                    >
                      <ZoomOut size={14} />
                    </button>
                    <span className="text-[10px] font-mono text-slate-300 px-2 font-bold">{Math.round(zoomLevel * 100)}%</span>
                    <button
                      onClick={() => setZoomLevel((z) => Math.min(3, z + 0.25))}
                      className="p-1.5 text-slate-400 hover:text-white rounded hover:bg-slate-700 transition-colors"
                      title="Zoom In"
                    >
                      <ZoomIn size={14} />
                    </button>
                  </div>

                  {/* Rotate control */}
                  <button
                    onClick={() => setRotation((r) => (r + 90) % 360)}
                    className="p-2 text-slate-400 hover:text-white rounded-lg bg-slate-800 border border-slate-700 hover:bg-slate-700 transition-colors"
                    title="Rotate 90° Clockwise"
                  >
                    <RotateCw size={14} />
                  </button>

                  <button
                    onClick={handleCloseLightbox}
                    className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors ml-2"
                  >
                    <X size={18} />
                  </button>
                </div>
              </div>

              {/* Image Preview Canvas */}
              <div className="flex-1 bg-black/95 flex items-center justify-center overflow-auto p-4 min-h-[350px] max-h-[68vh]">
                <img
                  src={resolvePhotoSrc(selectedPhoto)}
                  alt="High-resolution Evidence"
                  style={{
                    transform: `scale(${zoomLevel}) rotate(${rotation}deg)`,
                    transition: "transform 0.2s ease-out"
                  }}
                  className="max-h-[62vh] w-auto max-w-full object-contain select-none shadow-2xl rounded-lg"
                />
              </div>

              {/* Bottom Footer Telemetry */}
              <div className="p-3.5 bg-slate-950 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs shrink-0">
                <div className="flex items-center gap-4 text-slate-400 font-mono">
                  <span className="flex items-center gap-1.5">
                    <Clock size={13} className="text-indigo-400" />
                    {selectedPhoto.timestamp ? new Date(selectedPhoto.timestamp).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) : "N/A"}
                  </span>
                  {selectedPhoto.location?.latitude && (
                    <a
                      href={`https://www.google.com/maps?q=${selectedPhoto.location.latitude},${selectedPhoto.location.longitude}`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-1.5 text-indigo-400 hover:text-indigo-300 underline"
                      title="Open coordinates on Google Maps"
                    >
                      <MapPin size={13} className="text-red-400" />
                      {Number(selectedPhoto.location.latitude).toFixed(6)}, {Number(selectedPhoto.location.longitude).toFixed(6)}
                    </a>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleCopyLink(resolvePhotoSrc(selectedPhoto))}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white rounded-lg border border-slate-700 text-xs font-medium transition-colors"
                  >
                    {copied ? <Check size={13} className="text-emerald-400" /> : <Copy size={13} />}
                    {copied ? "Copied" : "Copy Link"}
                  </button>

                  <a
                    href={resolvePhotoSrc(selectedPhoto)}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white rounded-lg border border-slate-700 text-xs font-medium transition-colors"
                  >
                    <ExternalLink size={13} /> Open Raw
                  </a>

                  <a
                    href={resolvePhotoSrc(selectedPhoto)}
                    download={`SafeHer_Evidence_${selectedPhoto.id}.jpg`}
                    className="flex items-center gap-1.5 px-3.5 py-1.5 bg-pink-600 hover:bg-pink-500 text-white rounded-lg text-xs font-bold transition-all shadow-md shadow-pink-600/30"
                  >
                    <Download size={13} /> Download
                  </a>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
