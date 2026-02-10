from typing import List, Optional, Tuple
from datetime import date, datetime
import uuid
from ..models.schemas import (
    Pilot, Drone, Conflict, ConflictType, 
    PilotStatus, DroneStatus, SkillLevel
)
from .google_sheets_service import get_sheets_service
import logging

logger = logging.getLogger(__name__)


class ConflictDetectionService:
    """Service for detecting scheduling conflicts and mismatches."""
    
    def __init__(self):
        self.sheets_service = get_sheets_service()
        self.skill_order = ['Beginner', 'Intermediate', 'Advanced', 'Expert']

    def _generate_conflict_id(self) -> str:
        return f"CONF-{uuid.uuid4().hex[:8].upper()}"

    def _dates_overlap(self, start1: date, end1: date, start2: date, end2: date) -> bool:
        """Check if two date ranges overlap."""
        return start1 <= end2 and end1 >= start2

    def detect_all_conflicts(self) -> List[Conflict]:
        """Run all conflict detection checks and return list of conflicts."""
        conflicts = []
        
        pilots = self.sheets_service.get_all_pilots()
        drones = self.sheets_service.get_all_drones()
        projects = self.sheets_service.get_demo_projects()
        
        # Check for various conflict types
        conflicts.extend(self._detect_pilot_double_bookings(pilots, projects))
        conflicts.extend(self._detect_drone_double_bookings(drones, projects))
        conflicts.extend(self._detect_certification_mismatches(pilots, projects))
        conflicts.extend(self._detect_skill_mismatches(pilots, projects))
        conflicts.extend(self._detect_location_mismatches(pilots, drones, projects))
        conflicts.extend(self._detect_drone_maintenance_conflicts(drones, projects))
        conflicts.extend(self._detect_capability_mismatches(drones, projects))
        
        return conflicts

    def _detect_pilot_double_bookings(self, pilots: List[Pilot], projects: List[dict]) -> List[Conflict]:
        """Detect pilots assigned to overlapping projects."""
        conflicts = []
        
        for pilot in pilots:
            if not pilot.current_assignment or not pilot.assignment_start_date or not pilot.assignment_end_date:
                continue
            
            # Check against all other projects
            for project in projects:
                if project['name'] == pilot.current_assignment:
                    continue
                
                if pilot.id in project.get('assigned_pilots', []):
                    proj_start = datetime.strptime(project['start_date'], '%Y-%m-%d').date()
                    proj_end = datetime.strptime(project['end_date'], '%Y-%m-%d').date()
                    
                    if self._dates_overlap(
                        pilot.assignment_start_date, pilot.assignment_end_date,
                        proj_start, proj_end
                    ):
                        conflicts.append(Conflict(
                            id=self._generate_conflict_id(),
                            conflict_type=ConflictType.DOUBLE_BOOKING_PILOT,
                            severity="Critical",
                            description=f"Pilot {pilot.name} is double-booked: assigned to '{pilot.current_assignment}' "
                                       f"({pilot.assignment_start_date} to {pilot.assignment_end_date}) which overlaps with "
                                       f"'{project['name']}' ({project['start_date']} to {project['end_date']})",
                            affected_pilot_id=pilot.id,
                            affected_pilot_name=pilot.name,
                            affected_project_id=project['id'],
                            affected_project_name=project['name']
                        ))
        
        return conflicts

    def _detect_drone_double_bookings(self, drones: List[Drone], projects: List[dict]) -> List[Conflict]:
        """Detect drones assigned to overlapping projects."""
        conflicts = []
        
        for drone in drones:
            if not drone.current_assignment or not drone.assignment_start_date or not drone.assignment_end_date:
                continue
            
            for project in projects:
                if project['name'] == drone.current_assignment:
                    continue
                
                if drone.id in project.get('assigned_drones', []):
                    proj_start = datetime.strptime(project['start_date'], '%Y-%m-%d').date()
                    proj_end = datetime.strptime(project['end_date'], '%Y-%m-%d').date()
                    
                    if self._dates_overlap(
                        drone.assignment_start_date, drone.assignment_end_date,
                        proj_start, proj_end
                    ):
                        conflicts.append(Conflict(
                            id=self._generate_conflict_id(),
                            conflict_type=ConflictType.DOUBLE_BOOKING_DRONE,
                            severity="Critical",
                            description=f"Drone {drone.serial_number} ({drone.model}) is double-booked: "
                                       f"assigned to '{drone.current_assignment}' which overlaps with '{project['name']}'",
                            affected_drone_id=drone.id,
                            affected_drone_serial=drone.serial_number,
                            affected_project_id=project['id'],
                            affected_project_name=project['name']
                        ))
        
        return conflicts

    def _detect_certification_mismatches(self, pilots: List[Pilot], projects: List[dict]) -> List[Conflict]:
        """Detect pilots assigned to projects requiring certifications they lack."""
        conflicts = []
        
        for project in projects:
            required_certs = project.get('required_certifications', [])
            if not required_certs:
                continue
            
            for pilot_id in project.get('assigned_pilots', []):
                pilot = next((p for p in pilots if p.id == pilot_id), None)
                if not pilot:
                    continue
                
                missing_certs = [cert for cert in required_certs if cert not in pilot.certifications]
                
                if missing_certs:
                    conflicts.append(Conflict(
                        id=self._generate_conflict_id(),
                        conflict_type=ConflictType.CERTIFICATION_MISMATCH,
                        severity="High",
                        description=f"Pilot {pilot.name} is assigned to '{project['name']}' but lacks required "
                                   f"certifications: {', '.join(missing_certs)}",
                        affected_pilot_id=pilot.id,
                        affected_pilot_name=pilot.name,
                        affected_project_id=project['id'],
                        affected_project_name=project['name']
                    ))
        
        return conflicts

    def _detect_skill_mismatches(self, pilots: List[Pilot], projects: List[dict]) -> List[Conflict]:
        """Detect pilots assigned to projects requiring higher skill levels."""
        conflicts = []
        
        for project in projects:
            required_skill = project.get('required_skill_level')
            if not required_skill:
                continue
            
            required_idx = self.skill_order.index(required_skill) if required_skill in self.skill_order else 0
            
            for pilot_id in project.get('assigned_pilots', []):
                pilot = next((p for p in pilots if p.id == pilot_id), None)
                if not pilot:
                    continue
                
                pilot_idx = self.skill_order.index(pilot.skill_level) if pilot.skill_level in self.skill_order else 0
                
                if pilot_idx < required_idx:
                    conflicts.append(Conflict(
                        id=self._generate_conflict_id(),
                        conflict_type=ConflictType.SKILL_MISMATCH,
                        severity="Medium",
                        description=f"Pilot {pilot.name} (skill level: {pilot.skill_level}) is assigned to "
                                   f"'{project['name']}' which requires {required_skill} level",
                        affected_pilot_id=pilot.id,
                        affected_pilot_name=pilot.name,
                        affected_project_id=project['id'],
                        affected_project_name=project['name']
                    ))
        
        return conflicts

    def _detect_location_mismatches(self, pilots: List[Pilot], drones: List[Drone], 
                                    projects: List[dict]) -> List[Conflict]:
        """Detect pilot-drone location mismatches for assigned projects."""
        conflicts = []
        
        for project in projects:
            project_location = project.get('location', '').lower()
            assigned_pilots = project.get('assigned_pilots', [])
            assigned_drones = project.get('assigned_drones', [])
            
            # Check pilot locations
            for pilot_id in assigned_pilots:
                pilot = next((p for p in pilots if p.id == pilot_id), None)
                if pilot and pilot.current_location.lower() != project_location:
                    conflicts.append(Conflict(
                        id=self._generate_conflict_id(),
                        conflict_type=ConflictType.LOCATION_MISMATCH,
                        severity="Medium",
                        description=f"Pilot {pilot.name} is in {pilot.current_location} but assigned to "
                                   f"'{project['name']}' in {project['location']}",
                        affected_pilot_id=pilot.id,
                        affected_pilot_name=pilot.name,
                        affected_project_id=project['id'],
                        affected_project_name=project['name']
                    ))
            
            # Check drone locations
            for drone_id in assigned_drones:
                drone = next((d for d in drones if d.id == drone_id), None)
                if drone and drone.current_location.lower() != project_location:
                    conflicts.append(Conflict(
                        id=self._generate_conflict_id(),
                        conflict_type=ConflictType.LOCATION_MISMATCH,
                        severity="Medium",
                        description=f"Drone {drone.serial_number} is in {drone.current_location} but assigned to "
                                   f"'{project['name']}' in {project['location']}",
                        affected_drone_id=drone.id,
                        affected_drone_serial=drone.serial_number,
                        affected_project_id=project['id'],
                        affected_project_name=project['name']
                    ))
            
            # Check pilot-drone location mismatch within same project
            for pilot_id in assigned_pilots:
                pilot = next((p for p in pilots if p.id == pilot_id), None)
                if not pilot:
                    continue
                
                for drone_id in assigned_drones:
                    drone = next((d for d in drones if d.id == drone_id), None)
                    if drone and pilot.current_location.lower() != drone.current_location.lower():
                        conflicts.append(Conflict(
                            id=self._generate_conflict_id(),
                            conflict_type=ConflictType.LOCATION_MISMATCH,
                            severity="High",
                            description=f"Location mismatch on '{project['name']}': Pilot {pilot.name} is in "
                                       f"{pilot.current_location} but drone {drone.serial_number} is in {drone.current_location}",
                            affected_pilot_id=pilot.id,
                            affected_pilot_name=pilot.name,
                            affected_drone_id=drone.id,
                            affected_drone_serial=drone.serial_number,
                            affected_project_id=project['id'],
                            affected_project_name=project['name']
                        ))
        
        return conflicts

    def _detect_drone_maintenance_conflicts(self, drones: List[Drone], projects: List[dict]) -> List[Conflict]:
        """Detect drones in maintenance assigned to active projects."""
        conflicts = []
        
        for project in projects:
            for drone_id in project.get('assigned_drones', []):
                drone = next((d for d in drones if d.id == drone_id), None)
                if not drone:
                    continue
                
                if drone.status == DroneStatus.MAINTENANCE or drone.status == 'Maintenance':
                    conflicts.append(Conflict(
                        id=self._generate_conflict_id(),
                        conflict_type=ConflictType.DRONE_MAINTENANCE,
                        severity="Critical",
                        description=f"Drone {drone.serial_number} ({drone.model}) is in MAINTENANCE but assigned to "
                                   f"'{project['name']}'. Notes: {drone.notes or 'No details'}",
                        affected_drone_id=drone.id,
                        affected_drone_serial=drone.serial_number,
                        affected_project_id=project['id'],
                        affected_project_name=project['name']
                    ))
                
                # Check if maintenance is scheduled during project dates
                if drone.next_maintenance_date:
                    proj_start = datetime.strptime(project['start_date'], '%Y-%m-%d').date()
                    proj_end = datetime.strptime(project['end_date'], '%Y-%m-%d').date()
                    
                    if proj_start <= drone.next_maintenance_date <= proj_end:
                        conflicts.append(Conflict(
                            id=self._generate_conflict_id(),
                            conflict_type=ConflictType.DRONE_MAINTENANCE,
                            severity="Medium",
                            description=f"Drone {drone.serial_number} has scheduled maintenance on "
                                       f"{drone.next_maintenance_date} during '{project['name']}' "
                                       f"({project['start_date']} to {project['end_date']})",
                            affected_drone_id=drone.id,
                            affected_drone_serial=drone.serial_number,
                            affected_project_id=project['id'],
                            affected_project_name=project['name']
                        ))
        
        return conflicts

    def _detect_capability_mismatches(self, drones: List[Drone], projects: List[dict]) -> List[Conflict]:
        """Detect drones assigned to projects requiring capabilities they lack."""
        conflicts = []
        
        for project in projects:
            required_caps = project.get('required_capabilities', [])
            if not required_caps:
                continue
            
            for drone_id in project.get('assigned_drones', []):
                drone = next((d for d in drones if d.id == drone_id), None)
                if not drone:
                    continue
                
                missing_caps = [cap for cap in required_caps if cap not in drone.capabilities]
                
                if missing_caps:
                    conflicts.append(Conflict(
                        id=self._generate_conflict_id(),
                        conflict_type=ConflictType.CAPABILITY_MISMATCH,
                        severity="High",
                        description=f"Drone {drone.serial_number} ({drone.model}) lacks required capabilities "
                                   f"for '{project['name']}': {', '.join(missing_caps)}",
                        affected_drone_id=drone.id,
                        affected_drone_serial=drone.serial_number,
                        affected_project_id=project['id'],
                        affected_project_name=project['name']
                    ))
        
        return conflicts

    def check_assignment_conflicts(self, pilot_id: Optional[str], drone_id: Optional[str],
                                   project_id: str, start_date: date, end_date: date,
                                   required_certs: List[str], required_caps: List[str],
                                   required_skill: str, location: str) -> List[Conflict]:
        """Check for conflicts before making a new assignment."""
        conflicts = []
        
        if pilot_id:
            pilot = self.sheets_service.get_pilot_by_id(pilot_id)
            if pilot:
                # Check availability
                if pilot.status == PilotStatus.ON_LEAVE:
                    conflicts.append(Conflict(
                        id=self._generate_conflict_id(),
                        conflict_type=ConflictType.DOUBLE_BOOKING_PILOT,
                        severity="Critical",
                        description=f"Pilot {pilot.name} is currently on leave",
                        affected_pilot_id=pilot.id,
                        affected_pilot_name=pilot.name,
                        affected_project_id=project_id
                    ))
                
                # Check double booking
                if pilot.assignment_start_date and pilot.assignment_end_date:
                    if self._dates_overlap(pilot.assignment_start_date, pilot.assignment_end_date, 
                                          start_date, end_date):
                        conflicts.append(Conflict(
                            id=self._generate_conflict_id(),
                            conflict_type=ConflictType.DOUBLE_BOOKING_PILOT,
                            severity="Critical",
                            description=f"Pilot {pilot.name} is already assigned to '{pilot.current_assignment}' "
                                       f"during this period",
                            affected_pilot_id=pilot.id,
                            affected_pilot_name=pilot.name,
                            affected_project_id=project_id
                        ))
                
                # Check certifications
                missing_certs = [cert for cert in required_certs if cert not in pilot.certifications]
                if missing_certs:
                    conflicts.append(Conflict(
                        id=self._generate_conflict_id(),
                        conflict_type=ConflictType.CERTIFICATION_MISMATCH,
                        severity="High",
                        description=f"Pilot {pilot.name} lacks certifications: {', '.join(missing_certs)}",
                        affected_pilot_id=pilot.id,
                        affected_pilot_name=pilot.name,
                        affected_project_id=project_id
                    ))
                
                # Check skill level
                if required_skill in self.skill_order:
                    required_idx = self.skill_order.index(required_skill)
                    pilot_idx = self.skill_order.index(pilot.skill_level) if pilot.skill_level in self.skill_order else 0
                    if pilot_idx < required_idx:
                        conflicts.append(Conflict(
                            id=self._generate_conflict_id(),
                            conflict_type=ConflictType.SKILL_MISMATCH,
                            severity="Medium",
                            description=f"Pilot {pilot.name} skill level ({pilot.skill_level}) is below required ({required_skill})",
                            affected_pilot_id=pilot.id,
                            affected_pilot_name=pilot.name,
                            affected_project_id=project_id
                        ))
                
                # Check location
                if location and pilot.current_location.lower() != location.lower():
                    conflicts.append(Conflict(
                        id=self._generate_conflict_id(),
                        conflict_type=ConflictType.LOCATION_MISMATCH,
                        severity="Medium",
                        description=f"Pilot {pilot.name} is in {pilot.current_location}, project is in {location}",
                        affected_pilot_id=pilot.id,
                        affected_pilot_name=pilot.name,
                        affected_project_id=project_id
                    ))
        
        if drone_id:
            drone = self.sheets_service.get_drone_by_id(drone_id)
            if drone:
                # Check maintenance status
                if drone.status == DroneStatus.MAINTENANCE or drone.status == 'Maintenance':
                    conflicts.append(Conflict(
                        id=self._generate_conflict_id(),
                        conflict_type=ConflictType.DRONE_MAINTENANCE,
                        severity="Critical",
                        description=f"Drone {drone.serial_number} is in maintenance",
                        affected_drone_id=drone.id,
                        affected_drone_serial=drone.serial_number,
                        affected_project_id=project_id
                    ))
                
                # Check double booking
                if drone.assignment_start_date and drone.assignment_end_date:
                    if self._dates_overlap(drone.assignment_start_date, drone.assignment_end_date,
                                          start_date, end_date):
                        conflicts.append(Conflict(
                            id=self._generate_conflict_id(),
                            conflict_type=ConflictType.DOUBLE_BOOKING_DRONE,
                            severity="Critical",
                            description=f"Drone {drone.serial_number} is already assigned to '{drone.current_assignment}'",
                            affected_drone_id=drone.id,
                            affected_drone_serial=drone.serial_number,
                            affected_project_id=project_id
                        ))
                
                # Check capabilities
                missing_caps = [cap for cap in required_caps if cap not in drone.capabilities]
                if missing_caps:
                    conflicts.append(Conflict(
                        id=self._generate_conflict_id(),
                        conflict_type=ConflictType.CAPABILITY_MISMATCH,
                        severity="High",
                        description=f"Drone {drone.serial_number} lacks capabilities: {', '.join(missing_caps)}",
                        affected_drone_id=drone.id,
                        affected_drone_serial=drone.serial_number,
                        affected_project_id=project_id
                    ))
                
                # Check location
                if location and drone.current_location.lower() != location.lower():
                    conflicts.append(Conflict(
                        id=self._generate_conflict_id(),
                        conflict_type=ConflictType.LOCATION_MISMATCH,
                        severity="Medium",
                        description=f"Drone {drone.serial_number} is in {drone.current_location}, project is in {location}",
                        affected_drone_id=drone.id,
                        affected_drone_serial=drone.serial_number,
                        affected_project_id=project_id
                    ))
        
        return conflicts


# Singleton instance
_conflict_service = None

def get_conflict_service() -> ConflictDetectionService:
    global _conflict_service
    if _conflict_service is None:
        _conflict_service = ConflictDetectionService()
    return _conflict_service
