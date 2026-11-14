from app.core.database import get_collection
from datetime import datetime
from loguru import logger
import uuid

async def log_activity(user_id: str, action: str, details: dict = None):
    """Log a user activity to the database."""
    collection = get_collection("activity_logs")
    if collection is None:
        return
    
    doc = {
        "_id": str(uuid.uuid4()),
        "user_id": user_id,
        "action": action,
        "details": details or {},
        "timestamp": datetime.utcnow()
    }
    try:
        await collection.insert_one(doc)
    except Exception as e:
        logger.error(f"Failed to log activity '{action}' for user {user_id}: {e}")
