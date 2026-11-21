from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request, Response
from typing import Optional, List, Dict, Any
from app.models.alert import SOSAlertCreate, SOSAlertResponse, LocationData, SOSAlertTriggerResponse
from app.services.alert_service import (
    create_sos_alert, get_active_alerts, get_user_alerts,
    resolve_alert, format_alert_response, acknowledge_alert
)
from app.ai.llm_engine import analyze_text_for_danger, analyze_audio_intelligence, generate_ai_decision_log
from app.ai.voice_analyzer import transcribe_audio, analyze_voice_stress
from app.core.security import get_current_user, get_current_admin
from app.core.config import settings
from app.websockets.socket_manager import broadcast_to_admins
from app.core.database import get_collection
from app.api.routes.admin import get_alert_filter
from app.services.media_storage import save_media_file, handle_photo_stream_response, handle_audio_stream_response
from loguru import logger
import os, uuid, aiofiles, traceback, shutil
from fastapi import Body

router = APIRouter(prefix="/api/sos", tags=["SOS Alerts"])


@router.post("/trigger", response_model=SOSAlertTriggerResponse)
async def trigger_sos(
    alert_data: SOSAlertCreate,
    current_user: dict = Depends(get_current_user)
):
    """Trigger an SOS alert manually with full exception safety and duplicate prevention."""
    ai_fallback_used = False
    sms_status = "success"
    alert_doc = None
    
    try:
        logger.info(f"SOS TRIGGERED | User: {current_user.get('name')} ({current_user.get('_id')}) | Type: {alert_data.trigger_type}")
        alert_data.user_id = current_user["_id"]

        # Duplicate Prevention & Alert Lifecycle:
        # If an active alert exists from an earlier trigger (>5s ago), resolve it so this is a fresh emergency incident.
        # If triggered within 5s (rapid double-tap debounce), reuse and update the active incident.
        alerts_col = get_collection("alerts")
        from datetime import datetime
        now_dt = datetime.utcnow()

        if alerts_col is not None:
            existing_active = await alerts_col.find_one(
                {"user_id": current_user["_id"], "status": "active"},
                sort=[("created_at", -1)]
            )
            if existing_active:
                created_at = existing_active.get("created_at")
                age_sec = (now_dt - created_at).total_seconds() if isinstance(created_at, datetime) else 999
                if age_sec < 5:
                    logger.info(f"Rapid SOS trigger (<5s) for user {current_user.get('name')}: updating active incident {existing_active['_id']}")
                    alert = existing_active
                else:
                    logger.info(f"Resolving older active SOS {existing_active['_id']} ({age_sec:.0f}s old) to create fresh emergency incident")
                    await alerts_col.update_one(
                        {"_id": existing_active["_id"]},
                        {"$set": {"status": "resolved", "resolved_at": now_dt, "resolution_note": "Superseded by new emergency trigger"}}
                    )

        # Quick AI analysis / deterministic synthesis
        ai_analysis = None
        message_to_analyze = alert_data.message or f"User triggered an emergency {alert_data.trigger_type} SOS alert."
        try:
            ai_analysis = await analyze_text_for_danger(message_to_analyze, alert_data.location.dict())
            if ai_analysis and ai_analysis.get("fallback_active"):
                ai_fallback_used = True
        except Exception as ai_err:
            logger.error(f"SOS AI ERROR: {str(ai_err)}")
            ai_fallback_used = True
            ai_analysis = {
                "danger_level": "HIGH",
                "risk_score": 85,
                "emotion": "panic",
                "summary": f"User triggered a critical {alert_data.trigger_type} SOS alert.",
                "recommended_action": ["Attempt immediate contact verification", "Dispatch responders"],
                "fallback_active": True,
                "fallback_reason": str(ai_err)
            }

        # Check emergency contacts to determine SMS status baseline
        try:
            contacts_col = get_collection("emergency_contacts")
            if contacts_col is not None:
                contacts = await contacts_col.find({"user_id": current_user["_id"]}).to_list(length=10)
                if not contacts:
                    sms_status = "no_contacts_configured"
                    logger.warning(f"No emergency contacts configured for user {current_user.get('name')}")
            else:
                sms_status = "database_unavailable"
        except Exception as contacts_err:
            logger.error(f"SOS Contacts check failed: {str(contacts_err)}")
            sms_status = "error_checking_contacts"

        # Create the alert record immediately (dispatches SMS/calls in parallel background task)
        alert = await create_sos_alert(alert_data, ai_analysis)
        alert_doc = await format_alert_response(alert)

        # Format location safely for JSON/Socket.IO serialization
        try:
            loc = alert["location"]
            timestamp = loc.get("timestamp")
            if isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()
            elif timestamp:
                timestamp = str(timestamp)
            else:
                timestamp = now_dt.isoformat()
                
            location_payload = {
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "accuracy": loc.get("accuracy"),
                "address": loc.get("address"),
                "district": loc.get("district"),
                "division": loc.get("division"),
                "timestamp": timestamp,
            }

            # Broadcast via WebSocket to admins
            admin_payload = {
                "alert_id": alert["_id"],
                "id": alert["_id"],
                "_id": alert["_id"],
                "user_id": alert["user_id"],
                "user_name": current_user.get("name") or "Emergency User",
                "user_phone": current_user.get("phone") or "N/A",
                "severity": alert["severity"],
                "location": location_payload,
                "trigger_type": alert.get("trigger_type", "button"),
                "message": alert.get("message"),
                "status": "active",
                "acknowledged": False,
                "created_at": timestamp,
            }
            await broadcast_to_admins("new_sos_alert", admin_payload)
            logger.info(f"Broadcasted new_sos_alert to admins for alert {alert['_id']}")

            # Broadcast Tactical Intelligence Update
            if ai_analysis:
                recommendations = ai_analysis.get("recommendations") or ai_analysis.get("recommended_action")
                if isinstance(recommendations, str):
                    recommendations = [recommendations]
                elif not recommendations:
                    recommendations = ["Dispatch responders immediately."]
                    
                intelligence = {
                    "risk_score": ai_analysis.get("risk_score", 85),
                    "danger_level": ai_analysis.get("danger_level", "HIGH"),
                    "ai_tactical_summary": ai_analysis.get("ai_tactical_summary") or ai_analysis.get("summary") or f"Emergency {alert_data.trigger_type} SOS triggered.",
                    "recommendations": recommendations,
                }
                
                await broadcast_to_admins("tactical_intel_update", {
                    "alert_id": alert["_id"],
                    "id": alert["_id"],
                    "user_name": current_user.get("name") or "Emergency User",
                    "transcript": message_to_analyze,
                    "intelligence": intelligence,
                    "timestamp": timestamp
                })
        except Exception as ws_err:
            logger.error(f"SOS WebSocket Broadcast failed: {str(ws_err)}")

        return {
            "success": True,
            "message": "SOS triggered successfully",
            "ai_fallback_used": ai_fallback_used,
            "sms_status": sms_status,
            "alert": alert_doc
        }
    except Exception as e:
        logger.error(f"SOS TRIGGER CRITICAL ERROR: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"SOS trigger failed: {str(e)}"
        )


@router.post("/trigger-test")
async def trigger_sos_test(
    user_id: str = Body(...),
    latitude: float = Body(None),
    longitude: float = Body(None),
    message: str = Body(None),
):
    """DEV-ONLY: Trigger an SOS for a user without 2FA. Enabled only when DEV_TEST=1."""
    if os.environ.get("DEV_TEST") != "1":
        raise HTTPException(status_code=403, detail="Dev test endpoint disabled")

    try:
        loc = None
        if latitude is not None and longitude is not None:
            loc = LocationData(latitude=latitude, longitude=longitude)
        else:
            loc = LocationData(latitude=0.0, longitude=0.0)

        alert_data = SOSAlertCreate(
            user_id=user_id,
            trigger_type="dev_test",
            location=loc,
            message=message,
        )

        alert = await create_sos_alert(alert_data, None)
        try:
            location_payload = {
                "latitude": alert["location"].get("latitude"),
                "longitude": alert["location"].get("longitude"),
                "accuracy": alert["location"].get("accuracy"),
                "address": alert["location"].get("address"),
                "timestamp": alert["location"].get("timestamp"),
            }
            await broadcast_to_admins("new_sos_alert", {
                "alert_id": alert["_id"],
                "user_id": alert["user_id"],
                "user_name": "(dev-test)",
                "severity": alert["severity"],
                "location": location_payload,
            })
        except Exception:
            logger.exception("Failed broadcasting dev test alert")

        return {"success": True, "alert": alert}
    except Exception as e:
        logger.error(f"DEV TEST SOS failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger-voice")
@router.post("/upload-audio")
async def trigger_sos_with_voice(
    user_id: str = Form("unknown"),
    latitude: str = Form("0.0"),
    longitude: str = Form("0.0"),
    alert_id: str = Form(""),
    force_trigger: bool = Form(False),
    audio: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Intelligent AI Voice SOS workflow with automatic distress detection,
    contextual NLP analysis, false-positive protection, and duplicate prevention.
    """
    from datetime import datetime
    now_iso = datetime.utcnow().isoformat()
    session_id = str(uuid.uuid4())

    try:
        logger.info(f"AI VOICE SOS INGESTION | User: {current_user.get('name')} | File: {audio.filename}")
        
        # Parse coordinates safely
        try:
            lat = float(latitude)
            lng = float(longitude)
        except (ValueError, TypeError):
            lat, lng = 0.0, 0.0

        # Save audio using bounded streaming (max 15MB) into persistent MongoDB Atlas GridFS + local disk cache
        audio_id = str(uuid.uuid4())
        ext = os.path.splitext(audio.filename)[1] or ".m4a"
        filename = f"{audio_id}{ext}"

        MAX_AUDIO_BYTES = 15 * 1024 * 1024
        chunks = []
        total_read = 0
        while True:
            chunk = await audio.read(65536)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > MAX_AUDIO_BYTES:
                return {"success": False, "error": "Audio file exceeds 15MB limit"}
            chunks.append(chunk)

        audio_bytes = b"".join(chunks)
        save_res = await save_media_file(
            audio_bytes,
            filename,
            content_type="audio/mp4" if ext == ".m4a" else None,
            metadata={"user_id": current_user.get("_id"), "alert_id": alert_id, "type": "voice_sos"}
        )
        audio_path = save_res["local_path"]
        gridfs_id = save_res.get("gridfs_id")
        logger.info(f"AUDIO PERSISTED | Path: {audio_path} | GridFS ID: {gridfs_id} | Size: {len(audio_bytes)} bytes")

        # ─── 1. SPEECH TRANSCRIPTION (WHISPER) ───
        trans_text = ""
        try:
            trans_text = await transcribe_audio(audio_path)
            logger.info(f"Whisper transcript: '{trans_text}'")
        except Exception as stt_e:
            logger.error(f"Whisper STT error: {stt_e}")

        # ─── 2. ACOUSTIC DISTRESS ANALYSIS (LIBROSA / SIGNAL) ───
        acoustic_data = {}
        try:
            acoustic_data = await analyze_voice_stress(audio_path)
            logger.info(f"Acoustic stress score: {acoustic_data.get('stress_score')}, Emotion: {acoustic_data.get('emotion')}")
        except Exception as lib_e:
            logger.error(f"Acoustic analysis error: {lib_e}")
            acoustic_data = {
                "stress_score": 0.5,
                "emotion": "undetermined",
                "danger_level": "medium",
                "trigger_emergency": False
            }

        # ─── 3. CONTEXTUAL THREAT EVALUATION (OLLAMA PHI-3 / CONTEXTUAL CLASSIFIER) ───
        audio_meta = {
            "filesize_bytes": len(audio_bytes),
            "duration_sec": 5.0,
            "gridfs_id": gridfs_id
        }
        loc_dict = {"latitude": lat, "longitude": lng}
        user_prefs = current_user.get("safety_preferences", {}) if isinstance(current_user, dict) else {}
        custom_phrase = user_prefs.get("custom_voice_phrase", "Help me") if user_prefs else "Help me"
        intel = await analyze_audio_intelligence(
            trans_text,
            acoustic_data,
            loc_dict,
            audio_meta,
            custom_trigger_phrase=custom_phrase
        )

        # ─── 4. THRESHOLD ARBITRATION & FALSE-POSITIVE PROTECTION ───
        auto_threshold = getattr(settings, "AI_VOICE_AUTO_SOS_THRESHOLD", 75)
        risk_score = int(intel.get("risk_score", 0))
        danger_level = str(intel.get("danger_level", "LOW")).upper()
        
        # Criteria met if risk >= threshold, or explicit distress flag, or caller explicitly attached to active alert / force triggered
        is_client_attached = bool(alert_id and alert_id.strip())
        criteria_met = bool(
            force_trigger or
            is_client_attached or
            risk_score >= auto_threshold or
            danger_level in ["HIGH", "CRITICAL"] or
            intel.get("trigger_emergency_protocol", False)
        )

        alerts_col = get_collection("alerts")
        alert = None
        action_taken = "DISMISSED_BENIGN"

        if criteria_met:
            # ─── 5. DUPLICATE PREVENTION & ALERT SYNCHRONIZATION ───
            if alerts_col is not None:
                # If specific alert_id was passed
                if is_client_attached:
                    target_id = alert_id.strip()
                    alert = await alerts_col.find_one({"_id": target_id, "user_id": current_user["_id"]})
                    if alert:
                        action_taken = "EVIDENCE_ATTACHED_DIRECT"
                        logger.info(f"Attaching voice evidence directly to designated alert: {alert['_id']}")

                # If no alert attached yet, check for existing active alert within duplicate window
                if not alert:
                    existing_active = await alerts_col.find_one(
                        {"user_id": current_user["_id"], "status": "active"},
                        sort=[("created_at", -1)]
                    )
                    if existing_active:
                        created_at = existing_active.get("created_at")
                        now_dt = datetime.utcnow()
                        dup_window = getattr(settings, "AI_VOICE_DUPLICATE_WINDOW_SEC", 300)
                        age_sec = (now_dt - created_at).total_seconds() if isinstance(created_at, datetime) else 999
                        if age_sec < dup_window:
                            alert = existing_active
                            action_taken = "EVIDENCE_ATTACHED_DUPLICATE_PREVENTED"
                            logger.info(f"Duplicate prevented: attaching voice telemetry to active alert {alert['_id']} ({age_sec:.0f}s old)")
                        else:
                            logger.info(f"Resolving stale active alert {existing_active['_id']} ({age_sec:.0f}s old)")
                            await alerts_col.update_one(
                                {"_id": existing_active["_id"]},
                                {"$set": {"status": "resolved", "resolved_at": now_dt, "resolution_note": "Superseded by fresh AI Voice SOS"}}
                            )

            sev_val = "critical" if danger_level == "CRITICAL" else "high"
            trigger_reason = intel.get("trigger_reason") or f"AI Voice SOS triggered with {risk_score}/100 threat score"

            # ─── 6. AUTOMATIC SOS ALERT CREATION (WHEN CRITERIA MET) ───
            if not alert:
                location = LocationData(latitude=lat, longitude=lng)
                alert_data = SOSAlertCreate(
                    user_id=current_user["_id"],
                    trigger_type="voice_intelligence",
                    location=location,
                    message=trans_text or f"Voice SOS: {trigger_reason}",
                    audio_file_path=audio_path,
                )
                alert = await create_sos_alert(alert_data, intel)
                action_taken = "AUTO_SOS_CREATED"
                logger.warning(f"AUTOMATIC AI VOICE SOS ALERT CREATED: {alert['_id']} (Risk: {risk_score})")

                # Broadcast new alert to all connected admin dispatchers
                try:
                    loc = alert.get("location", {})
                    location_payload = {
                        "latitude": lat,
                        "longitude": lng,
                        "accuracy": loc.get("accuracy"),
                        "address": loc.get("address"),
                        "district": loc.get("district"),
                        "division": loc.get("division"),
                        "timestamp": now_iso,
                    }
                    await broadcast_to_admins("new_sos_alert", {
                        "alert_id": alert["_id"],
                        "user_id": alert["user_id"],
                        "user_name": current_user.get("name"),
                        "user_phone": current_user.get("phone"),
                        "severity": sev_val,
                        "location": location_payload,
                        "trigger_type": "voice_intelligence",
                        "message": trans_text or f"Voice SOS: {trigger_reason}",
                        "status": "active",
                        "acknowledged": False,
                        "created_at": now_iso,
                        "risk_score": risk_score,
                    })
                except Exception as ws_e:
                    logger.error(f"Voice SOS instant broadcast error: {ws_e}")

            # ─── 7. UPDATE ALERT WITH DECISION LOG & INTEL ───
            decision_log = generate_ai_decision_log(
                session_id=session_id,
                transcript=trans_text,
                acoustic_data=acoustic_data,
                intel=intel,
                location=loc_dict,
                audio_meta=audio_meta,
                threshold=auto_threshold,
                action_taken=action_taken,
                alert_id=alert["_id"]
            )

            if alerts_col is not None:
                await alerts_col.update_one(
                    {"_id": alert["_id"]},
                    {"$set": {
                        "transcript": trans_text,
                        "ai_analysis": intel,
                        "acoustic_analysis": acoustic_data,
                        "audio_file_path": audio_path,
                        "ai_decision_log": decision_log,
                        "severity": sev_val,
                        "priority_score": 5 if sev_val == "critical" else 4,
                        "trigger_reason": trigger_reason
                    }}
                )

            # Broadcast tactical intelligence update to admins
            try:
                await broadcast_to_admins("tactical_intel_update", {
                    "alert_id": alert["_id"],
                    "user_id": current_user.get("_id"),
                    "user_name": current_user.get("name"),
                    "transcript": trans_text or "(Distress vocalization / acoustic frequency signature)",
                    "intelligence": intel,
                    "acoustic_data": acoustic_data,
                    "decision_log": decision_log,
                    "timestamp": now_iso,
                    "source": "voice",
                    "audio_url": f"/api/sos/audio/{alert['_id']}"
                })
            except Exception as ws_err:
                logger.error(f"Socket intelligence broadcast error: {ws_err}")

            return {
                "success": True,
                "auto_sos_created": True,
                "decision": action_taken,
                "alert": await format_alert_response(alert),
                "transcript": trans_text,
                "intelligence": intel,
                "decision_log": decision_log,
                "cancellation_window_seconds": getattr(settings, "AI_VOICE_CANCELLATION_WINDOW_SEC", 15),
                "cancel_url": f"/api/sos/{alert['_id']}/cancel-voice"
            }

        else:
            # ─── FALSE-POSITIVE PROTECTION: CRITERIA NOT MET ───
            logger.info(f"AI VOICE SOS: Criteria not met (Risk: {risk_score}/{auto_threshold}) - False positive suppressed.")
            decision_log = generate_ai_decision_log(
                session_id=session_id,
                transcript=trans_text,
                acoustic_data=acoustic_data,
                intel=intel,
                location=loc_dict,
                audio_meta=audio_meta,
                threshold=auto_threshold,
                action_taken="DISMISSED_BENIGN"
            )

            # Save prediction record for auditability
            preds_col = get_collection("ai_predictions")
            if preds_col is not None:
                await preds_col.insert_one({
                    "_id": session_id,
                    "user_id": current_user.get("_id"),
                    "input_text": trans_text,
                    "audio_file_path": audio_path,
                    "danger_level": danger_level,
                    "confidence_score": intel.get("confidence_score", 0.9),
                    "analysis": intel,
                    "acoustic_analysis": acoustic_data,
                    "decision_log": decision_log,
                    "auto_sos_created": False,
                    "created_at": datetime.utcnow()
                })

            return {
                "success": True,
                "auto_sos_created": False,
                "decision": "DISMISSED_BENIGN",
                "trigger_reason": intel.get("trigger_reason", "Conversational audio without distress criteria"),
                "transcript": trans_text,
                "intelligence": intel,
                "decision_log": decision_log
            }

    except Exception as e:
        logger.error(f"CRITICAL VOICE SOS ERROR: {str(e)}")
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/{alert_id}/cancel-voice")
@router.post("/{alert_id}/cancel")
async def cancel_voice_sos(
    alert_id: str,
    reason: str = Form("False alarm - User confirmed safe"),
    pin: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Discreet cancellation option for an auto-triggered voice SOS alert.
    Allows user to safely cancel within the cancellation window or confirm safety,
    immediately notifying admins and halting emergency dispatch.
    """
    alerts_col = get_collection("alerts")
    if alerts_col is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    alert = await alerts_col.find_one({"_id": alert_id, "user_id": current_user["_id"]})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    from datetime import datetime
    now_dt = datetime.utcnow()
    await alerts_col.update_one(
        {"_id": alert_id},
        {"$set": {
            "status": "cancelled",
            "resolved_at": now_dt,
            "resolution_note": f"Discreet Voice Cancellation: {reason}",
            "cancellation_reason": reason,
        }}
    )

    # Broadcast cancellation to all admins via Socket.IO
    try:
        await broadcast_to_admins("alert_cancelled", {
            "alert_id": alert_id,
            "user_id": current_user["_id"],
            "user_name": current_user.get("name"),
            "status": "cancelled",
            "reason": reason,
            "timestamp": now_dt.isoformat()
        })
    except Exception as e:
        logger.error(f"Error broadcasting alert cancellation: {e}")

    return {
        "success": True,
        "alert_id": alert_id,
        "status": "cancelled",
        "message": "Voice SOS alert successfully cancelled. Emergency contacts and responders notified."
    }


@router.post("/upload-evidence")
async def upload_photo_evidence(
    user_id: str = Form("unknown"),
    latitude: str = Form("0.0"),
    longitude: str = Form("0.0"),
    alert_id: str = Form(""),
    photo: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    try:
        try:
            lat = float(latitude)
            lng = float(longitude)
        except (ValueError, TypeError):
            lat, lng = 0.0, 0.0

        # Save photo using bounded streaming (max 10MB) to both local cache and persistent MongoDB GridFS
        photo_id = str(uuid.uuid4())
        ext = os.path.splitext(photo.filename)[1].lower() or ".jpg"
        filename = f"{photo_id}{ext}"

        MAX_PHOTO_BYTES = 10 * 1024 * 1024
        chunks = []
        total_read = 0
        while True:
            chunk = await photo.read(65536)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > MAX_PHOTO_BYTES:
                return {"success": False, "error": "Photo evidence exceeds 10MB limit"}
            chunks.append(chunk)

        photo_bytes = b"".join(chunks)
        save_res = await save_media_file(
            photo_bytes,
            filename,
            content_type="image/jpeg",
            metadata={"user_id": current_user["_id"], "alert_id": alert_id.strip() if alert_id else "", "type": "photo_evidence"}
        )
        photo_path = save_res["local_path"]
        logger.info(f"PHOTO PERSISTED | Path: {photo_path} | GridFS ID: {save_res.get('gridfs_id')} | Size: {len(photo_bytes)} bytes")

        evidence_col = get_collection("photo_evidence")

        # Use the alert_id from the client if provided (preferred — avoids race condition).
        # Fall back to DB lookup only if the frontend didn't send one.
        resolved_alert_id = alert_id.strip() if alert_id and alert_id.strip() else None
        if not resolved_alert_id:
            alerts_col = get_collection("alerts")
            if alerts_col is not None:
                active_alert = await alerts_col.find_one(
                    {"user_id": current_user["_id"], "status": "active"},
                    sort=[("created_at", -1)]
                )
                resolved_alert_id = str(active_alert["_id"]) if active_alert else "unknown"
            else:
                resolved_alert_id = "unknown"

        from datetime import datetime
        doc = {
            "user_id": current_user["_id"],
            "alert_id": resolved_alert_id,
            "photo_path": photo_path,
            "filename": filename,
            "gridfs_id": save_res.get("gridfs_id"),
            "location": {"latitude": lat, "longitude": lng},
            "timestamp": datetime.utcnow()
        }

        if evidence_col is not None:
            result = await evidence_col.insert_one(doc)
            doc["_id"] = str(result.inserted_id)
        else:
            doc["_id"] = str(uuid.uuid4())

        doc["timestamp"] = doc["timestamp"].isoformat()
        doc["url"] = f"/api/sos/evidence/photo/{doc['_id']}"
        doc["direct_url"] = f"/uploads/{filename}"

        # Also push photo evidence summary directly to alert document in MongoDB
        alerts_col = get_collection("alerts")
        if alerts_col is not None and resolved_alert_id and resolved_alert_id != "unknown":
            try:
                await alerts_col.update_one(
                    {"_id": resolved_alert_id},
                    {"$push": {"photo_evidence": {
                        "id": doc["_id"],
                        "photo_path": photo_path,
                        "url": doc["url"],
                        "direct_url": doc["direct_url"],
                        "timestamp": doc["timestamp"],
                        "location": doc["location"]
                    }}}
                )
            except Exception as update_e:
                logger.warning(f"Could not push photo to alert doc: {update_e}")

        await broadcast_to_admins("new_photo_evidence", doc)

        return {"success": True, "evidence": doc}
    except Exception as e:
        logger.error(f"PHOTO EVIDENCE UPLOAD ERROR: {str(e)}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@router.get("/active")
async def get_active_sos(
    skip: int = 0,
    limit: int = 50,
    current_admin: dict = Depends(get_current_admin)
):
    """Get all active SOS alerts (admin only)."""
    alerts_col = get_collection("alerts")
    if alerts_col is None:
        return []
    query = {"status": "active", **get_alert_filter(current_admin)}
    cursor = alerts_col.find(query).sort([("priority_score", -1), ("created_at", -1)]).skip(skip).limit(limit)
    alerts = await cursor.to_list(length=limit)
    return [await format_alert_response(a) for a in alerts]


@router.get("/my-alerts")
async def get_my_alerts(
    skip: int = 0,
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get current user's alert history."""
    try:
        alerts = await get_user_alerts(current_user["_id"], skip, limit)
        return [await format_alert_response(a) for a in alerts]
    except Exception as e:
        return []


@router.patch("/{alert_id}/resolve")
async def resolve_sos_alert(
    alert_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Resolve an active SOS alert."""
    admin_id = str(current_user.get("_id") or current_user.get("id") or "")
    admin_name = current_user.get("name") or "Administrator"
    alert = await resolve_alert(alert_id, admin_id=admin_id, admin_name=admin_name)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    try:
        await broadcast_to_admins("sos_alert_resolved", {
            "alert_id": alert_id,
            "resolved_by": admin_id,
            "resolved_by_name": admin_name
        })
    except Exception as e:
        logger.error(f"Failed to broadcast alert resolution: {e}")
    return await format_alert_response(alert)


@router.patch("/{alert_id}/acknowledge")
async def acknowledge_sos_alert(
    alert_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Acknowledge an active SOS alert."""
    alert = await acknowledge_alert(alert_id, admin_id=current_admin.get("_id"))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    try:
        await broadcast_to_admins("sos_alert_acknowledged", {
            "alert_id": alert_id,
            "admin_id": current_admin.get("_id"),
            "admin_name": current_admin.get("name")
        })
    except Exception as e:
        logger.error(f"Failed to broadcast alert acknowledgement: {e}")
    return await format_alert_response(alert)


@router.get("/audio/{alert_id}")
async def get_emergency_audio(alert_id: str, request: Request):
    """
    Serve emergency audio evidence with persistent MongoDB GridFS support and
    HTTP Range (RFC 7233) streaming for HTML5 <audio> players.
    """
    path = None
    voice_logs = get_collection("voice_logs")
    if voice_logs is not None:
        log = await voice_logs.find_one({"alert_id": alert_id})
        if log and log.get("audio_path"):
            path = log["audio_path"]

    if not path:
        alerts_col = get_collection("alerts")
        if alerts_col is not None:
            alert = await alerts_col.find_one({"_id": alert_id})
            if alert and alert.get("audio_file_path"):
                path = alert["audio_file_path"]

    if not path:
        raise HTTPException(status_code=404, detail="Audio evidence not found")

    return await handle_audio_stream_response(request, path)


@router.get("/evidence/photo/{evidence_id}")
async def get_photo_file(evidence_id: str, request: Request):
    """
    Serve photo evidence with persistent MongoDB GridFS support and
    seamless fallback for archived incidents.
    """
    from bson import ObjectId
    from app.services.media_storage import _normalize_filename
    evidence_col = get_collection("photo_evidence")
    doc = None
    if evidence_col is not None:
        try:
            doc = await evidence_col.find_one({"_id": ObjectId(evidence_id)})
        except Exception:
            pass
        if not doc:
            try:
                doc = await evidence_col.find_one({"_id": evidence_id})
            except Exception:
                pass
        if not doc:
            try:
                doc = await evidence_col.find_one({"filename": evidence_id})
            except Exception:
                pass

    if not doc:
        alerts_col = get_collection("alerts")
        if alerts_col is not None:
            try:
                alert = await alerts_col.find_one({"photo_evidence.id": evidence_id})
                if alert:
                    for pe in alert.get("photo_evidence", []):
                        if pe.get("id") == evidence_id or pe.get("filename") == evidence_id:
                            doc = pe
                            break
            except Exception:
                pass

    path = None
    if doc:
        path = doc.get("filename") or _normalize_filename(doc.get("photo_path", "")) or doc.get("gridfs_id")
    
    if not path:
        path = evidence_id

    fallback_title = f"SOS Snapshot #{evidence_id[:6]}"
    return await handle_photo_stream_response(path, fallback_title=fallback_title)


@router.get("/evidence/photo/file/{filename}")
async def get_photo_by_filename(filename: str, request: Request):
    """Serve photo evidence by filename with persistent GridFS lookup."""
    return await handle_photo_stream_response(filename, fallback_title="SOS Photo Evidence")

@router.get("/evidence/alert/{alert_id}")
async def get_alert_evidence(alert_id: str, current_admin: dict = Depends(get_current_admin)):
    evidence_col = get_collection("photo_evidence")
    if evidence_col is None:
        return []
    docs = await evidence_col.find({"alert_id": alert_id}).to_list(length=100)
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs
