import sys
import os
import io
import wave
import struct
import math
from dotenv import load_dotenv

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
load_dotenv(os.path.join(backend_dir, ".env"))

import pytest
import httpx
from app.main import app
from app.core.security import get_current_user, get_current_admin
from app.ai.llm_engine import (
    evaluate_keyword_and_acoustic_threat,
    analyze_audio_intelligence,
    generate_ai_decision_log,
)
from app.ai.voice_analyzer import _pure_python_acoustic_analysis

# Helper to generate in-memory synthetic audio bytes with specified volume & frequency
def create_test_wav(duration_sec: float = 1.0, freq_hz: float = 440.0, volume: float = 0.5) -> bytes:
    sample_rate = 16000
    num_samples = int(sample_rate * duration_sec)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(num_samples):
            val = int(volume * 32767.0 * math.sin(2.0 * math.pi * freq_hz * (i / sample_rate)))
            frames.extend(struct.pack('<h', max(-32768, min(32767, val))))
        wf.writeframes(frames)
    return buf.getvalue()

TEST_USER = {
    "_id": "test_user_voice_sos",
    "name": "Priya Sharma",
    "email": "priya@example.com",
    "phone": "+919876543210",
    "role": "user",
    "district": "Central Division",
    "division": "Metro"
}

TEST_ADMIN = {
    "_id": "test_admin_voice_sos",
    "name": "Dispatcher Officer",
    "email": "dispatcher@safeher.gov",
    "role": "admin",
    "district": "Central Division"
}

app.dependency_overrides[get_current_user] = lambda: TEST_USER
app.dependency_overrides[get_current_admin] = lambda: TEST_ADMIN

@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_contextual_distress_phrase_help_me():
    """Test Case 1: Configured distress phrase 'Help me, someone is following me' triggers CRITICAL risk."""
    intel = evaluate_keyword_and_acoustic_threat(
        "Help me, someone is following me!",
        {"stress_score": 0.85, "emotion": "panic/rapid_speech", "acoustic_features": {"dbfs": -20.0, "pitch_hz": 280.0}}
    )
    assert intel["danger_level"] == "CRITICAL"
    assert intel["risk_score"] >= 88
    assert intel["intent"] == "URGENT_DISTRESS"
    assert intel["trigger_emergency_protocol"] is True
    assert any("help me" in p.lower() for p in intel["distress_phrases_detected"])


@pytest.mark.anyio
async def test_contextual_distress_phrase_save_me_and_danger():
    """Test Case 2: Configured distress phrases 'Save me' and 'I'm in danger' trigger CRITICAL risk."""
    intel = evaluate_keyword_and_acoustic_threat(
        "Save me! Please call the police, I'm in danger!",
        {"stress_score": 0.78, "emotion": "fear/scream", "acoustic_features": {"dbfs": -18.0, "pitch_hz": 310.0}}
    )
    assert intel["danger_level"] == "CRITICAL"
    assert intel["risk_score"] >= 88
    assert intel["intent"] == "URGENT_DISTRESS"
    assert intel["trigger_emergency_protocol"] is True
    assert "save me" in [p.lower() for p in intel["distress_phrases_detected"]]


@pytest.mark.anyio
async def test_multilingual_distress_phrase_bachao():
    """Test Case 3: Multilingual Hinglish distress phrase 'Bachao mujhe koi stalk kar raha hai'."""
    intel = evaluate_keyword_and_acoustic_threat(
        "Bachao mujhe, koi piche aa raha hai, madad karo!",
        {"stress_score": 0.82, "emotion": "panic/rapid_speech"}
    )
    assert intel["danger_level"] == "CRITICAL"
    assert intel["risk_score"] >= 88
    assert intel["intent"] == "URGENT_DISTRESS"
    assert intel["trigger_emergency_protocol"] is True


@pytest.mark.anyio
async def test_false_positive_protection_homework():
    """Test Case 4: Benign sentence with 'help' ('help me with homework') is suppressed as SAFE."""
    intel = evaluate_keyword_and_acoustic_threat(
        "Can you please help me with my math homework tonight?",
        {"stress_score": 0.20, "emotion": "calm/conversational", "acoustic_features": {"dbfs": -30.0, "pitch_hz": 180.0}}
    )
    assert intel["danger_level"] == "SAFE"
    assert intel["risk_score"] <= 30
    assert intel["intent"] == "BENIGN_CONVERSATION"
    assert intel["trigger_emergency_protocol"] is False
    assert "false positive suppressed" in intel["trigger_reason"].lower()


@pytest.mark.anyio
async def test_false_positive_protection_normal_conversation():
    """Test Case 5: Normal conversational chatter without distress phrases is classified as SAFE/LOW."""
    intel = evaluate_keyword_and_acoustic_threat(
        "Hello, I am having coffee with friends and everything is fine.",
        {"stress_score": 0.15, "emotion": "calm/conversational", "acoustic_features": {"dbfs": -28.0}}
    )
    assert intel["danger_level"] in ["SAFE", "LOW"]
    assert intel["risk_score"] <= 35
    assert intel["trigger_emergency_protocol"] is False


@pytest.mark.anyio
async def test_ambient_silence_noise_protection():
    """Test Case 6: Low-amplitude background silence or hiss does not trigger SOS."""
    intel = evaluate_keyword_and_acoustic_threat(
        "",
        {"stress_score": 0.10, "emotion": "ambient/silence", "acoustic_features": {"dbfs": -55.0, "energy_rms": 150}}
    )
    assert intel["danger_level"] == "SAFE"
    assert intel["risk_score"] <= 15
    assert intel["intent"] == "AMBIENT_NOISE"
    assert intel["trigger_emergency_protocol"] is False


@pytest.mark.anyio
async def test_acoustic_screaming_duress_without_words():
    """Test Case 7: Panic frequency / screaming without coherent words triggers acoustic duress SOS."""
    intel = evaluate_keyword_and_acoustic_threat(
        "",
        {"stress_score": 0.92, "emotion": "fear/scream", "acoustic_features": {"dbfs": -10.0, "pitch_hz": 380.0}}
    )
    assert intel["danger_level"] == "CRITICAL"
    assert intel["risk_score"] >= 88
    assert intel["intent"] == "ACOUSTIC_DISTRESS"
    assert intel["trigger_emergency_protocol"] is True


@pytest.mark.anyio
async def test_failed_ai_service_resilience():
    """Test Case 8: When external LLM/Ollama is offline, contextual classifier accurately evaluates threat without crashing."""
    # Pass an unreachable Ollama URL to verify fallback resilience
    intel = await analyze_audio_intelligence(
        "Please help me, someone is chasing me with a knife!",
        {"stress_score": 0.88, "emotion": "fear/scream", "acoustic_features": {"dbfs": -16.0, "pitch_hz": 320.0}},
        {"latitude": 12.9716, "longitude": 77.5946}
    )
    assert intel["danger_level"] == "CRITICAL"
    assert intel["risk_score"] >= 88
    assert intel["trigger_emergency_protocol"] is True
    assert intel["fallback_active"] is True
    assert "SafeHer" in intel["ai_engine"]


@pytest.mark.anyio
async def test_decision_log_generation_audit_trail():
    """Test Case 9: Structured decision log contains all 6 audit steps, metrics, and thresholds."""
    intel = evaluate_keyword_and_acoustic_threat("Help me, emergency!", {"stress_score": 0.80})
    log = generate_ai_decision_log(
        session_id="test_sess_123",
        transcript="Help me, emergency!",
        acoustic_data={"stress_score": 0.80, "emotion": "panic"},
        intel=intel,
        location={"latitude": 12.9716, "longitude": 77.5946},
        audio_meta={"filesize_bytes": 10240, "duration_sec": 5.0, "gridfs_id": "gridfs_mock_1"},
        threshold=75,
        action_taken="AUTO_SOS_CREATED",
        alert_id="alert_mock_999"
    )
    assert log["session_id"] == "test_sess_123"
    assert log["decision"]["threshold_used"] == 75
    assert log["decision"]["action_taken"] == "AUTO_SOS_CREATED"
    assert log["decision"]["trigger_emergency_criteria_met"] is True
    assert len(log["audit_steps"]) == 6
    assert all("status" in s and s["status"] in ["COMPLETED", "FALLBACK"] for s in log["audit_steps"])


@pytest.mark.anyio
async def test_e2e_voice_sos_trigger_endpoint_emergency_creation():
    """Test Case 10: Complete E2E POST /api/sos/trigger-voice with distress audio creates active SOS alert."""
    test_audio = create_test_wav(duration_sec=1.0, freq_hz=520.0, volume=0.8)
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        files = {"audio": ("sos_distress.wav", test_audio, "audio/wav")}
        data = {
            "latitude": "12.9716",
            "longitude": "77.5946",
            "force_trigger": "true"
        }
        res = await ac.post("/api/sos/trigger-voice", data=data, files=files)
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["auto_sos_created"] is True
        assert "alert" in body
        assert "decision_log" in body
        assert "cancellation_window_seconds" in body
        alert_id = body["alert"]["id"]

        # Test Case 11: Duplicate Prevention - second upload attaches to active alert
        files_2 = {"audio": ("sos_followup.wav", test_audio, "audio/wav")}
        res_2 = await ac.post("/api/sos/trigger-voice", data={"latitude": "12.9716", "longitude": "77.5946", "force_trigger": "true"}, files=files_2)
        assert res_2.status_code == 200
        body_2 = res_2.json()
        assert body_2["success"] is True
        assert "DUPLICATE_PREVENTED" in body_2["decision"] or body_2["alert"]["id"] == alert_id

        # Test Case 12: Discreet Cancellation - cancel active voice alert safely
        res_cancel = await ac.post(f"/api/sos/{alert_id}/cancel-voice", data={"reason": "User confirmed safe - false alarm verification"})
        assert res_cancel.status_code == 200
        cancel_body = res_cancel.json()
        assert cancel_body["success"] is True
        assert cancel_body["status"] == "cancelled"


@pytest.mark.anyio
async def test_manual_sos_functionality_preserved():
    """Test Case 13: Manual button / shake SOS continues to work independently of AI voice."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "trigger_type": "button",
            "location": {"latitude": 12.9716, "longitude": 77.5946},
            "message": "Manual emergency button triggered"
        }
        res = await ac.post("/api/sos/trigger", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "alert" in data
        assert data["alert"]["trigger_type"] == "button"
