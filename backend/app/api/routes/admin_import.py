from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any
from app.core.security import get_current_admin, log_admin_action, get_password_hash
from app.core.database import get_collection
from loguru import logger
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/admin/import", tags=["Admin Import"])

@router.post("/users")
async def import_users(
    users: List[Dict[str, Any]] = Body(...),
    current_admin: dict = Depends(get_current_admin)
):
    """Import users from Excel JSON data"""
    if current_admin.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Unauthorized to import users")
        
    users_col = get_collection("users")
    if users_col is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
        
    inserted_count = 0
    errors = []
    
    for row in users:
        try:
            # Validate required fields
            email = row.get("email")
            name = row.get("name")
            phone = row.get("phone")
            
            if not email or not name:
                errors.append(f"Row missing email or name: {row}")
                continue
                
            # Check if exists
            existing = await users_col.find_one({"email": email})
            if existing:
                errors.append(f"User with email {email} already exists")
                continue
                
            now = datetime.utcnow()
            user_doc = {
                "_id": str(uuid.uuid4()),
                "name": name,
                "email": email,
                "phone": phone or "",
                "role": "user",
                "is_active": True,
                "requires_password_change": True,
                "hashed_password": get_password_hash("SafeHer@123"),  # Temporary initial password
                "created_at": now,
                "updated_at": now
            }
            await users_col.insert_one(user_doc)
            inserted_count += 1
        except Exception as e:
            logger.error(f"Error processing row {row.get('email', 'unknown')}: {e}")
            errors.append(f"Error processing row {row.get('email', 'unknown')}: {str(e)}")
            
    await log_admin_action(
        current_admin["_id"],
        current_admin.get("email", ""),
        "import_users",
        details=f"Imported {inserted_count} users with {len(errors)} errors"
    )
            
    return {
        "success": True,
        "message": f"Successfully imported {inserted_count} users.",
        "inserted_count": inserted_count,
        "errors": errors
    }
