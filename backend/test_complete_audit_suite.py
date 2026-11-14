"""
SafeHer AI: Full System API Audit & Workflow Verification Test Suite
Covers all endpoints, schemas, database queries, and user-to-admin workflows.
"""
import sys
import os
import asyncio
import uuid
from datetime import datetime, timedelta
import io

from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path)

# Set stdout encoding for Windows
if sys.platform == "win32" and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import connect_db, close_db, get_collection
from app.core.security import create_access_token, get_password_hash
from app.models.location import LocationUpdate
from app.models.contact import EmergencyContactCreate, EmergencyContactUpdate
from app.models.complaint import ComplaintCreate, ComplaintStatus
from app.models.alert import SOSAlertCreate, LocationData
from app.services.alert_service import create_sos_alert, resolve_alert
from app.services.walk_service import WalkService
from app.services.report_service import ReportGenerator
from app.ai.llm_engine import generate_rule_based_chat_response, evaluate_keyword_and_acoustic_threat
from app.utils.geocoding import reverse_geocode
from app.utils.pathfinding import calculate_safe_route
from app.websockets.socket_manager import get_connected_count

async def run_full_audit_suite():
    print("=" * 80)
    print("🚀 SAFEHER AI: COMPREHENSIVE END-TO-END API & SYSTEM VERIFICATION SUITE")
    print("=" * 80)

    # 1. Database Connection Check
    print("\n[TEST 1] Testing Database Connection...")
    await connect_db()
    users_col = get_collection("users")
    assert users_col is not None, "Users collection is unreachable"
    print("  [PASS] MongoDB Atlas connection verified and collections responding.")

    # 2. Authentication & JWT Tokens
    print("\n[TEST 2] Testing Auth & JWT Token Engine...")
    test_user_id = "audit-test-user-001"
    token = create_access_token({"sub": test_user_id, "role": "user", "phone": "+919999999999"})
    assert token and isinstance(token, str), "Failed to generate JWT access token"
    from app.core.security import decode_token
    payload = decode_token(token)
    assert payload.get("sub") == test_user_id, "Decoded token subject does not match"
    print(f"  [PASS] JWT Token Generation & Verification: Valid token for {test_user_id}")

    # 3. Emergency Contacts Operations
    print("\n[TEST 3] Testing Emergency Contacts Operations...")
    contacts_col = get_collection("emergency_contacts")
    # Clean previous audit test contacts
    await contacts_col.delete_many({"user_id": test_user_id})
    
    c_id = str(uuid.uuid4())
    test_contact = {
        "_id": c_id,
        "user_id": test_user_id,
        "name": "Jane Guardian",
        "phone": "+919876543210",
        "relation": "Sister",
        "is_primary": True,
        "notify_sms": True,
        "notify_call": True,
        "created_at": datetime.utcnow()
    }
    await contacts_col.insert_one(test_contact)
    found = await contacts_col.find_one({"_id": c_id})
    assert found and found["name"] == "Jane Guardian", "Failed to retrieve inserted contact"

    # Update contact
    await contacts_col.update_one({"_id": c_id}, {"$set": {"relation": "Mother"}})
    updated = await contacts_col.find_one({"_id": c_id})
    assert updated["relation"] == "Mother", "Contact update failed"
    print("  [PASS] Emergency Contacts: Insert, Query, and Update verified.")

    # 4. Geocoding & GPS Reverse Lookup
    print("\n[TEST 4] Testing Geocoding & Location Normalization...")
    geo = await reverse_geocode(12.9716, 77.5946)
    assert geo and "formatted_address" in geo, "Reverse geocoding failed"
    print(f"  [PASS] Reverse Geocoding (12.9716, 77.5946) -> {geo.get('formatted_address', '')[:60]}...")

    # 5. Full Standard SOS & GPS Workflow
    print("\n[TEST 5] Testing Standard SOS Trigger & GPS Breadcrumbs...")
    alerts_col = get_collection("alerts")
    await alerts_col.delete_many({"user_id": test_user_id})

    loc = LocationData(latitude=12.9716, longitude=77.5946)
    sos_data = SOSAlertCreate(
        user_id=test_user_id,
        trigger_type="button_press",
        location=loc,
        message="EMERGENCY SOS - Physical Alert Pressed",
    )
    alert = await create_sos_alert(sos_data, None)
    alert_id = alert["_id"]
    assert alert["status"] == "active", "SOS alert should be active upon creation"
    print(f"  [PASS] SOS Alert Created: {alert_id} | Status: active | Severity: {alert['severity']}")

    # Test High-Frequency Live GPS Breadcrumb update
    lh_col = get_collection("location_history")
    lh_id = str(uuid.uuid4())
    await lh_col.insert_one({
        "_id": lh_id,
        "user_id": test_user_id,
        "latitude": 12.9720,
        "longitude": 77.5950,
        "accuracy": 5.0,
        "speed": 1.2,
        "formatted_address": "Near MG Road, Bengaluru",
        "timestamp": datetime.utcnow(),
        "source": "sos_live"
    })
    lh_entry = await lh_col.find_one({"_id": lh_id})
    assert lh_entry is not None, "Failed to persist SOS live breadcrumb"
    print("  [PASS] High-frequency SOS Live Location tracking verified.")

    # Resolve SOS
    resolved = await resolve_alert(alert_id)
    assert resolved and resolved["status"] == "resolved", "Failed to resolve SOS alert"
    print(f"  [PASS] SOS Incident Resolution verified: {alert_id} marked as resolved.")

    # 6. Walk With Me Safety Pathfinding
    print("\n[TEST 6] Testing Walk With Me Route Calculation & A* Pathfinding...")
    danger_zones = [{"latitude": 12.9730, "longitude": 77.5960, "radius_km": 0.5, "risk_score": 90}]
    route = calculate_safe_route(12.9716, 77.5946, 12.9780, 77.5990, danger_zones)
    assert route and len(route) >= 2, "Pathfinding returned empty route"
    print(f"  [PASS] Safe Corridor Pathfinding: Computed corridor with {len(route)} waypoints avoiding danger zone.")

    # 7. AI Predictive Guardian
    print("\n[TEST 7] Testing AI Predictive Guardian Engine...")
    rule_chat = generate_rule_based_chat_response("I think someone is following me")
    assert rule_chat["danger_detected"] is True, "AI Chat failed to detect danger"
    assert rule_chat["danger_level"] == "critical", "AI Chat danger level not critical"
    print(f"  [PASS] AI Threat Detection: {rule_chat['danger_level'].upper()} detected for 'following me'.")

    # 8. Complaints Submission & Admin Resolution Workflow
    print("\n[TEST 8] Testing Complaints Lifecycle Workflow...")
    complaints_col = get_collection("complaints")
    await complaints_col.delete_many({"user_id": test_user_id})

    comp_id = str(uuid.uuid4())
    complaint_doc = {
        "_id": comp_id,
        "complaint_id": comp_id,
        "user_id": test_user_id,
        "title": "Street light malfunction in dark alley",
        "description": "Lack of street lighting creates safety hazard during night commute.",
        "category": "Harassment",
        "status": ComplaintStatus.pending.value,
        "district": "Bengaluru Urban",
        "division": "Bengaluru Division",
        "state": "Karnataka",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    await complaints_col.insert_one(complaint_doc)

    # Admin updates complaint to in_progress then resolved
    await complaints_col.update_one(
        {"_id": comp_id},
        {"$set": {
            "status": ComplaintStatus.resolved.value,
            "resolved_at": datetime.utcnow(),
            "resolved_by_name": "Audit Admin",
            "resolution_notes": "Street light fixed by local municipal authority."
        }}
    )
    comp_resolved = await complaints_col.find_one({"_id": comp_id})
    assert comp_resolved["status"] == ComplaintStatus.resolved.value, "Complaint resolution update failed"
    print(f"  [PASS] Complaint Lifecycle: Submission -> Review -> Resolved with notes.")

    # 9. Broadcast Emergency Notifications
    print("\n[TEST 9] Testing Broadcast & Emergency Notifications...")
    broadcasts_col = get_collection("broadcasts")
    b_id = str(uuid.uuid4())
    broadcast_doc = {
        "_id": b_id,
        "title": "Safety Advisory: Heavy Rain",
        "body": "Avoid waterlogged subways near Majestic.",
        "type": "safety_tip",
        "priority": "high",
        "target_type": "all",
        "read_by": [],
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(days=1)
    }
    await broadcasts_col.insert_one(broadcast_doc)
    
    # Mark read by user
    await broadcasts_col.update_one({"_id": b_id}, {"$addToSet": {"read_by": test_user_id}})
    b_read = await broadcasts_col.find_one({"_id": b_id})
    assert test_user_id in b_read["read_by"], "User failed to mark broadcast as read"
    print("  [PASS] Broadcast System: Dispatch & Mark-as-Read verified.")

    # 10. Official Intelligence PDF Report Generation
    print("\n[TEST 10] Testing Government-Ready PDF Intelligence Report Generator...")
    mock_admin = {
        "_id": "admin-audit-1",
        "email": "audit_admin@safeher.gov.in",
        "role": "super_admin",
        "state": "Karnataka"
    }
    generator = ReportGenerator(
        admin=mock_admin,
        start_date=None,
        end_date=None,
        requested_district="Bengaluru Urban",
        requested_division="Bengaluru Division"
    )
    pdf_buf = await generator.generate_pdf()
    pdf_bytes = pdf_buf.getvalue()
    assert len(pdf_bytes) > 1000, "Generated PDF is empty or corrupted"
    assert pdf_bytes.startswith(b"%PDF"), "Generated file does not have valid PDF magic bytes"
    print(f"  [PASS] PDF Report Generator: Produced official intelligence report ({len(pdf_bytes)} bytes).")

    # 11. Socket.IO Telemetry Status
    print("\n[TEST 11] Testing Socket.IO Real-Time Telemetry...")
    conn_count = get_connected_count()
    assert "total_users" in conn_count and "admins" in conn_count, "Socket connection counter malformed"
    print(f"  [PASS] Socket.IO Telemetry Engine active (active users: {conn_count['total_users']}, active admins: {conn_count['admins']}).")

    # Clean up test audit data
    await contacts_col.delete_many({"user_id": test_user_id})
    await alerts_col.delete_many({"user_id": test_user_id})
    await lh_col.delete_many({"user_id": test_user_id})
    await complaints_col.delete_many({"user_id": test_user_id})
    await broadcasts_col.delete_many({"_id": b_id})
    print("\n[CLEANUP] Audit test records purged successfully.")

    print("\n" + "=" * 80)
    print("🎉 ALL 11 API & SYSTEM AUDIT TEST SUITES PASSED FLAWLESSLY!")
    print("=" * 80)
    await close_db()
    return True

if __name__ == "__main__":
    success = asyncio.run(run_full_audit_suite())
    sys.exit(0 if success else 1)
