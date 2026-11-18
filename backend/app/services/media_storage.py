import os
import re
import mimetypes
from typing import Optional, Tuple, Dict, Any
from fastapi import Request, Response, HTTPException
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from bson import ObjectId
from app.core.config import settings
from app.core.database import get_database, get_collection

_bucket = None


def get_gridfs_bucket() -> AsyncIOMotorGridFSBucket:
    global _bucket
    db = get_database()
    if _bucket is None or getattr(_bucket, "_db", None) != db:
        _bucket = AsyncIOMotorGridFSBucket(db)
    return _bucket


def _normalize_filename(path_or_name: str) -> str:
    """Extract standard base filename from path or name."""
    if not path_or_name:
        return ""
    return os.path.basename(path_or_name.replace("\\", "/"))


def _detect_content_type(filename: str, default: str = "application/octet-stream") -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    elif ext == ".png":
        return "image/png"
    elif ext == ".webp":
        return "image/webp"
    elif ext in [".m4a", ".mp4", ".aac"]:
        # RFC 4337: audio/mp4 is the browser standard for m4a/aac audio containers
        return "audio/mp4"
    elif ext == ".mp3":
        return "audio/mpeg"
    elif ext == ".wav":
        return "audio/wav"
    elif ext in [".ogg", ".oga"]:
        return "audio/ogg"
    
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or default


async def save_media_file(
    file_bytes: bytes,
    filename: str,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Dual-layer storage:
    1. Writes to local disk cache (settings.UPLOAD_DIR) for fast local reads.
    2. Persists to MongoDB Atlas GridFS so evidence survives Render restarts and dyno wipes.
    """
    clean_filename = _normalize_filename(filename)
    detected_type = content_type or _detect_content_type(clean_filename)
    metadata = metadata or {}
    metadata["content_type"] = detected_type
    metadata["size"] = len(file_bytes)

    # 1. Local disk cache
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    local_path = os.path.join(settings.UPLOAD_DIR, clean_filename)
    try:
        with open(local_path, "wb") as f:
            f.write(file_bytes)
    except Exception as e:
        logger.warning(f"Failed to write to local disk cache {local_path}: {e}")

    # 2. MongoDB Atlas GridFS Persistent Storage
    gridfs_id = None
    try:
        bucket = get_gridfs_bucket()
        # Clean up any existing file with same filename to avoid duplicates
        try:
            cursor = bucket.find({"filename": clean_filename})
            async for existing in cursor:
                await bucket.delete(existing["_id"])
        except Exception:
            pass

        gridfs_id = await bucket.upload_from_stream(
            clean_filename,
            file_bytes,
            metadata=metadata
        )
        logger.info(f"PERSISTENT STORAGE: Saved {clean_filename} ({len(file_bytes)} bytes) to MongoDB GridFS ID: {gridfs_id}")
    except Exception as e:
        logger.error(f"Failed to save {clean_filename} to MongoDB GridFS: {e}")

    return {
        "filename": clean_filename,
        "local_path": local_path,
        "gridfs_id": str(gridfs_id) if gridfs_id else None,
        "size": len(file_bytes),
        "content_type": detected_type,
    }


async def get_media_file(filename_or_path: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve media file:
    1. Checks local disk cache first.
    2. If missing (e.g. after Render dyno restart), fetches from MongoDB GridFS and re-hydrates disk cache.
    """
    clean_filename = _normalize_filename(filename_or_path)
    if not clean_filename:
        return None

    local_path = os.path.join(settings.UPLOAD_DIR, clean_filename)
    content_type = _detect_content_type(clean_filename)

    # 1. Check local disk cache
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        try:
            with open(local_path, "rb") as f:
                data = f.read()
            return {
                "filename": clean_filename,
                "bytes": data,
                "size": len(data),
                "content_type": content_type,
                "source": "disk_cache"
            }
        except Exception as e:
            logger.warning(f"Error reading local disk cache {local_path}: {e}")

    # 2. Check MongoDB GridFS
    try:
        bucket = get_gridfs_bucket()
        cursor = bucket.find({"filename": clean_filename})
        file_doc = await cursor.to_list(length=1)
        
        if not file_doc:
            # Try searching by ObjectId if filename_or_path looks like an ObjectId
            try:
                if len(clean_filename) == 24:
                    obj_id = ObjectId(clean_filename)
                    cursor = bucket.find({"_id": obj_id})
                    file_doc = await cursor.to_list(length=1)
            except Exception:
                pass

        if file_doc:
            doc = file_doc[0]
            download_stream = await bucket.open_download_stream(doc["_id"])
            data = await download_stream.read()
            doc_meta = doc.get("metadata") or {}
            stored_type = doc_meta.get("content_type") or content_type

            # Re-hydrate local disk cache so next read is immediate
            try:
                os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(data)
                logger.info(f"Re-hydrated local disk cache for {clean_filename} from MongoDB GridFS")
            except Exception as w_err:
                logger.debug(f"Cache re-hydration note: {w_err}")

            return {
                "filename": clean_filename,
                "bytes": data,
                "size": len(data),
                "content_type": stored_type,
                "source": "gridfs"
            }
    except Exception as e:
        logger.error(f"GridFS retrieval failed for {clean_filename}: {e}")

    return None


def _generate_svg_photo_fallback(title: str, subtitle: str) -> bytes:
    """Generate sleek SVG badge for missing or unexposed photo evidence."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e1b4b"/>
    </linearGradient>
    <linearGradient id="badge" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ec4899"/>
      <stop offset="100%" stop-color="#8b5cf6"/>
    </linearGradient>
  </defs>
  <rect width="640" height="480" fill="url(#bg)" rx="16"/>
  <rect x="20" y="20" width="600" height="440" fill="none" stroke="#334155" stroke-width="2" stroke-dasharray="8 6" rx="12"/>
  
  <circle cx="320" cy="180" r="48" fill="#1e293b" stroke="#475569" stroke-width="2"/>
  <path d="M304 165 h32 l8 12 h16 a8 8 0 0 1 8 8 v40 a8 8 0 0 1 -8 8 h-80 a8 8 0 0 1 -8 -8 v-40 a8 8 0 0 1 8 -8 h16 z" fill="none" stroke="url(#badge)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="320" cy="195" r="14" fill="none" stroke="url(#badge)" stroke-width="3"/>
  
  <text x="320" y="270" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="20" font-weight="bold" fill="#f1f5f9" text-anchor="middle">
    {title}
  </text>
  <text x="320" y="302" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" font-size="13" fill="#94a3b8" text-anchor="middle">
    {subtitle}
  </text>
  <rect x="220" y="340" width="200" height="32" rx="6" fill="#1e293b" stroke="#334155"/>
  <text x="320" y="361" font-family="monospace" font-size="11" fill="#ec4899" text-anchor="middle" font-weight="bold">
    SAFEHER EVIDENCE ARCHIVE
  </text>
</svg>"""
    return svg.encode("utf-8")


async def handle_photo_stream_response(filename_or_path: str, fallback_title: str = "Photo Evidence") -> Response:
    """Serve photo with automatic GridFS retrieval and robust SVG fallback if not found."""
    media = await get_media_file(filename_or_path)
    
    if media and media.get("bytes"):
        return Response(
            content=media["bytes"],
            status_code=200,
            media_type=media.get("content_type", "image/jpeg"),
            headers={
                "Content-Length": str(media["size"]),
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*",
                "X-SafeHer-Storage": media.get("source", "unknown"),
            }
        )

    # Graceful fallback: render informative SVG badge instead of 404/broken box
    fallback_svg = _generate_svg_photo_fallback(
        fallback_title,
        "Snapshot captured prior to persistent storage initialization."
    )
    return Response(
        content=fallback_svg,
        status_code=200,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
            "X-SafeHer-Fallback": "true"
        }
    )


async def handle_audio_stream_response(request: Request, filename_or_path: str) -> Response:
    """
    Serve audio evidence with full HTTP Range (RFC 7233) support for HTML5 <audio>.
    Enables duration calculation (avoids 0:00 bug), scrub bar seeking, and browser compatibility.
    """
    media = await get_media_file(filename_or_path)
    if not media or not media.get("bytes"):
        raise HTTPException(status_code=404, detail="Audio evidence not found")

    file_bytes = media["bytes"]
    total_size = len(file_bytes)
    content_type = media.get("content_type", "audio/mp4")

    # Range header support for browser seeking & duration computation
    range_header = request.headers.get("range")
    if range_header:
        # Expected format: "bytes=start-end" or "bytes=start-"
        range_match = re.match(r"bytes=(\d+)-(\d*)", range_header.strip())
        if range_match:
            start = int(range_match.group(1))
            end_str = range_match.group(2)
            end = int(end_str) if end_str else total_size - 1

            if start >= total_size:
                raise HTTPException(
                    status_code=416,
                    detail="Requested Range Not Satisfiable",
                    headers={"Content-Range": f"bytes */{total_size}"}
                )

            end = min(end, total_size - 1)
            chunk = file_bytes[start : end + 1]

            return Response(
                content=chunk,
                status_code=206,
                media_type=content_type,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{total_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(len(chunk)),
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*",
                    "X-SafeHer-Storage": media.get("source", "unknown"),
                }
            )

    return Response(
        content=file_bytes,
        status_code=200,
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(total_size),
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*",
            "X-SafeHer-Storage": media.get("source", "unknown"),
        }
    )
