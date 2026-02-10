from fastapi import APIRouter, HTTPException
from typing import Optional, List
from ..models.schemas import Drone, DroneStatus
from ..services.google_sheets_service import get_sheets_service
from pydantic import BaseModel
from datetime import date

router = APIRouter(prefix="/api/drones", tags=["Drones"])


class DroneStatusUpdate(BaseModel):
    status: str
    assignment: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class MaintenanceFlag(BaseModel):
    issue_notes: str


@router.get("/", response_model=List[Drone])
async def get_all_drones():
    """Get all drones from the fleet."""
    service = get_sheets_service()
    return service.get_all_drones()


@router.get("/available", response_model=List[Drone])
async def get_available_drones(
    capability: Optional[str] = None,
    location: Optional[str] = None,
    model: Optional[str] = None
):
    """Get available drones with optional filters."""
    service = get_sheets_service()
    return service.get_available_drones(
        capability=capability,
        location=location,
        model=model
    )


@router.get("/{drone_id}", response_model=Drone)
async def get_drone(drone_id: str):
    """Get a specific drone by ID."""
    service = get_sheets_service()
    drone = service.get_drone_by_id(drone_id)
    if not drone:
        raise HTTPException(status_code=404, detail=f"Drone {drone_id} not found")
    return drone


@router.put("/{drone_id}/status")
async def update_drone_status(drone_id: str, update: DroneStatusUpdate):
    """Update a drone's status (syncs to Google Sheets)."""
    service = get_sheets_service()
    
    # Validate status
    valid_statuses = ["Available", "Deployed", "Maintenance", "Unavailable"]
    if update.status not in valid_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )
    
    success = service.update_drone_status(
        drone_id=drone_id,
        status=update.status,
        assignment=update.assignment,
        start_date=update.start_date,
        end_date=update.end_date
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update drone status")
    
    return {"message": f"Drone {drone_id} status updated to {update.status}", "success": True}


@router.post("/{drone_id}/maintenance")
async def flag_maintenance(drone_id: str, flag: MaintenanceFlag):
    """Flag a drone for maintenance (syncs to Google Sheets)."""
    service = get_sheets_service()
    
    success = service.flag_maintenance_issue(
        drone_id=drone_id,
        issue_notes=flag.issue_notes
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to flag drone for maintenance")
    
    return {
        "message": f"Drone {drone_id} flagged for maintenance",
        "issue_notes": flag.issue_notes,
        "success": True
    }
