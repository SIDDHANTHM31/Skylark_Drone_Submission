from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class PilotStatus(str, Enum):
    AVAILABLE = "Available"
    ON_LEAVE = "On Leave"
    UNAVAILABLE = "Unavailable"
    ASSIGNED = "Assigned"


class DroneStatus(str, Enum):
    AVAILABLE = "Available"
    DEPLOYED = "Deployed"
    MAINTENANCE = "Maintenance"
    UNAVAILABLE = "Unavailable"


class SkillLevel(str, Enum):
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"
    EXPERT = "Expert"


class Pilot(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    skill_level: SkillLevel
    certifications: List[str] = Field(default_factory=list)
    drone_experience: List[str] = Field(default_factory=list)  # Drone models they can operate
    current_location: str
    current_assignment: Optional[str] = None
    assignment_start_date: Optional[date] = None
    assignment_end_date: Optional[date] = None
    status: PilotStatus = PilotStatus.AVAILABLE
    notes: Optional[str] = None

    class Config:
        use_enum_values = True


class Drone(BaseModel):
    id: str
    serial_number: str
    model: str
    capabilities: List[str] = Field(default_factory=list)  # e.g., thermal, mapping, inspection
    current_assignment: Optional[str] = None
    assignment_start_date: Optional[date] = None
    assignment_end_date: Optional[date] = None
    status: DroneStatus = DroneStatus.AVAILABLE
    current_location: str
    last_maintenance_date: Optional[date] = None
    next_maintenance_date: Optional[date] = None
    flight_hours: float = 0.0
    notes: Optional[str] = None

    class Config:
        use_enum_values = True


class Project(BaseModel):
    id: str
    name: str
    client: str
    location: str
    start_date: date
    end_date: date
    required_certifications: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    required_skill_level: SkillLevel
    assigned_pilots: List[str] = Field(default_factory=list)
    assigned_drones: List[str] = Field(default_factory=list)
    status: str = "Active"
    priority: str = "Normal"  # Normal, High, Urgent
    notes: Optional[str] = None

    class Config:
        use_enum_values = True


class Assignment(BaseModel):
    id: str
    project_id: str
    project_name: str
    pilot_id: Optional[str] = None
    pilot_name: Optional[str] = None
    drone_id: Optional[str] = None
    drone_serial: Optional[str] = None
    start_date: date
    end_date: date
    location: str
    status: str = "Active"


class ConflictType(str, Enum):
    DOUBLE_BOOKING_PILOT = "Double Booking (Pilot)"
    DOUBLE_BOOKING_DRONE = "Double Booking (Drone)"
    CERTIFICATION_MISMATCH = "Certification Mismatch"
    SKILL_MISMATCH = "Skill Level Mismatch"
    LOCATION_MISMATCH = "Location Mismatch"
    DRONE_MAINTENANCE = "Drone in Maintenance"
    CAPABILITY_MISMATCH = "Capability Mismatch"


class Conflict(BaseModel):
    id: str
    conflict_type: ConflictType
    severity: str  # Low, Medium, High, Critical
    description: str
    affected_pilot_id: Optional[str] = None
    affected_pilot_name: Optional[str] = None
    affected_drone_id: Optional[str] = None
    affected_drone_serial: Optional[str] = None
    affected_project_id: Optional[str] = None
    affected_project_name: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.now)
    resolved: bool = False
    resolution_notes: Optional[str] = None

    class Config:
        use_enum_values = True


class ChatMessage(BaseModel):
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    conflicts_detected: List[Conflict] = Field(default_factory=list)
    actions_taken: List[str] = Field(default_factory=list)


class UrgentReassignmentRequest(BaseModel):
    reason: str  # e.g., "pilot_sick", "drone_failure", "client_request", "emergency"
    original_pilot_id: Optional[str] = None
    original_drone_id: Optional[str] = None
    project_id: str
    urgency_level: str = "High"  # High, Critical
    preferred_location: Optional[str] = None
    notes: Optional[str] = None
