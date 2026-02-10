from fastapi import APIRouter, HTTPException
from typing import Optional, List
from ..models.schemas import Pilot, PilotStatus
from ..services.google_sheets_service import get_sheets_service
from pydantic import BaseModel
from datetime import date

router = APIRouter(prefix="/api/pilots", tags=["Pilots"])


class PilotStatusUpdate(BaseModel):
    status: str
    assignment: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


@router.get("/", response_model=List[Pilot])
async def get_all_pilots():
    """Get all pilots from the roster."""
    service = get_sheets_service()
    return service.get_all_pilots()


@router.get("/available", response_model=List[Pilot])
async def get_available_pilots(
    skill_level: Optional[str] = None,
    certification: Optional[str] = None,
    location: Optional[str] = None,
    drone_model: Optional[str] = None
):
    """Get available pilots with optional filters."""
    service = get_sheets_service()
    return service.get_available_pilots(
        skill_level=skill_level,
        certification=certification,
        location=location,
        drone_model=drone_model
    )


@router.get("/{pilot_id}", response_model=Pilot)
async def get_pilot(pilot_id: str):
    """Get a specific pilot by ID."""
    service = get_sheets_service()
    pilot = service.get_pilot_by_id(pilot_id)
    if not pilot:
        raise HTTPException(status_code=404, detail=f"Pilot {pilot_id} not found")
    return pilot


@router.put("/{pilot_id}/status")
async def update_pilot_status(pilot_id: str, update: PilotStatusUpdate):
    """Update a pilot's status (syncs to Google Sheets)."""
    service = get_sheets_service()
    
    # Validate status
    valid_statuses = ["Available", "On Leave", "Unavailable", "Assigned"]
    if update.status not in valid_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )
    
    success = service.update_pilot_status(
        pilot_id=pilot_id,
        status=update.status,
        assignment=update.assignment,
        start_date=update.start_date,
        end_date=update.end_date
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update pilot status")
    
    return {"message": f"Pilot {pilot_id} status updated to {update.status}", "success": True}
