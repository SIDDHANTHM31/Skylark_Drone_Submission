import os
import csv
from typing import List, Optional
from datetime import date, datetime
import logging

# Google Sheets imports
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

from ..models.schemas import Pilot, Drone, PilotStatus, DroneStatus, SkillLevel

logger = logging.getLogger(__name__)

# CSV file paths (fallback for demo mode)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PILOT_CSV = os.path.join(BASE_DIR, 'pilot_roster.csv')
DRONE_CSV = os.path.join(BASE_DIR, 'drone_fleet.csv')
MISSIONS_CSV = os.path.join(BASE_DIR, 'missions.csv')


class GoogleSheetsService:
    """
    Service for managing pilot and drone data with Google Sheets as primary data source.
    
    Data Flow:
    - READ: Always fetches fresh data from Google Sheets (or CSV fallback)
    - WRITE: Updates Google Sheets directly, changes are immediately visible
    - 2-WAY SYNC: External changes in Google Sheets are reflected in the app
    """
    
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self.pilot_sheet = None
        self.drone_sheet = None
        self.missions_sheet = None
        self._use_google_sheets = False
        
        # Try to connect to Google Sheets
        if GSPREAD_AVAILABLE:
            self._init_google_sheets()
        
        if not self._use_google_sheets:
            logger.info("Running in DEMO MODE - using local CSV files")
            logger.info("To enable Google Sheets sync, run: python setup_google_sheets.py")

    def _init_google_sheets(self):
        """Initialize Google Sheets connection."""
        try:
            creds_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
            sheet_id = os.getenv('GOOGLE_SHEET_ID')
            
            creds_path = os.path.join(BASE_DIR, creds_file)
            
            if not os.path.exists(creds_path):
                logger.info(f"Google Sheets credentials not found at {creds_path}")
                return
            
            if not sheet_id:
                logger.info("GOOGLE_SHEET_ID not set in environment")
                return
            
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
            self.client = gspread.authorize(creds)
            
            # Open the spreadsheet
            self.spreadsheet = self.client.open_by_key(sheet_id)
            
            # Get worksheet references
            pilot_tab = os.getenv('PILOT_ROSTER_TAB', 'Pilot Roster')
            drone_tab = os.getenv('DRONE_FLEET_TAB', 'Drone Fleet')
            missions_tab = os.getenv('MISSIONS_TAB', 'Missions')
            
            self.pilot_sheet = self.spreadsheet.worksheet(pilot_tab)
            self.drone_sheet = self.spreadsheet.worksheet(drone_tab)
            
            try:
                self.missions_sheet = self.spreadsheet.worksheet(missions_tab)
            except gspread.WorksheetNotFound:
                logger.warning(f"Missions sheet '{missions_tab}' not found")
                self.missions_sheet = None
            
            self._use_google_sheets = True
            logger.info(f"✅ Connected to Google Sheets: {self.spreadsheet.title}")
            logger.info(f"   Spreadsheet URL: https://docs.google.com/spreadsheets/d/{sheet_id}")
            
        except Exception as e:
            logger.warning(f"Failed to connect to Google Sheets: {e}")
            logger.info("Falling back to CSV files for demo mode")
            self._use_google_sheets = False

    # =====================
    # PILOT OPERATIONS
    # =====================
    
    def get_all_pilots(self) -> List[Pilot]:
        """Get all pilots - reads directly from Google Sheets for real-time data."""
        if self._use_google_sheets:
            return self._get_pilots_from_sheets()
        return self._get_pilots_from_csv()

    def _get_pilots_from_sheets(self) -> List[Pilot]:
        """Fetch pilots directly from Google Sheets."""
        try:
            records = self.pilot_sheet.get_all_records()
            pilots = []
            
            for row in records:
                pilot = self._parse_pilot_row(row)
                if pilot:
                    pilots.append(pilot)
            
            logger.debug(f"Fetched {len(pilots)} pilots from Google Sheets")
            return pilots
            
        except Exception as e:
            logger.error(f"Error fetching pilots from Google Sheets: {e}")
            return self._get_pilots_from_csv()

    def _get_pilots_from_csv(self) -> List[Pilot]:
        """Load pilot data from CSV file (fallback/demo mode)."""
        pilots = []
        try:
            with open(PILOT_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pilot = self._parse_pilot_row(row)
                    if pilot:
                        pilots.append(pilot)
            logger.debug(f"Loaded {len(pilots)} pilots from CSV")
        except FileNotFoundError:
            logger.warning(f"Pilot CSV not found at {PILOT_CSV}")
        except Exception as e:
            logger.error(f"Error loading pilots from CSV: {e}")
        return pilots

    def _parse_pilot_row(self, row: dict) -> Optional[Pilot]:
        """Parse a row (from Sheets or CSV) into a Pilot object."""
        try:
            # Handle different column name formats
            pilot_id = row.get('pilot_id') or row.get('Pilot ID') or row.get('ID', '')
            name = row.get('name') or row.get('Name', '')
            
            if not pilot_id or not name:
                return None
            
            # Parse skills
            skills_str = row.get('skills') or row.get('Skills', '')
            skills = [s.strip() for s in skills_str.split(',') if s.strip()]
            
            # Parse certifications
            certs_str = row.get('certifications') or row.get('Certifications', '')
            certs = [c.strip() for c in certs_str.split(',') if c.strip()]
            
            # Determine skill level
            if len(skills) >= 3:
                skill_level = SkillLevel.EXPERT
            elif len(skills) >= 2:
                skill_level = SkillLevel.ADVANCED
            elif len(skills) >= 1:
                skill_level = SkillLevel.INTERMEDIATE
            else:
                skill_level = SkillLevel.BEGINNER
            
            # Parse status
            status_str = (row.get('status') or row.get('Status', 'Available')).strip()
            status_map = {
                'Available': PilotStatus.AVAILABLE,
                'Assigned': PilotStatus.ASSIGNED,
                'On Leave': PilotStatus.ON_LEAVE,
                'Unavailable': PilotStatus.UNAVAILABLE
            }
            status = status_map.get(status_str, PilotStatus.AVAILABLE)
            
            # Parse assignment
            assignment = (row.get('current_assignment') or row.get('Current Assignment', '')).strip()
            if assignment in ['–', '-', '']:
                assignment = None
            
            # Parse location
            location = (row.get('location') or row.get('Location', '')).strip()
            
            # Parse available_from date
            available_from_str = row.get('available_from') or row.get('Available From', '')
            available_from = self._parse_date(available_from_str)
            
            return Pilot(
                id=pilot_id.strip(),
                name=name.strip(),
                email=f"{name.lower().replace(' ', '.')}@skylark.com",
                phone=None,
                skill_level=skill_level,
                certifications=certs,
                drone_experience=skills,
                current_location=location,
                current_assignment=assignment,
                assignment_start_date=available_from if status == PilotStatus.ASSIGNED else None,
                assignment_end_date=None,
                status=status,
                notes=f"Skills: {', '.join(skills)}" if skills else ""
            )
        except Exception as e:
            logger.error(f"Error parsing pilot row: {e}")
            return None

    def get_pilot_by_id(self, pilot_id: str) -> Optional[Pilot]:
        """Get a specific pilot by ID."""
        pilots = self.get_all_pilots()
        return next((p for p in pilots if p.id == pilot_id), None)

    def get_available_pilots(self, skill_level: Optional[str] = None,
                            certification: Optional[str] = None,
                            location: Optional[str] = None,
                            drone_model: Optional[str] = None) -> List[Pilot]:
        """Get available pilots with optional filters."""
        pilots = [p for p in self.get_all_pilots() if p.status == PilotStatus.AVAILABLE]
        
        if skill_level:
            skill_order = ['Beginner', 'Intermediate', 'Advanced', 'Expert']
            min_idx = skill_order.index(skill_level) if skill_level in skill_order else 0
            pilots = [p for p in pilots if skill_order.index(p.skill_level) >= min_idx]
        
        if certification:
            pilots = [p for p in pilots if any(certification.lower() in c.lower() for c in p.certifications)]
        
        if location:
            pilots = [p for p in pilots if p.current_location.lower() == location.lower()]
        
        if drone_model:
            pilots = [p for p in pilots if any(drone_model.lower() in exp.lower() for exp in p.drone_experience)]
        
        return pilots

    def update_pilot_status(self, pilot_id: str, status: str, 
                           assignment: Optional[str] = None,
                           start_date: Optional[date] = None,
                           end_date: Optional[date] = None) -> bool:
        """
        Update a pilot's status - writes directly to Google Sheets.
        This is the 2-way sync: changes in the app update the spreadsheet.
        """
        if self._use_google_sheets:
            return self._update_pilot_in_sheets(pilot_id, status, assignment)
        return self._update_pilot_in_csv(pilot_id, status, assignment)

    def _update_pilot_in_sheets(self, pilot_id: str, status: str, assignment: Optional[str] = None) -> bool:
        """Update pilot directly in Google Sheets."""
        try:
            # Find the pilot row
            cell = self.pilot_sheet.find(pilot_id)
            if not cell:
                logger.error(f"Pilot {pilot_id} not found in Google Sheets")
                return False
            
            row = cell.row
            
            # Get header row to find column indices
            headers = self.pilot_sheet.row_values(1)
            
            # Find column indices (case-insensitive)
            status_col = None
            assignment_col = None
            
            for idx, header in enumerate(headers, 1):
                header_lower = header.lower()
                if header_lower == 'status':
                    status_col = idx
                elif header_lower in ['current_assignment', 'current assignment']:
                    assignment_col = idx
            
            # Update status
            if status_col:
                self.pilot_sheet.update_cell(row, status_col, status)
                logger.info(f"Updated pilot {pilot_id} status to '{status}' in Google Sheets")
            
            # Update assignment
            if assignment_col:
                assignment_value = assignment if assignment else '–'
                self.pilot_sheet.update_cell(row, assignment_col, assignment_value)
                logger.info(f"Updated pilot {pilot_id} assignment to '{assignment_value}' in Google Sheets")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating pilot in Google Sheets: {e}")
            return False

    def _update_pilot_in_csv(self, pilot_id: str, status: str, assignment: Optional[str] = None) -> bool:
        """Update pilot in CSV file (demo mode)."""
        try:
            # Read all rows
            rows = []
            with open(PILOT_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    if row.get('pilot_id') == pilot_id:
                        row['status'] = status
                        row['current_assignment'] = assignment if assignment else '–'
                    rows.append(row)
            
            # Write back
            with open(PILOT_CSV, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            logger.info(f"Updated pilot {pilot_id} in CSV file")
            return True
            
        except Exception as e:
            logger.error(f"Error updating pilot in CSV: {e}")
            return False

    # =====================
    # DRONE OPERATIONS
    # =====================
    
    def get_all_drones(self) -> List[Drone]:
        """Get all drones - reads directly from Google Sheets for real-time data."""
        if self._use_google_sheets:
            return self._get_drones_from_sheets()
        return self._get_drones_from_csv()

    def _get_drones_from_sheets(self) -> List[Drone]:
        """Fetch drones directly from Google Sheets."""
        try:
            records = self.drone_sheet.get_all_records()
            drones = []
            
            for row in records:
                drone = self._parse_drone_row(row)
                if drone:
                    drones.append(drone)
            
            logger.debug(f"Fetched {len(drones)} drones from Google Sheets")
            return drones
            
        except Exception as e:
            logger.error(f"Error fetching drones from Google Sheets: {e}")
            return self._get_drones_from_csv()

    def _get_drones_from_csv(self) -> List[Drone]:
        """Load drone data from CSV file (fallback/demo mode)."""
        drones = []
        try:
            with open(DRONE_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    drone = self._parse_drone_row(row)
                    if drone:
                        drones.append(drone)
            logger.debug(f"Loaded {len(drones)} drones from CSV")
        except FileNotFoundError:
            logger.warning(f"Drone CSV not found at {DRONE_CSV}")
        except Exception as e:
            logger.error(f"Error loading drones from CSV: {e}")
        return drones

    def _parse_drone_row(self, row: dict) -> Optional[Drone]:
        """Parse a row (from Sheets or CSV) into a Drone object."""
        try:
            # Handle different column name formats
            drone_id = row.get('drone_id') or row.get('Drone ID') or row.get('ID', '')
            model = row.get('model') or row.get('Model', '')
            
            if not drone_id or not model:
                return None
            
            # Parse capabilities
            caps_str = row.get('capabilities') or row.get('Capabilities', '')
            capabilities = [c.strip() for c in caps_str.split(',') if c.strip()]
            
            # Parse status
            status_str = (row.get('status') or row.get('Status', 'Available')).strip()
            status_map = {
                'Available': DroneStatus.AVAILABLE,
                'Deployed': DroneStatus.DEPLOYED,
                'Maintenance': DroneStatus.MAINTENANCE,
                'Unavailable': DroneStatus.UNAVAILABLE
            }
            status = status_map.get(status_str, DroneStatus.AVAILABLE)
            
            # Parse assignment
            assignment = (row.get('current_assignment') or row.get('Current Assignment', '')).strip()
            if assignment in ['–', '-', '']:
                assignment = None
            
            # Parse location
            location = (row.get('location') or row.get('Location', '')).strip()
            
            # Parse maintenance date
            maint_str = row.get('maintenance_due') or row.get('Maintenance Due', '')
            maintenance_due = self._parse_date(maint_str)
            
            return Drone(
                id=drone_id.strip(),
                serial_number=f"{model.replace(' ', '-')}-{drone_id}",
                model=model.strip(),
                capabilities=capabilities,
                current_assignment=assignment,
                assignment_start_date=None,
                assignment_end_date=None,
                status=status,
                current_location=location,
                last_maintenance_date=None,
                next_maintenance_date=maintenance_due,
                flight_hours=0.0,
                notes=f"Capabilities: {', '.join(capabilities)}" if capabilities else ""
            )
        except Exception as e:
            logger.error(f"Error parsing drone row: {e}")
            return None

    def get_drone_by_id(self, drone_id: str) -> Optional[Drone]:
        """Get a specific drone by ID."""
        drones = self.get_all_drones()
        return next((d for d in drones if d.id == drone_id), None)

    def get_available_drones(self, capability: Optional[str] = None,
                            location: Optional[str] = None,
                            model: Optional[str] = None) -> List[Drone]:
        """Get available drones with optional filters."""
        drones = [d for d in self.get_all_drones() if d.status == DroneStatus.AVAILABLE]
        
        if capability:
            drones = [d for d in drones if any(capability.lower() in c.lower() for c in d.capabilities)]
        
        if location:
            drones = [d for d in drones if d.current_location.lower() == location.lower()]
        
        if model:
            drones = [d for d in drones if model.lower() in d.model.lower()]
        
        return drones

    def update_drone_status(self, drone_id: str, status: str,
                           assignment: Optional[str] = None,
                           start_date: Optional[date] = None,
                           end_date: Optional[date] = None) -> bool:
        """
        Update a drone's status - writes directly to Google Sheets.
        This is the 2-way sync: changes in the app update the spreadsheet.
        """
        if self._use_google_sheets:
            return self._update_drone_in_sheets(drone_id, status, assignment)
        return self._update_drone_in_csv(drone_id, status, assignment)

    def _update_drone_in_sheets(self, drone_id: str, status: str, assignment: Optional[str] = None) -> bool:
        """Update drone directly in Google Sheets."""
        try:
            # Find the drone row
            cell = self.drone_sheet.find(drone_id)
            if not cell:
                logger.error(f"Drone {drone_id} not found in Google Sheets")
                return False
            
            row = cell.row
            
            # Get header row to find column indices
            headers = self.drone_sheet.row_values(1)
            
            status_col = None
            assignment_col = None
            
            for idx, header in enumerate(headers, 1):
                header_lower = header.lower()
                if header_lower == 'status':
                    status_col = idx
                elif header_lower in ['current_assignment', 'current assignment']:
                    assignment_col = idx
            
            # Update status
            if status_col:
                self.drone_sheet.update_cell(row, status_col, status)
                logger.info(f"Updated drone {drone_id} status to '{status}' in Google Sheets")
            
            # Update assignment
            if assignment_col:
                assignment_value = assignment if assignment else '–'
                self.drone_sheet.update_cell(row, assignment_col, assignment_value)
                logger.info(f"Updated drone {drone_id} assignment to '{assignment_value}' in Google Sheets")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating drone in Google Sheets: {e}")
            return False

    def _update_drone_in_csv(self, drone_id: str, status: str, assignment: Optional[str] = None) -> bool:
        """Update drone in CSV file (demo mode)."""
        try:
            rows = []
            with open(DRONE_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    if row.get('drone_id') == drone_id:
                        row['status'] = status
                        row['current_assignment'] = assignment if assignment else '–'
                    rows.append(row)
            
            with open(DRONE_CSV, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            logger.info(f"Updated drone {drone_id} in CSV file")
            return True
            
        except Exception as e:
            logger.error(f"Error updating drone in CSV: {e}")
            return False

    def flag_maintenance_issue(self, drone_id: str, issue_notes: str) -> bool:
        """Flag a drone for maintenance."""
        success = self.update_drone_status(drone_id, "Maintenance")
        if success:
            logger.info(f"Drone {drone_id} flagged for maintenance: {issue_notes}")
        return success

    # =====================
    # PROJECT/MISSION OPERATIONS
    # =====================
    
    def get_demo_projects(self) -> List[dict]:
        """Get all projects/missions from Google Sheets or CSV."""
        if self._use_google_sheets and self.missions_sheet:
            return self._get_projects_from_sheets()
        return self._get_projects_from_csv()

    def _get_projects_from_sheets(self) -> List[dict]:
        """Fetch projects from Google Sheets."""
        try:
            records = self.missions_sheet.get_all_records()
            projects = []
            
            for row in records:
                project = self._parse_project_row(row)
                if project:
                    projects.append(project)
            
            logger.debug(f"Fetched {len(projects)} projects from Google Sheets")
            return projects
            
        except Exception as e:
            logger.error(f"Error fetching projects from Google Sheets: {e}")
            return self._get_projects_from_csv()

    def _get_projects_from_csv(self) -> List[dict]:
        """Load projects from CSV file."""
        projects = []
        try:
            with open(MISSIONS_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    project = self._parse_project_row(row)
                    if project:
                        projects.append(project)
            logger.debug(f"Loaded {len(projects)} projects from CSV")
        except FileNotFoundError:
            logger.warning(f"Missions CSV not found at {MISSIONS_CSV}")
        except Exception as e:
            logger.error(f"Error loading projects from CSV: {e}")
        return projects

    def _parse_project_row(self, row: dict) -> Optional[dict]:
        """Parse a project/mission row."""
        try:
            project_id = row.get('project_id') or row.get('Project ID', '')
            client = row.get('client') or row.get('Client', '')
            
            if not project_id:
                return None
            
            location = row.get('location') or row.get('Location', '')
            
            # Parse required skills
            skills_str = row.get('required_skills') or row.get('Required Skills', '')
            req_skills = [s.strip() for s in skills_str.split(',') if s.strip()]
            
            # Parse required certs
            certs_str = row.get('required_certs') or row.get('Required Certs', '')
            req_certs = [c.strip() for c in certs_str.split(',') if c.strip()]
            
            # Parse dates
            start_date = self._parse_date(row.get('start_date') or row.get('Start Date', ''))
            end_date = self._parse_date(row.get('end_date') or row.get('End Date', ''))
            
            # Priority
            priority = row.get('priority') or row.get('Priority', 'Standard')
            
            # Determine skill level based on priority
            if priority == 'Urgent':
                req_skill_level = 'Advanced'
            elif priority == 'High':
                req_skill_level = 'Intermediate'
            else:
                req_skill_level = 'Intermediate'
            
            # Determine status based on dates
            today = date.today()
            if start_date and end_date:
                if today < start_date:
                    status = "Pending"
                elif today > end_date:
                    status = "Completed"
                else:
                    status = "Active"
            else:
                status = "Pending Assignment"
            
            return {
                "id": project_id.strip(),
                "name": f"{client} - {location}",
                "client": client.strip(),
                "location": location.strip(),
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "required_certifications": req_certs,
                "required_capabilities": req_skills,
                "required_skill_level": req_skill_level,
                "assigned_pilots": [],
                "assigned_drones": [],
                "status": status,
                "priority": priority.strip(),
                "notes": f"Required skills: {', '.join(req_skills)}"
            }
        except Exception as e:
            logger.error(f"Error parsing project row: {e}")
            return None

    # =====================
    # HELPER METHODS
    # =====================

    def _parse_date(self, value: str) -> Optional[date]:
        """Parse a date string into a date object."""
        if not value:
            return None
        value = str(value).strip()
        
        formats = [
            '%Y-%m-%d',      # 2026-02-05
            '%m/%d/%y',      # 2/5/26
            '%m/%d/%Y',      # 2/5/2026
            '%d/%m/%y',      # 5/2/26
            '%d/%m/%Y',      # 5/2/2026
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        
        return None
    
    def is_connected_to_sheets(self) -> bool:
        """Check if connected to Google Sheets."""
        return self._use_google_sheets
    
    def get_connection_info(self) -> dict:
        """Get information about the current data connection."""
        if self._use_google_sheets:
            return {
                "mode": "Google Sheets",
                "connected": True,
                "spreadsheet_id": os.getenv('GOOGLE_SHEET_ID'),
                "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{os.getenv('GOOGLE_SHEET_ID')}",
                "sync": "2-way (read and write)"
            }
        return {
            "mode": "Demo (CSV files)",
            "connected": False,
            "message": "Run 'python setup_google_sheets.py' to enable Google Sheets sync"
        }


# Singleton instance
_sheets_service = None

def get_sheets_service() -> GoogleSheetsService:
    global _sheets_service
    if _sheets_service is None:
        _sheets_service = GoogleSheetsService()
    return _sheets_service

def reset_sheets_service():
    """Reset the singleton to force reinitialization (useful after env changes)."""
    global _sheets_service
    _sheets_service = None
