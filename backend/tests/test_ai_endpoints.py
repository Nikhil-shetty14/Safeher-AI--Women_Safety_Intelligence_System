import sys
import os
from dotenv import load_dotenv

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
load_dotenv(os.path.join(backend_dir, ".env"))

import pytest
import httpx
from app.main import app
from app.core.security import get_current_user

# Mock the authentication dependency
def override_get_current_user():
    return {
        "_id": "test_user_id",
        "email": "test@example.com",
        "role": "admin",
        "phone": "+1234567890"
    }

app.dependency_overrides[get_current_user] = override_get_current_user

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.mark.anyio
async def test_area_risk_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/ai/area-risk?latitude=12.9716&longitude=77.5946")
        assert res.status_code == 200
        data = res.json()
        assert "risk_score" in data
        assert "threat_level" in data
        assert "fallback_active" in data

@pytest.mark.anyio
async def test_chat_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        payload = {"message": "Hello SafeHer, I feel a bit unsafe walking home.", "session_id": "test_session_1"}
        res = await ac.post("/api/ai/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "reply" in data
        assert "danger_detected" in data

@pytest.mark.anyio
async def test_predict_route_safety():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "start_latitude": 12.9716,
            "start_longitude": 77.5946,
            "end_latitude": 12.9756,
            "end_longitude": 77.5996
        }
        res = await ac.post("/api/ai/predict-route-safety", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True
        assert "safety_score" in data
        assert "safest_route" in data
        assert len(data.get("safest_route")) > 0

@pytest.mark.anyio
async def test_dashboard_stats_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/ai/dashboard-stats")
        assert res.status_code == 200
        data = res.json()
        assert "global_threat_level" in data
        assert "ai_recommendations" in data
        assert "recent_insights" in data
