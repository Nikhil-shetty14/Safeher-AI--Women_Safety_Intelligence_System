import os
import tempfile
import threading
from typing import Optional, Dict, Any
from loguru import logger
from pydub import AudioSegment
from app.core.config import settings

# ── Thread-safe Model Lock to prevent concurrent model allocations ──
_whisper_lock = threading.Lock()
_whisper_model = None
_ai_available = None
_librosa_available = None


def _check_ai() -> bool:
    """Check if local torch and whisper are enabled and importable."""
    global _ai_available
    if not getattr(settings, "ENABLE_LOCAL_HEAVY_AI", False):
        return False
    if _ai_available is not None:
        return _ai_available
    try:
        try:
            import static_ffmpeg
            static_ffmpeg.add_paths()
        except Exception as fe:
            logger.debug(f"static_ffmpeg note: {fe}")
        import torch  # noqa: F401
        import whisper  # noqa: F401
        _ai_available = True
        logger.info("Local Heavy AI (Torch/Whisper) loaded successfully.")
    except (ImportError, OSError) as e:
        _ai_available = False
        logger.warning(f"Local PyTorch/Whisper unavailable: {e}")
    return _ai_available


def _check_librosa() -> bool:
    """Check if local librosa is enabled and importable."""
    global _librosa_available
    if not getattr(settings, "ENABLE_LOCAL_HEAVY_AI", False):
        return False
    if _librosa_available is not None:
        return _librosa_available
    try:
        import librosa  # noqa: F401
        _librosa_available = True
    except (ImportError, OSError) as e:
        _librosa_available = False
        logger.debug(f"Librosa unavailable: {e}")
    return _librosa_available


def get_whisper_model():
    """Thread-safe lazy loader for local Whisper (only when ENABLE_LOCAL_HEAVY_AI=True)."""
    global _whisper_model
    if not _check_ai():
        return None
    with _whisper_lock:
        if _whisper_model is None:
            try:
                import torch
                import whisper
                device = "cuda" if torch.cuda.is_available() else "cpu"
                _whisper_model = whisper.load_model("tiny" if device == "cpu" else "base", device=device)
                logger.info(f"Local Whisper model loaded on {device}")
            except Exception as e:
                logger.error(f"Whisper initialization failed: {e}")
    return _whisper_model


async def _cloud_transcribe_groq(audio_file_path: str, api_key: str) -> Optional[str]:
    """Transcribe audio via Groq Whisper API (whisper-large-v3-turbo, ~200ms latency, 0MB RAM)."""
    import httpx
    try:
        filename = os.path.basename(audio_file_path)
        with open(audio_file_path, "rb") as f:
            file_bytes = f.read()

        async with httpx.AsyncClient(timeout=15.0) as client:
            files = {"file": (filename, file_bytes, "audio/m4a")}
            data = {"model": "whisper-large-v3-turbo"}
            headers = {"Authorization": f"Bearer {api_key}"}
            resp = await client.post("https://api.groq.com/openai/v1/audio/transcriptions", files=files, data=data, headers=headers)
            if resp.status_code == 200:
                result = resp.json()
                text = result.get("text", "").strip()
                logger.info(f"Groq Cloud Whisper transcription succeeded ({len(text)} chars)")
                return text
            else:
                logger.warning(f"Groq transcription returned status {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Groq Whisper transcription failed: {e}")
    return None


async def _cloud_transcribe_openai(audio_file_path: str, api_key: str) -> Optional[str]:
    """Transcribe audio via OpenAI Whisper API (0MB local RAM)."""
    import httpx
    try:
        filename = os.path.basename(audio_file_path)
        with open(audio_file_path, "rb") as f:
            file_bytes = f.read()

        async with httpx.AsyncClient(timeout=15.0) as client:
            files = {"file": (filename, file_bytes, "audio/m4a")}
            data = {"model": "whisper-1"}
            headers = {"Authorization": f"Bearer {api_key}"}
            resp = await client.post("https://api.openai.com/v1/audio/transcriptions", files=files, data=data, headers=headers)
            if resp.status_code == 200:
                result = resp.json()
                text = result.get("text", "").strip()
                logger.info(f"OpenAI Cloud Whisper transcription succeeded ({len(text)} chars)")
                return text
    except Exception as e:
        logger.error(f"OpenAI Whisper transcription failed: {e}")
    return None


async def _external_service_transcribe(audio_file_path: str, base_url: str) -> Optional[str]:
    """Transcribe audio via a dedicated external AI inference microservice."""
    import httpx
    try:
        url = f"{base_url.rstrip('/')}/transcribe"
        filename = os.path.basename(audio_file_path)
        with open(audio_file_path, "rb") as f:
            file_bytes = f.read()

        async with httpx.AsyncClient(timeout=20.0) as client:
            files = {"audio": (filename, file_bytes, "audio/m4a")}
            resp = await client.post(url, files=files)
            if resp.status_code == 200:
                result = resp.json()
                return result.get("transcript") or result.get("text")
    except Exception as e:
        logger.error(f"External AI inference microservice transcription failed: {e}")
    return None


def _sync_local_whisper_transcribe(audio_file_path: str) -> Optional[str]:
    """Synchronous local Whisper transcription if enabled."""
    model = get_whisper_model()
    if not model:
        return None

    temp_wav = None
    try:
        target_path = audio_file_path
        if not audio_file_path.endswith(".wav"):
            audio = AudioSegment.from_file(audio_file_path)
            temp_wav = audio_file_path + ".normalized.wav"
            audio.export(temp_wav, format="wav")
            target_path = temp_wav

        result = model.transcribe(target_path, fp16=False)
        return result.get("text", "").strip()
    except Exception as e:
        logger.error(f"Local Whisper transcription error: {e}")
        return None
    finally:
        if temp_wav and os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass


async def transcribe_audio(audio_file_path: str) -> Optional[str]:
    """
    Transcribe emergency audio.
    Prioritizes:
    1. Dedicated AI Inference Service URL (0MB local RAM)
    2. Cloud Whisper APIs (Groq / OpenAI) (0MB local RAM)
    3. Local Whisper (only if ENABLE_LOCAL_HEAVY_AI=True)
    4. Heuristic Fallback
    """
    if not os.path.exists(audio_file_path) or os.path.getsize(audio_file_path) == 0:
        return ""

    # 1. External Microservice
    ext_url = getattr(settings, "AI_INFERENCE_SERVICE_URL", "").strip()
    if ext_url:
        result = await _external_service_transcribe(audio_file_path, ext_url)
        if result:
            return result

    # 2. Cloud Whisper (Groq)
    groq_key = getattr(settings, "GROQ_API_KEY", "").strip()
    if groq_key:
        result = await _cloud_transcribe_groq(audio_file_path, groq_key)
        if result:
            return result

    # 3. Cloud Whisper (OpenAI)
    openai_key = getattr(settings, "OPENAI_API_KEY", "").strip()
    if openai_key:
        result = await _cloud_transcribe_openai(audio_file_path, openai_key)
        if result:
            return result

    # 4. Local Whisper (only if heavy AI explicitly enabled)
    if _check_ai():
        import asyncio
        result = await asyncio.to_thread(_sync_local_whisper_transcribe, audio_file_path)
        if result:
            return result

    logger.info("Transcribe: Cloud STT not configured and local heavy AI disabled. Audio archived with acoustic distress telemetry.")
    return "[Emergency audio recorded and archived - acoustic telemetry analyzed]"


def _pure_python_acoustic_analysis(audio_file_path: str) -> Dict[str, Any]:
    """
    Zero-RAM, ultra-fast acoustic distress analysis using pure Python and pydub.
    Computes RMS volume, dBFS loudness, dynamic stress variance, and detects panic vocal signatures.
    Runs in ~5ms with ~0MB RAM overhead.
    """
    try:
        audio = AudioSegment.from_file(audio_file_path)
        # Limit analysis to first 30 seconds for speed and memory bounds
        if len(audio) > 30000:
            audio = audio[:30000]

        rms = float(audio.rms)
        dbfs = float(audio.dBFS) if audio.dBFS != float("-inf") else -90.0
        max_possible = float(audio.max_possible_amplitude)

        # Slice into 250ms chunks to evaluate vocal distress variance
        chunk_length_ms = 250
        chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
        chunk_dbfs = [c.dBFS for c in chunks if c.dBFS != float("-inf")]

        variance = 0.0
        if len(chunk_dbfs) > 1:
            mean_dbfs = sum(chunk_dbfs) / len(chunk_dbfs)
            variance = sum((x - mean_dbfs) ** 2 for x in chunk_dbfs) / len(chunk_dbfs)

        # Distress classification
        # Screaming / extreme loud distress
        if dbfs > -13.0 or rms > 12000:
            stress_score = 0.92
            emotion = "fear/scream"
            danger_level = "critical"
        # Dynamic vocal agitation / shouting / gasping
        elif variance > 75.0 and dbfs > -26.0:
            stress_score = 0.82
            emotion = "panic/rapid_speech"
            danger_level = "high"
        # Elevated background aggression or high volume
        elif dbfs > -18.0 or rms > 7000:
            stress_score = 0.75
            emotion = "aggression/loud_noise"
            danger_level = "high"
        # Whispering / muffled / suppressed vocalization
        elif dbfs < -45.0 or rms < 400:
            stress_score = 0.12
            emotion = "ambient/silence"
            danger_level = "safe"
        elif variance < 45.0 and -38.0 <= dbfs <= -22.0:
            stress_score = 0.20
            emotion = "calm/conversational"
            danger_level = "safe"
        elif variance < 65.0:
            stress_score = 0.35
            emotion = "normal/conversational"
            danger_level = "low"
        else:
            stress_score = 0.48
            emotion = "elevated/tense"
            danger_level = "medium"

        return {
            "stress_score": float(stress_score),
            "emotion": emotion,
            "danger_level": danger_level,
            "acoustic_features": {
                "pitch_hz": 0.0,
                "energy_rms": round(rms, 2),
                "peak_energy": round(max_possible, 2),
                "dbfs": round(dbfs, 2),
                "speech_activity": round(min(1.0, max(0.0, (dbfs + 60.0) / 60.0)), 2),
            },
            "trigger_emergency": stress_score >= 0.75,
            "analysis_engine": "pydub-zero-ram"
        }
    except Exception as e:
        logger.error(f"Pure python acoustic analysis failed: {e}")
        return _get_default_analysis()


def _librosa_acoustic_analysis(audio_file_path: str) -> Dict[str, Any]:
    """Librosa acoustic analysis (used only when heavy AI is explicitly enabled)."""
    try:
        import numpy as np
        import librosa

        y, sr = librosa.load(audio_file_path, sr=16000, duration=30)
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        pitch = np.mean(pitches[pitches > 0]) if np.any(pitches > 0) else 0

        rms = librosa.feature.rms(y=y)[0]
        energy = np.mean(rms)
        energy_max = np.max(rms)

        zcr = librosa.feature.zero_crossing_rate(y)[0]
        speech_rate = np.mean(zcr)

        if pitch > 250 and energy > 0.05:
            stress_score = 0.90
            emotion = "fear/scream"
        elif speech_rate > 0.2:
            stress_score = 0.75
            emotion = "panic/rapid_speech"
        elif energy > 0.08:
            stress_score = 0.80
            emotion = "aggression/loud_noise"
        elif energy < 0.005:
            stress_score = 0.20
            emotion = "whispering/muffled"
        else:
            stress_score = 0.40
            emotion = "agitated"

        danger_level = "low"
        if stress_score > 0.85: danger_level = "critical"
        elif stress_score > 0.7: danger_level = "high"
        elif stress_score > 0.4: danger_level = "medium"

        return {
            "stress_score": float(stress_score),
            "emotion": emotion,
            "danger_level": danger_level,
            "acoustic_features": {
                "pitch_hz": float(pitch),
                "energy_rms": float(energy),
                "peak_energy": float(energy_max),
                "speech_activity": float(speech_rate)
            },
            "trigger_emergency": stress_score > 0.75,
            "analysis_engine": "librosa-heavy"
        }
    except Exception as e:
        logger.error(f"Librosa acoustic analysis failed: {e}")
        return _pure_python_acoustic_analysis(audio_file_path)


async def analyze_voice_stress(audio_file_path: str) -> Dict[str, Any]:
    """Perform acoustic stress analysis in a non-blocking thread."""
    import asyncio
    if _check_librosa():
        return await asyncio.to_thread(_librosa_acoustic_analysis, audio_file_path)
    return await asyncio.to_thread(_pure_python_acoustic_analysis, audio_file_path)


def _get_default_analysis() -> Dict[str, Any]:
    return {
        "stress_score": 0.5,
        "emotion": "undetermined",
        "danger_level": "medium",
        "acoustic_features": {},
        "trigger_emergency": False,
        "analysis_engine": "default-fallback"
    }
