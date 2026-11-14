import uuid
import socketio
from loguru import logger
from typing import Dict, Set
from datetime import datetime

# Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1_000_000,
)

# Track connected users: {user_id: sid}
connected_users: Dict[str, str] = {}
# Track admin sockets: {sid: {"role": role, "division": div, "district": dist}}
admin_sockets: Dict[str, dict] = {}
# Track live locations: {user_id: location_data}
live_locations: Dict[str, dict] = {}

# Maximum tracked entities to prevent unbounded memory growth
_MAX_CONNECTED_USERS = 50_000
_MAX_LIVE_LOCATIONS = 50_000


@sio.event
async def connect(sid, environ, auth):
    logger.info(f"Socket connected: {sid}")
    try:
        await sio.emit("connection_ack", {"message": "Connected to SafeHer AI", "sid": sid}, to=sid)
    except Exception as e:
        logger.error(f"Failed to send connection_ack to {sid}: {e}")


@sio.event
async def disconnect(sid):
    # Remove from connected users
    user_id = None
    for uid, socket_id in list(connected_users.items()):
        if socket_id == sid:
            user_id = uid
            del connected_users[uid]
            break

    admin_sockets.pop(sid, None)
    if user_id:
        live_locations.pop(user_id, None)
        logger.info(f"User {user_id} disconnected")
    else:
        logger.info(f"Socket {sid} disconnected")


@sio.event
async def register_user(sid, data):
    """Register a user socket for targeted messaging."""
    if not isinstance(data, dict):
        logger.warning(f"Invalid register_user data from {sid}: expected dict, got {type(data).__name__}")
        return
    user_id = data.get("user_id")
    role = data.get("role", "user")

    # Validate role value
    valid_roles = {"user", "admin", "super_admin", "regional_admin", "district_admin"}
    if role not in valid_roles:
        logger.warning(f"Invalid role '{role}' from {sid}, defaulting to 'user'")
        role = "user"

    if role in ["admin", "super_admin", "regional_admin", "district_admin"]:
        admin_sockets[sid] = {
            "role": role,
            "division": data.get("division"),
            "district": data.get("district")
        }
        logger.info(f"Admin registered on socket: {sid} | Role: {role}")
        try:
            await sio.emit("registered", {"status": "ok", "role": role}, to=sid)
        except Exception as e:
            logger.error(f"Failed to emit registered to admin {sid}: {e}")
        return

    if user_id:
        if not isinstance(user_id, str) or len(user_id) > 200:
            logger.warning(f"Invalid user_id from {sid}: {repr(user_id)[:50]}")
            return
        # Evict oldest if at capacity to prevent memory leak
        if len(connected_users) >= _MAX_CONNECTED_USERS and user_id not in connected_users:
            logger.warning(f"Connected users at capacity ({_MAX_CONNECTED_USERS}), rejecting new registration")
            return
        connected_users[user_id] = sid
        try:
            await sio.emit("registered", {"status": "ok", "user_id": user_id}, to=sid)
        except Exception as e:
            logger.error(f"Failed to emit registered to user {user_id}: {e}")
        logger.info(f"User {user_id} registered (role={role})")


@sio.event
async def register(sid, data):
    """Alias for register_user supporting different client frameworks."""
    await register_user(sid, data)


@sio.event
async def location_update(sid, data):
    """Receive real-time location update from user."""
    if not isinstance(data, dict):
        return
    user_id = data.get("user_id")
    if not user_id or not isinstance(user_id, str):
        return

    # Validate latitude and longitude
    try:
        lat = float(data.get("latitude", 0))
        lng = float(data.get("longitude", 0))
    except (TypeError, ValueError):
        logger.warning(f"Invalid coordinates from user {user_id}")
        return

    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        logger.warning(f"Out-of-range coordinates from user {user_id}: lat={lat}, lng={lng}")
        return

    location = {
        "user_id": user_id,
        "latitude": lat,
        "longitude": lng,
        "accuracy": data.get("accuracy"),
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Prevent unbounded memory growth
    if len(live_locations) >= _MAX_LIVE_LOCATIONS and user_id not in live_locations:
        logger.warning(f"Live locations at capacity ({_MAX_LIVE_LOCATIONS}), skipping update for {user_id}")
        return
    live_locations[user_id] = location

    # Broadcast to all admins
    for admin_sid in list(admin_sockets.keys()):
        try:
            await sio.emit("user_location_update", location, to=admin_sid)
        except Exception as e:
            logger.error(f"Failed to emit location_update to admin {admin_sid}: {e}")


@sio.event
async def sos_triggered(sid, data):
    """Handle SOS trigger from mobile app."""
    if not isinstance(data, dict):
        logger.warning(f"Invalid sos_triggered data from {sid}")
        return
    user_id = data.get("user_id")
    location = data.get("location", {})
    user_name = data.get("user_name")
    user_phone = data.get("user_phone")

    if not user_id:
        logger.warning(f"SOS triggered from {sid} without user_id")

    if user_id and (not user_name or not user_phone):
        try:
            from app.core.database import get_collection
            users_col = get_collection("users")
            if users_col is not None:
                user_doc = await users_col.find_one({"_id": user_id})
                if user_doc:
                    user_name = user_name or user_doc.get("name")
                    user_phone = user_phone or user_doc.get("phone")
        except Exception as e:
            logger.error(f"Failed to fetch user details for SOS: {e}")

    alert_id = data.get("alert_id") or str(uuid.uuid4())
    alert_broadcast = {
        "type": "sos_alert",
        "alert_id": alert_id,
        "id": alert_id,
        "_id": alert_id,
        "user_id": user_id,
        "user_name": user_name or "Emergency User",
        "user_phone": user_phone or "N/A",
        "location": location,
        "timestamp": datetime.utcnow().isoformat(),
        "severity": data.get("severity", "high"),
        "trigger_type": data.get("trigger_type", "socket_trigger"),
        "message": data.get("message") or "Emergency SOS Alert Activated",
        "status": "active",
        "acknowledged": False,
    }

    logger.warning(f"SOS TRIGGERED: user={user_id}, alert_id={alert_id}, trigger={data.get('trigger_type', 'socket_trigger')}")

    if admin_sockets:
        # Broadcast to admins based on region
        alert_district = location.get("district") if isinstance(location, dict) else None
        alert_division = location.get("division") if isinstance(location, dict) else None
        
        for admin_sid, admin_data in list(admin_sockets.items()):
            try:
                role = admin_data.get("role")
                if role in ["super_admin", "admin"] or not alert_district:
                    await sio.emit("new_sos_alert", alert_broadcast, to=admin_sid)
                elif role == "regional_admin" and admin_data.get("division") == alert_division:
                    await sio.emit("new_sos_alert", alert_broadcast, to=admin_sid)
                elif role == "district_admin" and admin_data.get("district") == alert_district:
                    await sio.emit("new_sos_alert", alert_broadcast, to=admin_sid)
            except Exception as e:
                logger.error(f"Failed to emit SOS alert to admin {admin_sid}: {e}")
                
        logger.info(f"SOS broadcast processed for user {user_id}")
    else:
        logger.warning(f"SOS triggered by user {user_id}, but no admin(s) are currently connected to receive the broadcast.")


@sio.event
async def voice_stream(sid, data):
    """Handle voice stream data for real-time analysis."""
    if not isinstance(data, dict):
        return
    user_id = data.get("user_id")
    if not user_id:
        logger.warning(f"voice_stream from {sid} without user_id")
        return
    # Echo analysis trigger back to user
    try:
        await sio.emit("voice_received", {"status": "analyzing", "user_id": user_id}, to=sid)
    except Exception as e:
        logger.error(f"Failed to emit voice_received to {sid}: {e}")


async def emit_to_user(user_id: str, event: str, data: dict):
    """Emit event to a specific user."""
    sid = connected_users.get(user_id)
    if sid:
        try:
            await sio.emit(event, data, to=sid)
            return True
        except Exception as e:
            logger.error(f"Failed to emit '{event}' to user {user_id} (sid={sid}): {e}")
            return False
    return False


async def broadcast_to_admins(event: str, data: dict):
    """Broadcast event to admins, filtering by region if applicable."""
    alert_district = None
    alert_division = None
    
    # Try to extract location info from data
    if "location" in data and isinstance(data["location"], dict):
        alert_district = data["location"].get("district")
        alert_division = data["location"].get("division")
        
    for admin_sid, admin_data in list(admin_sockets.items()):
        try:
            role = admin_data.get("role")
            if role in ["super_admin", "admin"] or not alert_district:
                await sio.emit(event, data, to=admin_sid)
            elif role == "regional_admin" and admin_data.get("division") == alert_division:
                await sio.emit(event, data, to=admin_sid)
            elif role == "district_admin" and admin_data.get("district") == alert_district:
                await sio.emit(event, data, to=admin_sid)
        except Exception as e:
            logger.error(f"Failed to broadcast '{event}' to admin {admin_sid}: {e}")


async def broadcast_to_users(event: str, data: dict, user_ids: list = None):
    """Broadcast event to all users or specific user_ids."""
    if user_ids is not None:
        for user_id in user_ids:
            sid = connected_users.get(user_id)
            if sid:
                try:
                    await sio.emit(event, data, to=sid)
                except Exception as e:
                    logger.error(f"Failed to broadcast '{event}' to user {user_id}: {e}")
    else:
        for uid, sid in list(connected_users.items()):
            try:
                await sio.emit(event, data, to=sid)
            except Exception as e:
                logger.error(f"Failed to broadcast '{event}' to user {uid}: {e}")


def get_connected_count() -> dict:
    return {
        "total_users": len(connected_users),
        "admins": len(admin_sockets),
        "live_tracking": len(live_locations),
    }
