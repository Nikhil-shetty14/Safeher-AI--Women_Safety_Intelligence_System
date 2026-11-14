from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.services.walk_service import WalkService
from app.core.security import get_current_user
from loguru import logger

router = APIRouter(prefix="/walk", tags=["Walk With Me"])

class WalkStartRequest(BaseModel):
    origin_lat: float = Field(..., ge=-90.0, le=90.0)
    origin_lng: float = Field(..., ge=-180.0, le=180.0)
    destination_lat: float = Field(..., ge=-90.0, le=90.0)
    destination_lng: float = Field(..., ge=-180.0, le=180.0)

@router.post("/start")
async def start_walk(request: WalkStartRequest, current_user: dict = Depends(get_current_user)):
    """Generate a walking route from origin to destination and return polyline."""
    try:
        route = await WalkService.get_route(
            request.origin_lat,
            request.origin_lng,
            request.destination_lat,
            request.destination_lng,
        )
        return {"success": True, "route": route}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(f"Error starting walk for user {current_user.get('_id')}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to calculate walking route")

@router.post("/recalc")
async def recalc_walk(request: WalkStartRequest, current_user: dict = Depends(get_current_user)):
    """Recalculate route from current location to original destination (same logic as start)."""
    return await start_walk(request, current_user)
